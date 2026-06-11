# CLAUDE.md

Guidance for Claude Code when working in this repository.

## 1. Project Overview

An **enterprise internal-document Q&A assistant** built with **LangGraph**, implementing a
self-correcting Agentic RAG (CRAG-style) workflow. It answers questions from an ingested
knowledge base and falls back to web search when needed.

**Stack:** LangGraph, LangChain, OpenAI (`gpt-5-mini`, `OpenAIEmbeddings`), Chroma (vector
store), Tavily (web search). Managed with **uv**.

**High-level flow** (see `structure.md` for details):

```
question
→ route_question
    ├── websearch → generate
    └── retrieve → grade_documents
            ├── relevant docs → generate
            └── no relevant docs → websearch → generate
generate
→ grounding check (hallucination_grader)
    ├── not grounded → add grounding feedback → regenerate
    └── grounded → usefulness check (answer_grader)
            ├── useful → END
            └── not useful → rewrite search query → websearch
```

Three quality gates: **document relevance**, **answer grounding** (anti-hallucination), and
**answer usefulness**. A `retries` counter in state caps the regenerate/websearch loop at
`MAX_RETRIES = 5` (defined in `graph/graph.py`).

External dependency failures (retriever, Tavily, generation LLM, graders, query rewriter)
never crash the graph: each call site catches the exception, degrades or stops safely, and
records a `stop_reason` (`retrieval_error`, `web_search_error`, `generation_error`,
`tool_error`) so `main.py` appends an honest caveat. Console banners log only the exception
type, never the message.

## 2. Project Structure

| Path | Purpose |
|------|---------|
| `main.py` | CLI entry point. Loads `.env`, then imports the compiled `app` and runs an interactive Q&A loop. Seeds the full `GraphState`. Formats the final answer: `stop_reason` caveats plus a deterministic `Sources:` section built from `Document` metadata (`format_sources`; local corpus vs. `web_search` supplement). |
| `ingestion.py` | Builds the knowledge base: loads URLs, splits, embeds, persists to Chroma. Exposes `get_retriever()` (lazy, `@lru_cache`). Run once before `main.py`. |
| `graph/graph.py` | Assembles the LangGraph `StateGraph`, wires nodes + conditional edges, exports compiled `app`. Holds `MAX_RETRIES` and the routing decision functions. |
| `graph/state.py` | `GraphState` TypedDict: `question`, `documents`, `generation`, `web_search`, `web_search_enabled`, `retries`, `stop_reason`, `retry_feedback`, `search_query`, plus budget counters (`llm_call_count`, `web_search_count`, `web_result_grading_count`). |
| `graph/config.py` | Env-driven runtime flags: `web_search_enabled()` (privacy mode) and the per-run budgets `max_llm_calls_per_run()` / `max_web_searches_per_run()` / `max_web_results_to_grade()`. |
| `graph/consts.py` | Node-name string constants (`RETRIEVE`, `GRADE_DOCUMENTS`, `GENERATE`, `WEBSEARCH`, `WEB_SEARCH_DISABLED_NOTICE`) and `stop_reason` values. |
| `graph/nodes/` | Graph node functions: `retrieve`, `grade_documents`, `generate`, `web_search`, retry helpers (`add_grounding_feedback`, `rewrite_query`), plus terminal notice nodes (`web_search_disabled_notice`, `max_retries_not_grounded_notice`, `max_retries_not_useful_notice`, `budget_exhausted_notice`, `tool_error_notice`) that record `stop_reason`. |
| `graph/chains/` | LCEL chains: `generation`, `retrieval_grader`, `question_router`, `hallucination_grader`, `answer_grader`, `query_rewriter`. Each exposes a lazy `get_*()` factory. |
| `tests/node/` | Unit tests for node functions. Fully mocked — no API keys needed. |
| `tests/graph/` | Routing / privacy-toggle / compiled-graph tests. Fully mocked — no API keys needed. |
| `tests/chains/` | Integration tests for the chains. Call the real `gpt-5-mini` — need `OPENAI_API_KEY`. |
| `tests/conftest.py` | Loads `.env` before collection; provides the `requires_openai` skip marker. |
| `pyproject.toml` | uv project config: deps, `[dependency-groups] dev`, and `[tool.pytest.ini_options]` (`pythonpath = ["."]`, `testpaths = ["tests"]`). |

