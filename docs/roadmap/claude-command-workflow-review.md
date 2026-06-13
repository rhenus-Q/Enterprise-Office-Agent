# Claude Command Workflow Review

Status: Review

Date: 2026-06-12

## 1. Executive summary

The four-command workflow (`/new-spec` → `/plan-spec` → `/implement-spec` → `/review-diff`)
is well designed for this project and is **usable after minor fixes**. The commands and
templates agree with each other on directory layout, naming, safety constraints, validation
commands, and the no-commit / no-branch policy. The safety rules accurately encode this
project's real protections (full eval requires separate approval, `tests/chains/` and
`ingestion.py` are off by default, prompts/models/corpus/`.env`/graph behavior/`stop_reason`/
fallback-policy semantics are guarded).

The issues found are mechanical, not structural: a permission allowlist
(`Bash(uv run:*)`) that is broader than the written safety rules, malformed YAML
frontmatter in `plan-spec.md`, one template instruction that contradicts the
plan-first token-saving rule, and a few small naming inconsistencies. No typo
directories (`docs/rodamap/`, `docs/roadmap/implemention/`) exist, and no template
is in the wrong directory.

## 2. Files reviewed

Context:

* `CLAUDE.md`
* `README.md`
* `structure.md`
* `git status --short` (only `?? .claude/` — the command files themselves are not yet committed)
* `evals/run_eval.py` (spot-check: the `--output` flag referenced by commands/templates exists)

Commands:

* `.claude/commands/new-spec.md`
* `.claude/commands/plan-spec.md`
* `.claude/commands/implement-spec.md`
* `.claude/commands/review-diff.md`

Templates:

* `docs/roadmap/spec/spec-template.md`
* `docs/roadmap/plan/plan-template.md`
* `docs/roadmap/implementation/implementation-template.md`

Note on expected paths: the review brief named the spec template as
`docs/roadmap/spec/template.md`. That file does not exist; the actual file is
`docs/roadmap/spec/spec-template.md`, and **all commands consistently reference the
actual file**, so this is a mismatch between the brief and the repo, not a workflow bug.

## 3. Command review

### `/new-spec`

**Purpose:** Turn a short idea into a structured spec at `docs/roadmap/spec/<feature_slug>.md`.

**What is good:**

* Minimal context read (`CLAUDE.md` + the template only).
* Stops with a clear message if the template is missing; does not invent one.
* Solid slug rules (kebab-case, charset, max length, collapse/trim dashes).
* Asks the user instead of guessing when title/slug can't be inferred.
* Spec-only: no implementation, no branch/commit, full safety-rule block matching the project.
* Exact, terse final response format; doesn't dump the spec into chat.

**Problems found:**

* The required-sections list says "Validation plan," but the spec template's
  matching section is titled "Test plan" (§9). Cosmetic, but an agent following the
  checklist literally could flag a false mismatch.
* `allowed-tools` omits `Glob`, while `/plan-spec` includes it — harmless but inconsistent.
* The template's `Date: <YYYY-MM-DD>` field has no instruction for how to obtain
  the date (no date command is allowlisted). In practice the session date is known,
  so this is minor.

