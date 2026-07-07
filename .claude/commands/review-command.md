---
description: Review a Claude Code command file for correctness, safety, and project fit
argument-hint: Command path or command name, for example .claude/commands/arch-review.md or /arch-review
allowed-tools: Read, Write, Glob, Grep, Bash(git status:*), Bash(mkdir:*), Bash(powershell.exe:*)
---

You are reviewing a Claude Code command file for this Agentic RAG project.

User input: $ARGUMENTS

This is a review-only task.

Do not modify the command file.

Do not modify `CLAUDE.md`.

Do not modify application code.

Do not modify tests.

Do not modify eval files.

Do not modify README.

Do not modify roadmap files except for writing the command review report.

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

Review whether the target Claude Code command is correct, safe, useful, and consistent with this project's command workflow.

The review should check:

* Claude Code frontmatter correctness
* tool permission safety
* input handling
* output/report behavior
* file-write behavior
* safety constraints
* token discipline
* consistency with existing commands
* whether the command fits this Agentic RAG project

Write a new command review report under:

`docs/roadmap/commands-review/`

Do not overwrite previous command review reports.

## Step 0. Determine the authoritative date and time

Before the first report write, run this command exactly once:

    powershell.exe -NoProfile -Command "Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz'"

Treat the returned timestamp as the only authoritative current local time, and reuse that same value throughout this run. Use its `YYYY-MM-DD` portion consistently for the report filename, the report title, the `Date:` / metadata field, and any generated-date text in the body. Never infer or guess the date from model knowledge, conversation history, Git history, existing reports, or existing filenames, and never copy the date from an existing report. If the command fails, stop and report the failure; do not write a report with a guessed date.

## Step 1. Validate and resolve input

If `$ARGUMENTS` is empty, stop and ask the user for a command path or command name.

Accepted input formats:

* `.claude/commands/arch-review.md`
* `.claude/commands/update-claude-md.md`
* `/arch-review`
* `/arch-review.md`
* `/update-claude-md`
* `/update-claude-md.md`
* `arch-review`
* `arch-review.md`
* `update-claude-md`
* `update-claude-md.md`

Resolve the target command path using this order:

1. Trim whitespace from the input.
2. If the input starts with `/`, remove the leading `/`.
3. If the normalized input contains a directory separator (`/`), treat it as an explicit path as-is.
4. Otherwise, resolve it under `.claude/commands/` as a bare command name.
5. If the resolved path does not end with `.md`, append `.md`.

This ensures `/arch-review.md`, `arch-review.md`, `/arch-review`, and `arch-review` all resolve cleanly to `.claude/commands/arch-review.md` without relying on close-match fallback.

If the resolved command file does not exist, use `Glob` under `.claude/commands/` to look for close matches.

If exactly one close match is found, use it.

If multiple close matches are found, stop and list the candidate command files. Ask the user to rerun with the exact command path or exact command name. Do not guess.

If no matching command file is found, stop and report the missing file.

Do not search outside `.claude/commands/` for command files.

## Step 2. Read minimal context

Read:

* `CLAUDE.md`
* the target command file

Then read relevant peer commands for consistency.

Prefer reading only these peer commands if they exist:

* `.claude/commands/review-diff.md`
* `.claude/commands/implement-spec.md`
* `.claude/commands/arch-review.md`
* `.claude/commands/update-claude-md.md`
* `.claude/commands/new-spec.md`
* `.claude/commands/plan-spec.md`

Do not read unrelated project files unless needed to avoid an incorrect review.

Run only:

```powershell
git status --short
```

Do not run tests.

## Step 3. Determine review report path

Create the directory if needed:

`docs/roadmap/commands-review/`

Create a unique report filename using this format:

`docs/roadmap/commands-review/<YYYY-MM-DD>-<command-slug>-command-review.md`

Where:

* `<YYYY-MM-DD>` is the verified date from Step 0.
* `<command-slug>` is the command file name without `.md`.
* Convert the command name to lowercase and keep only letters, numbers, and hyphens where possible.

Examples:

* `/arch-review` writes to something like:
  `docs/roadmap/commands-review/2026-06-13-arch-review-command-review.md`

* `/update-claude-md` writes to something like:
  `docs/roadmap/commands-review/2026-06-13-update-claude-md-command-review.md`

Before writing, use `Glob` to check whether the target report path already exists.

If the target report already exists, do not overwrite it. Instead check each candidate path in order and choose the first unused path:

