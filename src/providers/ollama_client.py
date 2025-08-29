"""
Ollama client integration.

Provides a minimal, robust wrapper to call a local Ollama server via its /api/chat endpoint.
- Default host is read from config (api.ollama.host) or env OLLAMA_HOST; falls back to http://localhost:11434
- No API key is required.
- Message format matches the rest of the providers: [{"role": "system"|"user"|"assistant", "content": "..."}]

References:
- https://github.com/ollama/ollama/blob/main/docs/api.md#chat
"""

from __future__ import annotations

import os
import json
import logging
from typing import Any, Dict, List, Optional

import requests

from .model_config import get_ollama_config

logger = logging.getLogger(__name__)


def _normalize_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """
    Ensure messages conform to Ollama chat schema:
    [{"role": "system"|"user"|"assistant", "content": "text"}]
    """
    norm: List[Dict[str, str]] = []
    for i, m in enumerate(messages or []):
        role = str(m.get("role", "user")).lower()
        content = m.get("content", "")
        if not isinstance(content, str):
            try:
                content = json.dumps(content, ensure_ascii=False)
            except Exception:
                content = str(content)
        norm.append({"role": role, "content": content})
    return norm


def run_ollama_client(
    messages: List[Dict[str, Any]],
    model_name: Optional[str] = None,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
    host: Optional[str] = None,
    timeout_seconds: float = 120.0,
) -> str:
    """
    High-level function to call a local Ollama server.

    Args:
        messages: List of chat messages with roles and content
        model_name: Optional override of model; defaults to config api.ollama.model
        max_tokens: Optional override; mapped to Ollama 'num_predict'
        temperature: Optional override; defaults to config
        host: Optional Ollama base URL; defaults to env/config. Example: http://localhost:11434
        timeout_seconds: Request timeout

    Returns:
        Assistant text content string.

    Raises:
        RuntimeError on HTTP errors or missing/invalid responses.
    """
    cfg = get_ollama_config() or {}
    base_url = (host or cfg.get("host") or os.getenv("OLLAMA_HOST") or "http://localhost:11434").rstrip("/")
    model = model_name or cfg.get("model") or "llama3.1"
    temp = temperature if temperature is not None else cfg.get("temperature", 0.2)
    # Ollama uses num_predict for output token limit; if None, let Ollama decide
    num_predict = max_tokens if max_tokens is not None else cfg.get("max_tokens", None)

    payload: Dict[str, Any] = {
        "model": model,
        "messages": _normalize_messages(messages),
        "stream": False,
        "options": {
            # Map to Ollama options
            "temperature": float(temp) if temp is not None else 0.2,
        },
    }
    if num_predict is not None:
        try:
            payload["options"]["num_predict"] = int(num_predict)
        except Exception:
            logger.warning(f"Invalid num_predict value provided: {num_predict} (ignoring)")

    url = f"{base_url}/api/chat"
    logger.info(f"Ollama request -> {url} (model={model}, temp={temp}, num_predict={payload['options'].get('num_predict')})")

    try:
        resp = requests.post(url, json=payload, timeout=timeout_seconds)
    except Exception as e:
        msg = f"Failed to connect to Ollama at {url}: {e}"
        logger.error(msg)
        raise RuntimeError(msg) from e

    if resp.status_code != 200:
        msg = f"Ollama returned HTTP {resp.status_code}: {resp.text[:512]}"
        logger.error(msg)
        raise RuntimeError(msg)

    try:
        data = resp.json()
    except Exception as e:
        msg = f"Failed to parse JSON response from Ollama: {e} | raw={resp.text[:512]}"
        logger.error(msg)
        raise RuntimeError(msg) from e

    # Non-streaming /api/chat typically returns:
    # {
    #   "model": "...",
    #   "created_at": "...",
    #   "message": {"role": "assistant", "content": "..."},
    #   "done": true,
    #   ...
    # }
    text = None
    if isinstance(data, dict):
        if "message" in data and isinstance(data["message"], dict):
            text = data["message"].get("content")
        elif "response" in data:
            # Some endpoints (like /api/generate) use 'response'
            text = data.get("response")
        elif "choices" in data:
            # Fallback for OpenAI-like shapes (just in case)
            try:
                text = data["choices"][0]["message"]["content"]
            except Exception:
                pass

    if not text:
        msg = f"Ollama response did not contain message content. Keys={list(data.keys()) if isinstance(data, dict) else type(data)}"
        logger.error(msg)
        raise RuntimeError(msg)

    logger.info(f"Ollama response length: {len(text)} chars")
    return text