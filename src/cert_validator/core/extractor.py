import base64
import logging
from pathlib import Path

import fitz  # PyMuPDF

logger = logging.getLogger("cert_validator")

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".docx", ".jpg", ".jpeg", ".png", ".tiff", ".bmp"}


def extract_content(file_path: Path, dpi: int = 200) -> list[bytes] | str:
    ext = file_path.suffix.lower()
    if ext == ".pdf":
        return pdf_to_images(file_path, dpi)
    elif ext == ".txt":
        return read_text_file(file_path)
    elif ext == ".docx":
        return read_docx_file(file_path)
    elif ext in {".jpg", ".jpeg", ".png", ".tiff", ".bmp"}:
        return [file_path.read_bytes()]
    else:
        raise ValueError(
            f"Unsupported file type: {ext}. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )


def pdf_to_images(pdf_path: Path, dpi: int = 200) -> list[bytes]:
    doc = fitz.open(pdf_path)
    images = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        pix = page.get_pixmap(dpi=dpi)
        images.append(pix.tobytes("png"))

    doc.close()
    logger.info(f"Rendered {len(images)} pages from {pdf_path.name} at {dpi} DPI")
    return images


def read_text_file(txt_path: Path) -> str:
    text = txt_path.read_text(encoding="utf-8", errors="replace")
    logger.info(f"Read {len(text)} chars from {txt_path.name}")
    return text


def read_docx_file(docx_path: Path) -> str:
    from docx import Document

    doc = Document(docx_path)
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    text = "\n".join(paragraphs)
    logger.info(f"Read {len(paragraphs)} paragraphs ({len(text)} chars) from {docx_path.name}")
    return text


def encode_image(image_bytes: bytes) -> str:
    return base64.b64encode(image_bytes).decode("utf-8")


def find_files(path: Path) -> list[Path]:
    if path.is_file():
        if path.suffix.lower() in SUPPORTED_EXTENSIONS:
            return [path]
        return []
    return sorted(f for f in path.iterdir() if f.suffix.lower() in SUPPORTED_EXTENSIONS)
