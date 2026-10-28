import base64
from datetime import date
from pathlib import Path

import pymupdf

from extractor.llm import DEFAULT_MODEL, call_openrouter
from extractor.normalize import normalize
from extractor.status import DEFAULT_WINDOW_DAYS
from extractor.validate import validate

DEFAULT_DPI = 200
# Enough for a cover letter + the credential + a wallet card; bounds cost per document.
DEFAULT_MAX_PAGES = 3
SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}


def load_images(
    data: bytes, suffix: str, dpi: int = DEFAULT_DPI, max_pages: int = DEFAULT_MAX_PAGES
) -> list[tuple[str, str]]:
    """Return [(mime_type, base64_data)], one per page. PDFs send their first max_pages pages."""
    suffix = suffix.lower()
    if suffix == ".pdf":
        with pymupdf.open(stream=data, filetype="pdf") as pdf:
            pages = [pdf[i].get_pixmap(dpi=dpi).tobytes("png") for i in range(min(len(pdf), max_pages))]
        return [("image/png", base64.b64encode(page).decode()) for page in pages]
    mime = "image/jpeg" if suffix in {".jpg", ".jpeg"} else f"image/{suffix[1:]}"
    return [(mime, base64.b64encode(data).decode())]


def load_text_layer(data: bytes, suffix: str, max_pages: int = DEFAULT_MAX_PAGES) -> str:
    """Embedded PDF text (often noisy OCR). Only used to cross-check, never as a source."""
    if suffix.lower() != ".pdf":
        return ""
    with pymupdf.open(stream=data, filetype="pdf") as pdf:
        return "\n".join(pdf[i].get_text() for i in range(min(len(pdf), max_pages)))


def extract_bytes(
    data: bytes,
    suffix: str,
    reference: date,
    model: str = DEFAULT_MODEL,
    call=call_openrouter,
    dpi: int = DEFAULT_DPI,
    window_days: int = DEFAULT_WINDOW_DAYS,
    max_pages: int = DEFAULT_MAX_PAGES,
) -> tuple[dict, dict]:
    """Everything happens in memory: the document is never written to disk."""
    images = load_images(data, suffix, dpi, max_pages)
    raw, usage = call(images, model)
    result = normalize(raw, reference, window_days)
    result["warnings"] = validate(result, raw, load_text_layer(data, suffix, max_pages))
    return result, {**usage, "raw": raw, "pages": len(images)}


def extract_document(path: Path, reference: date, **kwargs) -> tuple[dict, dict]:
    return extract_bytes(path.read_bytes(), path.suffix, reference, **kwargs)
