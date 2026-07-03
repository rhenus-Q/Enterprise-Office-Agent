"""
evals/office_assist/run_office_assist_eval.py — offline validator + optional
real-model runner for the Office Agent LLM email-digest assist.

Separate from the RAG eval harness: `evals/run_eval.py` and `evals/questions.jsonl`
are untouched. Two modes:

  --validate-only : offline and keys-free. Load and schema-check `cases.jsonl`
                    only; make no LLM call. Safe to run anywhere.
  (default / full): call the real gpt-5-mini digest chain per row and check
                    grounding, action-item id recall against the hand labels, and
                    the "no invented deadline" rule. Requires `OPENAI_API_KEY` and
                    is APPROVAL-GATED — same rule as the RAG eval: never run a
                    full / real-model eval without explicit user approval.

No history / delta machinery in Phase 1. `office_agent` is imported lazily inside
the full runner so `--validate-only` stays import-light and keys-free.

Usage:
    uv run python evals/office_assist/run_office_assist_eval.py --validate-only
    uv run python evals/office_assist/run_office_assist_eval.py --output evals/office_assist/results.md
"""

import argparse
import json
import sys
from pathlib import Path

CASES_PATH = Path(__file__).resolve().parent / "cases.jsonl"

# Required keys and their expected JSON types for each dataset row.
_REQUIRED_FIELDS: dict[str, type | tuple[type, ...]] = {
    "id": str,
    "query": str,
    "expected_action_item_email_ids": list,
    "must_not_invent_deadline_for": list,
}


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
            raise ValueError(f"cases.jsonl line {line_number}: invalid JSON ({exc})") from exc
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

        deadlines = row.get("expected_deadlines", {})
        if not isinstance(deadlines, dict):
            problems.append(f"row {index}: 'expected_deadlines' must be an object when present")

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
    """Call the real digest chain per row and check grounding / recall / deadlines.

    Approval-gated: only run this mode with explicit user approval and a real
    `OPENAI_API_KEY`. Imports `office_agent` lazily so the keys-free
    `--validate-only` path never imports the LLM stack.
    """

    # Make the repository root importable when run as a script.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from office_agent.llm_assist import email_digest
    from office_agent.tools import email

    rows = load_cases()
    problems = validate_cases(rows)
    if problems:
        print("Refusing to run: dataset failed schema validation. Run --validate-only for details.")
        return 1

    report_lines = ["# Office-assist eval results", ""]
    total = 0
    passed = 0

    for row in rows:
        total += 1
        _label, matched = email.filter_for_query(row["query"])
        try:
            digest = email_digest.digest_emails(matched)
            email_digest.validate_digest(digest, matched)
        except Exception as exc:
            # Report failures per row, do not abort the whole run.
            report_lines.append(
                f"- {row['id']}: FAIL (chain/grounding error: {type(exc).__name__})"
            )
            continue

        produced_ids = {item.email_id for item in digest.action_items}
        expected_ids = set(row["expected_action_item_email_ids"])
        recall = len(expected_ids & produced_ids) / len(expected_ids) if expected_ids else 1.0

        deadline_by_id = {item.email_id: item.deadline for item in digest.action_items}
        no_invented = all(
            not deadline_by_id.get(email_id) for email_id in row["must_not_invent_deadline_for"]
        )
        expected_deadlines = row.get("expected_deadlines", {})
        deadlines_ok = all(
            (deadline_by_id.get(email_id) or "").lower().find(substr.lower()) >= 0
            for email_id, substr in expected_deadlines.items()
        )

        ok = recall == 1.0 and no_invented and deadlines_ok
        passed += int(ok)
        report_lines.append(
            f"- {row['id']}: {'PASS' if ok else 'FAIL'} "
            f"(recall={recall:.2f}, no_invented_deadline={no_invented}, deadlines_ok={deadlines_ok})"
        )

    summary = f"{passed}/{total} case(s) passed."
    report_lines += ["", summary]
    print("\n".join(report_lines))

    if output:
        Path(output).write_text("\n".join(report_lines) + "\n", encoding="utf-8")
        print(f"Wrote {output}")

    return 0 if passed == total else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Office Agent LLM email-digest eval.")
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Offline, keys-free schema validation of cases.jsonl (no LLM call).",
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
