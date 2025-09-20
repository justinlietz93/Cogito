"""
Test script for LaTeX document generation.

This script tests the LaTeX document generation functionality without
running the full critique pipeline. It can test both philosophical and
scientific modes.
"""
import os
import sys
import shutil
import argparse
import datetime
import platform
from pathlib import Path

# Add parent directory to path to allow imports
sys.path.insert(0, str(Path(__file__).absolute().parent.parent.parent))

from src.latex.formatter import format_as_latex
from src.latex.processors.citation_processor import CitationProcessor


def generate_sample_content(scientific_mode):
    """
    Generate sample content for testing based on the mode.
    
    Args:
        scientific_mode: Whether to generate content for scientific mode
        
    Returns:
        Tuple of (original_content, critique_content, peer_review_content)
    """
    # Original content with citations - simplified to avoid any problematic characters
    original_content = """This is a sample document to test the LaTeX generation.
It includes references to scholarly works by Aristotle (1984), Descartes (1996), and Kant (1998).

The content provides a theoretical framework that could be analyzed using various 
methodological approaches. It contains mathematical expressions like E = mc^2 and
philosophical concepts that might be processed.
"""
    
    # Generate mode-appropriate critique content
    if scientific_mode:
        critique_content = """# Scientific Methodology Analysis

## Systems Analysis

This content requires further analysis of component interactions and structural optimization.
The system described by Aristotle (1984) lacks modularity in its approach.

## First Principles Analysis

The foundational assumptions presented by Descartes (1996) require formal validation.
When analyzed from first principles, we observe inconsistencies in the axiomatic framework.

## Boundary Condition Analysis

Operational limits are not well-defined, leading to potential issues at edge cases.
The constraints model proposed by Kant (1998) provides a better framework for boundary analysis.

## Empirical Validation Analysis

The claims made are not empirically testable in their current form and lack falsifiability.
"""
    else:
        critique_content = """# Philosophical Critique Report

## Aristotelian Analysis

The teleological structure of the arguments follows Aristotelian principles of form and function.
However, as noted by Aristotle (1984), proper categorization is essential.

## Cartesian Analysis

Applying methodical doubt as described by Descartes (1996) reveals several unexamined assumptions.
When we reduce the arguments to clear and distinct ideas, significant gaps emerge.

## Kantian Analysis

The framework lacks proper consideration of a priori synthetic judgments.
According to Kant (1998), transcendental arguments require careful structure.
"""

    # Generate peer review content
    if scientific_mode:
        peer_review_content = """# Scientific Peer Review

## Dr. Emily Richards, Ph.D.
### Center for Applied Methodological Research, Stanford University
### Specialization: Scientific Methodology and Systems Analysis

This peer review evaluates the methodology analysis report using scientific criteria.
The systems analysis correctly identifies structural inefficiencies in the original content.
The first principles analysis by Descartes (1996) provides a solid foundation.

However, the boundary condition analysis needs strengthening with more specific operational limits.
"""
    else:
        peer_review_content = """# Philosophical Peer Review

## Dr. Jonathan Smith, Ph.D.
### Department of Philosophy, Harvard University
### Specialization: Comparative Philosophy and Epistemology

This peer review evaluates the philosophical critique from a scholarly perspective.
The Aristotelian analysis correctly identifies teleological elements in the argument structure.
The Cartesian approach by Descartes (1996) effectively applies methodical doubt.

However, the Kantian analysis could be strengthened with more explicit references to the Critique of Pure Reason.
"""
    
    return original_content, critique_content, peer_review_content


