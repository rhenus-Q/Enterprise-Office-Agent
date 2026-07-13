# Office Agent Quick Start

*Last updated: 2026-07-13*

## What the Office Agent Does

The Office Agent is a single assistant you can ask, in plain English, to help
with everyday work questions. You type one request; it figures out what you
mean and hands back a clear, structured answer.

It currently helps with seven things:

- **Knowledge Q&A** — answering questions from AcmeCorp's internal policy and
  document knowledge base.
- **Email Summary** — summarizing your inbox.
- **Calendar Lookup** — checking your meetings and schedule.
- **Ticket / Task Assistant** — reviewing tickets and tasks.
- **Daily Briefing** — a single morning overview across email, calendar, and
  tickets.
- **Meeting Prep** — a focused prep sheet for one meeting.
- **Workflow / Approval Agent** — reviewing approvals and simulating approve /
  reject decisions.

You don't need to memorize exact phrases. The Office Agent recognizes the *kind*
of request from the words you use, so ask naturally.

## Before You Start

A few important things to understand about this version:

- **It runs on sample data, not your real accounts.** The email, calendar,
  ticket, task, and approval information all come from a small, fictional
  "AcmeCorp" data set built into the project. It is **not** connected to Gmail,
  Outlook, Google Calendar, Jira, Linear, Asana, Trello, Slack, or any other
  real service.
