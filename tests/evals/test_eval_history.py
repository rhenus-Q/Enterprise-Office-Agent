"""
Unit tests for the eval history and delta helpers (evals/run_eval.py).

All tests are mocked/pure — no API keys, no graph calls needed.
Covers: dataset_fingerprint, build_history_record, compute_delta,
render_delta_section, write/load history I/O, baseline error paths,
--no-history behavior, write-failure status, and render_markdown regression.
"""

import json
import sys
from unittest.mock import MagicMock

import pytest

from evals.run_eval import (
    HistoryBaselineError,
    build_history_record,
    compute_delta,
    dataset_fingerprint,
    load_history_record,
    load_latest_history_record,
    render_delta_section,
    render_markdown,
    run_eval,
    write_history_record,
)

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _row_entry(rid, passed=True, category="local_corpus"):
    """Minimal history-record row dict."""
    return {
        "id": rid,
        "category": category,
        "passed": passed,
        "failed_checks": [] if passed else ["stop_reason"],
        "stop_reason": "",
        "retries": 0,
        "llm_call_count": 1,
        "web_search_count": 0,
    }


def _metrics(passed=2, total=2):
    """Minimal metrics dict matching compute_metrics output shape (tuples)."""
    return {
        "total": total,
        "passed": passed,
        "stop_reason_matches": (0, 0),
        "source_type_matches": (0, 0),
        "expected_contains_matches": (0, 0),
        "expected_not_contains_matches": (0, 0),
        "source_titles_matches": (0, 0),
        "min_local_sources_matches": (0, 0),
        "web_search_count_matches": (0, 0),
        "policy_applied_matches": (0, 0),
        "local_answerable_passed": (passed, total),
        "web_fallback_passed": (0, 0),
        "insufficient_context_passed": (0, 0),
        "privacy_mode_passed": (0, 0),
        "multi_document_passed": (0, 0),
        "policy_fallback_passed": (0, 0),
        "average_retries": 0.0,
        "average_llm_calls": 1.0,
        "total_web_searches": 0,
    }


def _record(
    run_id="run-001",
    generated="2026-06-13T10:00:00Z",
    rows=None,
    sha="abc123",
    passed=2,
    total=2,
):
    """Build a minimal history record dict."""
    if rows is None:
        rows = [_row_entry("r1"), _row_entry("r2")]
    ids = [r["id"] for r in rows]
    return {
        "schema_version": 1,
        "run_id": run_id,
        "generated": generated,
        "dataset": "evals/questions.jsonl",
        "dataset_fingerprint": {
            "row_count": len(rows),
            "ids": ids,
            "dataset_sha256": sha,
        },
        "metrics": _metrics(passed=passed, total=total),
        "rows": rows,
    }


def _minimal_evaluated(ids=("r1", "r2"), all_passing=True):
    """Build minimal evaluated entries for build_history_record tests."""
    result = []
    for rid in ids:
        summary = {
            "answer": "The answer.",
            "formatted_answer": "The answer.",
            "stop_reason": "",
            "retries": 0,
            "llm_call_count": 1,
            "web_search_count": 0,
            "web_result_grading_count": 0,
            "sources_shown": False,
            "local_source_used": False,
            "web_source_used": False,
            "local_source_titles": [],
            "web_fallback_policy": "conservative",
        }
        result.append(
            {
                "row": {
                    "id": rid,
                    "category": "local_corpus",
                    "question": f"Q {rid}",
                    "web_search_enabled": True,
                    "expected_behavior": "answers",
                },
                "summary": summary,
                "checks": {},
                "passed": all_passing,
            }
        )
    return result


# ---------------------------------------------------------------------------
# dataset_fingerprint — pure
# ---------------------------------------------------------------------------


def test_dataset_fingerprint_sha256_changes_on_content_edit_same_ids():
    rows = [{"id": "r1"}, {"id": "r2"}]
    content_a = b'{"id": "r1"}\n{"id": "r2"}\n'
    content_b = b'{"id": "r1", "question": "changed"}\n{"id": "r2"}\n'

    fp_a = dataset_fingerprint(rows, content_a)
    fp_b = dataset_fingerprint(rows, content_b)

    assert fp_a["row_count"] == fp_b["row_count"] == 2
    assert fp_a["ids"] == fp_b["ids"] == ["r1", "r2"]
    assert fp_a["dataset_sha256"] != fp_b["dataset_sha256"]


