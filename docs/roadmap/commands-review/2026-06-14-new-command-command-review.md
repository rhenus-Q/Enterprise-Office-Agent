# Claude Command Review

Status: Review

Date: 2026-06-14

Target command: `.claude/commands/new-command.md`

Report file: `docs/roadmap/commands-review/2026-06-14-new-command-command-review.md`

## 1. Executive summary

**Ready after minor fixes.**

`new-command.md` is a meta-command that generates new Claude Code command files. Its *body* is
excellent: tightly scoped (creates exactly one file under `.claude/commands/`), thorough input
normalization and collision handling, and — most impressively — it propagates this project's
least-privilege and safety posture into the commands it generates (Step 5 tool patterns, Step 7
project-critical protections including privacy mode).

It is held back by one real defect: **malformed YAML frontmatter**. The block has a blank line
after the opening `---`, closes with a long run of dashes instead of `---`, and uses an unquoted
`argument-hint` containing `: `. This is not theoretical — the command currently registers in the
skills list with its description shown as a row of dashes, confirming the frontmatter is not
parsing as intended. The fix is trivial and mechanical. A secondary least-privilege nit
(`Bash(mkdir:*)` is unnecessary) should also be addressed.

## 2. Files reviewed

* `CLAUDE.md` (project rules — in context)
* `.claude/commands/new-command.md` (target — full read, 344 lines)
* Peer commands for consistency (in context this session): `arch-review.md`, `review-diff.md`,
  `implement-spec.md`, `new-spec.md`, `plan-spec.md`, and `update-claude-md.md`
* `review-command.md` (effectively reviewed — its body is the injected `/review-command` prompt)
* `git status --short`
* `.claude/commands/` and `docs/roadmap/commands-review/` inventories (Glob)

## 3. Frontmatter and permission review

### Frontmatter — malformed (primary finding)

Current block (lines 1–6):

```
---
<blank line>
description: Create a new Claude Code command file from a command name and purpose
argument-hint: Command name plus purpose, for example "review-config: review config files for safety and consistency"
allowed-tools: Read, Write, Glob, Grep, Bash(git status:*), Bash(mkdir:*)
-------------------------------------------------------------------------
```

Three problems:

1. **Blank line after the opening `---`** (line 2). Non-standard; many frontmatter parsers expect
   the first key immediately after the opening delimiter.
2. **Closing delimiter is a long dash run** (line 6: `----…----`) instead of exactly `---`. A
   parser requiring `^---$` will not recognize this as the closing delimiter.
3. **`argument-hint` is an unquoted plain scalar containing `: `** (`"review-config: review …"`).
   A `: ` inside a plain YAML scalar can trigger a "mapping values are not allowed here" parse
   error or misparse.

**Observed consequence (not theoretical):** in the current available-skills listing, `new-command`
appears with its description rendered as a row of dashes rather than "Create a new Claude Code
command file …". Every other command in the suite shows its real description. This strongly
indicates the malformed delimiter/blank line is leaking into metadata parsing. The same parsing
fragility puts the `allowed-tools` allowlist at risk of being dropped — a safety-relevant outcome
for a command whose job is to `Write` files.

**Irony worth noting:** the command itself correctly instructs *generated* commands to use a clean
`---` … `---` frontmatter block (Step 6, lines 226–234), yet its own file violates that rule.

### allowed-tools — mostly correct, one unnecessary grant

`allowed-tools: Read, Write, Glob, Grep, Bash(git status:*), Bash(mkdir:*)`

| Tool | Verdict | Notes |
|------|---------|-------|
| `Read` | Necessary | Reads `CLAUDE.md` and peer commands (Step 3). |
| `Write` | Necessary | Creates the new command file (Step 6). |
| `Glob` | Necessary | Existence check (Step 2) and peer discovery. |
| `Grep` | Borderline | No clear content-search need; peers are read via `Read`. Could be dropped for least-privilege. Read-only, so no risk. |
| `Bash(git status:*)` | Necessary | Steps 3 and 8. |
| `Bash(mkdir:*)` | **Unnecessary** | The target directory `.claude/commands/` always exists (the command itself lives there), so no directory is ever created. This contradicts the command's own Step 4 guidance: "Do not grant tools just because peer commands have them. Grant only what the new command actually needs." |

No `Edit`/`MultiEdit` (correct — it only creates new files and forbids modifying existing ones), no
`Bash(*)`, no `Bash(uv run:*)`, no test/eval/ingestion/API-key permissions. Aside from `mkdir`
(and arguably `Grep`), the set is appropriate.

## 4. Scope and safety review

The command's own scope is well-fenced:

* "Create exactly one new file under `.claude/commands/`" + "Do not modify existing command files."
* Full protected litany: `CLAUDE.md`, application code, tests, eval files, README, roadmap files,
  prompts, model names, corpus, `.env`/`.env.example`.
* Forbidden ops: tests, full eval, `ingestion.py`, `tests/chains/`, API-key commands, commit,
  branch.
* `Write` is restricted in prose to `.claude/commands/<command-name>.md`; Step 2 refuses to
  overwrite or create a suffixed duplicate. Correct for commands (you do not want silent
  duplicates).
* Correctly separated from review: "It does not review the command … does not write a command
  review report," and Step 9 recommends `/review-command` as the next step.

**Meta-safety (strong):** because this command generates *other* commands, the relevant safety is
two-layered, and the second layer is handled well:

* Step 5 enforces narrowest-safe `allowed-tools` for generated commands and explicitly forbids
  `Bash(*)`, `Bash(uv run:*)`, broad test/full-eval/ingestion/API-key grants unless explicitly
  required.
