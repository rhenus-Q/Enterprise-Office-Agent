# Testing Strategy

This repository is validated by a **fully mocked, CI-safe** test suite plus a
key-gated integration layer and a separate behavioral eval harness. The guiding
principle: the default test run must be **deterministic and require no API keys or
network**, so anyone (and CI) can validate the repository offline.

## Test suites at a glance

| Suite | Scope | External calls |
|---|---|---|
| [`tests/node/`](../../tests/node/) | Each `enterprise_rag` node's in/out behavior, the web-result relevance gate, defensive parsing, and graceful degradation | None — every dependency mocked at its lazy `get_*()` seam |
| [`tests/graph/`](../../tests/graph/) | The routing functions, privacy toggle, stop reasons, budgets/counters, caveat formatting, and compiled-graph end-to-end runs | None — fully mocked |
| [`tests/evals/`](../../tests/evals/) | The eval harness's pure helpers (dataset validation, per-row checks, metrics, rendering) | None — pure functions |
| [`tests/office_agent/`](../../tests/office_agent/) | The Office Agent: router, engine dispatch, and each mock tool | None — fully mocked/deterministic; Knowledge adapter patched |
| [`tests/chains/`](../../tests/chains/) | The six LCEL chains against the real `gpt-5-mini` | **Real OpenAI API** — gated by the `requires_openai` marker |

## Unit tests

Unit tests target the **lazy seam** — every external client is constructed inside
a lazy factory (`@lru_cache def get_x()`), so tests patch that factory with
`monkeypatch` instead of the real client. This keeps imports side-effect-free and
makes each node/tool testable in isolation with no keys and no network.

## Office Agent tool tests

Each Office Agent tool (`email`, `calendar`, `tickets`, `briefing`, `meeting`,
`approvals`, and the `knowledge` adapter) has fully mocked, deterministic tests in
`tests/office_agent/`. Because the mock tools read static JSON anchored to the
data (not the system clock), their output is identical on every run, so tests
assert exact rendered content rather than fuzzy matches.

## Router tests

The router is pure keyword matching, so its tests are exhaustive and
deterministic: they assert that representative requests classify to the expected
intent and that **precedence** holds (e.g. an `APR-<n>` / approval request routes
to `workflow_approval` before ticket/task; meeting-prep phrasing routes to
`meeting_agent` before the broad calendar keywords; unsupported requests fall to
`unknown`).

## Engine dispatch tests

Dispatch tests verify that `answer_office_request()` routes each intent to exactly
one tool and builds a uniform `OfficeAgentResponse` with the routed intent
attached. The Knowledge Q&A path is tested with the `enterprise_rag` adapter
**patched** — the real graph is never invoked from the Office Agent suite.

## Mock-data no-mutation tests

Because simulated actions (task creation, approve/reject) must never mutate the
repo mock data, the Office Agent tests assert **no mutation**:
`handle_approval_request` and the pure `build_simulated_*` helpers compute results
in the response only. The optional `record_decision(..., persist_path=...)` seam
is exercised against a caller-provided path (pytest's `tmp_path`), never the
repo's `mock_data/` files.

## CI-safe design

- **Imports are side-effect-free** — importing any module constructs no external
  client and needs no keys.
- **External clients are lazy** (`@lru_cache`), so tests patch one well-known seam.
- **Mock data is deterministic** — anchored to the data, not the wall clock.
- CI ([`.github/workflows/ci.yml`](../../.github/workflows/ci.yml)) runs two
  parallel keys-free jobs: **`mocked-tests`** (the fully mocked suites) and
  **`lint`** (`ruff check`, `ruff format --check`, scoped `mypy`).

## Avoiding external calls

- **Node/graph/eval/office_agent tests never call OpenAI, Tavily, Chroma, or
  embeddings.** They pass with no API keys.
- **Do not** introduce a real network call into these suites. If a new capability
  needs an external dependency, put it behind a lazy factory and patch that seam.
- The only suite that calls real services is `tests/chains/`, which is gated by
  the `requires_openai` marker and excluded from CI. **Do not run it without
  explicit approval.**

## Full-suite validation

```powershell
# Fully mocked suites — NO API keys required
uv run pytest tests/node/ tests/graph/ tests/evals/ tests/office_agent/ -v

# Whole suite (chains/ integration tests skip without OPENAI_API_KEY)
uv run pytest -v
```

The v1.6 baseline: **137 passed** in `tests/office_agent/` and **592 passed**
across the full suite (chains/ skipped without keys).

## When evals are relevant — and when they are not

The behavioral eval harness in [`evals/`](../../evals/) is **separate from the
test suites**. It runs a 24-row dataset through the **real** `enterprise_rag`
compiled graph (`enterprise_rag.graph.engine.answer_question()`) and scores
deterministic checks (stop reasons, source provenance, counters, expected
substrings, fallback-policy echoes).

- **Relevant** when you change `enterprise_rag` behavior (routing, prompts,
  grading, fallback policy) and want to measure the effect on answer quality.
- **Not relevant** for Office Agent work or docs/docstring changes — those do not
  touch the RAG graph. The Office Agent is validated by `tests/office_agent/`.
- The full eval run needs real API keys and is **excluded from CI**. **Never run
  the full eval without explicit approval**; `evals/enterprise_rag/run_eval.py --validate-only`
  checks the dataset with no API calls and is safe.

## Recommended pre-PR commands

```powershell
git status --short
git diff --check
uv run pytest tests/office_agent/ -v      # Office Agent work
uv run pytest -v                          # broader changes
uv run ruff check .
uv run ruff format --check .
uv run mypy
```
