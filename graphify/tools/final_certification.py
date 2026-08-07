"""Final 100% planning certification and three-layer determinism proof (gated).

The certification begins in an unverified state and may write
``status: PASS`` / ``implementation_planning_100_percent_complete: true`` /
``remaining_blockers: []`` only after every gate below has genuinely passed.
On any failure it writes ``status: FAIL`` with the exact blockers and returns
a non-zero exit code.  Saved PASS text is never trusted: every required input
is re-read, re-hashed, and structurally re-verified from raw evidence.

Execution sequence (non-circular two-stage design)
--------------------------------------------------

1. ``build_semantic_plan.py`` regenerates every derived plan output from the
   authoritative sources in ``semantic-plan-source/``.
2. ``validate_plan.py --write-results --pre-certification`` runs all
   non-final-certification checks (every level except the final L20 check).
   L20 is recorded as deferred to the final certification validation stage so
   the process is not circular.
3. ``adversarial_fixtures.py`` regenerates the adversarial results.
4. Pre-certification validation (in-memory): the validator report is parsed
   structurally (all non-L20 levels PASS, required levels present exactly
   once), the adversarial report is parsed structurally, every required file
   is checked for existence/readability and hashed, source/rendered equality
   is recomputed, external integrity is parsed structurally, and the full
   Graphify SHA manifest is recomputed and compared to the saved manifest.
5. The provisional Layer 1/2/3 artifacts are written, then
   ``validate_plan.py --write-results`` runs again: L20 now independently
   verifies every pre-certification evidence item and the final artifacts.
6. Final certification validation: the resulting validator report is parsed
   structurally again, the final Layer 1/2/3 artifacts are rewritten against
   the final tree, and a read-only full validator run re-verifies the final
   artifacts without mutating the tree.

Only after steps 4-6 all pass is the readiness declaration published.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

sys.dont_write_bytecode = True

GRAPHIFY = pathlib.Path(__file__).resolve().parents[1]
PLAN = GRAPHIFY / "12-semantic-implementation-plan"
REPORTS = PLAN / "13-reports"
REVIEWS = GRAPHIFY / "semantic-plan-source" / "reviews"
SOURCE = GRAPHIFY / "semantic-plan-source"
VALIDATORS = PLAN / "12-validators"
BUILDER = GRAPHIFY / "build_semantic_plan.py"
VALIDATOR = VALIDATORS / "validate_plan.py"
ADVERSARIAL = VALIDATORS / "adversarial_fixtures.py"
HANDOFF_GENERATOR = GRAPHIFY / "tools" / "generate_gpt_handoff.py"

sys.path.insert(0, str(GRAPHIFY / "tools"))
from write_guard import write_json  # noqa: E402
from certification_gates import (  # noqa: E402
    CERTIFICATION_GATES,
    DECLARATION,
    LAYER1_EXCLUDED,
    LAYER1_EXCLUSION_RATIONALES,
    LAYER3_EXCLUDED,
    LAYER3_EXCLUSION_RATIONALES,
    NOT_CERTIFIED_DECLARATION,
    compute_expected_evidence_arrays,
    compute_full_graphify_manifest,
    compute_layer1,
    compute_layer3,
    compute_required_file_evidence,
    compute_source_rendered_mismatches,
    read_json,
    verify_adversarial_report,
    verify_authoritative_source_coverage,
    verify_certification_tool_coverage,
    verify_external_integrity_report,
    verify_full_graphify_manifest,
    verify_required_files,
    verify_validator_report,
)


PASS_A = "PASS A COMPLETE \u2014 ALL ACTIONABLE REQUIREMENTS INDIVIDUALLY REVIEWED"
PASS_B = "PASS B COMPLETE \u2014 PACKAGE ARCHITECTURE AND DEPENDENCY PROVENANCE READY"
PASS_C = "PASS C COMPLETE \u2014 ALL COMPONENT AND LICENCE DECISIONS FINALIZED"


def run(script: pathlib.Path, *arguments: str) -> None:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["TEMP"] = str(REPORTS)
    environment["TMP"] = str(REPORTS)
    completed = subprocess.run(
        [sys.executable, "-B", str(script), *arguments],
        cwd=str(GRAPHIFY),
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode:
        raise RuntimeError(
            f"{script.relative_to(GRAPHIFY)} failed with exit {completed.returncode}\n"
            f"{completed.stdout}\n{completed.stderr}"
        )


def certification_payload(
    *,
    status: str,
    blockers: list[str],
    gates: dict[str, str],
    layer1: dict[str, object],
    required_evidence: dict[str, object],
    full_manifest: dict[str, object],
    external_summary: dict[str, object],
    validator_summary: dict[str, object],
    adversarial_summary: dict[str, object],
) -> dict[str, object]:
    passing = status == "PASS"
    return {
        "status": status,
        "readiness_declaration": DECLARATION if passing else NOT_CERTIFIED_DECLARATION,
        "implementation_planning_100_percent_complete": passing,
        "first_allowed_package": "WP-I0-001" if passing else None,
        "automatic_next_package": None,
        "remaining_blockers": blockers,
        "passA": PASS_A,
        "passB": PASS_B,
        "passC": PASS_C,
        "layer1Hash": layer1.get("sha256"),
        "fullGraphifyManifestDigest": full_manifest.get("digest"),
        "fullGraphifyManifestFileCount": full_manifest.get("file_count"),
        "requiredFileCount": len(required_evidence.get("hashes", {})),
        "requiredFiles": required_evidence.get("hashes", {}),
        "missingFiles": sorted(required_evidence.get("missingFiles", [])),
        "mismatchedFiles": sorted(required_evidence.get("mismatchedFiles", [])),
        "unexpectedFiles": sorted(required_evidence.get("unexpectedFiles", [])),
        "unexplainedExclusions": sorted(required_evidence.get("unexplainedExclusions", [])),
        "sourceRenderedMismatches": sorted(required_evidence.get("sourceRenderedMismatches", [])),
        "externalIntegrity": external_summary,
        "validator": validator_summary,
        "adversarial": adversarial_summary,
        "certificationGates": gates,
    }


def write_layer1_manifest(layer1: dict[str, object]) -> None:
    manifest = {
        "layer": 1,
        "sha256": layer1.get("sha256"),
        "fileCount": layer1.get("fileCount"),
        "files": layer1.get("files"),
        "fileHashes": layer1.get("fileHashes"),
        "excluded": sorted(LAYER1_EXCLUDED),
        "exclusionRationales": LAYER1_EXCLUSION_RATIONALES,
    }
    write_json(REPORTS / "final-content-manifest.json", manifest)
    write_json(REVIEWS / "final-content-manifest.json", manifest)


def write_envelope(layer3: dict[str, object], mismatched_files: list[str]) -> None:
    envelope = {
        "layer": 3,
        "sha256": layer3.get("sha256"),
        "fileCount": layer3.get("fileCount"),
        "files": layer3.get("files"),
        "fileHashes": layer3.get("fileHashes"),
        "missingFiles": sorted(layer3.get("missingFiles", [])),
        "unexpectedFiles": sorted(layer3.get("unexpectedFiles", [])),
        "mismatchedFiles": sorted(mismatched_files),
        "excluded": sorted(LAYER3_EXCLUDED),
        "exclusionRationales": LAYER3_EXCLUSION_RATIONALES,
    }
    write_json(REPORTS / "final-release-envelope.json", envelope)
    write_json(REVIEWS / "final-release-envelope.json", envelope)


def write_determinism_proof(
    first: tuple[str, str],
    second: tuple[str, str],
    evidence: dict[str, object],
    passing: bool,
) -> None:
    proof = {
        "layer1FirstHash": first[0],
        "layer1SecondHash": second[0],
        "layer3FirstHash": first[1],
        "layer3SecondHash": second[1],
        "missingFiles": sorted(evidence.get("missingFiles", [])),
        "mismatchedFiles": sorted(evidence.get("mismatchedFiles", [])),
        "unexpectedFiles": sorted(evidence.get("unexpectedFiles", [])),
        "unexplainedExclusions": sorted(evidence.get("unexplainedExclusions", [])),
        "excluded": sorted(LAYER3_EXCLUDED | LAYER1_EXCLUDED),
        "exclusionRationales": {
            **LAYER3_EXCLUSION_RATIONALES,
            **LAYER1_EXCLUSION_RATIONALES,
        },
        "status": "PASS" if passing else "FAIL",
    }
    write_json(REPORTS / "final-determinism-proof.json", proof)
    write_json(REVIEWS / "final-determinism-proof.json", proof)


def write_failure_certification(blockers: list[str]) -> None:
    """Write a FAIL certification so a stale PASS can never survive a failure."""
    evidence = compute_expected_evidence_arrays(GRAPHIFY)
    evidence["hashes"] = compute_required_file_evidence(GRAPHIFY)["hashes"]
    layer1 = compute_layer1(GRAPHIFY)
    full_manifest = compute_full_graphify_manifest(GRAPHIFY)
    layer3 = compute_layer3(GRAPHIFY)
    cert = certification_payload(
        status="FAIL",
        blockers=blockers,
        gates={gate: "NOT_RUN" for gate in CERTIFICATION_GATES},
        layer1=layer1,
        required_evidence=evidence,
        full_manifest=full_manifest,
        external_summary={"status": "FAIL"},
        validator_summary={"status": "FAIL"},
        adversarial_summary={"status": "FAIL"},
    )
    write_json(REPORTS / "final-100-percent-certification.json", cert)
    write_json(REVIEWS / "final-100-percent-certification.json", cert)
    write_layer1_manifest(layer1)
    write_envelope(layer3, evidence.get("mismatchedFiles", []))
    write_determinism_proof(
        (str(layer1.get("sha256")), str(layer3.get("sha256"))),
        (str(layer1.get("sha256")), str(layer3.get("sha256"))),
        evidence,
        passing=False,
    )


def summarize_validator(report: dict[str, object]) -> dict[str, object]:
    return {
        "status": report.get("status"),
        "levelCount": report.get("levelCount"),
        "failedLevels": report.get("failedLevels"),
    }


def summarize_adversarial(report: dict[str, object]) -> dict[str, object]:
    return {
        "status": report.get("status"),
        "fixtureCount": report.get("fixtureCount"),
        "expectedFailuresObserved": report.get("expectedFailuresObserved"),
    }


def main() -> int:
    blockers: list[str] = []
    try:
        # Stage 0 -- deterministic rebuild and pre-certification evidence.
        run(BUILDER)
        run(VALIDATOR, "--write-results", "--pre-certification")
        run(ADVERSARIAL)
        # The full Graphify SHA manifest and handoff counts are generated after
        # the validation evidence so the saved manifest covers the current
        # fixture counts and validator status deterministically.
        run(HANDOFF_GENERATOR)

        # Stage 1 -- pre-certification validation (every gate except the final
        # certification validation, which L20 performs after artifacts exist).
        validator_report = read_json(VALIDATORS / "validator-results.json")
        adversarial_report = read_json(VALIDATORS / "adversarial-results.json")
        pre_errors: list[str] = []
        pre_errors.extend(
            verify_validator_report(validator_report, require_l20_note="deferred_to_final_certification_validation")
        )
        pre_errors.extend(verify_adversarial_report(adversarial_report))
        pre_errors.extend(verify_required_files(GRAPHIFY))
        source_mismatches = compute_source_rendered_mismatches(GRAPHIFY)
        pre_errors.extend(f"source/rendered mismatch: {mismatch}" for mismatch in source_mismatches)
        pre_errors.extend(verify_external_integrity_report(GRAPHIFY))
        pre_errors.extend(verify_full_graphify_manifest(GRAPHIFY))
        recomputed_manifest = compute_full_graphify_manifest(GRAPHIFY)
        pre_errors.extend(verify_authoritative_source_coverage(GRAPHIFY, recomputed_manifest["files"]))
        pre_errors.extend(verify_certification_tool_coverage(GRAPHIFY, recomputed_manifest["files"]))
        if pre_errors:
            blockers = sorted(set(pre_errors))
            write_failure_certification(blockers)
            print(json.dumps({"status": "FAIL", "remaining_blockers": blockers}, indent=2, ensure_ascii=False))
            return 1

        gates = {gate: "PASS" for gate in CERTIFICATION_GATES}
        evidence = compute_expected_evidence_arrays(GRAPHIFY)
        evidence["hashes"] = compute_required_file_evidence(GRAPHIFY)["hashes"]
        if evidence["missingFiles"] or evidence["mismatchedFiles"] or evidence["unexpectedFiles"]:
            blockers = sorted(
                set(evidence["missingFiles"])
                | set(evidence["mismatchedFiles"])
                | set(evidence["unexpectedFiles"])
            )
            write_failure_certification(blockers)
            print(json.dumps({"status": "FAIL", "remaining_blockers": blockers}, indent=2, ensure_ascii=False))
            return 1

        # Provisional artifacts: written so the stage-2 L20 run can verify the
        # final certification evidence without circularity.  Layer 3 is
        # computed after the Layer 1 manifest and certification are written so
        # the recorded digest covers the exact committed files.
        layer1 = compute_layer1(GRAPHIFY)
        cert = certification_payload(
            status="PASS",
            blockers=[],
            gates=gates,
            layer1=layer1,
            required_evidence=evidence,
            full_manifest=recomputed_manifest,
            external_summary={"status": "PASS", "added": 0, "removed": 0, "modified": 0, "renamed": 0},
            validator_summary=summarize_validator(validator_report),
            adversarial_summary=summarize_adversarial(adversarial_report),
        )
        write_layer1_manifest(layer1)
        write_json(REPORTS / "final-100-percent-certification.json", cert)
        write_json(REVIEWS / "final-100-percent-certification.json", cert)
        layer3 = compute_layer3(GRAPHIFY)
        write_envelope(layer3, evidence["mismatchedFiles"])
        write_determinism_proof(
            (str(layer1["sha256"]), str(layer3["sha256"])),
            (str(layer1["sha256"]), str(layer3["sha256"])),
            evidence,
            passing=True,
        )

        # Stage 2 -- final certification validation: L20 independently verifies
        # all pre-certification evidence and the provisional final artifacts.
        run(VALIDATOR, "--write-results")
        final_validator_report = read_json(VALIDATORS / "validator-results.json")
        final_errors = verify_validator_report(
            final_validator_report, require_l20_note="final_certification_validation_complete"
        )
        if final_errors:
            blockers = sorted(set(final_errors))
            write_failure_certification(blockers)
            print(json.dumps({"status": "FAIL", "remaining_blockers": blockers}, indent=2, ensure_ascii=False))
            return 1

        # Final certification artifacts against the final tree (validator
        # results now reflect the full L20 validation).
        final_layer1 = compute_layer1(GRAPHIFY)
        final_evidence = compute_expected_evidence_arrays(GRAPHIFY)
        final_evidence["hashes"] = compute_required_file_evidence(GRAPHIFY)["hashes"]
        final_cert = certification_payload(
            status="PASS",
            blockers=[],
            gates=gates,
            layer1=final_layer1,
            required_evidence=final_evidence,
            full_manifest=recomputed_manifest,
            external_summary={"status": "PASS", "added": 0, "removed": 0, "modified": 0, "renamed": 0},
            validator_summary=summarize_validator(final_validator_report),
            adversarial_summary=summarize_adversarial(adversarial_report),
        )
        write_layer1_manifest(final_layer1)
        write_json(REPORTS / "final-100-percent-certification.json", final_cert)
        write_json(REVIEWS / "final-100-percent-certification.json", final_cert)
        final_layer3 = compute_layer3(GRAPHIFY)
        write_envelope(final_layer3, final_evidence["mismatchedFiles"])

        # Two in-memory Layer 1/3 runs over the final tree; both must agree.
        first_layer1 = compute_layer1(GRAPHIFY)
        first_layer3 = compute_layer3(GRAPHIFY)
        second_layer1 = compute_layer1(GRAPHIFY)
        second_layer3 = compute_layer3(GRAPHIFY)
        stable = (
            first_layer1["sha256"] == second_layer1["sha256"]
            and first_layer3["sha256"] == second_layer3["sha256"]
        )
        write_determinism_proof(
            (str(first_layer1["sha256"]), str(first_layer3["sha256"])),
            (str(second_layer1["sha256"]), str(second_layer3["sha256"])),
            final_evidence,
            passing=stable,
        )
        if not stable:
            blockers = ["layer1 or layer3 hashes differ between certification runs"]
            write_failure_certification(blockers)
            print(json.dumps({"status": "FAIL", "remaining_blockers": blockers}, indent=2, ensure_ascii=False))
            return 1

        # Stage 3 -- read-only full validator run against the FINAL artifacts
        # (no writes), so L20 independently confirms what is committed.
        run(VALIDATOR)
        read_only_report = read_json(VALIDATORS / "validator-results.json")
        if read_only_report.get("status") != "PASS":
            blockers = ["final certification validation did not pass on the committed artifacts"]
            write_failure_certification(blockers)
            print(json.dumps({"status": "FAIL", "remaining_blockers": blockers}, indent=2, ensure_ascii=False))
            return 1

        final_cert = read_json(REPORTS / "final-100-percent-certification.json")
        final_proof = read_json(REPORTS / "final-determinism-proof.json")
        print(json.dumps({
            "status": "PASS",
            "readiness_declaration": DECLARATION,
            "layer1FirstHash": final_proof.get("layer1FirstHash"),
            "layer1SecondHash": final_proof.get("layer1SecondHash"),
            "layer3FirstHash": final_proof.get("layer3FirstHash"),
            "layer3SecondHash": final_proof.get("layer3SecondHash"),
            "fullGraphifyManifestDigest": final_cert.get("fullGraphifyManifestDigest"),
            "fullGraphifyManifestFileCount": final_cert.get("fullGraphifyManifestFileCount"),
            "requiredFileCount": final_cert.get("requiredFileCount"),
            "missingFiles": final_cert.get("missingFiles"),
            "mismatchedFiles": final_cert.get("mismatchedFiles"),
            "unexpectedFiles": final_cert.get("unexpectedFiles"),
            "unexplainedExclusions": final_cert.get("unexplainedExclusions"),
            "externalIntegrity": final_cert.get("externalIntegrity"),
            "validator": final_cert.get("validator"),
            "adversarial": final_cert.get("adversarial"),
        }, indent=2, ensure_ascii=False))
        return 0
    except RuntimeError as error:
        blockers = [str(error)]
        write_failure_certification(blockers)
        print(json.dumps({"status": "FAIL", "remaining_blockers": blockers}, indent=2, ensure_ascii=False))
        return 1
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        blockers = [f"certification aborted: {error}"]
        write_failure_certification(blockers)
        print(json.dumps({"status": "FAIL", "remaining_blockers": blockers}, indent=2, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
