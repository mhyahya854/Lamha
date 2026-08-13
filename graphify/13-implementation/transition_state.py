#!/usr/bin/env python3
"""Persist a GitHub-verified package completion and deterministic next authorization."""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
STATE = Path(__file__).resolve().parent / "implementation-state.json"
TRANSITION = Path(__file__).resolve().parent / "implementation-transition.json"
LEGACY = ROOT / "graphify/13-implementation/WP-I0-011"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("package")
    parser.add_argument("commit")
    args = parser.parse_args()
    package = args.package
    commit = args.commit
    if git("rev-parse", "HEAD") != commit or git("rev-parse", "origin/main") != commit:
        raise SystemExit("completion commit is not the exact local/origin main SHA")

    governance = load_module("governance", LEGACY / "governance.py")
    sys.modules["governance"] = governance
    sys.path.insert(0, str(LEGACY))
    collector = load_module("collector", LEGACY / "collect_evidence.py")
    source = ROOT / "graphify/semantic-plan-source"
    requirements = collector.read_csv(source / "requirements/requirements.csv")
    canonical_ids = {row["canonical_id"] for row in requirements}
    memberships = collector.read_csv(source / "packages/requirement-membership.csv")
    owned = sorted(row["canonical_id"] for row in memberships if row["work_package_id"] == package)
    package_rows = collector.load_json(source / "packages/work-packages.json")["workPackages"]
    packages = {row["work_package_id"]: row for row in package_rows}
    package_ids = set(packages)
    dependencies = collector.read_csv(source / "packages/dependencies.csv")

    prior_path = STATE if STATE.exists() else LEGACY / "implementation-state.json"
    state = collector.load_json(prior_path)
    if package in state["completedPackages"]:
        raise SystemExit(f"{package} is already complete")
    evidence = collector.completed_package_evidence(ROOT, package, commit)
    timestamp = git("show", "-s", "--format=%cI", commit)
    actor = git("show", "-s", "--format=%cn", commit)
    revisions = list(state["revisions"])
    package_links = [*evidence["links"], f"git-origin:{commit}"]
    collector.append_chain(
        revisions, "PACKAGE", package, actor, timestamp, package_links,
        collector.complete_package_gates(package, evidence, commit),
    )
    for requirement in owned:
        requirement_links = [
            *package_links,
            "graphify/semantic-plan-source/requirements/requirements.csv",
            "graphify/semantic-plan-source/packages/requirement-membership.csv",
        ]
        collector.append_chain(
            revisions, "REQUIREMENT", requirement, actor, timestamp,
            requirement_links,
            collector.complete_requirement_gates(package, evidence, commit),
        )

    current = {
        f"{item['subjectType']}:{item['subjectId']}": item["status"]
        for item in state["importedBaselines"]
    }
    for revision in revisions:
        current[f"{revision['subjectType']}:{revision['subjectId']}"] = revision["toStatus"]
    completed = sorted({key.split(":", 1)[1] for key, value in current.items() if key.startswith("PACKAGE:") and value == "COMPLETE"})
    ready = collector.ready_packages(packages, dependencies, set(completed))
    selected = ready[0] if ready else None

    next_state = {
        **state,
        "packageId": package,
        "repositoryHead": commit,
        "explicitAuthorizedPackage": selected,
        "selectedPackage": selected,
        "readyPackages": ready,
        "completedPackages": completed,
        "revisions": revisions,
        "current": current,
    }
    next_state.pop("generationId", None)
    next_state["generationId"] = governance.semantic_hash(next_state)
    risks = collector.parse_risks(ROOT, packages)
    governance.validate_tracker(
        next_state, canonical_ids, package_ids, ROOT,
        risk_ownership=risks,
        runtime_risk_evidence=next_state.get("runtimeRiskEvidence", []),
        release_status="PENDING",
        required_current_keys={f"PACKAGE:{package}", *{f"REQUIREMENT:{rid}" for rid in owned}},
    )
    STATE.write_text(json.dumps(next_state, indent=2) + "\n", encoding="utf-8")
    actionable_total = sum(row.get("supersession_status") == "ACTIVE" for row in requirements)
    completed_requirements = sum(key.startswith("REQUIREMENT:") and value == "COMPLETE" for key, value in current.items())
    transition = {
        "schemaVersion": 1,
        "status": "PASS",
        "completedPackage": package,
        "githubVerifiedCommit": commit,
        "completedRequirements": owned,
        "readyPackages": ready,
        "selectionRule": "phase, package major, package minor, full ID",
        "selectedPackage": selected,
        "selectedPackageStatus": "NOT_STARTED" if selected else None,
        "completedPackages": len(completed),
        "totalPackages": len(packages),
        "completedActionableRequirements": completed_requirements,
        "totalActionableRequirements": actionable_total,
        "nextPackageImplementationChanges": 0,
        "codebaseChanges": {"added": 0, "removed": 0, "modified": 0, "renamed": 0},
        "stateGenerationId": next_state["generationId"],
    }
    TRANSITION.write_text(json.dumps(transition, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(transition, sort_keys=True))


if __name__ == "__main__":
    main()
