# Cogito Configuration Guide (config.json)

Purpose

- Central reference for configuring Cogito via config.json
- Defines each section and parameter, their meaning, valid values, and precedence rules
- Notes on environment-variable overrides, defaults, and validation

Canonical loader and file

- Canonical file: config.json at the project root
- Loader implementation: [src/config_loader.py](src/config_loader.py:1)
- CLI and pipeline entry points load JSON directly:
  - Research CLI: [src/presentation/cli/research_cli.py](src/presentation/cli/research_cli.py:365)
  - Critique CLI: [run_critique.py](run_critique.py:299)
  - Test harness: [src/main.py](src/main.py:130)

Important separation: arxiv vs research_apis

- ArXiv configuration is a top-level section "arxiv" (NOT under research_apis). It is consumed by critique/content and syncretic-catalyst flows.
  - Usage examples: [src/arxiv/arxiv_reference_service.py](src/arxiv/arxiv_reference_service.py:88)
- research_apis config is used by the multi-source ResearchAPIOrchestrator for PubMed, Semantic Scholar, CrossRef, and Web search.
  - Orchestrator initialization: [src/research_apis/orchestrator.py](src/research_apis/orchestrator.py:75)

Configuration precedence

- config.json is the primary source.
- Environment variables can override some sensitive or deployment-specific values (e.g., model names, API keys). These are documented per provider.
- CLI flags (where offered) may override config at runtime (e.g., run_research sources, parallel mode).

Validation behavior

- JSON syntax errors are raised as json.JSONDecodeError during load: [src/config_loader.py](src/config_loader.py:36)
- Several components fail fast if required values are missing (e.g., model names/keys) to avoid silent misconfiguration.

---

## Top-level structure

Below is a representative structure for config.json. Not all keys are required; defaults and environment overrides are noted under each section.

{
  "api": { ... },
  "research_apis": { ... },
  "arxiv": { ... },
  "preflight": { ... },
  "reasoning_tree": { ... },
  "council_orchestrator": { ... },
  "critique": { ... },
  "latex": { ... }
}

---

## api: Provider and model settings

Where used:

- Provider selection and model parameters are read by provider clients and orchestration layers.
- Primary provider accessor: [src/providers/model_config.py](src/providers/model_config.py:18)
- OpenAI client call path: [src/providers/openai_client.py](src/providers/openai_client.py:402)

Structure:

- primary_provider: string (e.g., "openai", "anthropic", "deepseek", "gemini")
- openai: per-provider config (see below)
- anthropic, deepseek, gemini, xai, openrouter, ollama, etc.: provider-specific sections are supported by the evolving provider modules

Notes:

- Hardcoded providers or model IDs in code were removed. You must specify model(s) here (or via environment variables) for active providers.
- If required values are missing (e.g., model name or API key), provider code will now fail clearly at runtime with explicit errors.

### api.primary_provider

- Description: The default provider used by high-level orchestration when a provider is not explicitly selected by a caller.
- Type: string
- Required: Yes for high-level "AIOrchestrator" usage
- Example: "openai"
- Accessor: [get_primary_provider()](src/providers/model_config.py:18)
- Env override: PRIMARY_PROVIDER (optional convention)

### api.openai

Common fields (example):
{
  "model": "gpt-5",
  "retries": 3,
  "temperature": 0.2,
  "max_tokens": 30000,
  "system_message": "You are a helpful assistant"
}

Fields:

- model (string, required): The model identifier to use (no hardcoded fallback).
- max_tokens (number, optional): Default token budget (non-o-series); o-series uses responses API.
- temperature (number, optional): Sampling temperature (skipped for o-series reasoning chat models where unsupported).
- retries (number, optional): Retry attempts in caller logic.
- system_message (string, optional): Default system message template.

Environment overrides:

- OPENAI_API_KEY (required for live calls)
- OPENAI_MODEL or OPENAI_DEFAULT_MODEL (used only if config model is not set)
- If no model resolved (config/env), [run_openai_client()](src/providers/openai_client.py:402) and [call_openai_with_retry()](src/providers/openai_client.py:109) fail fast.

