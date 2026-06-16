# Claude Command Review

Status: Review

Date: 2026-06-16

Target command: `.claude/commands/plan-spec.md`

Report file: `docs/roadmap/commands-review/2026-06-16-plan-spec-command-review.md`

## 1. Executive summary

**Ready to use.**

`/plan-spec` is a well-scoped, planning-only command with clear required locations, safe
permissions, good missing-file handling, and a fixed final-response format. The recently added
*Optional LangChain Docs MCP documentation check* is conditional, narrowly scoped, names the exact
MCP tools, and correctly keeps project-local sources authoritative. Remaining items are minor
consistency/robustness improvements, not blockers.

## 2. Files reviewed

* `CLAUDE.md` (project rules, in context)
* `.claude/commands/plan-spec.md` (target)
* `.claude/commands/implement-spec.md` (peer, reviewed separately)
* `.claude/commands/arch-review.md` (peer, for path/collision conventions)

## 3. Frontmatter and permission review

Frontmatter is valid: standard `---` delimiters, sensible `description`, useful `argument-hint`.

`allowed-tools`: `Read, Write, Glob, Bash(git status:*), Bash(mkdir:*),
mcp__docs-langchain__search_docs_by_lang_chain,
mcp__docs-langchain__query_docs_filesystem_docs_by_lang_chain`.

* `Read` — needed (CLAUDE.md, plan template, spec).
* `Write` — needed (writes the plan file).
* `Glob` — **not referenced anywhere in the command body.** Pre-existing unused permission. Either
  use it (e.g. for plan-file collision detection, see §6) or drop it.
* `Bash(git status:*)` — used in Step 2. Correctly scoped.
* `Bash(mkdir:*)` — used to create `docs/roadmap/plan/`. Fine.
* MCP doc tools — read-only documentation lookups, used only in the optional section. Exact tool
  names match those exposed in this environment. Safe and appropriately narrow.

No broad `Bash(*)`, no `Bash(uv run:*)`, no test/eval/ingestion/API-key permissions. Permission
surface is safe.

## 4. Scope and safety review

The command states up front it is planning-only ("Create a plan only. Do not implement"). The
**Safety rules** section explicitly protects application/graph code, eval rows, the eval runner,
tests, prompts, model names, corpus documents, `.env`/`.env.example`, full eval, `ingestion.py`,
`tests/chains/`, commits, and branches. Strong coverage, consistent with peer commands.

`Write` is restricted in prose to `docs/roadmap/plan/<feature_slug>-plan.md`. The MCP section is
read-only and explicitly forbids letting external docs override local contracts, and forbids using
MCP for project-local rules already covered by `CLAUDE.md`/code/tests/evals/roadmap. Good.

## 5. Input handling review

* Missing plan template → stop with exact message. Good.
* Missing spec file → stop with exact message. Good.
* Un-inferable title/slug → ask the user. Good.
* Empty `$ARGUMENTS` → not handled explicitly; it would fall through to the "spec file not found"
  path, which is acceptable but slightly indirect. Low risk.

## 6. Output behavior review

Output directory, filename convention (`<feature_slug>-plan.md`), and slug derivation rules are
clear. Final response uses the generated plan path and avoids dumping the full plan into chat.

**Gap:** unlike `/arch-review` (which checks numbered candidate paths to avoid overwriting),
`/plan-spec` has **no collision handling for the plan file**. Re-running on the same spec silently
overwrites the existing plan. This may be intentional (a plan is a regenerable artifact), but it is
worth making explicit — either state "overwrites any existing plan for this slug" or adopt the
arch-review numbered-candidate pattern. Medium-ish, likely by design.

The new MCP note guidance ("add a small note in the most appropriate existing plan section, e.g.
`External docs consulted: LangChain Docs MCP, <library/topic>`") correctly avoids adding a large new
section and does not disturb the fixed Step 5 final-response format.

## 7. Project fit and consistency review

Consistent with `/new-spec`, `/implement-spec`, and `/arch-review`: same roadmap directory
conventions, same safety wording, same "use as few tools as possible" discipline. The optional MCP
section mirrors the one added to `/implement-spec`, keeping the two commands symmetric.

Minor consistency nit: the MCP section is an **unnumbered** `## Optional ...` heading inserted
between Step 3 and Step 4, while the rest of the command uses numbered steps. This is acceptable for
an optional step but slightly breaks the numbered flow.

## 8. Problems found

1. **Unused `Glob` permission.**
   * Why it matters: unused permissions add surface area and mislead readers about what the command
     does.
   * Risk level: Low.
   * Recommended fix: drop `Glob` from `allowed-tools`, or use it for plan-file collision detection.

2. **No plan-file collision handling.**
   * Why it matters: re-running overwrites an existing plan without warning; could discard manual
     edits to a prior plan.
   * Risk level: Medium (mitigated if regeneration is the intended behavior).
   * Recommended fix: either document that plans are overwritten, or adopt the numbered-candidate
     pattern from `/arch-review`.

3. **Empty `$ARGUMENTS` not explicitly handled.**
   * Why it matters: relies on the "spec not found" path instead of a clear prompt.
   * Risk level: Low.
   * Recommended fix: add a one-line "if `$ARGUMENTS` is empty, ask for a spec path" check.

4. **Optional MCP section is unnumbered amid numbered steps.**
   * Why it matters: minor structural inconsistency.
   * Risk level: Low.
   * Recommended fix: leave as-is (acceptable) or fold into Step 3/Step 4 numbering.

## 9. Recommended fixes

### Must fix

* None.

### Should fix soon

* Decide and document plan-file collision behavior (Problem 2).

### Optional improvements

* Remove or use the `Glob` permission (Problem 1).
* Add explicit empty-`$ARGUMENTS` handling (Problem 3).
* Normalize the optional MCP heading into the numbered flow (Problem 4).

## 10. Final verdict

**Ready to use.**
