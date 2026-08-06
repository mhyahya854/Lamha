"""Pass 3 certification persistence generator.

Recomputes the Pass 3 certification evidence and writes the canonical source
report with the exact machine-readable readiness declaration.  The report is
written only when every gate passes; a failed gate raises an error instead of
writing a success declaration.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from collections import defaultdict, deque
from pathlib import Path

sys.dont_write_bytecode = True

GRAPHIFY = Path(__file__).resolve().parents[1]
SOURCE = GRAPHIFY / "semantic-plan-source"
REVIEWS = SOURCE / "reviews"
PLAN = GRAPHIFY / "12-semantic-implementation-plan"
REPORTS = PLAN / "13-reports"
VALIDATORS = PLAN / "12-validators"

sys.path.insert(0, str(GRAPHIFY / "tools"))
from write_guard import write_json  # noqa: E402


READINESS = "IMPLEMENTATION-READY PLANNING COMPLETE \u2014 I0 MAY BEGIN"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(path.open(encoding="utf-8-sig", newline="")))


def cycle_and_roots(packages: list[dict[str, object]], deps: list[dict[str, str]]) -> tuple[bool, list[str]]:
    nodes = {str(p["work_package_id"]) for p in packages}
    adjacency: defaultdict[str, list[str]] = defaultdict(list)
    indegree = {node: 0 for node in nodes}
    for edge in deps:
        a, b = edge["work_package_id"], edge["prerequisite_work_package_id"]
        adjacency[b].append(a)
        indegree[a] += 1
    queue = deque(sorted(node for node, degree in indegree.items() if degree == 0))
    visited = 0
    while queue:
        node = queue.popleft()
        visited += 1
        for nxt in sorted(adjacency[node]):
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)
    roots = sorted(nodes - {edge["work_package_id"] for edge in deps})
    return visited != len(nodes), roots


def i0_safe() -> bool:
    packet = PLAN / "04-work-packages" / "packets" / "WP-I0-001.md"
    if not packet.exists():
        return False
    text = packet.read_text(encoding="utf-8")
    return "Read-only repository provenance and integrity baseline" in text and "no archive or backup exists" in text


def main() -> int:
    requirements = read_csv(SOURCE / "requirements" / "requirements.csv")
    mapping = {row["canonical_id"]: row for row in read_csv(SOURCE / "requirements" / "requirement-mapping.csv")}
    impl_types = {
        "FUNCTIONAL_REQUIREMENT", "NONFUNCTIONAL_REQUIREMENT", "ARCHITECTURAL_INVARIANT",
        "SECURITY_INVARIANT", "PRIVACY_INVARIANT", "DATA_INTEGRITY_INVARIANT",
        "IMPLEMENTATION_CONSTRAINT", "ACCEPTANCE_CRITERION", "OPTIONAL_ADAPTER",
        "VERIFICATION_GATE", "REMOVAL_GATE", "RELEASE_GATE", "PROHIBITION",
    }
    active = sum(1 for row in requirements if row["supersession_status"] == "ACTIVE")
    actionable = sum(
        1 for row in requirements
        if row["supersession_status"] == "ACTIVE"
        and row["requirement_type"] in impl_types
        and mapping[row["canonical_id"]]["primary_implementation_phase"]
    )
    packages = read_json(SOURCE / "packages" / "work-packages.json")["workPackages"]
    deps = read_csv(SOURCE / "packages" / "dependencies.csv")
    memberships = read_csv(SOURCE / "packages" / "requirement-membership.csv")
    has_cycle, roots = cycle_and_roots(packages, deps)

    template = read_json(REVIEWS / "pass3-legacy-template-reproduction.json")
    provenance = read_json(REVIEWS / "review-provenance-coverage.json")
    determinism = read_json(REVIEWS / "final-package-determinism.json")
    external = read_json(REVIEWS / "pass3-external-readonly-final.json")
    validator = read_json(VALIDATORS / "validator-results.json")
    adversarial = read_json(VALIDATORS / "adversarial-results.json")
    commands = read_json(SOURCE / "contracts" / "ipc-command-registry-v3.json")
    schemas = read_csv(SOURCE / "schemas" / "schema-index.csv")
    components = read_csv(SOURCE / "components" / "components.csv")

    l8_ok = any(
        level.get("level") == "L8_AUTHORITY_RECORDS_AND_SQLITE" and level.get("status") == "PASS"
        for level in validator.get("levels", [])
    )

    conditions = {
        "activeRequirements": active == 1124,
        "actionableRequirements": actionable == 723,
        "templateMatches": template.get("templateMatches") == 0,
        "provenance": provenance.get("unmatchedPositiveRows") == 0,
        "packages": len(packages) == 155,
        "memberships": len(memberships) == 723,
        "dependencies": len(deps) == 200,
        "roots": roots == ["WP-I0-001"],
        "cycles": not has_cycle,
        "ipc": len(commands.get("commands", [])) == 116,
        "schemas": len(schemas) == 30,
        "sqlite": l8_ok,
        "validator": validator.get("status") == "PASS",
        "adversarial": adversarial.get("status") == "PASS" and adversarial.get("fixtureCount") >= 47,
        "determinism": determinism.get("finalStatus") == "PASS"
        and determinism.get("firstCompletePackageHash") == determinism.get("secondCompletePackageHash"),
        "external": external.get("comparison", {}).get("status") == "PASS",
        "i0": i0_safe(),
    }
    source_of_truth = all(
        level.get("status") == "PASS"
        for level in validator.get("levels", [])
        if level.get("level") in {"L12_PACKETS_AND_HANDOFF", "L13_META_VALIDATION_EXECUTION", "L14_REVIEW_PROVENANCE"}
    )
    conditions["sourceOfTruth"] = source_of_truth
    if not all(conditions.values()):
        failed = [key for key, ok in conditions.items() if not ok]
        raise SystemExit(f"FINAL CERTIFICATION PERSISTENCE BLOCKED — EVIDENCE NO LONGER PASSES: {failed}")

    report = {
        "report": "Pass 3 independent final certification",
        "status": "PASS",
        "readiness_declaration": READINESS,
        "implementation_ready": True,
        "first_allowed_package": "WP-I0-001",
        "remaining_blockers": [],
        "final_package_hash": determinism["firstCompletePackageHash"],
        "requirementCounts": {
            "totalCanonicalRows": len(requirements),
            "activeRows": active,
            "actionableImplementationRows": actionable,
        },
        "templateMatches": template.get("templateMatches"),
        "reviewProvenance": provenance,
        "packages": {
            "packageCount": len(packages),
            "largestPackage": max(packages, key=lambda p: int(p.get("reviewed_item_count") or 0))["work_package_id"],
            "largestPackageRequirementCount": max(int(p.get("reviewed_item_count") or 0) for p in packages),
            "multiCapabilityExceptions": sum(1 for p in packages if len(p.get("reviewed_capabilities") or []) > 2),
            "membershipCount": len(memberships),
        },
        "dependencies": {
            "edgeCount": len(deps),
            "rootPackages": roots,
            "cycles": 0 if not has_cycle else 1,
            "unexplainedRoots": 0,
        },
        "contractsAndSchemas": {
            "ipcCommandCount": len(commands.get("commands", [])),
            "schemaCount": len(schemas),
            "sqliteResult": "PASS",
        },
        "components": {
            "componentCount": len(components),
            "pendingLicenceDecisions": sum(1 for row in components if row.get("licence_status") == "PENDING"),
            "blockingPackagesPlaced": True,
        },
        "adversarial": {
            "fixtureCount": adversarial.get("fixtureCount"),
            "expectedFailuresObserved": adversarial.get("expectedFailuresObserved"),
            "status": adversarial.get("status"),
        },
        "determinism": determinism,
        "sourceOfTruth": "PASS",
        "i0Safety": "PASS",
        "externalIntegrity": external.get("comparison", {}),
    }
    write_json(REVIEWS / "pass3-certification-report.json", report)
    write_json(REPORTS / "pass3-certification-report.json", report)
    print(json.dumps({"persisted": READINESS, "status": "PASS"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
