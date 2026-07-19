# Claude Code Commands

Project-specific Claude Code slash commands for this repository, covering
**planning, evaluation, implementation, review, remediation, validation, and
repository maintenance**.

These commands **complement** the root [`CLAUDE.md`](../../CLAUDE.md); they do not
replace the project rules defined there. Each command file's own body is the
authoritative source of truth for its behavior — this README is a discovery index,
not a specification.

## Quick command catalog

| Command | Purpose | When to use | Input | Modifies files? | Main output |
|---|---|---|---|---|---|
| `/eval-imple` | Evaluate whether a proposed change is justified, then implement the smallest correct change — or none — and validate it. | You are unsure whether a proposed change is necessary. | Free-text change request | **Yes, or none** — code, only if justified ("no change" is a valid success) | In-chat report + implemented change (if any) |
| `/imple-spec` | Implement an already-approved spec or implementation plan. | A reviewed spec/plan already exists and the decision to build is made. | Spec/plan file path | **Yes** — code | Implemented changes + implementation report under `docs/roadmap/implementation/` |
| `/new-function-spec` | Create one implementation-ready function spec from a short feature description. Does not implement. | You want to turn an idea into a concrete spec before building. | Short feature description | **Yes** — new spec file under `docs/roadmap/spec/` | Spec file |
| `/review-diff` | Review the current working-tree git diff for safety, scope, and commit readiness. | Code has already changed and you want a pre-commit check. | Optional review focus | **No** (review-only) | In-chat review + commit recommendation |
| `/arch-review` | Review project architecture and write a timestamped report. | Broad architecture/design audit. | Optional focus | Report file only (no code) | Report under `docs/roadmap/architecture-review/` |
| `/security-review` | Review security, prompt-injection, and privacy risks; write a timestamped report. | Broad security/privacy audit. | Optional focus | Report file only (no code) | Report under `docs/roadmap/security-review/` |
| `/failure-modes-review` | Review failure handling, cost/budget controls, and production-readiness risks; write a timestamped report. | Broad reliability/production-readiness audit. | Optional focus | Report file only (no code) | Report under `docs/roadmap/failure-modes-review/` |
| `/test-coverage-review` | Review test-coverage gaps; write a timestamped report. | Broad test-coverage audit. | Optional focus | Report file only (no code) | Report under `docs/roadmap/test-coverage-review/` |
| `/docs-drift-review` | Audit tracked Markdown and embedded doc prose for drift against the current code/config/behavior. Reports only; does not repair. | Broad documentation-accuracy audit. | Optional file/dir/module/category | Report file only (no docs repaired) | Report under `docs/roadmap/docs-drift-review/` |
| `/review-command` | Review a Claude Code command file for correctness, safety, and project fit; write a report. | Auditing a command file (including new ones). | Command path or name (e.g. `/arch-review`) | Report file only (does not edit the reviewed command) | Report under `docs/roadmap/commands-review/` |
| `/apply-review-report` | Apply scoped fixes from a **project-level** review report (arch / security / failure-modes / test-coverage / docs-drift). | Turning a project-level review report's findings into changes. | Review report path, or topic/focus | **Yes** — code / tests / docs | Implemented fixes |
| `/apply-command-review` | Apply fixes from a **command-file** review report to the reviewed command file. | Turning a `/review-command` report's findings into changes. | Command review report path (`docs/roadmap/commands-review/…`) | **Yes** — the target `.claude/commands/*.md` file | Edited command file |
| `/update-claude-md` | Update durable rules in `CLAUDE.md` and artifact conventions in `docs/roadmap/README.md` after a completed change. | Recording durable project rules/conventions post-change. | Implementation report path, spec/plan path, or short description | **Yes** — `CLAUDE.md` and `docs/roadmap/README.md` | Documentation edits |

> Report artifacts under `docs/roadmap/` are local-only and gitignored by default
> (see the root `CLAUDE.md`). "Report file only" means the command writes a review
> artifact but does not touch application code, tests, or eval files.

## Recommended workflows

The commands separate **deciding**, **building**, **reviewing**, and **applying
findings** into distinct steps:

- **`/eval-imple`** decides whether a proposed change is warranted *before*
  touching the repository, treats "no change" as a successful outcome, and
  implements only the smallest justified change.
- **`/imple-spec`** assumes that decision is already made and a spec/plan
  exists; it builds the approved scope.
- **`/review-diff`** reviews an *existing* working-tree diff *after* changes have
  been made.
- The **specialized review commands** (`/arch-review`, `/security-review`,
  `/failure-modes-review`, `/test-coverage-review`, `/docs-drift-review`) perform
  broad subsystem audits and write report files; they do not modify code.
- The **apply commands** turn review findings into changes, and are **not**
  interchangeable:
  - `/apply-review-report` — for **project-level** review reports
    (arch / security / failure-modes / test-coverage / docs-drift).
  - `/apply-command-review` — for **command-file** review reports under
    `docs/roadmap/commands-review/`. Do **not** route command-file review reports
    through `/apply-review-report`.

Uncertain proposed change:

```text
Uncertain proposed change
→ /eval-imple
→ /review-diff
→ optional specialized *-review
→ apply findings with the matching apply command
→ final /review-diff
```

Approved spec:

```text
Approved spec
→ /imple-spec <spec-path>
→ /review-diff
```

## Command selection guidance

- Use **`/eval-imple`** when it is unclear whether a proposed change is
  necessary.
- Use **`/imple-spec`** when a reviewed spec or plan already exists.
- Use **`/new-function-spec`** to turn a rough idea into a concrete spec first.
- Use **`/review-diff`** when code has already changed and you want a pre-commit
  check.
- Use a specialized **`*-review`** command for a broad subsystem audit
  (architecture, security, failure modes, test coverage, docs drift).
- Use **`/review-command`** to audit a Claude Code command file.
- Use **`/apply-review-report`** for project-level review reports; use
  **`/apply-command-review`** for reports under `docs/roadmap/commands-review/`.
  Do not route command-file review reports through `/apply-review-report`.
- Use **`/update-claude-md`** to record durable rules/conventions after a change
  lands.

## Archived commands

`.claude/commands/old_command/` contains **inactive / superseded** command files
(`commit-staged`, `new-command`, `new-spec`, `plan-spec`). They are not part of the
active suite above and are not recommended for use unless the repository explicitly
says otherwise.

## Maintenance

- Update this README whenever an active command is **added, removed, renamed, or
  has a materially changed responsibility**.
- Treat each command file (its frontmatter and body) as the **source of truth**;
  this README only summarizes.
- Keep entries concise — do not copy full command bodies into this file.
