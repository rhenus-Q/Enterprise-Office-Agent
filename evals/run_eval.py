"""
run_eval.py — lightweight behavioral evaluation harness.

Runs the eval dataset (evals/questions.jsonl) through the compiled graph and
checks *behavior*, not just code paths: did local questions answer from the
corpus, did out-of-corpus questions fall back to the web, did unanswerable
questions decline instead of fabricating, and did privacy-mode rows trigger
zero web searches.

All checks are deterministic (stop_reason, source metadata, counters,
expected substrings) — no LLM-as-judge.

Usage:
    uv run python evals/run_eval.py                  # full eval (REAL API calls)
    uv run python evals/run_eval.py --limit 3        # first N rows only
    uv run python evals/run_eval.py --output path.md # custom report path
    uv run python evals/run_eval.py --validate-only  # dataset checks, no API calls

NOT part of CI: the full run drives the real router/graders/generation
(OpenAI) and possibly Tavily, so it needs API keys, costs money, and is
nondeterministic. Run it deliberately. --validate-only is always safe.
"""

import argparse
import json
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

# Make project-root imports (graph.*, main) work when invoked as
# `python evals/run_eval.py` from anywhere.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from graph.consts import WEB_SEARCH_SOURCE  # noqa: E402  (pure constants, side-effect-free)
from graph.config import (  # noqa: E402  (pure env helpers, side-effect-free)
    WEB_FALLBACK_AGGRESSIVE,
    WEB_FALLBACK_CONSERVATIVE,
    WEB_FALLBACK_DISABLED,
)

DEFAULT_DATASET = Path(__file__).parent / "questions.jsonl"
DEFAULT_OUTPUT = Path(__file__).parent / "results.md"

CATEGORIES = ("local_corpus", "web_fallback", "insufficient_context", "privacy_mode")
REQUIRED_FIELDS = ("id", "category", "question", "web_search_enabled", "expected_behavior")
SOURCE_TYPES = ("local_corpus", "web", "none")
WEB_FALLBACK_POLICIES = (
    WEB_FALLBACK_CONSERVATIVE,
    WEB_FALLBACK_AGGRESSIVE,
    WEB_FALLBACK_DISABLED,
)

# Substring marking a non-confident answer. Matches the graph's deterministic
# insufficient-context answer and the usual phrasing of an honest decline.
INSUFFICIENT_MARKER = "do not have enough information"

# Unicode dash/hyphen variants normalized to ASCII "-" before substring
# checks: models routinely emit typographic hyphens (e.g. "Sev‑1" with a
# U+2011 non-breaking hyphen) for content the dataset spells in ASCII, which
# must not fail an otherwise-correct answer.
_DASH_VARIANTS = (
    "‐"  # hyphen
    "‑"  # non-breaking hyphen
    "‒"  # figure dash
    "–"  # en dash
    "—"  # em dash
    "−"  # minus sign
    "﹘"  # small em dash
    "﹣"  # small hyphen-minus
    "－"  # fullwidth hyphen-minus
)
_DASH_TRANSLATION = str.maketrans({c: "-" for c in _DASH_VARIANTS})


def normalize_for_contains(text):
    """
    Normalize text for expected_contains matching: NFKC Unicode
    normalization, common dash/hyphen variants folded to ASCII "-",
    whitespace runs (including line breaks) collapsed to single spaces, and
    casefold for case-insensitive comparison. This makes the check robust to
    typographic variation while staying strict about actual content.
    """

    normalized = unicodedata.normalize("NFKC", str(text))
    normalized = normalized.translate(_DASH_TRANSLATION)
    normalized = " ".join(normalized.split())
    return normalized.casefold()


# ---------------------------------------------------------------------------
# Dataset loading and validation (safe: no graph, no API)
# ---------------------------------------------------------------------------


def load_dataset(path):
    """Parse a JSONL file into a list of row dicts (blank lines skipped)."""

    rows = []
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"line {line_number}: invalid JSON ({exc})") from exc
    return rows


