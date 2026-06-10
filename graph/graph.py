"""
graph.py

Purpose:
- Assemble the Agentic RAG workflow as a LangGraph StateGraph.
- Wire the nodes (retrieve / grade_documents / generate / websearch) together
  with conditional edges driven by the router and the two graders.
- Export the compiled `app`, which main.py invokes.

Workflow (see structure.md):

    question
    → route_question
        ├── websearch → generate
        └── retrieve → grade_documents
                ├── relevant docs → generate
                └── no relevant docs → websearch → generate

    generate
    → grounding + usefulness check
        ├── not grounded   → regenerate (generate again)
        ├── grounded+useful → END
        └── grounded+not useful → websearch

Privacy mode: when state["web_search_enabled"] is False (seeded from the
WEB_SEARCH_ENABLED env var by main.py), every websearch route above is disabled —
questions are never sent to an external search service. Routing falls back to
vector retrieval / direct generation, and "grounded but not useful" ends the run
with the grounded answer instead of searching the web.

Failure surfacing: runs that cannot end with a passing answer (web search
disabled, or MAX_RETRIES exhausted while a quality gate still fails) terminate
through small notice nodes that record state["stop_reason"], so main.py can
attach a user-facing caveat instead of presenting the answer as successful.
"""

from dotenv import load_dotenv

# Load .env up front.
# External clients (ChatOpenAI / OpenAIEmbeddings / retriever / Tavily) are now built
# lazily on first use rather than at import, but they still read env vars like
# OPENAI_API_KEY when constructed at runtime — so load .env before anything runs.
load_dotenv()

from langgraph.graph import StateGraph, END  # noqa: E402

from graph.state import GraphState  # noqa: E402
from graph.consts import (  # noqa: E402
    RETRIEVE,
    GRADE_DOCUMENTS,
    GENERATE,
    WEBSEARCH,
    WEB_SEARCH_DISABLED_NOTICE,
    MAX_RETRIES_NOT_GROUNDED_NOTICE,
    MAX_RETRIES_NOT_USEFUL_NOTICE,
)

from graph.nodes import (  # noqa: E402
    retrieve,
    grade_documents,
    generate,
    web_search,
    web_search_disabled_notice,
    max_retries_not_grounded_notice,
    max_retries_not_useful_notice,
)

from graph.chains.question_router import get_question_router  # noqa: E402
from graph.chains.hallucination_grader import get_hallucination_grader  # noqa: E402
from graph.chains.answer_grader import get_answer_grader  # noqa: E402


# Max number of generations allowed in the quality-check loop (regenerate / web search).
# Once the limit is reached, force an end to avoid looping between "not grounded" and "not useful".
MAX_RETRIES = 5


# ---------------------------------------------------------------------------
# Conditional edge functions
# These functions don't modify state; they only read it (or call chains) to decide
# the next node. The returned string must be a key in the add_conditional_edges mapping.
# ---------------------------------------------------------------------------


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
    route = get_question_router().invoke({"question": question})

    if route.datasource == WEBSEARCH:
        print("---ROUTE TO WEB SEARCH---")
        return WEBSEARCH

    print("---ROUTE TO RETRIEVE---")
    return RETRIEVE


def decide_to_generate(state: GraphState) -> str:
    """
    Decision after document grading:
    - If any document was flagged as not relevant (web_search=True), go to web search first.
    - Otherwise, generate the answer directly.
    """

    print("---ASSESS GRADED DOCUMENTS---")

    if state.get("web_search", False):
        if not state.get("web_search_enabled", True):
            # Privacy mode: generate from whatever relevant documents remain.
            # With none left, generation returns its deterministic
            # insufficient-context answer instead of fabricating one.
            print("---DECISION: SOME DOCS NOT RELEVANT, WEB SEARCH DISABLED, GENERATE---")
            return GENERATE

        print("---DECISION: SOME DOCS NOT RELEVANT, GO TO WEB SEARCH---")
        return WEBSEARCH

    print("---DECISION: GENERATE---")
    return GENERATE


def grade_generation(state: GraphState) -> str:
    """
    Two-layer quality check after generation, returning six explicit outcomes
    (each maps one-to-one to the conditional edges below):

    - "not_grounded": answer not supported by documents   -> back to GENERATE (regenerate).
    - "useful":       grounded and answers the question    -> END.
    - "not_useful":   grounded but doesn't answer it       -> WEBSEARCH (supplement).
    - "web_search_disabled": grounded but off-target with web search disabled
                             -> notice node recording a stop reason, then END
                                (no way to add information; main.py shows a caveat).
    - "max_retries_not_grounded": retry limit reached, answer still not grounded
                             -> notice node recording a stop reason, then END.
    - "max_retries_not_useful":   retry limit reached, answer grounded but off-target
                             -> notice node recording a stop reason, then END.
    """

    print("---CHECK HALLUCINATIONS---")

    question = state["question"]
    documents = state["documents"]
    generation = state["generation"]
    retries = state.get("retries", 0)

    # Key point: grade first, then check the retry limit.
    # This way even the MAX_RETRIES-th (final) generation is fully graded;
    # only when it fails and would otherwise loop do we stop via "max_retries".

    grounded = get_hallucination_grader().invoke(
        {
            "documents": documents,
            "generation": generation,
        }
    )

    if grounded.is_grounded:
        print("---DECISION: GROUNDED, GRADE ANSWER USEFULNESS---")

        useful = get_answer_grader().invoke(
            {
                "question": question,
                "generation": generation,
            }
        )

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

        # But if the limit is reached, stop protectively and record that the
        # final answer is grounded yet still off-target.
        if retries >= MAX_RETRIES:
            print(f"---MAX RETRIES ({MAX_RETRIES}) REACHED, ANSWER NOT USEFUL, STOP---")
            return "max_retries_not_useful"

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
workflow.add_node(MAX_RETRIES_NOT_GROUNDED_NOTICE, max_retries_not_grounded_notice)
workflow.add_node(MAX_RETRIES_NOT_USEFUL_NOTICE, max_retries_not_useful_notice)

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
        "not_grounded": GENERATE,       # not grounded -> regenerate
        "useful": END,                  # grounded and useful -> end
        "not_useful": WEBSEARCH,        # grounded but off-target -> web search
        # off-target but privacy mode -> record the stop reason, then stop
        # with the grounded answer (main.py attaches a user-facing caveat)
        "web_search_disabled": WEB_SEARCH_DISABLED_NOTICE,
        # retry limit reached with a still-failing answer -> record which
        # quality gate failed, then stop (main.py attaches a warning)
        "max_retries_not_grounded": MAX_RETRIES_NOT_GROUNDED_NOTICE,
        "max_retries_not_useful": MAX_RETRIES_NOT_USEFUL_NOTICE,
    },
)

# 7. The notice nodes are terminal: they only record a stop reason.
workflow.add_edge(WEB_SEARCH_DISABLED_NOTICE, END)
workflow.add_edge(MAX_RETRIES_NOT_GROUNDED_NOTICE, END)
workflow.add_edge(MAX_RETRIES_NOT_USEFUL_NOTICE, END)

# 8. Compile into a callable app
app = workflow.compile()






