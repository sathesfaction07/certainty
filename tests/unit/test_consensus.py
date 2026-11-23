"""Unit tests for confidence-weighted consensus backend."""
from unittest.mock import MagicMock

from cert_validator.backends.base import AnalysisResult
from cert_validator.backends.consensus import ConsensusBackend


def _mock_backend(standards_found, should_fail=False):
    """Create a mock backend that returns the given standards or raises an exception."""
    backend = MagicMock()
    if should_fail:
        backend.analyze_images.side_effect = Exception("Backend failure")
        backend.analyze_text.side_effect = Exception("Backend failure")
    else:
        result = AnalysisResult(
            standards_found=standards_found,
            document_type="test report",
            lab_name="Test Lab",
            date="2025-01-01",
            detected_category="toys",
        )
        backend.analyze_images.return_value = result
        backend.analyze_text.return_value = result
    return backend


class TestConsensusAgreement:
    """Test cases where both backends find the same standards."""

    def test_both_agree_high_confidence(self):
        """Both backends find the same standard with high confidence."""
        primary = _mock_backend(
            [{"standard": "ASTM F963-17", "normalized": "ASTM F963", "confidence": "high"}]
        )
        secondary = _mock_backend(
            [{"standard": "ASTM F963-17", "normalized": "ASTM F963", "confidence": "high"}]
        )
        consensus = ConsensusBackend(primary, secondary)

        result = consensus.analyze_images([b"fake"])

        assert len(result.standards_found) == 1
        assert result.standards_found[0]["standard"] == "ASTM F963-17"
        assert result.standards_found[0]["confidence"] == "high"

    def test_agreement_prefers_max_confidence(self):
        """When both find the same standard, the higher confidence version is selected."""
        primary = _mock_backend(
            [{"standard": "ASTM F963", "normalized": "ASTM F963", "confidence": "medium"}]
        )
        secondary = _mock_backend(
            [{"standard": "ASTM F963", "normalized": "ASTM F963", "confidence": "high"}]
        )
        consensus = ConsensusBackend(primary, secondary)

        result = consensus.analyze_images([b"fake"])

        assert len(result.standards_found) == 1
        assert result.standards_found[0]["confidence"] == "high"

    def test_agreement_prefers_primary_on_tie(self):
        """When confidences are equal, prefer primary backend."""
        primary = _mock_backend(
            [
                {
                    "standard": "ASTM F963-17",
                    "normalized": "ASTM F963",
                    "confidence": "high",
                }
            ]
        )
        secondary = _mock_backend(
            [
                {
                    "standard": "ASTM F963-20",
                    "normalized": "ASTM F963",
                    "confidence": "high",
                }
            ]
        )
        consensus = ConsensusBackend(primary, secondary)

        result = consensus.analyze_images([b"fake"])

        # Should prefer primary's version (2017) over secondary's (2020)
        assert len(result.standards_found) == 1
        assert result.standards_found[0]["standard"] == "ASTM F963-17"


class TestConsensusDisagreement:
    """Test cases where backends disagree on confidence levels."""

    def test_higher_confidence_wins(self):
        """The backend with higher confidence for a standard wins."""
        primary = _mock_backend(
            [{"standard": "UL 2054", "normalized": "UL 2054", "confidence": "low"}]
        )
        secondary = _mock_backend(
            [{"standard": "UL 2054", "normalized": "UL 2054", "confidence": "high"}]
        )
        consensus = ConsensusBackend(primary, secondary)

        result = consensus.analyze_images([b"fake"])

        assert len(result.standards_found) == 1
        assert result.standards_found[0]["confidence"] == "high"

    def test_multiple_standards_different_confidences(self):
        """Multiple standards, each with different confidence from each backend."""
        primary = _mock_backend(
            [
                {"standard": "ASTM F963", "normalized": "ASTM F963", "confidence": "high"},
                {"standard": "UL 2054", "normalized": "UL 2054", "confidence": "low"},
            ]
        )
        secondary = _mock_backend(
            [
                {"standard": "ASTM F963", "normalized": "ASTM F963", "confidence": "medium"},
                {"standard": "UL 2054", "normalized": "UL 2054", "confidence": "high"},
            ]
        )
        consensus = ConsensusBackend(primary, secondary)

        result = consensus.analyze_images([b"fake"])

        assert len(result.standards_found) == 2
        # ASTM F963: primary wins (high > medium)
        astm = next(s for s in result.standards_found if "F963" in s["standard"])
        assert astm["confidence"] == "high"
        # UL 2054: secondary wins (high > low)
        ul = next(s for s in result.standards_found if "2054" in s["standard"])
        assert ul["confidence"] == "high"


