from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class AnalysisResult:
    standards_found: list[dict] = field(default_factory=list)
    document_type: str = "unknown"
    lab_name: str | None = None
    date: str | None = None
    detected_category: str | None = None
    raw_response: str = ""


class AnalysisBackend(ABC):
    @abstractmethod
    def analyze_images(self, images: list[bytes]) -> AnalysisResult: ...

    @abstractmethod
    def analyze_text(self, text: str) -> AnalysisResult: ...
