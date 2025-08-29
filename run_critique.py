# run_critique.py
# import asyncio # No longer needed
import os
import logging
import datetime
import argparse # Added argparse
from dotenv import load_dotenv
from src.config_loader import config_loader
from src.input_reader import (
    find_default_input_file,
    find_all_input_files,
    read_file_content,
    concatenate_inputs,
    materialize_concatenation_to_temp,
    TEXT_EXTS, PDF_EXTS, IMAGE_EXTS, AUDIO_EXTS
)
from src import critique_goal_document  # Now synchronous
from src.scientific_review_formatter import format_scientific_peer_review
from src.latex.cli import add_latex_arguments, handle_latex_output


# --- Configure Logging ---
def setup_logging():
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    system_log_file = os.path.join(log_dir, "system.log")
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
                        filename=system_log_file,
                        filemode='w',
                        encoding='utf-8')
    logging.info("Root logging configured. System logs in logs/system.log")
# -------------------------

# Make main synchronous
def main():
    # --- Argument Parsing ---
    parser = argparse.ArgumentParser(description="Run the Critique Council on a given input file.")
    parser.add_argument(
        "input_file",
        nargs="?",
        default=None,
        help="Path to the input file or directory. If omitted, ingests all files in INPUT/ by default."
    )
    parser.add_argument("--PR", "--peer-review", action="store_true",
                        help="Enable Peer Review mode, enhancing personas with SME perspective.")
    parser.add_argument("--scientific", action="store_true",
                        help="Use scientific methodology agents instead of philosophical agents.")

    # Ingestion/backends runtime overrides
    parser.add_argument("--ingest-batch", action="store_true",
                        help="Concatenate all files in the INPUT/ directory (or provided directory) into one input.")
    parser.add_argument("--pdf-backend", choices=["auto", "pymupdf", "pdfminer", "pypdf2"], default=None,
                        help="Override PDF extraction backend at runtime.")
    parser.add_argument("--ocr-enable", dest="ocr_enable", action="store_true",
                        help="Enable OCR for images regardless of config.")
    parser.add_argument("--no-ocr", dest="ocr_enable", action="store_false",
                        help="Disable OCR for images regardless of config.")
    parser.set_defaults(ocr_enable=None)
    parser.add_argument("--ocr-lang", default=None,
                        help="Tesseract language codes (e.g., 'eng', or 'eng+spa').")
    parser.add_argument("--tesseract-cmd", default=None,
                        help="Path to the tesseract binary if not on PATH.")
    parser.add_argument("--audio-enable", dest="audio_enable", action="store_true",
                        help="Enable audio transcription regardless of config.")
    parser.add_argument("--no-audio", dest="audio_enable", action="store_false",
                        help="Disable audio transcription regardless of config.")
    parser.set_defaults(audio_enable=None)
    parser.add_argument("--whisper-backend", choices=["whisper_local", "whisper_openai"], default=None,
                        help="Override audio transcription backend at runtime.")
    parser.add_argument("--whisper-model", default=None,
                        help="Override local Whisper model size (e.g., 'base', 'small', 'medium').")
    parser.add_argument("--log-ingestion-choices", action="store_true",
                        help="Log which ingestion backend is used per file (for batch mode).")

    # Add LaTeX-related arguments
    parser = add_latex_arguments(parser)
    args = parser.parse_args()
    # -------------------------

    setup_logging()
    root_logger = logging.getLogger(__name__)

    # --- Load Configuration (YAML via config_loader) ---
    app_config = config_loader.config

    load_dotenv()
    root_logger.info("Environment variables loaded from .env (if found).")
    # -------------------------

    # --- Resolve input path (file or directory, with defaults) ---
    passed_path = args.input_file
    if not passed_path:
        # Default to ingest all files in INPUT/ (or configured ingestion.input_dir)
        try:
            default_input_dir = config_loader.get_section('ingestion').get('input_dir', 'INPUT')  # type: ignore
        except Exception:
            default_input_dir = 'INPUT'
        args.input_file = default_input_dir
        passed_path = args.input_file
        root_logger.info(f"No input specified. Defaulting to directory ingestion of: {passed_path}")
    # If a directory was provided, auto-pick the best candidate inside it (used for single-file ingestion path/logging)
    if os.path.isdir(passed_path):
        abs_dir = os.path.abspath(passed_path)
        base = os.path.dirname(abs_dir)
        name = os.path.basename(abs_dir)
        candidate = find_default_input_file(base_dir=base, input_dir_name=name)
        if candidate:
            resolved_path = candidate
            root_logger.info(f"Directory provided. Auto-selected input: {resolved_path}")
        else:
            root_logger.error(f"Directory provided but no suitable input files found in: {abs_dir}")
            print(f"Error: No suitable input files found in directory: {abs_dir}")
            return
    else:
        resolved_path = passed_path

    # --- Prepare Module Config ---
    # Structure the configuration to include all available providers
    module_config = {
        'api': {
            'providers': {},  # Provider configuration container
            'primary_provider': app_config.get('api', {}).get('primary_provider', 'gemini'),
        },
        'reasoning_tree': app_config.get('reasoning_tree', {}),
        'council_orchestrator': app_config.get('council_orchestrator', {})
    }
    
    # Add Gemini configuration if available
    if 'gemini' in app_config.get('api', {}):
        module_config['api']['providers']['gemini'] = {
            **app_config.get('api', {}).get('gemini', {}),
            'resolved_key': os.getenv('GEMINI_API_KEY'),
        }
        # Also add at top level for backward compatibility with older provider modules
        module_config['api']['gemini'] = module_config['api']['providers']['gemini']
        
    # Add DeepSeek configuration if available
    if 'deepseek' in app_config.get('api', {}) or os.getenv('DEEPSEEK_API_KEY'):
        module_config['api']['providers']['deepseek'] = {
            **app_config.get('api', {}).get('deepseek', {}),
            'api_key': os.getenv('DEEPSEEK_API_KEY'),
        }
        # Also add at top level for backward compatibility with older provider modules
        module_config['api']['deepseek'] = module_config['api']['providers']['deepseek']
        
    # Add OpenAI configuration if available
    if 'openai' in app_config.get('api', {}) or os.getenv('OPENAI_API_KEY'):
        module_config['api']['providers']['openai'] = {
            **app_config.get('api', {}).get('openai', {}),
            'resolved_key': os.getenv('OPENAI_API_KEY'),
        }
        # Also add at top level for backward compatibility with older provider modules
        module_config['api']['openai'] = module_config['api']['providers']['openai']
    
    # Add OpenRouter configuration if available
    if 'openrouter' in app_config.get('api', {}) or os.getenv('OPENROUTER_API_KEY'):
        module_config['api']['providers']['openrouter'] = {
            **app_config.get('api', {}).get('openrouter', {}),
            'api_key': os.getenv('OPENROUTER_API_KEY'),
        }
        # Also add at top level for backward compatibility with older provider modules
        module_config['api']['openrouter'] = module_config['api']['providers']['openrouter']
    # For backward compatibility with older components
    primary_provider = module_config['api']['primary_provider']
    if primary_provider in module_config['api']['providers'] and 'resolved_key' in module_config['api']['providers'][primary_provider]:
        module_config['api']['resolved_key'] = module_config['api']['providers'][primary_provider]['resolved_key']
    
    root_logger.info("Module configuration prepared.")
    # -------------------------

    # --- Validate Primary Provider API Key ---
    primary_provider = module_config['api']['primary_provider']
    # Some providers do not require API keys (e.g., local Ollama)
    providers_without_keys = {'ollama'}
    if primary_provider not in providers_without_keys:
        # Check both locations (providers nested and direct)
        api_key_missing = (
            (primary_provider not in module_config['api']['providers'] or
             not module_config['api']['providers'][primary_provider].get('resolved_key', module_config['api']['providers'][primary_provider].get('api_key')))
            and
            (primary_provider not in module_config['api'] or
             not module_config['api'][primary_provider].get('resolved_key', module_config['api'][primary_provider].get('api_key')))
        )
        
        if api_key_missing:
            error_msg = f"Primary provider '{primary_provider}' API key not found in .env file or environment. Cannot proceed."
            print(f"Error: {error_msg}")
            root_logger.error(error_msg)
            return
    else:
        root_logger.info(f"Primary provider '{primary_provider}' does not require API keys; skipping key validation.")
    # -------------------------

    # --- Build ingestion override config from CLI ---
    ingestion_override = {}

    # PDF backend override
    if args.pdf_backend is not None:
        ingestion_override.setdefault("pdf", {})["backend"] = args.pdf_backend

    # OCR overrides
    if args.ocr_enable is not None:
        ingestion_override.setdefault("ocr", {})["enabled"] = bool(args.ocr_enable)
    if args.ocr_lang is not None:
        ingestion_override.setdefault("ocr", {})["languages"] = args.ocr_lang
    if args.tesseract_cmd is not None:
        ingestion_override.setdefault("ocr", {})["tesseract_cmd"] = args.tesseract_cmd

    # Audio overrides
    if args.audio_enable is not None:
        ingestion_override.setdefault("audio", {})["enabled"] = bool(args.audio_enable)
    if args.whisper_backend is not None:
        ingestion_override.setdefault("audio", {})["backend"] = args.whisper_backend
    if args.whisper_model is not None:
        ingestion_override.setdefault("audio", {})["whisper_model"] = args.whisper_model

    # Determine whether to run batch mode
    use_batch = bool(args.ingest_batch or (os.path.isdir(args.input_file)))

    # Compute base/input directory context for discovery
    # If a directory was passed, use that; otherwise default to INPUT/
    if os.path.isdir(args.input_file):
        abs_dir = os.path.abspath(args.input_file)
        base_dir = os.path.dirname(abs_dir)
        input_dir_name = os.path.basename(abs_dir)
    else:
        base_dir = os.getcwd()
        input_dir_name = "INPUT"

    # Resolve final input content
    if use_batch:
        files = find_all_input_files(base_dir=base_dir, input_dir_name=input_dir_name)
        if not files:
            err = f"No input files found in {os.path.join(base_dir, input_dir_name)} for batch ingestion."
            print(f"Error: {err}")
            root_logger.error(err)
            return

        if args.log_ingestion_choices:
            for p in files:
                ext = os.path.splitext(p)[1].lower()
                if ext in PDF_EXTS:
                    backend = (ingestion_override.get("pdf", {}) or {}).get("backend", "auto")
                    root_logger.info(f"[INGEST] {p} -> PDF backend: {backend}")
                elif ext in IMAGE_EXTS:
                    ocr_cfg = ingestion_override.get("ocr", {}) or {}
                    root_logger.info(f"[INGEST] {p} -> OCR enabled={ocr_cfg.get('enabled', 'config')}, lang={ocr_cfg.get('languages', 'config')}")
                elif ext in AUDIO_EXTS:
                    audio_cfg = ingestion_override.get("audio", {}) or {}
                    root_logger.info(f"[INGEST] {p} -> Audio backend={audio_cfg.get('backend', 'config')}, model={audio_cfg.get('whisper_model', 'config')}")
                elif ext in TEXT_EXTS:
                    root_logger.info(f"[INGEST] {p} -> Text (UTF-8)")
                else:
                    root_logger.info(f"[INGEST] {p} -> Treated as text fallback")

        concatenated = concatenate_inputs(files, ingestion_override)
        temp_input = materialize_concatenation_to_temp(concatenated, suffix=".txt")
        input_file = temp_input
        input_basename = f"{input_dir_name}_batch"
        root_logger.info(f"Batch ingestion created temp file: {temp_input}")
    else:
        # Resolve a single best file if user passed directory-like default or default path
        if os.path.isdir(args.input_file):
            candidate = find_default_input_file(base_dir=base_dir, input_dir_name=input_dir_name)
            if not candidate:
                err = f"No suitable input found in directory {os.path.join(base_dir, input_dir_name)}"
                print(f"Error: {err}")
                root_logger.error(err)
                return
            resolved_path = candidate
            root_logger.info(f"Directory provided. Auto-selected input: {resolved_path}")
        else:
            # args.input_file can be non-existent default; fallback to INPUT/content.txt
            resolved_path = args.input_file
            if not os.path.exists(resolved_path):
                default_fallback = os.path.join("INPUT", "content.txt")
                if os.path.exists(default_fallback):
                    resolved_path = default_fallback
                    root_logger.info(f"No such path provided. Falling back to default: {resolved_path}")
                else:
                    err = f"Input path does not exist and no default present: {args.input_file}"
                    print(f"Error: {err}")
                    root_logger.error(err)
                    return

        # Read single file via ingestion to honor backend overrides, then materialize
        try:
            content = read_file_content(resolved_path, ingestion_override)
        except Exception as e:
            err = f"Failed to ingest '{resolved_path}': {e}"
            print(f"Error: {err}")
            root_logger.error(err, exc_info=True)
            return

        temp_input = materialize_concatenation_to_temp(content, suffix=".txt")
        input_file = temp_input
        input_basename = os.path.splitext(os.path.basename(resolved_path))[0]
        root_logger.info(f"Single-file ingestion created temp file: {temp_input}")

    peer_review_mode = args.PR  # or args.peer_review
    scientific_mode = args.scientific

    root_logger.info(f"Initiating critique for: {input_file} (Peer Review Mode: {peer_review_mode}, Scientific Mode: {scientific_mode})")
    try:
        # Pass peer_review_mode and scientific_mode to the critique function
        final_critique_report = critique_goal_document(
            input_file, 
            module_config, 
            peer_review=peer_review_mode,
            scientific_mode=scientific_mode
        )

        # Save standard critique report
        output_dir = "critiques"
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        input_basename = os.path.splitext(os.path.basename(input_file))[0]
        output_filename = os.path.join(output_dir, f"{input_basename}_critique_{timestamp}.md")

        with open(output_filename, 'w', encoding='utf-8') as f:
            f.write(final_critique_report)
            
        success_msg = f"Critique report successfully saved to {output_filename}"
        root_logger.info(success_msg)
        print(f"\n{success_msg}")
        
        # If peer review mode is active, generate formal scientific peer review
        if peer_review_mode:
            root_logger.info(f"Peer Review mode active - Generating scientific peer review format... (Scientific Mode: {scientific_mode})")
            try:
                # Read the original content
                with open(input_file, 'r', encoding='utf-8') as f:
                    original_content = f.read()
                
                # Generate the scientific peer review
                scientific_review = format_scientific_peer_review(
                    original_content=original_content,
                    critique_report=final_critique_report,
                    config=module_config,
                    scientific_mode=scientific_mode
                )
                
                # Save the scientific peer review to a separate file
                pr_output_filename = os.path.join(output_dir, f"{input_basename}_peer_review_{timestamp}.md")
                with open(pr_output_filename, 'w', encoding='utf-8') as f:
                    f.write(scientific_review)
                
                pr_success_msg = f"Scientific Peer Review successfully saved to {pr_output_filename}"
                root_logger.info(pr_success_msg)
                print(f"\n{pr_success_msg}")
                
                # Generate LaTeX document if requested
                if args.latex:
                    try:
                        # Read the original content again to be safe
                        with open(input_file, 'r', encoding='utf-8') as f:
                            original_content = f.read()
                            
                        # Generate the LaTeX document
                        latex_success, tex_path, pdf_path = handle_latex_output(
                            args, 
                            original_content,
                            final_critique_report,
                            scientific_review,
                            scientific_mode  # Pass the scientific mode flag
                        )
                        
                        if latex_success:
                            if tex_path:
                                latex_success_msg = f"LaTeX document successfully saved to {tex_path}"
                                root_logger.info(latex_success_msg)
                                print(f"\n{latex_success_msg}")
                            if pdf_path:
                                pdf_success_msg = f"PDF document successfully saved to {pdf_path}"
                                root_logger.info(pdf_success_msg)
                                print(f"\n{pdf_success_msg}")
                        else:
                            latex_error_msg = "Failed to generate LaTeX document"
                            root_logger.error(latex_error_msg)
                            print(f"\nWarning: {latex_error_msg}")
                    except Exception as e:
                        latex_error_msg = f"Error generating LaTeX document: {e}"
                        root_logger.error(latex_error_msg, exc_info=True)
                        print(f"\nWarning: {latex_error_msg}")
                
            except Exception as e:
                pr_error_msg = f"Error generating scientific peer review: {e}"
                root_logger.error(pr_error_msg, exc_info=True)
                print(f"\nWarning: {pr_error_msg}")
                
        # If LaTeX is requested but peer review is not, generate LaTeX with just the critique
        elif args.latex:
            try:
                # Read the original content
                with open(input_file, 'r', encoding='utf-8') as f:
                    original_content = f.read()
                    
                # Generate the LaTeX document without peer review
                latex_success, tex_path, pdf_path = handle_latex_output(
                    args, 
                    original_content,
                    final_critique_report,
                    scientific_mode=scientific_mode  # Pass the scientific mode flag
                )
                
                if latex_success:
                    if tex_path:
                        latex_success_msg = f"LaTeX document successfully saved to {tex_path}"
                        root_logger.info(latex_success_msg)
                        print(f"\n{latex_success_msg}")
                    if pdf_path:
                        pdf_success_msg = f"PDF document successfully saved to {pdf_path}"
                        root_logger.info(pdf_success_msg)
                        print(f"\n{pdf_success_msg}")
                else:
                    latex_error_msg = "Failed to generate LaTeX document"
                    root_logger.error(latex_error_msg)
                    print(f"\nWarning: {latex_error_msg}")
            except Exception as e:
                latex_error_msg = f"Error generating LaTeX document: {e}"
                root_logger.error(latex_error_msg, exc_info=True)
                print(f"\nWarning: {latex_error_msg}")

    except FileNotFoundError as e:
        error_msg = f"Input file not found at {input_file}"
        print(f"Error: {error_msg}")
        root_logger.error(error_msg, exc_info=True)
    except Exception as e:
        error_msg = f"An unexpected error occurred during critique: {e}"
        print(f"Error: {error_msg}")
        root_logger.error(error_msg, exc_info=True)

if __name__ == "__main__":
    main() # Call main directly
