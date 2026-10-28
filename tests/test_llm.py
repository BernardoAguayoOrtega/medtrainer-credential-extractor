import json

import pytest

from extractor.llm import ExtractionError, build_payload, parse_response


def test_payload_requests_strict_json_schema_and_usage():
    payload = build_payload([("image/png", "QUJD")], "some/model")

    assert payload["model"] == "some/model"
    assert payload["temperature"] == 0
    assert payload["usage"] == {"include": True}
    schema = payload["response_format"]["json_schema"]
    assert schema["strict"] is True
    assert "expiration_status" not in schema["schema"]["properties"]  # computed in code


def test_schema_asks_for_the_printed_label_before_each_value():
    props = build_payload([("image/png", "QUJD")], "m", labelled=True)["response_format"]["json_schema"]["schema"]["properties"]

    assert list(props["license_number"]["properties"]) == ["label", "value"]
    assert list(props["issue_date"]["properties"]) == ["label", "text"]
    assert list(props["expiration_date"]["properties"]) == ["label", "text"]


def test_flat_schema_variant_has_plain_fields_and_no_label_rule():
    payload = build_payload([("image/png", "QUJD")], "m", labelled=False)
    props = payload["response_format"]["json_schema"]["schema"]["properties"]

    assert props["license_number"] == {"type": ["string", "null"]}
    assert props["expiration_date"]["type"] == ["string", "null"]
    assert "first copy the label" not in payload["messages"][0]["content"]


def test_payload_sends_every_page_in_order():
    content = build_payload([("image/png", "UDE="), ("image/png", "UDI=")], "m")["messages"][-1]["content"]

    urls = [c["image_url"]["url"] for c in content if c["type"] == "image_url"]
    assert urls == ["data:image/png;base64,UDE=", "data:image/png;base64,UDI="]
    assert "2 pages" in content[0]["text"]


def test_reasoning_is_disabled_by_default():
    assert build_payload([("image/png", "QUJD")], "m")["reasoning"] == {"enabled": False}


def test_reasoning_can_be_enabled():
    assert build_payload([("image/png", "QUJD")], "m", reasoning=True)["reasoning"] == {"enabled": True}


def test_payload_sends_the_image_as_data_url():
    content = build_payload([("image/png", "QUJD")], "m")["messages"][-1]["content"]

    assert {"type": "image_url", "image_url": {"url": "data:image/png;base64,QUJD"}} in content


def test_parse_response_returns_fields_and_usage():
    body = {
        "id": "gen-1",
        "choices": [{"message": {"content": json.dumps({"is_credential": True})}}],
        "usage": {"prompt_tokens": 900, "completion_tokens": 80, "cost": 0.0003},
    }

    fields, usage = parse_response(body)

    assert fields == {"is_credential": True}
    assert usage == {"generation_id": "gen-1", "prompt_tokens": 900, "completion_tokens": 80, "cost": 0.0003}


def test_parse_response_tolerates_code_fences():
    body = {"choices": [{"message": {"content": '```json\n{"is_credential": false}\n```'}}]}

    assert parse_response(body)[0] == {"is_credential": False}


def test_parse_response_raises_on_invalid_json():
    body = {"choices": [{"message": {"content": "sorry, I can't"}}]}

    with pytest.raises(ExtractionError):
        parse_response(body)
