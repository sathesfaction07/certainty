# CertValidator — Technical Architecture

## Overview

CertValidator is a compliance certificate pre-screening tool that identifies test standards in documents (PDF, DOCX, TXT, images) and verifies them against category-specific requirements. It accepts single files or batch directories, extracts content using OCR or direct text parsing, sends extracted data to Claude Vision via AWS Bedrock for standard identification using structured prompting, and produces pass/fail verdicts with detailed explanations suitable for human review.

**Design principle:** This tool pre-screens and flags — it does not approve. All validation outputs require human review. The system identifies missing standards and surfaces confidence signals, but final compliance decisions remain with trained reviewers.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     CLI ENTRY (cert-validator)                          │
│                                                                         │
│  Arguments: file/directory, --category, --backend, --output            │
│  Outputs: JSON (structured) or CSV (spreadsheet-ready)                 │
└─────────────────────┬───────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                  CORE PIPELINE (src/cert_validator/core/)               │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │ validate_certificate() / validate_batch()                         │ │
│  │   1. Load category rules (or auto-detect)                         │ │
│  │   2. Extract content by file type                                 │ │
│  │   3. Route to backend (images or text)                            │ │
│  │   4. Match found standards against required list                  │ │
│  │   5. Return verdict + missing standards + confidence              │ │
│  └───────────────────────────────────────────────────────────────────┘ │
└─────────────────────┬───────────────────────────────────────────────────┘
                      │
            ┌─────────┴──────────┐
            ▼                    ▼
┌──────────────────────┐  ┌──────────────────────────────────────────────┐
│   EXTRACTOR          │  │   RULE ENGINE                                │
│ (core/extractor.py)  │  │ (core/rules.py, core/pipeline.py)            │
│                      │  │                                              │
│ .pdf  → PyMuPDF      │  │ CategoryRule: 12 categories defined in       │
│         render pages │  │   data/rules/categories.json                 │
│         at 200 DPI   │  │                                              │
│                      │  │ _standard_present(): token-subset matching   │
│ .docx → python-docx  │  │   - "16 CFR 1303" matches "16 CFR Part 1303" │
│         parse paras  │  │   - Handles version suffixes (ASTM F963-17)  │
│                      │  │   - Exact substring or token subset logic    │
│ .txt  → read directly│  │                                              │
│                      │  │ _auto_detect_category(): if not specified,   │
│ .jpg  → pass bytes   │  │   use LLM's detected_category field          │
│ .png    through      │  │                                              │
│ .tiff                │  │ _find_detail(): match required → found text  │
└──────────┬───────────┘  └──────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│           EXTRACTION BACKENDS (src/cert_validator/backends/)            │
│                                                                         │
│  ┌────────────────────┐  ┌──────────────────┐  ┌────────────────────┐ │
│  │ ClaudeVisionBackend│  │ TextractBackend  │  │ GoogleDocAIBackend │ │
│  │                    │  │                  │  │                    │ │
│  │ images → Claude    │  │ images → Textract│  │ images → DocAI OCR │ │
│  │ (via Bedrock)      │  │ OCR → Claude     │  │ → Claude reasoning │ │
│  │                    │  │                  │  │                    │ │
│  │ text → Claude      │  │ text → Claude    │  │ text → Claude      │ │
│  │                    │  │                  │  │                    │ │
│  │ Model: Sonnet 4    │  │ Textract detects │  │ Processor extracts │ │
│  │ Temperature: 0     │  │ document text    │  │ text, Claude IDs   │ │
│  │ Max tokens: 1000   │  │ (LINE blocks)    │  │ standards          │ │
│  │                    │  │                  │  │                    │ │
│  │ Returns:           │  │ Returns same     │  │ Returns same       │ │
│  │ AnalysisResult     │  │ AnalysisResult   │  │ AnalysisResult     │ │
│  └────────────────────┘  └──────────────────┘  └────────────────────┘ │
│                                                                         │
│  All three implement: analyze_images(list[bytes]) → AnalysisResult     │
│                       analyze_text(str) → AnalysisResult               │
│                                                                         │
│  AnalysisResult fields:                                                │
│    standards_found: [{standard, normalized, confidence}, ...]          │
│    document_type: str                                                  │
│    lab_name: str | None                                                │
│    date: str | None                                                    │
│    detected_category: str | None                                       │
└─────────────────────────────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        EXTERNAL SERVICES                                │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │ AWS Bedrock                                                       │ │
│  │ Model: us.anthropic.claude-sonnet-4-6-20250514-v1:0              │ │
│  │ Region: us-east-1                                                 │ │
│  │ Temperature: 0 (deterministic)                                    │ │
│  │ Max tokens: 1000                                                  │ │
│  │ Retry: 3 attempts on ThrottlingException                          │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │ AWS Textract (optional)                                           │ │
│  │ API: detect_document_text                                         │ │
│  │ Returns: Blocks with LINE text + confidence                       │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │ Google Document AI (optional, requires google-cloud-documentai)   │ │
│  │ Processor API: process_document                                   │ │
│  │ Returns: document.text with structured extraction                 │ │
│  └──────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Components

