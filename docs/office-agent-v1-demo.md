# Office Agent v1 — demo & usage

Office Agent v1 is a small, deterministic assistant that routes a free-text
request to one of five capabilities and returns a structured response. It lives
in [`office_agent/`](../office_agent/) and is the office-automation companion to
the completed [`enterprise_rag`](../enterprise_rag/README.md) engine.

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
| `unknown` | Unsupported request | Returns a safe "can't do that" message; no tool runs |

Routing precedence is `email → calendar → ticket/task → daily_briefing →
knowledge → unknown`: an explicit tool-specific request wins, a broad "brief me /
what should I focus on" request goes to Daily Briefing, and a policy/document
question falls to Knowledge Q&A. There is **no LLM router** — routing is pure
keyword matching, so it is fast, offline, and fully reproducible.

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
| `"what is the VPN access policy?"` | `knowledge_qa` |
| `"order lunch for the team"` | `unknown` |

## Run the demo script

```powershell
# Local-only demo (Daily Briefing, Email, Calendar, Tickets/Tasks, Unknown).
# No API keys, no external services, no Chroma index required.
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
- **Email Summary, Calendar Lookup, Task / Ticket Assistant, and Daily Briefing**
  read static fictional JSON in
  [`office_agent/mock_data/`](../office_agent/mock_data/). No network, no keys, no
  LLM.

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

See [ADR 015](adr/015-office-agent-v1-architecture.md) for the full architecture
decision behind Office Agent v1.
