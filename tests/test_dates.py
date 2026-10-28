import pytest

from extractor.dates import parse_date


@pytest.mark.parametrize(
    "text, expected",
    [
        ("2026-12-15", "2026-12-15"),
        ("12/15/2026", "2026-12-15"),
        ("12/15/26", "2026-12-15"),
        ("02-28-2026", "2026-02-28"),
        ("March 4, 2027", "2027-03-04"),
        ("Mar 4 2027", "2027-03-04"),
        ("March 4th, 2027", "2027-03-04"),
        ("4 March 2027", "2027-03-04"),
        ("04-MAR-2027", "2027-03-04"),
        ("2027/03/04", "2027-03-04"),
        ("  08/31/2027 ", "2027-08-31"),
    ],
)
def test_parses_common_formats_to_iso(text, expected):
    assert parse_date(text) == expected


def test_us_month_first_wins_when_ambiguous():
    assert parse_date("03/04/2027") == "2027-03-04"


def test_falls_back_to_day_first_when_month_first_is_impossible():
    assert parse_date("15/12/2026") == "2026-12-15"


@pytest.mark.parametrize("text", [None, "", "  ", "N/A", "none", "not printed", "13/32/2026"])
def test_unparseable_or_missing_returns_none(text):
    assert parse_date(text) is None
