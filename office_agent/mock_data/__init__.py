"""
office_agent.mock_data — local, fictional sample data for the Office Agent.

Ships two static, entirely fictional AcmeCorp-style datasets:

- `emails.json` — inbox data for the mock Email Summary tool
  (`office_agent.tools.email`).
- `calendar_events.json` — calendar data for the mock Calendar Lookup tool
  (`office_agent.tools.calendar`).

There is NO connection to Gmail, Outlook, Google Calendar, or any service — this
is static local data so the tools stay deterministic and CI-safe. Replace it
with real adapters in later phases behind the same tool interfaces.
"""
