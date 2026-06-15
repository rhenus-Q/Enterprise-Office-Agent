---
description: Update CLAUDE.md with durable project rules from a completed change
argument-hint: Implementation report path, spec/plan path, or short feature description
allowed-tools: Read, Edit, Glob, Grep, Bash(git status:*), Bash(git diff:*)
---

You are updating `CLAUDE.md` with durable project guidance after a completed implementation.

User input: $ARGUMENTS

This is a documentation-only task.

Modify only:

`CLAUDE.md`

Use `Edit` only for `CLAUDE.md`.

Do not edit any other file.

Do not create new files.

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

Do not run `tests/chains/`.

Do not run API-key-requiring commands.

Do not commit.

Do not create or switch branches.

Use as few tools as possible.

## Goal

Update `CLAUDE.md` only if the completed change introduced durable project rules, architecture conventions, testing conventions, safety constraints, generated-file rules, or workflow rules that future Claude Code agents need to know.

Do not summarize the implementation.

Do not copy the implementation report.

Do not add temporary notes.

Do not add one-off feature details.

Do not add dates, commit history, one-time validation outputs, or completed-task summaries.

When unsure whether a rule is durable, do not update `CLAUDE.md`.

## Step 1. Validate input

If `$ARGUMENTS` is empty, stop and ask the user for one of:

* an implementation report path
* a spec path
* a plan path
* a short feature description

Do not search broadly without input.

## Step 2. Read current project memory

Read:

* `CLAUDE.md`

Then resolve the user input.

Decide whether `$ARGUMENTS` is a file path or a short feature description:

* Treat input containing a path separator (`/` or `\`) as a file path.
* Treat input ending in `.md` as a file path.
* Otherwise treat input as a short feature description.

If `$ARGUMENTS` is a file path:

* Read that file.
* If the file does not exist, stop and tell the user:
  `File not found. Provide a valid report/spec/plan path or a short feature description.`
* Do not improvise after a failed read.
* Do not search broadly after a missing explicit path.

If `$ARGUMENTS` is a short feature description, search only under:

* `docs/roadmap/spec/`
* `docs/roadmap/plan/`
* `docs/roadmap/implementation/`
* `docs/roadmap/architecture-review/`
* `docs/roadmap/commands-review/`

Do not search the whole repo.

Then resolve the match:

* If exactly one clearly relevant file is found, read it.
* If several roadmap files are equally relevant, stop and list the candidate paths, then ask the user to rerun with the exact path. Do not guess.
* If no relevant file is found, stop and say no matching roadmap file was found.

Read only the relevant files.

Do not read unrelated project files unless needed to avoid an incorrect `CLAUDE.md` update.

## Step 3. Decide whether CLAUDE.md should change

Before editing, decide whether the change introduced any long-lived rules.

Good candidates for `CLAUDE.md`:

* Durable architecture boundaries.
* Safety constraints future agents must obey.
* Testing or validation conventions.
* Generated-file or gitignore conventions.
* Public contracts that should not be broken.
* Project-specific workflow rules.
* Canonical entry points.
* Tool permissions or command workflow rules.
* Eval or history conventions that affect future development.

Bad candidates for `CLAUDE.md`:

* One-off implementation details.
* Temporary notes.
* Full test output.
* Full implementation report summaries.
* Dates or commit history.
* Feature-specific trivia that future agents do not need.
* Anything already clearly covered in `CLAUDE.md`.

If no durable rule is needed, do not edit `CLAUDE.md`.

## Step 4. Edit CLAUDE.md carefully

If an update is needed:

* Modify only `CLAUDE.md`.
* Keep the update concise.
* Add the guidance to the most relevant existing section.
* Preserve the existing structure and tone.
* Prefer short bullets over long paragraphs.
* Avoid duplicating existing rules.
* Do not turn `CLAUDE.md` into a changelog.
* Do not mention completed-task history unless it expresses a durable rule.
* When editing `CLAUDE.md`, do not alter descriptions of graph routing, graph nodes, `stop_reason` semantics, privacy mode, or fallback-policy semantics unless the source change actually changed them.

Examples of acceptable durable guidance:

* "`evals/history/*.json` is generated at runtime and should stay gitignored; only `.gitkeep` is tracked by default."
* "`graph/engine.py::answer_question()` is the canonical runtime entry point."
* "`GraphState` channels are expected to remain last-value channels unless `_run_graph_with_trace` is redesigned."
* "Claude command files under `.claude/commands/` must keep narrow `allowed-tools` and avoid broad `Bash(uv run:*)` grants."

Examples of unacceptable guidance:

* "On 2026-06-13, Phase 3D was implemented."
* "378 tests passed."
* "Architecture review said the project is portfolio-ready."
* "The implementation report was written to a specific path."

## Step 5. Validate the documentation diff

Run:

```powershell
git status --short
git diff -- CLAUDE.md
git diff --stat -- CLAUDE.md
```

Do not run tests.

Do not run full eval.

Do not run `ingestion.py`.

Do not run API-key-requiring commands.

Do not commit.

Do not create or switch branches.

## Step 6. Final response

Report in this fixed format:

CLAUDE.md updated: `<yes / no>`

Durable rules added: `<short description of the rules added, or "none — <why no update was needed>">`

Confirm: no code, tests, eval files, README, or roadmap files were changed.

Then include:

* `git status --short`
* `git diff --stat -- CLAUDE.md`

Do not commit.
