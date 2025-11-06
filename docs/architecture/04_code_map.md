# Cogito Code Map

**System:** Cogito AI Research Platform  
**Commit:** 0f51527  
**Last Updated:** 2025-11-06

This document provides a comprehensive mapping of key modules, classes, and their responsibilities within the Cogito codebase.

---

## Table of Contents

1. [Entry Points](#entry-points)
2. [Core Orchestration](#core-orchestration)
3. [Domain Layer](#domain-layer)
4. [Application Layer](#application-layer)
5. [Infrastructure Layer](#infrastructure-layer)
6. [Provider Abstraction](#provider-abstraction)
7. [Research Integration](#research-integration)
8. [Output Processing](#output-processing)
9. [Module Statistics](#module-statistics)

---

## Entry Points

### CLI Applications

| File | Module | Responsibility | LOC |
|------|--------|---------------|-----|
| `run_critique.py` | Root | Main entry point for critique workflow | ~50 |
| `run_research.py` | Root | Main entry point for research workflow | ~50 |
| `src/main.py` | `main` | Core critique function (`critique_goal_document`) | 155 |
| `src/presentation/cli/app.py` | `presentation.cli.app` | CLI application orchestration | 485 |
| `src/presentation/cli/preflight.py` | `presentation.cli.preflight` | Preflight CLI commands | 596 |
| `src/presentation/cli/research_cli.py` | `presentation.cli.research_cli` | Research-specific CLI | 391 |
| `src/presentation/cli/interactive.py` | `presentation.cli.interactive` | Interactive mode | 342 |

### Responsibilities
- Command-line argument parsing
- Input validation and routing
- Pipeline selection and invocation
- Result presentation and formatting

---

## Core Orchestration

### Council Orchestration

| File | Module | Responsibility | LOC | Metrics |
|------|--------|---------------|-----|---------|
| `src/council_orchestrator.py` | `council_orchestrator` | Multi-agent critique orchestration | 327 | Fan-in: 1, Fan-out: 1 |
| `src/reasoning_tree.py` | `reasoning_tree` | Hierarchical reasoning execution | 386 | Stable (0.0) |
| `src/reasoning_agent.py` | `reasoning_agent` | Individual critique agent | 376 | Stable (0.0) |
| `src/reasoning_agent_self_critique.py` | `reasoning_agent_self_critique` | Self-critique mechanisms | 204 | Stable (0.0) |

**Key Functions:**
- `run_critique_council(content: str) -> dict`: Orchestrates full critique workflow
- `execute_reasoning_tree()`: Executes hierarchical reasoning with Phase → Task → Step structure
- `ReasoningAgent.generate_critique()`: Generates individual agent critique
- `self_critique_loop()`: Iterative self-improvement

### Syncretic Catalyst Orchestration

| File | Module | Responsibility | LOC |
|------|--------|---------------|-----|
| `src/syncretic_catalyst/thesis_builder.py` | `syncretic_catalyst.thesis_builder` | Main thesis generation orchestrator | 92 |
| `src/syncretic_catalyst/research_enhancer.py` | `syncretic_catalyst.research_enhancer` | Research enhancement workflow | 104 |
| `src/syncretic_catalyst/orchestrator.py` | `syncretic_catalyst.orchestrator` | General orchestration utilities | 4 |
| `src/syncretic_catalyst/application/workflow.py` | `syncretic_catalyst.application.workflow` | End-to-end workflow coordination | ~200 |

**Key Functions:**
- `build_thesis(concept: str)`: Generates comprehensive thesis from concept
- `enhance_research(project_path: str)`: Enhances existing research with literature
- `coordinate_research_agents()`: Parallel agent execution

---

## Domain Layer

### Domain Models

| File | Module | Responsibility | LOC |
|------|--------|---------------|-----|
| `src/pipeline_input.py` | `pipeline_input` | Core input data structure | 341 |
| `src/domain/preflight/` | `domain.preflight` | Preflight domain models | ~100 |
| `src/domain/user_settings/` | `domain.user_settings` | User preferences models | ~50 |
| `src/syncretic_catalyst/domain/thesis_agents.py` | `syncretic_catalyst.domain.thesis_agents` | Research agent definitions | ~150 |
| `src/syncretic_catalyst/domain/thesis_types.py` | `syncretic_catalyst.domain.thesis_types` | Thesis domain entities | ~100 |

**Key Classes:**
- `PipelineInput`: Main input container (fan-in: 13)
- `ExtractedPoint`: Preflight extraction result
- `QueryPlan`: Research query structure
- `ThesisAgent`: Research agent persona definition
- `ThesisSection`: Thesis structural unit

### Business Logic

| File | Module | Responsibility | LOC |
|------|--------|---------------|-----|
| `src/content_assessor.py` | `content_assessor` | Content quality evaluation | 372 |
| `src/council/synthesis.py` | `council.synthesis` | Multi-agent result aggregation | 147 |
| `src/council/adjustments.py` | `council.adjustments` | Confidence weighting & Arbiter logic | 89 |
| `src/syncretic_catalyst/research_generator.py` | `syncretic_catalyst.research_generator` | Research content generation | 76 |
| `src/syncretic_catalyst/assemble_research.py` | `syncretic_catalyst.assemble_research` | Multi-source aggregation | 72 |

**Key Functions:**
- `assess_content_quality(content: str) -> float`: Evaluates input quality
- `synthesize_council_results(critiques: List) -> dict`: Aggregates agent outputs
- `apply_arbiter_weighting(results: dict) -> dict`: Applies Judge/Arbiter logic
- `generate_research_section(agent: ThesisAgent, context: str) -> str`: Generates research content

---

## Application Layer

### Preflight Services

| File | Module | Responsibility | LOC | Status |
|------|--------|---------------|-----|--------|
| `src/application/preflight/orchestrator.py` | `application.preflight.orchestrator` | Multi-stage coordination | ~250 | Production |
| `src/application/preflight/services.py` | `application.preflight.services` | Extraction & query services | ~300 | Production |
| `src/application/preflight/extraction_parser.py` | `application.preflight.extraction_parser` | Response parsing | 362 | Production |
| `src/application/preflight/query_parser.py` | `application.preflight.query_parser` | Query plan parsing | 357 | Production |
| `src/application/preflight/prompts.py` | `application.preflight.prompts` | Prompt management | 329 | Production |

**Key Services:**
- `ExtractionService.run()`: Extracts key points from content
- `QueryPlanningService.run()`: Generates research queries
- `PreflightOrchestrator.run_full_preflight()`: Coordinates extraction + planning

### Critique Services

| File | Module | Responsibility | LOC |
|------|--------|---------------|-----|
| `src/application/critique/services.py` | `application.critique.services` | Critique use cases | ~200 |
| `src/application/critique/configuration.py` | `application.critique.configuration` | Pipeline configuration | ~150 |
| `src/application/critique/ports.py` | `application.critique.ports` | Repository interfaces | ~50 |

### Research Services

| File | Module | Responsibility | LOC |
|------|--------|---------------|-----|
| `src/application/research_execution/services.py` | `application.research_execution.services` | Query execution | ~200 |

### Syncretic Catalyst Application Services

| File | Module | Responsibility | LOC |
|------|--------|---------------|-----|
| `src/syncretic_catalyst/application/thesis/services.py` | `application.thesis.services` | Thesis generation orchestration | ~250 |
| `src/syncretic_catalyst/application/research_generation/services.py` | `application.research_generation.services` | Research content generation | ~200 |
| `src/syncretic_catalyst/application/research_enhancement/services.py` | `application.research_enhancement.services` | Enhancement orchestration | ~200 |
| `src/syncretic_catalyst/application/framework.py` | `application.framework` | Shared application logic | ~150 |

---

## Infrastructure Layer

### LLM Gateways

| File | Module | Responsibility | LOC | Issues |
|------|--------|---------------|-----|--------|
| `src/infrastructure/preflight/openai_gateway.py` | `infrastructure.preflight.openai_gateway` | OpenAI API for preflight | 1235 | **⚠️ Exceeds 500 LOC** |

**Hotspot:** This file requires refactoring into smaller, focused modules.

### I/O Repositories

| File | Module | Responsibility | LOC |
|------|--------|---------------|-----|
| `src/infrastructure/io/directory_repository.py` | `infrastructure.io.directory_repository` | Multi-file input aggregation | 456 |
| `src/infrastructure/critique/` | `infrastructure.critique` | Critique persistence | ~100 |
| `src/syncretic_catalyst/infrastructure/project_file_repository.py` | `infrastructure.project_file_repository` | File management | ~150 |

### Research Infrastructure

| File | Module | Responsibility | LOC |
|------|--------|---------------|-----|
| `src/syncretic_catalyst/infrastructure/thesis/ai_client.py` | `infrastructure.thesis.ai_client` | LLM provider adapter | ~200 |
| `src/syncretic_catalyst/infrastructure/thesis/reference_service.py` | `infrastructure.thesis.reference_service` | Citation management | ~150 |
| `src/syncretic_catalyst/infrastructure/thesis/output_repository.py` | `infrastructure.thesis.output_repository` | Result persistence | ~150 |

---

## Provider Abstraction

### Multi-Provider Clients

| File | Module | Responsibility | LOC | Issues |
|------|--------|---------------|-----|--------|
| `src/providers/openai_client.py` | `providers.openai_client` | OpenAI API wrapper | 484 | None |
| `src/providers/gemini_client.py` | `providers.gemini_client` | Google Gemini wrapper | 319 | None |
| `src/providers/anthropic_client.py` | `providers.anthropic_client` | Anthropic Claude wrapper | ~250 | None |
| `src/providers/deepseek_client.py` | `providers.deepseek_client` | DeepSeek wrapper | ~200 | None |
| `src/providers/model_config.py` | `providers.model_config` | Configuration management | ~100 | High instability |

**Key Capabilities:**
- Unified interface across providers
- Streaming support
- Token counting and cost tracking
- Retry logic with exponential backoff
- Fallback mechanisms

---

## Research Integration

### ArXiv Integration

| File | Module | Responsibility | LOC |
|------|--------|---------------|-----|
| `src/arxiv/arxiv_reference_service.py` | `arxiv.arxiv_reference_service` | Paper retrieval & caching | 403 |
| `src/arxiv/vector_store.py` | `arxiv.vector_store` | Vector embeddings & search | 434 |
| `src/arxiv/vector_db.py` | `arxiv.vector_db` | Vector database operations | 411 |
| `src/arxiv/db_cache_manager.py` | `arxiv.db_cache_manager` | Cache management | 361 |
| `src/arxiv/arxiv_vector_reference_service.py` | `arxiv.arxiv_vector_reference_service` | Combined vector + reference service | 354 |

**Key Functions:**
- `search_arxiv(query: str, max_results: int)`: Searches ArXiv database
- `embed_and_store(papers: List)`: Creates vector embeddings
- `semantic_search(query_embedding: np.array)`: Finds similar papers
- `cache_paper(paper_id: str, metadata: dict)`: Caches paper data

### Multi-Source Research APIs

| File | Module | Responsibility | LOC |
|------|--------|---------------|-----|
| `src/research_apis/orchestrator.py` | `research_apis.orchestrator` | Multi-source coordination | 358 |
| `src/research_apis/pubmed.py` | `research_apis.pubmed` | PubMed integration | 395 |
| `src/research_apis/semantic_scholar.py` | `research_apis.semantic_scholar` | Semantic Scholar API | 204 |
| `src/research_apis/crossref.py` | `research_apis.crossref` | CrossRef metadata | 199 |
| `src/research_apis/web_search.py` | `research_apis.web_search` | Web search integration | 336 |

**Key Functions:**
- `execute_research_query(query: QueryPlan)`: Executes across all sources
- `search_pubmed(query: str)`: Biomedical literature search
- `get_citation_metadata(doi: str)`: Retrieves citation info
- `semantic_scholar_search(query: str)`: Academic graph search

---

## Output Processing

### LaTeX Generation

| File | Module | Responsibility | LOC |
|------|--------|---------------|-----|
| `src/latex/formatter.py` | `latex.formatter` | Main LaTeX formatter | 452 |
| `src/latex/converters/markdown_to_latex.py` | `latex.converters.markdown_to_latex` | Markdown conversion | 580 |
| `src/latex/converters/direct_latex_generator.py` | `latex.converters.direct_latex_generator` | Direct LaTeX generation | 389 |
| `src/latex/utils/latex_compiler.py` | `latex.utils.latex_compiler` | PDF compilation | 425 |
| `src/latex/processors/citation_processor.py` | `latex.processors.citation_processor` | Citation handling | ~200 |
| `src/latex/processors/math_formatter.py` | `latex.processors.math_formatter` | Math expression formatting | ~150 |
| `src/latex/processors/jargon_processor.py` | `latex.processors.jargon_processor` | Terminology handling | ~150 |

**Key Capabilities:**
- Multiple LaTeX templates (ACM, Literature Review, Machine Learning)
- BibTeX citation management
- Math expression formatting
- PDF compilation with error handling

### Output Formatters

| File | Module | Responsibility | LOC |
|------|--------|---------------|-----|
| `src/output_formatter.py` | `output_formatter` | General result formatting | 157 |
| `src/scientific_review_formatter.py` | `scientific_review_formatter` | Peer review formatting | 209 |

---

## Module Statistics

### Top 20 Largest Files

| Rank | Module | LOC | Status |
|------|--------|-----|--------|
| 1 | `prompt_texts` | 1755 | **⚠️ Exceeds limit** |
| 2 | `infrastructure.preflight.openai_gateway` | 1235 | **⚠️ Exceeds limit** |
| 3 | `presentation.cli.preflight` | 596 | Within limit |
| 4 | `latex.converters.markdown_to_latex` | 580 | Within limit |
| 5 | `presentation.cli.app` | 485 | Within limit |
| 6 | `providers.openai_client` | 484 | Within limit |
| 7 | `infrastructure.io.directory_repository` | 456 | Within limit |
| 8 | `latex.formatter` | 452 | Within limit |
| 9 | `arxiv.vector_store` | 434 | Within limit |
| 10 | `latex.utils.latex_compiler` | 425 | Within limit |
| 11 | `arxiv.vector_db` | 411 | Within limit |
| 12 | `arxiv.arxiv_reference_service` | 403 | Within limit |
| 13 | `research_apis.pubmed` | 395 | Within limit |
| 14 | `presentation.cli.research_cli` | 391 | Within limit |
| 15 | `latex.converters.direct_latex_generator` | 389 | Within limit |
| 16 | `reasoning_tree` | 386 | Within limit |
| 17 | `reasoning_agent` | 376 | Within limit |
| 18 | `content_assessor` | 372 | Within limit |
| 19 | `application.preflight.extraction_parser` | 362 | Within limit |
| 20 | `arxiv.db_cache_manager` | 361 | Within limit |

### High Fan-In Modules (Most Depended Upon)

| Module | Fan-In Count | Interpretation |
|--------|--------------|----------------|
| `pipeline_input` | 13 | Core data structure, appropriate coupling |
| `prompt_texts` | 5 | Shared prompts library |
| `arxiv_reference_service` | 2 | ArXiv integration point |

### Architectural Quality Metrics

- **Total Modules**: 148
- **Total Dependencies**: 62
- **Average LOC per Module**: 176
- **Cyclic Dependencies**: 0 ✅
- **Files > 500 LOC**: 2 ⚠️
- **Modules with High Instability (>0.8)**: 12 ⚠️
- **Hotspots Requiring Attention**: 28

---

## Cross-Cutting Concerns

### Configuration Management

| File | Module | Responsibility |
|------|--------|---------------|
| `src/config_loader.py` | `config_loader` | Central configuration loader |
| `config.json` | Root | Main configuration file |
| `config.yaml` | Root | Alternative configuration format |
| `.env` | Root | Environment variables (secrets) |

### Prompts & Templates

| File | Module | Responsibility | LOC | Status |
|------|--------|---------------|-----|--------|
| `src/prompt_texts.py` | `prompt_texts` | Prompt templates library | 1755 | **⚠️ Requires refactoring** |

**Recommendation:** Split into:
- `prompts/philosophical.py`
- `prompts/scientific.py`
- `prompts/synthesis.py`
- `prompts/critique.py`
- `prompts/preflight.py`

### Logging

| File | Module | Responsibility |
|------|--------|---------------|
| `src/council/logging.py` | `council.logging` | Council-specific logging |
| Various | Throughout | Standard Python logging |

**Current State:** Basic logging present, lacks structured logging and distributed tracing.

---

## Key Insights

### Architectural Strengths

1. **Clean Layering**: Clear separation between presentation, application, domain, and infrastructure
2. **Zero Cycles**: No circular dependencies detected
3. **Domain-Driven Design**: Well-defined domain models and bounded contexts
4. **Provider Abstraction**: Flexible LLM provider switching

### Improvement Opportunities

1. **Refactor Large Files**: `prompt_texts.py` and `openai_gateway.py` exceed limits
2. **Reduce High Instability**: 12 modules with instability > 0.8 need review
3. **Enhance Observability**: Add structured logging, tracing, and metrics
4. **Formalize Contracts**: Document interfaces and API contracts
5. **Improve Test Coverage**: Measure and track coverage systematically

---

## Related Documentation

- [05_dependency_graph.dot](./05_dependency_graph.dot) - Visual dependency graph
- [06_dependency_matrix.csv](./06_dependency_matrix.csv) - Adjacency matrix
- [10_quality_gates.md](./10_quality_gates.md) - Detailed quality analysis
- [13_refactor_plan.md](./13_refactor_plan.md) - Prioritized refactoring roadmap
