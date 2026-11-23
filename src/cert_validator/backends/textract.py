import logging

import boto3

from .base import AnalysisBackend, AnalysisResult
from .claude_vision import ClaudeVisionBackend

logger = logging.getLogger("cert_validator")


class TextractBackend(AnalysisBackend):
    def __init__(self, region: str = "us-east-1", **kwargs):
        self.textract = boto3.client("textract", region_name=region)
        self.reasoning = ClaudeVisionBackend(region=region)

    def analyze_images(self, images: list[bytes]) -> AnalysisResult:
        all_text = []
        for img_bytes in images:
            text = self._extract_text(img_bytes)
            all_text.append(text)

        combined = "\n\n---PAGE BREAK---\n\n".join(all_text)
        return self.reasoning.analyze_text(combined)

    def analyze_text(self, text: str) -> AnalysisResult:
        return self.reasoning.analyze_text(text)

    def _extract_text(self, image_bytes: bytes) -> str:
        response = self.textract.detect_document_text(Document={"Bytes": image_bytes})

        lines = []
        for block in response.get("Blocks", []):
            if block["BlockType"] == "LINE":
                lines.append(block["Text"])

        text = "\n".join(lines)
        logger.debug(f"Textract extracted {len(lines)} lines ({len(text)} chars)")
        return text
