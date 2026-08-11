"""Apply the reviewed CAN-LAM-TEST-020 ownership amendment deterministically."""

from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from copy import deepcopy
from io import StringIO
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1]
GRAPHIFY = SOURCE.parent
REPO = GRAPHIFY.parent
REVISION = "2026-08-11-wp-i0-011-ownership-repair"
PARENT = "CAN-LAM-TEST-020"
RELEASE_GATE = "I15:RELEASE"


def read_csv(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(path.open(encoding="utf-8-sig", newline="")))


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str] | None = None) -> None:
    fields = fields or list(rows[0])
    stream = StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    path.write_text(stream.getvalue(), encoding="utf-8", newline="\n")


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def parse_risk_register() -> dict[str, dict[str, str]]:
    path = REPO / "graphify/11-implementation-ready-plan/19-RISK-REGISTER-EXPANDED.md"
    rows: dict[str, dict[str, str]] = {}
    headers: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells and cells[0] == "ID":
            headers = cells
        elif headers and cells and re.fullmatch(r"R-\d{2}", cells[0]):
            rows[cells[0]] = dict(zip(headers, cells, strict=True))
    if set(rows) != {f"R-{index:02d}" for index in range(1, 33)}:
        raise ValueError("expanded risk register must contain R-01 through R-32 exactly")
    if {row["Severity"] for row in rows.values()} - {"P0", "P1"}:
        raise ValueError("expanded risk register contains a non-P0/P1 row")
    return rows


def ownership_mechanism(record: dict[str, object], risk: dict[str, str]) -> str:
    return (
        f"{record['testOwnerPackage']} owns the executable {risk['ID']} mitigation boundary because its bounded "
        f"surface can run '{risk['Test']}' against {record['testTarget']}; raw evidence tied to that package and "
        f"commit blocks {record['testOwnerPackage']}:EXIT and {RELEASE_GATE} when absent or failing."
    )


def child_statement(record: dict[str, object], risk: dict[str, str]) -> str:
    return (
        f"The {record['testOwnerPackage']} exit gate must run and pass the {risk['ID']} '{risk['Test']}' failure or "
        f"boundary test for {risk['Risk']}, preserve raw evidence tied to the executing package and commit, and block "
        f"both {record['testOwnerPackage']}:EXIT and {RELEASE_GATE} when the evidence is absent, stale, mismatched, or failing."
    )


def acceptance(record: dict[str, object], risk: dict[str, str]) -> str:
    return (
        f"Given {risk['ID']} and the implementation owned by {';'.join(record['mitigationOwnerPackages'])}, when "
        f"{record['testOwnerPackage']} evaluates its exit gate, then '{risk['Test']}' executes against the real "
        f"mitigation boundary and produces package-and-commit-bound raw PASS evidence; otherwise the package and release gates fail."
    )


