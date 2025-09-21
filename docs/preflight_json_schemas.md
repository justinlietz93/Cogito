# Preflight JSON Schemas

Cogito's preflight pipeline writes structured JSON artefacts that downstream
tools can consume without invoking the critique workflow. The schemas live under
`src/contexts/schemas/` and mirror the immutable domain models defined in
`src/domain/preflight/models.py`.

## Extraction Result (`extraction.schema.json`)

An extraction run returns an `ExtractionResult` document with the following
shape:

- `points` *(array, required)* – ordered list of extracted insights. Each entry
  must satisfy the `ExtractedPoint` definition:
  - `id` *(string, required)* – stable identifier (`pt-<n>` by convention).
  - `title` *(string, required)* – concise heading.
  - `summary` *(string, required)* – multi-sentence description.
  - `evidence_refs` *(array[string], required)* – supporting references such as
    file paths or citation identifiers.
  - `confidence` *(number, required)* – normalised confidence within `[0.0, 1.0]`.
  - `tags` *(array[string], optional)* – thematic classifications. Defaults to
    an empty list when omitted.
- `source_stats` *(object, required)* – metadata describing the analysed corpus
  (counts, token usage, truncation flags). Additional keys are permitted so the
  orchestrator can surface provider-specific measurements without breaking
  consumers.
- `truncated` *(boolean, required)* – signals that caps or provider limits
  prevented the extractor from emitting the full set of points.

### Example Extraction Artefact

```json
{
  "points": [
    {
      "id": "pt-1",
      "title": "Transformer depth controls summarisation fidelity",
      "summary": "Long-form transcripts benefit from deeper decoder stacks...",
      "evidence_refs": ["/docs/transcript.md#L42-L88"],
      "confidence": 0.82,
      "tags": ["summarisation", "architecture"]
    }
  ],
  "source_stats": {
    "source_count": 1,
    "char_count": 18450,
    "time_ms": 2940
  },
  "truncated": false
}
```

## Query Plan (`query_plan.schema.json`)

Query planning yields a `QueryPlan` document comprised of:

- `queries` *(array, required)* – ordered list of follow-up actions. Each entry
  adheres to the `BuiltQuery` definition:
  - `id` *(string, required)* – stable identifier (`q-<n>` by convention).
  - `text` *(string, required)* – natural-language request.
  - `purpose` *(string, required)* – why the query matters.
  - `priority` *(integer, required)* – execution order; lower numbers run first.
  - `depends_on_ids` *(array[string], optional)* – prerequisites that must
    complete successfully.
  - `target_audience` *(string|null, optional)* – intended respondent or system.
  - `suggested_tooling` *(array[string], optional)* – helper tools or pipelines.
- `rationale` *(string, required)* – overall strategy for the plan. Defaults to
  an empty string when omitted by the model but is filled during parsing.
- `assumptions` *(array[string], optional)* – contextual assumptions for the
  plan (default: empty list).
- `risks` *(array[string], optional)* – identified risks or mitigations
  (default: empty list).

### Example Query Plan Artefact

```json
{
  "queries": [
    {
      "id": "q-1",
      "text": "Request the original dataset to verify reported baselines.",
      "purpose": "Validate reproducibility claims before deeper analysis.",
      "priority": 1,
      "depends_on_ids": [],
      "target_audience": "research-author",
      "suggested_tooling": ["http_client"]
    }
  ],
  "rationale": "Confirm data availability before designing experiments.",
  "assumptions": ["Authors can share the dataset"],
  "risks": ["Dataset may be proprietary"]
}
```

## Validation & Tooling

- Integration coverage lives in
  `tests/integration/test_cli_preflight_artifacts.py` and verifies the CLI emits
  artefacts that conform to both schemas.
- Run the test directly to validate local changes:

  ```bash
  pytest tests/integration/test_cli_preflight_artifacts.py -q
  ```
- For ad-hoc inspection, pass generated artefacts through any JSON Schema
  validator that supports Draft 2020-12 (for example the `jsonschema` Python
  package).