### 1. CLI (`src/cert_validator/cli.py`)

Entry point: `cert-validator` (Click-based)

| Flag | Purpose |
|:--|:--|
| `PATH` | File or directory (positional argument) |
| `--category` | Product category (12 options). Omit to auto-detect via LLM. |
| `--backend` | `claude` (default), `textract`, or `google` |
| `--region` | AWS region for Bedrock/Textract (default: `us-east-1`) |
| `--output` | Output file path. `.json` for structured data, `.csv` for spreadsheets. |
| `--list-categories` | Print available categories and exit |
| `--verbose` | DEBUG-level logging |

Function: `main()` — orchestrates input validation, backend initialization, single/batch processing, and output formatting.

Function: `_print_result()` — console output with colored PASS/FAIL status, matched counts, missing standards, and metadata (lab name, date).

### 2. Core Pipeline (`src/cert_validator/core/`)

**extractor.py** — Multi-format content extraction

- `extract_content(file_path, dpi=200) -> list[bytes] | str`
  - `.pdf` → `pdf_to_images()`: PyMuPDF renders pages to PNG at 200 DPI
  - `.docx` → `read_docx_file()`: python-docx extracts paragraphs
  - `.txt` → `read_text_file()`: direct UTF-8 read with error replacement
  - `.jpg/.png/.tiff/.bmp` → raw bytes (passed through)
  - Unsupported extensions raise `ValueError`
- `find_files(path) -> list[Path]`: recursive directory scan for supported extensions
- `encode_image(image_bytes) -> str`: Base64 encoding for API submission

**pipeline.py** — Orchestration and matching logic

- `validate_certificate(file_path, category, backend) -> dict`
  - Loads rules or auto-detects category
  - Extracts content, routes to backend (images or text)
  - Matches found standards against required list via `_standard_present()`
  - Returns: `{valid, file, category, matched, required, missing, matched_details, lab_name, date, document_type}`
- `validate_batch(path, category, backend) -> list[dict]`
  - Finds all files in directory
  - Processes each with exception handling (partial failure resilience)
  - Logs summary: `{passed}/{total} passed`
- `export_csv(results, output_path)`: writes CSV with UTF-8 BOM for Excel compatibility, comma-joins missing arrays
- `_auto_detect_category(result)`: uses `result.detected_category` if it matches a known category key
- `_standard_present(required, found_set) -> bool`: core matching logic (see Rule Engine section)
- `_find_detail(required, standards_found) -> dict`: extracts confidence and "found_as" text for matched standards

**rules.py** — Category definitions

- `CategoryRule`: dataclass with `category`, `required_standards`, `threshold`, `description`
- `load_rules(category) -> CategoryRule | None`: loads from `data/rules/categories.json`
- `list_categories() -> list[str]`: returns all 12 category keys

