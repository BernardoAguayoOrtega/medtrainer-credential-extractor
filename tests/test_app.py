from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app as app_module

DOCS = Path(__file__).parent.parent / "docs"


@pytest.fixture
def client(monkeypatch):
    calls = []

    def fake_call(mime, image_b64, model):
        calls.append(mime)
        return {"is_credential": True, "holder_name": "X", "license_number": "PA20733", "expiration_date": "02/28/2026"}, {
            "cost": 0.0002
        }

    monkeypatch.setattr(app_module, "call_model", fake_call)
    app_module.rate_limiter.reset()
    client = TestClient(app_module.app)
    client.calls = calls
    return client


def upload(client, name="tx_02.pdf", content=None, **data):
    content = content if content is not None else (DOCS / "tx_02.pdf").read_bytes()
    return client.post("/api/extract", files={"file": (name, content)}, data=data)


def test_home_page_has_an_upload_form(client):
    response = client.get("/")

    assert response.status_code == 200
    assert 'type="file"' in response.text


def test_extract_returns_contract_fields_warnings_and_meta(client):
    response = upload(client, reference_date="2026-11-01")

    assert response.status_code == 200
    body = response.json()
    assert body["result"]["expiration_date"] == "2026-02-28"
    assert body["result"]["expiration_status"] == "expired"
    assert isinstance(body["result"]["warnings"], list)
    assert body["meta"]["reference_date"] == "2026-11-01"
    assert body["meta"]["cost_usd"] == 0.0002


def test_reference_date_defaults_to_today(client):
    body = upload(client).json()

    assert body["meta"]["reference_date"] == date.today().isoformat()


def test_images_are_accepted(client):
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 100

    assert upload(client, name="card.png", content=png).status_code == 200
    assert client.calls[-1] == "image/png"


def test_unsupported_type_is_rejected_without_calling_the_model(client):
    response = upload(client, name="notes.docx", content=b"PK...")

    assert response.status_code == 415
    assert client.calls == []


def test_file_that_lies_about_being_a_pdf_is_rejected(client):
    response = upload(client, name="fake.pdf", content=b"hello")

    assert response.status_code == 415
    assert client.calls == []


def test_oversized_file_is_rejected(client, monkeypatch):
    monkeypatch.setattr(app_module, "MAX_UPLOAD_BYTES", 10)

    assert upload(client).status_code == 413
    assert client.calls == []


def test_invalid_reference_date_is_rejected(client):
    assert upload(client, reference_date="31/12/2026").status_code == 422


def test_rate_limit_blocks_after_the_quota(client, monkeypatch):
    monkeypatch.setattr(app_module.rate_limiter, "limit", 2)

    assert [upload(client).status_code for _ in range(3)] == [200, 200, 429]


def test_model_failure_returns_502_with_a_safe_message(client, monkeypatch):
    def broken(mime, image_b64, model):
        raise RuntimeError("OpenRouter 500: secret details")

    monkeypatch.setattr(app_module, "call_model", broken)
    response = upload(client)

    assert response.status_code == 502
    assert "secret" not in response.text
