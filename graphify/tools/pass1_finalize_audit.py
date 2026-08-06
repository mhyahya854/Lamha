"""Finalize the Pass 1 semantic audit and independently computed template metrics.

The pre-rewrite audit is reconstructed from the explicit v2 decision registry so
every detected record retains its individual disposition.  Template metrics are
independently recomputed against the final active registry using the legacy
oracle and structural family rules.
"""

from __future__ import annotations

import csv
import importlib.util
import json
import re
import sys
from pathlib import Path


sys.dont_write_bytecode = True

GRAPHIFY = Path(__file__).resolve().parents[1]
SOURCE = GRAPHIFY / "semantic-plan-source"
REVIEWS = SOURCE / "reviews"
REPORTS = GRAPHIFY / "12-semantic-implementation-plan" / "13-reports"
LEGACY_SCRIPT = GRAPHIFY / "tools" / "superseded" / "seed_reviewed_registries.legacy.py"

sys.path.insert(0, str(GRAPHIFY / "tools"))
from write_guard import write_csv, write_json  # noqa: E402
from pass1_legacy_template_detector import FAMILY_RULES, detect_family, normalize, meaningful_word_count, short_source  # noqa: E402


def read_csv(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(path.open(encoding="utf-8-sig", newline="")))


def load_oracle():
    spec = importlib.util.spec_from_file_location("legacy_oracle_finalize", LEGACY_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def main() -> int:
    decisions = read_csv(REVIEWS / "reviewed-requirement-decisions-v2.csv")
    requirements = read_csv(SOURCE / "requirements" / "requirements.csv")
    mappings = read_csv(SOURCE / "requirements" / "requirement-mapping.csv")
    memberships = read_csv(SOURCE / "packages" / "requirement-membership.csv")
    req_by_id = {row["canonical_id"]: row for row in requirements}
    map_by_id = {row["canonical_id"]: row for row in mappings}
    member_by_id = {row["canonical_id"]: row for row in memberships}

    audit: list[dict[str, str]] = []
    for decision in decisions:
        rid = decision["record_id"]
        req = req_by_id[rid]
        evidence = decision["evidence"]
        exact_marker = "EXACT_LEGACY_OUTPUT" if "EXACT_LEGACY_OUTPUT" in evidence else ""
        family_name = detect_family(decision["previous_statement"])
        family_parts = [exact_marker]
        if family_name:
            family_parts.append(f"FAMILY:{family_name}")
        if short_source(decision["original_source_text"]) and meaningful_word_count(decision["previous_statement"]) < 8:
            family_parts.append("LABEL_ONLY")
        family = ";".join(family_parts)
        source_text = decision["original_source_text"]
        audit.append({
            "canonical_id": rid,
            "title": req.get("title", ""),
            "source_text": source_text,
            "current_statement": decision["previous_statement"],
            "matched_template_family": family,
            "why_current_statement_may_be_semantically_wrong": (
                f"Detected as {family or 'template-family pattern'}; explicit disposition "
                f"{decision['disposition']} with status {decision['review_status']}; rationale: {decision['review_rationale']}"
            ),
            "current_capability": decision["capability"],
            "current_phase": decision["primary_phase"],
            "current_package": member_by_id.get(rid, {}).get("work_package_id", ""),
            "required_disposition": decision["disposition"],
            "requirement_type": decision["final_classification"],
            "source_section": req.get("source_section", ""),
            "parent_requirement_id": req.get("parent_requirement_id", ""),
            "parent_title": req_by_id.get(req.get("parent_requirement_id", ""), {}).get("title", ""),
            "parent_statement": req_by_id.get(req.get("parent_requirement_id", ""), {}).get("statement", ""),
            "source_length_category": "SHORT" if short_source(source_text) else "LONG",
        })
    audit.sort(key=lambda row: (row["source_section"], row["canonical_id"]))
    fields = [
        "canonical_id", "title", "source_text", "current_statement", "matched_template_family",
        "why_current_statement_may_be_semantically_wrong", "current_capability", "current_phase",
        "current_package", "required_disposition", "requirement_type", "source_section",
        "parent_requirement_id", "parent_title", "parent_statement", "source_length_category",
    ]
    write_csv(REPORTS / "legacy-template-semantic-audit.csv", audit, fields)
    write_csv(REVIEWS / "legacy-template-semantic-audit.csv", audit, fields)

    oracle = load_oracle()
    active = [row for row in requirements if row.get("supersession_status") == "ACTIVE"]
    after_exact = 0
    after_family: dict[str, int] = {}
    after_label = 0
    for row in active:
        try:
            legacy_out = oracle.criterion_statement(row)
        except Exception:
            legacy_out = ""
        if normalize(row.get("statement", "")) == normalize(legacy_out):
            after_exact += 1
        family = detect_family(row.get("statement", ""))
        if family:
            after_family[family] = after_family.get(family, 0) + 1
        if short_source(row.get("source_text", "")) and meaningful_word_count(row.get("statement", "")) < 8:
            after_label += 1

    before_exact = sum(1 for d in decisions if "EXACT_LEGACY_OUTPUT" in d["evidence"])
    before_family = sum(1 for d in decisions if detect_family(d["previous_statement"]))
    metrics = {
        "before": {
            "detectedRecords": len(decisions),
            "exactLegacyOutput": before_exact,
            "familyPatternMatches": before_family,
        },
        "after": {
            "activeRecords": len(active),
            "exactLegacyOutput": after_exact,
            "familyPatternMatches": sum(after_family.values()),
            "familyByPattern": dict(sorted(after_family.items())),
            "fragmentaryLabelStatements": after_label,
        },
        "method": "Independent reproduction of the superseded criterion_statement oracle plus structural family rules over the final active registry.",
    }
    write_json(REPORTS / "pass1-template-metrics.json", metrics)
    write_json(REVIEWS / "pass1-template-metrics.json", metrics)
    print(json.dumps(metrics, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
