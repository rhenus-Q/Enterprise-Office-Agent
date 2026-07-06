---
description: Review the project architecture and write a timestamped architecture review report
argument-hint: Optional review focus, for example "eval harness" or "graph flow"
allowed-tools: Read, Write, Glob, Grep, Bash(git status:*), Bash(mkdir:*), Bash(date:*)
---

You are reviewing the architecture of this Agentic RAG project.

User input: $ARGUMENTS

This is a review-only task.

Do not modify application code.

Do not modify tests.

Do not modify eval files.

Do not modify prompts.

Do not modify model names.

Do not modify corpus documents.

Do not modify `.env` or `.env.example`.

Do not modify graph behavior.

Do not modify graph routing.

Do not modify graph nodes.

Do not modify `stop_reason` semantics.

Do not modify fallback policy semantics.

Do not run full eval.

Do not run `ingestion.py`.

Do not run `tests/enterprise_rag/chains/`.

Do not run API-key-requiring commands.

Do not commit.

Do not create or switch branches.

Use as few tools as possible.

## Goal

Review whether the current project architecture is clean, maintainable, testable, observable, safe to continue building on, and suitable as a production-oriented Agentic RAG / LangGraph project.

This review should cover:

* architecture quality
* separation of concerns
* graph design
* configuration and side effects
* observability architecture
* production readiness
* eval architecture
* test architecture
* documentation and workflow quality

Write a new architecture review report under:

`docs/roadmap/architecture-review/`

Do not overwrite previous architecture review reports.

## Report filename rule

Create a unique report filename using this format:

`docs/roadmap/architecture-review/<YYYY-MM-DD>-<focus-slug>-architecture-review.md`

Where:

* `<YYYY-MM-DD>` is today's date.

* `<focus-slug>` is derived from `$ARGUMENTS`.

* If `$ARGUMENTS` is empty, use `overall`.

* Convert the focus to a lowercase slug:

  * trim whitespace
  * replace spaces with hyphens
  * remove quotes
  * remove characters that are unsafe for filenames
  * keep only letters, numbers, and hyphens where possible

* If `$ARGUMENTS` is not empty but sanitizing it produces an empty slug, use `overall`.

Examples:

* `/arch-review` writes to something like:
  `docs/roadmap/architecture-review/2026-06-13-overall-architecture-review.md`

* `/arch-review eval harness` writes to something like:
  `docs/roadmap/architecture-review/2026-06-13-eval-harness-architecture-review.md`

* `/arch-review graph flow` writes to something like:
  `docs/roadmap/architecture-review/2026-06-13-graph-flow-architecture-review.md`

* `/arch-review ??` and `/arch-review !!!` sanitize to an empty slug, so they use `overall`:
  `docs/roadmap/architecture-review/2026-06-13-overall-architecture-review.md`

Before writing, select the report path by checking candidate paths for existence in order and using the first candidate that does not already exist:

1. the base filename `docs/roadmap/architecture-review/<YYYY-MM-DD>-<focus-slug>-architecture-review.md`
2. then `docs/roadmap/architecture-review/<YYYY-MM-DD>-<focus-slug>-architecture-review-2.md`
3. then `docs/roadmap/architecture-review/<YYYY-MM-DD>-<focus-slug>-architecture-review-3.md`
4. continue incrementing the numeric suffix until a candidate path does not exist

Check each candidate with `Glob` or an equivalent path-existence check before selecting it.

Do not overwrite any existing architecture review report.

Use `Write` only for the selected unique report file.

Do not write any other file.

If the user provides a focus in `$ARGUMENTS`, prioritize that focus while still checking the overall architecture.

## Step 1. Read minimal project context

Read:

* `CLAUDE.md`
* `README.md`
* `structure.md`

Run:

```powershell
git status --short
```

If today's date is needed for the report filename, use a minimal date command.

Then inspect only architecture-relevant files.

Prefer targeted reads over broad file reading.

## Step 2. Inspect architecture-relevant areas

Inspect these areas as needed.

### Project entry points and configuration

* `pyproject.toml`
* `.github/workflows/ci.yml`
* `.github/workflows/CI.yml`
* `.gitignore`
* `CLAUDE.md`
* `README.md`
* `structure.md`

