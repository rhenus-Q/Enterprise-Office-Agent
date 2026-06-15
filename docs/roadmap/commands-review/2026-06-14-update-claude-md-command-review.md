# Claude Command Review

Status: Review

Date: 2026-06-14

Target command: `.claude/commands/update-claude-md.md`

Report file: `docs/roadmap/commands-review/2026-06-14-update-claude-md-command-review.md`

## 1. Executive summary

**Ready to use.**

`update-claude-md.md` is a tightly-scoped, documentation-only command with an exemplary
permission set: it can only `Edit` `CLAUDE.md`, run read-only `git status` / `git diff`, and
read/search files. It carries no `Write`, no test/eval/ingestion runners, no API-key commands,
and no broad `Bash` grants. Its safety litany, good/bad-candidate guidance, and final-response
contract are all consistent with the existing command suite, and its CLAUDE.md examples are
accurate against the real project.

The only gaps are minor robustness/consistency improvements (no explicit missing-file handling,
no path-vs-description disambiguation rule, no stop-on-ambiguous-match), none of which is a
safety problem or a blocker. The command is safe to use as-is.

## 2. Files reviewed

* `CLAUDE.md` (project rules — already in context)
* `.claude/commands/update-claude-md.md` (target)
* `.claude/commands/arch-review.md` (peer — report-producing review command)
* `.claude/commands/review-diff.md` (peer — review-only command)
* `.claude/commands/implement-spec.md` (peer — editing/implementing command)
* `.claude/commands/new-spec.md` (peer — artifact-producing command)
* `.claude/commands/plan-spec.md` (peer — artifact-producing command)
* `git status --short`
* `docs/roadmap/commands-review/` (existing report inventory, for collision check)

## 3. Frontmatter and permission review

Frontmatter is correct and well-formed:

* `---` open (line 1) and close (line 5) delimiters are clean; no blank or malformed delimiter.
* `description` — present, concise, matches the registered skill description.
* `argument-hint` — present and useful: "Implementation report path, spec/plan path, or short
  feature description" accurately describes the three accepted input shapes.
* `allowed-tools: Read, Edit, Glob, Grep, Bash(git status:*), Bash(git diff:*)`

Per-tool necessity:

| Tool | Verdict | Notes |
|------|---------|-------|
| `Read` | Necessary | Reads `CLAUDE.md` and the resolved input file. |
| `Edit` | Necessary | The only mutation surface; prose restricts it to `CLAUDE.md` ("Use `Edit` only for `CLAUDE.md`"). |
| `Glob` | Necessary | Step 2 filename search under `docs/roadmap/*` when the input is a description. |
| `Grep` | Justified, borderline | Plausibly used for content search to find "the most relevant" roadmap doc. Read-only, so no risk; could be dropped if search is strictly filename-based, but keeping it is defensible. |
| `Bash(git status:*)` | Necessary | Step 5 validation + Step 6 final response. |
| `Bash(git diff:*)` | Necessary | Step 5 `git diff -- CLAUDE.md` and `git diff --stat -- CLAUDE.md`. |

Safety of the permission set is strong:

* **No `Write`** — correct. `CLAUDE.md` already exists, so `Edit` is the right verb, and the
  command explicitly forbids creating files. This is more disciplined than the artifact-producing
  peers (which legitimately need `Write` + `Bash(mkdir:*)`).
* **No `Bash(uv run:*)`, no test/eval/ingestion runners, no API-key commands, no `Bash(*)`.**
* Every Bash command that appears in the prose (`git status --short`, `git diff -- CLAUDE.md`,
  `git diff --stat -- CLAUDE.md`) is covered by the two narrow `git` grants — no permission gap,
  and no granted permission is left unused.

This is the narrowest correct permission set for the command's job.

## 4. Scope and safety review

The command is explicitly a "documentation-only task" and is unusually well-fenced:

* Mutation is restricted to `CLAUDE.md` in three independent ways: "Modify only `CLAUDE.md`",
  "Use `Edit` only for `CLAUDE.md`", "Do not edit any other file", plus "Do not create new files".
* Protected areas are enumerated: application code, tests, eval files, README, roadmap files,
  prompts, model names, corpus documents, `.env` / `.env.example`.
* Forbidden operations: run tests, run full eval, run `ingestion.py`, run `tests/chains/`, run
  API-key-requiring commands, commit, create/switch branches.

Cross-check against project-critical areas:

| Area | Protected? | How |
|------|-----------|-----|
| application code | Yes | "Do not modify application code" + Edit-only-on-CLAUDE.md |
| tests | Yes | explicit |
| eval files | Yes | explicit |
| prompts | Yes (implicit) | covered by Edit-only-on-CLAUDE.md; not enumerated by name |
| model names | Yes | explicit |
| corpus documents | Yes | explicit |
| `.env` / `.env.example` | Yes | explicit |
| graph behavior / routing / nodes | Yes (implicit) | covered by Edit-only-on-CLAUDE.md; not enumerated by name |
| `stop_reason` semantics | Yes (implicit) | covered by Edit-only-on-CLAUDE.md; not enumerated by name |
| fallback policy semantics | Yes (implicit) | covered by Edit-only-on-CLAUDE.md; not enumerated by name |
| full eval | Yes | explicit |
| `ingestion.py` | Yes | explicit |
| `tests/chains/` | Yes | explicit |
| commits / branches | Yes | explicit |

Note on "Do not modify roadmap files": this is consistent, not contradictory, with the input
being a roadmap file — roadmap docs are read as input only; the sole write target is `CLAUDE.md`.

Editing-command scoping (review checklist item): the target file is explicit, unrelated-file
creation is forbidden, and the validation diff is correctly scoped to `CLAUDE.md`
(`git diff -- CLAUDE.md`). Pass.

The only enumeration gap is that graph behavior / routing / nodes / `stop_reason` /
fallback-policy semantics are **not listed by name** in the protected set, unlike `arch-review`,
`review-diff`, and `implement-spec`. This is **not a safety hole**, because the command can only
edit `CLAUDE.md` and cannot touch graph code at all. The residual concern is purely descriptive
(an agent could write a `CLAUDE.md` sentence that *misdescribes* `stop_reason`/fallback
semantics), which the "preserve structure/tone, avoid duplication, prefer durable rules"
guardrails already mitigate. Optional consistency improvement only.

## 5. Input handling review

| Case | Handled? | Detail |
|------|----------|--------|
| Empty `$ARGUMENTS` | Yes | Step 1 stops and asks for report/spec/plan path or a short description. "Do not search broadly without input." |
| File-path input | Yes | Step 2: "If `$ARGUMENTS` is a file path, read that file." |
| Short-description input | Yes | Step 2: searches only under `docs/roadmap/{spec,plan,implementation,architecture-review,commands-review}/`. |
| Non-existent file path | **No explicit handling** | Unlike `implement-spec`/`plan-spec` ("If the file does not exist, stop and tell the user…"), there is no missing-file branch. The agent would hit a `Read` error and improvise. |
| Path vs description disambiguation | **Implicit only** | No rule for deciding whether input is a path or a description (e.g. "contains `/` or ends in `.md`"). Left to judgment. |
| Ambiguous description match | **Partial** | "Find the most relevant … Read only the relevant files." Picks one; no stop-and-ask on multiple equally-relevant candidates (the `review-command` peer does stop-and-list). |
| Repeated runs | Yes | Bad-candidate list rejects "Anything already clearly covered in `CLAUDE.md`" and Step 4 says "Avoid duplicating existing rules", so reruns are effectively idempotent. |
| Output-file collision | N/A | Command edits `CLAUDE.md` in place; produces no report file, so there is nothing to collide. |

The missing-file and ambiguity gaps are real but low-impact: the command's terminal action is
heavily gated ("When unsure whether a rule is durable, do not update `CLAUDE.md`"), so a slightly
wrong input read degrades to "no change" rather than a bad edit.

## 6. Output behavior review

This is an editing command (not a report producer), so the report-file conventions do not apply;
the relevant checks pass:

* **Target file explicit** — `CLAUDE.md`, stated repeatedly.
* **No unrelated files created** — "Do not create new files"; no `Write` permission.
* **Validation diff scoped to target** — Step 5 uses `git diff -- CLAUDE.md` and
  `git diff --stat -- CLAUDE.md`; `git status --short` is used only as a whole-tree sanity check.
* **Edit guidance is sound** — add to the most relevant existing section, keep concise, prefer
  short bullets, don't turn `CLAUDE.md` into a changelog, no dates/commit history/test output.
* **Final response (Step 6)** reports whether `CLAUDE.md` changed, what durable rules were added
  (or why none), confirms no other files changed, and echoes `git status --short` +
  `git diff --stat -- CLAUDE.md`. Clear and verifiable.

The good/bad-candidate lists and the acceptable/unacceptable examples are the strongest part of
the command: they encode genuinely durable rules (e.g. `graph/engine.py::answer_question()` as
canonical entry point; `evals/history/*.json` generated/gitignored; `.claude/commands/` must keep
narrow `allowed-tools` and avoid broad `Bash(uv run:*)`), and they are accurate against the
current `CLAUDE.md` and project structure.

## 7. Project fit and consistency review

Strong fit with the existing workflow and conventions:

* **Workflow position** — sits correctly at the tail of
  `/new-spec → /plan-spec → /implement-spec → /review-diff → /update-claude-md`, capturing durable
  rules after a completed change. It is aware of all sibling artifact directories, including
  `docs/roadmap/commands-review/`.
