# Enterprise RAG Eval Baseline

Snapshot date: 2026-07-06
Source: `evals/enterprise_rag/results.md`
- Dataset file at evaluation time: `evals/questions.jsonl`
Dataset: synthetic AcmeCorp evaluation dataset

This is an intentionally committed, reviewed snapshot for documentation and
portfolio purposes. The runtime-generated report at
`evals/enterprise_rag/results.md` is gitignored and may be overwritten by future
eval runs.

# Eval results

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
| Average tracked LLM calls | 2.54 |
| Total web searches | 11 |

Tracked LLM calls are the graph's budgeted operational counter (generations, query rewrites, web-result grades). Router and grader calls are not individually tracked, so this is not total LLM usage and not billing-accurate cost accounting.

## Delta vs. previous run

No previous run found — this is the first recorded run.

## Per-question results

| id | category | passed | stop_reason | retries | tracked llm | web | failed checks |
|---|---|---|---|---|---|---|---|
| local-vpn-access | local_corpus | PASS | — | 1 | 1 | 0 | — |
| local-expense-approval | local_corpus | PASS | — | 1 | 1 | 0 | — |
| local-sev1-escalation | local_corpus | PASS | — | 1 | 1 | 0 | — |
| local-after-hours-paging | local_corpus | PASS | — | 1 | 1 | 0 | — |
| local-audit-log-retention | local_corpus | PASS | — | 1 | 1 | 0 | — |
| web-python-version | web_fallback | PASS | — | 3 | 14 | 3 | — |
| web-msft-ceo | web_fallback | PASS | — | 1 | 4 | 1 | — |
| web-cyber-news | web_fallback | PASS | — | 1 | 4 | 1 | — |
| web-sre-salary | web_fallback | PASS | — | 1 | 4 | 1 | — |
| web-nist-guidelines | web_fallback | PASS | — | 1 | 4 | 1 | — |
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
| policy-conservative-web-when-empty | policy_fallback | PASS | max_retries_not_grounded | 5 | 12 | 2 | — |
| policy-disabled-declines-honestly | policy_fallback | PASS | — | 1 | 0 | 0 | — |
| policy-disabled-router-web-still-works | policy_fallback | PASS | — | 1 | 4 | 1 | — |

## Answers (truncated)

### local-vpn-access

**Q:** How do I request VPN access?

**A:** Short answer — do this: 1. In the IT Service Portal submit the "VPN Access Request" form (ServiceNow → Service Catalog → Network Access). 2. Have your direct manager approve the request in the portal (requests without manager approval are automatically rejected after 5 business days). 3. After manager approval, IT Security provisions approved requests within 2 business days. 4. Before first use, c…

### local-expense-approval

**Q:** What expenses require manager approval?

**A:** Per the policy, manager approval is required for: - Any single-item expense of $100.01–$1,000 (direct manager approval). - Approval to book premium-economy for flights longer than 6 hours (manager approval is required). Note: Expenses over $500 should be approved before purchase whenever practical, and splitting purchases to stay under thresholds is prohibited. Sources: - Local corpus: AcmeCorp Ex…

### local-sev1-escalation

**Q:** When should a security incident be escalated to Sev-1?

**A:** Escalate immediately to Sev-1 if any of the following apply: - Confirmed unauthorized access to customer data or employee PII. - Ransomware or destructive malware on any production system. - An active attacker with privileged (admin/root) access. - A customer-facing outage caused by a security event lasting > 30 minutes or affecting > 10% of customers. - Any incident with likely regulatory notific…

### local-after-hours-paging

**Q:** Who gets paged for after-hours production incidents?

