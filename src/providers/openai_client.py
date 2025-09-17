"""
Client interface for OpenAI API.
Provides functions to call OpenAI models with retry logic and high-level interface.
"""

import logging
import json
import time
import os
from typing import Dict, Any, Tuple, Optional, List, Union
from openai import OpenAI
from .exceptions import ModelCallError, MaxRetriesExceededError

# Import the model configuration and decorators
from .model_config import get_openai_config
from .decorators import with_retry, with_error_handling, cache_result

logger = logging.getLogger(__name__)

@with_error_handling
@with_retry(max_attempts=3, delay_base=2.0)
def call_openai_with_retry(
    prompt_template: str,
    context: Dict[str, Any],
    config: Dict[str, Any],
    is_structured: bool = False,
    **kwargs
) -> Tuple[Union[str, Dict[str, Any]], str]:
    """
    Calls OpenAI API with the given prompt template and context.
    Implements retry logic for transient errors.
    
    Args:
        prompt_template: The base prompt template
        context: Dictionary of variables to be formatted into the template
        config: Configuration dictionary containing API settings
        is_structured: Whether to expect and parse a JSON response
        system_message: Optional system message to override the default
        max_tokens: Optional maximum token limit for the response
        
    Returns:
        Tuple of (response content, model used)
    """
    # Extract configuration - check both direct and nested paths
    api_config = config.get('api', {})
    openai_config = api_config.get('openai', {})
    
    # Handle system message from either kwargs or config
    system_message = kwargs.get('system_message') or openai_config.get('system_message')
    max_tokens = kwargs.get('max_tokens') or openai_config.get('max_tokens')
    
    # Get model and API key. Honour environment overrides so deployments can
    # select any accessible model without changing source defaults.
    default_model = (
        openai_config.get('model')
        or os.getenv('OPENAI_MODEL')
        or os.getenv('OPENAI_DEFAULT_MODEL')
        or 'gpt-4o-mini'
    )
    api_key = openai_config.get('resolved_key') or os.getenv('OPENAI_API_KEY')
    
    if not api_key:
        raise ModelCallError("OpenAI API key not found in configuration or environment")
    
    # Create OpenAI client
    client = OpenAI(api_key=api_key)
    
    # Format prompt with context
    formatted_prompt = prompt_template
    for key, value in context.items():
        placeholder = f"{{{key}}}"
        if placeholder in formatted_prompt:
            formatted_prompt = formatted_prompt.replace(placeholder, str(value))
    
    # Prepare system message
    if not system_message:
        system_message = "You are a highly knowledgeable assistant specialized in scientific and philosophical critique."
    
    if is_structured:
        system_message += " Respond strictly in valid JSON format."
    
    # Prepare message structure
    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": formatted_prompt}
    ]
    
    # Determine if we're using an o-series reasoning model which requires the
    # responses.create API endpoint.
    lower_model = str(default_model).lower()
    normalised_model = lower_model.split("/")[-1]
    is_response_api_model = normalised_model in {"o1", "o1-mini", "o3", "o3-mini"}
    
    if is_response_api_model:
        # o1 models use the responses.create API with a completely different structure
        o1_params = {
            "model": default_model,
            # Prepend system message to formatted prompt for o1 models since they don't have a separate system message parameter
            "input": [
                {
                    "role": "developer",
                    "content": [
                        {
                            "type": "input_text",
                            "text": f"System instruction: {system_message}\n\nUser message: {formatted_prompt}"
                        }
                    ]
                }
            ],
            "text": {
                "format": {
                    "type": "json_object" if is_structured else "text"
                }
            },
            "reasoning": {
                "effort": openai_config.get('reasoning_effort', "high")
            },
            "tools": [],
            "store": True
        }
        
        # Add max_tokens if specified
        if max_tokens:
            o1_params["max_output_tokens"] = max_tokens

        model_params = o1_params
    else:
        # Standard chat completion parameters for non-o1 models
        model_params = {
            "model": default_model,
            "messages": messages,
        }
        
        # Add parameters for non-O1 models
        model_params["temperature"] = openai_config.get('temperature', 0.2)
        if max_tokens:
            model_params["max_tokens"] = max_tokens
        
        if is_structured:
            model_params["response_format"] = {"type": "json_object"}
    
    logger.debug(f"Calling OpenAI API with model {default_model}")
    
    # Process O1 response or chat completion response based on model type
    if is_response_api_model:
        logger.debug(f"Using responses.create API for {default_model} model")
        response = client.responses.create(**model_params)
        
        # Extract content from o1 response format which has a complex structure
        try:
            # More flexible approach - don't rely on specific indices
            json_found = False
            
            if hasattr(response, 'output'):
                # Find the message component in the output list
                for output_item in response.output:
                    if hasattr(output_item, 'content') and hasattr(output_item, 'role') and output_item.role == 'assistant':
                        # Found the assistant's message
                        for content_item in output_item.content:
                            if hasattr(content_item, 'text'):
                                content = content_item.text
                                logger.debug(f"Successfully extracted content from response API: {content[:100]}...")
                                
                                # Parse JSON if structured
                                if is_structured and content:
                                    # The content often contains a JSON object
                                    try:
                                        content_dict = json.loads(content)
                                        logger.debug(f"Successfully parsed JSON from {default_model} response")
                                        json_found = True
                                        return content_dict, default_model
                                    except json.JSONDecodeError as e:
                                        logger.error(f"Failed to parse {default_model} JSON response: {e}. Content: {content}")
                                        # Try to repair broken JSON
                                        try:
                                            # Attempt basic JSON repair
                                            open_braces = content.count('{')
                                            close_braces = content.count('}')
                                            open_brackets = content.count('[')
                                            close_brackets = content.count(']')
                                            
                                            logger.debug(f"JSON balance: {open_braces}:{close_braces}, {open_brackets}:{close_brackets}")
                                            
                                            # Fix truncated JSON by adding missing braces
                                            if open_braces > close_braces:
                                                content += '}' * (open_braces - close_braces)
                                            if open_brackets > close_brackets:
                                                content += ']' * (open_brackets - close_brackets)
                                            
                                            # Try parsing again
                                            content_dict = json.loads(content)
                                            logger.info(f"Successfully repaired and parsed JSON from {default_model}")
                                            json_found = True
                                            return content_dict, default_model
                                        except Exception as repair_e:
                                            logger.warning(f"JSON repair failed: {repair_e}")
                                            # Continue with returning the raw text
                                
                                # Return raw text if no JSON or not structured
                                if not json_found:
                                    return content, default_model
            
            # If we get here, try direct access to output fields based on error logs
            logger.warning("Couldn't find content with flexible approach, trying direct access...")
            if hasattr(response, 'output') and isinstance(response.output, list) and len(response.output) > 1:
                output_msg = response.output[1]  # Second item in output is the message
                
                if hasattr(output_msg, 'content') and isinstance(output_msg.content, list) and len(output_msg.content) > 0:
                    output_text = output_msg.content[0]  # First item in content is the text
                    
                    if hasattr(output_text, 'text'):
                        content = output_text.text
                        logger.debug(f"Extracted content via direct access: {content[:100]}...")
                        
                        # Parse JSON if structured
                        if is_structured and content:
                            try:
                                content_dict = json.loads(content)
                                return content_dict, default_model
                            except json.JSONDecodeError as e:
                                logger.error(f"Failed to parse {default_model} JSON response: {e}. Content: {content}")
                                # Continue with returning the raw text
                        
                        return content, default_model
            
            # If we get here, the structure didn't match expectations
            logger.error(f"Failed to extract content from {default_model} response: {response}")
            # Instead of raising an error, try to return the entire response as string to help debugging
            return str(response), default_model
            
        except Exception as e:
            logger.error(f"Error processing {default_model} response: {e}. Response: {response}")
            raise ModelCallError(f"Error processing {default_model} response: {e}")
    else:
        logger.debug(f"Using Chat Completions API endpoint with params")
        response = client.chat.completions.create(**model_params)
        
        # Extract content from standard completion response
        if hasattr(response, 'choices') and len(response.choices) > 0 and hasattr(response.choices[0], 'message'):
            content = response.choices[0].message.content
        else:
            # Handle unexpected response structure
            logger.error(f"Unexpected Chat API response structure: {response}")
            raise ModelCallError(f"Unexpected Chat API response structure: {response}")
        
        # Parse JSON if structured
        if is_structured and content:
            try:
                content_dict = json.loads(content)
                return content_dict, default_model
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse Chat API JSON response: {e}. Content: {content}")
                raise ModelCallError(f"Failed to parse Chat API JSON response: {e}")
    
    return content, default_model