### 3. Extraction Backends (`src/cert_validator/backends/`)

All backends implement `AnalysisBackend` interface with two methods:
- `analyze_images(images: list[bytes]) -> AnalysisResult`
- `analyze_text(text: str) -> AnalysisResult`

| Backend | Technique | Handles degraded scans? | Structured output? | When to use |
|:--|:--|:--|:--|:--|
| `claude` (ClaudeVisionBackend) | Page images sent directly to Claude Vision | Moderate — depends on image quality | Yes — JSON schema enforced | Clean PDFs, quick validation, lowest latency |
| `textract` (TextractBackend) | Textract OCR extracts text → Claude reasons | Yes — purpose-built OCR handles rotations, noise, forms | Yes — same AnalysisResult | Degraded scans, faxes, photocopies |
| `google` (GoogleDocAIBackend) | Document AI OCR → Claude reasons | Yes — comparable to Textract | Yes — same AnalysisResult | Same as Textract, different billing/quota model |

**ClaudeVisionBackend**
- Model: `us.anthropic.claude-sonnet-4-6-20250514-v1:0`
- System prompt: 5 rules for accuracy (no inference, report as written, confidence levels, category detection, JSON-only output)
- Images: Base64-encoded PNG, prefixed with page numbers
- Text: limited to 15,000 chars (first portion only)
- Retry: 3 attempts with exponential backoff on `ThrottlingException`
- Parsing: JSON decode with regex fallback (`\{[\s\S]*\}` extraction)

**TextractBackend / GoogleDocAIBackend**
- Both delegate to ClaudeVisionBackend after OCR
- Textract uses `detect_document_text`, extracts LINE blocks
- Google uses `DocumentProcessorServiceClient`, requires project/processor IDs
- Text concatenation: pages joined with `\n\n` (Google) or `---PAGE BREAK---` (Textract)

**Response schema** (enforced in SYSTEM_PROMPT):
```json
{
  "standards_found": [
    {"standard": "ASTM F963-17", "normalized": "ASTM F963", "confidence": "high"}
  ],
  "document_type": "test report",
  "lab_name": "Intertek Testing Services",
  "date": "2024-03-15",
  "detected_category": "toys"
}
```

### 4. Rule Engine

**Category definitions** (`data/rules/categories.json`):
12 categories, each with:
- `description`: human-readable label
- `standards`: list of required standard IDs
- `threshold`: legacy field (not used in current matching logic)

Example:
```json
"toys": {
  "description": "Children's toys — CPSIA/ASTM compliance",
  "standards": ["ASTM F963", "CPSIA Section 101", "16 CFR 1303"],
  "threshold": 80
}
```

**Matching logic** (`_standard_present` in pipeline.py):
1. Normalize required and found standards to lowercase
2. Check exact substring: if `required` in `found` OR `found` in `required` → match
3. Check token subset: split both into tokens, if all required tokens present in found → match
4. Check version suffix: strip hyphen suffix from found (e.g., `ASTM F963-17` → `ASTM F963`), compare → match

This handles:
- Insertions: "16 CFR Part 1303" matches "16 CFR 1303" (token subset)
- Version suffixes: "ASTM F963" matches "ASTM F963-17" (base comparison)
- Abbreviations: exact substring catches partial matches

---

## Data Flow

```
1. User invokes: cert-validator certificate.pdf --category toys --output results.json
2. CLI validates inputs, initializes ClaudeVisionBackend(region="us-east-1")
3. validate_certificate() loads CategoryRule for "toys" (3 required standards)
4. extract_content() detects .pdf extension, calls pdf_to_images()
5. PyMuPDF renders 3 pages to PNG at 200 DPI → [bytes, bytes, bytes]
6. Pipeline routes to backend.analyze_images(images)
7. ClaudeVisionBackend Base64-encodes images, constructs Bedrock API payload
8. Bedrock invokes Claude Sonnet with system prompt + images + response schema
9. Claude returns: {"standards_found": [{"standard": "ASTM F963-17", ...}, {"standard": "16 CFR 1303", ...}], "detected_category": "toys", ...}
10. Backend parses JSON, constructs AnalysisResult(standards_found=[...])
11. Pipeline extracts normalized/raw standards: {"astm f963-17", "astm f963", "16 cfr 1303"}
12. For each required standard, _standard_present() checks: "ASTM F963" → token subset match in "astm f963-17" → matched
13. "CPSIA Section 101" → not found → missing
14. Pipeline returns: {valid: false, matched: 2, required: 3, missing: ["CPSIA Section 101"], ...}
15. CLI exports to results.json: [{"valid": false, "file": "certificate.pdf", "category": "toys", ...}]
```

