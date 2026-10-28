"""Field-level eval: compares extractor outputs with the expected JSON files.

Two scores per field:
- strict: exact equality. This is the headline number.
- lenient: strings compared ignoring case and repeated/edge whitespace. Only a
  diagnostic, to tell formatting misses apart from wrong values.

A missing output file or an extractor error counts as wrong on every field.

Usage:
    python evaluate.py outputs/
    python evaluate.py outputs/ --expected expected/ --json results/baseline.json
"""

import argparse
import json
import sys
from pathlib import Path

FIELDS = [
    "is_credential",
    "holder_name",
    "credential_type",
    "license_number",
    "issuing_authority",
    "issue_date",
    "expiration_date",
    "expiration_status",
]


def _lenient(value):
    return " ".join(value.split()).casefold() if isinstance(value, str) else value


def field_matches(expected, actual, lenient: bool = False) -> bool:
    if type(expected) is not type(actual):
        return False
    if lenient:
        return _lenient(expected) == _lenient(actual)
    return expected == actual


def _load_output(path: Path) -> tuple[dict | None, str | None]:
    if not path.exists():
        return None, "missing output"
    data = json.loads(path.read_text())
    if "error" in data:
        return None, str(data["error"])
    return data, None


def evaluate(expected_dir: Path, outputs_dir: Path) -> dict:
    expected_files = sorted(p for p in Path(expected_dir).glob("*.json") if not p.name.startswith("_"))
    hits = {f: {"strict": 0, "lenient": 0} for f in FIELDS}
    mismatches, errors = [], []
    exact_documents = 0

    for expected_path in expected_files:
        name = expected_path.stem
        expected = json.loads(expected_path.read_text())
        actual, error = _load_output(Path(outputs_dir) / expected_path.name)
        if error:
            errors.append(f"{name}: {error}")
            continue

        all_fields_match = True
        for field in FIELDS:
            exp, act = expected.get(field), actual.get(field)
            if field_matches(exp, act):
                hits[field]["strict"] += 1
            else:
                all_fields_match = False
                mismatches.append({"document": name, "field": field, "expected": exp, "actual": act})
            if field_matches(exp, act, lenient=True):
                hits[field]["lenient"] += 1
        exact_documents += all_fields_match

    total = len(expected_files)
    fields = {f: {k: (n / total if total else 0.0) for k, n in h.items()} for f, h in hits.items()}
    overall = {k: sum(fields[f][k] for f in FIELDS) / len(FIELDS) for k in ("strict", "lenient")}
    return {
        "documents": total,
        "exact_documents": exact_documents,
        "fields": fields,
        "overall": overall,
        "mismatches": mismatches,
        "errors": errors,
    }


def format_report(report: dict) -> str:
    lines = [f"{'field':<20}{'strict':>8}{'lenient':>9}"]
    for field, score in report["fields"].items():
        lines.append(f"{field:<20}{score['strict']:>8.0%}{score['lenient']:>9.0%}")
    overall = report["overall"]
    lines.append(f"{'OVERALL':<20}{overall['strict']:>8.1%}{overall['lenient']:>9.1%}")
    lines.append(f"documents fully correct: {report['exact_documents']}/{report['documents']}")
    for error in report["errors"]:
        lines.append(f"ERROR {error}")
    for m in report["mismatches"]:
        lines.append(f"MISS  {m['document']}.{m['field']}: expected {m['expected']!r}, got {m['actual']!r}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Score extractor outputs against expected JSON.")
    parser.add_argument("outputs", type=Path, help="Folder with one <document>.json per document")
    parser.add_argument("--expected", type=Path, default=Path("expected"))
    parser.add_argument("--json", type=Path, help="Also write the full report here")
    args = parser.parse_args()

    if not args.outputs.is_dir():
        sys.exit(f"{args.outputs} is not a folder")

    report = evaluate(args.expected, args.outputs)
    print(format_report(report))
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
