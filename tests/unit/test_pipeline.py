from pathlib import Path
from unittest.mock import MagicMock, patch

from cert_validator.backends.base import AnalysisResult
from cert_validator.core.pipeline import (
    _standard_present,
    export_csv,
    validate_batch,
    validate_certificate,
)


def _mock_backend(standards_found, detected_category=None):
    backend = MagicMock()
    result = AnalysisResult(
        standards_found=standards_found,
        document_type="test report",
        lab_name="SafetyFirst Labs",
        date="2025-03-15",
        detected_category=detected_category,
    )
    backend.analyze_images.return_value = result
    backend.analyze_text.return_value = result
    return backend


class TestValidateCertificate:
    @patch("cert_validator.core.pipeline.extract_content")
    def test_all_standards_found(self, mock_extract):
        mock_extract.return_value = [b"fake_png"]
        backend = _mock_backend(
            [
                {"standard": "ASTM F963-17", "normalized": "ASTM F963", "confidence": "high"},
                {
                    "standard": "CPSIA Section 101",
                    "normalized": "CPSIA Section 101",
                    "confidence": "high",
                },
                {"standard": "16 CFR Part 1303", "normalized": "16 CFR 1303", "confidence": "high"},
            ]
        )
        result = validate_certificate(Path("fake.pdf"), "toys", backend=backend)
        assert result["valid"] is True
        assert result["matched"] == 3

    @patch("cert_validator.core.pipeline.extract_content")
    def test_missing_standard(self, mock_extract):
        mock_extract.return_value = [b"fake_png"]
        backend = _mock_backend(
            [
                {"standard": "ASTM F963-17", "normalized": "ASTM F963", "confidence": "high"},
            ]
        )
        result = validate_certificate(Path("fake.pdf"), "toys", backend=backend)
        assert result["valid"] is False
        assert "CPSIA Section 101" in result["missing"]

    def test_unknown_category(self):
        result = validate_certificate(Path("fake.pdf"), "nonexistent_category")
        assert result["valid"] is False
        assert "error" in result

    @patch("cert_validator.core.pipeline.extract_content")
    def test_empty_content(self, mock_extract):
        mock_extract.return_value = []
        result = validate_certificate(Path("fake.pdf"), "toys")
        assert result["valid"] is False

    @patch("cert_validator.core.pipeline.extract_content")
    def test_text_input_uses_analyze_text(self, mock_extract):
        mock_extract.return_value = "ASTM F963 report content"
        backend = _mock_backend(
            [
                {"standard": "ASTM F963", "normalized": "ASTM F963", "confidence": "high"},
                {
                    "standard": "CPSIA Section 101",
                    "normalized": "CPSIA Section 101",
                    "confidence": "high",
                },
                {"standard": "16 CFR 1303", "normalized": "16 CFR 1303", "confidence": "high"},
            ]
        )
        result = validate_certificate(Path("cert.txt"), "toys", backend=backend)
        assert result["valid"] is True
        backend.analyze_text.assert_called_once()

    @patch("cert_validator.core.pipeline.extract_content")
    def test_auto_detect_category(self, mock_extract):
        mock_extract.return_value = [b"fake"]
        backend = _mock_backend(
            [
                {"standard": "ASTM F963", "normalized": "ASTM F963", "confidence": "high"},
                {
                    "standard": "CPSIA Section 101",
                    "normalized": "CPSIA Section 101",
                    "confidence": "high",
                },
                {"standard": "16 CFR 1303", "normalized": "16 CFR 1303", "confidence": "high"},
            ],
            detected_category="toys",
        )
        result = validate_certificate(Path("cert.pdf"), None, backend=backend)
        assert result["valid"] is True
        assert result["category"] == "toys"
        assert result["category_auto_detected"] is True

    @patch("cert_validator.core.pipeline.extract_content")
    def test_auto_detect_fails_gracefully(self, mock_extract):
        mock_extract.return_value = [b"fake"]
        backend = _mock_backend([], detected_category=None)
        result = validate_certificate(Path("cert.pdf"), None, backend=backend)
        assert result["valid"] is False
        assert "auto-detect" in result["error"]


class TestValidateBatch:
    @patch("cert_validator.core.pipeline.find_files")
    @patch("cert_validator.core.pipeline.extract_content")
    def test_processes_multiple(self, mock_extract, mock_find):
        mock_find.return_value = [Path("a.pdf"), Path("b.txt"), Path("c.jpg")]
        mock_extract.return_value = [b"fake"]
        backend = _mock_backend(
            [
                {"standard": "ASTM F963", "normalized": "ASTM F963", "confidence": "high"},
                {
                    "standard": "CPSIA Section 101",
                    "normalized": "CPSIA Section 101",
                    "confidence": "high",
                },
                {"standard": "16 CFR 1303", "normalized": "16 CFR 1303", "confidence": "high"},
            ]
        )
        results = validate_batch(Path("dir/"), "toys", backend=backend)
        assert len(results) == 3
        assert all(r["valid"] for r in results)

    @patch("cert_validator.core.pipeline.find_files")
    def test_no_files(self, mock_find):
        mock_find.return_value = []
        results = validate_batch(Path("empty/"), "toys")
        assert results[0].get("error")

    @patch("cert_validator.core.pipeline.find_files")
    @patch("cert_validator.core.pipeline.extract_content")
    def test_partial_failure(self, mock_extract, mock_find):
        mock_find.return_value = [Path("good.pdf"), Path("bad.pdf")]
        mock_extract.side_effect = [[b"fake"], Exception("corrupt file")]
        backend = _mock_backend(
            [
                {"standard": "ASTM F963", "normalized": "ASTM F963", "confidence": "high"},
                {
                    "standard": "CPSIA Section 101",
                    "normalized": "CPSIA Section 101",
                    "confidence": "high",
                },
                {"standard": "16 CFR 1303", "normalized": "16 CFR 1303", "confidence": "high"},
            ]
        )
        results = validate_batch(Path("dir/"), "toys", backend=backend)
        assert len(results) == 2
        assert results[0]["valid"] is True
        assert results[1]["valid"] is False
        assert "error" in results[1]


class TestExportCSV:
    def test_writes_csv(self, tmp_path):
        results = [
            {
                "file": "a.pdf",
                "valid": True,
                "category": "toys",
                "matched": 3,
                "required": 3,
                "missing": [],
                "lab_name": "Lab",
                "date": "2025-01",
                "document_type": "report",
            },
            {
                "file": "b.pdf",
                "valid": False,
                "category": "toys",
                "matched": 1,
                "required": 3,
                "missing": ["UL 2054", "IEC 62133"],
                "lab_name": None,
                "date": None,
                "document_type": "unknown",
            },
        ]
        out = tmp_path / "out.csv"
        export_csv(results, out)
        assert out.exists()
        content = out.read_text()
        assert "a.pdf" in content
        assert "UL 2054, IEC 62133" in content


class TestStandardPresent:
    def test_exact_match(self):
        assert _standard_present("ASTM F963", {"astm f963"})

    def test_version_suffix(self):
        assert _standard_present("ASTM F963", {"astm f963-17"})

    def test_token_subset(self):
        assert _standard_present("16 CFR 1303", {"16 cfr part 1303"})

    def test_no_match(self):
        assert not _standard_present("UL 2054", {"ul 2034", "iec 62133"})
