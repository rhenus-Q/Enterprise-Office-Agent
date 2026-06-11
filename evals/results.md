# Eval results

- Generated: 2026-06-11 19:10 UTC
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
| Average retries | 1.0 |
| Average tracked LLM calls | 1.93 |
| Total web searches | 6 |

Tracked LLM calls are the graph's budgeted operational counter (generations, query rewrites, web-result grades). Router and grader calls are not individually tracked, so this is not total LLM usage and not billing-accurate cost accounting.

## Per-question results

| id | category | passed | stop_reason | retries | tracked llm | web | failed checks |
|---|---|---|---|---|---|---|---|
| local-vpn-access | local_corpus | PASS | — | 1 | 1 | 0 | — |
| local-expense-approval | local_corpus | PASS | — | 1 | 1 | 0 | — |
| local-sev1-escalation | local_corpus | PASS | — | 1 | 4 | 1 | — |
| local-after-hours-paging | local_corpus | PASS | — | 1 | 1 | 0 | — |
| local-audit-log-retention | local_corpus | PASS | — | 1 | 1 | 0 | — |
| web-python-version | web_fallback | PASS | — | 1 | 4 | 1 | — |
| web-msft-ceo | web_fallback | PASS | — | 1 | 4 | 1 | — |
| web-cyber-news | web_fallback | PASS | — | 1 | 4 | 1 | — |
| web-sre-salary | web_fallback | PASS | — | 1 | 4 | 1 | — |
| web-nist-guidelines | web_fallback | PASS | — | 1 | 4 | 1 | — |
| insuf-parental-leave | insufficient_context | PASS | web_search_disabled | 1 | 0 | 0 | — |
| insuf-wifi-password | insufficient_context | PASS | web_search_disabled | 1 | 0 | 0 | — |
| insuf-ai-tools | insufficient_context | PASS | web_search_disabled | 1 | 0 | 0 | — |
| privacy-local-answer | privacy_mode | PASS | — | 1 | 1 | 0 | — |
| privacy-web-question | privacy_mode | PASS | web_search_disabled | 1 | 0 | 0 | — |

## Answers (truncated)

### local-vpn-access

**Q:** How do I request VPN access?

**A:** Submit the "VPN Access Request" form in the IT Service Portal: - ServiceNow → Service Catalog → Network Access. - Your direct manager must approve the request in the portal; requests without manager approval are automatically rejected after 5 business days. - IT Security provisions approved requests within 2 business days. - Complete MFA enrollment in Okta Verify before first use (VPN sign‑in with…

### local-expense-approval

**Q:** What expenses require manager approval?

**A:** - Single-item expenses of $100.01–$1,000 require approval by your direct manager. - Premium-economy airfare on flights longer than 6 hours is permitted only with manager approval. Note: the policy also says expenses over $500 should be approved before purchase whenever practical, and splitting purchases to avoid thresholds is prohibited. Sources: - Local corpus: AcmeCorp Expense Reimbursement Poli…

### local-sev1-escalation

**Q:** When should a security incident be escalated to Sev-1?

**A:** Escalate immediately to Sev-1 if any of the following is true: - Confirmed unauthorized access to customer data or employee PII. - Ransomware or destructive malware on any production system. - An active attacker with privileged (admin/root) access. - A customer-facing outage caused by a security event that has lasted >30 minutes or affects >10% of customers. - Any incident likely to trigger regula…

### local-after-hours-paging

**Q:** Who gets paged for after-hours production incidents?

**A:** - Primary on-call engineer for the service that owns the failing component — pages are routed via the PagerDuty service mapping. - If the owning service is unclear, the SRE platform on-call is paged and will re-route the incident. Escalation (if pages go unacknowledged) - Primary on-call: Ack target 5 min (Sev‑1) / 15 min (Sev‑2) after the initial page. - Secondary on-call: Automatically paged if …

### local-audit-log-retention

**Q:** How long are security audit logs retained?

**A:** Security audit logs are retained for 18 months. They remain in hot storage for the first 90 days, then move to cold archive. Note: contract- or jurisdiction-specific retention requirements can override this schedule (recorded in the data-processing register), and legal holds temporarily override retention/deletion. Sources: - Local corpus: AcmeCorp Data Retention Policy

### web-python-version

**Q:** What is the latest stable version of Python right now?

**A:** According to the provided documents, the latest stable Python release is Python 3.14, released on October 7, 2025. Sources: - Web search: "What is the latest stable version of Python right now?"

### web-msft-ceo

**Q:** Who is the current CEO of Microsoft?

**A:** The current CEO of Microsoft is Satya Narayana Nadella. Sources: - Web search: "Who is the current CEO of Microsoft?"

### web-cyber-news

**Q:** What are the biggest cybersecurity news stories this week?

**A:** Based on the provided documents, the biggest cybersecurity stories this week are: - Chrome V8 zero‑day (CVE‑2026‑11645) exploited in the wild — users/administrators urged to patch. - New FROST attack: websites can track what sites/apps you open via SSD timing. - One‑character Linux kernel flaw enables local root access; public exploits available. - CISA adds Cisco, Chrome, and Arista flaws to its …

### web-sre-salary

**Q:** What is the average salary for a site reliability engineer in the United States in 2026?

**A:** The documents do not give a single, definitive 2026 figure. Reported averages in the provided sources include: - Built In: average salary $131,477 (additional cash $15,684; average total compensation $147,161); median $120,000. - Another Built In/Career summary: average base ≈ $130,214 and total compensation ≈ $144,134. - Glassdoor (cited in the 2026 salary guide): average SRE salary $166,123. So …

### web-nist-guidelines

**Q:** What does the latest NIST incident response guidance recommend?

**A:** Summary of the latest NIST incident response guidance (SP 800-61 Revision 3, April 2025): - Purpose and scope - SP 800-61r3 (April 2025) supersedes Revision 2 and shifts focus from static procedures to embedding incident response into cybersecurity risk management using the NIST Cybersecurity Framework (CSF) 2.0. - It aims to provide a common language and guidance to improve preparedness, reduce i…

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

**A:** Security audit logs are retained for 18 months. They remain in hot storage for the first 90 days, then move to cold archive. Notes from the policy: - Customer- or regulation-specific contract terms may require longer retention and take precedence. - Legal holds override retention/deletion rules. - For questions or access: privacy@acmecorp.example or security-eng@acmecorp.example. Sources: - Local …

### privacy-web-question

**Q:** What are today's top technology news headlines?

**A:** I do not have enough information in the provided documents. Note: Web search is disabled, so I could only use the local knowledge base. I may not have enough information to fully answer this question.

