# Engagement readout: Certainty

How this project would be scoped, delivered and handed over if it were a customer engagement.
The customer is a composite: a product compliance team that reviews test certificates from labs
worldwide, not a named company. Volumes below are the scenario's assumptions; test results are
reproducible from this repository.

## The customer and what they asked for

Reviewers check about 200 certificates a week across 12 product categories. Each category requires
specific test standards (toys need ASTM F963, CPSIA Section 101 and 16 CFR 1303, for example).
Certificates arrive as native PDFs, scans, faxes, Word files and phone photos.

**The ask:** "Use AI to read the certificates."

## What discovery found

| Observed | What it meant |
|:--|:--|
| Labs write the same standard many ways: "16 CFR Part 1303", "16 CFR 1303", "ASTM F963-17" | Reading the text is half the job. Matching what was read against what is required needs its own rule, and it must not produce false passes |
| Input quality varies from clean PDFs to faxed photocopies | No single extraction method is best everywhere. A vision model is cheapest on clean documents; a document OCR service is stronger on degraded scans |
| The team works in spreadsheets and audits in Excel | Output must be CSV that Excel opens correctly, with the missing standards in one filterable cell |
| A batch is a folder dumped from email, sometimes with a corrupt file in it | One bad file must not lose the rest of the batch |

**What was deliberately not built:** an automatic accept. Certainty answers "does this document
contain the required standards?"; whether the certificate is genuine stays with the reviewer.

## What was delivered

- One CLI that takes a file or a folder of mixed formats and returns PASS or FAIL with the missing
  standards, as JSON or CSV.
- Three interchangeable extraction backends selected at runtime: a vision model reading page
  images, Amazon Textract, and Google Document AI, each followed by the same reasoning step.
- Category rules as data (`data/rules/categories.json`): a new category is a JSON entry.
- Token-subset matching with version-suffix handling, so formatting differences match and
  missing tokens never do.

## Proof that it works

| Claim | Evidence | Reproduce |
|:--|:--|:--|
| Every input format reaches the backend correctly | Extraction tests for PDF, DOCX, TXT and images | `pytest tests/unit/test_extractor.py` |
| Formatting differences match; missing tokens never do | Matching tests for exact, version-suffix and token-subset cases | `pytest tests/unit/test_pipeline.py` |
| A bad file does not fail the batch; a missing standard is named | Batch tests with per-file errors, CLI tests on a directory | `pytest tests/unit/test_pipeline.py tests/integration` |

The tests replace the model and OCR calls with fixed responses, so they prove the plumbing and the
matching rule, not the extraction accuracy.

## What is not yet proven, and how the engagement would prove it

**Extraction accuracy per backend has not been measured.** Phase 1 below fixes that: a labelled
set of real certificates, split by input quality (native, scanned, photographed), with the
standards a human reviewer found in each. The readout then reports, per backend and per quality
band, the false-pass rate (the number that matters to compliance), the false-fail rate (the number
that matters to reviewer time) and the cost per file. That table is what decides the default
backend, not a preference.

## Rollout plan

| Phase | What changes | Gate to move on |
|:--|:--|:--|
| 1. Shadow | Reviewers work as today; Certainty runs on the same certificates and its verdicts are compared afterwards | Labelled set built; false-pass rate per backend measured and agreed acceptable |
| 2. Pre-screen | Certainty's verdict and missing list are shown to the reviewer before they open the file | Reviewer time per certificate falls; every FAIL the reviewer overturns is logged and reviewed |
| 3. Route | Clear PASSes go to a light-touch queue; FAILs and low-quality scans go to full review | False-pass rate holds on a monthly audit sample |

## Risks and open items

- **False passes are the expensive error.** Matching is conservative by design, but a model that
  misreads a standard number can still produce one. The monthly audit sample in phase 3 is the
  control, and it must not be dropped.
- **Cost figures in the README are estimates** from list prices, not measured spend.
- **Category auto-detection** is a convenience; when it cannot decide, it fails and asks, and that
  behaviour should stay.

## Feedback for the platform team

Customers ask "which OCR should we use?" before they have any way to answer it. A small,
reusable evaluation harness (labelled documents in, false-pass and false-fail per backend and per
quality band out) would make the choice a measurement in every document-AI engagement.
