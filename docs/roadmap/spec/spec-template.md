# <Feature Title>

Status: Draft

Date: <YYYY-MM-DD>

Type: Spec

## 1. Summary

Briefly describe the change.

## 2. Background / Current behavior

Explain the existing behavior and why this change is needed.

## 3. Goals

List what this change should achieve.

## 4. Non-goals

List what this change explicitly will not do.

## 5. Files to inspect

List the project files that should be read before implementation.

Common files for this Agentic RAG project:

* `CLAUDE.md`
* `README.md`
* `structure.md`
* `graph/engine.py`
* `graph/graph.py`
* `graph/state.py`
* `graph/config.py`
* `graph/consts.py`
* `evals/run_eval.py`
* `evals/questions.jsonl`
* `evals/README.md`
* `tests/evals/test_eval_harness.py`

Only include files that are relevant to this specific feature.

## 6. Proposed changes

Describe the intended changes at a high level.

Do not include full code unless absolutely necessary.

## 7. Implementation plan

Break the work into small ordered steps.

Example:

1. Inspect current behavior.
2. Add or update the smallest necessary schema/API.
3. Add tests.
4. Update documentation.
5. Run safe validation commands.
6. Report final status.

## 8. Safety constraints

Default constraints for this project:

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
* Do not run `ingestion.py` unless explicitly approved.
* Do not run `tests/chains/` unless explicitly approved.
* Do not run API-key-requiring commands unless explicitly approved.
* Do not commit automatically.

## 9. Validation plan

Safe validation commands:

```powershell
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest tests/evals/ -q
uv run pytest tests/node/ tests/graph/ tests/evals/ -q
uv run python evals/run_eval.py --validate-only
```

Only run full eval if the feature explicitly needs it and the user separately approves:

```powershell
uv run python evals/run_eval.py --output evals/results.md
```

## 10. Acceptance criteria

Define exactly what success means.

Include measurable criteria such as:

* Relevant tests pass.
* Safe mocked suite passes if applicable.
* Eval dataset validates if eval files changed.
* Documentation is updated if behavior or workflow changed.
* No prompt/model/corpus/.env changes unless explicitly approved.
* No graph behavior changes unless explicitly approved.

## 11. Risks and calibration notes

List known risks, including:

* Retrieval instability.
* Eval row calibration risk.
* Web/API variability.
* LLM output variability.
* Possible stale documentation.
* Possible overengineering.

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
