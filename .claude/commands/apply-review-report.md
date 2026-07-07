---
description: Apply scoped fixes from a project-level review report
argument-hint: Review report path, or review topic/focus such as "failure-modes overall"
allowed-tools: Read, Edit, Glob, Grep, Bash(git status:*), Bash(git diff:*), Bash(git diff --stat:*), Bash(uv run python -m py_compile:*), Bash(uv run pytest tests/enterprise_rag/nodes:*), Bash(uv run pytest tests/enterprise_rag/graph:*), Bash(uv run pytest tests/enterprise_rag/evals:*)
---
You are applying scoped fixes from a completed project-level review report.

User input: $ARGUMENTS

This is an implementation task driven by a review report.

Do not improvise unrelated improvements.

Do not apply optional recommendations unless the user explicitly asks.

Do not apply broad refactors.

Do not change graph routing semantics unless the review report explicitly requires it.

Do not change `stop_reason` semantics unless the review report explicitly requires it.

Do not change fallback-policy semantics unless the review report explicitly requires it.

Do not change privacy-mode semantics unless the review report explicitly requires it.

Do not change model names unless the review report explicitly requires it.

Do not modify corpus documents.

Do not modify `.env` or `.env.example`.

Do not run full eval.

Do not run `ingestion.py`.

Do not run `tests/enterprise_rag/chains/`.

Do not run API-key-requiring commands.

Do not commit.

Do not create or switch branches.

Use as few tools as possible.

## Goal

Read a project-level review report and apply only the scoped fixes that are clearly justified by that report.

Supported review report families:

* `docs/roadmap/architecture-review/`
* `docs/roadmap/security-review/`
* `docs/roadmap/failure-modes-review/`
* `docs/roadmap/test-coverage-review/`
* `docs/roadmap/docs-drift-review/`

This command is for project-level review reports. Documentation-drift reports under `docs/roadmap/docs-drift-review/` are project-level review reports (handled here), not command-file review reports.

Do not use this command for command-file review reports under:

* `docs/roadmap/commands-review/`

Use `/apply-command-review` for command-file review reports instead.

## Default application policy

Apply fixes in this priority order:

1. Apply all clear `Must fix` items.
2. If there are no `Must fix` items, apply the first clear and narrowly scoped `Should fix soon` item.
3. Do not apply `Optional` items by default.
4. If every item is optional, do not edit files. Report that no default-applied fix exists.
5. If a finding is ambiguous, broad, architectural, or risky, do not apply it automatically. Ask the user to rerun with a more specific instruction.

A fix is clear and narrowly scoped only if the report identifies:

* the concrete issue
* why it matters
* the affected area or likely files
* a specific recommended fix
* a validation path or obvious minimal validation

### Documentation-drift reports (`docs/roadmap/docs-drift-review/`)

Documentation-drift reports do not use `Must fix` / `Should fix soon` / `Optional`
headings. Map their vocabulary onto the priority order above before selecting:

* A `Confirmed drift` finding classified `SAFE TO FIX` → treat as `Must fix` (apply;
  follow the report's `Suggested repair order` → `Safe mechanical fixes` grouping).
* A finding classified `REVIEW BEFORE FIXING` → treat as `Should fix soon` (apply only
  the first clear, narrowly scoped one; if it changes semantics or is architectural,
  stop and ask).
* `Possible drift`, anything classified `DO NOT CHANGE`, and anything under `Historical
  references preserved` → never apply automatically.
* Severity is a tiebreaker for ordering only: `BLOCKING` / `HIGH` rank as `Must fix`,
  `MEDIUM` as `Should fix soon`, `LOW` as `Optional`.

## Step 1. Validate input

If `$ARGUMENTS` is empty, stop and ask the user for either:

* an exact review report path
* a review topic and focus, such as `failure-modes overall`

Do not search broadly without input.

## Step 2. Resolve the review report

Decide whether `$ARGUMENTS` is an explicit path or a topic/focus query.

Treat input as an explicit path if it:

* contains `/` or `\`
* ends in `.md`

If `$ARGUMENTS` is an explicit path:

* Read exactly that file.
* If the file does not exist, stop and tell the user:
  `Review report not found. Provide a valid project-level review report path.`
* Do not search broadly after a missing explicit path.

If `$ARGUMENTS` is not an explicit path:

Search only under these directories:

* `docs/roadmap/architecture-review/`
* `docs/roadmap/security-review/`
* `docs/roadmap/failure-modes-review/`
* `docs/roadmap/test-coverage-review/`
* `docs/roadmap/docs-drift-review/`

Use the input words as topic/focus hints.

Examples:

* `failure-modes overall`
* `security overall`
* `test-coverage privacy`
* `architecture graph`
* `docs-drift overall`
* `docs-drift office-agent`

Resolve the match:

* If exactly one clearly relevant report is found, read it.
* If multiple reports are plausible, stop and list candidate paths. Ask the user to rerun with the exact path.
* If no report is found, stop and say no matching project-level review report was found.

Do not read command-review reports.

Do not read unrelated roadmap files.

## Step 3. Extract actionable findings

From the report, identify:

* `Must fix`
* `Should fix soon`
* `Optional`
* main issues
* recommended next actions
* affected files or likely affected areas
* validation recommendations

Then choose the default action using the default application policy.

Before editing, write a short internal plan in the response stream:

* report path
* selected finding
* why it is safe to apply
* files expected to change
* validation to run

If the selected finding would require broad design changes, multi-step refactoring, unclear semantics, or changing public behavior, stop and ask for confirmation.

## Step 4. Inspect only relevant files

Read only files needed for the selected finding.

Prefer targeted reads.

Use `Glob` only to discover actual existing files when filenames are uncertain.

Do not inspect `.env`.

Do not inspect generated artifacts.

Do not inspect unrelated source files.

Do not inspect unrelated tests.

## Step 5. Apply the selected fix

Edit only the files necessary for the selected finding.

Keep the change minimal.

Preserve existing public behavior unless the report explicitly requires a behavior change.

Preserve existing test style.

Preserve import-time side-effect-free behavior.

Preserve lazy factory patterns.

Preserve existing user-facing answer wording unless the selected finding is specifically about wording.

Preserve privacy-mode hard guarantees.

Preserve safe fallback behavior.

If applying a timeout, budget, or failure-handling fix:

* keep success-path behavior unchanged
* rely on existing exception handlers where possible
* add minimal config constants only if needed
* update tests only if the behavior is newly testable without API keys

If applying a test-coverage fix:

* add the smallest behavioral test that locks the reviewed risk
* add the test to the most appropriate existing test file via `Edit` (under `tests/enterprise_rag/nodes/`, `tests/enterprise_rag/graph/`, or `tests/enterprise_rag/evals/`)
* if the fix would genuinely require a new test module, stop and ask the user — this command edits existing files via `Edit` and does not create new files
* do not add API-key-requiring tests by default
* do not modify `tests/enterprise_rag/chains/`
* do not make brittle tests that depend on implementation details unnecessarily

If applying a documentation fix:

* keep wording durable and concise
* do not add changelog entries
* do not copy large report excerpts
* documentation-drift and other report fixes may edit any tracked doc (e.g. `README.md`, `structure.md`, `docs/adr/**`, `evals/**/README.md`), not only files under `enterprise_rag/`; validate a docs-only edit with `git diff --check` rather than a test run

## Step 6. Validate the change

Always run:

```powershell
git status --short
git diff --stat
git diff
```

Then run the smallest relevant validation only if applicable.

Allowed validation examples:

```powershell
uv run python -m py_compile enterprise_rag/graph/engine.py enterprise_rag/graph/config.py
uv run pytest tests/enterprise_rag/graph -q
uv run pytest tests/enterprise_rag/nodes -q
uv run pytest tests/enterprise_rag/evals -q
```

Do not run full eval.

Do not run `tests/enterprise_rag/chains/`.

Do not run API-key-requiring commands.

If validation is not applicable, say why.

If validation fails:

* report the failure
* do not keep editing indefinitely
* make at most one narrow fix attempt if the cause is obvious
* otherwise stop and ask the user

## Step 7. Final response

Respond in this format:

Applied review report: `<report path>`

Selected finding: `<Must fix / Should fix soon / none>`

Files changed:

* `<file 1>`
* `<file 2>`

What changed:

* `<short bullet>`
* `<short bullet>`

Validation:

* `<command run>` — `<result>`
* `<command run>` — `<result>`

Not applied:

* `<optional or ambiguous findings intentionally skipped>`

Next step:

* `Run /review-diff before committing.`

Do not include the full diff unless the user asks.

Do not commit.
