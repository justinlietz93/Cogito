# src/scientific_review_formatter.py

"""
Module for formatting critique results into a formal scientific peer review format.
This is used when the --PR (peer review) flag is active to transform the normal
critique output into a standard scientific peer review document.
"""

import logging
from collections.abc import Mapping
from copy import deepcopy
from typing import Dict, Any, Optional, Tuple

# Import provider factory for LLM clients
from .providers import ApiKeyError, ProviderError, call_with_retry

logger = logging.getLogger(__name__)

def _normalise_provider(value: Any) -> str:
    """Normalise provider identifiers to the canonical keys used by providers."""

    if not value:
        return "openai"

    name = str(value).strip().lower()
    if name in {"claude", "claude-3", "claude-3-7-sonnet"}:
        return "anthropic"
    if name in {"google", "google-ai"}:
        return "gemini"
    return name


def _prepare_formatter_config(
    config: Mapping[str, Any] | None,
    system_message: str,
) -> Tuple[Dict[str, Any], str]:
    """Create a defensive copy of ``config`` with the formatter system message applied."""

    safe_config: Dict[str, Any]
    if isinstance(config, Mapping):
        safe_config = deepcopy(dict(config))
    else:
        safe_config = {}

    api_section = safe_config.get("api", {})
    if not isinstance(api_section, Mapping):
        api_section = {}
    api_config = dict(api_section)

    provider_key = _normalise_provider(api_config.get("primary_provider"))
    api_config["primary_provider"] = provider_key

    providers_section = api_config.get("providers", {})
    if isinstance(providers_section, Mapping):
        providers_config = dict(providers_section)
    else:
        providers_config = {}

    provider_cfg = dict(providers_config.get(provider_key, {}))
    provider_cfg["system_message"] = system_message
    providers_config[provider_key] = provider_cfg
    api_config["providers"] = providers_config

    direct_provider_cfg = api_config.get(provider_key, {})
    if isinstance(direct_provider_cfg, Mapping):
        merged_direct_cfg = dict(direct_provider_cfg)
    else:
        merged_direct_cfg = {}
    merged_direct_cfg.update(provider_cfg)
    api_config[provider_key] = merged_direct_cfg

    safe_config["api"] = api_config
    return safe_config, provider_key