**Recommended changes:** Rename the checklist item to "Test plan" (or rename the
template section to "Validation plan" to match the plan template's §8). Optionally
add `Glob` for parity.

**Risk level: Low**

### `/plan-spec`

**Purpose:** Turn an existing spec into an implementation plan at
`docs/roadmap/plan/<feature_slug>-plan.md`.

**What is good:**

* Reads only `CLAUDE.md`, the plan template, and the source spec; extra files only
  when the spec itself names them. Explicitly forbids broad architecture review.
* Correct missing-file behavior for both the template and the spec.
* Required plan sections match the plan template one-to-one (including "Files that
  should not change" and "Recommended implementation prompt").
* Full safety-rule block, no-branch/no-commit, exact final response format.

**Problems found:**

* **Malformed YAML frontmatter.** The block opens with `---` followed by a blank
  line, and closes with a 67-character dash run
  (`-------...---`) instead of `---`. It happens to parse in the current harness
  (the description and tools load), but this is fragile across parsers and is the
  only command whose frontmatter deviates from the standard form.
* The slug rule "if the filename ends with `-spec`, remove that suffix" handles a
  filename pattern `/new-spec` never produces (it generates `<feature_slug>.md`
  with no suffix). Harmless defensive rule, but it implies a naming convention the
  workflow doesn't use.

**Recommended changes:** Fix the frontmatter to a standard
`---` / key-value lines / `---` block with no leading blank line.

**Risk level: Medium** (only because frontmatter parsing controls `allowed-tools`;
if a future parser rejects it, the command silently loses its tool restrictions or
fails to load)

### `/implement-spec`

**Purpose:** Execute a plan (or spec) with minimal reading, then write an
implementation report to `docs/roadmap/implementation/`.

**What is good:**

* The **plan-first reading rule is exactly right for token economy**: given a plan,
  do not read the source spec unless the plan demands it, is ambiguous, or the user
  asks. Given a spec, it looks for the matching plan and prefers it.
* Reads `CLAUDE.md` first; reads only files the plan/spec lists; forbids broad
  architecture review and scope expansion.
* Degrades gracefully when the report template is missing (continues, skips the
  report, tells the user) instead of fabricating a report structure.
* Stops on unrelated uncommitted changes before editing — correct for a command
  that writes code.
* The default safety constraints precisely cover this project's sensitive surface:
  prompts, model names, corpus, graph behavior/routing/nodes, `stop_reason`
  semantics, fallback-policy semantics, `.env`/`.env.example`, full eval,
  `ingestion.py`, `tests/chains/`, API-key commands, commits, branches.
* Validation commands are the safe mocked set plus `--validate-only`; full eval is
  shown but gated on plan/spec need **and** separate user approval — matching
  `CLAUDE.md` and `evals/run_eval.py`'s own warning.
* The report rules explicitly forbid inventing passing tests or claiming a full
  eval that wasn't run.

**Problems found:**

* **`allowed-tools` includes `Bash(uv run:*)`, which is broader than the safety
  rules.** That pattern permits `uv run python evals/run_eval.py` (full eval),
  `uv run python ingestion.py`, and `uv run pytest tests/chains/` at the
  permission layer; the only thing preventing them is prompt text. The protections
  the command promises are enforceable in the allowlist and should be.
* `MultiEdit` in `allowed-tools` is a stale tool name (merged into `Edit` in
  current Claude Code). Harmless, but dead weight.
* Minor tension with `CLAUDE.md`'s "don't run commands without explicit approval":
  invoking `/implement-spec` is reasonably read as that approval for the safe
  validation set, but the command could say so in one line to remove ambiguity.

**Recommended changes:** Replace `Bash(uv run:*)` with specific safe patterns, e.g.
`Bash(uv run ruff:*)`, `Bash(uv run mypy:*)`,
`Bash(uv run pytest tests/node:*)`, `Bash(uv run pytest tests/graph:*)`,
`Bash(uv run pytest tests/evals:*)`,
`Bash(uv run python evals/run_eval.py --validate-only:*)`. Drop `MultiEdit`.

**Risk level: Medium** (the permission gap is the single most consequential issue
in the workflow — full eval costs real API money and `ingestion.py` rebuilds the index)

### `/review-diff`

**Purpose:** Review-only assessment of the working tree for safety, scope, and
commit readiness.

**What is good:**

* Clearly review-only: no file modification, no commit, no branches.
* Correct inspection sequence: `git status --short`, `git diff --stat`,
  `git diff --name-only`, then targeted `git diff -- <file>` — explicitly preferred
  over reading whole files.
* The forbidden/risky checklist covers everything this project cares about,
  including stale eval results, generated files, formatting-only churn, missing
  tests, and "changes that require full eval but only validate-only was run."
* Tiered validation recommendations (basic set vs. mocked-suite set vs. full eval),
  with full eval recommended only for eval/retrieval/fallback-affecting diffs and
  **never run** by the command itself.
* Four-level commit-readiness verdict plus explicit `git add <files>` suggestions;
  `git add .` is discouraged except for trivially small, fully intended diffs.
* The Confirmations section forces an explicit statement on prompts, model names,
  corpus, `.env`, graph behavior, and eval results — a good last line of defense.

**Problems found:**

* **`allowed-tools` includes `Bash(uv run:*)` for a command that never instructs
  running anything.** Step 5 only *recommends* commands and looks for evidence in
  the conversation. The allowlist should not grant execution a review-only command
  doesn't need (and it has the same full-eval/ingestion exposure as
  `/implement-spec`).
* Untracked files are invisible to `git diff`. The command has `Read` and could
  inspect `??` entries, but no step says to — a brand-new risky file (e.g. a new
  corpus doc) would surface in `git status` and then escape diff review unless the
  agent improvises.
* New `docs/roadmap/` artifacts (specs/plans/reports) will routinely appear in
  diffs this command reviews, but the scope-classification list has no category for
  them, so they risk being classed "unrelated or suspicious."

**Recommended changes:** Remove `Bash(uv run:*)` (or constrain it as in
`/implement-spec` if running validation is intended). Add a step-2 note: for
untracked files, read the file content directly. Add "roadmap planning artifact" to
the scope categories.

**Risk level: Low–Medium**

## 4. Template review

### Spec template (`docs/roadmap/spec/spec-template.md`)

**What is good:** Covers every needed section — summary, background, goals,
non-goals, files to inspect (with a sensible project-specific starter list and the
instruction to prune it), proposed changes, ordered implementation plan, the full
project safety-constraint block, safe validation commands with the gated full-eval
command, measurable acceptance criteria, project-realistic risks (retrieval
instability, eval calibration, LLM variability), and a final report format that
matches the implementation report template field-for-field.

**Problems found:**

* §9 is titled "Test plan" while `/new-spec` requires a "Validation plan" section
  and the plan template calls its equivalent "Validation plan" (§8). One name
  should win.
* The "Files to inspect" starter list is eval-harness-leaning
  (`evals/run_eval.py`, `questions.jsonl`, `tests/evals/test_eval_harness.py`); fine
  for this project's current phase, but a node/chain-touching feature gets no hint
  toward `graph/nodes/` or `graph/chains/`. Minor — the "only include relevant
  files" instruction mitigates it.

**Recommended changes:** Rename §9 to "Validation plan."

**Risk level: Low**

### Plan template (`docs/roadmap/plan/plan-template.md`)

**What is good:** The strongest of the three for token economy: required/optional
file split for implementation reading, per-step "files likely changed / what to
avoid / validation to run," explicit "files expected to change" vs. "files that
should not change" (pre-seeded with this project's protected surface:
`graph/nodes/`, `graph/chains/`, prompts, model names, corpus, `.env`,
`ingestion.py`), "do not guess" grounding rule in §2, and a clear note that the
*planning* step must not run validation commands. §11's "Recommended
implementation prompt" makes plans directly executable.

