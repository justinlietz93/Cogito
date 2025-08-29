"""
Client interface for OpenRouter API.
"""

import logging
from typing import Dict, Any, List, Optional
from openai import OpenAI
from .model_config import get_openrouter_config

logger = logging.getLogger(__name__)

def normalize_openrouter_model_name(model_name: str) -> str:
    """
    Normalize model slugs for OpenRouter:
    - If no vendor prefix and the name starts with 'gpt-5', prefix with 'openai/'.
    - Otherwise leave unchanged.
    """
    if not model_name:
        return model_name
    name = model_name.strip()
    lower = name.lower()
    if "/" not in lower and lower.startswith("gpt-5"):
        return f"openai/{name}"
    return name


def run_openrouter_client(
    messages: List[Dict[str, str]],
    model_name: Optional[str] = None,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None
) -> str:
    """
    High-level function to run the OpenRouter client.
    """
    try:
        config = get_openrouter_config()
        
        client = OpenAI(
            base_url=config["api_base"],
            api_key=config["api_key"],
        )
        
        raw_model = model_name or config["model"]
        model = normalize_openrouter_model_name(raw_model)
        max_tokens_to_use = max_tokens or config["max_tokens"]
        temp_to_use = temperature if temperature is not None else config["temperature"]
        
        logger.info(f"Using OpenRouter model: {model} with temperature: {temp_to_use}")
        
        chat_completion = client.chat.completions.create(
            messages=messages,
            model=model,
            temperature=temp_to_use,
            max_tokens=max_tokens_to_use,
        )
        
        response = chat_completion.choices[0].message.content
        logger.info(f"OpenRouter response received from {model} - length: {len(response)} characters")
        return response
        
    except Exception as e:
        error_msg = f"ERROR from OpenRouter: {str(e)}"
        logger.error(error_msg)
        import traceback
        traceback.print_exc()
        return error_msg