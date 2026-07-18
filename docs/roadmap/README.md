# docs/roadmap

Process artifacts produced during development of this project.

## Version-control policy

`docs/roadmap/` is a **local working-artifact area**. Its contents are ignored by
Git by default.

**Only these four files are version-controlled** — they are workflow
infrastructure referenced by the `.claude/commands/` files:

* `docs/roadmap/README.md` (this file)
* `docs/roadmap/spec/spec-template.md`
* `docs/roadmap/plan/plan-template.md`
* `docs/roadmap/implementation/implementation-template.md`

Everything else — specs, plans, implementation reports, and all review reports
(`<topic>-review/`, `commands-review/`) — **stays local and is never committed**.
These are point-in-time working artifacts: they capture the state of the
repository on the day they were written and go stale as the code moves on.

**Durable conclusions must be promoted** out of this directory into the tracked
documentation that is kept current:

| Conclusion | Promote into |
|---|---|
| An architectural or behavioral decision | `docs/adr/` (new or superseding ADR) |
| Engineering process / workflow guidance | `docs/engineering/` |
| Setup, usage, or capability documentation | `README.md`, `enterprise_rag/README.md`, `office_agent/README.md` |
| Module / file layout | `structure.md` |
| A verified behavioral guarantee | tests under `tests/` |
| A durable project rule for Claude Code | `CLAUDE.md` |

A roadmap artifact is finished work once its conclusions are promoted; the file
itself is not the record.

Older superseded local review reports may be deleted manually at any time once a
newer report on the same focus exists. Nothing under this directory is deleted
automatically.

Do not commit caches, generated output, absolute machine paths, or links into
gitignored directories.

## Subfolders

| Folder | Contents |
|---|---|
| `spec/` | Feature specs — a brief description of *what* a feature should do and why. Written before implementation planning begins. |
| `plan/` | Implementation plans — step-by-step approach for a feature, usually produced from a spec. Includes the files to change and key decisions. |
| `implementation/` | Implementation reports — post-implementation summaries of what was done, what changed, and what was left out. |
| `commands-review/` | Command-file review reports — reviews of `.claude/commands/` files (structure, safety, tool scoping, template quality), e.g. from `/review-command`. |
| `<topic>-review/` | Timestamped project-level review reports from `<topic>-review` commands. One folder per topic, e.g. `architecture-review/`, `security-review/`, `failure-modes-review/`, `test-coverage-review/`. |

## Naming convention

Specs, plans, and implementation reports use a short feature slug, e.g.
`eval-history-delta-reporting.md`.

Project-level `<topic>-review/` reports use a dated, collision-safe filename:
`<YYYY-MM-DD>-<focus-slug>-<topic>-review.md`
(e.g. `2026-06-13-overall-architecture-review.md`) so that multiple reviews can
coexist in the same folder, sort chronologically, and never overwrite prior
reports. Older un-dated files (e.g. `architecture-review.md`) are
pre-convention baselines and can be read as historical context.

`docs/roadmap/<topic>-review/` holds project-level review reports; the separate
`docs/roadmap/commands-review/` holds command-file review reports (e.g. from
`/review-command`).
