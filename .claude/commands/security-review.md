---
description: Review security, prompt-injection, and privacy risks and write a timestamped security review report
argument-hint: Optional review focus, for example "prompt injection" or "web search privacy"
allowed-tools: Read, Write, Glob, Grep, Bash(git status:*), Bash(date:*)
---

You are reviewing the security, prompt-injection, and privacy posture of this Agentic RAG project.

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

Do not run tests.

Do not run `tests/chains/`.

Do not run API-key-requiring commands.

Do not commit.

Do not create or switch branches.

Use as few tools as possible.

## Goal

Review whether the current project is secure enough for a portfolio-grade Agentic RAG / LangGraph system, with special attention to:

* prompt injection
* untrusted retrieved context
* web search privacy
* user input secret handling
* trace/log safety
* `.env` and secret hygiene
* RAG document safety
* tool-call boundaries
* security-related test coverage
* production-like privacy risks

Write a new security review report under:

`docs/roadmap/security-review/`

Do not overwrite previous security review reports.

## Report filename rule

Create a unique report filename using this format:

`docs/roadmap/security-review/<YYYY-MM-DD>-<focus-slug>-security-review.md`

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

* `/security-review` writes to something like:
  `docs/roadmap/security-review/2026-06-24-overall-security-review.md`

* `/security-review prompt injection` writes to something like:
  `docs/roadmap/security-review/2026-06-24-prompt-injection-security-review.md`

* `/security-review web search privacy` writes to something like:
  `docs/roadmap/security-review/2026-06-24-web-search-privacy-security-review.md`

* `/security-review ??` and `/security-review !!!` sanitize to an empty slug, so they use `overall`:
  `docs/roadmap/security-review/2026-06-24-overall-security-review.md`

Before writing, select the report path by checking candidate paths for existence in order and using the first candidate that does not already exist:

1. the base filename `docs/roadmap/security-review/<YYYY-MM-DD>-<focus-slug>-security-review.md`
2. then `docs/roadmap/security-review/<YYYY-MM-DD>-<focus-slug>-security-review-2.md`
3. then `docs/roadmap/security-review/<YYYY-MM-DD>-<focus-slug>-security-review-3.md`
4. continue incrementing the numeric suffix until a candidate path does not exist

Check each candidate with `Glob` or an equivalent path-existence check before selecting it.

Do not overwrite any existing security review report.

Use `Write` only for the selected unique report file.

Do not write any other file.

If the user provides a focus in `$ARGUMENTS`, prioritize that focus while still checking the overall security posture.

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

Then inspect only security-relevant files.

Prefer targeted reads over broad file reading.

## Step 2. Inspect security-relevant areas

Inspect these areas as needed.

### Security-sensitive runtime files

* `graph/engine.py`
* `graph/config.py`
* `graph/consts.py`
* `graph/formatting.py`
* `graph/state.py`
* `graph/graph.py`

### Prompt and chain files

* `graph/chains/generation.py`
* `graph/chains/retrieval_grader.py`
* `graph/chains/hallucination_grader.py`
* `graph/chains/answer_grader.py`
* `graph/chains/query_rewriter.py`
* `graph/chains/question_router.py`

### Node files and external boundaries

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

Inspect `tests/chains/` only if needed to assess security test coverage.

Do not run `tests/chains/`.

### Tooling and project hygiene

* `pyproject.toml`
* `.github/workflows/ci.yml`
* `.github/workflows/CI.yml`
* `.gitignore`
* `.claude/commands/`
* `ingestion.py`

Do not run `ingestion.py`.

Do not inspect `.env`.

Do not inspect `.env.example` unless needed to assess whether it contains placeholders rather than real secrets.

Do not inspect corpus documents broadly. Only inspect corpus metadata or filenames if needed for security review.

Do not inspect generated runtime artifacts unless needed.

## Step 3. Review security quality

Evaluate the following areas.

### User input secret handling

* Are user-provided secret-like values redacted before entering GraphState?
* Can API keys, tokens, passwords, or secrets reach retrievers, graders, generators, routers, query rewriters, or web search queries?
* Is the original user input stored anywhere after redaction?
* Is a safe hash used for correlation instead of storing raw input?
* Is the redaction best-effort behavior clearly documented?
* Are there obvious secret patterns missing from the redaction rules?
* Does redaction avoid breaking ordinary user questions unnecessarily?

### Prompt injection defense

* Do generation prompts clearly treat retrieved documents as untrusted context?
* Do prompts instruct the model not to follow instructions inside retrieved documents or web results?
* Are system/developer instructions separated from retrieved context?
* Are context delimiters clear enough?
* Could malicious retrieved content override the system prompt?
* Could retrieved content cause tool execution, data exfiltration, secret disclosure, or policy bypass?
* Are graders or routers vulnerable to prompt injection through user question, document text, or web result content?
* Are retry feedback and query rewriting prompts safe against malicious previous answers or documents?

### RAG document and web result safety

* Are retrieved local documents graded before generation?
* Are web search results treated as untrusted?
* Are web results relevance-graded before entering generation?
* Are ungraded or failed-grade web results excluded?
* Are web supplement documents marked clearly with metadata?
* Could web result content inject instructions into downstream generation?
* Are raw URLs/titles handled safely in sources?
* Is there any risk of mixing trusted local corpus with untrusted web content without metadata?

### Privacy and web search controls

* Is `web_search_enabled=False` a hard privacy guarantee?
* Can user input be sent to external web search when privacy mode is disabled?
* Are fallback policies separate from the global web-search privacy switch?
* Are web fallback decisions explicit and testable?
* Does secret redaction happen before outbound web queries?
* Is the search query derived safely from user input and rewritten query state?
* Are web search counts and limits enforced?
* Are privacy risks documented clearly enough?

