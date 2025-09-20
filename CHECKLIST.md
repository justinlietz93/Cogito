# Testing and Coverage Checklist

This checklist tracks the outstanding work required to keep the entire `src/` tree at 100% passing tests with at least 95% statement coverage (currently 99% overall when measuring every module under `src/`).

## Test Tooling and Reporting
- [x] Add `pytest-cov` (and `coverage` if needed) to the development dependencies so coverage runs are available without manual installs.
  - `requirements-dev.txt` now pins `coverage` and `pytest-cov` alongside `pytest` so local and CI environments can run coverage commands directly.
- [x] Update `.coveragerc` so the default include list spans the whole `src/` tree instead of a handful of modules, ensuring coverage gates reflect the real project state.
- [x] Wire the `pytest --cov=src --cov-report term-missing` command (or equivalent `coverage` invocation) into CI and fail the pipeline when coverage dips below 95%.
- [x] Silence or fix the `PytestReturnNotNoneWarning` emitted by `tests/latex/test_latex_generation.py::test_latex_generation` to keep the suite warning-free.

## Application Layer
- [x] Create unit tests for `src/application/critique/services.py` (currently 53% covered) that exercise the failure-handling branches, dispatcher wiring, and summarization helpers.
- [x] Add tests for `src/application/critique/configuration.py` that cover the fallback/default branches around lines 115-135.
- [x] Expand coverage for `src/application/user_settings/services.py`, especially the validation and persistence branches that are never invoked during tests.

## ArXiv Integration
- [x] Design a fixture-based test harness for the `src/arxiv/` package so that API, cache, and vector-store integrations can run against mocked services (multiple modules sit at 0–55% coverage).
- [x] Prioritize coverage for `arxiv/api_client.py`, `arxiv/arxiv_reference_service.py`, and `arxiv/vector_store.py`, mocking external HTTP/vector backends to exercise happy-path and error handling flows.
- [x] Add regression tests for the CLI entry points in `src/arxiv/agno_integration.py` and `src/arxiv/arxiv_agno_service.py` to lift them off 0% coverage.
- [x] Cover caching layers (`cache_manager.py`, `db_cache_manager.py`) by simulating cache hits/misses and failure scenarios.

## Council and Reasoning
- [x] Increase coverage for `src/council_orchestrator.py`, ensuring both the multi-agent coordination paths and the error propagation logic are exercised.
  - Added `tests/council/test_council_orchestrator.py` to cover short-circuit handling, empty agent lists, and the full orchestration flow (content assessment, critique/self-critique, arbitration, synthesis).
- [x] Create tests for `src/council/adjustments.py` and `src/council/synthesis.py` to validate scoring/weighting strategies and synthesis fallbacks.
  - Added `tests/council/test_council_adjustments.py` and `tests/council/test_council_synthesis.py` covering recursive adjustment application, clamp warnings, area-label resolution, and synthesis summarisation branches.
- [x] Expand `src/reasoning_agent.py`, `src/reasoning_agent_self_critique.py`, and `src/reasoning_tree.py` tests to cover delegate orchestration, critique loops, and pruning logic (currently 78–84% coverage).
  - Added targeted stub-agent tests for peer-review enhancements, prompt error surfacing, and arbiter behaviours, alongside scoped self-critique checks that validate assigned-point consensus logic and evidence heuristics.
  - Extended the reasoning tree suite to confirm assigned point delegation, recursive fan-out, and context propagation across assessment calls.

## LaTeX Generation Pipeline
- [x] Add tests around `src/latex/cli.py`, `src/latex/config.py`, and `src/latex/formatter.py` to cover CLI argument parsing, configuration defaults, and formatting edge cases.
  - Added focused suites in `tests/latex/test_cli.py`, `tests/latex/test_config.py`, and `tests/latex/test_formatter_behavior.py` that exercise CLI overrides, configuration validation, direct conversion flows, and standard template fallbacks.
- [x] Strengthen coverage for helper modules such as `src/latex/converters/markdown_to_latex.py`, `math_formatter.py`, and the processors/utilities packages (coverage ranges from 51–90%).
  - Added metadata assertions for the jargon processor and exercised remaining formatter fallbacks so all helpers now exceed 95% coverage.
