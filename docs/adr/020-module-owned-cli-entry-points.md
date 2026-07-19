# ADR 020: Module-owned interactive CLI entry points

Status: Accepted

Date: 2026-07-18

Scope: **Repository-wide** — this decision governs the `enterprise_rag` and
`office_agent` command-line entry points, the repository-root `main.py`
Office Agent entry point, and the future repository-level API/frontend
architecture, so the ADR lives at `docs/adr/` rather than under either module's
ADR directory (the second repository-level ADR, beside
[ADR 019](019-hierarchical-runtime-privacy-modes.md)).

## Context

The repository is organized as named capability modules
([ADR 014](enterprise_rag/014-enterprise-rag-package-and-office-agent-placeholder.md)):
`enterprise_rag/` owns the completed RAG engine and `office_agent/` owns the
deterministic Office Agent. But the interactive surface did not follow that
boundary:

- The only interactive CLI was the repository-root `main.py`. It owned the
  Enterprise RAG Q&A loop directly (banners, input loop, answer formatting) and
  additionally re-exported the presentation names from
  `enterprise_rag/graph/formatting.py` so that `from main import …` kept
  working — a surface eight test files depended on, and which
  [ADR 014](enterprise_rag/014-enterprise-rag-package-and-office-agent-placeholder.md)
  recorded as a compatibility decision. This coupled the root entry point to
  the RAG engine's internals and required `["F401", "E402"]` Ruff ignores for
  the re-exports-after-`load_dotenv()` pattern.
- The Office Agent had **no** interactive CLI at all. Its only runnable surface
  was the scripted demo `scripts/demo_office_agent_v1.py` (fixed requests, not
  interactive), even though `office_agent.engine.answer_office_request()` is a
  single, thin entry point already carrying everything a CLI needs
  (`intent`, `content`, `tool`, `stop_reason`, `sources`, `run_id`).

The repository is also headed toward a service/UI layer (an HTTP API and a
frontend) over the two engines. That layer needs a clean per-module entry-point
story to build on, and the root `main.py` owning RAG logic while the Office
Agent had no entry point of its own was the wrong foundation. The repository is
named **Enterprise-Office-Agent**, so the Office Agent — not the RAG engine — is
the product-level default that the repository-level entry point should launch.

## Decision

Give each implemented module its own interactive CLI, and make the root entry
point launch the product-level default (the Office Agent CLI). No engine
behavior changes.

### 1. `enterprise_rag/cli.py` owns the Enterprise RAG CLI

The Enterprise RAG interactive loop moved verbatim from `main.py` into
`enterprise_rag/cli.py`: the same title, the same three mutually exclusive
banners (`OFFLINE_MODE` → `PRIVACY_MODE` → `WEB_SEARCH_ENABLED=false`, byte-for-byte
wording), the same input loop over
`enterprise_rag.graph.engine.answer_question()`, the same
`format_answer(result.raw_state)` output and `exit`/`quit`/`q` behavior.
`load_dotenv()` and `enforce_tracing_privacy()` moved from module-import time
into the first two statements of `main()`, making `import enterprise_rag.cli`
side-effect-free — consistent with the repository's side-effect-free-import rule
and behavior-equivalent because all env consumers read lazily at call time and
the graph never runs before `main()`. Runnable as `uv run python -m enterprise_rag.cli`.

### 2. `office_agent/cli.py` owns the Office Agent CLI

A new interactive CLI over `answer_office_request()` displays the routed intent,
the selected tool, the response content, and the carried-through observability
fields (stop reason, sources, run id) only when set. It duplicates no router or
tool logic — it is a pure presentation layer over the single entry point — and
imports nothing from `enterprise_rag`, preserving Office Agent module
independence (tracing privacy on the Knowledge Q&A path is already enforced
per-run inside `answer_question()`). It reconfigures stdout to UTF-8 like the
demo script, since the deterministic mock output contains em-dashes that would
crash a cp1252 Windows console. Runnable as `uv run python -m office_agent.cli`.

### 3. `main.py` is the repository-level Office Agent entry point; the re-export surface is retired

`main.py` is reduced to a docstring plus `from office_agent.cli import main` and
the `__main__` guard, so `uv run python main.py` launches the Office Agent CLI —
the same interface as `uv run python -m office_agent.cli`. This is an
**intentional behavior change**: the previous `main.py` ran the Enterprise RAG
CLI, and root `main.py` no longer runs or forwards to RAG. Enterprise RAG remains
fully accessible through its own module-owned CLI
(`uv run python -m enterprise_rag.cli`). The resulting command ownership is:

