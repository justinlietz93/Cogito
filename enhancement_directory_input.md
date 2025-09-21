# Agent TODO Checklist: LLM Point Extractor & Query Builder

Instruction to Coding Agent: Use this checklist to create concrete tasks and implement an LLM-first Point Extractor and Query Builder that plug cleanly into the existing architecture. Favor small, testable increments. Each public module/class/function must include professional docstrings. Keep files ≤500 LOC. No shims; wire via interfaces.

## 1) Architecture & Contracts

- [x] Define clean contracts in the application layer (no framework deps):
  - [x] `PointExtractorGateway` (port): extract concise, structured points from raw `PipelineInput`.
  - [x] `QueryBuilderGateway` (port): produce follow-up questions/queries from points and context.
  - [x] `ExtractionService` and `QueryBuildingService` orchestration services (thin, pure, testable).
- [x] DTOs (domain/application):
  - [x] `ExtractedPoint` (id, title, summary, evidence_refs, confidence [0-1], tags[]).
  - [x] `ExtractionResult` (points[], source_stats, truncated: bool).
  - [x] `BuiltQuery` (id, text, purpose, priority, depends_on_ids[], target_audience, suggested_tooling?).
  - [x] `QueryPlan` (queries[], rationale, assumptions, risks).
- [x] Ensure dependency direction: presentation → application → providers/infrastructure (inward only).

## 2) Prompting & Structured Output

- [x] Author robust LLM prompts (system + user) for:
  - [x] Point extraction: require strict JSON output matching a JSON Schema.
  - [x] Query building: produce questions/queries with purpose and dependency fields.
- [x] Define JSON Schemas (in `src/contexts/schemas/`):
  - [x] `extraction.schema.json` for `ExtractionResult`.
  - [x] `query_plan.schema.json` for `QueryPlan`.
- [x] Implement parser/validator:
  - [x] Strict JSON parsing with schema validation; reject if invalid and attempt 1 retry with error message reflection.
  - [x] Safe fallbacks: if still invalid, store raw text with `validation_errors` metadata and continue.

## 3) Provider Integrations

- [x] Implement provider adapters behind gateways (e.g., OpenAI first):
  - [x] Route GPT‑5/4.1/o‑series through Responses API with `max_output_tokens`.
  - [x] Set deterministic defaults (e.g., `temperature=0.2`) unless model requires override.
  - [x] Enforce timeouts via shared timeout config; no hard-coded numeric literals.
- [x] Add thin mappers: DTO ↔ provider payloads; keep providers isolated from application types.

## 4) Application Wiring

- [x] Add services:
  - [x] `ExtractionService.run(PipelineInput) -> ExtractionResult`.
  - [x] `QueryBuildingService.run(ExtractionResult, PipelineInput?) -> QueryPlan`.
- [x] Update orchestrator(s) (optional toggle):
  - [x] New preflight stage: run extraction → queries before critique, or write artifacts for later stages.
  - [x] Record outputs to artifacts directory (JSON files) and attach paths to run metadata.

## 5) CLI / UX

- [ ] CLI flags in `run_critique.py` (and any relevant entrypoints):
  - [ ] `--preflight-extract` to enable extraction.
  - [ ] `--preflight-build-queries` to enable query building.
  - [ ] `--points-out <path>` and `--queries-out <path>` to control JSON artifact locations.
  - [ ] `--max-points <n>` and `--max-queries <n>` (caps enforced in prompts and post-filtering).
- [ ] Help text and examples updated; defaults sourced from `config.json`.

## 6) Configuration & Defaults

- [ ] Extend `config.json` with:
  - [ ] `preflight.extract.enabled`, `preflight.extract.max_points`.
  - [ ] `preflight.queries.enabled`, `preflight.queries.max_queries`.
  - [ ] Model + provider settings for preflight stages (model name, temperature, tokens).
- [ ] Loader changes: keep YAML loader optional; ensure CLI path reads JSON config.

