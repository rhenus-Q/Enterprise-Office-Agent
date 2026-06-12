"""
Unit tests for the eval harness's pure helpers (evals/run_eval.py).

These tests never invoke the graph or any API: they cover dataset loading and
validation, result summarization, the deterministic per-row checks, metric
aggregation, and report rendering. The real dataset file is validated here so
a malformed row fails fast in CI-safe tests rather than mid-eval.
"""

from langchain_core.documents import Document

from evals.run_eval import (
    CATEGORIES,
    DEFAULT_DATASET,
    compute_metrics,
    evaluate_row,
    load_dataset,
    normalize_for_contains,
    render_markdown,
    summarize_result,
    validate_dataset,
)
from graph.consts import WEB_SEARCH_SOURCE


def _row(**overrides):
    row = {
        "id": "r1",
        "category": "local_corpus",
        "question": "Q",
        "web_search_enabled": True,
        "expected_behavior": "answers",
    }
    row.update(overrides)
    return row


def _summary(**overrides):
    summary = {
        "answer": "The answer.",
        "formatted_answer": "The answer.",
        "stop_reason": "",
        "retries": 1,
        "llm_call_count": 1,
        "web_search_count": 0,
        "web_result_grading_count": 0,
        "sources_shown": True,
        "local_source_used": True,
        "web_source_used": False,
        "local_source_titles": ["AcmeCorp Employee Onboarding Guide"],
        "web_fallback_policy": "conservative",
    }
    summary.update(overrides)
    return summary


# ---------------------------------------------------------------------------
# The shipped dataset itself
# ---------------------------------------------------------------------------


def test_shipped_dataset_is_valid_with_expected_category_mix():
    rows = load_dataset(DEFAULT_DATASET)

    assert validate_dataset(rows) == []
    assert len(rows) == 24
    counts = {c: sum(1 for r in rows if r["category"] == c) for c in CATEGORIES}
    assert counts == {
        "local_corpus": 5,
        "web_fallback": 5,
        "insufficient_context": 3,
        "privacy_mode": 2,
        "multi_document": 4,
        "policy_fallback": 5,
    }


def test_shipped_dataset_privacy_and_insufficient_rows_disable_web():
    rows = load_dataset(DEFAULT_DATASET)

    for row in rows:
        if row["category"] in ("privacy_mode", "insufficient_context"):
            assert row["web_search_enabled"] is False, row["id"]


def test_shipped_dataset_multi_document_rows_have_load_bearing_checks():
    rows = load_dataset(DEFAULT_DATASET)

    multi_rows = [row for row in rows if row["category"] == "multi_document"]

    assert len(multi_rows) == 4
    for row in multi_rows:
        assert row["expected_min_local_sources"] >= 2, row["id"]
        assert len(row["expected_source_titles"]) >= 2, row["id"]


def test_shipped_dataset_policy_rows_have_load_bearing_checks_and_pairs():
    rows = load_dataset(DEFAULT_DATASET)
    by_id = {row["id"]: row for row in rows}
    policy_rows = [row for row in rows if row["category"] == "policy_fallback"]

    assert len(policy_rows) == 5
    for row in policy_rows:
        assert row.get("web_fallback_policy") in ("conservative", "aggressive", "disabled")
        assert "expected_web_search_count" in row

    assert (
        by_id["policy-conservative-stays-local"]["question"]
        == by_id["policy-aggressive-escalates"]["question"]
    )
    assert (
        by_id["policy-conservative-web-when-empty"]["question"]
        == by_id["policy-disabled-declines-honestly"]["question"]
    )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_validate_accepts_minimal_valid_row():
    assert validate_dataset([_row()]) == []


def test_validate_flags_missing_required_field():
    row = _row()
    del row["question"]

    errors = validate_dataset([row])

    assert any("question" in e for e in errors)


def test_validate_flags_bad_category_and_duplicate_ids():
    errors = validate_dataset([_row(category="nonsense"), _row(), _row()])

    assert any("invalid category" in e for e in errors)
    assert any("duplicate id" in e for e in errors)


