# Cogito Backend Pipeline Flow

This document traces the complete data flow through Cogito's backend pipelines, from input ingestion to final output.

## Overview

Cogito has two main pipelines:
1. **Critique Pipeline**: Analyzes and critiques documents
2. **Syncretic Catalyst Pipeline**: Synthesizes research from concepts

Both pipelines can now leverage the new research API integrations.

## Pipeline 1: Critique Pipeline with Research Enhancement

### Flow Diagram

```
Input Files (input/)
    ↓
Directory Input Aggregation
    ↓
[Optional] Preflight Extraction
    ↓
Key Points & Insights (artifacts/points.json)
    ↓
[Optional] Query Plan Generation
    ↓
Research Queries (artifacts/queries.json)
    ↓
[NEW] Multi-Source Research Execution
    ├── PubMed
    ├── Semantic Scholar
    ├── CrossRef
    └── Web Search
    ↓
Research Results (artifacts/research_results.json)
    ↓
Critique Council Analysis
    ├── Philosophical Agents
    ├── Scientific Agents
    └── Arbiter
    ↓
Formatted Critique Output
    ↓
[Optional] LaTeX Compilation
    ↓
Final Output (critiques/*.md or *.pdf)
```

### Detailed Steps

#### Step 1: Input Aggregation

**Entry Point**: `run_critique.py`

```python
# File: src/presentation/cli/app.py
# Function: CliApp.run()

# Handles:
# - Single file input
# - Directory input (--input-dir)
# - Literal text input
```

**Directory Input Features**:
- Recursive traversal
- Include/exclude patterns (globs)
- Explicit file ordering
- Max file/character limits
- Section labeling

**Implementation**:
```python
# File: src/infrastructure/io/directory_repository.py
# Class: DirectoryContentRepository

def load_input(self) -> PipelineInput:
    # 1. Discover files matching patterns
    # 2. Apply ordering rules
    # 3. Aggregate content with metadata
    # 4. Return unified PipelineInput
```

#### Step 2: Preflight Extraction (Optional)

**Trigger**: `--preflight-extract` flag

```python
# File: src/application/preflight/services.py
# Class: ExtractionService

def run(self, pipeline_input: PipelineInput) -> ExtractionResult:
    # 1. Send content to extraction gateway
    # 2. Parse and validate response
    # 3. Return structured points
```

**Output**: `ExtractedPoint` objects with:
- ID (unique identifier)
- Title (summary heading)
- Summary (detailed description)
- Evidence references
- Confidence score
- Tags

**File**: `artifacts/points.json`

#### Step 3: Query Plan Generation (Optional)

**Trigger**: `--preflight-build-queries` flag

```python
# File: src/application/preflight/services.py
# Class: QueryBuildingService

def run(self, extraction: ExtractionResult) -> QueryPlan:
    # 1. Analyze extracted points
    # 2. Generate research queries
    # 3. Set priorities and dependencies
    # 4. Return structured plan
```

**Output**: `QueryPlan` with:
- Multiple `BuiltQuery` objects
- Rationale and assumptions
- Dependency graph
- Target audiences

**File**: `artifacts/queries.json`

#### Step 4: Research Query Execution (NEW)

**Trigger**: `run_research.py execute-plan`

```python
# File: src/application/research_execution/services.py
# Class: ResearchQueryExecutor

def execute_query_plan(self, query_plan: QueryPlan) -> QueryExecutionResult:
    # 1. Sort queries by priority
    # 2. Check dependencies
    # 3. Execute via ResearchAPIOrchestrator
    # 4. Aggregate and deduplicate results
    # 5. Save to JSON
```

**Orchestrator Flow**:
```python
# File: src/research_apis/orchestrator.py
# Class: ResearchAPIOrchestrator

def search_all(self, query: str) -> List[ResearchResult]:
    # Parallel execution:
    with ThreadPoolExecutor() as executor:
        futures = [
            executor.submit(pubmed.search, query),
            executor.submit(semantic_scholar.search, query),
            executor.submit(crossref.search, query),
            executor.submit(web_search.search, query),
        ]
        # Collect results
        # Deduplicate by URL and title
        # Return unified list
```

**Output**: `QueryExecutionResult` with:
- Research results per query
- Execution statistics
- Detailed logs

**File**: `artifacts/research_results.json`

#### Step 5: Critique Council Analysis

**Entry Point**: `critique_goal_document()` in `src/main.py`

```python
# File: src/council_orchestrator.py
# Function: run_critique_council()

def run_critique_council(pipeline_input, config, peer_review, scientific_mode):
    # 1. Initialize agents (philosophical or scientific)
    # 2. Generate critiques from each agent
    # 3. Synthesize via arbiter
    # 4. Format output
```

**Agent Types**:
- **Philosophical**: Aristotle, Descartes, Kant, Leibniz, Popper, Russell
- **Scientific**: Domain-specific methodology agents