def test_dataset_fingerprint_changes_on_id_edit():
    rows_a = [{"id": "r1"}, {"id": "r2"}]
    rows_b = [{"id": "r1"}, {"id": "r3"}]

    fp_a = dataset_fingerprint(rows_a, b"content-a")
    fp_b = dataset_fingerprint(rows_b, b"content-b")

    assert fp_a["ids"] != fp_b["ids"]
    assert fp_a["dataset_sha256"] != fp_b["dataset_sha256"]


def test_dataset_fingerprint_changes_on_row_add():
    rows_a = [{"id": "r1"}]
    rows_b = [{"id": "r1"}, {"id": "r2"}]

    fp_a = dataset_fingerprint(rows_a, b"line1")
    fp_b = dataset_fingerprint(rows_b, b"line1\nline2")

    assert fp_a["row_count"] == 1
    assert fp_b["row_count"] == 2
    assert fp_a["dataset_sha256"] != fp_b["dataset_sha256"]


def test_dataset_fingerprint_is_deterministic():
    rows = [{"id": "r1"}, {"id": "r2"}]
    content = b"the content"

    assert dataset_fingerprint(rows, content) == dataset_fingerprint(rows, content)


# ---------------------------------------------------------------------------
# build_history_record — pure
# ---------------------------------------------------------------------------


def test_build_history_record_shape():
    rows = [{"id": "r1"}]
    evaluated = _minimal_evaluated(ids=("r1",))
    m = _metrics(passed=1, total=1)
    fp = dataset_fingerprint(rows, b"content")

    record = build_history_record(
        evaluated,
        m,
        "evals/questions.jsonl",
        fp,
        timestamp="2026-06-13T10:00:00Z",
        run_id="test-run-001",
    )

    assert record["schema_version"] == 1
    assert record["run_id"] == "test-run-001"
    assert record["generated"] == "2026-06-13T10:00:00Z"
    assert record["dataset"] == "evals/questions.jsonl"
    assert record["dataset_fingerprint"] == fp
    assert record["metrics"] is m
    assert len(record["rows"]) == 1
    assert record["rows"][0]["id"] == "r1"


def test_build_history_record_is_metadata_only():
    """No answer text, formatted_answer, or page_content must appear in the record."""
    evaluated = _minimal_evaluated(ids=("r1",))
    fp = dataset_fingerprint([{"id": "r1"}], b"content")

    record = build_history_record(
        evaluated,
        _metrics(1, 1),
        "evals/questions.jsonl",
        fp,
        timestamp="2026-06-13T10:00:00Z",
        run_id="test-run-001",
    )

    row_entry = record["rows"][0]
    assert "answer" not in row_entry
    assert "formatted_answer" not in row_entry
    serialized = json.dumps(record)
    assert "page_content" not in serialized


def test_build_history_record_failed_row_has_run_completed_in_failed_checks():
    evaluated = [
        {
            "row": {
                "id": "r1",
                "category": "local_corpus",
                "question": "Q",
                "web_search_enabled": True,
                "expected_behavior": "x",
            },
            "summary": {
                "answer": "",
                "formatted_answer": "",
                "stop_reason": "",
                "retries": 0,
                "llm_call_count": 0,
                "web_search_count": 0,
                "web_result_grading_count": 0,
                "sources_shown": False,
                "local_source_used": False,
                "web_source_used": False,
                "local_source_titles": [],
                "web_fallback_policy": "",
            },
            "checks": {"run_completed": False},
            "passed": False,
        }
    ]
    fp = dataset_fingerprint([{"id": "r1"}], b"c")

    record = build_history_record(
        evaluated,
        _metrics(0, 1),
        "evals/questions.jsonl",
        fp,
        timestamp="2026-06-13T10:00:00Z",
        run_id="r002",
    )

    assert record["rows"][0]["passed"] is False
    assert record["rows"][0]["failed_checks"] == ["run_completed"]


