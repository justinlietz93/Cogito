# Enhancement: Add Directory Input Support Across All Pipelines (Clean-Architecture Compliant)

## Context

- Current behavior:
  - Critique Council CLI accepts only a single file or literal text.
  - Syncretic Catalyst flows support directory repositories with ordered documents.
- Goal:
  - Unify input handling so any pipeline (Critique Council, ArXiv flows, Syncretic Catalyst, others) can accept a full directory as input, with deterministic ordering, safe filtering, and robust aggregation.
- Constraints:
  - Strictly follow `ARCHITECTURE_RULES.md` and project standards: layered architecture, dependency inversion, DTOs, repository pattern, ≤500 LOC per file, full docstrings, robust error handling, and test-first mindset.

## Requirements

### CLI/UX

- Add directory-based flags to all pipeline entrypoints that consume content:
  - `--input-dir <path>`
  - `--include <glob1,glob2,...>` and `--exclude <glob1,glob2,...>`
  - `--recursive` (default true)
  - `--order <file1.md,file2.md,...>` or `--order-from <path/to/order.txt|json>` (optional explicit order)
  - `--max-files <n>` and `--max-chars <n>` (safety caps)
  - `--section-separator <string>` (default: a Markdown heading separator)
  - `--label-sections` (prepend per-file headings)
- Backwards compatibility: keep the single `input_file` positional and literal-text mode working.
- Output naming: when base name derives from a directory, use directory stem; avoid duplicate “critique_critique” patterns (if base ends with `critique`, suffix becomes `_report_`).

### Architecture & Design

- Introduce an input abstraction (no shims):
  - Domain/Application contract (pure types): `ContentRepository` interface.
  - Implementations:
    - `SingleFileContentRepository` (existing behavior).
    - `DirectoryContentRepository` (new).
  - Contract (example):
    - Input: `root: Path`, `include: list[str]`, `exclude: list[str]`, `order: Optional[list[str]]`, `recursive: bool`, `max_files: int`, `max_chars: int`.
    - Output: `PipelineInput` where:
      - `content: str` (concatenated)
      - `metadata: { files: [ { path, start_offset, end_offset, bytes, sha256 } ], input_type: "directory" }`.
- Layer boundaries:
  - Presentation: parse CLI args, pass to application service.
  - Application: orchestrate repositories and build `PipelineInput`.
  - Domain: pure models/DTOs; no I/O.
  - Infrastructure: file system enumeration, filtering, ordering, reading (UTF-8 only), hashing.
- Deterministic ordering:
  - Respect explicit `--order` first; else lexicographic by path.
  - Ignore hidden files by default unless explicitly included.
  - Skip binaries (heuristic: try UTF-8 decode; on decode error, skip with log).

### Safety & Security

- Path traversal guard: keep reads within `--input-dir`.
- Symlink policy: ignore symlinks by default (consider `--follow-symlinks` later).
- Enforce `max_files` and `max_chars`; log when truncation occurs.
- Do not shell out; do not use `shell=True`; use fixed whitelisted argument lists.

### Error Handling & Logging

- Clear exceptions: invalid directory, empty selection after filters, unreadable file.
- Log counts/bytes and decisions (included/excluded files), not content.
- No silent failures; surface recoverable warnings in CLI output.

### Configuration

- `config.json` defaults (example):

  ```json
  {
    "critique": {
      "directory_input": {
        "enabled": true,
        "include": ["**/*.md", "**/*.txt"],
        "exclude": ["**/.git/**", "**/node_modules/**"],
        "recursive": true,
        "max_files": 200,
        "max_chars": 1000000,
        "label_sections": true
      }
    }
  }
  ```

- Pipelines can override defaults (Syncretic Catalyst may set a predefined order).

## Tests

### Unit (application/infrastructure)

- Merges multiple UTF-8 files in deterministic order.
- Respects include/exclude/recursive flags.
- Skips non-text/unreadable files (decode error).
- Enforces `max_files` and `max_chars` with truncation metadata.
- Directory base name derivation (no duplicate “critique_critique”).

### Integration

- Run Critique CLI with `--input-dir` on a temp tree; assert:
  - One critique output is created.
  - Base name derives from directory stem.
  - Section labels are present in aggregated content.

### E2E (optional smoke)

- With a small directory, ensure pipeline completes and writes outputs to the expected output directory.

## Documentation & Help

- Update `README.md` with directory usage examples.
- Extend CLI `--help` for new flags with examples.
- Migration note: single-file usage is unchanged.

## Non-Functional

- Performance: stream reads/concat with caps to avoid memory blow-up (chunked concatenation).
- Observability: include counts, total bytes, truncation events in logs/metadata.
- Maintainability: keep files ≤500 LOC; refactor if needed.
- Docstrings: every public module/class/function must have complete docstrings (purpose, params, returns, exceptions, side effects, timeouts).

## Scope of Code Changes (Indicative)

