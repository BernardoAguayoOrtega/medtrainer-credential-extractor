import json
from pathlib import Path

import pytest

from evaluate import FIELDS, evaluate, field_matches

CREDENTIAL = {
    "is_credential": True,
    "holder_name": "DEVIN KOFI ASANTE",
    "credential_type": "Physician Assistant License",
    "license_number": "PA20733",
    "issuing_authority": "Texas Physician Assistant Licensing Board",
    "issue_date": None,
    "expiration_date": "2026-02-28",
    "expiration_status": "expired",
}


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


@pytest.fixture
def dirs(tmp_path):
    expected, outputs = tmp_path / "expected", tmp_path / "outputs"
    write_json(expected / "_reference.json", {"reference_date": "2026-11-01"})
    write_json(expected / "tx_02.json", CREDENTIAL)
    return expected, outputs


class TestFieldMatches:
    def test_identical_values_match(self):
        assert field_matches("PA20733", "PA20733")

    def test_null_matches_only_null(self):
        assert field_matches(None, None)
        assert not field_matches(None, "2026-02-28")
        assert not field_matches("2026-02-28", None)

    def test_strict_mode_is_case_and_space_sensitive(self):
        assert not field_matches("DEVIN KOFI ASANTE", "Devin Kofi Asante")
        assert not field_matches("PA20733", "PA 20733")

    def test_lenient_mode_ignores_case_and_extra_whitespace(self):
        assert field_matches("DEVIN KOFI ASANTE", "devin  kofi asante ", lenient=True)

    def test_lenient_mode_does_not_ignore_inner_characters(self):
        assert not field_matches("PA20733", "PA 20733", lenient=True)

    def test_booleans_are_not_strings(self):
        assert field_matches(True, True)
        assert not field_matches(True, "true")


class TestEvaluate:
    def test_perfect_output_scores_100(self, dirs):
        expected, outputs = dirs
        write_json(outputs / "tx_02.json", CREDENTIAL)

        report = evaluate(expected, outputs)

        assert report["documents"] == 1
        assert all(report["fields"][f]["strict"] == 1.0 for f in FIELDS)
        assert report["overall"]["strict"] == 1.0
        assert report["mismatches"] == []

    def test_reference_file_is_not_a_document(self, dirs):
        expected, outputs = dirs
        write_json(outputs / "tx_02.json", CREDENTIAL)

        assert evaluate(expected, outputs)["documents"] == 1

    def test_wrong_field_is_reported(self, dirs):
        expected, outputs = dirs
        write_json(outputs / "tx_02.json", {**CREDENTIAL, "expiration_status": "valid"})

        report = evaluate(expected, outputs)

        assert report["fields"]["expiration_status"]["strict"] == 0.0
        assert report["fields"]["license_number"]["strict"] == 1.0
        assert report["overall"]["strict"] == pytest.approx(7 / 8)
        assert report["mismatches"] == [
            {"document": "tx_02", "field": "expiration_status", "expected": "expired", "actual": "valid"}
        ]

    def test_missing_field_counts_as_null(self, dirs):
        expected, outputs = dirs
        output = {k: v for k, v in CREDENTIAL.items() if k != "issue_date"}
        write_json(outputs / "tx_02.json", output)

        assert evaluate(expected, outputs)["fields"]["issue_date"]["strict"] == 1.0

    def test_missing_output_file_fails_every_field(self, dirs):
        expected, outputs = dirs
        outputs.mkdir()

        report = evaluate(expected, outputs)

        assert report["overall"]["strict"] == 0.0
        assert report["errors"] == ["tx_02: missing output"]

    def test_extractor_error_fails_every_field(self, dirs):
        expected, outputs = dirs
        write_json(outputs / "tx_02.json", {"error": "invalid JSON from model", "raw": "oops"})

        report = evaluate(expected, outputs)

        assert report["overall"]["strict"] == 0.0
        assert report["errors"] == ["tx_02: invalid JSON from model"]

    def test_lenient_score_forgives_case_only(self, dirs):
        expected, outputs = dirs
        write_json(outputs / "tx_02.json", {**CREDENTIAL, "holder_name": "Devin Kofi Asante"})

        holder = evaluate(expected, outputs)["fields"]["holder_name"]

        assert holder == {"strict": 0.0, "lenient": 1.0}

    def test_document_accuracy_requires_every_field(self, dirs):
        expected, outputs = dirs
        write_json(expected / "al_03.json", {f: None for f in FIELDS} | {"is_credential": False})
        write_json(outputs / "tx_02.json", CREDENTIAL)
        write_json(outputs / "al_03.json", {f: None for f in FIELDS} | {"is_credential": True})

        report = evaluate(expected, outputs)

        assert report["documents"] == 2
        assert report["exact_documents"] == 1
