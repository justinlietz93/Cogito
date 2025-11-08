#!/usr/bin/env python3
"""
Direct LaTeX generator that bypasses complex markdown conversion.

This script provides a simple, direct approach to generating LaTeX from
peer review files without complex markdown conversion.
"""

import os
import re
import logging
import argparse
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add repository root to path
import sys
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

def simplify_to_latex(content, title=None):
    """
    Convert markdown content to LaTeX by using a simplified approach.
    
    Instead of trying to handle all markdown syntax, just do minimal processing
    to ensure the LaTeX compiles correctly.
    
    Args:
        content: The markdown content to convert
        title: Optional title override
        
    Returns:
        LaTeX content ready for compilation
    """
    # Extract title if not provided
    if not title:
        title_match = re.search(r'^# (.+?)$', content, re.MULTILINE)
        if title_match:
            title = title_match.group(1)
        else:
            title = "Scientific Review"
    
    # First, handle the header markers to avoid escaping issues
    result = []
    for line in content.split('\n'):
        if line.startswith('# '):  # Top-level heading
            result.append(f"\\section{{{line[2:]}}}")
        elif line.startswith('## '):  # Second-level heading
            result.append(f"\\subsection{{{line[3:]}}}")
        elif line.startswith('### '):  # Third-level heading
            result.append(f"\\subsubsection{{{line[4:]}}}")
        elif re.match(r'^\d+\.\s+.+$', line):  # Numbered sections
            match = re.match(r'^(\d+)\.\s+(.+)$', line)
            if match:
                result.append(f"\\subsection{{{match.group(2)}}}")
        elif line.startswith('---') or line.startswith('───'):  # Horizontal rules
            result.append("\\hrulefill")
        else:
            result.append(line)
    
    # Join the processed lines back into a string
    latex_content = '\n'.join(result)
    
    # Escape LaTeX special characters that aren't part of markup
    for char, escaped in [('%', r'\%'), ('&', r'\&'), ('$', r'\$'), 
                         ('_', r'\_'), ('#', r'\#')]:
        latex_content = latex_content.replace(char, escaped)
    
    # Convert basic markdown emphasis
    latex_content = re.sub(r'\*\*(.+?)\*\*', r'\\textbf{\1}', latex_content)
    latex_content = re.sub(r'\*(.+?)\*', r'\\textit{\1}', latex_content)
    
    # Handle lists (bullet points only)
    latex_content = re.sub(r'^\s*\* (.+?)$', r'\\begin{itemize}\n\\item \1\n\\end{itemize}', 
                         latex_content, flags=re.MULTILINE)
    
    # Remove markdown-style blockquotes
    latex_content = re.sub(r'^>\s*(.+?)$', r'\1', latex_content, flags=re.MULTILINE)
    
    # Create the most basic LaTeX document possible
    document = f"""\\documentclass{{article}}

% Minimal required packages
\\usepackage[utf8]{{inputenc}}

% Document metadata
\\title{{{title}}}
\\author{{Scientific Review Council}}
\\date{{\\today}}

\\begin{{document}}

% Title section
\\maketitle

{latex_content}

\\end{{document}}
"""
    
    return document


def direct_latex_from_peer_review():
    """
    Generate LaTeX directly from a peer review file with minimal markdown processing.
    """
    logger.info("Generating direct LaTeX from peer review file")
    
    # Find the most recent peer review file
    critiques_dir = Path("critiques")
    peer_review_files = list(critiques_dir.glob("content_peer_review_*.md"))
    
    if not peer_review_files:
        logger.error("No peer review files found in 'critiques' directory")
        return False
    
    # Sort by modification time to get the most recent
    peer_review_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    peer_review_file = peer_review_files[0]
    
    logger.info(f"Using peer review file: {peer_review_file}")
    
    # Read peer review content
    with open(peer_review_file, "r", encoding="utf-8") as f:
        peer_review_content = f.read()
    
    # Generate direct LaTeX with ultra-minimal processing
    latex_content = simplify_to_latex(peer_review_content)
    
    # Extra safety - replace any remaining troublesome characters
    replacements = [
        ('─', '-'),        # Replace Unicode dash with ASCII dash
        ('…', '...'),      # Replace ellipsis with periods
        ('—', '--'),       # Replace em dash
        ('–', '-'),        # Replace en dash
        ('"', '"'),        # Replace smart quotes
        ('"', '"'),        # Replace smart quotes
        (''', "'"),        # Replace smart apostrophes
        (''', "'"),        # Replace smart apostrophes
        ('≈', '$\\approx$'),  # Replace approximate symbol
        ('≠', '$\\neq$'),   # Replace not equal symbol
        ('°', '$^{\\circ}$'),  # Replace degree symbol
        ('\t', '    '),    # Replace tabs with spaces
    ]
    
    for old, new in replacements:
        latex_content = latex_content.replace(old, new)
    
    # Force cleanup any remaining problematic lines
    clean_lines = []
    for line in latex_content.split('\n'):
        # Skip raw markdown section headers that weren't caught by the initial processing
        if line.strip().startswith('#'):
            continue
        clean_lines.append(line)
    
    latex_content = '\n'.join(clean_lines)
    
    # Write LaTeX output
    output_dir = Path("latex_output")
    output_dir.mkdir(exist_ok=True)
    
    output_file = output_dir / "direct_peer_review.tex"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(latex_content)
    
    logger.info(f"LaTeX file generated: {output_file}")
    
    # Attempt to compile PDF if pdflatex is available
    try:
        import subprocess
        result = subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "-output-directory=latex_output", output_file],
            capture_output=True,
            text=True,
            check=False,
        )
        
        if result.returncode == 0:
            pdf_file = output_dir / "direct_peer_review.pdf"
            logger.info(f"PDF compiled successfully: {pdf_file}")
            return True
        else:
            logger.error(f"PDF compilation failed: {result.stderr}")
            return False
    except FileNotFoundError:
        logger.warning("pdflatex not found, skipping PDF compilation")
        return True
    except Exception as e:
        logger.error(f"Error during PDF compilation: {e}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Generate direct LaTeX from peer review files')
    args = parser.parse_args()
    
    success = direct_latex_from_peer_review()
    
    if success:
        print("\nSUCCESS: Direct LaTeX generation completed")
        sys.exit(0)
    else:
        print("\nFAILURE: Direct LaTeX generation failed")
        sys.exit(1)