- `run_critique.py`: extend argparse with directory flags.
- `src/presentation/cli/app.py`: handle directory args and pass to runner; adjust base-name logic for directories.
- `src/presentation/cli/utils.py`: update `derive_base_name` to avoid duplicate suffix when base ends with “critique”.
- `src/application/critique/services.py`: integrate `ContentRepository` to produce `PipelineInput`.
- `src/infrastructure/io/directory_repository.py` (new): enumerate/filter/order/read files; produce concatenated content + metadata.
- `src/pipeline_input.py`: keep canonical; optionally add helper to accept pre-assembled directory content metadata.
- Tests under `tests/` as specified above.

## Acceptance Criteria

- Passing unit/integration tests for directory ingestion.
- CLI: `--input-dir` works for Critique Council and is easy to wire into any pipeline.
- Deterministic output naming from directory stem; no duplicate “critique_critique.”
- Enforced safety caps with clear warnings and metadata in outputs/logs.
- Documentation updated; CLI help shows new flags.
- No violation of layering/dependency rules; no shims; each file ≤500 LOC; full docstrings.

## Developer Smoke Commands

```bash
# Critique over a directory
python run_critique.py --input-dir ./examples/paper --output-dir /tmp/critiques --no-peer-review --no-scientific

# Include/exclude patterns and explicit order
python run_critique.py \
  --input-dir ./examples/paper \
  --include "**/*.md,**/*.txt" \
  --exclude "**/drafts/**" \
  --order abstract.md,intro.md,methods.md,results.md,discussion.md \
  --output-dir /tmp/critiques
```

## Notes

- Preserve current single-file behavior.
- Keep the change set minimal and layered.
- If a pipeline has its own repository abstraction (e.g., Syncretic Catalyst), add a small adapter to reuse the shared `ContentRepository` rather than duplicating logic.
- Avoid transitional “shims”; do a clean integration per the architecture rules.

## Deliverables

- Code changes and new repository implementation files.
- Tests (unit/integration) passing locally.
- Updated `README.md` and CLI help.
- Short CHANGELOG entry summarizing the enhancement.

## Agent TODO Checklist

Instruction to Agent: Populate the following categories with concrete, actionable tasks required to implement directory input support across all pipelines while strictly following `ARCHITECTURE_RULES.md`. Then execute those tasks, checking items off as you complete them. Use deterministic ordering, strong error handling, full docstrings, and add tests before implementation where feasible.

- [ ] Architecture & Design
  - [x] Define `ContentRepository` contract and DTOs
    - [x] Inspect existing `src/application` and `src/domain` packages to determine canonical location for the repository interface and DTO definitions.
    - [x] Draft interface methods (`load`, `list_metadata`) and DTO structures ensuring they remain framework agnostic and under 500 LOC per file.
    - [x] Document dependency direction and invariants for repository usage in architecture notes or inline comments referencing `ARCHITECTURE_RULES.md`.
  - [x] Sequence diagram for presentation → application → infrastructure
    - [x] Enumerate participating components (CLI parser, application service, repositories) and confirm dependency flow respects clean architecture.
    - [x] Produce Mermaid-based diagram under `docs/architecture/` illustrating request handling for single-file vs directory inputs.
    - [x] Circulate diagram for review (self-check) and update checklist once invariants verified.

- [x] CLI / UX
  - [x] Add flags (`--input-dir`, `--include`, `--exclude`, `--order`, `--order-from`, `--max-files`, `--max-chars`, `--section-separator`, `--label-sections`, `--recursive`)
    - [x] Audit each CLI entrypoint (`run_critique.py`, others) to confirm argparse wiring locations.
    - [x] Implement new flags with defaults sourced from configuration while maintaining backward compatibility with positional `input_file`.
    - [x] Ensure mutually exclusive handling between literal text, single file, and directory inputs with descriptive validation errors.
  - [x] Update `--help` with examples and defaults
    - [x] Extend argparse help strings to list default include/exclude patterns and safety caps.
    - [x] Add usage examples for directory workflows in CLI help output and README snippet.

- [x] Application Orchestration
  - [x] Wire repositories in runner to produce `PipelineInput`
    - [x] Refactor application service to accept `ContentRepository` abstraction via dependency injection.
    - [x] Implement selection logic that instantiates `SingleFileContentRepository` or `DirectoryContentRepository` based on parsed args.
    - [x] Update pipeline orchestration to consume repository output while preserving existing single-file tests.
  - [x] Handle directory base-name derivation and filename suffix logic
    - [x] Update `derive_base_name` utility to strip redundant `_critique` suffixes and respect directory stems.
    - [x] Add regression tests covering both file and directory naming scenarios.

