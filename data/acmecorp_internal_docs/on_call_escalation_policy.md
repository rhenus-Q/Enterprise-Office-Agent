# AcmeCorp On-Call and Escalation Policy

- **Document ID:** OPS-POL-003
- **Version:** 2.4
- **Effective date:** 2025-09-15
- **Policy owner:** Site Reliability Engineering (sre@acmecorp.example)
- **Applies to:** All engineering teams that own production services

## 1. Purpose and scope

This policy defines who gets paged for production incidents, how quickly
pages must be acknowledged, and how unanswered pages escalate. Security
incidents additionally follow the *Security Incident Response Playbook*
(ITSEC-PLB-002).

## 2. Rotation structure

- Every production service has a **primary** and **secondary** on-call
  engineer in PagerDuty.
- Rotations are **weekly**, handing off on **Mondays at 10:00 local time**
  with a written handoff note in the team channel.
- Engineers must have completed at least 3 months on the team and a shadow
  rotation before joining the on-call rotation.

## 3. Who gets paged

**After-hours production incidents page the primary on-call engineer of the
service that owns the failing component**, as routed by the PagerDuty
service mapping. If the owning service is unclear, the SRE platform on-call
is paged and re-routes the incident.

## 4. Acknowledgement SLAs and escalation chain

| Step | Target | Trigger |
|---|---|---|
| Primary on-call | Ack within **5 min** (Sev-1) / **15 min** (Sev-2) | Initial page |
| Secondary on-call | Paged automatically | No ack after **10 minutes** |
| Engineering manager | Paged | No ack from secondary after a further 10 minutes |
| Director of Engineering | Notified | Sev-1 unacknowledged for 30 minutes total |

Sev-3 issues do not page after hours; they are queued for business hours.

## 5. During an incident

- The first responder is the incident owner until they explicitly hand off.
- Open a dedicated channel **#inc-<service>-<date>** for any incident
  lasting longer than 30 minutes.
- Customer-impacting incidents require a status-page update within
  **20 minutes** of confirmation.
- Do not perform risky remediation alone at night — page the secondary for
  a second pair of eyes.

## 6. Compensation and well-being

- On-call weeks carry the standard on-call stipend (see the compensation
  page in the HR portal).
- If you are paged for more than 4 cumulative hours overnight, take
  recovery time the next day and notify your manager.

## 7. Exceptions

Teams may propose alternative rotation structures (e.g., follow-the-sun) to
SRE leadership. Exceptions are documented per-service in the service
catalog and reviewed every 6 months.

## 8. Contacts

| Need | Contact |
|---|---|
| Rotation or PagerDuty configuration | #sre-oncall on Slack |
| Policy questions | sre@acmecorp.example |
| Escalation problems during an incident | SRE platform on-call (PagerDuty "sre-platform") |
