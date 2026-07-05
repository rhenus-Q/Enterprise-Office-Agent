---
description: Review the current git diff for safety, scope, and commit readiness
argument-hint: Optional review focus, for example "eval changes" or "docs only"
allowed-tools: Read, Glob, Grep, Bash(git status:*), Bash(git diff:*), Bash(git log:*)
---

You are reviewing the current git diff for this Agentic RAG project.

User input: $ARGUMENTS

This is a review-only command.

Do not modify files.

Do not implement changes.

Do not commit.

Do not create or switch branches.

Use as few tools as possible.

## Step 1. Read project rules

Read:

* `CLAUDE.md`

## Step 2. Inspect git state

Run:

```powershell
git status --short
git diff --stat
git diff --name-only
```

Then inspect the relevant diffs.

Prefer targeted diffs over reading entire files.

Use:

```powershell
git diff -- <file>
```

for changed files that need closer review.

For any `??` (untracked) files shown by `git status --short`, read the file directly using the Read tool before assessing commit readiness. An untracked file may be a new corpus document, a generated file, a secrets file, or an accidental addition — it is invisible to `git diff` and must be reviewed explicitly.

## Step 3. Review scope

Classify the diff by purpose.

Examples:

* eval harness change
* eval dataset change
* documentation update
* graph behavior change
* test update
* dev tooling change
* generated result update
* roadmap planning artifact (spec / plan / implementation report)
* unrelated or suspicious change

Check whether the changed files match the intended scope from the user input.

If the user input is empty, infer the likely scope from changed files.

## Step 4. Check for forbidden or risky changes

Flag any unexpected changes to:

* prompts
* model names
* corpus documents
* graph behavior
* graph routing
* graph nodes
* `stop_reason` semantics
* fallback policy semantics
* `.env`
* `.env.example`
* `ingestion.py`
* `tests/chains/`

Also flag:

* broad unrelated refactors
* accidental formatting-only churn
* generated files that should not be committed
* stale docs
* stale eval results
* missing tests for changed behavior
* changes that require full eval but only validate-only was run

## Step 5. Check validation evidence

Look for validation evidence in the current conversation if available.

If not available, recommend the smallest appropriate validation set.

For most changes, recommend:

```powershell
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest tests/evals/ -q
uv run python evals/enterprise_rag/run_eval.py --validate-only
```

For graph/node/eval-behavior changes, recommend:

```powershell
uv run pytest tests/node/ tests/graph/ tests/evals/ -q
```

Only recommend full eval when the diff changes eval rows, eval expectations, retrieval behavior, fallback behavior, or generated eval results:

```powershell
uv run python evals/enterprise_rag/run_eval.py --output evals/enterprise_rag/results.md
```

Never run full eval unless the user explicitly asks.

Do not run `ingestion.py`.

Do not run `tests/chains/`.

Do not run API-key-requiring commands unless explicitly approved.

## Step 6. Commit readiness judgment

Give one of these outcomes:

* `Ready to commit`
* `Ready after minor check`
* `Not ready`
* `Needs clarification`

Base this on:

* scope correctness
* changed files
* test evidence
* risk level
* whether generated files are expected
* whether forbidden areas were touched

## Step 7. Suggested commit command

If the diff is ready or nearly ready, suggest an explicit `git add` command with only the appropriate files.

Do not suggest `git add .` unless the diff is very small and all changed files are clearly intended.

Then suggest a concise commit message.

Example:

```powershell
git add evals/enterprise_rag/questions.jsonl evals/enterprise_rag/results.md
git commit -m "Refresh eval results after Phase 3 calibration"
```

## Final response format

Use this format:

### Review summary

* Scope:
* Risk level:
* Commit readiness:

### Changed files

List changed files grouped by purpose.

### Findings

List important findings.

Use:

* ✅ for safe/expected
* ⚠️ for needs attention
* ❌ for blocking issue

### Validation

List tests/checks already evidenced or still recommended.

### Commit recommendation

If ready, provide:

```powershell
git add <files>
git commit -m "<message>"
```

If not ready, explain what must be fixed first.

### Confirmations

Explicitly state whether the diff appears to change:

* prompts
* model names
* corpus documents
* `.env` / `.env.example`
* graph behavior
* full eval results
