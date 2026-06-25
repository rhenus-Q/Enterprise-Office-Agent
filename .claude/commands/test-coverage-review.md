---
description: Review test coverage gaps and write a timestamped test coverage review report
argument-hint: Optional review focus, for example "graph routing" or "privacy mode"
allowed-tools: Read, Write, Glob, Grep, Bash(git status:*), Bash(date:*)
---

You are reviewing test coverage for this Agentic RAG project.

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

Do not run tests.

Do not run full eval.

Do not run `ingestion.py`.

Do not run `tests/chains/`.

Do not run API-key-requiring commands.

Do not commit.

Do not create or switch branches.

Use as few tools as possible.

## Goal

Review whether the current project has enough test coverage for a portfolio-grade Agentic RAG / LangGraph system.

This review should focus on coverage gaps, regression risks, and missing tests around important behavior.

This review should cover:

* node test coverage
* graph routing test coverage
* eval harness test coverage
* failure-path test coverage
* privacy-mode test coverage
* fallback-policy test coverage
* budget-limit test coverage
* stop_reason test coverage
* trace/observability test coverage
* security-related test coverage
* documentation/test alignment
* risky untested seams

Write a new test coverage review report under:

`docs/roadmap/test-coverage-review/`

Do not overwrite previous test coverage review reports.

## Report filename rule

Create a unique report filename using this format:

`docs/roadmap/test-coverage-review/<YYYY-MM-DD>-<focus-slug>-test-coverage-review.md`

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

* `/test-coverage-review` writes to something like:
  `docs/roadmap/test-coverage-review/2026-06-24-overall-test-coverage-review.md`

* `/test-coverage-review graph routing` writes to something like:
  `docs/roadmap/test-coverage-review/2026-06-24-graph-routing-test-coverage-review.md`

* `/test-coverage-review privacy mode` writes to something like:
  `docs/roadmap/test-coverage-review/2026-06-24-privacy-mode-test-coverage-review.md`

* `/test-coverage-review ??` and `/test-coverage-review !!!` sanitize to an empty slug, so they use `overall`:
  `docs/roadmap/test-coverage-review/2026-06-24-overall-test-coverage-review.md`

Before writing, select the report path by checking candidate paths for existence in order and using the first candidate that does not already exist:

1. the base filename `docs/roadmap/test-coverage-review/<YYYY-MM-DD>-<focus-slug>-test-coverage-review.md`
2. then `docs/roadmap/test-coverage-review/<YYYY-MM-DD>-<focus-slug>-test-coverage-review-2.md`
3. then `docs/roadmap/test-coverage-review/<YYYY-MM-DD>-<focus-slug>-test-coverage-review-3.md`
4. continue incrementing the numeric suffix until a candidate path does not exist

Check each candidate with `Glob` or an equivalent path-existence check before selecting it.

Do not overwrite any existing test coverage review report.

Use `Write` only for the selected unique report file.

Do not write any other file.

If the user provides a focus in `$ARGUMENTS`, prioritize that focus while still checking the overall test coverage posture.

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

Then inspect only test-coverage-relevant files.

Prefer targeted reads over broad file reading.

## Step 2. Inspect test-coverage-relevant areas

Inspect these areas as needed.

Use discovery first, then targeted reads.

Do not assume exact implementation filenames. Use `Glob` to discover the actual project layout before reading files.

Read only files that are relevant to the requested focus and to test coverage review.

### Runtime and architecture areas

First use `Glob` to discover relevant runtime files under:

* `graph/*.py`
* `graph/nodes/*.py`
* `graph/chains/*.py`

Then inspect only the relevant existing files.

Prioritize files that define or affect:

* graph construction and routing
* runtime state
* constants and `stop_reason` values
* configuration and budget policy
* engine entry points
* answer formatting and source rendering
* observability and trace behavior
* node behavior
* chain / prompt boundaries
* structured output schemas
* retry behavior
* privacy-mode behavior
* failure paths

Do not fail or waste time if a likely file is absent. Use the discovered `graph/` file list as the source of truth.

### Eval system

First use `Glob` to discover relevant eval files under:

* `evals/*`
* `evals/**/*.py`
* `evals/**/*.jsonl`
* `evals/**/*.md`

Then inspect only the relevant existing files.

Prioritize eval files that define or document:

* eval schema validation
* expected output checks
* `expected_contains`
* OR-group semantics
* `expected_not_contains`
* `expected_web_search_count`
* `expected_stop_reason`
* `expected_min_local_sources`
* history records
* delta reporting
* validate-only behavior
* markdown reporting

Do not run full eval.

### Test directories

First use `Glob` to discover relevant test files under:

* `tests/node/**/*.py`
* `tests/graph/**/*.py`
* `tests/evals/**/*.py`

Then inspect only the test files relevant to the requested focus and to coverage-gap analysis.

Prioritize tests that cover:

* node behavior
* graph routing
* eval harness behavior
* engine behavior
* config behavior
* privacy mode
* fallback policies
* budget limits
* `stop_reason` behavior
* trace / observability behavior
* failure paths
* recent security or redaction changes

Inspect `tests/chains/` only if the user explicitly asks.

Do not run `tests/chains/`.

Do not run tests.

Do not run API-key-requiring tests.

### Tooling and CI

First use `Glob` to discover relevant tooling files under:

* `.github/workflows/*`
* `.claude/commands/*`
* `*.toml`
* `*.md`
* `.gitignore`

Then inspect only the relevant existing files.

Prioritize tooling files that define or document:

* safe default test commands
* lint commands
* format checks
* type checks
* CI test jobs
* API-key-requiring test isolation
* generated artifact hygiene
* ignored runtime outputs
* command workflow expectations
* safe versus unsafe test workflows

Do not inspect `.env`.

Do not inspect generated runtime artifacts unless needed.

### Documentation

Use the already-read project docs from Step 1 as the primary documentation context.

Inspect additional documentation only when needed to verify test command accuracy, CI expectations, eval workflow, or coverage-related claims.

Do not broadly read roadmap artifacts unless they are directly relevant to the test coverage review.



## Step 3. Review test coverage quality

Evaluate the following areas.

### Node test coverage

* Are all node functions covered by mocked unit tests?
* Are node inputs and GraphState updates tested?
* Are success paths tested?
* Are failure paths tested?
* Are stop_reason updates tested?
* Are counters tested where nodes update counters?
* Are privacy, fallback, and budget-related fields tested?
* Are notice nodes tested?
* Are transient error cleanup behaviors tested?

### Graph routing coverage

* Are major graph routes covered?
* Are conditional routing decisions tested?
* Are terminal paths tested?
* Are retry loops tested?
* Are max-retry paths tested?
* Are insufficient-context paths tested?
* Are web-search-disabled paths tested?
* Are fallback-disabled paths tested?
* Are budget-exhausted paths tested?
* Are graph tests isolated from real API calls?

### Chain seam coverage

* Are chains separated from nodes enough to mock LLM behavior?
* Are node tests using monkeypatch seams rather than real API calls?
* Are structured-output chain expectations tested safely where possible?
* Are prompt-level risks covered by review or eval rows when direct tests would require API keys?
* Are chain imports side-effect free and testable without secrets?
* Are tests/chains isolated from default CI if they require API keys?

### Engine and state coverage

* Is `seed_state()` tested?
* Is per-run config resolution tested?
* Is `AnswerOptions` dict conversion tested?
* Is `AnswerResult` construction tested?
* Is run_id generation tested?
* Is node_path/timing trace collection tested?
* Is trace write failure behavior tested?
* Is user input redaction tested?
* Is question hashing tested?
* Is raw question exclusion from runtime state tested?

### Config and budget coverage

* Are default config values tested?
* Are environment override behaviors tested?
* Are invalid environment values tested?
* Are budget defaults tested?
* Are budget override parsing rules tested?
* Are web_search_enabled and web_fallback_policy interactions tested?
* Are conservative, aggressive, and disabled fallback policies tested?
* Are budget-exhausted paths tested at graph or node level?

### Security and privacy coverage

* Are user-input secret redaction behaviors tested?
* Are API key/token/password patterns tested?
* Are privacy-mode guarantees tested?
* Are web search disabled guarantees tested?
* Are outbound web query redaction behaviors tested?
* Are trace metadata-only guarantees tested?
* Are raw document/prompt/raw_state leakage risks covered by tests or review checks?
* Are prompt-injection defenses covered by mocked tests, eval rows, or command reviews?

### Eval harness coverage

* Are eval schema validations tested?
* Are expected_contains semantics tested?
* Are OR-group semantics tested?
* Are expected_not_contains checks tested?
* Are expected_web_search_count checks tested?
* Are expected_stop_reason checks tested?
* Are expected_min_local_sources checks tested?
* Are history record and delta calculations tested?
* Are validate-only paths tested?
* Are reporting functions tested without running full eval?

### CI and safe default coverage

* Does CI run the safe mocked tests?
* Does CI avoid API-key-requiring tests by default?
* Are lint, formatting, type-checking, and safe tests wired correctly?
* Are test commands documented and consistent with CLAUDE.md?
* Are generated results/history artifacts kept out of accidental commits where appropriate?

### Coverage gap quality

