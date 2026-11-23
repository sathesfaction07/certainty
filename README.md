# CertValidator

Validates compliance certificates by identifying test standards in documents and checking them against category-specific requirements. Accepts PDFs (scanned or native), DOCX, TXT, and raw images. Processes single files or entire directories. Supports three extraction backends — Claude Vision, Amazon Textract, and Google Document AI — selectable at runtime.

---

## The Problem

Product compliance requires certificates proving specific test standards were met. These arrive as PDFs from hundreds of labs worldwide — some digitally generated, some photocopied and scanned, some photographed with a phone camera. The formats vary: different fonts, layouts, languages, abbreviations. Some certificates are Word documents. Some are just a photo of a paper certificate sent as a JPEG.

A reviewer needs to answer one question: "Does this document contain the standards required for this product category?" At 200+ certificates per week across 12 categories, each with different required standards, this is tedious and error-prone manually.

CertValidator answers that question by sending the document to a vision-capable LLM that reads it like a human would, then checking the identified standards against the category's requirements.

---

## How It Works

**Step 1 — Accept any document format**

The input can be a PDF, DOCX, TXT, JPG, PNG, TIFF, or BMP. It can be a single file or a directory containing a mix of these. The extractor routes by file type: PDFs are rendered to page images at 200 DPI. DOCX files are parsed into text via python-docx. TXT files are read directly. Image files are passed through as-is.

**Step 2 — Send to the analysis backend**

Three backends are available:

- **Claude Vision** (default): sends page images or text directly to Claude Sonnet via Bedrock. The model reads the document visually and returns structured JSON listing every standard it finds — with exact text as written, a normalized canonical form, and a confidence level. Also identifies the product category, lab name, and date.

- **Textract**: Amazon Textract extracts text with near-perfect OCR accuracy (including tables and forms), then sends the structured text to Claude for standard identification. Better than Claude Vision alone on badly degraded scans because Textract's document OCR is trained specifically for this.

- **Google Document AI**: Google's document processor extracts text, then sends to Claude for reasoning. Comparable accuracy to Textract, different billing model.

All three produce the same output structure. The backend is selected at runtime — no code changes needed to switch.

**Step 3 — Match against category rules**

The identified standards are compared against the category's required list. Matching uses token-subset logic: "16 CFR 1303" matches "16 CFR Part 1303" because all required tokens are present. Version suffixes are handled: "ASTM F963" matches "ASTM F963-17".

If no category is specified, the LLM auto-detects it from the document content.

**Step 4 — Verdict and output**

