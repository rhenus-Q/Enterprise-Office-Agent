# Arch Review Command Review v2

Status: Review

Date: 2026-06-13

## 1. Executive summary

The updated `/arch-review` command (`.claude/commands/arch-review.md`) is **Ready after minor fixes**.

The update is a clear improvement over the version assessed in `arch-review-command-review.md`.
Four of the five prior findings are fully resolved, the fifth is partially resolved, and the
headline new feature — repeated, non-overwriting, timestamped/focus-slug architecture reports —
is well specified. Scope, safety prose, and consistency with the sibling commands are now strong.

It is **not** a clean "Ready to use" for one concrete reason plus two robustness gaps:

* **Must fix — malformed frontmatter close.** The closing delimiter (line 6) is a long run of
  hyphens (`-----…`), not the standard `---`, and a stray blank line was inserted after the
  opening `---` (line 2). The sibling `review-diff.md` closes cleanly with `---`. If Claude
  Code's frontmatter parser requires an exact `---`, the entire frontmatter block — including
  `allowed-tools` — may fail to parse, silently dropping the command's tool-level safety
  scoping. This is a one-line fix but it is foundational, so it blocks "Ready to use".
* **Should fix — empty slug after sanitization.** `overall` is only used when `$ARGUMENTS` is
  *empty*. An argument that sanitizes to nothing (e.g. `"??"`) yields a malformed filename.
* **Should fix — per-candidate collision check.** The suffix loop (`-2`, `-3`, …) does not
  explicitly require a `Glob` on each candidate, leaving a small overwrite ambiguity.

None of these affect application code, tests, evals, prompts, models, or corpus.

## 2. Files reviewed

* `CLAUDE.md` (from project context)
* `.claude/commands/arch-review.md` (target under review — read only, not modified)
* `.claude/commands/review-diff.md`
* `docs/roadmap/commands-review/arch-review-command-review.md` (prior v1 review)
* `git status --short` output
* `docs/roadmap/architecture-review/` directory listing (via `Glob`)
* `.claude/commands/` directory listing (via `Glob`)

No application code, tests, eval files, prompts, model names, corpus, or `.env` files were
read or modified. The command file was not modified.

## 3. Frontmatter and permission review

### Frontmatter delimiters — **defective**

* **Opening** — `---` is present as line 1. ✅ But line 2 is a stray **blank line** before the
  first key. A leading blank line inside YAML frontmatter is tolerated by most parsers, so this
  alone is cosmetic, but it is non-standard for this repo.
* **Closing** — line 6 is `-------------------------------------------------------------------------`
  (a ~70-character hyphen run), **not** the standard `---`. ❌ This is the main defect. The
  previous version closed cleanly with `---`, so the update introduced this regression.
  `review-diff.md` (line 5) closes with `---`. **Recommended fix:** replace the hyphen run with
  exactly `---` and delete the blank line at line 2.

Risk if a strict parser rejects the close: the frontmatter (and therefore `allowed-tools`) is
not applied, so the curated least-privilege tool set is lost and the command falls back to the
session's default permissions. The review-only *prose* still applies, but the tool-layer guard
is the whole point of `allowed-tools`.

### Fields

* **`description`** — "Review the project architecture and write a timestamped architecture
  review report". Clear, and correctly updated to advertise the new timestamped behavior. ✅
* **`argument-hint`** — `Optional review focus, for example "eval harness" or "graph flow"`.
  Useful and matches the `$ARGUMENTS` focus-slug handling in the body. ✅

### `allowed-tools`

`Read, Write, Glob, Grep, Bash(git status:*), Bash(mkdir:*)`