---

## Rule Engine and Matching Design

The matching system evolved from fuzzy string matching (rapidfuzz) to token-subset logic after discovering that OCR/LLM outputs exhibit specific, predictable variance patterns rather than random character errors.

**Why token-subset over fuzzy matching (ADR-001)**

The original design used fuzzy string matching with per-category thresholds (80-92% similarity). This failed on insertions like "16 CFR Part 1303" vs "16 CFR 1303" — the word "Part" dropped similarity scores below threshold regardless of tuning. Sliding window tokenization required exact window sizes, missing 4-token standards with 3/5-token windows. Each category needed manual threshold calibration against 10-15 real certificates.

Switching to Claude Vision eliminated OCR noise (Claude reads visually, not via text extraction), but labs write standards inconsistently: "ASTM F963-17", "ASTM F963", "ASTMF963", "F963-17". Token-subset matching handles this: if all tokens in the required standard appear in the found text, it's a match. "16 CFR 1303" has tokens `{16, cfr, 1303}`; "16 CFR Part 1303" has `{16, cfr, part, 1303}` — the required tokens are a subset, so it matches. Zero false positives because missing tokens fail the subset test.

**OCR failure modes that forced the architecture**

Before Claude Vision, PyMuPDF text extraction produced: "16CFR1303" (no spaces), "ASTM F963 - 17" (extra spaces around hyphen), "1б CFR 1303" (Cyrillic б mistaken for 6). Textract handles these better (purpose-built OCR), but even Textract outputs "16 CFR Part 1303" when the certificate uses that full form. The system must match canonical "16 CFR 1303" against that variant. Token-subset handles it; fuzzy matching required threshold tuning per category and still failed on 10% of certificates.

**Fuzzy threshold tradeoffs**

Original thresholds: toys (80%), batteries (90%), laser_products (92%). Lower thresholds increased false positives (matching "UL 2054" to "UL 2580" at 75% similarity). Higher thresholds missed valid matches ("ASTM F963-17" vs "ASTM F963" at 88% similarity because of the suffix). The sweet spot was 85-90%, but this required testing against 10-15 certificates per category and failed when labs used new phrasing (e.g., "CPSIA Sec 101" vs "CPSIA Section 101").

Token-subset eliminates this: "CPSIA Section 101" requires `{cpsia, section, 101}`; "CPSIA Sec 101" has `{cpsia, sec, 101}` — not a match. But "CPSIA Section 101 Compliance" has all three tokens — match. No threshold tuning needed. The only failure mode: abbreviations like "Sec" vs "Section". This is acceptable because the LLM output includes both `standard` (as written) and `normalized` (canonical form), and matching checks both.

**Missing vs unreadable fields**

`AnalysisResult.standards_found` includes per-standard confidence: "high", "medium", "low". Low confidence indicates the LLM saw text but couldn't read it clearly (e.g., partial OCR, rotated text, watermark overlap). This is distinct from a missing standard (not mentioned in the document at all).

Distinction matters to reviewers:
- **Missing**: certificate doesn't claim compliance with the standard → likely invalid for the category, needs follow-up with supplier
- **Unreadable**: certificate may claim compliance but text is illegible → request a clearer copy before rejecting

The output includes `matched_details` with confidence per match: `{"standard": "ASTM F963", "found_as": "ASTM F963-17", "confidence": "high"}`. A "low" confidence match triggers manual review even if technically passing.

