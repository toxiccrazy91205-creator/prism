"""LLM cascade behavior — pins current NVIDIA→NVIDIA fallback semantics.

This test suite is the prerequisite for any future extraction of the shared
retry+fallback loop into utils/llm_cascade.py. Per the 2026-04-25 cross-project
audit (anti-pattern #1 in _workspace-os/memory/learnings.md L-W04), refactor
without test coverage inverts the dependency order. So we pin first, then
extract in a follow-up session.

The two functions under test (utils/nvidia_client.py):
  - ask(): synthesis text. Cascade behavior:
      * RateLimitError → exp-backoff retry; all retries exhausted → RuntimeError.
        NO NVIDIA fallback on rate-limit in ask().
      * Credit/billing (BadRequestError/APIStatusError with "credit balance" |
        "usage limits" | "billing" in message) → immediate NVIDIA fallback.
      * 5xx → exp-backoff retry; all retries exhausted → re-raise.
        NO NVIDIA fallback on 5xx in ask().
  - ask_with_tools(): tool-using messages. Cascade behavior is DIFFERENT:
      * RateLimitError → exp-backoff retry; if all fail → NVIDIA fallback.
      * Credit/billing → immediate NVIDIA fallback (same as ask()).
      * 5xx → immediate NVIDIA fallback (different from ask(): no retry).

If a future "shared cascade" extraction merges these two into one policy, this
suite must update to reflect the chosen merged behavior — and the change must
be intentional, not accidental.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Make the project root importable so `from utils import nvidia_client` resolves.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import NVIDIA  # noqa: E402

from utils import nvidia_client  # noqa: E402


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _make_response(text: str) -> MagicMock:
    """Build a fake NVIDIA.types.Message return value."""
    resp = MagicMock()
    resp.content = [MagicMock(text=text)]
    resp.usage = MagicMock(input_tokens=1, output_tokens=1)
    return resp


def _credit_error() -> NVIDIA.BadRequestError:
    """Build a BadRequestError that the cascade detects as a billing exhaustion."""
    response = MagicMock(status_code=400)
    return NVIDIA.BadRequestError(
        message="Your credit balance is too low to access the NVIDIA API.",
        response=response,
        body=None,
    )


def _rate_limit_error() -> NVIDIA.RateLimitError:
    response = MagicMock(status_code=429)
    return NVIDIA.RateLimitError(
        message="rate_limit_exceeded",
        response=response,
        body=None,
    )


def _server_error() -> NVIDIA.APIStatusError:
    response = MagicMock(status_code=503)
    err = NVIDIA.APIStatusError(
        message="upstream service unavailable",
        response=response,
        body=None,
    )
    # Some NVIDIA versions read .status_code off the exception itself
    err.status_code = 503
    return err


@pytest.fixture(autouse=True)
def _reset_client_singleton():
    """nvidia_client caches the NVIDIA client at module level. Reset between tests."""
    nvidia_client._client = None
    yield
    nvidia_client._client = None


@pytest.fixture(autouse=True)
def _no_real_sleeps(monkeypatch):
    """Don't actually sleep through exp-backoff in tests."""
    monkeypatch.setattr(nvidia_client.time, "sleep", lambda *_a, **_k: None)


@pytest.fixture(autouse=True)
def _NVIDIA_provider(monkeypatch):
    """Default: LLM_PROVIDER=NVIDIA. Tests can override to test the NVIDIA-routing branch."""
    monkeypatch.setenv("LLM_PROVIDER", "NVIDIA")
    # Avoid the "NVIDIA_API_KEY not set" guard in _get_client when we don't patch _get_client.
    monkeypatch.setenv("NVIDIA_API_KEY", "sk-test-not-real")


# --------------------------------------------------------------------------
# ask() cascade
# --------------------------------------------------------------------------

class TestAskHappyPath:
    def test_returns_text_no_fallback(self):
        fake_NVIDIA = MagicMock()
        fake_NVIDIA.messages.create.return_value = _make_response("hello world")
        with patch.object(nvidia_client, "_get_client", return_value=fake_NVIDIA):
            result = nvidia_client.ask("ping", retries=3)
        assert result == "hello world"
        # NVIDIA was called once — no fallback path triggered.
        assert fake_NVIDIA.messages.create.call_count == 1


