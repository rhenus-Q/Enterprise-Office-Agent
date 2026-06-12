# Eval results

- Generated: 2026-06-12 14:21 UTC
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
| source_titles matches | 5 / 5 |
| min_local_sources matches | 4 / 4 |
| web_search_count matches | 9 / 9 |
| policy_applied matches | 9 / 9 |
| Average retries | 1.42 |
| Average tracked LLM calls | 2.88 |
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
| web-nist-guidelines | web_fallback | PASS | — | 4 | 19 | 4 | — |
| insuf-parental-leave | insufficient_context | PASS | web_search_disabled | 1 | 0 | 0 | — |
| insuf-wifi-password | insufficient_context | PASS | web_search_disabled | 1 | 0 | 0 | — |
| insuf-ai-tools | insufficient_context | PASS | web_search_disabled | 1 | 0 | 0 | — |
| privacy-local-answer | privacy_mode | PASS | — | 1 | 1 | 0 | — |
| privacy-web-question | privacy_mode | PASS | web_search_disabled | 1 | 0 | 0 | — |
| multi-onboarding-vpn | multi_document | PASS | — | 1 | 1 | 0 | — |
| multi-sev1-after-hours | multi_document | PASS | — | 1 | 1 | 0 | — |
| multi-legal-hold-audit-logs | multi_document | PASS | — | 1 | 1 | 0 | — |
| multi-shared-vpn-credentials | multi_document | PASS | — | 3 | 3 | 0 | — |
| policy-conservative-stays-local | policy_fallback | PASS | — | 1 | 1 | 0 | — |
| policy-aggressive-escalates | policy_fallback | PASS | — | 1 | 4 | 1 | — |
| policy-conservative-web-when-empty | policy_fallback | PASS | max_retries_not_grounded | 5 | 8 | 1 | — |
| policy-disabled-declines-honestly | policy_fallback | PASS | — | 1 | 0 | 0 | — |
| policy-disabled-router-web-still-works | policy_fallback | PASS | — | 1 | 4 | 1 | — |

## Answers (truncated)

### local-vpn-access

**Q:** How do I request VPN access?

**A:** Short answer — submit the VPN Access Request form in the IT Service Portal and get your manager to approve it. Details: - Open the IT Service Portal: ServiceNow → Service Catalog → Network Access and submit the "VPN Access Request" form. - Your direct manager must approve the request in the portal. Requests without manager approval are automatically rejected after 5 business days. - After approval…

### local-expense-approval

**Q:** What expenses require manager approval?

