# Implementation Gaps Checklist

## Critical Bugs
- [x] Repair `read_file_content` to re-raise `UnicodeDecodeError` using the proper constructor so decoding failures do not produce a secondary `TypeError`. 【F:src/input_reader.py†L1-L40】
- [x] Update `providers.call_with_retry` to respect the assembled `primary_provider` rather than always routing to the OpenAI client, otherwise Anthropic/Gemini configuration never activates. 【F:src/providers/__init__.py†L48-L75】
- [x] Defer YAML loading in `config_loader` or swallow missing-file errors so importing LaTeX helpers does not crash when `config.yaml` is absent in fresh installs. 【F:src/config_loader.py†L20-L140】
- [x] Fix the direct LaTeX generator so character replacements do not double-escape inserted math fragments, allowing the readiness sweep to complete without failing `test_character_replacements`. 【F:src/latex/converters/direct_latex_generator.py†L26-L106】【F:tests/latex/test_direct_latex_generation.py†L120-L133】【8b6876†L1-L71】

## Configuration & Settings
- [x] Teach `ModuleConfigBuilder` to read provider settings stored under `api["providers"]` in addition to top-level keys so YAML-style configuration works consistently. 【F:src/application/critique/configuration.py†L27-L92】
- [x] Normalise preferred provider values before persisting settings so entries like "OpenAI" still match provider keys when resolving the primary provider. 【F:src/application/user_settings/services.py†L26-L146】【F:src/application/critique/configuration.py†L94-L119】
- [x] Remove the baked-in `"o3-mini"` defaults from the configuration templates and model configuration helper so provider selection follows the stored preferences instead of assuming OpenAI’s o3 reasoning model. 【F:config.json†L1-L21】【F:config.yaml†L5-L55】【F:src/providers/model_config.py†L1-L98】【F:src/providers/openai_client.py†L1-L212】

## CLI & Execution Flow
- [x] Allow CLI runs to pass raw text or `PipelineInput` objects; currently `CliApp` always converts to a `Path` and `critique_goal_document` treats strings as file paths, which breaks ad-hoc text critiques. 【F:src/presentation/cli/app.py†L32-L243】【F:src/application/critique/services.py†L9-L82】【F:src/main.py†L1-L88】
- [x] Wrap CLI report and LaTeX writes in error handling so permissions issues do not crash after a successful critique. 【F:src/presentation/cli/app.py†L188-L249】
- [x] Put `--interactive` and `--no-interactive` into an argparse mutually exclusive group to prevent contradictory flags from silently defaulting to non-interactive mode. 【F:run_critique.py†L83-L151】

## Council & Formatting Behaviour
- [x] Make `format_scientific_peer_review` provider-agnostic or fall back gracefully when OpenAI credentials are unavailable; it currently forces `primary_provider="openai"` and expects OpenAI-specific config. 【F:src/scientific_review_formatter.py†L1-L260】
- [x] Replace the hard-coded "Philosopher" label in synthesized points with logic that reflects the active agent cohort, especially during scientific mode runs. 【F:src/council_orchestrator.py†L336-L397】【F:tests/test_council_orchestrator.py†L95-L180】
- [x] Swap the orchestrator's extensive `print` statements for structured logging so executions respect the CLI log configuration. 【F:src/council_orchestrator.py†L170-L390】
- [x] Replace the placeholder `ReasoningAgent.self_critique` behaviour with real adjustment logic so council arbitration no longer relies on a stubbed confidence delta. 【F:src/reasoning_agent.py†L151-L169】【F:src/reasoning_agent_self_critique.py†L1-L220】【F:tests/test_reasoning_agent.py†L121-L220】

## Architecture & Code Quality
- [x] Split `src/council_orchestrator.py` into smaller collaborators so each module stays below the 500 line limit defined in the architecture guide. 【F:src/council_orchestrator.py†L1-L40】【F:src/council/logging.py†L1-L44】【F:src/council/adjustments.py†L1-L81】【F:src/council/synthesis.py†L1-L130】
- [x] Break `src/syncretic_catalyst/orchestrator.py` into domain-appropriate services instead of a 600 line script that crosses presentation, application, and infrastructure boundaries. 【F:src/syncretic_catalyst/orchestrator.py†L1-L8】【F:src/syncretic_catalyst/presentation/cli.py†L1-L53】【F:src/syncretic_catalyst/application/workflow.py†L1-L200】【F:src/syncretic_catalyst/infrastructure/file_repository.py†L1-L136】【F:src/syncretic_catalyst/domain/models.py†L1-L24】
- [x] Decompose `src/syncretic_catalyst/thesis_builder.py` into layered collaborators; the current 650+ line script patches `sys.path`, configures logging, owns provider wiring, and embeds the CLI entrypoint in the same module. 【F:src/syncretic_catalyst/thesis_builder.py†L1-L125】【F:src/syncretic_catalyst/application/thesis/services.py†L1-L226】【F:src/syncretic_catalyst/infrastructure/thesis/output_repository.py†L1-L74】
- [x] Port `src/syncretic_catalyst/research_enhancer.py` into the modular architecture so imports, AI prompts, and CLI handling no longer live in a 500 line monolith with manual `sys.path` shims and inline fallbacks. 【F:src/syncretic_catalyst/application/research_enhancement/services.py†L1-L219】【F:src/syncretic_catalyst/infrastructure/research_enhancement/repository.py†L1-L91】【F:src/syncretic_catalyst/research_enhancer.py†L1-L119】
- [x] Fold `src/syncretic_catalyst/research_generator.py` into the new services to eliminate inline environment loading, key masking, and manual persistence sprinkled through the CLI routine. 【F:src/syncretic_catalyst/application/research_generation/services.py†L1-L128】【F:src/syncretic_catalyst/infrastructure/research_generation/repository.py†L1-L83】【F:src/syncretic_catalyst/research_generator.py†L1-L78】
- [ ] Move `src/syncretic_catalyst/assemble_research.py` into a testable service layer; it currently performs file discovery, mutation, and CLI execution directly in the script. 【F:src/syncretic_catalyst/assemble_research.py†L1-L109】

## Testing & Tooling
- [x] Flesh out the placeholder test modules that currently contain only `# TODO` stubs so provider, content, and integration behaviours are validated. 【F:tests/content/test_point_extraction.py†L1-L109】【F:tests/providers/test_openai_client.py†L1-L133】【F:tests/providers/test_o3_mini_integration.py†L1-L80】【F:tests/integration/test_critique_pipeline.py†L1-L86】
- [x] Expand the readiness suite to execute the full pytest collection (once the placeholders are ready) instead of a curated subset to catch regressions earlier. 【F:tests/test_readiness_suite.py†L13-L45】
- [x] Remove `generate_test_structure.py` so contributors are not tempted to regenerate placeholder-heavy test scaffolds. 【F:IMPLEMENTATION_GAPS.md†L23-L41】
- [x] Convert the LaTeX integration smoke tests into pytest-style assertions (with skips when fixtures are missing) so they no longer return booleans and trigger warnings during the readiness sweep. 【F:test_latex_peer_review.py†L1-L76】【F:test_latex_simplified.py†L1-L86】
