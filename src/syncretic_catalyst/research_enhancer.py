"""Command-line entrypoint for the research enhancement workflow."""
from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path
from typing import Sequence

from .ai_clients import AIOrchestrator
from .application.research_enhancement import (
    ProjectDocumentsNotFound,
    ResearchEnhancementService,
)
from .domain import ResearchEnhancementResult
from .infrastructure import (
    ArxivReferenceService,
    FileSystemResearchEnhancementRepository,
    OrchestratorContentGenerator,
)

<<<<<<< HEAD
_LOGGER = logging.getLogger(__name__)
=======
# Import the vector search functionality
from src.arxiv.arxiv_vector_reference_service import ArxivVectorReferenceService
from src.arxiv.smart_vector_store import ArxivSmartStore
from src.input_reader import find_all_input_files as ingest_find_all, concatenate_inputs as ingest_concat
>>>>>>> 7f5694d (Add comprehensive test scripts for LaTeX configuration, content extraction, and vector store functionality)


def enhance_research(
    *,
    model: str | None = None,
    force_fallback: bool = False,
    output_dir: str = "some_project",
    max_papers: int = 20,
    max_concepts: int | None = None,
) -> ResearchEnhancementResult:
    """Run the research enhancement workflow and return the resulting artefacts."""

    base_dir = Path(output_dir)
    orchestrator = AIOrchestrator(model_name=model)
    generator = OrchestratorContentGenerator(orchestrator)
    reference_service = ArxivReferenceService(
        cache_root=Path("storage"), force_fallback=force_fallback
    )
    repository = FileSystemResearchEnhancementRepository(base_dir)

    service = ResearchEnhancementService(
        reference_service=reference_service,
        project_repository=repository,
        content_generator=generator,
    )

    _LOGGER.info("Starting Syncretic Catalyst research enhancement")
    start = time.time()

    result = service.enhance(max_papers=max_papers, max_concepts=max_concepts)

    duration = time.time() - start
    _LOGGER.info("Enhancement completed in %.2f seconds", duration)
    _LOGGER.info("Extracted %s key concepts", len(result.key_concepts))
    _LOGGER.info("Retrieved %s relevant papers", len(result.papers))
    _LOGGER.info("Outputs written to %s", base_dir)

    return result


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Enhance research proposals using vector search and LLM analysis",
    )
    parser.add_argument(
        "--model",
        dest="model",
        help="Optional provider override (e.g. claude, deepseek, openai, gemini)",
    )
    parser.add_argument(
        "--force-fallback",
        action="store_true",
        help="Force use of the fallback vector store implementation",
    )
    parser.add_argument(
        "--output-dir",
        default="some_project",
        help="Directory that contains the project documents and receives outputs",
    )
    parser.add_argument(
        "--max-papers",
        type=int,
        default=20,
        help="Maximum number of papers to retrieve during enhancement",
    )
    parser.add_argument(
        "--max-concepts",
        type=int,
        help="Optional override for the maximum number of key concepts to extract",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO)

    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        enhance_research(
            model=args.model,
            force_fallback=args.force_fallback,
            output_dir=args.output_dir,
            max_papers=args.max_papers,
            max_concepts=args.max_concepts,
        )
    except ProjectDocumentsNotFound as exc:
        _LOGGER.error("%s", exc)
        _LOGGER.error(
            "No project documents were found in %%s. Populate the directory with Syncretic Catalyst"
            " outputs before running enhancement.",
            Path(args.output_dir) / "doc",
        )
        return 1
    except Exception as exc:  # pragma: no cover - defensive logging
        _LOGGER.error("Research enhancement failed: %s", exc)
        return 1
    return 0

