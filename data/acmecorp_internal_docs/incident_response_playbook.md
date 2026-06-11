# AcmeCorp Security Incident Response Playbook

- **Document ID:** ITSEC-PLB-002
- **Version:** 4.1
- **Effective date:** 2026-02-01
- **Policy owner:** Security Engineering (security-eng@acmecorp.example)
- **Applies to:** All engineering, IT, and security staff

## 1. Purpose and scope

This playbook defines how AcmeCorp classifies, escalates, and responds to
security incidents: suspected breaches, malware, credential compromise,
denial of service, and data exposure. For routine production outages with no
security dimension, use the *On-Call and Escalation Policy* (OPS-POL-003).

## 2. Severity levels

| Severity | Definition | Examples |
|---|---|---|
| **Sev-3** | Limited, contained issue with no confirmed data impact | Single phishing email reported, malware blocked by EDR |
| **Sev-2** | Active issue with potential for data or service impact | Compromised non-privileged account, vulnerability being actively probed |
| **Sev-1** | Confirmed or imminent major impact | Confirmed data breach, ransomware, active attacker with privileged access |

## 3. When to escalate to Sev-1

Escalate **immediately** to Sev-1 if **any** of the following is true:

- Confirmed unauthorized access to customer data or employee PII.
- Ransomware or destructive malware on any production system.
- An active attacker with privileged (admin/root) access.
- A customer-facing outage caused by a security event lasting more than
  **30 minutes** or affecting more than **10%** of customers.
- Any incident with likely regulatory notification obligations.

When in doubt between Sev-2 and Sev-1, **declare Sev-1**. Downgrading later
is cheap; a late escalation is not.

## 4. Sev-1 response steps

1. **Page the Incident Commander** via the PagerDuty service **"sec-ic"**.
   The IC must acknowledge within **15 minutes**.
2. IC opens a dedicated Slack channel **#incident-<id>** and starts the
   incident log.
3. **Notify the CISO and Legal within 1 hour** for any suspected data
   exposure. Legal owns all regulatory-notification decisions.
4. Contain first, investigate second: isolate affected hosts, revoke
   compromised credentials, block attacker infrastructure.
5. Preserve evidence before remediation — snapshot affected systems and
   export relevant logs. Evidence retention follows the *Data Retention
   Policy* (CMP-POL-005), and legal hold overrides normal deletion.
6. Communications: only the IC or their delegate posts status updates. No
   public statements or customer notifications without Legal approval.

## 5. Sev-2 and Sev-3 handling

- **Sev-2:** assign an owner in the security queue within **4 business
  hours**; daily status updates until resolved.
- **Sev-3:** triage within **2 business days**; batch-review acceptable.

## 6. Post-incident review

Every Sev-1 and Sev-2 incident requires a blameless post-incident review
within **5 business days** of resolution, with a written timeline, root
cause, and tracked action items.

## 7. Exceptions

Deviations from this playbook during an active incident must be approved by
the Incident Commander and recorded in the incident log. Standing exceptions
require CISO approval.

## 8. Contacts and escalation paths

| Need | Contact |
|---|---|
| Report a suspected incident (24/7) | PagerDuty service "sec-ir" or #security-reports |
| Sev-1 Incident Commander | PagerDuty service "sec-ic" |
| Regulatory / disclosure questions | Legal — legal@acmecorp.example |
| Playbook questions | Security Engineering — security-eng@acmecorp.example |
