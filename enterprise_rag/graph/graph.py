"""
graph.py

Purpose:
- Assemble the Agentic RAG workflow as a LangGraph StateGraph.
- Wire the nodes (retrieve / grade_documents / generate / websearch) together
  with conditional edges driven by the router and the two graders.
- Export the compiled `app`, which the engine (enterprise_rag/graph/engine.py) invokes.

Workflow (see structure.md):

    question
    → route_question
        ├── websearch → generate
        └── retrieve → grade_documents
                ├── relevant docs → generate
                └── no relevant docs → websearch → generate

    generate
    → grounding + usefulness check
        ├── not grounded   → add grounding feedback → regenerate
        ├── grounded+useful → END
        └── grounded+not useful → rewrite search query → websearch

Meaningful retries: a failed grounding check injects corrective feedback into
the next generation input (add_grounding_feedback), and a failed usefulness
check rewrites the web search query (rewrite_query) — so each retry differs
from the previous attempt instead of repeating identical inputs at
temperature=0. Both extra nodes are linear pass-throughs inside the existing
retry cycles; every cycle still passes through generate, which increments
the retries counter that MAX_RETRIES caps.

Web-fallback policy: the per-run policy in state["web_fallback_policy"]
(seeded by enterprise_rag/graph/engine.py; the WEB_FALLBACK_POLICY env var is the default
source) tunes when document grading triggers web fallback while web search
is otherwise allowed.
"conservative" (default) generates from the remaining relevant local documents
and uses the web only when none remain; "aggressive" restores the legacy
any-irrelevant-doc-triggers-web behavior; "disabled" keeps local retrieval
paths local entirely — including the post-generation not-useful retry, which
ends through the web_fallback_disabled notice on local-only runs.

Privacy mode: when state["web_search_enabled"] is False (seeded from the
WEB_SEARCH_ENABLED env var by enterprise_rag/graph/engine.py::seed_state()), every websearch route above is disabled —
questions are never sent to an external search service. Routing falls back to
vector retrieval / direct generation, and "grounded but not useful" ends the run
with the grounded answer instead of searching the web.

Failure surfacing: runs that cannot end with a passing answer (web search
disabled, or MAX_RETRIES exhausted while a quality gate still fails) terminate
through small notice nodes that record state["stop_reason"], so the CLI
(enterprise_rag/cli.py) can attach a user-facing caveat instead of presenting
the answer as successful.

Insufficient-context bypass: when generation produced the deterministic
insufficient-context answer (no usable documents; flagged by the generate node
via state["insufficient_context"]), the graders are skipped — there is nothing
to verify, and regenerating from the same empty context cannot improve the
answer. The run ends honestly instead of looping toward a misleading
max-retries warning.

Graceful degradation: external dependency failures (Chroma retriever, Tavily,
the generation LLM, the graders, the query rewriter) never crash the graph.
Nodes catch the failure at the call site, degrade or stop safely, and record a
stop_reason (retrieval_error / web_search_error / generation_error /
tool_error). Grader failures inside the pure grade_generation edge route to
the tool_error notice node; a failed generation routes straight to END,
ungraded. Console banners log only the exception type, never messages that
could carry secrets.
"""

from dotenv import load_dotenv

# Load .env up front.
# External clients (ChatOpenAI / OpenAIEmbeddings / retriever / Tavily) are now built
# lazily on first use rather than at import, but they still read env vars like
# OPENAI_API_KEY when constructed at runtime — so load .env before anything runs.
load_dotenv()

from langgraph.graph import END, StateGraph

