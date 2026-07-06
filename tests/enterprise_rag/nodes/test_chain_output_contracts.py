"""
Contract tests for the chains' structured-output models.

The mocked node and graph suites fake chain outputs with SimpleNamespace
objects carrying fields such as `is_relevant`, `is_grounded`,
`answers_question`, and `datasource`. Those mocks would stay green even if a
real Pydantic output model renamed the field its runtime consumer reads, so
this module locks the field-name contract directly against the model classes.

Keys-free by construction: it imports only the Pydantic model classes (not the
`get_*()` chain factories), so no ChatOpenAI client is built, and it needs no
API keys, network, or environment variables. Importing the chain modules is
side-effect-free per the repo's import rules — the client is constructed lazily
inside each `get_*()` factory, never at import time.

Each test asserts the required field is PRESENT (a subset check), so harmless
future additional fields do not break the contract, and it stays resilient to
unrelated prompt/implementation refactors.
"""

from enterprise_rag.graph.chains.answer_grader import GradeAnswer
from enterprise_rag.graph.chains.hallucination_grader import GradeHallucination
from enterprise_rag.graph.chains.question_router import RouteQuery
from enterprise_rag.graph.chains.retrieval_grader import RetrievalGrade
from enterprise_rag.graph.consts import RETRIEVE, WEBSEARCH

# ---------------------------------------------------------------------------
# retrieval grader -> RetrievalGrade.is_relevant
# (consumed by grade_documents and web_search via `score.is_relevant`)
# ---------------------------------------------------------------------------


def test_retrieval_grade_exposes_is_relevant_field():
    assert "is_relevant" in RetrievalGrade.model_fields


def test_retrieval_grade_instance_attribute_access_works():
    for value in (True, False):
        grade = RetrievalGrade(is_relevant=value)
        assert grade.is_relevant is value


# ---------------------------------------------------------------------------
# hallucination grader -> GradeHallucination.is_grounded
# (consumed by grade_generation via `grounded.is_grounded`)
# ---------------------------------------------------------------------------


def test_grade_hallucination_exposes_is_grounded_field():
    assert "is_grounded" in GradeHallucination.model_fields


def test_grade_hallucination_instance_attribute_access_works():
    for value in (True, False):
        grade = GradeHallucination(is_grounded=value)
        assert grade.is_grounded is value


# ---------------------------------------------------------------------------
# answer grader -> GradeAnswer.answers_question
# (consumed by grade_generation via `useful.answers_question`)
# ---------------------------------------------------------------------------


def test_grade_answer_exposes_answers_question_field():
    assert "answers_question" in GradeAnswer.model_fields


def test_grade_answer_instance_attribute_access_works():
    for value in (True, False):
        grade = GradeAnswer(answers_question=value)
        assert grade.answers_question is value


# ---------------------------------------------------------------------------
# question router -> RouteQuery.datasource
# (consumed by route_question via `route.datasource == WEBSEARCH`)
# ---------------------------------------------------------------------------


def test_route_query_exposes_datasource_field():
    assert "datasource" in RouteQuery.model_fields


def test_route_query_accepts_the_routing_constants_the_edge_compares_against():
    # route_question compares route.datasource against the RETRIEVE / WEBSEARCH
    # constants, so the model must accept exactly those two values as valid.
    for value in (RETRIEVE, WEBSEARCH):
        route = RouteQuery(datasource=value)
        assert route.datasource == value
