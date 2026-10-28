import json
from datetime import date
from pathlib import Path

from run import load_reference, run_batch

DOCS = Path(__file__).parent.parent / "docs"


def test_load_reference_reads_the_eval_date():
    reference, window = load_reference(Path(__file__).parent.parent / "expected" / "_reference.json")

    assert reference == date(2026, 11, 1)
    assert window == 60


def test_run_batch_writes_outputs_and_cost_log(tmp_path):
    def call(images, model):
        return {"is_credential": False}, {"cost": 0.0002}

    summary = run_batch([DOCS / "al_03.pdf", DOCS / "tx_02.pdf"], tmp_path, date(2026, 11, 1), "m", call=call)

    assert json.loads((tmp_path / "al_03.json").read_text())["is_credential"] is False
    log = json.loads((tmp_path / "_run.json").read_text())
    assert log["model"] == "m"
    assert log["documents"]["tx_02"]["cost"] == 0.0002
    assert summary["total_cost"] == 0.0004


def test_run_batch_merges_with_a_previous_log_of_the_same_model(tmp_path):
    def call(images, model):
        return {"is_credential": False}, {"cost": 0.0002}

    run_batch([DOCS / "al_03.pdf"], tmp_path, date(2026, 11, 1), "m", call=call)
    summary = run_batch([DOCS / "tx_02.pdf"], tmp_path, date(2026, 11, 1), "m", call=call)

    log = json.loads((tmp_path / "_run.json").read_text())
    assert set(log["documents"]) == {"al_03", "tx_02"}
    assert summary["total_cost"] == 0.0004


def test_run_batch_records_errors_without_stopping(tmp_path):
    def call(images, model):
        raise RuntimeError("boom")

    summary = run_batch([DOCS / "al_03.pdf"], tmp_path, date(2026, 11, 1), "m", call=call)

    assert json.loads((tmp_path / "al_03.json").read_text()) == {"error": "boom"}
    assert summary["errors"] == 1
