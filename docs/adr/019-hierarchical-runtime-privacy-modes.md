# ADR 019: Hierarchical runtime privacy modes (`PRIVACY_MODE` / `OFFLINE_MODE`)

Status: Accepted

Date: 2026-07-18

Scope: **Repository-wide** — this decision governs `enterprise_rag`, `office_agent`,
the root entry points, tracing, ingestion, the evals, and the tests, so the ADR
lives at `docs/adr/` rather than under either module's ADR directory.

## Context

The repository accumulated one switch per external service, each with its own
default and its own parsing:

- `WEB_SEARCH_ENABLED` (default **on**) — the Tavily privacy switch ([ADR 002](enterprise_rag/002-web-search-privacy-mode.md)).
- `OFFICE_LLM_ENABLED` (default **off**) — the two optional Office LLM assists
  ([ADR 017](office_agent/017-office-agent-llm-assist-email-digest.md),
  [ADR 018](office_agent/018-office-agent-llm-assist-daily-briefing.md)).
- `LANGCHAIN_TRACING_V2` / `LANGSMITH_TRACING` — LangSmith export, which was
  explicitly **not** covered by privacy mode; `.env.example` carried a warning
  saying so.

Two operator intents were therefore impossible to express in one place:

1. *"This is a privacy-sensitive deployment"* — no data to third parties beyond
   the OpenAI calls the system fundamentally needs. An operator had to coordinate
   three variables by hand and still got LangSmith export unless they remembered
   the separate tracing flag.
2. *"This machine is offline / air-gapped"* — nothing leaves at all. Nothing
   expressed this. Every OpenAI-dependent path (Knowledge Q&A, ingestion, the
   real-model evals, the gated integration tests) would attempt a call and fail
   with an opaque connection error rather than an honest, deterministic refusal.

The second gap was the sharper one: failing with a raw network exception is not
the repo's failure convention. Every other external-dependency failure degrades
to a machine-readable `stop_reason` plus an honest user-facing caveat
([ADR 006](enterprise_rag/006-graceful-degradation.md)).

## Decision

Add two hierarchical, default-off runtime modes, each read from the environment
with strict truthy parsing (`true`/`1`/`yes`/`on`), so a typo can never activate
or deactivate a restriction.

**`PRIVACY_MODE`** — no user/document data leaves the machine except to OpenAI.
Forces off Tavily web search, LangSmith tracing, and both optional Office LLM
assists. Preserves the core OpenAI RAG path unchanged.

**`OFFLINE_MODE`** — nothing leaves the machine. Implies every `PRIVACY_MODE`
restriction and additionally disables OpenAI chat/embeddings and all other
external services.

Precedence is strict and one-directional: `OFFLINE_MODE` > `PRIVACY_MODE` >
individual flags > per-run `AnswerOptions`. **A mode can only restrict.** While a
mode is active it overrides `WEB_SEARCH_ENABLED=true`, `OFFICE_LLM_ENABLED=true`,
the tracing variables, and an explicit `AnswerOptions(web_search_enabled=True)`.

Implementation points:

- `enterprise_rag/graph/config.py` gains `privacy_mode()`, `offline_mode()`, and
  `privacy_restrictions_active()` (the "offline implies privacy" hierarchy).
  `web_search_enabled()` returns `False` whenever restrictions are active.
- `office_agent/llm_assist/config.py` gains its **own** mode readers — no
  `enterprise_rag` import, preserving that module's documented independence — and
  gates `office_llm_enabled()` on them. Both assists keep their byte-for-byte
  flag-off guarantee; a mode simply reuses that existing path.
- `enterprise_rag/graph/engine.py` applies the floor in `seed_state()`, so the
  restriction holds for **every** caller (CLI, evals, the Office adapter, direct
  `seed_state()` users) without touching the graph or the state schema.
- `enterprise_rag/runtime_privacy.py` (new) holds `enforce_tracing_privacy()`,
  which sets **both** `LANGCHAIN_TRACING_V2` and `LANGSMITH_TRACING` to `"false"`.
  It lives outside `config.py` because that module's contract is "pure env reads,
  no side effects". It is called at each entry point right after `load_dotenv()`
  (`main.py`, `enterprise_rag/ingestion.py`, the full eval runner) and per-run
  inside `answer_question()`.
