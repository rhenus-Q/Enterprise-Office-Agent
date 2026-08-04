---
description: Evaluate whether a proposed change is justified, then implement the smallest correct change (or none) and validate it
argument-hint: The proposed task or change request, for example "add a retry cap to web search"
allowed-tools: Read, Write, Edit, Glob, Grep, Bash(git status:*), Bash(git diff:*), Bash(uv run ruff:*), Bash(uv run mypy:*), Bash(uv run python -m mypy:*), Bash(uv run pytest tests/enterprise_rag/nodes:*), Bash(uv run python -m pytest tests/enterprise_rag/nodes:*), Bash(uv run pytest tests/enterprise_rag/graph:*), Bash(uv run python -m pytest tests/enterprise_rag/graph:*), Bash(uv run pytest tests/enterprise_rag/evals:*), Bash(uv run python -m pytest tests/enterprise_rag/evals:*), Bash(uv run pytest tests/office_agent:*), Bash(uv run python -m pytest tests/office_agent:*), Bash(uv run python evals/enterprise_rag/run_eval.py --validate-only:*), mcp__docs-langchain__search_docs_by_lang_chain, mcp__docs-langchain__query_docs_filesystem_docs_by_lang_chain
---

You are evaluating a proposed change for this Agentic RAG project, then implementing it **only if the repository evidence justifies it**.

User input: $ARGUMENTS

This command formalizes one workflow: **evaluate first → decide whether a change is justified → implement only when necessary → validate the result.**

Core principle: **do not assume the proposed solution is necessary merely because it was requested.** A no-change decision is a complete, successful outcome. When action is warranted, make the smallest correct change.

Use as few tools as possible.

Do not create or switch git branches.

Do not commit automatically.

## Step 0. Validate input

If `$ARGUMENTS` is empty, stop before reading any files and ask the user to
describe the proposed change or goal:

`Please describe the change or goal you want evaluated.`

## Step 1. Read project rules

Read first:

* `CLAUDE.md`

Prefer evidence from this repository — its code, tests, ADRs, configuration, and
docs — over generic best practices.

## Step 2. Understand the request

State, in your own words:

* the underlying **problem or goal** behind the request (not just the literal
  solution proposed);
* what "solved" would look like.

If the request conflates a problem with a specific solution, separate the two.

## Step 3. Inspect the current implementation

Inspect only what is relevant to the request: the current implementation, related
tests, configuration, documentation, ADRs (`docs/adr/`), and existing
abstractions. Prefer targeted `Grep`/`Glob` and focused reads over broad sweeps.

Determine whether the current implementation **already solves the problem**. If it
does, that is strong evidence for a no-change outcome.

### Optional LangChain Docs MCP check

Only if the change depends on current LangChain / LangGraph / LangSmith / MCP
behavior, consult the LangChain Docs MCP server
(`mcp__docs-langchain__search_docs_by_lang_chain` /
`mcp__docs-langchain__query_docs_filesystem_docs_by_lang_chain`) with a narrow
query. Do not let external docs override local project contracts, and do not dump
raw MCP output. Mention it in the final report only if used.

## Step 4. Evaluate the proposed change

Assess the proposal against the current codebase for:

* correctness;
* meaningful practical value;
* architectural consistency;
* duplication of an existing abstraction;
* unnecessary complexity;
* maintenance burden;
* compatibility and public-contract impact;
* testing impact;
* documentation drift;
* security implications;
* error and failure behavior.

Then consider whether a **smaller or simpler solution** would solve the same
problem, and whether the repository already offers a more idiomatic approach.

## Step 5. Decide

Choose exactly one:

* **no change** — the problem is already solved, or the change is not justified;
* the **proposed change**;
* a **smaller alternative** that solves the same problem;
* a **different implementation** supported by stronger repository evidence.

Treat "no change" as a valid, complete result.

### If no change is justified

Make no modifications. Go straight to the final report and clearly explain the
evidence supporting the decision. This is a successful outcome.

### If a change is justified

Continue to Step 6.

## Step 6. Check working tree

Run:

```bash
git status --short
```

If the working tree has unrelated uncommitted changes, stop and ask the user
whether to continue. Do not overwrite unrelated changes.

## Step 7. Implement the smallest correct change

* Implement only what the decision requires.
* Preserve existing behavior and public contracts unless the request explicitly
  requires otherwise.
* Do not add speculative abstractions, future-proofing, dependencies, or
  configuration.
* Do not perform unrelated refactoring or cleanup.
* Update tests and documentation only where the change makes it necessary.
* Never weaken or delete tests to make a change pass.

### Default safety constraints

Unless the request explicitly approves an exception:

* Do not change prompts, model names, or corpus documents.
* Do not change graph behavior, graph routing, graph nodes, `stop_reason`
  semantics, or fallback-policy semantics.
* Do not modify `.env` or `.env.example`.
* Preserve the Office Agent's deterministic design: keep routing deterministic
  keyword-based, keep the local mock capabilities LLM-free and free of external
  services, keep the mock data read-only, keep simulated actions from mutating the
  repository's `office_agent/mock_data/` files, and keep the two optional LLM
  assists' byte-for-byte flag-off guarantee and the Knowledge Q&A adapter boundary
  with `enterprise_rag` intact.
* Do not run full eval, `ingestion.py`, `tests/enterprise_rag/chains/`,
  `tests/office_agent/integration/`, or any API-key-requiring command.
* Do not commit automatically; do not create or switch branches.

## Step 8. Validate

Run the **narrowest relevant validation first**, then expand only when justified.
Run each keys-free suite as its own command so it matches its scoped
`allowed-tools` permission:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest tests/enterprise_rag/nodes/ -q
uv run pytest tests/enterprise_rag/graph/ -q
uv run pytest tests/enterprise_rag/evals/ -q
uv run pytest tests/office_agent/ --ignore=tests/office_agent/integration -q
uv run python evals/enterprise_rag/run_eval.py --validate-only
```

Run only the suites relevant to the change. Do not run full eval, ingestion,
chain integration tests, or API-key commands unless the user separately approves.

## Step 9. Review the final diff

Inspect the diff (`git diff`, `git status --short`) and check for:

* accidental scope expansion;
* unnecessary files or abstractions;
* duplication;
* contradictions;
* regressions;
* weakened tests;
* stale or inaccurate documentation;
* security or failure-mode regressions.

If any appear, fix or revert them before reporting.

## Step 10. Ask only when necessary

Ask for confirmation only when the action is destructive, irreversible,
security-sensitive, materially ambiguous, or requires a product decision that
cannot be inferred from the repository. Otherwise decide from repository evidence
and proceed.

## Final report

Report:

* the underlying **problem or goal**;
* whether a change was **necessary** (yes / no);
* the **evidence** supporting the decision;
* the **chosen approach**;
* important **alternatives considered and rejected**;
* files **created, modified, or deleted** (or "none");
* **tests and validation** performed, and their **results**;
* remaining **risks, limitations, or unresolved ambiguity**.

Do not commit. Do not create or switch branches.
