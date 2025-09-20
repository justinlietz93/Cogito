"""
Main formatter for generating LaTeX documents from critique reports.

This module provides the main formatter class for generating LaTeX documents
from critique reports and peer reviews.
"""

import os
import re
import logging
import datetime
from typing import Dict, Any, Optional, List, Union, Tuple

# Import the global configuration loader
try:
    from src.config_loader import config_loader
except ImportError:
    # Handle case when running from different directory
    import sys
    import os.path
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
    from src.config_loader import config_loader

from .config import LatexConfig
from .converters import MarkdownToLatexConverter, MathFormatter
# Import the new direct generator
from .converters.direct_latex_generator import DirectLatexGenerator
from .processors import ContentProcessor, JargonProcessor, CitationProcessor
from .utils import FileManager, LatexCompiler

logger = logging.getLogger(__name__)


class LatexFormatter:
    """
    Main formatter for generating LaTeX documents from critique reports.
    
    This class uses the converters, processors, and utilities to generate
    comprehensive LaTeX documents from critique reports and peer reviews.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the LaTeX formatter.
        
        Args:
            config: Optional configuration dictionary containing formatter options.
                   If not provided, will use the global configuration from config.yaml.
        """
        # If no config provided, use the global config's latex section
        if config is None:
            latex_config = config_loader.get_latex_config()
            # Convert to LatexConfig for backwards compatibility
            self.config = LatexConfig(latex_config)
            logger.info("Using global YAML configuration for LaTeX formatter")
        else:
            # Use provided config with LatexConfig for backwards compatibility
            self.config = LatexConfig(config)
            logger.info("Using provided configuration for LaTeX formatter")
        
        # Get main configuration parameters
        scientific_mode = self.config.get('scientific_mode', False)
        template_dir = self.config.get('template_dir')
        output_dir = self.config.get('output_dir')
        compile_pdf = self.config.get('compile_pdf', True)  # Default to True with new config
        
        # Select the appropriate template based on mode
        if scientific_mode:
            template = self.config.get('scientific_template')
            self.config.set('main_template', template)
            logger.info(f"Using scientific methodology mode with template: {template}")
        else:
            template = self.config.get('philosophical_template', 'academic_paper.tex')
            self.config.set('main_template', template)
            logger.info(f"Using philosophical mode with template: {template}")
        
        # Initialize file manager
        self.file_manager = FileManager({
            'template_dir': template_dir,
            'output_dir': output_dir
        })
        
        # Initialize converters
        self.markdown_converter = MarkdownToLatexConverter({
            'katex_compatibility': self.config.get('katex_compatibility', True)
        })
        
        self.math_formatter = MathFormatter({
            'katex_compatibility': self.config.get('katex_compatibility', True)
        })
        
        # Initialize processors
        self.jargon_processor = JargonProcessor(
            objectivity_level=self.config.get('scientific_objectivity_level', 'high')
        )
        
        self.citation_processor = CitationProcessor(
            output_dir=output_dir
        )
        
        # Initialize LaTeX compiler if needed - pass the whole config
        # so that compiler can access MiKTeX specific settings
        if compile_pdf:
            logger.info("PDF compilation enabled, initializing LaTeX compiler")
            # Use the global config directly to ensure all settings are available to compiler
            self.latex_compiler = LatexCompiler(latex_config if config is None else config)
        else:
            logger.info("PDF compilation disabled")
            self.latex_compiler = None
    
    def format_document(
        self, 
        original_content: str, 
        critique_report: str, 
        peer_review: Optional[str] = None
    ) -> Tuple[str, Optional[str]]:
        """
        Format critique report and optional peer review into a LaTeX document.
        
        Args:
            original_content: The original content that was critiqued.
            critique_report: The generated critique report.
            peer_review: Optional peer review document.
            
        Returns:
            A tuple of (tex_file_path, pdf_file_path), where pdf_file_path
            is None if compilation is not enabled or fails.
        """
        logger.info("Starting LaTeX document formatting process")
        
        # Generate timestamp for filename early
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename_base = self.config.get('output_filename', 'critique_report')
        
        tex_file_path = None
        pdf_file_path = None
        
        # === Conditional Direct LaTeX Generation ===
        if self.config.get('direct_conversion') and peer_review:
            logger.info("Using direct LaTeX generation for peer review.")
            
            # Extract title from peer review (similar to _prepare_context logic)
            title_match = re.search(r'#\s+([^\n]+)', peer_review)
            direct_title = title_match.group(1) if title_match else "Scientific Peer Review"
            
            # Instantiate and generate the full document directly
            direct_generator = DirectLatexGenerator(
                peer_review,
                title=direct_title,
                custom_preamble=self.config.get('custom_preamble', '')
            )
            rendered_content = direct_generator.generate_latex_document()
            
            # Write the output file
            output_filename = f"{output_filename_base}_direct_{timestamp}.tex"
            tex_file_path = self.file_manager.write_output_file(output_filename, rendered_content)
            
            # Compile to PDF if enabled (no extra templates needed for direct)
            if self.latex_compiler is not None and self.config.get('compile_pdf', False):
                logger.info("Compiling direct LaTeX document to PDF")
                success, result = self.latex_compiler.compile_document(tex_file_path)
                if success:
                    pdf_file_path = result
                    logger.info(f"Direct PDF compilation successful: {pdf_file_path}")
                else:
                    logger.error(f"Direct PDF compilation failed: {result}. Error details: {result.stderr}")
            
        # === Standard Template-Based Generation ===
        else:
            if self.config.get('direct_conversion'):
                 logger.warning("Direct conversion enabled but no peer review provided. Falling back to standard method.")
            logger.info("Using standard template-based LaTeX generation.")
            
            # Prepare content context
            context = self._prepare_context(original_content, critique_report, peer_review)
            
            # Process each content field through processors
            if 'analysis_content' in context:
                context['analysis_content'] = self._process_content(context['analysis_content'])
            
            if 'review_content' in context:
                context['review_content'] = self._process_content(context['review_content'])
            
            # Read main template
            template_name = self.config.get('main_template')
            logger.debug(f"Reading main template: {template_name}")
            template_content = self.file_manager.read_template(template_name)
            
            # Render template with context
            logger.debug("Rendering template with context.")
            rendered_content = self.file_manager.render_template(template_content, context)
            
            # Write the output file
            output_filename = f"{output_filename_base}_{timestamp}.tex"
            tex_file_path = self.file_manager.write_output_file(output_filename, rendered_content)
            
            # Copy required template files to output directory
            required_templates = ['preamble.tex']
            if self.config.get('include_bibliography', True):
                required_templates.append('bibliography.bib')
            
            logger.debug(f"Copying required templates: {required_templates}")
            self.file_manager.copy_templates_to_output(required_templates)
            
            # Compile to PDF if enabled
            if self.latex_compiler is not None and self.config.get('compile_pdf', False):
                logger.info("Compiling standard LaTeX document to PDF")
                success, result = self.latex_compiler.compile_document(tex_file_path)
                if success:
                    pdf_file_path = result
                    logger.info(f"Standard PDF compilation successful: {pdf_file_path}")
                else:
                    logger.error(f"Standard PDF compilation failed: {result}")

        if tex_file_path:
             logger.info(f"LaTeX generation complete. Output TEX: {tex_file_path}")
        else:
             logger.error("LaTeX generation failed: No TEX file path generated.")
             
        return tex_file_path, pdf_file_path
    
    def _prepare_context(
        self,
        original_content: str,
        critique_report: str,
        peer_review: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Prepare the context for rendering the LaTeX template.
        
        Args:
            original_content: The original content that was critiqued.
            critique_report: The generated critique report.
            peer_review: Optional peer review document.
            
        Returns:
            Dictionary with context variables for template rendering.
        """
        # Check if we're in scientific mode
        scientific_mode = self.config.get('scientific_mode', False)
        
        # Prioritize peer review for metadata extraction if available
        source_content = peer_review if peer_review else critique_report
        
        # Extract metadata from source content
        title = "Scientific Methodology Analysis" if scientific_mode else "Philosophical Critique"
        author = "Scientific Methodology Council" if scientific_mode else "Critique Council"
        date = datetime.datetime.now().strftime("%B %d, %Y")
        
        # Try to extract a better title and author if available
        title_match = re.search(r'#\s+([^\n]+)', source_content)
        if title_match:
            title = title_match.group(1)
        
        author_match = re.search(r'##\s+Author:\s+([^\n]+)', source_content)
        if author_match:
            author = author_match.group(1)
        
        # Extract possible abstract from source content
        abstract = self._extract_abstract(source_content)
        
        # Set keywords based on mode
        if scientific_mode:
            keywords = 'scientific methodology, empirical analysis, systems analysis, validation, logical analysis'
        else:
            keywords = 'philosophical critique, analysis, peer review'
        
        # Process original content
        processed_original = self._escape_latex_chars(original_content)
        if len(processed_original) > 1000:
            processed_original = processed_original[:997] + '...'
        
        # Create context dictionary with template variables
        # If peer review is available, prioritize it as the main content
        if peer_review:
            context = {
                'title': title,
                'author': author,
                'date': date,
                'abstract': abstract,
                'original_content': processed_original,
                'analysis_content': peer_review,  # Use peer review as main content
                'review_content': critique_report,  # Use critique report as review
                'include_bibliography': self.config.get('include_bibliography', True),
                'keywords': keywords,
                'using_peer_review': True  # Flag to indicate we're using peer review
            }
        else:
            context = {
                'title': title,
                'author': author,
                'date': date,
                'abstract': abstract,
                'original_content': processed_original,
                'analysis_content': critique_report,
                'review_content': "No peer review available for this analysis.",
                'include_bibliography': self.config.get('include_bibliography', True),
                'keywords': keywords,
                'using_peer_review': False  # Flag to indicate we're using critique report
            }
        
        return context
    
    def _extract_abstract(self, content: str) -> str:
        """
        Extract an abstract from the content.
        
        This method attempts to extract an abstract from the content,
        looking for explicit abstract sections or using the first paragraph.
        
        Args:
            content: The content to extract an abstract from.
            
        Returns:
            The extracted abstract.
        """
        # Try to find an explicit abstract section
        abstract_match = re.search(r'(?:##?\s+Abstract|Executive Summary[^\n]*\n)(.*?)(?:\n##?|$)', 
                                  content, re.DOTALL)
        
        if abstract_match:
            return abstract_match.group(1).strip()
        
        # If no explicit abstract, use the first paragraph (up to 500 chars)
        paragraphs = [p for p in content.split('\n\n') if p.strip()]
        if paragraphs:
            first_para = paragraphs[0].strip()
            # Remove any headings
            first_para = re.sub(r'^#+ .*\n', '', first_para)
            # Truncate if too long
            if len(first_para) > 500:
                return first_para[:497] + '...'
            return first_para
        
        # Default abstract if nothing else works
        return "This document presents a scientific critique and analysis of the provided content."
    
    def _prepare_original_content_summary(self, original_content: str) -> str:
        """
        Prepare a summary of the original content.
        
        Args:
            original_content: The original content to summarize.
            
        Returns:
            A summary of the original content suitable for inclusion in the LaTeX document.
        """
        # Truncate original content if too long
        if len(original_content) > 1000:
            summary = original_content[:997] + '...'
        else:
            summary = original_content
            
        # Escape any LaTeX special characters
        summary = self._escape_latex_chars(summary)
        
        return f"""
The analysis in this document is based on the following original content:

\\begin{{quote}}
{summary}
\\end{{quote}}

The critique and peer review sections provide a comprehensive analysis of this content
from multiple methodological perspectives.
"""
    
    def _process_content(self, content: str) -> str:
        """
        Process the content through all processors and converters.
        
        Args:
            content: The content to process.
            
        Returns:
            The processed content.
        """
        # Apply jargon processor to make content more scientific
        content = self.jargon_processor.process(content)
        
        # Apply citation processor to handle citations and bibliography
        content = self.citation_processor.process(content)
        
        # Apply math formatter to format mathematical expressions
        content = self.math_formatter.format(content)
        
        # Convert markdown to LaTeX
        content = self.markdown_converter.convert(content)
        
        return content
    
    def _escape_latex_chars(self, text: str) -> str:
        """
        Escape LaTeX special characters in text.
        
        Args:
            text: The text to escape.
            
        Returns:
            The escaped text.
        """
        print(f"Escaping LaTeX chars, text begins with: {repr(text[:50])}")
        
        # Define LaTeX special characters and their escaped versions
        latex_special_chars = [
            ('\\', '\\textbackslash{}'),
            ('&', '\\&'),
            ('%', '\\%'),
            ('$', '\\$'),
            ('#', '\\#'),
            ('_', '\\_'),
            ('{', '\\{'),
            ('}', '\\}'),
            ('~', '\\textasciitilde{}'),
            ('^', '\\textasciicircum{}'),
        ]
        
        # Escape LaTeX special characters
        result = text
        for char, escaped in latex_special_chars:
            result = result.replace(char, escaped)
        
        print(f"After escaping, text begins with: {repr(result[:50])}")
        return result


# Function for direct use
def format_as_latex(
    original_content: str,
    critique_report: str,
    peer_review: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None
) -> Tuple[str, Optional[str]]:
    """
    Format critique report and optional peer review into a LaTeX document.
    
    This function provides a simple interface for formatting critique reports
    and peer reviews into LaTeX documents without directly instantiating the
    LatexFormatter class.
    
    Args:
        original_content: The original content that was critiqued.
        critique_report: The generated critique report.
        peer_review: Optional peer review document.
        config: Optional configuration dictionary.
        
    Returns:
        A tuple of (tex_file_path, pdf_file_path), where pdf_file_path
        is None if compilation is not enabled or fails.
    """
    formatter = LatexFormatter(config)
    return formatter.format_document(original_content, critique_report, peer_review)