**Problems found:**

* **§11 instructs the implementation prompt to say "Read the source spec" — this
  directly contradicts `/implement-spec`'s plan-first rule** (do not automatically
  read the source spec when the plan is complete). Every plan generated from this
  template will tell the implementer to burn tokens on a file the workflow
  deliberately avoids.

**Recommended changes:** Change §11's bullet to "Read the source spec **only if
this plan says it is required or the plan is insufficient on its own**."

**Risk level: Medium** (it silently defeats the workflow's main token-saving
mechanism on every run)

### Implementation report template (`docs/roadmap/implementation/implementation-template.md`)

**What is good:** Changed files grouped by purpose; "What was intentionally not
changed" with the project's exact protected list; a validation section that demands
per-command results and an explicit statement when full eval was *not* run (plus
results-file/pass-count fields when it was); "do not claim work that was not done"
stated twice; embedded `git status --short` and `git diff --stat`; a final
confirmation checklist mirroring the safety constraints, including "no commit was
created automatically."

**Problems found:**

* Header has `Source spec:` and `Source plan:` but no guidance for the
  plan-first case where the spec was deliberately not read — a literal-minded agent
  may go read the spec just to fill the field. One parenthetical ("path, or 'not
  read — implemented from plan'") fixes it.
* No field records *which* input (`plan` vs `spec`) drove the implementation,
  though `/implement-spec`'s final chat response does capture it. Minor.

**Recommended changes:** Allow "not read" as a valid `Source spec:` value.

**Risk level: Low**

## 5. Cross-command consistency findings

Consistent (verified, no action needed):

* Directory layout: specs → `docs/roadmap/spec/`, plans → `docs/roadmap/plan/`,
  reports → `docs/roadmap/implementation/`, commands → `.claude/commands/`. **No
  `rodamap` or `implemention` typo paths exist anywhere**; no template is in the
  wrong directory.
* File naming chain works end-to-end: `<slug>.md` → `<slug>-plan.md` →
  `<slug>-implementation-report.md`, and `/implement-spec`'s suffix-stripping rules
  invert the naming correctly.
* Safety-constraint blocks are word-for-word aligned across both authoring
  commands, both authoring templates, `/implement-spec`, and the report template.
* Validation command lists are identical everywhere they appear, and the full-eval
  approval language ("explicitly needs it **and** the user separately approves") is
  uniform. The `--output evals/results.md` flag was verified to exist in
  `evals/run_eval.py`.
* No-branch and no-commit policies appear in all four commands and the report
  confirmation.

Inconsistencies / issues:

1. **Permission-vs-prompt gap:** `Bash(uv run:*)` in `/implement-spec` and
   `/review-diff` allowlists permits full eval, `ingestion.py`, and
   `tests/chains/` despite the written rules forbidding them (Must fix).
2. **`plan-spec.md` frontmatter** is malformed (blank line after opening `---`,
   dash-run closer) — the only command deviating from standard frontmatter
   (Must fix).
3. **Plan template §11 vs. plan-first rule:** template tells implementers to read
   the source spec unconditionally (Must fix — one-line edit).
4. **"Test plan" (spec template §9) vs. "Validation plan"** (everywhere else)
   (Should fix).
5. **Templates live inside the output directories** they template. Workable, and
   the `-template` suffix avoids slug collisions in practice (a 40-char slug ending
   in `-template` is improbable; `plan-template.md` would need a spec slugged
   `plan-template` to collide). Acceptable; a `docs/roadmap/templates/` directory
   would remove the edge case at the cost of touching every path reference — not
   worth it now.
6. **Duplicated validation blocks in six places** (4 command/template validation
   sections + review-diff tiers) are consistent today but are a known drift risk;
   any future change must be applied everywhere (Awareness, not a fix).
7. **Stale `MultiEdit`** tool name in `/implement-spec` (Optional).
8. **`.claude/` is untracked** — the workflow itself isn't committed, so it isn't
   versioned or shared yet (Should fix: commit it once the fixes land).
9. The review brief's expected spec-template path (`docs/roadmap/spec/template.md`)
   does not match the actual, internally consistent `spec-template.md` — recommend
   keeping the actual name (it matches `plan-template.md` /
   `implementation-template.md` conventions) and correcting the brief/docs instead
   of renaming the file.

## 6. Suitability for this Agentic RAG project

The workflow fits this project well — it encodes the project's actual cost and
safety topology rather than generic hygiene:

* **Expensive operations are correctly identified and gated.** Full eval (24 real
  OpenAI/Tavily-backed graph runs) requires explicit separate approval everywhere;
  `--validate-only` is correctly treated as the safe default. `tests/chains/`
  (real `gpt-5-mini`) and `ingestion.py` (index rebuild; a mid-run failure leaves
  the index empty) are off by default in every command.
* **The protected surface matches `CLAUDE.md`'s development rules** exactly:
  prompts, model names (`gpt-5-mini`), corpus documents, graph
  routing/nodes/behavior, `stop_reason` semantics, fallback-policy semantics, and
  `.env`/`.env.example`.
* **The safe validation set is the project's real safe set:** `ruff`, scoped
  `mypy`, and the three fully mocked suites (`tests/node/ tests/graph/
  tests/evals/`) — the same set CI runs without keys.
* **Token-saving behavior is designed in**, not bolted on: minimal context reads,
  plan-first implementation, required/optional file splits, targeted diffs, and
  "don't repeat the artifact in chat" final formats. The one defect is the plan
  template §11 contradiction noted above.
* **The artifact trail (spec → plan → report → diff review) suits an eval-driven
  project** where changes need calibration evidence: the report template forces
  honest recording of what was and wasn't run, and `/review-diff` checks for stale
  eval results and validate-only-when-full-eval-was-needed gaps.

One clarification worth adding somewhere (e.g. a short `docs/roadmap/README.md`):
whether roadmap artifacts are committed. The repo's history says yes (phase plans
are already committed), so `/review-diff` should treat new spec/plan/report files
as an expected change category, not noise.