def validate_dataset(rows):
    """Return a list of human-readable problems ([] = dataset is valid)."""

    errors = []
    seen_ids = set()

    for index, row in enumerate(rows):
        label = f"row {index}"
        if not isinstance(row, dict):
            errors.append(f"{label}: not a JSON object")
            continue
        label = f"row {index} ({row.get('id', '?')})"

        for field in REQUIRED_FIELDS:
            if field not in row:
                errors.append(f"{label}: missing required field '{field}'")

        row_id = row.get("id")
        if row_id in seen_ids:
            errors.append(f"{label}: duplicate id")
        seen_ids.add(row_id)

        if "category" in row and row["category"] not in CATEGORIES:
            errors.append(f"{label}: invalid category {row['category']!r}")
        if "question" in row and not (isinstance(row["question"], str) and row["question"].strip()):
            errors.append(f"{label}: question must be a non-empty string")
        if "web_search_enabled" in row and not isinstance(row["web_search_enabled"], bool):
            errors.append(f"{label}: web_search_enabled must be a boolean")

        expected_stop = row.get("expected_stop_reason")
        if expected_stop is not None and not (
            isinstance(expected_stop, str)
            or (isinstance(expected_stop, list) and all(isinstance(s, str) for s in expected_stop))
        ):
            errors.append(f"{label}: expected_stop_reason must be null, a string, or a list of strings")

        expected_source = row.get("expected_source_type")
        if expected_source is not None and expected_source not in SOURCE_TYPES:
            errors.append(f"{label}: expected_source_type must be null or one of {SOURCE_TYPES}")

        # Optional per-row fallback-policy override (existing rows omit it).
        policy = row.get("web_fallback_policy")
        if policy is not None and policy not in WEB_FALLBACK_POLICIES:
            errors.append(
                f"{label}: web_fallback_policy must be null or one of {WEB_FALLBACK_POLICIES}"
            )

        contains = row.get("expected_contains")
        if contains is not None and not (
            isinstance(contains, list) and all(isinstance(s, str) for s in contains)
        ):
            errors.append(f"{label}: expected_contains must be a list of strings")

    return errors


# ---------------------------------------------------------------------------
# Result summarization and per-row checks (pure: unit-testable without APIs)
# ---------------------------------------------------------------------------


def summarize_result(result, formatted_answer):
    """Reduce a final graph state to the fields the checks need."""

    documents = result.get("documents") or []
    web_source_used = any(
        (getattr(doc, "metadata", None) or {}).get("source") == WEB_SEARCH_SOURCE
        for doc in documents
    )
    local_source_used = any(
        (getattr(doc, "metadata", None) or {}).get("source") != WEB_SEARCH_SOURCE
        for doc in documents
    )

    return {
        "answer": result.get("generation", ""),
        "formatted_answer": formatted_answer,
        "stop_reason": result.get("stop_reason", ""),
        "retries": result.get("retries", 0),
        "llm_call_count": result.get("llm_call_count", 0),
        "web_search_count": result.get("web_search_count", 0),
        "web_result_grading_count": result.get("web_result_grading_count", 0),
        "sources_shown": bool(documents),
        "local_source_used": local_source_used,
        "web_source_used": web_source_used,
    }


def evaluate_row(row, summary):
    """
    Apply every deterministic check that applies to this row.

    Returns {"checks": {name: bool}, "passed": bool} — a row passes when all
    of its applicable checks pass.
    """

    checks = {}

    expected_stop = row.get("expected_stop_reason")
    if expected_stop is not None:
        allowed = [expected_stop] if isinstance(expected_stop, str) else list(expected_stop)
        checks["stop_reason"] = summary["stop_reason"] in allowed

    expected_source = row.get("expected_source_type")
    if expected_source is not None:
        checks["source_type"] = {
            "local_corpus": summary["local_source_used"],
            "web": summary["web_source_used"],
            "none": not summary["sources_shown"],
        }[expected_source]

    contains = row.get("expected_contains") or []
    if contains:
        text = normalize_for_contains(summary["formatted_answer"])
        checks["expected_contains"] = all(
            normalize_for_contains(needle) in text for needle in contains
        )

    # Hard privacy guarantee: a disabled-web row must never search the web.
    if not row["web_search_enabled"]:
        checks["privacy_no_web_search"] = summary["web_search_count"] == 0

    category = row["category"]
    if category == "web_fallback":
        checks["web_fallback_used"] = summary["web_source_used"] and summary["web_search_count"] >= 1
    if category == "insufficient_context":
        # The system must not answer confidently: either it says it lacks the
        # information, or the run ended with an explicit stop-reason caveat.
        declined = INSUFFICIENT_MARKER in summary["answer"].lower()
        checks["declined_or_caveated"] = declined or summary["stop_reason"] != ""

    return {"checks": checks, "passed": all(checks.values())}


