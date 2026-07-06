---
description: Apply fixes from a Claude command review report to the reviewed command file
argument-hint: 'Command review report path, e.g. docs/roadmap/commands-review/2026-06-14-new-command-command-review.md'
allowed-tools: Read, Edit, Glob, Grep, Bash(git status:*), Bash(git diff:*)
---

You are applying fixes from a Claude command review report to the reviewed Claude Code command file.

User input: $ARGUMENTS

This is a focused command-file edit task.

Modify only the target command file identified by the review report.

The target command file must be under:

`.claude/commands/`

Do not modify the review report.

Do not create a new review report.

Do not create new files.

Do not modify any other Claude command file.

Do not modify `CLAUDE.md`.

Do not modify application code.

Do not modify tests.

Do not modify eval files.

Do not modify README.

Do not modify roadmap files.

Do not modify prompts.

Do not modify model names.

Do not modify corpus documents.

Do not modify `.env` or `.env.example`.

Do not run tests.

Do not run full eval.

Do not run `ingestion.py`.

Do not run `tests/enterprise_rag/chains/`.

Do not run API-key-requiring commands.

Do not commit.

Do not create or switch branches.

Use as few tools as possible.

## Goal

Read a command review report produced by `/review-command`.

Find the reviewed target command file.

Apply only the concrete fixes recommended by the report.

Keep the command's original purpose and structure.

Do not redesign the command.

Do not rewrite the whole command.

Do not make unrelated wording changes.

Do not apply cosmetic or optional changes unless the user explicitly asks for optional fixes.

## Step 1. Validate input

If `$ARGUMENTS` is empty, stop and ask the user for a command review report path.

The input must be a review report path, usually under:

`docs/roadmap/commands-review/`

Treat the input as a file path.

If the report path does not exist, stop and say:

`Review report not found. Provide a valid command review report path.`

Do not search the whole repo for a replacement report.

## Step 2. Read the review report

Read the provided review report.

Extract:

* `Target command:`
* `Final verdict`
* `Problems found`
* `Recommended fixes`
* `Must fix`
* `Should fix soon`
* `Optional improvements`

If the report does not identify a target command, stop and ask the user to provide the target command path explicitly.

If the target command path is not under `.claude/commands/`, stop.

If the target command file does not exist, stop and report the missing target command.

## Step 3. Decide what to apply

Apply fixes in this priority order:

1. Must fix
2. Should fix soon

Do not apply optional improvements unless the user explicitly asks for optional fixes by including one of:

* `include optional`
* `--include-optional`
* `apply optional`

Do not apply cosmetic-only suggestions unless explicitly requested.

If the report verdict is `Ready to use` and there are no Must fix or Should fix soon items, do not edit the command file.

If all findings are optional or cosmetic, do not edit unless optional fixes were explicitly requested.

Do not manufacture extra fixes.

Only apply fixes that are directly traceable to the review report.

## Step 4. Read the target command

Read the target command file.

Inspect only the sections needed to apply the selected fixes.

Do not read unrelated project files unless needed to avoid an incorrect command edit.

If the selected fix concerns consistency with peer commands, read only the specific peer command files mentioned in the report.

## Step 5. Apply focused edits

Use `Edit` only for the target command file.

Do not use `Edit` on any other file.

Before applying a fix, confirm the text it targets still exists. If a selected fix refers to
specific text, wording, frontmatter, permission lines, or command sections that are no longer
present in the current target command file, the review report is stale. Stop and report review
drift: name which fix could not be applied because the expected target text or section was not
found. Do not guess, and do not perform a broader rewrite to compensate.

Keep edits minimal and localized.

Preserve the existing command style.

Preserve the command's intended task category.

Preserve narrow `allowed-tools`.

Never add broad permissions such as:

* `Bash(*)`
* `Bash(uv run:*)`
* broad test permissions
* full eval permission
* ingestion permission
* API-key command permission

Do not add `Write` unless the reviewed command's purpose explicitly requires creating files and the review report specifically says `Write` is missing.

Do not add `Edit` unless the reviewed command's purpose explicitly requires editing files and the review report specifically says `Edit` is missing.

If fixing frontmatter:

* opening delimiter must be exactly `---`
* no blank line after the opening delimiter
* closing delimiter must be exactly `---`
* quote YAML values when they contain `: `
* keep `allowed-tools` as narrow as possible

If fixing input handling:

* prefer deterministic rules
* stop on missing files
* stop on ambiguous matches
* do not guess
* do not broaden searches beyond the command's intended scope

If fixing output/report behavior:

* preserve old reports
* avoid overwriting existing reports
* use collision-safe filenames when applicable
* ensure final response reports the selected path

## Step 6. Validate the command-file diff

Run only:

```powershell
git status --short
git diff -- <target-command-file>
git diff --stat -- <target-command-file>
```

If the target command file is untracked, `git diff` may show no output. That is expected.

Do not run tests.

Do not run full eval.

Do not run `ingestion.py`.

Do not run API-key-requiring commands.

Do not commit.

Do not create or switch branches.

## Step 7. Final response

Report:

* review report path
* target command file
* whether edits were applied
* fixes applied
* fixes skipped and why
* confirmation that only the target command file was modified
* confirmation that no code, tests, eval files, README, roadmap files, `CLAUDE.md`, prompts, model names, corpus documents, `.env`, or `.env.example` were modified
* `git status --short`
* `git diff --stat -- <target-command-file>`

Then recommend the next step:

`/review-command /<target-command-name>`

Do not commit.