from enterprise_rag.graph.chains.answer_grader import get_answer_grader
from enterprise_rag.graph.chains.hallucination_grader import get_hallucination_grader
from enterprise_rag.graph.chains.question_router import get_question_router
from enterprise_rag.graph.config import (
    WEB_FALLBACK_AGGRESSIVE,
    WEB_FALLBACK_DISABLED,
    max_llm_calls_per_run,
    max_web_searches_per_run,
    normalize_web_fallback_policy,
    web_fallback_policy,
)
from enterprise_rag.graph.consts import (
    ADD_GROUNDING_FEEDBACK,
    BUDGET_EXHAUSTED_NOTICE,
    CLEAR_TRANSIENT_TOOL_ERROR,
    GENERATE,
    GRADE_DOCUMENTS,
    MAX_RETRIES_NOT_GROUNDED_NOTICE,
    MAX_RETRIES_NOT_USEFUL_NOTICE,
    RETRIEVE,
    REWRITE_QUERY,
    STOP_REASON_GENERATION_ERROR,
    TOOL_ERROR_NOTICE,
    WEB_FALLBACK_DISABLED_NOTICE,
    WEB_SEARCH_DISABLED_NOTICE,
    WEBSEARCH,
)
from enterprise_rag.graph.nodes import (
    add_grounding_feedback,
    budget_exhausted_notice,
    clear_transient_tool_error,
    generate,
    grade_documents,
    max_retries_not_grounded_notice,
    max_retries_not_useful_notice,
    retrieve,
    rewrite_query,
    tool_error_notice,
    web_fallback_disabled_notice,
    web_search,
    web_search_disabled_notice,
)
from enterprise_rag.graph.state import GraphState

# Max number of generations allowed in the quality-check loop (regenerate / web search).
# Once the limit is reached, force an end to avoid looping between "not grounded" and "not useful".
MAX_RETRIES = 5


# ---------------------------------------------------------------------------
# Conditional edge functions
# These functions don't modify state; they only read it (or call chains) to decide
# the next node. The returned string must be a key in the add_conditional_edges mapping.
# ---------------------------------------------------------------------------


def _resolve_web_fallback_policy(state: GraphState) -> str:
    """
    Effective web-fallback policy for this run.

    Ownership: enterprise_rag/graph/engine.py::seed_state() is the canonical entry point.
    It resolves the policy once — from AnswerOptions.web_fallback_policy or
    the WEB_FALLBACK_POLICY env var — normalizes it, and writes the result
    into state["web_fallback_policy"] before the graph starts. For every
    engine-driven run (answer_question() or seed_state()) the re-normalization
    here is a no-op: the value is already valid and re-normalizing a valid
    value is stable (idempotent).

    Compatibility: callers that invoke app.invoke() / app.stream() directly
    without going through answer_question() may omit web_fallback_policy from
    their seed state or pass an empty string. In that case this helper falls
    back to config.web_fallback_policy() (the env-driven default), preserving
    the pre-engine behavior. This path is intentional and does not affect
    engine-driven runs — it exists purely for direct-graph / legacy callers.
    See tests/enterprise_rag/graph/test_engine.py::test_missing_state_policy_falls_back_to_environment
    and tests/enterprise_rag/graph/test_web_fallback_policy.py for the coverage.
    """

    raw = state.get("web_fallback_policy")
    if not raw:
        return web_fallback_policy()
    return normalize_web_fallback_policy(raw)


def route_question(state: GraphState) -> str:
    """
    Entry routing: decide whether the question goes to web search or vector retrieval first.

    With web search disabled (privacy mode), skip the router LLM entirely: every
    question goes to vector retrieval and never reaches an external service.
    """

    print("---ROUTE QUESTION---")

    if not state.get("web_search_enabled", True):
        print("---WEB SEARCH DISABLED: ROUTE TO RETRIEVE---")
        return RETRIEVE

    question = state["question"]

    # The router LLM is an external call like any other, so a failure (timeout,
    # auth/quota error, network error, structured-output parse error) must not
    # crash the graph. Fall back to local retrieval — the safe, local-first
    # default that keeps the run alive and usually answers from the curated
    # corpus. This conditional edge is pure and cannot write state, so no
    # stop_reason is recorded here; the run continues through the normal gates.
    try:
        route = get_question_router().invoke({"question": question})
    except Exception as exc:
        # Log only the exception type: messages may carry secrets, prompts,
        # endpoints, or the question itself.
        print(f"---ROUTING FAILED ({type(exc).__name__}): FALLING BACK TO RETRIEVE---")
        return RETRIEVE

    if route.datasource == WEBSEARCH:
        print("---ROUTE TO WEB SEARCH---")
        return WEBSEARCH

    print("---ROUTE TO RETRIEVE---")
    return RETRIEVE


