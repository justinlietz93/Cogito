# Cogito Quickstart Guide

Purpose
- Minimal, practical steps to install, configure, and run Cogito.
- Covers Critique Council pipeline, LaTeX output, and Syncretic Catalyst research workflows.
- Does not modify the main README; this is a standalone quickstart.

Checklist (recommended path)
- [ ] Install system and Python dependencies
- [ ] Configure provider API keys in .env
- [ ] Place input files into INPUT/
- [ ] Run a critique (optional: scientific/peer-review/LaTeX)
- [ ] Explore Syncretic Catalyst (thesis builder / research enhancer)
- [ ] Verify outputs and logs

Contents
- Prerequisites
- Installation
- Configuration (API keys, providers)
- Input ingestion behavior (files in INPUT/)
- Run the Critique Council
- LaTeX options
- Syncretic Catalyst quickstart
- ArXiv vector search (notes)
- Outputs and directories
- Troubleshooting

Prerequisites
- Python 3.8+ (recommended: 3.10+)
- Pip packages: pip install -r requirements.txt
- Optional system tools by feature:
  - OCR for images: Tesseract OCR (Linux: sudo apt-get install tesseract-ocr; macOS: brew install tesseract)
  - Audio transcription: FFmpeg (Linux: sudo apt-get install ffmpeg; macOS: brew install ffmpeg)
  - LaTeX PDF compilation: A LaTeX distribution (e.g., TeX Live, MiKTeX)
- Optional Python extras by feature (if not already present):
  - PDF backends: PyMuPDF, pdfminer.six, PyPDF2
  - OCR: pillow, pytesseract
  - Audio: openai-whisper (local)

Installation
- Clone and install Python dependencies:
  - git clone & cd into repository
  - pip install -r requirements.txt
- The unified YAML config is loaded by [ConfigLoader.__init__()](Cogito/src/config_loader.py:20). Default path is project-root/config.yaml.

Configuration (API keys, providers)
- Primary provider is selected in [config.yaml](Cogito/config.yaml) under api.primary_provider. Default observed: "openrouter".
- Runtime resolution of provider credentials is performed in [run_critique.py](Cogito/run_critique.py:120) by merging config with environment variables (via dotenv).
- Environment variables recognized (set in your .env):
  - OPENROUTER_API_KEY (OpenRouter)
  - OPENAI_API_KEY (OpenAI; also used by some ArXiv vector features)
  - GEMINI_API_KEY (Gemini)
  - ANTHROPIC_API_KEY (Anthropic)
  - DEEPSEEK_API_KEY (DeepSeek)
  - XAI_API_KEY (X.ai/Groq)
- Provider config accessors for reference:
  - [get_primary_provider()](Cogito/src/providers/model_config.py:18)
  - [get_openrouter_config()](Cogito/src/providers/model_config.py:111)
  - [get_openai_config()](Cogito/src/providers/model_config.py:69)
  - [get_gemini_config()](Cogito/src/providers/model_config.py:90)
  - [get_deepseek_config()](Cogito/src/providers/model_config.py:50)
  - [get_xai_config()](Cogito/src/providers/model_config.py:141)
- Clients (examples):
  - [run_openrouter_client()](Cogito/src/providers/openrouter_client.py:27)
  - [run_xai_client()](Cogito/src/providers/xai_client.py:13)

Input ingestion behavior
- Default location: put your files in [Cogito/INPUT/](Cogito/INPUT/).
- If you run the CLI without an input path, it now defaults to ingesting all files in INPUT/ (directory ingestion). See CLI parsing at [run_critique.py](Cogito/run_critique.py:38) and default handling/path resolution at [run_critique.py](Cogito/run_critique.py:91).
- Supported file types (auto-detected):
  - Text: .txt, .md, .markdown, .json, .yaml, .yml
  - PDF: via backends (PyMuPDF, pdfminer.six, PyPDF2)
  - Images: OCR via pytesseract (if enabled)
  - Audio: Whisper (local or OpenAI)
  - XML: treated as text by fallback
- Core ingestion functions:
  - [read_file_content()](Cogito/src/input_reader.py:186)
  - [find_all_input_files()](Cogito/src/input_reader.py:272)
  - [concatenate_inputs()](Cogito/src/input_reader.py:288)
  - [materialize_concatenation_to_temp()](Cogito/src/input_reader.py:304)
- CLI ingestion overrides (flags):
  - --ingest-batch: Force concatenation of all files in a directory with file headers
  - --pdf-backend {auto,pymupdf,pdfminer,pypdf2}
  - --ocr-enable / --no-ocr, --ocr-lang, --tesseract-cmd
  - --audio-enable / --no-audio, --whisper-backend {whisper_local,whisper_openai}, --whisper-model
  - --log-ingestion-choices: Log which backend was used per file (see [run_critique.py](Cogito/run_critique.py:237))

Run the Critique Council
- Basic usage (directory ingestion default):
  - python run_critique.py
- Explicit directory or single file:
  - python run_critique.py INPUT/
  - python run_critique.py INPUT/content.txt
- Scientific mode and peer review:
  - python run_critique.py --scientific
  - python run_critique.py --scientific --PR
- Batch ingestion and backends:
  - python run_critique.py INPUT/ --ingest-batch --pdf-backend auto --ocr-enable --audio-enable --log-ingestion-choices
- Behavior overview:
  - CLI defined in [run_critique.py](Cogito/run_critique.py:38)
  - In single-file mode, the ingested content is materialized to a temp file for processing [run_critique.py](Cogito/run_critique.py:284)
  - Output markdown saved under critiques/ with timestamp [run_critique.py](Cogito/run_critique.py:318)
  - Peer review generation (optional) follows critique generation [run_critique.py](Cogito/run_critique.py:326)

