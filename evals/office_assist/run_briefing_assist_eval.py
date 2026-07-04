"""
evals/office_assist/run_briefing_assist_eval.py — offline validator + optional
real-model runner for the Office Agent LLM Daily Briefing narrative assist.

Separate from both the RAG eval harness (`evals/run_eval.py`, `evals/questions.jsonl`)
and the Phase 1 email-digest eval (`cases.jsonl`, `run_office_assist_eval.py`) —
all of those are untouched. Two modes:

  --validate-only : offline and keys-free. Load and schema-check
                    `briefing_cases.jsonl` only; make no LLM call. Safe anywhere.
  (default / full): build the collected briefing facts once (they are constant),
                    call the real gpt-5-mini narrative chain, check grounding via
                    `validate_narrative`, and check per-row reference recall and
                    required source-type coverage. Requires `OPENAI_API_KEY` and is
                    APPROVAL-GATED — same rule as the RAG eval: never run a full /
                    real-model eval without explicit user approval.

`office_agent` is imported lazily inside the full runner so `--validate-only` stays
import-light and keys-free.

Usage:
    uv run python evals/office_assist/run_briefing_assist_eval.py --validate-only
    uv run python evals/office_assist/run_briefing_assist_eval.py --output evals/office_assist/briefing_results.md
"""

import argparse
import json
import sys
from pathlib import Path

CASES_PATH = Path(__file__).resolve().parent / "briefing_cases.jsonl"

# Required keys and their expected JSON types for each dataset row.
_REQUIRED_FIELDS: dict[str, type | tuple[type, ...]] = {
    "id": str,
    "query": str,
    "expected_reference_ids": list,
    "must_reference_source_types": list,
}

# The source types a reference may carry (mirrors BriefingSourceType).
_VALID_SOURCE_TYPES = {"email", "meeting", "ticket", "task", "approval"}


def load_cases() -> list[dict]:
    """Load the JSONL dataset into a list of row dicts."""

    rows: list[dict] = []
    for line_number, raw in enumerate(CASES_PATH.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"briefing_cases.jsonl line {line_number}: invalid JSON ({exc})"
            ) from exc
    return rows


def validate_cases(rows: list[dict]) -> list[str]:
    """Return a list of schema problems (empty when the dataset is valid)."""

    problems: list[str] = []
    seen_ids: set[str] = set()

    for index, row in enumerate(rows, start=1):
        for field, expected_type in _REQUIRED_FIELDS.items():
            if field not in row:
                problems.append(f"row {index}: missing required field '{field}'")
            elif not isinstance(row[field], expected_type):
                problems.append(f"row {index}: field '{field}' has the wrong type")

        row_id = row.get("id")
        if isinstance(row_id, str):
            if row_id in seen_ids:
                problems.append(f"row {index}: duplicate id '{row_id}'")
            seen_ids.add(row_id)

        for source_type in row.get("must_reference_source_types", []):
            if source_type not in _VALID_SOURCE_TYPES:
                problems.append(f"row {index}: unknown source type '{source_type}'")

    return problems


def _run_validate_only() -> int:
    rows = load_cases()
    problems = validate_cases(rows)
    if problems:
        print(f"INVALID: {len(problems)} problem(s) in {CASES_PATH.name}:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print(f"VALID: {len(rows)} case(s) in {CASES_PATH.name} passed schema validation.")
    return 0


def _run_full(output: str | None) -> int:
    """Call the real narrative chain once and check grounding / recall / coverage.

    Approval-gated: only run this mode with explicit user approval and a real
    `OPENAI_API_KEY`. Imports `office_agent` lazily so the keys-free
    `--validate-only` path never imports the LLM stack. The collected facts are
    constant (query does not change them), so the chain is called once and every
    row is evaluated against that single grounded narrative.

    Environment / error handling (see `evals/office_assist/_env.py`):
      - CONFIG_ERROR — a missing/blank `OPENAI_API_KEY` is detected up front, before
        any client is built or the LLM stack is imported. Fails fast, writes no
        report, exits non-zero.
      - INFRA_ERROR — an OpenAI/transport failure (auth, connection, timeout, rate
        limit, provider error) is reported as an invalid run (no model-quality
        pass rate), writes no report, exits non-zero. It never counts as FAIL.
      - EVAL_FAIL — a grounding assertion failed on obtained structured output.
        Reported as FAIL in the written report (existing behavior).
    """

    # Make the repository root importable when run as a script.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from evals.office_assist import _env

    # Full-mode precondition: require OPENAI_API_KEY before importing the LLM
    # stack, constructing any client, or making any model call.
    try:
        _env.ensure_openai_api_key()
    except _env.ConfigError as exc:
        _env.print_config_error(exc)
        return _env.EXIT_INVALID_RUN

    from office_agent.llm_assist import briefing_narrative
    from office_agent.tools import briefing

    rows = load_cases()
    problems = validate_cases(rows)
    if problems:
        print("Refusing to run: dataset failed schema validation. Run --validate-only for details.")
        return 1

    facts = briefing.collect_briefing_facts()
    report_lines = ["# Office briefing-narrative eval results", ""]

    try:
        narrative = briefing_narrative.narrate_briefing(facts)
        briefing_narrative.validate_narrative(narrative, facts)
    except Exception as exc:
        if _env.is_infra_error(exc):
            # Infrastructure failure: invalid run, no model-quality summary, and
            # no report written so a prior valid report is never overwritten.
            _env.print_infra_error(exc)
            return _env.EXIT_INVALID_RUN
        if not isinstance(exc, ValueError):
            # Unexpected local error: surface it instead of mislabeling it as a
            # model-quality failure; write no report and exit non-zero.
            _env.print_unexpected_error(exc)
            return _env.EXIT_INVALID_RUN
        # Structured output was obtained but failed the grounding assertion: an
        # ordinary EVAL_FAIL, reported as FAIL (existing behavior).
        report_lines.append(f"FAIL: narrative grounding error: {type(exc).__name__}")
        print("\n".join(report_lines))
        if output:
            Path(output).write_text("\n".join(report_lines) + "\n", encoding="utf-8")
        return _env.EXIT_EVAL_FAIL

    produced_ids = {reference.id for reference in narrative.references}
    produced_types = {reference.source_type for reference in narrative.references}

    total = 0
    passed = 0
    for row in rows:
        total += 1
        expected_ids = set(row["expected_reference_ids"])
        recall = len(expected_ids & produced_ids) / len(expected_ids) if expected_ids else 1.0
        required_types = set(row["must_reference_source_types"])
        types_ok = required_types.issubset(produced_types)

        ok = recall == 1.0 and types_ok
        passed += int(ok)
        report_lines.append(
            f"- {row['id']}: {'PASS' if ok else 'FAIL'} "
            f"(reference_recall={recall:.2f}, source_types_ok={types_ok})"
        )

    summary = f"{passed}/{total} case(s) passed."
    report_lines += ["", summary]
    print("\n".join(report_lines))

    if output:
        Path(output).write_text("\n".join(report_lines) + "\n", encoding="utf-8")
        print(f"Wrote {output}")

    return 0 if passed == total else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Office Agent LLM briefing-narrative eval.")
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Offline, keys-free schema validation of briefing_cases.jsonl (no LLM call).",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional path to write a markdown report (full mode only).",
    )
    args = parser.parse_args()

    if args.validate_only:
        return _run_validate_only()
    return _run_full(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