def decide_to_generate(state: GraphState) -> str:
    """
    Decision after document grading. web_search=True means grading filtered
    something out (or retrieval itself failed); what happens next depends on
    the privacy switch first, then the WEB_FALLBACK_POLICY:

    - Privacy mode (web_search_enabled=False): always generate from whatever
      relevant documents remain — never web search.
    - "conservative" (default): generate when at least one relevant local
      document remains; web fallback only with zero relevant docs left. The
      curated corpus is answered from first; the not-useful gate can still
      escalate to the web later.
    - "aggressive" (legacy CRAG): any filtered document triggers web fallback
      before generation.
    - "disabled": local retrieval paths never fall back to the web; with no
      relevant docs left, generation returns the deterministic
      insufficient-context answer instead.
    """

    print("---ASSESS GRADED DOCUMENTS---")

    if state.get("web_search", False):
        if not state.get("web_search_enabled", True):
            # Privacy mode: generate from whatever relevant documents remain.
            # With none left, generation returns its deterministic
            # insufficient-context answer instead of fabricating one.
            print("---DECISION: SOME DOCS NOT RELEVANT, WEB SEARCH DISABLED, GENERATE---")
            return GENERATE

        policy = _resolve_web_fallback_policy(state)

        if policy == WEB_FALLBACK_AGGRESSIVE:
            print("---DECISION: SOME DOCS NOT RELEVANT, GO TO WEB SEARCH (AGGRESSIVE POLICY)---")
            return WEBSEARCH

        if policy == WEB_FALLBACK_DISABLED:
            print("---DECISION: WEB FALLBACK DISABLED BY POLICY, GENERATE---")
            return GENERATE

        # Conservative (default): trust the curated corpus first.
        if state.get("documents"):
            print("---DECISION: RELEVANT LOCAL DOCS REMAIN, GENERATE (CONSERVATIVE POLICY)---")
            return GENERATE

        print("---DECISION: NO RELEVANT LOCAL DOCS REMAIN, GO TO WEB SEARCH---")
        return WEBSEARCH

    print("---DECISION: GENERATE---")
    return GENERATE