## 7) Logging, Metrics, and Observability

- [ ] Structured logs (no content):
  - [ ] Extraction summary: points_count, truncated, time_ms.
  - [ ] Query plan summary: queries_count, dependencies_present, time_ms.
  - [ ] Provider context on errors: provider, operation, stage, failure_class, fallback_used.
- [ ] Emit internal metrics: `time_to_first_token_ms`, `total_duration_ms`, `emitted_count` when streaming is applicable.

## 8) Error Handling & Timeouts

- [ ] Use shared timeout config and `operation_timeout` wrappers for blocking segments.
- [ ] Retry policy: single retry on schema-parse failure with corrective system instruction.
- [ ] Never fail silently; return artifacts with `validation_errors` when strict validation fails.

## 9) Security & Privacy

- [ ] Do not log content; only counts/ids.
- [ ] Mask API keys in logs; validate executables via `shutil.which` if any subprocesses are introduced (avoid shell).
- [ ] Respect max tokens and caps to avoid data overexposure to providers.

## 10) Tests (TDD preferred)

- [ ] Unit tests:
  - [ ] Prompt builder emits constraints and exemplars.
  - [ ] Parser validates schema and surfaces errors; retry path covered.
  - [ ] Services handle caps and truncated inputs.
- [ ] Integration tests:
  - [ ] CLI with `--preflight-extract` produces `points.json` with valid schema.
  - [ ] CLI with `--preflight-build-queries` produces `queries.json` with valid schema.
- [ ] Edge cases:
  - [ ] Empty/very small input → zero points, no errors.
  - [ ] Large input → capped points, `truncated=true` in metadata.
  - [ ] Provider error → artifact with `fallback_used=true` and error logged once.
- [ ] Decomposition Output Robustness (array vs object):
  - [ ] Normalization layer accepts both shapes:
    - [ ] If result is a list of strings, use directly.
    - [ ] If result is an object with a list-of-strings under common keys (prefer `topics`, fallback `items`/`subtopics`), extract that list.
    - [ ] If neither, log a single structured warning per run (provider, model, keys seen, expected) and skip recursion for that branch.
  - [ ] Prompt alignment:
    - [ ] Update decomposition prompt to request an object shape: `{ "topics": ["...", "..."] }` to match providers that enforce `json_object` responses when `is_structured=true`.
    - [ ] Alternatively, for o-series Responses API, prefer `json_schema` with an array-of-strings schema when supported; otherwise keep object-with-topics.
  - [ ] Tests:
    - [ ] Unit: parser accepts `list[str]` and `{topics: list[str]}`; rejects other shapes with a single warning.
    - [ ] Integration: run with decomposition using `gpt-5` and confirm no repeated warnings; recursion proceeds with extracted topics.

## 11) Documentation

- [ ] README: quickstart for preflight extraction and query building with example commands.
- [ ] Add short JSON schema docs under `docs/` with sample outputs.
- [ ] CHANGELOG: note the new preflight stages and artifacts.

## 12) Performance & Limits

- [ ] For large inputs, use a bounded chunk → summarize (map) → merge (reduce) pipeline:
  - [ ] Split content into chunks by semantic boundaries with hard size caps; attach path/offset metadata.
  - [ ] Run per‑chunk LLM passes (summaries/points) with item caps (e.g., `max_points_per_chunk`).
  - [ ] Merge and deduplicate across chunks; select top‑K globally by salience/coverage.
  - [ ] Optional final pass to normalize and fill gaps; keep total tokens within configured budget.
- [ ] Keep memory bounded (no single giant prompt or whole‑corpus in memory at once); prefer streaming/iterative processing.

## 13) Acceptance Criteria

- [ ] Passing unit + integration tests for extraction and query building paths.
- [ ] Artifacts (`points.json`, `queries.json`) validate against schemas.
- [ ] Clean architecture preserved; no layer violations; files ≤500 LOC; full docstrings present.
- [ ] CLI help and README updated; logs show summaries without leaking content.
