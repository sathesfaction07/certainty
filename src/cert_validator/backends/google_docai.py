import logging

from .base import AnalysisBackend, AnalysisResult

logger = logging.getLogger("cert_validator")


class GoogleDocAIBackend(AnalysisBackend):
    def __init__(
        self, project_id: str = "", location: str = "us", processor_id: str = "", **kwargs
    ):
        self.project_id = project_id
        self.location = location
        self.processor_id = processor_id

    def analyze_images(self, images: list[bytes]) -> AnalysisResult:
        from google.cloud import documentai_v1 as documentai

        client = documentai.DocumentProcessorServiceClient()
        name = client.processor_path(self.project_id, self.location, self.processor_id)

        all_text = []
        for img_bytes in images:
            raw_document = documentai.RawDocument(content=img_bytes, mime_type="image/png")
            request = documentai.ProcessRequest(name=name, raw_document=raw_document)
            result = client.process_document(request=request)
            all_text.append(result.document.text)

        combined = "\n\n".join(all_text)
        logger.info(f"Document AI extracted {len(combined)} chars from {len(images)} pages")

        # Document AI extracts text; we still need LLM to identify standards
        # Use Claude for reasoning (imported inline to avoid circular dep at module level)
        from .claude_vision import ClaudeVisionBackend

        reasoning = ClaudeVisionBackend()
        return reasoning.analyze_text(combined)

    def analyze_text(self, text: str) -> AnalysisResult:
        from .claude_vision import ClaudeVisionBackend

        reasoning = ClaudeVisionBackend()
        return reasoning.analyze_text(text)
