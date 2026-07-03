---
description: Implement an existing spec or implementation plan
argument-hint: Path to spec or plan file, for example docs/roadmap/plan/eval-history-delta-reporting-plan.md
allowed-tools: Read, Write, Edit, Glob, Grep, Bash(git status:*), Bash(git diff:*), Bash(mkdir:*), Bash(uv run ruff:*), Bash(uv run mypy:*), Bash(uv run python -m mypy:*), Bash(uv run pytest tests/node:*), Bash(uv run python -m pytest tests/node:*), Bash(uv run pytest tests/graph:*), Bash(uv run python -m pytest tests/graph:*), Bash(uv run pytest tests/evals:*), Bash(uv run python -m pytest tests/evals:*), Bash(uv run pytest tests/office_agent:*), Bash(uv run python -m pytest tests/office_agent:*), Bash(uv run python evals/run_eval.py --validate-only:*), mcp__docs-langchain__search_docs_by_lang_chain, mcp__docs-langchain__query_docs_filesystem_docs_by_lang_chain
---

You are implementing an existing spec or implementation plan for this Agentic RAG project.

User input: $ARGUMENTS

Implement only the requested scope.

Use as few tools as possible.

Do not create or switch git branches.

Do not commit automatically.

## Step 0. Validate input

If `$ARGUMENTS` is empty, stop before reading any files and ask the user to
provide an exact spec or implementation-plan path:

`Please provide a spec or implementation plan path.`

Do not let an empty argument fall through to the generic file-not-found path in
Step 3.

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

## Optional LangChain Docs MCP documentation check

This step is conditional. Use it only when the implementation depends on current external documentation. Do this before editing code.

If the implementation depends on current LangChain / LangGraph / LangSmith / langchain-mcp-adapters / MCP integration behavior (for example LangChain retrievers, tools, document loaders, vector stores, OpenAI/Chroma/Tavily integration through LangChain, or other version-sensitive ecosystem APIs), consult the installed LangChain Docs MCP server (`mcp__docs-langchain__search_docs_by_lang_chain` / `mcp__docs-langchain__query_docs_filesystem_docs_by_lang_chain`) before editing code.

* Keep the documentation query narrow and tied to the specific API or integration being implemented.
* Use docs to avoid stale API usage, deprecated imports, outdated LangGraph patterns, or incorrect LangChain integration assumptions.
* Do not paste large documentation dumps into code, comments, reports, or final responses. Summarize only the relevant API assumptions or constraints.
* If LangChain Docs MCP is unavailable, fails, or returns no relevant docs, continue without blocking and mention that external docs were unavailable or not consulted.
* Do not use LangChain Docs MCP for project-local rules already covered by `CLAUDE.md`, source code, tests, evals, or roadmap docs.
* Do not let LangChain Docs MCP override local project contracts. Project-local sources remain authoritative.

If LangChain Docs MCP is consulted while implementing, briefly mention it in the final response, for example:

`External docs consulted: LangChain Docs MCP, <library/topic>`

Do not dump raw MCP output, and do not mention LangChain Docs MCP if it was not used.

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
* Preserve the Office Agent's deterministic design: keep routing deterministic
  keyword-based, keep the local mock capabilities LLM-free and free of external
  services, keep the mock data read-only, keep simulated actions from mutating the
  repository's `office_agent/mock_data/` files, and keep the Knowledge Q&A adapter
  boundary with `enterprise_rag` intact.

## Step 8. Validate

Run only validation commands approved by the plan or spec.

Usually safe commands are:

Run each keys-free suite as its own command so each matches its own scoped
`allowed-tools` permission (do not combine test directories into one `pytest`
invocation — the permission match then depends on which directory appears first):

```powershell
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest tests/node/ -q
uv run pytest tests/graph/ -q
uv run pytest tests/evals/ -q
uv run pytest tests/office_agent/ -q
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

Then choose a collision-safe report path. Before writing, use `Glob` (or an
equivalent permitted existence check) to select the first unused path in this
order:

* `docs/roadmap/implementation/<feature-slug>-implementation-report.md`
* `docs/roadmap/implementation/<feature-slug>-implementation-report-2.md`
* `docs/roadmap/implementation/<feature-slug>-implementation-report-3.md`
* continue incrementing the numeric suffix until an unused path is found

Do not overwrite an existing implementation report. Write only to the selected
unused path, and use that exact selected path in the Step 10 final response.

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
* Implementation report path, if created (the exact collision-safe path selected in Step 9).
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
