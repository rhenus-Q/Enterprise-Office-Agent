# Phase 2B Dev Hygiene Plan

Status: Implemented (2026-06-12)

Date: 2026-06-12

## Context

Phases 1 and 2A gave the project a canonical engine API (`graph/engine.py`:
`answer_question()` / `AnswerOptions` / `AnswerResult`), centralized state
seeding (`seed_state()`), per-run `web_fallback_policy` resolution, and
lightweight observability (`run_id`, `node_path`, `node_timings_ms`,
`total_duration_ms`, optional metadata-only trace JSON). The safe mocked test
suite stands at **294 passing tests** (`tests/node/` + `tests/graph/` +
`tests/evals/`), enforced by CI without API keys.

Phase 2B adds development hygiene — linting (ruff), formatting (ruff format),
local hooks (pre-commit), and scoped static typing (mypy) — **without changing
any RAG behavior**: no prompts, models, corpus, routing, state schema,
stop_reason semantics, or eval questions are touched. Every diff in this phase
must be mechanical and reviewable; the 294 mocked tests are the behavioral
regression gate after each step.

## Current Tooling State

Inspected on 2026-06-12:

| Area | State |
|---|---|
| Package manager | uv (`pyproject.toml` + committed `uv.lock`, `package = false`) |
| Python floor | `requires-python = ">=3.11"`; CI pins 3.12 |
| Dev dependencies | `[dependency-groups] dev = ["pytest"]` — nothing else |
| Lint / format | **None.** No ruff, flake8, black, isort, or any config file |
| Type checking | **None.** No mypy/pyright config |
| Pre-commit | **None.** No `.pre-commit-config.yaml` |
| CI | One job (`.github/workflows/ci.yml`): `uv sync --locked --group dev` + mocked pytest. No lint/type job |
| Line endings | **No `.gitattributes`.** Windows working copies already produce `LF will be replaced by CRLF` warnings — a real churn risk for formatters/hooks |
| Pytest config | `[tool.pytest.ini_options]` in `pyproject.toml` (`pythonpath=["."]`, `testpaths=["tests"]`) |

Codebase shape (tracked files only): 53 `.py` files, ~8,900 lines.
Long lines: 35 lines > 100 chars, only 6 > 120 (mostly prose-heavy comments,
e.g. `graph/state.py` field comments).

Existing idioms the tooling must respect (deliberate, documented behavior —
not lint debt):

- `# noqa: E402` imports after `load_dotenv()` in `graph/graph.py` and
  `main.py`, and after the `sys.path` insert in `evals/run_eval.py`.
- `main.py` re-exports `graph/formatting.py` names for backward
  compatibility (already carries `# noqa: E402,F401`).
- `print()` banners are the documented console UX (`---GENERATE---` etc.) —
  do **not** enable flake8-print (`T20`).
- Broad `except Exception` at every external call site is the graceful-
  degradation contract (logs exception type only) — do **not** enable
  blind-except/raise lint families that would fight it.
- Lazy module-level `__getattr__` in `graph/chains/*` for backward-compatible
  chain names; `@lru_cache(maxsize=1)` factories everywhere.
- Typing gradient: `graph/engine.py`, `graph/config.py`, `graph/state.py`,
  `graph/consts.py` are well annotated; `graph/formatting.py` has some
  untyped parameters (`documents`, `metadata`, `result`); nodes return
  untyped partial-state dicts; tests are untyped.

## Recommendation

**Adopt the full sequence — ruff first, then pre-commit, then scoped mypy,
then CI — but land each phase as its own small commit/PR**, in this order:

1. **2B-1 Ruff** (lint, then format as a separate mechanical commit).
2. **2B-2 Pre-commit** (mirrors ruff locally + basic hygiene hooks; includes
   the `.gitattributes` line-ending fix *before* any whitespace hooks run).
3. **2B-3 Scoped mypy** (the five well-typed core modules only; not nodes,
   chains, or tests yet).
4. **2B-4 CI** (one new `lint` job; the existing `mocked-tests` job is not
   modified).

