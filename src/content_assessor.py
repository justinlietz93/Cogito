"""
Content assessor module for objective point extraction.

This module provides a ContentAssessor class that analyzes input content
and extracts a list of objective points or claims made in the content
without any philosophical bias or critique. It also attaches relevant
ArXiv references to each point when enabled.
"""

import logging
import json
import os
from typing import Dict, List, Any, Optional

from .prompt_texts import CONTENT_EXTRACTION_PROMPT

from .providers import call_with_retry
from .arxiv_reference_service import ArxivReferenceService

logger = logging.getLogger(__name__)

class ContentAssessor:
    """
    Content assessor that extracts objective points from content.
    
    This class analyzes content and identifies key points or claims made
    without applying any philosophical framework or bias. It serves as an
    unbiased first step in the critique process to identify points that
    can be distributed among philosophical critics.
    """
    
    def __init__(self):
        """Initialize the content assessor."""
        self.style = "ContentAssessor"
    
    def set_logger(self, logger: logging.Logger):
        """Set the logger for this assessor."""
        self.logger = logger
    
    def extract_points(self, content: str, config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract a list of objective points from the content.
        
        Args:
            content: The content to analyze.
            config: Configuration settings.
            
        Returns:
            A list of extracted points, each as a dictionary with at least
            'id' and 'point' keys. When ArXiv references are enabled,
            points may also include a 'references' key with a list of
            relevant references from ArXiv.
        """
        self.logger.info("Extracting objective points from content")
        
        # Create a prompt to identify key points without bias
        prompt = self._create_extraction_prompt(content)
        
        try:
            # Call the provider to extract points
            result, model_used = call_with_retry(
                prompt_template=prompt,
                context={},
                config=config,
                is_structured=True
            )
            
            self.logger.info(f"Successfully extracted points using {model_used}")
            
            # Ensure the result is a list of points
            points = self._validate_and_format_points(result)
            
            # Attach ArXiv references if enabled
            self._attach_arxiv_references(points, content, config)
            
            self.logger.info(f"Extracted {len(points)} points from content")
            return points
            
        except Exception as e:
            self.logger.error(f"Error extracting points: {e}", exc_info=True)
            # Return an empty list if extraction fails
            return []
    
    def _attach_arxiv_references(self, points: List[Dict[str, Any]], content: str, config: Dict[str, Any]) -> None:
        """
        Attach relevant ArXiv references to each extracted point.
        
        Args:
            points: The list of extracted points to attach references to.
            content: The original content (used for context if needed).
            config: Configuration settings.
        """
        if not points:
            self.logger.debug("No points to attach ArXiv references to.")
            return
            
        # Check if ArXiv reference lookup is enabled
        arxiv_config = config.get('arxiv', {})
        if not arxiv_config.get('enabled', True):
            self.logger.debug("ArXiv reference lookup is disabled in configuration.")
            return
            
        # Initialize ArXiv service
        arxiv_service = None
        refs_by_point_count = 0
        
        try:
            # Create ArXiv service with configured cache directory
            cache_dir = arxiv_config.get('cache_dir', 'storage/arxiv_cache')
            arxiv_service = ArxivReferenceService(cache_dir=cache_dir)
            self.logger.info(f"ArXiv reference service initialized with cache dir: {cache_dir}")
            
            # Get configuration settings for search
            max_refs_per_point = arxiv_config.get('max_references_per_point', 3)
            sort_by = arxiv_config.get('search_sort_by', 'relevance')
            sort_order = arxiv_config.get('search_sort_order', 'descending')
            use_cache = arxiv_config.get('use_cache', True)
            
            # For each point, find relevant ArXiv references
            for point in points:
                point_text = point.get('point', '')
                point_id = point.get('id', 'unknown')
                
                if not point_text or len(point_text) < 10:
                    continue
                    
                try:
                    self.logger.debug(f"Searching ArXiv references for point: {point_id}")
                    
                    # Search for relevant papers
                    papers = arxiv_service.get_references_for_content(
                        point_text,
                        max_results=max_refs_per_point,
                        domains=None  # Using default domains
                    )
                    
                    if papers:
                        # Attach only essential reference data
                        references = []
                        for paper in papers:
                            # Extract only the fields we need
                            ref = {
                                'id': paper.get('id', ''),
                                'title': paper.get('title', ''),
                                'authors': paper.get('authors', []),
                                'summary': paper.get('summary', '')[:200] + '...' if paper.get('summary') else '',
                                'url': paper.get('arxiv_url', paper.get('id', '')),
                                'published': paper.get('published', '')
                            }
                            references.append(ref)
                            
                            # Register this reference with the agent name "ContentAssessor"
                            arxiv_service.register_reference_for_agent(
                                agent_name="ContentAssessor", 
                                paper_id=paper.get('id', ''),
                                relevance_score=0.8  # Default high relevance
                            )
                        
                        point['references'] = references
                        refs_by_point_count += 1
                        self.logger.debug(f"Attached {len(references)} references to point {point_id}")
                    else:
                        self.logger.debug(f"No relevant references found for point {point_id}")
                        
                except Exception as point_e:
                    # Handle exceptions per point, but continue processing other points
                    self.logger.warning(f"Error finding references for point {point_id}: {point_e}")
                    
            # Update bibliography if requested
            if arxiv_service and arxiv_config.get('update_bibliography', True):
                try:
                    # Combine with LaTeX configuration
                    latex_config = config.get('latex', {})
                    output_dir = latex_config.get('output_dir', 'latex_output')
                    
                    # Ensure the LaTeX output directory exists
                    os.makedirs(output_dir, exist_ok=True)
                    
                    # Get the bibliography template path
                    bibliography_path = os.path.join(
                        output_dir, 
                        latex_config.get('output_filename', 'critique_report') + '_bibliography.bib'
                    )
                    
                    # Update the bibliography
                    success = arxiv_service.update_latex_bibliography(bibliography_path)
                    if success:
                        self.logger.info(f"Updated LaTeX bibliography with ArXiv references at {bibliography_path}")
                    else:
                        self.logger.warning(f"Failed to update LaTeX bibliography at {bibliography_path}")
                except Exception as bib_e:
                    self.logger.error(f"Error updating bibliography: {bib_e}", exc_info=True)
            
            self.logger.info(f"ArXiv reference attachment complete. Added references to {refs_by_point_count}/{len(points)} points.")
            
        except Exception as e:
            # Handle exceptions, but allow processing to continue
            self.logger.error(f"Error in ArXiv reference lookup: {e}", exc_info=True)
    
    def _create_extraction_prompt(self, content: str) -> str:
        """
        Create a prompt for extracting objective points.
        
        Args:
            content: The content to analyze.
            
        Returns:
            A prompt string.
        """
        return CONTENT_EXTRACTION_PROMPT.format(content=content)
    
    def _validate_and_format_points(self, result: Any) -> List[Dict[str, Any]]:
        """
        Validate and format the extracted points.
        
        Args:
            result: The result from the provider call.
            
        Returns:
            A list of formatted points.
        """
        points = []
        
        try:
            # First, try to ensure result is properly serialized
            if isinstance(result, str):
                # This might be a string containing JSON or a partial JSON response
                try:
                    # Attempt to parse as JSON, handling potentially incomplete JSON
                    result = self._repair_and_parse_json(result)
                except Exception as json_err:
                    self.logger.warning(f"Could not parse result as JSON: {json_err}")
                    # Keep as string and will be handled below
            
            # Handle different possible formats from the provider
            if isinstance(result, dict) and "points" in result:
                raw_points = result["points"]
            elif isinstance(result, list):
                raw_points = result
            elif isinstance(result, str):
                # Try to extract points from string format
                self.logger.warning(f"Received string result, attempting to extract points")
                extracted_points = self._extract_points_from_text(result)
                if extracted_points:
                    return extracted_points
                else:
                    self.logger.warning(f"Could not extract points from string: {result[:200]}...")
                    raw_points = []
            else:
                self.logger.warning(f"Unexpected result format: {type(result)}")
                raw_points = []
            
            # Process each point to ensure it has the required fields
            for i, point in enumerate(raw_points):
                if isinstance(point, dict):
                    # Ensure each point has an id
                    if "id" not in point:
                        point["id"] = f"point-{i+1}"
                    points.append(point)
                else:
                    # Convert simple strings to dictionaries
                    points.append({
                        "id": f"point-{i+1}",
                        "point": str(point)
                    })
            
        except Exception as e:
            self.logger.error(f"Error validating points: {e}", exc_info=True)
        
        # Create fallback points if none were extracted (moved outside try/except block)
        if not points:
            self.logger.info("Creating fallback points due to extraction failure")
            # Create at least one fallback point to allow processing to continue
            points = [{
                "id": "point-fallback",
                "point": "The content requires analysis but point extraction failed."
            }]
        
        return points
        
    def _repair_and_parse_json(self, json_str: str) -> Any:
        """
        Attempt to repair and parse potentially broken JSON.
        
        Args:
            json_str: String containing potentially broken JSON
            
        Returns:
            Parsed JSON object if successful, otherwise raises exception
        """
        # First try standard parsing
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            self.logger.warning(f"Standard JSON parsing failed: {e}")
            
            # Check for common truncation issues (e.g., missing closing braces)
            try:
                # Count opening and closing braces to check for balance
                open_braces = json_str.count('{')
                close_braces = json_str.count('}')
                open_brackets = json_str.count('[')
                close_brackets = json_str.count(']')
                
                self.logger.debug(f"Braces balance: {open_braces}:{close_braces}, Brackets balance: {open_brackets}:{close_brackets}")
                
                # Handle truncated JSON, try to fix it
                if open_braces > close_braces:
                    # Add missing closing braces
                    json_str += '}' * (open_braces - close_braces)
                if open_brackets > close_brackets:
                    # Add missing closing brackets
                    json_str += ']' * (open_brackets - close_brackets)
                
                # Try parsing again
                repaired = json.loads(json_str)
                self.logger.info(f"Successfully repaired and parsed JSON response.")
                return repaired
            except Exception as repair_e:
                self.logger.warning(f"JSON repair attempt failed: {repair_e}")
                raise
    
    def _extract_points_from_text(self, text: str) -> List[Dict[str, Any]]:
        """
        Attempt to extract points from raw text when JSON parsing fails.
        
        Args:
            text: Raw text potentially containing structured point information
            
        Returns:
            List of extracted points or empty list if extraction fails
        """
        points = []
        try:
            # Look for point patterns - try to identify numbered points
            # Example pattern: "1. Point description" or "Point 1: Description"
            import re
            
            # Try a few common patterns
            patterns = [
                r'(?:^|\n)"?(?:point-?)?(\d+)"?[\.:\)]?\s+"?([^"]+)"?',  # point-1: "text" or 1. text
                r'"id":\s*"point-?(\d+)",\s*"point":\s*"([^"]+)"',       # "id": "point-1", "point": "text"
                r'(?:^|\n)(\d+)[\.:\)]\s+(.+?)(?=(?:\n\d+[\.:\)])|$)',   # Numbered list items
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, text, re.MULTILINE)
                if matches:
                    self.logger.info(f"Found {len(matches)} points using pattern: {pattern}")
                    for i, match in enumerate(matches):
                        points.append({
                            "id": f"point-{match[0] if len(match) > 0 else i+1}",
                            "point": match[1] if len(match) > 1 else match[0]
                        })
                    # If we found points with one pattern, return them
                    if points:
                        return points
            
            # If no patterns matched, try splitting by lines and create points from non-empty lines
            if not points:
                lines = [line.strip() for line in text.split('\n') if line.strip()]
                if len(lines) > 2:  # Ensure we have at least a few substantial lines
                    for i, line in enumerate(lines[:10]):  # Limit to first 10 lines
                        if len(line) > 20:  # Only use lines with some substance
                            points.append({
                                "id": f"point-{i+1}",
                                "point": line
                            })
        except Exception as e:
            self.logger.error(f"Error extracting points from text: {e}", exc_info=True)
            
        return points
