# Office Agent v1.6 — demo & usage

The Office Agent is a small, deterministic assistant that routes a free-text
request to one of its capabilities and returns a structured response. It lives
in [`office_agent/`](../office_agent/) and is the office-automation companion to
the completed [`enterprise_rag`](../enterprise_rag/README.md) engine.

## Version map

The Office Agent has grown across three releases; all seven capabilities ship
today:

| Release | Phase | Capabilities added |
|---|---|---|
| **v1** | Phases 1–5 | Knowledge Q&A, Email Summary, Calendar Lookup, Task / Ticket Assistant, Daily Briefing |
| **v1.5** | Phase 6 | Meeting Agent / Meeting Prep |
| **v1.6** | Phase 7 | Workflow / Approval Agent |

> **v1.5 (Phase 6)** added a **Meeting Agent / Meeting Prep** capability
> (`meeting_agent`) — an advanced *composition* tool that combines the local
> calendar, inbox, and ticket/task mock data into one deterministic meeting-prep
> sheet. See [Meeting Agent / Meeting Prep](#meeting-agent--meeting-prep) below.
>
> **v1.6 (Phase 7)** added a **Workflow / Approval Agent** capability
> (`workflow_approval`) — a deterministic mock approval assistant over a local
> approval queue + audit log, with *simulated* approve/reject decisions and
> follow-up tasks (mock data is never mutated). See
> [Workflow / Approval Agent](#workflow--approval-agent) below.

Everything except Knowledge Q&A is **local, mock-data-backed, and LLM-free**, so
most of it demos with no API keys and no external services.

## Capabilities and intents

A deterministic keyword [router](../office_agent/router.py) classifies each
request into one **intent**, and the engine dispatches to exactly one tool:

| Intent | Capability | Data source |
|---|---|---|
| `knowledge_qa` | Enterprise document Q&A | Adapts `enterprise_rag` (real RAG pipeline) |
| `email_summary` | Inbox summary | Local mock `mock_data/emails.json` |
| `calendar_lookup` | Calendar / meetings | Local mock `mock_data/calendar_events.json` |
| `ticket_assistant` | Tickets & tasks | Local mock `mock_data/tickets.json` + `tasks.json` |
| `daily_briefing` | Aggregated morning briefing | Aggregates the email + calendar + ticket mock data |
| `meeting_agent` | Meeting prep (composition) | Combines the calendar + email + ticket/task mock data for one meeting |
| `workflow_approval` | Approval workflows | Local mock `mock_data/approvals.json` + `audit_log.json` |
| `unknown` | Unsupported request | Returns a safe "can't do that" message; no tool runs |

Routing precedence is `email → workflow_approval → ticket/task → meeting_agent →
calendar → daily_briefing → knowledge → unknown`: an explicit email request wins
first; workflow/approval requests (an approval keyword like "approve"/"reject"/
"approval", or an explicit `APR-<n>` id) are matched **before** ticket/task, so
"create a follow-up task for APR-001" is an approval action rather than a plain
task; plain ticket/task requests follow; meeting-*prep* semantics ("prepare me
for…", "meeting prep", "bring up", "agenda") are matched before the broad
calendar keywords so a plain lookup like "what meetings do I have today?" still
routes to Calendar Lookup; a broad "brief me / what should I focus on" request
goes to Daily Briefing; and a policy/document question falls to Knowledge Q&A.
There is **no LLM router** — routing is pure keyword matching, so it is fast,
offline, and fully reproducible.

## Programmatic usage

The single entry point is `office_agent.engine.answer_office_request`:

```python
from office_agent.engine import answer_office_request

response = answer_office_request("give me my daily briefing")
print(response.intent)    # "daily_briefing"
print(response.content)   # the rendered briefing text
```

`response` is an `OfficeAgentResponse` with `intent`, `content`, `tool`,
`stop_reason`, `sources`, and `run_id` (the last three are populated for
Knowledge Q&A, which carries through the `enterprise_rag` caveats and sources).

### Example requests

| Request | Routes to |
|---|---|
| `"give me my daily briefing"` | `daily_briefing` |
| `"summarize unread emails"` | `email_summary` |
| `"what meetings do I have today?"` | `calendar_lookup` |
| `"show blocked tickets"` | `ticket_assistant` |
| `"prepare me for my next meeting"` | `meeting_agent` |
| `"what should I bring up in the VPN rollout meeting?"` | `meeting_agent` |
| `"show pending approvals"` | `workflow_approval` |
| `"approve APR-001"` | `workflow_approval` |
| `"what is the VPN access policy?"` | `knowledge_qa` |
| `"order lunch for the team"` | `unknown` |

## Run the demo script

```powershell
# Local-only demo (Daily Briefing, Email, Calendar, Tickets/Tasks, Meeting Prep,
# Workflow / Approval, Unknown). No API keys, no external services, no Chroma index.
uv run python scripts/demo_office_agent_v1.py

# Also run the Knowledge Q&A example (needs the enterprise_rag setup below).
uv run python scripts/demo_office_agent_v1.py --include-knowledge
```

The default demo exercises only the local mock capabilities, so it is safe to run
anywhere. `--include-knowledge` additionally sends one question through the real
Enterprise RAG pipeline.

## Knowledge Q&A vs. the local mock tools

- **Knowledge Q&A** is an *adapter* over `enterprise_rag` — it calls the real
  `answer_question()` graph and reuses its formatting, so it may require the
  existing RAG setup: a built **Chroma** index (`uv run python -m
  enterprise_rag.ingestion`) and **API keys** (`OPENAI_API_KEY`, and `TAVILY_API_KEY`
  when web search is enabled). See
  [`enterprise_rag/README.md`](../enterprise_rag/README.md).
- **Email Summary, Calendar Lookup, Task / Ticket Assistant, Daily Briefing,
  Meeting Agent / Meeting Prep, and Workflow / Approval Agent** read static
  fictional JSON in [`office_agent/mock_data/`](../office_agent/mock_data/). No
  network, no keys, no LLM.

## Local-only mock-data design

The mock tools are intentionally simple and deterministic so the whole agent is
reviewable and CI-safe:

- Mock JSON is loaded lazily and **treated as read-only** — task "creation" is
  *simulated* (a computed task in the response), never a write to the mock files.
- Dates are **anchored to the mock data, not the system clock** (e.g. "today" is
  the calendar tool's resolved day), so output is identical on every run.
- No external service is ever contacted (no Gmail / Outlook / Google Calendar /
  Slack / Jira / Linear / Asana / Trello).

## How the Daily Briefing is built

Daily Briefing is a **thin aggregator**, not a new agent graph. It reuses the
other tools' pure helpers to assemble one concise briefing:

- **Priority emails** — unread / high-priority / response-needed counts (+ a few
  key bullets) from the Email tool's loader.
- **Today's calendar** — today's meeting count, the next meeting, and any
  schedule conflicts, from the Calendar tool's helpers.
- **Tickets & tasks** — open / high-priority / blocked / assigned-to-me ticket
  counts and open/linked task counts, from the Ticket tool's loaders.
- **Recommended focus** — a short, deterministic list derived from the above.

## Meeting Agent / Meeting Prep

Meeting Agent (`meeting_agent`, added in v1.5 / Phase 6) is an advanced
**composition** capability: like Daily Briefing it reuses the other tools' pure
helpers rather than reimplementing them, but it is *scoped to a single selected
meeting* and produces a focused prep sheet. It is **local-only, LLM-free, and
never calls the Enterprise RAG pipeline** — the "relevant knowledge areas" it
lists are inferred deterministically from labels, not retrieved from the corpus.

**Meeting selection** (deterministic, never the system clock):

- a request mentioning **"next"** picks the earliest-starting event (the calendar
  tool's `next_meeting`);
- otherwise the meeting whose **title words / labels best match** the request is
  chosen (`"prep me for the security review board"` → *Security review board*),
  ties broken by earliest start;
- if nothing matches, it **falls back to the next meeting**.

**The prep sheet** contains, for the selected meeting: the meeting metadata; up
to three **relevant emails** (subject + sender only, high-importance /
response-needed / unread / newest first); up to three **relevant tickets/tasks**
(high-priority / active / assigned-to-me / label match first); inferred
**relevant knowledge areas**; a **suggested agenda** (3–5 deterministic items); a
**risks / blockers** list (schedule conflicts with the selected meeting, plus
relevant blocked tickets); and **recommended follow-ups**. Output is concise,
bounded, and identical on every run.

Example requests: `"prepare me for my next meeting"`, `"generate meeting prep"`,
`"what should I bring up in the VPN rollout meeting?"`, `"prep me for the security
review board"`, `"meeting prep for the budget workshop"`.

## Workflow / Approval Agent

Workflow / Approval Agent (`workflow_approval`, added in v1.6 / Phase 7) is a
deterministic mock approval assistant over a local approval queue
([`mock_data/approvals.json`](../office_agent/mock_data/approvals.json)) and audit
log ([`mock_data/audit_log.json`](../office_agent/mock_data/audit_log.json)). It
is **local-only, LLM-free, and never calls the Enterprise RAG pipeline or any
external service** (no Jira / Linear / Asana / Trello / Slack / Gmail / Outlook /
Google Calendar).

**Views** (deterministic precedence; case-insensitive):

- **List / filter** — all approvals, `pending`, `assigned to me` (approver is
  me), `urgent`/`high`, `approved`, `rejected`, and topic filters such as "show
  expense approvals" / "show VPN approvals".
- **Status** — status for a specific id (any `APR-<n>`): status, priority,
  requester, approver/owner, due date, amount, linked ticket/task, policy area.
- **Simulated approve/reject** — `"approve APR-001"` / `"reject APR-002"` return a
  clear **Simulated action** section (previous → new status, actor, note).
- **Simulated follow-up task** — `"create a follow-up task for APR-001"` returns a
  **Simulated follow-up task** section.
- **Audit log** — `"show audit log for APR-001"` lists that approval's audit
  events, sorted by timestamp.

**Simulated actions never mutate the mock data.** `approve`/`reject` and
follow-up task creation compute their result in the response only;
`handle_approval_request` writes nothing. `build_simulated_decision` and
`build_simulated_followup_task` are pure (no system clock — timestamps mirror the
source approval), so output is identical on every run. `record_decision` exposes
an optional `persist_path` seam for tests only — it writes solely to a
caller-provided path (e.g. pytest's `tmp_path`), never to the repo's `mock_data/`
files.

Example requests: `"show pending approvals"`, `"which approvals are assigned to
me?"`, `"show urgent approvals"`, `"what is the status of APR-001?"`, `"approve
APR-001"`, `"reject APR-002"`, `"create a follow-up task for APR-001"`, `"show
audit log for APR-001"`, `"show expense approvals"`.

## Optional: LLM-assisted email digest (default off)

The Email Summary tool has one **optional, default-off** LLM enhancement. When
`OFFICE_LLM_ENABLED` is set to a truthy value (`true`/`1`/`yes`/`on`), a single
structured-output `gpt-5-mini` call reads the filtered emails' bodies and appends a
`Digest (LLM-assisted):` block — a short summary, extracted action items (each tied
to a source email id, with a deadline only when the body states one), and a
priority order. A second optional setting, `OFFICE_LLM_REQUEST_TIMEOUT_SECONDS`
(default 60), bounds that call.

Key properties:

- **Default demo stays key-free.** With the flag unset (the default), no LLM client
  is constructed and the email output is byte-for-byte the deterministic summary —
  every other capability remains local and LLM-free.
- **Grounded and bounded.** The digest crosses into the tool only as a validated
  model; action-item and priority ids are checked against the filtered emails, and
  the model has no ability to send, reply, delete, or persist anything.
- **Honest fallback.** Any failure (timeout, API error, parse or grounding failure)
  returns the standard deterministic summary plus a one-line caveat and a
  `llm_assist_error` stop reason — the Office Agent never crashes because of the
  assist.

Enable it for a demo with a real key by setting `OFFICE_LLM_ENABLED=true` in your
environment (see `.env.example`), then asking an email question such as
`"summarize my emails"`. The gated real-model test lives under
`tests/office_chains/` and the offline dataset check is
`uv run python evals/office_assist/run_office_assist_eval.py --validate-only`.

See [ADR 015](adr/015-office-agent-v1-architecture.md) for the architecture
decision behind the original five-capability Office Agent v1,
[ADR 016](adr/016-office-agent-capability-extensions.md) for the later Meeting and
Workflow / Approval extensions (the current seven-capability architecture), and
[ADR 017](adr/017-office-agent-llm-assist-email-digest.md) for this optional
LLM-assisted email digest.