Why not "ruff only" — ruff without pre-commit reverts to "remember to run it,"
and the gap between local habit and CI enforcement is where churn commits come
from. Why not stop at "ruff + pre-commit" — the engine API is now the contract
for evals and the future workflow layer; a scoped mypy run over
`engine/config/formatting/state/consts` is cheap (those files are already
~fully annotated) and protects exactly the surface other code will build on.
Full-repo mypy is deliberately deferred (see Deferred Work).

Each phase ends with the same gate:
`uv run pytest tests/node/ tests/graph/ tests/evals/ -q` → 294 passed.

## Phase 2B-1: Ruff

Add ruff as a dev dependency and configure it in `pyproject.toml` (no separate
`ruff.toml`; the project already centralizes config there).

Proposed configuration:

```toml
[tool.ruff]
target-version = "py311"     # match requires-python, not CI's 3.12
line-length = 100

[tool.ruff.lint]
select = [
    "E4", "E7", "E9",  # pycodestyle errors (default scope)
    "F",               # pyflakes
    "W",               # pycodestyle warnings
    "I",               # isort (import sorting)
    "UP",              # pyupgrade (py311+ idioms)
    "B",               # flake8-bugbear
]
ignore = [
    "E501",            # long lines: 35 offenders, mostly prose comments; revisit later
]

[tool.ruff.lint.per-file-ignores]
"main.py" = ["F401", "E402"]            # intentional re-exports after load_dotenv()
"graph/graph.py" = ["E402"]             # imports after load_dotenv()
"evals/run_eval.py" = ["E402"]          # imports after sys.path insert
"tests/**" = ["E731"]                   # monkeypatch lambdas are the house style
```

Notes and decisions:

- **`E501` ignored initially, `line-length = 100`.** The formatter still wraps
  *code* to 100; the ignore only spares the long prose comments from manual
  rewrapping. Tightening (un-ignoring E501) is a possible follow-up, not a
  blocker.
- **Per-file-ignores over inline noqa where the whole file shares one reason**;
  keep the existing inline `# noqa` comments where they are more precise.
  After enabling, run `ruff check --select RUF100` once to delete any noqa
  comments that turn out to be unused.
- **Rule families deliberately not selected:** `T20` (print is the UX),
  `BLE`/`TRY` (broad except is the degradation contract), `D` (docstring
  style — fine as-is), `S` (bandit — separate decision), `SIM`/`PL`
  (rewrite-y; would produce non-mechanical diffs).
- **Two commits:**
  1. *Lint commit*: config + `ruff check --fix .` (safe fixes only — never
     `--unsafe-fixes`) + any tiny manual fixes. Expect mostly import-sorting
     (`I001`), unused imports, and pyupgrade rewrites (`typing.Dict` →
     `dict`, etc. — these are type-annotation-only changes, no runtime
     behavior).
  2. *Format commit*: `ruff format .` as a purely mechanical diff. Optionally
     record this commit's SHA in a `.git-blame-ignore-revs` file.
- Run the 294-test gate after each commit.

## Phase 2B-2: Pre-commit

Two parts, in this order:

**1. Line-ending normalization first** (prevents hook/formatter churn on this
Windows-developed repo). Add `.gitattributes`:

```gitattributes
* text=auto
*.py text
*.md text
*.yml text
*.toml text
*.json text
```

then renormalize in a dedicated commit (`git add --renormalize .`). Without
this, `trailing-whitespace` / `end-of-file-fixer` hooks would fight the CRLF
working copies indefinitely.

**2. `.pre-commit-config.yaml`** mirroring exactly what CI will enforce —
no hook that isn't also checked in CI, and vice versa:

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: <pin latest at implementation time>
    hooks:
      - id: ruff-check
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: <pin latest at implementation time>
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-toml
      - id: check-added-large-files
      - id: check-merge-conflict