* `docs/roadmap/commands-review/<YYYY-MM-DD>-<command-slug>-command-review.md`
* `docs/roadmap/commands-review/<YYYY-MM-DD>-<command-slug>-command-review-2.md`
* `docs/roadmap/commands-review/<YYYY-MM-DD>-<command-slug>-command-review-3.md`
* continue until an unused filename is found

Use `Write` only for the selected unique command review report.

Do not write any other file.

## Step 4. Review frontmatter and permissions

Check whether the target command has:

* valid Claude Code frontmatter
* standard `---` opening and closing delimiter
* no blank or malformed frontmatter delimiter
* appropriate `description`
* useful `argument-hint`
* safe `allowed-tools`
* no overly broad Bash permissions
* no unnecessary `Write`
* no unnecessary `Edit`
* no unnecessary `MultiEdit`
* no unnecessary test runner permissions
* no full eval permission unless explicitly required and safe
* no ingestion/API-key command permission
* no broad `Bash(*)`
* no broad `Bash(uv run:*)`

For each allowed tool, decide whether it is necessary for the command's purpose.

Flag unused or risky permissions.

## Step 5. Review command scope and safety

Check whether the command clearly says what it may modify.

Review whether it protects:

* application code
* tests
* eval files
* prompts
* model names
* corpus documents
* `.env` / `.env.example`
* graph behavior
* graph routing
* graph nodes
* `stop_reason` semantics
* fallback policy semantics
* full eval
* `ingestion.py`
* `tests/enterprise_rag/chains/`
* API-key-requiring commands
* commits
* branch creation or switching

For artifact-producing commands, check whether `Write` usage is restricted in prose to the intended output file or directory.

For editing commands, check whether `Edit` usage is restricted in prose to the intended file.

For review-only commands, check that the command cannot modify the thing it is reviewing.

## Step 6. Review input handling

Check whether the command handles:

* empty `$ARGUMENTS`
* file path input
* short description input
* command name input
* missing files
* ambiguous matches
* repeated runs
* existing report/output-file collisions

Flag ambiguity that could cause:

* reading too broadly
* writing to the wrong path
* overwriting previous reports
* modifying unrelated files
* wasting tokens

## Step 7. Review output behavior

Check whether the command's output behavior is appropriate.

For commands that create reports, check:

* output directory
* filename convention
* collision handling
* whether old reports are preserved
* whether final response uses the selected report path

For commands that edit files, check:

* whether the target file is explicit
* whether the command avoids creating unrelated files
* whether validation diff is scoped to the target file

For commands that implement code, check:

* whether report generation is separated from implementation
* whether validation commands are appropriate
* whether forbidden operations are blocked

## Step 8. Review project fit

Assess whether the command fits this Agentic RAG project.

Check consistency with:

* `/new-spec`
* `/plan-spec`
* `/implement-spec`
* `/review-diff`
* `/arch-review`
* `/update-claude-md`
* existing roadmap directory structure
* `CLAUDE.md` rules
* project safety constraints

Look for:

* inconsistent path conventions
* inconsistent final response format
* inconsistent safety wording
* unnecessary template usage
* over-engineering
* under-specified behavior
* risk of turning docs into noisy process artifacts

## Step 9. Write review report

Create the selected unique report file.

Use this structure:

# Claude Command Review

Status: Review

Date: <YYYY-MM-DD>

Target command: `<target command path>`

Report file: `<selected unique report path>`

## 1. Executive summary

Say whether the command is:

* Ready to use
* Ready after minor fixes
* Not ready

Give a short explanation.

## 2. Files reviewed

List files reviewed.

## 3. Frontmatter and permission review

Assess frontmatter correctness and allowed-tools safety.

## 4. Scope and safety review

Assess what the command can modify and whether it protects project-critical areas.

## 5. Input handling review

Assess how the command handles arguments, missing files, ambiguity, and repeated runs.

## 6. Output behavior review

Assess whether output files, report files, or edits are correctly scoped and collision-safe.

## 7. Project fit and consistency review

Compare with existing Claude Code commands and project rules.

## 8. Problems found

For each problem include:

* Issue
* Why it matters
* Risk level: Low / Medium / High
* Recommended fix

## 9. Recommended fixes

Separate into:

### Must fix

### Should fix soon

### Optional improvements

## 10. Final verdict

Give one of:

* Ready to use
* Ready after minor fixes
* Not ready

## Step 10. Final response

After writing the report, respond with:

Review report: `<selected unique report path>`

Target command: `<target command path>`

Verdict: `<Ready to use / Ready after minor fixes / Not ready>`

Top issues:

* <issue 1>
* <issue 2>
* <issue 3>

Do not repeat the full report in chat unless asked.
