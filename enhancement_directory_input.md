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
  - [ ] Define `ContentRepository` contract and DTOs
  - [ ] Sequence diagram for presentation → application → infrastructure

- [ ] CLI / UX
  - [ ] Add flags (`--input-dir`, `--include`, `--exclude`, `--order`, `--order-from`, `--max-files`, `--max-chars`, `--section-separator`, `--label-sections`, `--recursive`)
  - [ ] Update `--help` with examples and defaults

- [ ] Application Orchestration
  - [ ] Wire repositories in runner to produce `PipelineInput`
  - [ ] Handle directory base-name derivation and filename suffix logic

- [ ] Infrastructure (File I/O)
  - [ ] Implement `DirectoryContentRepository` (enumerate, filter, order, read, hash, concat)
  - [ ] Guard path traversal; ignore symlinks; enforce caps

- [ ] Domain Models & DTOs
  - [ ] Add directory metadata model (path, offsets, bytes, sha256)
  - [ ] Ensure domain remains framework-agnostic

- [ ] Configuration & Defaults
  - [ ] Add `critique.directory_input` defaults to `config.json`
  - [ ] Allow pipeline overrides

- [ ] Error Handling & Logging
  - [ ] Raise explicit exceptions for invalid dir/empty selection/unreadable file
  - [ ] Structured logs for counts/bytes/truncation (no content logging)

- [ ] Security & Limits
  - [ ] Enforce `max_files`, `max_chars` and log truncation
  - [ ] Validate all paths stay under `--input-dir`

- [ ] Testing
  - [ ] Unit: ordering, filters, decoding errors, limits, metadata
  - [ ] Integration: CLI run with `--input-dir` produces expected outputs
  - [ ] E2E smoke: small dir run writes outputs to target

- [ ] Documentation & Help
  - [ ] Update README examples and CLI docs
  - [ ] Add a short migration note

- [ ] Performance & Observability
  - [ ] Streamed concatenation to minimize memory
  - [ ] Record counts/bytes/truncation in metadata

- [ ] Acceptance Criteria Validation
  - [ ] Verify criteria against test results and artifacts

- [ ] Change Management
  - [ ] Write CHANGELOG entry and link PR

Execution Notes:

- Plan tasks per category; mark one item in progress at a time; complete with validation steps (tests, lint, run).
- Ensure no file exceeds 500 LOC and all public members have professional docstrings.
- Avoid shims; implement the clean interface and wire through layers.
