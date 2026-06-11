# Evals

A lightweight behavioral evaluation harness. The mocked test suites prove the
*code paths* work; this harness measures whether the system *behaves* well on
realistic questions: answering from the corpus, falling back to the web,
declining when it doesn't know, and honoring privacy mode.

All checks are deterministic — stop reasons, source metadata, run counters,
and expected substrings. No LLM-as-judge.

## Files

| File | Purpose |
|---|---|
| `questions.jsonl` | The eval dataset (15 rows, one JSON object per line). |
| `run_eval.py` | The runner: invokes the real graph per row, checks behavior, writes the report. |
| `results.md` | The generated report (overwritten on every run). |

## Dataset schema

Required fields per row:

- `id` — unique row identifier.
- `category` — `local_corpus` (5 rows) \| `web_fallback` (5) \| `insufficient_context` (3) \| `privacy_mode` (2).
- `question` — the user question sent to the graph.
- `web_search_enabled` — seeded into graph state per row (the same seam
  `main.py` uses); `.env` is never touched.
- `expected_behavior` — human-readable description of the expected outcome.

Optional check fields (`null`/absent = not checked):

- `expected_stop_reason` — string or list; `""` means the run must end clean.
- `expected_source_type` — `local_corpus` \| `web` \| `none`.
- `expected_contains` — case-insensitive substrings that must appear in the
  formatted answer (caveats and Sources included).
- `notes` — rationale for the row.

## Checks

Per row: stop-reason match, source-type match, expected substrings, plus an
automatic `web_search_count == 0` assertion for every `web_search_enabled=false`
row. Category rules: `web_fallback` rows must actually use a web source after
≥ 1 search; `insufficient_context` rows must decline ("do not have enough
information") or end with an explicit stop-reason caveat. A row passes when
all of its applicable checks pass.

The `insufficient_context` rows run with web search disabled on purpose: with
web enabled the graph would (correctly) answer them via web fallback, which
would test routing rather than fabrication resistance.

## Running

```powershell
# Validate the dataset only — no API calls, always safe
uv run python evals/run_eval.py --validate-only

# Full eval — REAL OpenAI (and Tavily) calls; requires keys in .env
uv run python evals/run_eval.py

# Variants
uv run python evals/run_eval.py --limit 3
uv run python evals/run_eval.py --output evals/results.md
```

## Why this is not in CI

The full run needs real API keys, costs money, and is nondeterministic
(routing/grading are model judgments; web results change daily). CI runs only
the fully mocked suites. The harness's pure helpers (loading, validation,
checks, metrics, rendering) are unit-tested in `tests/evals/` without any API
calls, and `--validate-only` is safe everywhere.