def test_build_history_record_fingerprint_embedded():
    rows = [{"id": "r1"}, {"id": "r2"}]
    fp = dataset_fingerprint(rows, b"dataset content")
    evaluated = _minimal_evaluated(ids=("r1", "r2"))

    record = build_history_record(
        evaluated,
        _metrics(),
        "evals/questions.jsonl",
        fp,
        timestamp="2026-06-13T10:00:00Z",
        run_id="fp-test",
    )

    assert record["dataset_fingerprint"]["row_count"] == 2
    assert record["dataset_fingerprint"]["ids"] == ["r1", "r2"]
    assert record["dataset_fingerprint"]["dataset_sha256"] == fp["dataset_sha256"]


# ---------------------------------------------------------------------------
# compute_delta — pure
# ---------------------------------------------------------------------------


def test_compute_delta_newly_passing():
    baseline = _record(rows=[_row_entry("r1", passed=False)], passed=0, total=1)
    current = _record(
        run_id="cur",
        generated="2026-06-13T11:00:00Z",
        rows=[_row_entry("r1", passed=True)],
        passed=1,
        total=1,
    )

    delta = compute_delta(baseline, current)

    assert delta["rows"]["newly_passing"] == ["r1"]
    assert delta["rows"]["newly_failing"] == []
    assert delta["rows"]["still_failing"] == []


def test_compute_delta_newly_failing():
    baseline = _record(rows=[_row_entry("r1", passed=True)], passed=1, total=1)
    current = _record(
        run_id="cur",
        generated="2026-06-13T11:00:00Z",
        rows=[_row_entry("r1", passed=False)],
        passed=0,
        total=1,
    )

    delta = compute_delta(baseline, current)

    assert delta["rows"]["newly_failing"] == ["r1"]
    assert delta["rows"]["newly_passing"] == []
    assert delta["rows"]["still_failing"] == []


def test_compute_delta_still_failing():
    baseline = _record(rows=[_row_entry("r1", passed=False)], passed=0, total=1)
    current = _record(
        run_id="cur",
        generated="2026-06-13T11:00:00Z",
        rows=[_row_entry("r1", passed=False)],
        passed=0,
        total=1,
    )

    delta = compute_delta(baseline, current)

    assert delta["rows"]["still_failing"] == ["r1"]
    assert delta["rows"]["newly_passing"] == []
    assert delta["rows"]["newly_failing"] == []


def test_compute_delta_added():
    baseline = _record(rows=[_row_entry("r1")], passed=1, total=1, sha="sha-b")
    current = _record(
        run_id="cur",
        generated="2026-06-13T11:00:00Z",
        rows=[_row_entry("r1"), _row_entry("r2")],
        passed=2,
        total=2,
        sha="sha-c",
    )

    delta = compute_delta(baseline, current)

    assert delta["rows"]["added"] == ["r2"]
    assert delta["rows"]["removed"] == []


def test_compute_delta_removed():
    baseline = _record(rows=[_row_entry("r1"), _row_entry("r2")], passed=2, total=2, sha="sha-b")
    current = _record(
        run_id="cur",
        generated="2026-06-13T11:00:00Z",
        rows=[_row_entry("r1")],
        passed=1,
        total=1,
        sha="sha-c",
    )

    delta = compute_delta(baseline, current)

    assert delta["rows"]["removed"] == ["r2"]
    assert delta["rows"]["added"] == []


def test_compute_delta_tuple_vs_list_equivalence():
    # Simulate JSON round-trip: baseline metrics have lists, current has tuples.
    baseline = _record(passed=1, total=2)
    baseline["metrics"]["local_answerable_passed"] = [1, 2]  # list (JSON form)
    baseline["metrics"]["stop_reason_matches"] = [0, 0]  # list (JSON form)
    current = _record(run_id="cur", generated="2026-06-13T11:00:00Z", passed=2, total=2)
    # current["metrics"]["local_answerable_passed"] is tuple (2, 2)

    delta = compute_delta(baseline, current)

    # local_answerable_passed: 2 (current) - 1 (baseline) = +1
    b_v, c_v, d_v = delta["categories"]["local_answerable_passed"]
    assert b_v == 1
    assert c_v == 2
    assert d_v == 1
    # stop_reason_matches: 0 - 0 = 0
    b_v2, c_v2, d_v2 = delta["checks"]["stop_reason_matches"]
    assert d_v2 == 0


