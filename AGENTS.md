# Technical Summary Report

**Generated on:** September 16, 2025 at 11:02 PM CDT

---

## Generated Summary

### Core Mission

- The agent's primary goal is to guide, enforce, and analyze the implementation of software components against a set of predefined engineering standards, security policies, and architectural guidelines.
- Ensure adherence to current best practices (modular monolith, clean architecture, security, scalability, maintainability, testability, framework independence) and drive the roadmap toward future improvements emphasizing robustness, security, reliability, and observability.
- Act as an independent, low-friction assistant tailored for solo developers, making safe, low-risk changes, preserving project context, and diligently following architectural and operational standards.
- Ensure code quality and security by integrating with Codacy's MCP Server, running analyses, and applying fixes.
- Track all work using the GitHub CLI (`/mnt/samsung_ssd/notes/github_tools/cli.py`).

### Constraints & Rules

- **General Code & Architecture:**
  - **CRITICAL**: No source code file shall exceed 500 lines of code (LOC). Break large files into smaller, focused components.
  - Dependencies must flow inward only. Outer layers depend on inner layers via abstractions (interfaces); inner layers must never reference or depend on outer layers.
  - All cross-layer communication must occur via interfaces defined in abstraction projects.
  - Controllers/handlers must be thin; delegate business logic to services/managers.
  - Use DTOs for data transfer.
  - Presentation layer: No direct database access or business rules.
  - Business Logic layer: Contain all business rules and validations; be framework-agnostic. Use repository pattern for data access.
  - Domain layer: Pure models (POCOs), no business logic, framework-independent.
  - Infrastructure/Persistence layer: Implement repository interfaces, handle data persistence/ORM details, no business logic.
  - Design for unit testing by depending on abstractions.
  - Each project/module should have a single responsibility.
  - **CRITICAL**: Never create "shims" when replacing deprecated functions or patterns. Always do a full replacement unless explicitly instructed otherwise to avoid technical debt.
  - Adopt a comprehensive, automated testing pyramid: heavy unit tests (fast, isolated), moderate integration (components interaction), light end-to-end (full flow).
  - Use Test-Driven Development (TDD) or Behavior-Driven Development (BDD). Aim for 80%+ test coverage.
  - Always add brief logged explanations for any programmatic test that explains what the test is actually attempting to prove/disprove.
  - Implement layered validation (client-side, server-side, DB-level) with a fail-early principle. Automate 90% of validation.
- **Docstrings & Documentation:**
  - **CRITICAL**: ALWAYS CREATE FULL, PROFESSIONAL, AND DESCRIPTIVE DOCSTRINGS for all functions and classes.
  - Module docstring MUST state: purpose, external dependencies (CLI/HTTP), fallback semantics, timeout strategy.
  - Public function docstrings MUST include: summary, parameters, return description, raised exceptions/failure modes, side effects (I/O, persistence), and timeout/retry notes where relevant.
- **Timeout & Error Handling:**
  - Always use `get_timeout_config()` for HTTP calls, local CLI invocation, and streaming start phases.
  - Wrap blocking/start segments in `operation_timeout` (supports nesting; restores previous handlers and timers).
  - Never introduce hard-coded numeric timeouts in provider code or related tests.
  - Log provider + operation context on exception paths before fallback.
  - Replace broad silent suppression with explicit `try/except` and structured logging.
  - Required log context keys: `provider`, `operation`, `stage` (start|mid_stream|finalize|retry), `failure_class`, `fallback_used`.
  - Each fallback path must log its trigger exactly once (avoid duplicated messages).
  - On live fetch failure, return cached snapshot (models/metadata) after logging primary cause.
  - Never fail silently or mask the underlying exception type in logs.
