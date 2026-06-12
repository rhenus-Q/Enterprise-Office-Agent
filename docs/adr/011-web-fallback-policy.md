# ADR 011: Configurable web-fallback policy (conservative by default)

Status: Accepted (amended 2026-06-11: policy resolved into per-run state, see Update below)

Date: 2026-06-11

## Context

The original CRAG-style behavior was maximally eager about web fallback: if
*any* retrieved chunk was graded irrelevant, the run detoured through Tavily
before generating — even when relevant local policy content was already in
hand. The baseline eval made the cost concrete: `local-sev1-escalation`, a
pure incident-playbook question, answered correctly from the corpus but still
spent one web search and three web-result grading calls because one of the
three retrieved chunks was off-topic.

For an enterprise internal-document assistant this default is backwards. The
local corpus is the curated, trusted source; the web is an untrusted
supplement (ADR 004, ADR 010). Every unnecessary fallback transmits internal
question text to an external service, adds cost and latency, and pulls
untrusted content into the generation context. Eagerness is also not free
insurance: the answer-usefulness gate already escalates to the web *after* a
local answer proves insufficient, so generating locally first loses nothing
except one speculative search.

## Decision

A `WEB_FALLBACK_POLICY` environment variable (parsed in `graph/config.py`,
invalid values fall back to the default) with three values, applied in
`decide_to_generate` after document grading:

- **`conservative` (default)** — generate when at least one relevant local
  document remains; web fallback only when zero relevant documents survive
  grading. The not-useful retry path is unchanged: a grounded local answer
  that fails the usefulness gate may still trigger a rewritten web search.
- **`aggressive`** — the legacy CRAG behavior: any irrelevant retrieved
  document triggers web fallback before generation. Kept for comparability
  with the original pattern and for corpora known to be sparse, where partial
  retrieval usually does signal missing coverage.
- **`disabled`** — local retrieval paths never escalate to the web. This
  deliberately uses the safer enterprise interpretation: it blocks not only
  the grading-time fallback but also the **post-generation not-useful web
  retry on local-only runs** (detected by `web_search_count == 0`), which
  ends through a dedicated `web_fallback_disabled` stop reason and caveat.
  Router-initiated web searches — and their own not-useful re-searches — stay
  allowed: they were never a local-path fallback. With no relevant local
  documents, the run declines honestly via the insufficient-context bypass
  (ADR-010-adjacent behavior in `grade_generation`).

> **Update (2026-06-11, engine API phase):** the policy is no longer read
> from `os.environ` at decision time. `graph/engine.py` resolves the
> effective policy once at run start — an explicit `AnswerOptions` value
> wins, otherwise the `WEB_FALLBACK_POLICY` env var — normalizes it
> (`graph.config.normalize_web_fallback_policy`, invalid → `conservative`),
> and seeds it into `GraphState["web_fallback_policy"]`. `decide_to_generate`
> and `grade_generation` read the policy from state, falling back to the
> env helper only for legacy callers that seed state without the field.
> This supersedes the "No new graph state was needed" note below: one state
> field was added so evals, tests, and future workflow callers can vary the
> policy per run without mutating the environment, and so a run's behavior
> cannot change mid-flight if the environment does. Semantics of the three
> policy values, the conservative default, and the privacy-switch override
> are unchanged.

`WEB_FALLBACK_POLICY` is deliberately separate from `WEB_SEARCH_ENABLED`:
the privacy switch decides whether external web search is allowed *at all*
(checked first; `false` guarantees no router LLM call and no Tavily call,
overriding every policy value), while the policy decides *when* the system
chooses fallback within an allowance. Collapsing both into one variable
would force privacy-sensitive deployments to also accept routing changes,
and vice versa.

No new graph state was needed: `decide_to_generate` distinguishes "some
relevant documents remain" from "none remain" by reading the already-filtered
`documents` list.

## Consequences

- Local-corpus questions with partially relevant retrievals now answer
  locally by default: fewer external transmissions of internal question
  text, lower cost/latency, less untrusted content in context.
- The default change is observable in evals: rows like
  `local-sev1-escalation` should now pass with `web_search_count == 0`
  (`evals/results.md` is stale until the next baseline run).
- One new terminal notice node and stop reason (`web_fallback_disabled`)
  follow the ADR 001 recipe, so the blocked-by-policy ending is honest and
  machine-checkable rather than silently reusing the privacy caveat.
- Graceful degradation composes with the policy: a retriever failure still
  degrades to web search under `conservative` (zero docs remain), but under
  `disabled` it declines locally instead — the policy's containment promise
  takes precedence over the degradation path.

## Trade-offs

- **`conservative` can miss useful web augmentation** when local documents
  are partially relevant but incomplete: generation proceeds with what
  survived grading, and the web is consulted only if the usefulness gate
  rejects the result — one extra generation round in that case.
- **`aggressive` improves first-pass coverage** for sparse corpora but
  maximizes privacy/cost/external-dependency exposure — every partially
  irrelevant retrieval ships the question to a third party.
- **`disabled` maximizes containment but increases insufficient-context
  answers and policy caveats** — questions the corpus cannot answer end as
  honest declines rather than web-supplemented answers.
- A third env knob adds configuration surface; mitigated by a safe default,
  case-insensitive parsing, and fallback-to-conservative on invalid values.
- `disabled`'s local-only detection keys on `web_search_count == 0`, which
  conflates "router chose retrieval" with "no search has happened yet" —
  equivalent today, but a future multi-source design would need an explicit
  origin marker.

## Alternatives considered

- **Keeping the aggressive default and documenting it**: rejected — the
  enterprise framing makes local-first the correct default, and the eval
  evidence showed real waste on in-corpus questions.
- **A relevant-document threshold (e.g. fallback if fewer than N relevant)**:
  rejected for now — more tunable but harder to reason about and test; the
  three named policies cover the meaningful operating points.
- **Deciding inside `grade_documents`** (not setting `web_search` at all
  under conservative): rejected — it would overload the grading node with
  routing policy and break the existing degradation contract where
  `web_search=True` also signals retriever failure; the decision belongs in
  the routing function that already owns it.
- **Folding the policy into `WEB_SEARCH_ENABLED` (e.g. a third value)**:
  rejected — the hard privacy guarantee must stay a simple boolean that
  cannot be weakened by a routing-policy typo.
