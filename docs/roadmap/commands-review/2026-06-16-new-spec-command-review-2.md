# Claude Command Review

Status: Review

Date: 2026-06-16

Target command: `.claude/commands/new-spec.md`

Report file: `docs/roadmap/commands-review/2026-06-16-new-spec-command-review-2.md`

## 1. Executive summary

**Ready to use.**

This is a re-review of `/new-spec` after the fixes from the first review
(`2026-06-16-new-spec-command-review.md`) were applied. Both **Should fix soon** items are
resolved: `Glob` is now in `allowed-tools`, and Step 4 performs a collision check on the target
spec path before writing, stopping to ask the user instead of silently overwriting an existing
spec. Frontmatter is valid, tool permissions are tight and exactly scoped, the safety section is
thorough, and the optional LangChain Docs MCP step is correctly gated and keeps project-local
sources authoritative. Only two **Low / optional** cosmetic items remain (implicit empty-argument
handling, and the unnumbered MCP section), neither of which blocks use.

## 2. Files reviewed

* `CLAUDE.md` (project rules — via session context)
* `.claude/commands/new-spec.md` (target — current post-fix state)
* `.claude/commands/plan-spec.md` (peer — closest analog)
* `.claude/commands/arch-review.md` (peer — collision-safe artifact writer)
* `docs/roadmap/commands-review/` (existing reports — report-path collision check)
* `git status --short`

## 3. Frontmatter and permission review

Frontmatter is correct:

* Opening and closing `---` delimiters present and well-formed; no blank/malformed lines.
* `description: Create a spec file from a short idea` — accurate and concise.
* `argument-hint: Short feature description` — useful and matches the input model.
* `allowed-tools: Read, Write, Glob, Bash(git status:*), Bash(mkdir:*), mcp__docs-langchain__search_docs_by_lang_chain, mcp__docs-langchain__query_docs_filesystem_docs_by_lang_chain`

Per-tool necessity:

* `Read` — necessary (`CLAUDE.md`, template).
* `Write` — necessary (writes the spec file); restricted in prose to `docs/roadmap/spec/`.
* `Glob` — now necessary and used: Step 4 uses it for the spec-path existence check. Resolves
  the prior gap and aligns with `/plan-spec` / `/arch-review`.
* `Bash(git status:*)` — necessary (Step 2); narrowly scoped.
* `Bash(mkdir:*)` — creates `docs/roadmap/spec/`; consistent with peers; narrowly scoped.
* `mcp__docs-langchain__search_docs_by_lang_chain` — necessary for the optional docs step;
  scoped to the specific installed MCP server.
* `mcp__docs-langchain__query_docs_filesystem_docs_by_lang_chain` — same; necessary and scoped.

No risky permissions: no `Bash(*)`, no `Bash(uv run:*)`, no `Edit`/`MultiEdit`, no test runner,
no full-eval, no `ingestion.py`, no API-key-requiring permissions. Every granted tool is now
exercised by the command body — no dead grants.

## 4. Scope and safety review

Strong and unchanged from the prior review:

* "Create a spec only. Do not implement the feature." stated up front.
* `Write` restricted in prose to `docs/roadmap/spec/` (Steps 2 and 4).
* Comprehensive "Safety rules" section protects application/graph code, eval rows, the eval
  runner, tests, prompts, model names, corpus documents, `.env`/`.env.example`, and blocks full
  eval, `ingestion.py`, `tests/chains/`, API-key commands, commits, and branch creation/switching.
* The MCP section keeps project-local contracts authoritative ("must not override project-local
  contracts") and limits external lookups to a defined trigger list.

Given `allowed-tools` (`Read`/`Write`/`Glob`/scoped `Bash`/scoped MCP) plus the prose write
restriction, the command cannot touch any of the protected areas.

## 5. Input handling review

* **Empty `$ARGUMENTS`** — still handled only implicitly via the Step 3 "cannot infer title/slug
  → ask" clause; not called out explicitly. Low severity, carried over from the prior review's
  optional list.
* **Short description input** — primary path; handled well with deterministic title/slug rules.
* **Missing template** — explicitly handled (stop with fixed message; do not invent a replacement).
* **Slug generation** — robust (lowercase, kebab-case, charset restriction, collapse, trim,
  40-char cap).
* **Repeated runs / output collision** — **now handled.** Step 4 checks `docs/roadmap/spec/<feature_slug>.md`
  with `Glob` before writing and stops to ask (revise vs. new slug) rather than overwriting. This
  closes the prior review's main gap.

## 6. Output behavior review

* Output directory (`docs/roadmap/spec/`) and filename convention (`<feature_slug>.md`) are clear
  and consistent with `/plan-spec`.
* Collision handling is present and preserves prior specs (stop-and-ask, no silent overwrite).
* Final response format is explicit and matches the project's terse "artifact + title, don't echo
  the body" convention.
* The MCP "External docs consulted" note is constrained to an existing section, no large new
  section, no raw dumps, only when MCP was used — good output hygiene.

## 7. Project fit and consistency review

Good fit. The command mirrors `/plan-spec` in structure, safety wording, and final-response style,
and path conventions match the roadmap layout in `CLAUDE.md`. The `Glob` + collision pattern now
matches `/arch-review` and `/plan-spec`, improving cross-command consistency. The LangChain Docs
MCP addition is appropriate for this LangGraph/LangChain/OpenAI stack and is gated so it does not
turn every spec into a docs-fetch exercise.

Minor consistency nit (carried over): the optional MCP section is an unnumbered `## Optional ...`
heading between Step 3 and Step 4, interrupting the numbered-step flow. Cosmetic only.

## 8. Problems found

### Problem 1 — Empty-argument handling is implicit

* **Issue:** A bare `/new-spec` invocation relies on the Step 3 "cannot infer" clause rather than
  an explicit early check.
* **Why it matters:** Slightly less predictable prompting for missing input; no functional risk.
* **Risk level:** Low.
* **Recommended fix:** Add an explicit early check — if `$ARGUMENTS` is empty, ask for a short
  feature description and stop. (Optional.)

### Problem 2 — Unnumbered MCP section breaks step sequence

* **Issue:** The optional MCP section sits as an unnumbered heading between Step 3 and Step 4.
* **Why it matters:** Cosmetic consistency only.
* **Risk level:** Low.
* **Recommended fix:** Renumber or fold it into Step 4 as an optional sub-step. (Optional.)

## 9. Recommended fixes

### Must fix

* (none)

### Should fix soon

* (none) — both prior Should-fix items (collision handling, missing `Glob`) are resolved.

### Optional improvements

* Make empty-argument handling explicit (Problem 1).
* Renumber or relocate the optional MCP section (Problem 2).

## 10. Final verdict

**Ready to use.**

The two substantive issues from the first review are fixed. The command is safe, correctly and
minimally permissioned, collision-safe on output, and consistent with peer commands. Only
low-severity cosmetic refinements remain, and they are optional.
