# Claude Command Review

Status: Review

Date: 2026-06-14

Target command: `.claude/commands/update-claude-md.md`

Report file: `docs/roadmap/commands-review/2026-06-14-update-claude-md-command-review-2.md`

## 1. Executive summary

**Ready to use.**

This is a re-review of `update-claude-md.md` after the four fixes recommended in the prior report
(`docs/roadmap/commands-review/2026-06-14-update-claude-md-command-review.md`) were applied. All
four prior findings are now resolved in the file:

* **P1 — missing-file handling** is present (Step 2, lines 98–104).
* **P2 — path-vs-description disambiguation** is present (Step 2, lines 92–96).
* **P3 — stop-on-ambiguous-match** is present (Step 2, lines 116–120) with "Do not search the
  whole repo" (line 114).
* **P4 — graph-semantics protection** is present (Step 4, line 166).

The optional final-response relabel was also applied (Step 6, lines 204–219). The permission set
is unchanged and remains the narrowest correct set for the job. No new issues of substance were
introduced; only trivial, optional polish remains. The command is safe and ready to use as-is.

## 2. Files reviewed

* `CLAUDE.md` (project rules — in context)
* `.claude/commands/update-claude-md.md` (target — re-read at current state, 220 lines)
* Peer commands (in context from the prior review): `arch-review.md`, `review-diff.md`,
  `implement-spec.md`, `new-spec.md`, `plan-spec.md`
* Prior review report: `docs/roadmap/commands-review/2026-06-14-update-claude-md-command-review.md`
* `git status --short`
* `docs/roadmap/commands-review/` (report inventory, for collision check)

## 3. Frontmatter and permission review

Frontmatter is unchanged from the prior review and remains correct:

* Clean `---` open (line 1) / close (line 5); no blank or malformed delimiter.
* `description` — concise, matches the registered skill description.
* `argument-hint` — "Implementation report path, spec/plan path, or short feature description";
  still accurate, and now matched precisely by the Step 2 disambiguation logic.
* `allowed-tools: Read, Edit, Glob, Grep, Bash(git status:*), Bash(git diff:*)` — unchanged.

Per-tool necessity (unchanged, with one strengthened justification):

| Tool | Verdict | Notes |
|------|---------|-------|
| `Read` | Necessary | Reads `CLAUDE.md` and the resolved input file. |
| `Edit` | Necessary | Sole mutation surface; prose restricts it to `CLAUDE.md`. |
| `Glob` | Necessary | Roadmap-folder search when input is a description. |
| `Grep` | Justified | Justification is now slightly stronger: the new "if several roadmap files are equally relevant" step (line 119) benefits from content matching to rank relevance. Read-only, no risk. |
| `Bash(git status:*)` | Necessary | Step 5 validation + Step 6 final response. |
| `Bash(git diff:*)` | Necessary | Step 5 `git diff -- CLAUDE.md` / `git diff --stat -- CLAUDE.md`. |

Still no `Write`, no `MultiEdit`, no test/eval/ingestion runners, no API-key commands, no
`Bash(uv run:*)`, no `Bash(*)`. Every Bash command in the prose is covered by the two narrow `git`
grants, and no granted permission is unused. This remains the narrowest correct permission set.

## 4. Scope and safety review

Scope fencing is unchanged and still strong: mutation restricted to `CLAUDE.md` three independent
ways ("Modify only", "Use `Edit` only for", "Do not edit any other file") plus "Do not create new
files", with the full forbidden-operations litany (tests, full eval, `ingestion.py`,
`tests/chains/`, API-key commands, commit, branch) intact.

The prior §4 enumeration gap is now closed at the point where it matters. Step 4 line 166 adds:

> "When editing `CLAUDE.md`, do not alter descriptions of graph routing, graph nodes,
> `stop_reason` semantics, privacy mode, or fallback-policy semantics unless the source change
> actually changed them."

This directly addresses the only residual concern from the prior review — that a `CLAUDE.md` edit
could *misdescribe* graph/`stop_reason`/fallback semantics — and it correctly includes "privacy
mode," which is a real project concept (`web_search_enabled` per `graph/config.py`). Graph code
itself was already fully protected by Edit-only-on-`CLAUDE.md`.

Editing-command scoping check still passes: target file explicit, no unrelated-file creation,
validation diff scoped to `CLAUDE.md` (`git diff -- CLAUDE.md`).

## 5. Input handling review

Materially improved since the prior review. Updated coverage:

| Case | Handled? | Detail |
|------|----------|--------|
| Empty `$ARGUMENTS` | Yes | Step 1 stops and asks for report/spec/plan path or description. |
| Path vs description | **Yes (now explicit)** | Lines 92–96: separator (`/` or `\`) ⇒ path; ending in `.md` ⇒ path; otherwise ⇒ description. |
| File-path input | Yes | Line 100: read the file. |
| Non-existent file path | **Yes (now explicit)** | Lines 101–104: stop with `File not found. Provide a valid report/spec/plan path or a short feature description.`; do not improvise; do not search broadly after a missing explicit path. |
| Description input | Yes | Lines 106–114: search only the five `docs/roadmap/*` folders; "Do not search the whole repo." |
| Ambiguous description match | **Yes (now explicit)** | Lines 116–120: one ⇒ read; several ⇒ stop, list candidates, ask for exact path, do not guess; none ⇒ stop and say no match. |
| Repeated runs | Yes | Bad-candidate list + "Avoid duplicating existing rules" keep reruns effectively idempotent. |
| Output-file collision | N/A | Edits `CLAUDE.md` in place; produces no report file. |

The resolution logic now mirrors the deterministic stop-and-ask pattern used by the `review-command`
peer, which is the right model for this suite.

## 6. Output behavior review

Editing-command checks all pass:

* **Target explicit** — `CLAUDE.md` throughout.
* **No unrelated files** — "Do not create new files"; no `Write`.
* **Validation scoped to target** — Step 5 diffs `CLAUDE.md` only; `git status --short` is a
  whole-tree sanity check.
* **Final response (Step 6)** — now a fixed labeled block (`CLAUDE.md updated:` /
  `Durable rules added:` / `Confirm:` + the two git lines). It preserves the same reported items as
  before while reading more uniformly with `new-spec`/`plan-spec`. Good, proportionate change — not
  over-done.

The acceptable/unacceptable durable-guidance examples (lines 168–180) remain accurate against the
current project (`graph/engine.py::answer_question()` as canonical entry point; `.claude/commands/`
narrow `allowed-tools`; `evals/history/*.json` generated/gitignored; `GraphState` last-value
channels).

## 7. Project fit and consistency review

Fit is unchanged and strong; the edits improved cross-command consistency rather than harming it:

* Workflow position (tail of `/new-spec → /plan-spec → /implement-spec → /review-diff →
  /update-claude-md`) unchanged.
* Missing-file handling now matches `implement-spec`/`plan-spec`.
* Ambiguous-match handling now matches `review-command`.
* "Do not search the whole repo" reinforces the suite-wide token-discipline posture.
* Final-response labeling now closer to `new-spec`/`plan-spec`.
* Permission restraint (no `Write`/`mkdir`) still correctly distinguishes this edit-only command
  from the artifact-producing peers.

No over-engineering, no template noise, no changelog-churn risk (the command still explicitly
guards against that).

## 8. Problems found

No must-fix or should-fix problems remain. The items below are trivial, optional observations only.

### O1 — Disambiguation can misclassify a description containing `/` or ending in `.md`

* **Issue:** A feature description that happens to contain a path separator (e.g.
  `VPN/onboarding docs`) or end in `.md` is classified as a file path (lines 94–95), then fails the
  existence check.
* **Why it matters:** Minimal — it degrades gracefully to the `File not found` stop (lines 101–102),
  which prompts the user to rephrase. No wrong edit, no broad search.
* **Risk level:** Low.
* **Recommended fix (optional):** None required. If desired, note that such inputs should be passed
  as a plain description without slashes.

### O2 — Step 2 heading slightly under-describes its content

* **Issue:** The heading "Read current project memory" (line 84) now also houses the full
  input-resolution logic. (This predates the recent edits.)
* **Why it matters:** Cosmetic readability only.
* **Risk level:** Low.
* **Recommended fix (optional):** Rename to e.g. "Read project memory and resolve input," or split
  resolution into its own step.

### O3 — Final-response "Confirm" list omits "other Claude command files"

* **Issue:** Step 6 line 212 confirms no code/tests/eval/README/roadmap files changed but does not
  name other `.claude/commands/*` files.
* **Why it matters:** Cosmetic; the command can only edit `CLAUDE.md`, so other command files cannot
  be touched anyway.
* **Risk level:** Low.
* **Recommended fix (optional):** Optionally add "or other Claude command files" to the confirm
  line for completeness.

## 9. Recommended fixes

### Must fix

* None.

### Should fix soon

* None. All four findings from the prior report (P1–P4) are resolved.

### Optional improvements

* **O1** — note that descriptions should avoid slashes / `.md` endings (or accept the graceful
  failure as-is).
* **O2** — clarify the Step 2 heading or split out input resolution.
* **O3** — extend the Step 6 confirm line to mention other Claude command files.

## 10. Final verdict

**Ready to use.**

The four prior recommendations are fully applied, the command is safe (Edit-only-on-`CLAUDE.md`,
read-only git, no `Write`/runners/API-key/broad-`Bash` grants), input handling is now deterministic
and consistent with the rest of the suite, and only cosmetic optional polish remains.
