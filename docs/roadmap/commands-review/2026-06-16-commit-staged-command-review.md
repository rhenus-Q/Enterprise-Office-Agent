# Claude Command Review

Status: Review

Date: 2026-06-16

Target command: `.claude/commands/commit-staged.md`

Report file: `docs/roadmap/commands-review/2026-06-16-commit-staged-command-review.md`

## 1. Executive summary

**Ready after minor fixes.**

The command's intent, workflow, and safety prose are good: it commits only already-staged changes,
explicitly refuses `git add`/push/branch operations, and screens the staged diff for secrets and
generated artifacts. However the **YAML frontmatter is malformed** — there is a blank line
immediately after the opening `---`, and the closing delimiter is a ~90-character run of dashes
instead of exactly `---`. This can prevent the frontmatter (including `allowed-tools`) from being
parsed correctly and must be fixed before relying on the command. Two smaller issues (no
"nothing staged" handling; an unused `git ls-files` permission and an over-broad `git commit` scope)
should also be addressed.

(Note: the invocation `/commit-satged` was a typo; resolved via close-match to the single candidate
`.claude/commands/commit-staged.md`.)

## 2. Files reviewed

* `CLAUDE.md` (project rules, in context)
* `.claude/commands/commit-staged.md` (target)
* `.claude/commands/review-diff.md` (peer — the natural predecessor command)

## 3. Frontmatter and permission review

**Frontmatter is malformed — High priority.**

```
1  ---
2  (blank line)
3  description: ...
4  argument-hint: ...
5  allowed-tools: ...
6  -----------------------------------------------... (≈90 dashes)
```

* Line 2 is a blank line directly after the opening `---`.
* Line 6 is **not** a valid `---` closing delimiter; it is a long dash run. Claude Code expects the
  block to close with exactly `---`.

Consequence: the frontmatter (notably `allowed-tools`) may fail to parse, in which case the command
could lose its tool allowlist and prompt for every tool call — undesirable for a command that runs
`git commit`. This should be corrected to a clean block:

```
---
description: Commit currently staged changes with a generated commit message
argument-hint: Optional commit intent, for example "eval history delta reporting"
allowed-tools: Bash(git status:*), Bash(git diff:*), Bash(git commit:*)
---
```

`description` and `argument-hint` content are appropriate.

`allowed-tools` content review:
* `Bash(git status:*)` — used in Steps 1 and 5. Needed.
* `Bash(git diff:*)` — used (`git diff --cached`). Needed.
* `Bash(git ls-files:*)` — **not referenced anywhere in the body.** Unused; drop it.
* `Bash(git commit:*)` — used in Step 4. Needed, but see §4 (scope is broad enough to permit
  `git commit -a` / `--no-verify`, which the prose forbids).

No `Bash(git add:*)`, no push permission, no test/eval/ingestion/API-key permissions, no broad
`Bash(*)` or `Bash(uv run:*)`. The permission surface (once `git ls-files` is removed) is otherwise
appropriately minimal.

## 4. Scope and safety review

Scope is clearly stated and well-guarded for a commit command:

* "Only commit staged changes"; "Do not run `git add`/`git add .`"; "Do not stage unstaged files";
  "Do not push"; "Do not create or switch branches." Good.
* Step 2 blocks committing `.env`, `.env.example`, secrets/tokens, `chroma_db/`, `__pycache__/`,
  `.mypy_cache/`, `.pytest_cache/`, generated `evals/history/*.json`, and unrelated files — strong,
  project-aware screening.
* "Do not amend unless the user explicitly asks." Good.

Gaps:

* `Bash(git commit:*)` permits flags the prose forbids in spirit — e.g. `git commit -a` (which would
  pull in unstaged tracked changes) or `git commit --no-verify` (skips hooks). The prose says commit
  only staged changes, but the permission glob does not enforce it. Worth a one-line explicit
  prohibition ("Do not use `git commit -a`/`-am` or `--no-verify`").
* The command does not add a Co-Authored-By trailer, which the environment's git guidance calls for
  on commit messages. Optional, but mentioning it would align generated commits with project
  conventions.

## 5. Input handling review

* Optional intent via `$ARGUMENTS` — empty input is handled implicitly (message generated from the
  staged diff). Reasonable.
* **Nothing-staged case is not handled.** If there are no staged changes, `git commit` will fail (or
  with `-a` could behave unexpectedly). The command should detect an empty staged diff in Step 1 and
  stop with a clear message ("No staged changes — stage files first, then re-run").
* Unrelated/unsafe staged files → Step 2 stops and tells the user what to unstage. Good.
* Repeated runs: each run commits whatever is currently staged; no collision concerns (not a
  report-producing command).

## 6. Output behavior review

This is an action command, not a report command, so report-collision rules do not apply.

* It does not write any files; it only creates a commit. Correct.
* Final response (Step 5) reports the commit message, files committed, confirmation that no push ran,
  and `git status --short`. Appropriate and scoped.
* It correctly avoids `git add` and push, so it cannot expand beyond the staged set (provided the
  `git commit -a` gap in §4 is closed).

## 7. Project fit and consistency review

Good fit. It is the natural action counterpart to `/review-diff`, which ends by *suggesting* a
`git add` + `git commit`; `/commit-staged` then commits the already-staged result. The two are
complementary and consistent in safety wording (no push, no branch, secret/generated-file
awareness).

Final-response format is simpler than the report commands (`/plan-spec`, `/arch-review`), which is
appropriate for an action command. No template misuse, no over-engineering, no roadmap-noise risk.

## 8. Problems found

1. **Malformed YAML frontmatter (blank first line + dash-run closing delimiter).**
   * Why it matters: frontmatter (including `allowed-tools`) may fail to parse, dropping the tool
     allowlist and causing per-call permission prompts, or mis-rendering the block as body content.
   * Risk level: High.
   * Recommended fix: remove the blank line after the opening `---` and replace the long dash run
     with exactly `---`.

2. **No handling for the "nothing staged" case.**
   * Why it matters: `git commit` with an empty index fails or behaves confusingly; the command
     should fail fast with guidance.
   * Risk level: Medium.
   * Recommended fix: in Step 1, if `git diff --cached --stat` is empty, stop and tell the user to
     stage files first.

3. **`Bash(git commit:*)` is broad enough to allow `-a` / `--no-verify`.**
   * Why it matters: the glob permits commit flags that would violate the "only staged changes" and
     hook-respecting intent.
   * Risk level: Medium.
   * Recommended fix: add an explicit prose prohibition on `git commit -a`/`-am` and `--no-verify`.

4. **Unused `Bash(git ls-files:*)` permission.**
   * Why it matters: unused permissions widen the surface and misrepresent the command's behavior.
   * Risk level: Low.
   * Recommended fix: remove it from `allowed-tools`.

5. **No Co-Authored-By trailer guidance.**
   * Why it matters: project/environment git guidance expects the trailer on commit messages.
   * Risk level: Low.
   * Recommended fix: optionally instruct Step 3 to append the Co-Authored-By trailer.

## 9. Recommended fixes

### Must fix

* Repair the frontmatter delimiters (Problem 1).

### Should fix soon

* Handle the empty-staged-index case (Problem 2).
* Forbid `git commit -a`/`--no-verify` in prose (Problem 3).

### Optional improvements

* Drop the unused `git ls-files` permission (Problem 4).
* Add Co-Authored-By trailer guidance (Problem 5).

## 10. Final verdict

**Ready after minor fixes.**
