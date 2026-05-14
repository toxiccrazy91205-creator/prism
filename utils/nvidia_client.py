from __future__ import annotations

import os
import time
import base64
import json
import logging
from typing import Any, List, Optional

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Default models (NVIDIA-hosted)
DEFAULT_MODEL = "meta/llama-3.1-70b-instruct"
FAST_MODEL = "meta/llama-3.1-8b-instruct"
VISION_MODEL = "meta/llama-3.2-11b-vision-instruct"

_client: OpenAI | None = None
_logger = logging.getLogger(__name__)

class _FakeUsage:
    def __init__(self, prompt_tokens: int, completion_tokens: int):
        self.input_tokens = prompt_tokens
        self.output_tokens = completion_tokens

class _FakeBlock:
    def __init__(self, block_dict: dict):
        self.type = block_dict.get("type")
        self.text = block_dict.get("text")
        self.id = block_dict.get("id")
        self.name = block_dict.get("name")
        self.input = block_dict.get("input")

class _FakeMessage:
    def __init__(self, content: List[_FakeBlock], stop_reason: str, usage: _FakeUsage):
        self.content = content
        self.stop_reason = stop_reason
        self.usage = usage

def _record(resp: Any, model: str, call_type: str) -> None:
    """Persist a cost_ledger row. Fail-silent."""
    try:
        from utils import cost_tracker
        usage = getattr(resp, "usage", None)
        cost_tracker.record(
            "nvidia",
            tokens_in=getattr(usage, "prompt_tokens", 0) or 0,
            tokens_out=getattr(usage, "completion_tokens", 0) or 0,
            call_type=call_type,
            model=model,
        )
    except Exception:
        pass

def _get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.environ.get("NVIDIA_API_KEY")
        if not api_key:
            raise RuntimeError(
                "NVIDIA_API_KEY not set. Add it to your .env file."
            )
        _client = OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=api_key
        )
    return _client

def ask(
    prompt: str,
    max_tokens: int = 1024,
    model: str = DEFAULT_MODEL,
    system: str = "",
    retries: int = 3,
) -> str:
    """Call NVIDIA NIM and return the text response."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    for attempt in range(retries):
        try:
            resp = _get_client().chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
            )
            _record(resp, model, "synthesis")
            return resp.choices[0].message.content or ""
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt * 2)
                continue
            _logger.error(f"[nvidia] ask failed: {e}")
            raise

def ask_fast(prompt: str, max_tokens: int = 512) -> str:
    """Use the fast model for low-stakes tasks."""
    return ask(prompt, max_tokens=max_tokens, model=FAST_MODEL)

def ask_vision(
    prompt: str,
    image_bytes: bytes,
    media_type: str = "image/png",
    max_tokens: int = 512,
    model: str = VISION_MODEL,
    system: str = "",
    retries: int = 3,
) -> str:
    """Send an image + text prompt to NVIDIA vision models."""
    img_b64 = base64.b64encode(image_bytes).decode("utf-8")
    
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    
    messages.append({
        "role": "user",
        "content": [
            {"type": "text", "text": prompt},
            {
                "type": "image_url",
                "image_url": {"url": f"data:{media_type};base64,{img_b64}"}
            },
        ],
    })

    for attempt in range(retries):
        try:
            resp = _get_client().chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
            )
            _record(resp, model, "vision")
            return resp.choices[0].message.content or ""
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt * 2)
                continue
            _logger.error(f"[nvidia-vision] ask_vision failed: {e}")
            raise

def ask_with_tools(
    messages: list[dict],
    tools: list[dict],
    system: str = "",
    model: str = DEFAULT_MODEL,
    max_tokens: int = 4096,
    retries: int = 3,
) -> Any:
    """Call NVIDIA NIM with tool definitions. Returns an NVIDIA-compatible Message object."""
    formatted_messages = []
    if system:
        formatted_messages.append({"role": "system", "content": system})
    
    # Map NVIDIA message format to OpenAI
    for m in messages:
        role = m.get("role")
        content = m.get("content")
        
        if isinstance(content, list):
            # Handle tool_result/tool_use blocks
            new_content = []
            for block in content:
                if block.get("type") == "tool_result":
                    formatted_messages.append({
                        "role": "tool",
                        "tool_call_id": block.get("tool_use_id"),
                        "content": str(block.get("content")),
                    })
                elif block.get("type") == "tool_use":
                    # This shouldn't happen from user role usually, but just in case
                    pass
                else:
                    new_content.append(block)
            if new_content:
                formatted_messages.append({"role": role, "content": new_content})
        else:
            formatted_messages.append({"role": role, "content": content})

    # Map NVIDIA tool definitions to OpenAI
    openai_tools = []
    for t in tools:
        openai_tools.append({
            "type": "function",
            "function": {
                "name": t.get("name"),
                "description": t.get("description", ""),
                "parameters": t.get("input_schema", {}),
            }
        })

    for attempt in range(retries):
        try:
            resp = _get_client().chat.completions.create(
                model=model,
                messages=formatted_messages,
                tools=openai_tools if openai_tools else None,
                max_tokens=max_tokens,
            )
            
            # Map OpenAI response back to NVIDIA-compatible _FakeMessage
            msg = resp.choices[0].message
            content_blocks = []
            
            if msg.content:
                content_blocks.append(_FakeBlock({"type": "text", "text": msg.content}))
            
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    content_blocks.append(_FakeBlock({
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.function.name,
                        "input": json.loads(tc.function.arguments),
                    }))
            
            stop_reason = "end_turn"
            if msg.tool_calls:
                stop_reason = "tool_use"
            elif resp.finish_reason == "length":
                stop_reason = "max_tokens"

            return _FakeMessage(
                content=content_blocks,
                stop_reason=stop_reason,
                usage=_FakeUsage(
                    prompt_tokens=resp.usage.prompt_tokens,
                    completion_tokens=resp.usage.completion_tokens
                )
            )
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt * 2)
                continue
            _logger.error(f"[nvidia-tools] ask_with_tools failed: {e}")
            raise
