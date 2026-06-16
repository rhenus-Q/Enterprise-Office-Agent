# Claude Command Review

Status: Review

Date: 2026-06-16

Target command: `.claude/commands/commit-staged.md`

Report file: `docs/roadmap/commands-review/2026-06-16-commit-staged-command-review-2.md`

## 1. Executive summary

**Ready to use.**

This is a re-review after the fixes from
`docs/roadmap/commands-review/2026-06-16-commit-staged-command-review.md` were applied. All Must fix
and Should fix soon items are resolved: the frontmatter is now a clean `---` … `---` block, the
empty-staged-index case is handled, and `git commit -a`/`-am`/`--no-verify` are explicitly
forbidden. The command is correct, safe, narrowly scoped, and consistent with the project's command
workflow. Only two Optional improvements from the prior review remain, neither blocking.

## 2. Files reviewed

* `CLAUDE.md` (project rules, in context)
* `.claude/commands/commit-staged.md` (target, current state)
* `.claude/commands/review-diff.md` (peer — the predecessor command, reviewed earlier)
* Prior report: `docs/roadmap/commands-review/2026-06-16-commit-staged-command-review.md`

## 3. Frontmatter and permission review

Frontmatter is now **valid**: opening `---` on line 1, no blank line after it, three clean keys, and
a proper `---` closing delimiter on line 5. The earlier malformed dash-run closer is gone.

* `description` / `argument-hint` — appropriate and unchanged.
* `allowed-tools`: `Bash(git status:*), Bash(git diff:*), Bash(git ls-files:*), Bash(git commit:*)`.
  * `git status` — used (Steps 1, 5). Needed.
  * `git diff` — used (`git diff --cached`). Needed.
  * `git ls-files` — still **unused** in the body (Optional removal from the prior review, not yet
    applied). Low risk.
  * `git commit` — used (Step 4). Needed; the glob breadth is now mitigated by explicit prose
    prohibitions on `-a`/`-am`/`--no-verify`.

No push, `git add`, test, eval, ingestion, or API-key permissions. No broad `Bash(*)` or
`Bash(uv run:*)`. Permission surface is safe.

## 4. Scope and safety review

Scope remains clearly stated and well-guarded:

* Commits only staged changes; refuses `git add`/`git add .`, staging unstaged files, push, and
  branch operations.
* **New:** Step 1 stops if `git diff --cached --stat` is empty and refuses to create an empty commit.
* **New:** Step 4 forbids `git commit -a`/`-am` (no pulling in unstaged tracked changes) and
  `--no-verify` (no bypassing hooks), closing the gap between the broad `Bash(git commit:*)` glob and
  the staged-only intent.
* Step 2 still screens for `.env`/`.env.example`, secrets, `chroma_db/`, caches, generated
  `evals/history/*.json`, and unrelated files. Strong, project-aware.
* "Do not amend unless the user explicitly asks." Preserved.

## 5. Input handling review

* Optional intent via `$ARGUMENTS`; empty input handled implicitly (message generated from the
  staged diff). Reasonable.
* Empty staged index — now handled (stops with guidance). Resolved.
* Unsafe/unrelated staged files — Step 2 stops and names what to unstage. Good.
* Repeated runs — each run commits the current staged set; no collision concerns (not a
  report-producing command).

## 6. Output behavior review

Action command, not a report command. It writes no files, only creates a commit, and cannot expand
beyond the staged set now that `-a` is prohibited. Final response (Step 5) reports the commit
message, files committed, no-push confirmation, and `git status --short`. Appropriately scoped.

## 7. Project fit and consistency review

Good fit and complementary to `/review-diff` (which ends by suggesting `git add` + commit;
`/commit-staged` then commits the staged result). Safety wording (no push, no branch,
secret/generated-file awareness) is consistent with peer commands. Final-response format is
appropriately lighter than the report commands. No template misuse or roadmap-noise risk.

## 8. Problems found

1. **Unused `Bash(git ls-files:*)` permission.**
   * Why it matters: unused permissions widen the surface and misrepresent behavior.
   * Risk level: Low.
   * Recommended fix: remove it from `allowed-tools` (carried over from the prior review's Optional
     list).

2. **No Co-Authored-By trailer guidance.**
   * Why it matters: the environment's git guidance expects the trailer on commit messages; generated
     commits will omit it.
   * Risk level: Low.
   * Recommended fix: optionally instruct Step 3 to append the Co-Authored-By trailer.

No Must fix or Should fix soon items remain.

## 9. Recommended fixes

### Must fix

* None.

### Should fix soon

* None.

### Optional improvements

* Remove the unused `git ls-files` permission (Problem 1).
* Add Co-Authored-By trailer guidance to Step 3 (Problem 2).

## 10. Final verdict

**Ready to use.**
