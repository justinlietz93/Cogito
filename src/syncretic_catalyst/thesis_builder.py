#!/usr/bin/env python3
"""
Syncretic Catalyst Thesis Builder

This module implements a comprehensive multi-agent research pipeline that:
1. Takes a concept, theory, or hypothesis from the user
2. Employs specialized research agents to comprehensively explore and develop it
3. Scours research papers (including overlooked historical and cutting-edge modern research)
4. Performs validations, mathematical analysis, and logical reasoning
5. Finds supporting evidence and relevant references
6. Produces a final thesis or academic proposal

Similar to the critique system but constructive rather than critical.
"""

import os
import sys
import json
import logging
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import re
import time
from datetime import datetime
from collections import defaultdict
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add project root to path to ensure imports work properly
# The project is now an installable package, so this is no longer needed.
# sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

# Import vector search functionality
from src.arxiv.arxiv_vector_reference_service import ArxivVectorReferenceService

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("syncretic_catalyst")

# Research Agent definitions
RESEARCH_AGENTS = {
    "FoundationalLiteratureExplorer": {
        "role": "Explores historical and foundational literature relevant to the concept",
        "system_prompt": """You are a Research Scholar specializing in exploring foundational and historical literature. 
Your goal is to find relevant historical papers, theories, and overlooked research that relates to the given concept.
Focus on understanding the historical context, evolution of ideas, and foundational principles.
Your analysis should be thorough, well-structured, and focused on identifying key historical insights that could inform the new research.
For each relevant historical work, provide:
1. A clear explanation of its core ideas
2. Its relevance to the current concept
3. How it might provide overlooked insights or foundations
4. Any mathematical models or frameworks it established that could be built upon"""
    },
    "ModernResearchSynthesizer": {
        "role": "Analyzes current research landscape and identifies cutting-edge developments",
        "system_prompt": """You are a Modern Research Synthesizer specializing in current academic trends and cutting-edge developments.
Your goal is to analyze the current research landscape related to the given concept.
Focus on:
1. Synthesizing the most recent and relevant developments in the field
2. Identifying current research gaps and opportunities
3. Analyzing competing theories or approaches
4. Highlighting methodologies and techniques that could be applied
5. Recognizing key researchers and institutions working in this area
Provide a comprehensive overview of the current state of knowledge, with specific attention to mathematical models, experimental results, and empirical evidence."""
    },
    "MethodologicalValidator": {
        "role": "Develops and validates methodological approaches for the concept",
        "system_prompt": """You are a Methodological Validator specializing in research design and validation.
Your goal is to develop and validate appropriate methodological approaches for investigating the given concept.
Focus on:
1. Designing rigorous research methodologies suitable for the concept
2. Identifying potential experimental or analytical approaches
3. Highlighting required data, tools, or resources
4. Evaluating methodological strengths and limitations
5. Proposing validation techniques and criteria
Be particularly detailed when describing mathematical frameworks, statistical approaches, or empirical validation techniques necessary to establish the concept's validity."""
    },
    "InterdisciplinaryConnector": {
        "role": "Explores connections across different disciplines and identifies novel applications",
        "system_prompt": """You are an Interdisciplinary Connector specializing in identifying connections across different fields.
Your goal is to explore how the given concept intersects with or could benefit from insights in other disciplines.
Focus on:
1. Identifying relevant theories, methods, or findings from other fields
2. Exploring how interdisciplinary connections might strengthen the concept
3. Suggesting novel applications or extensions based on interdisciplinary insights
4. Recognizing parallel developments in other domains
5. Proposing innovative combinations of approaches from different fields
Your analysis should be creative yet rigorous, with particular attention to mathematical or theoretical frameworks that could be transferred across disciplines."""
    },
    "MathematicalFormulator": {
        "role": "Develops mathematical frameworks and formal representations of the concept",
        "system_prompt": """You are a Mathematical Formulator specializing in developing formal mathematical representations.
Your goal is to create rigorous mathematical frameworks and formalizations for the given concept.
Focus on:
1. Developing appropriate mathematical representations (equations, models, algorithms)
2. Formalizing key relationships and processes
3. Analyzing properties, constraints, and boundary conditions
4. Deriving potential implications through mathematical reasoning
5. Proposing testable predictions based on the mathematical framework
Your work should be precise, rigorous, and include detailed mathematical notation, derivations, and proofs where appropriate.
If the concept doesn't immediately lend itself to mathematical treatment, explore creative ways to quantify or formalize aspects of it."""
    },
    "EvidenceAnalyst": {
        "role": "Gathers and analyzes empirical evidence related to the concept",
        "system_prompt": """You are an Evidence Analyst specializing in empirical data and research findings.
Your goal is to gather and analyze all available empirical evidence related to the given concept.
Focus on:
1. Collecting relevant empirical findings from published research
2. Evaluating the strength and quality of available evidence
3. Identifying patterns, consistencies, or contradictions in the evidence
4. Assessing methodological rigor of relevant studies
5. Highlighting gaps in empirical knowledge
Your analysis should be data-driven and objective, with careful attention to quantitative results, statistical significance, and empirical validity. 
Summarize key findings in a way that clearly indicates their relevance and strength of support for the concept."""
    },
    "ImplicationExplorer": {
        "role": "Explores broader implications, applications, and future directions",
        "system_prompt": """You are an Implication Explorer specializing in identifying broader impacts and applications.
Your goal is to thoroughly explore the potential implications, applications, and future directions of the given concept.
Focus on:
1. Theoretical implications for the field and related domains
2. Practical applications and potential implementations
3. Societal, ethical, or policy implications
4. Future research directions and open questions
5. Potential paradigm shifts or transformative impacts
Your analysis should be forward-thinking yet grounded, explicitly connecting implications to the concept's core principles and supporting evidence. 
Provide concrete examples of how the concept could be applied and what specific impacts it might have."""
    },
    "SynthesisArbitrator": {
        "role": "Synthesizes inputs from all agents and creates a coherent thesis",
        "system_prompt": """You are a Synthesis Arbitrator specializing in integrating diverse research perspectives.
Your goal is to synthesize inputs from multiple research agents into a coherent, comprehensive thesis.
Focus on:
1. Identifying key themes, insights, and connections across different analyses
2. Resolving any contradictions or tensions between different perspectives
3. Creating a unified theoretical framework that incorporates diverse elements
4. Prioritizing the most significant and well-supported aspects
5. Developing a coherent narrative that presents the concept with appropriate nuance and rigor

Your synthesis should be comprehensive yet focused, balancing detail with clarity. 
The final thesis should include:
- A clear articulation of the core concept and its significance
- A thorough literature review incorporating historical and modern research
- Well-defined methodology and mathematical frameworks
- Comprehensive evaluation of supporting evidence
- Exploration of interdisciplinary connections and applications
- Discussion of implications and future directions
- Complete references and citations

Throughout, maintain academic rigor while highlighting the concept's novelty and potential impact."""
    }
}

