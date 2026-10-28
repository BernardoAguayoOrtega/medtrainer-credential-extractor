"""Web app: upload a credential document, get the extracted JSON.

Run locally:  uvicorn app:app --reload
"""

import logging
import os
import time
from collections import defaultdict, deque
from datetime import date
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse

from extractor.llm import DEFAULT_MODEL, call_openrouter
from extractor.pipeline import extract_bytes

logger = logging.getLogger("credential-extractor")

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MODEL = os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL)
# Magic bytes, so a renamed file cannot reach the model.
SIGNATURES = {
    ".pdf": [b"%PDF"],
    ".png": [b"\x89PNG"],
    ".jpg": [b"\xff\xd8\xff"],
    ".jpeg": [b"\xff\xd8\xff"],
    ".webp": [b"RIFF"],
}
INDEX_HTML = (Path(__file__).parent / "templates" / "index.html").read_text()

call_model = call_openrouter


class RateLimiter:
    """Per-IP sliding window. In memory, so per instance: a guard for a shared $5 key, not a quota system."""

    def __init__(self, limit: int = 20, window_seconds: int = 3600):
        self.limit, self.window = limit, window_seconds
        self.hits: dict[str, deque] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now, hits = time.monotonic(), self.hits[key]
        while hits and now - hits[0] > self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            return False
        hits.append(now)
        return True

    def reset(self) -> None:
        self.hits.clear()


rate_limiter = RateLimiter()
app = FastAPI(title="Credential Extractor")


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return INDEX_HTML


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "model": MODEL}


@app.post("/api/extract")
async def extract(request: Request, file: UploadFile = File(...), reference_date: str | None = Form(None)) -> dict:
    client_ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "?").split(",")[0]
    if not rate_limiter.allow(client_ip):
        raise HTTPException(429, "Too many documents from this address. Try again later.")

    try:
        reference = date.fromisoformat(reference_date) if reference_date else date.today()
    except ValueError:
        raise HTTPException(422, "reference_date must be YYYY-MM-DD")

    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SIGNATURES:
        raise HTTPException(415, "Upload a PDF, PNG, JPG or WEBP file.")
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File is larger than 10 MB.")
    if not any(data.startswith(sig) for sig in SIGNATURES[suffix]):
        raise HTTPException(415, "The file content does not match its extension.")

    started = time.monotonic()
    try:
        result, meta = extract_bytes(data, suffix, reference, model=MODEL, call=call_model)
    except Exception as exc:
        # Log the error type only: messages may echo document content (PHI).
        logger.error("extraction failed: %s", type(exc).__name__)
        raise HTTPException(502, "The extraction failed. Please try again.")

    return {
        "result": result,
        "meta": {
            "model": MODEL,
            "reference_date": reference.isoformat(),
            "cost_usd": meta.get("cost"),
            "latency_s": round(time.monotonic() - started, 2),
        },
    }
