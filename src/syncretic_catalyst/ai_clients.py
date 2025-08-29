"""
ai_clients.py

Interface for calling AI providers:
1) Anthropic (Claude models)
2) DeepSeek (API models)
3) OpenAI (GPT models)
4) Gemini (Google's models)

This module acts as an interface to the provider implementations in src/providers/
and maintains a consistent API for the rest of the Syncretic Catalyst code.
All models are selected based on the root configuration file.
"""

import logging
from typing import List, Dict, Any, Optional, Union

# Import the model configuration
from src.providers.model_config import get_primary_provider

# Import provider implementations with unified interfaces
from src.providers import anthropic_client, deepseek_client, openai_client, gemini_client, xai_client, openrouter_client, ollama_client

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get primary provider from config
PRIMARY_PROVIDER = get_primary_provider()
logger.info(f"Using primary provider from config: {PRIMARY_PROVIDER}")

class AIOrchestrator:
    """
    An orchestrator that selects the appropriate AI provider
    based on the root configuration and calls the run method.
    """

    def __init__(self, model_name: Optional[str] = None):
        """
        Initialize the orchestrator with the specified model.
        
        Args:
            model_name: Optional override for model name. If not provided, uses the primary_provider from config.
                       Supported values: "claude", "anthropic", "deepseek", "openai", "gemini", "openrouter", "ollama"
        """
        # If model_name not provided, use the primary provider from config
        self.model_name = model_name.lower() if model_name else PRIMARY_PROVIDER
        
        # Map model names to their normalized form
        if self.model_name == "claude37sonnet" or self.model_name == "claude":
            self.provider = "anthropic"
        elif self.model_name == "deepseekr1" or self.model_name == "deepseek":
            self.provider = "deepseek"
        elif self.model_name == "openai":
            self.provider = "openai"
        elif self.model_name == "gemini":
            self.provider = "gemini"
        elif self.model_name == "xai":
            self.provider = "xai"
        elif self.model_name == "openrouter":
            self.provider = "openrouter"
        elif self.model_name == "ollama":
            self.provider = "ollama"
        else:
            logger.warning(f"Unknown model: {self.model_name}, falling back to default: {PRIMARY_PROVIDER}")
            self.__init__(PRIMARY_PROVIDER)  # Reinitialize with default provider
            return
            
        logger.info(f"Using {self.provider} as the LLM provider")

    def call_llm(self, system_prompt: str, user_prompt: str, max_tokens: int = 8192, step_number: int = 0) -> str:
        """
        Call the LLM with system and user prompts.
        
        Args:
            system_prompt: System prompt
            user_prompt: User prompt
            max_tokens: Maximum tokens in the response
            step_number: Current step number for logging
            
        Returns:
            Response from the LLM
        """
        logger.info(f"Processing step number: {step_number}")
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        # Call the appropriate provider based on the selected provider
        if self.provider == "anthropic":
            return anthropic_client.run_anthropic_client(
                messages=messages,
                max_tokens=max_tokens,
                enable_thinking=False
            )
        elif self.provider == "deepseek":
            return deepseek_client.run_deepseek_client(
                messages=messages,
                max_tokens=max_tokens
            )
        elif self.provider == "openai":
            return openai_client.run_openai_client(
                messages=messages,
                max_tokens=max_tokens
            )
        elif self.provider == "gemini":
            return gemini_client.run_gemini_client(
                messages=messages,
                max_tokens=max_tokens
            )
        elif self.provider == "xai":
            return xai_client.run_xai_client(
                messages=messages,
                max_tokens=max_tokens
            )
        elif self.provider == "openrouter":
            return openrouter_client.run_openrouter_client(
                messages=messages,
                max_tokens=max_tokens
            )
        elif self.provider == "ollama":
            return ollama_client.run_ollama_client(
                messages=messages,
                max_tokens=max_tokens
            )
        else:
            # This should never happen due to the initialization checks
            error_msg = f"Unknown provider: {self.provider}"
            logger.error(error_msg)
            return error_msg
