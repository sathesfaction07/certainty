import json
import logging
import time

import boto3

from ..core.extractor import encode_image
from .base import AnalysisBackend, AnalysisResult

logger = logging.getLogger("cert_validator")

SYSTEM_PROMPT = """You are a compliance certificate analyzer. You examine certificates and identify which test standards are documented in them.

Rules:
1. Only report standards you can clearly read in the document. Do not infer or guess.
2. Report the standard exactly as written (e.g., "ASTM F963-17", "16 CFR Part 1303").
3. If a standard is partially visible or unclear, include it but set confidence to "low".
4. Identify the product category if possible (e.g., "toys", "batteries", "electronics").
5. Return valid JSON only. No prose before or after."""

RESPONSE_SCHEMA = """\nRespond with this JSON structure:
{
    "standards_found": [
        {"standard": "<name as written>", "normalized": "<canonical form>", "confidence": "high"|"medium"|"low"}
    ],
    "document_type": "<e.g., test report, certificate of compliance>",
    "lab_name": "<testing laboratory name if visible, else null>",
    "date": "<report date if visible, else null>",
    "detected_category": "<product category if identifiable, else null>"
}"""


class ClaudeVisionBackend(AnalysisBackend):
    def __init__(
        self, region: str = "us-east-1", model: str = "us.anthropic.claude-sonnet-4-6-20250514-v1:0"
    ):
        self.client = boto3.client("bedrock-runtime", region_name=region)
        self.model = model

    def analyze_images(self, images: list[bytes]) -> AnalysisResult:
        content = []
        for i, img_bytes in enumerate(images):
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": encode_image(img_bytes),
                    },
                }
            )
            content.append({"type": "text", "text": f"(Page {i + 1} of {len(images)})"})

        content.append(
            {
                "type": "text",
                "text": "Identify all test standards referenced in this certificate."
                + RESPONSE_SCHEMA,
            }
        )
        return self._call(content)

    def analyze_text(self, text: str) -> AnalysisResult:
        content = [
            {"type": "text", "text": f"CERTIFICATE CONTENT:\n\n{text[:15000]}"},
            {
                "type": "text",
                "text": "\nIdentify all test standards referenced in this certificate."
                + RESPONSE_SCHEMA,
            },
        ]
        return self._call(content)

    def _call(self, content: list[dict]) -> AnalysisResult:
        response_text = self._invoke(content)
        parsed = self._parse(response_text)
        return AnalysisResult(
            standards_found=parsed.get("standards_found", []),
            document_type=parsed.get("document_type", "unknown"),
            lab_name=parsed.get("lab_name"),
            date=parsed.get("date"),
            detected_category=parsed.get("detected_category"),
            raw_response=response_text,
        )

    def _invoke(self, content: list[dict]) -> str:
        for attempt in range(3):
            try:
                response = self.client.invoke_model(
                    modelId=self.model,
                    body=json.dumps(
                        {
                            "anthropic_version": "bedrock-2023-05-31",
                            "max_tokens": 1000,
                            "temperature": 0,
                            "system": SYSTEM_PROMPT,
                            "messages": [{"role": "user", "content": content}],
                        }
                    ),
                    contentType="application/json",
                )
                body = json.loads(response["body"].read())
                return body["content"][0]["text"]
            except Exception as e:
                if attempt < 2 and "Throttling" in str(type(e).__name__):
                    time.sleep(2**attempt)
                else:
                    raise
        return "{}"

    def _parse(self, text: str) -> dict:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            import re

            match = re.search(r"\{[\s\S]*\}", text)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
        logger.warning("Failed to parse response as JSON")
        return {}
