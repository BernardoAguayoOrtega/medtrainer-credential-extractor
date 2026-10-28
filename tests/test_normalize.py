from datetime import date

from extractor.normalize import normalize

REF = date(2026, 11, 1)

RAW = {
    "document_kind": "Texas physician license wall certificate",
    "is_credential": True,
    "holder_name": "  ROBERT ALAN   MITCHELL JR. ",
    "credential_type": "Physician License",
    "license_number": " Q 8150 ",
    "issuing_authority": "Texas Board of Medical Licensure",
    "issue_date": None,
    "expiration_date": "11/30/2026",
}


def test_produces_exactly_the_contract_fields():
    assert list(normalize(RAW, REF)) == [
        "is_credential",
        "holder_name",
        "credential_type",
        "license_number",
        "issuing_authority",
        "issue_date",
        "expiration_date",
        "expiration_status",
    ]


def test_cleans_values_and_computes_status():
    result = normalize(RAW, REF)

    assert result["holder_name"] == "ROBERT ALAN MITCHELL JR."
    assert result["license_number"] == "Q8150"
    assert result["expiration_date"] == "2026-11-30"
    assert result["expiration_status"] == "expiring_soon"


def test_minor_words_are_lowercase_inside_titles():
    result = normalize(
        {**RAW, "credential_type": "Certificate Of Registration", "issuing_authority": "The Board Of Nursing And Midwifery"},
        REF,
    )

    assert result["credential_type"] == "Certificate of Registration"
    assert result["issuing_authority"] == "Board of Nursing and Midwifery"


def test_leading_article_is_dropped_from_issuing_authority():
    result = normalize({**RAW, "issuing_authority": "The State of New York Department of Health"}, REF)

    assert result["issuing_authority"] == "State of New York Department of Health"


def test_unparseable_expiration_is_unknown_not_no_expiration():
    result = normalize({**RAW, "expiration_date": "Dec. the 31st"}, REF)

    assert result["expiration_date"] is None
    assert result["expiration_status"] is None


def test_holder_name_casing_is_never_touched():
    result = normalize({**RAW, "holder_name": "Rafael Ignacio De La Cruz"}, REF)

    assert result["holder_name"] == "Rafael Ignacio De La Cruz"


def test_accepts_labelled_fields_from_the_schema():
    raw = {
        **RAW,
        "license_number": {"label": "LICENSE NUMBER", "value": "Q8150"},
        "issue_date": {"label": None, "text": None},
        "expiration_date": {"label": "EXPIRATION DATE", "text": "11/30/2026"},
    }

    result = normalize(raw, REF)

    assert result["license_number"] == "Q8150"
    assert result["issue_date"] is None
    assert result["expiration_date"] == "2026-11-30"


def test_blank_strings_become_null():
    result = normalize({**RAW, "credential_type": "  ", "issue_date": ""}, REF)

    assert result["credential_type"] is None
    assert result["issue_date"] is None


def test_missing_expiration_means_no_expiration():
    result = normalize({**RAW, "expiration_date": None}, REF)

    assert result["expiration_status"] == "no_expiration"


def test_non_credential_nulls_every_field():
    result = normalize({**RAW, "is_credential": False}, REF)

    assert result == {"is_credential": False} | {k: None for k in list(result)[1:]}
