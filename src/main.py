# src/critique_module/main.py

"""
Main entry point for the Reasoning Council Critique Module.
"""
from typing import Dict, Any
import logging # Import logging

# Component Imports
from .input_reader import read_file_content
# import asyncio # No longer needed
from .council_orchestrator import run_critique_council # Now synchronous
from .output_formatter import format_critique_output

# Make synchronous
def critique_goal_document(
    file_path: str, 
    config: Dict[str, Any], 
    peer_review: bool = False,
    scientific_mode: bool = False
) -> str:
    """
    Reads content, runs critique sequentially, returns formatted assessment.
    
    Args:
        file_path: Path to the content file to analyze
        config: Configuration dictionary
        peer_review: Whether to enable peer review mode with SME personas
        scientific_mode: Whether to use scientific methodology agents instead of philosophers
        
    Returns:
        Formatted critique output as a string
    """
    logger = logging.getLogger(__name__) # Get logger

    try:
        logger.debug("Step 1: Reading input...")
        content = read_file_content(file_path)
        logger.debug("Input read successfully.")

        logger.debug(f"Step 2: Running critique council... (Peer Review: {peer_review}, Scientific Mode: {scientific_mode})")
        # Call synchronous council function with all parameters
        critique_data = run_critique_council(
            content, 
            config, 
            peer_review=peer_review,
            scientific_mode=scientific_mode
        )
        logger.debug("Council finished.")

        logger.debug(f"Step 3: Formatting output... (Peer Review: {peer_review})")
        # Pass original content, config, and peer_review flag needed for Judge summary
        formatted_output = format_critique_output(critique_data, content, config, peer_review=peer_review)
        logger.debug("Output formatted.")

        logger.info("Critique process completed successfully.")
        return formatted_output

    except FileNotFoundError as e:
        logger.error(f"Input file error in main: {e}", exc_info=True)
        raise e # Re-raise specific exception
    except IOError as e:
        logger.error(f"Input file read error in main: {e}", exc_info=True)
        raise e # Re-raise specific exception
    except Exception as e:
        logger.error(f"Unexpected error in critique_goal_document: {e}", exc_info=True)
        # Re-raise a generic exception for the runner script to catch
        raise Exception(f"Critique module failed unexpectedly in main: {e}") from e

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
    except ImportError:
        print("ImportError: Could not import components directly. Ensure PYTHONPATH is set or run from project root.")
        sys.exit(1)

    # Synchronous test function
    def direct_critique_test(file_path: str) -> str:
        print(f"Initiating direct critique test for: {file_path}")
        # Load unified YAML configuration
        try:
            # Import config_loader after adjusting sys.path above
            from src.config_loader import config_loader as direct_config_loader
            test_config = direct_config_loader.config
            print("Loaded config from config.yaml for test.")
        except Exception as cfg_e:
            print(f"Warning: Could not load config.yaml: {cfg_e}. Using minimal fallback config.")
            test_config = {'api': {'gemini': {'retries': 1}}, 'reasoning_tree': {}, 'council_orchestrator': {}}

        # Add dummy resolved_key if needed for direct run (assuming no .env)
        if 'resolved_key' not in test_config.get('api',{}):
             test_config.setdefault('api', {})['resolved_key'] = 'DUMMY_KEY_FOR_TEST'


        try:
            print("Step 1: Reading input (direct)...")
            content = direct_read(file_path)
            print("Input read successfully (direct).")

            print("Step 2: Running critique council (direct)...")
            # Call sync function
            critique_data = direct_run_council(content, test_config) # No await
            print("Council finished (direct).")

            print("Step 3: Formatting output (direct)...")
            formatted_output = direct_format(critique_data)
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
            raise Exception(f"Direct critique test failed unexpectedly: {e}") from e

    # Default input now lives under INPUT/
    test_file_rel = os.path.join('INPUT', 'content.txt')  # Use INPUT/content.txt as default test
    print(f"--- Running Example Usage (Direct Execution Context) ---")
    test_file_abs = os.path.abspath(os.path.join(project_root, test_file_rel))

    if not os.path.exists(test_file_abs):
         print(f"Error: Default input '{test_file_rel}' not found (abs: {test_file_abs}). Place files in the INPUT/ folder.")
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
