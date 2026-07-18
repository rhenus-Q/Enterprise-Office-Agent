"""
run_eval.py — lightweight behavioral evaluation harness.

Runs the eval dataset (evals/enterprise_rag/questions.jsonl) through the compiled
graph and checks *behavior*, not just code paths: did local questions answer from
the corpus, did out-of-corpus questions fall back to the web, did unanswerable
questions decline instead of fabricating, and did privacy-mode rows trigger
zero web searches.

All checks are deterministic (stop_reason, source metadata, counters,
expected substrings) — no LLM-as-judge.

Usage:
    uv run python evals/enterprise_rag/run_eval.py                  # full eval (REAL API calls)
    uv run python evals/enterprise_rag/run_eval.py --limit 3        # first N rows only
    uv run python evals/enterprise_rag/run_eval.py --output path.md # custom report path
    uv run python evals/enterprise_rag/run_eval.py --validate-only  # dataset checks, no API calls
    uv run python evals/enterprise_rag/run_eval.py --no-history     # skip writing history record
    uv run python evals/enterprise_rag/run_eval.py --baseline evals/enterprise_rag/history/<file>.json

NOT part of CI: the full run drives the real router/graders/generation
(OpenAI) and possibly Tavily, so it needs API keys, costs money, and is
nondeterministic. Run it deliberately. --validate-only is always safe.
"""

import argparse
import hashlib
import json
import sys
import unicodedata
import uuid
from datetime import UTC, datetime
from pathlib import Path

# Make project-root imports (enterprise_rag.*, main) work when invoked as
# `python evals/enterprise_rag/run_eval.py` from anywhere.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from enterprise_rag.graph.config import (
    WEB_FALLBACK_AGGRESSIVE,
    WEB_FALLBACK_CONSERVATIVE,
    WEB_FALLBACK_DISABLED,
    offline_mode,
)
from enterprise_rag.graph.consts import WEB_SEARCH_SOURCE
from enterprise_rag.runtime_privacy import enforce_tracing_privacy

# Exit code for a run refused by configuration (distinct from 1 = eval problems),
# matching the office assist runners' "invalid run" convention.
EXIT_INVALID_RUN = 2

DEFAULT_DATASET = Path(__file__).parent / "questions.jsonl"
DEFAULT_OUTPUT = Path(__file__).parent / "results.md"
DEFAULT_HISTORY_DIR = Path(__file__).parent / "history"

CATEGORIES = (
    "local_corpus",
    "web_fallback",
    "insufficient_context",
    "privacy_mode",
    "multi_document",
    "policy_fallback",
)
CATEGORY_METRIC_KEYS = {
    "local_corpus": "local_answerable_passed",
    "web_fallback": "web_fallback_passed",
    "insufficient_context": "insufficient_context_passed",
    "privacy_mode": "privacy_mode_passed",
    "multi_document": "multi_document_passed",
    "policy_fallback": "policy_fallback_passed",
}
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


class HistoryBaselineError(Exception):
    """Raised when an explicit --baseline file is missing, invalid, or incompatible."""


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


def _valid_expected_contains_item(item):
    if isinstance(item, str):
        return bool(item)
    if isinstance(item, list):
        return bool(item) and all(isinstance(s, str) and bool(s) for s in item)
    return False


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
            errors.append(
                f"{label}: expected_stop_reason must be null, a string, or a list of strings"
            )

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
            isinstance(contains, list)
            and all(_valid_expected_contains_item(item) for item in contains)
        ):
            errors.append(
                f"{label}: expected_contains must be a list of non-empty strings or non-empty string groups"
            )

        not_contains = row.get("expected_not_contains")
        if not_contains is not None and not (
            isinstance(not_contains, list) and all(isinstance(s, str) and s for s in not_contains)
        ):
            errors.append(f"{label}: expected_not_contains must be a list of non-empty strings")

        expected_titles = row.get("expected_source_titles")
        if expected_titles is not None and not (
            isinstance(expected_titles, list)
            and all(isinstance(title, str) for title in expected_titles)
        ):
            errors.append(f"{label}: expected_source_titles must be a list of strings")

        min_local_sources = row.get("expected_min_local_sources")
        if min_local_sources is not None and (
            isinstance(min_local_sources, bool)
            or not isinstance(min_local_sources, int)
            or min_local_sources <= 0
        ):
            errors.append(f"{label}: expected_min_local_sources must be a positive integer")

        web_search_count = row.get("expected_web_search_count")
        if web_search_count is not None and not _valid_web_search_count_expectation(
            web_search_count
        ):
            errors.append(
                f"{label}: expected_web_search_count must be an integer >= 0 "
                'or an object with integer "min" / "max" values'
            )

    return errors


