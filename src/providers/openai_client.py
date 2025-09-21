"""OpenAI provider client utilities.

Purpose:
    Provide resilient wrappers around the OpenAI HTTP API so that the
    application can issue prompts, capture structured responses, and surface
    provider metadata without leaking SDK details into higher layers.
External Dependencies:
    Uses the official ``openai`` Python SDK to communicate with OpenAI's
    hosted API over HTTPS.
Fallback Semantics:
    Retries transient failures via the ``with_retry`` decorator, performs
    structured error handling, and degrades gracefully by returning raw
    strings when JSON payload parsing fails.
Timeout Strategy:
    Relies on the OpenAI SDK's default request timeouts while delegating
    retry timing to the exponential backoff implemented in the retry
    decorator.
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

RESPONSE_API_MODEL_ALIASES = {"o1", "o1-mini", "o1-preview", "o3", "o3-mini"}
REASONING_COMPLETION_PARAM_KEYWORDS = ("reasoning",)
REASONING_COMPLETION_PARAM_PREFIXES = ("gpt-4.1", "gpt-5")


def _model_uses_responses_api(normalised_model: str) -> bool:
    """Determine whether a model must be called via ``responses.create``.

    Args:
        normalised_model: Lowercase model name stripped of any provider
            namespace prefix.

    Returns:
        ``True`` when the Responses API should be used for the supplied model,
        ``False`` otherwise.
    """

    if normalised_model in RESPONSE_API_MODEL_ALIASES:
        return True

    base_name = normalised_model.split("-")[0]
    return bool(base_name.startswith("o") and len(base_name) > 1 and base_name[1].isdigit())


def _chat_completion_token_parameter(normalised_model: str) -> str:
    """Return the appropriate token limit parameter for chat completions.

    Args:
        normalised_model: Lowercase identifier for the selected OpenAI model.

    Returns:
        Name of the parameter that constrains completion tokens. Newer
        reasoning-capable chat models require ``max_completion_tokens`` whereas
        legacy chat models still rely on ``max_tokens``.
    """

    for prefix in REASONING_COMPLETION_PARAM_PREFIXES:
        if normalised_model.startswith(prefix):
            return "max_completion_tokens"
    for keyword in REASONING_COMPLETION_PARAM_KEYWORDS:
        if keyword in normalised_model:
            return "max_completion_tokens"
    return "max_tokens"

@with_error_handling
@with_retry(max_attempts=3, delay_base=2.0)
def call_openai_with_retry(
    prompt_template: str,
    context: Dict[str, Any],
    config: Dict[str, Any],
    is_structured: bool = False,
    **kwargs
) -> Tuple[Union[str, Dict[str, Any]], str]:
    """Execute an OpenAI request with structured retries and parsing rules.

    Args:
        prompt_template: Template string that will be formatted with context
            variables to construct the user prompt.
        context: Mapping of placeholder names to runtime values injected into
            the prompt template.
        config: Configuration dictionary containing API credentials and model
            defaults sourced from application settings.
        is_structured: Indicates whether the caller expects JSON output that
            should be parsed into a Python object.
        **kwargs: Optional overrides such as ``system_message`` or
            ``max_tokens``/``max_completion_tokens`` supplied by upstream
            services.

    Returns:
        Tuple containing the model response (text or parsed JSON) and the name
        of the model that generated it.

    Raises:
        ModelCallError: If configuration is incomplete or the response payload
            cannot be processed into the requested format.
        MaxRetriesExceededError: Propagated when repeated transient failures
            exhaust the retry budget defined by ``with_retry``.

    Side Effects:
        Issues HTTPS requests via the OpenAI SDK and logs debug information
        about payload construction and parsing branches.

    Timeout Strategy:
        Relies on the OpenAI SDK's default timeout management while applying
        exponential backoff between retry attempts through ``with_retry``.
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
    is_response_api_model = _model_uses_responses_api(normalised_model)
    
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
            token_param = _chat_completion_token_parameter(normalised_model)
            model_params[token_param] = max_tokens
            logger.debug(
                "Using %s=%s for chat completion model %s",
                token_param,
                max_tokens,
                default_model,
            )
        
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
    """Send a conversational request to the configured OpenAI chat model.

    Args:
        messages: Ordered list of chat message dictionaries in OpenAI format.
        model_name: Optional explicit model identifier overriding configuration
            and environment defaults.
        max_tokens: Optional maximum token budget for the completion; falls
            back to configuration when omitted.
        temperature: Optional sampling temperature override; configuration
            value is used when ``None``.

    Returns:
        Assistant response text returned by the selected OpenAI model.

    Raises:
        ModelCallError: Bubbled up from ``call_openai_with_retry`` when the
            provider call cannot be completed successfully.

    Side Effects:
        Emits informational logs regarding the selected model and performs an
        HTTPS request to the OpenAI API.

    Timeout Strategy:
        Delegates timeout management to the underlying OpenAI SDK alongside the
        retry policy defined within ``call_openai_with_retry``.
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
