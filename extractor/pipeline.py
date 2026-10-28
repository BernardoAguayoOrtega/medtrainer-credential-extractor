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


def load_image(data: bytes, suffix: str, dpi: int = DEFAULT_DPI) -> tuple[str, str]:
    """Return (mime_type, base64_data). PDFs use the first page."""
    suffix = suffix.lower()
    if suffix == ".pdf":
        with pymupdf.open(stream=data, filetype="pdf") as pdf:
            pixmap = pdf[0].get_pixmap(dpi=dpi)
            return "image/png", base64.b64encode(pixmap.tobytes("png")).decode()
    mime = "image/jpeg" if suffix in {".jpg", ".jpeg"} else f"image/{suffix[1:]}"
    return mime, base64.b64encode(data).decode()


def load_text_layer(data: bytes, suffix: str) -> str:
    """Embedded PDF text (often noisy OCR). Only used to cross-check, never as a source."""
    if suffix.lower() != ".pdf":
        return ""
    with pymupdf.open(stream=data, filetype="pdf") as pdf:
        return pdf[0].get_text()


def extract_bytes(
    data: bytes,
    suffix: str,
    reference: date,
    model: str = DEFAULT_MODEL,
    call=call_openrouter,
    dpi: int = DEFAULT_DPI,
    window_days: int = DEFAULT_WINDOW_DAYS,
) -> tuple[dict, dict]:
    """Everything happens in memory: the document is never written to disk."""
    mime, image_b64 = load_image(data, suffix, dpi)
    raw, usage = call(mime, image_b64, model)
    result = normalize(raw, reference, window_days)
    result["warnings"] = validate(result, raw, load_text_layer(data, suffix))
    return result, {**usage, "raw": raw}


def extract_document(path: Path, reference: date, **kwargs) -> tuple[dict, dict]:
    return extract_bytes(path.read_bytes(), path.suffix, reference, **kwargs)