class TestConsensusUniqueFindings:
    """Test cases where one backend finds standards the other doesn't."""

    def test_unique_high_confidence_included(self):
        """Unique findings with high confidence are included."""
        primary = _mock_backend(
            [{"standard": "ASTM F963", "normalized": "ASTM F963", "confidence": "high"}]
        )
        secondary = _mock_backend(
            [{"standard": "UL 2054", "normalized": "UL 2054", "confidence": "high"}]
        )
        consensus = ConsensusBackend(primary, secondary)

        result = consensus.analyze_images([b"fake"])

        assert len(result.standards_found) == 2
        standards = {s["standard"] for s in result.standards_found}
        assert standards == {"ASTM F963", "UL 2054"}

    def test_unique_medium_confidence_included(self):
        """Unique findings with medium confidence are included."""
        primary = _mock_backend(
            [{"standard": "ASTM F963", "normalized": "ASTM F963", "confidence": "medium"}]
        )
        secondary = _mock_backend([])
        consensus = ConsensusBackend(primary, secondary)

        result = consensus.analyze_images([b"fake"])

        assert len(result.standards_found) == 1
        assert result.standards_found[0]["standard"] == "ASTM F963"

    def test_unique_low_confidence_excluded(self):
        """Unique findings with low confidence are excluded."""
        primary = _mock_backend(
            [{"standard": "ASTM F963", "normalized": "ASTM F963", "confidence": "low"}]
        )
        secondary = _mock_backend([])
        consensus = ConsensusBackend(primary, secondary)

        result = consensus.analyze_images([b"fake"])

        assert len(result.standards_found) == 0


class TestConsensusBackendFailure:
    """Test cases where one or both backends fail."""

    def test_primary_fails_use_secondary(self):
        """If primary fails, use secondary results."""
        primary = _mock_backend([], should_fail=True)
        secondary = _mock_backend(
            [{"standard": "ASTM F963", "normalized": "ASTM F963", "confidence": "high"}]
        )
        consensus = ConsensusBackend(primary, secondary)

        result = consensus.analyze_images([b"fake"])

        assert len(result.standards_found) == 1
        assert result.standards_found[0]["standard"] == "ASTM F963"

    def test_secondary_fails_use_primary(self):
        """If secondary fails, use primary results."""
        primary = _mock_backend(
            [{"standard": "UL 2054", "normalized": "UL 2054", "confidence": "high"}]
        )
        secondary = _mock_backend([], should_fail=True)
        consensus = ConsensusBackend(primary, secondary)

        result = consensus.analyze_images([b"fake"])

        assert len(result.standards_found) == 1
        assert result.standards_found[0]["standard"] == "UL 2054"

    def test_both_fail_returns_empty(self):
        """If both backends fail, return empty result."""
        primary = _mock_backend([], should_fail=True)
        secondary = _mock_backend([], should_fail=True)
        consensus = ConsensusBackend(primary, secondary)

        result = consensus.analyze_images([b"fake"])

        assert len(result.standards_found) == 0
        assert result.document_type == "unknown"


