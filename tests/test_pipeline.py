from datetime import date
from pathlib import Path

from extractor.pipeline import extract_bytes, extract_document

DOCS = Path(__file__).parent.parent / "docs"


def fake_call(fields):
    calls = []

    def call(images, model):
        calls.append({"mimes": [m for m, _ in images], "model": model, "sizes": [len(b) for _, b in images]})
        return fields, {"cost": 0.0001}

    return call, calls


def test_extract_document_renders_calls_and_normalizes():
    call, calls = fake_call({"is_credential": True, "expiration_date": "02/28/2026", "license_number": "PA 20733"})

    result, usage = extract_document(DOCS / "tx_02.pdf", date(2026, 11, 1), model="m", call=call)

    assert calls[0]["mimes"][0] == "image/png" and calls[0]["model"] == "m"
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


def test_extract_bytes_matches_extract_document():
    call, _ = fake_call({"is_credential": True, "license_number": "PA20733", "expiration_date": "02/28/2026"})
    data = (DOCS / "tx_02.pdf").read_bytes()

    from_bytes, _ = extract_bytes(data, ".pdf", date(2026, 11, 1), model="m", call=call)
    from_path, _ = extract_document(DOCS / "tx_02.pdf", date(2026, 11, 1), model="m", call=call)

    assert from_bytes == from_path


def test_pdf_renders_at_higher_resolution_than_baseline():
    call, calls = fake_call({"is_credential": False})
    extract_document(DOCS / "tx_02.pdf", date(2026, 11, 1), model="m", call=call, dpi=100)
    low = calls[-1]["sizes"][0]
    extract_document(DOCS / "tx_02.pdf", date(2026, 11, 1), model="m", call=call)
    assert calls[-1]["sizes"][0] > low


def test_multi_page_pdf_sends_every_page_up_to_the_limit():
    call, calls = fake_call({"is_credential": False})

    extract_document(DOCS / "tx_02.pdf", date(2026, 11, 1), model="m", call=call)  # 2 pages
    extract_document(DOCS / "tx_02.pdf", date(2026, 11, 1), model="m", call=call, max_pages=1)
    extract_document(DOCS / "al_01.pdf", date(2026, 11, 1), model="m", call=call)  # 1 page

    assert [len(c["mimes"]) for c in calls] == [2, 1, 1]


def test_image_upload_is_a_single_page():
    call, calls = fake_call({"is_credential": False})
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 50

    extract_bytes(png, ".png", date(2026, 11, 1), model="m", call=call)

    assert calls[0]["mimes"] == ["image/png"]