def test_validate_accepts_new_categories():
    assert validate_dataset([_row(category="multi_document")]) == []
    assert validate_dataset([_row(category="policy_fallback")]) == []


def test_validate_flags_bad_optional_field_types():
    errors = validate_dataset(
        [
            _row(id="a", web_search_enabled="yes"),
            _row(id="b", expected_stop_reason=42),
            _row(id="c", expected_source_type="cloud"),
            _row(id="d", expected_contains="not-a-list"),
        ]
    )

    assert len(errors) == 4


def test_validate_accepts_new_optional_eval_v2_fields():
    assert (
        validate_dataset(
            [
                _row(
                    expected_source_titles=["Doc A", "Doc B"],
                    expected_min_local_sources=2,
                    expected_web_search_count=0,
                ),
                _row(id="b", expected_web_search_count={"min": 1}),
                _row(id="c", expected_web_search_count={"max": 2}),
                _row(id="d", expected_web_search_count={"min": 1, "max": 3}),
            ]
        )
        == []
    )


def test_validate_flags_malformed_eval_v2_fields():
    errors = validate_dataset(
        [
            _row(id="a", expected_source_titles="Doc A"),
            _row(id="b", expected_source_titles=["Doc A", 42]),
            _row(id="c", expected_min_local_sources=0),
            _row(id="d", expected_min_local_sources="2"),
            _row(id="e", expected_web_search_count=-1),
            _row(id="f", expected_web_search_count={"min": "1"}),
            _row(id="g", expected_web_search_count={"max": -1}),
            _row(id="h", expected_web_search_count={"min": 3, "max": 1}),
            _row(id="i", expected_web_search_count={"exact": 1}),
        ]
    )

    assert sum("expected_source_titles" in e for e in errors) == 2
    assert sum("expected_min_local_sources" in e for e in errors) == 2
    assert sum("expected_web_search_count" in e for e in errors) == 5


def test_validate_accepts_optional_web_fallback_policy():
    # Existing rows omit the field entirely; new rows may pin a policy.
    assert validate_dataset([_row()]) == []
    assert validate_dataset([_row(web_fallback_policy=None)]) == []
    for policy in ("conservative", "aggressive", "disabled"):
        assert validate_dataset([_row(web_fallback_policy=policy)]) == []


def test_validate_flags_invalid_web_fallback_policy():
    errors = validate_dataset([_row(web_fallback_policy="bogus")])

    assert any("web_fallback_policy" in e for e in errors)


# ---------------------------------------------------------------------------
# Result summarization
# ---------------------------------------------------------------------------


def test_summarize_detects_local_and_web_sources():
    result = {
        "generation": "A",
        "stop_reason": "",
        "retries": 2,
        "llm_call_count": 3,
        "web_search_count": 1,
        "web_result_grading_count": 2,
        "documents": [
            Document(
                page_content="c",
                metadata={"source": "data/x.md", "title": "AcmeCorp VPN Access Policy"},
            ),
            Document(page_content="w", metadata={"source": WEB_SEARCH_SOURCE}),
        ],
        "web_fallback_policy": "aggressive",
    }

    summary = summarize_result(result, "formatted A")

    assert summary["local_source_used"] is True
    assert summary["web_source_used"] is True
    assert summary["sources_shown"] is True
    assert summary["formatted_answer"] == "formatted A"
    assert summary["retries"] == 2
    assert summary["local_source_titles"] == ["AcmeCorp VPN Access Policy"]
    assert summary["web_fallback_policy"] == "aggressive"


def test_summarize_handles_empty_result_safely():
    summary = summarize_result({}, "")

    assert summary["sources_shown"] is False
    assert summary["local_source_used"] is False
    assert summary["web_source_used"] is False
    assert summary["stop_reason"] == ""
    assert summary["web_search_count"] == 0
    assert summary["local_source_titles"] == []
    assert summary["web_fallback_policy"] == ""