## 7. Recommended fixes

### Must fix before using

1. **Tighten `Bash(uv run:*)` in `/implement-spec`** to enumerated safe patterns
   (`uv run ruff …`, `uv run mypy`, `uv run pytest tests/node|graph|evals …`,
   `uv run python evals/run_eval.py --validate-only`) so full eval, `ingestion.py`,
   and `tests/chains/` are blocked at the permission layer, not just by prompt text.
2. **Remove (or equally tighten) `Bash(uv run:*)` in `/review-diff`** — a
   review-only command shouldn't carry execution permissions it never uses.
3. **Repair `plan-spec.md` frontmatter** to a standard `---`-delimited block.
4. **Fix plan template §11** so the recommended implementation prompt says to read
   the source spec only when the plan requires it.

### Should fix soon

5. Unify "Test plan" → "Validation plan" between the spec template and `/new-spec`.
6. Add untracked-file handling and a "roadmap planning artifact" scope category to
   `/review-diff`.
7. Allow "not read — implemented from plan" as a `Source spec:` value in the
   implementation report template.
8. Commit `.claude/` so the workflow is versioned.

### Optional improvements

9. Drop stale `MultiEdit` from `/implement-spec`'s `allowed-tools`.
10. Add `Glob` to `/new-spec` for parity with `/plan-spec`.
11. Add a short `docs/roadmap/README.md` documenting the spec → plan →
    implementation → review lifecycle and the commit policy for artifacts.
