# Security Policy

## Supported versions

Security fixes are focused on the current 1.7.x release line.

| Version | Supported |
|---|---|
| 1.7.x | Yes |
| Earlier releases | No |

## Reporting a vulnerability

Report security issues through GitHub's
[private vulnerability reporting](https://github.com/rhenus-Q/Enterprise-Office-Agent/security/advisories/new)
(**Security → Report a vulnerability**).

Do not disclose vulnerabilities or exploit details in a public issue, pull
request, or discussion, and do not post sensitive details publicly while
arranging contact.

## What to include

Please include:

- the affected version or commit;
- the affected component;
- steps to reproduce the issue;
- the expected impact;
- a minimal proof of concept, where it is safe to provide one; and
- suggested remediation, if available.

Redact API keys, personal information, production data, provider credentials,
and unrelated confidential material from the report and supporting artifacts.

## Response expectations

Maintainers will make a reasonable effort to acknowledge a complete report,
assess its reproducibility and impact, and coordinate remediation and disclosure
when appropriate. This is not a guaranteed response or remediation SLA.

## Security scope

This repository is an open-source reference and demonstration system. Its
FastAPI adapter and frontend are a localhost presentation surface, not a hosted
service or production security boundary. The project has no built-in
authentication, authorization, tenant isolation, or real enterprise
integrations.

The following are design decisions, not vulnerabilities:

- **No authentication or authorization.** The adapter binds to localhost and
  serves a single user. Exposing it on a network is out of scope.
- **No tenant isolation.** There is one corpus and one set of fixtures.
- **Answer quality is not a security boundary.** A wrong routing decision, a
  mis-classified ticket, or an unhelpful answer is a quality issue.
- **Prompt-injection defense is prompt-layer only.** Retrieved context is framed
  as untrusted evidence and web results face the same relevance gate as local
  chunks, but a sufficiently persuasive document can still influence generated
  text. The defense limits blast radius; it does not guarantee immunity.

### Tool execution boundary

The agent's capabilities are read-only by construction, which is what keeps the
missing authorization layer from mattering:

- **No write or side-effect surface.** Six of the seven capabilities are
  deterministic, LLM-free, and read local JSON fixtures under
  `office_agent/mock_data/`. Approving or rejecting a request and creating a
  follow-up task are *simulated*: the tool computes an audit event or task
  object, returns it, and persists nothing.
- **The one persistence seam is test-only.** `record_decision` and
  `create_task_from_ticket` accept an optional `persist_path` that defaults to
  `None`; no CLI or HTTP path passes it, and the tests that do pass a pytest
  `tmp_path`. The repository's own fixtures are never written.
- **No external integrations.** There is no connection to Gmail, Outlook,
  Google Calendar, Slack, Jira, Linear, Asana, or Trello, and `office_agent/`
  makes no outbound network calls of its own.

If a future change adds a real integration or a write path, this section stops
being accurate and must be revised in the same change.

## Trust boundaries and data egress

Nothing leaves the machine unless a provider path is explicitly configured. What
crosses the boundary depends on which paths are enabled:

| Path | Enabled by | What leaves the machine | Destination |
|---|---|---|---|
| Deterministic capabilities (email, calendar, tickets, briefing, meeting, approvals) | Always on | **Nothing** | — |
| Knowledge Q&A retrieval | `OPENAI_API_KEY` | The request text (after secret redaction), and the local document chunks selected for grading and generation | OpenAI |
| Web-search fallback | `WEB_SEARCH_ENABLED=true` + `TAVILY_API_KEY` | The search query — the original or rewritten request text | Tavily |
| Email digest assist | `OFFICE_LLM_ENABLED=true` | Content from the local email fixtures that the digest summarizes | OpenAI |
| Daily Briefing narrative assist | `OFFICE_LLM_ENABLED=true` | The collected briefing fact set | OpenAI |
| Tracing | `LANGCHAIN_TRACING_V2` / `LANGSMITH_TRACING` | Run traces, including prompts and responses | LangSmith |

Two runtime modes restrict this, and they can only ever restrict — no
lower-level flag or per-run option can re-enable a path a mode has turned off:

- **`PRIVACY_MODE`** forces off web search, tracing, and both optional LLM
  assists. The OpenAI retrieval-and-generation path is preserved, so **OpenAI is
  still contacted** in this mode.
- **`OFFLINE_MODE`** implies every `PRIVACY_MODE` restriction and additionally
  disables OpenAI chat and embeddings, ingestion, and every other external path,
  failing closed rather than degrading.

The Office Agent's own tool calls produce no outbound requests; the only
capability that reaches a provider is Knowledge Q&A, through the
`enterprise_rag` adapter.

## Secret handling

- **Credentials live in `.env`, which is gitignored.** `.env.example` is the
  committed template and contains placeholders only. A `.gitleaks.toml` is
  committed and the full commit history is scanned with it.
- **Console banners log the exception type only,** never the message, because
  provider error messages can carry request URLs, paths, or key fragments.
- **Input redaction is best-effort credential hygiene, not confidentiality.**
  Secret-shaped values in a request are replaced with `[REDACTED]` before the
  text enters the graph, so no matching credential reaches the retriever,
  generator, graders, or an outbound web-search query. It does not remove
  personal, confidential, or business-sensitive prose that is not shaped like a
  credential.
- **Trace files are local debugging artifacts, not sanitized output.** A run
  writes one only when `AnswerOptions.trace_path` is set. The payload excludes
  document text, prompts, full responses, and raw graph state, but it does
  include a redacted question preview and an unkeyed SHA-256 of the original
  input — so predictable inputs remain guessable. `/traces/` is gitignored;
  review a trace file before sharing it.
- **Eval history records are metadata-only** — counters, flags, stop reasons,
  and a dataset fingerprint, never answer text, document content, or prompts.