### api.gemini

Example:
{
  "model_name": "gemini-2.5-pro-exp-03-25",
  "retries": 3,
  "temperature": 0.6,
  "top_p": 1.0,
  "top_k": 32,
  "max_output_tokens": 8192
}

- model_name (string, required): Gemini model id.
- Other numeric tunings are optional.

### api.deepseek

Example:
{
  "model_name": "deepseek-reasoner",
  "base_url": "<https://api.deepseek.com/v1>"
}

- model_name (string, required): DeepSeek model id.
- base_url (string, required for self-hosted or when provider SDK expects it)

Other providers (anthropic, xai, openrouter, ollama):

- Follow similar patterns (api.{provider}.*). Keys depend on the provider modules currently integrated.

---

## research_apis: Multi-source research orchestrator

Where used:

- Provider registration and parallel search: [src/research_apis/orchestrator.py](src/research_apis/orchestrator.py:60)

Structure:
{
  "pubmed": {
    "enabled": true,
    "timeout": 30,
    "max_retries": 3,
    "retry_delay": 1.0,
    "tool_name": "Cogito",
    "email": ""
  },
  "semantic_scholar": {
    "enabled": true,
    "timeout": 30,
    "max_retries": 3,
    "retry_delay": 1.0
  },
  "crossref": {
    "enabled": true,
    "timeout": 30,
    "max_retries": 3,
    "retry_delay": 1.0,
    "email": "<cogito@example.com>"
  },
  "web_search": {
    "enabled": true,
    "timeout": 30,
    "max_retries": 3,
    "retry_delay": 1.0,
    "search_engine": "duckduckgo",
    "use_fallback": true
  }
}

Fields (per provider):

- enabled (bool): Include in orchestrator
- timeout (int): HTTP timeout (seconds)
- max_retries (int): Retry count for transient failures
- retry_delay (float): Base delay for backoff
- Provider-specific:
  - pubmed.email (string): Contact email per E-utilities policy
  - crossref.email (string): CrossRef polite rate-limiting email
  - web_search.search_engine (string): "duckduckgo" | "google" | "bing" (SerpAPI requires API key)
  - web_search.use_fallback (bool): Use DuckDuckGo HTML scraping when SerpAPI fails/unavailable

Note on dynamic routing:

- The ResearchQueryExecutor uses a DomainRouter to select relevant sources per query when --sources is not provided:
  - [src/application/research_execution/services.py](src/application/research_execution/services.py:85)
  - [src/application/research_execution/domain_router.py](src/application/research_execution/domain_router.py:1)

---

## arxiv: ArXiv configuration (Top-level)

Where used:

- Critique/content and syncretic-catalyst flows (not orchestrator): [src/arxiv/arxiv_reference_service.py](src/arxiv/arxiv_reference_service.py:88)

Structure:
{
  "enabled": true,
  "max_references_per_point": 3,
  "cache_dir": "storage/arxiv_cache",
  "use_cache": true,
  "use_db_cache": true,
  "cache_ttl_days": 30,
  "search_sort_by": "relevance",
  "search_sort_order": "descending",
  "update_bibliography": true
}

Fields:

- enabled (bool): Toggle ArXiv lookups in flows that use them
- max_references_per_point (int): Limit references per extracted content point
- cache_dir (string): Path to ArXiv cache
- use_cache (bool): Use cached results
- use_db_cache (bool): Use SQLite-based cache vs file cache
- cache_ttl_days (int): Cache expiration
- search_sort_by (string): "relevance" | "lastUpdatedDate" | "submittedDate"
- search_sort_order (string): "ascending" | "descending"
- update_bibliography (bool): Update LaTeX bibliography artifacts

Vector and embedding notes:

- Some ArXiv vector store options appear under arxiv.* (e.g., vector_table_name, vector_cache_dir) depending on store backend modules. Check:
  - [src/arxiv/arxiv_vector_reference_service.py](src/arxiv/arxiv_vector_reference_service.py:55)
  - [docs/vector_search.md](docs/vector_search.md:9)

---

## preflight: Extraction and query-building

