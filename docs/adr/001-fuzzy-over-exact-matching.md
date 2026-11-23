# ADR-001: Claude Vision Over Fuzzy Text Matching

## Status
Accepted (supersedes previous fuzzy-matching approach)

## Context
Need to verify that specific test standards appear in PDF compliance certificates. These certificates come from hundreds of labs with inconsistent formatting. The original approach was PyMuPDF text extraction + rapidfuzz fuzzy matching with category-specific thresholds.

## Decision
Send PDF pages as images to Claude (via Bedrock) and let the VLM identify standards directly. Remove the text extraction + fuzzy matching pipeline entirely.

## Why the original approach had problems

The fuzzy matcher worked ~90% of the time but had persistent edge cases:
- "16 CFR Part 1303" vs "16 CFR 1303" — the inserted word "Part" dropped scores below threshold regardless of tuning
- Sliding window tokenization required exact window sizes to match standard lengths — a 4-token standard missed by 3/5/8 windows
- Category-specific thresholds needed manual calibration per category (tested against 10-15 real certs each)
- OCR fallback for scanned PDFs produced noisy text that further degraded fuzzy scores

## Why Claude Vision works better

Claude sees the document as a human would — it reads "ASTM F963-17" regardless of spacing, font, or surrounding text. It also extracts metadata (lab name, date, document type) that the text-based approach required separate regex for.

Accuracy on test set: ~99% vs ~90% for fuzzy matching. Zero threshold calibration needed.

## Tradeoffs accepted
- **Cost:** ~$0.01-0.05 per certificate (vs $0 for local fuzzy matching)
- **Latency:** 3-5 seconds per cert (vs 50ms for local)
- **Requires network:** Can't run offline (fuzzy approach could)
- **External dependency:** If Bedrock is down, validation fails (no graceful degradation)

These are acceptable because: certificates are validated at submission time (not real-time), volume is hundreds/day not millions, and the accuracy improvement justifies the cost.
