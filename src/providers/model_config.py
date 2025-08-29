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
    openai_config = api_config.get('openai', {})
    
    # Set defaults if not specified
    if 'model' not in openai_config:
        openai_config['model'] = 'o3-mini'
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


@cache_result(ttl=60)  # Cache for 60 seconds
def get_openrouter_config() -> Dict[str, Any]:
    """
    Get OpenRouter model configuration from the unified YAML config.

    Returns:
        Dictionary containing OpenRouter configuration settings
    """
    api_config = get_api_config()
    openrouter_config = api_config.get('openrouter', {})

    # Set defaults if not specified
    if 'model' not in openrouter_config:
        openrouter_config['model'] = 'x-ai/grok-4'
    if 'max_tokens' not in openrouter_config:
        openrouter_config['max_tokens'] = 8192
    if 'temperature' not in openrouter_config:
        openrouter_config['temperature'] = 0.2
    if 'retries' not in openrouter_config:
        openrouter_config['retries'] = 3
    if 'api_base' not in openrouter_config:
        openrouter_config['api_base'] = os.getenv('OPENROUTER_API_BASE', 'https://openrouter.ai/api/v1')

    # Resolve API key from environment
    if 'api_key' not in openrouter_config:
        openrouter_config['api_key'] = os.getenv('OPENROUTER_API_KEY')

    return openrouter_config


@cache_result(ttl=60)  # Cache for 60 seconds
def get_xai_config() -> Dict[str, Any]:
    """
    Get XAI (Groq/X.ai) model configuration from the unified YAML config.

    Returns:
        Dictionary containing XAI configuration settings
    """
    api_config = get_api_config()
    xai_config = api_config.get('xai', {})

    # Set defaults if not specified
    if 'model' not in xai_config:
        xai_config['model'] = 'grok-1'
    if 'max_tokens' not in xai_config:
        xai_config['max_tokens'] = 8192
    if 'temperature' not in xai_config:
        xai_config['temperature'] = 0.2
    if 'retries' not in xai_config:
        xai_config['retries'] = 3

    # Resolve API key from environment
    if 'api_key' not in xai_config:
        xai_config['api_key'] = os.getenv('XAI_API_KEY')

    return xai_config

@cache_result(ttl=60)  # Cache for 60 seconds
def get_ollama_config() -> Dict[str, Any]:
    """
    Get Ollama (local inference) configuration from the unified YAML config.

    Returns:
        Dictionary containing Ollama configuration settings:
        {
          'model': 'llama3.1',
          'max_tokens': 8192,
          'temperature': 0.2,
          'host': 'http://localhost:11434'  # or env OLLAMA_HOST
        }
    """
    api_config = get_api_config()
    ollama_cfg = dict(api_config.get('ollama', {}) or {})

    # Defaults
    if 'model' not in ollama_cfg:
        ollama_cfg['model'] = 'gpt-oss:120b'
    if 'max_tokens' not in ollama_cfg:
        ollama_cfg['max_tokens'] = 8192
    if 'temperature' not in ollama_cfg:
        ollama_cfg['temperature'] = 0.2

    # Host preference: config overrides env only if explicitly set; otherwise use env or default
    env_host = os.getenv('OLLAMA_HOST')
    if not ollama_cfg.get('host'):
        ollama_cfg['host'] = env_host or 'http://localhost:11434'

    return ollama_cfg