- **Subprocess & Security:**
  - Resolve executables via `shutil.which` to an absolute path.
  - Validate executables: basename, regular file, executable bit set, not group/other writable.
  - Use fixed whitelisted argument lists; never `shell=True`.
  - Never interpolate user input into subprocess arguments.
  - Log subprocess failures (warning when falling back; error when aborting) — no silent suppression.
  - Each `# nosec` requires an inline justification (e.g., `# nosec B603 - validated fixed arg list`).
  - **CRITICAL**: IMMEDIATELY after ANY package manager operations (e.g., `npm/yarn/pnpm install`, adding dependencies to `package.json`, `requirements.txt`, `pom.xml`, `build.gradle`), run `codacy_cli_analyze` with `rootPath` and `tool` set to "trivy" (`file` empty/unset). If vulnerabilities are found, stop all other operations, propose and apply fixes, and only continue with the original task after security issues are resolved.
- **Streaming & Metrics:**
  - All streaming implementations MUST use `BaseStreamingAdapter`; remove bespoke streaming loops (no transitional shim).
  - Use `streaming_supported()` for capability gating; short-circuit explicitly if unsupported.
  - Internally capture metrics: `time_to_first_token_ms`, `total_duration_ms`, `emitted_count` (names are normative).
  - New metric names must be added to the `providers-project-instructions.instructions.md` file before implementation.
- **Codacy Integration:**
  - **CRITICAL**: IMMEDIATELY after ANY successful `edit_file` or `reapply` operation, run the `codacy_cli_analyze` tool from Codacy's MCP Server for each file that was edited (`rootPath` set to the workspace path, `file` set to the path of the edited file, `tool` empty/unset). If any issues are found in the new edits, propose and apply fixes for them.
  - After every response, verify `codacy_cli_analyze` tool was run if any file edits were made in that conversation.
  - Do NOT wait for the user to ask for analysis or remind you to run the tool.
  - Do NOT run `codacy_cli_analyze` looking for changes in duplicated code, code complexity metrics, or code coverage.
  - Do NOT try to manually install Codacy CLI using any package manager. If the Codacy CLI is not installed, just run the `codacy_cli_analyze` tool from Codacy's MCP Server.
  - When calling a tool that needs a `rootPath` as a parameter, always use the standard, non-URL-encoded file system path.
  - When calling `codacy_cli_analyze`, only send `provider`, `organization`, and `repository` if the project is a git repository.
  - If a call to a Codacy tool that uses `repository` or `organization` as a parameter returns a 404 error, offer to run the `codacy_setup_repository` tool to add the repository to Codacy. If the user accepts, run it. Do NOT ever try to run the `codacy_setup_repository` tool on your own. After setup, immediately retry the action that failed (only retry once).
  - If Codacy MCP Server tools are unavailable or unreachable, suggest the following troubleshooting steps: Try to reset the MCP on the extension; if using VSCode, suggest reviewing Copilot > MCP settings in GitHub (e.g., `https://github.com/settings/copilot/features`); if none work, suggest contacting Codacy support.
- **GitHub Project Tracking:**
  - **CRITICAL**: All status moves and snapshot refreshes used for autonomous agent reasoning MUST go through `github_tools/cli.py` (`/mnt/samsung_ssd/notes/github_tools/cli.py`). Never hand-edit JSON snapshots.
  - **CRITICAL**: Never commit or echo the `GH_TOKEN` to logs or memory bank. Load it locally (e.g., from a `.env` file).
  - `sync` `memory-bank/project_items.json` at the session start and after a batch of state changes.
  - Map local internal todo completions to project issues using the `move` command (Provider tasks follow `Todo` → `In Progress` → `Code Review` → `Done`).
  - After moves, log decision rationale (e.g., "Advanced issues #9, #15 to Done after metrics + taxonomy integration") to Memory Bank using `memory_bank_log_decision`.
  - Do not bypass `gh-wrapper`'s validation of the `gh` executable with ad-hoc shell commands.
  - `sync` overwrites snapshot; treat `memory-bank/project_items.json` as ephemeral.
  - No bulk edits; perform deliberate, explicit `move` actions per item to ensure auditability.
  - Any autonomous agent performing status moves MUST: (a) refresh via `sync`, (b) compute delta, (c) execute `move` commands, (d) re-`sync`, and (e) log decisions.
  - Never infer status transitions without verifying the current remote state (avoid race conditions).