* Are missing tests prioritized by risk?
* Are recommendations specific enough to implement?
* Are gaps separated into Must fix, Should fix soon, and Optional?
* Are proposed tests scoped to the right layer: node, graph, eval, engine, config, or docs?
* Are recommendations careful not to demand brittle tests that lock implementation details unnecessarily?

## Step 4. Look for risks and improvement opportunities

Flag:

* important behavior with no test coverage
* critical failure paths tested only by accident
* tests that only cover happy paths
* graph routing not covered by tests
* stop_reason semantics not locked by tests
* budget behavior not covered
* privacy mode not covered
* user input redaction not covered
* trace safety not covered
* eval harness behavior not covered
* fragile or over-specific tests
* tests that require API keys in safe/default workflows
* mismatches between docs, CI, and actual tests
* generated artifacts that tests may accidentally rely on
* missing regression tests for recent changes

Do not rewrite the architecture.

Do not implement tests.

Do not modify code.

Only review and recommend.

## Step 5. Write test coverage review report

Create the directory if needed:

`docs/roadmap/test-coverage-review/`

Create a new unique report file using the filename rule above.

Do not overwrite an existing test coverage review report.

Use this structure:

# Test Coverage Review

Status: Review

Date: <YYYY-MM-DD>

Focus: <user input or "Overall test coverage">

Report file: <selected unique report path>

## 1. Executive summary

State whether the test coverage posture is:

* Strong / portfolio-ready
* Good but needs minor cleanup
* Needs significant improvement

Give a short explanation.

## 2. Files reviewed

List the files and directories reviewed.

## 3. Test coverage map

Briefly describe the current test architecture:

* Node tests
* Graph tests
* Eval tests
* Chain tests if relevant
* Engine/config tests
* CI test commands
* Safe versus API-key-requiring workflows

## 4. What is strong

List the strongest test coverage choices.

## 5. Main coverage gaps

For each gap include:

* Gap
* Why it matters
* Risk level: Low / Medium / High
* Recommended test
* Suggested test layer: node / graph / eval / engine / config / docs
* Whether it should be done now or later

## 6. Node test coverage review

Assess:

* retrieve
* grade_documents
* generate
* web_search
* rewrite_query
* notice nodes
* transient error cleanup
* node-level failure paths
* state update expectations

## 7. Graph routing test coverage review

Assess:

* conditional edges
* terminal paths
* retry loops
* web fallback paths
* privacy-mode paths
* budget-exhausted paths
* max-retry paths
* insufficient-context paths

## 8. Engine/config/observability test coverage review

Assess:

* seed_state
* AnswerOptions
* AnswerResult
* per-run config resolution
* runtime input redaction
* question hashing
* trace collection
* trace JSON safety
* trace write failure behavior
* config defaults and environment overrides

## 9. Security and privacy test coverage review

Assess:

* secret redaction tests
* privacy mode tests
* web-search-disabled tests
* outbound web query safety
* prompt-injection related tests or eval rows
* trace/log safety tests
* raw input/raw_state risks

## 10. Budget and failure-path test coverage review

Assess:

* LLM budget tests
* web search budget tests
* web result grading budget tests
* generation failure tests
* retriever failure tests
* web search failure tests
* grader failure tests
* query rewriter failure tests
* stale stop_reason cleanup tests

## 11. Eval harness test coverage review

Assess:

* eval schema validation
* expected_contains
* OR-group semantics
* expected_not_contains
* expected_web_search_count
* expected_stop_reason
* expected_min_local_sources
* history records
* delta reporting
* validate-only
* markdown reporting

## 12. CI and safe workflow review

Assess:

* mocked test defaults
* API-key-requiring test isolation
* lint/format/typecheck coverage
* CI workflow correctness
* docs/CI/test command alignment
* generated artifact hygiene

## 13. Documentation and workflow review

Assess:

* README
* structure.md
* CLAUDE.md
* eval docs
* Claude commands
* whether test coverage expectations are documented clearly

## 14. Recommended next actions

Separate recommendations into:

### Must fix

### Should fix soon

### Optional improvements

## 15. Test-readiness verdict

Give one of:

* Test-ready for portfolio use
* Test-ready after minor cleanup
* Not test-ready yet

Explain why.

## 16. Overall recommendation

Do not restate the executive summary or the test-readiness verdict here.

Instead, give a short, action-oriented recommendation that answers:

* Is the current test posture safe to continue building on?
* Is cleanup needed before adding more features?
* What is the single next recommended test to add?

## Step 6. Final response

After writing the report, respond with:

Test coverage review report: `<selected unique report path>`

Overall recommendation: `<overall recommendation>`

Top coverage gaps:

* <gap 1>
* <gap 2>
* <gap 3>

Do not repeat the full report in chat unless the user explicitly asks.