- [x] Mock out file and compiler dependencies in `src/latex/utils/file_manager.py` and `latex_compiler.py` so that compilation error handling and retry logic are tested without invoking external binaries.
  - `tests/latex/test_file_manager.py`, `tests/latex/test_latex_compiler_compile.py`, and `tests/latex/test_latex_compiler_engine.py` now monkeypatch filesystem and compiler calls to exercise retry behaviour, error logging, and fallback branches under fully isolated tests.

## Presentation Layer
- [x] Break up and test `src/presentation/cli/app.py` (currently 22% covered). Focus on command routing, configuration loading, and error handling, possibly by extracting smaller, testable components.
  - Split the monolithic test module into focused suites covering execution paths, interactive prompts, and settings workflows via `tests/presentation/cli/test_app_execution.py`, `test_app_interactive.py`, and `test_app_settings.py` backed by shared helpers.
- [x] Add coverage for `src/presentation/cli/utils.py`, ensuring formatting helpers and I/O utilities are validated.
  - Added `tests/presentation/cli/test_utils.py` to exercise latex argument extraction, base-name derivation, and API-key masking helpers.

## Providers and External Clients
- [x] Build integration-style tests with mocked HTTP transports for each provider client (`anthropic_client`, `claude_client`, `deepseek_client`, `gemini_client`, etc.), covering credential handling, retry logic, and failure modes.
  - Added targeted suites in `tests/providers/test_anthropic_client.py`, `tests/providers/test_claude_client.py`, and `tests/providers/test_deepseek_client.py` that patch SDK/HTTP dependencies to exercise streaming, fallback configuration, error wrapping, structured-response cleaning, and the high-level `run_*` helpers.
  - Included `tests/providers/test_exceptions.py` to cover the custom exception messaging and updated `.coveragerc` so provider modules participate in the global coverage gate.
- [x] Improve coverage for `src/providers/decorators.py` by exercising decorator combinations and error paths.
  - Verified the existing `tests/providers/test_decorators.py` suite under the expanded coverage configuration to ensure every branch remains executed.
- [x] Expand `src/providers/model_config.py` tests to cover the remaining conditional branches (currently missing 5 statements).
  - Extended `tests/providers/test_model_config.py` with cache-reset hooks and new assertions covering environment fallbacks, provider-specific defaults, and configuration caching semantics.

## Infrastructure and Syncretic Catalyst Modules
- [x] Write tests for repositories and gateways under `src/infrastructure/` and `src/syncretic_catalyst/infrastructure/`, focusing on file persistence, caching, and error handling (many modules sit between 16–93% coverage).
  - Repositories and gateways are now exercised end-to-end via `tests/infrastructure/*` and the dedicated `tests/syncretic_catalyst/infrastructure/` suites, covering persistence, caching, and error branches.
- [x] Cover application workflows in `src/syncretic_catalyst/application/workflow.py` and related services to ensure orchestration logic is exercised (currently 17% coverage).
  - Added regression tests for CLI entry points and workflow facades in `tests/syncretic_catalyst/test_assemble_research.py`, `test_research_enhancer.py`, `test_research_generator.py`, `test_thesis_builder.py`, and `presentation/test_cli.py`, raising the orchestration modules above the 95% threshold.
- [x] Add tests for `src/syncretic_catalyst/ai_clients.py` to validate client selection and error fallbacks.
  - `tests/syncretic_catalyst/test_ai_clients.py` now verifies provider routing, fallback behaviour, and error messaging.

## General Quality Gates
- [x] After adding tests, rerun `coverage report` (with the broadened config) to verify the overall project coverage meets or exceeds 95%.
  - `pytest --cov=src --cov-report=term-missing` now reports 99% coverage with only a defensive guard remaining.
- [x] Keep the checklist updated as modules reach ≥95% coverage and all suite warnings are resolved.
  - Syncretic Catalyst coverage additions and `.coveragerc` updates documented above ensure the checklist reflects the current status.
