---
description: Review failure handling, cost/budget controls, and production-readiness risks and write a timestamped failure-mode review report
argument-hint: Optional review focus, for example "web search failures" or "budget limits"
allowed-tools: Read, Write, Glob, Grep, Bash(git status:*), Bash(date:*)
---

You are reviewing failure modes, failure handling, cost/budget controls, and production-readiness risks in this Agentic RAG project.

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

Review whether the current project handles failures safely and predictably enough for a portfolio-grade Agentic RAG / LangGraph system.

This review should cover:

* failure handling
* retry and loop behavior
* stop_reason correctness
* fallback policy behavior
* privacy-mode failure behavior
* LLM cost and budget controls
* web search budget controls
* web result grading budget controls
* external dependency failure behavior
* degraded-mode behavior
* production-readiness risks
* failure-related test coverage

Write a new failure-mode review report under:

`docs/roadmap/failure-modes-review/`

Do not overwrite previous failure-mode review reports.

## Report filename rule

Create a unique report filename using this format:

`docs/roadmap/failure-modes-review/<YYYY-MM-DD>-<focus-slug>-failure-modes-review.md`

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

* `/failure-modes-review` writes to something like:
  `docs/roadmap/failure-modes-review/2026-06-24-overall-failure-modes-review.md`

* `/failure-modes-review web search failures` writes to something like:
  `docs/roadmap/failure-modes-review/2026-06-24-web-search-failures-failure-modes-review.md`

* `/failure-modes-review budget limits` writes to something like:
  `docs/roadmap/failure-modes-review/2026-06-24-budget-limits-failure-modes-review.md`

* `/failure-modes-review ??` and `/failure-modes-review !!!` sanitize to an empty slug, so they use `overall`:
  `docs/roadmap/failure-modes-review/2026-06-24-overall-failure-modes-review.md`

Before writing, select the report path by checking candidate paths for existence in order and using the first candidate that does not already exist:

1. the base filename `docs/roadmap/failure-modes-review/<YYYY-MM-DD>-<focus-slug>-failure-modes-review.md`
2. then `docs/roadmap/failure-modes-review/<YYYY-MM-DD>-<focus-slug>-failure-modes-review-2.md`
3. then `docs/roadmap/failure-modes-review/<YYYY-MM-DD>-<focus-slug>-failure-modes-review-3.md`
4. continue incrementing the numeric suffix until a candidate path does not exist

Check each candidate with `Glob` or an equivalent path-existence check before selecting it.

Do not overwrite any existing failure-mode review report.

Use `Write` only for the selected unique report file.

Do not write any other file.

If the user provides a focus in `$ARGUMENTS`, prioritize that focus while still checking the overall failure-handling and budget-control posture.

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

Then inspect only failure-mode-relevant files.

Prefer targeted reads over broad file reading.

## Step 2. Inspect failure-mode-relevant areas

Inspect these areas as needed.

### Runtime and configuration

* `graph/engine.py`
* `graph/config.py`
* `graph/consts.py`
* `graph/state.py`
* `graph/graph.py`
* `graph/formatting.py`

### Graph routing and loop behavior

* `graph/graph.py`
* `graph/nodes/`
* `graph/chains/`

### Key node failure boundaries

* `graph/nodes/retrieve.py`
* `graph/nodes/grade_documents.py`
* `graph/nodes/generate.py`
* `graph/nodes/web_search.py`
* `graph/nodes/rewrite_query.py`
* `graph/nodes/add_grounding_feedback.py`
* `graph/nodes/clear_transient_tool_error.py`
* `graph/nodes/*notice*.py`

### Eval and tests

* `evals/run_eval.py`
* `evals/questions.jsonl`
* `evals/README.md`
* `tests/node/`
* `tests/graph/`
* `tests/evals/`

Inspect `tests/chains/` only if needed to assess failure-related test coverage.

Do not run `tests/chains/`.

### Tooling and CI

* `pyproject.toml`
* `.github/workflows/ci.yml`
* `.github/workflows/CI.yml`
* `.gitignore`
* `.claude/commands/`

Do not inspect `.env`.

Do not run `ingestion.py`.

Do not run API-key-requiring commands.

Do not inspect generated runtime artifacts unless needed.