```

Decisions:

- **Mypy is *not* a pre-commit hook.** The mirrors-mypy hook runs in an
  isolated venv without the project's dependencies, which makes it slow and
  unreliable for LangChain-typed code. Mypy runs via `uv run mypy` locally
  and in CI (2B-3/2B-4) instead.
- Pin hook `rev`s to released tags; update deliberately, not automatically.
- One-time `uv run pre-commit run --all-files` cleanup lands together with
  the config (expected to be a no-op-ish diff if 2B-1 and the renormalize
  commit came first).
- `pre-commit install` is a per-developer step; document it in README setup.

## Phase 2B-3: Scoped Mypy

Scope: only the engine-API surface that is already (nearly) fully annotated
and that future callers depend on.

```toml
[tool.mypy]
python_version = "3.11"
files = [
    "graph/engine.py",
    "graph/config.py",
    "graph/formatting.py",
    "graph/state.py",
    "graph/consts.py",
]
warn_unused_configs = true
warn_unused_ignores = true
warn_redundant_casts = true
no_implicit_optional = true
check_untyped_defs = true

[[tool.mypy.overrides]]
module = ["graph.graph", "graph.nodes.*", "graph.chains.*"]
follow_imports = "silent"   # typed-as-available; do not error inside unscoped modules
```

Expected, allowed work (type-only edits, zero runtime change):

- `graph/formatting.py`: annotate the untyped parameters
  (`documents: Sequence[Document] | None`-style, `metadata: Mapping`-style,
  `result: Mapping[str, Any]`) and bare `-> list` returns.
- `graph/engine.py`: the `graph_runtime.app` handle may need a
  `CompiledStateGraph`-or-`Any` annotation depending on how well LangGraph's
  generics resolve; `dict(initial_state)` ↔ `GraphState` conversions may need
  a targeted `cast`. Acceptable; behavior-identical.
- Possibly one or two `# type: ignore[<code>]` with the error code spelled
  out — always code-specific, never bare.

Not in scope: `disallow_untyped_defs` repo-wide, strict mode, nodes/chains/
tests/`main.py`/`ingestion.py`/`evals/`. Third-party stubs: langchain-core /
langgraph / pydantic ship `py.typed`; if any transitive import still
complains, add a targeted `ignore_missing_imports = true` override for that
one module rather than globally.

## Phase 2B-4: CI Updates

Add **one new job** to `.github/workflows/ci.yml`; do not touch the existing
`mocked-tests` job (it stays the behavioral gate, keys-free):

```yaml
  lint:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
        with:
          python-version: "3.12"
          enable-cache: true
      - run: uv sync --locked --group dev
      - run: uv run ruff check .
      - run: uv run ruff format --check .
      - run: uv run mypy
```

Decisions:

- Run the tools directly rather than `pre-commit run --all-files` in CI:
  faster (no hook-venv builds), and failures point at the actual tool.
  Pre-commit stays the *local* mirror of the same three commands.
- The lint job runs in parallel with tests (no `needs:`), so test feedback
  is never delayed by lint failures.
- `uv run mypy` only enters the workflow once 2B-3 has landed; if 2B-4 ships
  earlier, the mypy line is added later with 2B-3.
- Update the CI comment header and `structure.md` §15 CI paragraph to
  mention the lint job (documentation-only CI change, as permitted).

## Risks

| Risk | Severity | Mitigation |
|---|---|---|
| **Formatter churn**: `ruff format` touches most of the 53 files → big diff, blame noise, painful conflicts with any in-flight branch | Medium | Separate mechanical commit; land when no feature branch is open; optional `.git-blame-ignore-revs` |
| **CRLF/LF instability**: no `.gitattributes` today; Windows checkouts already warn. Whitespace hooks + formatter could flip-flop endings | Medium | `.gitattributes` + `git add --renormalize` commit *before* enabling whitespace hooks (2B-2 step 1) |
| **Lint fixes that aren't mechanical**: `B` (bugbear) sometimes flags real-but-intentional patterns (e.g. mutable defaults, `except` ordering); pyupgrade rewrites in `graph/chains/*` touch files containing prompt strings | Medium | Safe fixes only; never `--unsafe-fixes`; review every non-import diff hunk by hand; prompt string literals must be byte-identical after 2B-1 (grep-verify) |
| Noisy areas: `tests/**` (lambdas, long mock setups), `evals/run_eval.py` (E402 after sys.path insert), `main.py` (re-export block), prose-heavy comments vs E501 | Low | Per-file-ignores prepared above; E501 ignored initially |
| Mypy vs LangChain/LangGraph generics (`app.stream` chunk types, `Document` metadata as `dict[str, Any]`) | Low–Medium | Scoped files only; `follow_imports = silent` for unscoped modules; code-specific `type: ignore` as last resort |
| Pre-commit hooks auto-modifying files during a commit surprises contributors | Low | README note; hooks are the same three tools as CI, nothing exotic |
| Tooling phase accidentally changing behavior | Must-not-happen | After every commit: 294-test gate; additionally diff-check that `graph/chains/*` prompt strings and `data/` are untouched |

