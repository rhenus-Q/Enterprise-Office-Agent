# ADR 007: Deterministic answer provenance, not LLM-generated citations

Status: Accepted

Date: 2026-06-11

## Context

An enterprise document assistant should show where its answers came from —
users need to distinguish "this is from our VPN policy" from "this came off
the public web." The obvious approach, asking the generation LLM to emit
citations, has two well-known failure modes: hallucinated citations (the most
damaging possible failure for a trust feature) and prompt instability (every
prompt change risks shifting answer quality, and this project's development
rules deliberately freeze prompts and model behavior).

The graph already carries everything needed: the final `documents` list holds
the filtered local chunks plus at most one vetted web supplement, each with
metadata.

## Decision

Provenance is **pure post-run formatting of `Document` metadata**, done in
`main.py` after the graph finishes — the LLM is never asked to cite.
`format_sources(result["documents"])` builds a `Sources:` section:

- **Local corpus documents** are cited by their ingestion metadata: the H1
  `title` (e.g. "AcmeCorp VPN Access Policy"), falling back to the `source`
  path, then to the safe label `Local corpus document`.
- **The web supplement** is detected by the shared `WEB_SEARCH_SOURCE`
  metadata marker (a constant in `graph/consts.py` used by both the
  `websearch` node that writes it and `main.py` that reads it, so they cannot
  drift) and cited as `Web search: "<query>"` using the `search_query` the
  node recorded — falling back to `Web search result`.
- Duplicate lines are collapsed order-preservingly (several chunks of one
  policy cite it once); document *content* is never exposed; an empty
  document list produces no section at all, so there is never a misleading
  empty "Sources" header.
- Ordering: answer → stop-reason caveat → sources. The caveat sits directly
  under the answer so a sources list next to an error never implies the
  answer was verified.

## Consequences

- Citations cannot be hallucinated: every line corresponds to a `Document`
  that actually sat in the final context.
- Zero prompt, chain, or model changes — generation behavior is bit-for-bit
  identical with and without the feature.
- Fully deterministic and unit-testable: the provenance tests assert exact
  output strings, and the eval harness checks local-vs-web source usage per
  question.
- The ingestion pipeline (ADR 008) only had to guarantee metadata
  (`source`, `title`, `source_type`, `document_category`) survives chunking.

## Trade-offs

- **This is final-answer provenance, not inline citations.** The section says
  *which* sources fed the context, not *which sentence* came from *which*
  source. Claim-level attribution would require either LLM-generated markers
  (reintroducing hallucination risk) or span-matching machinery — both out of
  scope for the first version.
- Listing is by presence in the final context, not by proven influence: a
  relevant-but-unused chunk is still cited. Conservative over-citation was
  chosen over under-citation.
- On a `generation_error` stop, sources of the attempted context are still
  shown next to the placeholder answer; the caveat-first ordering carries the
  warning.

## Alternatives considered

- **LLM-generated citations in the answer**: rejected — hallucinated
  citations are worse than none, and verification would need yet another
  grader pass.
- **Inline claim-level citations via post-hoc span matching**: deferred —
  significant machinery (sentence alignment, thresholds) for a single-turn
  CLI; the deterministic section delivers most of the trust value first.
- **Showing chunk text or snippets**: rejected — exposes document content in
  output (a leak surface in shared terminals/logs) and bloats the answer.
- **Putting sources into graph state during the run**: rejected — provenance
  is presentation, and the project's design grammar keeps user-facing
  formatting in `main.py`, leaving orchestration output machine-readable.
