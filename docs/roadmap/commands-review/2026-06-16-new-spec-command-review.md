# Claude Command Review

Status: Review

Date: 2026-06-16

Target command: `.claude/commands/new-spec.md`

Report file: `docs/roadmap/commands-review/2026-06-16-new-spec-command-review.md`

## 1. Executive summary

**Ready after minor fixes.**

`/new-spec` is a well-structured, safe artifact-producing command. Its frontmatter is valid,
its tool permissions are tight, and its safety section is thorough and consistent with peer
commands (`/plan-spec`, `/arch-review`). The recently added "Optional LangChain Docs MCP
documentation check" is correctly scoped: it is optional, narrow, keeps project-local sources
authoritative, degrades gracefully when the MCP server is unavailable, and references the exact
MCP tool names that are also declared in `allowed-tools`.

The main gap is pre-existing and unrelated to the MCP change: **the command does not check
whether the target spec file already exists before writing it**, so a repeated run with the
same `feature_slug` would silently overwrite a previous spec. Peer commands that produce
artifacts (`/arch-review`, and the review commands) do collision-safe path selection; `/new-spec`
does not, and it does not carry `Glob` in `allowed-tools` to do so. Adding collision handling is
the only thing standing between this command and "Ready to use."

## 2. Files reviewed

* `CLAUDE.md` (project rules — via session context)
* `.claude/commands/new-spec.md` (target)
* `.claude/commands/plan-spec.md` (peer — closest analog)
* `.claude/commands/arch-review.md` (peer — collision-safe artifact writer)
* `docs/roadmap/commands-review/` (existing reports — collision check)
* `git status --short`

## 3. Frontmatter and permission review

Frontmatter is correct:

* Opening and closing `---` delimiters are present and well-formed; no blank/malformed lines.
* `description: Create a spec file from a short idea` — accurate and concise.
* `argument-hint: Short feature description` — useful and matches the command's input model.
* `allowed-tools: Read, Write, Bash(git status:*), Bash(mkdir:*), mcp__docs-langchain__search_docs_by_lang_chain, mcp__docs-langchain__query_docs_filesystem_docs_by_lang_chain`

Permission assessment, per tool:

* `Read` — necessary (reads `CLAUDE.md`, template).
* `Write` — necessary (writes the spec file). Restricted in prose to `docs/roadmap/spec/`.
* `Bash(git status:*)` — necessary (Step 2 working-tree check); narrowly scoped.
* `Bash(mkdir:*)` — used to create `docs/roadmap/spec/`; consistent with `/plan-spec` and
  `/arch-review`. Narrowly scoped.
* `mcp__docs-langchain__search_docs_by_lang_chain` — necessary only for the optional docs
  step; scoped to the specific installed MCP server, not a broad MCP grant.
* `mcp__docs-langchain__query_docs_filesystem_docs_by_lang_chain` — same; necessary and scoped.

No risky permissions found: no `Bash(*)`, no `Bash(uv run:*)`, no `Edit`/`MultiEdit`, no test
runner, no full-eval, no `ingestion.py`, no API-key-requiring command permissions. The two MCP
tools are the exact names exposed in this environment, so they will resolve rather than being
dead grants.

Gap: `Glob` is **not** present. It is needed if collision-safe spec-file selection is added
(see §6 / §8). Peer artifact commands carry `Glob` for exactly this.

## 4. Scope and safety review

Strong. The command:

* States up front "Create a spec only. Do not implement the feature."
* Restricts writes in prose to `docs/roadmap/spec/` (Step 2 and Step 4).
* Carries a comprehensive "Safety rules" section protecting application code, graph code, eval
  rows, the eval runner, tests, prompts, model names, corpus documents, `.env`/`.env.example`,
  and blocking full eval, `ingestion.py`, `tests/chains/`, API-key commands, commits, and
  branch creation/switching.
* The new MCP section reinforces that project-local sources (`CLAUDE.md`, source, tests,
  existing specs/plans/reports, README/roadmap) remain authoritative and that MCP "must not
  override project-local contracts" — this is the correct guardrail and prevents external docs
  from corrupting local rules.

The command cannot modify the things it is forbidden to modify, given the `allowed-tools`
(`Read`/`Write`/scoped `Bash`/scoped MCP) plus the prose restriction of `Write` to the spec dir.

## 5. Input handling review

* **Empty `$ARGUMENTS`** — handled indirectly: Step 3 says "If you cannot infer a sensible
  title and slug, ask the user to clarify instead of guessing." An empty argument falls under
  this, but it is not called out explicitly. Minor.
* **Short description input** — the primary intended input; handled well with title/slug rules.
* **Missing template** — explicitly handled (stop with a fixed message; do not invent a
  replacement).
* **Slug generation** — robust rules (lowercase, kebab-case, charset restriction, collapse,
  trim, 40-char cap).