Where used:

- Preflight CLI integration in critique pipeline: [run_critique.py](run_critique.py:77)

Structure:
{
  "provider": "openai",
  "metadata": { "stage": "preflight" },
  "extract": {
    "enabled": false,
    "max_points": 12,
    "artifact_path": "artifacts/points.json"
  },
  "queries": {
    "enabled": false,
    "max_queries": 8,
    "artifact_path": "artifacts/queries.json"
  },
  "api": {
    "openai": { "model": "gpt-4.1-mini", "temperature": 0.2, "max_tokens": 8192 }
  }
}

Fields:

- provider (string): LLM provider for preflight steps (independent of api.primary_provider if you wish)
- extract.enabled / max_points / artifact_path: Controls for key point extraction
- queries.enabled / max_queries / artifact_path: Controls for query building
- api.*: Optional preflight-specific provider config

### When to set extract.enabled or queries.enabled to false

- You already have curated artifacts: Use precomputed INPUT/ artifacts (e.g., points.json, queries.json) verbatim without regenerating.
- Deterministic/audited runs: Avoid non-determinism and reduce token use; drive runs from fixed artifacts for reproducibility and regression testing.
- Cost or rate-limit constraints: Skip LLM-dependent preflight during quick local dry-runs or when provider quotas are tight.
- Offline or keyless environments: CI or air-gapped environments without provider keys can bypass preflight stages.
- Narrow manual prompts: You intentionally prepared a single handcrafted query/summary in INPUT; auto-generating extras may add noise.
- Pipelined workflows: An upstream system is responsible for extraction/query-building; this pipeline should only critique/report.

Recommended defaults:

- Operational default: set both extract.enabled and queries.enabled to true for most interactive/standard workflows.
- Set to false only for the scenarios above. CLI flags may also force-enable these stages at runtime.

---

## reasoning_tree

Structure:
{ "max_depth": 1, "confidence_threshold": 0.3 }

Fields:

- max_depth (int): Depth of exploration in reasoning tree
- confidence_threshold (float): Threshold that affects pruning or confidence gating

---

## council_orchestrator

Structure:
{ "synthesis_confidence_threshold": 0.4 }

Fields:

- synthesis_confidence_threshold (float): Threshold for synthesis/consensus gating

---

## critique.directory_input and overrides

Where used:

- Critique CLI directory ingestion behavior: [run_critique.py](run_critique.py:77)
- INPUT-only ingestion is enforced by CLI guards:
  - Path resolution and enforcement: [run_critique.py](run_critique.py:356)
  - Utilities for discovery and concatenation:
    - [find_all_input_files()](src/input_reader.py:56)
    - [concatenate_inputs()](src/input_reader.py:93)
    - [materialize_concatenation_to_temp()](src/input_reader.py:109)

Structure:
{
  "directory_input": {
    "enabled": true,
    "include": ["**/*.md", "**/*.txt"],
    "exclude": ["**/.git/**", "**/node_modules/**"],
    "recursive": true,
    "max_files": 200,
    "max_chars": 1000000,
    "section_separator": "\n\n---\n\n",
    "label_sections": true
  },
  "directory_input_overrides": {
    "syncretic_catalyst": {
      "order": ["PROJECT_OVERVIEW.md", "RESEARCH_CONTEXT.md", "NEXT_STEPS.md"],
      "label_sections": false,
      "section_separator": "\n\n---\n\n"
    }
  }
}

Fields:

- include/exclude: Glob filters
- recursive (bool): Descend into subdirectories
- max_files, max_chars: Caps for ingestion
- section_separator, label_sections: Formatting options for aggregated content

---

## latex

Where used:

- LaTeX generation and formatting steps: [src/latex/cli.py](src/latex/cli.py:28), [src/latex/formatter.py](src/latex/formatter.py:28)