12. Broaden the spec template's "Files to inspect" starter list with a
    graph-feature variant (`graph/nodes/`, `graph/chains/`, `tests/node/`).

## 8. Suggested final directory layout

Keep the current layout (it is already consistent); add only the index README:

```
.claude/
└── commands/
    ├── new-spec.md
    ├── plan-spec.md
    ├── implement-spec.md
    └── review-diff.md

docs/
└── roadmap/
    ├── README.md                          # (new, optional) workflow lifecycle + commit policy
    ├── claude-command-workflow-review.md  # this review
    ├── spec/
    │   ├── spec-template.md               # keep this name; don't rename to template.md
    │   └── <feature-slug>.md
    ├── plan/
    │   ├── plan-template.md
    │   └── <feature-slug>-plan.md
    └── implementation/
        ├── implementation-template.md
        └── <feature-slug>-implementation-report.md
```

## 9. Suggested next command to create

**`/run-eval`** — a dedicated, explicitly-approved full-eval command. Full eval is
the one expensive operation every other command must dance around; giving it its
own command makes the approval boundary structural instead of textual. It would:
state the cost up front and require confirmation, run
`uv run python evals/run_eval.py --output evals/results.md` (optionally
`--limit N` for a cheap smoke pass), diff the new `evals/results.md` pass/fail
counts against the previous one, and flag rows that flipped — directly supporting
the calibration loop visible in recent history ("Calibrate Phase 3 eval results").
It is also the only command that legitimately needs the broad eval execution
permission the others should lose.

Runner-up: `/sync-docs` — after an implementation, check `README.md`,
`structure.md`, and `docs/adr/` for drift against the actual diff (this project's
docs are detailed enough that drift is its main documentation risk).

## 10. Final verdict

**Ready after minor fixes.**

The structure, sequencing, safety model, and token discipline are right for this
project. Fix the four must-fix items — two permission-allowlist tightenings, one
frontmatter repair, one template line — and the workflow is safe to adopt as the
standard development loop.
