"""Run the improved extractor over documents and log the real cost of each call.

Usage:
    python run.py docs/ --out-dir outputs/iter1
    python run.py docs/tx_01.pdf --out-dir outputs/iter1      # one document
    python run.py docs/ --out-dir outputs/iter1 --reference-date 2026-11-01
"""

import argparse
import json
import os
from datetime import date
from functools import partial
from pathlib import Path

from extractor.llm import DEFAULT_MODEL, call_openrouter
from extractor.pipeline import SUPPORTED_EXTENSIONS, extract_document

REFERENCE_FILE = Path("expected/_reference.json")


def load_reference(path: Path = REFERENCE_FILE) -> tuple[date, int]:
    data = json.loads(path.read_text())
    return date.fromisoformat(data["reference_date"]), data["expiring_soon_window_days"]


def run_batch(files, out_dir: Path, reference: date, model: str, window_days: int = 60, call=call_openrouter) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / "_run.json"
    log = {"model": model, "reference_date": reference.isoformat(), "documents": {}}
    if log_path.exists():
        previous = json.loads(log_path.read_text())
        if previous.get("model") == model and previous.get("reference_date") == log["reference_date"]:
            log["documents"] = previous["documents"]
    errors = 0
    for path in files:
        try:
            result, usage = extract_document(path, reference, model, call=call, window_days=window_days)
        except Exception as exc:  # one bad document must not stop the batch
            result, usage = {"error": str(exc)}, {"cost": None}
            errors += 1
        (out_dir / f"{path.stem}.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
        log["documents"][path.stem] = usage
        print(f"{path.name}: cost={usage.get('cost')}" + (f" ERROR {result['error']}" if "error" in result else ""))

    costs = [u.get("cost") or 0 for u in log["documents"].values()]
    log["total_cost"] = round(sum(costs), 8)
    log["errors"] = errors
    log_path.write_text(json.dumps(log, indent=2) + "\n")
    return {"total_cost": log["total_cost"], "errors": errors}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("path", type=Path)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--model", default=os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL))
    parser.add_argument("--labelled", action="store_true", help="Iteration 4 schema: printed label before each value (discarded, worse)")
    parser.add_argument("--reference-date", type=date.fromisoformat, help="Defaults to expected/_reference.json")
    args = parser.parse_args()

    reference, window = load_reference()
    reference = args.reference_date or reference
    if args.path.is_dir():
        files = sorted(p for p in args.path.iterdir() if p.suffix.lower() in SUPPORTED_EXTENSIONS)
    else:
        files = [args.path]

    call = partial(call_openrouter, labelled=args.labelled)
    summary = run_batch(files, args.out_dir, reference, args.model, window, call=call)
    print(f"total cost: ${summary['total_cost']:.6f}  errors: {summary['errors']}")


if __name__ == "__main__":
    main()