## Step 3. Review failure handling quality

Evaluate the following areas.

### Failure-mode map

* What can fail in this system?
* Are LLM failures handled?
* Are retriever/vector-store failures handled?
* Are web search failures handled?
* Are grader failures handled?
* Are query rewriter failures handled?
* Are trace-write failures handled?
* Are eval/reporting failures isolated from runtime behavior?
* Does the system degrade safely instead of crashing where appropriate?

### Stop reason correctness

* Are stop reasons explicit and consistent?
* Does each major failure path set the correct `stop_reason`?
* Are terminal notice nodes clear and intentional?
* Does formatting surface stop reasons accurately to users?
* Are stale or transient stop reasons cleared only when safe?
* Are stop reasons testable and covered by tests?
* Are stop reasons stable enough for eval expectations and future automation?

### Retry and loop safety

* Are retry loops bounded?
* Are hallucination retries bounded?
* Are usefulness retries bounded?
* Are rewrite-query loops bounded?
* Are graph cycles understandable?
* Can any path loop forever?
* Are max retry terminal paths clear?
* Are retry counters incremented consistently?
* Does retry feedback change the next generation attempt meaningfully?

### Cost and budget controls

* Are LLM call budgets enforced?
* Are web search budgets enforced?
* Are web result grading budgets enforced?
* Are budget limits centralized in config?
* Are budget defaults safe?
* Are invalid budget environment variables handled safely?
* Is `tracked_llm_calls` clearly documented as an operational counter rather than total billing?
* Can expensive paths accidentally run too many LLM/tool calls?
* Are budget-exhausted paths clear and user-visible?
* Are budget-related behaviors tested?

### External dependency failures

* If OpenAI/LLM calls fail, does the system return a safe result?
* If Chroma/vector store retrieval fails, does the system avoid crashing?
* If Tavily/web search fails, does the system preserve local results when possible?
* If graders fail, does the system avoid trusting unverified content?
* If query rewriting fails, does the system fall back safely?
* If trace writing fails, does the answer still return?
* Are exception logs careful not to print sensitive messages?
* Are dependency failures represented accurately in `stop_reason`?

### Web fallback and degraded mode

* Are fallback policies clear?
* Is conservative fallback behavior understandable?
* Is aggressive fallback behavior, if present, controlled?
* Is disabled fallback behavior explicit?
* Does privacy mode prevent outbound web search even when fallback is requested?
* Does the system produce an honest insufficient-context answer when it cannot safely continue?
* Are local documents preserved when web search fails?
* Are unverified web results excluded from generation?

### Privacy and security-related failure behavior

* If user input contains secrets, are they redacted before failure paths can log or persist them?
* If web search is disabled, is the privacy guarantee preserved under all failure paths?
* If a tool fails, can raw user input, raw documents, or secrets leak through logs/traces?
* Are trace and observability failures safe?
* Are exception messages intentionally limited?

### Production readiness

* Is the project safe to continue building on without accumulating fragile failure paths?
* Are failure behaviors documented clearly enough?
* Are operational counters sufficient for debugging?
* Are CI checks enough to prevent regressions in failure handling?
* Are generated artifacts and runtime outputs controlled?
* Is the demo robust enough to show to a hiring manager or senior engineer?
* Are production-like risks acknowledged without pretending the project is fully production-hardened?

### Failure-related test coverage

* Are mocked node tests covering failure paths?
* Are graph tests covering terminal notice paths?
* Are eval tests covering stop_reason and fallback behavior?
* Are budget-exhausted paths tested?
* Are privacy-mode failure paths tested?
* Are web search failure paths tested?
* Are generation failure paths tested?
* Are retriever failure paths tested?
* Are grader failure paths tested?
* Are trace-write failure paths tested?
* Are there missing regression tests for recent failure-handling changes?

## Step 4. Look for risks and improvement opportunities

Flag:

* failure paths that crash instead of degrading safely
* silent failures with no `stop_reason`
* stale `stop_reason` values that survive successful recovery
* failure paths that overwrite useful previous context
* unbounded loops
* retry counters that are inconsistent
* budget counters that do not match actual expensive operations
* web search or grading paths that can exceed configured limits
* fallback-policy confusion
* privacy-mode bypasses
* exception messages that may leak paths, prompts, raw documents, or secrets
* observability that is too weak to debug failures
* tests that only cover happy paths
* production-readiness gaps that could cause fragile demos
* documentation that overstates reliability