* `Read`, `Glob`, `Grep` — correct for inspection; `Glob` is needed for the existence check. ✅
* `Write` — required to produce the report; unrestricted at the tool layer (Claude Code cannot
  path-scope `Write`), but now prose-scoped (line 100, "Use `Write` only for the selected unique
  report file"; line 102, "Do not write any other file"). ✅ (residual note in §5)
* `Bash(git status:*)` — used in Step 1; scoped, read-only. ✅
* `Bash(mkdir:*)` — used to create `docs/roadmap/architecture-review/`. ✅
* **`Bash(git diff:*)` is gone** — the unused grant flagged in v1 (P2) has been removed. ✅
* **No test runner**, **no full-eval**, **no `ingestion.py`**, **no API-key command**, and **no
  broad `Bash(*)`/shell** — confirmed absent. ✅
* **`Edit` is correctly not granted** — in-place code edits are not enabled. ✅

## 4. Repeated-report behavior review

The new naming/collision mechanism (lines 62–104) is the core addition and is well specified.

| Requirement | Present? | Where |
|---|---|---|
| Report directory `docs/roadmap/architecture-review/` | ✅ | 58, 66, 256–258 |
| Filename `<YYYY-MM-DD>-<focus-slug>-architecture-review.md` | ✅ | 66 |
| Date = today | ✅ | 70 |
| Slug derived from `$ARGUMENTS` | ✅ | 71 |
| Fallback slug `overall` | ✅ (empty arg only — see gap) | 72 |
| Filename safety rules (trim/space→hyphen/strip quotes & unsafe chars) | ✅ | 73–79 |
| Worked examples | ✅ | 81–90 |
| `Glob` before writing | ✅ | 92 |
| No-overwrite / numeric suffix `-2`, `-3`, … | ✅ | 94–98 |
| Final response uses the selected unique path | ✅ | 274, 397 |

**No collision with the legacy report.** The existing `docs/roadmap/architecture-review/architecture-review.md`
(old fixed-name scheme) can never be overwritten, because every new filename carries a
`YYYY-MM-DD-` prefix. ✅ The two schemes coexist; worth a one-line note in the repo that the
unprefixed file predates this command.

**Gaps / ambiguities flagged:**

1. **Empty slug after sanitization (Medium-ish edge case).** `overall` is only used "If
   `$ARGUMENTS` is empty" (line 72). A non-empty argument that sanitizes to nothing
   (`"??"`, `"@#$"`) produces a malformed name like `2026-06-13--architecture-review.md`.
   Fix: "If the slug is empty after sanitization, use `overall`."
2. **Per-candidate existence check (Low).** Line 92 mandates a `Glob` for the *initial* target;
   the suffix loop (94–98) says "continue until an unused filename is found" but does not
   explicitly require a `Glob` on each `-N` candidate. A literal agent could `Glob` only the
   base, then `Write` `-2` without checking it. Fix: either "`Glob` each candidate in turn and
   use the first that does not exist", or — cleaner and fewer tools — "`Glob`
   `…-<slug>-architecture-review*.md` once and pick the next free index."
3. **No length cap / repeated-hyphen collapse (Low, optional).** A long focus sentence yields an
   unwieldy slug; `"eval  harness"` (double space) yields `eval--harness`. Optional polish.

## 5. Safety review

The command is review-only and the protective prose is now comprehensive. The top block
(lines 12–50) explicitly forbids modifying / running:

application code (14) · tests (16) · eval files (18) · prompts (20) · model names (22) ·
corpus documents (24) · `.env`/`.env.example` (26) · graph behavior (28) · graph routing (30) ·
graph nodes (32) · `stop_reason` semantics (34) · fallback policy semantics (36) · full eval
(38) · `ingestion.py` (40) · `tests/chains/` (42) · API-key-requiring commands (44) ·
commits (46) · branch creation/switching (48).

All eighteen protected areas requested for this project are present. The graph-behavior
specifics (routing / nodes / `stop_reason` / fallback) that v1 flagged as missing (P5) are now
named explicitly, matching `review-diff.md`. ✅ Step 4 also reinforces "Do not rewrite the
architecture / Do not implement fixes / Only review and recommend" (248–252), and Step 2 adds
"Do not inspect `.env`" (169) and "Do not inspect `tests/chains/` unless the user explicitly
asks" (161). ✅

**Can it mutate anything other than the report?**

* `Edit` is not granted → no in-place edits. ✅
* `Write` is granted and cannot be tool-scoped to a path in Claude Code, so the *only* guard
  against writing `graph/`, prompts, or corpus is prose. That prose is now explicit (lines
  100, 102). **Residual risk: Low**, identical to the other artifact-producing commands
  (`new-spec`, `plan-spec`, `implement-spec`). Acceptable and well-mitigated.
* `Bash(mkdir:*)` can create arbitrary directories but cannot mutate file contents; used only
  for the report dir. ✅
* `Bash(git status:*)` is read-only. ✅

Net: subject to the frontmatter parsing caveat in §3, the command cannot mutate project
behavior. If the frontmatter fails to parse, the tool-layer scoping is lost and only the prose
remains — another reason the §3 fix is a must.

## 6. Scope review

The architecture-review scope (Steps 2–3) maps cleanly onto this project and is appropriately
broad without being wasteful:

* **Covered:** graph flow, nodes, chains, `state`/`config`/`consts`, `engine`, `formatting`,
  eval harness (`run_eval.py`, `questions.jsonl`), eval history/delta reporting (`evals/history/`,
  line 153; Step 3 "history and delta reporting safe and metadata-only"), `tests/node`,
  `tests/graph`, `tests/evals`, README, `structure.md`, `CLAUDE.md`, `pyproject.toml`, CI,
  `.gitignore`, **and `.claude/commands/`** (the v1 P3 gap — now added at 163–167), plus
  portfolio readiness (Step 3 "Portfolio quality", report §11).
* **Token discipline is built in:** "Use as few tools as possible" (50), "Prefer targeted reads
  over broad file reading" (122), "Inspect these areas as needed" (126), and "Do not repeat the
  full report in chat" (407). These mitigate the inherent cost of a 12-section report spanning
  graph + eval + tests + docs + commands.
* **Minor:** some listed inspection paths may not exist (e.g. `evals/README.md`); the command
  hedges with "Inspect these areas as needed", so a missing file degrades gracefully. No fix
  required.

Verdict: scope is well matched — not too narrow, broad-but-mitigated, not token-reckless.

## 7. Consistency with existing commands

Compared against `/review-diff` (read in full) and `/new-spec`, `/plan-spec`, `/implement-spec`
(per the v1 review):

* **Wording** — consistent: shared "User input: `$ARGUMENTS`", "Use as few tools as possible",
  numbered `## Step N` structure, and the "Do not repeat the full report in chat unless …"
  closing. ✅
* **Safety constraints** — now consistent. The graph-behavior specifics are enumerated as in
  `review-diff`/`implement-spec`. ✅ (was the v1 P5 gap)
* **Path style** — consistent backticked `docs/roadmap/...` artifact paths. ✅
* **No-branch / no-commit** — consistent (lines 46, 48). ✅
* **Final response format** — consistent concise/no-repeat style (Step 6). ✅
* **Token-saving behavior** — consistent. ✅
* **Report location** — consistent `docs/roadmap/...` convention; the timestamped/focus-slug
  naming is a justified enhancement unique to `arch-review` (it is designed to be re-run).
* **Frontmatter delimiter — inconsistent.** `review-diff.md` closes with a clean `---` (line 5);
  `arch-review.md` closes with a hyphen run and adds a stray blank line. This is the §3 defect
  and the only real consistency break.

## 8. Problems found

### P1 — Malformed / non-standard frontmatter close (regression)

* **Issue:** Line 6 closes the frontmatter with a long hyphen run instead of `---`; line 2 is a
  stray blank line after the opening `---`.
* **Why it matters:** If the parser requires an exact `---`, the frontmatter — including
  `allowed-tools` — may not parse, silently removing the command's tool-level safety scoping.
  It is also inconsistent with `review-diff.md` and the project's documented standard.
* **Risk level:** Medium.
* **Recommended fix:** Replace line 6 with exactly `---`; delete the blank line at line 2.

### P2 — `overall` fallback misses the empty-after-sanitization case

* **Issue:** `overall` is used only when `$ARGUMENTS` is empty (line 72), not when a non-empty
  argument sanitizes to an empty slug.
* **Why it matters:** Produces a malformed filename (`2026-06-13--architecture-review.md`) for
  inputs like `"??"`.
* **Risk level:** Low.
* **Recommended fix:** "If the slug is empty after sanitization, use `overall`."

### P3 — Suffix loop does not mandate a per-candidate existence check

* **Issue:** Line 92 requires `Glob` for the initial target only; the `-2`/`-3` loop (94–98)
  does not explicitly require checking each candidate.
* **Why it matters:** A literal agent could write `-2` without confirming it is free, risking an
  overwrite.
* **Risk level:** Low.
* **Recommended fix:** "`Glob` each candidate in turn and use the first that does not exist," or
  "`Glob` `…-<slug>-architecture-review*.md` once and pick the next free index" (fewer tools).

### P4 — Residual unrestricted `Write` (carried from v1, now mitigated)

* **Issue:** `Write` cannot be path-scoped in `allowed-tools`; only prose (lines 100, 102)
  confines it to the report file.
* **Why it matters:** A review command's only writable surface should ideally be enforced, not
  instructed.
* **Risk level:** Low — `Edit` is withheld and the prose is now explicit; inherent to every
  artifact-producing command in this repo.
* **Recommended fix:** None required; the explicit lines added in this update are the right
  mitigation.

### P5 — Overlapping verdict sections (partially carried from v1 P4)

* **Issue:** Report §1 (executive-summary classification) and §11 (portfolio-readiness verdict)
  still emit near-identical three-way verdicts. §12 was improved with an explicit "Do not
  restate the executive summary or the portfolio-readiness verdict" instruction (385–391), so
  the 11↔12 overlap is resolved; the 1↔11 overlap remains.
* **Why it matters:** Mild redundancy and risk of inconsistent verdicts across sections.
* **Risk level:** Low.
* **Recommended fix:** Have §1 reference the §11 verdict label rather than restate a parallel
  classification, or merge the two verdicts.

## 9. Recommended fixes

### Must fix

* **P1** — Normalize the frontmatter: closing `---` on its own line, remove the blank line after
  the opening `---`. One-line change; foundational to the permission model.

### Should fix soon

* **P2** — Fall back to `overall` when the sanitized slug is empty.
* **P3** — Require an existence check per suffix candidate (or a single wildcard `Glob`).

### Optional improvements

* **P5** — Collapse the §1↔§11 verdict overlap.
* Add a slug length cap and collapse repeated hyphens.
* Add a one-line repo note that the legacy unprefixed `architecture-review.md` predates the new
  timestamped scheme.

## 10. Final verdict

**Ready after minor fixes.**

The updated `/arch-review` resolves v1's P1/P2/P3/P5, partially resolves P4, and adds a
well-designed, non-overwriting timestamped report mechanism. Scope, safety prose, and
consistency are now strong, and it runs no expensive or API-key-requiring operation. The single
must-fix is the malformed frontmatter close (P1) — trivial to apply but foundational because it
underpins the `allowed-tools` safety scoping. With P1 fixed (and ideally P2/P3), the command is
fully ready for repeated architecture reviews.
