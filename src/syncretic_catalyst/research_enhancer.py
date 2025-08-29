#!/usr/bin/env python3
"""
AI Research Enhancer with ArXiv Vector Search

This module extends the research_generator.py functionality by:
1. Using vector search to find relevant ArXiv papers for a research topic
2. Analyzing research gaps between proposed ideas and existing literature
3. Identifying potential novel connections and insights
4. Enhancing research proposals with relevant citations and context
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import argparse
import json
import re

# Add project root to path to ensure imports work properly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

# Import the vector search functionality
from src.arxiv.arxiv_vector_reference_service import ArxivVectorReferenceService
from src.arxiv.smart_vector_store import ArxivSmartStore

# Import the AI clients and research generator
try:
    # Import AI clients from current directory (relative import)
    from .ai_clients import Claude37SonnetClient, DeepseekR1Client
    from .research_generator import read_file_content, get_project_title, FILE_ORDER
except ImportError:
    print("Warning: Unable to import from this directory. Trying absolute imports...")
    try:
        # Try absolute imports
        from src.syncretic_catalyst.ai_clients import Claude37SonnetClient, DeepseekR1Client
        from src.syncretic_catalyst.research_generator import read_file_content, get_project_title, FILE_ORDER
    except ImportError:
        print("Warning: Unable to import from src.syncretic_catalyst. Falling back to direct import.")
        try:
            # Direct import (assuming running from same directory)
            from ai_clients import Claude37SonnetClient, DeepseekR1Client
            from research_generator import read_file_content, get_project_title, FILE_ORDER
        except ImportError:
            print("Warning: Unable to import from research_generator.py. Make sure it's in the same directory.")
    # Define minimal versions of needed functions
    def read_file_content(file_path: Path) -> str:
        """Read and return the content of a file."""
        try:
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
        return "Unknown Project"
        
    FILE_ORDER = [
        "CONTEXT_CONSTRAINTS.md",
        "DIVERGENT_SOLUTIONS.md", 
        "DEEP_DIVE_MECHANISMS.md",
        "SELF_CRITIQUE_SYNERGY.md", 
        "BREAKTHROUGH_BLUEPRINT.md",
        "IMPLEMENTATION_PATH.md",
        "NOVELTY_CHECK.md",
        "ELABORATIONS.md"
    ]

def extract_key_concepts(content: str, max_concepts: int = 10) -> List[str]:
    """
    Extract key concepts from the project content.
    
    Args:
        content: Combined content from project documents
        max_concepts: Maximum number of concepts to extract
        
    Returns:
        List of key concepts
    """
    # Split into sentences and paragraphs
    paragraphs = re.split(r'\n\n+', content)
    
    # Look for explicitly mentioned concepts in headings or bullet points
    concepts = []
    
    # Extract from headings
    heading_matches = re.findall(r'#+ ([^\n]+)', content)
    for match in heading_matches:
        if 3 < len(match) < 80 and match not in concepts:
            concepts.append(match.strip())
    
    # Extract from bullet points
    bullet_matches = re.findall(r'[-*] ([^\n]+)', content)
    for match in bullet_matches:
        if 3 < len(match) < 80 and match not in concepts:
            concepts.append(match.strip())
    
    # Extract bold/emphasized text
    emphasis_matches = re.findall(r'\*\*([^*]+)\*\*|\*([^*]+)\*|__([^_]+)__|_([^_]+)_', content)
    for match_tuple in emphasis_matches:
        for match in match_tuple:
            if match and 3 < len(match) < 80 and match not in concepts:
                concepts.append(match.strip())
    
    # If we don't have enough concepts yet, extract noun phrases from paragraphs
    if len(concepts) < max_concepts:
        # Simple heuristic: find capitalized phrases
        for paragraph in paragraphs:
            cap_matches = re.findall(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)', paragraph)
            for match in cap_matches:
                if 3 < len(match) < 80 and match not in concepts:
                    concepts.append(match.strip())
                    if len(concepts) >= max_concepts:
                        break
            if len(concepts) >= max_concepts:
                break
    
    return concepts[:max_concepts]

def find_relevant_papers(reference_service: ArxivVectorReferenceService, 
                         project_content: str, 
                         key_concepts: List[str],
                         max_papers: int = 20) -> List[Dict[str, Any]]:
    """
    Find papers relevant to the project using vector search.
    
    Args:
        reference_service: ArxivVectorReferenceService instance
        project_content: Combined content from project documents
        key_concepts: Key concepts extracted from the project
        max_papers: Maximum number of papers to find
        
    Returns:
        List of paper metadata dictionaries
    """
    # First try searching with the full content (but truncated to avoid overwhelming)
    truncated_content = project_content[:10000]  # First 10K chars only
    content_papers = reference_service.get_references_for_content(
        truncated_content,
        max_results=max_papers // 2
    )
    
    # Then search for each key concept to get more targeted results
    concept_papers = []
    papers_per_concept = max(1, (max_papers - len(content_papers)) // len(key_concepts))
    
    for concept in key_concepts:
        papers = reference_service.get_references_for_content(
            concept,
            max_results=papers_per_concept
        )
        concept_papers.extend(papers)
    
    # Combine results, removing duplicates
    all_papers = content_papers.copy()
    seen_ids = {paper.get('id') for paper in all_papers if paper.get('id')}
    
    for paper in concept_papers:
        paper_id = paper.get('id')
        if paper_id and paper_id not in seen_ids:
            all_papers.append(paper)
            seen_ids.add(paper_id)
            
            if len(all_papers) >= max_papers:
                break
    
    return all_papers[:max_papers]

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
    
    # 1. Set up paths (workspace under module tree, results in universal output directory)
    WORKSPACE_DIR = Path("src/syncretic_catalyst/workspaces/some_project")
    doc_folder = WORKSPACE_DIR / "doc"
    output_folder = Path("output_results") / "syncretic_catalyst" / "some_project"
    
    # Create output folder if not exists
    output_folder.mkdir(parents=True, exist_ok=True)
    
    # Check if the folder exists
    if not doc_folder.exists():
        print("Error: 'src/syncretic_catalyst/workspaces/some_project/doc' folder does not exist.")
        doc_folder.mkdir(parents=True, exist_ok=True)
        print("Created empty 'src/syncretic_catalyst/workspaces/some_project/doc' folder. Please add your research documents.")
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
    
    # 4. Get project title and content
    project_title = get_project_title(doc_folder)
    print(f"Project title: {project_title}")
    
    combined_content = combine_project_content(doc_folder)
    if not combined_content:
        print("Error: No content found in project documents.")
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
