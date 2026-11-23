import csv
import logging
from pathlib import Path

from ..backends import get_backend
from ..backends.base import AnalysisBackend, AnalysisResult
from .extractor import extract_content, find_files
from .rules import list_categories, load_rules

logger = logging.getLogger("cert_validator")


def validate_certificate(
    file_path: Path, category: str | None, backend: AnalysisBackend | None = None
) -> dict:
    if category is not None:
        rule = load_rules(category)
        if not rule:
            return {
                "valid": False,
                "error": f"Unknown category: {category}",
                "file": file_path.name,
                "matched": 0,
                "required": 0,
            }

    if backend is None:
        backend = get_backend("claude")

    content = extract_content(file_path)
    if not content:
        return {"valid": False, "error": "No content extracted from file", "file": file_path.name}

    if isinstance(content, list):
        result = backend.analyze_images(content)
    else:
        result = backend.analyze_text(content)

    if category is None:
        category = _auto_detect_category(result)
        if category is None:
            return {
                "valid": False,
                "error": "Could not auto-detect category. Please specify --category.",
                "file": file_path.name,
                "standards_found": [s["standard"] for s in result.standards_found],
            }

    rule = load_rules(category)
    if not rule:
        return {"valid": False, "error": f"Unknown category: {category}", "file": file_path.name}

    found_normalized = {
        s["normalized"].lower() for s in result.standards_found if s.get("normalized")
    }
    found_raw = {s["standard"].lower() for s in result.standards_found}
    all_found = found_normalized | found_raw

    matched = []
    missing = []
    for required in rule.required_standards:
        if _standard_present(required, all_found):
            detail = _find_detail(required, result.standards_found)
            matched.append(detail)
        else:
            missing.append(required)

    valid = len(missing) == 0
    logger.info(
        f"[{file_path.name}] {'PASS' if valid else 'FAIL'}: {len(matched)}/{len(rule.required_standards)} for {category}"
    )

    return {
        "valid": valid,
        "file": file_path.name,
        "category": category,
        "category_auto_detected": result.detected_category is not None,
        "matched": len(matched),
        "required": len(rule.required_standards),
        "missing": missing,
        "matched_details": matched,
        "document_type": result.document_type,
        "lab_name": result.lab_name,
        "date": result.date,
    }


def validate_batch(
    path: Path, category: str | None, backend: AnalysisBackend | None = None
) -> list[dict]:
    files = find_files(path)
    if not files:
        return [{"error": f"No supported files found at {path}"}]

    if backend is None:
        backend = get_backend("claude")

    results = []
    for file_path in files:
        logger.info(f"Processing {file_path.name}...")
        try:
            result = validate_certificate(file_path, category, backend=backend)
        except Exception as e:
            logger.error(f"Failed on {file_path.name}: {e}")
            result = {"valid": False, "file": file_path.name, "error": str(e)}
        results.append(result)

    passed = sum(1 for r in results if r.get("valid"))
    logger.info(f"Batch complete: {passed}/{len(results)} passed")
    return results


def export_csv(results: list[dict], output_path: Path) -> None:
    fieldnames = [
        "file",
        "valid",
        "category",
        "matched",
        "required",
        "missing",
        "lab_name",
        "date",
        "document_type",
        "error",
    ]
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in results:
            row = {**r}
            row["missing"] = ", ".join(row.get("missing", []))
            writer.writerow(row)
    logger.info(f"CSV exported to {output_path}")


def _auto_detect_category(result: AnalysisResult) -> str | None:
    if result.detected_category:
        detected = result.detected_category.lower().strip()
        if detected in list_categories():
            return detected
    return None


def _standard_present(required: str, found_set: set[str]) -> bool:
    req_lower = required.lower()
    req_tokens = set(req_lower.split())

    for found in found_set:
        if req_lower in found or found in req_lower:
            return True
        found_tokens = set(found.split())
        if req_tokens.issubset(found_tokens):
            return True
        found_base = found.split("-")[0].strip()
        if req_lower == found_base:
            return True
    return False


def _find_detail(required: str, standards_found: list[dict]) -> dict:
    for s in standards_found:
        if (
            required.lower() in s.get("normalized", "").lower()
            or required.lower() in s.get("standard", "").lower()
        ):
            return {
                "standard": required,
                "found_as": s["standard"],
                "confidence": s.get("confidence", "high"),
            }
    return {"standard": required, "found_as": required, "confidence": "high"}