Common fields:
{
  "document_class": "article",
  "document_options": ["12pt", "a4paper"],
  "template_dir": "src/latex/templates",
  "main_template": "academic_paper.tex",
  "scientific_template": "scientific_paper.tex",
  "philosophical_template": "philosophical_paper.tex",
  "preamble_template": "preamble.tex",
  "bibliography_template": "bibliography.bib",
  "replace_philosophical_jargon": true,
  "scientific_objectivity_level": "high",
  "scientific_mode": false,
  "include_bibliography": true,
  "detect_math": true,
  "math_environments": ["equation", "align", "gather"],
  "inline_math_delimiters": ["$", "$"],
  "display_math_delimiters": ["$$", "$$"],
  "output_dir": "latex_output",
  "output_filename": "critique_report",
  "compile_pdf": true,
  "keep_tex": true,
  "latex_engine": "pdflatex",
  "latex_args": ["-interaction=nonstopmode", "-halt-on-error"],
  "bibtex_run": true,
  "latex_runs": 2
}

---

## Examples

Minimal configuration (OpenAI only, ArXiv enabled)
{
  "api": {
    "primary_provider": "openai",
    "openai": { "model": "gpt-5", "temperature": 0.2, "max_tokens": 30000 }
  },
  "arxiv": {
    "enabled": true,
    "max_references_per_point": 3,
    "use_cache": true,
    "use_db_cache": true,
    "cache_dir": "storage/arxiv_cache",
    "cache_ttl_days": 30,
    "search_sort_by": "relevance",
    "search_sort_order": "descending",
    "update_bibliography": true
  },
  "research_apis": {
    "pubmed": { "enabled": false },
    "semantic_scholar": { "enabled": true },
    "crossref": { "enabled": true },
    "web_search": { "enabled": true, "search_engine": "duckduckgo", "use_fallback": true }
  }
}

Multi-provider with domain-aware routing (default behavior)

- DomainRouter uses query text to select among enabled sources. No extra config required:
  - Router: [src/application/research_execution/domain_router.py](src/application/research_execution/domain_router.py:1)
  - Executor integration: [src/application/research_execution/services.py](src/application/research_execution/services.py:85)

---

## Environment variables

Common:

- OPENAI_API_KEY (required for OpenAI live calls)
- OPENAI_MODEL / OPENAI_DEFAULT_MODEL (used only if config omits model)
- PUBMED_API_KEY (optional, better rate limits; services may accept email instead for polite usage)
- SERPAPI_KEY (optional, enables SerpAPI web search with Google/Bing)
- Provider-specific keys: ANTHROPIC_API_KEY, GEMINI_API_KEY, etc. as applicable to provider client code

Note:

- Environment overrides do not select providers for you; keep api.primary_provider and provider sections consistent in config.

---

## Migration notes (YAML → JSON)

- The canonical configuration is now config.json. YAML loading support was removed from the core loader.
- Tests were updated to JSON:
  - Loader tests: [tests/test_config_loader.py](tests/test_config_loader.py:1)
  - Agno demo test harness now reads config.json: [tests/test_agno_reference_service.py](tests/test_agno_reference_service.py:47)
- If config.yaml remains present in your repo, it is inert (not read by loaders). Remove it manually as per your policy.

---

## Troubleshooting

- "Model not configured" errors:
  - Ensure config.json includes the provider model (e.g., api.openai.model).
  - Alternatively set an environment override (OPENAI_MODEL); the provider code will honor env only if the config value is absent.

- "API key not found":
  - Set the appropriate provider key in environment (e.g., OPENAI_API_KEY).
  - Some providers allow keys in config; use with care and prefer environment for secrets.

- "Invalid JSON" on startup:
  - Fix syntax errors; the loader raises json.JSONDecodeError. Validate with jq or any JSON linter.

- ArXiv results missing:
  - Confirm "arxiv.enabled": true and cache settings.
  - ArXiv is not part of research_apis by design; flows that rely on the orchestrator will not use ArXiv unless you choose to integrate it explicitly.

---

## Security and best practices

- Prefer environment variables for secrets (API keys), not committed config files.
- Avoid hardcoded model ids or providers in code; select via config.json.
- Keep provider enablement minimal (disable irrelevant research_apis.* sources to reduce noise and bandwidth).
- Use domain-aware routing (default) for efficient research API usage.
