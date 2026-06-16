---
description: Commit currently staged changes with a generated commit message
argument-hint: Optional commit intent, for example "eval history delta reporting"
allowed-tools: Bash(git status:*), Bash(git diff:*), Bash(git ls-files:*), Bash(git commit:*)
---

You are creating a Git commit for the currently staged changes.

User intent: $ARGUMENTS

This command may create a commit, but must not push.

## Step 1. Inspect staged state

Run:

```powershell
git status --short
git diff --cached --stat
git diff --cached
```

If `git diff --cached --stat` shows no staged changes, stop and tell the user there is nothing staged to commit. Ask them to stage files first, then re-run. Do not create an empty commit.

Only commit staged changes.

Do not run `git add`.
Do not run `git add .`.
Do not stage unstaged files.
Do not push.
Do not create or switch branches.

## Step 2. Safety checks

Before committing, check the staged diff for unsafe or unrelated files.

Do not commit if staged changes include:

* `.env`
* `.env.example`
* API keys, secrets, tokens, credentials
* `chroma_db/`
* `__pycache__/`
* `.mypy_cache/`
* `.pytest_cache/`
* generated history JSON files under `evals/history/*.json`
* unrelated files that do not match the user's commit intent

If unsafe or unrelated files are staged, stop and tell the user exactly what to unstage.

## Step 3. Create commit message

Generate a concise commit message from the staged diff.

Use this style:

* `Add ...`
* `Update ...`
* `Fix ...`
* `Refactor ...`
* `Document ...`

Prefer a clear one-line message unless the diff is large enough to need a body.

Examples:

```text
Add richer eval contains checks
Add eval history and delta reporting
Update eval README for history records
Fix eval delta baseline selection
```

## Step 4. Commit

If the staged diff is safe and coherent, run:

```powershell
git commit -m "<generated message>"
```

Do not amend unless the user explicitly asks.
Do not use `git commit -a` or `git commit -am`; commit only what is already staged.
Do not use `--no-verify`; do not bypass hooks.
Do not push.

## Step 5. Final response

Report:

* Commit message used.
* Files committed.
* Confirm no push was run.
* `git status --short`.
