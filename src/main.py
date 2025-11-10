# src/critique_module/main.py

"""Main entry point for the Reasoning Council Critique Module."""

from typing import Any, Dict, Mapping, Optional, Union
import json
import logging

from .input_reader import read_file_content, enforce_input_only
from .pipeline_input import (
    EmptyPipelineInputError,
    InvalidPipelineInputError,
    PipelineInput,
    ensure_pipeline_input,
)
from .council_orchestrator import run_critique_council
from .output_formatter import format_critique_output


class CritiqueExecutionError(RuntimeError):
    """Raised when the critique pipeline fails unexpectedly."""

# Make synchronous
def critique_goal_document(
    input_data: Union[str, PipelineInput, Mapping[str, Any]],
    config: Optional[Dict[str, Any]] = None,
    peer_review: bool = False,
    scientific_mode: bool = False,
) -> str:
    """Run the critique pipeline using the supplied input.

    Args:
        input_data: Source data for the critique. Strings are interpreted as file
            paths when they exist and otherwise treated as literal text for
            convenience. Mappings must include a ``content`` or ``text`` key.
        config: Configuration dictionary. Optional for convenience during testing.
        peer_review: Enables peer review enhancements when ``True``.
        scientific_mode: Switches the council to scientific methodology agents.

    Returns:
        Formatted critique output as a Markdown string.
    """

    logger = logging.getLogger(__name__)
    resolved_config: Dict[str, Any] = dict(config or {})

    try:
        logger.debug("Normalising pipeline input...")

        # Enforce INPUT-only ingestion when a filesystem path is provided
        if isinstance(input_data, str):
            import os as _os  # local alias to avoid module-level import churn
            if _os.path.exists(input_data) and _os.path.isfile(input_data):
                enforce_input_only(input_data)

        pipeline_input = ensure_pipeline_input(
            input_data,
            read_file=read_file_content,
            assume_path=True,
            fallback_to_content=True,
        )
        logger.debug(
            "Pipeline input ready (source=%s, chars=%d)",
            pipeline_input.source or pipeline_input.metadata.get("source_path", "<direct>"),
            len(pipeline_input.content),
        )

        logger.debug(
            "Running critique council (peer_review=%s, scientific_mode=%s)",
            peer_review,
            scientific_mode,
        )
        critique_data = run_critique_council(
            pipeline_input,
            config=resolved_config,
            peer_review=peer_review,
            scientific_mode=scientific_mode,
        )

        logger.debug("Formatting critique output...")
        formatted_output = format_critique_output(
            critique_data,
            pipeline_input.content,
            resolved_config,
            peer_review=peer_review,
        )
        logger.info("Critique process completed successfully.")
        return formatted_output

    except FileNotFoundError as exc:
        logger.error("Input file error in main: %s", exc, exc_info=True)
        raise
    except IOError as exc:
        logger.error("Input file read error in main: %s", exc, exc_info=True)
        raise
    except EmptyPipelineInputError as exc:
        logger.error("Received empty input for critique: %s", exc, exc_info=True)
        raise ValueError("Critique input contains no content.") from exc
    except InvalidPipelineInputError as exc:
        logger.error("Invalid critique input: %s", exc, exc_info=True)
        raise ValueError(f"Invalid critique input: {exc}") from exc
    except Exception as exc:  # noqa: BLE001 - We intentionally re-wrap unexpected errors.
        logger.error("Unexpected error in critique_goal_document: %s", exc, exc_info=True)
        raise CritiqueExecutionError(
            f"Critique module failed unexpectedly: {exc}"
        ) from exc

# Keep direct execution block, but make it synchronous
if __name__ == '__main__':
    import sys
    import os

    # Setup basic logging for direct execution test
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    src_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if project_root not in sys.path: sys.path.insert(0, project_root)
    if src_root not in sys.path: sys.path.insert(0, src_root)

    try:
        # Imports remain the same, but functions are now sync
        from input_reader import read_file_content as direct_read
        from council_orchestrator import run_critique_council as direct_run_council
        from output_formatter import format_critique_output as direct_format
        from pipeline_input import PipelineInput as DirectPipelineInput
    except ImportError:
        print("ImportError: Could not import components directly. Ensure PYTHONPATH is set or run from project root.")
        sys.exit(1)

    # Synchronous test function
    def direct_critique_test(file_path: str) -> str:
        print(f"Initiating direct critique test for: {file_path}")
        # Use config from file if available, else dummy
        config_path = os.path.join(project_root, 'config.json')
        test_config = {}
        if os.path.exists(config_path):
             try:
                 with open(config_path, 'r') as f:
                      test_config = json.load(f)
                 print("Loaded config from config.json for test.")
             except Exception as cfg_e:
                  print(f"Warning: Could not load config.json: {cfg_e}. Using dummy config.")
                  test_config = {'api': {'gemini': {'retries': 1}}, 'reasoning_tree': {}, 'council_orchestrator': {}}
        else:
             print("Warning: config.json not found. Using dummy config.")
             test_config = {'api': {'gemini': {'retries': 1}}, 'reasoning_tree': {}, 'council_orchestrator': {}}

        # Add dummy resolved_key if needed for direct run (assuming no .env)
        if 'resolved_key' not in test_config.get('api',{}):
             test_config.setdefault('api', {})['resolved_key'] = 'DUMMY_KEY_FOR_TEST'


        try:
            print("Step 1: Reading input (direct)...")
            content = direct_read(file_path)
            print("Input read successfully (direct).")

            print("Step 2: Running critique council (direct)...")
            pipeline_input = DirectPipelineInput(content=content, source=file_path)
            critique_data = direct_run_council(pipeline_input, config=test_config)
            print("Council finished (direct).")

            print("Step 3: Formatting output (direct)...")
            formatted_output = direct_format(critique_data, pipeline_input.content, test_config, peer_review=False)
            print("Output formatted (direct).")

            print("Direct critique test process completed.")
            return formatted_output
        except FileNotFoundError as e:
            print(f"Error (direct): Input file not found at {file_path}")
            raise e
        except IOError as e:
            print(f"Error (direct): Could not read input file at {file_path}")
            raise e
        except Exception as e:
            print(f"An unexpected error occurred during direct critique test: {e}")
            raise CritiqueExecutionError(
                f"Direct critique test failed unexpectedly: {e}"
            ) from e

    # Path relative to the 'critique_council' directory
    test_file_rel = 'content.txt' # Use content.txt as default test
    print(f"--- Running Example Usage (Direct Execution Context) ---")
    test_file_abs = os.path.abspath(os.path.join(project_root, test_file_rel))

    if not os.path.exists(test_file_abs):
         print(f"Error: Test file '{test_file_rel}' (abs: {test_file_abs}) not found in project root.")
         sys.exit(1)

    try:
        # Run the synchronous test function
        final_critique = direct_critique_test(test_file_abs) # No asyncio.run
        print("\n--- Final Critique Output (Direct Execution Context) ---")
        print(final_critique)
    except Exception as e:
        print(f"\n--- Example Usage Failed (Direct Execution Context) ---")
        print(f"Error: {e}")
    print(f"--- End Example Usage (Direct Execution Context) ---")
