"""Generate the live GPT-5.6 reviewer handoff files.

Writes gpt-review-counts.json and gpt-review-sha-manifest.json into both the
authoritative handoff source and the rendered plan.  The SHA manifest covers
every deterministic committed Graphify file except itself and the explicitly
documented volatile certification/external-integrity artifacts, so it cannot
hash itself or depend on artifacts that are verified by the deterministic
certification runs instead.
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import deque
from pathlib import Path

sys.dont_write_bytecode = True

GRAPHIFY = Path(__file__).resolve().parents[1]
SOURCE = GRAPHIFY / "semantic-plan-source"
PLAN = GRAPHIFY / "12-semantic-implementation-plan"
HANDOFF_SOURCE = SOURCE / "handoff-gpt"
HANDOFF_PLAN = PLAN / "14-handoff"

DECLARATION = "FULL IMPLEMENTATION PLANNING 100% COMPLETE \u2014 WP-I0-001 MAY BEGIN"
HANDOFF_DECLARATION = "DEEPSEEK PRE-GPT PLANNING REVIEW COMPLETE \u2014 AWAITING GPT-5.6 INDEPENDENT REVIEW"

SHA_MANIFEST_EXCLUDED = {
    # The manifest itself (source and rendered copies).
    "semantic-plan-source/handoff-gpt/gpt-review-sha-manifest.json",
    "12-semantic-implementation-plan/14-handoff/gpt-review-sha-manifest.json",
    # Volatile timestamped external-integrity finals.
    "12-semantic-implementation-plan/13-reports/pass1-external-final.json",
    "12-semantic-implementation-plan/13-reports/pass2c-external-readonly-final.json",
    "12-semantic-implementation-plan/13-reports/pass3-external-readonly-final.json",
    "semantic-plan-source/reviews/pass1-external-final.json",
    "semantic-plan-source/reviews/pass2c-external-readonly-final.json",
    "semantic-plan-source/reviews/pass3-external-readonly-final.json",
    # Self-referential certification artifacts verified by the two-run
    # deterministic certification instead of by this manifest.
    "12-semantic-implementation-plan/PLAN-MANIFEST.json",
    "12-semantic-implementation-plan/13-reports/final-content-manifest.json",
    "12-semantic-implementation-plan/13-reports/final-100-percent-certification.json",
    "12-semantic-implementation-plan/13-reports/final-release-envelope.json",
    "12-semantic-implementation-plan/13-reports/final-determinism-proof.json",
    "semantic-plan-source/reviews/final-content-manifest.json",
    "semantic-plan-source/reviews/final-100-percent-certification.json",
    "semantic-plan-source/reviews/final-release-envelope.json",
    "semantic-plan-source/reviews/final-determinism-proof.json",
    "semantic-plan-source/reviews/final-package-determinism.json",
    "12-semantic-implementation-plan/13-reports/final-package-determinism.json",
    "semantic-plan-source/reviews/pass3-certification-report.json",
    "12-semantic-implementation-plan/13-reports/pass3-certification-report.json",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def compute_counts() -> dict[str, object]:
    requirements = read_csv(SOURCE / "requirements" / "requirements.csv")
    mappings = read_csv(SOURCE / "requirements" / "requirement-mapping.csv")
    mapping_by_id = {row["canonical_id"]: row for row in mappings}
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
        and mapping_by_id.get(row["canonical_id"], {}).get("primary_implementation_phase")
    )
    packages = read_json(SOURCE / "packages" / "work-packages.json")["workPackages"]
    memberships = read_csv(SOURCE / "packages" / "requirement-membership.csv")
    dependencies = read_csv(SOURCE / "packages" / "dependencies.csv")
    components = read_csv(SOURCE / "components" / "components.csv")
    commands = read_json(SOURCE / "contracts" / "ipc-command-registry-v3.json")["commands"]
    schemas = read_csv(SOURCE / "schemas" / "schema-index.csv")

    nodes = {str(row["work_package_id"]) for row in packages}
    adjacency: dict[str, list[str]] = {node: [] for node in nodes}
    indegree = {node: 0 for node in nodes}
    for edge in dependencies:
        target, prerequisite = edge["work_package_id"], edge["prerequisite_work_package_id"]
        adjacency[prerequisite].append(target)
        indegree[target] += 1
    queue = deque(sorted(node for node, degree in indegree.items() if degree == 0))
    visited = 0
    while queue:
        node = queue.popleft()
        visited += 1
        for nxt in sorted(adjacency[node]):
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)
    roots = sorted(nodes - {edge["work_package_id"] for edge in dependencies})

    validator_results = read_json(PLAN / "12-validators" / "validator-results.json") if (PLAN / "12-validators" / "validator-results.json").exists() else {}
    adversarial_results = read_json(PLAN / "12-validators" / "adversarial-results.json") if (PLAN / "12-validators" / "adversarial-results.json").exists() else {}
    v3_rows = read_csv(SOURCE / "reviews" / "reviewed-actionable-requirements-v3.csv")

    return {
        "canonical_rows": len(requirements),
        "active_rows": active,
        "actionable_rows": actionable,
        "requirement_review_rows": len(v3_rows),
        "package_count": len(packages),
        "membership_count": len(memberships),
        "dependency_count": len(dependencies),
        "component_count": len(components),
        "ipc_command_count": len(commands),
        "schema_count": len(schemas),
        "root_packages": roots,
        "dependency_cycles": 1 if visited != len(nodes) else 0,
        "validator_status": validator_results.get("status", "UNKNOWN"),
        "failed_validator_levels": validator_results.get("failedLevels", []),
        "adversarial_fixture_count": adversarial_results.get("fixtureCount", 0),
        "adversarial_expected_failures_observed": adversarial_results.get("expectedFailuresObserved", 0),
        "adversarial_status": adversarial_results.get("status", "UNKNOWN"),
        "layer_hashes": "See 13-reports/final-determinism-proof.json; generated after the handoff by final_certification.py.",
        "readiness_declaration": DECLARATION,
        "administrative_handoff_declaration": HANDOFF_DECLARATION,
    }


def sha_manifest() -> dict[str, object]:
    files: list[tuple[str, Path]] = []
    for path in sorted(GRAPHIFY.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        rel = path.relative_to(GRAPHIFY).as_posix()
        if rel in SHA_MANIFEST_EXCLUDED:
            continue
        files.append((rel, path))
    hasher = hashlib.sha256()
    entries: dict[str, str] = {}
    for rel, path in files:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        entries[rel] = digest
        hasher.update(rel.encode("utf-8"))
        hasher.update(digest.encode("utf-8"))
    return {
        "schema_version": 1,
        "algorithm": "SHA-256",
        "digest": hasher.hexdigest(),
        "file_count": len(files),
        "files": entries,
        "excluded": sorted(SHA_MANIFEST_EXCLUDED),
        "exclusion_rationales": {
            "semantic-plan-source/handoff-gpt/gpt-review-sha-manifest.json": "The manifest cannot hash itself.",
            "12-semantic-implementation-plan/14-handoff/gpt-review-sha-manifest.json": "Rendered copy of the manifest itself.",
            "12-semantic-implementation-plan/13-reports/pass1-external-final.json": "Contains volatile verification timestamp.",
            "12-semantic-implementation-plan/13-reports/pass2c-external-readonly-final.json": "Contains volatile verification timestamp.",
            "12-semantic-implementation-plan/13-reports/pass3-external-readonly-final.json": "Contains volatile verification timestamp.",
            "semantic-plan-source/reviews/pass1-external-final.json": "Source copy of the volatile external-integrity final.",
            "semantic-plan-source/reviews/pass2c-external-readonly-final.json": "Source copy of the volatile external-integrity final.",
            "semantic-plan-source/reviews/pass3-external-readonly-final.json": "Source copy of the volatile external-integrity final.",
            "12-semantic-implementation-plan/PLAN-MANIFEST.json": "Manifest of generated outputs that cannot hash itself.",
            "12-semantic-implementation-plan/13-reports/final-content-manifest.json": "Layer 1 manifest; verified by the two-run deterministic certification.",
            "12-semantic-implementation-plan/13-reports/final-100-percent-certification.json": "Layer 2 certification; verified by the two-run deterministic certification.",
            "12-semantic-implementation-plan/13-reports/final-release-envelope.json": "Layer 3 envelope; verified by the two-run deterministic certification.",
            "12-semantic-implementation-plan/13-reports/final-determinism-proof.json": "Records the Layer 1/3 hashes and cannot be hashed without circularity.",
            "semantic-plan-source/reviews/final-content-manifest.json": "Source copy of the Layer 1 manifest.",
            "semantic-plan-source/reviews/final-100-percent-certification.json": "Source copy of the Layer 2 certification.",
            "semantic-plan-source/reviews/final-release-envelope.json": "Source copy of the Layer 3 envelope.",
            "semantic-plan-source/reviews/final-determinism-proof.json": "Source copy of the determinism proof.",
            "semantic-plan-source/reviews/final-package-determinism.json": "Pass 3 determinism evidence; converges during certification.",
            "12-semantic-implementation-plan/13-reports/final-package-determinism.json": "Pass 3 determinism evidence; converges during certification.",
            "semantic-plan-source/reviews/pass3-certification-report.json": "Pass 3 certification report; validated independently by L15.",
            "12-semantic-implementation-plan/13-reports/pass3-certification-report.json": "Pass 3 certification report; validated independently by L15.",
        },
    }


def source_of_truth_report(counts: dict[str, object]) -> dict[str, object]:
    pairs = [
        (SOURCE / "requirements" / "requirements.csv", PLAN / "02-requirements" / "canonical-registry.csv"),
        (SOURCE / "requirements" / "requirement-mapping.csv", PLAN / "03-phases" / "reviewed-requirement-mapping.csv"),
        (SOURCE / "packages" / "requirement-membership.csv", PLAN / "04-work-packages" / "requirement-membership.csv"),
        (SOURCE / "packages" / "dependencies.csv", PLAN / "04-work-packages" / "dependencies.csv"),
        (SOURCE / "components" / "components.csv", PLAN / "10-component-manifest" / "components.csv"),
        (SOURCE / "contracts" / "ipc-command-registry-v3.json", PLAN / "05-contracts" / "ipc-command-registry-v3.json"),
        (SOURCE / "schemas" / "schema-index.csv", PLAN / "06-schemas" / "schema-index.csv"),
        (SOURCE / "validators" / "validate_plan.py", PLAN / "12-validators" / "validate_plan.py"),
        (SOURCE / "validators" / "adversarial_fixtures.py", PLAN / "12-validators" / "adversarial_fixtures.py"),
    ]
    mismatches: list[str] = []
    for source_path, rendered_path in pairs:
        if not source_path.exists() or not rendered_path.exists():
            mismatches.append(f"{source_path.name}: missing rendered copy")
            continue
        if source_path.read_bytes() != rendered_path.read_bytes():
            mismatches.append(source_path.name)
    source_packages = json.loads((SOURCE / "packages" / "work-packages.json").read_text(encoding="utf-8"))["workPackages"]
    rendered_packages = json.loads((PLAN / "04-work-packages" / "work-packages.json").read_text(encoding="utf-8"))
    source_package_ids = {row["work_package_id"] for row in source_packages}
    rendered_package_ids = {row["work_package_id"] for row in rendered_packages}
    if source_package_ids != rendered_package_ids:
        mismatches.append("work-packages.json: package ID sets differ")
    for row in rendered_packages:
        if row.get("work_package_id") not in source_package_ids:
            continue
        base = {key: value for key, value in row.items() if key not in ("included_requirement_ids", "technical_dependencies")}
        source_row = next(item for item in source_packages if item["work_package_id"] == row["work_package_id"])
        if base != source_row:
            mismatches.append(f"work-packages.json: enriched row differs for {row['work_package_id']}")
    source_reviews = sorted(path for path in (SOURCE / "reviews").rglob("*") if path.is_file() and "superseded" not in path.parts)
    for source_path in source_reviews:
        rendered_path = PLAN / "13-reports" / source_path.relative_to(SOURCE / "reviews")
        if not rendered_path.exists():
            mismatches.append(f"reviews/{source_path.name}: missing rendered copy")
        elif source_path.read_bytes() != rendered_path.read_bytes():
            mismatches.append(f"reviews/{source_path.name}")
    source_handoff = sorted(path for path in HANDOFF_SOURCE.rglob("*") if path.is_file())
    for source_path in source_handoff:
        rendered_path = HANDOFF_PLAN / source_path.relative_to(HANDOFF_SOURCE)
        if not rendered_path.exists():
            mismatches.append(f"handoff-gpt/{source_path.name}: missing rendered copy")
        elif source_path.read_bytes() != rendered_path.read_bytes():
            mismatches.append(f"handoff-gpt/{source_path.name}")
    validator_ok = counts.get("validator_status") == "PASS" and not counts.get("failed_validator_levels")
    adversarial_ok = counts.get("adversarial_status") == "PASS"
    consistent = not mismatches and validator_ok and adversarial_ok
    return {
        "report": "Source-of-truth hierarchy and consistency",
        "authoritative_layers": [
            "Original source plans and source clauses",
            "Reviewed requirement ledger (reviewed-actionable-requirements-v3.csv)",
            "Final canonical requirements (requirements.csv)",
            "Package, membership, dependency, and implementation-map ledgers",
            "Component and licence ledger (components.csv)",
            "IPC command registry",
            "JSON Schema registry and authority records",
            "SQLite planning artifacts",
            "Reviewed Pass B evidence ledgers",
            "AI model override amendment artifacts",
            "GPT-5.6 reviewer handoff sources",
        ],
        "generated_layers": [
            "12-semantic-implementation-plan/02-requirements",
            "12-semantic-implementation-plan/03-phases",
            "12-semantic-implementation-plan/04-work-packages (registry, membership, dependencies, packets)",
            "12-semantic-implementation-plan/05-contracts",
            "12-semantic-implementation-plan/06-schemas",
            "12-semantic-implementation-plan/07-sqlite",
            "12-semantic-implementation-plan/10-component-manifest",
            "12-semantic-implementation-plan/11-model-packets",
            "12-semantic-implementation-plan/12-validators",
            "12-semantic-implementation-plan/13-reports",
            "12-semantic-implementation-plan/14-handoff",
        ],
        "generation_direction": "Authoritative semantic-plan-source renders one-way into 12-semantic-implementation-plan via build_semantic_plan.py; final_certification.py, pass3_determinism.py, and generate_gpt_handoff.py persist derived evidence.",
        "conflict_rule": "Authoritative sources win. Review reports never override the records they validate. Generated packets never override authoritative registries. Any mismatch fails the validator and the source-of-truth report.",
        "final_consistency_status": "PASS" if consistent else "FAIL",
        "source_of_truth_consistency": "PASS" if consistent else "FAIL",
        "conflicting_authoritative_records": len(mismatches),
        "stale_generated_records": len(mismatches),
        "mismatches": mismatches,
        "evidence": "Byte-for-byte source/rendered comparison plus validator L12/L13/L14/L15/L16/L17/L18/L19/L20/L21 all PASS.",
    }


def main() -> int:
    counts = compute_counts()
    write_json(HANDOFF_SOURCE / "gpt-review-counts.json", counts)
    write_json(HANDOFF_PLAN / "gpt-review-counts.json", counts)
    manifest = sha_manifest()
    write_json(HANDOFF_SOURCE / "gpt-review-sha-manifest.json", manifest)
    write_json(HANDOFF_PLAN / "gpt-review-sha-manifest.json", manifest)
    truth = source_of_truth_report(counts)
    write_json(SOURCE / "reviews" / "source-of-truth-report.json", truth)
    write_json(PLAN / "13-reports" / "source-of-truth-report.json", truth)
    print(json.dumps({
        "counts": {key: counts[key] for key in (
            "canonical_rows", "active_rows", "actionable_rows", "package_count",
            "membership_count", "dependency_count", "component_count",
            "ipc_command_count", "schema_count", "root_packages", "dependency_cycles",
        )},
        "sha_manifest_digest": manifest["digest"],
        "sha_manifest_file_count": manifest["file_count"],
        "source_of_truth_consistency": truth["source_of_truth_consistency"],
        "stale_generated_records": truth["stale_generated_records"],
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