### Graph and runtime flow

* `graph/graph.py`
* `graph/state.py`
* `graph/consts.py`
* `graph/config.py`
* `graph/engine.py`
* `graph/formatting.py`
* `graph/nodes/`
* `graph/chains/`

### Eval system

* `evals/enterprise_rag/run_eval.py`
* `evals/enterprise_rag/questions.jsonl`
* `evals/enterprise_rag/README.md`
* `evals/enterprise_rag/history/`
* `evals/office_agent/llm_assist/`

### Tests

* `tests/enterprise_rag/nodes/`
* `tests/enterprise_rag/graph/`
* `tests/enterprise_rag/evals/`

Do not inspect `tests/enterprise_rag/chains/` unless the user explicitly asks.

### Claude command workflow

* `.claude/commands/`

Inspect roadmap artifacts only when needed for workflow review.

Do not inspect `.env`.

Do not inspect generated runtime artifacts unless needed.

## Step 3. Review architecture quality

Evaluate the following areas.

### Graph design

* Is the graph flow understandable?
* Are node responsibilities clear?
* Are routing decisions explicit?
* Are loop limits and retry behavior safe?
* Are stop reasons consistent?
* Are fallback policies clear and testable?
* Are terminal paths clear?
* Are quality gates such as document grading, hallucination grading, and answer usefulness grading placed in the right layer?

### Configuration and side effects

* Are API clients lazy-loaded?
* Are imports side-effect free where they should be?
* Is environment/config access centralized?
* Are expensive operations avoided at import time?
* Are `.env` and secrets protected?
* Can tests import modules without API keys?
* Are runtime policies resolved once per run rather than read inconsistently across nodes?

### Separation of concerns

* Is graph execution separated from formatting?
* Is eval logic separated from graph logic?
* Are node and chain responsibilities separated?
* Are nodes responsible for GraphState updates while chains handle LLM/prompt logic?
* Is persistence/history logic isolated enough?
* Are docs and tests aligned with behavior?
* Is business behavior separated from observability and reporting?

### Eval architecture

* Are eval rows expressive enough?
* Are eval checks deterministic?
* Are history and delta reporting safe and metadata-only?
* Is full eval clearly separated from safe validation?
* Are generated history files correctly ignored?
* Is `validate-only` safe?
* Are eval expectations readable and maintainable?

### Observability architecture

* Are `run_id`, `node_path`, node timings, counters, and trace outputs useful for debugging graph runs?
* Is observability additive and non-behavior-changing?
* Are trace files metadata-only?
* Are raw documents, prompts, raw graph state, user secrets, and API keys excluded from trace output?
* Are trace write failures handled safely without losing the answer?
* Are `stop_reason`, retry counters, web search counters, and grading counters sufficient to understand why a run ended?
* Are observability fields exposed in a structured way through `AnswerResult`?
* Are generated trace/debug artifacts safe to persist or share?
* Does the observability design help diagnose graph failures without making the graph harder to reason about?

### Testability

* Are important behaviors covered by mocked tests?
* Are graph/node/eval tests separated correctly?
* Are API-key-requiring tests avoided by default?
* Are there brittle tests or under-tested seams?
* Are recent features covered by unit tests?
* Are privacy mode, fallback policies, budget limits, stop reasons, and failure paths covered?
* Are monkeypatch seams clean and intentional?

### Production readiness

* Are runtime configuration, privacy controls, and fallback policies clear and centralized?
* Are LLM call budgets, web search limits, and web result grading limits enforced consistently?
* Are external dependency failures handled safely, including LLM, retriever, vector store, web search, and grading failures?
* Are import-time side effects avoided so tests and tooling can run without API keys?
* Are logs, traces, eval history, and generated reports safe for local development and CI?
* Are `.env`, secrets, generated artifacts, vector stores, and runtime outputs protected from accidental commit?
* Are CI checks sufficient for safe development without requiring paid API calls?
* Is the project easy to run, test, debug, and explain as a well-engineered system?
* Are production-like risks documented clearly enough without overengineering the system?
* Is cleanup needed before adding more features?

