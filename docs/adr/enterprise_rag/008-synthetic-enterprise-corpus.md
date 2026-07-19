# ADR 008: Synthetic AcmeCorp enterprise corpus

Status: Accepted

Date: 2026-06-11

## Context

The project positions itself as an *enterprise internal-document* Q&A
assistant, and its distinguishing features — privacy mode, provenance,
graceful degradation, honest refusal — only make sense against internal
documents. Yet the original knowledge base was three public LangChain
documentation pages (RAG, vector stores, text splitters). That mismatch
undercut the product story: privacy mode "protecting" public tutorial content
is theater, and "How do text splitters work?" exercises none of the
policy-style retrieval the design targets.

Using real internal documents was never an option: confidential data and
copyrighted policies do not belong in a public repository.

## Decision

Replace the tutorial corpus with a **fictional, synthetic AcmeCorp internal
corpus** under `data/acmecorp_internal_docs/`: six Markdown documents (VPN
access policy, expense reimbursement policy, security incident response
playbook, on-call & escalation policy, data retention policy, employee
onboarding guide). Written for realism, not bulk:

- Each has a document ID, version, effective date, policy owner, sections
  with **specific** rules (approval tiers at $100/$1,000/$5,000, 5-minute
  Sev-1 ack SLA, 18-month audit-log retention, 2-business-day VPN
  provisioning), escalation paths, an exceptions process, and contact tables.
- Documents cross-reference each other (onboarding → VPN policy and on-call
  policy; incident playbook → retention policy's legal hold), so
  multi-document questions retrieve coherently.
- All names and addresses are fictional (`acmecorp.example`); no real company
  data, no copyrighted policy text.

`ingestion.py` loads the local Markdown with plain `pathlib` (dropping the
sunset `WebBaseLoader` dependency), attaches provenance metadata per document
(`source` path, H1 `title`, `source_type: "local_corpus"`,
`document_category`), and rebuilds the Chroma collection **idempotently**:
the existing collection is dropped, then chunks are written with
deterministic ids (`<source>::chunk-<i>`) — re-running never duplicates and
removed files disappear from the index. The question-router prompt's topic
list was updated to the AcmeCorp policy domains accordingly.

## Consequences

- The corpus supports realistic evaluation: the eval harness's local
  questions ("When should a security incident be escalated to Sev-1?") have
  specific, checkable answers, and its fabrication-bait questions (Wi-Fi
  passwords, nonexistent policies) test refusal meaningfully.
- Privacy mode now protects content that *looks like* what it would protect
  in production.
- Provenance citations read like an enterprise tool ("Local corpus: AcmeCorp
  VPN Access Policy").
- Swapping in real documents is the documented path: drop Markdown into the
  folder, optionally extend `DOCUMENT_CATEGORIES`, re-run ingestion.

## Trade-offs

- **It is synthetic, not a production corpus.** Six small, well-structured
  documents do not exercise messy real-world ingestion (PDFs, tables, scans,
  thousands of documents, conflicting versions). The project demonstrates the
  workflow architecture, not corpus-scale engineering, and says so.
- Invented facts must stay internally consistent by authorial discipline;
  there is no source of truth to validate against.
- The idempotent rebuild's tradeoff: a run failing mid-ingestion leaves the
  index empty until re-run — accepted for an offline build script as strictly
  better than the previous silent chunk duplication.
- Changing the router prompt's domain list was a deliberate, reviewed prompt
  change — the single exception to the "prompts frozen" rule, required for
  routing to match the corpus.

## Alternatives considered

- **Keeping the LangChain docs corpus**: rejected — product-story mismatch;
  every enterprise feature demoed against public tutorials.
- **A real public-policy corpus** (e.g. government documents): rejected —
  legally safe but still not *internal*-shaped; no escalation paths, ticket
  queues, or org-specific thresholds.
- **LLM-bulk-generating dozens of documents**: rejected — volume without
  curation produces internally inconsistent facts, which silently corrupts
  grounding evaluation.
- **A database or hosted vector store for the corpus**: rejected — over-
  engineering; local Markdown + Chroma matches the project's scale and keeps
  setup to one command.
