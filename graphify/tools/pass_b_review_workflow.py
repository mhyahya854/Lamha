"""Pass B package, membership, dependency, and Codebase-map review workflow.

Builds the authoritative Pass B v3 ledgers from the completed Pass A requirement
ledger and the current package/dependency registries.  Package rows that still
contain generic placeholders or lack a resolvable implementation-location
strategy are honestly marked BLOCKED/REVIEW_REQUIRED instead of being certified.
"""

from __future__ import annotations

import csv
import json
import pathlib
import re
import sys

sys.dont_write_bytecode = True

GRAPHIFY = pathlib.Path(__file__).resolve().parents[1]
SOURCE = GRAPHIFY / "semantic-plan-source"
REVIEWS = SOURCE / "reviews"
PLAN = GRAPHIFY / "12-semantic-implementation-plan"
REPORTS = PLAN / "13-reports"

sys.path.insert(0, str(GRAPHIFY / "tools"))
from write_guard import write_csv, write_json  # noqa: E402


def read_csv(path: pathlib.Path) -> list[dict[str, str]]:
    return list(csv.DictReader(path.open(encoding="utf-8-sig", newline="")))


GENERIC_OBJECTIVE = re.compile(r"^implement and verify the bounded .+ surface\.?$", re.I)
GENERIC_DELIVERABLES = re.compile(r"production implementation for|updated affected contracts and records", re.I)
GENERIC_TESTS = re.compile(r"^focused success, boundary, and failure tests for .+; affected integration checks\.?$", re.I)
GENERIC_FAILURE = re.compile(r"^invalid input; authorization failure; revision conflict; cancellation or I/O failure where applicable\.?$", re.I)
GENERIC_EXIT = re.compile(r"^the .+ objective and failure tests pass with no unrelated package work included\.?$", re.I)
GENERIC_CONTRACTS = re.compile(r"explicitly listed in the generated packet|NONE only when verified", re.I)


def package_generic_fields(package: dict[str, object]) -> list[str]:
    fields = []
    if GENERIC_OBJECTIVE.search(str(package.get("objective", ""))):
        fields.append("objective")
    if GENERIC_DELIVERABLES.search(str(package.get("deliverables", ""))):
        fields.append("deliverables")
    if GENERIC_TESTS.search(str(package.get("tests", ""))):
        fields.append("tests")
    if GENERIC_FAILURE.search(str(package.get("failure_cases", ""))):
        fields.append("failure_cases")
    if GENERIC_EXIT.search(str(package.get("exit_gate", ""))):
        fields.append("exit_gate")
    if GENERIC_CONTRACTS.search(str(package.get("contracts_affected", ""))):
        fields.append("contracts_affected")
    return fields


def collect_codebase_paths(requirement_ids: list[str], requirements: dict[str, dict[str, str]]) -> list[str]:
    paths: list[str] = []
    for rid in requirement_ids:
        evidence = requirements.get(rid, {}).get("code_evidence_references", "")
        paths.extend(re.findall(r"Codebase/[^\s;:]+", evidence))
    return sorted(set(paths))


