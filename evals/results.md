# Eval results

- Generated: 2026-06-11 22:46 UTC
- Dataset: `C:\Agentic AI\LangGraph\Agentic_RAG_Claude\evals\questions.jsonl`
- Rows evaluated: 15

## Metrics

| Metric | Value |
|---|---|
| Overall passed | 15 / 15 |
| local_corpus passed | 5 / 5 |
| web_fallback passed | 5 / 5 |
| insufficient_context passed | 3 / 3 |
| privacy_mode passed | 2 / 2 |
| stop_reason matches | 7 / 7 |
| source_type matches | 11 / 11 |
| expected_contains matches | 6 / 6 |
| Average retries | 1.2 |
| Average tracked LLM calls | 2.47 |
| Total web searches | 7 |

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
| web-sre-salary | web_fallback | PASS | — | 2 | 5 | 1 | — |
| web-nist-guidelines | web_fallback | PASS | — | 2 | 9 | 2 | — |
| insuf-parental-leave | insufficient_context | PASS | web_search_disabled | 1 | 0 | 0 | — |
| insuf-wifi-password | insufficient_context | PASS | web_search_disabled | 1 | 0 | 0 | — |
| insuf-ai-tools | insufficient_context | PASS | web_search_disabled | 1 | 0 | 0 | — |
| privacy-local-answer | privacy_mode | PASS | — | 1 | 1 | 0 | — |
| privacy-web-question | privacy_mode | PASS | web_search_disabled | 1 | 0 | 0 | — |

## Answers (truncated)

### local-vpn-access

**Q:** How do I request VPN access?

**A:** - Submit the "VPN Access Request" form in the IT Service Portal (ServiceNow → Service Catalog → Network Access). - Your direct manager must approve the request in the portal; requests without manager approval are automatically rejected after 5 business days. - IT Security will provision approved requests within 2 business days. - Complete multi-factor authentication (MFA) enrollment in Okta Verify…

### local-expense-approval

**Q:** What expenses require manager approval?

**A:** Direct manager approval is required for single-item expenses of $100.01–$1,000. Note: expenses over $500 should be approved before purchase whenever practical, and splitting purchases to avoid thresholds is prohibited. Sources: - Local corpus: AcmeCorp Expense Reimbursement Policy

### local-sev1-escalation

**Q:** When should a security incident be escalated to Sev-1?

**A:** Escalate immediately to Sev-1 if any of the following are true: - Confirmed unauthorized access to customer data or employee PII (confirmed data breach). - Ransomware or destructive malware on any production system. - An active attacker with privileged (admin/root) access. - A customer-facing outage caused by a security event that lasts more than 30 minutes or affects more than 10% of customers. -…

### local-after-hours-paging

**Q:** Who gets paged for after-hours production incidents?

**A:** - Primary on-call engineer for the service that owns the failing component (pages are routed via the PagerDuty service mapping). - If the owning service is unclear, the SRE platform on-call is paged and will re-route the incident. Escalation (if the page is not acknowledged): - Secondary on-call — auto-paged if no ack after 10 minutes. - Engineering manager — paged if no ack from secondary after a…

### local-audit-log-retention

**Q:** How long are security audit logs retained?

**A:** Security audit logs are retained for 18 months. The first 90 days are kept in hot storage, then they move to cold archive. Note that contract- or jurisdiction-specific retention requirements take precedence, and legal holds override this schedule. Sources: - Local corpus: AcmeCorp Data Retention Policy

### web-python-version

**Q:** What is the latest stable version of Python right now?

**A:** According to the provided documents, the latest stable release is Python 3.14.6 (released June 10, 2026). Sources: - Web search: Python Source Releases — https://www.python.org/downloads/source - Web search: Python Release Python 3.13.0 — https://www.python.org/downloads/release/python-3130 - Web search: Python Release Python 3.12.0 — https://www.python.org/downloads/release/python-3120

### web-msft-ceo

**Q:** Who is the current CEO of Microsoft?

**A:** According to the provided documents, the current CEO of Microsoft is Satya Nadella (CEO since 2014). Sources: - Web search: Why Does Microsoft Now Have a New, Extra CEO? — https://technologymagazine.com/news/why-is-microsoft-ceo-satya-nadella-shifting-his-focus-to-ai - Web search: Who is the CEO of Microsoft in 2026? Satya Nadella's Bio - Clay — https://www.clay.com/dossier/microsoft-ceo - Web sea…

### web-cyber-news

**Q:** What are the biggest cybersecurity news stories this week?

**A:** Based only on the provided documents, the prominent cybersecurity items shown this week are: - Microsoft patches an exploited Exchange Server vulnerability (link slug: microsoft-patches-exploited-exchange-server-vulnerability). - Google addresses Vertex security issues after researchers weaponized an AI agent (link slug: google-addresses-vertex-security-issues-after-researchers-weaponize-ai-agent)…

### web-sre-salary

**Q:** What is the average salary for a site reliability engineer in the United States in 2026?

**A:** The documents provide conflicting figures, so I cannot state a single definitive average. - One document explicitly says: "As of Jun 9, 2026, the average annual pay for a Site Reliability Engineer in the United States is $132,583 a year." - Another document reports an average of $157,839 per year (based on 2.6k salaries from job postings on Indeed). - a third document lists an average of $171,745 …

### web-nist-guidelines

**Q:** What does the latest NIST incident response guidance recommend?

**A:** According to the provided materials, NIST recommends enhancing threat detection and incident response by following a four-stage incident‑response lifecycle: - Preparation (establish policies, tools, and response teams before an incident occurs) - Detection and analysis - Containment, eradication, and recovery - Post‑incident activity Sources: - Web search: NIST Best Practices for Cyber Resilience …

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

**A:** Security audit logs are retained for 18 months. - Storage breakdown: hot storage for the first 90 days, then moved to cold archive. - Notes/overrides: contract- or jurisdiction-specific retention requirements recorded in the data‑processing register take precedence; legal holds override the retention schedule. - For questions or exceptions: privacy@acmecorp.example (retention questions), legal@acm…

### privacy-web-question

**Q:** What are today's top technology news headlines?

**A:** I do not have enough information in the provided documents. Note: Web search is disabled, so I could only use the local knowledge base. I may not have enough information to fully answer this question.