- **How AI is used varies by capability.**
  - **Knowledge Q&A** uses the Enterprise RAG system to search the internal
    document knowledge base and write an answer from what it finds.
  - **Email Summary** and **Daily Briefing** are deterministic by default, but
    can optionally add an LLM-assisted digest or narrative on top of their
    standard output (off unless enabled — see
    [Optional LLM-Assisted Features](#optional-llm-assisted-features)).
  - **Calendar Lookup**, **Ticket / Task Assistant**, **Meeting Prep**, and
    **Workflow / Approval** remain deterministic and do not call an LLM.
- **Date words are resolved from the sample data, not the real system clock.**
  Words like "today" and "tomorrow" are interpreted against each capability's
  own sample data rather than the actual calendar date; the individual
  capability sections below explain their specific behavior.
- **Nothing you ask changes any real system.** Actions like approving a request
  or creating a follow-up task are *simulated* — see [Simulated Actions](#simulated-actions).

## Supported Capabilities

### Knowledge Q&A

**Use it for**

Questions about AcmeCorp internal policies and documents — VPN access, expense
reimbursement, incident response, on-call rotation, data retention, and
onboarding.

**Example questions**

- "What is the VPN access policy?"
- "How do I request reimbursement?"
- "When should an incident be escalated to Sev-1?"
- "What is the data retention policy?"
- "What does the onboarding guide say?"

**What you will receive**

A written answer drawn from the internal knowledge base, followed by a
**Sources** section listing which documents the answer came from. If the system
is unsure or information is missing, the answer includes an honest note saying so.

**Important limitations**

- This is the only capability that needs AI and internal setup to run; if the
  knowledge base has not been prepared, it may be unavailable.
- It only knows the internal documents it was given. It will not answer general
  web questions unless internal information is insufficient and web fallback has
  been enabled.

### Email Summary

**Use it for**

Getting a quick, filtered overview of your inbox instead of scrolling through
every message.

**Example questions**

- "Summarize my emails."
- "Summarize unread emails."
- "Show important emails."
- "Which emails need my response?"
- "What emails came in today?"
- "Give me an inbox summary."

**What you will receive**

A one-line summary (which filter was applied and how many messages matched),
then a bulleted list of the matching messages. Each bullet shows whether the
message is unread, its importance, its subject and sender, and whether it needs
a response. If any messages are waiting on your reply, a separate **Action
items** list highlights them.

**Important limitations**

- Supported filters are **unread**, **important / high-priority** (also triggered
  by "priority" or "urgent"), **response needed** (also "reply"), and **today**.
  Anything else returns all messages.
- Only one filter applies per request, so ask for one thing at a time.
- "Today" refers to the latest day present in the sample inbox.

### Calendar Lookup

**Use it for**

Checking what meetings you have and spotting scheduling problems.

**Example questions**

- "What meetings do I have today?"
- "Show my calendar today."
- "What is my next meeting?"
- "Do I have any meetings tomorrow?"
- "Do I have schedule conflicts?"
- "Show important meetings."

**What you will receive**

A one-line summary (which view and how many events matched), followed by the
matching meetings sorted by start time, each showing its time span, importance,
title, and location. When two meetings overlap, a **Schedule conflicts** section
lists the overlapping pairs.

**Important limitations**

- Supported views are **today**, **tomorrow**, **next** (your next meeting),
  **conflicts**, and **important** (high-priority). Anything else returns your
  full schedule.
- "Today" and "tomorrow" are anchored to the sample data, not the real date.

### Ticket / Task Assistant

**Use it for**

Reviewing your support tickets and to-do tasks, and drafting a follow-up task
from a ticket.

**Example questions**

- "Show open tickets."
- "Summarize urgent tickets."
- "Which tickets are assigned to me?"
- "Show blocked tickets."
- "Show my tasks."
- "Create a task from TICK-001."

**What you will receive**

For a listing request: a one-line summary plus a bulleted list of the matching
tickets (or tasks), each showing status, priority, ID, title, and assignee or
owner.

For a create request: a **simulated** follow-up task, with a clear note that it
was not saved anywhere.

**Important limitations**

- Supported ticket views are **open**, **blocked**, **urgent / high-priority**,
  and **assigned to me**; you can also ask for existing **tasks** or tasks
  **linked** to tickets. Anything else returns all tickets.
- Task creation is a simulation only (see [Simulated Actions](#simulated-actions)).
  For a specific ticket, mention its ID (for example, `TICK-001`).

### Daily Briefing

**Use it for**

One consolidated "start of day" overview instead of asking about email,
calendar, and tickets separately.

**Example questions**

- "Give me my daily briefing."
- "What should I focus on today?"
- "Summarize my day."
- "What is on my plate today?"
- "Brief me for today."

**What you will receive**

A single briefing with four sections:

- **Priority emails** — counts of unread, high-priority, and response-needed
  messages, plus a couple of key items.
- **Calendar** — how many meetings you have that day, your next meeting, and any
  schedule conflicts.
- **Tickets and tasks** — counts of open, high-priority, blocked, and
  assigned-to-you tickets, plus open task counts.
- **Recommended focus** — a short, prioritized list of what to tackle.

**Important limitations**

- The briefing is holistic and ignores extra wording in your request — it always
  covers the whole day across all three sources.
- It reports counts and highlights, not every single item.

### Meeting Prep

**Use it for**

Getting ready for one specific meeting — an agenda, related emails and tickets,
and things to raise.

**Example questions**

- "Prepare me for my next meeting."
- "Generate meeting prep."
- "What should I bring up in the VPN rollout meeting?"
- "Prep me for the security review board."
- "Meeting prep for the budget workshop."

**What you will receive**

A prep sheet for the selected meeting containing: the meeting details (time,
title, location, attendees, importance, labels); up to three **relevant emails**;
up to three **relevant tickets or tasks**; **relevant knowledge areas** to review;
a **suggested agenda**; a **risks / blockers** list; and **recommended
follow-ups**.

**Important limitations**

- If you say "next," it prepares for your earliest upcoming meeting. Otherwise it
  picks the meeting whose title or topic best matches your words, so include the
  meeting topic when you can. If nothing matches, it falls back to your next
  meeting.
- The "relevant knowledge areas" are suggested topic names to read up on — this
  capability does **not** pull answers from the document knowledge base.

### Workflow / Approval Agent

**Use it for**

Reviewing approval requests, checking the status of one approval, and simulating
approve / reject decisions or a follow-up task.

**Example questions**

- "Show pending approvals."
- "Which approvals are assigned to me?"
- "Show urgent approvals."
- "What is the status of APR-001?"
- "Approve APR-001."
- "Reject APR-002."
- "Create a follow-up task for APR-001."
- "Show audit log for APR-001."
- "Show expense approvals."

**What you will receive**

- **List views** show matching approvals with status, priority, ID, title, and
  approver.
- **Status** for a specific approval shows its full detail (status, priority,
  requester, approver, due date, amount, linked ticket/task, and policy area).
- **Approve / reject** returns a **simulated** decision showing the status change
  and a note that nothing was saved.
- **Create a follow-up task** returns a **simulated** task.
- **Audit log** lists the recorded history for that approval.

**Important limitations**

- Checking one approval's status, approving, rejecting, creating a follow-up
  task, or viewing an audit log all require an explicit approval ID such as
  `APR-001`.
- List filters include **pending**, **assigned to me**, **urgent / high**,
  **approved**, **rejected**, and topic filters like "expense approvals" or "VPN
  approvals."
- Approve, reject, and follow-up task actions are simulated only (see
  [Simulated Actions](#simulated-actions)).

## Simulated Actions

Some requests look like they *do* something, but in this version they only show
you what the result *would* look like. They never change the sample data and
never touch any real system:

- **Approving or rejecting an approval** (for example, "Approve APR-001").
- **Creating a follow-up task** from a ticket or an approval.

Each of these responses is clearly labelled as **simulated** and includes a note
that nothing was saved. You can run the same request repeatedly and get the same
result — no state is stored.

## Optional LLM-Assisted Features

Two capabilities — **Email Summary** and **Daily Briefing** — can optionally add
an AI-written summary layer on top of their normal output. This is **turned off
by default**, so unless an administrator has enabled it, you will always see the
standard, non-AI results.

When it is enabled:

- **Email Summary** adds a short AI **digest** below the normal summary —
  a brief overview, extracted action items, and a suggested priority order.
- **Daily Briefing** adds a short AI **narrative** above the briefing that ties
  the day together across email, meetings, tickets, tasks, and approvals. The complete,
  unchanged factual briefing still appears below it.

A few reassurances:

- **The facts stay the facts.** The AI layer is added *around* the standard
  output; it never rewrites or removes the reliable, deterministic details.
- **It can't take actions.** The AI can only summarize — it cannot send, reply,
  approve, reject, delete, or save anything.
- **Failures are safe.** If the AI layer is unavailable for any reason, you
  simply get the normal output plus a one-line note that the assist wasn't
  available. The Office Agent never fails because of it.
- **Not everything uses AI.** The other five capabilities never use this layer.

## Tips for Asking Good Questions

- **Include an ID when the request is about one specific item.** Approval status,
  approve/reject, follow-up tasks, and audit logs need an approval ID like
  `APR-001`; creating a task from a specific ticket works best with a ticket ID
  like `TICK-001`.
- **Name the meeting topic for meeting prep.** "Prep me for the security review
  board" works better than a vague "prep me," because the topic helps pick the
  right meeting. Say "next" if you just want your next meeting.
- **Use filter words when you want a filtered view.** Words such as "unread,"
  "today," "important," "blocked," "open," "pending," and "urgent" trigger the
  matching filters.
- **Ask one clear thing at a time.** The Office Agent routes each request to a
  single capability, and some words take priority over others (for example, an
  email request wins over a policy question, and an approval request wins over a
  plain task request). One focused request avoids surprises.

## Unsupported or Out-of-Scope Requests

The Office Agent will tell you when it can't help, rather than guess. Things it
cannot do in this version include:

- Anything outside the seven capabilities above — for example, ordering lunch,
  booking travel, or translating text.
- Making **real** changes in any external system. It is not connected to real
  email, calendars, ticketing tools, or approval systems, so it cannot actually
  send an email, book a meeting, close a ticket, or finalize an approval.
- Saving or remembering changes. Simulated actions are shown for illustration and
  are not stored.

If a request isn't supported, you'll get a short message naming what the Office
Agent *can* do, so you can rephrase toward one of those capabilities.

## Quick Reference

| Capability | Example request | Returned information |
|---|---|---|
| Knowledge Q&A | "What is the VPN access policy?" | An answer from internal documents, with a Sources list |
| Email Summary | "Summarize unread emails." | Filtered inbox summary, message list, and action items |
| Calendar Lookup | "What meetings do I have today?" | Matching meetings by time, plus any schedule conflicts |
| Ticket / Task Assistant | "Show blocked tickets." | Filtered tickets or tasks with status, priority, and assignee or owner |
| Daily Briefing | "Give me my daily briefing." | One overview of email, calendar, tickets, and a focus list |
| Meeting Prep | "Prep me for the security review board." | A prep sheet: agenda, related items, risks, and follow-ups |
| Workflow / Approval Agent | "Show pending approvals." | Approvals list, status detail, or a simulated decision |