def run_openai_client(
    messages: List[Dict[str, str]],
    model_name: Optional[str] = None,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None
) -> str:
    """
    High-level function to run the OpenAI client.
    This is the main function to call from the AI client interface.
    
    Args:
        messages: List of message objects
        model_name: OpenAI model name (optional, will use config if not provided)
        max_tokens: Maximum tokens (optional, will use config if not provided)
        temperature: Temperature for generation (optional, will use config if not provided)
        
    Returns:
        Generated response
    """
    try:
        # Get config
        config = get_openai_config()
        
        # Use provided values or get from config
        env_model = os.getenv('OPENAI_MODEL') or os.getenv('OPENAI_DEFAULT_MODEL')
        model = model_name or config.get('model') or env_model or 'gpt-4o-mini'
        max_tokens_to_use = max_tokens or config.get('max_tokens', 8192)
        temp_to_use = temperature if temperature is not None else config.get('temperature', 0.2)
        
        logger.info(f"Using OpenAI model: {model} with temperature: {temp_to_use}")
        
        # Extract system message and create user content
        system_msg = None
        user_content = ""
        
        for msg in messages:
            if msg["role"] == "system":
                system_msg = msg["content"]
            elif msg["role"] == "user":
                user_content += msg["content"] + "\n"
        
        # Create config for call_openai_with_retry
        api_config = {
            'api': {
                'openai': {
                    'model': model,
                    'max_tokens': max_tokens_to_use,
                    'temperature': temp_to_use,
                    'system_message': system_msg
                }
            }
        }
        
        # Call with retry logic
        response, model_used = call_openai_with_retry(
            prompt_template="{content}",
            context={"content": user_content},
            config=api_config,
            is_structured=False
        )
        
        logger.info(f"OpenAI response received from {model_used} - length: {len(response) if isinstance(response, str) else 'unknown'} characters")
        return response
        
    except Exception as e:
        error_msg = f"ERROR from OpenAI: {str(e)}"
        logger.error(error_msg)
        import traceback
        traceback.print_exc()
        return error_msg
