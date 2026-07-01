"""
office_agent.mock_data — local, fictional sample data for the Office Agent.

Phase 2 ships `emails.json`: a small, entirely fictional AcmeCorp-style inbox
used by the mock Email Summary tool (`office_agent.tools.email`). There is NO
connection to Gmail, Outlook, or any mail service — this is static local data so
the tool is deterministic and CI-safe. Replace it with a real mail adapter in a
later phase behind the same tool interface.
"""