class TestConsensusZeroConfidence:
    """Test cases involving missing or zero confidence."""

    def test_missing_confidence_treated_as_low(self):
        """Standards without a confidence field are treated as low confidence."""
        primary = _mock_backend(
            [{"standard": "ASTM F963", "normalized": "ASTM F963"}]  # no confidence field
        )
        secondary = _mock_backend([])
        consensus = ConsensusBackend(primary, secondary)

        result = consensus.analyze_images([b"fake"])

        # Unique finding with implicit low confidence should be excluded
        assert len(result.standards_found) == 0

    def test_empty_confidence_treated_as_low(self):
        """Standards with empty confidence string are treated as low."""
        primary = _mock_backend(
            [{"standard": "ASTM F963", "normalized": "ASTM F963", "confidence": ""}]
        )
        secondary = _mock_backend(
            [{"standard": "ASTM F963", "normalized": "ASTM F963", "confidence": "high"}]
        )
        consensus = ConsensusBackend(primary, secondary)

        result = consensus.analyze_images([b"fake"])

        # Should select secondary's high confidence version
        assert len(result.standards_found) == 1
        assert result.standards_found[0]["confidence"] == "high"

    def test_both_return_zero_confidence(self):
        """When both backends return standards with no/low confidence."""
        primary = _mock_backend(
            [{"standard": "ASTM F963", "normalized": "ASTM F963", "confidence": "low"}]
        )
        secondary = _mock_backend(
            [{"standard": "ASTM F963", "normalized": "ASTM F963", "confidence": "low"}]
        )
        consensus = ConsensusBackend(primary, secondary)

        result = consensus.analyze_images([b"fake"])

        # Both found it with low confidence, so include it (not unique)
        assert len(result.standards_found) == 1
        assert result.standards_found[0]["confidence"] == "low"


class TestConsensusMetadata:
    """Test consensus behavior for document metadata."""

    def test_metadata_prefers_primary(self):
        """Metadata fields prefer primary backend when both provide values."""
        primary = _mock_backend([])
        primary.analyze_images.return_value = AnalysisResult(
            document_type="certificate",
            lab_name="Primary Lab",
            date="2025-01-15",
            detected_category="batteries",
        )
        secondary = _mock_backend([])
        secondary.analyze_images.return_value = AnalysisResult(
            document_type="report",
            lab_name="Secondary Lab",
            date="2025-01-20",
            detected_category="toys",
        )
        consensus = ConsensusBackend(primary, secondary)

        result = consensus.analyze_images([b"fake"])

        assert result.document_type == "certificate"
        assert result.lab_name == "Primary Lab"
        assert result.date == "2025-01-15"
        assert result.detected_category == "batteries"

    def test_metadata_fallback_to_secondary(self):
        """Metadata falls back to secondary when primary has None values."""
        primary = _mock_backend([])
        primary.analyze_images.return_value = AnalysisResult(
            lab_name=None, date=None, detected_category=None
        )
        secondary = _mock_backend([])
        secondary.analyze_images.return_value = AnalysisResult(
            lab_name="Secondary Lab", date="2025-01-20", detected_category="toys"
        )
        consensus = ConsensusBackend(primary, secondary)

        result = consensus.analyze_images([b"fake"])

        assert result.lab_name == "Secondary Lab"
        assert result.date == "2025-01-20"
        assert result.detected_category == "toys"


class TestConsensusAnalyzeText:
    """Test that analyze_text also uses consensus logic."""

    def test_analyze_text_merges_standards(self):
        """analyze_text method applies the same consensus logic."""
        primary = _mock_backend(
            [{"standard": "ASTM F963", "normalized": "ASTM F963", "confidence": "high"}]
        )
        secondary = _mock_backend(
            [{"standard": "UL 2054", "normalized": "UL 2054", "confidence": "high"}]
        )
        consensus = ConsensusBackend(primary, secondary)

        result = consensus.analyze_text("fake text content")

        assert len(result.standards_found) == 2
        standards = {s["standard"] for s in result.standards_found}
        assert standards == {"ASTM F963", "UL 2054"}