def test_summarize_deduplicates_local_titles_excludes_web_and_missing_titles():
    result = {
        "documents": [
            Document(page_content="a", metadata={"source": "data/a.md", "title": "Doc A"}),
            Document(page_content="a2", metadata={"source": "data/a.md", "title": "Doc A"}),
            Document(page_content="b", metadata={"source": "data/b.md", "title": "Doc B"}),
            Document(page_content="untitled", metadata={"source": "data/c.md"}),
            Document(
                page_content="web",
                metadata={"source": WEB_SEARCH_SOURCE, "title": "Web Title"},
            ),
        ]
    }

    summary = summarize_result(result, "formatted")

    assert summary["local_source_titles"] == ["Doc A", "Doc B"]


# ---------------------------------------------------------------------------
# Per-row checks
# ---------------------------------------------------------------------------


def test_stop_reason_check_accepts_string_and_list_forms():
    assert evaluate_row(_row(expected_stop_reason=""), _summary())["passed"] is True
    assert (
        evaluate_row(_row(expected_stop_reason=""), _summary(stop_reason="tool_error"))["passed"]
        is False
    )
    assert (
        evaluate_row(
            _row(expected_stop_reason=["web_search_disabled", ""]),
            _summary(stop_reason="web_search_disabled"),
        )["passed"]
        is True
    )


def test_source_type_checks():
    assert evaluate_row(_row(expected_source_type="local_corpus"), _summary())["passed"] is True
    assert (
        evaluate_row(_row(expected_source_type="web"), _summary(web_source_used=False))["passed"]
        is False
    )
    assert (
        evaluate_row(
            _row(expected_source_type="none"),
            _summary(sources_shown=False, local_source_used=False),
        )["passed"]
        is True
    )


def test_expected_contains_is_case_insensitive_and_checks_formatted_answer():
    row = _row(expected_contains=["18 MONTHS"])

    ok = evaluate_row(row, _summary(formatted_answer="Retained for 18 months.\n\nSources:..."))
    bad = evaluate_row(row, _summary(formatted_answer="Retained for a while."))

    assert ok["passed"] is True
    assert bad["passed"] is False


def test_expected_contains_matches_unicode_hyphen_variants():
    # Models emit typographic hyphens (here U+2011, the non-breaking hyphen
    # that failed local-sev1-escalation) for content the dataset spells in
    # ASCII; a semantically correct answer must not fail on the dash glyph.
    row = _row(expected_contains=["Sev-1"])

    result = evaluate_row(row, _summary(formatted_answer="Escalate to Sev‑1 immediately"))

    assert result["checks"]["expected_contains"] is True
    assert result["passed"] is True


def test_expected_contains_matches_every_listed_dash_variant():
    row = _row(expected_contains=["Sev-1"])
    dash_variants = [
        "‐",  # hyphen
        "‑",  # non-breaking hyphen
        "‒",  # figure dash
        "–",  # en dash
        "—",  # em dash
        "−",  # minus sign
        "﹘",  # small em dash
        "﹣",  # small hyphen-minus
        "－",  # fullwidth hyphen-minus
    ]

    for dash in dash_variants:
        result = evaluate_row(row, _summary(formatted_answer=f"Sev{dash}1 criteria"))
        assert result["passed"] is True, f"U+{ord(dash):04X} did not match"


def test_expected_contains_still_fails_when_phrase_genuinely_absent():
    # Normalization must not weaken the check into a false positive.
    row = _row(expected_contains=["Sev-1"])

    result = evaluate_row(row, _summary(formatted_answer="Escalate severe incidents immediately."))

    assert result["checks"]["expected_contains"] is False
    assert result["passed"] is False


def test_expected_contains_tolerates_line_break_inside_phrase():
    # Whitespace runs (including newlines) collapse to single spaces, so a
    # wrapped phrase still matches.
    row = _row(expected_contains=["18 months"])

    result = evaluate_row(row, _summary(formatted_answer="retained for 18\nmonths in hot storage"))

    assert result["passed"] is True