def test_compute_delta_missing_category_treated_as_zero():
    baseline = _record()
    del baseline["metrics"]["local_answerable_passed"]
    current = _record(run_id="cur", generated="2026-06-13T11:00:00Z", passed=2, total=2)

    delta = compute_delta(baseline, current)

    b_v, c_v, d_v = delta["categories"]["local_answerable_passed"]
    assert b_v == 0
    assert c_v == 2
    assert d_v == 2


def test_compute_delta_missing_check_treated_as_zero():
    baseline = _record()
    del baseline["metrics"]["stop_reason_matches"]
    current = _record(run_id="cur", generated="2026-06-13T11:00:00Z")
    current["metrics"]["stop_reason_matches"] = (1, 1)

    delta = compute_delta(baseline, current)

    b_v, c_v, d_v = delta["checks"]["stop_reason_matches"]
    assert b_v == 0
    assert c_v == 1
    assert d_v == 1


def test_compute_delta_dataset_changed_when_row_count_differs():
    baseline = _record(sha="same-sha")
    current = _record(run_id="cur", generated="2026-06-13T11:00:00Z", sha="same-sha")
    current["dataset_fingerprint"]["row_count"] = 99

    delta = compute_delta(baseline, current)

    assert delta["dataset_changed"] is True


def test_compute_delta_dataset_changed_when_ids_differ():
    baseline = _record(rows=[_row_entry("r1"), _row_entry("r2")], sha="sha-b")
    current = _record(
        run_id="cur",
        generated="2026-06-13T11:00:00Z",
        rows=[_row_entry("r1"), _row_entry("r3")],
        sha="sha-c",
    )

    delta = compute_delta(baseline, current)

    assert delta["dataset_changed"] is True


def test_compute_delta_dataset_changed_when_sha_differs_only():
    baseline = _record(sha="sha-a")
    current = _record(run_id="cur", generated="2026-06-13T11:00:00Z", sha="sha-b")

    delta = compute_delta(baseline, current)

    assert delta["dataset_changed"] is True


def test_compute_delta_dataset_not_changed_when_fingerprints_equal():
    baseline = _record(sha="sha-x")
    current = _record(run_id="cur", generated="2026-06-13T11:00:00Z", sha="sha-x")

    delta = compute_delta(baseline, current)

    assert delta["dataset_changed"] is False


def test_compute_delta_overall_counts():
    baseline = _record(passed=1, total=2)
    current = _record(run_id="cur", generated="2026-06-13T11:00:00Z", passed=2, total=2)

    delta = compute_delta(baseline, current)

    b_p, c_p, d_p = delta["overall"]["passed"]
    assert b_p == 1
    assert c_p == 2
    assert d_p == 1


# ---------------------------------------------------------------------------
# render_delta_section — pure
# ---------------------------------------------------------------------------


def test_render_delta_section_no_baseline():
    lines = render_delta_section(None)

    assert any("No previous run found" in line for line in lines)
    assert any("## Delta vs. previous run" in line for line in lines)


def test_render_delta_section_dataset_changed_warning():
    baseline = _record(sha="sha-a")
    current = _record(run_id="cur", generated="2026-06-13T11:00:00Z", sha="sha-b")
    delta = compute_delta(baseline, current)

    lines = render_delta_section(delta)

    assert any("Warning" in line for line in lines)
    assert any("dataset fingerprint changed" in line for line in lines)


def test_render_delta_section_no_warning_when_fingerprint_same():
    baseline = _record(sha="sha-x")
    current = _record(run_id="cur", generated="2026-06-13T11:00:00Z", sha="sha-x")
    delta = compute_delta(baseline, current)

    lines = render_delta_section(delta)

    assert not any("Warning" in line for line in lines)


def test_render_delta_section_signed_deltas():
    baseline = _record(passed=1, total=2)
    current = _record(run_id="cur", generated="2026-06-13T11:00:00Z", passed=2, total=2)
    delta = compute_delta(baseline, current)

    lines = render_delta_section(delta)
    text = "\n".join(lines)

    assert "+1" in text  # overall passed went from 1 to 2