Do not rewrite the architecture.

Do not implement fixes.

Only review and recommend.

## Step 5. Write failure-mode review report

Create the directory if needed:

`docs/roadmap/failure-modes-review/`

Create a new unique report file using the filename rule above.

Do not overwrite an existing failure-mode review report.

Use this structure:

# Failure Modes Review

Status: Review

Date: <YYYY-MM-DD>

Focus: <user input or "Overall failure modes">

Report file: <selected unique report path>

## 1. Executive summary

State whether the failure-handling posture is:

* Strong / portfolio-ready
* Good but needs minor cleanup
* Needs significant improvement

Give a short explanation.

## 2. Files reviewed

List the files and directories reviewed.

## 3. Failure-mode map

Briefly describe the current system failure boundaries:

* User input boundary
* Graph routing boundary
* Local retrieval boundary
* Document grading boundary
* Generation boundary
* Hallucination/usefulness grading boundary
* Web search boundary
* Query rewrite boundary
* Budget boundary
* Trace/observability boundary
* Eval/test boundary

## 4. What is strong

List the strongest failure-handling, budget-control, and degraded-mode choices.

## 5. Main issues found

For each issue include:

* Issue
* Why it matters
* Risk level: Low / Medium / High
* Recommended fix
* Whether it should be done now or later

## 6. Stop reason review

Assess:

* stop_reason coverage
* terminal notice nodes
* stale stop_reason cleanup
* formatting behavior
* eval/test stability
* whether stop_reason semantics are consistent enough for future automation

## 7. Retry and loop review

Assess:

* graph cycles
* max retry behavior
* retry counters
* grounding retry behavior
* usefulness retry behavior
* query rewriting retry behavior
* whether any path could loop indefinitely

## 8. Cost and budget review

Assess:

* LLM call budgets
* web search budgets
* web result grading budgets
* config defaults
* invalid environment handling
* budget-exhausted behavior
* tracked counter accuracy
* whether expensive paths are bounded

## 9. External dependency failure review

Assess:

* LLM failure handling
* retriever/vector-store failure handling
* web search failure handling
* grader failure handling
* query rewriter failure handling
* trace write failure handling
* exception logging safety

## 10. Web fallback and degraded-mode review

Assess:

* conservative fallback
* aggressive fallback if present
* disabled fallback
* privacy-mode interaction
* local document preservation
* insufficient-context behavior
* failed web search behavior
* unverified web result exclusion

## 11. Production readiness review

Assess:

* operational robustness
* CI safety
* import-time side effects
* generated artifact hygiene
* observability usefulness
* documentation accuracy
* whether failure-handling gaps should be fixed before adding more features

## 12. Failure-related test coverage review

Assess:

* node failure tests
* graph terminal-path tests
* eval stop_reason tests
* budget tests
* privacy-mode tests
* web-search-failure tests
* generation-failure tests
* retriever-failure tests
* grader-failure tests
* trace-write-failure tests
* missing tests
* risky tests

## 13. Documentation and workflow review

Assess:

* README
* structure.md
* CLAUDE.md
* eval docs
* Claude commands
* whether failure behavior, budgets, and degraded modes are documented clearly

## 14. Recommended next actions

Separate recommendations into:

### Must fix

### Should fix soon

### Optional improvements

## 15. Failure-readiness verdict

Give one of:

* Failure-ready for portfolio use
* Failure-ready after minor cleanup
* Not failure-ready yet

Explain why.

## 16. Overall recommendation

Do not restate the executive summary or the failure-readiness verdict here.

Instead, give a short, action-oriented recommendation that answers:

* Is the failure-handling posture safe to continue building on?
* Is cleanup needed before adding more features?
* What is the single next recommended action?

## Step 6. Final response

After writing the report, respond with:

Failure-mode review report: `<selected unique report path>`

Overall recommendation: `<overall recommendation>`

Top issues:

* <issue 1>
* <issue 2>
* <issue 3>

Do not repeat the full report in chat unless the user explicitly asks.