#### Step 6: Output Formatting

```python
# File: src/output_formatter.py
# Function: format_critique_output()

# Formats as:
# - Markdown report
# - [Optional] LaTeX document
# - [Optional] PDF compilation
```

### Code Trace Example

**Command**:
```bash
python run_critique.py --input-dir ./input \
  --preflight-extract \
  --preflight-build-queries \
  --scientific --peer-review
```

**Call Stack**:
```
1. run_critique.py::main()
2. CliApp.run(args)
3. CritiqueRunner.run(input_source)
4. DirectoryContentRepository.load_input()
   → Returns: PipelineInput with aggregated content
5. PreflightOrchestrator.run(pipeline_input, options)
   a. ExtractionService.run() → ExtractedPoint[]
   b. QueryBuildingService.run() → QueryPlan
6. [Manual step] run_research.py execute-plan queries.json
   → ResearchQueryExecutor.execute_query_plan()
   → Returns: QueryExecutionResult
7. ModuleCritiqueGateway.run(pipeline_input, config)
8. critique_goal_document(pipeline_input)
9. run_critique_council(pipeline_input)
   → Returns: critique_data
10. format_critique_output(critique_data)
    → Returns: formatted_output (Markdown)
11. [Optional] LaTeX generation and compilation
```

## Pipeline 2: Syncretic Catalyst (Research Synthesis)

### Flow Diagram

```
Research Concept/Query
    ↓
Thesis Builder Service
    ↓
Vector Search (ArXiv)
    ↓
[NEW] Multi-Source Research (Optional)
    ├── PubMed
    ├── Semantic Scholar
    ├── CrossRef
    └── Web Search
    ↓
Multi-Agent Research Team
    ├── Historical Development Agent
    ├── Modern Research Agent
    ├── Methodological Agent
    ├── Mathematical Agent
    ├── Empirical Evidence Agent
    ├── Interdisciplinary Agent
    └── Implications Agent
    ↓
Thesis Synthesis
    ↓
Output Files (syncretic_output/)
    ├── thesis.md
    ├── agent_outputs.json
    └── references.bib
```

### Entry Point

**Command**:
```bash
python src/syncretic_catalyst/thesis_builder.py "quantum computing applications"
```

**Implementation**:
```python
# File: src/syncretic_catalyst/thesis_builder.py
# Function: build_thesis()

def build_thesis(concept, model, force_fallback, output_dir, max_papers):
    # 1. Initialize AI orchestrator
    # 2. Initialize reference service (ArXiv)
    # 3. Create thesis builder service
    # 4. Execute multi-agent research
    # 5. Synthesize thesis
    # 6. Generate outputs
```

### Agent Profiles

```python
# File: src/syncretic_catalyst/domain/thesis_agents.py
# Constant: DEFAULT_AGENT_PROFILES

AGENT_PROFILES = [
    "historical_development",
    "modern_research",
    "methodological_approaches",
    "mathematical_formalization",
    "empirical_evidence",
    "interdisciplinary_connections",
    "implications_applications"
]
```

### Integration Points for New Research APIs

The syncretic catalyst can be enhanced to use the new research APIs:

```python
# Future enhancement - not yet implemented
from src.research_apis import ResearchAPIOrchestrator

# In thesis_builder.py
orchestrator = ResearchAPIOrchestrator(config)
multi_source_results = orchestrator.search_all(
    query=concept,
    max_results_per_source=max_papers
)
```

## Data Structures

### PipelineInput

```python
@dataclass
class PipelineInput:
    """Unified input format for all pipelines."""
    content: str  # Aggregated text content
    source: str  # Source identifier
    metadata: Dict[str, Any]  # Extended metadata
    
    # For directory inputs:
    # metadata['aggregated'] = AggregatedContentMetadata
    #   - segments: List[FileSegmentMetadata]
    #   - total_bytes, truncated, etc.
```

### ExtractedPoint

```python
@dataclass(frozen=True)
class ExtractedPoint:
    """Key insight extracted during preflight."""
    id: str
    title: str
    summary: str
    evidence_refs: Tuple[str, ...]
    confidence: float  # 0.0-1.0
    tags: Tuple[str, ...]
```

### BuiltQuery

```python
@dataclass(frozen=True)
class BuiltQuery:
    """Research query generated from insights."""
    id: str
    text: str  # Actual query text
    purpose: str  # Why this query matters
    priority: int  # Execution order
    depends_on_ids: Tuple[str, ...]  # Dependencies
    target_audience: Optional[str]
    suggested_tooling: Tuple[str, ...]
```

### ResearchResult

```python
@dataclass
class ResearchResult:
    """Unified result from any research source."""
    id: str  # DOI, PMID, paper ID, URL
    title: str
    authors: List[str]
    abstract: str
    url: str
    published_date: Optional[str]
    source: str  # "pubmed", "semantic_scholar", etc.
    metadata: Dict[str, Any]
    relevance_score: Optional[float]
```