<<<<<<< HEAD
=======
def analyze_research_gaps(project_content: str, papers: List[Dict[str, Any]], ai_client) -> str:
    """
    Analyze research gaps between the project and existing literature.
    
    Args:
        project_content: Combined content from project documents
        papers: List of paper metadata dictionaries
        ai_client: AI client instance for analysis
        
    Returns:
        Analysis of research gaps
    """
    # Prepare a prompt to analyze research gaps
    paper_summaries = []
    for i, paper in enumerate(papers[:10], 1):  # Limit to 10 papers for prompt size
        title = paper.get('title', 'Unknown Title')
        authors = paper.get('authors', [])
        if authors and isinstance(authors[0], dict):
            author_names = [a.get('name', '') for a in authors if a.get('name')]
        else:
            author_names = authors if isinstance(authors, list) else []
        author_text = ', '.join(author_names) if author_names else 'Unknown Authors'
        summary = paper.get('summary', 'No summary available')
        
        paper_summaries.append(f"{i}. \"{title}\" by {author_text}\nSummary: {summary[:300]}...")
    
    paper_text = '\n\n'.join(paper_summaries)
    
    prompt = f"""
Research Gap Analysis

Please analyze the following research project description and identify gaps or novel contributions 
when compared to the existing literature (ArXiv papers) provided below.

Focus on:
1. Identifying unique aspects of the proposed research not covered in existing literature
2. Potential novel connections between concepts in the project and existing research
3. Areas where the project could make meaningful contributions to the field
4. Suggestions for strengthening the project's novelty and impact

=== PROJECT DESCRIPTION ===
{project_content[:5000]}...
(Project description truncated for brevity)

=== RELEVANT EXISTING LITERATURE ===
{paper_text}

=== ANALYSIS REQUESTED ===
Please provide a detailed analysis of research gaps and novel contribution opportunities, 
structured in the following sections:
1. Uniqueness Analysis - How the project differs from existing work
2. Novel Connections - Potential connections between this project and existing research
3. Contribution Opportunities - Specific areas where this project could contribute to the field
4. Recommendations - Suggestions to strengthen the project's novelty and impact
"""
    
    # Send to AI for analysis
    messages = [
        {"role": "system", "content": "You are a research scientist with expertise in identifying research gaps and novel contributions in academic proposals."},
        {"role": "user", "content": prompt}
    ]
    
    try:
        response = ai_client.run(messages, max_tokens=4000)
        return response
    except Exception as e:
        print(f"Error requesting AI analysis: {e}")
        return "Error: Unable to generate research gap analysis."

def enhance_research_proposal(project_content: str, 
                             papers: List[Dict[str, Any]], 
                             research_gaps: str,
                             ai_client) -> str:
    """
    Enhance a research proposal with relevant citations and insights.
    
    Args:
        project_content: Combined content from project documents
        papers: List of paper metadata dictionaries
        research_gaps: Analysis of research gaps
        ai_client: AI client instance for enhancement
        
    Returns:
        Enhanced research proposal
    """
    # Create citation data
    citations = []
    for i, paper in enumerate(papers, 1):
        title = paper.get('title', 'Unknown Title')
        authors = paper.get('authors', [])
        if authors and isinstance(authors[0], dict):
            author_names = [a.get('name', '') for a in authors if a.get('name')]
        else:
            author_names = authors if isinstance(authors, list) else []
        author_text = ', '.join(author_names) if author_names else 'Unknown Authors'
        published = paper.get('published', '').split('T')[0] if paper.get('published') else 'n.d.'
        arxiv_id = paper.get('id', '').split('v')[0] if paper.get('id') else 'unknown'
        
        citation = f"{i}. {author_text}. ({published}). \"{title}\". arXiv:{arxiv_id}."
        citations.append(citation)
    
    citations_text = '\n'.join(citations)
    
    prompt = f"""
Research Proposal Enhancement

Please enhance the following research project with insights from the research gap analysis
and integrate relevant citations from the provided literature.

=== PROJECT CONTENT ===
{project_content[:7000]}...
(Project content truncated for brevity)

=== RESEARCH GAP ANALYSIS ===
{research_gaps}

=== RELEVANT LITERATURE (For Citations) ===
{citations_text}

=== ENHANCEMENT REQUESTED ===
Create an enhanced academic research proposal that:
1. Maintains the original project's core ideas and structure
2. Incorporates insights from the research gap analysis
3. Integrates relevant citations from the literature list
4. Strengthens the proposal's academic rigor and novelty claims
5. Includes a proper literature review section and bibliography

Format the proposal as a formal academic document with all necessary sections.
"""
    
    # Send to AI for enhancement
    messages = [
        {"role": "system", "content": "You are an expert academic writer specializing in creating rigorous research proposals with proper citations and academic formatting."},
        {"role": "user", "content": prompt}
    ]
    
    try:
        response = ai_client.run(messages, max_tokens=10000)
        return response
    except Exception as e:
        print(f"Error requesting AI enhancement: {e}")
        return "Error: Unable to generate enhanced research proposal."