- [x] Infrastructure (File I/O)
  - [x] Implement `DirectoryContentRepository` (enumerate, filter, order, read, hash, concat)
    - [x] Create repository module under `src/infrastructure/io/` with full docstrings and streaming read implementation.
    - [x] Support explicit ordering, lexicographic fallback, and UTF-8 decode validation with skip + log behavior.
    - [x] Aggregate metadata including offsets, byte counts, and SHA-256 digests for each included file.
  - [x] Guard path traversal; ignore symlinks; enforce caps
    - [x] Validate resolved paths remain within the declared root and reject/skip symlinks by default.
    - [x] Enforce `max_files` and `max_chars` thresholds with structured truncation metadata and warnings routed through logger.

- [x] Domain Models & DTOs
  - [x] Add directory metadata model (path, offsets, bytes, sha256)
    - [x] Define immutable dataclass or pydantic-free structure representing per-file metadata with docstrings.
    - [x] Integrate metadata into `PipelineInput` without introducing infrastructure dependencies.
  - [x] Ensure domain remains framework-agnostic
    - [x] Review imports to confirm no presentation/infrastructure modules leak into domain/application layers post-refactor.
    - [x] Add unit tests or static checks enforcing absence of forbidden dependencies if practical.

- [ ] Configuration & Defaults
  - [x] Add `critique.directory_input` defaults to `config.json`
    - [x] Extend configuration schema to include directory input defaults ensuring compatibility with existing loaders.
    - [x] Provide sane include/exclude defaults matching documentation requirements.
  - [ ] Allow pipeline overrides
    - [ ] Identify pipelines needing overrides and expose configuration hooks for customizing repository parameters.
    - [ ] Document override usage within configuration docs or inline comments.

- [x] Error Handling & Logging
  - [x] Raise explicit exceptions for invalid dir/empty selection/unreadable file
    - [x] Map repository errors to user-friendly CLI messages while preserving stack context for debugging.
    - [x] Add tests covering failure cases (missing dir, permissions, decode errors) to ensure reliability.
  - [x] Structured logs for counts/bytes/truncation (no content logging)
    - [x] Introduce logging helpers that emit structured dictionaries for instrumentation without leaking content.
    - [x] Verify logs integrate with existing logging configuration through manual smoke test or unit assertion.

- [ ] Security & Limits
  - [x] Enforce `max_files`, `max_chars` and log truncation
    - [x] Implement counters within repository to stop reading when caps reached and append truncation notices to metadata.
    - [x] Unit test truncation behavior to confirm logs and metadata entries align with requirements.
  - [x] Validate all paths stay under `--input-dir`
    - [x] Resolve candidate paths and compare to root using `Path.resolve()` guard; raise exception when violation occurs.
    - [x] Add regression test using `..` segments to confirm traversal prevention.

- [ ] Testing
  - [x] Unit: ordering, filters, decoding errors, limits, metadata
    - [x] Create fixtures for temp directories with mixed content types for deterministic testing.
    - [x] Write application-layer tests verifying repository selection and metadata assembly.
  - [ ] Integration: CLI run with `--input-dir` produces expected outputs
    - [ ] Implement CLI integration test using temporary output directory verifying file naming and section labels.
    - [ ] Capture CLI logs to assert inclusion/exclusion summaries without leaking content.
  - [ ] E2E smoke: small dir run writes outputs to target
    - [ ] Document manual smoke test steps; automate if time permits using pytest marker for slow tests.
    - [ ] Record observed output paths and naming for acceptance documentation.

- [ ] Documentation & Help
  - [x] Update README examples and CLI docs
    - [x] Add new directory usage section with sample commands and expected outputs.
    - [x] Ensure documentation cross-links to configuration defaults and safety guidance.
  - [x] Add a short migration note
    - [x] Highlight backward compatibility assurances and new flag interplay in changelog/README.

- [ ] Performance & Observability
  - [ ] Streamed concatenation to minimize memory
    - [ ] Evaluate existing concatenation logic; refactor to chunked approach if currently loading entire files into memory.
    - [ ] Benchmark repository assembly on sample directories to validate memory usage improvements.
  - [ ] Record counts/bytes/truncation in metadata
    - [ ] Extend metadata schema and tests to confirm counts and truncation flags persist through pipeline outputs.
    - [ ] Update logging to surface aggregated metrics post-run.

- [ ] Acceptance Criteria Validation
  - [ ] Verify criteria against test results and artifacts
    - [ ] Map each acceptance criterion to corresponding automated test or manual check in a tracking note.
    - [ ] Perform final review ensuring CLI help, documentation, and outputs align with specification before marking complete.

- [ ] Change Management
  - [ ] Write CHANGELOG entry and link PR
    - [ ] Draft concise changelog entry summarizing directory input enhancement and reference PR number.
    - [ ] Prepare PR description referencing checklist items and attach sequence diagram artifact.

Execution Notes:

- Plan tasks per category; mark one item in progress at a time; complete with validation steps (tests, lint, run).
- Ensure no file exceeds 500 LOC and all public members have professional docstrings.
- Avoid shims; implement the clean interface and wire through layers.