**A:** Direct manager approval is required for any single-item expense of $100.01–$1,000. Related notes from the policy: - Expenses over $500 should be approved before purchase whenever practical (do not split purchases to avoid thresholds). - Manager approval is also required to book premium-economy for flights longer than 6 hours. If you need the exact policy text or other approval levels (director / V…

### local-sev1-escalation

**Q:** When should a security incident be escalated to Sev-1?

**A:** Escalate immediately to Sev‑1 if any of the following is true: - Confirmed unauthorized access to customer data or employee PII. - Ransomware or destructive malware on any production system. - An active attacker with privileged (admin/root) access. - A customer‑facing outage caused by a security event that lasts >30 minutes or affects >10% of customers. - Any incident likely to trigger regulatory …

### local-after-hours-paging

**Q:** Who gets paged for after-hours production incidents?

**A:** - Initial page: the primary on-call engineer for the service that owns the failing component (routed via PagerDuty service mapping). - If the owning service is unclear: the SRE platform on-call is paged and will re-route the incident. - Escalation (if no ack): secondary on-call is paged after 10 minutes, then the engineering manager after a further 10 minutes; for Sev‑1s unacknowledged for 30 minu…

### local-audit-log-retention

**Q:** How long are security audit logs retained?

**A:** Security audit logs are retained for 18 months. They remain in hot storage for the first 90 days, then move to a cold archive. Notes from the policy: - Customer- or jurisdiction-specific contractual requirements can override this schedule (recorded in the data‑processing register). - Retention exceptions require written approval from Compliance & Legal; legal holds override retention rules. Contac…

### web-python-version

**Q:** What is the latest stable version of Python right now?

**A:** According to the provided documents, the latest stable version is Python 3.14.6. Sources: - Web search: Python Release Python 3.14.0 — https://www.python.org/downloads/release/python-3140 - Web search: Python Release Python 3.12.0 — https://www.python.org/downloads/release/python-3120 - Web search: Download Python - Python.org — https://www.python.org/downloads

### web-msft-ceo

**Q:** Who is the current CEO of Microsoft?

**A:** According to the provided documents, Satya Nadella is the current Chief Executive Officer of Microsoft (CEO since February 2014). Sources: - Web search: Why Does Microsoft Now Have a New, Extra CEO? — https://technologymagazine.com/news/why-is-microsoft-ceo-satya-nadella-shifting-his-focus-to-ai - Web search: Satya Nadella - Wikipedia — https://en.wikipedia.org/wiki/Satya_Nadella - Web search: Sat…

### web-cyber-news

**Q:** What are the biggest cybersecurity news stories this week?

**A:** Based on the provided documents, the biggest cybersecurity stories this week are: - Mini Shai-Hulud campaign resurfaces — a new wave of supply‑chain poisoning in the wild, underscoring that software supply‑chain attacks are rapidly becoming a recurring threat. - Akamai SOTI report: "AI‑Empowered Botnets and API Visibility Gaps" — highlights increasingly sophisticated, persistent DDoS attacks (incl…

### web-sre-salary

**Q:** What is the average salary for a site reliability engineer in the United States in 2026?

**A:** The provided documents give three different average annual salaries for a U.S. Site Reliability Engineer: - $157,916 (Indeed; 2.6k salaries from job postings) - $132,583 (explicitly dated “As of Jun 11, 2026”) - $171,745 (source not specified in the excerpt) I do not have enough information in the provided documents to determine a single definitive average for 2026. The only entry explicitly dated…

### web-nist-guidelines

**Q:** What does the latest NIST incident response guidance recommend?

**A:** Based on the provided documents, NIST SP 800-61 Revision 3 recommends: - Align incident response with NIST CSF 2.0 by mapping guidance to the six CSF functions: Govern, Identify, Protect, Detect, Respond, and Recover. - Incorporate incident response recommendations and considerations throughout an organization’s broader cybersecurity risk‑management activities (not just as a standalone IR function…

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

**A:** Security audit logs are retained for 18 months. They remain in hot storage for 90 days, then move to cold archive. If a customer jurisdiction or contract requires longer retention, the contract-specific schedule takes precedence and is recorded in the data‑processing register. Retention exceptions require written approval from Compliance & Legal. Contacts: - Retention questions / exceptions: priva…

### privacy-web-question

**Q:** What are today's top technology news headlines?

**A:** I do not have enough information in the provided documents. Note: Web search is disabled, so I could only use the local knowledge base. I may not have enough information to fully answer this question.

### multi-onboarding-vpn

**Q:** As a new employee, how do I get VPN access and what do I need to set up before I can use it?

**A:** Short answer — submit the VPN request in ServiceNow and complete Okta MFA first. Steps and pre-requisites from the onboarding docs: What to do - Submit the "VPN Access Request" form in the IT Service Portal (ServiceNow → Service Catalog → Network Access). - Do NOT submit a duplicate request if your onboarding ticket already includes VPN access. - Your direct manager must approve the request in the…

### multi-sev1-after-hours

**Q:** A Sev-1 security incident starts at 2 AM - who gets paged and how quickly must they acknowledge?

**A:** Immediate action: - Page the Incident Commander (IC) via the PagerDuty service "sec-ic". The IC must acknowledge within 15 minutes. Operational paging (after-hours / production context): - The primary on-call engineer for the service that owns the failing component is paged per the PagerDuty service mapping (if the owning service is unclear, the SRE platform on-call is paged to re-route). The prim…

### multi-legal-hold-audit-logs

**Q:** During a security incident, what does the Incident Response Playbook say about evidence preservation or Incident Commander holds, and what does the Data Retention Policy say about normal audit-log ret…

**A:** - Incident Response Playbook: Preserve evidence before remediation — snapshot affected systems and export relevant logs. Evidence retention follows the Data Retention Policy (CMP‑POL‑005), and a legal hold overrides normal deletion (Legal is notified within 1 hour and owns regulatory/notification decisions). - Data Retention Policy (normal audit‑log retention): Security audit logs are retained 18 …

### multi-shared-vpn-credentials

**Q:** Using AcmeCorp's VPN Access Policy and Security Incident Response Playbook, what happens when an employee shares VPN credentials or MFA devices, and should the incident be reported through PagerDuty s…

**A:** - Per the VPN Access Policy (Usage rules): sharing VPN credentials or MFA devices is prohibited and "treated as a security incident" (see ITSEC-PLB-002). - The Security Incident Response Playbook (ITSEC-PLB-002) governs how such incidents are classified, escalated, and responded to. The provided documents do not state whether the incident should be reported via PagerDuty "sec-ir" or via the #secur…

### policy-conservative-stays-local

**Q:** What security training must new employees complete?

**A:** New hires must complete the mandatory security awareness training within 7 days of their start date (it’s assigned automatically in the learning portal). Access to production systems is blocked until this training is finished. (Additionally, on day one you must activate your Okta account and enroll in Okta Verify MFA before internal systems/VPN will permit access.) Sources: - Local corpus: AcmeCor…

### policy-aggressive-escalates

**Q:** What security training must new employees complete?

**A:** According to the provided onboarding docs: - Complete the mandatory security awareness training within 7 days of your start date (it’s assigned automatically in the learning portal). Access to production systems is blocked until this is complete. - In addition, onboarding includes role‑targeted security training within the first 30 days (for example, secure coding training for development teams). …

### policy-conservative-web-when-empty

**Q:** What is AcmeCorp's pet insurance benefit?

**A:** Based only on the provided documents, AcmeCorp’s pet insurance benefit includes: - Coverage options for accidents, illnesses, and wellness care. - Up to a $7,500 maximum annual benefit. - Premiums starting at $14 per paycheck. - Policy may provide cash back for certain medical expenses. - A lifetime 5% discount on pet insurance (cats and dogs only) through Pets Best. - Plan details (including excl…

### policy-disabled-declines-honestly

**Q:** What is AcmeCorp's pet insurance benefit?

**A:** I do not have enough information in the provided documents.

### policy-disabled-router-web-still-works

**Q:** Who is the current CEO of Microsoft?

**A:** According to the provided documents, Satya Nadella is the current Chief Executive Officer of Microsoft (CEO since February 2014). Sources: - Web search: Why Does Microsoft Now Have a New, Extra CEO? — https://technologymagazine.com/news/why-is-microsoft-ceo-satya-nadella-shifting-his-focus-to-ai - Web search: Satya Nadella - Wikipedia — https://en.wikipedia.org/wiki/Satya_Nadella - Web search: Sat…

