---
description: Create a spec file from a short idea
argument-hint: Short feature description
allowed-tools: Read, Write, Glob, Bash(git status:*), Bash(mkdir:*), mcp__docs-langchain__search_docs_by_lang_chain, mcp__docs-langchain__query_docs_filesystem_docs_by_lang_chain
---

You are creating a new spec document for this Agentic RAG project.

User input: $ARGUMENTS

Create a spec only. Do not implement the feature.

Use as few tools as possible.

## Required locations

Spec template:

`docs/roadmap/spec/spec-template.md`

Generated spec files:

`docs/roadmap/spec/<feature_slug>.md`

Do not create or switch git branches.

## Step 1. Minimal project context

Read only these files first:

* `CLAUDE.md`
* `docs/roadmap/spec/spec-template.md`

If `docs/roadmap/spec/spec-template.md` does not exist, stop and tell the user:

`Missing docs/roadmap/spec/spec-template.md. Please create the spec template first.`

Do not invent a replacement template.

## Step 2. Check working tree

Run:

```powershell
git status --short
```

If the working tree has unrelated uncommitted changes, warn the user.

Do not modify application code.

It is okay to create the new spec file if the only intended change is under:

`docs/roadmap/spec/`

## Step 3. Parse the user input

From `$ARGUMENTS`, infer:

### feature_title

A short human-readable title in Title Case.

Example:

`Eval History and Delta Reporting`

### feature_slug

A safe filename slug.

Rules:

* Lowercase.
* Kebab-case.
* Only `a-z`, `0-9`, and `-`.
* Replace spaces and punctuation with `-`.
* Collapse multiple `-` into one.
* Trim `-` from the start and end.
* Maximum length: 40 characters.

Example:

`eval-history-delta-reporting`

If you cannot infer a sensible title and slug, ask the user to clarify instead of guessing.

## Optional LangChain Docs MCP documentation check

This step is optional and applies only when the requested spec depends on **current
external** LangChain ecosystem documentation. It is available via the installed LangChain
Docs MCP server (`mcp__docs-langchain__search_docs_by_lang_chain`,
`mcp__docs-langchain__query_docs_filesystem_docs_by_lang_chain`).

Use the LangChain Docs MCP server only when the requested spec depends on current external
docs for one of: LangChain, LangGraph, LangSmith, LangChain retrievers, tools, document
loaders, or vector stores, LangChain / OpenAI integration patterns, `langchain-mcp-adapters`,
or MCP-related LangChain integration behavior.

When you do consult it:

* Keep the documentation query narrow and tied to the requested feature.
* Do not paste large documentation dumps into the spec.
* Summarize only the relevant API assumptions, constraints, or version-sensitive behavior.
* If the LangChain Docs MCP server is unavailable, errors, or returns no relevant docs,
  continue without blocking and note that external docs were unavailable or not consulted.

Do **not** use the LangChain Docs MCP server for project-local rules already covered by
`CLAUDE.md`, source code, tests, existing specs/plans/implementation reports, or roadmap docs.
This includes local architecture rules, local graph behavior, local eval dataset rules, local
command-workflow rules, local roadmap conventions, local test expectations, and prose- or
comments-only changes.

Project-local sources remain authoritative. The LangChain Docs MCP server may inform external
API details, but must not override project-local contracts (`CLAUDE.md`, source code, tests,
existing specs/plans/implementation reports, README / roadmap docs).

If — and only if — you consulted the LangChain Docs MCP server, add a small note in the most
appropriate existing section of the generated spec (e.g. an assumptions / references section),
such as:

`External docs consulted: LangChain Docs MCP, <library/topic>`

Do not add a large new section, and do not dump raw MCP output. Do not mention the LangChain
Docs MCP server in the spec if it was not used.

## Step 4. Create the spec file

Create the directory if needed:

`docs/roadmap/spec/`

Before writing, check whether the target spec file already exists. Use `Glob` (or an
equivalent path-existence check) on:

`docs/roadmap/spec/<feature_slug>.md`

If that file already exists, do not overwrite it. Stop and ask the user whether to:

* revise the existing spec at that path, or
* create a new spec under a different `feature_slug`.

Do not silently overwrite an existing spec.

Only once the target path is confirmed unused (or the user explicitly chooses a path), create:

`docs/roadmap/spec/<feature_slug>.md`

Use `docs/roadmap/spec/spec-template.md` as the exact structure.

Fill the template with project-specific details.

The spec must be detailed enough for a later implementation agent to execute safely.

The spec must include:

* Summary.
* Background / current behavior.
* Goals.
* Non-goals.
* Files to inspect.
* Proposed changes.
* Implementation plan.
* Safety constraints.
* Validation plan.
* Acceptance criteria.
* Risks and calibration notes.
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

Do not run `tests/enterprise_rag/chains/`.

Do not run API-key-requiring commands.

Do not commit.

Do not create or switch branches.

## Step 5. Final response

After the spec file is saved, respond in this exact format:

Spec file: `docs/roadmap/spec/<feature_slug>.md`

Title: `<feature_title>`

Do not repeat the full spec in chat unless the user explicitly asks to see it.
