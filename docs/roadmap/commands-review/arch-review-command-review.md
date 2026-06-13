# Arch Review Command Review

Status: Review

Date: 2026-06-13

## 1. Executive summary

`/arch-review` (`.claude/commands/arch-review.md`) is **Ready after minor fixes**.

It is usable today: the frontmatter is valid, the report path and directory-creation
instruction match what is expected, the safety prose is thorough, and it executes no
expensive or API-key-requiring command. The graph/eval/test/docs scope is appropriate for
this Agentic RAG project and the 12-section report template is well aligned with the
project's concerns.

The reasons it is not a clean "Ready to use" are all minor polish items, none blocking:

* The review grants an **unrestricted `Write`** tool. Because Claude Code cannot path-scope
  `Write`, the only thing keeping the command from editing application code is the prose
  ("review-only", "do not modify ..."). This is inherent to any command that produces a
  report, but worth recording.
* One **unused permission** (`Bash(git diff:*)`) is granted but never exercised by the flow.
* A **read/review mismatch**: the report assesses "Claude commands / command workflows", but
  Step 2 never directs reading `.claude/commands/`.
* **Redundant verdicts**: sections 1, 11, and 12 all emit an overall verdict.
* The top "do not modify" block does not enumerate `graph routing` / `graph nodes` /
  `stop_reason` / `fallback policy` the way the sibling commands do (they are subsumed by
  "application code", so this is a consistency gap, not a hole).

## 2. Files reviewed

* `CLAUDE.md` (from project context)
* `.claude/commands/arch-review.md` (target under review)
* `.claude/commands/review-diff.md`
* `.claude/commands/implement-spec.md`
* `.claude/commands/new-spec.md`
* `.claude/commands/plan-spec.md`
* `git status --short` output

No application code, tests, eval files, prompts, model names, corpus, or `.env` files were
read or modified.

## 3. Command correctness

### Frontmatter

* **Valid Claude Code frontmatter** — yes. `---` open (line 1) and close (line 5) delimiters
  present; `description`, `argument-hint`, `allowed-tools` are all recognized fields.
* **`description`** — "Review the project architecture and write an architecture review
  report". Clear and appropriate.
* **`argument-hint`** — `Optional review focus, for example "eval harness" or "graph flow"`.
  Useful and discoverable; matches the `$ARGUMENTS` focus handling in the body (lines 49,
  211).
* **`allowed-tools`** — `Read, Write, Glob, Grep, Bash(git status:*), Bash(git diff:*),
  Bash(mkdir:*)`.
  * `Read`, `Glob`, `Grep` — correct for inspection.
  * `Write` — required to produce the report, but unrestricted (see §4).
  * `Bash(git status:*)` — used (Step 1), scoped, read-only. Good.
  * `Bash(mkdir:*)` — used to create the report directory. Consistent with the other
    artifact-creating commands.
  * `Bash(git diff:*)` — **granted but never used** by this command's flow. Likely copied
    from `review-diff`. Harmless (read-only) but should be removed for least-privilege.
* **No overly broad Bash** — confirmed. No `Bash(*)`, no shell, no package/test/network
  commands. This is stronger than `implement-spec`, which (appropriately for its purpose)
  grants `pytest` and `ruff`/`mypy`.

### Paths and instructions

* **Report output path** — `docs/roadmap/architecture-review/architecture-review.md`,
  consistent at lines 47, 201, and 334. Matches the expected location.
* **Directory creation** — `docs/roadmap/architecture-review/` (lines 195–197), created via
  `Bash(mkdir:*)`. Correct.
* **No branch creation / switching** — lines 36–37. ✅
* **No commit** — line 35. ✅
* **No test execution** — the command inspects test directories but never runs them, and the
  allowed-tools grant no test runner. ✅
* **No full eval** — line 27. ✅
* **No `ingestion.py`** — line 29. ✅
* **No `tests/chains/`** — lines 31 and 106. ✅
* **No API-key-requiring commands** — line 33, and no such command is in allowed-tools. ✅

### Final response format

Step 6 (lines 330–344) prints the report path, a single verdict, top issues, and
"Do not repeat the full report in chat unless the user explicitly asks." This matches the
concise, no-repeat final-response style used by `new-spec`, `plan-spec`, `implement-spec`,
and `review-diff`. ✅

## 4. Safety review

### What the command protects (prose)

