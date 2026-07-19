# <Feature Title> — Implementation Plan

Status: Planned

Date: <YYYY-MM-DD>

Type: Plan

Source spec: `<path-to-spec>`

## 1. Spec summary

Summarize the source spec in a few paragraphs.

Include:

* What the feature is.
* Why it is needed.
* What problem it solves.
* What must not change.

## 2. Current system understanding

Describe the current project behavior relevant to this feature.

Include only what was verified from project files.

Do not guess.

## 3. Files to inspect during implementation

List the files the implementation agent should read before editing.

Separate them into:

### Required files

Files that must be read.

### Optional files

Files that may be read only if needed.

## 4. Proposed implementation steps

Break implementation into small ordered steps.

Each step should include:

* Goal.
* Files likely changed.
* What to avoid.
* Validation to run after the step, if useful.

Example:

1. Add minimal schema support.
2. Add unit tests.
3. Add dataset rows.
4. Update docs.
5. Run safe validation.

## 5. Files expected to change

List files that are expected to change.

## 6. Files that should not change

List files that should remain untouched.

For this Agentic RAG project, usually avoid changing:

* `enterprise_rag/graph/nodes/`
* `enterprise_rag/graph/chains/`
* prompt text
* model names
* corpus documents
* `.env`
* `.env.example`
* `enterprise_rag/ingestion.py`

Unless the spec explicitly requires it.

## 7. Safety constraints

Default constraints:

* Do not change prompts unless explicitly approved.
* Do not change model names unless explicitly approved.
* Do not change corpus documents unless explicitly approved.
* Do not change graph behavior unless explicitly approved.
* Do not change graph routing unless explicitly approved.
* Do not change graph nodes unless explicitly approved.
* Do not change `stop_reason` semantics unless explicitly approved.
* Do not change fallback policy semantics unless explicitly approved.
* Do not modify `.env` or `.env.example`.
* Do not run full eval unless explicitly approved.
* Do not run `enterprise_rag/ingestion.py` unless explicitly approved.
* Do not run `tests/enterprise_rag/chains/` unless explicitly approved.
* Do not run `tests/office_agent/integration/` unless explicitly approved.
* Do not run API-key-requiring commands unless explicitly approved.
* Do not commit automatically.

## 8. Validation plan

This section defines what the implementing agent should run after implementation.

The plan creation step must not run these commands unless explicitly requested.

Safe validation commands usually include:

```powershell
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest tests/enterprise_rag/evals/ -q
uv run pytest tests/enterprise_rag/nodes/ tests/enterprise_rag/graph/ tests/enterprise_rag/evals/ -q
uv run pytest tests/office_agent/ --ignore=tests/office_agent/integration -q
uv run python evals/enterprise_rag/run_eval.py --validate-only
```

Only run full eval if the feature explicitly needs it and the user separately approves:

```powershell
uv run python evals/enterprise_rag/run_eval.py --output evals/enterprise_rag/results.md
```

## 9. Acceptance criteria

Define what must be true for the implementation to be considered complete.

Include:

* Tests that must pass.
* Docs that must be updated.
* Behavior that must remain unchanged.
* Files that must not be touched.
* Whether full eval is required or explicitly deferred.

## 10. Risks and calibration notes

List known risks.

Examples:

* Retrieval top-k instability.
* LLM wording variability.
* Web search variability.
* Eval row calibration risk.
* Documentation drift.
* Overengineering risk.

## 11. Recommended implementation prompt

Write a concise prompt that can be given to an implementation agent.

It should tell the agent to:

* Read `CLAUDE.md`.
* Read the source spec only if this plan says it is required, the plan is insufficient on its own, or the user explicitly asks.
* Read this implementation plan.
* Implement only the planned scope.
* Respect all safety constraints.
* Run only approved validation commands.
* Report final status.

## 12. Final report format

The implementing agent should report:

* Files changed.
* What was implemented.
* Tests run.
* Whether full eval was run.
* Whether API-key commands were run.
* Whether prompts/models/corpus/.env changed.
* Whether graph behavior changed.
* `git status --short`.
* `git diff --stat`.
* Known risks or follow-up work.