## 3. Development Rules

- **Preserve behavior by default.** Do not change graph routing, `GraphState` schema, prompts,
  model names (`gpt-5-mini`), `temperature=0`, chain input variables, or node return
  structures unless explicitly asked.
- **No broad architecture changes.** Avoid restructuring the graph or rewriting modules wholesale.
- **Refactors should be small, mechanical, and reviewable.** Prefer minimal diffs.
- **Lazy external clients (required pattern).** `ChatOpenAI`, `OpenAIEmbeddings`,
  `TavilySearchResults`, `Chroma`, retrievers, and any API-backed tool must be constructed
  inside a lazy factory — use `@lru_cache(maxsize=1) def get_x(): ...` — never at module level.
- **Imports must be side-effect-free.** Importing any module (`graph.graph`, `graph.nodes.*`,
  `graph.chains.*`, `ingestion`) must NOT require API keys or network, and must NOT construct
  any external client.
- **Backward-compatible chain names.** Chain modules expose `get_*()` factories; old
  module-level names (e.g. `generation_chain`, `question_router`) remain available via a lazy
  module-level `__getattr__`. Don't reintroduce eager module-level chain objects.
- Code comments/docstrings are written in **English**.

## 4. Testing Rules

- **Unit tests mock all external dependencies** via `monkeypatch`, targeting the lazy seam
  (e.g. patch `get_node_retriever`, `get_web_search_tool`, `get_retrieval_grader`,
  `generate_answer`).
- **Node tests (`tests/node/`) must never call real OpenAI, Tavily, Chroma, or embeddings.**
  They must pass with no API keys.
- **Integration tests (`tests/chains/`) call real services** and require `OPENAI_API_KEY`.
  Label such tests clearly and gate them with the `requires_openai` marker from `conftest.py`.
- **Do not run tests unless explicitly asked.** Writing tests ≠ running them.

## 5. Claude Code Behavior Rules

- **Plan first.** Before changing files, explain the plan and list every file to be changed and why.
- **Summarize after.** After editing, provide a diff summary.
- **Don't run commands without explicit approval** — no `pytest`, `python -c`, `py_compile`, or
  any code-executing command unless the user asks. Provide commands for the user to run instead.
- **Stop and ask** before any change that may affect business logic, graph routing, prompt
  behavior, model behavior, or the state schema.
- **Tests-only tasks:** when the request is only to write tests, prefer asking before touching
  production code; make the smallest safe change if a seam is genuinely needed for testability.

## 6. Common Commands

> These are for **the user to run manually**. Claude Code should not execute them without approval.

```powershell
# Always work from the project root
cd "C:\Agentic AI\LangGraph\Agentic_RAG_Claude"

# Set up the environment (creates .venv, writes uv.lock)
uv sync --group dev

# Build the Chroma index (one-time, before first run)
uv run python ingestion.py

# Run the assistant
uv run python main.py

# Node unit tests — fully mocked, NO API keys required
uv run pytest tests/node/ -v

# Chain integration tests — real gpt-5-mini, needs OPENAI_API_KEY
uv run pytest tests/chains/ -v

# Whole suite
uv run pytest -v

# Syntax-only check (no test execution)
$files = @(
    "graph/graph.py",
    "graph/nodes/generate.py",
    "graph/nodes/retrieve.py",
    "graph/nodes/web_search.py",
    "graph/nodes/grade_documents.py",
    "graph/chains/generation.py",
    "graph/chains/retrieval_grader.py",
    "graph/chains/question_router.py",
    "graph/chains/hallucination_grader.py",
    "graph/chains/answer_grader.py",
    "ingestion.py",
    "main.py"
)

uv run python -m py_compile $files

# Verify imports construct no clients and need no keys
uv run python -c "import graph.graph, graph.nodes, graph.chains, ingestion; print('IMPORT OK')"
```