def grade_generation(state: GraphState) -> str:
    """
    Two-layer quality check after generation, returning eleven explicit
    outcomes (each maps one-to-one to the conditional edges below):

    - "insufficient_context": the generation is the deterministic
                             insufficient-context answer (no usable documents,
                             produced without an LLM call). There is nothing to
                             verify and regenerating from the same empty
                             context cannot improve it, so the graders are
                             skipped entirely -> END (in privacy mode with no
                             earlier failure recorded, via the
                             web_search_disabled notice so the caveat explains
                             why no information could be added).
    - "not_grounded": answer not supported by documents
                             -> ADD_GROUNDING_FEEDBACK, then GENERATE (the retry
                                receives corrective feedback in its input).
    - "useful":       grounded and answers the question
                             -> clear-transient-tool-error pass-through, then
                                END (a stale mid-run tool_error is cleared:
                                the answer passed both gates, so the warning
                                no longer describes the terminal outcome;
                                retrieval_error / web_search_error persist).
    - "not_useful":   grounded but doesn't answer it
                             -> REWRITE_QUERY, then WEBSEARCH (the retry searches
                                with a more specific rewritten query).
    - "web_search_disabled": grounded but off-target with web search disabled
                             -> notice node recording a stop reason, then END
                                (no way to add information; the CLI shows a caveat).
    - "web_fallback_disabled": grounded but off-target on a local-only run with
                             WEB_FALLBACK_POLICY=disabled -> notice node
                             recording a stop reason, then END (the policy
                             forbids escalating a local run to the web).
    - "max_retries_not_grounded": retry limit reached, answer still not grounded
                             -> notice node recording a stop reason, then END.
    - "max_retries_not_useful":   retry limit reached, answer grounded but off-target
                             -> notice node recording a stop reason, then END.
    - "budget_exhausted": the per-run cost budget is spent (checked BEFORE the
                             graders run, so no further spend occurs)
                             -> notice node recording a stop reason, then END.
    - "generation_error": the generation LLM call itself failed (the generate
                             node recorded the stop reason and substituted a
                             safe answer) -> END directly, never graded.
    - "tool_error":       a grader call failed, so the answer cannot be
                             verified -> notice node recording a stop reason,
                             then END (the answer is delivered with a caveat,
                             never presented as verified).
    """

    print("---CHECK HALLUCINATIONS---")

    question = state["question"]
    documents = state["documents"]
    generation = state["generation"]
    retries = state.get("retries", 0)

    # A failed generation must never be graded or presented as normal. The
    # generate node already recorded the stop reason and substituted a safe
    # answer; end the run immediately (the CLI attaches the caveat).
    if state.get("stop_reason") == STOP_REASON_GENERATION_ERROR:
        print("---GENERATION FAILED, STOP---")
        return "generation_error"

    # The deterministic insufficient-context answer carries no claims to
    # verify, and regenerating from the same empty context cannot improve it:
    # grading it wastes two grader calls per loop and can end an honest
    # decline in a misleading max-retries warning. Stop before the budget
    # check too — a clean decline must not be tagged budget_exhausted.
    # Privacy mode records web_search_disabled (the caveat explains why no
    # information could be added) unless an earlier, more specific failure
    # reason (e.g. retrieval_error) is already recorded — that one survives
    # by routing straight to END.
    if state.get("insufficient_context", False):
        if not state.get("web_search_enabled", True) and not state.get("stop_reason"):
            print("---INSUFFICIENT CONTEXT, WEB SEARCH DISABLED, STOP WITHOUT GRADING---")
            return "web_search_disabled"
        print("---INSUFFICIENT CONTEXT, STOP WITHOUT GRADING---")
        return "insufficient_context"

    # Per-run cost budget: checked before invoking the graders so an exhausted
    # run spends nothing more. The final answer is returned unverified, and
    # the CLI attaches a caveat saying exactly that. (Grader calls themselves
    # are not individually counted — they are bounded at two per generation,
    # so capping counted LLM calls transitively caps them.)
    if state.get("llm_call_count", 0) >= max_llm_calls_per_run():
        print("---LLM CALL BUDGET EXHAUSTED, STOP---")
        return "budget_exhausted"

    # Key point: grade first, then check the retry limit.
    # This way even the MAX_RETRIES-th (final) generation is fully graded;
    # only when it fails and would otherwise loop do we stop via "max_retries".

    # Grader failures are conservative: an answer whose verification failed
    # is never presented as verified. The tool_error notice node records the
    # stop reason (this edge is pure and cannot write state).
    try:
        grounded = get_hallucination_grader().invoke(
            {
                "documents": documents,
                "generation": generation,
            }
        )
    except Exception as exc:
        # Log only the exception type: messages may carry secrets.
        print(f"---GROUNDING CHECK FAILED ({type(exc).__name__}), STOP WITH UNVERIFIED ANSWER---")
        return "tool_error"

    if grounded.is_grounded:
        print("---DECISION: GROUNDED, GRADE ANSWER USEFULNESS---")

        try:
            useful = get_answer_grader().invoke(
                {
                    "question": question,
                    "generation": generation,
                }
            )
        except Exception as exc:
            print(
                f"---USEFULNESS CHECK FAILED ({type(exc).__name__}), STOP WITH UNVERIFIED ANSWER---"
            )
            return "tool_error"

        if useful.answers_question:
            # Answer passes: end directly, regardless of how many generations occurred.
            print("---DECISION: ANSWER IS USEFUL---")
            return "useful"

        # Grounded but doesn't answer the question: would normally go to WEBSEARCH
        # for another round. In privacy mode there is no way to add information --
        # regenerating from the same documents can't help, so stop with the
        # grounded answer we have.
        if not state.get("web_search_enabled", True):
            print("---DECISION: ANSWER NOT USEFUL, WEB SEARCH DISABLED, STOP---")
            return "web_search_disabled"

        # WEB_FALLBACK_POLICY=disabled: a run that has stayed on the local
        # retrieval path (no web search so far) must not escalate to the web
        # post-generation either — the safer enterprise interpretation.
        # Web-originated runs (web_search_count > 0) may still retry their
        # own search. Checked before the retry limit because, like privacy
        # mode, improvement was impossible regardless of retries.
        if (
            _resolve_web_fallback_policy(state) == WEB_FALLBACK_DISABLED
            and state.get("web_search_count", 0) == 0
        ):
            print("---DECISION: ANSWER NOT USEFUL, WEB FALLBACK DISABLED BY POLICY, STOP---")
            return "web_fallback_disabled"

        # But if the limit is reached, stop protectively and record that the
        # final answer is grounded yet still off-target.
        if retries >= MAX_RETRIES:
            print(f"---MAX RETRIES ({MAX_RETRIES}) REACHED, ANSWER NOT USEFUL, STOP---")
            return "max_retries_not_useful"

        # Improving a not-useful answer requires another web search; if the
        # search budget is spent, looping toward a search that would be
        # skipped is pure waste -- stop with the budget caveat instead.
        if state.get("web_search_count", 0) >= max_web_searches_per_run():
            print("---WEB SEARCH BUDGET EXHAUSTED, STOP---")
            return "budget_exhausted"

        print("---DECISION: ANSWER NOT USEFUL, GO TO WEB SEARCH---")
        return "not_useful"

    # Not grounded: would normally go back to GENERATE to regenerate.
    # But if the limit is reached, stop protectively and record that the final
    # answer still failed the grounding (anti-hallucination) check.
    if retries >= MAX_RETRIES:
        print(f"---MAX RETRIES ({MAX_RETRIES}) REACHED, ANSWER NOT GROUNDED, STOP---")
        return "max_retries_not_grounded"

    print("---DECISION: NOT GROUNDED, RE-GENERATE---")
    return "not_grounded"