* **Repeated runs / output collision** — **not handled.** If the same idea is run twice (or two
  ideas slugify identically), `Write` overwrites the earlier spec with no warning. This is the
  one material input-handling gap.

## 6. Output behavior review

* Output directory (`docs/roadmap/spec/`) and filename convention
  (`<feature_slug>.md`) are clear and consistent with `/plan-spec`.
* Final response format is explicit and matches the project's terse "artifact + title, don't
  echo the body" convention.
* **Collision handling is missing.** Unlike `/arch-review` (which checks candidate paths with
  `Glob` and increments a numeric suffix until an unused path is found), `/new-spec` writes
  straight to `docs/roadmap/spec/<feature_slug>.md`. Recommended: before writing, check
  existence and either (a) increment a suffix, or (b) stop and ask the user whether to
  overwrite. Option (b) is arguably better for specs, since a duplicate slug usually signals the
  user wants to revise the existing spec, not silently fork it.
* The MCP "External docs consulted" note is correctly constrained to an existing section, no
  large new section, no raw dumps, and only when MCP was actually used — good output hygiene.

## 7. Project fit and consistency review

Good fit. The command is consistent with the spec→plan→implement→review workflow and mirrors
`/plan-spec` closely in structure, safety wording, and final-response style. Path conventions
align with the roadmap directory layout described in `CLAUDE.md`.

The LangChain Docs MCP addition is appropriate for this project specifically — the stack is
LangGraph/LangChain/OpenAI/Chroma/Tavily, so version-sensitive external API details are a real
concern for some specs, and gating the lookup behind a narrow trigger list avoids turning every
spec into a docs-fetch exercise.

Minor consistency note: the MCP section sits between "Step 3" and "Step 4" as an unnumbered
`## Optional ...` heading, interrupting the otherwise numbered step sequence. It reads fine as
an optional aside, but renumbering (e.g. an explicit "Step 3.5 / optional") or moving it under
Step 4 would keep the step flow uniform.

## 8. Problems found

### Problem 1 — No collision handling on the output spec file

* **Issue:** Step 4 writes `docs/roadmap/spec/<feature_slug>.md` without checking whether it
  already exists. A repeated run, or two distinct ideas that slugify identically, silently
  overwrites an existing spec.
* **Why it matters:** Specs are durable process artifacts; silent overwrite destroys prior work
  with no warning and no git-staged signal beyond a modified file.
* **Risk level:** Medium.
* **Recommended fix:** Before writing, check existence (via `Glob` or equivalent). Either stop
  and ask whether to overwrite/revise, or select the first unused suffixed path
  (`<slug>-2.md`, `<slug>-3.md`, …) as `/arch-review` does. Add `Glob` to `allowed-tools`.

### Problem 2 — `Glob` missing from `allowed-tools`

* **Issue:** The command has no path-discovery tool, which both blocks the fix for Problem 1
  and diverges from peer artifact commands (`/plan-spec`, `/arch-review`) that carry `Glob`.
* **Why it matters:** Without it, collision-safe writing cannot be implemented.
* **Risk level:** Low (on its own); enables the Medium fix above.
* **Recommended fix:** Add `Glob` to `allowed-tools` when adding collision handling.

### Problem 3 — Empty-argument handling is implicit

* **Issue:** Empty `$ARGUMENTS` is only covered by the general "cannot infer title/slug → ask"
  clause, not called out explicitly.
* **Why it matters:** A bare `/new-spec` invocation should clearly prompt for input rather than
  rely on inference failing.
* **Risk level:** Low.
* **Recommended fix:** Add an explicit early check: if `$ARGUMENTS` is empty, ask the user for a
  short feature description and stop.

### Problem 4 — Unnumbered MCP section breaks step sequence

* **Issue:** The optional MCP section is an unnumbered heading inserted between Step 3 and
  Step 4.
* **Why it matters:** Cosmetic consistency; the rest of the command uses numbered steps.
* **Risk level:** Low.
* **Recommended fix:** Renumber or fold it into Step 4 as an optional sub-step.

## 9. Recommended fixes

### Must fix

* (none blocking) — the command is safe to use as-is; the items below improve robustness.

### Should fix soon

* Add collision handling for the output spec file (Problem 1) and add `Glob` to `allowed-tools`
  (Problem 2).

### Optional improvements

* Make empty-argument handling explicit (Problem 3).
* Renumber or relocate the optional MCP section for step-sequence consistency (Problem 4).

## 10. Final verdict

**Ready after minor fixes.**

The command is safe, correctly permissioned, and the LangChain Docs MCP addition is scoped
exactly as it should be. The one substantive gap is the absent output-file collision handling
(plus the missing `Glob` needed to implement it); addressing that would bring it to "Ready to
use."