## Deferred Work

Explicitly **not** in Phase 2B:

- Full-repo or strict mypy; annotating nodes (partial-state return types),
  chains, tests, `ingestion.py`, `main.py`.
- Un-ignoring `E501` (rewrapping prose comments).
- Additional ruff families: `D` (docstrings), `S` (security/bandit), `SIM`,
  `PL`, `RUF` beyond `RUF100`, preview rules.
- Coverage measurement/gating, `pytest -p no:cacheprovider` tweaks, etc.
- Dependabot / Renovate for hook and action pinning.
- Running `tests/chains/` or the full eval in CI (stays excluded by design).
- Any behavior-adjacent refactor (e.g. typing-driven restructuring of
  `grade_generation`) — out of scope, per standing constraints.

## Commands

All commands are for the implementer to run from the project root, per phase.

**2B-1 Ruff**

```powershell
uv add --group dev ruff
# (edit pyproject.toml: [tool.ruff] + [tool.ruff.lint] as specified above)
uv run ruff check .                  # survey first; expect import-order + pyupgrade findings
uv run ruff check --fix .            # safe autofixes only
uv run ruff check --select RUF100 .  # find now-unused noqa comments
uv run pytest tests/node/ tests/graph/ tests/evals/ -q   # gate: 294 passed
# commit 1 (lint), then:
uv run ruff format .
uv run pytest tests/node/ tests/graph/ tests/evals/ -q   # gate: 294 passed
# commit 2 (format, mechanical)
```

**2B-2 Pre-commit**

```powershell
# (add .gitattributes as specified above)
git add --renormalize .
uv run pytest tests/node/ tests/graph/ tests/evals/ -q   # gate
# commit (renormalize), then:
uv add --group dev pre-commit
# (add .pre-commit-config.yaml as specified above, with pinned revs)
uv run pre-commit install
uv run pre-commit run --all-files
uv run pytest tests/node/ tests/graph/ tests/evals/ -q   # gate
# commit (hooks)
```

**2B-3 Scoped mypy**

```powershell
uv add --group dev mypy
# (add [tool.mypy] + overrides to pyproject.toml as specified above)
uv run mypy                          # iterate on type-only fixes in the five scoped files
uv run pytest tests/node/ tests/graph/ tests/evals/ -q   # gate
# commit
```

**2B-4 CI**

```powershell
# (add the lint job to .github/workflows/ci.yml as specified above;
#  update the header comment + structure.md §15 CI paragraph)
uv run ruff check . ; uv run ruff format --check . ; uv run mypy   # local dry-run of the job
uv run pytest tests/node/ tests/graph/ tests/evals/ -q             # gate
# commit; verify both CI jobs green on the PR
```

## Acceptance Criteria

Phase 2B is done when all of the following hold:

1. `uv run ruff check .` exits 0.
2. `uv run ruff format --check .` exits 0.
3. `uv run mypy` exits 0 over the five scoped modules.
4. `uv run pre-commit run --all-files` exits 0 and the hook set equals the CI
   lint job's tool set.
5. CI has two green jobs: `lint` and the **unmodified** `mocked-tests`.
6. `uv run pytest tests/node/ tests/graph/ tests/evals/ -q` still reports
   **294 passed** (no test added/removed/changed by this phase).
7. Zero behavior deltas: prompts (`graph/chains/*` string literals), model
   names, corpus (`data/`), eval dataset (`evals/questions.jsonl`),
   `.env`/`.env.example`, `GraphState`, routing, and `stop_reason` semantics
   are byte-identical to the pre-2B state.
8. No new tooling beyond ruff, pre-commit, mypy (no flake8/black/isort
   duplicates, no FastAPI/UI/workflow code).