def test_source_titles_check_passes_and_fails_exact_titles():
    row = _row(expected_source_titles=["Doc A", "Doc B"])

    ok = evaluate_row(row, _summary(local_source_titles=["Doc A", "Doc B", "Doc C"]))
    missing = evaluate_row(row, _summary(local_source_titles=["Doc A"]))

    assert ok["checks"]["source_titles"] is True
    assert ok["passed"] is True
    assert missing["checks"]["source_titles"] is False
    assert missing["passed"] is False


def test_min_local_sources_check_counts_distinct_local_titles():
    row = _row(expected_min_local_sources=2)

    ok = evaluate_row(row, _summary(local_source_titles=["Doc A", "Doc B"]))
    too_few = evaluate_row(row, _summary(local_source_titles=["Doc A"]))

    assert ok["checks"]["min_local_sources"] is True
    assert ok["passed"] is True
    assert too_few["checks"]["min_local_sources"] is False
    assert too_few["passed"] is False


def test_web_search_count_exact_check_passes_and_fails():
    row = _row(expected_web_search_count=0)

    assert evaluate_row(row, _summary(web_search_count=0))["passed"] is True
    result = evaluate_row(row, _summary(web_search_count=1))

    assert result["checks"]["web_search_count"] is False
    assert result["passed"] is False


def test_web_search_count_min_max_checks_pass_and_fail():
    min_row = _row(expected_web_search_count={"min": 1})
    max_row = _row(expected_web_search_count={"max": 2})
    range_row = _row(expected_web_search_count={"min": 1, "max": 2})

    assert evaluate_row(min_row, _summary(web_search_count=1))["passed"] is True
    assert evaluate_row(min_row, _summary(web_search_count=2))["passed"] is True
    assert evaluate_row(min_row, _summary(web_search_count=0))["passed"] is False
    assert evaluate_row(max_row, _summary(web_search_count=2))["passed"] is True
    assert evaluate_row(max_row, _summary(web_search_count=3))["passed"] is False
    assert evaluate_row(range_row, _summary(web_search_count=1))["passed"] is True
    assert evaluate_row(range_row, _summary(web_search_count=3))["passed"] is False


def test_policy_applied_check_passes_fails_and_skips_when_no_policy():
    matched = evaluate_row(
        _row(web_fallback_policy="aggressive"),
        _summary(web_fallback_policy="aggressive"),
    )
    mismatched = evaluate_row(
        _row(web_fallback_policy="aggressive"),
        _summary(web_fallback_policy="conservative"),
    )
    skipped = evaluate_row(_row(), _summary(web_fallback_policy="conservative"))

    assert matched["checks"]["policy_applied"] is True
    assert matched["passed"] is True
    assert mismatched["checks"]["policy_applied"] is False
    assert mismatched["passed"] is False
    assert "policy_applied" not in skipped["checks"]


def test_normalize_for_contains_folds_dashes_case_and_whitespace():
    assert normalize_for_contains("Sev‑1") == "sev-1"
    assert normalize_for_contains("  A—B \n C ") == "a-b c"
    # Plain ASCII content is unchanged apart from casefolding.
    assert normalize_for_contains("Sev-1") == "sev-1"


def test_privacy_rows_fail_on_any_web_search():
    row = _row(category="privacy_mode", web_search_enabled=False)

    assert evaluate_row(row, _summary(web_search_count=0))["passed"] is True
    result = evaluate_row(row, _summary(web_search_count=1))
    assert result["passed"] is False
    assert result["checks"]["privacy_no_web_search"] is False


def test_web_fallback_requires_web_source_and_a_search():
    row = _row(category="web_fallback")

    ok = evaluate_row(row, _summary(web_source_used=True, web_search_count=1))
    no_source = evaluate_row(row, _summary(web_source_used=False, web_search_count=1))
    no_search = evaluate_row(row, _summary(web_source_used=True, web_search_count=0))

    assert ok["passed"] is True
    assert no_source["passed"] is False
    assert no_search["passed"] is False


def test_insufficient_context_passes_on_decline_or_stop_reason():
    row = _row(category="insufficient_context", web_search_enabled=False)

    declined = evaluate_row(
        row, _summary(answer="I do not have enough information in the provided documents.")
    )
    caveated = evaluate_row(row, _summary(stop_reason="web_search_disabled"))
    confident = evaluate_row(row, _summary(answer="The password is hunter2."))

    assert declined["passed"] is True
    assert caveated["passed"] is True
    assert confident["passed"] is False


