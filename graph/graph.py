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
                 └── max retries → END

    generate
    → grounding + usefulness check
        ├── not grounded   → regenerate (generate again)
        ├── grounded+useful → END
        └── grounded+not useful → websearch
"""

from dotenv import load_dotenv

# Load .env up front.
# External clients (ChatOpenAI / OpenAIEmbeddings / retriever / Tavily) are now built
# lazily on first use rather than at import, but they still read env vars like
# OPENAI_API_KEY when constructed at runtime — so load .env before anything runs.
load_dotenv()

from langgraph.graph import StateGraph, END  # noqa: E402

from graph.state import GraphState  # noqa: E402
from graph.consts import RETRIEVE, GRADE_DOCUMENTS, GENERATE, WEBSEARCH  # noqa: E402

from graph.nodes import retrieve, grade_documents, generate, web_search  # noqa: E402

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
    """

    print("---ROUTE QUESTION---")

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
        print("---DECISION: SOME DOCS NOT RELEVANT, GO TO WEB SEARCH---")
        return WEBSEARCH

    print("---DECISION: GENERATE---")
    return GENERATE


def grade_generation(state: GraphState) -> str:
    """
    Two-layer quality check after generation, returning four explicit outcomes
    (each maps one-to-one to the conditional edges below):

    - "not_grounded": answer not supported by documents   -> back to GENERATE (regenerate).
    - "useful":       grounded and answers the question    -> END.
    - "not_useful":   grounded but doesn't answer it       -> WEBSEARCH (supplement).
    - "max_retries":  retry limit reached                  -> END (protective stop).
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

        # Grounded but doesn't answer the question: would normally go to WEBSEARCH for another round.
        # But if the limit is reached, stop protectively.
        if retries >= MAX_RETRIES:
            print(f"---MAX RETRIES ({MAX_RETRIES}) REACHED AFTER CHECK, STOP---")
            return "max_retries"

        print("---DECISION: ANSWER NOT USEFUL, GO TO WEB SEARCH---")
        return "not_useful"

    # Not grounded: would normally go back to GENERATE to regenerate.
    # But if the limit is reached, stop protectively.
    if retries >= MAX_RETRIES:
        print(f"---MAX RETRIES ({MAX_RETRIES}) REACHED AFTER CHECK, STOP---")
        return "max_retries"

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
        "not_grounded": GENERATE,   # not grounded -> regenerate
        "useful": END,              # grounded and useful -> end
        "not_useful": WEBSEARCH,    # grounded but off-target -> web search
        "max_retries": END,         # retry limit reached -> protective stop
    },
)

# 7. Compile into a callable app
app = workflow.compile()






