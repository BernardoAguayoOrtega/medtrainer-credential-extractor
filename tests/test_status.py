from datetime import date

import pytest

from extractor.status import expiration_status

REF = date(2026, 11, 1)


@pytest.mark.parametrize(
    "expiration, expected",
    [
        ("2026-02-28", "expired"),
        ("2026-10-31", "expired"),
        ("2026-11-01", "expiring_soon"),  # still valid on its expiration day
        ("2026-11-30", "expiring_soon"),
        ("2026-12-31", "expiring_soon"),  # day 60 is inside the window
        ("2027-01-01", "valid"),  # day 61
        ("2028-03-31", "valid"),
        (None, "no_expiration"),
    ],
)
def test_status_against_reference_date(expiration, expected):
    assert expiration_status(True, expiration, REF) == expected


def test_window_is_configurable():
    assert expiration_status(True, "2026-11-30", REF, window_days=10) == "valid"


def test_not_a_credential_has_no_status():
    assert expiration_status(False, "2027-01-01", REF) is None
