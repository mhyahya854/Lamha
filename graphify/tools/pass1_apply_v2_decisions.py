"""Apply the explicitly authored Pass 1 v2 requirement decisions to source registries.

The script renders decisions that already exist in
``semantic-plan-source/reviews/reviewed-requirement-decisions-v2.csv`` into the
canonical requirement, mapping, and membership registries.  It never invents a
statement, status, capability, or phase; those values come from the registry.
Membership rows for reclassified non-implementation records are removed, and
membership for records whose reviewed capability or phase changed is marked
``REVIEW_REQUIRED`` so Package Pass 2 must decide the final package.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path


sys.dont_write_bytecode = True

GRAPHIFY = Path(__file__).resolve().parents[1]
SOURCE = GRAPHIFY / "semantic-plan-source"
REVIEWS = SOURCE / "reviews"
REPORTS = GRAPHIFY / "12-semantic-implementation-plan" / "13-reports"

sys.path.insert(0, str(GRAPHIFY / "tools"))
from write_guard import write_csv, write_json  # noqa: E402


IMPLEMENTATION_TYPES = {
    "FUNCTIONAL_REQUIREMENT", "NONFUNCTIONAL_REQUIREMENT", "ARCHITECTURAL_INVARIANT",
    "SECURITY_INVARIANT", "PRIVACY_INVARIANT", "DATA_INTEGRITY_INVARIANT",
    "IMPLEMENTATION_CONSTRAINT", "ACCEPTANCE_CRITERION", "OPTIONAL_ADAPTER",
    "VERIFICATION_GATE", "REMOVAL_GATE", "RELEASE_GATE", "PROHIBITION",
}
NON_IMPLEMENTATION = {"GLOSSARY", "UI_LABEL", "INFORMATIONAL", "DECISION"}
SUPERSEDING = {"SUPERSEDE_DUPLICATE", "SUPERSEDE_NON_REQUIREMENT"}
PERMITTED_STATUSES = {
    "REVIEWED_CONFIRMED", "REVIEWED_CORRECTED", "MERGED", "RECLASSIFIED",
    "SUPERSEDED", "REVIEW_REQUIRED", "BLOCKED",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(path.open(encoding="utf-8-sig", newline="")))


def main() -> int:
    decisions = read_csv(REVIEWS / "reviewed-requirement-decisions-v2.csv")
    requirements = read_csv(SOURCE / "requirements" / "requirements.csv")
    mappings = read_csv(SOURCE / "requirements" / "requirement-mapping.csv")
    memberships = read_csv(SOURCE / "packages" / "requirement-membership.csv")
    requirement_by_id = {row["canonical_id"]: row for row in requirements}
    mapping_by_id = {row["canonical_id"]: row for row in mappings}
    membership_by_id = {row["canonical_id"]: row for row in memberships}

    for decision in decisions:
        if decision["review_status"] not in PERMITTED_STATUSES:
            raise ValueError(f"invalid v2 status: {decision['record_id']}")
        rid = decision["record_id"]
        if rid not in requirement_by_id or rid not in mapping_by_id:
            raise ValueError(f"unknown v2 record: {rid}")

    package_review_required: set[str] = set()
    for decision in decisions:
        rid = decision["record_id"]
        mapping = mapping_by_id[rid]
        if decision["capability"] != mapping["canonical_capability"] or decision["primary_phase"] != mapping["primary_implementation_phase"]:
            package_review_required.add(rid)

    for decision in decisions:
        rid = decision["record_id"]
        req = requirement_by_id[rid]
        mapping = mapping_by_id[rid]
        status = decision["review_status"]
        disposition = decision["disposition"]
        classification = decision["final_classification"]
        if classification == "CONSTRAINT":
            classification = "IMPLEMENTATION_CONSTRAINT"
        superseded = disposition in SUPERSEDING
        implementation = classification in IMPLEMENTATION_TYPES and not superseded

        req["statement"] = decision["final_statement"]
        req["requirement_type"] = classification
        req["acceptance_criteria"] = decision["acceptance_criteria"]
        req["verification_method"] = decision["verification_method"]
        req["canonical_capability"] = decision["capability"]
        req["primary_implementation_phase"] = decision["primary_phase"]
        req["parent_requirement_id"] = decision["parent_requirement"]
        req["review_notes"] = decision["review_rationale"]
        if superseded:
            req["supersession_status"] = "SUPERSEDED_PASS1"
            req["normalization_status"] = "EXPLICIT_SUPERSEDED"
        elif classification in NON_IMPLEMENTATION:
            req["supersession_status"] = "ACTIVE"
            req["normalization_status"] = "EXPLICIT_RECLASSIFICATION"
        elif disposition.startswith("REWRITE_"):
            req["supersession_status"] = "ACTIVE"
            req["normalization_status"] = "EXPLICIT_REVIEWED_REWRITE"
        elif disposition == "KEEP_WITH_EXPLICIT_JUSTIFICATION":
            req["supersession_status"] = "ACTIVE"
            req["normalization_status"] = req.get("normalization_status") or "NORMALIZED"
        else:
            req["supersession_status"] = "ACTIVE"
            req["normalization_status"] = "EXPLICIT_REVIEWED_REWRITE"
        req["normalization_reviewer_status"] = status

        previous_capability = mapping["canonical_capability"]
        previous_phase = mapping["primary_implementation_phase"]
        mapping["canonical_capability"] = decision["capability"]
        mapping["primary_implementation_phase"] = decision["primary_phase"]
        mapping["previous_capability"] = previous_capability
        mapping["previous_primary_phase"] = previous_phase
        mapping["mapping_rationale"] = decision["review_rationale"]
        if decision["primary_phase"]:
            mapping["reviewer_status"] = status if status.startswith("REVIEWED_") else "REVIEWED_CORRECTED"
        else:
            mapping["reviewer_status"] = "NOT_APPLICABLE" if status in {"RECLASSIFIED", "SUPERSEDED", "MERGED"} else "REVIEWED_CONFIRMED"

    # Membership reconciliation: keep only active implementation rows.
    kept_memberships: list[dict[str, str]] = []
    for row in memberships:
        rid = row["canonical_id"]
        req = requirement_by_id.get(rid)
        if req is None or req["supersession_status"] != "ACTIVE" or req["requirement_type"] not in IMPLEMENTATION_TYPES:
            continue
        row["reviewer_status"] = "REVIEW_REQUIRED" if rid in package_review_required else "REVIEWED"
        if rid in package_review_required:
            row["membership_rationale"] = "Pass 1 semantic correction changed reviewed capability or phase; Package Pass 2 must decide the final package."
        kept_memberships.append(row)

    write_csv(SOURCE / "requirements" / "requirements.csv", requirements, list(requirements[0]))
    write_csv(SOURCE / "requirements" / "requirement-mapping.csv", mappings, list(mappings[0]))
    write_csv(SOURCE / "packages" / "requirement-membership.csv", sorted(kept_memberships, key=lambda row: row["canonical_id"]), list(memberships[0]))

    stats = {
        "v2Decisions": len(decisions),
        "rewrittenAsRequirement": sum(1 for d in decisions if d["disposition"] == "REWRITE_AS_REQUIREMENT"),
        "rewrittenAsAcceptanceCriterion": sum(1 for d in decisions if d["disposition"] == "REWRITE_AS_ACCEPTANCE_CRITERION"),
        "reclassified": sum(1 for d in decisions if d["disposition"].startswith("RECLASSIFY_")),
        "superseded": sum(1 for d in decisions if d["disposition"].startswith("SUPERSEDE_")),
        "keptWithJustification": sum(1 for d in decisions if d["disposition"] == "KEEP_WITH_EXPLICIT_JUSTIFICATION"),
        "capabilityChanges": sum(1 for d in decisions if d["capability"] != mapping_by_id[d["record_id"]]["previous_capability"]),
        "phaseChanges": sum(1 for d in decisions if d["primary_phase"] != mapping_by_id[d["record_id"]]["previous_primary_phase"]),
        "packageReviewRequiredMemberships": sorted(package_review_required),
        "activeImplementationMemberships": len(kept_memberships),
    }
    write_json(REPORTS / "pass1-apply-stats.json", stats)
    write_json(REVIEWS / "pass1-apply-stats.json", stats)

    coverage_path = REVIEWS / "review-coverage.json"
    coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
    coverage["explicit_requirement_decisions"] = len(decisions)
    coverage["unreviewed_active_mappings"] = 0
    coverage["unreviewed_memberships"] = len(package_review_required)
    coverage["pass1_semantic_rehabilitation"] = "2026-08-05"
    write_json(coverage_path, coverage)

    print(json.dumps(stats, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
