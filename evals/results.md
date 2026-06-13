# Eval results

- Generated: 2026-06-13 05:02 UTC
- Dataset: `C:\Agentic AI\LangGraph\Agentic_RAG_Claude\evals\questions.jsonl`
- Rows evaluated: 24

## Metrics

| Metric | Value |
|---|---|
| Overall passed | 24 / 24 |
| local_corpus passed | 5 / 5 |
| web_fallback passed | 5 / 5 |
| insufficient_context passed | 3 / 3 |
| privacy_mode passed | 2 / 2 |
| multi_document passed | 4 / 4 |
| policy_fallback passed | 5 / 5 |
| stop_reason matches | 13 / 13 |
| source_type matches | 15 / 15 |
| expected_contains matches | 12 / 12 |
| expected_not_contains matches | 0 / 0 |
| source_titles matches | 5 / 5 |
| min_local_sources matches | 4 / 4 |
| web_search_count matches | 9 / 9 |
| policy_applied matches | 9 / 9 |
| Average retries | 1.25 |
| Average tracked LLM calls | 2.71 |
| Total web searches | 12 |

Tracked LLM calls are the graph's budgeted operational counter (generations, query rewrites, web-result grades). Router and grader calls are not individually tracked, so this is not total LLM usage and not billing-accurate cost accounting.

## Per-question results

| id | category | passed | stop_reason | retries | tracked llm | web | failed checks |
|---|---|---|---|---|---|---|---|
| local-vpn-access | local_corpus | PASS | — | 1 | 1 | 0 | — |
| local-expense-approval | local_corpus | PASS | — | 1 | 1 | 0 | — |
| local-sev1-escalation | local_corpus | PASS | — | 1 | 1 | 0 | — |
| local-after-hours-paging | local_corpus | PASS | — | 1 | 1 | 0 | — |
| local-audit-log-retention | local_corpus | PASS | — | 1 | 1 | 0 | — |
| web-python-version | web_fallback | PASS | — | 2 | 9 | 2 | — |
| web-msft-ceo | web_fallback | PASS | — | 1 | 4 | 1 | — |
| web-cyber-news | web_fallback | PASS | — | 1 | 4 | 1 | — |
| web-sre-salary | web_fallback | PASS | — | 1 | 4 | 1 | — |
| web-nist-guidelines | web_fallback | PASS | — | 5 | 20 | 4 | — |
| insuf-parental-leave | insufficient_context | PASS | web_search_disabled | 1 | 0 | 0 | — |
| insuf-wifi-password | insufficient_context | PASS | web_search_disabled | 1 | 0 | 0 | — |
| insuf-ai-tools | insufficient_context | PASS | web_search_disabled | 1 | 0 | 0 | — |
| privacy-local-answer | privacy_mode | PASS | — | 1 | 1 | 0 | — |
| privacy-web-question | privacy_mode | PASS | web_search_disabled | 1 | 0 | 0 | — |
| multi-onboarding-vpn | multi_document | PASS | — | 1 | 1 | 0 | — |
| multi-sev1-after-hours | multi_document | PASS | — | 1 | 1 | 0 | — |
| multi-legal-hold-audit-logs | multi_document | PASS | — | 1 | 1 | 0 | — |
| multi-shared-vpn-credentials | multi_document | PASS | — | 1 | 1 | 0 | — |
| policy-conservative-stays-local | policy_fallback | PASS | — | 1 | 1 | 0 | — |
| policy-aggressive-escalates | policy_fallback | PASS | — | 1 | 4 | 1 | — |
| policy-conservative-web-when-empty | policy_fallback | PASS | — | 2 | 5 | 1 | — |
| policy-disabled-declines-honestly | policy_fallback | PASS | — | 1 | 0 | 0 | — |
| policy-disabled-router-web-still-works | policy_fallback | PASS | — | 1 | 4 | 1 | — |

## Answers (truncated)

### local-vpn-access

**Q:** How do I request VPN access?

**A:** Do the following: 1. Submit the "VPN Access Request" form in the IT Service Portal (ServiceNow → Service Catalog → Network Access). 2. Have your direct manager approve the request in the portal (requests without manager approval are automatically rejected after 5 business days). 3. IT Security will provision approved requests within 2 business days. 4. Before first use, complete multi-factor authe…

### local-expense-approval

**Q:** What expenses require manager approval?

**A:** - Per the approval thresholds: any single-item expense of $100.01–$1,000 requires direct manager approval. - Travel note: choosing premium economy on flights over 6 hours is permitted only with manager approval. - Also, expenses over $500 should be approved before the purchase whenever practical (and splitting purchases to avoid thresholds is prohibited). Sources: - Local corpus: AcmeCorp Expense …