def save_output(content: str, file_path: Path) -> None:
    """Save content to a file."""
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Saved to {file_path}")

def combine_project_content(doc_folder: Path) -> str:
    """Combine content from all project documents."""
    combined_content = ""
    
    for file_name in FILE_ORDER:
        file_path = doc_folder / file_name
        if file_path.exists():
            section_name = file_name.replace('.md', '').replace('_', ' ').title()
            content = read_file_content(file_path)
            combined_content += f"\n\n## {section_name}\n\n{content}"
    
    return combined_content

def enhance_research(model: str = "claude", force_fallback: bool = False) -> None:
    """
    Enhance research with vector search and AI analysis.
    
    Args:
        model: The AI model to use ('claude' or 'deepseek')
        force_fallback: Whether to force the use of the fallback vector store implementation
    """
    print("Starting Research Enhancement with Vector Search")
    
    # 1. Set up paths (ingest ONLY from INPUT/)
    COGITO_ROOT = Path(__file__).resolve().parents[2]
    input_dir = COGITO_ROOT / "INPUT"
    output_folder = Path("some_project")  # keep existing output location
    
    # Create output folder if not exists
    output_folder.mkdir(parents=True, exist_ok=True)
    
    # Enforce INPUT/ directory existence
    if not input_dir.exists() or not input_dir.is_dir():
        print(f"Error: INPUT directory does not exist at {input_dir}")
        return
    
    # 2. Setup the vector reference service
    print("Initializing ArXiv Vector Reference Service...")
    config = {
        'arxiv': {
            'cache_dir': 'storage/arxiv_cache',
            'vector_cache_dir': 'storage/arxiv_vector_cache',
            'cache_ttl_days': 30,
            'force_vector_fallback': force_fallback
        }
    }
    reference_service = ArxivVectorReferenceService(config=config)
    
    # 3. Initialize the AI client using the orchestrator
    ai_client = None
    try:
        # Try import with different approaches for AIOrchestrator
        try:
            # Try relative import first
            from .ai_clients import AIOrchestrator
            print("Imported AIOrchestrator (relative import)")
        except ImportError:
            # Try absolute import
            try:
                from src.syncretic_catalyst.ai_clients import AIOrchestrator
                print("Imported AIOrchestrator (absolute import)")
            except ImportError:
                # Fall back to direct import
                from ai_clients import AIOrchestrator
                print("Imported AIOrchestrator (direct import)")
                
        # Create the orchestrator with optional model override
        orchestrator = AIOrchestrator(model_name=model)
        
        # Create a simple adapter that mimics the interface expected by our other functions
        class AIClientAdapter:
            def __init__(self, orchestrator):
                self.orchestrator = orchestrator
                
            def run(self, messages, max_tokens=4000):
                # Extract system and user prompts
                system_prompt = None
                user_prompt = ""
                
                for msg in messages:
                    if msg["role"] == "system":
                        system_prompt = msg["content"]
                    elif msg["role"] == "user":
                        user_prompt += msg["content"]
                
                # Default system prompt if none provided
                if not system_prompt:
                    system_prompt = "You are a helpful research assistant."
                
                # Call the orchestrator
                return self.orchestrator.call_llm(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    max_tokens=max_tokens
                )
        
        # Create the adapter
        ai_client = AIClientAdapter(orchestrator)
        print(f"Using AI provider based on configuration or override: {model if model else 'from config'}")
        
    except Exception as e:
        print(f"Error initializing AI client: {e}")
        return
    
    # 4. Ingest INPUT/ corpus and combine content (supports arbitrary number of files)
    try:
        candidates = ingest_find_all(base_dir=str(COGITO_ROOT), input_dir_name="INPUT", recursive=True)
    except Exception as e:
        print(f"Error discovering INPUT files: {e}")
        return
    
    if not candidates:
        print(f"Error: No input files found under {input_dir}")
        return
    
    print(f"INGEST: Found {len(candidates)} input files under {input_dir}")
    combined_content = ingest_concat(candidates)
    project_title = "INPUT Corpus"
    print(f"Project title: {project_title}")
    
    if not combined_content or not combined_content.strip():
        print("Error: Combined content from INPUT is empty.")
        return
    
    # 5. Extract key concepts
    print("Extracting key concepts from project content...")
    key_concepts = extract_key_concepts(combined_content)
    print(f"Extracted {len(key_concepts)} key concepts:")
    for i, concept in enumerate(key_concepts, 1):
        print(f"  {i}. {concept}")
    
    # Save key concepts
    concepts_file = output_folder / "key_concepts.json"
    save_output(json.dumps(key_concepts, indent=2), concepts_file)
    
    # 6. Find relevant papers
    print("\nSearching for relevant papers on ArXiv...")
    relevant_papers = find_relevant_papers(reference_service, combined_content, key_concepts)
    print(f"Found {len(relevant_papers)} relevant papers")
    
    # Save papers to file
    papers_file = output_folder / "relevant_papers.json"
    save_output(json.dumps(relevant_papers, indent=2), papers_file)
    
    # Create readable paper list
    paper_list = []
    for i, paper in enumerate(relevant_papers, 1):
        title = paper.get('title', 'Unknown Title')
        authors = paper.get('authors', [])
        if authors and isinstance(authors[0], dict):
            author_names = [a.get('name', '') for a in authors if a.get('name')]
        else:
            author_names = authors if isinstance(authors, list) else []
        author_text = ', '.join(author_names) if author_names else 'Unknown Authors'
        published = paper.get('published', '').split('T')[0] if paper.get('published') else 'n.d.'
        arxiv_id = paper.get('id', '').split('v')[0] if paper.get('id') else 'unknown'
        
        entry = f"{i}. **{title}**\n   Authors: {author_text}\n   Published: {published}\n   ArXiv ID: {arxiv_id}"
        if paper.get('summary'):
            entry += f"\n   Summary: {paper.get('summary')[:300]}..."
        paper_list.append(entry)
    
    papers_md = "# Relevant Research Papers\n\n" + "\n\n".join(paper_list)
    papers_md_file = output_folder / "relevant_papers.md"
    save_output(papers_md, papers_md_file)
    
    # 7. Analyze research gaps
    print("\nAnalyzing research gaps and novel contribution opportunities...")
    research_gaps = analyze_research_gaps(combined_content, relevant_papers, ai_client)
    
    # Save research gaps analysis
    gaps_file = output_folder / "research_gaps_analysis.md"
    save_output(research_gaps, gaps_file)
    print(f"Research gaps analysis saved to {gaps_file}")
    
    # 8. Enhance research proposal
    print("\nEnhancing research proposal with literature and insights...")
    enhanced_proposal = enhance_research_proposal(
        combined_content, 
        relevant_papers, 
        research_gaps,
        ai_client
    )
    
    # Save enhanced proposal
    proposal_file = output_folder / "enhanced_research_proposal.md"
    save_output(enhanced_proposal, proposal_file)
    print(f"Enhanced research proposal saved to {proposal_file}")
    
    print("\nResearch enhancement complete!")
    print("\nOutputs generated:")
    print(f"1. Key Concepts: {concepts_file}")
    print(f"2. Relevant Papers (JSON): {papers_file}")
    print(f"3. Relevant Papers (Markdown): {papers_md_file}")
    print(f"4. Research Gaps Analysis: {gaps_file}")
    print(f"5. Enhanced Research Proposal: {proposal_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enhance research with vector search and AI analysis")
    parser.add_argument('--model', choices=['claude', 'deepseek'], default='claude', 
                        help='AI model to use (claude or deepseek)')
    parser.add_argument('--force-fallback', action='store_true', 
                        help='Force use of fallback vector store implementation')
    args = parser.parse_args()
    
    enhance_research(args.model, args.force_fallback)
>>>>>>> 7f5694d (Add comprehensive test scripts for LaTeX configuration, content extraction, and vector store functionality)
