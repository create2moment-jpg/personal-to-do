# Prompt library

Versioned prompt templates for the AI layer (Phase 5+). Folders follow the
build brief (`00_system` … `13_meta`). Nothing here is used yet; this file
fixes the contract so prompts are written consistently from the start.

## File layout

```
prompts/<area>/<capability>/
├── v1.md              # the prompt (front matter + template)
├── v1.small.md        # optional variant tuned for small local models
├── input.schema.json  # or a reference into /schemas
├── output.schema.json
└── fixtures/          # synthetic regression cases: <name>.input.json / <name>.expected.json
```

Prompt versions are immutable once used for a stored output; change = new
version. Stored AI outputs record `prompt_id@version` and model id.

## Required front matter

```yaml
id: weekly.review
version: 1
role: "You are a careful planning assistant…"
objective: "Summarise the week from the provided records."
allowed_sources: [tasks, daily_plans, notes:journal]   # nothing else may be cited
input_schema: input.schema.json
output_schema: output.schema.json
constraints:
  - Use only the provided records; do not invent achievements.
  - Every claim must cite one or more source ids.
uncertainty: "If records are missing or ambiguous, say so in `gaps`."
provenance: "Each item has `sources: [id…]` and `kind: fact|document_claim|user_statement|inference|recommendation`."
context_budget_tokens: 6000
small_model_variant: v1.small.md
```

## Fixtures and evaluation

Fixtures are synthetic (never real personal data — the repo safety guard
enforces the data boundary). Evaluations measure schema validity,
groundedness (every cited id exists in the input), latency and, in use,
accept/edit/reject rates.