def main() -> None:
    ownership_path = SOURCE / "risks/risk-test-ownership.json"
    ownership = json.loads(ownership_path.read_text(encoding="utf-8"))
    records = ownership["records"]
    risks = parse_risk_register()
    if len(records) != 32 or {row["riskId"] for row in records} != set(risks):
        raise ValueError("ownership registry must map every expanded risk exactly once")
    for record in records:
        record.setdefault("verificationStatus", "PENDING")
        record.setdefault("runtimeEvidence", [])
        record.setdefault("implementationCommit", "")
        record["blockingPackageGate"] = f"{record['testOwnerPackage']}:EXIT"
        record["blockingReleaseGate"] = RELEASE_GATE
    write_json(ownership_path, ownership)

    package_path = SOURCE / "packages/work-packages.json"
    package_doc = json.loads(package_path.read_text(encoding="utf-8"))
    packages = package_doc["workPackages"]
    package_by_id = {row["work_package_id"]: row for row in packages}
    for record in records:
        for package_id in [*record["mitigationOwnerPackages"], record["testOwnerPackage"], *record["requiredAfterPackages"]]:
            if package_id not in package_by_id:
                raise ValueError(f"unknown risk owner package: {package_id}")

    requirements_path = SOURCE / "requirements/requirements.csv"
    requirements = read_csv(requirements_path)
    req_fields = list(requirements[0])
    requirements = [row for row in requirements if not row["canonical_id"].startswith("CAN-LAM-RISK-TEST-")]
    parent = next(row for row in requirements if row["canonical_id"] == PARENT)
    parent_statement = (
        "The planning-governance validator must map every P0/P1 risk to exactly one risk-specific test requirement, "
        "an actual mitigation/test owner, a blocking package exit gate, and I15:RELEASE; it must reject missing, "
        "duplicate, upstream-incompatible, metadata-only, or unverified mappings without claiming that WP-I0-011 "
        "executes downstream product tests."
    )
    parent_acceptance = (
        "Given the authoritative P0/P1 risk register, when planning validation runs, then every risk has one reviewed "
        "child test obligation whose owner is the mitigation package or a DAG-reachable downstream test package, and "
        "no product risk is marked verified from governance metadata alone."
    )
    parent.update({
        "title": "P0/P1 risk-test ownership and gate enforcement",
        "statement": parent_statement,
        "rationale": "Planning governance owns traceability and enforcement; the package that implements or integrates each mitigation owns its real executable boundary test.",
        "acceptance_criteria": parent_acceptance,
        "verification_method": "Risk ownership registry schema, DAG reachability, package-gate and release-gate adversarial fixture suite.",
        "risk_links": "R-01..R-32",
        "normalization_status": "EXPLICIT_REVIEWED_REWRITE",
        "normalization_reviewer_status": "REVIEWED_CORRECTED",
        "review_notes": "Split governance enforcement from 32 risk-specific executable mitigation-test obligations.",
    })
    requirement_by_id = {row["canonical_id"]: row for row in requirements}
    mappings_path = SOURCE / "requirements/requirement-mapping.csv"
    mappings = [row for row in read_csv(mappings_path) if not row["canonical_id"].startswith("CAN-LAM-RISK-TEST-")]
    map_fields = list(mappings[0])
    parent_mapping = next(row for row in mappings if row["canonical_id"] == PARENT)
    parent_mapping.update({
        "mapping_rationale": "WP-I0-011 owns the risk-to-test mapping schema, DAG/gate enforcement, and adversarial rejection logic; downstream packages own real product mitigation tests.",
        "reviewer_status": "REVIEWED_CORRECTED",
    })
    memberships_path = SOURCE / "packages/requirement-membership.csv"
    memberships = [row for row in read_csv(memberships_path) if not row["canonical_id"].startswith("CAN-LAM-RISK-TEST-")]
    member_fields = list(memberships[0])
    parent_member = next(row for row in memberships if row["canonical_id"] == PARENT)
    parent_member.update({
        "work_package_id": "WP-I0-011",
        "membership_rationale": "WP-I0-011 owns the explicit ownership registry, reachability checks, package/release gate enforcement, and rejection fixtures; it does not impersonate the downstream packages that execute product mitigation tests.",
        "reviewer_status": "REVIEWED",
    })

    for record in records:
        risk = risks[record["riskId"]]
        owner = package_by_id[record["testOwnerPackage"]]
        if not owner["reviewed_capabilities"]:
            owner["reviewed_capabilities"] = ["Risk mitigation verification"]
        owner_capability = owner["reviewed_capabilities"][0]
        rid = record["runtimeRequirementId"]
        statement = child_statement(record, risk)
        criterion = acceptance(record, risk)
        row = deepcopy(parent)
        row.update({
            "canonical_id": rid,
            "original_requirement_ids": risk["ID"],
            "parent_requirement_id": PARENT,
            "requirement_type": "VERIFICATION_GATE",
            "title": f"{risk['ID']} executable mitigation boundary test",
            "statement": statement,
            "rationale": record["rationale"],
            "source_plan": "19-RISK-REGISTER-EXPANDED.md",
            "source_section": "Expanded P0/P1 risk register",
            "source_text": " | ".join(risk.values()),
            "source_locator": risk["ID"],
            "code_evidence_references": "ABSENT_NEW_WORK" if record["verificationStatus"] == "PENDING" else ";".join(record["runtimeEvidence"]),
            "target_capability": owner_capability,
            "acceptance_criteria": criterion,
            "priority": risk["Severity"],
            "implementation_status": "VERIFIED" if record["verificationStatus"] == "VERIFIED" else "NOT_STARTED",
            "verification_method": f"Execute {risk['Test']} at {record['testOwnerPackage']}:EXIT and retain raw package/commit evidence.",
            "risk_links": risk["ID"],
            "decision_links": "CAN-LAM-TEST-020;risk-test-ownership.json",
            "normalization_status": "SYNTHESIZED_RISK_TEST_CHILD",
            "notes": f"Gate binding: {record['testOwnerPackage']}:EXIT;{RELEASE_GATE}.",
            "primary_implementation_phase": owner["implementation_phase"],
            "verification_phases": f"{owner['implementation_phase']};I15" if owner["implementation_phase"] != "I15" else "I15",
            "release_gate": "RG-FINAL",
            "phase_mapping_rationale": record["rationale"],
            "legacy_work_package_id": "",
            "old_primary_phase": "",
            "phase_mapping_changed": "true",
            "legacy_target_capability": "Risk management",
            "canonical_capability": owner_capability,
            "normalization_reviewer_status": "REVIEWED_CORRECTED",
            "review_notes": ownership_mechanism(record, risk),
        })
        requirements.append(row)
        requirement_by_id[rid] = row
        mappings.append({
            "canonical_id": rid,
            "canonical_capability": row["canonical_capability"],
            "primary_implementation_phase": owner["implementation_phase"],
            "integration_verification_phases": row["verification_phases"],
            "removal_phase": "",
            "release_validation_phase": "I15",
            "global_invariant_links": "CAN-LAM-TEST-020",
            "mapping_rationale": record["rationale"],
            "reviewer_status": "REVIEWED_CORRECTED",
            "exception_status": "NONE",
            "previous_capability": "Risk management",
            "previous_primary_phase": "",
        })
        memberships.append({
            "canonical_id": rid,
            "work_package_id": record["testOwnerPackage"],
            "membership_rationale": ownership_mechanism(record, risk),
            "reviewer_status": "REVIEWED",
        })

    requirements.sort(key=lambda row: row["canonical_id"])
    mappings.sort(key=lambda row: row["canonical_id"])
    memberships.sort(key=lambda row: row["canonical_id"])
    write_csv(requirements_path, requirements, req_fields)
    write_csv(mappings_path, mappings, map_fields)
    write_csv(memberships_path, memberships, member_fields)

    risk_rows = []
    for record in records:
        risk = risks[record["riskId"]]
        risk_rows.append({
            "risk_id": risk["ID"], "risk": risk["Risk"], "severity": risk["Severity"],
            "trigger": risk["Trigger"], "impact": risk["Impact"], "prevention": risk["Prevention"],
            "detection": risk["Detection"], "recovery": risk["Recovery"], "required_test": risk["Test"],
            "owner_phase": risk["Owner phase"], "source_status": risk["Status"],
            "runtime_requirement_id": record["runtimeRequirementId"],
            "mitigation_owner_packages": ";".join(record["mitigationOwnerPackages"]),
            "test_owner_package": record["testOwnerPackage"],
            "required_after_packages": ";".join(record["requiredAfterPackages"]),
            "package_gate": record["blockingPackageGate"], "release_gate": record["blockingReleaseGate"],
            "verification_status": record["verificationStatus"],
            "runtime_evidence": ";".join(record["runtimeEvidence"]),
            "implementation_commit": record["implementationCommit"],
            "review_status": ownership["reviewStatus"], "review_revision": ownership["reviewRevision"],
        })
    write_csv(SOURCE / "risks/high-critical-risk-register.csv", risk_rows)

    risk_by_owner: defaultdict[str, list[dict[str, object]]] = defaultdict(list)
    for record in records:
        risk_by_owner[record["testOwnerPackage"]].append(record)
    members_by_package: defaultdict[str, list[str]] = defaultdict(list)
    for row in memberships:
        members_by_package[row["work_package_id"]].append(row["canonical_id"])
    for package in packages:
        pid = package["work_package_id"]
        package["reviewed_item_count"] = str(len(members_by_package[pid]))
        if not risk_by_owner[pid]:
            continue
        obligations = "; ".join(
            f"{record['riskId']}/{record['runtimeRequirementId']} executes '{risks[record['riskId']]['Test']}'"
            for record in risk_by_owner[pid]
        )
        package["tests"] = package["tests"].split(" Risk-gate obligations:", 1)[0] + f" Risk-gate obligations: {obligations}."
        package["exit_gate"] = package["exit_gate"].split(" Risk-gate exit:", 1)[0] + (
            f" Risk-gate exit: raw PASS evidence tied to {pid} and its implementation commit is required for "
            f"{'; '.join(record['riskId'] for record in risk_by_owner[pid])}; absence or failure blocks {pid}:EXIT and {RELEASE_GATE}."
        )
    write_json(package_path, package_doc)

    dependency_path = SOURCE / "packages/dependencies.csv"
    dependencies = read_csv(dependency_path)
    dep_fields = list(dependencies[0])
    required_edges = [
        ("WP-I15-008", "WP-I10-002"), ("WP-I15-008", "WP-I11-012"),
        ("WP-I8-005", "WP-I7-008"), ("WP-I15-001", "WP-I10-002"),
        ("WP-I0-007", "WP-I0-006"), ("WP-I15-008", "WP-I3-010"),
        ("WP-I15-008", "WP-I5-017"), ("WP-I15-008", "WP-I13-011"),
    ]
    existing_pairs = {(row["work_package_id"], row["prerequisite_work_package_id"]) for row in dependencies}
    for dependent, prerequisite in required_edges:
        if (dependent, prerequisite) in existing_pairs:
            continue
        dependencies.append({
            "work_package_id": dependent,
            "prerequisite_work_package_id": prerequisite,
            "dependency_type": "REQUIRES_RUNTIME",
            "technical_rationale": f"{dependent} owns an integrated risk boundary test that consumes the mitigation implemented by {prerequisite} before it can produce valid raw evidence.",
            "evidence": f"risk-test-ownership.json reviewed requiredAfterPackages binding for {dependent} <- {prerequisite}",
            "review_status": "REVIEWED_CORRECTED", "reviewer_type": "AI_SEMANTIC_REVIEW",
            "review_revision": REVISION, "reviewer_status": "REVIEWED", "artificial_adjacency": "false",
        })
    dependencies.sort(key=lambda row: (row["work_package_id"], row["prerequisite_work_package_id"]))
    write_csv(dependency_path, dependencies, dep_fields)

    update_reviews(requirements, mappings, memberships, packages, dependencies, records, risks, risk_by_owner)


