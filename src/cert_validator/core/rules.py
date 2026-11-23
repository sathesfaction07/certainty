import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("cert_validator")

RULES_DIR = Path(__file__).parent.parent.parent.parent / "data" / "rules"


@dataclass
class CategoryRule:
    category: str
    required_standards: list[str]
    threshold: float
    description: str


def load_rules(category: str) -> CategoryRule | None:
    rules_file = RULES_DIR / "categories.json"
    if not rules_file.exists():
        logger.error(f"Rules file not found: {rules_file}")
        return None

    with open(rules_file) as f:
        all_rules = json.load(f)

    rule_data = all_rules.get(category.lower())
    if not rule_data:
        logger.warning(f"No rules defined for category: {category}")
        return None

    return CategoryRule(
        category=category.lower(),
        required_standards=rule_data["standards"],
        threshold=rule_data.get("threshold", 85),
        description=rule_data.get("description", ""),
    )


def list_categories() -> list[str]:
    rules_file = RULES_DIR / "categories.json"
    if not rules_file.exists():
        return []
    with open(rules_file) as f:
        return list(json.load(f).keys())