* **Path conventions** — matches the `docs/roadmap/{spec,plan,implementation,...}/` layout used by
  the peers.
* **Shared idioms** — "Use as few tools as possible", the "Do not …" safety litany, "User input:
  $ARGUMENTS", and a Step N structure ending in a "Final response" section all match the suite.
* **Restraint** — correctly omits `Bash(mkdir:*)`/`Write` that the artifact-producing peers carry,
  because it creates nothing. This is the right kind of inconsistency (less privilege, not more).
* **`CLAUDE.md` rules** — honors the documentation/English/preserve-behavior posture; it edits
  only docs and never touches code or model names.

Consistency nits (minor):

* The protected-area list is shorter than `arch-review`/`review-diff`/`implement-spec` (omits the
  graph/`stop_reason`/fallback enumeration) — see §4; benign given Edit-only-on-CLAUDE.md.
* Final-response style is prose ("Report: …") rather than a fixed labeled block like
  `new-spec`/`plan-spec`; acceptable, but a fixed format would read more uniformly.
* Out of scope for this command, but observed during the collision check: existing reports in
  `docs/roadmap/commands-review/` (`arch-review-command-review.md`,
  `arch-review-command-review-v2.md`, `review-command-command-review.md`) do **not** follow the
  dated `<YYYY-MM-DD>-<slug>-command-review.md` convention. This is an artifact-naming drift in the
  review directory, not a defect in `update-claude-md.md`.

No over-engineering, no template noise, no risk of turning docs into changelog churn — in fact the
command explicitly guards against that ("Do not turn `CLAUDE.md` into a changelog").

## 8. Problems found

### P1 — No explicit handling for a non-existent input file path

* **Issue:** Step 2 says "If `$ARGUMENTS` is a file path, read that file" with no branch for a
  path that does not exist. Peers `implement-spec` and `plan-spec` both stop and emit a clear
  message in this case.
* **Why it matters:** Inconsistent UX; the agent falls back to improvising on a `Read` error
  instead of a deterministic, friendly stop.
* **Risk level:** Low.
* **Recommended fix:** Add a line: "If the provided path does not exist, stop and tell the user:
  `File not found. Provide a valid report/spec/plan path or a short feature description.`"

### P2 — No rule to disambiguate a path from a feature description

* **Issue:** Step 2 branches on "is a file path" vs "is a short feature description" without a
  decision rule.
* **Why it matters:** Borderline inputs (e.g. `eval history delta`) could be mis-routed to a
  filesystem read or a broad search.
* **Risk level:** Low.
* **Recommended fix:** Add a heuristic: "Treat input containing a path separator (`/`) or ending
  in `.md` as a file path; otherwise treat it as a feature description."

### P3 — No stop-on-ambiguous-match for description search

* **Issue:** When a description matches multiple roadmap files, the command instructs picking
  "the most relevant" rather than stopping to confirm, unlike the `review-command` peer.
* **Why it matters:** The agent could read a slightly wrong source doc; bounded because the
  durable-rule gate is conservative and the worst case is "no edit".
* **Risk level:** Low.
* **Recommended fix:** Add: "If several roadmap files are equally relevant, list them and ask the
  user to pick one before continuing."

### P4 — Protected-area list omits graph/`stop_reason`/fallback enumeration

* **Issue:** Unlike the peer commands, the safety list does not name graph behavior/routing/nodes,
  `stop_reason` semantics, or fallback-policy semantics.
* **Why it matters:** Purely consistency/descriptive; the command can only edit `CLAUDE.md`, so
  graph code is already fully protected. Residual risk is only that a `CLAUDE.md` edit could
  *misdescribe* those semantics.
* **Risk level:** Low.
* **Recommended fix (optional):** Add one line: "When editing `CLAUDE.md`, do not alter
  descriptions of graph routing, `stop_reason` semantics, or fallback-policy semantics unless the
  source change actually changed them."

## 9. Recommended fixes

### Must fix

* None. The command is safe and functional as written.

### Should fix soon

* **P1** — add explicit non-existent-file handling to match `implement-spec`/`plan-spec`.

### Optional improvements

* **P2** — add a path-vs-description disambiguation heuristic.
* **P3** — stop-and-ask on ambiguous description matches.
* **P4** — name the graph/`stop_reason`/fallback semantics in the protected list for consistency.
* Adopt a fixed labeled final-response block (as in `new-spec`/`plan-spec`) for uniformity.

## 10. Final verdict

**Ready to use.**

The command is safe (Edit-only-on-`CLAUDE.md`, read-only git, no `Write`, no runners, no API-key
or broad `Bash` grants), correctly scoped, idempotent on reruns, and a clean fit with the existing
command workflow. The findings are minor robustness and consistency polish, not blockers.
