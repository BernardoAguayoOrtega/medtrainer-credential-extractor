"""Deterministic checks on an extraction. They never change values; they return
warnings so a human reviews the document instead of trusting a wrong field."""

import re
from difflib import SequenceMatcher

from extractor.raw import raw_label, raw_value

MIN_YEAR, MAX_YEAR = 1950, 2100
MIN_TEXT_LAYER_CHARS = 200  # below this the PDF is image-only; nothing to check against


MIN_SIMILARITY = 0.8  # tolerates OCR losing or garbling 1-2 characters

# A label that contradicts the field it was extracted into.
SUSPICIOUS_LABELS = {
    "license_number": re.compile(r"receipt|notice|invoice|board action|order|account|amount|check", re.IGNORECASE),
    "issue_date": re.compile(r"expir|through|until|valid to|renew", re.IGNORECASE),
    "expiration_date": re.compile(r"issued|issue date|original|notice date|birth", re.IGNORECASE),
}


def _alnum(text: str) -> str:
    return re.sub(r"[^0-9a-z]", "", text.lower())


def _in_text_layer(number: str, text_layer: str) -> bool:
    target = _alnum(number)
    if target in _alnum(text_layer):
        return True
    tokens = [_alnum(t) for t in text_layer.split()]
    return any(SequenceMatcher(None, target, t).ratio() >= MIN_SIMILARITY for t in tokens if t)


def validate(result: dict, raw: dict, text_layer: str) -> list[str]:
    if not result.get("is_credential"):
        return []
    warnings = []

    for field in ("holder_name", "license_number"):
        if not result.get(field):
            warnings.append(f"{field} is missing")

    for field, pattern in SUSPICIOUS_LABELS.items():
        label = raw_label(raw, field)
        if label and pattern.search(label):
            warnings.append(f"{field} comes from a field labelled {label!r}")

    for field in ("issue_date", "expiration_date"):
        printed = raw_value(raw, field)
        if result.get(field) is None and isinstance(printed, str) and printed.strip():
            warnings.append(f"{field} {printed.strip()!r} could not be parsed")
        elif result.get(field):
            year = int(result[field][:4])
            if not MIN_YEAR <= year <= MAX_YEAR:
                warnings.append(f"{field} year {year} looks implausible")

    issued, expires = result.get("issue_date"), result.get("expiration_date")
    if issued and expires and issued > expires:
        warnings.append("issue_date is after expiration_date")

    number = result.get("license_number")
    if number:
        if not re.search(r"\d", number):
            warnings.append("license_number has no digits")
        elif len(text_layer.strip()) >= MIN_TEXT_LAYER_CHARS and not _in_text_layer(number, text_layer):
            warnings.append("license_number not found in the PDF text layer")

    return warnings
