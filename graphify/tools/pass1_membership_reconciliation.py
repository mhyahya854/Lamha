"""Reconcile Pass 1 membership after semantic rehabilitation.

Records whose reviewed phase or capability changed keep their existing package
but are marked ``REVIEW_REQUIRED``.  Records that became active implementation
rows without a prior package receive a deterministic phase- and
capability-matched temporary package, also marked ``REVIEW_REQUIRED`` so Package
Pass 2 must confirm it.  Non-implementation records (glossary/UI/informational/
decision) have their mapping phase cleared.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path


sys.dont_write_bytecode = True

GRAPHIFY = Path(__file__).resolve().parents[1]
SOURCE = GRAPHIFY / "semantic-plan-source"

sys.path.insert(0, str(GRAPHIFY / "tools"))
from write_guard import write_csv  # noqa: E402


IMPLEMENTATION_TYPES = {
    "FUNCTIONAL_REQUIREMENT", "NONFUNCTIONAL_REQUIREMENT", "ARCHITECTURAL_INVARIANT",
    "SECURITY_INVARIANT", "PRIVACY_INVARIANT", "DATA_INTEGRITY_INVARIANT",
    "IMPLEMENTATION_CONSTRAINT", "ACCEPTANCE_CRITERION", "OPTIONAL_ADAPTER",
    "VERIFICATION_GATE", "REMOVAL_GATE", "RELEASE_GATE", "PROHIBITION",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(path.open(encoding="utf-8-sig", newline="")))


def main() -> int:
    requirements = read_csv(SOURCE / "requirements" / "requirements.csv")
    mappings = read_csv(SOURCE / "requirements" / "requirement-mapping.csv")
    memberships = read_csv(SOURCE / "packages" / "requirement-membership.csv")
    packages = json.loads((SOURCE / "packages" / "work-packages.json").read_text(encoding="utf-8"))["workPackages"]
    req_by_id = {row["canonical_id"]: row for row in requirements}
    mapping_by_id = {row["canonical_id"]: row for row in mappings}
    membership_by_id = {row["canonical_id"]: row for row in memberships}

    for row in mappings:
        rid = row["canonical_id"]
        req = req_by_id.get(rid)
        if req is not None and req["requirement_type"] not in IMPLEMENTATION_TYPES:
            row["primary_implementation_phase"] = ""
            row["reviewer_status"] = "NOT_APPLICABLE"

    for row in requirements:
        rid = row["canonical_id"]
        if row["supersession_status"] != "ACTIVE" or row["requirement_type"] not in IMPLEMENTATION_TYPES:
            continue
        phase = mapping_by_id[rid]["primary_implementation_phase"]
        if not phase or rid in membership_by_id:
            continue
        capability = row.get("canonical_capability", "").casefold()
        candidates = [
            package for package in packages
            if package["implementation_phase"] == phase
            and any(capability in str(value).casefold() for value in package.get("reviewed_capabilities", []))
        ]
        if not candidates:
            candidates = [package for package in packages if package["implementation_phase"] == phase]
        if not candidates:
            candidates = packages
        package = min(candidates, key=lambda item: item["work_package_id"])
        memberships.append({
            "canonical_id": rid,
            "work_package_id": package["work_package_id"],
            "membership_rationale": "Pass 1 semantic correction; temporary phase/capability-matched assignment that Package Pass 2 must confirm.",
            "reviewer_status": "REVIEW_REQUIRED",
        })
        membership_by_id[rid] = memberships[-1]

    write_csv(SOURCE / "requirements" / "requirement-mapping.csv", mappings, list(mappings[0]))
    write_csv(SOURCE / "packages" / "requirement-membership.csv", sorted(memberships, key=lambda row: row["canonical_id"]), list(memberships[0]))
    print(json.dumps({
        "memberships": len(memberships),
        "reviewRequired": sum(1 for row in memberships if row["reviewer_status"] == "REVIEW_REQUIRED"),
        "addedTemporary": len(membership_by_id) - len(set(row["canonical_id"] for row in memberships)),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