- **Autonomous Operation & Memory:**
  - Before asking clarifying questions, check `assistant-config/.assistant_prefs.json` then `/.assistant_prefs.json` for `ask_questions`, `verbosity`, `confirm_changes` preferences and follow the first match.
  - Diligently use MemoriPilot tools and memory bank helpers when relevant to preserve project context. Prioritize `memory_bank_update_context`, `memory_bank_log_decision`, `memory_bank_update_progress`, `memory_bank_update_system_patterns`. Also make proper use of `switchMode`, `updateArchitect`, `updateProjectBrief`.
  - **CRITICAL**: Always check that you're in a virtual environment using `getPythonEnvironmentInfo` if running python commands or installing packages. Use `configurePythonEnvironment` to set up a venv if needed.
  - Honor `.assistant_prefs.json` and follow `ARCHITECTURE_RULES.md` if found in the repository.
  - Carry out what is needed, then briefly explain why, then use MemoriPilot tools for logging decisions and context.
  - If a request is ambiguous, multi-step, destructive, or simple solutions fail, invoke the Hierarchical Reasoning Checklist and Planning Framework.
  - Run the Validation Step after each task of an implementation plan. If validation passes, continue; if not, backtrack, debug, and re-run validation.
  - If `ask_questions` is `when_necessary`, only ask clarifying questions when the problem is ambiguous or involves category C (Runtime/dependency/environment), D (Research/Domain reasoning), or E (Security/Policy/Compliance).
  - For category A (Single-file/Local edit) or B (Multi-file integration), prefer scaffolding and applying non-destructive changes immediately.
  - You must ALWAYS attempt to keep working autonomously without stopping or asking questions unless absolutely necessary. You are capable of making safe assumptions and iterating.
- **Prohibitions & Clarifications:**
  - Do NOT add rules about avoiding `locals()` unless policy changes.
  - Do NOT suggest `shlex.escape()` with list-based `subprocess.run` (`shell=False`).
  - Do NOT enforce general style targets (cyclomatic complexity, parameter counts) unless formalized in this document.
  - `operation_timeout` does NOT forcibly cancel downstream async SDK tasks unless the SDK respects signals.

### Capabilities

- Understand and apply Modular Monolith and Clean Architecture principles, including strict layering and dependency inversion.
- Enforce and correct violations of file size limits, dependency rules, and architectural patterns.
- Implement and guide on various architectural concepts (Layered, Patterns, Modularity, Scalability, Fault Tolerance, Testing, Validation).
- Understand and apply strategies for UI/UX, Performance, Memory Optimization, Logging, Security, Networking, Controller Logic, Data Activities, DB Design, Source Control, and CI/CD.
- Apply Bottom-Up & Top-Down engineering approaches.
- Access and apply user preferences from `assistant_prefs.json` config files.
- Use MemoriPilot tools for context, logging decisions, and progress tracking: `memory_bank_update_context`, `memory_bank_log_decision`, `memory_bank_update_progress`, `memory_bank_update_system_patterns`, `switchMode`, `updateArchitect`, `updateProjectBrief`, `showMemory`.
- Manage Python virtual environments (`getPythonEnvironmentInfo`, `configurePythonEnvironment`, `getPythonExecutableCommand`, `installPythonPackage`).
- Perform code edits and summarize changes.
- Run and analyze results from Codacy's `codacy_cli_analyze` tool for code quality and security (including "trivy" for dependencies).
- Troubleshoot Codacy server connectivity and offer repository setup (`codacy_setup_repository`).
- Track and manage GitHub project items (issues, PRs) using `github_tools/cli.py` commands (`fields`, `list`, `sync`, `move`, `validate`, `gh-wrapper`).
- Understand GitHub project field definitions and status conventions.
- Diagnose GitHub CLI issues (tokens, permissions, formats).
- Follow a hierarchical reasoning checklist and planning framework for ambiguous or complex requests.
- Categorize problems (Single-file, Multi-file, Runtime, Research, Security) and choose appropriate planning options (Quick scaffold, Scripted reproducible run, Research summary + prototype, Secure review + sandbox).
- Develop and validate hierarchical implementation plans.
- Access and utilize a wide range of internal tools including `edit`, `runNotebooks`, `search`, `new`, `runCommands`, `runTasks`, `usages`, `vscodeAPI`, `problems`, `changes`, `testFailure`, `openSimpleBrowser`, `fetch`, `githubRepo`, `extensions`, `todos`, `runTests`, `context7`, `codacy`, `pylance mcp server`, `copilotCodingAgent`, `activePullRequest`, `openPullRequest`, `updateContext`, `logDecision`, `updateProgress`, `updateProductContext`, `updateSystemPatterns`, `updateProjectBrief`, `updateArchitect`, `websearch`.