## Configuration Flow

### Config Loading

```python
# 1. Load config.json
with open('config.json') as f:
    config = json.load(f)

# 2. Environment variables override
config['research_apis']['pubmed']['api_key'] = os.getenv('PUBMED_API_KEY', '')

# 3. CLI arguments override
if args.sources:
    enabled_sources = args.sources.split(',')
```

### Provider Initialization

```python
# In ResearchAPIOrchestrator.__init__()
research_config = config.get('research_apis', {})

if research_config.get('pubmed', {}).get('enabled', True):
    self.providers['pubmed'] = PubMedAPI(
        api_key=research_config.get('pubmed', {}).get('api_key'),
        config=research_config.get('pubmed', {})
    )
```

## Error Handling Flow

### Defensive Exception Handling

All external API calls use defensive exception handling:

```python
try:
    results = provider.search(query)
except Exception as exc:  # noqa: BLE001
    logger.error("Provider %s failed: %s", provider_name, exc)
    # Continue with other providers
```

### Retry Logic

```python
for attempt in range(self.max_retries):
    try:
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        return self._parse_response(response)
    except requests.exceptions.RequestException as exc:
        if attempt < self.max_retries - 1:
            wait_time = self.retry_delay * (attempt + 1)
            time.sleep(wait_time)
        else:
            raise
```

### Fallback Strategies

1. **Web Search**: SerpAPI → DuckDuckGo
2. **Multi-source**: Continue with successful providers
3. **Validation**: Use raw response when structured parsing fails

## Performance Characteristics

### Directory Input
- **Time**: O(n) where n = number of files
- **Memory**: Holds aggregated content in memory
- **Limits**: Configurable max_files and max_chars

### Preflight Extraction
- **Time**: O(tokens) - LLM processing time
- **Memory**: Single request/response cycle
- **Limits**: Model token limits (handled via truncation)

### Research Query Execution
- **Time**: O(queries × sources) or O(max(sources)) if parallel
- **Memory**: Accumulates results in memory
- **Limits**: API rate limits, network timeouts

### Critique Council
- **Time**: O(agents × critique_passes)
- **Memory**: Agent outputs accumulated
- **Limits**: LLM token limits, API rate limits

## Monitoring and Observability

### Logging

All modules use structured logging:

```python
logger.info(
    "operation=search provider=%s query=%s results=%d",
    provider_name,
    query,
    len(results)
)
```

### Execution Logs

```python
QueryExecutionResult.execution_log = [
    "[START] Query q1: Purpose description",
    "[SUCCESS] Query q1: 15 results",
    "[START] Query q2: Purpose description",
    "[FAILED] Query q2: Network timeout"
]
```

### Performance Metrics

Future enhancement - add telemetry:
- Query execution time
- API response times
- Cache hit rates
- Error rates by provider

## Future Pipeline Enhancements

1. **Streaming Results**: Stream research results as they arrive
2. **Incremental Processing**: Process files as they're discovered
3. **Caching**: Cache research results and extracted points
4. **Parallelization**: Parallel critique agent execution
5. **Checkpointing**: Resume interrupted pipelines
6. **Result Ranking**: Score and rank research results by relevance

## Debugging Tips

### Enable Debug Logging

```python
logging.basicConfig(level=logging.DEBUG)
```

### Trace Request/Response

```python
# In research API code
logger.debug("Request URL: %s", url)
logger.debug("Request params: %s", params)
logger.debug("Response status: %d", response.status_code)
logger.debug("Response body: %s", response.text[:500])
```

### Check Intermediate Artifacts

```bash
# View extracted points
cat artifacts/points.json | jq '.points[] | {id, title}'

# View query plan
cat artifacts/queries.json | jq '.queries[] | {id, text, priority}'

# View research results
cat artifacts/research_results.json | jq '.summary'
```

### Test Individual Components

```python
# Test directory input
from src.infrastructure.io.file_repository import FileSystemContentRepositoryFactory
from src.application.critique.requests import DirectoryInputRequest
from pathlib import Path

request = DirectoryInputRequest(root=Path('./input'))
factory = FileSystemContentRepositoryFactory()
repo = factory.create_for_directory(request)
pipeline_input = repo.load_input()
print(f"Loaded {len(pipeline_input.content)} characters")
```

## Summary

The Cogito backend now provides:
- ✅ Robust directory input pipeline
- ✅ Intelligent preflight extraction and query generation
- ✅ Multi-source research execution (4 providers)
- ✅ Unified data flow from input to output
- ✅ Comprehensive error handling and logging
- ✅ Clean architecture with clear boundaries
- ✅ Extensible design for future enhancements

All pipelines trace cleanly from input through processing to final output, with clear integration points for the new research API capabilities.
