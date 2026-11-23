from pathlib import Path
from unittest.mock import MagicMock

from cert_validator.backends.base import AnalysisResult
from cert_validator.core.pipeline import validate_certificate

SAMPLE_DIR = Path(__file__).parent.parent.parent / "data" / "sample_certs"


class TestFullPipeline:
    def test_toy_certificate_passes(self):
        backend = MagicMock()
        backend.analyze_images.return_value = AnalysisResult(
            standards_found=[
                {"standard": "ASTM F963-17", "normalized": "ASTM F963", "confidence": "high"},
                {
                    "standard": "CPSIA Section 101 - Lead Content",
                    "normalized": "CPSIA Section 101",
                    "confidence": "high",
                },
                {"standard": "16 CFR Part 1303", "normalized": "16 CFR 1303", "confidence": "high"},
            ],
            document_type="test report",
            lab_name="SafetyFirst Labs, Inc.",
            date="2025-03-15",
        )
        result = validate_certificate(SAMPLE_DIR / "toy_certificate.pdf", "toys", backend=backend)
        assert result["valid"] is True
        assert result["matched"] == 3
        assert result["lab_name"] == "SafetyFirst Labs, Inc."

    def test_wrong_category_fails(self):
        backend = MagicMock()
        backend.analyze_images.return_value = AnalysisResult(
            standards_found=[
                {"standard": "ASTM F963-17", "normalized": "ASTM F963", "confidence": "high"},
            ],
            document_type="test report",
            lab_name="Lab",
            date=None,
        )
        result = validate_certificate(
            SAMPLE_DIR / "toy_certificate.pdf", "batteries", backend=backend
        )
        assert result["valid"] is False
        assert len(result["missing"]) > 0
