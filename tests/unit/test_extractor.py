from pathlib import Path

import pytest

from cert_validator.core.extractor import SUPPORTED_EXTENSIONS, extract_content, find_files

SAMPLE_DIR = Path(__file__).parent.parent.parent / "data" / "sample_certs"


class TestExtractContent:
    def test_pdf_returns_images(self):
        result = extract_content(SAMPLE_DIR / "toy_certificate.pdf")
        assert isinstance(result, list)
        assert len(result) >= 1
        assert isinstance(result[0], bytes)

    def test_txt_returns_string(self, tmp_path):
        txt = tmp_path / "cert.txt"
        txt.write_text("ASTM F963 test report\nResult: PASS")
        result = extract_content(txt)
        assert isinstance(result, str)
        assert "ASTM F963" in result

    def test_docx_returns_string(self, tmp_path):
        from docx import Document

        docx_path = tmp_path / "cert.docx"
        doc = Document()
        doc.add_paragraph("Test Report: UL 2054 Battery Safety")
        doc.save(docx_path)
        result = extract_content(docx_path)
        assert isinstance(result, str)
        assert "UL 2054" in result

    def test_image_returns_bytes(self, tmp_path):
        img = tmp_path / "cert.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        result = extract_content(img)
        assert isinstance(result, list)
        assert isinstance(result[0], bytes)

    def test_jpg_supported(self, tmp_path):
        img = tmp_path / "cert.jpg"
        img.write_bytes(b"\xff\xd8\xff" + b"\x00" * 100)
        result = extract_content(img)
        assert isinstance(result, list)

    def test_unsupported_raises(self, tmp_path):
        bad = tmp_path / "cert.xlsx"
        bad.write_text("")
        with pytest.raises(ValueError, match="Unsupported"):
            extract_content(bad)


class TestFindFiles:
    def test_single_file(self, tmp_path):
        pdf = tmp_path / "a.pdf"
        pdf.write_bytes(b"")
        assert find_files(pdf) == [pdf]

    def test_directory_finds_all_supported(self, tmp_path):
        (tmp_path / "a.pdf").write_bytes(b"")
        (tmp_path / "b.txt").write_text("x")
        (tmp_path / "c.docx").write_bytes(b"")
        (tmp_path / "d.jpg").write_bytes(b"")
        (tmp_path / "e.xlsx").write_bytes(b"")
        files = find_files(tmp_path)
        assert len(files) == 4
        assert all(f.suffix in SUPPORTED_EXTENSIONS for f in files)

    def test_empty_directory(self, tmp_path):
        assert find_files(tmp_path) == []
