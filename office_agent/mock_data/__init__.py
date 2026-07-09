"""
office_agent.mock_data — local, fictional sample data for the Office Agent.

Ships static, entirely fictional AcmeCorp-style datasets:

- `emails.json` — inbox data for the mock Email Summary tool
  (`office_agent.tools.email`).
- `calendar_events.json` — calendar data for the mock Calendar Lookup tool
  (`office_agent.tools.calendar`).
- `tickets.json` / `tasks.json` — ticket/task data for the mock Task / Ticket
  Assistant (`office_agent.tools.tickets`).
- `approvals.json` / `audit_log.json` — approval queue and audit log for the mock
  Workflow / Approval Agent (`office_agent.tools.approvals`).

There is NO connection to Gmail, Outlook, Google Calendar, Jira, Linear, or any
service — this is static local data so the tools stay deterministic and CI-safe.
The tools treat these files as read-only (task creation is simulated and never
writes here). Replace them with real adapters in later phases behind the same
tool interfaces.
"""
