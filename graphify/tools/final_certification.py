"""Final 100% planning certification and three-layer determinism proof (gated).

The certification begins in an unverified state and may write
``status: PASS`` / ``implementation_planning_100_percent_complete: true`` /
``remaining_blockers: []`` only after every gate below has genuinely passed.
On any failure it writes ``status: FAIL`` with the exact blockers and returns
a non-zero exit code.  Saved PASS text is never trusted: every required input
is re-read, re-hashed, and structurally re-verified from raw evidence.

Crash/interruption safety
-------------------------

* A stale PASS is invalidated at the very beginning of the run.
* Before the Stage 2 final certification validation completes, the persisted
  certification is always ``status: PROVISIONAL`` with the
  ``NOT CERTIFIED - IMPLEMENTATION BLOCKED`` declaration,
  ``implementation_planning_100_percent_complete: false``,
  ``first_allowed_package: null``, the remaining blocker
  ``final certification validation has not completed``, and the determinism
  plus final-validation gates recorded as ``PENDING``.
* Final records are built entirely in memory, validated, written to temporary
  files inside Graphify, fsynced, and atomically replaced.  The PASS
  certification is published last, so an interruption at any earlier point
  leaves only a blocked provisional state on disk.

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
5. The provisional Layer 1/2/3 artifacts are written with PROVISIONAL
   semantics, then ``validate_plan.py --write-results`` runs again: L20 now
   independently verifies every pre-certification evidence item and the final
   artifacts while the persisted state remains NOT CERTIFIED.
6. Final certification validation: the resulting validator report is parsed
   structurally again, the final Layer 1/2/3 artifacts are built in memory
   against the final tree, verified in memory, and atomically published with
   the PASS certification last.
7. A read-only full validator run re-verifies the published artifacts without
   mutating the tree; any failure immediately invalidates the PASS.
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

CERTIFICATION = "final-100-percent-certification.json"
CONTENT_MANIFEST = "final-content-manifest.json"
RELEASE_ENVELOPE = "final-release-envelope.json"
DETERMINISM_PROOF = "final-determinism-proof.json"

sys.path.insert(0, str(GRAPHIFY / "tools"))
from write_guard import guard_write_path, write_json  # noqa: E402
from certification_gates import (  # noqa: E402
    CERTIFICATION_GATES,
    DECLARATION,
    LAYER1_EXCLUDED,
    LAYER1_EXCLUSION_RATIONALES,
    LAYER3_EXCLUDED,
    LAYER3_EXCLUSION_RATIONALES,
    NOT_CERTIFIED_DECLARATION,
    PROVISIONAL_BLOCKER,
    PROVISIONAL_PENDING_GATES,
    compute_expected_evidence_arrays,
    compute_full_graphify_manifest,
    compute_layer1,
    compute_layer3,
    compute_required_file_evidence,
    compute_source_rendered_mismatches,
    read_json,
    verify_adversarial_report,
    verify_authoritative_source_coverage,
    verify_cert_hash_agreements,
    verify_certificate_gate_states,
    verify_certification_tool_coverage,
    verify_exact_exclusion_set,
    verify_external_integrity_report,
    verify_full_graphify_manifest,
    verify_layer3_membership,
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


def build_layer1_manifest(layer1: dict[str, object]) -> dict[str, object]:
    return {
        "layer": 1,
        "sha256": layer1.get("sha256"),
        "fileCount": layer1.get("fileCount"),
        "files": layer1.get("files"),
        "fileHashes": layer1.get("fileHashes"),
        "excluded": sorted(LAYER1_EXCLUDED),
        "exclusionRationales": LAYER1_EXCLUSION_RATIONALES,
    }


def build_envelope(layer3: dict[str, object], mismatched_files: list[str]) -> dict[str, object]:
    return {
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


def build_determinism_proof(
    first: tuple[str, str],
    second: tuple[str, str],
    evidence: dict[str, object],
    status: str,
) -> dict[str, object]:
    return {
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
        "status": status,
    }


def write_layer1_manifest(layer1: dict[str, object]) -> None:
    manifest = build_layer1_manifest(layer1)
    write_json(REPORTS / CONTENT_MANIFEST, manifest)
    write_json(REVIEWS / CONTENT_MANIFEST, manifest)


def write_envelope(layer3: dict[str, object], mismatched_files: list[str]) -> None:
    envelope = build_envelope(layer3, mismatched_files)
    write_json(REPORTS / RELEASE_ENVELOPE, envelope)
    write_json(REVIEWS / RELEASE_ENVELOPE, envelope)


def write_determinism_proof(
    first: tuple[str, str],
    second: tuple[str, str],
    evidence: dict[str, object],
    status: str,
) -> None:
    proof = build_determinism_proof(first, second, evidence, status)
    write_json(REPORTS / DETERMINISM_PROOF, proof)
    write_json(REVIEWS / DETERMINISM_PROOF, proof)


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
    write_json(REPORTS / CERTIFICATION, cert)
    write_json(REVIEWS / CERTIFICATION, cert)
    write_layer1_manifest(layer1)
    write_envelope(layer3, evidence.get("mismatchedFiles", []))
    write_determinism_proof(
        (str(layer1.get("sha256")), str(layer3.get("sha256"))),
        (str(layer1.get("sha256")), str(layer3.get("sha256"))),
        evidence,
        status="FAIL",
    )


def write_blocked_artifacts(blockers: list[str], gates: dict[str, str]) -> None:
    """Persist PROVISIONAL / NOT CERTIFIED artifacts (never PASS semantics)."""
    evidence = compute_expected_evidence_arrays(GRAPHIFY)
    evidence["hashes"] = compute_required_file_evidence(GRAPHIFY)["hashes"]
    layer1 = compute_layer1(GRAPHIFY)
    full_manifest = compute_full_graphify_manifest(GRAPHIFY)
    layer3 = compute_layer3(GRAPHIFY)
    cert = certification_payload(
        status="PROVISIONAL",
        blockers=blockers,
        gates=gates,
        layer1=layer1,
        required_evidence=evidence,
        full_manifest=full_manifest,
        external_summary={"status": "PENDING"},
        validator_summary={"status": "PENDING"},
        adversarial_summary={"status": "PENDING"},
    )
    write_layer1_manifest(layer1)
    write_json(REPORTS / CERTIFICATION, cert)
    write_json(REVIEWS / CERTIFICATION, cert)
    write_envelope(layer3, evidence.get("mismatchedFiles", []))
    write_determinism_proof(
        (str(layer1.get("sha256")), str(layer3.get("sha256"))),
        (str(layer1.get("sha256")), str(layer3.get("sha256"))),
        evidence,
        status="PROVISIONAL",
    )


def write_provisional_artifacts(
    evidence: dict[str, object],
    layer1: dict[str, object],
    full_manifest: dict[str, object],
    validator_summary: dict[str, object],
    adversarial_summary: dict[str, object],
) -> None:
    """Persist the pre-Stage-2 provisional artifacts (NOT CERTIFIED)."""
    gates = {gate: "PASS" for gate in CERTIFICATION_GATES}
    for gate in PROVISIONAL_PENDING_GATES:
        gates[gate] = "PENDING"
    cert = certification_payload(
        status="PROVISIONAL",
        blockers=[PROVISIONAL_BLOCKER],
        gates=gates,
        layer1=layer1,
        required_evidence=evidence,
        full_manifest=full_manifest,
        external_summary={"status": "PASS", "added": 0, "removed": 0, "modified": 0, "renamed": 0},
        validator_summary=validator_summary,
        adversarial_summary=adversarial_summary,
    )
    write_layer1_manifest(layer1)
    write_json(REPORTS / CERTIFICATION, cert)
    write_json(REVIEWS / CERTIFICATION, cert)
    layer3 = compute_layer3(GRAPHIFY)
    write_envelope(layer3, evidence.get("mismatchedFiles", []))
    write_determinism_proof(
        (str(layer1["sha256"]), str(layer3["sha256"])),
        (str(layer1["sha256"]), str(layer3["sha256"])),
        evidence,
        status="PROVISIONAL",
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


def serialized_json_bytes(value: object) -> bytes:
    """Exact bytes ``write_json`` persists, so in-memory digests match disk."""
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def atomic_write_bytes(path: pathlib.Path, data: bytes) -> None:
    target = guard_write_path(path)
    temp = guard_write_path(target.with_name(target.name + ".cert-tmp"))
    with temp.open("wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, target)


def cleanup_temp_files() -> None:
    for directory in (REPORTS, REVIEWS):
        if not directory.exists():
            continue
        for path in directory.glob("*.cert-tmp"):
            try:
                path.unlink()
            except OSError:
                pass


def atomic_publish(
    cert: dict[str, object],
    manifest: dict[str, object],
    envelope: dict[str, object],
    proof: dict[str, object],
) -> None:
    """Atomically replace the final artifacts; publish the PASS cert LAST."""
    manifest_bytes = serialized_json_bytes(manifest)
    envelope_bytes = serialized_json_bytes(envelope)
    proof_bytes = serialized_json_bytes(proof)
    cert_bytes = serialized_json_bytes(cert)
    writes = [
        (REPORTS / CONTENT_MANIFEST, manifest_bytes),
        (REVIEWS / CONTENT_MANIFEST, manifest_bytes),
        (REPORTS / RELEASE_ENVELOPE, envelope_bytes),
        (REVIEWS / RELEASE_ENVELOPE, envelope_bytes),
        (REPORTS / DETERMINISM_PROOF, proof_bytes),
        (REVIEWS / DETERMINISM_PROOF, proof_bytes),
        # The canonical PASS certification is the final operation.
        (REVIEWS / CERTIFICATION, cert_bytes),
        (REPORTS / CERTIFICATION, cert_bytes),
    ]
    for path, data in writes:
        atomic_write_bytes(path, data)


def verify_final_records_in_memory(
    cert: dict[str, object],
    manifest: dict[str, object],
    envelope: dict[str, object],
    proof: dict[str, object],
    full_manifest_digest: object,
    full_manifest_count: object,
) -> list[str]:
    errors: list[str] = []
    errors.extend(verify_certificate_gate_states(cert))
    errors.extend(verify_layer3_membership(envelope))
    errors.extend(
        verify_exact_exclusion_set(manifest, "excluded", LAYER1_EXCLUDED, "exclusionRationales", "layer1")
    )
    errors.extend(
        verify_exact_exclusion_set(envelope, "excluded", LAYER3_EXCLUDED, "exclusionRationales", "layer3")
    )
    errors.extend(
        verify_exact_exclusion_set(
            proof,
            "excluded",
            LAYER1_EXCLUDED | LAYER3_EXCLUDED,
            "exclusionRationales",
            "layer1_layer3",
        )
    )
    errors.extend(verify_cert_hash_agreements(cert, manifest, envelope, proof))
    if cert.get("status") != "PASS":
        errors.append("final certification status is not PASS")
    if cert.get("readiness_declaration") != DECLARATION:
        errors.append("final 100% certification declaration missing or incorrect")
    if cert.get("implementation_planning_100_percent_complete") is not True:
        errors.append("final certification implementation_planning flag is not true")
    if cert.get("first_allowed_package") != "WP-I0-001":
        errors.append("final certification first_allowed_package is not WP-I0-001")
    if cert.get("remaining_blockers"):
        errors.append("final certification has remaining blockers")
    if proof.get("status") != "PASS":
        errors.append("final determinism proof did not pass")
    if (
        cert.get("fullGraphifyManifestDigest") != full_manifest_digest
        or cert.get("fullGraphifyManifestFileCount") != full_manifest_count
    ):
        errors.append("certification full Graphify manifest digest or count mismatch")
    return errors


def main() -> int:
    blockers: list[str] = []
    try:
        # Invalidate any stale PASS immediately.  No gate is marked PASS before
        # it has executed successfully.
        cleanup_temp_files()
        write_blocked_artifacts(
            [PROVISIONAL_BLOCKER],
            {gate: "NOT_RUN" for gate in CERTIFICATION_GATES},
        )

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
        # final certification evidence without circularity.  The persisted
        # state is PROVISIONAL / NOT CERTIFIED until the final publication.
        layer1 = compute_layer1(GRAPHIFY)
        write_provisional_artifacts(
            evidence,
            layer1,
            recomputed_manifest,
            summarize_validator(validator_report),
            summarize_adversarial(adversarial_report),
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

        # Build the final records entirely in memory over the final tree.
        final_layer1 = compute_layer1(GRAPHIFY)
        final_evidence = compute_expected_evidence_arrays(GRAPHIFY)
        final_evidence["hashes"] = compute_required_file_evidence(GRAPHIFY)["hashes"]
        if final_evidence["missingFiles"] or final_evidence["mismatchedFiles"] or final_evidence["unexpectedFiles"]:
            blockers = sorted(
                set(final_evidence["missingFiles"])
                | set(final_evidence["mismatchedFiles"])
                | set(final_evidence["unexpectedFiles"])
            )
            write_failure_certification(blockers)
            print(json.dumps({"status": "FAIL", "remaining_blockers": blockers}, indent=2, ensure_ascii=False))
            return 1

        final_gates = {gate: "PASS" for gate in CERTIFICATION_GATES}
        final_cert = certification_payload(
            status="PASS",
            blockers=[],
            gates=final_gates,
            layer1=final_layer1,
            required_evidence=final_evidence,
            full_manifest=recomputed_manifest,
            external_summary={"status": "PASS", "added": 0, "removed": 0, "modified": 0, "renamed": 0},
            validator_summary=summarize_validator(final_validator_report),
            adversarial_summary=summarize_adversarial(adversarial_report),
        )
        final_manifest = build_layer1_manifest(final_layer1)
        final_cert_bytes = serialized_json_bytes(final_cert)
        final_manifest_bytes = serialized_json_bytes(final_manifest)
        layer3_overrides = {
            f"12-semantic-implementation-plan/13-reports/{CERTIFICATION}": final_cert_bytes,
            f"12-semantic-implementation-plan/13-reports/{CONTENT_MANIFEST}": final_manifest_bytes,
        }

        # Two in-memory Layer 1/3 runs over the final records; both must agree.
        first_layer1 = compute_layer1(GRAPHIFY)
        first_layer3 = compute_layer3(GRAPHIFY, overrides=layer3_overrides)
        second_layer1 = compute_layer1(GRAPHIFY)
        second_layer3 = compute_layer3(GRAPHIFY, overrides=layer3_overrides)
        stable = (
            first_layer1["sha256"] == second_layer1["sha256"]
            and first_layer3["sha256"] == second_layer3["sha256"]
        )
        final_envelope = build_envelope(first_layer3, final_evidence["mismatchedFiles"])
        final_proof = build_determinism_proof(
            (str(first_layer1["sha256"]), str(first_layer3["sha256"])),
            (str(second_layer1["sha256"]), str(second_layer3["sha256"])),
            final_evidence,
            status="PASS",
        )
        if not stable:
            blockers = ["layer1 or layer3 hashes differ between certification runs"]
            write_failure_certification(blockers)
            print(json.dumps({"status": "FAIL", "remaining_blockers": blockers}, indent=2, ensure_ascii=False))
            return 1

        in_memory_errors = verify_final_records_in_memory(
            final_cert,
            final_manifest,
            final_envelope,
            final_proof,
            recomputed_manifest.get("digest"),
            recomputed_manifest.get("file_count"),
        )
        if in_memory_errors:
            blockers = sorted(set(in_memory_errors))
            write_failure_certification(blockers)
            print(json.dumps({"status": "FAIL", "remaining_blockers": blockers}, indent=2, ensure_ascii=False))
            return 1

        # Atomic publication; the PASS certification is the last operation.
        atomic_publish(final_cert, final_manifest, final_envelope, final_proof)
        cleanup_temp_files()

        # Stage 3 -- read-only full validator run against the FINAL artifacts
        # (no writes), so L20 independently confirms what is committed.
        run(VALIDATOR)
        read_only_report = read_json(VALIDATORS / "validator-results.json")
        if read_only_report.get("status") != "PASS":
            blockers = ["final certification validation did not pass on the committed artifacts"]
            write_failure_certification(blockers)
            print(json.dumps({"status": "FAIL", "remaining_blockers": blockers}, indent=2, ensure_ascii=False))
            return 1

        final_cert = read_json(REPORTS / CERTIFICATION)
        final_proof = read_json(REPORTS / DETERMINISM_PROOF)
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
    finally:
        cleanup_temp_files()


if __name__ == "__main__":
    raise SystemExit(main())