def test_render_delta_section_transition_lists():
    baseline = _record(rows=[_row_entry("r1", passed=True), _row_entry("r2", passed=False)])
    current = _record(
        run_id="cur",
        generated="2026-06-13T11:00:00Z",
        rows=[_row_entry("r1", passed=False), _row_entry("r2", passed=True)],
    )
    delta = compute_delta(baseline, current)

    lines = render_delta_section(delta)
    text = "\n".join(lines)

    assert "Newly passing" in text
    assert "Newly failing" in text
    assert "`r2`" in text  # r2 went from failing to passing
    assert "`r1`" in text  # r1 went from passing to failing


def test_render_delta_section_includes_baseline_info():
    baseline = _record(run_id="baseline-run-xyz", generated="2026-06-13T09:00:00Z")
    current = _record(run_id="cur", generated="2026-06-13T11:00:00Z")
    delta = compute_delta(baseline, current)

    lines = render_delta_section(delta)
    text = "\n".join(lines)

    assert "baseline-run-xyz" in text
    assert "2026-06-13T09:00:00Z" in text


# ---------------------------------------------------------------------------
# render_markdown regression — output unchanged when no delta_lines
# ---------------------------------------------------------------------------


def _minimal_render_inputs():
    evaluated = _minimal_evaluated(ids=("r1",))
    m = {
        "total": 1,
        "passed": 1,
        "stop_reason_matches": (0, 0),
        "source_type_matches": (0, 0),
        "expected_contains_matches": (0, 0),
        "expected_not_contains_matches": (0, 0),
        "source_titles_matches": (0, 0),
        "min_local_sources_matches": (0, 0),
        "web_search_count_matches": (0, 0),
        "policy_applied_matches": (0, 0),
        "local_answerable_passed": (1, 1),
        "web_fallback_passed": (0, 0),
        "insufficient_context_passed": (0, 0),
        "privacy_mode_passed": (0, 0),
        "multi_document_passed": (0, 0),
        "policy_fallback_passed": (0, 0),
        "average_retries": 0.0,
        "average_llm_calls": 1.0,
        "total_web_searches": 0,
    }
    return evaluated, m


def test_render_markdown_without_delta_lines_is_stable():
    """render_markdown(delta_lines=None) must produce the same output as before."""
    evaluated, m = _minimal_render_inputs()

    report_without = render_markdown(evaluated, m, "evals/questions.jsonl")
    report_with_none = render_markdown(evaluated, m, "evals/questions.jsonl", delta_lines=None)

    assert report_without == report_with_none


def test_render_markdown_delta_section_inserted_before_per_question():
    evaluated, m = _minimal_render_inputs()
    delta_lines = ["## Delta vs. previous run", "", "No previous run found.", ""]

    report = render_markdown(evaluated, m, "evals/questions.jsonl", delta_lines=delta_lines)

    delta_pos = report.index("## Delta vs. previous run")
    per_q_pos = report.index("## Per-question results")
    assert delta_pos < per_q_pos


def test_render_markdown_no_delta_section_when_none():
    evaluated, m = _minimal_render_inputs()

    report = render_markdown(evaluated, m, "evals/questions.jsonl")

    assert "## Delta vs. previous run" not in report


# ---------------------------------------------------------------------------
# write_history_record / load_history_record / load_latest — I/O
# ---------------------------------------------------------------------------


def test_write_and_load_history_record_round_trip(tmp_path):
    rec = _record()
    path = write_history_record(rec, tmp_path)

    loaded = load_history_record(path)

    assert loaded["run_id"] == rec["run_id"]
    assert loaded["schema_version"] == 1
    assert loaded["dataset_fingerprint"]["dataset_sha256"] == rec["dataset_fingerprint"]["dataset_sha256"]


def test_write_history_record_filename_is_sortable(tmp_path):
    rec1 = _record(run_id="run-a", generated="2026-06-13T09:00:00Z")
    rec2 = _record(run_id="run-b", generated="2026-06-13T10:00:00Z")

    path1 = write_history_record(rec1, tmp_path)
    path2 = write_history_record(rec2, tmp_path)

    # Lexicographic sort of filenames must equal chronological order
    files = sorted(tmp_path.glob("*.json"))
    assert files[0] == path1
    assert files[1] == path2


def test_write_history_record_creates_history_dir(tmp_path):
    sub = tmp_path / "new_history"
    rec = _record()

    write_history_record(rec, sub)

    assert sub.exists()
    assert list(sub.glob("*.json"))


