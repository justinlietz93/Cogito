"""CLI entrypoint for the research proposal generation workflow."""
from __future__ import annotations

<<<<<<< HEAD
=======
This module ingests ONLY from the project INPUT/ directory,
combines an arbitrary number of files (recursively), and has the AI
generate a formal academic research proposal from that corpus.
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Optional
>>>>>>> 7f5694d (Add comprehensive test scripts for LaTeX configuration, content extraction, and vector store functionality)
import argparse
from pathlib import Path
from typing import Sequence

from .ai_clients import AIOrchestrator
from .application.research_generation import ResearchProposalGenerationService
from .application.research_generation.exceptions import ProjectDocumentsNotFound
from .infrastructure.research_generation import FileSystemResearchGenerationRepository
from .infrastructure.thesis.ai_client import OrchestratorContentGenerator

<<<<<<< HEAD
_DEFAULT_MAX_TOKENS = 20_000
=======
# Import the existing AI clients correctly
from src.syncretic_catalyst.ai_clients import Claude37SonnetClient, DeepseekR1Client
from src.input_reader import find_all_input_files
>>>>>>> 7f5694d (Add comprehensive test scripts for LaTeX configuration, content extraction, and vector store functionality)


def build_service(
    project_dir: Path, *, model: str | None = None, default_max_tokens: int = _DEFAULT_MAX_TOKENS
) -> tuple[ResearchProposalGenerationService, FileSystemResearchGenerationRepository]:
    """Compose the generation service and its dependencies."""

    orchestrator = AIOrchestrator(model)
    generator = OrchestratorContentGenerator(
        orchestrator, default_max_tokens=default_max_tokens
    )
    repository = FileSystemResearchGenerationRepository(project_dir)
    service = ResearchProposalGenerationService(
        project_repository=repository,
        output_repository=repository,
        content_generator=generator,
        max_tokens=default_max_tokens,
    )
    return service, repository


def main(argv: Sequence[str] | None = None) -> int:
    """Execute the research generation workflow."""

    parser = argparse.ArgumentParser(
        description="Generate an academic research proposal from project documents."
    )
    parser.add_argument(
        "--model",
        help=(
            "Optional provider override. If omitted the configured primary provider "
            "will be used."
        ),
    )
    parser.add_argument(
        "--project-dir",
        type=Path,
        default=Path("some_project"),
        help="Project workspace containing the doc/ directory and output artefacts.",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=None,
        help="Optional override for the response token budget.",
    )

    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
<<<<<<< HEAD
        service, repository = build_service(args.project_dir, model=args.model)
    except OSError as exc:
        print(
            f"Error: Failed to prepare project directory '{args.project_dir}': {exc}"
        )
        return 1
=======
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return f"[Content from {file_path.name} could not be read]"

def get_project_title(doc_folder: Path) -> str:
    """Extract the project title from the BREAKTHROUGH_BLUEPRINT.md file."""
    blueprint_path = doc_folder / "BREAKTHROUGH_BLUEPRINT.md"
    if blueprint_path.exists():
        content = read_file_content(blueprint_path)
        lines = content.split('\n')
        for line in lines:
            if line.startswith('# '):
                return line.replace('# ', '')

def prepare_prompt(file_contents: Dict[str, str], project_title: str) -> str:
    """Prepare the prompt for the AI model."""
    prompt = f"""
Create a formal academic research proposal for a project titled "{project_title}".

Use the following content from previous design documents to create a comprehensive, well-structured academic research proposal. Format it according to standard academic conventions with proper sections, citations, and academic tone.

The research proposal should include:
1. Title Page
2. Abstract
3. Introduction and Problem Statement
4. Literature Review
5. Research Questions and Objectives
6. Methodology and Technical Approach
7. Implementation Plan and Timeline
8. Expected Results and Impact
9. Conclusion
10. References

Below are the source documents to synthesize into the proposal:

"""
    
    # Add each file's content to the prompt
    # Iterate deterministically over provided files (by section/file name)
    for file_name in sorted(file_contents.keys(), key=lambda x: x.lower()):
        section_name = file_name.replace('.md', '').replace('_', ' ').title()
        prompt += f"\n===== {section_name} =====\n"
        prompt += file_contents[file_name]
        prompt += "\n\n"

    prompt += """
Create a cohesive, professionally formatted academic research proposal that integrates these materials. 
Use formal academic language and structure. Ensure proper citation of external works where appropriate.
Focus on presenting this as a serious, innovative research initiative with clear methodology and expected outcomes.
The proposal should be comprehensive enough for submission to a major research funding organization.
"""

    return prompt