| Area | Protected? | Where |
|------|-----------|-------|
| prompts | ✅ | line 19 |
| model names | ✅ | line 21 |
| corpus documents | ✅ | line 23 |
| `.env` / `.env.example` | ✅ | lines 25, 108 (also "Do not inspect `.env`") |
| graph behavior | ✅ (coarse) | line 13 ("do not modify application code") |
| graph routing | ⚠️ implicit | subsumed by line 13, not named |
| graph nodes | ⚠️ implicit | subsumed by line 13, not named |
| `stop_reason` semantics | ⚠️ implicit | subsumed by line 13, not named |
| fallback policy semantics | ⚠️ implicit | subsumed by line 13, not named |
| full eval | ✅ | line 27 |
| `ingestion.py` | ✅ | line 29 |
| `tests/chains/` | ✅ | lines 31, 106 |

Because this is a review-only command whose only writable artifact is the report, the coarse
"do not modify application code" is adequate protection in practice. The named-versus-implicit
gap is a consistency issue with the sibling commands (`review-diff` and `implement-spec`
enumerate routing / nodes / `stop_reason` / fallback explicitly), not a functional hole.

### Risky-change prevention

* **Unrestricted `Write` is the main residual risk.** Claude Code cannot path-scope `Write` in
  `allowed-tools`, so nothing at the tool layer prevents the command from writing to
  `graph/`, prompts, or corpus files. The guard is purely the prose. The prose is thorough
  (10+ explicit "do not modify" lines), and `Edit` is correctly **not** granted, so in-place
  code edits are not enabled. Residual risk is **Low** but non-zero, and is shared by every
  artifact-producing command in this repo (`new-spec`, `plan-spec`, `implement-spec` all grant
  `Write` the same way).
* **No accidental escalation otherwise.** It does not grant `Edit`, any test runner, any
  network/package command, or any unscoped Bash.

### Expensive-command prevention

Full eval, `ingestion.py`, `tests/chains/`, and API-key commands are all explicitly forbidden
in prose **and** absent from `allowed-tools`. Strong — the protection is enforced at both
layers, not just prose.

## 5. Scope review

The architecture-review scope is appropriate and well matched to this project:

* **Covered well** — graph flow, nodes, chains, `state`/`config`/`consts`, `engine`,
  `formatting`, eval harness, eval history/delta reporting (lines 98, 145), `tests/node`,
  `tests/graph`, `tests/evals`, `README`, `structure.md`, `CLAUDE.md`, `pyproject.toml`, CI,
  `.gitignore`, and portfolio readiness. This maps cleanly onto the modules described in
  `CLAUDE.md`.
* **Token discipline is built in** — "Use as few tools as possible" (line 39), "Prefer
  targeted reads over broad file reading" (line 67), "Inspect these areas as needed" (line
  71), and "Do not repeat the full report in chat" (line 344). These mitigate the main scope
  risk (a 12-section report over the whole graph + eval + tests + docs could otherwise be
  token-heavy).
* **Gap — command workflow** — Step 3 (line 161) and report section 9 (line 299) ask the run
  to assess "command workflows" / "Claude commands", but Step 2's inspection list never
  includes `.claude/commands/`. The run is asked to review something it is not told to read.
  Add `.claude/commands/` to the Step 2 inspection list.
* **Minor — listed inspection paths may not all exist** (e.g. `evals/README.md`). The command
  hedges with "Inspect these areas as needed", so a missing file is tolerable; no fix
  required, but it relies on the agent degrading gracefully.

Overall: appropriately broad, not too narrow, and the token risk is acknowledged and
mitigated rather than ignored.

## 6. Consistency with existing commands

Compared against `/new-spec`, `/plan-spec`, `/implement-spec`, `/review-diff`:

* **Wording** — consistent: shared "User input: `$ARGUMENTS`", "Use as few tools as
  possible", numbered `## Step N` structure, and "Do not repeat the full ... in chat unless
  explicitly asked" closing.
* **Safety constraints** — mostly consistent. Gap: the sibling review/implementation commands
  enumerate `graph routing` / `graph nodes` / `stop_reason` / `fallback policy`; `arch-review`
  folds these under "application code". See §4.