def run_latex_generation(scientific_mode=False, clean=False, output_dir="latex_output", compile_pdf=False):
    """Generate LaTeX artifacts for downstream assertions and manual runs.

    Args:
        scientific_mode: Whether to emit the scientific variant of the template.
        clean: When true, the output directory is purged before rendering.
        output_dir: Folder that receives the generated TeX (and optional PDF) files.
        compile_pdf: If set, attempt to compile the TeX output into a PDF.

    Returns:
        Tuple containing a success flag, the TeX file path, and the optional PDF path.
    """
    print(f"Testing LaTeX generation (Scientific Mode: {scientific_mode})...")
    
    # Clean output directory if requested
    if clean and os.path.exists(output_dir):
        print(f"Cleaning output directory: {output_dir}")
        shutil.rmtree(output_dir)
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate sample content
    original_content, critique_content, peer_review_content = generate_sample_content(scientific_mode)
    
    # Configure LaTeX formatting
    config = {
        'output_dir': output_dir,
        'compile_pdf': compile_pdf,
        'scientific_objectivity_level': 'high',
        'include_bibliography': True,
        'scientific_mode': scientific_mode,
        'output_filename': f"{'scientific' if scientific_mode else 'philosophical'}_test"
    }
    
    try:
        # Print first 50 characters of content for debugging
        print(f"Original content starts with: {repr(original_content[:50])}")
        print(f"Critique content starts with: {repr(critique_content[:50])}")
        print(f"Peer review content starts with: {repr(peer_review_content[:50])}")
        
        # Generate the LaTeX document
        tex_path, pdf_path = format_as_latex(
            original_content,
            critique_content,
            peer_review_content,
            config
        )
        
        # Check if the bibliography file was generated
        bib_path = os.path.join(output_dir, 'bibliography.bib')
        if os.path.exists(bib_path):
            print(f"Bibliography file generated: {bib_path}")
            # Read the first few lines to check the format
            with open(bib_path, 'r', encoding='utf-8') as f:
                bib_header = ''.join(f.readline() for _ in range(5))
                print(f"Bibliography header:\n{bib_header}...")
        else:
            print("Warning: Bibliography file was not generated")
        
        # Report success
        if tex_path:
            print(f"LaTeX document generated: {tex_path}")
            # Read the first few lines to verify content
            with open(tex_path, 'r', encoding='utf-8') as f:
                tex_header = ''.join(f.readline() for _ in range(10))
                print(f"LaTeX header:\n{tex_header}...")
        if pdf_path:
            print(f"PDF document generated: {pdf_path}")
            
        return True, tex_path, pdf_path
    
    except Exception as e:
        print(f"Error generating LaTeX document: {e}")
        return False, None, None


def test_latex_generation(tmp_path: Path):
    """Pytest-facing shim ensuring the helper succeeds without returning values."""

    output_directory = tmp_path / "latex_output"
    success, tex_path, pdf_path = run_latex_generation(
        scientific_mode=False,
        clean=True,
        output_dir=str(output_directory),
        compile_pdf=False,
    )

    assert success, "Sample LaTeX generation should complete without errors"
    assert tex_path, "A LaTeX document path should always be produced"
    assert Path(tex_path).exists(), "The LaTeX document should be written to disk"
    assert pdf_path is None, "PDF compilation is disabled in the regression test"


def main():
    """Main entry point for the test script."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Test LaTeX document generation.")
    parser.add_argument("--scientific", action="store_true", help="Use scientific mode")
    parser.add_argument("--clean", action="store_true", help="Clean output directory before running")
    parser.add_argument("--output-dir", type=str, default="latex_output", help="Output directory")
    parser.add_argument("--no-compile", action="store_true", help="Skip PDF compilation (default: will try to compile)")
    args = parser.parse_args()
    
    # Run the test
    success, tex_path, pdf_path = run_latex_generation(
        scientific_mode=args.scientific,
        clean=args.clean,
        output_dir=args.output_dir,
        compile_pdf=not args.no_compile  # Default to compiling unless --no-compile is specified
    )
    
    # Report final status
    if success:
        print("\nTest completed successfully!")
        # Print absolute paths for easier navigation
        output_dir_abs = os.path.abspath(args.output_dir)
        print(f"Output directory: {output_dir_abs}")
        
        if tex_path:
            print(f"Generated LaTeX file: {os.path.basename(tex_path)}")
        if pdf_path:
            print(f"Generated PDF file: {os.path.basename(pdf_path)}")
            
        # Print command to open the output directory in file explorer (platform-specific)
        if platform.system() == "Windows":
            print(f"\nView files with: explorer \"{output_dir_abs}\"")
        elif platform.system() == "Darwin":  # macOS
            print(f"\nView files with: open \"{output_dir_abs}\"")
        else:  # Linux and others
            print(f"\nView files with: xdg-open \"{output_dir_abs}\"")
        return 0
    else:
        print("\nTest failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
