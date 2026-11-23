from .base import AnalysisBackend, AnalysisResult
from .claude_vision import ClaudeVisionBackend
from .consensus import ConsensusBackend
from .google_docai import GoogleDocAIBackend
from .textract import TextractBackend

BACKENDS = {
    "claude": ClaudeVisionBackend,
    "textract": TextractBackend,
    "google": GoogleDocAIBackend,
}


def get_backend(name: str, **kwargs) -> AnalysisBackend:
    cls = BACKENDS.get(name)
    if not cls:
        available = ", ".join(BACKENDS.keys())
        raise ValueError(f"Unknown backend: {name}. Available: {available}")
    return cls(**kwargs)

# Re-exported: this module IS the package's public surface.
__all__ = [
    "AnalysisBackend",
    "AnalysisResult",
    "ClaudeVisionBackend",
    "ConsensusBackend",
    "GoogleDocAIBackend",
    "TextractBackend",
]