class ResearchAgent:
    """A specialized research agent focused on a particular aspect of research."""
    
    def __init__(self, name: str, role: str, system_prompt: str, ai_client):
        """
        Initialize a research agent.
        
        Args:
            name: Name of the agent
            role: Description of the agent's role
            system_prompt: System prompt for the agent
            ai_client: AI client to use for generating content
        """
        self.name = name
        self.role = role
        self.system_prompt = system_prompt
        self.ai_client = ai_client
        self.response = None
    
    def research(self, concept: str, papers: List[Dict[str, Any]], context: Optional[str] = None) -> str:
        """
        Perform research on the given concept.
        
        Args:
            concept: The concept to research
            papers: List of relevant papers to consider
            context: Additional context (e.g., responses from other agents)
            
        Returns:
            Research output
        """
        # Format paper information for the agent
        paper_information = self._format_papers(papers)
        
        # Create the full prompt
        prompt = self._create_prompt(concept, paper_information, context)
        
        # Log the operation
        logger.info(f"Agent '{self.name}' is researching concept: {concept[:50]}...")
        
        # Generate response
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt}
        ]
        
        try:
            self.response = self.ai_client.run(messages, max_tokens=4000)
            return self.response
        except Exception as e:
            logger.error(f"Error in agent '{self.name}': {e}")
            return f"Error in research: {e}"
    
    def _format_papers(self, papers: List[Dict[str, Any]]) -> str:
        """Format paper information for the agent."""
        formatted_papers = []
        
        for i, paper in enumerate(papers, 1):
            title = paper.get('title', 'Unknown Title')
            
            # Handle different author formats
            authors = paper.get('authors', [])
            author_names = []
            if authors:
                if isinstance(authors[0], dict):
                    author_names = [a.get('name', '') for a in authors if a.get('name')]
                else:
                    author_names = authors if isinstance(authors, list) else []
            
            author_text = ', '.join(author_names) if author_names else 'Unknown Authors'
            published = paper.get('published', '').split('T')[0] if paper.get('published') else 'n.d.'
            arxiv_id = paper.get('id', '').split('v')[0] if paper.get('id') else 'unknown'
            summary = paper.get('summary', 'No summary available')
            
            paper_entry = f"Paper {i}:\nTitle: {title}\nAuthors: {author_text}\nPublished: {published}\nArXiv ID: {arxiv_id}\nSummary: {summary}\n"
            formatted_papers.append(paper_entry)
        
        return "\n".join(formatted_papers)
    
    def _create_prompt(self, concept: str, paper_information: str, context: Optional[str] = None) -> str:
        """Create the full prompt for the agent."""
        # Base prompt with concept and research task
        prompt = f"""
Research Task: Please thoroughly research the following concept according to your specific role as a {self.name}.

CONCEPT:
{concept}

RELEVANT RESEARCH PAPERS:
{paper_information}
"""
        
        # Add context from other agents if provided
        if context:
            prompt += f"""
ADDITIONAL CONTEXT FROM OTHER RESEARCH:
{context}
"""
        
        # Add specific instructions for the agent type
        prompt += f"""
RESEARCH OUTPUT REQUESTED:
Based on your role as a {self.name} ({self.role}), please provide a comprehensive research analysis 
of the given concept. Your analysis should focus on your specific area of expertise while incorporating 
the provided research papers and any additional context.

Organize your response clearly with appropriate sections and subsections. Include specific references 
to the provided papers where relevant. If mathematical formulations are appropriate, include them 
with clear explanations.

Your research should be rigorous, well-reasoned, and academically sound, written at the level of a 
peer-reviewed academic publication.
"""
        
        return prompt


