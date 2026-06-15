# Review Command Review

Status: Review

Date: 2026-06-14

Target command: `.claude/commands/review-command.md`

Report file: `docs/roadmap/commands-review/review-command-command-review.md`

## 1. Executive summary

**Ready after minor fixes.**

`.claude/commands/review-command.md` is a well-formed, safe, review-only meta-command. Its
frontmatter is valid, its `allowed-tools` set is correctly minimal (no `Edit`, no `MultiEdit`,
no broad `Bash`, no test/eval/ingestion grants), and `Write` is tightly restricted in prose to
the single selected report file. Scope and safety wording match the rest of the command suite,
and collision-safe report naming is implemented correctly.

Two genuine weaknesses keep it from "Ready to use": (a) the input-resolution rules order the
`.md` check before the leading-slash check, so an input like `/arch-review.md` is mishandled,
and (b) the "close match" fallback has no rule for *multiple* matches, which is exactly the
ambiguity that could cause the command to review the wrong file. Both are low-severity and
easily fixed; neither is a safety risk.

## 2. Files reviewed

- `CLAUDE.md`
- `.claude/commands/review-command.md` (target)
- `.claude/commands/review-diff.md`
- `.claude/commands/arch-review.md`
- `.claude/commands/update-claude-md.md`
- `.claude/commands/implement-spec.md`
- `.claude/commands/new-spec.md`
- `.claude/commands/plan-spec.md`
- `git status --short`

## 3. Frontmatter and permission review

**Frontmatter: valid.**

- Standard `---` opening (line 1) and closing (line 5) delimiters, no blank or malformed
  delimiter, no stray blank line inside the block.
- `description` (line 2) is accurate and action-oriented: "Review a Claude Code command file
  for correctness, safety, and project fit".
- `argument-hint` (line 3) is useful and shows both accepted formats (path and `/name`).
- `allowed-tools` (line 4): `Read, Write, Glob, Grep, Bash(git status:*), Bash(mkdir:*)`.

**Permission assessment:**

| Tool | Needed? | Verdict |
|------|---------|---------|
| `Read` | Yes — reads `CLAUDE.md`, target, peers | ✅ appropriate |
| `Glob` | Yes — close-match search + collision checks | ✅ appropriate |
| `Grep` | Yes — content inspection of command files | ✅ appropriate |
| `Write` | Yes — only to emit the review report | ✅ appropriate, prose-restricted |
| `Bash(git status:*)` | Yes — single narrow git read | ✅ appropriate |
| `Bash(mkdir:*)` | Marginal — creates the report directory | ✅ acceptable (see note) |

