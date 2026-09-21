"""Evidence-first package compliance triage.

This module deliberately separates a missing declaration from an unreadable one.
It is a decision-support prototype; statutory enforcement always needs an officer's
review of the physical package and current, category-specific notifications.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import re
from typing import Any, Callable


PASS = "pass"
FAIL = "fail"
WARN = "warn"
REVIEW = "review"
NA = "na"


@dataclass(frozen=True)
class Rule:
    code: str
    title: str
    citation: str
    severity: str
    applies: Callable[[dict[str, Any]], bool]
    evaluate: Callable[[dict[str, Any]], tuple[str, str, str | None]]


def _has(value: Any) -> bool:
    return bool(value and str(value).strip())


def _declared_or_review(value: Any, label: str) -> tuple[str, str, str | None]:
    if _has(value):
        return PASS, f"{label} was found in the captured evidence.", str(value)
    return REVIEW, f"{label} was not reliably extracted. Inspect the physical package before recording a violation.", None


def _validate_address(value: Any, label: str) -> tuple[str, str, str | None]:
    if not _has(value):
        return REVIEW, f"{label} is not reliably visible in the evidence.", None
    # A reasonable prototype signal: street/city plus a six digit PIN is strong evidence.
    if re.search(r"\b\d{6}\b", str(value)) and len(str(value)) > 18:
        return PASS, f"{label} has an address-like declaration with PIN evidence.", str(value)
    return WARN, f"{label} was found, but its completeness could not be confirmed (look for a full postal address/PIN).", str(value)


def _mrp(fields: dict[str, Any]) -> tuple[str, str, str | None]:
    value = fields.get("mrp")
    raw = fields.get("raw_text", "")
    if not _has(value):
        return REVIEW, "No MRP declaration was reliably extracted from the captured sides.", None
    amount_ok = bool(re.search(r"(?:₹|rs\.?|inr)\s*\d", str(value), re.I))
    tax_ok = bool(re.search(r"incl(?:usive)?\.?\s*(?:of)?\s*all\s*tax", str(value) + " " + raw, re.I))
    if amount_ok and tax_ok:
        return PASS, "MRP amount and the inclusive-of-all-taxes wording were found.", str(value)
    if amount_ok:
        return WARN, "MRP amount found; the inclusive-of-all-taxes wording needs visual confirmation.", str(value)
    return REVIEW, "Price-like text was found but is too ambiguous to verify as an MRP declaration.", str(value)


def _quantity(fields: dict[str, Any]) -> tuple[str, str, str | None]:
    value = fields.get("net_quantity")
    if not _has(value):
        return REVIEW, "Net quantity was not reliably extracted.", None
    if re.search(r"\b\d+(?:\.\d+)?\s*(?:mg|g|kg|ml|l|litre|litres|m|cm|nos?\.?|pieces?)\b", str(value), re.I):
        return PASS, "Net quantity with a recognizable unit was found.", str(value)
    return WARN, "A quantity was found but its prescribed-unit presentation needs review.", str(value)


def _date(fields: dict[str, Any]) -> tuple[str, str, str | None]:
    value = fields.get("mfg_date")
    if not _has(value):
        return REVIEW, "Manufacture/pack/import month and year were not reliably extracted.", None
    if re.search(r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|0?[1-9]|1[0-2])[^\n]{0,8}(?:20)?\d{2}", str(value), re.I):
        return PASS, "A month-and-year declaration was found.", str(value)
    return WARN, "A date was found but month-and-year formatting needs visual confirmation.", str(value)


def _consumer_care(fields: dict[str, Any]) -> tuple[str, str, str | None]:
    care = fields.get("consumer_care") or {}
    if not isinstance(care, dict):
        care = {}
    email = care.get("email") or fields.get("consumer_email")
    phone = care.get("phone") or fields.get("consumer_phone")
    address = care.get("address") or fields.get("consumer_address")
    found = ", ".join(item for item, present in (("phone", phone), ("email", email), ("address", address)) if present)
    if email and phone and address:
        return PASS, "Consumer-care address, phone and email were captured.", found
    if found:
        return WARN, f"Consumer-care declaration is partial in the evidence ({found}).", found
    return REVIEW, "Consumer-care details were not reliably extracted.", None


def _fssai(fields: dict[str, Any]) -> tuple[str, str, str | None]:
    value = fields.get("fssai_license")
    if not _has(value):
        return REVIEW, "No 14-digit FSSAI licence number was reliably extracted.", None
    digits = re.sub(r"\D", "", str(value))
    if len(digits) == 14:
        return PASS, "A 14-digit FSSAI licence number was found (format check only).", digits
    return WARN, "FSSAI-like text was found but it does not have 14 digits.", str(value)


def _origin(fields: dict[str, Any]) -> tuple[str, str, str | None]:
    value = fields.get("country_of_origin")
    if _has(value):
        return PASS, "Country-of-origin declaration was found.", str(value)
    return REVIEW, "Imported-product context detected, but country of origin was not reliably extracted.", None


def _legibility(fields: dict[str, Any]) -> tuple[str, str, str | None]:
    score = fields.get("legibility_score")
    if score is None:
        return REVIEW, "No image-quality measurement is available; check that declarations are legible and prominent.", None
    if score >= 0.7:
        return PASS, f"Image legibility signal is {round(score * 100)}%; visual review is still required.", None
    if score >= 0.45:
        return WARN, f"Image legibility signal is only {round(score * 100)}%; capture a sharper close-up.", None
    return REVIEW, f"Image legibility signal is {round(score * 100)}%; no legal conclusion can be drawn from this capture.", None


def _all(_: dict[str, Any]) -> bool:
    return True


def _food(f: dict[str, Any]) -> bool:
    return f.get("product_type") == "food"


def _imported(f: dict[str, Any]) -> bool:
    return bool(f.get("is_imported"))


def _multi_ingredient(f: dict[str, Any]) -> bool:
    return f.get("product_type") == "food" and not bool(f.get("single_ingredient"))


RULES: list[Rule] = [
    Rule("LM-01", "Manufacturer / packer / importer identity", "LMPC Rules, 2011, Rule 6(1)(a)", "high", _all, lambda f: _declared_or_review(f.get("manufacturer") or f.get("packer") or f.get("importer"), "Responsible business identity")),
    Rule("LM-02", "Responsible business address", "LMPC Rules, 2011, Rule 6(1)(a)", "high", _all, lambda f: _validate_address(f.get("manufacturer_address") or f.get("packer_address") or f.get("importer_address"), "Responsible business address")),
    Rule("LM-03", "Common or generic commodity name", "LMPC Rules, 2011, Rule 6(1)(b)", "medium", _all, lambda f: _declared_or_review(f.get("product_name"), "Common/generic commodity name")),
    Rule("LM-04", "Net quantity", "LMPC Rules, 2011, Rule 6(1)(c)", "high", _all, _quantity),
    Rule("LM-05", "Month and year of manufacture / pack / import", "LMPC Rules, 2011, Rule 6(1)(d)", "medium", _all, _date),
    Rule("LM-06", "Maximum retail price inclusive of all taxes", "LMPC Rules, 2011, Rule 6(1)(e)", "high", _all, _mrp),
    Rule("LM-07", "Consumer-care declaration", "LMPC Rules, 2011, Rule 6(1)(f)", "medium", _all, _consumer_care),
    Rule("LM-08", "Country of origin", "LMPC Rules, 2011, Rule 6(1)(a); importer context", "high", _imported, _origin),
    Rule("LM-09", "Legible and prominent declaration", "LMPC Rules, 2011, Rule 9(1)(a)", "medium", _all, _legibility),
    Rule("FD-01", "FSSAI licence format", "FSS (Labelling and Display) Regulations, 2020 — food review", "high", _food, _fssai),
    Rule("FD-02", "Ingredient list", "FSS (Labelling and Display) Regulations, 2020 — food review", "medium", _multi_ingredient, lambda f: _declared_or_review(f.get("ingredients"), "Ingredient list")),
    Rule("FD-03", "Nutrition information", "FSS (Labelling and Display) Regulations, 2020 — food review", "medium", _food, lambda f: _declared_or_review(f.get("nutrition"), "Nutrition information")),
    Rule("FD-04", "Vegetarian / non-vegetarian declaration", "FSS (Labelling and Display) Regulations, 2020 — food review", "medium", _food, lambda f: _declared_or_review(f.get("veg_nonveg"), "Veg/non-veg declaration")),
    Rule("FD-05", "Allergen declaration", "FSS (Labelling and Display) Regulations, 2020 — conditional food review", "medium", _food, lambda f: _declared_or_review(f.get("allergens"), "Allergen declaration")),
    Rule("FD-06", "Best-before / expiry declaration", "FSS (Labelling and Display) Regulations, 2020 — category review", "high", _food, lambda f: _declared_or_review(f.get("best_before"), "Best-before / expiry declaration")),
    Rule("LM-10", "Unit notation consistency", "LMPC Rules, 2011, Rule 12; Legal Metrology (Numeration) Rules", "low", _all, _quantity),
    Rule("LM-11", "Quantity plausibility", "LMPC Rules, 2011, Rule 12 — contextual review", "low", _all, lambda f: _declared_or_review(f.get("net_quantity"), "Quantity declaration")),
    Rule("LM-12", "Cross-side declaration consistency", "Niyam evidence integrity check (not a statutory rule)", "medium", _all, lambda f: _cross_side(f)),
]


def _cross_side(fields: dict[str, Any]) -> tuple[str, str, str | None]:
    conflicts = fields.get("conflicts") or []
    if conflicts:
        return WARN, "Captured sides contain a potentially conflicting declaration: " + "; ".join(conflicts), "; ".join(conflicts)
    if fields.get("captured_sides", 0) >= 2:
        return PASS, "Front and back label evidence were captured with no detected field conflict.", "front + back"
    return REVIEW, "Only one side was captured. A back-label capture is needed for evidence completeness.", None


def parse_label_text(text: str, supplied: dict[str, Any] | None = None) -> dict[str, Any]:
    """Extract a cautious, auditable field map from OCR/manual text.

    Caller-provided structured fields win, preserving the source used by a human reviewer.
    """
    fields: dict[str, Any] = dict(supplied or {})
    text = text or ""
    fields["raw_text"] = text

    def first(pattern: str, flags: int = re.I) -> str | None:
        match = re.search(pattern, text, flags)
        return match.group(1).strip(" :.-") if match else None

    fields.setdefault("manufacturer", first(r"(?:manufactured|made)\s+by\s*[:\-]?\s*([^\n]{3,100})"))
    fields.setdefault("packer", first(r"(?:packed|marketed)\s+by\s*[:\-]?\s*([^\n]{3,100})"))
    fields.setdefault("importer", first(r"imported\s+by\s*[:\-]?\s*([^\n]{3,100})"))
    fields.setdefault("manufacturer_address", first(r"(?:manufactured|made)\s+by[^\n]{0,120}(?:\n|,\s*)([^\n]{12,150}\b\d{6}\b[^\n]*)"))
    fields.setdefault("net_quantity", first(r"(?:net\s*(?:qty|quantity|wt|weight)|quantity)\s*[:\-]?\s*(\d+(?:\.\d+)?\s*(?:mg|g|kg|ml|l|litre|litres|nos?\.?|pieces?))"))
    fields.setdefault("mrp", first(r"((?:mrp|maximum retail price)[^\n]{0,70})"))
    fields.setdefault("mfg_date", first(r"(?:mfg|mfd|manufactured|packed|pkd)\.?\s*(?:on)?\s*[:\-]?\s*([^\n]{3,35})"))
    fields.setdefault("best_before", first(r"(?:best\s*before|use\s*by|expiry|exp)\s*[:\-]?\s*([^\n]{3,80})"))
    fields.setdefault("fssai_license", first(r"fssai(?:\s*(?:lic(?:ence|ense)?\.?\s*(?:no\.?)?)?)?\s*[:\-]?\s*(\d[\d\s-]{11,20})"))
    fields.setdefault("ingredients", first(r"ingredients?\s*[:\-]?\s*([^\n]{5,300})"))
    fields.setdefault("allergens", first(r"(?:contains|allergen(?:s)?)\s*[:\-]?\s*([^\n]{3,200})"))
    fields.setdefault("country_of_origin", first(r"(?:country\s*of\s*origin|made\s*in)\s*[:\-]?\s*([^\n]{3,70})"))
    fields.setdefault("consumer_email", first(r"([\w.+-]+@[\w.-]+\.[A-Za-z]{2,})"))
    fields.setdefault("consumer_phone", first(r"(?:tel|phone|contact|consumer\s*care)[^\n]{0,35}?(\+?\d[\d\s-]{7,16})"))
    fields.setdefault("product_name", first(r"(?:product|commodity|item)\s*(?:name)?\s*[:\-]?\s*([^\n]{3,100})"))
    if not fields.get("product_name"):
        lines = [line.strip() for line in text.splitlines() if len(line.strip()) > 3]
        fields["product_name"] = lines[0] if lines else None

    if not fields.get("nutrition") and re.search(r"nutrition(?:al)?\s*(?:information|facts)?", text, re.I):
        fields["nutrition"] = "nutrition panel detected"
    if not fields.get("veg_nonveg") and re.search(r"\b(?:vegetarian|non[- ]?vegetarian|veg|non[- ]?veg)\b", text, re.I):
        fields["veg_nonveg"] = re.search(r"\b(?:vegetarian|non[- ]?vegetarian|veg|non[- ]?veg)\b", text, re.I).group(0)
    care = fields.setdefault("consumer_care", {})
    if not isinstance(care, dict):
        care = {}
        fields["consumer_care"] = care
    for key, source in (("email", "consumer_email"), ("phone", "consumer_phone")):
        if fields.get(source):
            care.setdefault(key, fields[source])
    fields["is_imported"] = bool(fields.get("is_imported") or fields.get("importer") or fields.get("country_of_origin") or re.search(r"\bimported\b", text, re.I))
    if not fields.get("product_type"):
        food_signals = ("fssai", "ingredients", "nutrition", "best before", "allergen")
        fields["product_type"] = "food" if any(fields.get(key) for key in ("fssai_license", "ingredients", "nutrition", "allergens")) or any(signal in text.lower() for signal in food_signals) else "general"
    fields.setdefault("captured_sides", 1)
    return fields


def run_compliance(fields: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    counts = {PASS: 0, FAIL: 0, WARN: 0, REVIEW: 0, NA: 0}
    for rule in RULES:
        if not rule.applies(fields):
            result = {"code": rule.code, "title": rule.title, "citation": rule.citation, "severity": rule.severity, "status": NA, "message": "Not applicable to the detected package context.", "evidence": None}
        else:
            status, message, evidence = rule.evaluate(fields)
            result = {"code": rule.code, "title": rule.title, "citation": rule.citation, "severity": rule.severity, "status": status, "message": message, "evidence": evidence}
        counts[result["status"]] += 1
        checks.append(result)
    applicable = len(checks) - counts[NA]
    verified = counts[PASS] + counts[WARN]
    risk_points = counts[FAIL] * 20 + counts[WARN] * 7 + counts[REVIEW] * 3
    score = max(0, round(100 * counts[PASS] / max(1, applicable)))
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "Decision-support triage only. 'Review' means no legal conclusion; verify the physical package and current category-specific rules before enforcement.",
        "summary": {
            "applicable_checks": applicable,
            "passed": counts[PASS],
            "warnings": counts[WARN],
            "needs_review": counts[REVIEW],
            "score": score,
            "risk_index": min(100, risk_points),
            "evidence_coverage": round(100 * verified / max(1, applicable)),
        },
        "checks": checks,
        "fields": {key: value for key, value in fields.items() if key not in {"raw_text"}},
        "capture_next": capture_next(fields, checks),
    }


def capture_next(fields: dict[str, Any], checks: list[dict[str, Any]]) -> list[str]:
    actions: list[str] = []
    if fields.get("captured_sides", 0) < 2:
        actions.append("Capture the back or side panel to close the evidence gap.")
    check_codes = {check["code"]: check for check in checks}
    if check_codes.get("LM-06", {}).get("status") in {REVIEW, WARN}:
        actions.append("Take a glare-free close-up of the MRP and tax wording.")
    if fields.get("product_type") == "food" and check_codes.get("FD-01", {}).get("status") in {REVIEW, WARN}:
        actions.append("Capture the FSSAI licence panel at 2× zoom.")
    if check_codes.get("LM-02", {}).get("status") in {REVIEW, WARN}:
        actions.append("Capture the full manufacturer/packer address including PIN code.")
    return actions or ["Evidence set is sufficiently complete for an officer’s visual review."]


def serialize_rules() -> list[dict[str, str]]:
    return [{"code": rule.code, "title": rule.title, "citation": rule.citation, "severity": rule.severity} for rule in RULES]