class ThesisBuilder:
    """
    Thesis Builder that coordinates multiple research agents to comprehensively
    research a concept and produce a final thesis.
    """
    
    def __init__(self, 
                output_dir: str = "syncretic_output",
                force_fallback: bool = False,
                ai_client = None):
        """
        Initialize the Thesis Builder.
        
        Args:
            output_dir: Directory for output files
            force_fallback: Whether to force the fallback vector store implementation
            ai_client: AI client to use for agent research
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup vector reference service
        config = {
            'arxiv': {
                'cache_dir': 'storage/arxiv_cache_new',
                'vector_cache_dir': 'storage/arxiv_vector_cache',
                'cache_ttl_days': 30,
                'force_vector_fallback': force_fallback
            }
        }
        self.reference_service = ArxivVectorReferenceService(config=config)
        
        # Save AI client
        self.ai_client = ai_client
        
        # Initialize agents
        self.agents = {}
        if ai_client:
            for name, info in RESEARCH_AGENTS.items():
                self.agents[name] = ResearchAgent(
                    name=name,
                    role=info["role"],
                    system_prompt=info["system_prompt"],
                    ai_client=ai_client
                )
    
    def research_concept(self, concept: str, max_papers: int = 50) -> Dict[str, Any]:
        """
        Research a concept using the multi-agent approach.
        
        Args:
            concept: The concept to research
            max_papers: Maximum number of papers to retrieve
            
        Returns:
            Dictionary with research results
        """
        logger.info(f"Starting comprehensive research on concept: {concept[:50]}...")
        research_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        results = {
            "concept": concept,
            "research_id": research_id,
            "timestamp": datetime.now().isoformat(),
            "papers": [],
            "agent_research": {},
            "thesis": None
        }
        
        # Step 1: Find relevant papers
        logger.info("Finding relevant research papers...")
        papers = self._find_relevant_papers(concept, max_papers)
        results["papers"] = papers
        
        # Save papers
        papers_file = self.output_dir / f"papers_{research_id}.json"
        with open(papers_file, 'w', encoding='utf-8') as f:
            json.dump(papers, f, indent=2)
        logger.info(f"Saved {len(papers)} papers to {papers_file}")
        
        # Create readable paper list
        paper_list = []
        for i, paper in enumerate(papers, 1):
            title = paper.get('title', 'Unknown Title')
            # Handle different author formats
            authors = paper.get('authors', [])
            author_names = []
            if authors:
                if isinstance(authors[0], dict):
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
        papers_md_file = self.output_dir / f"papers_{research_id}.md"
        with open(papers_md_file, 'w', encoding='utf-8') as f:
            f.write(papers_md)
        
        # Step 2: Run initial research agents (all except SynthesisArbitrator)
        logger.info("Running specialized research agents...")
        
        for name, agent in self.agents.items():
            # Skip the synthesis agent for now
            if name == "SynthesisArbitrator":
                continue
            
            logger.info(f"Running agent: {name}")
            agent_response = agent.research(concept, papers)
            results["agent_research"][name] = agent_response
            
            # Save individual agent response
            agent_file = self.output_dir / f"agent_{name}_{research_id}.md"
            with open(agent_file, 'w', encoding='utf-8') as f:
                f.write(f"# {name}: {agent.role}\n\n{agent_response}")
            logger.info(f"Saved {name} research to {agent_file}")
        
        # Step 3: Run the synthesis agent
        logger.info("Running synthesis to create final thesis...")
        
        # Prepare context for synthesis (combine all other agent responses)
        synthesis_context = ""
        for name, response in results["agent_research"].items():
            synthesis_context += f"=== {name}: {self.agents[name].role} ===\n\n{response}\n\n"
        
        # Run synthesis agent
        if "SynthesisArbitrator" in self.agents:
            synthesis_agent = self.agents["SynthesisArbitrator"]
            thesis = synthesis_agent.research(concept, papers, synthesis_context)
            results["thesis"] = thesis
            
            # Save thesis
            thesis_file = self.output_dir / f"thesis_{research_id}.md"
            with open(thesis_file, 'w', encoding='utf-8') as f:
                f.write(f"# Research Thesis: {concept}\n\n{thesis}")
            logger.info(f"Saved final thesis to {thesis_file}")
        
        # Step 4: Create final research report
        self._create_final_report(results, research_id)
        
        return results
    
    def _find_relevant_papers(self, concept: str, max_papers: int) -> List[Dict[str, Any]]:
        """Find papers relevant to the concept."""
        # Extract key terms for more targeted search
        key_terms = self._extract_key_terms(concept)
        
        # First, search with the full concept
        concept_papers = self.reference_service.get_references_for_content(
            concept,
            max_results=max_papers // 2
        )
        
        # Then search for specific key terms
        term_papers = []
        papers_per_term = max(1, (max_papers - len(concept_papers)) // len(key_terms))
        
        for term in key_terms:
            term_results = self.reference_service.get_references_for_content(
                term,
                max_results=papers_per_term
            )
            term_papers.extend(term_results)
        
        # Combine results, removing duplicates
        all_papers = concept_papers.copy()
        seen_ids = {paper.get('id') for paper in all_papers if paper.get('id')}
        
        for paper in term_papers:
            paper_id = paper.get('id')
            if paper_id and paper_id not in seen_ids:
                all_papers.append(paper)
                seen_ids.add(paper_id)
                
                if len(all_papers) >= max_papers:
                    break
        
        return all_papers[:max_papers]
    
    def _extract_key_terms(self, concept: str, max_terms: int = 5) -> List[str]:
        """Extract key terms from the concept for targeted search."""
        # Split the concept into words and phrases
        words = re.findall(r'\b\w+\b', concept.lower())
        phrases = re.findall(r'\b\w+(?:\s+\w+){1,3}\b', concept)
        
        # Filter common stopwords
        stopwords = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'with', 'by', 'about', 'as'}
        filtered_words = [w for w in words if w not in stopwords and len(w) > 3]
        
        # Select most significant terms
        # Priority: longer phrases, then capitalized terms, then longer words
        capitalized_phrases = [p for p in phrases if any(w[0].isupper() for w in p.split())]
        other_phrases = [p for p in phrases if p not in capitalized_phrases]
        
        # Combine and select most relevant terms
        candidates = (
            sorted(capitalized_phrases, key=len, reverse=True) +
            sorted(other_phrases, key=len, reverse=True) +
            sorted(filtered_words, key=len, reverse=True)
        )
        
        # Remove duplicates while preserving order
        seen = set()
        unique_terms = []
        for term in candidates:
            if term.lower() not in seen:
                seen.add(term.lower())
                unique_terms.append(term)
        
        return unique_terms[:max_terms]
    
    def _create_final_report(self, results: Dict[str, Any], research_id: str) -> None:
        """Create a final comprehensive research report."""
        report = f"""# Comprehensive Research Report

