# Release Checklist

A pre-release / pre-PR checklist for the Enterprise Office Agent. Run every
command from the repository root. Most of this checklist is **keys-free** —
matching what CI runs offline. A few validations need a real `OPENAI_API_KEY`
(Knowledge Q&A / the RAG engine, the two optional Office LLM assists, and their
gated real-model tests / full evals); those are called out explicitly and run
**only with explicit approval**.

## 1. Working-tree hygiene

```powershell
git status --short            # confirm only intended files changed
git diff --check              # no trailing whitespace / conflict markers
```

- [ ] Only intended files are modified.
- [ ] `git diff --check` is clean.

## 2. Demo (Office Agent)

```powershell
uv run python scripts/demo_office_agent_v1.py
```

- [ ] The local-only demo runs and prints the expected intents/responses (no API
  keys required).

## 3. Tests

```powershell
uv run pytest tests/office_agent/ -v      # Office Agent suite
uv run pytest -v                          # full suite (chains/ skips without keys)
```

- [ ] `tests/office_agent/` passes (fully mocked, no keys).
- [ ] Full suite passes (`tests/chains/` and `tests/office_chains/` skip without
  `OPENAI_API_KEY`).

## 3a. Office LLM-assist validation (optional, mostly key-gated)

The two assists (Email Digest, Daily Briefing Narrative) are **default-off**.
Verify the flag-off guarantee and dataset schemas offline; treat real-model
checks as approval-gated.

- [ ] With `OFFICE_LLM_ENABLED` unset/false, Email Summary and Daily Briefing
  return their byte-for-byte deterministic output (covered by
  `tests/office_agent/`, no keys).
- [ ] `.env.example` matches the code: `OFFICE_LLM_ENABLED` default-off and
  `OFFICE_LLM_REQUEST_TIMEOUT_SECONDS` default `60`.
- [ ] Both assist eval datasets validate offline (no keys):

```powershell
uv run python evals/office_agent/llm_assist/run_email_digest_eval.py --validate-only
uv run python evals/office_agent/llm_assist/run_briefing_narrative_eval.py --validate-only
```

- [ ] **Only with explicit approval and a real `OPENAI_API_KEY`:** the gated
  real-model chain tests (`uv run pytest tests/office_chains/ -v`) and the full
  assist behavioral evals (the same runners **without** `--validate-only`).

## 3b. Enterprise RAG real-model validation (key-gated)

- [ ] `uv run python evals/enterprise_rag/run_eval.py --validate-only` passes
  (keys-free).
- [ ] **Only with explicit approval and real keys:** `tests/chains/` and the full
  RAG behavioral eval.

## 4. Lint, format check, mypy

```powershell
uv run ruff check .
uv run ruff format --check .
uv run mypy
```

- [ ] `ruff check` passes.
- [ ] `ruff format --check` passes.
- [ ] `mypy` passes.

## 5. Docs consistency checks

- [ ] `README.md`, `structure.md`, `office_agent/README.md`, and the release
  notes agree on:
  - the capability count (**seven**) and the version map (below);
  - the **two optional LLM assists** (Email Digest, Daily Briefing Narrative)
    described as presentation layers, **not** additional capabilities or intents;
  - the assists being **default-off** (gated by `OFFICE_LLM_ENABLED`) with a
    deterministic fallback.
- [ ] `office_agent/README.md` still exists and is referenced from the docs
  that should link it.

```powershell
Test-Path office_agent/README.md
git grep -n "office_agent/README.md"
```

## 6. Stale version-wording checks

Each of the patterns below maps to a version-drift bug. Run each `git grep` and
expect **no output**, excluding two intentional sources: this checklist file
(which quotes the patterns as documentation) and the historical ADRs under
`docs/adr/` (which describe the original reserved-`office_agent` placeholder and
must not be rewritten). To skip those automatically, append the pathspecs shown:

```powershell
git grep -n "added in v1.5 / Phase 7"          -- ':!docs/engineering/release-checklist.md'
git grep -n "Workflow / Approval Agent.*v1.5"  -- ':!docs/engineering/release-checklist.md'
git grep -n "Phase 7.*v1.5"                    -- ':!docs/engineering/release-checklist.md'
git grep -n "office_agent.*placeholder"        -- ':!docs/engineering/release-checklist.md' ':!docs/adr/'
git grep -n "five capabilities"                -- ':!docs/engineering/release-checklist.md'
```

Version map to enforce everywhere:

| Release | Phase | Capabilities |
|---|---|---|
| v1 | Phases 1–5 | Knowledge Q&A, Email Summary, Calendar Lookup, Task / Ticket Assistant, Daily Briefing |
| v1.5 | Phase 6 | Meeting Agent / Meeting Prep |
| v1.6 | Phase 7 | Workflow / Approval Agent |

## 7. Safety / scope checks

- [ ] **No secrets** — no API keys, tokens, or `.env` contents committed.
- [ ] **No generated artifacts** — nothing under `evals/enterprise_rag/history/*.json`
  (or the gitignored `evals/office_agent/llm_assist/*_results.md`) or other
  ignored/generated paths force-added by accident.
- [ ] **No accidental `enterprise_rag` changes** — graph logic, prompts, model
  names, state schema, corpus, and eval semantics unchanged unless the release is
  specifically about them.
- [ ] **No test or mock-data changes** for a docs/refactor release.
- [ ] **No `docs/roadmap/`** or architecture-review files touched for docs-only
  work.

```powershell
git diff --name-only origin/main            # review every path in the diff
```

## 8. PR description checklist

- [ ] Summary of what changed and why.
- [ ] Scope statement — one of: **docs only**, **deterministic Office Agent
  behavior**, **optional Office Agent LLM assist**, or **Enterprise RAG behavior**.
- [ ] Validation results pasted (tests, ruff, format check, mypy, demo).
- [ ] Confirmation that `enterprise_rag`, tests, and mock data are unchanged (when
  applicable).
- [ ] Links to the relevant docs (`office_agent/README.md`, release notes).

## 9. Tag checklist (for a versioned release)

- [ ] Release notes exist under `docs/releases/` (e.g.
  `docs/releases/office-agent-v1.6.md`).
- [ ] Version map in the release notes matches the code and docs.
- [ ] The tag name matches the release (e.g. `office-agent-v1.6`).
- [ ] The tag points at the merge commit that includes the validated changes.
