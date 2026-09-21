import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parents[1] / "backend"))
from compliance import parse_label_text, run_compliance
from demo_data import DEMO_FIELDS, DEMO_LABEL


def test_food_demo_has_high_evidence_coverage():
    report = run_compliance(parse_label_text(DEMO_LABEL, DEMO_FIELDS))
    assert report["summary"]["applicable_checks"] >= 15
    assert report["summary"]["passed"] >= 12
    assert report["summary"]["needs_review"] <= 2


def test_unknown_text_is_review_not_automatically_failure():
    report = run_compliance(parse_label_text("Mystery product", {}))
    assert report["summary"]["needs_review"] >= 5
    assert not any(check["status"] == "fail" for check in report["checks"])


def test_import_context_requires_origin_evidence():
    report = run_compliance(parse_label_text("Imported by: Acme Trading Pvt Ltd\nNet Qty: 200 g", {}))
    origin = next(check for check in report["checks"] if check["code"] == "LM-08")
    assert origin["status"] == "review"


if __name__ == "__main__":
    test_food_demo_has_high_evidence_coverage()
    test_unknown_text_is_review_not_automatically_failure()
    test_import_context_requires_origin_evidence()
    print("All compliance-engine safety checks passed.")