LaTeX options
- Enable LaTeX output:
  - Add --latex to generate a .tex document. Add --latex-compile to try compiling to PDF.
  - Example: python run_critique.py --scientific --PR --latex --latex-compile
- CLI options injected by [add_latex_arguments()](Cogito/src/latex/cli.py:28), processed by [handle_latex_output()](Cogito/src/latex/cli.py:78).
- Configuration merges config.yaml latex section with CLI overrides.
  - Output directory default: latex_output (configurable via --latex-output-dir)
  - Scientific objectivity level: --latex-scientific-level {low,medium,high}
  - Direct LaTeX mode (faster, limited markdown support): --direct-latex
- If LaTeX engine is installed, PDFs are placed in latex_output/ (see console/logs for exact paths).

Syncretic Catalyst quickstart
- Thesis Builder (multi-agent research synthesis):
  - Single concept: python Cogito/src/syncretic_catalyst/thesis_builder.py "Your concept here"
  - From file (concepts separated by ---): python Cogito/src/syncretic_catalyst/thesis_builder.py --file INPUT/concepts.txt
  - Optional model override: --model {claude,deepseek,xai,openrouter}
  - Entry points:
    - [build_thesis()](Cogito/src/syncretic_catalyst/thesis_builder.py:548)
    - [ThesisBuilder.research_concept()](Cogito/src/syncretic_catalyst/thesis_builder.py:323)
- Research Enhancer (augment existing documents with vector search and citations):
  - Prepare documents under src/syncretic_catalyst/workspaces/some_project/doc/
  - Run: python Cogito/src/syncretic_catalyst/research_enhancer.py --model claude
  - Entry point: [enhance_research()](Cogito/src/syncretic_catalyst/research_enhancer.py:340)
- Outputs:
  - Syncretic outputs in Cogito/syncretic_output/ and/or output_results/syncretic_catalyst/some_project/
  - Files include: relevant_papers.json/.md, research_gaps_analysis.md, enhanced_research_proposal.md, thesis_*.md, research_report_*.md

ArXiv vector search (notes)
- The vector-augmented reference service is [ArxivVectorReferenceService.__init__()](Cogito/src/arxiv/arxiv_vector_reference_service.py:27) which wraps a smart vector store.
- Some vector features may use OpenAI embeddings if configured (OPENAI_API_KEY). Not strictly required for basic usage.
- Caches and vector store paths are under Cogito/storage/ (e.g., arxiv_cache, arxiv_vector_cache).

Outputs and directories (by default)
- INPUT/: Place your input sources here (ingestion scans this directory by default)
- critiques/: Markdown output of critique runs with timestamps [run_critique.py](Cogito/run_critique.py:318)
- latex_output/: LaTeX and optional PDFs if enabled via CLI
- logs/system.log: Run-time logs; enable --log-ingestion-choices to see per-file ingest backends
- storage/: ArXiv caches and vector caches
- syncretic_output/, output_results/: Syncretic Catalyst outputs

Troubleshooting
- No input found:
  - Ensure at least one file exists in INPUT/. Directory ingestion is used when no path is provided. For explicit file: python run_critique.py INPUT/content.txt
- Provider API key missing:
  - Error emitted if primary provider key is absent [run_critique.py](Cogito/run_critique.py:183). Set the appropriate KEY in .env (see Configuration).
- PDF/OCR/Audio not working:
  - Install respective backends (PyMuPDF/pdfminer/PyPDF2; pillow+pytesseract; ffmpeg+openai-whisper) and enable via CLI or config.
- LaTeX PDF not produced:
  - Confirm LaTeX installation, and use --latex-compile. See latex logs and latex_output/ for .tex and PDF.
- Inspect ingestion choices:
  - Use --log-ingestion-choices to trace which backend processed each file [run_critique.py](Cogito/run_critique.py:237).

Examples
- Ingest everything in INPUT/ and run scientific critique:
  - python run_critique.py --scientific
- Peer review + LaTeX (compile to PDF if LaTeX is installed):
  - python run_critique.py --scientific --PR --latex --latex-compile
- Batch ingest from a directory with backends enabled:
  - python run_critique.py INPUT/ --ingest-batch --pdf-backend auto --ocr-enable --audio-enable --log-ingestion-choices
- Thesis builder for a concept:
  - python Cogito/src/syncretic_catalyst/thesis_builder.py "Quantum computation for climate modeling"

References (selected implementation links)
- CLI and pipeline orchestration: [run_critique.py](Cogito/run_critique.py:38)
- Ingestion utilities: [read_file_content()](Cogito/src/input_reader.py:186), [find_all_input_files()](Cogito/src/input_reader.py:272), [concatenate_inputs()](Cogito/src/input_reader.py:288)
- LaTeX CLI integration: [add_latex_arguments()](Cogito/src/latex/cli.py:28), [handle_latex_output()](Cogito/src/latex/cli.py:78)
- Configuration loader: [ConfigLoader.__init__()](Cogito/src/config_loader.py:20), [config_loader](Cogito/src/config_loader.py:121)
- Provider configs: [get_primary_provider()](Cogito/src/providers/model_config.py:18), [get_openrouter_config()](Cogito/src/providers/model_config.py:111)
- OpenRouter client: [run_openrouter_client()](Cogito/src/providers/openrouter_client.py:27)
- Syncretic Catalyst: [build_thesis()](Cogito/src/syncretic_catalyst/thesis_builder.py:548), [enhance_research()](Cogito/src/syncretic_catalyst/research_enhancer.py:340)