### Trace, logging, and artifact safety

* Are trace files metadata-only?
* Are raw documents, prompts, raw graph state, user secrets, and API keys excluded from trace output?
* Are trace question previews redacted and truncated?
* Is the original question hash safe enough for correlation?
* Are trace write failures handled without exposing exception messages that might contain paths or secrets?
* Are eval history files metadata-only?
* Are generated reports safe to commit or clearly ignored when appropriate?
* Is there any direct printing of raw state, document content, prompt content, or secrets?

### `.env`, secret, and repository hygiene

* Is `.env` ignored?
* Does `.env.example` avoid real secrets?
* Are API keys avoided in committed files?
* Are vector stores, generated traces, runtime outputs, and local artifacts ignored where appropriate?
* Does CI avoid requiring real API keys by default?
* Are API clients lazy-loaded to avoid import-time secret requirements?
* Are error messages careful not to print secret values?

### Tool-call and command boundaries

* Do Claude commands use narrow tool permissions?
* Do review commands avoid modifying code unless explicitly intended?
* Are dangerous commands, full eval, ingestion, and API-key workflows blocked by default?
* Are there overly broad Bash grants?
* Are generated reports written only to intended report paths?
* Is command behavior safe if the working tree is dirty?

### Security test coverage

* Are user-input redaction behaviors tested?
* Is privacy mode tested?
* Is web-search-disabled behavior tested?
* Are prompt-injection guardrails tested at least through mocked unit tests or eval rows?
* Are trace-safety guarantees tested?
* Are failure paths tested without real API keys?
* Are tests separated so safe tests can run in CI?
* Are there missing regression tests around recent security changes?

## Step 4. Look for risks and improvement opportunities

Flag:

* raw user input reaching GraphState, LLMs, or web search
* secrets stored in AnswerResult, raw_state, trace, eval history, or reports
* prompt injection weaknesses in generation, grading, routing, or query rewriting
* untrusted web results entering generation without filtering
* privacy mode bypasses
* fallback policy confusion
* logging or trace leakage
* `.env` or generated artifact hygiene problems
* overly broad Claude command permissions
* missing security tests
* stale docs that overstate security guarantees
* areas where the project looks secure by accident rather than by design

Do not rewrite the architecture.

Do not implement fixes.

Only review and recommend.

## Step 5. Write security review report

Create the directory if needed:

`docs/roadmap/security-review/`

Create a new unique report file using the filename rule above.

Do not overwrite an existing security review report.

Use this structure:

# Security Review

Status: Review

Date: <YYYY-MM-DD>

Focus: <user input or "Overall security">

Report file: <selected unique report path>

## 1. Executive summary

State whether the security posture is:

* Strong / portfolio-ready
* Good but needs minor cleanup
* Needs significant improvement

Give a short explanation.

## 2. Files reviewed

List the files and directories reviewed.

## 3. Security map

Briefly describe the current security-relevant flow:

* User input handling
* Secret redaction
* GraphState boundary
* Local retrieval boundary
* Web search boundary
* Prompt / chain boundary
* Trace and logging boundary
* Eval and test boundary

## 4. What is strong

List the strongest security choices.

## 5. Main issues found

For each issue include:

* Issue
* Why it matters
* Risk level: Low / Medium / High
* Recommended fix
* Whether it should be done now or later

## 6. Prompt injection review

Assess:

* generation prompt
* retrieved-context treatment
* web result treatment
* grader prompts
* router prompt
* query rewriter prompt
* retry feedback path
* whether untrusted content can override trusted instructions

## 7. Privacy review

Assess:

* user input redaction
* original question storage
* web search privacy mode
* fallback policy interaction
* outbound web query safety
* trace privacy
* eval history privacy
* generated artifact privacy

## 8. Secret handling review

Assess:

* `.env`
* `.env.example`
* API key handling
* token/password redaction
* question hashing
* AnswerResult fields
* raw_state risks
* CI secret usage
* accidental commit risks

## 9. Web search and external dependency review

Assess:

* Tavily/web search boundary
* search query construction
* web result grading
* web source metadata
* failed web search behavior
* external service failure handling
* privacy implications

## 10. Trace and observability safety review

Assess:

* trace JSON contents
* metadata-only guarantees
* question preview redaction
* question hash correlation
* node_path and timing safety
* counter safety
* trace write failure behavior
* whether any observability artifact could leak secrets

## 11. Security test coverage review

Assess:

* mocked security tests
* privacy mode tests
* redaction tests
* web-search-disabled tests
* prompt-injection tests
* trace-safety tests
* missing tests
* risky tests

## 12. Documentation and workflow review

Assess:

* README
* structure.md
* CLAUDE.md
* eval docs
* Claude commands
* whether security behavior is documented clearly and not overstated

## 13. Recommended next actions

Separate recommendations into:

### Must fix

### Should fix soon

### Optional improvements

## 14. Security-readiness verdict

Give one of:

* Security-ready for portfolio use
* Security-ready after minor cleanup
* Not security-ready yet

Explain why.

## 15. Overall recommendation

Do not restate the executive summary or the security-readiness verdict here.

Instead, give a short, action-oriented recommendation that answers:

* Is the security posture safe to continue building on?
* Is cleanup needed before adding more features?
* What is the single next recommended action?

## Step 6. Final response

After writing the report, respond with:

Security review report: `<selected unique report path>`

Overall recommendation: `<overall recommendation>`

Top issues:

* <issue 1>
* <issue 2>
* <issue 3>

Do not repeat the full report in chat unless the user explicitly asks.