### local-sev1-escalation

**Q:** When should a security incident be escalated to Sev-1?

**A:** Escalate immediately to Sev‑1 if any of the following apply: - Confirmed unauthorized access to customer data or employee PII. - Ransomware or destructive malware on any production system. - An active attacker with privileged (admin/root) access. - A customer‑facing outage caused by a security event that lasts >30 minutes or affects >10% of customers. - Any incident likely to trigger regulatory no…

### local-after-hours-paging

**Q:** Who gets paged for after-hours production incidents?

**A:** After-hours production incidents page the primary on‑call engineer for the service that owns the failing component (via PagerDuty service mapping). If the owning service is unclear, the SRE platform on‑call is paged and will re‑route the incident. Note: Sev‑3 issues do not page after hours (they are queued for business hours). Sources: - Local corpus: AcmeCorp On-Call and Escalation Policy

### local-audit-log-retention

**Q:** How long are security audit logs retained?

**A:** Security audit logs are retained for 18 months. They remain in hot storage for 90 days, then move to cold archive. Note: contract- or jurisdiction-specific retention requirements can override this schedule; retention exceptions require written approval from Compliance & Legal (see privacy@acmecorp.example) and audit-log access requests go to security-eng@acmecorp.example. Sources: - Local corpus: …

### web-python-version

**Q:** What is the latest stable version of Python right now?

**A:** According to the provided documents, the latest stable Python release is Python 3.14.6 (released June 10, 2026). Sources: - Web search: Python Release Python 3.9.0 — https://www.python.org/downloads/release/python-390 - Web search: Python Source Releases — https://www.python.org/downloads/source - Web search: Python Release Python 3.12.6 — https://www.python.org/downloads/release/python-3126

### web-msft-ceo

**Q:** Who is the current CEO of Microsoft?

**A:** According to the provided documents, the current CEO of Microsoft is Satya Nadella (CEO since 2014; also executive chairman). Sources: - Web search: Why Does Microsoft Now Have a New, Extra CEO? — https://technologymagazine.com/news/why-is-microsoft-ceo-satya-nadella-shifting-his-focus-to-ai - Web search: Who is the CEO of Microsoft in 2026? Satya Nadella's Bio - Clay — https://www.clay.com/dossie…

### web-cyber-news

**Q:** What are the biggest cybersecurity news stories this week?

**A:** Based on the provided documents, the biggest cybersecurity stories this week are: - New wave of the "Mini Shai‑Hulud" campaign — a supply‑chain poisoning campaign resurfacing in the wild, cited as evidence that software supply‑chain poisoning is becoming a recurring, high‑impact threat in 2026. - Akamai SOTI Security report: “AI‑Empowered Botnets and API Visibility Gaps” — the report highlights in…

### web-sre-salary

**Q:** What is the average salary for a site reliability engineer in the United States in 2026?

**A:** The provided documents give conflicting figures rather than a single definitive number: - $157,916 per year (based on 2.6k salaries from job postings on Indeed). - $132,583 per year (reported as of Jun 11, 2026). The Site Reliability Engineer Salary Guide 2026 also reports a 2026 base-salary range of roughly $100,000–$265,000, with mid-level SREs near $130,000–$175,000, seniors $160,000–$210,000, …

### web-nist-guidelines

**Q:** What does the latest NIST incident response guidance recommend?

**A:** Based only on the provided documents, the latest NIST incident response guidance (NIST SP 800-61 Revision 3, released April 3, 2025) recommends the following high-level approaches: - Align incident response with the NIST Cybersecurity Framework (CSF) 2.0 functions — explicitly mapping incident response recommendations to CSF functions such as Govern, Identify, Protect, Detect, Respond, and Recover…

### insuf-parental-leave

**Q:** What is AcmeCorp's parental leave policy?

**A:** I do not have enough information in the provided documents. Note: Web search is disabled, so I could only use the local knowledge base. I may not have enough information to fully answer this question.

### insuf-wifi-password

**Q:** What is the Wi-Fi password for the AcmeCorp Berlin office?

**A:** I do not have enough information in the provided documents. Note: Web search is disabled, so I could only use the local knowledge base. I may not have enough information to fully answer this question.

### insuf-ai-tools

**Q:** What is AcmeCorp's policy on using personal AI tools for work?

**A:** I do not have enough information in the provided documents. Note: Web search is disabled, so I could only use the local knowledge base. I may not have enough information to fully answer this question.

