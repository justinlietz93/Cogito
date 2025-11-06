# Directory Input Smoke Test

This guide captures the manual verification steps for the directory ingestion
feature. Run the sequence below whenever major refactors touch the CLI,
`DirectoryContentRepository`, or configuration defaults.

## Prerequisites

- Create a throwaway workspace:
  ```bash
  tmp_root=$(mktemp -d)
  mkdir -p "$tmp_root/research_notes"
  cat <<'DOC' > "$tmp_root/research_notes/outline.md"
  # Outline
  - Introduction
  - Methods
  DOC
  cat <<'DOC' > "$tmp_root/research_notes/findings.md"
  # Findings
  The experiment produced conclusive evidence.
  DOC
  ```
- Optionally adjust `config.json` to exercise overrides (for example set
  `critique.directory_input_overrides.syncretic_catalyst.order`).

## Execution

Run the CLI against the temporary tree:

```bash
python run_critique.py \
  --input-dir "$tmp_root/research_notes" \
  --output-dir "$tmp_root/out" \
  --no-peer-review \
  --no-scientific
```

## Expected Results

1. The console prints the critique output path and no error messages.
2. `$tmp_root/out` contains one file named
   `research_notes_critique_<timestamp>.md`.
3. The file content contains two section headers (`## outline.md`,
   `## findings.md`) separated by the configured section delimiter.
4. The file metadata embeds a `files` collection with SHA-256 digests and byte
   counts for each document.
5. `logs/system.log` includes a "Directory aggregation summary" entry whose JSON
   payload records `processed_files`, `total_bytes`, and any truncation events.

Document the timestamped output path inside the enhancement checklist once the
smoke run succeeds. Clean up the temporary workspace when finished:

```bash
rm -rf "$tmp_root"
```
