"""NVIDIA text embeddings via OpenAI-compatible SDK.

Model: `nvidia/nv-embedqa-e5-v5` — 1024 dim.
"""
from __future__ import annotations

import logging
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

MODEL = "nvidia/nv-embedqa-e5-v5"
DIM = 1024

_client: OpenAI | None = None

def _get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.environ.get("NVIDIA_API_KEY")
        if not api_key:
            return None
        _client = OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=api_key
        )
    return _client

def embed(text: str, task_type: str = "query") -> list[float] | None:
    """Compute an embedding vector for `text`. Returns None on any failure."""
    if not text or not text.strip():
        return None
    client = _get_client()
    if not client:
        return None
    
    try:
        # task_type mapping if needed, NVIDIA uses query/passage usually.
        # But we'll just use the default.
        resp = client.embeddings.create(
            input=[text[:2000]],
            model=MODEL,
            encoding_format="float",
        )
        return resp.data[0].embedding
    except Exception as exc:
        logger.debug("[nvidia_embed] failed: %s", exc)
        return None

def is_available() -> bool:
    return os.environ.get("NVIDIA_API_KEY") is not None
