# Phase 3A / 3B Eval v2 Plan — Multi-Document and Fallback-Policy Eval Rows

Status: Planned (not implemented)

Date: 2026-06-12

Scope: **planning only.** This document proposes new eval rows and the minimal
harness/schema changes needed to support them. No eval, graph, corpus, prompt,
or test files are modified by this phase's planning step. The full eval
refresh (real API run) remains a separately approved step.

---

## 1. Current eval system summary

Inspected on 2026-06-12: `evals/README.md`, `evals/questions.jsonl`,
`evals/run_eval.py`, `tests/evals/test_eval_harness.py`, plus the graph
modules the checks depend on (`graph/engine.py`, `graph/config.py`,
`graph/formatting.py`, `graph/graph.py`, `graph/consts.py`) and all six corpus
documents.

### 1.1 Current row schema

Required fields: `id`, `category`, `question`, `web_search_enabled`,
`expected_behavior`.

Optional check fields (`null`/absent = not checked):

| Field | Type | Semantics |
|---|---|---|
| `expected_stop_reason` | string \| list \| null | Final `stop_reason` must be in the allowed set (`""` = clean finish) |
| `expected_source_type` | `local_corpus` \| `web` \| `none` \| null | At least one local doc used / web supplement used / no documents at all |
| `expected_contains` | list of strings | **All** substrings must appear in the formatted answer (case-insensitive, NFKC + dash + whitespace normalized) |
| `web_fallback_policy` | `conservative` \| `aggressive` \| `disabled` \| null | Per-row policy override, passed to `AnswerOptions` |
| `notes` | string | Rationale, not checked |

Important existing capability: **per-row `web_fallback_policy` is already
fully plumbed** — `validate_dataset()` validates it
(`evals/run_eval.py:154-158`), the runner passes it into
`AnswerOptions(web_fallback_policy=row.get("web_fallback_policy"))`
(`evals/run_eval.py:377`), and `tests/evals/test_eval_harness.py` covers the
validation (`test_validate_accepts_optional_web_fallback_policy`). No shipped
row uses it yet, and **nothing checks that the policy actually changed
behavior**.

### 1.2 Current categories

`CATEGORIES` is a fixed tuple in `run_eval.py:46`:
`local_corpus` (5 rows), `web_fallback` (5), `insufficient_context` (3),
`privacy_mode` (2) — 15 rows total. The category counts and total are
hard-asserted in `tests/evals/test_eval_harness.py`
(`test_shipped_dataset_is_valid_with_expected_category_mix`), and
`compute_metrics()` / `render_markdown()` hard-code the four category names.

### 1.3 Current deterministic checks (`evaluate_row`)

- `stop_reason` — exact membership in the allowed list.
- `source_type` — boolean derived from `Document` metadata
  (`source == WEB_SEARCH_SOURCE` marks the web supplement; anything else is
  local).
- `expected_contains` — all substrings present after normalization.
- `privacy_no_web_search` — automatic for every `web_search_enabled=false`
  row: `web_search_count == 0`.
- Category rules: `web_fallback` rows must have used a web source **and**
  `web_search_count >= 1`; `insufficient_context` rows must decline
  (`"do not have enough information"`) or end with a non-empty `stop_reason`.

### 1.4 Current result format

`results.md`: a metrics table (overall + per-category pass counts, per-check
match counts, average retries, average **tracked** LLM calls, total web
searches), a per-question table (id, category, pass/fail, stop_reason,
counters, failed checks), and truncated answers per row.

### 1.5 What the current eval proves

- Single-document corpus questions answer cleanly from local sources with the
  expected key fact present.
- Out-of-corpus questions route to, and actually use, web search.
- Unanswerable questions (with web disabled) decline instead of fabricating.
- Privacy mode performs zero web searches, both for answerable and
  web-needing questions.

### 1.6 What it does not yet prove

- **Multi-document synthesis.** Every `local_corpus` row is answerable from a
  single document; `expected_source_type: "local_corpus"` is satisfied by
  *one* local source. No check can express "at least two distinct local
  documents were cited."
- **Fallback-policy behavior.** No row sets `web_fallback_policy`; there is no
  check on `web_search_count` as an expectation field (only the automatic
  privacy zero-check), so conservative vs. aggressive vs. disabled behavior is
  covered only by mocked tests (`tests/graph/test_web_fallback_policy.py`),
  never by a behavioral eval against the real graph.
