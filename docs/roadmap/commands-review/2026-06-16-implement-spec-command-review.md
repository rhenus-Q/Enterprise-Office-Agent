# Claude Command Review

Status: Review

Date: 2026-06-16

Target command: `.claude/commands/implement-spec.md`

Report file: `docs/roadmap/commands-review/2026-06-16-implement-spec-command-review.md`

## 1. Executive summary

**Ready to use.**

`/implement-spec` is a thorough, well-guarded implementation command: it has a plan-first reading
rule, an extensive default-safety section, scoped validation permissions, and a separated
implementation-report step. The recently added *Optional LangChain Docs MCP documentation check* is
conditional, narrowly scoped, placed before code edits, names the exact MCP tools, and keeps
project-local sources authoritative. The only notable gap is that the Step 10 final-response
checklist does not yet have a slot for the "external docs consulted" note that the MCP section asks
for — a minor consistency item.

## 2. Files reviewed

* `CLAUDE.md` (project rules, in context)
* `.claude/commands/implement-spec.md` (target)
* `.claude/commands/plan-spec.md` (peer, reviewed separately)
* `.claude/commands/arch-review.md` (peer, for safety-wording conventions)

## 3. Frontmatter and permission review

Frontmatter is valid: standard `---` delimiters, sensible `description`, useful `argument-hint`.

`allowed-tools`: `Read, Write, Edit, Glob, Grep, Bash(git status:*), Bash(git diff:*),
Bash(git ls-files:*), Bash(mkdir:*), Bash(uv run ruff:*), Bash(uv run mypy:*),
Bash(uv run pytest tests/node:*), Bash(uv run pytest tests/graph:*),
Bash(uv run pytest tests/evals:*), Bash(uv run python evals/run_eval.py --validate-only:*),
mcp__docs-langchain__search_docs_by_lang_chain,
mcp__docs-langchain__query_docs_filesystem_docs_by_lang_chain`.

* `Read`/`Edit`/`Write` — needed (read plan/spec/files, edit code, write report).
* `Glob`/`Grep` — needed to locate files during implementation.
* `Bash(git status/diff/ls-files:*)` — used for working-tree checks and diff-stat in the report.
* `Bash(mkdir:*)` — used to create the implementation directory.
* `Bash(uv run ruff/mypy:*)` — scoped validation. Fine.
* `pytest` permissions — correctly scoped to `tests/node`, `tests/graph`, `tests/evals`; **does not**
  grant `tests/chains` (the API-key suite). Good.
* `evals/run_eval.py --validate-only` — the safe eval path only; no full-eval permission. Good.
* MCP doc tools — read-only documentation lookups, used only in the optional section. Exact tool
  names match those exposed in this environment. Safe and narrow.

No broad `Bash(*)`, no blanket `Bash(uv run:*)`, no ingestion or API-key permissions. The permission
surface is broad-but-justified for an implementation command, and each entry maps to documented
behavior.

## 4. Scope and safety review

The **Default safety constraints** section is strong: it protects prompts, model names, corpus
documents, graph behavior/routing/nodes, `stop_reason` semantics, fallback-policy semantics,
`.env`/`.env.example`, full eval, `ingestion.py`, `tests/chains/`, API-key commands, commits, and
branches — all gated behind "unless the plan or spec explicitly approves an exception."

`Edit`/`Write` are governed by the plan/spec scope (Step 7 "implement only the requested scope") and
the report step (Step 9). The new MCP section is read-only, explicitly forbids overriding local
contracts, and forbids using MCP for project-local rules already covered by
`CLAUDE.md`/code/tests/evals/roadmap. No guardrail is weakened.

## 5. Input handling review

* Plan vs. spec input distinguished (Step 3 / Step 4) with a sensible plan-first rule.
* Missing input file → stop with exact message. Good.
* Un-inferable title/slug → ask the user. Good.
* Unrelated uncommitted changes → stop and ask. Good.
* Repeated runs: the implementation itself is idempotent-by-scope; the report path (Step 9) reuses
  `<feature-slug>-implementation-report.md` and would overwrite a prior report — see §6.

## 6. Output behavior review

Implementation and report generation are cleanly separated (Steps 7–9). Validation commands
(Step 8) are appropriate and scoped. Forbidden operations (full eval, ingestion, chains tests) are
explicitly blocked.

**Items:**

1. **MCP "external docs consulted" note has no slot in Step 10.** The optional MCP section says to
   "briefly mention it in the final response," but the Step 10 final-response checklist does not list
   that item. The two are consistent in spirit but the checklist should include it so the note is not
   forgotten. Low risk.

2. **Implementation report overwrite.** Step 9 always targets
   `<feature-slug>-implementation-report.md`; a second run on the same slug overwrites the prior
   report. This is likely acceptable (the report reflects the latest run), but unlike `/arch-review`
   it is not collision-safe. Low/Medium, likely by design.

The MCP section correctly forbids dumping raw MCP output into code, comments, reports, or the final
response. Good.

## 7. Project fit and consistency review

Consistent with `/new-spec`, `/plan-spec`, `/review-diff`, and `/arch-review`: shared roadmap
directory conventions, shared safety wording, plan-first discipline. The optional MCP section mirrors
the one in `/plan-spec`, keeping the plan→implement pair symmetric.

Minor consistency nit (same as `/plan-spec`): the MCP section is an **unnumbered** `## Optional ...`
heading inserted between Step 6 and Step 7, while the surrounding flow is numbered. Acceptable for an
optional step.

## 8. Problems found

1. **Step 10 final-response checklist omits the "external docs consulted" note.**
   * Why it matters: the MCP section asks for the note in the final response, but the explicit
     checklist doesn't include it, so it may be dropped.
   * Risk level: Low.
   * Recommended fix: add a bullet to Step 10 such as "Whether LangChain Docs MCP was consulted
     (and for which library/topic)."

2. **Implementation report is overwritten on re-run.**
   * Why it matters: a re-run discards the previous report for the same slug.
   * Risk level: Low/Medium (mitigated if latest-run reporting is intended).
   * Recommended fix: document the overwrite, or adopt numbered-candidate report paths.

3. **Optional MCP section is unnumbered amid numbered steps.**
   * Why it matters: minor structural inconsistency.
   * Risk level: Low.
   * Recommended fix: leave as-is, or fold into the Step 6/Step 7 numbering.

## 9. Recommended fixes

### Must fix

* None.

### Should fix soon

* Add the "external docs consulted" item to the Step 10 final-response checklist (Problem 1).

### Optional improvements

* Document or make collision-safe the implementation report path (Problem 2).
* Normalize the optional MCP heading into the numbered flow (Problem 3).

## 10. Final verdict

**Ready to use.**
