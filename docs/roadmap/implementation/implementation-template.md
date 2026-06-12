# <Feature Title> — Implementation Report

Status: Implemented

Date: <YYYY-MM-DD>

Type: Implementation Report

Source spec: `<path-to-spec, or "not read — implemented from plan">`

Source plan: `<path-to-plan>`

## 1. Summary

Briefly summarize what was implemented.

## 2. Files changed

List all changed files.

Group them by purpose:

### Code

### Tests

### Documentation

### Eval files

### Other

## 3. What was implemented

Describe the actual implementation.

Keep this grounded in the final diff.

Do not claim work that was not done.

## 4. What was intentionally not changed

List important non-changes.

For this Agentic RAG project, explicitly mention whether these were unchanged:

* Prompts.
* Model names.
* Corpus documents.
* Graph behavior.
* Graph routing.
* Graph nodes.
* `stop_reason` semantics.
* Fallback policy semantics.
* `.env` / `.env.example`.

## 5. Validation run

List every command that was run.

For each command, include the result.

Example:

* `uv run ruff check .` — passed.
* `uv run ruff format --check .` — passed.
* `uv run mypy` — passed.
* `uv run pytest tests/evals/ -q` — passed.
* `uv run pytest tests/node/ tests/graph/ tests/evals/ -q` — passed.
* `uv run python evals/run_eval.py --validate-only` — passed.

If full eval was run, include:

* command
* result
* whether `evals/results.md` changed
* final pass count

If full eval was not run, say so clearly.

## 6. Risks and follow-up work

List any known risks, skipped work, calibration concerns, or recommended next steps.

Examples:

* Full eval still needs separate approval.
* Some eval rows may need calibration.
* Documentation may need a later sync pass.
* A broader architecture review may be useful later.

## 7. Final git state

Include:

```text
git status --short
```

Include:

```text
git diff --stat
```

## 8. Final confirmation

Confirm:

* No prompt changes unless explicitly approved.
* No model-name changes unless explicitly approved.
* No corpus changes unless explicitly approved.
* No `.env` or `.env.example` changes.
* No graph behavior changes unless explicitly approved.
* No full eval unless explicitly approved.
* No `ingestion.py` run unless explicitly approved.
* No `tests/chains/` run unless explicitly approved.
* No commit was created automatically.
