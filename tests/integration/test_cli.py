"""The `certainty` command end to end, with only the analysis backend replaced.

A real .txt certificate goes through the real extractor, rules and reporting; the stand-in
backend answers as an LLM/OCR service would, so no cloud call is made. These tests were added
because the CLI had none at all, which kept the project under its own 70% coverage gate.
"""

import csv
import json

import pytest
from click.testing import CliRunner

from cert_validator import cli
from cert_validator.backends.base import AnalysisBackend, AnalysisResult

ALL_TOY_STANDARDS = [
    {"standard": "ASTM F963-17", "normalized": "ASTM F963", "confidence": "high"},
    {"standard": "CPSIA Section 101", "normalized": "CPSIA Section 101", "confidence": "high"},
    {"standard": "16 CFR Part 1303", "normalized": "16 CFR 1303", "confidence": "high"},
]


class StandIn(AnalysisBackend):
    def __init__(self, standards, detected_category=None):
        self.result = AnalysisResult(
            standards_found=standards,
            document_type="test report",
            lab_name="SafetyFirst Labs",
            date="2025-03-15",
            detected_category=detected_category,
        )
        self.calls = 0

    def analyze_images(self, images):
        self.calls += 1
        return self.result

    def analyze_text(self, text):
        self.calls += 1
        return self.result


@pytest.fixture
def cert(tmp_path):
    path = tmp_path / "toy_cert.txt"
    path.write_text("Test report. ASTM F963-17. CPSIA Section 101.", encoding="utf-8")
    return path


def run(monkeypatch, backend, *args):
    monkeypatch.setattr(cli, "get_backend", lambda name, **kw: backend)
    return CliRunner().invoke(cli.main, [str(a) for a in args])


def test_list_categories_needs_no_backend(tmp_path):
    result = CliRunner().invoke(cli.main, [str(tmp_path), "--list-categories"])
    assert result.exit_code == 0
    assert "toys" in result.output


def test_a_certificate_with_every_required_standard_passes(monkeypatch, cert):
    result = run(monkeypatch, StandIn(ALL_TOY_STANDARDS), cert, "--category", "toys")
    assert result.exit_code == 0, result.output
    assert "PASS: 3/3 standards found" in result.output
    assert "Lab: SafetyFirst Labs" in result.output
    assert "Date: 2025-03-15" in result.output
    assert 'Found: ASTM F963 → "ASTM F963-17" (high)' in result.output


def test_a_missing_standard_fails_and_is_named(monkeypatch, cert):
    result = run(monkeypatch, StandIn(ALL_TOY_STANDARDS[:2]), cert, "--category", "toys")
    assert "FAIL: 2/3 standards found" in result.output
    assert "Missing: 16 CFR 1303" in result.output


def test_the_category_can_be_auto_detected(monkeypatch, cert):
    result = run(monkeypatch, StandIn(ALL_TOY_STANDARDS, detected_category="toys"), cert)
    assert "Category (auto-detected): toys" in result.output


def test_a_directory_is_validated_file_by_file(monkeypatch, cert):
    (cert.parent / "second.txt").write_text("Another report.", encoding="utf-8")
    backend = StandIn(ALL_TOY_STANDARDS)
    result = run(monkeypatch, backend, cert.parent, "--category", "toys")
    assert result.output.count("PASS: 3/3") == 2
    assert backend.calls == 2


def test_json_output(monkeypatch, cert, tmp_path):
    out = tmp_path / "results.json"
    result = run(monkeypatch, StandIn(ALL_TOY_STANDARDS), cert, "--category", "toys",
                 "--output", out)
    assert f"Results written to {out}" in result.output
    [record] = json.loads(out.read_text(encoding="utf-8"))
    assert record["valid"] is True
    assert record["matched"] == 3


def test_csv_output(monkeypatch, cert, tmp_path):
    out = tmp_path / "results.csv"
    run(monkeypatch, StandIn(ALL_TOY_STANDARDS[:2]), cert, "--category", "toys", "--output", out)
    with out.open(encoding="utf-8", newline="") as fh:
        [row] = list(csv.DictReader(fh))
    assert row["valid"] in ("False", "false")


def test_consensus_needs_exactly_two_backends(monkeypatch, cert):
    result = run(monkeypatch, StandIn([]), cert, "--consensus", "claude")
    assert "requires exactly two backends" in result.output


def test_consensus_combines_two_backends(monkeypatch, cert):
    result = run(monkeypatch, StandIn(ALL_TOY_STANDARDS), cert, "--category", "toys",
                 "--consensus", "claude,textract")
    assert result.exit_code == 0, result.output
    assert "Using consensus: claude + textract" in result.output


def test_an_error_result_is_printed_as_an_error(capsys):
    cli._print_result({"error": "could not read file"})
    assert "ERROR: could not read file" in capsys.readouterr().out
