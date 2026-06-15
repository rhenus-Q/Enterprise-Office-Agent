# Claude Command Review

Status: Review

Date: 2026-06-14

Target command: `.claude/commands/apply-command-review.md`

Report file: `docs/roadmap/commands-review/2026-06-14-apply-command-review-command-review-2.md`

## 1. Executive summary

**Ready to use.**

This is a re-review of `apply-command-review.md` after the optional drift-detection safeguard was
added to Step 5. The command remains a well-formed, tightly scoped single-file editing command: it
consumes a `/review-command` report, applies only Must-fix / Should-fix items traceable to that
report, and edits exactly one file under `.claude/commands/`. Frontmatter is valid, `allowed-tools`
is narrow and identical to its closest peer (`/update-claude-md`), the safety constraints are
comprehensive, and input handling is deterministic with explicit stop conditions. The new drift rule
closes the one previously-noted optional gap and is consistent with the command's existing
"stop, don't guess" posture. No Must-fix or Should-fix issues found.

## 2. Files reviewed

* `CLAUDE.md` (project rules / safety constraints — provided in context)
* `.claude/commands/apply-command-review.md` (target — including the new Step 5 drift rule)
* `.claude/commands/review-command.md` (producer of the report this command consumes)
* `.claude/commands/update-claude-md.md` (closest peer: an `Edit`-based, single-file editing command)
* `git status --short` (working-tree state)

## 3. Frontmatter and permission review

Frontmatter is correct and complete, and unchanged since the prior review:

* Opening and closing delimiters are exactly `---`, no blank/malformed line after the opener.
* `description` is accurate and scoped.
* `argument-hint` is concrete and useful (gives a real example report path); single-quoted, which is
  harmless.
* `allowed-tools: Read, Edit, Glob, Grep, Bash(git status:*), Bash(git diff:*)` — identical to
  `/update-claude-md`, the right precedent for a single-file editor.

Permission safety:

* `Edit` is necessary and is the core action; restricted in prose to the target command file.
* `Read` is necessary (report + target + optional named peer files).
* `Bash(git status:*)` and `Bash(git diff:*)` cover all three Step 6 validation commands. No gap.
* No broad `Bash(*)`, no `Bash(uv run:*)`, no test-runner / full-eval / ingestion / API-key grants.
  No `Write`, no `MultiEdit`.
* `Glob` / `Grep` remain read-only and are retained for peer consistency (the user explicitly chose
  to keep them). Harmless.

## 4. Scope and safety review

Strong and now slightly stronger. The command:

* Restricts editing to the single target command file identified by the report, required to be under
  `.claude/commands/`, with `Edit` explicitly forbidden on any other file.
* Forbids creating new files, modifying the review report, or touching any other command.
* Carries the full project protection list: `CLAUDE.md`, application code, tests, eval files, README,
  roadmap files, prompts, model names, corpus documents, `.env` / `.env.example`; forbids running
  tests, full eval, `ingestion.py`, `tests/chains/`, API-key commands; forbids commits and branch
  creation/switching.
* Forbids adding broad permissions during a fix and gates adding `Write`/`Edit` on the report
  explicitly calling for it.

**New: drift safeguard (Step 5).** Before applying a fix, the command now requires confirming the
targeted text still exists; if the report refers to text, wording, frontmatter, permission lines, or
sections no longer present, it must stop and report review drift, naming the un-appliable fix, and
must not guess or perform a broader rewrite. This is a genuine safety improvement: it prevents a
stale report from driving a confused or partial edit, and it reinforces the command's minimal-diff
intent.

Graph-routing / `stop_reason` / fallback-policy semantics are not separately enumerated, which
remains correct — this command edits only command-prose files, and "Do not modify application code"
already covers runtime behavior.

## 5. Input handling review

Deterministic and safe (unchanged):

* Empty `$ARGUMENTS` → stop and ask for a report path.
* Input treated strictly as a file path; missing report → fixed stop message, with explicit
  "Do not search the whole repo for a replacement report."
* Report missing a `Target command:` → stop and ask explicitly.
* Target not under `.claude/commands/` → stop. Target file missing → stop and report.

Over-application guardrails are good (Must then Should only; optional fixes require an explicit
opt-in token; "do not manufacture extra fixes"; "only apply fixes directly traceable to the report";
no-op when verdict is `Ready to use` with no Must/Should items). The drift rule adds a further
stop-condition for the previously-identified stale-report edge case, so the prior "minor gap" is now
resolved.

## 6. Output behavior review

Correct for an editing command (unchanged):

* No new files created; edits minimal and localized; existing command style preserved.
* Validation diff scoped to the target file (`git diff -- <target>`, `git diff --stat -- <target>`).
* Correctly anticipates that an untracked target yields empty `git diff` output — accurate, since the
  target itself is currently untracked (`??`).
* Final response is explicit (report path, target, applied/skipped fixes + why, single-file and
  protected-areas confirmations, the two git outputs) and recommends a sensible next step
  (`/review-command /<target>`).

The drift rule's "stop and report review drift" path integrates cleanly with the existing final
response, which already accounts for fixes skipped and the reasons.

## 7. Project fit and consistency review

Fits cleanly and mirrors established conventions:

* `allowed-tools`, the "Do not modify / Do not run" block, "Use as few tools as possible", and the
  Step 6 git-validation pattern all match `/update-claude-md`.
* Extracted report sections (`Target command:`, `Final verdict`, `Problems found`,
  `Recommended fixes`, `Must fix`, `Should fix soon`, `Optional improvements`) line up exactly with
  the structure emitted by `/review-command`. Producer/consumer contract is consistent.
* The drift rule's wording ("Stop and report... Do not guess... do not perform a broader rewrite")
  matches the deterministic, no-guess tone used elsewhere in the command and across peers.
* Completes the review loop: `/review-command` → `/apply-command-review`.

No over-engineering, no broad searches, no noisy-artifact risk (produces no report, creates no files).

## 8. Problems found

No Must-fix or Should-fix problems were found. Optional items only (carried over; both are deliberate
choices the user has elected to keep):

* **Issue:** `argument-hint` is single-quoted while peer commands leave it unquoted.
  **Why it matters:** Trivial stylistic inconsistency.
  **Risk level:** Low.
  **Recommended fix:** Optional — leave as-is (quoting is harmless) or drop quotes to match peers.

* **Issue:** `Glob` and `Grep` are granted but not strictly exercised by the prose flow.
  **Why it matters:** Slightly wider read surface than demonstrably needed; both read-only, no real
  safety cost.
  **Risk level:** Low.
  **Recommended fix:** Optional — keep for peer consistency (the user's chosen stance) or trim.

The previously-flagged drift gap has been **resolved** by the new Step 5 rule.

## 9. Recommended fixes

### Must fix

* None.

### Should fix soon

* None.

### Optional improvements

* Align `argument-hint` quoting with peer commands (cosmetic).
* Optionally trim `Glob`/`Grep` from `allowed-tools` (currently kept for consistency).

## 10. Final verdict

**Ready to use.**