# ---------------------------------------------------------------------------
# Build the graph
# ---------------------------------------------------------------------------

workflow = StateGraph(GraphState)

# 1. Register nodes
workflow.add_node(RETRIEVE, retrieve)
workflow.add_node(GRADE_DOCUMENTS, grade_documents)
workflow.add_node(GENERATE, generate)
workflow.add_node(WEBSEARCH, web_search)
workflow.add_node(WEB_SEARCH_DISABLED_NOTICE, web_search_disabled_notice)
workflow.add_node(WEB_FALLBACK_DISABLED_NOTICE, web_fallback_disabled_notice)
workflow.add_node(MAX_RETRIES_NOT_GROUNDED_NOTICE, max_retries_not_grounded_notice)
workflow.add_node(MAX_RETRIES_NOT_USEFUL_NOTICE, max_retries_not_useful_notice)
workflow.add_node(ADD_GROUNDING_FEEDBACK, add_grounding_feedback)
workflow.add_node(REWRITE_QUERY, rewrite_query)
workflow.add_node(BUDGET_EXHAUSTED_NOTICE, budget_exhausted_notice)
workflow.add_node(TOOL_ERROR_NOTICE, tool_error_notice)
workflow.add_node(CLEAR_TRANSIENT_TOOL_ERROR, clear_transient_tool_error)