def test_load_latest_history_record_returns_newest(tmp_path):
    rec1 = _record(run_id="run-a", generated="2026-06-13T09:00:00Z")
    rec2 = _record(run_id="run-b", generated="2026-06-13T10:00:00Z")
    write_history_record(rec1, tmp_path)
    write_history_record(rec2, tmp_path)

    loaded = load_latest_history_record(tmp_path)

    assert loaded["run_id"] == "run-b"


def test_load_latest_history_record_exclude_skips_file(tmp_path):
    rec1 = _record(run_id="run-a", generated="2026-06-13T09:00:00Z")
    rec2 = _record(run_id="run-b", generated="2026-06-13T10:00:00Z")
    write_history_record(rec1, tmp_path)
    path2 = write_history_record(rec2, tmp_path)

    loaded = load_latest_history_record(tmp_path, exclude=path2)

    assert loaded["run_id"] == "run-a"


def test_load_latest_history_record_empty_dir_returns_none(tmp_path):
    assert load_latest_history_record(tmp_path) is None


def test_load_latest_history_record_absent_dir_returns_none(tmp_path):
    absent = tmp_path / "no_such_dir"
    assert load_latest_history_record(absent) is None


# ---------------------------------------------------------------------------
# Baseline error paths
# ---------------------------------------------------------------------------


def test_load_history_record_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_history_record(tmp_path / "missing.json")


