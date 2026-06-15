# Claude Command Review

Status: Review

Date: 2026-06-14

Target command: `.claude/commands/apply-command-review.md`

Report file: `docs/roadmap/commands-review/2026-06-14-apply-command-review-command-review.md`

## 1. Executive summary

**Ready to use.**

`apply-command-review.md` is a well-formed, tightly scoped editing command. It consumes a
`/review-command` report, applies only the Must-fix / Should-fix items it traces back to that
report, and edits exactly one file: the reviewed command under `.claude/commands/`. Frontmatter is
valid, `allowed-tools` is narrow and identical to its closest peer (`/update-claude-md`), the safety
constraints are comprehensive, input handling is deterministic with explicit stop conditions, and
the validation step correctly anticipates untracked-file behavior. No Must-fix or Should-fix issues
were found — only a couple of optional polish items.

## 2. Files reviewed

* `CLAUDE.md` (project rules / safety constraints — provided in context)
* `.claude/commands/apply-command-review.md` (target)
* `.claude/commands/review-command.md` (producer of the report this command consumes)
* `.claude/commands/update-claude-md.md` (closest peer: an `Edit`-based, single-file editing command)
* `git status --short` (working-tree state)

## 3. Frontmatter and permission review

Frontmatter is correct and complete:

* Opening and closing delimiters are exactly `---`, with no blank or malformed line after the opener.
* `description` is accurate and scoped: "Apply fixes from a Claude command review report to the
  reviewed command file."
* `argument-hint` is concrete and useful (gives a real example report path). It is single-quoted;
  the peer `/update-claude-md` leaves its hint unquoted. The quoting is harmless (and arguably safer),
  so this is only a cosmetic inconsistency.
* `allowed-tools: Read, Edit, Glob, Grep, Bash(git status:*), Bash(git diff:*)` — identical to
  `/update-claude-md`, which is the right precedent for a single-file editor.

Permission safety:

* `Edit` is necessary and is the command's core action.
* `Read` is necessary (report + target + optional peer files).
* `Bash(git status:*)` and `Bash(git diff:*)` cover all three Step 6 validation commands
  (`git status --short`, `git diff -- <file>`, `git diff --stat -- <file>`). No permission gap.
* No broad `Bash(*)`, no `Bash(uv run:*)`, no test-runner, full-eval, ingestion, or API-key
  permissions. No `Write`, no `MultiEdit`.
* `Glob` / `Grep` are read-only and present for consistency with peers, but the prose flow
  (read explicit report path → read target → optionally read named peer files) does not strictly
  require them. Harmless; noted as optional.

## 4. Scope and safety review

Strong. The command:

* Restricts editing to "only the target command file identified by the review report" and requires
  that file to be under `.claude/commands/`.
* States `Edit` may be used only on the target command file ("Do not use `Edit` on any other file").
* Explicitly forbids creating new files, modifying the review report, or touching any other command.
* Carries the full project protection list: `CLAUDE.md`, application code, tests, eval files, README,
  roadmap files, prompts, model names, corpus documents, `.env` / `.env.example`.
* Forbids running tests, full eval, `ingestion.py`, `tests/chains/`, and API-key commands; forbids
  commits and branch creation/switching.
* Forbids adding broad permissions during a fix (`Bash(*)`, `Bash(uv run:*)`, broad test/eval/
  ingestion/API-key grants) and gates adding `Write`/`Edit` on the report explicitly calling for it.

This is a review-fix command that cannot escape its lane. Graph-routing / `stop_reason` /
fallback-policy semantics are not separately enumerated, but that is correct here: this command edits
only command-prose files, and "Do not modify application code" already covers runtime behavior. (The
peer `/update-claude-md` enumerates those semantics specifically because it edits `CLAUDE.md`, which
*describes* them — not applicable to this command.)

## 5. Input handling review

Deterministic and safe:

