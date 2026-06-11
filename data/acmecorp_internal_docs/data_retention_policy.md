# AcmeCorp Data Retention Policy

- **Document ID:** CMP-POL-005
- **Version:** 3.0
- **Effective date:** 2025-12-01
- **Policy owner:** Compliance & Legal (privacy@acmecorp.example)
- **Applies to:** All systems and teams that store company or customer data

## 1. Purpose and scope

This policy defines how long AcmeCorp retains each category of data, when
data must be deleted, and how legal holds work. It exists to meet
contractual, regulatory, and security obligations while minimizing the data
we keep.

## 2. Retention schedule

| Data category | Retention period | Notes |
|---|---|---|
| Security audit logs | **18 months** | Hot storage 90 days, then cold archive |
| Application logs | **30 days** | Production log platform default |
| Financial records | **7 years** | Tax and audit requirements |
| HR / employment records | **6 years after employment ends** | |
| Email and chat messages | **24 months** | Auto-deleted afterwards |
| System backups | **35 days** rolling | Encrypted at rest |
| Customer data | **Per contract**, plus **90 days** after contract termination | Then permanently deleted |

Where regulations in a customer's jurisdiction require longer retention,
the contract-specific schedule takes precedence and is recorded in the
data-processing register.

## 3. Deletion process

- Automated deletion jobs run **quarterly** against each retention class;
  data-owning teams confirm completion in the compliance tracker.
- Deletion must be irreversible (cryptographic erasure or hard delete),
  including replicas and derived datasets.
- Backups age out naturally through the 35-day rolling window; no manual
  deletion from backups is required unless under a verified erasure request.

## 4. Legal hold

When Legal issues a hold notice, **the hold overrides every retention and
deletion rule in this policy** for the named data until the hold is lifted
in writing. Deleting data under legal hold is a serious policy violation.
During security incidents, evidence preservation requests from the Incident
Commander are treated as temporary holds (see ITSEC-PLB-002).

## 5. Exceptions

- Retention exceptions (keeping data longer or shorter than scheduled)
  require written approval from Compliance & Legal.
- Exceptions are logged in the data-processing register and reviewed
  annually.

## 6. Responsibilities

- **Data-owning teams** implement and verify retention rules per system.
- **Compliance & Legal** maintains the schedule and the register.
- **Security Engineering** owns the audit-log pipeline and its archive.

## 7. Contacts

| Need | Contact |
|---|---|
| Retention questions, exceptions | privacy@acmecorp.example |
| Legal hold status | legal@acmecorp.example |
| Audit-log access requests | security-eng@acmecorp.example |