def test_load_history_record_invalid_json_raises(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("not json", encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        load_history_record(bad)


def test_load_history_record_incompatible_schema_version_raises(tmp_path):
    bad = tmp_path / "bad_schema.json"
    bad.write_text(json.dumps({"schema_version": 99, "run_id": "x"}), encoding="utf-8")

    with pytest.raises(ValueError, match="schema_version"):
        load_history_record(bad)


def test_load_latest_skips_invalid_and_uses_next_valid(tmp_path, capsys):
    rec_good = _record(run_id="run-a", generated="2026-06-13T09:00:00Z")
    write_history_record(rec_good, tmp_path)

    # Write an invalid file with a later timestamp so it sorts first
    bad_file = tmp_path / "20260613T100000Z__bad-run.json"
    bad_file.write_text("not json", encoding="utf-8")

    loaded = load_latest_history_record(tmp_path)

    assert loaded is not None
    assert loaded["run_id"] == "run-a"
    captured = capsys.readouterr()
    assert "WARNING" in captured.out
    assert "JSONDecodeError" in captured.out


def test_load_latest_all_invalid_returns_none(tmp_path):
    bad = tmp_path / "20260613T100000Z__bad.json"
    bad.write_text("{bad json", encoding="utf-8")

    result = load_latest_history_record(tmp_path)

    assert result is None


# ---------------------------------------------------------------------------
# run_eval integration: --no-history and write-failure (mocked graph)
# ---------------------------------------------------------------------------


def _mock_graph_modules(monkeypatch):
    """Patch sys.modules so run_eval's lazy graph import uses mocks."""
    mock_state = {
        "generation": "Mock answer.",
        "stop_reason": "",
        "retries": 0,
        "llm_call_count": 1,
        "web_search_count": 0,
        "web_result_grading_count": 0,
        "documents": [],
        "web_fallback_policy": "conservative",
    }

    mock_answer = MagicMock()
    mock_answer.raw_state = mock_state

    mock_engine = MagicMock()
    mock_engine.answer_question.return_value = mock_answer
    mock_engine.AnswerOptions = MagicMock(return_value=None)

    mock_formatting = MagicMock()
    mock_formatting.format_answer.return_value = "Mock answer."

    monkeypatch.setitem(sys.modules, "graph.engine", mock_engine)
    monkeypatch.setitem(sys.modules, "graph.formatting", mock_formatting)

    return mock_engine


def _minimal_rows():
    return [
        {
            "id": "r1",
            "category": "local_corpus",
            "question": "Test question?",
            "web_search_enabled": False,
            "expected_behavior": "answers",
        }
    ]


def test_no_history_skips_write_but_renders_delta(tmp_path, monkeypatch):
    _mock_graph_modules(monkeypatch)

    # Seed a baseline so the delta section has content
    baseline = _record(
        run_id="baseline",
        generated="2026-06-13T09:00:00Z",
        rows=[_row_entry("r1")],
        passed=1,
        total=1,
    )
    write_history_record(baseline, tmp_path / "history")

    output_path = tmp_path / "report.md"
    run_eval(
        _minimal_rows(),
        str(output_path),
        "evals/questions.jsonl",
        history_dir=str(tmp_path / "history"),
        no_history=True,
    )

    # No new record should have been written (only the pre-seeded baseline)
    history_files = list((tmp_path / "history").glob("*.json"))
    assert len(history_files) == 1
    assert history_files[0].stem.endswith("baseline")

    # Report must still contain the delta section
    report = output_path.read_text(encoding="utf-8")
    assert "## Delta vs. previous run" in report


def test_no_history_no_baseline_renders_no_previous_run(tmp_path, monkeypatch):
    _mock_graph_modules(monkeypatch)
    output_path = tmp_path / "report.md"
    empty_history = tmp_path / "history"
    empty_history.mkdir()

    run_eval(
        _minimal_rows(),
        str(output_path),
        "evals/questions.jsonl",
        history_dir=str(empty_history),
        no_history=True,
    )

    report = output_path.read_text(encoding="utf-8")
    assert "No previous run found" in report
    assert not list(empty_history.glob("*.json"))


def test_history_write_failure_still_produces_valid_report(tmp_path, monkeypatch, capsys):
    _mock_graph_modules(monkeypatch)
    output_path = tmp_path / "report.md"

    def _fail_write(record, history_dir):
        raise OSError("disk full")

    monkeypatch.setattr("evals.run_eval.write_history_record", _fail_write)

    run_eval(
        _minimal_rows(),
        str(output_path),
        "evals/questions.jsonl",
        history_dir=str(tmp_path / "history"),
    )

    assert output_path.exists()
    report = output_path.read_text(encoding="utf-8")
    assert "# Eval results" in report

    captured = capsys.readouterr()
    assert "WARNING" in captured.out
    assert "OSError" in captured.out


def test_history_written_on_normal_run(tmp_path, monkeypatch):
    _mock_graph_modules(monkeypatch)
    output_path = tmp_path / "report.md"
    history_dir = tmp_path / "history"

    run_eval(
        _minimal_rows(),
        str(output_path),
        "evals/questions.jsonl",
        history_dir=str(history_dir),
    )

    written = list(history_dir.glob("*.json"))
    assert len(written) == 1
    rec = json.loads(written[0].read_text(encoding="utf-8"))
    assert rec["schema_version"] == 1
    assert "answer" not in rec["rows"][0]
    assert "formatted_answer" not in rec["rows"][0]


def test_explicit_baseline_missing_raises_history_baseline_error(tmp_path, monkeypatch):
    _mock_graph_modules(monkeypatch)
    output_path = tmp_path / "report.md"

    with pytest.raises(HistoryBaselineError):
        run_eval(
            _minimal_rows(),
            str(output_path),
            "evals/questions.jsonl",
            history_dir=str(tmp_path / "history"),
            baseline=str(tmp_path / "nonexistent.json"),
        )


def test_explicit_baseline_invalid_json_raises_history_baseline_error(tmp_path, monkeypatch):
    _mock_graph_modules(monkeypatch)
    bad = tmp_path / "bad.json"
    bad.write_text("not json", encoding="utf-8")
    output_path = tmp_path / "report.md"

    with pytest.raises(HistoryBaselineError):
        run_eval(
            _minimal_rows(),
            str(output_path),
            "evals/questions.jsonl",
            history_dir=str(tmp_path / "history"),
            baseline=str(bad),
        )


def test_explicit_baseline_incompatible_schema_raises_history_baseline_error(tmp_path, monkeypatch):
    _mock_graph_modules(monkeypatch)
    bad = tmp_path / "bad_schema.json"
    bad.write_text(json.dumps({"schema_version": 99, "run_id": "x"}), encoding="utf-8")
    output_path = tmp_path / "report.md"

    with pytest.raises(HistoryBaselineError, match="schema_version"):
        run_eval(
            _minimal_rows(),
            str(output_path),
            "evals/questions.jsonl",
            history_dir=str(tmp_path / "history"),
            baseline=str(bad),
        )