**A:** - Initial page: the primary on-call engineer for the service that owns the failing component (as routed by PagerDuty). - If the owning service is unclear: the SRE platform on-call is paged and will re-route the incident. - Escalation (if unacknowledged): - Secondary on-call is paged automatically (no ack after 10 minutes). - Engineering manager is paged (no ack from secondary after a further 10 mi…

### local-audit-log-retention

**Q:** How long are security audit logs retained?

**A:** Security audit logs are retained for 18 months. They are kept in hot storage for the first 90 days and then moved to cold archive. Note: contract- or jurisdiction-specific retention requirements can supersede this schedule, and legal holds override the retention rules. Sources: - Local corpus: AcmeCorp Data Retention Policy

### web-python-version

**Q:** What is the latest stable version of Python right now?

**A:** According to the provided documents, the latest stable Python release is Python 3.14.6. Sources: - Web search: Python Release Python 3.12.0 — https://www.python.org/downloads/release/python-3120 - Web search: Python Release Python 3.14.0 — https://www.python.org/downloads/release/python-3140 - Web search: Download Python - Python.org — https://www.python.org/downloads

### web-msft-ceo

**Q:** Who is the current CEO of Microsoft?

**A:** The current CEO of Microsoft is Satya Nadella (appointed CEO in February 2014 and also serving as Chairman). Sources: - Web search: Satya Nadella — https://news.microsoft.com/source/exec/satya-nadella - Web search: Satya Nadella — https://en.wikipedia.org/wiki/Satya_Nadella - Web search: Satya Nadella — https://build.microsoft.com/en-US/speakers/1768245294609build26-1775670526436001p1Pd

### web-cyber-news

**Q:** What are the biggest cybersecurity news stories this week?

**A:** Based only on the documents you provided, the biggest cybersecurity stories this week are: - Google addresses Vertex security issues after researchers weaponize AI agents — Google patched Vertex security problems after researchers demonstrated weaponizing AI agents. - Cisco patches another SD‑WAN zero‑day that has been exploited in attacks — Cisco released a fix for a newly exploited SD‑WAN vulner…

### web-sre-salary

**Q:** What is the average salary for a site reliability engineer in the United States in 2026?

**A:** The documents provide differing figures: - $132,583 per year — reported “as of Jun 14, 2026” for a Site Reliability Engineer in the U.S. - $157,974 per year — from Indeed (based on 2.7k salaries / job postings). - $166,123 per year — from Glassdoor (with experience-based ranges also listed). So average pay depends on the source; the provided documents do not give a single unified 2026 average. Sou…

### web-nist-guidelines

**Q:** What does the latest NIST incident response guidance recommend?

**A:** Based on the provided documents, the latest NIST incident‑response guidance: - Sets forth six principles companies should consider when planning incident‑response programs to help ensure they are efficient. - In Revision 3, adds significant new recommendations and guidance; entities should consider reviewing and updating their incident‑response materials in light of those changes. - Organizes resp…

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

**A:** Security audit logs are retained for 18 months. They remain in hot storage for the first 90 days, then are moved to cold archive. Notes from the policy: - Customer-specific contracts or local regulations may require longer retention; the contract schedule takes precedence and is recorded in the data-processing register. - Legal holds override retention and deletion rules. - For retention questions…

### privacy-web-question

**Q:** What are today's top technology news headlines?

**A:** I do not have enough information in the provided documents. Note: Web search is disabled, so I could only use the local knowledge base. I may not have enough information to fully answer this question.

### multi-onboarding-vpn

**Q:** As a new employee, how do I get VPN access and what do I need to set up before I can use it?

**A:** Short answer - Request VPN access in the IT Service Portal (ServiceNow → Service Catalog → Network Access). Your manager must approve the request. IT Security will provision approved requests within 2 business days. Do not submit a duplicate request if your onboarding ticket already includes VPN. - Before you can use VPN you must activate your Okta account and enroll in Okta Verify (MFA). VPN sign…

### multi-sev1-after-hours

**Q:** A Sev-1 security incident starts at 2 AM - who gets paged and how quickly must they acknowledge?

**A:** Short answer: - Page the Incident Commander via the PagerDuty service "sec-ic". The IC must acknowledge within 15 minutes. - In addition, after‑hours production paging will page the primary on‑call engineer for the service that owns the failing component (or the SRE platform on‑call if the owner is unclear). The primary on‑call must acknowledge within 5 minutes for a Sev‑1. If the primary does not…

### multi-legal-hold-audit-logs

**Q:** During a security incident, what does the Incident Response Playbook say about evidence preservation or Incident Commander holds, and what does the Data Retention Policy say about normal audit-log ret…

**A:** From the Incident Response Playbook (Sev‑1 steps) - Preserve evidence before remediation: snapshot affected systems and export relevant logs. - Evidence retention is governed by the Data Retention Policy (CMP‑POL‑005). - A legal hold overrides normal deletion. The playbook does not state that the Incident Commander can unilaterally override deletions—only that legal hold takes precedence. From the…

### multi-shared-vpn-credentials

**Q:** Using AcmeCorp's VPN Access Policy and Security Incident Response Playbook, what happens when an employee shares VPN credentials or MFA devices, and should the incident be reported through PagerDuty s…

**A:** - What happens: Sharing VPN credentials or MFA devices is explicitly prohibited by the VPN Access Policy and "treated as a security incident" (ITSEC-POL-004). The matter should be handled under the Security Incident Response Playbook (ITSEC-PLB-002), which governs classification, escalation, and response for credential compromise and related incidents. - Reporting channel: The two provided documen…

### policy-conservative-stays-local

**Q:** What security training must new employees complete?

**A:** New hires must complete the mandatory security awareness training. It is assigned automatically in the learning portal and must be finished within 7 days of your start date — access to production systems is blocked until it is complete. Sources: - Local corpus: AcmeCorp Employee Onboarding Guide

### policy-aggressive-escalates

**Q:** What security training must new employees complete?

**A:** - Mandatory Security Awareness training — it is assigned automatically in the learning portal and must be completed within 7 days of your start date (access to production systems is blocked until it is finished). - Company policy also states approved Security Awareness training must be completed prior to, or within 30 days of, being granted access to Company Information Resources. - Additional rol…

### policy-conservative-web-when-empty

**Q:** What is AcmeCorp's pet insurance benefit?

**A:** AcmeCorp’s pet insurance (both plans) has a $250 annual deductible and a $7,500 maximum annual benefit. Pre‑existing conditions are not covered. Covered items listed include accidents, illnesses, hereditary and congenital conditions, and cancer. Warning: This answer did not pass the grounding (anti-hallucination) check after the retry limit was reached. It may contain information that is not suppo…

### policy-disabled-declines-honestly

**Q:** What is AcmeCorp's pet insurance benefit?

**A:** I do not have enough information in the provided documents.

### policy-disabled-router-web-still-works

**Q:** Who is the current CEO of Microsoft?

**A:** According to the provided documents, Satya Nadella is the current CEO of Microsoft. Sources: - Web search: Why Does Microsoft Now Have a New, Extra CEO? — https://technologymagazine.com/news/why-is-microsoft-ceo-satya-nadella-shifting-his-focus-to-ai - Web search: Who is the CEO of Microsoft in 2026? Satya Nadella's Bio - Clay — https://www.clay.com/dossier/microsoft-ceo - Web search: Satya Nadell…