### privacy-local-answer

**Q:** How long are security audit logs retained?

**A:** Security audit logs are retained for 18 months. They stay in hot storage for the first 90 days, then move to cold archive. Notes: contract- or jurisdiction-specific retention requirements in a customer's contract take precedence and are recorded in the data-processing register; Legal holds override the retention schedule. For retention questions or exceptions, contact privacy@acmecorp.example. Sou…

### privacy-web-question

**Q:** What are today's top technology news headlines?

**A:** I do not have enough information in the provided documents. Note: Web search is disabled, so I could only use the local knowledge base. I may not have enough information to fully answer this question.

### multi-onboarding-vpn

**Q:** As a new employee, how do I get VPN access and what do I need to set up before I can use it?

**A:** Short answer — follow the onboarding flow and complete MFA before you can use VPN. Step-by-step (new hire): 1. Day one - Pick up your laptop (or confirm courier delivery). - Activate your Okta account and enroll in Okta Verify (MFA). MFA enrollment is required before any internal system — including VPN — will let you in. 2. Request VPN (if your onboarding ticket does not already include it) - Subm…

### multi-sev1-after-hours

**Q:** A Sev-1 security incident starts at 2 AM - who gets paged and how quickly must they acknowledge?

**A:** Short answer - Page the Incident Commander via the PagerDuty service "sec-ic" — the IC must acknowledge within 15 minutes. - Because it’s after hours, also page the primary on‑call engineer for the service that owns the failing component (as routed by PagerDuty). The primary on‑call must acknowledge within 5 minutes for a Sev‑1. Escalation if unacknowledged - If the owning service is unclear, the …

### multi-legal-hold-audit-logs

**Q:** During a security incident, what does the Incident Response Playbook say about evidence preservation or Incident Commander holds, and what does the Data Retention Policy say about normal audit-log ret…

**A:** - Incident Response Playbook: preserve evidence before remediation — snapshot affected systems and export relevant logs. Evidence retention follows the Data Retention Policy (CMP‑POL‑005), and a legal hold overrides normal deletion. - Data Retention Policy (normal audit-log retention): security audit logs are retained for 18 months (hot storage for 90 days, then moved to cold archive). Sources: - …

### multi-shared-vpn-credentials

**Q:** Using AcmeCorp's VPN Access Policy and Security Incident Response Playbook, what happens when an employee shares VPN credentials or MFA devices, and should the incident be reported through PagerDuty s…

**A:** - What happens: Per the VPN Access Policy, sharing VPN credentials or MFA devices is explicitly prohibited and "treated as a security incident." The Security Incident Response Playbook (ITSEC-PLB-002) covers credential compromise as an incident type and defines how such incidents are classified, escalated, and responded to. - How to report: The provided documents do not state whether to report via…

### policy-conservative-stays-local

**Q:** What security training must new employees complete?

**A:** New hires must complete the mandatory security awareness training within 7 days of their start date. It is assigned automatically in the learning portal, and access to production systems is blocked until it is finished. Sources: - Local corpus: AcmeCorp Employee Onboarding Guide

### policy-aggressive-escalates

**Q:** What security training must new employees complete?

**A:** - Complete the mandatory security awareness training assigned in the learning portal within 7 days of your start date. (Access to production systems is blocked until this is finished.) - The onboarding materials list a Basic Information Security Awareness Training (≈41 minutes) as part of required trainings. - You may also be assigned role-specific security training (for example, secure‑coding tra…

### policy-conservative-web-when-empty

**Q:** What is AcmeCorp's pet insurance benefit?

**A:** I do not have enough information in the provided documents to state AcmeCorp’s specific pet insurance benefit. From the documents you provided, the only pet-insurance facts available are: - Pet insurance may give you cash back for certain medical expenses. - Plan details (including information on pre‑existing conditions and other restrictions) are in the “more resources” section and the Benefit Bo…

### policy-disabled-declines-honestly

**Q:** What is AcmeCorp's pet insurance benefit?

**A:** I do not have enough information in the provided documents.

### policy-disabled-router-web-still-works

**Q:** Who is the current CEO of Microsoft?

**A:** According to the provided documents, the current CEO of Microsoft is Satya Nadella (CEO since February 2014; also Chairman since 2021). Sources: - Web search: Why Does Microsoft Now Have a New, Extra CEO? — https://technologymagazine.com/news/why-is-microsoft-ceo-satya-nadella-shifting-his-focus-to-ai - Web search: Satya Nadella - Wikipedia — https://en.wikipedia.org/wiki/Satya_Nadella - Web searc…