def _valid_web_search_count_expectation(value):
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return value >= 0
    if not isinstance(value, dict):
        return False

    allowed_keys = {"min", "max"}
    if not value or any(key not in allowed_keys for key in value):
        return False

    for count in value.values():
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            return False

    if "min" in value and "max" in value and value["min"] > value["max"]:
        return False

    return True


# ---------------------------------------------------------------------------
# Result summarization and per-row checks (pure: unit-testable without APIs)
# ---------------------------------------------------------------------------


def summarize_result(result, formatted_answer):
    """Reduce a final graph state to the fields the checks need."""

    documents = result.get("documents") or []
    local_source_titles = []
    seen_local_titles = set()
    for doc in documents:
        metadata = getattr(doc, "metadata", None) or {}
        if metadata.get("source") == WEB_SEARCH_SOURCE:
            continue
        title = str(metadata.get("title") or "").strip()
        if title and title not in seen_local_titles:
            seen_local_titles.add(title)
            local_source_titles.append(title)

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
        "local_source_titles": local_source_titles,
        "web_fallback_policy": result.get("web_fallback_policy", ""),
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
            normalize_for_contains(item) in text
            if isinstance(item, str)
            else any(normalize_for_contains(s) in text for s in item)
            for item in contains
        )

    not_contains = row.get("expected_not_contains") or []
    if not_contains:
        text = normalize_for_contains(summary["formatted_answer"])
        checks["expected_not_contains"] = all(
            normalize_for_contains(needle) not in text for needle in not_contains
        )

    expected_titles = row.get("expected_source_titles") or []
    if expected_titles:
        local_titles = summary["local_source_titles"]
        checks["source_titles"] = all(title in local_titles for title in expected_titles)

    expected_min_local = row.get("expected_min_local_sources")
    if expected_min_local is not None:
        checks["min_local_sources"] = len(summary["local_source_titles"]) >= expected_min_local

    expected_web_count = row.get("expected_web_search_count")
    if expected_web_count is not None:
        actual_web_count = summary["web_search_count"]
        if isinstance(expected_web_count, int):
            checks["web_search_count"] = actual_web_count == expected_web_count
        else:
            min_ok = (
                "min" not in expected_web_count or actual_web_count >= expected_web_count["min"]
            )
            max_ok = (
                "max" not in expected_web_count or actual_web_count <= expected_web_count["max"]
            )
            checks["web_search_count"] = min_ok and max_ok

    if row.get("web_fallback_policy") is not None:
        checks["policy_applied"] = summary["web_fallback_policy"] == row["web_fallback_policy"]

    # Hard privacy guarantee: a disabled-web row must never search the web.
    if not row["web_search_enabled"]:
        checks["privacy_no_web_search"] = summary["web_search_count"] == 0

    category = row["category"]
    if category == "web_fallback":
        checks["web_fallback_used"] = (
            summary["web_source_used"] and summary["web_search_count"] >= 1
        )
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

    metrics = {
        "total": total,
        "passed": sum(1 for e in evaluated if e["passed"]),
        "stop_reason_matches": check_counts("stop_reason"),
        "source_type_matches": check_counts("source_type"),
        "expected_contains_matches": check_counts("expected_contains"),
        "expected_not_contains_matches": check_counts("expected_not_contains"),
        "source_titles_matches": check_counts("source_titles"),
        "min_local_sources_matches": check_counts("min_local_sources"),
        "web_search_count_matches": check_counts("web_search_count"),
        "policy_applied_matches": check_counts("policy_applied"),
        "average_retries": round(sum(retries) / total, 2) if total else 0.0,
        "average_llm_calls": round(sum(llm_calls) / total, 2) if total else 0.0,
        "total_web_searches": sum(e["summary"]["web_search_count"] for e in evaluated),
    }
    for category, metric_key in CATEGORY_METRIC_KEYS.items():
        metrics[metric_key] = category_counts(category)

    return metrics


