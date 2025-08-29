# Syncretic Catalyst

A set of tools to accelerate research processes by combining AI and vector search technologies.

## Overview

The Syncretic Catalyst toolkit leverages your existing research documents, combines them with AI analysis and ArXiv vector search to find research gaps, identify novel connections, and enhance your research proposals with relevant citations and academic context.

## Components

1. **Research Generator** (`research_generator.py`) - Creates academic research proposals from project documents
2. **Research Enhancer** (`research_enhancer.py`) - Enhances research with ArXiv vector search to identify gaps and novel connections

## Key Features

- **Vector-based Paper Discovery** - Uses semantic search to find relevant papers
- **Research Gap Analysis** - Identifies differences between your ideas and existing literature
- **Novel Connection Identification** - Discovers potential connections between your research and existing work
- **Enhanced Proposal Generation** - Creates formal academic proposals with proper citations
- **Automatic Citation Management** - Formats references from ArXiv papers

## Requirements

- Python 3.8 or higher
- ArXiv Vector Search capabilities (implemented in this project)
- AI client libraries (Claude or DeepSeek)

## Usage

### Basic Usage

1. Create your research documents in the `src/syncretic_catalyst/workspaces/some_project/doc` directory
2. Run the research enhancer script:

```bash
python src/syncretic_catalyst/research_enhancer.py
```

This will:
- Extract key concepts from your documents
- Find relevant papers on ArXiv using vector search
- Analyze research gaps
- Generate an enhanced research proposal

### Use with Fallback Mode

If you don't have the necessary API keys for Agno or OpenAI embeddings:

```bash
python src/syncretic_catalyst/research_enhancer.py --force-fallback
```

This will use the pure Python vector search implementation that doesn't require external API keys.

### Choose AI Model

You can select the AI model to use for analysis:

```bash
python src/syncretic_catalyst/research_enhancer.py --model claude
# or
python src/syncretic_catalyst/research_enhancer.py --model deepseek
```

## Output Files

The script produces several output files in the `output_results/syncretic_catalyst/some_project` directory:

1. `key_concepts.json` - Key concepts extracted from your research
2. `relevant_papers.json` - Detailed metadata of relevant ArXiv papers (JSON format)
3. `relevant_papers.md` - Human-readable list of relevant papers (Markdown)
4. `research_gaps_analysis.md` - Analysis of research gaps and novel contribution opportunities
5. `enhanced_research_proposal.md` - Complete research proposal with citations

## How It Works

1. **Concept Extraction** - Extracts key concepts using regex patterns (headings, bullet points, emphasized text)
2. **Vector Search** - Uses ArXivVectorReferenceService to find semantically related papers
3. **Gap Analysis** - AI analyzes differences between your ideas and existing literature
4. **Proposal Enhancement** - AI integrates citations and strengthens novelty claims
5. **Output Generation** - Creates multiple useful output files for further refinement

## Example Workflow

1. Create your research documents with preliminary ideas
2. Run the enhancer to find related papers and gaps
3. Review the gap analysis to identify the most promising novel contributions
4. Use the enhanced proposal as a starting point for your formal academic paper
5. Iteratively refine your research by repeating this process

## Integration with Vector Search

This toolkit uses the integrated ArXiv vector search capabilities to find papers based on semantic similarity rather than just keyword matching. The `ArxivVectorReferenceService` provides context-aware search for research papers that would be difficult to find using traditional search methods.