Each file gets PASS (all standards found) or FAIL (with a list of what's missing). Output can be JSON (for programmatic use) or CSV (for spreadsheet workflows). Batch runs report a summary and continue processing even if individual files fail.

---

## Architecture

```
Input (file or directory)
    │
    ├── .pdf → render pages to PNG (PyMuPDF)
    ├── .docx → extract paragraphs (python-docx)
    ├── .txt → read directly
    └── .jpg/.png/.tiff → pass through as image bytes
           │
           ▼
┌──────────────────────────────────────────────┐
│          Backend (configurable)               │
│                                              │
│  ┌─────────────┐  ┌──────────┐  ┌────────┐ │
│  │Claude Vision │  │ Textract │  │Doc AI  │ │
│  │(images→LLM) │  │(OCR→LLM) │  │(OCR→LLM│ │
│  └─────────────┘  └──────────┘  └────────┘ │
│                                              │
│  All return: standards_found + metadata      │
└──────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────┐
│  Category Rules (12 categories)               │
│  Token-subset matching + version handling     │
└──────────────────────────────────────────────┘
           │
           ▼
  PASS / FAIL + details → JSON or CSV
```

---

## Project Structure

```
cert-validator/
├── src/cert_validator/
│   ├── cli.py                    Click entry point
│   ├── backends/
│   │   ├── base.py              Abstract interface (AnalysisBackend)
│   │   ├── claude_vision.py     Bedrock Claude — images or text
│   │   ├── textract.py          AWS Textract OCR → Claude reasoning
│   │   └── google_docai.py      Google Document AI → Claude reasoning
│   └── core/
│       ├── extractor.py         Multi-format content extraction
│       ├── pipeline.py          Orchestration, matching, batch, CSV export
│       └── rules.py             Category definitions (12 categories)
├── data/
│   ├── rules/categories.json
│   └── sample_certs/
├── tests/
│   ├── unit/                    33 tests covering all paths
│   └── integration/
├── docs/adr/
└── pyproject.toml
```

---

## Running

```bash
pip install -e ".[dev]"

# Single file
cert-validator certificate.pdf --category toys

# Auto-detect category (LLM identifies it from content)
cert-validator certificate.pdf

# Entire directory of mixed formats
cert-validator certs/ --category batteries --output results.json

# CSV output for spreadsheet workflows
cert-validator certs/ --category toys --output audit.csv

# Use Textract backend for degraded scans
cert-validator scanned/ --category chargers --backend textract

# Use Google Document AI
pip install "cert-validator[google]"
cert-validator certs/ --backend google

# List available categories
cert-validator --list-categories
```

---

## Backends

| Backend | How it works | Best for | Cost |
|:--|:--|:--|:--|
| `claude` (default) | Page images sent directly to Claude Vision | Clean PDFs, quick single-file checks | ~$0.02-0.05/file |
| `textract` | Textract OCR extracts text → Claude reasons over text | Degraded scans, faxes, rotated pages | ~$0.01 (Textract) + ~$0.005 (Claude text) |
| `google` | Document AI extracts → Claude reasons | Same as Textract, different billing | Similar to Textract |

Switch at runtime: `--backend textract`. Same output regardless of backend.

---

## Testing

```bash
pytest tests/ -v              # 33 tests
pytest tests/ --cov=src       # coverage
```

Tests mock the backend interface — no actual API calls. Covers: multi-format extraction (PDF/DOCX/TXT/images), batch processing with partial failures, auto-category detection, CSV export, standard matching logic (exact, version suffix, token subset), and the backend factory.

---

## Category Rules

12 categories in `data/rules/categories.json`. Adding a new one: add a JSON entry, no code changes.

| Category | Required Standards | Notes |
|:--|:--|:--|
| toys | ASTM F963, CPSIA Section 101, 16 CFR 1303 | |
| batteries | UL 2054, IEC 62133, UN 38.3, UL 2580 | Strictest — short codes need exact matching |
| chargers | UL 60950-1, IEC 60950-1, UL 62368-1 | |
| laser_products | 21 CFR 1040.10, IEC 60825-1 | Safety-critical |
| e_bikes | UL 2849, EN 15194, UL 2272 | |
| smoke_alarms | UL 217, UL 2034, NFPA 72 | |
| helmets | CPSC 16 CFR 1203, ASTM F1447 | |
| cosmetics | FDA 21 CFR 700, EU Regulation 1223/2009 | |
| supplements | FDA 21 CFR 111, cGMP Compliance | |
| furniture | ASTM F2057, 16 CFR 1219, ASTM F1169 | |
| electronics | FCC Part 15, UL 62368-1 | |
| textiles | 16 CFR 1610, 16 CFR 1615 | |

---

## Tradeoffs and Decisions I Made Along the Way

**Three backends instead of picking one**

I started with Claude Vision only. It's accurate on clean documents but struggled on photocopied faxes — the image quality degrades and the model occasionally misreads characters. Textract is purpose-built for document OCR and handles degraded inputs better, but it only extracts text — it can't reason about what the standards mean. The natural architecture: let the best OCR tool do the reading (Textract/Document AI), let the best reasoning model do the thinking (Claude). But for clean documents, sending images directly to Claude is faster and cheaper (one API call instead of two). So all three options exist, and the user picks based on their input quality.

**Auto-category detection as a convenience, not a requirement**

Most users know what category they're validating. But when processing a mixed batch of certificates (a folder dumped from email), requiring `--category` for each one is impractical. Letting the LLM identify the category from document content handles this. If it can't identify the category (e.g., a certificate that's too generic), it fails explicitly and asks the user to specify — rather than guessing wrong.

**Token-subset matching instead of exact string comparison**

Labs write standards differently: "16 CFR Part 1303", "16 CFR 1303", "16CFR1303". The Claude output includes a "normalized" form, but labs don't follow the canonical spelling. Token-subset matching (are all tokens in "16 CFR 1303" present in "16 CFR Part 1303"?) handles insertions gracefully. It's simpler than fuzzy matching and produces zero false positives — if the tokens aren't all there, it doesn't match.

**Image files as first-class input**

Certificates arrive as email attachments. Sometimes the attachment is a PDF. Sometimes it's a photo of the certificate taken with a phone camera — a .jpg file. Requiring users to wrap images in a PDF before validating adds friction for no benefit. The extractor passes image bytes directly to the backend. Claude Vision handles raw images the same as rendered PDF pages.

**Partial failure in batch mode**

A directory might contain 50 certificates. One might be a corrupted PDF that crashes PyMuPDF. The previous behavior: entire batch fails, 0 results. Now: the corrupted file gets `{"valid": false, "error": "..."}` in the results, the other 49 process normally. The user sees exactly which file failed and why, without losing the work on everything else.

**CSV export with UTF-8 BOM**

The JSON output is for programmatic consumption. But auditors live in Excel. CSV with BOM encoding ensures Excel opens it correctly with proper character rendering (lab names in Chinese, standard names with special characters). The "missing" list is comma-joined into a single cell rather than being a JSON array — because that's what an auditor can filter on in a spreadsheet.

---

## Stack

Python 3.11, PyMuPDF (PDF rendering), python-docx, boto3 (Bedrock + Textract), google-cloud-documentai (optional), Click.
