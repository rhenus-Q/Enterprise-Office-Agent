---
description: Create an implementation plan from an existing spec
argument-hint: Path to spec file, for example docs/roadmap/spec/eval-history-delta-reporting.md
allowed-tools: Read, Write, Glob, Bash(git status:*), Bash(mkdir:*)
---

You are creating an implementation plan from an existing spec for this Agentic RAG project.

User input: $ARGUMENTS

Create a plan only. Do not implement the feature.

Use as few tools as possible.

Do not create or switch git branches.

Do not commit automatically.

## Required locations

Spec files live under:

`docs/roadmap/spec/`

Plan files live under:

`docs/roadmap/plan/`

Plan template:

`docs/roadmap/plan/plan-template.md`

Generated plan files should use this format:

`docs/roadmap/plan/<feature-slug>-plan.md`

## Step 1. Minimal project context

Read only these files first:

* `CLAUDE.md`
* `docs/roadmap/plan/plan-template.md`

Then read the spec file from `$ARGUMENTS`.

If `docs/roadmap/plan/plan-template.md` does not exist, stop and tell the user:

`Missing docs/roadmap/plan/plan-template.md. Please create the plan template first.`

If the spec file from `$ARGUMENTS` does not exist, stop and tell the user:

`Spec file not found. Please provide a valid spec path.`

Do not invent a replacement template or spec.

## Step 2. Check working tree

Run:

```powershell
git status --short
```

If the working tree has unrelated uncommitted changes, warn the user.

Do not modify application code.

It is okay to create the new plan file if the only intended change is under:

`docs/roadmap/plan/`

## Step 3. Parse the spec path

From `$ARGUMENTS`, infer:

### source_spec_path

The spec file path.

Example:

`docs/roadmap/spec/eval-history-delta-reporting.md`

### feature_slug

Infer the slug from the spec filename.

Rules:

* Remove `.md`.
* If the filename ends with `-spec`, remove that suffix.
* Keep lowercase kebab-case.
* Only `a-z`, `0-9`, and `-`.
* Maximum length: 40 characters if a new slug must be generated.

Example:

`eval-history-delta-reporting`

### feature_title

Infer the title from the spec heading if possible.

Example:

`Eval History and Delta Reporting`

If you cannot infer a sensible title and slug, ask the user to clarify instead of guessing.

## Step 4. Create the plan file

Create the directory if needed:

`docs/roadmap/plan/`

Create:

`docs/roadmap/plan/<feature_slug>-plan.md`

Use `docs/roadmap/plan/plan-template.md` as the exact structure.

Fill the template with project-specific implementation planning based on:

* `CLAUDE.md`
* The source spec
* Any directly relevant project files that the spec itself says must be inspected

Read extra project files only when needed.

Do not perform broad architecture review unless the spec asks for it.

The plan must be detailed enough for a later implementation agent to execute safely.

The plan must include:

* Spec summary.
* Current system understanding.
* Files to inspect during implementation.
* Proposed implementation steps.
* Files expected to change.
* Files that should not change.
* Safety constraints.
* Validation plan.
* Acceptance criteria.
* Risks and calibration notes.
* Recommended implementation prompt.
* Final report format.

## Safety rules

Do not implement the feature.

Do not modify application code.

Do not modify graph code.

Do not modify eval rows.

Do not modify the eval runner.

Do not modify tests.

Do not modify prompts.

Do not modify model names.

Do not modify corpus documents.

Do not modify `.env` or `.env.example`.

Do not run full eval.

Do not run `ingestion.py`.

Do not run `tests/chains/`.

Do not run API-key-requiring commands.

Do not commit.

Do not create or switch branches.

## Step 5. Final response

After the plan file is saved, respond in this exact format:

Plan file: `docs/roadmap/plan/<feature_slug>-plan.md`

Source spec: `<source_spec_path>`

Title: `<feature_title>`

Do not repeat the full plan in chat unless the user explicitly asks to see it.