**Confidence propagation**

Claude returns per-standard confidence. The system does NOT aggregate these into a document-level confidence score because:
1. Pass/fail is binary per category (all required standards present or not)
2. A document with 5 "high" confidence standards and 1 "low" confidence standard might pass or fail depending on which one is low
3. Aggregation (average? minimum?) obscures which specific standard needs review

Instead, the CSV/JSON output includes `matched_details` with per-standard confidence. A reviewer filters for "low" confidence entries and manually verifies those certificates.

**Backend disagreement**

The three backends can disagree:
- Claude Vision on a degraded scan: misreads "UL 2054" as "UL 2054" but with "low" confidence
- Textract on the same scan: OCR extracts "UL 2054" clearly, Claude reasons with "high" confidence
- Google Document AI: similar to Textract, different character recognition in edge cases

The system does NOT run multiple backends and vote. Instead:
1. User selects backend via `--backend` flag
2. If validation fails with `claude`, user retries with `textract` (better OCR for degraded scans)
3. Results from different backends are NOT merged — each run is independent

This avoids complexity (consensus logic, partial failure handling, cost multipliers) and makes behavior predictable: the backend you choose is the backend you get. If uncertain, Textract is recommended for scanned/photocopied inputs, Claude Vision for clean PDFs.

**Limitations**

- **No semantic understanding**: "ASTM F963" and "ASTM F963-17" match because of version suffix handling, but "ISO 8124" (international equivalent of ASTM F963 for toys) does not match. The system requires exact standard IDs, not equivalent standards. This is intentional — compliance categories specify exact standards, and reviewers need to see exactly what the certificate claims.
- **Language-specific phrasing**: "CPSIA Section 101" vs "CPSIA Article 101" (if a lab uses non-English legal term translations) will not match. Token subset handles insertions/reorderings, not synonyms.
- **Confidence thresholds not enforced**: the system reports low confidence but does not auto-fail. A document with all required standards at "low" confidence still returns `valid: true`. This is correct behavior — the tool flags, the human decides.

---

## Configuration

No Pydantic Settings class exists. Configuration is via CLI flags and AWS credentials:

```bash
# AWS credentials (Bedrock/Textract)
export AWS_PROFILE=compliance_team
export AWS_REGION=us-east-1

# Google Document AI (optional, only for --backend google)
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
export GOOGLE_PROJECT_ID=project-123456
export GOOGLE_PROCESSOR_ID=abc123def456

# Runtime configuration via CLI flags
cert-validator <path> \
  --category <category> \
  --backend claude|textract|google \
  --region us-east-1 \
  --output results.json \
  --verbose
```

Category rules are in `data/rules/categories.json` — JSON file loaded at runtime. Adding a new category: edit JSON, no code changes required.

---

## Running

```bash
# Install
pip install -e .
pip install -e ".[dev]"           # includes pytest, ruff
pip install -e ".[google]"        # adds google-cloud-documentai

# Single file validation
cert-validator certificate.pdf --category toys

# Auto-detect category
cert-validator certificate.pdf

# Batch processing (directory)
cert-validator certs/ --category batteries --output results.csv

# Use Textract for degraded scans
cert-validator scanned_faxes/ --category chargers --backend textract

# Use Google Document AI
cert-validator docs/ --backend google --output results.json

# List available categories
cert-validator --list-categories
```

---

## Testing

```bash
# All tests (33 total: 24 unit, 9 integration)
pytest tests/ -v

# Unit tests only (no I/O, mocked backends)
pytest tests/unit/ -v

# Integration tests (requires AWS credentials for Bedrock)
pytest tests/integration/ -v

# Coverage
pytest tests/ --cov=src --cov-report=term-missing
```

Unit tests mock `AnalysisBackend.analyze_images()` and `analyze_text()` to avoid API calls. Integration tests use real Bedrock calls with sample certificates (small subset, CI skip recommended).