# ---------------------------------------------------------------------------
# Metrics and report
# ---------------------------------------------------------------------------


def _evaluated_fixture():
    rows = [
        _row(id="a", category="local_corpus", expected_stop_reason=""),
        _row(id="b", category="web_fallback"),
        _row(id="c", category="privacy_mode", web_search_enabled=False),
        _row(id="d", category="insufficient_context", web_search_enabled=False),
        _row(
            id="e",
            category="multi_document",
            expected_source_titles=["Doc A", "Doc B"],
            expected_min_local_sources=2,
        ),
        _row(
            id="f",
            category="policy_fallback",
            web_fallback_policy="disabled",
            expected_web_search_count=0,
        ),
    ]
    summaries = [
        _summary(retries=1, llm_call_count=2),
        _summary(web_source_used=True, web_search_count=2, retries=3, llm_call_count=4),
        _summary(web_search_count=0, retries=1, llm_call_count=1),
        _summary(
            answer="I do not have enough information in the provided documents.",
            web_search_count=0,
            retries=1,
            llm_call_count=0,
        ),
        _summary(local_source_titles=["Doc A", "Doc B"], retries=2, llm_call_count=2),
        _summary(
            web_fallback_policy="disabled",
            web_search_count=0,
            retries=1,
            llm_call_count=1,
        ),
    ]
    return [
        {"row": row, "summary": summary, **evaluate_row(row, summary)}
        for row, summary in zip(rows, summaries, strict=False)
    ]


def test_compute_metrics_aggregates_categories_checks_and_counters():
    metrics = compute_metrics(_evaluated_fixture())

    assert metrics["total"] == 6
    assert metrics["passed"] == 6
    assert metrics["local_answerable_passed"] == (1, 1)
    assert metrics["web_fallback_passed"] == (1, 1)
    assert metrics["privacy_mode_passed"] == (1, 1)
    assert metrics["insufficient_context_passed"] == (1, 1)
    assert metrics["multi_document_passed"] == (1, 1)
    assert metrics["policy_fallback_passed"] == (1, 1)
    assert metrics["stop_reason_matches"] == (1, 1)
    assert metrics["source_titles_matches"] == (1, 1)
    assert metrics["min_local_sources_matches"] == (1, 1)
    assert metrics["web_search_count_matches"] == (1, 1)
    assert metrics["policy_applied_matches"] == (1, 1)
    assert metrics["average_retries"] == round(9 / 6, 2)
    assert metrics["average_llm_calls"] == round(10 / 6, 2)
    assert metrics["total_web_searches"] == 2


def test_render_markdown_includes_metrics_and_every_row():
    evaluated = _evaluated_fixture()
    metrics = compute_metrics(evaluated)

    report = render_markdown(evaluated, metrics, "evals/questions.jsonl")

    assert "# Eval results" in report
    assert "Overall passed | 6 / 6" in report
    assert "multi_document passed | 1 / 1" in report
    assert "policy_fallback passed | 1 / 1" in report
    for entry in evaluated:
        assert entry["row"]["id"] in report


def test_render_markdown_labels_llm_calls_as_tracked():
    # The counter is a budgeted operational counter, not total LLM usage;
    # the report label must not overstate it.
    evaluated = _evaluated_fixture()
    metrics = compute_metrics(evaluated)

    report = render_markdown(evaluated, metrics, "evals/questions.jsonl")

    assert "Average tracked LLM calls" in report
    assert "| Average LLM calls |" not in report
    assert "| tracked llm |" in report  # per-question column header


def test_render_markdown_includes_partial_counter_note():
    evaluated = _evaluated_fixture()
    metrics = compute_metrics(evaluated)

    report = render_markdown(evaluated, metrics, "evals/questions.jsonl")

    assert "Router and grader calls are not individually tracked" in report
    assert "not billing-accurate" in report
