"""
Converter for transforming Markdown content to LaTeX format.

This module provides a converter that transforms Markdown-formatted content
into LaTeX-compatible formatting.
"""

import re
from typing import Dict, Any, Optional, List, Match


class MarkdownToLatexConverter:
    """
    Converter for transforming Markdown content to LaTeX format.
    
    This converter handles common Markdown elements like headers, lists,
    emphasis, links, etc., and converts them to appropriate LaTeX commands.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the Markdown to LaTeX converter.
        
        Args:
            config: Optional configuration dictionary for customizing conversion behavior.
        """
        self.config = config or {}
        
    def convert(self, content: str) -> str:
        """
        Convert Markdown content to LaTeX format.
        
        Args:
            content: The Markdown content to convert.
            
        Returns:
            The converted LaTeX content.
        """
        print(f"Starting Markdown conversion. Content begins with: {repr(content[:50])}")
        latex_content = content
        
        # Special handling for peer review credentials sections
        try:
            print("Processing peer review credentials")
            lowered = latex_content.lstrip().lower()
            # Skip credentials processing when the document is an error stub from the peer review generator
            if not (lowered.startswith('# error') or 'scientific peer review formatting failed' in lowered):
                latex_content = self._process_peer_review_credentials(latex_content)
        except Exception as e:
            print(f"Error in _process_peer_review_credentials: {e}")
            # Continue with original content
            pass
        
        # Process the content in a specific order to avoid nested conversions
        
        # 1. Escape LaTeX special characters that aren't part of Markdown syntax
        try:
            print("Escaping LaTeX chars")
            latex_content = self._escape_latex_chars(latex_content)
            print(f"After escaping LaTeX chars: {repr(latex_content[:50])}")
        except Exception as e:
            print(f"Error in _escape_latex_chars: {e}")
            # Instead of failing, continue with unmodified content
            pass
        
        # 2. Convert Markdown headings before handling other elements
        try:
            print("Converting headings")
            latex_content = self._convert_headings(latex_content)
            print(f"After converting headings: {repr(latex_content[:50])}")
        except Exception as e:
            print(f"Error in _convert_headings: {e}")
            # Continue with partially converted content
            pass
        
        # 3. Convert emphasis (bold, italic) and inline code
        try:
            print("Converting emphasis")
            latex_content = self._convert_emphasis(latex_content)
            print(f"After converting emphasis: {repr(latex_content[:50])}")
        except Exception as e:
            print(f"Error in _convert_emphasis: {e}")
            # Continue with partially converted content
            pass
        
        # 4. Convert lists (ordered and unordered)
        latex_content = self._convert_lists(latex_content)
        
        # 5. Convert horizontal rules
        latex_content = self._convert_horizontal_rules(latex_content)
        
        # 6. Convert blockquotes
        latex_content = self._convert_blockquotes(latex_content)
        
        # 7. Convert links and images
        latex_content = self._convert_links(latex_content)
        
        # 8. Convert code blocks
        latex_content = self._convert_code_blocks(latex_content)
        
        # 9. Convert tables (if present)
        latex_content = self._convert_tables(latex_content)
        
        # 10. Handle line breaks and paragraphs
        latex_content = self._convert_line_breaks(latex_content)
        
        return latex_content
    
    def _escape_latex_chars(self, content: str) -> str:
        """
        Escape LaTeX special characters in the content.
        
        Args:
            content: The content to process.
            
        Returns:
            The processed content with LaTeX special characters escaped.
        """
        # Define LaTeX special characters and their escaped versions
        latex_special_chars = [
            # Don't escape \, {, }, and $ as they're used in Markdown syntax
            # and we'll handle them separately
            ('&', r'\&'),
            ('%', r'\%'),
            ('#', r'\#'),
            ('_', r'\_'),
            ('^', r'\^{}'),
            ('~', r'\textasciitilde{}'),
            ('|', r'\textbar{}')
        ]
        
        # Escape LaTeX special characters
        for char, escaped in latex_special_chars:
            content = content.replace(char, escaped)
            
        return content
    
    def _convert_headings(self, content: str) -> str:
        """
        Convert Markdown headings to LaTeX section commands.
        
        Args:
            content: The content to process.
            
        Returns:
            The processed content with headings converted.
        """
        # Handle dividers commonly found in peer review documents
        content = re.sub(
            r'^-{5,}$',
            r'\\hrulefill',
            content,
            flags=re.MULTILINE
        )
        
        # Handle numbered sections like "1. Brief Summary of the Work" in peer reviews
        content = re.sub(
            r'^(\d+)\.\s+(.+?)$',
            r'\\subsection{\2}',
            content,
            flags=re.MULTILINE
        )
        
        # Handle "a. Sub-items" style in peer reviews (common in methodological analysis)
        content = re.sub(
            r'^([a-f])\.\s+(.+?)$',
            r'\\subsubsection{\2}',
            content,
            flags=re.MULTILINE
        )
        
        # Handle ATX-style headings (# Heading)
        heading_patterns = [
            (r'^# (.+?)$', r'\\section{\1}'),
            (r'^## (.+?)$', r'\\subsection{\1}'),
            (r'^### (.+?)$', r'\\subsubsection{\1}'),
            (r'^#### (.+?)$', r'\\paragraph{\1}'),
            (r'^##### (.+?)$', r'\\subparagraph{\1}'),
            (r'^###### (.+?)$', r'\\textbf{\1}\\\\')
        ]
        
        for pattern, replacement in heading_patterns:
            content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
        
        # Handle Setext-style headings (Heading\n=====)
        content = re.sub(
            r'^(.+?)\n=+$',
            r'\\section{\1}',
            content,
            flags=re.MULTILINE
        )
        
        content = re.sub(
            r'^(.+?)\n-+$',
            r'\\subsection{\1}',
            content,
            flags=re.MULTILINE
        )
        
        return content
    
    def _convert_emphasis(self, content: str) -> str:
        """
        Convert Markdown emphasis (bold, italic) to LaTeX formatting.
        
        Args:
            content: The content to process.
            
        Returns:
            The processed content with emphasis converted.
        """
        # Convert bold (** or __)
        content = re.sub(r'\*\*(.+?)\*\*', r'\\textbf{\1}', content)
        content = re.sub(r'__(.+?)__', r'\\textbf{\1}', content)
        
        # Convert italic (* or _) - more careful to avoid matching * in math or lists
        content = re.sub(r'(?<!\*)\*([^*\n]+?)\*(?!\*)', r'\\textit{\1}', content)
        content = re.sub(r'(?<!_)_([^_\n]+?)_(?!_)', r'\\textit{\1}', content)
        
        # Convert inline code (`code`)
        content = re.sub(r'`([^`\n]+?)`', r'\\texttt{\1}', content)
        
        return content
    
    def _convert_lists(self, content: str) -> str:
        """
        Convert Markdown lists to LaTeX list environments.
        
        Args:
            content: The content to process.
            
        Returns:
            The processed content with lists converted.
        """
        # Process unordered lists
        unordered_list_pattern = re.compile(
            r'^(?P<indent> *)(?P<marker>[\*\+\-]) (?P<item>.+?)$',
            re.MULTILINE
        )
        
        # Find all list blocks
        list_blocks = []
        current_block = []
        in_list = False
        
        for line in content.split('\n'):
            match = unordered_list_pattern.match(line)
            if match:
                if not in_list:
                    in_list = True
                current_block.append(line)
            elif in_list and line.strip() == '':
                # Empty line after list items
                current_block.append(line)
            elif in_list:
                # End of list
                in_list = False
                list_blocks.append(('\n'.join(current_block), 'unordered'))
                current_block = []
                
        # Handle case where the last block is a list
        if current_block:
            list_blocks.append(('\n'.join(current_block), 'unordered'))
        
        # Process ordered lists - similar approach but with number markers
        ordered_list_pattern = re.compile(
            r'^(?P<indent> *)(?P<number>\d+)\.+ (?P<item>.+?)$',
            re.MULTILINE
        )
        
        # Convert each list block to LaTeX
        for block, list_type in list_blocks:
            latex_list = ""
            if list_type == 'unordered':
                latex_list = "\\begin{itemize}\n"
                for line in block.split('\n'):
                    match = unordered_list_pattern.match(line)
                    if match:
                        latex_list += f"  \\item {match.group('item')}\n"
                latex_list += "\\end{itemize}"
            else:  # ordered
                latex_list = "\\begin{enumerate}\n"
                for line in block.split('\n'):
                    match = ordered_list_pattern.match(line)
                    if match:
                        latex_list += f"  \\item {match.group('item')}\n"
                latex_list += "\\end{enumerate}"
                
            # Replace the original block with the LaTeX version
            content = content.replace(block, latex_list)
        
        return content
    
    def _convert_horizontal_rules(self, content: str) -> str:
        """
        Convert Markdown horizontal rules to LaTeX horizontal lines.
        
        Args:
            content: The content to process.
            
        Returns:
            The processed content with horizontal rules converted.
        """
        # Convert standard horizontal rules (---, ***, ___)
        hr_pattern = re.compile(r'^(?P<rule>[\*\-_]{3,})$', re.MULTILINE)
        content = hr_pattern.sub(r'\\hrulefill', content)
        
        # Convert peer review style dividers with unicode characters
        peer_divider_pattern = re.compile(r'^(?P<rule>─{3,})$', re.MULTILINE)
        content = peer_divider_pattern.sub(r'\\hrulefill', content)
        
        return content
    
    def _process_peer_review_credentials(self, content: str) -> str:
        """
        Process peer review credentials sections at the top of peer review documents.

        Robustness:
        - Only attempts detection if the document likely contains a peer review section.
        - Uses guarded look-ahead to avoid out-of-range indexing.
        - Returns original content unchanged when no credentials block is detected.

        Args:
            content: The content to process.

        Returns:
            The processed content with peer review credentials formatted, or the original content.
        """
        # Quick signature check; avoid work if it clearly isn't a peer review document
        lowered = content.lower()
        if ("peer review" not in lowered) and ("peer-review" not in lowered):
            return content

        lines = content.split('\n')
        in_credentials = False
        credentials_start = -1
        credentials_end = -1

        for i, line in enumerate(lines):
            # Detect a plausible credentials block beginning after a blank line.
            if (line.strip() == '') and i > 0 and credentials_start == -1:
                if (i + 1) < len(lines):
                    next_line = lines[i + 1]
                    # Heuristic tokens frequently present in credentials
                    if any(token in next_line for token in ('Dr.', 'Ph.D.', 'Professor', 'Department', 'University')):
                        credentials_start = i + 1
                        in_credentials = True
                        continue

            # Credentials block ends on blank line or a visual divider
            if in_credentials and (line.strip() == '' or '─' in line or '---' in line):
                credentials_end = i
                break

        # If a block was detected, format it as an author section centered at top
        if credentials_start != -1 and credentials_end != -1 and credentials_end > credentials_start:
            credentials_lines = lines[credentials_start:credentials_end]
            credentials_text = '\n'.join(credentials_lines).strip()

            if credentials_text:
                formatted_credentials = (
                    "\\begin{center}\n"
                    "\\large\n"
                    f"{credentials_text}\n"
                    "\\end{center}\n"
                    "\\vspace{1em}\n"
                )

                # Replace the original block including the leading blank separator if present
                replace_start = max(credentials_start - 1, 0)
                original_section = '\n'.join(lines[replace_start:credentials_end + 1])
                content = content.replace(original_section, formatted_credentials, 1)

        return content
    
    def _convert_blockquotes(self, content: str) -> str:
        """
        Convert Markdown blockquotes to LaTeX quote environments.
        
        Args:
            content: The content to process.
            
        Returns:
            The processed content with blockquotes converted.
        """
        # Handle peer review indented quotes using spaces or symbols
        # First pattern: handle indented blocks with > at the start
        blockquote_pattern = re.compile(r'^>\s*(.+?)$', re.MULTILINE)
        
        # Find contiguous blockquote lines
        blockquote_blocks = []
        current_block = []
        in_blockquote = False
        
        for line in content.split('\n'):
            match = blockquote_pattern.match(line)
            if match:
                if not in_blockquote:
                    in_blockquote = True
                current_block.append(match.group(1))
            elif in_blockquote and line.strip() == '':
                # Empty line in blockquote
                current_block.append('')
            elif in_blockquote:
                # End of blockquote
                in_blockquote = False
                blockquote_blocks.append('\n'.join(current_block))
                current_block = []
                
        # Handle case where the last block is a blockquote
        if current_block:
            blockquote_blocks.append('\n'.join(current_block))
        
        # Convert each blockquote block to LaTeX
        for block in blockquote_blocks:
            latex_blockquote = "\\begin{quote}\n"
            latex_blockquote += block
            latex_blockquote += "\n\\end{quote}"
            
            # Replace the original block with the LaTeX version
            original_block = '\n'.join([f"> {line}" for line in block.split('\n')])
            content = content.replace(original_block, latex_blockquote)
        
        # Second pattern: handle common peer review style with indented text
        peer_quote_pattern = re.compile(r'^(\s{4,})(.+?)$', re.MULTILINE)
        
        # Find contiguous indented lines
        indented_blocks = []
        current_block = []
        current_indent = ""
        in_indented = False
        
        for line in content.split('\n'):
            match = peer_quote_pattern.match(line)
            if match:
                indent, text = match.groups()
                if not in_indented:
                    in_indented = True
                    current_indent = indent
                if indent == current_indent:  # Same indentation level
                    current_block.append(text)
            elif in_indented and line.strip() == '':
                # Empty line in indented block
                current_block.append('')
            elif in_indented:
                # End of indented block
                in_indented = False
                indented_blocks.append((current_indent, '\n'.join(current_block)))
                current_block = []
                current_indent = ""
                
        # Handle case where the last block is indented
        if current_block:
            indented_blocks.append((current_indent, '\n'.join(current_block)))
        
        # Convert each indented block to LaTeX
        for indent, block in indented_blocks:
            latex_blockquote = "\\begin{quote}\n"
            latex_blockquote += block
            latex_blockquote += "\n\\end{quote}"
            
            # Replace the original block with the LaTeX version
            original_lines = []
            for line in block.split('\n'):
                if line:
                    original_lines.append(f"{indent}{line}")
                else:
                    original_lines.append("")  # Preserve empty lines
            original_block = '\n'.join(original_lines)
            content = content.replace(original_block, latex_blockquote)
        
        return content
    
    def _convert_links(self, content: str) -> str:
        """
        Convert Markdown links and images to LaTeX formatting.
        
        Args:
            content: The content to process.
            
        Returns:
            The processed content with links and images converted.
        """
        # Convert inline links: [text](url)
        content = re.sub(
            r'\[([^\]]+)\]\(([^)]+)\)',
            r'\\href{\2}{\1}',
            content
        )
        
        # Convert images: ![alt](url)
        content = re.sub(
            r'!\[([^\]]*)\]\(([^)]+)\)',
            r'\\includegraphics[width=0.8\\textwidth]{\2}',
            content
        )
        
        return content
    
    def _convert_code_blocks(self, content: str) -> str:
        """
        Convert Markdown code blocks to LaTeX verbatim or listing environments.
        
        Args:
            content: The content to process.
            
        Returns:
            The processed content with code blocks converted.
        """
        # Convert fenced code blocks with backticks: ```lang\ncode\n```
        def replace_fenced_block(match):
            language = match.group(1).strip() if match.group(1) else ""
            code = match.group(2)
            
            if language:
                return f"\\begin{{lstlisting}}[language={language}]\n{code}\n\\end{{lstlisting}}"
            else:
                return f"\\begin{{verbatim}}\n{code}\n\\end{{verbatim}}"
        
        # Match fenced code blocks
        content = re.sub(
            r'```([^`\n]*)\n(.*?)\n```',
            replace_fenced_block,
            content,
            flags=re.DOTALL
        )
        
        # Convert indented code blocks (4 spaces or 1 tab)
        # This is more complex and would require preserving contiguous indented blocks
        
        return content
    
    def _convert_tables(self, content: str) -> str:
        """
        Convert Markdown tables to LaTeX tabular environments.
        
        Args:
            content: The content to process.
            
        Returns:
            The processed content with tables converted.
        """
        # Find table blocks (header, separator, and rows)
        table_pattern = re.compile(
            r'^([^\n]+\|[^\n]+)\n( *\|:?-+:?\| *)+\n((^[^\n]+\|[^\n]+\n)+)',
            re.MULTILINE
        )
        
        for match in table_pattern.finditer(content):
            table_block = match.group(0)
            header = match.group(1)
            rows = match.group(3)
            
            # Process header
            header_cells = [cell.strip() for cell in header.split('|') if cell.strip()]
            num_columns = len(header_cells)
            
            # Create LaTeX table
            latex_table = "\\begin{tabular}{" + "|".join(["c"] * num_columns) + "}\n"
            latex_table += "\\hline\n"
            
            # Add header row
            latex_table += " & ".join(header_cells) + " \\\\ \\hline\n"
            
            # Add data rows
            for row in rows.strip().split('\n'):
                row_cells = [cell.strip() for cell in row.split('|') if cell.strip()]
                latex_table += " & ".join(row_cells) + " \\\\ \\hline\n"
            
            # Close the table
            latex_table += "\\end{tabular}"
            
            # Replace the original table with the LaTeX version
            content = content.replace(table_block, latex_table)
        
        return content
    
    def _convert_line_breaks(self, content: str) -> str:
        """
        Convert Markdown line breaks and paragraphs to LaTeX formatting.
        
        Args:
            content: The content to process.
            
        Returns:
            The processed content with line breaks and paragraphs converted.
        """
        # Convert double line breaks to paragraph breaks
        content = re.sub(r'\n\s*\n', r'\n\n', content)
        
        # Convert explicit line breaks (line ending with two spaces)
        content = re.sub(r'  \n', r' \\\\\n', content)
        
        return content
