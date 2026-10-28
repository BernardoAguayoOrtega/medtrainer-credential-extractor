from extractor.validate import validate

GOOD = {
    "is_credential": True,
    "holder_name": "DEVIN KOFI ASANTE",
    "credential_type": "Physician Assistant License",
    "license_number": "PA20733",
    "issuing_authority": "Texas Physician Assistant Licensing Board",
    "issue_date": "2020-01-15",
    "expiration_date": "2026-02-28",
    "expiration_status": "expired",
}
TEXT = "TEXAS PHYSICIAN ASSISTANT LICENSING BOARD ... LICENSE NUMBER PA20733 " + "x" * 300


def test_clean_extraction_has_no_warnings():
    assert validate(GOOD, raw={}, text_layer=TEXT) == []


def test_non_credential_is_not_validated():
    assert validate({"is_credential": False}, raw={}, text_layer="") == []


def test_issue_after_expiration_is_flagged():
    warnings = validate({**GOOD, "issue_date": "2027-01-01"}, raw={}, text_layer=TEXT)

    assert "issue_date is after expiration_date" in warnings


def test_implausible_years_are_flagged():
    warnings = validate({**GOOD, "issue_date": "1890-01-01", "expiration_date": "2190-01-01"}, raw={}, text_layer=TEXT)

    assert "issue_date year 1890 looks implausible" in warnings
    assert "expiration_date year 2190 looks implausible" in warnings


def test_missing_key_fields_are_flagged():
    warnings = validate({**GOOD, "holder_name": None, "license_number": None}, raw={}, text_layer=TEXT)

    assert "holder_name is missing" in warnings
    assert "license_number is missing" in warnings


def test_license_number_without_digits_is_flagged():
    warnings = validate({**GOOD, "license_number": "PENDING"}, raw={}, text_layer="")

    assert "license_number has no digits" in warnings


def test_unparseable_printed_date_is_flagged():
    result = {**GOOD, "expiration_date": None, "expiration_status": None}

    warnings = validate(result, raw={"expiration_date": "Dec. the 31st"}, text_layer=TEXT)

    assert "expiration_date 'Dec. the 31st' could not be parsed" in warnings


def test_license_number_not_in_text_layer_is_flagged():
    warnings = validate({**GOOD, "license_number": "PA20788"}, raw={}, text_layer=TEXT)

    assert "license_number not found in the PDF text layer" in warnings


def test_text_layer_check_ignores_punctuation_and_case():
    text = "License # md.20417 " + "x" * 300

    assert validate({**GOOD, "license_number": "MD-20417"}, raw={}, text_layer=text) == []


def test_text_layer_check_tolerates_ocr_noise():
    for noisy in ("License# ~.41872", "License# MD.2\\417"):
        number = "MD.41872" if "41872" in noisy else "MD.20417"
        text = noisy + " " + "x" * 300

        assert validate({**GOOD, "license_number": number}, raw={}, text_layer=text) == [], noisy


def test_text_layer_check_still_flags_a_clearly_different_number():
    text = "License# ~.41872 " + "x" * 300

    warnings = validate({**GOOD, "license_number": "MD.99310"}, raw={}, text_layer=text)

    assert "license_number not found in the PDF text layer" in warnings


def test_license_number_taken_from_a_receipt_label_is_flagged():
    raw = {"license_number": {"label": "Receipt #", "value": "PA20733"}}

    warnings = validate(GOOD, raw=raw, text_layer=TEXT)

    assert "license_number comes from a field labelled 'Receipt #'" in warnings


def test_dates_with_swapped_labels_are_flagged():
    raw = {
        "issue_date": {"label": "Expires", "text": "01/15/2020"},
        "expiration_date": {"label": "Date Issued", "text": "02/28/2026"},
    }

    warnings = validate(GOOD, raw=raw, text_layer=TEXT)

    assert "issue_date comes from a field labelled 'Expires'" in warnings
    assert "expiration_date comes from a field labelled 'Date Issued'" in warnings


def test_expected_labels_raise_no_warning():
    raw = {
        "license_number": {"label": "License #", "value": "PA20733"},
        "issue_date": {"label": "Date Issued", "text": "01/15/2020"},
        "expiration_date": {"label": "Registered through", "text": "02/28/2026"},
    }

    assert validate(GOOD, raw=raw, text_layer=TEXT) == []


def test_unparseable_labelled_date_is_flagged():
    result = {**GOOD, "expiration_date": None, "expiration_status": None}
    raw = {"expiration_date": {"label": "Expires", "text": "Dec. the 31st"}}

    assert "expiration_date 'Dec. the 31st' could not be parsed" in validate(result, raw=raw, text_layer=TEXT)


def test_text_layer_check_is_skipped_for_image_only_documents():
    assert validate({**GOOD, "license_number": "PA20788"}, raw={}, text_layer="  ") == []
