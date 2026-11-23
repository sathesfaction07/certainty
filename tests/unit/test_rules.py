from cert_validator.core.rules import list_categories, load_rules


class TestLoadRules:
    def test_loads_toys(self):
        rule = load_rules("toys")
        assert rule is not None
        assert rule.category == "toys"
        assert "ASTM F963" in rule.required_standards
        assert rule.threshold == 80

    def test_loads_batteries(self):
        rule = load_rules("batteries")
        assert rule is not None
        assert len(rule.required_standards) == 4
        assert rule.threshold == 90

    def test_unknown_category_returns_none(self):
        assert load_rules("nonexistent_thing") is None

    def test_case_insensitive(self):
        rule = load_rules("TOYS")
        assert rule is not None

    def test_each_category_has_standards(self):
        for cat in list_categories():
            rule = load_rules(cat)
            assert rule is not None
            assert len(rule.required_standards) >= 1
            assert rule.threshold > 0


class TestListCategories:
    def test_returns_all(self):
        cats = list_categories()
        assert "toys" in cats
        assert "batteries" in cats
        assert len(cats) == 12

    def test_no_duplicates(self):
        cats = list_categories()
        assert len(cats) == len(set(cats))