# ---------------------------------------------------------------------------
# History and delta (pure helpers — no file I/O)
# ---------------------------------------------------------------------------


def read_dataset_content(path):
    """Read raw bytes from path. Thin I/O wrapper that feeds dataset_fingerprint."""
    return Path(path).read_bytes()


def dataset_fingerprint(rows, dataset_content):
    """Pure: compute a fingerprint from already-loaded rows and raw dataset bytes.

    dataset_content must be bytes. The SHA-256 covers file content so edits that
    leave ids unchanged still change the hash. No file I/O is performed here.
    """
    ids = [row.get("id") for row in rows]
    sha = hashlib.sha256(dataset_content).hexdigest()
    return {"row_count": len(rows), "ids": ids, "dataset_sha256": sha}


def build_history_record(evaluated, metrics, dataset_path, fingerprint, *, timestamp, run_id):
    """Pure: build a metadata-only, JSON-serializable history record.

    Never stores answer text, page_content, prompts, or raw graph state.
    The caller supplies the already-built fingerprint dict.
    """
    rows = []
    for entry in evaluated:
        row = entry["row"]
        checks = entry.get("checks", {})
        failed_checks = [name for name, ok in checks.items() if not ok]
        summary = entry.get("summary", {})
        rows.append(
            {
                "id": row.get("id"),
                "category": row.get("category"),
                "passed": bool(entry["passed"]),
                "failed_checks": failed_checks,
                "stop_reason": summary.get("stop_reason", ""),
                "retries": summary.get("retries", 0),
                "llm_call_count": summary.get("llm_call_count", 0),
                "web_search_count": summary.get("web_search_count", 0),
            }
        )
    return {
        "schema_version": 1,
        "run_id": run_id,
        "generated": timestamp,
        "dataset": str(dataset_path),
        "dataset_fingerprint": fingerprint,
        "metrics": metrics,
        "rows": rows,
    }


def _as_pair(value):
    """Normalize a (passed, total) tuple or [passed, total] list to (int, int).

    compute_metrics emits tuples; JSON round-trips them to lists. Both forms
    must be treated equivalently by compute_delta.
    """
    if isinstance(value, (tuple, list)) and len(value) == 2:
        return int(value[0]), int(value[1])
    return 0, 0