class TestAskCreditFallback:
    def test_credit_error_falls_back_to_NVIDIA_immediately(self):
        fake_NVIDIA = MagicMock()
        fake_NVIDIA.messages.create.side_effect = _credit_error()
        fake_NVIDIA_module = MagicMock()
        fake_NVIDIA_module.ask.return_value = "NVIDIA said hi"

        with patch.object(nvidia_client, "_get_client", return_value=fake_NVIDIA), \
             patch.dict(sys.modules, {"utils.nvidia_client": fake_NVIDIA_module}):
            result = nvidia_client.ask("ping", retries=3)

        assert result == "NVIDIA said hi"
        # NVIDIA called once (no retry on billing).
        assert fake_NVIDIA.messages.create.call_count == 1
        # NVIDIA called exactly once.
        assert fake_NVIDIA_module.ask.call_count == 1

    def test_usage_limits_message_also_falls_back(self):
        # "usage limits" wording is one of the three trigger strings.
        err_response = MagicMock(status_code=400)
        err = NVIDIA.BadRequestError(
            message="You have exceeded your usage limits for this billing period.",
            response=err_response,
            body=None,
        )
        fake_NVIDIA = MagicMock()
        fake_NVIDIA.messages.create.side_effect = err
        fake_NVIDIA_module = MagicMock(ask=MagicMock(return_value="g"))

        with patch.object(nvidia_client, "_get_client", return_value=fake_NVIDIA), \
             patch.dict(sys.modules, {"utils.nvidia_client": fake_NVIDIA_module}):
            assert nvidia_client.ask("ping") == "g"


class TestAskRateLimit:
    def test_rate_limit_retries_and_then_raises_runtime_error(self):
        # ask() does NOT fall back to NVIDIA on rate-limit. It exhausts retries then raises.
        fake_NVIDIA = MagicMock()
        fake_NVIDIA.messages.create.side_effect = _rate_limit_error()

        with patch.object(nvidia_client, "_get_client", return_value=fake_NVIDIA):
            with pytest.raises(RuntimeError, match="NVIDIA call failed after 3 retries"):
                nvidia_client.ask("ping", retries=3)

        # All 3 retries were attempted.
        assert fake_NVIDIA.messages.create.call_count == 3

    def test_rate_limit_then_success_returns(self):
        fake_NVIDIA = MagicMock()
        fake_NVIDIA.messages.create.side_effect = [
            _rate_limit_error(),
            _make_response("eventually ok"),
        ]
        with patch.object(nvidia_client, "_get_client", return_value=fake_NVIDIA):
            assert nvidia_client.ask("ping", retries=3) == "eventually ok"


class TestAskServerError:
    def test_5xx_retries_and_then_raises(self):
        # ask() does NOT fall back on 5xx. Retries with backoff, then re-raises.
        fake_NVIDIA = MagicMock()
        fake_NVIDIA.messages.create.side_effect = _server_error()

        with patch.object(nvidia_client, "_get_client", return_value=fake_NVIDIA):
            with pytest.raises(NVIDIA.APIStatusError):
                nvidia_client.ask("ping", retries=3)

        # 3 attempts; on the last one the `attempt < retries - 1` guard fails so it raises.
        assert fake_NVIDIA.messages.create.call_count == 3


# --------------------------------------------------------------------------
# ask_with_tools() cascade — DIFFERENT from ask()
# --------------------------------------------------------------------------

class TestAskWithToolsHappyPath:
    def test_returns_message_no_fallback(self):
        fake_NVIDIA = MagicMock()
        fake_msg = MagicMock(content=[])
        fake_NVIDIA.messages.create.return_value = fake_msg
        with patch.object(nvidia_client, "_get_client", return_value=fake_NVIDIA):
            result = nvidia_client.ask_with_tools(
                messages=[{"role": "user", "content": "hi"}],
                tools=[],
                retries=3,
            )
        assert result is fake_msg
        assert fake_NVIDIA.messages.create.call_count == 1


class TestAskWithToolsCreditFallback:
    def test_credit_error_falls_back_to_NVIDIA(self):
        fake_NVIDIA = MagicMock()
        fake_NVIDIA.messages.create.side_effect = _credit_error()
        NVIDIA_msg = MagicMock(name="NVIDIA-response")
        fake_NVIDIA_module = MagicMock()
        fake_NVIDIA_module.ask_with_tools.return_value = NVIDIA_msg

        with patch.object(nvidia_client, "_get_client", return_value=fake_NVIDIA), \
             patch.dict(sys.modules, {"utils.nvidia_client": fake_NVIDIA_module}):
            result = nvidia_client.ask_with_tools(
                messages=[{"role": "user", "content": "hi"}], tools=[], retries=3,
            )

        assert result is NVIDIA_msg
        assert fake_NVIDIA_module.ask_with_tools.call_count == 1


