# docs/roadmap

Process artifacts produced during development of this project.

## Subfolders

| Folder | Contents |
|---|---|
| `spec/` | Feature specs — a brief description of *what* a feature should do and why. Written before implementation planning begins. |
| `plan/` | Implementation plans — step-by-step approach for a feature, usually produced from a spec. Includes the files to change and key decisions. |
| `implementation/` | Implementation reports — post-implementation summaries of what was done, what changed, and what was left out. |
| `commands-review/` | Reviews of `.claude/commands/` command files — structure, safety, tool scoping, and template quality checks. |
| `architecture-review/` | Architecture review reports — periodic health checks of the overall codebase architecture, testability, and portfolio readiness. |

## Naming convention

Specs, plans, and implementation reports use a short feature slug, e.g.
`eval-history-delta-reporting.md`.

Architecture reviews use a dated filename:
`<YYYY-MM-DD>-<focus-slug>-architecture-review.md`
so that multiple reviews can coexist in the same folder and sort
chronologically. Older un-dated files (e.g. `architecture-review.md`) are
pre-convention baselines and can be read as historical context.