def save_proposal(content: str, output_path: Path) -> None:
    """Save the generated proposal to a file."""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Research proposal saved to {output_path}")

def check_environment_variables():
    """Check and display the status of environment variables."""
    print("\nEnvironment Variable Status:")
    
    # Check for Anthropic API key
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    if anthropic_key:
        key_preview = anthropic_key[:6] + "..." + anthropic_key[-4:] if len(anthropic_key) > 10 else "***"
        print(f"✓ ANTHROPIC_API_KEY is set: {key_preview}")
    else:
        print("❌ ANTHROPIC_API_KEY is not set in environment variables")
    
    # Check for DeepSeek API key
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY")
    if deepseek_key:
        key_preview = deepseek_key[:6] + "..." + deepseek_key[-4:] if len(deepseek_key) > 10 else "***" 
        print(f"✓ DEEPSEEK_API_KEY is set: {key_preview}")
    else:
        print("❌ DEEPSEEK_API_KEY is not set in environment variables")
        
    # List all environment variables (for debugging)
    print("\nDebug: All environment variable names:")
    for i, (key, _) in enumerate(os.environ.items()):
        print(f"  {key}")
        if i >= 20:  # Limit to first 20 to avoid overwhelming output
            print(f"  ... and {len(os.environ) - 20} more")
            break

def generate_ai_proposal(model: str = "claude") -> None:
    """
    Generate a research proposal using AI.
    
    Args:
        model: The AI model to use ('claude' or 'deepseek')
    """
    # Check environment variables
    check_environment_variables()
    
    # Enforce ingestion ONLY from INPUT/
    COGITO_ROOT = Path(__file__).resolve().parents[2]
    input_dir = COGITO_ROOT / "INPUT"
    output_folder = Path("some_project")
    
    if not input_dir.exists() or not input_dir.is_dir():
        print(f"Error: INPUT directory does not exist at {input_dir}")
        return
    
    # Discover and read all files under INPUT/ (recursive); supports arbitrary number of files
    file_contents = {}
    try:
        candidates = find_all_input_files(base_dir=str(COGITO_ROOT), input_dir_name="INPUT", recursive=True)
    except Exception as e:
        print(f"Error discovering INPUT files: {e}")
        return
    
    if not candidates:
        print(f"Error: No input files found under {input_dir}")
        return
    
    from os.path import basename
    for abs_path in candidates:
        try:
            name = basename(abs_path)
            file_contents[name] = read_file_content(Path(abs_path))
        except Exception as e:
            print(f"Warning: failed to read {abs_path}: {e}")
    
    # Get project title
    project_title = "INPUT Corpus"
    
    # Prepare the prompt
    prompt = prepare_prompt(file_contents, project_title)
    
    # Save the prompt for reference
    with open(output_folder / "ai_prompt.txt", 'w', encoding='utf-8') as f:
        f.write(prompt)
    print(f"Prompt saved to {output_folder}/ai_prompt.txt")
    
    # Call the appropriate AI client directly with the correct method
    ai_response = None
>>>>>>> 7f5694d (Add comprehensive test scripts for LaTeX configuration, content extraction, and vector store functionality)
    try:
        result = service.generate_proposal(max_tokens=args.max_tokens)
    except ProjectDocumentsNotFound as exc:
        print(f"Error: {exc}")
        return 1
    except RuntimeError as exc:
        print(f"Error: {exc}")
        return 1
    except OSError as exc:
        print(f"Error: Failed to write proposal artefacts: {exc}")
        return 1

    print(f"Prompt saved to {repository.prompt_path}")
    print(f"Research proposal saved to {repository.proposal_path}")
    print(f"Project title: {result.project_title}")
    return 0


if __name__ == "__main__":  # pragma: no cover - manual execution path
    raise SystemExit(main())