- The effective policy echoed by the engine
  (`AnswerResult.web_fallback_policy` / `raw_state["web_fallback_policy"]`) is
  never asserted per row.

### 1.7 Does the README/structure claim untested cross-document capability?

**Yes.** `README.md` ("The synthetic AcmeCorp corpus" section) claims:
*"documents cross-reference each other so multi-document questions retrieve
coherently"* — and ADR 008 documents the cross-references as a design goal.
The corpus genuinely contains the cross-references (e.g. the VPN policy points
at the onboarding guide and the incident playbook; the playbook points at the
retention policy and the on-call policy), but **no eval row exercises or
verifies a multi-document answer**. Phase 3A closes exactly this gap.

---

## 2. Phase 3A: Multi-document eval rows

### 2.1 Design constraints discovered during inspection

- **Retrieval is top-3** (`ingestion.py`: `as_retriever(search_kwargs={"k": 3})`).
  A multi-document answer requires chunks from *both* documents to land in the
  top 3 — questions must be phrased so both documents score highly. The corpus
  cross-references help (shared vocabulary), but this is the main flakiness
  risk for 3A rows.
- **Local source titles are deterministic**: `ingestion.py` records each
  document's H1 heading as `metadata["title"]`, which survives chunking and
  feeds `formatting.source_lines()`. Asserting on titles is therefore a
  metadata check, not an LLM-wording check — the strongest available
  multi-document signal.
- **The multi-document proof should live in provenance, not prose.**
  `expected_contains` anchors should stay minimal (1–2 robust facts); the
  claim "this answer used two documents" is proven by the cited source titles.
- All 3A rows pin `web_fallback_policy: "conservative"` so the row's behavior
  does not depend on the runner's environment, and use
  `web_search_enabled: true` with `expected_web_search_count: 0` — proving the
  corpus alone carried the answer in normal (non-privacy) mode.

One suggested theme was **rejected as not genuinely multi-document**: *expense
approval + reimbursement timing* — both live in
`expense_reimbursement_policy.md` (§2 approval thresholds, §7 payment
timeline). A row built on it would pass with a single source and prove
nothing new.

### 2.2 Proposed rows (4)

Exact ingested titles used below:
`AcmeCorp VPN Access Policy`, `AcmeCorp Employee Onboarding Guide`,
`AcmeCorp Security Incident Response Playbook`,
`AcmeCorp On-Call and Escalation Policy`, `AcmeCorp Data Retention Policy`.

#### Row 3A-1: `multi-onboarding-vpn`

- **question:** "As a new employee, how do I get VPN access and what do I need to set up before I can use it?"
- **category:** `multi_document`
- **expected source documents:** `employee_onboarding_guide.md` + `vpn_policy.md`
- **expected_contains:** `["MFA"]`
- **expected_source_titles:** `["AcmeCorp Employee Onboarding Guide", "AcmeCorp VPN Access Policy"]`
- **expected_min_local_sources:** 2
- **expected_web_search_count:** 0
- **expected_stop_reason:** `""`
- **Why truly multi-document:** the onboarding guide says VPN access is bundled
  into the onboarding ticket (no separate request) and Okta Verify MFA is
  enrolled on day one; the VPN policy says MFA enrollment is required before
  first VPN sign-in and provisioning takes 2 business days. The complete
  "how do I get it *and* what must I set up first" answer needs both; each
  document explicitly cross-references the other (HR-GDE-001 ↔ ITSEC-POL-004),
  so retrieval coherence is maximally favorable.

#### Row 3A-2: `multi-sev1-after-hours`

- **question:** "A Sev-1 security incident starts at 2 AM — who gets paged and how quickly must they acknowledge?"
- **category:** `multi_document`
- **expected source documents:** `incident_response_playbook.md` + `on_call_escalation_policy.md`
- **expected_contains:** `["primary"]`
- **expected_source_titles:** `["AcmeCorp Security Incident Response Playbook", "AcmeCorp On-Call and Escalation Policy"]`
- **expected_min_local_sources:** 2
- **expected_web_search_count:** 0
- **expected_stop_reason:** `""`
- **Why truly multi-document:** the playbook owns the Sev-1 path (page the
  Incident Commander via "sec-ic", ack within 15 minutes); the on-call policy
  owns after-hours paging (primary on-call of the owning service, Sev-1 ack
  within 5 minutes, escalation chain). Neither document alone answers both
  halves; the two documents cross-reference each other in their scope sections
  (ITSEC-PLB-002 ↔ OPS-POL-003).

