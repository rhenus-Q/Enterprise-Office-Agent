# Office Agent LLM-assist evals

Behavioral evals for the **two optional, default-off Office Agent LLM assists**:

- the **Email Digest** ([ADR 017](../../../docs/adr/office_agent/017-office-agent-llm-assist-email-digest.md)), and
- the **Daily Briefing Narrative** ([ADR 018](../../../docs/adr/office_agent/018-office-agent-llm-assist-daily-briefing.md)).

> **Scope:** this is *not* an eval of all seven deterministic Office Agent
> capabilities. The router and every deterministic tool are covered by the mocked
> suites in `tests/office_agent/`. These harnesses exercise only the two assists'
> LLM output — grounding, reference/action-item recall, and required source-type
> coverage — against hand-labeled cases.

Each assist has its own runner, case dataset, and generated report. Both runners
share `_env.py` for `.env` loading and CONFIG / INFRA / EVAL_FAIL error
classification, so an infrastructure/provider failure is never mislabeled as a
model-quality failure.

## Files

| File | Purpose |
|---|---|
| `_env.py` | Shared env loading + error classification for both runners. |
| `run_email_digest_eval.py` | Email Digest runner: validate-only or real-model. |
| `email_digest_cases.jsonl` | Email Digest hand-labeled cases. |
| `email_digest_results.md` | Generated Email Digest report (full mode only; gitignored). |
| `run_briefing_narrative_eval.py` | Daily Briefing Narrative runner: validate-only or real-model. |
| `briefing_narrative_cases.jsonl` | Briefing Narrative hand-labeled cases. |
| `briefing_narrative_results.md` | Generated Briefing Narrative report (full mode only; gitignored). |

## Case schemas

**Email Digest** (`email_digest_cases.jsonl`), required per row:

- `id` — unique row identifier (string).
- `query` — the request whose matched emails feed the digest (string).
- `expected_action_item_email_ids` — email ids the digest must surface as action items (list).
- `must_not_invent_deadline_for` — email ids that must **not** receive a fabricated deadline (list).
- `expected_deadlines` — optional object mapping email id → substring the deadline must contain.

**Briefing Narrative** (`briefing_narrative_cases.jsonl`), required per row:

- `id` — unique row identifier (string).
- `query` — the briefing request (string).
- `expected_reference_ids` — reference ids the narrative must cite (list).
- `must_reference_source_types` — source types the narrative must cover; each one of
  `email` / `meeting` / `ticket` / `task` / `approval` (list).

## Running

```powershell
# Offline, keys-free schema validation (always safe)
uv run python evals/office_agent/llm_assist/run_email_digest_eval.py --validate-only
uv run python evals/office_agent/llm_assist/run_briefing_narrative_eval.py --validate-only

# Full, real-model runs — call gpt-5-mini; require OPENAI_API_KEY; APPROVAL-GATED
uv run python evals/office_agent/llm_assist/run_email_digest_eval.py --output evals/office_agent/llm_assist/email_digest_results.md
uv run python evals/office_agent/llm_assist/run_briefing_narrative_eval.py --output evals/office_agent/llm_assist/briefing_narrative_results.md
```

`--validate-only` loads and schema-checks the case dataset only — no `.env`, no
client, no LLM call — so it is safe anywhere. A full run requires a real
`OPENAI_API_KEY` and, like the Enterprise RAG eval, must never be run without
explicit approval. The generated `*_results.md` reports are gitignored.

## Not part of CI

Full runs need real API keys, cost money, and are nondeterministic. CI runs only
the fully mocked suites. Each runner's env loading and error classification are
covered keys-free in `tests/evals/` (`test_office_assist_env.py`,
`test_office_assist_eval_runner.py`, `test_briefing_assist_eval_runner.py`); the
gated real-model assist tests live in `tests/office_chains/`.
