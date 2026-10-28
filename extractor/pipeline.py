import base64
from datetime import date
from pathlib import Path

import pymupdf

from extractor.llm import DEFAULT_MODEL, call_openrouter
from extractor.normalize import normalize
from extractor.status import DEFAULT_WINDOW_DAYS
from extractor.validate import validate

DEFAULT_DPI = 200
SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}


def load_image(path: Path, dpi: int = DEFAULT_DPI) -> tuple[str, str]:
    """Return (mime_type, base64_data). PDFs use the first page."""
    if path.suffix.lower() == ".pdf":
        with pymupdf.open(path) as pdf:
            pixmap = pdf[0].get_pixmap(dpi=dpi)
            return "image/png", base64.b64encode(pixmap.tobytes("png")).decode()
    suffix = path.suffix.lower()
    mime = "image/jpeg" if suffix in {".jpg", ".jpeg"} else f"image/{suffix[1:]}"
    return mime, base64.b64encode(path.read_bytes()).decode()


def extract_document(
    path: Path,
    reference: date,
    model: str = DEFAULT_MODEL,
    call=call_openrouter,
    dpi: int = DEFAULT_DPI,
    window_days: int = DEFAULT_WINDOW_DAYS,
) -> tuple[dict, dict]:
    mime, image_b64 = load_image(path, dpi)
    raw, usage = call(mime, image_b64, model)
    result = normalize(raw, reference, window_days)
    result["warnings"] = validate(result, raw, load_text_layer(path))
    return result, {**usage, "raw": raw}


def load_text_layer(path: Path) -> str:
    """Embedded PDF text (often noisy OCR). Only used to cross-check, never as a source."""
    if path.suffix.lower() != ".pdf":
        return ""
    with pymupdf.open(path) as pdf:
        return pdf[0].get_text()