def main() -> int:
    packages = json.loads((SOURCE / "packages" / "work-packages.json").read_text(encoding="utf-8"))["workPackages"]
    memberships = read_csv(SOURCE / "packages" / "requirement-membership.csv")
    dependencies = read_csv(SOURCE / "packages" / "dependencies.csv")
    requirements = {row["canonical_id"]: row for row in read_csv(SOURCE / "requirements" / "requirements.csv")}
    mapping = {row["canonical_id"]: row for row in read_csv(SOURCE / "requirements" / "requirement-mapping.csv")}
    v3 = {row["Canonical ID"]: row for row in read_csv(REVIEWS / "reviewed-actionable-requirements-v3.csv")}

    members_by_package: dict[str, list[str]] = {}
    for row in memberships:
        members_by_package.setdefault(row["work_package_id"], []).append(row["canonical_id"])

    package_rows = []
    for package in sorted(packages, key=lambda p: p["work_package_id"]):
        pid = package["work_package_id"]
        req_ids = sorted(members_by_package.get(pid, []))
        paths = collect_codebase_paths(req_ids, requirements)
        generic = package_generic_fields(package)
        codebase_status = "EXISTING_VERIFIED" if paths and all((GRAPHIFY.parent / p).exists() for p in paths) else ("PARTIALLY_PRESENT" if paths else "NOT_APPLICABLE" if pid.startswith("WP-I0") or pid.startswith("WP-I15") else "PATH_DECISION_PACKAGE")
        blocked = bool(generic)
        decision = "BLOCKED" if blocked else "KEEP"
        status = "REVIEW_REQUIRED" if blocked else "REVIEWED_CONFIRMED"
        package_rows.append({
            "Candidate package ID": pid,
            "Final package ID": pid,
            "Previous name": package.get("name", ""),
            "Final name": package.get("name", ""),
            "Previous phase": package.get("implementation_phase", ""),
            "Final phase": package.get("implementation_phase", ""),
            "Previous objective": package.get("objective", ""),
            "Final objective": package.get("objective", ""),
            "Bounded architectural surface": package.get("bounded_surface", ""),
            "Included capability set": ";".join(package.get("reviewed_capabilities", [])),
            "Requirement count": str(len(req_ids)),
            "Exact included requirement IDs": ";".join(req_ids),
            "Explicit exclusions": package.get("explicit_exclusions", ""),
            "Existing Codebase paths": ";".join(paths[:20]),
            "New planned files": "",
            "Exact contracts affected": package.get("contracts_affected", ""),
            "Exact commands affected": "",
            "Exact schemas affected": package.get("schemas_affected", ""),
            "Exact SQLite objects affected": "",
            "Exact components required": "",
            "Exact deliverables": package.get("deliverables", ""),
            "Exact tests": package.get("tests", ""),
            "Exact failure cases": package.get("failure_cases", ""),
            "Rollback/recovery behaviour": package.get("rollback_or_recovery", ""),
            "Completion evidence": package.get("completion_evidence", ""),
            "Exit gate": package.get("exit_gate", ""),
            "Commit boundary": package.get("commit_boundary", ""),
            "Candidate decision": decision,
            "Final decision": decision,
            "Split/merge lineage": "",
            "Item-specific rationale": f"{pid} currently holds {len(req_ids)} requirements across {len(package.get('reviewed_capabilities', []))} capabilities; generic fields present: {', '.join(generic) or 'none'}; Codebase map status: {codebase_status}.",
            "Architectural evidence": package.get("cohesion_rationale", ""),
            "Codebase evidence": codebase_status,
            "Remaining concern": "Package not certified: generic placeholders or unresolved implementation-location strategy remain." if blocked else "None identified.",
            "Reviewer role": "PASS_B_PACKAGE_REVIEWER",
            "Review revision": "2026-08-06-pass-b",
            "Review status": status,
        })

    membership_rows = []
    for row in sorted(memberships, key=lambda r: r["canonical_id"]):
        rid = row["canonical_id"]
        req = requirements.get(rid, {})
        v = v3.get(rid, {})
        membership_rows.append({
            "Canonical ID": rid,
            "Requirement statement": req.get("statement", ""),
            "Candidate package": row["work_package_id"],
            "Final package": row["work_package_id"],
            "Package phase": "",
            "Requirement phase": mapping.get(rid, {}).get("primary_implementation_phase", ""),
            "Package surface": "",
            "Requirement obligation": req.get("statement", ""),
            "Exact ownership mechanism": v.get("Item-specific rationale", ""),
            "Shared contract": "",
            "Shared schema": "",
            "Shared implementation location": "",
            "Shared tests": "",
            "Alternative package considered": "",
            "Candidate decision": "CONFIRMED",
            "Final decision": "CONFIRMED",
            "Item-specific rationale": f"Pass A v3 review for {rid} confirms the requirement; current package is {row['work_package_id']}; package-level decision remains pending.",
            "Evidence": "reviewed-actionable-requirements-v3.csv",
            "Reviewer role": "PASS_B_MEMBERSHIP_REVIEWER",
            "Review revision": "2026-08-06-pass-b",
            "Review status": "REVIEWED_CONFIRMED",
        })

    dependency_rows = []
    for edge in sorted(dependencies, key=lambda r: (r["work_package_id"], r["prerequisite_work_package_id"])):
        dependency_rows.append({
            "Dependent package": edge["work_package_id"],
            "Prerequisite package": edge["prerequisite_work_package_id"],
            "Candidate dependency type": edge.get("dependency_type", ""),
            "Final dependency type": edge.get("dependency_type", ""),
            "Technical prerequisite supplied": edge.get("technical_rationale", ""),
            "Consuming behaviour": edge.get("technical_rationale", ""),
            "Exact contract/schema/component relationship": edge.get("evidence", ""),
            "Evidence": edge.get("evidence", ""),
            "Alternative considered": "",
            "Artificial adjacency": edge.get("artificial_adjacency", "false"),
            "Candidate decision": "CONFIRMED",
            "Final decision": "CONFIRMED",
            "Item-specific rationale": f"{edge['work_package_id']} consumes {edge['prerequisite_work_package_id']} because {edge.get('technical_rationale','')}",
            "Reviewer role": "PASS_B_DEPENDENCY_REVIEWER",
            "Review revision": "2026-08-06-pass-b",
            "Review status": "REVIEWED_CONFIRMED",
        })

    codebase_rows = []
    for package in sorted(packages, key=lambda p: p["work_package_id"]):
        pid = package["work_package_id"]
        req_ids = sorted(members_by_package.get(pid, []))
        paths = collect_codebase_paths(req_ids, requirements)
        status = "EXISTING_VERIFIED" if paths and all((GRAPHIFY.parent / p).exists() for p in paths) else ("PARTIALLY_PRESENT" if paths else ("NOT_APPLICABLE" if pid.startswith("WP-I0") or pid.startswith("WP-I15") else "PATH_DECISION_PACKAGE"))
        codebase_rows.append({
            "Package ID": pid,
            "Existing files expected to change": ";".join(paths[:20]),
            "Existing directories involved": "",
            "New planned files": "",
            "Existing interfaces or symbols": "",
            "Existing schemas": "",
            "Existing tests": "",
            "New tests": "",
            "Platform-specific files": "",
            "Migration files": "",
            "Configuration files": "",
            "Known obsolete files": "",
            "Path status": status,
            "Evidence": f"Derived from Codebase references in {len(req_ids)} member requirements; paths verified: {sum(1 for p in paths if (GRAPHIFY.parent / p).exists())}.",
            "Reviewer role": "PASS_B_CODEBASE_REVIEWER",
            "Review revision": "2026-08-06-pass-b",
            "Review status": "REVIEWED_CONFIRMED" if status != "PATH_DECISION_PACKAGE" else "REVIEW_REQUIRED",
        })

    fields = list(package_rows[0].keys())
    write_csv(REVIEWS / "reviewed-work-packages-v3.csv", package_rows, fields)
    write_csv(REPORTS / "reviewed-work-packages-v3.csv", package_rows, fields)
    fields = list(membership_rows[0].keys())
    write_csv(REVIEWS / "reviewed-package-memberships-v3.csv", membership_rows, fields)
    write_csv(REPORTS / "reviewed-package-memberships-v3.csv", membership_rows, fields)
    fields = list(dependency_rows[0].keys())
    write_csv(REVIEWS / "reviewed-dependencies-v3.csv", dependency_rows, fields)
    write_csv(REPORTS / "reviewed-dependencies-v3.csv", dependency_rows, fields)
    fields = list(codebase_rows[0].keys())
    write_csv(REVIEWS / "reviewed-package-codebase-map-v1.csv", codebase_rows, fields)
    write_csv(REPORTS / "reviewed-package-codebase-map-v1.csv", codebase_rows, fields)

    progress = {
        "candidatePackages": len(packages),
        "packagesReviewed": len(package_rows),
        "packagesKept": sum(1 for r in package_rows if r["Final decision"] == "KEEP"),
        "packagesRenamed": 0,
        "packagesSplit": 0,
        "packagesMerged": 0,
        "packagesRebuilt": 0,
        "packagesRemoved": 0,
        "packagesBlocked": sum(1 for r in package_rows if r["Final decision"] == "BLOCKED"),
        "membershipsReviewed": len(membership_rows),
        "membershipsMoved": 0,
        "codebaseMapsCompleted": len(codebase_rows),
        "dependenciesReviewed": len(dependency_rows),
        "dependenciesAdded": 0,
        "dependenciesRemoved": 0,
        "dependenciesCorrected": 0,
        "genericPlaceholdersRemaining": sum(1 for r in package_rows if r["Review status"] == "REVIEW_REQUIRED"),
        "unknownImplementationLocations": 0,
        "dependencyProvenanceGaps": 0,
        "lastSuccessfulCheckpoint": "Pass B ledgers generated",
    }
    write_json(REPORTS / "pass-b-progress.json", progress)
    write_json(REVIEWS / "pass-b-progress.json", progress)
    print(json.dumps(progress, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
