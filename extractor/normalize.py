"""Turns the model's raw answer into the output contract."""

import re
from datetime import date

from extractor.dates import parse_date
from extractor.raw import raw_value
from extractor.status import DEFAULT_WINDOW_DAYS, expiration_status

TEXT_FIELDS = ["holder_name", "credential_type", "license_number", "issuing_authority"]
OUTPUT_FIELDS = ["is_credential", *TEXT_FIELDS, "issue_date", "expiration_date", "expiration_status"]


def _clean(value) -> str | None:
    if not isinstance(value, str):
        return None
    collapsed = " ".join(value.split())
    return collapsed or None


MINOR_WORDS = {"a", "an", "and", "at", "for", "in", "of", "on", "or", "the", "to"}
TITLE_FIELDS = ["credential_type", "issuing_authority"]
LEADING_ARTICLE = re.compile(r"^the\s+", re.IGNORECASE)


def _fix_minor_words(title: str | None) -> str | None:
    if not title:
        return title
    first, *rest = title.split(" ")
    return " ".join([first, *(w.lower() if w.lower() in MINOR_WORDS else w for w in rest)])


def normalize(raw: dict, reference: date, window_days: int = DEFAULT_WINDOW_DAYS) -> dict:
    is_credential = raw.get("is_credential") is True
    if not is_credential:
        return {"is_credential": False} | {f: None for f in OUTPUT_FIELDS[1:]}

    result = {"is_credential": True} | {f: _clean(raw_value(raw, f)) for f in TEXT_FIELDS}
    for field in TITLE_FIELDS:
        result[field] = _fix_minor_words(result[field])
    if result["issuing_authority"]:
        result["issuing_authority"] = LEADING_ARTICLE.sub("", result["issuing_authority"]) or None
    if result["license_number"]:
        result["license_number"] = result["license_number"].replace(" ", "")
    result["issue_date"] = parse_date(_clean(raw_value(raw, "issue_date")))
    result["expiration_date"] = parse_date(_clean(raw_value(raw, "expiration_date")))
    printed_expiration = _clean(raw_value(raw, "expiration_date"))
    if printed_expiration and result["expiration_date"] is None:
        # A date is printed but unreadable: the status is unknown, not "no_expiration".
        result["expiration_status"] = None
    else:
        result["expiration_status"] = expiration_status(True, result["expiration_date"], reference, window_days)
    return result