- `uv run python main.py` → the Office Agent interactive CLI (product default).
- `uv run python -m office_agent.cli` → the same Office Agent interactive CLI.
- `uv run python -m enterprise_rag.cli` → the standalone Enterprise RAG CLI.

`main.py` imports nothing from `enterprise_rag`. The `from main import …`
presentation re-exports are **retired** as an explicitly documented compatibility
transition: every in-repo consumer (eight test files) is migrated in the same
change to import from the canonical `enterprise_rag.graph.formatting`. This is
safe because the project is an unpackaged application
(`[tool.uv] package = false`) with no external import consumers. The now-unneeded
`"main.py"` Ruff per-file-ignore is removed; `enterprise_rag/cli.py` is added to
the mypy `files` list.

### 4. Future target architecture (direction only — not implemented here)

The intended next layer, to be specified separately after this refactor, is a
service/UI tier over the two engines:

- `api/main.py` — the API application entry point.
- `api/routes/rag.py` — HTTP routes over `answer_question()`.
- `api/routes/office.py` — HTTP routes over `answer_office_request()`.
- `frontend/` — the user-facing web frontend.

This ADR records that direction so the entry-point layering is understood, but
API implementation, frontend implementation, deployment, and even the creation
of empty `api/` or `frontend/` placeholder directories are **explicit non-goals**
of this decision; each will receive its own spec.

## Consequences

- Each module owns its interactive surface: the entry-point layer now mirrors
  the `enterprise_rag` / `office_agent` module boundary, and the Office Agent is
  interactively runnable for the first time.
- The repository-level entry point matches the product: `uv run python main.py`
  launches the Office Agent (the repo's named product), not the RAG engine.
  `main.py` no longer couples the root to RAG internals; it imports only
  `office_agent.cli`, and the special-case Ruff ignores for it are gone.
- **Behavior change for existing users.** `uv run python main.py` previously
  opened the Enterprise RAG Q&A prompt; it now opens the Office Agent prompt.
  Users who want the RAG CLI run `uv run python -m enterprise_rag.cli`.
- Formatting names have a single canonical import path
  (`enterprise_rag.graph.formatting`); the `from main import …` indirection that
  [ADR 014](enterprise_rag/014-enterprise-rag-package-and-office-agent-placeholder.md)
  introduced is retired, and ADR 014 carries a one-line pointer here.
- The future API/frontend layer has a clean, documented pair of per-module entry
  points to build on.

## Trade-offs

- **A compatibility surface is removed.** `from main import …` no longer works.
  Accepted deliberately: the project is an unpackaged application, the only
  in-repo users were tests (migrated in the same change), and the canonical
  path is clearer. External cached imports of `main`'s re-exports (unlikely)
  would break.
- **One behavior-equivalent structural change.** Moving `load_dotenv()` /
  `enforce_tracing_privacy()` into `main()` is equivalent only because all env
  reads are lazy; the reasoning is documented in the module so a future edit
  doesn't reintroduce an import-time side effect.
- **A second CLI to maintain.** The Office CLI adds a small presentation surface,
  but it holds no routing or tool logic (pure pass-through over the engine
  response), so drift risk is low.

## Alternatives considered

- **Leave the RAG CLI in `main.py` and only add the Office CLI** — rejected:
  keeps the root coupled to RAG internals and the `from main import …` surface,
  and leaves the entry-point layer asymmetric with the module boundary.
- **Keep `main.py` forwarding to the RAG CLI** — rejected: the repository's named
  product is the Office Agent, so the repository-level entry point should launch
  it; the RAG CLI stays fully available at `uv run python -m enterprise_rag.cli`.
  The behavior change is intentional and accepted.
- **Keep the `from main import …` re-exports on the forwarder** — rejected:
  the indirection has no remaining consumer once the tests are migrated, and a
  single canonical import path is clearer; the softer transition was available
  as a fallback but was not needed.
- **Create the `api/` and `frontend/` directories now as placeholders** —
  rejected: out of scope. This refactor is about the CLI layer; empty
  placeholder directories would be dead weight ahead of their own specs.
- **File this ADR under `docs/adr/enterprise_rag/`** — rejected: the decision
  governs both packages' CLIs, the root Office Agent entry point, and the future
  repo-level API/frontend architecture, so it is repository-wide and belongs at
  the `docs/adr/` root beside ADR 019.