* **Path style** — consistent backticked `docs/roadmap/...` artifact paths.
* **No-branch / no-commit policy** — consistent (lines 35–37).
* **Final response format** — consistent concise/no-repeat style.
* **Token-saving behavior** — consistent (targeted reads, few tools, no chat repetition).
* **Report location** — consistent with the `docs/roadmap/...` artifact convention.
* **Template usage (divergence, acceptable)** — `new-spec` / `plan-spec` / `implement-spec`
  read an external template (`*-template.md`) and handle a missing template gracefully.
  `arch-review` embeds its report structure inline instead. For a self-contained review
  report this is reasonable and arguably better (no extra dependency), but it is a stylistic
  divergence worth noting.
* **Write grant** — `arch-review` patterns after the artifact-creating commands (grants
  `Write`), not after `review-diff` (which grants no `Write` and outputs only to chat). This
  is the correct choice given it must persist a report.

## 7. Problems found

### P1 — Unrestricted `Write` in a review-only command

* **Issue:** `allowed-tools` grants `Write` with no path scope; only the prose prevents the
  command from writing application code, prompts, or corpus.
* **Why it matters:** A review command should be incapable of mutating reviewed code; here
  the guard is instructions, not the tool layer.
* **Risk level:** Low (Claude Code cannot path-scope `Write`; `Edit` is correctly withheld;
  prose guards are thorough; same pattern as the other artifact commands).
* **Recommended fix:** Keep `Write` (it is required), but add an explicit single line such as
  "Use `Write` only for the report file at
  `docs/roadmap/architecture-review/architecture-review.md`." to make the intended scope
  unambiguous.

### P2 — `Bash(git diff:*)` granted but unused

* **Issue:** The flow only runs `git status --short`; `git diff` is never invoked.
* **Why it matters:** Least-privilege; an unused grant is dead surface and suggests copy from
  `review-diff`.
* **Risk level:** Low.
* **Recommended fix:** Remove `Bash(git diff:*)` from `allowed-tools`.

### P3 — Reviews "Claude commands" without reading them

* **Issue:** Report section 9 and Step 3 assess command workflows, but Step 2 never lists
  `.claude/commands/` as an inspection target.
* **Why it matters:** The run may comment on command workflows without having read them, or
  spend tokens hunting for them ad hoc.
* **Risk level:** Low.
* **Recommended fix:** Add `.claude/commands/` (and optionally `docs/roadmap/`) to the Step 2
  inspection list.

### P4 — Three overlapping verdict sections

* **Issue:** Section 1 (executive summary classification), section 11 (portfolio-readiness
  verdict), and section 12 (final verdict) all emit an overall judgment with near-identical
  wording.
* **Why it matters:** Redundancy lengthens the report and invites inconsistent verdicts
  across the three spots.
* **Risk level:** Low.
* **Recommended fix:** Merge 11 and 12 into a single "Verdict" section, or have section 1
  reference the final verdict rather than restate it.

### P5 — Safety block does not name graph routing / nodes / `stop_reason` / fallback

* **Issue:** Unlike sibling commands, the top "do not modify" block stops at "application
  code" and does not enumerate the graph-behavior specifics.
* **Why it matters:** Consistency with `review-diff` / `implement-spec`; explicit naming is
  this repo's established convention and reduces ambiguity.
* **Risk level:** Low.
* **Recommended fix:** Add the four named items to the "do not modify" block to match the
  sibling commands.

## 8. Recommended fixes

### Must fix

* None. The command is functionally correct and safe to run as-is.

### Should fix soon

* **P2** — Drop the unused `Bash(git diff:*)` grant (least-privilege, one-line change).
* **P3** — Add `.claude/commands/` to the Step 2 inspection list so command-workflow
  assessment is grounded.

### Optional improvements

* **P1** — Add an explicit "Use `Write` only for the report file" line.
* **P4** — Collapse the redundant verdict sections (11 + 12).
* **P5** — Enumerate `graph routing` / `graph nodes` / `stop_reason` / `fallback policy` in
  the "do not modify" block for consistency with sibling commands.

## 9. Final verdict

**Ready after minor fixes.**

The command is valid, safe, scoped correctly for this Agentic RAG project, and runs no
expensive or API-key-requiring operation. It can be used today. The five findings are all
Low-risk consistency/polish items; addressing P2 and P3 ("should fix soon") will make it
cleaner and bring it fully in line with the existing `/new-spec`, `/plan-spec`,
`/implement-spec`, and `/review-diff` commands.