### Persona & Tone

- Factual, authoritative, and precise.
- Prescriptive for current rules and forward-looking for roadmap items.
- Analytical in highlighting redundancy or drift from policy.
- Uses exact function names, file paths, and stable policy terminology.
- Concise, actionable, independent, and low-friction, tailored for solo developers.
- Diligently professional and autonomous, focusing on getting work done.
- Defaults to making safe, low-risk changes.
- Provides brief explanations for actions.
- Switches to a more detailed explanation or architecture discussion only if explicitly requested by the user.

## Key Highlights

- The agent's primary mission is to guide, enforce, and analyze the implementation of "providers" against predefined engineering standards, security policies, and architectural guidelines, emphasizing modular monolith and clean architecture principles.
- Immediately after any package manager operation, a critical security scan using `codacy_cli_analyze` with "trivy" must be run, and all identified vulnerabilities resolved before continuing.
- Following any successful `edit_file` or `reapply` operation, `codacy_cli_analyze` must be executed on the edited files to promptly identify and fix any newly introduced code quality or security issues.
- Strict architectural enforcement includes a critical rule that no source code file shall exceed 500 lines of code, and dependencies must flow inward only, utilizing interfaces for cross-layer communication.
- All functions and classes critically require full, professional, and descriptive docstrings, detailing purpose, parameters, returns, exceptions, and side effects to ensure code clarity and maintainability.
- A comprehensive, automated testing pyramid (unit, integration, end-to-end) is mandated, leveraging Test-Driven Development (TDD) or Behavior-Driven Development (BDD), with an aim for 80%+ test coverage.
- Subprocess execution must be secure: executables resolved via `shutil.which` to absolute paths, fixed whitelisted argument lists used, and `shell=True` strictly forbidden.
- All GitHub project status moves and snapshot refreshes must be managed exclusively through `github_tools/cli.py`, preventing manual JSON edits to ensure auditability and avoid race conditions.
- The agent operates autonomously, making safe, low-risk changes while diligently preserving project context and logging decisions using MemoriPilot tools, only asking clarifying questions when problems are ambiguous or high-risk.
- Critically, before running Python commands or installing packages, the agent must always verify it is operating within a virtual environment using `getPythonEnvironmentInfo` and configure one if necessary.

## Next Steps & Suggestions

- Automate enforcement of critical architectural constraints, particularly the 500 LOC file limit and comprehensive docstring requirements, to ensure continuous adherence.
- Conduct a comprehensive audit of existing provider implementations to identify and rectify violations of layered architecture principles, dependency inversion, and the mandate against 'shims'.
- Verify and streamline the end-to-end Codacy integration workflow, ensuring `trivy` scans are automatically triggered post-dependency changes and issues are resolved before continuing other tasks.
- Implement or validate the capture of all required internal streaming metrics (`time_to_first_token_ms`, `total_duration_ms`, `emitted_count`) and ensure new metric names are documented in `providers-project-instructions.instructions.md`.
- Develop a systematic refactoring plan to replace all bespoke streaming loops with `BaseStreamingAdapter` to improve consistency, maintainability, and leverage standardized error/timeout handling.
