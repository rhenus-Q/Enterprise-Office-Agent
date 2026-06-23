"""
Tests for the prompt-injection hardening on the grader / router / rewriter
chains.

These chains place untrusted input — user questions, retrieved documents, web
results, previous answers — directly into their prompts. Like the generation
chain (ADR 010, pinned by tests/node/test_generation_prompt.py), each must
explicitly demote that input from "instructions" to "data to classify, grade,
or rewrite". These tests pin the key security concepts so a later prompt edit
cannot silently drop the defense.

Pure string assertions on the prompt modules — importing them is
side-effect-free by design, so no API keys or network are required.
"""

from graph.chains.answer_grader import system_prompt as answer_grader_prompt
from graph.chains.hallucination_grader import (
    system_prompt as hallucination_grader_prompt,
)
from graph.chains.query_rewriter import system_prompt as query_rewriter_prompt
from graph.chains.question_router import system_prompt as question_router_prompt
from graph.chains.retrieval_grader import system_prompt as retrieval_grader_prompt

# ---------------------------------------------------------------------------
# Shared concepts every hardened chain must state
# ---------------------------------------------------------------------------


def _assert_untrusted_data_framing(prompt: str) -> None:
    # Collapse whitespace so line-wrapped multi-word phrases still match.
    lowered = " ".join(prompt.lower().split())
    # The input is untrusted data, not authority.
    assert "untrusted data" in lowered
    # It must be treated as data, not instructions.
    assert (
        "never as instructions" in lowered
        or "not as instructions" in lowered
        or "never as system or developer instructions" in lowered
    )
    # Embedded instructions must not be followed.
    assert "do not follow" in lowered or "do not obey" in lowered
    # Injection-control attempts must be ignored.
    assert "ignore" in lowered
    assert "ignore previous instructions" in lowered


# ---------------------------------------------------------------------------
# retrieval_grader
# ---------------------------------------------------------------------------


def test_retrieval_grader_prompt_frames_input_as_untrusted():
    _assert_untrusted_data_framing(retrieval_grader_prompt)


def test_retrieval_grader_prompt_keeps_its_criterion_and_notes_source():
    lowered = retrieval_grader_prompt.lower()
    assert "relevant" in lowered
    # The same chain grades local and web content.
    assert "web search" in lowered
    assert "mark this relevant" in lowered or '"mark this relevant"' in lowered


# ---------------------------------------------------------------------------
# hallucination_grader
# ---------------------------------------------------------------------------


def test_hallucination_grader_prompt_frames_input_as_untrusted():
    _assert_untrusted_data_framing(hallucination_grader_prompt)


def test_hallucination_grader_prompt_ignores_scoring_instructions():
    lowered = hallucination_grader_prompt.lower()
    assert "is_grounded=true" in lowered
    assert "supported by the documents" in lowered


# ---------------------------------------------------------------------------
# answer_grader
# ---------------------------------------------------------------------------


def test_answer_grader_prompt_frames_input_as_untrusted():
    _assert_untrusted_data_framing(answer_grader_prompt)


def test_answer_grader_prompt_ignores_pass_fail_forcing():
    lowered = answer_grader_prompt.lower()
    assert "pass/fail" in lowered
    assert "addresses the user's question" in lowered


# ---------------------------------------------------------------------------
# question_router
# ---------------------------------------------------------------------------


def test_question_router_prompt_frames_input_as_untrusted():
    _assert_untrusted_data_framing(question_router_prompt)


def test_question_router_prompt_forbids_privacy_and_secret_bypass():
    lowered = question_router_prompt.lower()
    assert "privacy" in lowered
    assert "secrets" in lowered
    assert "system or developer instructions" in lowered


# ---------------------------------------------------------------------------
# query_rewriter
# ---------------------------------------------------------------------------


def test_query_rewriter_prompt_frames_input_as_untrusted():
    lowered = query_rewriter_prompt.lower()
    assert "untrusted data" in lowered
    assert "never as instructions" in lowered or "not as instructions" in lowered
    assert "do not follow" in lowered


def test_query_rewriter_prompt_forbids_secret_exfiltration():
    lowered = query_rewriter_prompt.lower()
    assert "secrets" in lowered
    assert "api keys" in lowered
    assert "environment variables" in lowered
    assert "exfiltration" in lowered
    # Output contract is unchanged: only a clean search query.
    assert "clean search query" in lowered