### Documentation quality

* Do README and structure docs match the code?
* Are command workflows documented enough?
* Are eval docs accurate?
* Are roadmap artifacts useful rather than noisy?
* Do docs explain how to run safe tests versus API-key-requiring workflows?
* Do docs clearly describe the architecture without overstating production readiness?

### Engineering quality

* Would this architecture read as credible to a senior engineer?
* Are there signs of overengineering?
* Are there signs of underengineering?
* What would make the project more production-ready?
* Is the project's design explainable in a clear technical narrative?
* Does the architecture reflect real engineering judgment rather than only prototype LLM behavior?

## Step 4. Look for risks and improvement opportunities

Flag:

* hidden coupling
* unclear ownership of logic
* duplicate logic
* overly broad tool permissions
* generated files that should be ignored
* stale docs
* fragile eval assumptions
* excessive command/template complexity
* missing tests around important behavior
* architecture that makes future features harder
* observability that leaks too much or explains too little
* production-readiness gaps that could cause fragile behavior
* places where security, privacy, fallback, budget, or stop_reason semantics are unclear

Do not rewrite the architecture.

Do not implement fixes.

Only review and recommend.

## Step 5. Write architecture review report

Create the directory if needed:

`docs/roadmap/architecture-review/`

Create a new unique report file using the filename rule above.

Do not overwrite an existing architecture review report.

Use this structure:

# Architecture Review

Status: Review

Date: <YYYY-MM-DD>

Focus: <user input or "Overall architecture">

Report file: <selected unique report path>

## 1. Executive summary

State whether the architecture is:

* Strong / production-oriented
* Good but needs minor cleanup
* Needs significant improvement

Give a short explanation.

## 2. Files reviewed

List the files and directories reviewed.

## 3. Architecture map

Briefly describe the current system architecture:

* Graph flow
* Nodes and chains
* Config/runtime setup
* Eval harness
* Test structure
* Observability structure
* Docs/workflow structure

## 4. What is strong

List the strongest architectural choices.

## 5. Main issues found

For each issue include:

* Issue
* Why it matters
* Risk level: Low / Medium / High
* Recommended fix
* Whether it should be done now or later

## 6. Project-specific safety review

Explicitly assess whether these are protected:

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

## 7. Observability architecture review

Assess:

* run_id design
* node_path visibility
* node timing usefulness
* operational counters
* trace JSON safety
* metadata-only guarantees
* trace failure behavior
* whether observability helps debug graph failures without changing behavior
* whether any observability artifact could leak raw documents, prompts, raw state, or secrets

## 8. Production readiness review

Assess:

* runtime configuration
* privacy controls
* fallback policies
* budget limits
* external dependency failure handling
* CI safety
* import-time side effects
* generated artifact hygiene
* whether the system is safe to keep building on
* whether production-readiness gaps should be fixed before adding more features

## 9. Eval architecture review

Assess:

* eval schema
* eval checks
* history records
* delta reporting
* full eval workflow
* validate-only workflow
* test coverage

## 10. Test architecture review

Assess:

* mocked tests
* graph tests
* node tests
* eval tests
* missing tests
* risky tests

## 11. Documentation and workflow review

Assess:

* README
* structure.md
* CLAUDE.md
* Claude commands
* roadmap artifacts

## 12. Recommended next actions

Separate recommendations into:

### Must fix

### Should fix soon

### Optional improvements

## 13. Engineering-readiness verdict

Give one of:

* Production-oriented
* Production-oriented after minor cleanup
* Not production-ready yet

Explain why.

## 14. Overall recommendation

Do not restate the executive summary or the engineering-readiness verdict here.

Instead, give a short, action-oriented recommendation that answers:

* Is the architecture safe to continue building on?
* Is cleanup needed before adding more features?
* What is the single next recommended action?

## Step 6. Final response

After writing the report, respond with:

Architecture review report: `<selected unique report path>`

Overall recommendation: `<overall recommendation>`

Top issues:

* <issue 1>
* <issue 2>
* <issue 3>

Do not repeat the full report in chat unless the user explicitly asks.
