---
description: Implement an existing spec or implementation plan
argument-hint: Path to spec or plan file, for example docs/roadmap/plan/eval-history-delta-reporting-plan.md
allowed-tools: Read, Write, Edit, Glob, Grep, Bash(git status:*), Bash(git diff:*), Bash(git ls-files:*), Bash(mkdir:*), Bash(uv run ruff:*), Bash(uv run mypy:*), Bash(uv run pytest tests/node:*), Bash(uv run pytest tests/graph:*), Bash(uv run pytest tests/evals:*), Bash(uv run python evals/run_eval.py --validate-only:*)
---

You are implementing an existing spec or implementation plan for this Agentic RAG project.

User input: $ARGUMENTS

Implement only the requested scope.

Use as few tools as possible.

Do not create or switch git branches.

Do not commit automatically.

## Required locations

Spec files live under:

`docs/roadmap/spec/`

Plan files live under:

`docs/roadmap/plan/`

Implementation reports live under:

`docs/roadmap/implementation/`

Implementation report template:

`docs/roadmap/implementation/implementation-template.md`

Generated implementation report:

`docs/roadmap/implementation/<feature-slug>-implementation-report.md`

## Step 1. Read minimal project rules

Read first:

* `CLAUDE.md`

Then check whether the implementation report template exists:

`docs/roadmap/implementation/implementation-template.md`

If it exists, read it.

If it does not exist, continue implementation, but do not create an implementation report. Tell the user the template is missing at the end.

## Step 2. Check working tree

Run:

```powershell
git status --short
```

If the working tree has unrelated uncommitted changes, stop and ask the user whether to continue.

Do not overwrite unrelated changes.

Do not create or switch branches.

## Step 3. Resolve input file

The user input must be a path to either:

* a plan file, such as `docs/roadmap/plan/eval-history-delta-reporting-plan.md`
* a spec file, such as `docs/roadmap/spec/eval-history-delta-reporting.md`

Read the file from `$ARGUMENTS`.

If the file does not exist, stop and tell the user:

`Spec or plan file not found. Please provide a valid path.`

## Step 4. Plan-first reading rule

If the input is a plan file:

* Read the plan.
* Do not automatically read the source spec.
* Only read the source spec if:

  * the plan explicitly says the source spec must be read, or
  * the plan is ambiguous and cannot be safely implemented on its own, or
  * the user explicitly asks you to read the source spec.

If the input is a spec file:

* Read the spec.
* Look for a matching plan file named:
  `docs/roadmap/plan/<feature-slug>-plan.md`
* If the matching plan exists, read the plan and implement from the plan.
* If no matching plan exists, implement directly from the spec.

## Step 5. Infer feature metadata

Infer:

### feature_title

Use the document heading if possible.

### feature_slug

Infer from the input filename.

Rules:

* Remove `.md`.
* Remove `-plan` suffix if present.
* Remove `-implementation-report` suffix if present.
* Keep lowercase kebab-case.

Example:

Input:

`docs/roadmap/plan/eval-history-delta-reporting-plan.md`

Feature slug:

`eval-history-delta-reporting`

Implementation report:

`docs/roadmap/implementation/eval-history-delta-reporting-implementation-report.md`

If you cannot infer the title or slug, ask the user to clarify.

## Step 6. Read only necessary project files

Read the files listed in the plan or spec under:

* Files to inspect.
* Required files.
* Files expected to change.

Prefer the plan file as the source of truth.

Do not do a broad architecture review unless the plan or spec asks for it.

Do not read unrelated files unless needed to implement the requested change safely.

## Step 7. Implement the planned scope

Implement only what the plan or spec asks for.

Prefer the smallest safe change.

Do not expand scope.

Do not add extra features.

Do not refactor unrelated code.

Do not change behavior unless the plan or spec explicitly requires it.

## Default safety constraints

Unless the plan or spec explicitly approves an exception:

* Do not change prompts.
* Do not change model names.
* Do not change corpus documents.
* Do not change graph behavior.
* Do not change graph routing.
* Do not change graph nodes.
* Do not change `stop_reason` semantics.
* Do not change fallback policy semantics.
* Do not modify `.env` or `.env.example`.
* Do not run full eval.
* Do not run `ingestion.py`.
* Do not run `tests/chains/`.
* Do not run API-key-requiring commands.
* Do not commit automatically.
* Do not create or switch branches.

## Step 8. Validate

Run only validation commands approved by the plan or spec.

Usually safe commands are:

```powershell
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest tests/evals/ -q
uv run pytest tests/node/ tests/graph/ tests/evals/ -q
uv run python evals/run_eval.py --validate-only
```

Do not run full eval unless the plan or spec explicitly says it is needed and the user has separately approved it.

Full eval command:

```powershell
uv run python evals/run_eval.py --output evals/results.md
```

## Step 9. Create implementation report

If `docs/roadmap/implementation/implementation-template.md` exists, create the directory if needed:

`docs/roadmap/implementation/`

Then create:

`docs/roadmap/implementation/<feature-slug>-implementation-report.md`

Use `docs/roadmap/implementation/implementation-template.md` as the structure.

Fill it with the actual final implementation details.

The report must be grounded in the real diff and real command results.

Do not invent passing tests.

Do not claim full eval was run if it was not run.

## Step 10. Final response

At the end, respond with a concise implementation summary.

Include:

* Source plan path, if read.
* Source spec path, if read.
* Implementation report path, if created.
* Files changed.
* Tests run and results.
* Whether full eval was run.
* Whether API-key commands were run.
* Whether prompts/models/corpus/.env changed.
* Whether graph behavior changed.
* `git status --short`.
* `git diff --stat`.
* Known risks or follow-up work.

Do not commit.

Do not create or switch branches.
