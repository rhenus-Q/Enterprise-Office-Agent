# Evals

This directory holds behavioral evaluation harnesses, organized by the module
each one evaluates. The mocked test suites (`tests/`) prove the *code paths*
work; these harnesses measure whether the system *behaves* well against realistic
inputs. Each subdirectory is self-contained and owns its own dataset, runner,
report, and README.

| Area | Evaluates | Full run needs |
|---|---|---|
| [`enterprise_rag/`](enterprise_rag/README.md) | The complete Enterprise RAG graph | OpenAI, Tavily, Chroma |
| [`office_agent/llm_assist/`](office_agent/llm_assist/README.md) | The two optional Office Agent LLM assists | OpenAI |

## `enterprise_rag/` — Enterprise RAG behavioral eval

Exercises the full `enterprise_rag` LangGraph workflow end to end: retrieval,
routing, privacy mode, web fallback, provenance, stop reasons, run counters,
budgets, multi-document behavior, and fallback-policy choices. A full run drives
the real router / graders / generation (OpenAI), possibly Tavily web search, and
the Chroma vector store, so it needs API keys, costs money, and is
approval-gated. `--validate-only` is keys-free and always safe.

```powershell
uv run python evals/enterprise_rag/run_eval.py --validate-only
```

See [`enterprise_rag/README.md`](enterprise_rag/README.md) for the dataset schema,
checks, history/delta reporting, and report-privacy rules.

## `office_agent/llm_assist/` — Office Agent LLM-assist evals

Evaluates **only** the two optional, default-off Office Agent LLM assists — the
Email Digest ([ADR 017](../docs/adr/office_agent/017-office-agent-llm-assist-email-digest.md))
and the Daily Briefing Narrative
([ADR 018](../docs/adr/office_agent/018-office-agent-llm-assist-daily-briefing.md)). It is
**not** an eval of all seven deterministic Office Agent capabilities — those are
covered by the mocked suites in `tests/office_agent/`. A full run calls the real
`gpt-5-mini` model (OpenAI) and is approval-gated; `--validate-only` is keys-free.

```powershell
uv run python evals/office_agent/llm_assist/run_email_digest_eval.py --validate-only
uv run python evals/office_agent/llm_assist/run_briefing_narrative_eval.py --validate-only
```

See [`office_agent/llm_assist/README.md`](office_agent/llm_assist/README.md) for
the case schemas and check rules.

## Not part of CI

No full eval runs in CI: they need real API keys, cost money, and are
nondeterministic. CI runs only the fully mocked suites. Each harness's pure
helpers are unit-tested without API calls in `tests/evals/`, and every
`--validate-only` path is safe everywhere.