- `OFFLINE_MODE` fail-closed surfaces, all deterministic and all before any client
  is constructed:
  - `answer_question()` short-circuits **before the graph**, returning a normal
    `AnswerResult` with the new additive `STOP_REASON_OFFLINE_MODE` and the
    `OFFLINE_MODE_NOTE` caveat. The Office Knowledge Q&A adapter needed **no
    change** — it already passes `stop_reason` through and renders with
    `format_answer()`.
  - `enterprise_rag/ingestion.py` refuses at the script entry (`exit 2`) and in
    `get_retriever()` (`RuntimeError`).
  - All three real-model eval runners refuse (`CONFIG ERROR`, exit 2); every
    `--validate-only` path stays keys-free and mode-free.
  - `requires_openai` skips with an explicit offline reason.

## Consequences

- One switch now expresses each operator intent, and the tracing gap that
  `.env.example` previously warned about is closed.
- Offline behavior is honest and deterministic: an explicit caveat and a
  machine-readable `stop_reason`, never a raw connection error — consistent with
  [ADR 006](enterprise_rag/006-graceful-degradation.md) and [ADR 001](enterprise_rag/001-stop-reason.md).
- `offline_mode` is an **additive** `stop_reason`. No existing stop reason,
  caveat, routing decision, node, prompt, or model name changed.
- The graph is untouched. `PRIVACY_MODE` reuses the already-supported
  `web_search_enabled=False` state path from [ADR 002](enterprise_rag/002-web-search-privacy-mode.md);
  `OFFLINE_MODE` refuses in the engine *before* the graph runs.
- The deterministic Office capabilities keep working fully offline, which makes
  the Office Agent genuinely usable on an air-gapped machine.
- Running the full RAG eval under `PRIVACY_MODE` fails its web-dependent rows by
  design. This is correct mode behavior, not a regression, and is documented
  rather than "fixed" by recalibrating rows. `OFFLINE_MODE` blocks that eval
  outright; `PRIVACY_MODE` deliberately does not.

## Trade-offs

- **Duplicated truthy parsing** in three places (`enterprise_rag` config, the
  Office assist config, `tests/conftest.py`). Deliberate: it preserves the
  documented cross-package independence and keeps test collection free of
  application imports. The literal sets are identical and covered by tests.
- **Process-global env mutation** in `enforce_tracing_privacy()`. It only ever
  writes `"false"`, only under an active mode, and is idempotent — but it is a
  side effect, which is why it lives in its own module rather than in `config.py`.
- **Declared, not detected.** The modes are asserted by the operator; the system
  never probes for actual connectivity. Fail-closed means "the code never
  initiates the call", not a sandbox — a determined caller bypassing
  `answer_question()` is out of scope.
- **`PRIVACY_MODE` still trusts OpenAI.** That is the explicit boundary of the
  tier; operators needing more must use `OFFLINE_MODE`.

## Alternatives considered

- **A single `PRIVACY_LEVEL=0|1|2` enum.** Rejected: less readable in a
  `.env` file and in code than two named booleans, and it would have made the
  "offline implies privacy" hierarchy implicit rather than explicit.
- **Process-level egress blocking (socket patching).** Rejected as out of scope
  and misleading — it would suggest a sandbox guarantee the project cannot make,
  and would break local Chroma I/O.
- **Runtime connectivity detection.** Rejected: non-deterministic, and a flaky
  probe deciding whether the system answers is worse than an explicit switch.
- **Wiring `enforce_tracing_privacy()` into the two Office assist eval runners.**
  Rejected as dead code: those runners already refuse under either mode via
  `ensure_openai_api_key()`, so no model call — and therefore no trace export —
  can occur.
- **A new graph node for the offline refusal.** Rejected: it would change graph
  routing for a case that must never reach the graph at all. The engine-level
  short-circuit keeps the graph untouched.
- **Making `OFFLINE_MODE` block the RAG eval *and* `PRIVACY_MODE` too.**
  Rejected: `PRIVACY_MODE` preserves the OpenAI path by definition, so the eval
  can legitimately run; the web-row failures are meaningful signal, not an error.