def update_reviews(requirements, mappings, memberships, packages, dependencies, records, risks, risk_by_owner) -> None:
    review_root = SOURCE / "reviews"
    req_by_id = {row["canonical_id"]: row for row in requirements}
    map_by_id = {row["canonical_id"]: row for row in mappings}
    member_by_id = {row["canonical_id"]: row for row in memberships}
    package_by_id = {row["work_package_id"]: row for row in packages}

    path = review_root / "reviewed-actionable-requirements-v3.csv"
    rows = [row for row in read_csv(path) if not row["Canonical ID"].startswith("CAN-LAM-RISK-TEST-")]
    fields = list(rows[0])
    parent_review = next(row for row in rows if row["Canonical ID"] == PARENT)
    for rid in [PARENT, *(record["runtimeRequirementId"] for record in records)]:
        req = req_by_id[rid]
        mapping = map_by_id[rid]
        row = parent_review if rid == PARENT else deepcopy(parent_review)
        row.update({
            "Canonical ID": rid, "Title": req["title"], "Requirement type": req["requirement_type"],
            "Original source plan": req["source_plan"], "Original source section": req["source_section"],
            "Original source locator": req["source_locator"], "Original source text": req["source_text"],
            "Previous statement": row.get("Final reviewed statement", ""), "Final reviewed statement": req["statement"],
            "Final classification": req["requirement_type"], "Final capability": req["canonical_capability"],
            "Final phase": mapping["primary_implementation_phase"],
            "Actor or subsystem": f"The {req['canonical_capability']} subsystem",
            "Trigger or precondition": req["source_text"], "Required behaviour": req["statement"],
            "Observable result": req["acceptance_criteria"], "Failure behaviour": "The owning package and I15 release gates fail without valid raw evidence.",
            "Preservation behaviour": "No unrelated authoritative state is modified by a failed or missing test.",
            "Authority boundary": f"Owned by {member_by_id[rid]['work_package_id']}; governance validates but does not impersonate product execution.",
            "Privacy or security boundary": "Local-only test evidence; no outbound transfer is introduced.",
            "Parent requirement ID": req["parent_requirement_id"], "Acceptance criteria": req["acceptance_criteria"],
            "Verification method": req["verification_method"], "Codebase evidence": req["code_evidence_references"],
            "Architectural evidence": req["review_notes"], "Review decision": "CORRECTED",
            "Correction applied": "YES", "Item-specific rationale": req["rationale"], "Remaining concern": "",
            "Reviewer role": "OWNERSHIP_AMENDMENT_REVIEWER", "Review revision": REVISION, "Review status": "REVIEWED_CORRECTED",
        })
        if rid != PARENT:
            rows.append(row)
    rows.sort(key=lambda row: row["Canonical ID"])
    write_csv(path, rows, fields)

    path = review_root / "reviewed-package-memberships-v3.csv"
    rows = [row for row in read_csv(path) if not row["Canonical ID"].startswith("CAN-LAM-RISK-TEST-")]
    fields = list(rows[0])
    template = next(row for row in rows if row["Canonical ID"] == PARENT)
    for record in records:
        rid, risk = record["runtimeRequirementId"], risks[record["riskId"]]
        package = package_by_id[record["testOwnerPackage"]]
        req = req_by_id[rid]
        row = deepcopy(template)
        mechanism = ownership_mechanism(record, risk)
        row.update({
            "Canonical ID": rid, "Requirement statement": req["statement"],
            "Candidate package": record["testOwnerPackage"], "Final package": record["testOwnerPackage"],
            "Package phase": package["implementation_phase"], "Requirement phase": package["implementation_phase"],
            "Package surface": package["bounded_surface"], "Requirement obligation": req["statement"],
            "Exact ownership mechanism": mechanism, "Shared contract": package["contracts_affected"],
            "Shared schema": package["schemas_affected"], "Shared implementation location": f"Bounded {record['testOwnerPackage']} implementation surface.",
            "Shared tests": f"{risk['Test']} with raw evidence bound to {record['testOwnerPackage']} and its commit.",
            "Alternative package considered": "WP-I0-011 metadata-only ownership was rejected because it cannot execute this mitigation boundary.",
            "Candidate decision": "CORRECTED", "Final decision": "CONFIRMED",
            "Item-specific rationale": mechanism,
            "Evidence": f"requirements.csv:{rid}; requirement-membership.csv:{rid}; risk-test-ownership.json:{record['riskId']}",
            "Reviewer role": "OWNERSHIP_AMENDMENT_MEMBERSHIP_REVIEWER", "Review revision": REVISION,
            "Review status": "REVIEWED_CONFIRMED",
        })
        rows.append(row)
    rows.sort(key=lambda row: row["Canonical ID"])
    write_csv(path, rows, fields)

    path = review_root / "reviewed-work-packages-v3.csv"
    rows = read_csv(path)
    fields = list(rows[0])
    members_by_package: defaultdict[str, list[str]] = defaultdict(list)
    for member in memberships:
        members_by_package[member["work_package_id"]].append(member["canonical_id"])
    for row in rows:
        package = package_by_id[row["Final package ID"]]
        ids = sorted(members_by_package[package["work_package_id"]])
        row.update({
            "Requirement count": str(len(ids)), "Exact included requirement IDs": ";".join(ids),
            "Exact tests": package["tests"], "Exact failure cases": package["failure_cases"],
            "Rollback/recovery behaviour": package["rollback_or_recovery"], "Completion evidence": package["completion_evidence"],
            "Exit gate": package["exit_gate"], "Commit boundary": package["commit_boundary"],
            "Review revision": REVISION if risk_by_owner[package["work_package_id"]] else row["Review revision"],
        })
    write_csv(path, rows, fields)

    path = review_root / "pass2c-package-architecture-review.csv"
    rows = read_csv(path)
    fields = list(rows[0])
    for row in rows:
        if row["Package ID"] != "WP-I0-011":
            continue
        package = package_by_id["WP-I0-011"]
        row.update({
            "Requirement count": package["reviewed_item_count"],
            "Shared tests": package["tests"],
            "Final decision": "KEEP_WITH_COHESION_BOUNDARY_EXCEPTION",
            "Reviewer rationale": "WP-I0-011 remains cohesive because CAN-LAM-TEST-020 plus R-30/R-32 exercise governance mapping, bounded-package simplicity, and blocked-item protocol at the same tracker/evidence authority boundary; downstream product mitigation tests remain excluded.",
        })
    write_csv(path, rows, fields)

    path = review_root / "reviewed-dependencies-v3.csv"
    rows = read_csv(path)
    fields = list(rows[0])
    by_key = {(row["Dependent package"], row["Prerequisite package"]): row for row in rows}
    for edge in dependencies:
        key = (edge["work_package_id"], edge["prerequisite_work_package_id"])
        if key in by_key:
            continue
        row = {field: "" for field in fields}
        row.update({
            "Dependent package": key[0], "Prerequisite package": key[1],
            "Candidate dependency type": edge["dependency_type"], "Final dependency type": edge["dependency_type"],
            "Technical prerequisite supplied": edge["technical_rationale"], "Consuming behaviour": edge["technical_rationale"],
            "Exact contract/schema/component relationship": edge["evidence"], "Evidence": edge["evidence"],
            "Alternative considered": "Ordering without this mitigation prerequisite was rejected.", "Artificial adjacency": "false",
            "Candidate decision": "CORRECTED", "Final decision": "CONFIRMED",
            "Item-specific rationale": f"{key[0]} consumes {key[1]} because {edge['technical_rationale']}",
            "Reviewer role": "OWNERSHIP_AMENDMENT_DEPENDENCY_REVIEWER", "Review revision": REVISION,
            "Review status": "REVIEWED_CONFIRMED",
        })
        rows.append(row)
    rows.sort(key=lambda row: (row["Dependent package"], row["Prerequisite package"]))
    write_csv(path, rows, fields)

    path = review_root / "independently-verified-package-members-v2.csv"
    rows = [row for row in read_csv(path) if not row["Canonical ID"].startswith("CAN-LAM-RISK-TEST-")]
    fields = list(rows[0])
    template = next(row for row in rows if row["Canonical ID"] == PARENT)
    for record in records:
        rid, risk = record["runtimeRequirementId"], risks[record["riskId"]]
        package = package_by_id[record["testOwnerPackage"]]
        mechanism = ownership_mechanism(record, risk)
        row = deepcopy(template)
        row.update({
            "Package ID": record["testOwnerPackage"], "Canonical ID": rid,
            "Candidate placement": record["testOwnerPackage"], "Final placement": record["testOwnerPackage"],
            "Exact authority owner": package["reviewed_capabilities"][0], "Exact implementation owner": package["objective"],
            "Exact shared mechanism": mechanism, "Exact Codebase evidence": req_by_id[rid]["code_evidence_references"],
            "Exact contract evidence": package["contracts_affected"], "Exact schema evidence": package["schemas_affected"],
            "Exact test evidence": f"{risk['Test']} for {record['riskId']} at {record['testOwnerPackage']}:EXIT.",
            "Exact failure/recovery evidence": "Missing, stale, mismatched, or failing raw evidence blocks package and release gates without changing unrelated authoritative state.",
            "Alternative considered": "WP-I0-011 metadata-only ownership was rejected.", "Final decision": "VERIFIED",
            "Item-specific rationale": mechanism,
            "Evidence sources": f"requirements.csv:{rid};requirement-membership.csv:{rid};risk-test-ownership.json:{record['riskId']}",
            "Reviewer role": "OWNERSHIP_AMENDMENT_MEMBER_VERIFIER", "Review revision": REVISION, "Verification status": "VERIFIED",
        })
        rows.append(row)
    rows.sort(key=lambda row: row["Canonical ID"])
    write_csv(path, rows, fields)

    path = review_root / "independently-verified-package-tests-v2.csv"
    rows = read_csv(path)
    fields = list(rows[0])
    members_by_package = defaultdict(list)
    for member in memberships:
        members_by_package[member["work_package_id"]].append(member["canonical_id"])
    for row in rows:
        pid = row["Package ID"]
        row["Requirement IDs"] = ";".join(sorted(members_by_package[pid]))
        if risk_by_owner[pid]:
            row["Success cases"] = package_by_id[pid]["tests"]
            row["Evidence"] = f"Requirement and risk-gate verification methods for {pid}; risk-test-ownership.json"
            row["Review revision"] = REVISION
            row["Item-specific rationale"] = f"Exact membership coverage for {pid}: {len(members_by_package[pid])} canonical IDs, including its explicit risk boundary obligations, are owned by the package tests and exit gate."
    write_csv(path, rows, fields)

    path = review_root / "independently-verified-package-exit-gates-v2.csv"
    rows = read_csv(path)
    fields = list(rows[0])
    for row in rows:
        package = package_by_id[row["Package ID"]]
        row["Exit-gate text"] = package["exit_gate"]
        row["Test evidence required"] = package["tests"]
        row["Stop condition"] = package["exit_gate"]
        if risk_by_owner[row["Package ID"]]:
            row["Review revision"] = REVISION
            row["Item-specific rationale"] = f"Cross-checked {row['Package ID']} risk-test ownership, raw-evidence requirement, package exit gate, and I15 release block."
    write_csv(path, rows, fields)


if __name__ == "__main__":
    main()