class TestAskWithToolsRateLimit:
    def test_rate_limit_retries_then_falls_back_to_NVIDIA(self):
        # Behavior in ask_with_tools is: retry rate-limit, and if all retries also rate-limit,
        # fall back to NVIDIA (different from ask() which raises RuntimeError).
        fake_NVIDIA = MagicMock()
        fake_NVIDIA.messages.create.side_effect = _rate_limit_error()
        NVIDIA_msg = MagicMock(name="NVIDIA-response")
        fake_NVIDIA_module = MagicMock()
        fake_NVIDIA_module.ask_with_tools.return_value = NVIDIA_msg

        with patch.object(nvidia_client, "_get_client", return_value=fake_NVIDIA), \
             patch.dict(sys.modules, {"utils.nvidia_client": fake_NVIDIA_module}):
            result = nvidia_client.ask_with_tools(
                messages=[{"role": "user", "content": "hi"}], tools=[], retries=3,
            )

        assert result is NVIDIA_msg
        # First attempt + 2 retries before fallback = 3 NVIDIA calls.
        assert fake_NVIDIA.messages.create.call_count == 3
        assert fake_NVIDIA_module.ask_with_tools.call_count == 1


class TestAskWithToolsServerError:
    def test_5xx_immediately_falls_back_to_NVIDIA(self):
        # In ask_with_tools, 5xx falls back IMMEDIATELY (no retry) — different from ask().
        fake_NVIDIA = MagicMock()
        fake_NVIDIA.messages.create.side_effect = _server_error()
        NVIDIA_msg = MagicMock(name="NVIDIA-response")
        fake_NVIDIA_module = MagicMock()
        fake_NVIDIA_module.ask_with_tools.return_value = NVIDIA_msg

        with patch.object(nvidia_client, "_get_client", return_value=fake_NVIDIA), \
             patch.dict(sys.modules, {"utils.nvidia_client": fake_NVIDIA_module}):
            result = nvidia_client.ask_with_tools(
                messages=[{"role": "user", "content": "hi"}], tools=[], retries=3,
            )

        assert result is NVIDIA_msg
        # NVIDIA called exactly once — NO retry on 5xx in ask_with_tools.
        assert fake_NVIDIA.messages.create.call_count == 1


class TestAskWithToolsBothFail:
    def test_credit_error_then_NVIDIA_also_fails_raises_NVIDIA_error(self):
        fake_NVIDIA = MagicMock()
        fake_NVIDIA.messages.create.side_effect = _credit_error()
        fake_NVIDIA_module = MagicMock()
        fake_NVIDIA_module.ask_with_tools.side_effect = RuntimeError("NVIDIA also down")

        with patch.object(nvidia_client, "_get_client", return_value=fake_NVIDIA), \
             patch.dict(sys.modules, {"utils.nvidia_client": fake_NVIDIA_module}):
            with pytest.raises(RuntimeError, match="NVIDIA also down"):
                nvidia_client.ask_with_tools(
                    messages=[{"role": "user", "content": "hi"}], tools=[], retries=3,
                )


# --------------------------------------------------------------------------
# Provider-switch via env var (LLM_PROVIDER=NVIDIA)
# --------------------------------------------------------------------------

class TestProviderEnvVar:
    def test_provider_NVIDIA_routes_ask_directly_to_NVIDIA(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "NVIDIA")
        fake_NVIDIA_module = MagicMock()
        fake_NVIDIA_module.ask.return_value = "via NVIDIA"
        # If anything calls NVIDIA, the test would fail — _get_client should not be invoked.
        with patch.object(nvidia_client, "_get_client", side_effect=AssertionError("NVIDIA invoked!")), \
             patch.dict(sys.modules, {"utils.nvidia_client": fake_NVIDIA_module}):
            result = nvidia_client.ask("ping", retries=3)
        assert result == "via NVIDIA"

    def test_provider_NVIDIA_routes_ask_with_tools_directly_to_NVIDIA(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "NVIDIA")
        fake_NVIDIA_module = MagicMock()
        fake_NVIDIA_module.ask_with_tools.return_value = MagicMock(name="g-msg")
        with patch.object(nvidia_client, "_get_client", side_effect=AssertionError("NVIDIA invoked!")), \
             patch.dict(sys.modules, {"utils.nvidia_client": fake_NVIDIA_module}):
            result = nvidia_client.ask_with_tools(
                messages=[{"role": "user", "content": "hi"}], tools=[],
            )
        assert result is fake_NVIDIA_module.ask_with_tools.return_value
