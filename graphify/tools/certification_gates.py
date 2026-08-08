"""Shared read-only gate verification for the final planning certification.

These functions are used by:

* ``tools/final_certification.py`` -- the authoritative gated certification
  process (stage 1 pre-certification validation and the final certification
  validation stage).
* ``semantic-plan-source/validators/validate_plan.py`` -- L20, which
  independently re-verifies every final artifact from raw evidence and never
  trusts saved PASS text.
* ``semantic-plan-source/validators/adversarial_fixtures.py`` -- the negative
  fixtures that prove each final-certification weakness is rejected.

Every function in this module is read-only and deterministic.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


GRAPHIFY = Path(__file__).resolve().parents[1]
PLAN = GRAPHIFY / "12-semantic-implementation-plan"
SOURCE = GRAPHIFY / "semantic-plan-source"
REPORTS = PLAN / "13-reports"
VALIDATORS = PLAN / "12-validators"
HANDOFF_PLAN = PLAN / "14-handoff"
HANDOFF_SOURCE = SOURCE / "handoff-gpt"
REVIEWS = SOURCE / "reviews"

DECLARATION = "FULL IMPLEMENTATION PLANNING 100% COMPLETE \u2014 WP-I0-001 MAY BEGIN"
NOT_CERTIFIED_DECLARATION = "NOT CERTIFIED \u2014 IMPLEMENTATION BLOCKED"
GPT_FINAL_DECLARATION = "GPT-5.6 FINAL AUTHORITATIVE PLANNING REVIEW PASS — IMPLEMENTATION MAY BEGIN WITH WP-I0-001 ONLY"
PROVISIONAL_BLOCKER = "final certification validation has not completed"

# Gates that remain PENDING on a provisional certification written before the
# Stage 2 final certification validation has completed.
PROVISIONAL_PENDING_GATES = (
    "layer1_determinism",
    "layer3_determinism",
    "final_certification_validation",
)

# Rationales that do not explain why a specific path is excluded.
GENERIC_EXCLUSION_RATIONALE = re.compile(
    r"^(excluded|n/?a|none|no reason|generic|because|why|self[- ]referential|"
    r"volatile( timestamp)?|generated( output)?|cannot hash itself|"
    r"not applicable|unknown|see above|as above)$",
    re.I,
)

REQUIRED_VALIDATOR_LEVELS = [
    "L1_SOURCE_AND_WRITE_BOUNDARY",
    "L2_REQUIREMENT_SEMANTICS",
    "L2B_PASS1_SEMANTIC_REHABILITATION",
    "L3_EXPLICIT_SEMANTIC_MAPPING",
    "L4_WORK_PACKAGES",
    "L4B_PASS2_PACKAGE_SEMANTICS",
    "L4C_SEMANTIC_CAPABILITY_PHASE_CONSISTENCY",
    "L5_TECHNICAL_DAG",
    "L6_COMPONENT_DECISIONS",
    "L7_IPC_CONTRACTS",
    "L8_AUTHORITY_RECORDS_AND_SQLITE",
    "L9_AUDIT_AUTHENTICITY",
    "L10_METRICS_HONESTY",
    "L11_SCOPE_SAFETY",
    "L12_PACKETS_AND_HANDOFF",
    "L13_META_VALIDATION_EXECUTION",
    "L14_REVIEW_PROVENANCE",
    "L15_PERSISTED_READINESS",
    "L16_REQUIREMENT_LEDGER",
    "L17_PASS_B_LEDGER",
    "L18_PASS_B_ARCHITECTURE_COMPLETENESS",
    "L19_COMPONENT_AND_LICENCE_COMPLETENESS",
    "L20_FINAL_100_PERCENT_PLANNING_CERTIFICATION",
    "L21_AI_MODEL_OVERRIDE_AMENDMENT",
]

# Every required final input.  The minimum set mandated by the mission plus
# the relevant source-of-truth, external-integrity, and GPT-handoff reports
# and the active planning builders/certification tools.
REQUIRED_FILES = [
    # Rendered validation evidence.
    "12-semantic-implementation-plan/12-validators/validator-results.json",
    "12-semantic-implementation-plan/12-validators/adversarial-results.json",
    # Source-of-truth report (rendered and authoritative copies).
    "12-semantic-implementation-plan/13-reports/source-of-truth-report.json",
    "semantic-plan-source/reviews/source-of-truth-report.json",
    # Independent Pass B authenticity evidence.
    "12-semantic-implementation-plan/13-reports/pass-b-independent-evidence-authenticity.json",
    # External integrity evidence (final report and its baseline).
    "12-semantic-implementation-plan/13-reports/pass3-external-readonly-final.json",
    "12-semantic-implementation-plan/13-reports/pass3-external-readonly-baseline.json",
    "semantic-plan-source/reviews/pass3-external-readonly-final.json",
    "semantic-plan-source/reviews/pass3-external-readonly-baseline.json",
    "12-semantic-implementation-plan/13-reports/gpt-5.6-final-authoritative-review.json",
    "semantic-plan-source/reviews/gpt-5.6-final-authoritative-review.json",
    # Model packets and active handoff.
    "12-semantic-implementation-plan/11-model-packets/packet-manifest.json",
    "12-semantic-implementation-plan/14-handoff/START-HERE.md",
    # GPT reviewer handoff (rendered and authoritative copies).
    "12-semantic-implementation-plan/14-handoff/GPT-5.6-INDEPENDENT-REVIEW-HANDOFF.md",
    "12-semantic-implementation-plan/14-handoff/gpt-review-counts.json",
    "12-semantic-implementation-plan/14-handoff/gpt-review-critical-invariants.json",
    "12-semantic-implementation-plan/14-handoff/gpt-review-file-index.json",
    "12-semantic-implementation-plan/14-handoff/gpt-review-known-risk-areas.json",
    "12-semantic-implementation-plan/14-handoff/gpt-review-sha-manifest.json",
    "12-semantic-implementation-plan/14-handoff/gpt-review-validation-commands.json",
    "semantic-plan-source/handoff-gpt/GPT-5.6-INDEPENDENT-REVIEW-HANDOFF.md",
    "semantic-plan-source/handoff-gpt/gpt-review-counts.json",
    "semantic-plan-source/handoff-gpt/gpt-review-critical-invariants.json",
    "semantic-plan-source/handoff-gpt/gpt-review-file-index.json",
    "semantic-plan-source/handoff-gpt/gpt-review-known-risk-areas.json",
    "semantic-plan-source/handoff-gpt/gpt-review-sha-manifest.json",
    "semantic-plan-source/handoff-gpt/gpt-review-validation-commands.json",
    # Authoritative planning sources.
    "semantic-plan-source/requirements/requirements.csv",
    "semantic-plan-source/requirements/requirement-mapping.csv",
    "semantic-plan-source/packages/work-packages.json",
    "semantic-plan-source/packages/requirement-membership.csv",
    "semantic-plan-source/packages/dependencies.csv",
    "semantic-plan-source/components/components.csv",
    "semantic-plan-source/contracts/ipc-command-registry-v3.json",
    "semantic-plan-source/schemas/schema-index.csv",
    "semantic-plan-source/validators/validate_plan.py",
    "semantic-plan-source/validators/adversarial_fixtures.py",
    ".gitattributes",
    # Active planning builders, certification tools, and handoff generators.
    "build_semantic_plan.py",
    "tools/final_certification.py",
    "tools/certification_gates.py",
    "tools/simulate_provisional_certification.py",
    "tools/generate_gpt_handoff.py",
    "tools/pass3_external_integrity.py",
]

# Full-Graphify SHA manifest exclusions.  Shared with
# tools/generate_gpt_handoff.py so the generator and the certification
# verifier can never drift apart.
SHA_MANIFEST_EXCLUDED = frozenset({
    # The manifest itself (source and rendered copies).
    "semantic-plan-source/handoff-gpt/gpt-review-sha-manifest.json",
    "12-semantic-implementation-plan/14-handoff/gpt-review-sha-manifest.json",
    # Historical volatile timestamped external-integrity finals.
    "12-semantic-implementation-plan/13-reports/pass1-external-final.json",
    "12-semantic-implementation-plan/13-reports/pass2c-external-readonly-final.json",
    "semantic-plan-source/reviews/pass1-external-final.json",
    "semantic-plan-source/reviews/pass2c-external-readonly-final.json",
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
    # Regenerated validation evidence bound by Layer 3 and the certification's
    # required-file manifest instead of the full-tree manifest.
    "12-semantic-implementation-plan/12-validators/validator-results.json",
    "12-semantic-implementation-plan/12-validators/adversarial-results.json",
    "semantic-plan-source/validators/validator-results.json",
    "semantic-plan-source/validators/adversarial-results.json",
})

SHA_MANIFEST_EXCLUSION_RATIONALES = {
    "semantic-plan-source/handoff-gpt/gpt-review-sha-manifest.json": "The manifest cannot hash itself.",
    "12-semantic-implementation-plan/14-handoff/gpt-review-sha-manifest.json": "Rendered copy of the manifest itself.",
    "12-semantic-implementation-plan/13-reports/pass1-external-final.json": "Contains volatile verification timestamp.",
    "12-semantic-implementation-plan/13-reports/pass2c-external-readonly-final.json": "Contains volatile verification timestamp.",
    "semantic-plan-source/reviews/pass1-external-final.json": "Source copy of the volatile external-integrity final.",
    "semantic-plan-source/reviews/pass2c-external-readonly-final.json": "Source copy of the volatile external-integrity final.",
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
    "12-semantic-implementation-plan/12-validators/validator-results.json": "Regenerated by every validation pass; bound by Layer 3 and the certification required-file manifest.",
    "12-semantic-implementation-plan/12-validators/adversarial-results.json": "Regenerated by every validation pass; bound by Layer 3 and the certification required-file manifest.",
    "semantic-plan-source/validators/validator-results.json": "Source mirror of the regenerated validation evidence; bound by the rendered Layer 3 copy.",
    "semantic-plan-source/validators/adversarial-results.json": "Source mirror of the regenerated validation evidence; bound by the rendered Layer 3 copy.",
}

# Layer 1 (final-content-manifest.json) exclusions relative to PLAN.
LAYER1_EXCLUDED = frozenset({
    "PLAN-MANIFEST.json",
    "13-reports/final-content-manifest.json",
    "13-reports/final-100-percent-certification.json",
    "13-reports/final-release-envelope.json",
    "13-reports/final-determinism-proof.json",
    "13-reports/pass2c-external-readonly-final.json",
    "13-reports/pass1-external-final.json",
})

LAYER1_EXCLUSION_RATIONALES = {
    "PLAN-MANIFEST.json": "Manifest cannot hash itself.",
    "13-reports/final-content-manifest.json": "Layer 1 manifest cannot hash itself.",
    "13-reports/final-100-percent-certification.json": "Layer 2 certification report is hashed by Layer 3, not itself.",
    "13-reports/final-release-envelope.json": "Layer 3 envelope cannot hash itself.",
    "13-reports/final-determinism-proof.json": "Records the Layer 1/3 hashes and cannot be hashed without circularity; verified by the two in-memory runs.",
    "13-reports/pass2c-external-readonly-final.json": "Contains volatile verification timestamp.",
    "13-reports/pass1-external-final.json": "Contains volatile verification timestamp.",
}

# Layer 3 (final-release-envelope.json) membership.  Every listed file is
# actually hashed; a missing listed file fails certification.
LAYER3_FILES = [
    "12-semantic-implementation-plan/13-reports/final-content-manifest.json",
    "12-semantic-implementation-plan/13-reports/final-100-percent-certification.json",
    "12-semantic-implementation-plan/12-validators/validator-results.json",
    "12-semantic-implementation-plan/12-validators/adversarial-results.json",
    "12-semantic-implementation-plan/13-reports/pass-b-independent-evidence-authenticity.json",
    "12-semantic-implementation-plan/13-reports/source-of-truth-report.json",
    "12-semantic-implementation-plan/13-reports/pass3-external-readonly-baseline.json",
    "12-semantic-implementation-plan/13-reports/pass3-external-readonly-final.json",
    "12-semantic-implementation-plan/13-reports/gpt-5.6-final-authoritative-review.json",
    "12-semantic-implementation-plan/11-model-packets/packet-manifest.json",
    "12-semantic-implementation-plan/14-handoff/START-HERE.md",
    "12-semantic-implementation-plan/14-handoff/GPT-5.6-INDEPENDENT-REVIEW-HANDOFF.md",
    "12-semantic-implementation-plan/14-handoff/gpt-review-counts.json",
    "12-semantic-implementation-plan/14-handoff/gpt-review-critical-invariants.json",
    "12-semantic-implementation-plan/14-handoff/gpt-review-file-index.json",
    "12-semantic-implementation-plan/14-handoff/gpt-review-known-risk-areas.json",
    "12-semantic-implementation-plan/14-handoff/gpt-review-sha-manifest.json",
    "12-semantic-implementation-plan/14-handoff/gpt-review-validation-commands.json",
    "semantic-plan-source/handoff-gpt/gpt-review-sha-manifest.json",
    "semantic-plan-source/requirements/requirements.csv",
    "semantic-plan-source/requirements/requirement-mapping.csv",
    "semantic-plan-source/packages/work-packages.json",
    "semantic-plan-source/packages/requirement-membership.csv",
    "semantic-plan-source/packages/dependencies.csv",
    "semantic-plan-source/components/components.csv",
    "semantic-plan-source/contracts/ipc-command-registry-v3.json",
    "semantic-plan-source/schemas/schema-index.csv",
    "semantic-plan-source/validators/validate_plan.py",
    "semantic-plan-source/validators/adversarial_fixtures.py",
    "semantic-plan-source/reviews/source-of-truth-report.json",
    "semantic-plan-source/reviews/pass3-external-readonly-baseline.json",
    "semantic-plan-source/reviews/pass3-external-readonly-final.json",
    "semantic-plan-source/reviews/gpt-5.6-final-authoritative-review.json",
    ".gitattributes",
    "build_semantic_plan.py",
    "tools/final_certification.py",
    "tools/certification_gates.py",
    "tools/simulate_provisional_certification.py",
    "tools/generate_gpt_handoff.py",
    "tools/pass3_external_integrity.py",
]

LAYER3_EXCLUDED = frozenset({
    "12-semantic-implementation-plan/13-reports/final-release-envelope.json",
    "12-semantic-implementation-plan/13-reports/final-determinism-proof.json",
    "12-semantic-implementation-plan/13-reports/pass2c-external-readonly-final.json",
    "12-semantic-implementation-plan/13-reports/pass1-external-final.json",
})

LAYER3_EXCLUSION_RATIONALES = {
    "12-semantic-implementation-plan/13-reports/final-release-envelope.json": "Layer 3 envelope cannot hash itself.",
    "12-semantic-implementation-plan/13-reports/final-determinism-proof.json": "Records the Layer 3 digest and cannot be hashed without circularity; verified by the two in-memory runs and L20.",
    "12-semantic-implementation-plan/13-reports/pass2c-external-readonly-final.json": "Contains volatile verification timestamp.",
    "12-semantic-implementation-plan/13-reports/pass1-external-final.json": "Contains volatile verification timestamp.",
}

# Gates that must all be recorded as PASS before a PASS certification may be
# written or published.
CERTIFICATION_GATES = [
    "pre_certification_validator",
    "adversarial_fixtures",
    "required_files",
    "source_rendered_equality",
    "external_integrity",
    "full_graphify_manifest",
    "layer1_determinism",
    "layer3_determinism",
    "final_certification_validation",
]


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def compute_layer1(graphify_root: Path = GRAPHIFY) -> dict[str, object]:
    """Deterministic Layer 1 digest over the rendered plan tree."""
    plan = graphify_root / "12-semantic-implementation-plan"
    entries: list[tuple[str, Path]] = []
    for path in sorted(plan.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        rel = path.relative_to(plan).as_posix()
        if rel in LAYER1_EXCLUDED:
            continue
        entries.append((rel, path))
    hasher = hashlib.sha256()
    file_hashes: dict[str, str] = {}
    for rel, path in entries:
        digest = sha256_file(path)
        file_hashes[rel] = digest
        hasher.update(rel.encode("utf-8"))
        hasher.update(digest.encode("utf-8"))
    return {
        "sha256": hasher.hexdigest(),
        "fileCount": len(entries),
        "files": [rel for rel, _ in entries],
        "fileHashes": file_hashes,
    }


def compute_full_graphify_manifest(graphify_root: Path = GRAPHIFY) -> dict[str, object]:
    """Recompute the full-Graphify SHA manifest exactly as the generator does."""
    entries: list[tuple[str, Path]] = []
    for path in sorted(graphify_root.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        rel = path.relative_to(graphify_root).as_posix()
        if rel in SHA_MANIFEST_EXCLUDED:
            continue
        entries.append((rel, path))
    hasher = hashlib.sha256()
    file_hashes: dict[str, str] = {}
    for rel, path in entries:
        digest = sha256_file(path)
        file_hashes[rel] = digest
        hasher.update(rel.encode("utf-8"))
        hasher.update(digest.encode("utf-8"))
    return {
        "digest": hasher.hexdigest(),
        "file_count": len(entries),
        "files": file_hashes,
    }


def verify_saved_manifest_matches_recomputation(
    saved: Any,
    recomputed: dict[str, object],
) -> list[str]:
    errors: list[str] = []
    if not isinstance(saved, dict):
        return ["full Graphify SHA manifest is malformed"]
    if saved.get("digest") != recomputed.get("digest"):
        errors.append("full Graphify SHA manifest digest does not match recomputation")
    if saved.get("file_count") != recomputed.get("file_count"):
        errors.append("full Graphify SHA manifest file count does not match recomputation")
    if saved.get("files") != recomputed.get("files"):
        errors.append("full Graphify SHA manifest file hashes do not match recomputation")
    return errors


def verify_full_graphify_manifest(graphify_root: Path = GRAPHIFY) -> list[str]:
    errors: list[str] = []
    saved_paths = [
        graphify_root / "12-semantic-implementation-plan" / "14-handoff" / "gpt-review-sha-manifest.json",
        graphify_root / "semantic-plan-source" / "handoff-gpt" / "gpt-review-sha-manifest.json",
    ]
    for saved_path in saved_paths:
        if not saved_path.exists():
            errors.append(f"missing full Graphify SHA manifest: {saved_path.relative_to(graphify_root).as_posix()}")
    recomputed = compute_full_graphify_manifest(graphify_root)
    if saved_paths[0].exists():
        errors.extend(verify_saved_manifest_matches_recomputation(read_json(saved_paths[0]), recomputed))
        saved = read_json(saved_paths[0])
        errors.extend(
            verify_exact_exclusion_set(
                saved,
                "excluded",
                SHA_MANIFEST_EXCLUDED,
                "exclusion_rationales",
                "full_manifest",
            )
        )
    if saved_paths[0].exists() and saved_paths[1].exists():
        if saved_paths[0].read_bytes() != saved_paths[1].read_bytes():
            errors.append("full Graphify SHA manifest source/rendered copies differ")
    return errors


def verify_authoritative_source_coverage(graphify_root: Path = GRAPHIFY, entries: dict[str, str] | None = None) -> list[str]:
    if entries is None:
        entries = compute_full_graphify_manifest(graphify_root)["files"]
    errors: list[str] = []
    manifest_self_paths = {
        "semantic-plan-source/handoff-gpt/gpt-review-sha-manifest.json",
        "12-semantic-implementation-plan/14-handoff/gpt-review-sha-manifest.json",
    }
    for rel in REQUIRED_FILES:
        if rel in manifest_self_paths:
            # The full-Graphify manifest cannot hash itself; both copies are
            # bound by the Layer 3 envelope and the required-file manifest.
            continue
        if rel.startswith("semantic-plan-source/") or rel.startswith("tools/") or rel == "build_semantic_plan.py":
            if rel not in entries:
                errors.append(f"authoritative source not covered by full integrity manifest: {rel}")
    return errors


def verify_certification_tool_coverage(graphify_root: Path = GRAPHIFY, entries: dict[str, str] | None = None) -> list[str]:
    if entries is None:
        entries = compute_full_graphify_manifest(graphify_root)["files"]
    errors: list[str] = []
    for rel in (
        "tools/final_certification.py",
        "tools/certification_gates.py",
        "build_semantic_plan.py",
        "semantic-plan-source/validators/validate_plan.py",
        "semantic-plan-source/validators/adversarial_fixtures.py",
    ):
        if rel not in entries:
            errors.append(f"certification tool not covered by final integrity evidence: {rel}")
    return errors


def verify_validator_report(report: Any, require_l20_note: str | None = None) -> list[str]:
    errors: list[str] = []
    if not isinstance(report, dict):
        return ["validator report is malformed"]
    if report.get("status") != "PASS":
        errors.append("validator status is not PASS")
    levels = report.get("levels")
    if not isinstance(levels, list):
        errors.append("validator report has no levels list")
        return errors
    if report.get("levelCount") != len(levels):
        errors.append(f"validator levelCount mismatch: {report.get('levelCount')} != {len(levels)}")
    seen = Counter(
        level.get("level") for level in levels if isinstance(level, dict)
    )
    for name in REQUIRED_VALIDATOR_LEVELS:
        count = seen.get(name, 0)
        if count == 0:
            errors.append(f"validator missing level: {name}")
        elif count > 1:
            errors.append(f"validator duplicate level: {name}")
    for level in levels:
        if not isinstance(level, dict):
            errors.append("validator level entry is malformed")
            continue
        if level.get("status") != "PASS":
            errors.append(f"validator level not PASS: {level.get('level')}")
        if level.get("errors"):
            errors.append(f"validator level has errors: {level.get('level')}")
    failed = report.get("failedLevels")
    if isinstance(failed, list) and failed:
        errors.append("validator failedLevels is not empty")
    if require_l20_note is not None:
        l20 = next(
            (level for level in levels if isinstance(level, dict) and level.get("level") == "L20_FINAL_100_PERCENT_PLANNING_CERTIFICATION"),
            None,
        )
        if not isinstance(l20, dict):
            errors.append("validator report missing L20 level")
        elif l20.get("note") != require_l20_note:
            errors.append(f"validator L20 state note mismatch: expected {require_l20_note}")
    return errors


def verify_adversarial_report(report: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(report, dict):
        return ["adversarial report is malformed"]
    if report.get("status") != "PASS":
        errors.append("adversarial status is not PASS")
    count = report.get("fixtureCount")
    observed = report.get("expectedFailuresObserved")
    fixtures = report.get("fixtures")
    if not isinstance(count, int) or count <= 0:
        errors.append("adversarial fixtureCount is not a positive integer")
    if not isinstance(fixtures, list):
        errors.append("adversarial report has no fixtures list")
        return errors
    if isinstance(count, int) and count != len(fixtures):
        errors.append(f"adversarial fixtureCount mismatch: {count} != {len(fixtures)}")
    if observed != count:
        errors.append(f"adversarial expectedFailuresObserved mismatch: {observed} != {count}")
    names: list[str] = []
    for fixture in fixtures:
        if not isinstance(fixture, dict):
            errors.append("adversarial fixture entry is malformed")
            continue
        if fixture.get("status") != "EXPECTED_FAILURE_OBSERVED":
            errors.append(f"adversarial fixture did not observe expected failure: {fixture.get('fixture')}")
        if not fixture.get("validatorErrors"):
            errors.append(f"adversarial fixture has no validator errors: {fixture.get('fixture')}")
        names.append(fixture.get("fixture", ""))
    for duplicate in sorted({name for name in names if names.count(name) > 1}):
        errors.append(f"adversarial fixture name duplicated: {duplicate}")
    return errors


EXTERNAL_INTEGRITY_ALGORITHM = "Git blob object identity and canonical blob size"


def verify_external_integrity_file_rows(rows: Any, label: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(rows, list):
        return [f"external integrity {label} files list missing"]
    paths: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            errors.append(f"external integrity {label} file row is malformed")
            continue
        path = row.get("path")
        if not isinstance(path, str) or not path or path.startswith("graphify/"):
            errors.append(f"external integrity {label} file path is invalid")
        else:
            paths.append(path)
        oid = row.get("gitBlobOid")
        if not isinstance(oid, str) or re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", oid) is None:
            errors.append(f"external integrity {label} Git blob identity is invalid: {path}")
        if not isinstance(row.get("mode"), str) or re.fullmatch(r"[0-7]{6}", row.get("mode", "")) is None:
            errors.append(f"external integrity {label} Git mode is invalid: {path}")
        if not isinstance(row.get("size"), int) or int(row.get("size", -1)) < 0:
            errors.append(f"external integrity {label} canonical blob size is invalid: {path}")
        if "sha256" in row:
            errors.append(f"external integrity {label} uses checkout-byte SHA-256: {path}")
    if len(paths) != len(set(paths)):
        errors.append(f"external integrity {label} contains duplicate paths")
    if paths != sorted(paths):
        errors.append(f"external integrity {label} paths are not deterministically ordered")
    return errors


def verify_external_integrity_baseline(baseline: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(baseline, dict):
        return ["external integrity baseline report is malformed"]
    if baseline.get("schema_version") != 2:
        errors.append("external integrity baseline schema is not checkout-independent v2")
    if baseline.get("algorithm") != EXTERNAL_INTEGRITY_ALGORITHM:
        errors.append("external integrity baseline is checkout-byte-dependent")
    if "verifiedAt" in baseline:
        errors.append("external integrity baseline contains volatile timestamp")
    if baseline.get("project_root") != "." or baseline.get("graphify_root") != "graphify":
        errors.append("external integrity baseline contains checkout-specific root")
    files = baseline.get("files")
    errors.extend(verify_external_integrity_file_rows(files, "baseline"))
    if isinstance(files, list):
        if baseline.get("file_count") != len(files):
            errors.append("external integrity baseline file count mismatch")
        expected_bytes = sum(int(row.get("size", 0)) for row in files if isinstance(row, dict))
        if baseline.get("byte_count") != expected_bytes:
            errors.append("external integrity baseline canonical byte count mismatch")
    return errors


def verify_external_integrity_comparison(final: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(final, dict):
        return ["external integrity report is malformed"]
    if "verifiedAt" in final:
        errors.append("external integrity report contains volatile timestamp")
    if final.get("schemaVersion") != "2.0":
        errors.append("external integrity final schema is not checkout-independent v2")
    if final.get("algorithm") != EXTERNAL_INTEGRITY_ALGORITHM:
        errors.append("external integrity final is checkout-byte-dependent")
    if final.get("lamhaRoot") != "." or final.get("graphifyRoot") != "graphify":
        errors.append("external integrity report contains checkout-specific root")
    files = final.get("files")
    errors.extend(verify_external_integrity_file_rows(files, "final"))
    if isinstance(files, list):
        if final.get("fileCount") != len(files):
            errors.append("external integrity file count mismatch")
        expected_bytes = sum(int(row.get("size", 0)) for row in files if isinstance(row, dict))
        if final.get("byteCount") != expected_bytes:
            errors.append("external integrity final canonical byte count mismatch")
    comparison = final.get("comparison")
    if not isinstance(comparison, dict):
        errors.append("external integrity comparison field missing")
        return errors
    if comparison.get("status") != "PASS":
        errors.append("external integrity status is not PASS")
    for key in ("added", "removed", "modified", "renamed"):
        value = comparison.get(key)
        if not isinstance(value, list):
            errors.append(f"external integrity {key} field missing")
        elif value:
            errors.append(f"external integrity {key} is not zero")
    return errors


def verify_external_integrity_report(graphify_root: Path = GRAPHIFY) -> list[str]:
    errors: list[str] = []
    final_path = graphify_root / "12-semantic-implementation-plan" / "13-reports" / "pass3-external-readonly-final.json"
    baseline_path = graphify_root / "12-semantic-implementation-plan" / "13-reports" / "pass3-external-readonly-baseline.json"
    if not final_path.exists():
        return ["external integrity final report missing"]
    if not baseline_path.exists():
        errors.append("external integrity baseline report missing")
    final = read_json(final_path)
    errors.extend(verify_external_integrity_comparison(final))
    files = final.get("files")
    if baseline_path.exists():
        baseline = read_json(baseline_path)
        errors.extend(verify_external_integrity_baseline(baseline))
        if isinstance(files, list) and baseline.get("file_count") != final.get("fileCount"):
            errors.append("external integrity baseline/final scope counts differ")
        base_paths = {row.get("path") for row in (baseline.get("files") or []) if isinstance(row, dict)}
        final_paths = {row.get("path") for row in (files or []) if isinstance(row, dict)}
        if base_paths and final_paths and base_paths != final_paths:
            errors.append("external integrity baseline/final scopes differ")
        if baseline.get("files") != files:
            errors.append("external integrity baseline/final canonical Git trees differ")
        baseline_reference = final.get("baselinePath")
        if baseline_reference and not (graphify_root / str(baseline_reference)).exists():
            errors.append("external integrity baseline path does not resolve")
    return errors


def verify_line_ending_policy(graphify_root: Path = GRAPHIFY) -> list[str]:
    path = graphify_root / ".gitattributes"
    if not path.exists():
        return ["Graphify line-ending policy missing"]
    lines = {
        line.strip() for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    required = {
        ".gitattributes text eol=lf",
        "*.csv text eol=lf", "*.html text eol=lf", "*.json text eol=lf",
        "*.jsonl text eol=lf", "*.md text eol=lf", "*.py text eol=lf",
        "*.sql text eol=lf", "*.txt text eol=lf", "graphify-run-log.txt -text",
    }
    errors = [f"Graphify LF rule missing: {rule}" for rule in sorted(required - lines)]
    if any(line.startswith("../") or "Codebase" in line for line in lines):
        errors.append("Graphify line-ending policy escapes planning scope")
    return errors


def verify_final_gpt_review(graphify_root: Path = GRAPHIFY) -> list[str]:
    path = graphify_root / "semantic-plan-source" / "reviews" / "gpt-5.6-final-authoritative-review.json"
    if not path.exists():
        return ["GPT-5.6 final authoritative review evidence missing"]
    record = read_json(path)
    requirements = read_csv(graphify_root / "semantic-plan-source" / "requirements" / "requirements.csv")
    memberships = read_csv(graphify_root / "semantic-plan-source" / "packages" / "requirement-membership.csv")
    dependencies = read_csv(graphify_root / "semantic-plan-source" / "packages" / "dependencies.csv")
    packages = read_json(graphify_root / "semantic-plan-source" / "packages" / "work-packages.json")["workPackages"]
    components = read_csv(graphify_root / "semantic-plan-source" / "components" / "components.csv")
    commands = read_json(graphify_root / "semantic-plan-source" / "contracts" / "ipc-command-registry-v3.json")["commands"]
    schemas = read_csv(graphify_root / "semantic-plan-source" / "schemas" / "schema-index.csv")
    active = [row for row in requirements if row.get("supersession_status") == "ACTIVE"]
    expected = {
        "canonical_requirements": len(requirements), "active_requirements": len(active),
        "actionable_requirements": len(memberships), "independently_reviewed_actionable": len(memberships),
        "work_packages": len(packages), "memberships": len(memberships), "dependencies": len(dependencies),
        "components": len(components), "ipc_commands": len(commands), "schemas": len(schemas),
    }
    errors: list[str] = []
    if record.get("reviewed_counts") != expected:
        errors.append("GPT-5.6 final review counts disagree with raw authority")
    if record.get("administrative_declaration") != GPT_FINAL_DECLARATION:
        errors.append("GPT-5.6 final administrative declaration missing")
    if record.get("remaining_blockers") != []:
        errors.append("GPT-5.6 final review has remaining blockers")
    if record.get("wp_i0_001_status") != "NOT_STARTED" or record.get("automatic_next_package") is not None:
        errors.append("GPT-5.6 final review authorization state is unsafe")
    if not record.get("defects_found") or int(record.get("defects_fixed", -1)) <= 0:
        errors.append("GPT-5.6 final review lacks independent defect evidence")
    ending = record.get("ending_sha")
    if not isinstance(ending, dict) or ending.get("status") != "RESOLVED_BY_GITHUB_SYNC":
        errors.append("GPT-5.6 final review ending-SHA handling is missing or misleading")
    return errors


def verify_authority_graph(graphify_root: Path = GRAPHIFY) -> list[str]:
    path = graphify_root / "semantic-plan-source" / "reviews" / "source-of-truth-report.json"
    if not path.exists():
        return ["source-of-truth authority graph missing"]
    report = read_json(path)
    zeroes = {
        "unknown_authority_files": 0, "generated_files_without_source": 0,
        "generated_files_without_generator": 0, "circular_authority_relationships": 0,
        "generated_artifacts_used_as_their_own_authority": 0,
    }
    errors: list[str] = []
    if report.get("authority_invariants") != zeroes:
        errors.append("source-of-truth authority invariants are incomplete or nonzero")
    domains = {row.get("domain") for row in report.get("authority_graph", []) if isinstance(row, dict)}
    expected = {
        "Master Plan", "canonical requirements", "requirement mappings and reviews",
        "packages, memberships, dependencies", "components and licences", "IPC contracts",
        "schemas and SQLite", "AI amendment", "validators and fixtures", "certification, reports, and handoff",
    }
    if domains != expected:
        errors.append("source-of-truth authority domain coverage differs from the canonical set")
    for row in report.get("authority_graph", []):
        if isinstance(row, dict) and any(not row.get(field) for field in ("source", "generated", "generator", "validator", "derivation")):
            errors.append(f"source-of-truth authority mapping incomplete: {row.get('domain')}")
    return errors


def source_rendered_pairs(graphify_root: Path = GRAPHIFY) -> list[tuple[Path, Path, str]]:
    source = graphify_root / "semantic-plan-source"
    plan = graphify_root / "12-semantic-implementation-plan"
    pairs: list[tuple[Path, Path, str]] = [
        (source / "requirements" / "requirements.csv", plan / "02-requirements" / "canonical-registry.csv", "requirements.csv"),
        (source / "requirements" / "requirement-mapping.csv", plan / "03-phases" / "reviewed-requirement-mapping.csv", "requirement-mapping.csv"),
        (source / "packages" / "requirement-membership.csv", plan / "04-work-packages" / "requirement-membership.csv", "requirement-membership.csv"),
        (source / "packages" / "dependencies.csv", plan / "04-work-packages" / "dependencies.csv", "dependencies.csv"),
        (source / "components" / "components.csv", plan / "10-component-manifest" / "components.csv", "components.csv"),
        (source / "contracts" / "ipc-command-registry-v3.json", plan / "05-contracts" / "ipc-command-registry-v3.json", "ipc-command-registry-v3.json"),
        (source / "schemas" / "schema-index.csv", plan / "06-schemas" / "schema-index.csv", "schema-index.csv"),
        (source / "validators" / "validate_plan.py", plan / "12-validators" / "validate_plan.py", "validate_plan.py"),
        (source / "validators" / "adversarial_fixtures.py", plan / "12-validators" / "adversarial_fixtures.py", "adversarial_fixtures.py"),
        (source / "reviews" / "source-of-truth-report.json", plan / "13-reports" / "source-of-truth-report.json", "source-of-truth-report.json"),
    ]
    for source_path in sorted((source / "reviews").rglob("*")):
        if source_path.is_file() and "superseded" not in source_path.parts:
            rel = source_path.relative_to(source / "reviews")
            pairs.append((source_path, plan / "13-reports" / rel, f"reviews/{rel.as_posix()}"))
    for source_path in sorted((source / "handoff-gpt").rglob("*")):
        if source_path.is_file():
            rel = source_path.relative_to(source / "handoff-gpt")
            pairs.append((source_path, plan / "14-handoff" / rel, f"handoff-gpt/{rel.as_posix()}"))
    return pairs


def verify_source_rendered_pairs(pairs: list[tuple[Path, Path, str]]) -> list[str]:
    mismatches: list[str] = []
    for source_path, rendered_path, label in pairs:
        if not source_path.exists() or not rendered_path.exists():
            mismatches.append(f"{label}: missing rendered copy")
            continue
        try:
            if source_path.read_bytes() != rendered_path.read_bytes():
                mismatches.append(f"{label}: source/rendered bytes differ")
        except OSError as error:
            mismatches.append(f"{label}: unreadable ({error})")
    return mismatches


def verify_work_package_semantic_agreement(graphify_root: Path = GRAPHIFY) -> list[str]:
    mismatches: list[str] = []
    source_path = graphify_root / "semantic-plan-source" / "packages" / "work-packages.json"
    rendered_path = graphify_root / "12-semantic-implementation-plan" / "04-work-packages" / "work-packages.json"
    if not source_path.exists() or not rendered_path.exists():
        return ["work-packages.json: missing source or rendered copy"]
    source_packages = read_json(source_path)["workPackages"]
    rendered_packages = read_json(rendered_path)
    source_ids = {str(row["work_package_id"]) for row in source_packages}
    rendered_ids = {str(row["work_package_id"]) for row in rendered_packages}
    if source_ids != rendered_ids:
        mismatches.append("work-packages.json: package ID sets differ")
    for row in rendered_packages:
        pid = str(row.get("work_package_id"))
        if pid not in source_ids:
            continue
        base = {key: value for key, value in row.items() if key not in ("included_requirement_ids", "technical_dependencies")}
        source_row = next(item for item in source_packages if str(item["work_package_id"]) == pid)
        if base != source_row:
            mismatches.append(f"work-packages.json: enriched row differs for {pid}")
    return mismatches


def verify_packet_semantic_agreement(graphify_root: Path = GRAPHIFY) -> list[str]:
    mismatches: list[str] = []
    source = graphify_root / "semantic-plan-source"
    plan = graphify_root / "12-semantic-implementation-plan"
    manifest_path = plan / "11-model-packets" / "packet-manifest.json"
    if manifest_path.exists():
        manifest = read_json(manifest_path)
        for row in manifest.get("packets", []):
            packet_path = plan / str(row.get("path", ""))
            if not packet_path.exists():
                mismatches.append(f"packet missing: {row.get('path')}")
    packages_path = source / "packages" / "work-packages.json"
    membership_path = source / "packages" / "requirement-membership.csv"
    dependencies_path = source / "packages" / "dependencies.csv"
    requirements_path = source / "requirements" / "requirements.csv"
    commands_path = source / "contracts" / "ipc-command-registry-v3.json"
    if packages_path.exists() and membership_path.exists() and dependencies_path.exists() and requirements_path.exists() and commands_path.exists():
        packages = read_json(packages_path)["workPackages"]
        memberships = read_csv(membership_path)
        requirements = {row["canonical_id"]: row for row in read_csv(requirements_path)}
        dependencies = read_csv(dependencies_path)
        commands = read_json(commands_path)["commands"]
        member_by_package: defaultdict[str, list[str]] = defaultdict(list)
        for row in memberships:
            member_by_package[row["work_package_id"]].append(row["canonical_id"])
        for package in packages:
            pid = str(package["work_package_id"])
            packet = plan / "04-work-packages" / "packets" / f"{pid}.md"
            if not packet.exists():
                mismatches.append(f"packet missing for package: {pid}")
                continue
            requirement_ids = sorted(member_by_package.get(pid, []))
            req_lines = [
                f"- `{rid}` — {requirements[rid]['statement']} (source: {requirements[rid]['source_plan']} / {requirements[rid]['source_locator']})"
                for rid in requirement_ids
            ]
            prereqs = sorted(
                (row for row in dependencies if row["work_package_id"] == pid),
                key=lambda row: (row["prerequisite_work_package_id"], row["dependency_type"]),
            )
            dep_lines = [
                f"- `{row['prerequisite_work_package_id']}` via `{row['dependency_type']}` — {row['technical_rationale']}"
                for row in prereqs
            ] or ["- None."]
            dependent_ids = sorted({
                row["work_package_id"] for row in dependencies
                if row["prerequisite_work_package_id"] == pid
            })
            command_ids = sorted(str(row["commandId"]) for row in commands if row.get("workPackageId") == pid)
            expected = f"""# {pid} — {package['name']}