# 2. Entry: route_question decides the first step
workflow.set_conditional_entry_point(
    route_question,
    {
        WEBSEARCH: WEBSEARCH,
        RETRIEVE: RETRIEVE,
    },
)

# 3. Vector retrieval path: retrieve -> grade_documents
workflow.add_edge(RETRIEVE, GRADE_DOCUMENTS)

# 4. Decision after grading: relevant -> generate; any irrelevant -> websearch
workflow.add_conditional_edges(
    GRADE_DOCUMENTS,
    decide_to_generate,
    {
        WEBSEARCH: WEBSEARCH,
        GENERATE: GENERATE,
    },
)

# 5. After web search, always proceed to generate
workflow.add_edge(WEBSEARCH, GENERATE)

# 6. Two-layer quality check after generation
workflow.add_conditional_edges(
    GENERATE,
    grade_generation,
    {
        # not grounded -> inject corrective feedback, then regenerate
        "not_grounded": ADD_GROUNDING_FEEDBACK,
        # grounded and useful -> clear any stale transient tool_error
        # (an answer that passed both gates must not ship with an error
        # caveat), then end
        "useful": CLEAR_TRANSIENT_TOOL_ERROR,
        # grounded but off-target -> rewrite the search query, then web search
        "not_useful": REWRITE_QUERY,
        # off-target but privacy mode -> record the stop reason, then stop
        # with the grounded answer (the CLI attaches a user-facing caveat)
        "web_search_disabled": WEB_SEARCH_DISABLED_NOTICE,
        # off-target on a local-only run with WEB_FALLBACK_POLICY=disabled ->
        # record the stop reason, then stop with the grounded answer
        "web_fallback_disabled": WEB_FALLBACK_DISABLED_NOTICE,
        # retry limit reached with a still-failing answer -> record which
        # quality gate failed, then stop (the CLI attaches a warning)
        "max_retries_not_grounded": MAX_RETRIES_NOT_GROUNDED_NOTICE,
        "max_retries_not_useful": MAX_RETRIES_NOT_USEFUL_NOTICE,
        # per-run cost budget spent -> record the stop reason, then stop
        "budget_exhausted": BUDGET_EXHAUSTED_NOTICE,
        # the generation call itself failed -> the generate node already
        # recorded the stop reason and a safe answer; end directly
        "generation_error": END,
        # the deterministic insufficient-context answer -> nothing to verify,
        # nothing to improve; end directly (an earlier stop_reason, if any,
        # survives and keeps its caveat)
        "insufficient_context": END,
        # a grader call failed -> record the stop reason, then stop with an
        # explicitly unverified answer
        "tool_error": TOOL_ERROR_NOTICE,
    },
)

# 7. Meaningful-retry pass-throughs: feedback feeds the regenerate cycle,
#    the rewritten query feeds the web-search cycle.
workflow.add_edge(ADD_GROUNDING_FEEDBACK, GENERATE)
workflow.add_edge(REWRITE_QUERY, WEBSEARCH)

# 8. The notice nodes are terminal: they only record a stop reason.
workflow.add_edge(WEB_SEARCH_DISABLED_NOTICE, END)
workflow.add_edge(WEB_FALLBACK_DISABLED_NOTICE, END)
workflow.add_edge(MAX_RETRIES_NOT_GROUNDED_NOTICE, END)
workflow.add_edge(MAX_RETRIES_NOT_USEFUL_NOTICE, END)
workflow.add_edge(BUDGET_EXHAUSTED_NOTICE, END)
workflow.add_edge(TOOL_ERROR_NOTICE, END)

# 8b. Successful endings pass through the transient-tool-error cleanup: a
#     mid-run tool_error (dropped chunk/result, failed rewrite) is stale once
#     the answer passed both gates. Terminal degradations keep their reasons.
workflow.add_edge(CLEAR_TRANSIENT_TOOL_ERROR, END)

# 9. Compile into a callable app
app = workflow.compile()