def compute_delta(baseline_record, current_record):
    """Pure: compute run-over-run differences between two history records."""
    b_fp = baseline_record.get("dataset_fingerprint", {})
    c_fp = current_record.get("dataset_fingerprint", {})

    dataset_changed = (
        b_fp.get("row_count") != c_fp.get("row_count")
        or b_fp.get("ids") != c_fp.get("ids")
        or b_fp.get("dataset_sha256") != c_fp.get("dataset_sha256")
    )

    b_metrics = baseline_record.get("metrics", {})
    c_metrics = current_record.get("metrics", {})

    b_passed = b_metrics.get("passed", 0)
    c_passed = c_metrics.get("passed", 0)
    b_total = b_metrics.get("total", 0)
    c_total = c_metrics.get("total", 0)
    overall = {
        "passed": (b_passed, c_passed, c_passed - b_passed),
        "total": (b_total, c_total, c_total - b_total),
    }

    categories = {}
    for cat_key in CATEGORY_METRIC_KEYS.values():
        b_p, _b_t = _as_pair(b_metrics.get(cat_key, (0, 0)))
        c_p, _c_t = _as_pair(c_metrics.get(cat_key, (0, 0)))
        categories[cat_key] = (b_p, c_p, c_p - b_p)

    check_keys = (
        "stop_reason_matches",
        "source_type_matches",
        "expected_contains_matches",
        "expected_not_contains_matches",
        "source_titles_matches",
        "min_local_sources_matches",
        "web_search_count_matches",
        "policy_applied_matches",
    )
    checks = {}
    for check_key in check_keys:
        b_p, _b_t = _as_pair(b_metrics.get(check_key, (0, 0)))
        c_p, _c_t = _as_pair(c_metrics.get(check_key, (0, 0)))
        checks[check_key] = (b_p, c_p, c_p - b_p)

    b_rows = {r["id"]: r for r in baseline_record.get("rows", [])}
    c_rows = {r["id"]: r for r in current_record.get("rows", [])}
    b_ids = set(b_rows)
    c_ids = set(c_rows)
    common = b_ids & c_ids

    return {
        "baseline_run_id": baseline_record.get("run_id"),
        "baseline_generated": baseline_record.get("generated"),
        "dataset_changed": dataset_changed,
        "overall": overall,
        "categories": categories,
        "checks": checks,
        "rows": {
            "newly_passing": sorted(
                rid for rid in common if not b_rows[rid]["passed"] and c_rows[rid]["passed"]
            ),
            "newly_failing": sorted(
                rid for rid in common if b_rows[rid]["passed"] and not c_rows[rid]["passed"]
            ),
            "still_failing": sorted(
                rid for rid in common if not b_rows[rid]["passed"] and not c_rows[rid]["passed"]
            ),
            "added": sorted(c_ids - b_ids),
            "removed": sorted(b_ids - c_ids),
        },
    }


def render_delta_section(delta):
    """Pure: render a 'Delta vs. previous run' Markdown section as a list of lines.

    Pass delta=None for the no-baseline (first-run) case.
    """
    if delta is None:
        return [
            "## Delta vs. previous run",
            "",
            "No previous run found — this is the first recorded run.",
            "",
        ]

    lines = [
        "## Delta vs. previous run",
        "",
        f"Baseline: `{delta['baseline_run_id']}` — {delta['baseline_generated']}",
        "",
    ]

    if delta["dataset_changed"]:
        lines += [
            "> **Warning:** the dataset fingerprint changed between runs. Aggregate",
            "> deltas mix dataset changes with behavior changes and may be misleading.",
            "",
        ]

    o = delta["overall"]
    b_p, c_p, d_p = o["passed"]
    b_t, c_t, d_t = o["total"]
    sign_p = "+" if d_p >= 0 else ""
    sign_t = "+" if d_t >= 0 else ""
    lines += [
        "### Overall",
        "",
        "| Metric | Baseline | Current | Delta |",
        "|---|---|---|---|",
        f"| Overall passed | {b_p} | {c_p} | {sign_p}{d_p} |",
        f"| Total rows | {b_t} | {c_t} | {sign_t}{d_t} |",
        "",
        "### Categories",
        "",
        "| Category | Baseline passed | Current passed | Delta |",
        "|---|---|---|---|",
    ]
    for cat_key, (b_v, c_v, d_v) in delta["categories"].items():
        sign = "+" if d_v >= 0 else ""
        lines.append(f"| {cat_key} | {b_v} | {c_v} | {sign}{d_v} |")
    lines += [
        "",
        "### Checks",
        "",
        "| Check | Baseline matches | Current matches | Delta |",
        "|---|---|---|---|",
    ]
    for check_key, (b_v, c_v, d_v) in delta["checks"].items():
        sign = "+" if d_v >= 0 else ""
        lines.append(f"| {check_key} | {b_v} | {c_v} | {sign}{d_v} |")

    rows = delta["rows"]

    def _ids_line(ids, label):
        if ids:
            return [f"**{label}:** " + ", ".join(f"`{r}`" for r in ids), ""]
        return [f"**{label}:** (none)", ""]

    lines += ["", "### Row transitions", ""]
    lines += _ids_line(rows["newly_passing"], "Newly passing")
    lines += _ids_line(rows["newly_failing"], "Newly failing")
    lines += _ids_line(rows["still_failing"], "Still failing")
    lines += _ids_line(rows["added"], "Added rows")
    lines += _ids_line(rows["removed"], "Removed rows")

    return lines


