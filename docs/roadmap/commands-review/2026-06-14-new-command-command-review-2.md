# Claude Command Review

Status: Review

Date: 2026-06-14

Target command: `.claude/commands/new-command.md`

Report file: `docs/roadmap/commands-review/2026-06-14-new-command-command-review-2.md`

## 1. Executive summary

**Ready to use.**

This is a re-review of `new-command.md` after the fixes recommended in the prior report
(`docs/roadmap/commands-review/2026-06-14-new-command-command-review.md`) were applied. Both
blocking/should-fix findings are now resolved:

* **P1 — malformed frontmatter** is fixed: standard `---` open/close, no leading blank line, and a
  single-quoted `argument-hint`. Confirmed live — the command now registers in the skills list with
  its real description instead of a row of dashes.
* **P2 — unnecessary `Bash(mkdir:*)`** is removed; `allowed-tools` is now the narrowest correct set.

The optional Step 6 frontmatter-hygiene reminder was also added, which propagates the fix forward to
every command this meta-command generates. `Grep` was intentionally retained. Only one trivial,
optional nit remains (P3 — `Grep`). The command is safe and ready to use.

## 2. Files reviewed

* `CLAUDE.md` (project rules — in context)
* `.claude/commands/new-command.md` (target — current post-fix state)
* Peer commands (in context this session): `arch-review.md`, `review-diff.md`, `implement-spec.md`,
  `new-spec.md`, `plan-spec.md`, `update-claude-md.md`, `review-command.md`
* Prior review: `docs/roadmap/commands-review/2026-06-14-new-command-command-review.md`
* `git status --short`; `docs/roadmap/commands-review/` inventory (Glob)

## 3. Frontmatter and permission review

### Frontmatter — now well-formed (P1 resolved)

Current block (lines 1–5):

```
---
description: Create a new Claude Code command file from a command name and purpose
argument-hint: 'Command name plus purpose, e.g. "review-config: review config files for safety and consistency"'
allowed-tools: Read, Write, Glob, Grep, Bash(git status:*)
---
```

* Opening `---` immediately followed by the first key (no blank line). ✓
* Closing delimiter is exactly `---` (the long dash run is gone). ✓
* `argument-hint` is single-quoted, so the embedded `: ` is safe YAML. ✓
* **Live confirmation:** `new-command` now appears in the available-skills list with the correct
  description ("Create a new Claude Code command file from a command name and purpose"), where it
  previously showed dashes. This confirms the metadata now parses, and with it the `allowed-tools`
  fence is reliably applied.

### allowed-tools — now minimal (P2 resolved)

`allowed-tools: Read, Write, Glob, Grep, Bash(git status:*)`

| Tool | Verdict | Notes |
|------|---------|-------|
| `Read` | Necessary | Reads `CLAUDE.md` and peer commands (Step 3). |
| `Write` | Necessary | Creates the new command file (Step 6). |
| `Glob` | Necessary | Existence check (Step 2) and peer discovery. |
| `Grep` | Borderline (retained) | No content-search step is described, but it is read-only and was intentionally kept; harmless. |
| `Bash(git status:*)` | Necessary | Steps 3 and 8. |

`Bash(mkdir:*)` is now removed — correct, since the only write target lives in `.claude/commands/`,
which always exists. No `Edit`/`MultiEdit`, no `Bash(*)`, no `Bash(uv run:*)`, no
test/eval/ingestion/API-key grants. This is the narrowest correct set for the command's job.

## 4. Scope and safety review

Unchanged and strong (the edits did not touch the safety body):

* "Create exactly one new file under `.claude/commands/`" + "Do not modify existing command files."
* Full protected litany (`CLAUDE.md`, application code, tests, eval files, README, roadmap files,
  prompts, model names, corpus, `.env`/`.env.example`) plus the forbidden-ops litany (tests, full
  eval, `ingestion.py`, `tests/chains/`, API-key commands, commit, branch).
* `Write` restricted in prose to `.claude/commands/<command-name>.md`; Step 2 refuses overwrite and
  suffixed duplicates.
* Correctly separated from review (defers to `/review-command`).
* **Meta-safety remains excellent:** Step 5 enforces narrowest-safe `allowed-tools` for generated
  commands; Step 7 requires generated commands to protect the full project-critical set (incl.
  graph routing/nodes, `stop_reason`, fallback policy, privacy mode). The new Step 6 reminder now
  also makes generated commands inherit clean frontmatter (no leading blank line, exact `---`
  close, quoted `argument-hint` when it contains `: `) — a good forward-propagation of the P1 fix.

## 5. Input handling review

Unchanged and robust: empty input stops and asks; thorough name normalization; empty-name and
vague-purpose stops; existing-file collision stops without overwrite or suffixed duplicate; repeated
runs are idempotent via the existence check. Still the strongest input handling in the suite.

## 6. Output behavior review

Unchanged and correct: explicit output directory and filename convention; no-overwrite collision
handling; accurate Step 8 validation note that an untracked file yields an empty `git diff --stat`;
Step 9 final response reports path/name/category/tools and recommends `/review-command /<name>`.

## 7. Project fit and consistency review

Unchanged and strong. The frontmatter fix actually *improves* consistency: `new-command.md` now
matches the clean `---` … `---` frontmatter used by every peer, and its `allowed-tools` now follows
the project's own "report/file-writing command" pattern minus the unneeded `mkdir`. Completes the
`/new-command → /review-command` meta-workflow.

## 8. Problems found

No must-fix or should-fix problems remain. One trivial optional item:

### P3 — `Grep` retained without a described use

* **Issue:** `Grep` is granted but no content-search step is specified; peers are read via `Read`
  and existence is checked via `Glob`.
* **Why it matters:** Minor least-privilege tidy-up only; read-only, no real risk. It was kept
  deliberately.
* **Risk level:** Low.
* **Recommended fix (optional):** Drop `Grep` if no peer-content search is ever needed, or add a
  one-line note that `Grep` is for scanning peer command bodies.

## 9. Recommended fixes

### Must fix

* None. P1 (frontmatter) is resolved.

### Should fix soon

* None. P2 (`Bash(mkdir:*)`) is resolved.

### Optional improvements

* **P3** — drop `Grep`, or document its intended use.

## 10. Final verdict

**Ready to use.**

Both prior findings (P1 malformed frontmatter, P2 unnecessary `mkdir`) are fixed, confirmed live by
the corrected skill description, and the optional Step 6 reminder strengthens forward safety. The
command is well-scoped, safe, and the best-in-suite meta-generator; only a trivial `Grep`
least-privilege nit remains.
