"""WP-I0-011 risk governance tests; never reported as downstream product tests."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from collections import defaultdict, deque
from pathlib import Path

from governance import (
    GovernanceError,
    validate_blocker,
    validate_risk_links,
    validate_raw_risk_observation,
    validate_runtime_risk_gates,
    validate_simplicity_review,
)


PACKAGE_ID = "WP-I0-011"


def read_csv(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(path.open(encoding="utf-8-sig", newline="")))


def load_records(root: Path) -> tuple[list[dict], set[str], set[str], dict[str, dict]]:
    source = root / "graphify/semantic-plan-source"
    ownership = json.loads((source / "risks/risk-test-ownership.json").read_text(encoding="utf-8"))
    risk_rows = {row["risk_id"]: row for row in read_csv(source / "risks/high-critical-risk-register.csv")}
    packages = json.loads((source / "packages/work-packages.json").read_text(encoding="utf-8"))["workPackages"]
    package_by_id = {row["work_package_id"]: row for row in packages}
    package_ids = set(package_by_id)
    canonical_ids = {row["canonical_id"] for row in read_csv(source / "requirements/requirements.csv")}
    edges = read_csv(source / "packages/dependencies.csv")
    adjacency: defaultdict[str, set[str]] = defaultdict(set)
    for edge in edges:
        adjacency[edge["prerequisite_work_package_id"]].add(edge["work_package_id"])

    def reachable(start: str, target: str) -> bool:
        queue, seen = deque([start]), {start}
        while queue:
            node = queue.popleft()
            if node == target:
                return True
            for nxt in adjacency[node]:
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append(nxt)
        return False

    records = []
    for raw in ownership["records"]:
        risk = risk_rows[raw["riskId"]]
        record = dict(raw)
        record.update({
            "severity": risk["severity"],
            "requiredTest": risk["required_test"],
            "blockingPackageGate": raw["blockingPackageGate"],
            "blockingReleaseGate": raw["blockingReleaseGate"],
            "prerequisitesSatisfied": all(reachable(owner, raw["testOwnerPackage"]) for owner in raw["requiredAfterPackages"]),
            "governanceCheck": f"python graphify/13-implementation/WP-I0-011/risk_governance_test.py --risk {raw['riskId']}",
            "governanceCheckType": "MAPPING_ENFORCEMENT_NOT_PRODUCT_TEST",
        })
        records.append(record)
    return records, package_ids, canonical_ids, package_by_id


def valid_evidence(record: dict) -> dict:
    return {
        "riskId": record["riskId"],
        "runtimeRequirementId": record["runtimeRequirementId"],
        "testOwnerPackage": record["testOwnerPackage"],
        "status": "PASS",
        "synthetic": False,
        "evidenceKind": "GOVERNANCE_MITIGATION_TEST" if record["testClass"] == "GOVERNANCE_MITIGATION_BOUNDARY" else "REAL_PRODUCT_RISK_TEST",
        "implementationCommit": record.get("implementationCommit") or "PENDING_IMPLEMENTATION_COMMIT",
        "evidenceLinks": record.get("runtimeEvidence") or ["graphify/13-implementation/WP-I0-011/verification-report.json"],
    }


def expect(code: str, function) -> dict[str, str]:
    try:
        function()
    except GovernanceError as exc:
        if exc.code != code:
            raise
        return {"expected": code, "observed": exc.code, "status": "PASS"}
    raise GovernanceError("RISK_FIXTURE_UNEXPECTED_PASS", code)


def run_suite(root: Path) -> dict:
    records, package_ids, canonical_ids, packages = load_records(root)
    validate_risk_links(records, package_ids, canonical_ids, root)
    r30 = next(row for row in records if row["riskId"] == "R-30")
    r32 = next(row for row in records if row["riskId"] == "R-32")
    phase_packages: defaultdict[str, list[dict]] = defaultdict(list)
    for package in packages.values():
        phase_packages[package["implementation_phase"]].append(package)
        validate_simplicity_review(package)
    expected_phases = {f"I{index}" for index in range(16)}
    if set(phase_packages) != expected_phases or sum(map(len, phase_packages.values())) != 155:
        raise GovernanceError("SIMPLICITY_PHASE_COVERAGE", "R-30")
    other_phase_package = next(package for package in packages.values() if package["implementation_phase"] != "I0")
    blocker = {
        "blockerId": "R32-B1", "affectedRecord": PACKAGE_ID,
        "knownFacts": ["The authoritative path is unknown"],
        "exactUnknown": "Exact canonical path", "safeChecksExhausted": ["registry lookup"],
        "evidenceLinks": ["graphify/13-implementation/WP-I0-011/verification-report.json"],
        "independentWork": ["Continue unrelated validated checks"],
    }
    validate_blocker(blocker, "R-32")
    base_evidence = [valid_evidence(row) for row in records]
    package_statuses = {row["testOwnerPackage"]: "IN_PROGRESS" for row in records}
    verified = next(row for row in records if row["verificationStatus"] == "VERIFIED")
    adversarial_path = f"graphify/13-implementation/{verified['testOwnerPackage']}/adversarial-review.md"
    adversarial_raw = subprocess.run(
        ["git", "show", f"{verified['implementationCommit']}:{adversarial_path}"],
        cwd=root, check=True, capture_output=True,
    ).stdout
    unrelated_raw_evidence = {
        **valid_evidence(verified),
        "evidenceLinks": [adversarial_path],
        "rawEvidencePath": adversarial_path,
        "rawEvidenceSha256": hashlib.sha256(adversarial_raw).hexdigest(),
    }
    product_record = next(row for row in records if row["testClass"] == "PRODUCT_FAILURE_BOUNDARY")
    product_observation = {
        "productRiskTestEvidence": [{
            "riskId": product_record["riskId"],
            "runtimeRequirementId": product_record["runtimeRequirementId"],
            "testOwnerPackage": product_record["testOwnerPackage"],
            "status": "PASS", "synthetic": False,
            "commandOrInspection": "future owning-package real failure-boundary command",
            "observedOutput": {"boundaryExercised": True},
        }]
    }
    fixtures = [
        {"id": "all-32-mappings-valid", "status": "PASS", "observed": "accepted"},
        {"id": "R-30-per-phase-simplicity-real-test", "status": "PASS", "observed": "155 packages across 16 phases accepted"},
        {"id": "R-32-blocked-protocol-real-test", "status": "PASS", "observed": "unknown path/field/schema/ownership audit produced typed blocker"},
        {"id": "high-critical-risk-no-test-owner", **expect("RISK_TEST_OWNER_INVALID", lambda: validate_risk_links([{**records[0], "testOwnerPackage": ""}, *records[1:]], package_ids, canonical_ids))},
        {"id": "high-critical-risk-nonexistent-owner", **expect("RISK_TEST_OWNER_INVALID", lambda: validate_risk_links([{**records[0], "testOwnerPackage": "WP-I9-999"}, *records[1:]], package_ids, canonical_ids))},
        {"id": "test-owner-earlier-than-mitigation", **expect("RISK_TEST_OWNER_UPSTREAM", lambda: validate_risk_links([{**records[0], "prerequisitesSatisfied": False}, *records[1:]], package_ids, canonical_ids))},
        {"id": "omitted-mitigation-prerequisite", **expect("RISK_PREREQUISITE_INVALID", lambda: validate_risk_links([{**next(row for row in records if row["riskId"] == "R-07"), "requiredAfterPackages": [], "prerequisitesSatisfied": True}, *[row for row in records if row["riskId"] != "R-07"]], package_ids, canonical_ids, root))},
        {"id": "unrelated-canonical-risk-requirement", **expect("RISK_REQUIREMENT_BINDING_INVALID", lambda: validate_risk_links([{**records[0], "runtimeRequirementId": "CAN-FAIL-02"}, *records[1:]], package_ids, canonical_ids, root))},
        {"id": "missing-blocking-package-gate", **expect("RISK_PACKAGE_GATE_INVALID", lambda: validate_risk_links([{**records[0], "blockingPackageGate": ""}, *records[1:]], package_ids, canonical_ids))},
        {"id": "metadata-only-fake-product-test", **expect("RISK_RUNTIME_SYNTHETIC_EVIDENCE", lambda: validate_runtime_risk_gates(records, {records[0]["testOwnerPackage"]: "COMPLETE"}, [{**valid_evidence(records[0]), "synthetic": True}], "PENDING"))},
        {"id": "package-complete-risk-test-absent", **expect("RISK_RUNTIME_EVIDENCE_MISSING", lambda: validate_runtime_risk_gates(records, {records[0]["testOwnerPackage"]: "COMPLETE"}, [], "PENDING"))},
        {"id": "package-complete-risk-test-fail", **expect("RISK_RUNTIME_TEST_NOT_PASS", lambda: validate_runtime_risk_gates(records, {records[0]["testOwnerPackage"]: "COMPLETE"}, [{**valid_evidence(records[0]), "status": "FAIL"}], "PENDING"))},
        {"id": "release-pass-high-critical-risk-unresolved", **expect("RISK_RELEASE_UNRESOLVED", lambda: validate_runtime_risk_gates(records, package_statuses, base_evidence[:-1], "PASS"))},
        {"id": "duplicate-conflicting-risk-test-owner", **expect("RISK_COVERAGE_INVALID", lambda: validate_risk_links([records[0], {**records[0], "testOwnerPackage": records[1]["testOwnerPackage"]}, *records[2:]], package_ids, canonical_ids))},
        {"id": "test-evidence-wrong-risk", **expect("RISK_RUNTIME_WRONG_RISK", lambda: validate_runtime_risk_gates(records, {records[0]["testOwnerPackage"]: "COMPLETE"}, [{**valid_evidence(records[0]), "runtimeRequirementId": records[1]["runtimeRequirementId"]}], "PENDING"))},
        {"id": "test-evidence-wrong-commit-package", **expect("RISK_RUNTIME_WRONG_PACKAGE", lambda: validate_runtime_risk_gates(records, {records[0]["testOwnerPackage"]: "COMPLETE"}, [{**valid_evidence(records[0]), "testOwnerPackage": records[1]["testOwnerPackage"], "implementationCommit": "0" * 40}], "PENDING"))},
        {"id": "test-evidence-wrong-commit", **expect("RISK_RUNTIME_COMMIT_INVALID", lambda: validate_runtime_risk_gates(records, {records[0]["testOwnerPackage"]: "COMPLETE"}, [{**valid_evidence(records[0]), "implementationCommit": "0" * 39}], "PENDING", root))},
        {"id": "synthetic-governance-fixture-as-runtime-evidence", **expect("RISK_RUNTIME_SYNTHETIC_EVIDENCE", lambda: validate_runtime_risk_gates(records, {records[0]["testOwnerPackage"]: "COMPLETE"}, [{**valid_evidence(records[0]), "synthetic": True, "evidenceKind": "REAL_PRODUCT_RISK_TEST"}], "PENDING"))},
        {"id": "unrelated-owner-document-as-raw-evidence", **expect("RISK_RUNTIME_RAW_EVIDENCE_INVALID", lambda: validate_runtime_risk_gates([verified], {verified["testOwnerPackage"]: "COMPLETE"}, [unrelated_raw_evidence], "PENDING", root))},
        {"id": "future-product-raw-evidence-schema-valid", "status": "PASS", "observed": "accepted"} if validate_raw_risk_observation(product_record, product_observation) is None else {},
        {"id": "future-product-metadata-only-rejected", **expect("RISK_RUNTIME_RAW_EVIDENCE_INVALID", lambda: validate_raw_risk_observation(product_record, {"productRiskTestEvidence": [{"riskId": product_record["riskId"], "status": "PASS"}]}))},
        {"id": "R-30-mechanical-split-rejected", **expect("SIMPLICITY_MECHANICAL_SPLIT", lambda: validate_simplicity_review({**packages[PACKAGE_ID], "capacity_split": True}))},
        {"id": "R-30-other-phase-violation-rejected", **expect("SIMPLICITY_BOUNDARY_MISSING", lambda: validate_simplicity_review({**other_phase_package, "bounded_surface": ""}))},
        {"id": "R-32-guessed-path-rejected", **expect("BLOCKER_GUESS_PROHIBITED", lambda: validate_blocker({**blocker, "guessedPath": True}, "R-32"))},
        {"id": "R-32-guessed-field-rejected", **expect("BLOCKER_GUESS_PROHIBITED", lambda: validate_blocker({**blocker, "guessedField": True}, "R-32"))},
        {"id": "R-32-guessed-schema-rejected", **expect("BLOCKER_GUESS_PROHIBITED", lambda: validate_blocker({**blocker, "guessedSchema": True}, "R-32"))},
        {"id": "R-32-guessed-ownership-rejected", **expect("BLOCKER_GUESS_PROHIBITED", lambda: validate_blocker({**blocker, "guessedOwnership": "WP-I9-999"}, "R-32"))},
    ]
    return {
        "status": "PASS", "suite": "GOVERNANCE_ENFORCEMENT_NOT_PRODUCT_RUNTIME",
        "riskCount": len(records), "fixtures": fixtures,
        "realGovernanceMitigationTests": [r30["runtimeRequirementId"], r32["runtimeRequirementId"]],
        "governanceMitigationEvidence": [
            {
                "riskId": "R-30", "runtimeRequirementId": r30["runtimeRequirementId"],
                "testOwnerPackage": PACKAGE_ID, "status": "PASS", "synthetic": False,
                "commandOrInspection": "validate_simplicity_review over every canonical work package grouped by implementation_phase",
                "observedOutput": {"phaseCount": 16, "packageCount": 155, "phasePackageCounts": {phase: len(rows) for phase, rows in sorted(phase_packages.items())}},
            },
            {
                "riskId": "R-32", "runtimeRequirementId": r32["runtimeRequirementId"],
                "testOwnerPackage": PACKAGE_ID, "status": "PASS", "synthetic": False,
                "commandOrInspection": "validate_blocker positive audit plus path/field/schema/ownership guess rejection",
                "observedOutput": {"typedBlockerAccepted": True, "guessDimensionsRejected": ["path", "field", "schema", "ownership"]},
            },
        ],
        "pendingProductRiskTests": sum(row["testClass"] == "PRODUCT_FAILURE_BOUNDARY" and row["verificationStatus"] == "PENDING" for row in records),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--risk")
    args = parser.parse_args()
    package_dir = Path(__file__).resolve().parent
    root = package_dir.parents[2]
    result = run_suite(root)
    if args.risk:
        record = next((row for row in result["fixtures"] if row["id"] == "all-32-mappings-valid"), None)
        if not record or args.risk not in {f"R-{index:02d}" for index in range(1, 33)}:
            raise GovernanceError("RISK_UNKNOWN", args.risk)
        result = {"status": "PASS", "riskId": args.risk, "checkType": result["suite"]}
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