def compute_metrics(evaluated):
    """Aggregate per-row evaluations into the summary metrics."""

    total = len(evaluated)

    def category_counts(category):
        rows = [e for e in evaluated if e["row"]["category"] == category]
        return sum(1 for e in rows if e["passed"]), len(rows)

    def check_counts(check_name):
        rows = [e for e in evaluated if check_name in e["checks"]]
        return sum(1 for e in rows if e["checks"][check_name]), len(rows)

    retries = [e["summary"]["retries"] for e in evaluated]
    llm_calls = [e["summary"]["llm_call_count"] for e in evaluated]

    return {
        "total": total,
        "passed": sum(1 for e in evaluated if e["passed"]),
        "local_answerable_passed": category_counts("local_corpus"),
        "web_fallback_passed": category_counts("web_fallback"),
        "insufficient_context_passed": category_counts("insufficient_context"),
        "privacy_mode_passed": category_counts("privacy_mode"),
        "stop_reason_matches": check_counts("stop_reason"),
        "source_type_matches": check_counts("source_type"),
        "expected_contains_matches": check_counts("expected_contains"),
        "average_retries": round(sum(retries) / total, 2) if total else 0.0,
        "average_llm_calls": round(sum(llm_calls) / total, 2) if total else 0.0,
        "total_web_searches": sum(e["summary"]["web_search_count"] for e in evaluated),
    }


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def _table_cell(text, limit=200):
    """Single-line, pipe-safe, truncated cell content for the Markdown report."""

    flattened = " ".join(str(text).split()).replace("|", "\\|")
    return flattened[:limit] + ("…" if len(flattened) > limit else "")