Canonical source: `semantic-plan-source/packages/work-packages.json` plus the reviewed membership and dependency registries.

## Execution boundary

- Phase: `{package['implementation_phase']}`
- Objective: {package['objective']}
- Bounded surface: {package['bounded_surface']}
- Explicit exclusions: {package['explicit_exclusions']}
- Commit boundary: {package['commit_boundary']}

## Canonical requirements ({len(requirement_ids)})

{chr(10).join(req_lines)}

## Technical prerequisites

{chr(10).join(dep_lines)}

## Direct dependents

{', '.join(f'`{value}`' for value in dependent_ids) if dependent_ids else 'None.'}

## Contracts and schemas

- IPC commands: {', '.join(f'`{value}`' for value in command_ids) if command_ids else 'None verified for this package.'}
- Contracts affected: {package['contracts_affected']}
- Schemas affected: {package['schemas_affected']}

## Delivery and proof

- Deliverables: {package['deliverables']}
- Tests: {package['tests']}
- Failure cases: {package['failure_cases']}
- Rollback/recovery: {package['rollback_or_recovery']}
- Completion evidence: {package['completion_evidence']}
- Exit gate: {package['exit_gate']}

Execute only this bounded package. Do not start a dependent package until its technical prerequisites and exit gate are proven.
"""
            if packet.read_text(encoding="utf-8") != expected:
                mismatches.append(f"packet exact rendering differs from authority: {pid}")
    if dependencies_path.exists():
        edges = read_csv(dependencies_path)
        dependents_by_package: defaultdict[str, list[str]] = defaultdict(list)
        for edge in edges:
            dependents_by_package[edge["prerequisite_work_package_id"]].append(edge["work_package_id"])
        for pid, dependents in dependents_by_package.items():
            packet = plan / "04-work-packages" / "packets" / f"{pid}.md"
            if not packet.exists():
                continue
            text = packet.read_text(encoding="utf-8")
            section = text.split("## Direct dependents", 1)[1] if "## Direct dependents" in text else ""
            section = section.split("\n## ", 1)[0]
            for target in dependents:
                if f"`{target}`" not in section:
                    mismatches.append(f"packet direct dependents stale: {target} missing from {pid} packet")
    return mismatches


def compute_source_rendered_mismatches(graphify_root: Path = GRAPHIFY) -> list[str]:
    return (
        verify_source_rendered_pairs(source_rendered_pairs(graphify_root))
        + verify_work_package_semantic_agreement(graphify_root)
        + verify_packet_semantic_agreement(graphify_root)
    )


def compute_required_file_evidence(graphify_root: Path = GRAPHIFY) -> dict[str, object]:
    missing: list[str] = []
    unreadable: list[str] = []
    hashes: dict[str, str] = {}
    for rel in REQUIRED_FILES:
        path = graphify_root / rel
        if not path.exists():
            missing.append(rel)
            continue
        try:
            hashes[rel] = sha256_file(path)
        except OSError:
            unreadable.append(rel)
    return {
        "missingFiles": sorted(missing),
        "unreadableFiles": sorted(unreadable),
        "hashes": {rel: hashes[rel] for rel in sorted(hashes)},
    }


def verify_required_files(graphify_root: Path = GRAPHIFY) -> list[str]:
    evidence = compute_required_file_evidence(graphify_root)
    errors = [f"missing required file: {rel}" for rel in evidence["missingFiles"]]
    errors += [f"unreadable required file: {rel}" for rel in evidence["unreadableFiles"]]
    return errors


def compute_layer3(
    graphify_root: Path = GRAPHIFY,
    rels: list[str] | None = None,
    overrides: dict[str, bytes] | None = None,
) -> dict[str, object]:
    """Deterministic Layer 3 digest over the canonical membership.

    ``overrides`` maps canonical relative paths to the exact bytes that will be
    published, so the final publication can compute the envelope digest over
    in-memory final artifacts before anything is atomically replaced.
    """
    selected = sorted(rels or LAYER3_FILES)
    overrides = overrides or {}
    hasher = hashlib.sha256()
    file_hashes: dict[str, str] = {}
    missing: list[str] = []
    unreadable: list[str] = []
    for rel in selected:
        if rel in overrides:
            digest = sha256_bytes(overrides[rel])
        else:
            path = graphify_root / rel
            if not path.exists():
                missing.append(rel)
                continue
            try:
                digest = sha256_file(path)
            except OSError:
                unreadable.append(rel)
                continue
        file_hashes[rel] = digest
        hasher.update(rel.encode("utf-8"))
        hasher.update(digest.encode("utf-8"))
    return {
        "sha256": hasher.hexdigest(),
        "fileCount": len(file_hashes),
        "files": selected,
        "fileHashes": file_hashes,
        "missingFiles": sorted(missing),
        "unreadableFiles": sorted(unreadable),
        "unexpectedFiles": sorted(set(selected) - set(LAYER3_FILES)),
    }


def verify_layer3_membership(envelope: Any) -> list[str]:
    """Exact Layer 3 membership contract, independent of the on-disk tree.

    Requires ``files == sorted(LAYER3_FILES)``, exact ``fileHashes`` keys, and
    the canonical count, so a self-consistent smaller envelope can never pass.
    """
    errors: list[str] = []
    if not isinstance(envelope, dict):
        return ["layer 3 envelope is malformed"]
    listed = envelope.get("files")
    if not isinstance(listed, list):
        errors.append("layer3_file_membership_mismatch: layer 3 envelope files list missing")
        listed = []
    else:
        canonical = set(LAYER3_FILES)
        if set(listed) != canonical:
            for rel in sorted(canonical - set(listed)):
                errors.append(f"layer3_canonical_member_missing: {rel}")
            for rel in sorted(set(listed) - canonical):
                errors.append(f"layer3_unexpected_member: {rel}")
        if listed != sorted(LAYER3_FILES):
            errors.append("layer3_file_order_mismatch: envelope files are not canonical deterministic sorted order")
    file_hashes = envelope.get("fileHashes")
    if not isinstance(file_hashes, dict):
        errors.append("layer3_file_hash_membership_mismatch: layer 3 envelope per-file hashes missing")
        file_hashes = {}
    else:
        if set(file_hashes.keys()) != set(LAYER3_FILES):
            errors.append("layer3_file_hash_membership_mismatch: fileHashes keys differ from canonical Layer 3 files")
        if isinstance(listed, list) and set(listed) != set(file_hashes.keys()):
            errors.append("layer3_file_hash_membership_mismatch: files and fileHashes keys differ")
    if envelope.get("fileCount") != len(LAYER3_FILES):
        errors.append(
            f"layer3_file_count_mismatch: envelope fileCount {envelope.get('fileCount')} "
            f"!= canonical {len(LAYER3_FILES)}"
        )
    return errors


def verify_layer3_envelope(graphify_root: Path, envelope: Any) -> list[str]:
    """Full Layer 3 verification over the canonical membership and the tree."""
    errors: list[str] = verify_layer3_membership(envelope)
    if not isinstance(envelope, dict):
        return errors
    listed = envelope.get("files")
    file_hashes = envelope.get("fileHashes")
    if not isinstance(listed, list):
        listed = []
    if not isinstance(file_hashes, dict):
        file_hashes = {}
    for rel in listed:
        path = graphify_root / rel
        if not path.exists():
            errors.append(f"layer 3 listed file missing: {rel}")
            continue
        try:
            sha256_file(path)
        except OSError:
            errors.append(f"layer 3 listed file unreadable: {rel}")
    hasher = hashlib.sha256()
    hashed: list[str] = []
    for rel in sorted(LAYER3_FILES):
        path = graphify_root / rel
        if not path.exists():
            errors.append(f"layer 3 listed file missing: {rel}")
            continue
        try:
            digest = sha256_file(path)
        except OSError:
            errors.append(f"layer 3 listed file unreadable: {rel}")
            continue
        if rel in file_hashes and file_hashes.get(rel) != digest:
            errors.append(f"layer 3 listed file hash mismatch: {rel}")
        hasher.update(rel.encode("utf-8"))
        hasher.update(digest.encode("utf-8"))
        hashed.append(rel)
    for rel in LAYER3_FILES:
        if rel not in file_hashes:
            errors.append(f"layer 3 canonical file not hashed: {rel}")
        if rel not in hashed:
            errors.append(f"layer 3 canonical file missing from digest: {rel}")
    if envelope.get("sha256") != hasher.hexdigest():
        errors.append("layer 3 envelope digest does not match recomputation")
    return errors


def verify_cert_hash_agreements(cert: Any, manifest: Any, envelope: Any, proof: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(cert, dict) or not isinstance(manifest, dict) or not isinstance(envelope, dict) or not isinstance(proof, dict):
        return ["certification hash agreement evidence is malformed"]
    if cert.get("layer1Hash") != manifest.get("sha256"):
        errors.append("certification layer1 hash differs from content manifest")
    if proof.get("layer1FirstHash") != proof.get("layer1SecondHash"):
        errors.append("layer 1 hashes differ between certification runs")
    if proof.get("layer1FirstHash") != manifest.get("sha256"):
        errors.append("proof layer1 hash differs from content manifest")
    if proof.get("layer3FirstHash") != proof.get("layer3SecondHash"):
        errors.append("layer 3 hashes differ between certification runs")
    if proof.get("layer3FirstHash") != envelope.get("sha256"):
        errors.append("proof layer3 hash differs from release envelope")
    return errors


def verify_exclusion_rationales(record: Any, excluded_key: str, rationale_key: str) -> list[str]:
    """Strict exclusion-rationale verification.

    A missing/malformed ``excluded`` field, a missing rationale, an empty
    rationale, or a generic non-specific rationale is an error.
    """
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["exclusion evidence is malformed"]
    excluded = record.get(excluded_key)
    if not isinstance(excluded, list):
        errors.append(f"{excluded_key} exclusion set missing or wrong type")
        excluded = []
    rationales = record.get(rationale_key)
    if not isinstance(rationales, dict):
        errors.append(f"{rationale_key} exclusion rationales missing or wrong type")
        rationales = {}
    for rel in excluded:
        rationale = rationales.get(rel)
        if not isinstance(rationale, str) or not rationale.strip():
            errors.append(f"exclusion_rationale_missing: {rel}")
        elif len(rationale.strip()) < 10 or GENERIC_EXCLUSION_RATIONALE.match(rationale.strip()):
            errors.append(f"exclusion_rationale_not_specific: {rel}")
    return errors


def verify_exact_exclusion_set(
    record: Any,
    excluded_key: str,
    canonical: frozenset[str],
    rationale_key: str,
    label: str,
) -> list[str]:
    """Require the exact canonical exclusion set plus strict rationales."""
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["exclusion evidence is malformed"]
    excluded = record.get(excluded_key)
    if not isinstance(excluded, list):
        errors.append(f"{label}_exclusion_set_mismatch: {excluded_key} missing or wrong type")
        return errors
    actual = set(excluded)
    for rel in sorted(canonical - actual):
        errors.append(f"{label}_exclusion_set_mismatch: missing {rel}")
    for rel in sorted(actual - canonical):
        errors.append(f"{label}_exclusion_set_mismatch: unexpected {rel}")
    errors.extend(verify_exclusion_rationales(record, excluded_key, rationale_key))
    return errors


def verify_certification_gates_recorded(cert: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(cert, dict):
        return ["certification record is malformed"]
    gates = cert.get("certificationGates")
    if not isinstance(gates, dict):
        return ["certification gates record missing"]
    for gate in CERTIFICATION_GATES:
        if gates.get(gate) != "PASS":
            errors.append(f"certification gate not completed: {gate}")
    return errors


def verify_certificate_gate_states(cert: Any) -> list[str]:
    """Verify recorded certification gates reflect the actual execution state.

    A PASS certificate must have every gate PASS.  A provisional certificate
    (written before the Stage 2 final certification validation completes) must
    have the six pre-certification gates PASS and the determinism and final
    validation gates PENDING.  Unknown gates are rejected.
    """
    errors: list[str] = []
    if not isinstance(cert, dict):
        return ["certification record is malformed"]
    gates = cert.get("certificationGates")
    if not isinstance(gates, dict):
        return ["certification gates record missing"]
    for gate in gates:
        if gate not in CERTIFICATION_GATES:
            errors.append(f"certification gate unknown: {gate}")
    status = cert.get("status")
    if status == "PASS":
        for gate in CERTIFICATION_GATES:
            if gates.get(gate) != "PASS":
                errors.append(
                    f"final_pass_published_before_all_gates_complete: {gate}={gates.get(gate)}"
                )
    elif status == "PROVISIONAL":
        for gate in CERTIFICATION_GATES:
            if gate in PROVISIONAL_PENDING_GATES:
                if gates.get(gate) != "PENDING":
                    errors.append(f"provisional_gate_premature: {gate}={gates.get(gate)}")
            elif gates.get(gate) != "PASS":
                errors.append(f"provisional gate not completed: {gate}={gates.get(gate)}")
    else:
        errors.append(f"certification status is not PASS or PROVISIONAL: {status}")
    return errors


def verify_implementation_authorization(cert: Any, work_packages: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    if not isinstance(cert, dict):
        return ["certification authorization record is malformed"]
    if cert.get("automatic_next_package") is not None:
        errors.append("final certification automatically authorizes a next package")
    root = next((row for row in work_packages if row.get("work_package_id") == "WP-I0-001"), {})
    if root.get("status") != "NOT_STARTED":
        errors.append("WP-I0-001 status is not NOT_STARTED")
    return errors


def compute_expected_evidence_arrays(graphify_root: Path = GRAPHIFY) -> dict[str, object]:
    """The arrays the certification must record, recomputed from real files."""
    required = compute_required_file_evidence(graphify_root)
    layer3 = compute_layer3(graphify_root)
    source_mismatches = compute_source_rendered_mismatches(graphify_root)
    missing = sorted(set(required["missingFiles"]) | set(layer3["missingFiles"]))
    mismatched = sorted(set(source_mismatches))
    unexpected = sorted(set(layer3["unexpectedFiles"]))
    return {
        "missingFiles": missing,
        "mismatchedFiles": mismatched,
        "unexpectedFiles": unexpected,
        "sourceRenderedMismatches": mismatched,
    }


def verify_evidence_arrays_against_files(graphify_root: Path, cert: Any, envelope: Any, proof: Any) -> list[str]:
    errors: list[str] = []
    expected = compute_expected_evidence_arrays(graphify_root)
    records: list[tuple[str, Any]] = [("certification", cert), ("envelope", envelope)]
    if proof is not None:
        records.append(("proof", proof))
    for record_name, record in records:
        if not isinstance(record, dict):
            errors.append(f"{record_name} evidence record is malformed")
            continue
        for key in ("missingFiles", "mismatchedFiles", "unexpectedFiles"):
            actual = record.get(key)
            if not isinstance(actual, list):
                errors.append(f"{record_name} {key} field missing")
            elif sorted(actual) != expected.get(key):
                errors.append(f"{record_name} {key} disagrees with real files")
        actual_srm = record.get("sourceRenderedMismatches")
        if isinstance(record, dict) and "sourceRenderedMismatches" in record:
            if not isinstance(actual_srm, list) or sorted(actual_srm) != expected.get("sourceRenderedMismatches"):
                errors.append(f"{record_name} sourceRenderedMismatches disagrees with real files")
    return errors


def verify_certification_artifacts(graphify_root: Path = GRAPHIFY) -> list[str]:
    """Full independent final-certification validation (the L20 contract).

    Status-aware: a PROVISIONAL certificate must carry the NOT CERTIFIED
    declaration with the determinism and final-validation gates PENDING; a PASS
    certificate must carry the final declaration with every gate PASS, a PASS
    determinism proof, and no remaining blockers.
    """
    plan = graphify_root / "12-semantic-implementation-plan"
    reports = plan / "13-reports"
    cert_path = reports / "final-100-percent-certification.json"
    manifest_path = reports / "final-content-manifest.json"
    envelope_path = reports / "final-release-envelope.json"
    proof_path = reports / "final-determinism-proof.json"
    errors: list[str] = []
    missing_evidence = [
        path.relative_to(graphify_root).as_posix()
        for path in (cert_path, manifest_path, envelope_path)
        if not path.exists()
    ]
    if missing_evidence:
        errors.append("final 100% certification evidence missing: " + ", ".join(missing_evidence))
        return errors
    cert = read_json(cert_path)
    manifest = read_json(manifest_path)
    envelope = read_json(envelope_path)
    proof = read_json(proof_path) if proof_path.exists() else None
    validator_report = read_json(plan / "12-validators" / "validator-results.json")
    adversarial_report = read_json(plan / "12-validators" / "adversarial-results.json")

    errors.extend(verify_validator_report(validator_report))
    errors.extend(verify_adversarial_report(adversarial_report))
    errors.extend(verify_layer3_envelope(graphify_root, envelope))
    errors.extend(verify_external_integrity_report(graphify_root))
    errors.extend(verify_line_ending_policy(graphify_root))
    errors.extend(verify_final_gpt_review(graphify_root))
    errors.extend(verify_authority_graph(graphify_root))
    errors.extend(verify_full_graphify_manifest(graphify_root))
    recomputed_manifest = compute_full_graphify_manifest(graphify_root)
    manifest_entries = recomputed_manifest["files"]
    errors.extend(verify_authoritative_source_coverage(graphify_root, manifest_entries))
    errors.extend(verify_certification_tool_coverage(graphify_root, manifest_entries))
    errors.extend(verify_evidence_arrays_against_files(graphify_root, cert, envelope, proof))
    errors.extend(
        verify_exact_exclusion_set(manifest, "excluded", LAYER1_EXCLUDED, "exclusionRationales", "layer1")
    )
    errors.extend(
        verify_exact_exclusion_set(envelope, "excluded", LAYER3_EXCLUDED, "exclusionRationales", "layer3")
    )
    errors.extend(verify_certificate_gate_states(cert))
    if proof is not None:
        errors.extend(verify_cert_hash_agreements(cert, manifest, envelope, proof))
        errors.extend(
            verify_exact_exclusion_set(
                proof,
                "excluded",
                LAYER1_EXCLUDED | LAYER3_EXCLUDED,
                "exclusionRationales",
                "layer1_layer3",
            )
        )
    if cert.get("layer1Hash") != manifest.get("sha256"):
        errors.append("certification layer1 hash differs from content manifest")

    status = cert.get("status")
    if cert.get("fullGraphifyManifestDigest") != recomputed_manifest.get("digest") or cert.get("fullGraphifyManifestFileCount") != recomputed_manifest.get("file_count"):
        errors.append("certification full Graphify manifest digest or count mismatch")
    required_evidence = compute_required_file_evidence(graphify_root)
    if cert.get("requiredFiles") != required_evidence["hashes"]:
        errors.append("certification required-file hashes disagree with real files")
    if cert.get("requiredFileCount") != len(required_evidence["hashes"]):
        errors.append("certification required-file count mismatch")

    if status == "PASS":
        if cert.get("readiness_declaration") != DECLARATION:
            errors.append("final 100% certification declaration missing or incorrect")
        if cert.get("implementation_planning_100_percent_complete") is not True:
            errors.append("final certification implementation_planning flag is not true")
        if cert.get("first_allowed_package") != "WP-I0-001":
            errors.append("final certification first_allowed_package is not WP-I0-001")
        work_packages = read_json(graphify_root / "semantic-plan-source" / "packages" / "work-packages.json").get("workPackages", [])
        errors.extend(verify_implementation_authorization(cert, work_packages))
        if cert.get("remaining_blockers"):
            errors.append("final certification has remaining blockers")
        if proof is None or proof.get("status") != "PASS":
            errors.append("final determinism proof did not pass")
        handoff = plan / "14-handoff" / "START-HERE.md"
        if handoff.exists() and DECLARATION not in handoff.read_text(encoding="utf-8"):
            errors.append("handoff does not contain the final 100% declaration")
    elif status == "PROVISIONAL":
        if cert.get("readiness_declaration") != NOT_CERTIFIED_DECLARATION:
            errors.append("provisional certification declaration is not NOT CERTIFIED")
        if cert.get("implementation_planning_100_percent_complete") is not False:
            errors.append("provisional certification implementation_planning flag is not false")
        if cert.get("first_allowed_package") is not None:
            errors.append("provisional certification authorizes a first package")
        blockers = cert.get("remaining_blockers")
        if not isinstance(blockers, list) or PROVISIONAL_BLOCKER not in blockers:
            errors.append("provisional certification lacks final-validation blocker")
        if proof is not None and proof.get("status") == "PASS":
            errors.append("provisional certification has a PASS determinism proof")
    return errors
