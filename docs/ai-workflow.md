# AI-assisted development

This project was built primarily with [Claude Code](https://claude.com/claude-code),
working against a spec-driven workflow that is itself committed to this
repository. [Codex](https://openai.com/codex/) was used for a few isolated
frontend changes. Architectural decisions and reviews were made by a human; the
agent worked inside explicit, version-controlled rules.

This document describes how that workflow is organized and, more importantly,
which of its rules are enforced by something other than good intentions.

## Components

| Component | What it holds |
|---|---|
| [`CLAUDE.md`](../CLAUDE.md) | The durable project rules: module map, development constraints, testing discipline, and the behaviors that must not change without an explicit decision. |
| [`.claude/commands/`](../.claude/commands/README.md) | 13 slash commands covering the spec → plan → implement → review loop plus focused audit passes. |
| [`docs/roadmap/`](roadmap/README.md) | The spec / plan / implementation templates. Only the four workflow files are tracked; everything written from them is gitignored. |
| [`docs/adr/`](adr/README.md) | 21 architecture decision records, split by owning scope (`enterprise_rag/`, `office_agent/`, and repository-wide). |
| [`docs/engineering/`](engineering/) | `onboarding.md`, `testing-strategy.md`, and `release-checklist.md` — the maintainer-facing counterparts to the user-facing README. |

## The loop

```
new-function-spec  →  imple-spec  →  review-diff
   (write a spec)     (implement it)   (review the working diff)
```

Around that core sit the audit passes, each of which writes a dated report and
changes no code: `arch-review`, `security-review`, `failure-modes-review`,
`test-coverage-review`, `docs-drift-review`. Two more close the loop on the
tooling itself — `review-command` audits a command file, `apply-command-review`
applies the findings — and `update-claude-md` is the only command allowed to
edit the rules file.

`eval-imple` is deliberately different: it evaluates whether a proposed change is
justified *before* implementing it, and is allowed to conclude that the correct
change is none.

## Rules are executable, not prose

The rules that matter most are not left as documentation. They are assertions
that fail CI:

| Rule in `CLAUDE.md` | Enforced by |
|---|---|
| Credentials alone never authorize a paid model call — the opt-in must also be set | [`test_credentials_alone_do_not_authorize_real_model_tests`](../tests/test_environment_isolation.py#L32) |
| `OFFLINE_MODE` still blocks a real-model test that was otherwise authorized | [`test_offline_mode_still_blocks_an_authorized_real_model_test`](../tests/test_environment_isolation.py#L60) |
| The root entry point must not pull in `enterprise_rag` (ADR 020) | [`test_root_main_delegates_to_office_cli`](../tests/office_agent/test_cli.py#L192) |
| Run Settings resolve identically in Python and TypeScript | [`test_python_resolver_matches_the_contract`](../tests/office_agent/test_run_settings_contract.py#L64) |
| The HTTP wire schema does not drift from its checked-in contract | [`test_current_wire_schema_exactly_matches_checked_in_contract`](../tests/api/test_openapi_contract.py#L223) |

The environment-isolation suite also asserts that the test process is insulated
from a local `.env` and that the optional LLM assists are forced off during an
ordinary run, so a developer's own configuration cannot quietly change what the
suite is testing.

## Permissions are narrow

Every command declares an explicit `allowed-tools` allowlist in its frontmatter.
No command receives unrestricted `Bash`; grants are scoped down to the exact
invocation, for example `Bash(git status:*)`, `Bash(git diff:*)`, and
`Bash(date:*)`. A review command gets read tools and nothing that can mutate the
repository.

[`review-diff.md`](../.claude/commands/review-diff.md) goes further and refuses
to *read* secret-bearing files at all — a review pass has no business pulling a
credential into its own context in order to judge it. Such a file appearing as
untracked or staged is itself a blocking finding, reported by filename only.

## Methods are published; findings are not

Specs, plans, implementation reports, and every audit report are written under
`docs/roadmap/` and gitignored. Only the four workflow templates are tracked.

This is deliberate. A security-review report is a findings list about this
repository's own code, and a test-coverage report is a list of the places it is
weakest. Publishing either as a standing document is worse than useless: it goes
stale the moment the finding is fixed, and until then it is a map. What survives
is the durable form — an ADR, a regression test, or an entry under
[Limitations and non-goals](../README.md#limitations-and-non-goals) in the
README.

## What the agent was not allowed to decide

`CLAUDE.md` names the surfaces that require an explicit human decision before
they change: graph routing, the `GraphState` schema, prompts, model names,
`temperature=0`, and the `stop_reason` contract. Commands are required to stop
and ask rather than proceed when a change would touch one of them.

The same file records the reasoning behind constraints that would otherwise look
arbitrary — why every external client sits behind a lazy `@lru_cache` factory,
why imports must construct no client, and why `GraphState` fields must stay
plain last-value channels. Those explanations exist so that a future change can
see what it would be trading away, rather than discovering it through a failing
test.