#### Row 3A-3: `multi-legal-hold-audit-logs`

- **question:** "During a security incident, can audit logs that are due for deletion be deleted, and how long are they normally retained?"
- **category:** `multi_document`
- **expected source documents:** `data_retention_policy.md` + `incident_response_playbook.md`
- **expected_contains:** `["18 months", "legal hold"]`
- **expected_source_titles:** `["AcmeCorp Data Retention Policy", "AcmeCorp Security Incident Response Playbook"]`
- **expected_min_local_sources:** 2
- **expected_web_search_count:** 0
- **expected_stop_reason:** `""`
- **Why truly multi-document:** the retention policy holds the schedule
  (audit logs 18 months) and the legal-hold override rule; the incident
  playbook holds the incident-time evidence-preservation step ("legal hold
  overrides normal deletion", IC preservation requests are temporary holds).
  The "can they be deleted *during an incident*" half requires the playbook;
  the "how long normally" half requires the retention policy. Explicit
  cross-references both ways (CMP-POL-005 ↔ ITSEC-PLB-002).

#### Row 3A-4: `multi-shared-vpn-credentials`

- **question:** "What happens if an employee shares their VPN credentials, and how should that be reported?"
- **category:** `multi_document`
- **expected source documents:** `vpn_policy.md` + `incident_response_playbook.md`
- **expected_contains:** `["security incident"]`
- **expected_source_titles:** `["AcmeCorp VPN Access Policy", "AcmeCorp Security Incident Response Playbook"]`
- **expected_min_local_sources:** 2
- **expected_web_search_count:** 0
- **expected_stop_reason:** `""`
- **Why truly multi-document:** the VPN policy states the rule (credential
  sharing is prohibited and *treated as a security incident*, referencing
  ITSEC-PLB-002) but not the handling; the playbook states how incidents are
  reported and classified (PagerDuty "sec-ir" / #security-reports, credential
  compromise is a Sev-2 example). The "what happens" half is in one document,
  the "how to report" half in the other.

A fifth candidate (`multi-new-engineer-oncall`: "When can a newly hired
engineer join the on-call rotation?", onboarding guide + on-call policy) was
considered and **deferred**: both documents independently state the
3-months-plus-shadow-rotation rule, so a single source can fully answer it —
the row would prove retrieval overlap, not synthesis. It can be added later if
a fifth row is wanted.

### 2.3 Known risk for 3A rows

With `k=3`, a run can retrieve three chunks from one document, answer
correctly from it, and pass the usefulness gate — failing only the new
`expected_source_titles` / `expected_min_local_sources` checks. That is a
*true* finding (the claimed multi-document capability did not manifest), not a
harness bug — but it may also just reflect top-3 ranking on that day's
embeddings. The plan accepts this: rows were chosen where both documents share
distinctive vocabulary and cross-reference each other, and the first approved
full-eval run should be treated as calibration (tune question wording, not the
checks, if a row fails on provenance while the answer is correct). Do **not**
raise `k` to make rows pass — that would change RAG behavior.

---

## 3. Phase 3B: Fallback-policy eval rows

### 3.1 Current policy support recap

- `conservative` (default): generate from remaining relevant local chunks;
  web fallback only when zero relevant chunks survive grading.
- `aggressive`: any irrelevant retrieved chunk triggers web fallback before
  generation.
- `disabled`: local retrieval paths never escalate to the web (including the
  post-generation not-useful retry on local-only runs →
  `web_fallback_disabled` stop reason); **router-chosen** web searches still
  work when web search is enabled; with zero relevant local docs the run
  produces the deterministic insufficient-context decline.
- The env var is only the default; the engine resolves the per-run policy into
  state, and the harness already passes per-row `web_fallback_policy` through
  `AnswerOptions`.

The most deterministic discriminating signals available — none of which depend
on LLM wording — are `web_search_count` (zero vs. ≥ 1), the deterministic
insufficient-context decline text (produced *without* an LLM call), source
provenance, and `stop_reason`.

### 3.2 Proposed rows (5, category `policy_fallback`)

All rows: `web_search_enabled: true` (policy behavior is only meaningful when
web search is allowed at all).

#### Row 3B-1: `policy-conservative-stays-local`

- **question:** "What security training must new employees complete?"
- **web_fallback_policy:** `conservative`
- **expected_stop_reason:** `""`
- **expected_web_search_count:** 0
- **expected_contains:** `["7 days"]`
- **expected sources:** local corpus only (`expected_source_type: "local_corpus"`, `expected_source_titles: ["AcmeCorp Employee Onboarding Guide"]`)
- **Why it distinguishes:** the onboarding guide answers this (mandatory
  security awareness training within 7 days), but top-3 retrieval over a
  six-document corpus plausibly includes a chunk from a security document that
  grading drops. Conservative must still stay local (relevant chunks remain →
  generate). Paired with 3B-2 below, the *same question* under `aggressive`
  must search the web — same input, different policy, observably different
  `web_search_count`.

#### Row 3B-2: `policy-aggressive-escalates`

- **question:** "What security training must new employees complete?" (identical to 3B-1)
- **web_fallback_policy:** `aggressive`
- **expected_stop_reason:** `null` (web result quality varies; not pinned)
- **expected_web_search_count:** `{"min": 1}`
- **expected_contains:** `[]`
- **expected sources:** web supplement used (`expected_source_type: "web"`; local chunks may also legitimately remain in context)
- **Why it distinguishes:** with any retrieved chunk graded irrelevant,
  `aggressive` must detour through Tavily before generation while 3B-1 stayed
  at zero searches. This is the *only* pair in the dataset where the question
  is held constant and only the policy changes — the cleanest possible
  demonstration that the policy knob does something.

#### Row 3B-3: `policy-conservative-web-when-empty`

- **question:** "What is AcmeCorp's pet insurance benefit?"
- **web_fallback_policy:** `conservative`
- **expected_stop_reason:** `null` (not pinned — web results for a fictional company vary)
- **expected_web_search_count:** `{"min": 1}`
- **expected_contains:** `[]`
- **expected sources:** not pinned (`expected_source_type: null` — graded web results for a fictional benefit may all be dropped)
- **Why it distinguishes:** an HR-flavored question the router sends to
  retrieval (like the existing `insuf-*` rows) with no covering document:
  grading drops everything, and conservative's defining promise is that it
  *does* fall back to the web when nothing relevant remains. The hard check is
  `web_search_count >= 1` — the searched-at-all signal — contrasting directly
  with 3B-4.

#### Row 3B-4: `policy-disabled-declines-honestly`

- **question:** "What is AcmeCorp's pet insurance benefit?" (identical to 3B-3)
- **web_fallback_policy:** `disabled`
- **expected_stop_reason:** `""`
- **expected_web_search_count:** 0
- **expected_contains:** `["do not have enough information"]`
- **expected sources:** none (`expected_source_type: "none"`)
- **Why it distinguishes:** same question, policy flipped to `disabled`, web
  search still *enabled*: zero relevant local docs must now produce the
  deterministic insufficient-context decline (generated without an LLM call —
  the strongest deterministic signal in the system) with zero web searches and
  no sources, instead of 3B-3's web detour. This proves `disabled` ≠
  `conservative` even though both "prefer local."

#### Row 3B-5: `policy-disabled-router-web-still-works`

- **question:** "Who is the current CEO of Microsoft?"
- **web_fallback_policy:** `disabled`
- **expected_stop_reason:** `null`
- **expected_web_search_count:** `{"min": 1}`
- **expected_contains:** `[]`
- **expected sources:** web (`expected_source_type: "web"`)
- **Why it distinguishes:** the documented `disabled` semantics block only
  *retrieval-triggered* fallback; router-chosen web searches remain allowed
  when web search is enabled. Without this row, `disabled` would be
  indistinguishable from privacy mode in the eval — this is the row that
  proves the policy and the privacy switch are different controls.

Additionally, an **automatic check** (no schema field needed) applies to every
row that sets `web_fallback_policy`: the run's effective policy
(`raw_state["web_fallback_policy"]`, exposed via `summarize_result`) must
equal the row's value — proving the per-row override actually reached the
graph, not just the validator.

### 3.3 Determinism honesty note

3B-2 (`aggressive`) is the least deterministic row: it only diverges from
conservative when grading yields a *mixed* relevance outcome, which is a model
judgment. If a calibration run shows all three retrieved chunks graded
relevant (aggressive then behaves like conservative and the row fails), the
fix is to reword the question toward a more mixed retrieval — never to weaken
the check or touch the grader. Rows 3B-3/3B-4/3B-5 rest on fully deterministic
machinery (empty-context decline, zero-search counters, router-vs-retrieval
split).

---

## 4. Eval harness changes likely needed

### 4.1 Can `questions.jsonl` carry the new rows as-is?

Partially. `web_fallback_policy` already validates and flows through. But:

- The new categories (`multi_document`, `policy_fallback`) would be rejected
  by `validate_dataset` (fixed `CATEGORIES` tuple) and are invisible to
  `compute_metrics` / `render_markdown`.
- There is no way to express "two distinct local sources", "these exact local
  titles", or "this many web searches" — the load-bearing checks of both
  phases.

So `evals/run_eval.py` needs minimal schema support.

### 4.2 Field-by-field decision

| Candidate field | Decision | Reason |
|---|---|---|
| `expected_source_titles` | **Add** (list of strings; every listed title must appear among the distinct local-corpus titles of the final documents) | The multi-document proof. Pure metadata (H1 titles recorded by ingestion) — zero LLM-wording fragility. |
| `expected_min_local_sources` | **Add** (int; count of distinct local titles ≥ N) | Robust companion to titles: survives a future title edit, and `>= 2` is the literal definition of "multi-document". Cheap once title collection exists. |
| `expected_web_search_count` | **Add** (int for exact match, or `{"min": n}` / `{"max": n}` object) | The policy discriminator. Exact `0` proves "never searched"; `{"min": 1}` proves "escalated" without over-pinning a count that legitimately varies with retries. |
| `expected_web_fallback_policy` | **Don't add as a field** — implement as an automatic check when `web_fallback_policy` is set | A separate field could silently disagree with the override; deriving the assertion from the override itself can't drift. |
| `expected_all_contains` | **Don't add** | Redundant: `expected_contains` already has ALL semantics. |
| `expected_any_contains` | **Don't add now** | No proposed row needs OR semantics; the insufficient-context category rule already tolerates phrasing variants. Add only when a concrete row demands it. |
| `expected_not_contains` | **Don't add now** | Every "must not" in 3A/3B is better expressed by counters/provenance (`web_search_count == 0`, `source_type: none`). Negative text checks invite false failures on innocent wording. |

### 4.3 Smallest useful schema change (recommended)

Three new optional fields (`expected_source_titles`,
`expected_min_local_sources`, `expected_web_search_count`), two new category
values, and one automatic policy-echo check. Concretely in
`evals/run_eval.py`:

1. `CATEGORIES` += `"multi_document"`, `"policy_fallback"`.
2. `validate_dataset()`: type checks for the three new fields
   (list-of-strings / positive int / int-or-`{"min","max"}` object).
3. `summarize_result()`: add `local_source_titles` (ordered, deduplicated
   `metadata["title"]` of non-web documents; missing titles excluded) and
   `web_fallback_policy` (from `result.get("web_fallback_policy", "")`).
4. `evaluate_row()`: three new named checks (`source_titles`,
   `min_local_sources`, `web_search_count`) plus the automatic
   `policy_applied` check for rows that set `web_fallback_policy`.
5. `compute_metrics()` / `render_markdown()`: per-category lines for the two
   new categories (and the new check-match counts, following the existing
   pattern).

`run_eval()` itself needs **no change** — the policy override is already
passed through, and the new checks are pure post-run functions.

No LLM-as-judge anywhere; every new check reads counters or `Document`
metadata.

---

## 5. Test updates (`tests/evals/test_eval_harness.py`)

All additions stay in the existing mocked/pure style — no API keys, no graph
invocation.

- **Shipped-dataset assertions**: update
  `test_shipped_dataset_is_valid_with_expected_category_mix` (total 15 → 24;
  category map gains `multi_document: 4`, `policy_fallback: 5`). Add a
  shipped-dataset test asserting every `multi_document` row carries
  `expected_min_local_sources >= 2` and ≥ 2 `expected_source_titles`, and
  every `policy_fallback` row carries `web_fallback_policy` and
  `expected_web_search_count` — so the datasets can't silently lose their
  load-bearing checks.
- **Validation**: new fields accepted when well-typed; flagged when malformed
  (`expected_source_titles` non-list / non-string items,
  `expected_min_local_sources` zero/negative/non-int,
  `expected_web_search_count` wrong type or bad min/max object); new
  categories accepted, unknown still rejected.
- **Summarization**: `local_source_titles` deduplicates multiple chunks of the
  same document, excludes the web supplement, tolerates missing `title`
  metadata; `web_fallback_policy` defaults safely on an empty result (the
  error path in `run_eval` builds `summarize_result({}, "")`).
- **Per-row checks**:
  - `source_titles`: passes when all listed titles cited; fails when one is
    missing; case handling defined (recommend exact match — titles are
    machine-recorded metadata, not LLM output).
  - `min_local_sources`: 2 distinct titles passes `>= 2`; two chunks of one
    document (1 distinct title) fails — the exact multi-document regression
    the field exists to catch.
  - `web_search_count`: exact-int pass/fail; `{"min": 1}` pass at 1 and 2,
    fail at 0.
  - `policy_applied`: row with `web_fallback_policy: "aggressive"` fails when
    the summary echoes `conservative`; rows without the field skip the check.
- **No regressions**: existing rows/checks untouched — the current tests for
  stop_reason forms, source types, normalization, privacy, web_fallback, and
  insufficient-context rules must keep passing unmodified (only the two
  shipped-dataset count tests change).
- **Metrics/rendering**: new categories appear in `compute_metrics` output and
  the rendered report; a fixture row per new category keeps
  `test_compute_metrics_aggregates_categories_checks_and_counters` honest.

---

## 6. Documentation updates

| File | Update |
|---|---|
| `evals/README.md` | New dataset schema rows (three new optional fields with semantics, the two new categories with counts), new check descriptions (source titles, min local sources, web-search count, automatic policy echo), and a short "policy rows" note explaining the paired-question design (same question, different policy). |
| `README.md` | "Behavioral evals" section: row/category counts (15/4 → 24/6) and one sentence that the eval now proves multi-document provenance and fallback-policy behavior — this also turns the §"synthetic corpus" cross-reference claim from asserted into tested. Update the test-count table when the new harness tests land (currently says 23 eval tests; the suite is already at 25). |
| `structure.md` | §14 last paragraph: dataset description (15-question / four categories → updated counts and the two new categories). |
| `CLAUDE.md` | Only the `evals/` row in the §2 table ("15-row dataset" → new count, mention the new optional check fields). No behavior-rule changes needed — existing rules already cover everything this phase must respect. |
| `docs/adr/009-eval-harness.md` | Optional: a short addendum noting the v2 check fields, or a new ADR if the team prefers ADR-per-change. Recommend a dated addendum to ADR 009 — the decision (deterministic checks, no judge) is unchanged; only its vocabulary grew. |

---

## 7. Implementation order

Each step is a small, reviewable commit; the mocked suites
(`tests/node/ tests/graph/ tests/evals/`) are the regression gate after every
step. Schema support comes first because both phases depend on it.

1. **3A-1 — Harness schema support** (`evals/run_eval.py` only): new
   categories, validation, summary fields, checks, metrics/render lines.
   Gate: `--validate-only` still passes on the *unchanged* 15-row dataset;
   `tests/evals/` still passes.
2. **3A-2 — Harness tests for the new machinery**
   (`tests/evals/test_eval_harness.py`): validation/summary/check/metrics
   tests from §5 (everything except the shipped-dataset count updates).
3. **3A-3 — Add the 4 `multi_document` rows** to `evals/questions.jsonl` +
   update the shipped-dataset count tests. Gate:
   `uv run python evals/run_eval.py --validate-only`.
4. **3B-1 — Add the 5 `policy_fallback` rows** + shipped-dataset count test
   update (same gates).
5. **3B-2 — Dedicated shipped-dataset policy tests**: every `policy_fallback`
   row pins a policy and a web-search-count expectation; the 3B-1/3B-2 and
   3B-3/3B-4 question pairs are asserted identical (the paired design is the
   point — protect it).
6. **3B-3 — Documentation updates** (§6).
7. **Later, separately approved — full eval refresh**: run
   `uv run python evals/run_eval.py` with real keys, treat the first run as
   calibration for the 3A provenance rows and 3B-2 (§2.3, §3.3), commit the
   regenerated `evals/results.md`. **Not part of this phase.**

Steps 1–6 require no API keys and run entirely under the existing CI jobs.

---

## 8. Constraints and risks

Hard constraints (all respected by this plan):

- **No RAG behavior changes** unless the eval exposes a real bug — and then
  only with explicit approval as a separate change. In particular: do not
  raise retrieval `k`, do not reorder `grade_generation` outcomes.
- **No prompt changes, no model-name changes** (`gpt-5-mini`,
  `temperature=0`).
- **No corpus document changes** — the rows were designed around the corpus
  as it is, including its existing cross-references.
- **No `stop_reason` semantics changes**; expected values reference existing
  constants only.
- **No fallback-policy semantics changes** — 3B *documents-by-eval* the
  current semantics (including router-web-still-works under `disabled`).
- **No full eval during planning or implementation**; only `--validate-only`.
- **No `tests/chains/` runs, no `ingestion.py` runs, no API keys required**
  for any step 1–6.
- **No eval history/delta tracking, no LLM-as-judge, no workflow automation,
  no UI/API** in this phase.
- `.env` / `.env.example` untouched (per-row policy goes through
  `AnswerOptions`, never the environment).

Risks:

| Risk | Mitigation |
|---|---|
| Top-3 retrieval returns chunks from only one document on a 3A row | Questions chosen along explicit corpus cross-references with shared vocabulary; first full run is calibration — reword questions, never weaken checks or change `k` (§2.3). |
| 3B-2 (`aggressive`) needs a mixed grading outcome, which is a model judgment | Accepted and documented (§3.3); reword toward more mixed retrieval if calibration shows all-relevant grading. The other policy rows rest on deterministic machinery. |
| Web-dependent rows (3B-2/3B-3/3B-5) have variable answer content | No content anchors on those rows; checks are counters + provenance only; `expected_stop_reason: null` where outcomes legitimately vary. |
| Title drift (corpus H1 edited later) silently breaks `expected_source_titles` | `expected_min_local_sources` provides a title-independent backstop; the shipped-dataset test asserting both fields keeps rows self-consistent. |
| Hard-coded category handling in metrics/render misses a new category | §5's fixture-per-category test; validation rejects unknown categories so a typo'd row fails fast. |
| Dataset grows stale vs. README/structure claims | §6 doc updates are an explicit step (3B-3), not an afterthought. |

---

## 9. Acceptance criteria for future implementation

Implementation of this plan is done when all of the following hold:

- `uv run ruff check .` passes.
- `uv run ruff format --check .` passes.
- `uv run mypy` passes (scope unchanged — `run_eval.py` is outside mypy
  scope, so no scope edits needed).
- `uv run pytest tests/evals/ -q` passes, including the updated
  shipped-dataset assertions (24 rows, 6 categories).
- `uv run pytest tests/node/ tests/graph/ tests/evals/ -q` passes — no
  regression anywhere in the mocked suites.
- `uv run python evals/run_eval.py --validate-only` reports the dataset OK
  with the new category counts.
- **No** prompt, model-name, corpus, graph-routing, state-schema,
  `stop_reason`, policy-semantics, or `.env`/`.env.example` changes in the
  diff.
- The 4 `multi_document` rows each pin ≥ 2 expected local source titles and
  `expected_min_local_sources: 2` — the dataset *structurally* cannot claim
  multi-document proof without them.
- The 5 `policy_fallback` rows pin a per-row policy, a web-search-count
  expectation, and include both identical-question pairs (conservative vs.
  aggressive; conservative vs. disabled) plus the router-web-under-disabled
  row.
- The full eval refresh (real OpenAI/Tavily run, regenerated
  `evals/results.md`) is **left for a separately approved API run** and is
  not required for this phase to merge.

Baseline verified during planning (2026-06-12): `ruff check` clean,
`ruff format --check` clean (53 files), `mypy` clean (5 files),
`tests/evals/` 25 passed. Working tree clean at commit `8e5fedf`.