* Empty `$ARGUMENTS` → stop and ask for a report path.
* Input treated strictly as a file path; missing report → fixed stop message, with explicit
  "Do not search the whole repo for a replacement report."
* Report missing a `Target command:` → stop and ask for the target explicitly.
* Target not under `.claude/commands/` → stop.
* Target command file missing → stop and report.

Guardrails against over-application are good: apply Must-fix then Should-fix only; optional/cosmetic
fixes require an explicit opt-in token (`include optional` / `--include-optional` / `apply optional`);
"do not manufacture extra fixes"; "only apply fixes directly traceable to the review report"; and a
no-op path when the verdict is `Ready to use` with no Must/Should items.

Minor gap (optional): no explicit handling for *drift* — if the target command changed since the
review was written, a recommended edit may no longer match. The minimal-edit + "traceable to the
report" rules mitigate this, but a one-line "if the report's described text is no longer present,
stop and report drift" would harden it.

## 6. Output behavior review

Correct for an editing command (not a report producer):

* No new files created; edits are minimal and localized; existing command style preserved.
* Validation diff is scoped to the target file (`git diff -- <target-command-file>`,
  `git diff --stat -- <target-command-file>`).
* Correctly anticipates that a brand-new/untracked target command yields empty `git diff` output and
  states that is expected — relevant here, since the target itself is currently untracked (`??`).
* Final response is explicit: report path, target file, whether edits were applied, fixes applied,
  fixes skipped + why, single-file-modification confirmation, the protected-areas confirmation, and
  the two git outputs. It then recommends a sensible next step (`/review-command /<target>`).

## 7. Project fit and consistency review

Fits cleanly into the command-review workflow and mirrors established conventions:

* `allowed-tools`, the "Do not modify / Do not run" block, "Use as few tools as possible", and the
  Step 6 git-validation pattern all match `/update-claude-md` (the closest editing peer).
* The report sections it extracts (`Target command:`, `Final verdict`, `Problems found`,
  `Recommended fixes`, `Must fix`, `Should fix soon`, `Optional improvements`) line up exactly with
  the report structure emitted by `/review-command` (sections 9–10). The producer/consumer contract
  is consistent.
* Completes the review loop: `/review-command` (writes report) → `/apply-command-review` (applies it).
* Final-response format is a structured bullet list rather than the rigid fixed template used by
  `/update-claude-md` and `/review-command`; adequate and clear, slightly less prescriptive.

No over-engineering, no broad searches, no noisy-artifact risk (it produces no report and creates no
files).

## 8. Problems found

No Must-fix or Should-fix problems were found. Optional items only:

* **Issue:** `argument-hint` is single-quoted while peer commands leave it unquoted.
  **Why it matters:** Trivial stylistic inconsistency across the command set.
  **Risk level:** Low.
  **Recommended fix:** Optional — drop the quotes to match peers, or leave as-is (quoting is harmless).

* **Issue:** `Glob` and `Grep` are granted but not strictly exercised by the prose flow.
  **Why it matters:** Slightly wider read surface than the command demonstrably needs; both are
  read-only, so there is no real safety cost.
  **Risk level:** Low.
  **Recommended fix:** Optional — keep for peer consistency, or trim to `Read, Edit, Bash(git status:*),
  Bash(git diff:*)`.

* **Issue:** No explicit drift check between the report's described text and the current target file.
  **Why it matters:** A stale report could describe text that no longer exists, leading to a confused
  or partial edit.
  **Risk level:** Low.
  **Recommended fix:** Optional — add a one-line rule: if the text a fix targets is no longer present,
  stop and report drift instead of editing.

## 9. Recommended fixes

### Must fix

* None.

### Should fix soon

* None.

### Optional improvements

* Align `argument-hint` quoting with peer commands.
* Trim `Glob`/`Grep` from `allowed-tools` if you want minimal grants (or keep for consistency).
* Add a short drift-detection note in Step 5.

## 10. Final verdict

**Ready to use.**
