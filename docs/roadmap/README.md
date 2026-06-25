# docs/roadmap

Process artifacts produced during development of this project.

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