## Concept
{results['concept']}

## Research Overview
This report presents a comprehensive analysis of the concept using a multi-agent research approach.
The research was conducted on {results['timestamp']} with ID: {research_id}.

## Research Methodology
The research employed a syncretic catalyst approach with specialized research agents:

"""
        
        # Add agent descriptions
        for name, agent in self.agents.items():
            report += f"- **{name}**: {agent.role}\n"
        
        report += f"""
## Research Papers
This analysis drew from {len(results['papers'])} relevant academic papers retrieved through semantic vector search.
The complete list of papers can be found in `papers_{research_id}.md`.

## Research Findings
"""
        
        # Add summaries of each agent's findings
        for name, response in results["agent_research"].items():
            # Extract a summary (first paragraph or 300 chars)
            summary = response.split('\n\n')[0] if '\n\n' in response else response[:300] + "..."
            report += f"### {name}\n{summary}\n\n"
        
        report += f"""
## Thesis
The complete synthesized thesis can be found in `thesis_{research_id}.md`.

### Thesis Summary
"""
        
        # Add thesis summary
        if results["thesis"]:
            summary = results["thesis"].split('\n\n')[0] if '\n\n' in results["thesis"] else results["thesis"][:500] + "..."
            report += summary
        
        # Save report
        report_file = self.output_dir / f"research_report_{research_id}.md"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        logger.info(f"Saved comprehensive research report to {report_file}")


def build_thesis(concept: str, 
                model: Optional[str] = None,
                force_fallback: bool = False,
                output_dir: str = "syncretic_output") -> None:
    """
    Build a comprehensive thesis from a concept using the multi-agent approach.
    
    Args:
        concept: The concept to research
        model: Optional AI model override (if None, uses configured primary_provider)
        force_fallback: Whether to force the fallback vector store implementation
        output_dir: Directory for output files
    """
    logger.info("Starting Syncretic Catalyst Thesis Builder")
    
    # Initialize AI client using the orchestrator
    try:
        from src.syncretic_catalyst.ai_clients import AIOrchestrator
                
        # Create the orchestrator with optional model override
        orchestrator = AIOrchestrator(model_name=model)
        
        # Create a simple adapter that mimics the interface expected by our agents
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
        
    except ImportError:
        logger.error("Error: AI client libraries not found. Please ensure ai_clients.py is available.")
        return
    except Exception as e:
        logger.error(f"Error initializing AI client: {e}")
        return
    
    # Initialize thesis builder
    thesis_builder = ThesisBuilder(
        output_dir=output_dir,
        force_fallback=force_fallback,
        ai_client=ai_client
    )
    
    # Start research
    start_time = time.time()
    results = thesis_builder.research_concept(concept)
    end_time = time.time()
    
    # Report completion
    duration = end_time - start_time
    logger.info(f"Research completed in {duration:.2f} seconds")
    logger.info(f"Output files saved to {output_dir}")
    
    # Print thesis summary
    if results.get("thesis"):
        logger.info("\nThesis Summary:")
        summary = results["thesis"].split('\n\n')[0] if '\n\n' in results["thesis"] else results["thesis"][:300]
        logger.info(summary)


def main():
    """Main function to run the thesis builder from the command line."""
    parser = argparse.ArgumentParser(
        description="Build a comprehensive thesis from a concept using multi-agent research"
    )
    # Allow either a single concept or a file containing multiple concepts
    parser.add_argument("input", help="The concept, theory, or hypothesis to research, or a file path containing one concept per line")
    parser.add_argument('--file', action='store_true', help='Treat the input as a file path')
    parser.add_argument('--model', choices=['claude', 'deepseek', 'xai', 'openrouter'], default='claude',
                        help='AI model to use (claude or deepseek)')
    parser.add_argument('--force-fallback', action='store_true',
                        help='Force use of fallback vector store implementation')
    parser.add_argument('--output-dir', default='syncretic_output',
                        help='Directory for output files')
    
    args = parser.parse_args()
    
    if args.file:
        try:
            if os.path.isdir(args.input):
                # Recursive directory ingestion (default behavior)
                allowed_exts = {'.txt', '.md', '.markdown'}
                collected: List[str] = []
                for root, _, files in os.walk(args.input):
                    for fname in files:
                        if os.path.splitext(fname)[1].lower() in allowed_exts:
                            collected.append(os.path.join(root, fname))
                collected.sort()
                
                if not collected:
                    logger.error(f"No input files found in directory {args.input} for batch processing.")
                    return
                
                logger.info(f"Found {len(collected)} files in {args.input} (recursive). Starting batch processing.")
                for i, path in enumerate(collected, 1):
                    try:
                        with open(path, 'r', encoding='utf-8') as f:
                            concept = f.read().strip()
                    except Exception as fe:
                        logger.error(f"Failed to read {path}: {fe}")
                        continue
                    
                    logger.info(f"--- Processing file {i}/{len(collected)}: {path} ---")
                    build_thesis(
                        concept=concept,
                        model=args.model,
                        force_fallback=args.force_fallback,
                        output_dir=args.output_dir
                    )
                    logger.info(f"--- Completed file {i}/{len(collected)}: {path} ---")
            else:
                # Single file with '---' delimiters (existing behavior)
                with open(args.input, 'r', encoding='utf-8') as f:
                    content = f.read()
                concepts = [concept.strip() for concept in content.split('---') if concept.strip()]
                
                logger.info(f"Found {len(concepts)} concepts in {args.input}. Starting batch processing.")
                for i, concept in enumerate(concepts, 1):
                    logger.info(f"--- Processing concept {i}/{len(concepts)} ---")
                    build_thesis(
                        concept=concept,
                        model=args.model,
                        force_fallback=args.force_fallback,
                        output_dir=args.output_dir
                    )
                    logger.info(f"--- Completed concept {i}/{len(concepts)} ---")
            
        except FileNotFoundError:
            logger.error(f"Error: Input file not found at {args.input}")
        except Exception as e:
            logger.error(f"An error occurred during batch processing: {e}")
            
    else:
        # Process a single concept from the command line
        build_thesis(
            concept=args.input,
            model=args.model,
            force_fallback=args.force_fallback,
            output_dir=args.output_dir
        )

if __name__ == "__main__":
    main()
