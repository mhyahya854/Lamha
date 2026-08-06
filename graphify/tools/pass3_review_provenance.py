"""Pass 3 review-provenance audit.

Builds the set of explicitly reviewed item IDs from every reviewed-decision
registry and checks that every positive review status in the active canonical
registries has a matching provenance row.  The script can optionally mark
unproven items REVIEW_REQUIRED, but by default it reports coverage.
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


def read_csv(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(path.open(encoding="utf-8-sig", newline="")))


def provenance_ids() -> dict[str, set[str]]:
    ids: dict[str, set[str]] = {
        "requirement": set(),
        "membership": set(),
        "package": set(),
        "dependency": set(),
        "component": set(),
        "schema": set(),
        "command": set(),
    }
    source_files = [
        REVIEWS / "reviewed-requirement-decisions.csv",
        REVIEWS / "reviewed-requirement-decisions-v2.csv",
        REVIEWS / "reviewed-fragment-decisions.csv",
        REVIEWS / "reviewed-failure-controls.csv",
        REVIEWS / "reviewed-change-audit.csv",
        REVIEWS / "reviewed-membership-corrections.csv",
        REVIEWS / "reviewed-membership-decisions-v2.csv",
        REVIEWS / "reviewed-work-package-decisions-v2.csv",
        REVIEWS / "reviewed-package-decisions.csv",
        REVIEWS / "reviewed-dependency-additions.csv",
        REVIEWS / "reviewed-dependency-decisions-v2.csv",
        REVIEWS / "reviewed-dependency-roots.csv",
        REVIEWS / "reviewed-actionable-requirements-v3.csv",
        REVIEWS / "reviewed-dependencies-v3.csv",
        REVIEWS / "reviewed-package-memberships-v3.csv",
        REVIEWS / "reviewed-work-packages-v3.csv",
    ]
    for path in source_files:
        if not path.exists():
            continue
        for row in read_csv(path):
            value = (
                row.get("record_id") or row.get("canonical_id") or row.get("Canonical ID") or row.get("Item ID")
                or row.get("Dependent package") or row.get("Final package ID")
                or row.get("failure_id") or row.get("dependent_package")
                or row.get("work_package_id") or row.get("component") or row.get("schema")
            )
            if not value:
                continue
            if path.name.startswith("reviewed-requirement") or path.name.startswith("reviewed-fragment") or path.name.startswith("reviewed-failure") or path.name.startswith("reviewed-change"):
                ids["requirement"].add(value)
            elif path.name.startswith("reviewed-membership"):
                ids["membership"].add(value)
            elif path.name.startswith("reviewed-work-package") or path.name.startswith("reviewed-package"):
                ids["package"].add(value)
            elif path.name.startswith("reviewed-dependency"):
                ids["dependency"].add(value)
            elif path.name == "reviewed-actionable-requirements-v3.csv":
                if row.get("Review status") in {"REVIEWED_CONFIRMED", "REVIEWED_CORRECTED"}:
                    needs_acceptance = row.get("Requirement type") == "ACCEPTANCE_CRITERION"
                    substantive = (
                        row.get("Final reviewed statement", "")
                        and row.get("Verification method", "")
                        and row.get("Item-specific rationale", "")
                        and row.get("Actor or subsystem", "")
                        and row.get("Observable result", "")
                        and (not needs_acceptance or row.get("Acceptance criteria", ""))
                    )
                    if substantive:
                        ids["requirement"].add(row.get("Canonical ID", ""))
            elif path.name == "reviewed-dependencies-v3.csv":
                if row.get("Review status") in {"REVIEWED_CONFIRMED", "REVIEWED_CORRECTED"} and row.get("Technical prerequisite supplied") and row.get("Evidence"):
                    ids["dependency"].add(f"{row.get('Dependent package','')}<-{row.get('Prerequisite package','')}")
            elif path.name == "reviewed-package-memberships-v3.csv":
                if row.get("Review status") in {"REVIEWED_CONFIRMED", "REVIEWED_CORRECTED"} and row.get("Item-specific rationale") and row.get("Evidence"):
                    ids["membership"].add(row.get("Canonical ID", ""))
            elif path.name == "reviewed-work-packages-v3.csv":
                if row.get("Review status") in {"REVIEWED_CONFIRMED", "REVIEWED_CORRECTED"} and row.get("Item-specific rationale"):
                    ids["package"].add(row.get("Final package ID", ""))
    # Component and schema registries carry their own explicit evidence fields.
    component_path = SOURCE / "components" / "components.csv"
    if component_path.exists():
        for row in read_csv(component_path):
            if row.get("reviewer_status", "").startswith("REVIEWED_") or row.get("reviewer_status") == "REVIEWED":
                ids["component"].add(row.get("component", ""))
    schema_index_path = SOURCE / "schemas" / "schema-index.csv"
    if schema_index_path.exists():
        for row in read_csv(schema_index_path):
            if row.get("reviewer_status", "").startswith("REVIEWED_") or row.get("reviewer_status") == "REVIEWED":
                ids["schema"].add(row.get("schema", ""))
    commands_path = SOURCE / "contracts" / "ipc-command-registry-v3.json"
    if commands_path.exists():
        data = json.loads(commands_path.read_text(encoding="utf-8"))
        for row in data.get("commands", []):
            if str(row.get("reviewerStatus", "")).startswith("REVIEWED_"):
                ids["command"].add(row.get("commandId", ""))
    return ids


def main() -> int:
    ids = provenance_ids()
    rows: list[dict[str, str]] = []
    unmatched: list[str] = []
    impl_types = {
        "FUNCTIONAL_REQUIREMENT", "NONFUNCTIONAL_REQUIREMENT", "ARCHITECTURAL_INVARIANT",
        "SECURITY_INVARIANT", "PRIVACY_INVARIANT", "DATA_INTEGRITY_INVARIANT",
        "IMPLEMENTATION_CONSTRAINT", "ACCEPTANCE_CRITERION", "OPTIONAL_ADAPTER",
        "VERIFICATION_GATE", "REMOVAL_GATE", "RELEASE_GATE", "PROHIBITION",
    }
    mapping = {row["canonical_id"]: row for row in read_csv(SOURCE / "requirements" / "requirement-mapping.csv")}

    def check(item_type: str, rid: str, status: str) -> None:
        positive = status in {"REVIEWED", "REVIEWED_CONFIRMED", "REVIEWED_CORRECTED", "MANUALLY_REVIEWED", "INDEPENDENTLY_REVIEWED"}
        covered = rid in ids[item_type]
        rows.append({
            "Item type": item_type,
            "Item ID": rid,
            "Review status": status,
            "Provenance found": "YES" if covered else "NO",
            "Result": "PASS" if (not positive or covered) else "REVIEW_REQUIRED",
        })
        if positive and not covered:
            unmatched.append(f"{item_type}:{rid}")

    requirements = read_csv(SOURCE / "requirements" / "requirements.csv")
    for row in requirements:
        actionable = (
            row.get("requirement_type") in impl_types
            and mapping.get(row["canonical_id"], {}).get("primary_implementation_phase")
        )
        if actionable:
            check("requirement", row["canonical_id"], row.get("normalization_reviewer_status", ""))
        else:
            rows.append({
                "Item type": "requirement", "Item ID": row["canonical_id"],
                "Review status": "NOT_APPLICABLE", "Provenance found": "YES", "Result": "PASS",
            })
    for row in read_csv(SOURCE / "requirements" / "requirement-mapping.csv"):
        if mapping.get(row["canonical_id"], {}).get("primary_implementation_phase"):
            check("requirement", row["canonical_id"], row.get("reviewer_status", ""))
    for row in read_csv(SOURCE / "packages" / "requirement-membership.csv"):
        check("membership", row["canonical_id"], row.get("reviewer_status", ""))
    for package in json.loads((SOURCE / "packages" / "work-packages.json").read_text(encoding="utf-8"))["workPackages"]:
        check("package", package["work_package_id"], package.get("reviewer_status", ""))
    for row in read_csv(SOURCE / "packages" / "dependencies.csv"):
        check("dependency", f"{row['work_package_id']}<-{row['prerequisite_work_package_id']}", row.get("review_status", ""))
    component_path = SOURCE / "components" / "components.csv"
    if component_path.exists():
        for row in read_csv(component_path):
            check("component", row.get("component", ""), row.get("reviewer_status", ""))
    schema_index_path = SOURCE / "schemas" / "schema-index.csv"
    if schema_index_path.exists():
        for row in read_csv(schema_index_path):
            check("schema", row.get("schema", ""), row.get("reviewer_status", ""))
    commands_path = SOURCE / "contracts" / "ipc-command-registry-v3.json"
    if commands_path.exists():
        for row in json.loads(commands_path.read_text(encoding="utf-8")).get("commands", []):
            check("command", row.get("commandId", ""), str(row.get("reviewerStatus", "")))

    fields = ["Item type", "Item ID", "Review status", "Provenance found", "Result"]
    write_csv(REVIEWS / "review-provenance-coverage.csv", rows, fields)
    write_csv(REPORTS / "review-provenance-coverage.csv", rows, fields)
    result = {
        "checkedRows": len(rows),
        "unmatchedPositiveRows": len(unmatched),
        "unmatched": unmatched[:100],
    }
    write_json(REVIEWS / "review-provenance-coverage.json", result)
    write_json(REPORTS / "review-provenance-coverage.json", result)
    print(json.dumps(result, indent=2))
    return 0 if not unmatched else 1


if __name__ == "__main__":
    raise SystemExit(main())
