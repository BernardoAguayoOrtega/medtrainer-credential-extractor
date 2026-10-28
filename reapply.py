"""Re-run only the deterministic post-processing over saved outputs: zero model calls.

Used to measure code-only iterations. Earlier runs did not save the model's raw
answer, so the saved (already normalized) output is fed back as the raw answer;
normalization is idempotent, so the result equals a fresh run with the same model answer.

Usage:
    python reapply.py outputs/iter2 outputs/iter3
"""

import json
import sys
from pathlib import Path

from extractor.normalize import normalize
from extractor.pipeline import load_text_layer
from extractor.validate import validate
from run import load_reference


def main() -> None:
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    dst.mkdir(parents=True, exist_ok=True)
    reference, window = load_reference()
    for path in sorted(src.glob("*.json")):
        if path.name.startswith("_"):
            continue
        raw = json.loads(path.read_text())
        result = normalize(raw, reference, window)
        result["warnings"] = validate(result, raw, load_text_layer(Path("docs") / f"{path.stem}.pdf"))
        (dst / path.name).write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
        print(f"{path.stem}: {result['warnings'] or 'ok'}")


if __name__ == "__main__":
    main()
