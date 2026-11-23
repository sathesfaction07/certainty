"""Confidence-weighted consensus across multiple extraction providers.

Combines results from two backends, weighting each provider's contribution by
the reported confidence level of each standard. This improves extraction accuracy
when providers disagree.

Consensus Rules:
1. Agreement: Both backends find the same standard → include with max confidence
2. Disagreement: Different confidences → higher-confidence provider wins
3. Unique findings: Standard found by only one backend → include if confidence ≥ medium
4. Backend error: If one backend fails, use the successful backend's results
5. Zero/missing confidence: Treated as "low" confidence for weighting

Confidence weights: high=3, medium=2, low=1
"""
from __future__ import annotations

import logging

from .base import AnalysisBackend, AnalysisResult

logger = logging.getLogger("cert_validator")

CONFIDENCE_WEIGHTS = {"high": 3, "medium": 2, "low": 1}


class ConsensusBackend(AnalysisBackend):
    """Runs two backends and combines their results via confidence weighting."""

    def __init__(self, primary: AnalysisBackend, secondary: AnalysisBackend):
        self.primary = primary
        self.secondary = secondary

    def analyze_images(self, images: list[bytes]) -> AnalysisResult:
        return self._consensus(
            lambda: self.primary.analyze_images(images),
            lambda: self.secondary.analyze_images(images),
        )

    def analyze_text(self, text: str) -> AnalysisResult:
        return self._consensus(
            lambda: self.primary.analyze_text(text),
            lambda: self.secondary.analyze_text(text),
        )

    def _consensus(self, primary_fn, secondary_fn) -> AnalysisResult:
        """Run both backends and merge results by confidence weighting."""
        # Run both backends (fallback if one fails)
        primary_result = self._safe_call(primary_fn, "primary")
        secondary_result = self._safe_call(secondary_fn, "secondary")

        # If both failed, return empty result
        if primary_result is None and secondary_result is None:
            logger.error("Both backends failed, returning empty result")
            return AnalysisResult()

        # If one failed, use the other
        if primary_result is None:
            logger.warning("Primary backend failed, using secondary only")
            return secondary_result
        if secondary_result is None:
            logger.warning("Secondary backend failed, using primary only")
            return primary_result

        # Both succeeded: merge with confidence weighting
        merged_standards = self._merge_standards(
            primary_result.standards_found, secondary_result.standards_found
        )

        # Merge metadata (prefer primary, fallback to secondary)
        return AnalysisResult(
            standards_found=merged_standards,
            document_type=primary_result.document_type or secondary_result.document_type,
            lab_name=primary_result.lab_name or secondary_result.lab_name,
            date=primary_result.date or secondary_result.date,
            detected_category=primary_result.detected_category
            or secondary_result.detected_category,
            raw_response=(
                f"PRIMARY: {primary_result.raw_response}\n\n"
                f"SECONDARY: {secondary_result.raw_response}"
            ),
        )

    def _safe_call(self, fn, name: str) -> AnalysisResult | None:
        """Call a backend function, catching exceptions."""
        try:
            return fn()
        except Exception as e:
            logger.error(f"{name} backend failed: {e}")
            return None

    def _merge_standards(
        self, primary: list[dict], secondary: list[dict]
    ) -> list[dict]:
        """Merge standards from two backends using confidence weighting.

        Rules:
        - Normalize standard names for comparison (case-insensitive, stripped)
        - For each unique standard, select the version with higher confidence
        - Include unique findings only if confidence >= medium
        - If confidences equal, prefer primary backend
        """
        # Build lookup by normalized standard name
        by_normalized: dict[str, list[tuple[dict, str]]] = {}

        for std in primary:
            key = self._normalize_key(std)
            by_normalized.setdefault(key, []).append((std, "primary"))

        for std in secondary:
            key = self._normalize_key(std)
            by_normalized.setdefault(key, []).append((std, "secondary"))

        # Select best version of each standard
        merged = []
        for _, candidates in sorted(by_normalized.items()):
            if len(candidates) == 1:
                # Unique to one backend: include if confidence >= medium
                std, source = candidates[0]
                weight = self._get_weight(std)
                if weight >= CONFIDENCE_WEIGHTS["medium"]:
                    merged.append(std)
                    logger.debug(
                        f"Unique standard from {source}: {std['standard']} "
                        f"(confidence={std.get('confidence', 'low')})"
                    )
            else:
                # Found by both: select higher confidence (prefer primary on tie)
                candidates_sorted = sorted(
                    candidates,
                    key=lambda x: (
                        self._get_weight(x[0]),
                        1 if x[1] == "primary" else 0,
                    ),
                    reverse=True,
                )
                best, source = candidates_sorted[0]
                merged.append(best)
                weights = [self._get_weight(c) for c, _ in candidates]
                if weights[0] != weights[1]:
                    logger.debug(
                        f"Standard {best['standard']} selected from {source} (weights: {weights})"
                    )

        return merged

    def _normalize_key(self, std: dict) -> str:
        """Normalize a standard for comparison."""
        # Try normalized field first, fall back to standard field
        raw = std.get("normalized") or std.get("standard", "")
        return raw.lower().strip()

    def _get_weight(self, std: dict) -> int:
        """Get numeric weight for a standard's confidence level."""
        conf = std.get("confidence", "low").lower()
        return CONFIDENCE_WEIGHTS.get(conf, CONFIDENCE_WEIGHTS["low"])