# ---------------------------------------------------------------------------
# History I/O (thin wrappers — separated from pure logic above)
# ---------------------------------------------------------------------------


def write_history_record(record, history_dir):
    """Write a history record as UTF-8 JSON to history_dir. Returns the Path written.

    Filename is derived from the ISO-8601 generated timestamp + run_id so that
    lexicographic sort equals chronological sort, e.g.
    "20260613T141005Z__<run_id>.json".
    """
    history_dir = Path(history_dir)
    history_dir.mkdir(parents=True, exist_ok=True)
    stamp = record["generated"].replace("-", "").replace(":", "")
    path = history_dir / f"{stamp}__{record['run_id']}.json"
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return path


def load_history_record(path):
    """Load and return a history record dict. Raises on missing/invalid/incompatible."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise ValueError(f"Incompatible schema_version {data.get('schema_version')!r} in {path}")
    return data


def load_latest_history_record(history_dir, *, exclude=None):
    """Return the latest valid history record in history_dir, or None.

    Iterates candidates newest-first (lexicographic filename == chronological order).
    Skips unreadable, invalid-JSON, or schema-incompatible files with a type-only
    warning. The exclude path (if given) is skipped — used to prevent a freshly
    written record from being its own baseline.
    """
    history_dir = Path(history_dir)
    if not history_dir.exists():
        return None
    candidates = sorted(history_dir.glob("*.json"), reverse=True)
    exclude_path = Path(exclude).resolve() if exclude is not None else None
    for candidate in candidates:
        if exclude_path is not None and candidate.resolve() == exclude_path:
            continue
        try:
            return load_history_record(candidate)
        except Exception as exc:
            print(f"  WARNING: skipping history record {candidate.name} ({type(exc).__name__})")
    return None


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def _table_cell(text, limit=200):
    """Single-line, pipe-safe, truncated cell content for the Markdown report."""

    flattened = " ".join(str(text).split()).replace("|", "\\|")
    return flattened[:limit] + ("…" if len(flattened) > limit else "")


def render_markdown(
    evaluated, metrics, dataset_path, *, delta_lines=None, include_answer_text=True
):
    """Render the full eval report as Markdown.

    When delta_lines is provided (a list of strings from render_delta_section),
    the delta section is inserted after the Metrics section. When None, the
    output is byte-identical to the pre-history format.

    include_answer_text: when True (default) the per-question section renders the
    truncated user question and formatted answer, as before. When False (privacy
    mode, `--no-answer-text`) that section renders only a placeholder note — no
    question text and no generated/formatted answer text reach the Markdown. The
    metadata sections are unchanged in both modes: the Metrics table, the delta
    section, and the per-question results table (row ids, pass/fail, stop
    reasons, counters, and failed-check names) carry no answer content, so
    disabling answer text never removes per-row status.
    """

    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
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
        f"| multi_document passed | {metrics['multi_document_passed'][0]} / {metrics['multi_document_passed'][1]} |",
        f"| policy_fallback passed | {metrics['policy_fallback_passed'][0]} / {metrics['policy_fallback_passed'][1]} |",
        f"| stop_reason matches | {metrics['stop_reason_matches'][0]} / {metrics['stop_reason_matches'][1]} |",
        f"| source_type matches | {metrics['source_type_matches'][0]} / {metrics['source_type_matches'][1]} |",
        f"| expected_contains matches | {metrics['expected_contains_matches'][0]} / {metrics['expected_contains_matches'][1]} |",
        f"| expected_not_contains matches | {metrics['expected_not_contains_matches'][0]} / {metrics['expected_not_contains_matches'][1]} |",
        f"| source_titles matches | {metrics['source_titles_matches'][0]} / {metrics['source_titles_matches'][1]} |",
        f"| min_local_sources matches | {metrics['min_local_sources_matches'][0]} / {metrics['min_local_sources_matches'][1]} |",
        f"| web_search_count matches | {metrics['web_search_count_matches'][0]} / {metrics['web_search_count_matches'][1]} |",
        f"| policy_applied matches | {metrics['policy_applied_matches'][0]} / {metrics['policy_applied_matches'][1]} |",
        f"| Average retries | {metrics['average_retries']} |",
        f"| Average tracked LLM calls | {metrics['average_llm_calls']} |",
        f"| Total web searches | {metrics['total_web_searches']} |",
        "",
        "Tracked LLM calls are the graph's budgeted operational counter "
        "(generations, query rewrites, web-result grades). Router and grader "
        "calls are not individually tracked, so this is not total LLM usage "
        "and not billing-accurate cost accounting.",
        "",
    ]

    if delta_lines is not None:
        lines.extend(delta_lines)

    lines += [
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

    if include_answer_text:
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
    else:
        # Privacy mode (--no-answer-text): omit every question/answer excerpt.
        # The per-question status table above already carries the per-row
        # metadata, so the report stays complete without any content.
        lines += [
            "",
            "## Answers",
            "",
            "Answer text omitted by privacy setting (`--no-answer-text`). Question "
            "and answer excerpts are not written to this report; see the Metrics "
            "and Per-question results tables above for per-row status.",
            "",
        ]

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def run_eval(
    rows,
    output_path,
    dataset_path,
    *,
    history_dir=None,
    baseline=None,
    no_history=False,
    include_answer_text=True,
):
    """Run rows through the real graph (REAL API calls) and write the report.

    history_dir: if set, reads/writes history records and renders a delta section.
    baseline: explicit path to a baseline record (overrides auto-discovery).
    no_history: if True, renders the delta section but skips writing the record.
    include_answer_text: if False (privacy mode), the Markdown report omits all
    question/answer excerpts. Only the report is affected — evaluation, scoring,
    and the metadata-only history record are unchanged.
    """

    # Imported here so --validate-only never touches the graph. State seeding
    # and per-run config resolution live in the engine (enterprise_rag/graph/engine.py) —
    # the same entry point main.py uses — so the harness never mutates env.
    from enterprise_rag.graph.engine import AnswerOptions, answer_question
    from enterprise_rag.graph.formatting import format_answer

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
            entry = {
                "row": row,
                "summary": summary,
                "checks": {"run_completed": False},
                "passed": False,
            }
        evaluated.append(entry)

    metrics = compute_metrics(evaluated)

    # --- History and delta ---
    delta = None
    history_write_status = None
    written_path = None

    if history_dir is not None:
        run_id = str(uuid.uuid4())
        timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

        try:
            content = read_dataset_content(dataset_path)
            fingerprint = dataset_fingerprint(rows, content)
        except Exception as exc:
            print(f"  WARNING: could not compute dataset fingerprint ({type(exc).__name__})")
            fingerprint = {
                "row_count": len(rows),
                "ids": [r.get("id") for r in rows],
                "dataset_sha256": "",
            }

        current_record = build_history_record(
            evaluated,
            metrics,
            dataset_path,
            fingerprint,
            timestamp=timestamp,
            run_id=run_id,
        )

        # Select baseline BEFORE writing so the new record is never its own baseline.
        if baseline is not None:
            try:
                baseline_record = load_history_record(baseline)
            except Exception as exc:
                raise HistoryBaselineError(
                    f"--baseline {baseline!r}: {type(exc).__name__}: {exc}"
                ) from exc
        else:
            baseline_record = load_latest_history_record(history_dir)

        if baseline_record is not None:
            delta = compute_delta(baseline_record, current_record)

        if no_history:
            history_write_status = "skipped_by_no_history"
        else:
            try:
                written_path = write_history_record(current_record, history_dir)
                history_write_status = "written"
            except Exception as exc:
                print(f"  WARNING: history write failed ({type(exc).__name__})")
                history_write_status = "failed"

    # Render report (with delta section when history is enabled).
    delta_lines = render_delta_section(delta) if history_dir is not None else None
    Path(output_path).write_text(
        render_markdown(
            evaluated,
            metrics,
            dataset_path,
            delta_lines=delta_lines,
            include_answer_text=include_answer_text,
        ),
        encoding="utf-8",
    )

    print()
    print(f"Overall: {metrics['passed']}/{metrics['total']} passed")
    for key in CATEGORY_METRIC_KEYS.values():
        passed, total = metrics[key]
        print(f"  {key}: {passed}/{total}")
    print(
        f"  average retries: {metrics['average_retries']}, "
        f"average tracked LLM calls: {metrics['average_llm_calls']}, "
        f"total web searches: {metrics['total_web_searches']}"
    )
    if history_write_status is not None:
        status_note = f" → {written_path}" if written_path else ""
        print(f"  history: {history_write_status}{status_note}")
    print(f"Report written to {output_path}")
    return metrics


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Behavioral eval harness for the Agentic RAG graph."
    )
    parser.add_argument(
        "--dataset", default=str(DEFAULT_DATASET), help="Path to the JSONL dataset."
    )
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Markdown report path.")
    parser.add_argument("--limit", type=int, default=None, help="Run only the first N rows.")
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate the dataset format and exit (no API calls, no history I/O).",
    )
    parser.add_argument(
        "--no-history",
        action="store_true",
        help="Run and render the delta section but do not write a history record.",
    )
    parser.add_argument(
        "--baseline",
        default=None,
        metavar="PATH",
        help="Compare against a specific history record instead of auto-discovering the latest.",
    )
    parser.add_argument(
        "--history-dir",
        default=str(DEFAULT_HISTORY_DIR),
        metavar="PATH",
        help="Directory for history records (default: evals/enterprise_rag/history/).",
    )
    parser.add_argument(
        "--no-answer-text",
        action="store_true",
        help=(
            "Privacy mode: omit all question/answer excerpts from the Markdown "
            "report. Use for sensitive/private datasets. Scoring and history "
            "records are unaffected."
        ),
    )
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

    # Full mode only, below this point. OFFLINE_MODE fails closed: the eval drives
    # the real graph, which needs OpenAI, so refuse before running any row and
    # leave any existing report/history untouched.
    if offline_mode():
        print("CONFIG ERROR: OFFLINE_MODE is enabled — this eval requires the OpenAI service.")
        print("Unset OFFLINE_MODE to run the full eval, or use --validate-only.")
        print("No rows were executed; the existing report and history were left untouched.")
        return EXIT_INVALID_RUN

    # PRIVACY_MODE does NOT block this eval (the OpenAI path is preserved), but
    # tracing must be neutralized before the first row runs. No-op when no mode
    # is active. Note: under PRIVACY_MODE web search is forced off, so
    # web-dependent rows are expected to fail by design.
    enforce_tracing_privacy()

    if args.limit is not None:
        rows = rows[: args.limit]

    try:
        run_eval(
            rows,
            args.output,
            args.dataset,
            history_dir=args.history_dir,
            baseline=args.baseline,
            no_history=args.no_history,
            include_answer_text=not args.no_answer_text,
        )
    except HistoryBaselineError as exc:
        print(f"ERROR: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
