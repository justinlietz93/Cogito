"""
Client interface for XAI API.
"""

import logging
from typing import Dict, Any, List, Optional
from groq import Groq
from .model_config import get_xai_config

logger = logging.getLogger(__name__)


def run_xai_client(
    messages: List[Dict[str, str]],
    model_name: Optional[str] = None,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None
) -> str:
    """
    High-level function to run the XAI client.
    """
    try:
        config = get_xai_config()
        
        client = Groq(api_key=config["api_key"])
        
        model = model_name or config["model"]
        max_tokens_to_use = max_tokens or config["max_tokens"]
        temp_to_use = temperature if temperature is not None else config["temperature"]
        
        logger.info(f"Using XAI model: {model} with temperature: {temp_to_use}")
        
        chat_completion = client.chat.completions.create(
            messages=messages,
            model=model,
            temperature=temp_to_use,
            max_tokens=max_tokens_to_use,
        )
        
        response = chat_completion.choices[0].message.content
        logger.info(f"XAI response received from {model} - length: {len(response)} characters")
        return response
        
    except Exception as e:
        error_msg = f"ERROR from XAI: {str(e)}"
        logger.error(error_msg)
        import traceback
        traceback.print_exc()
        return error_msg