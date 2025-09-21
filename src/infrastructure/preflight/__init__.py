"""Infrastructure adapters for preflight extraction and query planning.

Purpose:
    Provide provider-specific gateway implementations that bridge the
    application layer's ports to concrete language model clients. The
    adapters coordinate prompt construction, provider invocation, and
    structured parsing so outer layers can depend on stable abstractions.
External Dependencies:
    Relies on the OpenAI provider client housed in ``src.providers`` and the
    clean application-layer utilities for prompts and parsing.
Fallback Semantics:
    When provider responses fail validation the adapters return fallback
    domain objects populated with the raw provider response and formatted
    validation errors, allowing callers to continue while flagging the
    issues.
Timeout Strategy:
    Delegates timeout enforcement to the shared ``operation_timeout`` context
    manager sourced from :mod:`src.infrastructure.timeouts`.
"""

from .openai_gateway import OpenAIPointExtractorGateway, OpenAIQueryBuilderGateway

__all__ = ["OpenAIPointExtractorGateway", "OpenAIQueryBuilderGateway"]
