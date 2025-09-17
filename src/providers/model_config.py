"""
Model configuration for AI providers.

This module centralizes access to model configuration settings from config.yaml.
It provides utilities for accessing model-specific settings for each provider.
"""

import os
import logging
from typing import Dict, Any, Optional

# Import the config loader and decorators
from src.config_loader import config_loader
from .decorators import cache_result

logger = logging.getLogger(__name__)

@cache_result(ttl=60)  # Cache for 60 seconds
def get_primary_provider() -> str:
    """
    Get the primary provider from config.
    
    Returns:
        String identifier for the primary provider ("openai", "anthropic", etc.)
    """
    return config_loader.get('api', 'primary_provider', 'openai')

@cache_result(ttl=60)  # Cache for 60 seconds
def get_api_config() -> Dict[str, Any]:
    """
    Get the entire API configuration section.
    
    Returns:
        Dictionary containing all API configurations
    """
    return config_loader.get_api_config()

@cache_result(ttl=60)  # Cache for 60 seconds
def get_anthropic_config() -> Dict[str, Any]:
    """
    Get Anthropic model configuration.
    
    Returns:
        Dictionary containing Anthropic configuration settings
    """
    api_config = get_api_config()
    return api_config.get('anthropic', {})

@cache_result(ttl=60)  # Cache for 60 seconds
def get_deepseek_config() -> Dict[str, Any]:
    """
    Get DeepSeek model configuration.
    
    Returns:
        Dictionary containing DeepSeek configuration settings
    """
    api_config = get_api_config()
    deepseek_config = api_config.get('deepseek', {})
    
    # Set defaults if not specified
    if 'model_name' not in deepseek_config:
        deepseek_config['model_name'] = 'deepseek-reasoner'
    if 'base_url' not in deepseek_config:
        deepseek_config['base_url'] = 'https://api.deepseek.com/v1'
    
    return deepseek_config

@cache_result(ttl=60)  # Cache for 60 seconds
def get_openai_config() -> Dict[str, Any]:
    """
    Get OpenAI model configuration.
    
    Returns:
        Dictionary containing OpenAI configuration settings
    """
    api_config = get_api_config()
    openai_config = dict(api_config.get('openai', {}))

    # Allow environment variables to override or supply defaults so deployments
    # can select any available model without editing source templates.
    env_model = os.getenv('OPENAI_MODEL') or os.getenv('OPENAI_DEFAULT_MODEL')
    if env_model:
        openai_config.setdefault('model', env_model)
    else:
        openai_config.setdefault('model', 'gpt-4o-mini')
    if 'max_tokens' not in openai_config:
        openai_config['max_tokens'] = 8192
    if 'temperature' not in openai_config:
        openai_config['temperature'] = 0.2
        
    return openai_config

@cache_result(ttl=60)  # Cache for 60 seconds
def get_gemini_config() -> Dict[str, Any]:
    """
    Get Gemini model configuration.
    
    Returns:
        Dictionary containing Gemini configuration settings
    """
    api_config = get_api_config()
    gemini_config = api_config.get('gemini', {})
    
    # Set defaults if not specified
    if 'model_name' not in gemini_config:
        gemini_config['model_name'] = 'gemini-2.5-pro-exp-03-25'
    if 'max_output_tokens' not in gemini_config:
        gemini_config['max_output_tokens'] = 8192
    if 'temperature' not in gemini_config:
        gemini_config['temperature'] = 0.6
        
    return gemini_config