def format_scientific_peer_review(
    original_content: str,
    critique_report: str,
    config: Dict[str, Any],
    scientific_mode: bool = False
) -> str:
    """
    Formats the critique report into a formal scientific peer review document.
    
    Args:
        original_content: The original content that was critiqued
        critique_report: The generated critique report from the council
        config: Configuration dictionary
        scientific_mode: Whether to use pure scientific methodology terminology
        
    Returns:
        A formatted scientific peer review document
    """
    logger.info(f"Formatting critique into formal scientific peer review document... (Scientific Mode: {scientific_mode})")
    
    # Modify the system message based on whether we're in scientific mode
    if scientific_mode:
        system_message = """
        You are an expert academic peer reviewer responsible for transforming a critique report into a formal 
        scientific peer review document. Follow these peer review best practices:
        
        1. Structure the review with these sections:
           - Brief summary of the entire manuscript (1-2 paragraphs)
           - Clear recommendation (accept, reject, or revise)
           - Major concerns (internal inconsistencies, missing data, methodological issues)
           - Minor concerns (grammar, typos, references, clarity issues)
           - Methodological Analysis Frameworks (detailed subsections from different methodological perspectives)
           - Conclusion
           - References (at least 10-15 relevant academic sources)
        
        2. Maintain a professional, constructive tone throughout
        
        3. Number each concern and organize them in order of appearance in the manuscript
        
        4. For each concern, cite specific page/paragraph/section numbers when possible
        
        5. Suggest specific improvements for each concern identified
        
        6. Keep recommendations reasonable and within the scope of the original work
        
        7. Include a comprehensive "Methodological Analysis Frameworks" section with detailed subsections from each scientific methodology approach:
           - Systems Analysis
           - First Principles Analysis 
           - Boundary Condition Analysis
           - Optimization Analysis
           - Empirical Validation Analysis
           - Logical Structure Analysis
           
        8. End with a formal References section in APA format that includes:
           - Relevant methodology texts for each analytical approach
           - Current academic literature related to the subject matter
           - Research methodology references supporting your recommended improvements
           
        Your review should be 4-6 pages long when printed, comprehensive and thorough in covering all methodological perspectives, using strictly scientific terminology with no philosophical jargon.
        """
    else:
        system_message = """
        You are an expert academic peer reviewer responsible for transforming a critique report into a formal 
        scientific peer review document. Follow these peer review best practices:
        
        1. Structure the review with these sections:
           - Brief summary of the entire manuscript (1-2 paragraphs)
           - Clear recommendation (accept, reject, or revise)
           - Major concerns (internal inconsistencies, missing data, methodological issues)
           - Minor concerns (grammar, typos, references, clarity issues)
           - Perspective-specific contributions (detailed analysis from each philosophical perspective)
           - Conclusion
           - References (at least 10-15 relevant academic sources)
        
        2. Maintain a professional, constructive tone throughout
        
        3. Number each concern and organize them in order of appearance in the manuscript
        
        4. For each concern, cite specific page/paragraph/section numbers when possible
        
        5. Suggest specific improvements for each concern identified
        
        6. Keep recommendations reasonable and within the scope of the original work
        
        7. Include a comprehensive "Perspective-specific Contributions" section with detailed subsections from each philosopher (Aristotle, Descartes, Kant, Leibniz, Popper, and Russell) - each philosopher should provide substantive, unique insights beyond what appears in the main concerns
        
        8. End with a formal References section in APA format that includes:
           - Relevant works from each philosopher mentioned in the review
           - Current academic literature related to the subject matter
           - Methodological references supporting your recommended improvements
           
        Your review should be 4-6 pages long when printed, comprehensive and thorough in covering all philosophical perspectives.
        """
    
    # Prepare the main prompt, adjusting for scientific mode if needed
    if scientific_mode:
        section_guidance = """
        5. Methodological Analysis Frameworks - ESSENTIAL SECTION with detailed subsections:
           a. Systems Analysis (min. 250 words)
           b. First Principles Analysis (min. 250 words)
           c. Boundary Condition Analysis (min. 250 words)
           d. Optimization & Sufficiency Analysis (min. 250 words)
           e. Empirical Validation Analysis (min. 250 words)
           f. Logical Structure Analysis (min. 250 words)
        """
        
        references_guidance = """
        7. References (include at least 10-15 relevant academic sources in APA format)
           a. Include methodological references for each analytical approach
           b. Include contemporary academic sources related to the subject matter
           c. Include research methodology references that support your recommended improvements
        """
    else:
        section_guidance = """
        5. Perspective-specific contributions - ESSENTIAL SECTION with detailed subsections:
           a. Aristotelian analysis (min. 250 words)
           b. Cartesian analysis (min. 250 words)
           c. Kantian analysis (min. 250 words)
           d. Leibnizian analysis (min. 250 words)
           e. Popperian analysis (min. 250 words)
           f. Russellian analysis (min. 250 words)
        """
        
        references_guidance = """
        7. References (include at least 10-15 relevant academic sources in APA format)
           a. Include works by each philosopher mentioned (Aristotle, Descartes, Kant, Leibniz, Popper, Russell)
           b. Include contemporary academic sources related to the subject matter
           c. Include methodological references that support your recommended improvements
        """
    
    # Format the prompt
    prompt = f"""
    Your task is to transform a {"scientific methodology" if scientific_mode else "philosophical"} critique report into a comprehensive formal scientific peer review document. This document should be a serious and legitimate attempt at scrutinizing the original content from a subject matter expert perspective, finding any gaps or holes in the logic with feedback for the author. The review should be structured and formatted according to the standards of academic publishing.

    You have access to:
    1. The ORIGINAL CONTENT that was analyzed
    2. A CRITIQUE REPORT produced by a council of {"scientific methodology" if scientific_mode else "philosophical"} critics
    
    Create a substantive and expansive formal peer review following scientific publishing standards.
    Present yourself as a domain expert with credentials relevant to the content.
    Focus on methodology, evidence, logic, scientific accuracy, and scholarly merit.
    
    The beginning of your review MUST include:
    1. Your full academic name and credentials (e.g., "Dr. Jonathan Smith, Ph.D.")
    2. Your institutional affiliation
    3. Your area of expertise
    
    Structure the review following this expanded academic peer review format:
    1. Brief summary of the work (1-2 paragraphs)
    2. Clear recommendation (accept/reject/revise)
    3. Major concerns (numbered, detailed analysis with at least 5-7 significant issues)
    4. Minor concerns (numbered, at least 3-5 issues)
    {section_guidance}
    6. Conclusion
    {references_guidance}
    
    # ORIGINAL CONTENT:
    {original_content}
    
    # CRITIQUE REPORT:
    {critique_report}
    """
    
    provider_key = "openai"
    try:
        formatter_config, provider_key = _prepare_formatter_config(config, system_message)

        # Call provider factory with whichever provider is configured
        review_content, model_used = call_with_retry(
            prompt_template=prompt,
            context={},  # Context is already embedded in the prompt template
            config=formatter_config,
            is_structured=False
        )
        
        logger.info(f"Scientific peer review formatting completed using {model_used} (Scientific Mode: {scientific_mode})")
        
        # Add a metadata header to the document
        review_with_header = f"""# Scientific Peer Review Report
Generated using the Critique Council PR module

---

{review_content}

---
End of Peer Review
"""

        # If we're in scientific mode, optionally process the text through the jargon processor
        # to ensure all philosophical terms are replaced with scientific alternatives
        if scientific_mode:
            try:
                # Import the jargon processor
                from .latex.processors.jargon_processor import JargonProcessor
                
                # Create a jargon processor with high objectivity
                jargon_processor = JargonProcessor(objectivity_level="high")
                
                # Process the review to convert any remaining philosophical terms
                processed_review = jargon_processor.process(review_with_header)
                
                logger.info("Applied jargon processor to convert philosophical terms to scientific terminology")
                return processed_review
            except Exception as e:
                # If jargon processing fails, log but return the unprocessed review
                logger.warning(f"Failed to apply jargon processor: {e}")
                return review_with_header
        else:
            return review_with_header
        
    except ApiKeyError as exc:
        logger.error(
            "Failed to format scientific peer review due to missing API key for %s: %s",
            provider_key,
            exc,
            exc_info=True,
        )
        provider_label = provider_key.capitalize() if provider_key else "configured"
        return f"""# ERROR: Scientific Peer Review Formatting Failed

The system attempted to format the critique using the configured {provider_label} provider, but no API key was available.

{str(exc)}

The original critique report is still available.
"""
    except ProviderError as exc:
        logger.error(
            "Failed to format scientific peer review due to provider error for %s: %s",
            provider_key,
            exc,
            exc_info=True,
        )
        return f"""# ERROR: Scientific Peer Review Formatting Failed

The configured provider could not process the formatting request:

{str(exc)}

The original critique report is still available.
"""
    except Exception as e:
        logger.error(f"Failed to format scientific peer review: {e}", exc_info=True)
        return f"""# ERROR: Scientific Peer Review Formatting Failed

The system encountered an error while attempting to format the critique as a scientific peer review:

{str(e)}

The original critique report is still available.
"""
