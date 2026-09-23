"""CLI roundtrip."""
from moth_honest.cli import main


def test_plant_cli(tmp_path, capsys):
    out = str(tmp_path / "ex")
    assert main(["plant", "--lang", "c", "-o", out]) == 0
    assert "c-overflow-001" in capsys.readouterr().out


def test_evaluate_verify_cli(tmp_path):
    import json
    report = tmp_path / "report.json"
    report.write_text(json.dumps({
        "hunter_id": "cli-test",
        "claims": [{"exercise_id": "c-overflow-001", "file": "main.c",
                    "line": 8, "bug_class": "buffer_overflow",
                    "confidence_q16": 32768}],
        "refusals": [{"exercise_id": "c-clean-001"}],
    }))
    out = str(tmp_path / "eval.jsonl")
    assert main(["evaluate", "--report", str(report), "-o", out]) == 0
    assert main(["verify", out]) == 0
