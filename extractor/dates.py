"""Deterministic date parsing: the model copies dates as printed, code turns them into ISO 8601."""

import re
from datetime import datetime

# Month-first before day-first: the documents are US credentials.
FORMATS = [
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%m/%d/%Y",
    "%m/%d/%y",
    "%m-%d-%Y",
    "%m-%d-%y",
    "%m.%d.%Y",
    "%B %d %Y",
    "%b %d %Y",
    "%d %B %Y",
    "%d %b %Y",
    "%d-%b-%Y",
    "%d/%m/%Y",
    "%d-%m-%Y",
]

_ORDINAL = re.compile(r"(\d)(st|nd|rd|th)\b", re.IGNORECASE)


def parse_date(text: str | None) -> str | None:
    """Return the date as YYYY-MM-DD, or None when it is missing or unreadable."""
    if not text or not text.strip():
        return None
    cleaned = _ORDINAL.sub(r"\1", text.strip()).replace(",", " ")
    cleaned = " ".join(cleaned.split())
    for fmt in FORMATS:
        try:
            return datetime.strptime(cleaned, fmt).date().isoformat()
        except ValueError:
            continue
    return None
