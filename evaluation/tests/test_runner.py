import json
import shutil
from pathlib import Path

import pytest

from evaluation.runner import main


def test_runner_writes_immutable_and_stable_reports() -> None:
    # The managed Windows sandbox may deny pytest's user-temp root, so this test
    # uses a verified workspace-local scratch directory and always removes it.
    output = Path(__file__).resolve().parent / "_runner_output"
    assert output.parent == Path(__file__).resolve().parent
    if output.exists():
        shutil.rmtree(output)
    try:
        assert main([
            "--adapter", "python",
            "--target", "evaluation.tests.fixture_adapter:adapter",
            "--output-dir", str(output),
            "--run-id", "fixture-run",
            "--experiment", "D",
            "--limit", "2",
            "--progress-every", "0",
        ]) == 0
        immutable = json.loads((output / "fixture-run" / "metrics.json").read_text(encoding="utf-8"))
        stable = json.loads((output / "latest.json").read_text(encoding="utf-8"))
        assert immutable == stable
        assert immutable["metadata"]["corpus"]["document_count"] == 12
        assert immutable["experiments"][0]["queries"] == 2
        assert immutable["experiments"][0]["recall_at_5"] == 1.0
    finally:
        if output.exists():
            shutil.rmtree(output)


def test_failed_gate_does_not_replace_latest_report() -> None:
    output = Path(__file__).resolve().parent / "_failed_runner_output"
    assert output.parent == Path(__file__).resolve().parent
    if output.exists():
        shutil.rmtree(output)
    output.mkdir()
    sentinel = {"status": "COMPLETED", "metadata": {"run_id": "accepted-run"}}
    (output / "latest.json").write_text(json.dumps(sentinel), encoding="utf-8")
    try:
        with pytest.raises(RuntimeError, match="error rate"):
            main([
                "--adapter", "python",
                "--target", "evaluation.tests.fixture_adapter:failing_adapter",
                "--output-dir", str(output),
                "--run-id", "failed-run",
                "--experiment", "A",
                "--limit", "1",
                "--progress-every", "0",
                "--max-error-rate", "0",
            ])
        assert json.loads((output / "latest.json").read_text(encoding="utf-8")) == sentinel
        failed = json.loads((output / "failed-run" / "metrics.json").read_text(encoding="utf-8"))
        assert failed["status"] == "FAILED"
        assert failed["metadata"]["gate_failure"]["actual"] == 1.0
    finally:
        if output.exists():
            shutil.rmtree(output)