- `Write` is necessary only because the command writes a review report, and prose restricts it
  ("Use `Write` only for the selected unique command review report. Do not write any other
  file." lines 160–162). ✅
- No `Edit`. ✅
- No `MultiEdit`. ✅
- No broad `Bash(*)`. ✅
- No broad `Bash(uv run:*)`. ✅
- No test-runner permission. ✅
- No full-eval permission. ✅
- No ingestion / API-key command permission. ✅

Note (Optional): the `Write` tool already creates parent directories, so `Bash(mkdir:*)` is
arguably redundant. It is retained here for parity with `arch-review.md` and `new-spec.md`, so
this is a consistency choice, not a defect.

## 4. Scope and safety review

The command is unambiguously review-only and write-scoped. It explicitly forbids modifying the
command file (line 13), `CLAUDE.md` (15), application code (17), tests (19), eval files (21),
README (23), prompts (27), model names (29), corpus documents (31), and `.env` /
`.env.example` (33). It forbids running tests (35), full eval (37), `ingestion.py` (39),
`tests/chains/` (41), and API-key-requiring commands (43), and forbids commit (45) and
branch creation/switching (47).

Project-critical behavior is protected via the Step 5 checklist (lines 188–217): graph
behavior, graph routing, graph nodes, `stop_reason` semantics, fallback-policy semantics,
full eval, `ingestion.py`, `tests/chains/`. The command only *reads about* and *reviews* these
areas; it has no tool capable of changing them (no `Edit`, restricted `Write`).

Critically for a meta-command: because the only mutating tool is `Write`, restricted in prose
to `docs/roadmap/commands-review/`, the command **cannot modify the command it is reviewing**,
including itself if asked to review `review-command`. Self-modification and command-file
modification are structurally impossible, not merely discouraged. ✅

## 5. Input handling review

Resolution rules (Step 1, lines 73–98) cover the required formats:

- `.claude/commands/arch-review.md` → path (ends with `.md`). ✅
- `/arch-review` → strip leading `/`, resolve to `.claude/commands/arch-review.md`. ✅
- `arch-review` (bare name) → `.claude/commands/<name>.md`. ✅
- Empty `$ARGUMENTS` → stop and ask (line 75). ✅
- Missing file → Glob fallback, then stop and report (lines 94–96). ✅
- Search is correctly confined to `.claude/commands/` (line 98). ✅

Two ambiguities:

1. **Rule ordering for leading-slash + `.md`.** The `.md` test (line 88) precedes the leading-
   slash test (line 89). An input such as `/arch-review.md` ends with `.md`, so it is treated
   literally as the path `/arch-review.md` (an absolute-style path that will not exist) instead
   of being normalized to `.claude/commands/arch-review.md`. Similarly a bare `arch-review.md`
   resolves relative to the repo root rather than `.claude/commands/`. The Glob close-match
   fallback usually rescues both, but the resolution is not clean.

2. **Multiple close matches undefined.** Line 94 says to "look for a close match" with Glob but
   gives no rule for when several candidates match. Silently picking one risks reviewing the
   wrong command — the exact failure the review brief asks to guard against.

## 6. Report output and collision review

- Output directory is fixed to `docs/roadmap/commands-review/` (lines 67–69, 129–131). ✅
- Filename convention is explicit:
  `<YYYY-MM-DD>-<command-slug>-command-review.md` (line 135), slug = command name without
  `.md`, lowercased, letters/digits/hyphens (lines 139–141). ✅
- Collision handling checks the base path with Glob, then increments `-2`, `-3`, … until an
  unused path is found (lines 151–158), checking each candidate before writing. ✅
- Old reports are preserved ("do not overwrite", lines 71, 153). ✅
- Final response uses the selected unique path (Step 10, line 370). ✅

Repeated-run behavior is safe: each run lands on a fresh suffixed file rather than clobbering
prior reports. The convention matches `arch-review.md`'s collision logic exactly.

One observation (Optional / consistency): the date component depends on the harness-provided
current date; like `arch-review.md`, the command has no tool to fetch the date itself. This is
an accepted pattern across the suite, not a fault of this command.

## 7. Project fit and consistency review

The command is a close structural sibling of `arch-review.md` and is consistent with the
broader workflow:

- **Safety wording** mirrors `arch-review`, `implement-spec`, `new-spec`, `plan-spec`
  (same "Do not modify … / Do not run …" block, same no-commit / no-branch policy). ✅
- **Report-under-roadmap pattern** matches `arch-review` (`architecture-review/` →
  `commands-review/`), including date-prefixed, collision-safe naming. ✅
- **Final response format** (report path, target, verdict, top issues, "Do not repeat the full
  report") matches `arch-review`. ✅
- **`allowed-tools`** matches `arch-review` exactly, which is the correct peer to imitate for a
  write-a-report command. ✅
- **Token discipline** ("Use as few tools as possible", "Prefer reading only these peer
  commands", "Do not read unrelated project files") matches the suite. ✅

Minor consistency gaps (low impact):

- The peer-reading list (Step 2, lines 109–116) and the project-fit comparison list (Step 8,
  lines 270–276) both omit `update-claude-md.md`, even though it is an existing command. A
  command-reviewer comparing for consistency should arguably consider it too.
- Dual verdict surfaces (executive summary §1 and final verdict §10) both restate Ready / Ready
  after minor fixes / Not ready. This matches `arch-review`'s pattern and is not confusing, so
  it is acceptable — noting only that there is no third redundant verdict block.

## 8. Problems found

### Problem 1 — Input rule ordering mishandles leading-slash + `.md`

- **Issue:** The `.md` check precedes the leading-slash strip, so `/arch-review.md` (and bare
  `arch-review.md`) resolve to literal/relative paths instead of `.claude/commands/...`.
- **Why it matters:** The resolved path will not exist; the run depends on the Glob fallback to
  recover, which is fragile and may surface a confusing "missing file" path.
- **Risk level:** Low.
- **Recommended fix:** Normalize first — strip a leading `/`, then if the value has no
  directory separator, resolve under `.claude/commands/` and append `.md` when absent; treat an
  explicit `.claude/commands/...md` path as-is. Apply the `.md` test only after normalization.

### Problem 2 — Ambiguous close-match handling is undefined

- **Issue:** When the exact path is missing, the command Globs for a "close match" but gives no
  rule for multiple candidates.
- **Why it matters:** Silently choosing one match could cause the command to review the wrong
  command file — directly the ambiguity the brief flags.
- **Risk level:** Low–Medium.
- **Recommended fix:** If more than one close match is found, stop and list the candidates,
  asking the user to disambiguate rather than guessing.

### Problem 3 — `update-claude-md` omitted from peer/consistency lists

- **Issue:** Steps 2 and 8 enumerate peer commands but exclude `update-claude-md.md`.
- **Why it matters:** A consistency reviewer may miss divergences between the target and an
  existing command, weakening the review.
- **Risk level:** Low.
- **Recommended fix:** Add `.claude/commands/update-claude-md.md` to both the peer-reading list
  and the project-fit comparison list.

### Problem 4 — `Bash(mkdir:*)` likely redundant

- **Issue:** `Write` auto-creates parent directories, so the `mkdir` grant may be unnecessary.
- **Why it matters:** Minimal permissions are best practice for a meta-command; an unused grant
  is mild surface area.
- **Risk level:** Low.
- **Recommended fix:** Optional — drop `Bash(mkdir:*)` and rely on `Write`, or keep it for
  parity with `arch-review.md`/`new-spec.md`. Either is defensible; document the choice.

## 9. Recommended fixes

### Must fix

- None. No safety, scope, or self-modification defects were found.

### Should fix soon

- Problem 2 — define behavior for multiple close matches (stop and ask).
- Problem 1 — reorder input normalization so leading-slash and `.md` inputs resolve cleanly.

### Optional improvements

- Problem 3 — include `update-claude-md.md` in peer/consistency lists.
- Problem 4 — reconsider whether `Bash(mkdir:*)` is needed.

## 10. Final verdict

**Ready after minor fixes.**

The command is safe, correctly write-scoped, structurally incapable of modifying the command it
reviews (including itself), and consistent with the existing Claude Code command workflow. The
only weaknesses are two low-severity input-resolution gaps (leading-slash/`.md` ordering and
undefined multiple-match handling). Addressing those makes it fully Ready to use.