* Step 7 requires generated commands to protect the full project-critical set — prompts, model
  names, corpus, `.env(.example)`, graph behavior/routing/nodes, `stop_reason` semantics, fallback
  policy semantics, **privacy mode**, full eval, `ingestion.py`, `tests/chains/`, API-key commands,
  commits, branches — and codifies "documentation commands must not touch code / review commands
  must not fix code."

This is the most security-conscious command in the suite and a good fit for the project.

## 5. Input handling review

| Case | Handled? | Detail |
|------|----------|--------|
| Empty `$ARGUMENTS` | Yes | Step 1 stops and asks for a command name + purpose. |
| Name + purpose parsing | Yes | Accepts `name: purpose`, `/name purpose`, `name - purpose`; thorough name normalization (trim, strip `/` and `.md`, spaces/underscores→hyphens, lowercase, collapse/strip hyphens). |
| Empty name after normalization | Yes | Stops and asks for a clearer name. |
| Missing/vague purpose | Yes | Stops and asks for a clearer purpose. |
| Existing-file collision | Yes | Step 2 stops, refuses overwrite and suffixed duplicate, points to `/review-command` or manual edit. |
| Repeated runs | Yes | Idempotent via the existence check (no second file is created). |

Input handling is the strongest part of the command and is more rigorous than several peers.

## 6. Output behavior review

File-creating command checks pass:

* **Output directory** explicit: `.claude/commands/`.
* **Filename convention** explicit: `<command-name>.md` with full normalization.
* **Collision handling**: stop, no overwrite, no suffixed duplicate (deliberately different from
  the auto-suffixing used by *report* commands — correct here).
* **Validation (Step 8)**: `git status --short` + `git diff --stat -- .claude/commands/<name>.md`,
  with an accurate note that an untracked file shows an empty diff (matches real behavior).
* **Final response (Step 9)**: reports path, name, category, chosen tools + rationale, confirms no
  other files changed, echoes git status/diff, and recommends `/review-command /<name>`.

## 7. Project fit and consistency review

Strong fit:

* Structure mirrors the suite (role statement, `User input: $ARGUMENTS`, scope, forbidden ops,
  numbered steps, validation, final response).
* Path conventions (`.claude/commands/`), "Use as few tools as possible," and the safety-litany
  wording all match peers.
* The Step 5 tool patterns are accurate against the real commands (e.g. the single-file-edit
  pattern exactly matches `update-claude-md.md`; the report pattern matches `arch-review.md`).
* Completes a clean meta-workflow: `/new-command` → `/review-command`, complementing the existing
  `/new-spec → /plan-spec → /implement-spec → /review-diff → /update-claude-md` chain.

No over-engineering, no noisy-artifact risk (it writes one command file and explicitly defers
review/reporting to `/review-command`).

## 8. Problems found

### P1 — Malformed YAML frontmatter

* **Issue:** Blank line after the opening `---` (line 2); closing delimiter is a long dash run
  instead of `---` (line 6); `argument-hint` is an unquoted plain scalar containing `: ` (line 4).
* **Why it matters:** The frontmatter is not parsing as intended — the command currently registers
  with its description shown as a row of dashes. Beyond the cosmetic description break, the same
  fragility risks the `allowed-tools` allowlist being dropped, which would remove the intended
  permission fence from a `Write`-capable command.
* **Risk level:** Medium.
* **Recommended fix:** Normalize the block to:
  ```
  ---
  description: Create a new Claude Code command file from a command name and purpose
  argument-hint: 'Command name plus purpose, e.g. "review-config: review config files for safety and consistency"'
  allowed-tools: Read, Write, Glob, Grep, Bash(git status:*)
  ---
  ```
  (no leading blank line; exactly `---` to close; single-quote the `argument-hint` value so the
  embedded `: ` is safe).

### P2 — Unnecessary `Bash(mkdir:*)` permission

* **Issue:** `Bash(mkdir:*)` is granted, but the only write target lives in `.claude/commands/`,
  which always exists; no directory is ever created.
* **Why it matters:** Violates least privilege and the command's own Step 4 guidance ("Grant only
  what the new command actually needs"). Low intrinsic danger, but unnecessary surface area.
* **Risk level:** Low.
* **Recommended fix:** Remove `Bash(mkdir:*)` from `allowed-tools` (reflected in the P1 snippet
  above). Drop the Step 8 implication that a directory might need creating, if any.

### P3 — `Grep` likely unused

* **Issue:** `Grep` is granted but peer commands are read via `Read` and existence is checked via
  `Glob`; no content search is described.
* **Why it matters:** Minor least-privilege tidy-up; read-only, so no real risk.
* **Risk level:** Low.
* **Recommended fix:** Drop `Grep` unless a concrete content-search step is added.

## 9. Recommended fixes

### Must fix

* **P1** — repair the frontmatter (remove the leading blank line, close with exactly `---`, quote
  the `argument-hint`). This is the only thing preventing "Ready to use."

### Should fix soon

* **P2** — remove the unnecessary `Bash(mkdir:*)` grant.

### Optional improvements

* **P3** — drop `Grep` if no content search is needed.
* Consider having the generated-command template (Step 6) include the same explicit "no leading
  blank line / close with `---`" reminder, so generated commands do not inherit this mistake.

## 10. Final verdict

**Ready after minor fixes.**

The command body is well-designed, tightly scoped, and propagates this project's safety and
least-privilege posture into the commands it generates — arguably the strongest meta-command in the
suite. The blocker is purely the malformed frontmatter (P1), which is already producing an
observable broken description in the skills list and risks dropping the `allowed-tools` fence; it is
a trivial mechanical fix. After P1 (and ideally P2), this is ready to use.
