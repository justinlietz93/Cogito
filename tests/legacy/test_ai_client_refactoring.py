"""
Test script to validate the AI client refactoring.
This script simply imports the refactored modules and verifies they work together properly.
"""

import os
import sys
from src.providers.model_config import (
    get_primary_provider, 
    get_openai_config, 
    get_anthropic_config,
    get_deepseek_config,
    get_gemini_config
)
from src.syncretic_catalyst.ai_clients import AIOrchestrator

def test_ai_orchestrator():
    """Test that the AIOrchestrator can be instantiated with different providers."""
    print("Testing AI Orchestrator initialization...")
    
    # Get primary provider
    primary = get_primary_provider()
    print(f"Primary provider from config: {primary}")
    
    # Test each provider configuration
    print("\nTesting provider configs:")
    print(f"OpenAI config: {get_openai_config()}")
    print(f"Anthropic config: {get_anthropic_config()}")
    print(f"DeepSeek config: {get_deepseek_config()}")
    print(f"Gemini config: {get_gemini_config()}")
    
    # Test orchestra initialization with different providers
    providers = ["openai", "anthropic", "deepseek", "gemini"]
    
    for provider in providers:
        print(f"\nInitializing AIOrchestrator with {provider}...")
        try:
            orchestrator = AIOrchestrator(provider)
            print(f"Success! Provider mapped to: {orchestrator.provider}")
        except Exception as e:
            print(f"Error initializing {provider}: {str(e)}")
    
    print("\nTesting default initialization...")
    try:
        orchestrator = AIOrchestrator()
        print(f"Success! Default provider: {orchestrator.provider}")
    except Exception as e:
        print(f"Error with default initialization: {str(e)}")
    
    print("\nAll tests completed!")

if __name__ == "__main__":
    test_ai_orchestrator()
