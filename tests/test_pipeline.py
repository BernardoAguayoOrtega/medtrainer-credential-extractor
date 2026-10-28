from datetime import date
from pathlib import Path

from extractor.pipeline import extract_document

DOCS = Path(__file__).parent.parent / "docs"


def fake_call(fields):
    calls = []

    def call(mime, image_b64, model):
        calls.append((mime, model, len(image_b64)))
        return fields, {"cost": 0.0001}

    return call, calls


def test_extract_document_renders_calls_and_normalizes():
    call, calls = fake_call({"is_credential": True, "expiration_date": "02/28/2026", "license_number": "PA 20733"})

    result, usage = extract_document(DOCS / "tx_02.pdf", date(2026, 11, 1), model="m", call=call)

    assert calls[0][0] == "image/png" and calls[0][1] == "m"
    assert result["expiration_date"] == "2026-02-28"
    assert result["expiration_status"] == "expired"
    assert result["license_number"] == "PA20733"
    assert usage["cost"] == 0.0001


def test_extract_document_adds_warnings_and_keeps_raw_answer():
    raw = {"is_credential": True, "holder_name": "X", "license_number": "PA99999", "expiration_date": "02/28/2026"}
    call, _ = fake_call(raw)

    result, meta = extract_document(DOCS / "tx_02.pdf", date(2026, 11, 1), model="m", call=call)

    assert isinstance(result["warnings"], list)
    assert meta["raw"] == raw


def test_pdf_renders_at_higher_resolution_than_baseline():
    call, calls = fake_call({"is_credential": False})
    extract_document(DOCS / "tx_02.pdf", date(2026, 11, 1), model="m", call=call, dpi=100)
    low = calls[-1][2]
    extract_document(DOCS / "tx_02.pdf", date(2026, 11, 1), model="m", call=call)
    assert calls[-1][2] > low