def render_markdown(evaluated, metrics, dataset_path):
    """Render the full eval report as Markdown."""

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Eval results",
        "",
        f"- Generated: {timestamp}",
        f"- Dataset: `{dataset_path}`",
        f"- Rows evaluated: {metrics['total']}",
        "",
        "## Metrics",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Overall passed | {metrics['passed']} / {metrics['total']} |",
        f"| local_corpus passed | {metrics['local_answerable_passed'][0]} / {metrics['local_answerable_passed'][1]} |",
        f"| web_fallback passed | {metrics['web_fallback_passed'][0]} / {metrics['web_fallback_passed'][1]} |",
        f"| insufficient_context passed | {metrics['insufficient_context_passed'][0]} / {metrics['insufficient_context_passed'][1]} |",
        f"| privacy_mode passed | {metrics['privacy_mode_passed'][0]} / {metrics['privacy_mode_passed'][1]} |",
        f"| stop_reason matches | {metrics['stop_reason_matches'][0]} / {metrics['stop_reason_matches'][1]} |",
        f"| source_type matches | {metrics['source_type_matches'][0]} / {metrics['source_type_matches'][1]} |",
        f"| expected_contains matches | {metrics['expected_contains_matches'][0]} / {metrics['expected_contains_matches'][1]} |",
        f"| Average retries | {metrics['average_retries']} |",
        f"| Average tracked LLM calls | {metrics['average_llm_calls']} |",
        f"| Total web searches | {metrics['total_web_searches']} |",
        "",
        "Tracked LLM calls are the graph's budgeted operational counter "
        "(generations, query rewrites, web-result grades). Router and grader "
        "calls are not individually tracked, so this is not total LLM usage "
        "and not billing-accurate cost accounting.",
        "",
        "## Per-question results",
        "",
        "| id | category | passed | stop_reason | retries | tracked llm | web | failed checks |",
        "|---|---|---|---|---|---|---|---|",
    ]

    for entry in evaluated:
        row, summary = entry["row"], entry["summary"]
        failed = ", ".join(name for name, ok in entry["checks"].items() if not ok) or "—"
        lines.append(
            f"| {row['id']} | {row['category']} | {'PASS' if entry['passed'] else 'FAIL'} "
            f"| {summary['stop_reason'] or '—'} | {summary['retries']} "
            f"| {summary['llm_call_count']} | {summary['web_search_count']} | {failed} |"
        )

    lines += ["", "## Answers (truncated)", ""]
    for entry in evaluated:
        row, summary = entry["row"], entry["summary"]
        lines += [
            f"### {row['id']}",
            "",
            f"**Q:** {_table_cell(row['question'])}",
            "",
            f"**A:** {_table_cell(summary['formatted_answer'], limit=400)}",
            "",
        ]

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def run_eval(rows, output_path, dataset_path):
    """Run rows through the real graph (REAL API calls) and write the report."""

    # Imported here so --validate-only never touches the graph. State seeding
    # and per-run config resolution live in the engine (graph/engine.py) —
    # the same entry point main.py uses — so the harness never mutates env.
    from graph.engine import AnswerOptions, answer_question
    from graph.formatting import format_answer

    evaluated = []
    for index, row in enumerate(rows, 1):
        print(f"[{index}/{len(rows)}] {row['id']} ({row['category']}) ...")
        try:
            answer = answer_question(
                row["question"],
                AnswerOptions(
                    web_search_enabled=row["web_search_enabled"],
                    web_fallback_policy=row.get("web_fallback_policy"),
                ),
            )
            result = answer.raw_state
            summary = summarize_result(result, format_answer(result))
            entry = {"row": row, "summary": summary, **evaluate_row(row, summary)}
        except Exception as exc:
            # One broken row must not kill the eval; record it as a failure.
            print(f"    ERROR: {type(exc).__name__}")
            summary = summarize_result({}, "")
            entry = {"row": row, "summary": summary, "checks": {"run_completed": False}, "passed": False}
        evaluated.append(entry)

    metrics = compute_metrics(evaluated)
    Path(output_path).write_text(render_markdown(evaluated, metrics, dataset_path), encoding="utf-8")

    print()
    print(f"Overall: {metrics['passed']}/{metrics['total']} passed")
    for key in ("local_answerable_passed", "web_fallback_passed",
                "insufficient_context_passed", "privacy_mode_passed"):
        passed, total = metrics[key]
        print(f"  {key}: {passed}/{total}")
    print(f"  average retries: {metrics['average_retries']}, "
          f"average tracked LLM calls: {metrics['average_llm_calls']}, "
          f"total web searches: {metrics['total_web_searches']}")
    print(f"Report written to {output_path}")
    return metrics


def main(argv=None):
    parser = argparse.ArgumentParser(description="Behavioral eval harness for the Agentic RAG graph.")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET), help="Path to the JSONL dataset.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Markdown report path.")
    parser.add_argument("--limit", type=int, default=None, help="Run only the first N rows.")
    parser.add_argument("--validate-only", action="store_true",
                        help="Validate the dataset format and exit (no API calls).")
    args = parser.parse_args(argv)

    rows = load_dataset(args.dataset)
    errors = validate_dataset(rows)
    if errors:
        print(f"Dataset INVALID ({len(errors)} problem(s)):")
        for error in errors:
            print(f"  - {error}")
        return 1

    if args.validate_only:
        counts = {c: sum(1 for r in rows if r["category"] == c) for c in CATEGORIES}
        print(f"Dataset OK: {len(rows)} rows " + ", ".join(f"{c}={n}" for c, n in counts.items()))
        return 0

    if args.limit is not None:
        rows = rows[: args.limit]

    run_eval(rows, args.output, args.dataset)
    return 0


if __name__ == "__main__":
    sys.exit(main())
