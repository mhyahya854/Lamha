"""Twelve negative fixtures proving every final-blocker regression is rejected."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
SCHEMA_ROOT = HERE.parent / ("schemas" if (HERE.parent / "schemas").exists() else "06-schemas")
SPEC = importlib.util.spec_from_file_location("lamha_validator", HERE / "validate_plan.py")
validator = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(validator)


def contains(errors: list[str], expected: str) -> tuple[bool, list[str]]:
    return any(expected in error for error in errors), errors


def requirement_row(record_id: str, statement: str, kind: str = "FUNCTIONAL_REQUIREMENT") -> dict[str, str]:
    return {
        "canonical_id": record_id,
        "requirement_type": kind,
        "statement": statement,
        "supersession_status": "ACTIVE",
        "verification_method": "Run the focused adversarial validator fixture and inspect the typed result.",
        "parent_requirement_id": "FIX-PARENT" if kind == "ACCEPTANCE_CRITERION" else "",
        "original_requirement_ids": f"{record_id}-SOURCE",
        "source_plan": "adversarial fixture",
        "source_section": "negative regression",
        "source_text": statement,
        "source_locator": f"fixture:{record_id}",
        "rationale": "Isolated negative input used only in memory by the adversarial suite.",
        "normalization_status": "NORMALIZED",
        "canonical_capability": "Fixture validation",
    }


def run() -> dict[str, object]:
    manual_errors = validator.check_review_artifact(
        "manual-semantic-audit.md",
        "This automatically generated analysis contains no explicit reviewed decisions.",
    )
    blanket_errors = validator.check_review_script_text(
        'for row in rows:\n    row["review_status"] = "REVIEWED_CONFIRMED"\n'
    )

    gps = requirement_row("FIX-GPS", "GPS.", "ACCEPTANCE_CRITERION")
    gps_errors = validator.check_requirement_records(
        [gps], {"FIX-GPS": {"primary_implementation_phase": "I4"}}
    )

    malformed = requirement_row(
        "CAN-FAIL-99",
        "The runtime must reject invalid input; Narrative mentioned failure history; Lacked explicit control; Mapped broad tests; extra audit prose.",
        "PROHIBITION",
    )
    malformed_errors = validator.check_requirement_records(
        [malformed], {"CAN-FAIL-99": {"primary_implementation_phase": "I4"}}
    )

    stale = requirement_row(
        "FIX-STALE-PACKAGE",
        "When an asset is indexed, the system must persist its typed identity and report the stored revision.",
    )
    stale["work_package_id"] = "WP-OLD-999"
    stale_errors = validator.check_requirement_records(
        [stale], {"FIX-STALE-PACKAGE": {"primary_implementation_phase": "I4"}}
    )

    mismatch_requirements = [requirement_row(
        "FIX-PHASE-MISMATCH",
        "When the fixture executes, the validator must reject the mismatched package phase and report both phase identifiers.",
    )]
    mismatch_mappings = {"FIX-PHASE-MISMATCH": {"primary_implementation_phase": "I4"}}
    mismatch_packages = [{
        "work_package_id": "WP-FIX-I5", "implementation_phase": "I5",
        "reviewed_capabilities": ["Fixture validation"],
    }]
    mismatch_membership = [{
        "canonical_id": "FIX-PHASE-MISMATCH", "work_package_id": "WP-FIX-I5",
        "reviewer_status": "REVIEWED",
    }]
    mismatch_errors = validator.check_phase_package_consistency(
        mismatch_requirements, mismatch_mappings, mismatch_packages, mismatch_membership
    )

    metric_keys = {
        "fragmentary_active_records", "non_observable_requirements", "generic_template_records",
        "untestable_criteria", "missing_parent_relationships", "missing_verification_methods",
        "phase_package_mismatches", "stale_package_references", "unreviewed_mappings",
        "unreviewed_package_memberships", "missing_dependency_rationales",
        "missing_authority_schema_decisions",
    }
    computed = {key: 0 for key in metric_keys}
    computed["fragmentary_active_records"] = 1
    metric_errors = validator.check_metrics_honesty(
        {"computedQualityMetrics": {key: 0 for key in metric_keys}, "finalFragmentaryOrNonObservable": 0},
        computed,
        "computed at runtime",
    )

    root_errors = validator.check_dependency_records(
        [{"work_package_id": "WP-FIX-ROOT", "implementation_phase": "I0"}], []
    )

    authority_errors = validator.check_authority_registry([], [], SCHEMA_ROOT)

    archive_errors = validator.check_scope_safety(
        [{
            "work_package_id": "WP-I0-FIX", "implementation_phase": "I0",
            "name": "Repository archive", "objective": "Create an immutable archive before implementation.",
        }],
        "WP-I0-001 I0 read-only provenance inspection.",
    )

    try:
        validator.safe_write_path(validator.GRAPHIFY.parent / "forbidden-fixture-write.tmp")
        guard_errors: list[str] = []
    except ValueError as error:
        guard_errors = [str(error)]

    anonymous_errors = validator.scan_open_objects({
        "type": "object", "properties": {
            "items": {"type": "array", "items": {"type": "object"}}
        }, "additionalProperties": False,
    })

    cases = [
        ("F01_GENERATED_REPORT_FALSELY_MANUAL", *contains(manual_errors, "automatically generated report labelled manual")),
        ("F02_BLANKET_REVIEW_CERTIFICATION", *contains(blanket_errors, "blanket script marks every row reviewed")),
        ("F03_GPS_FRAGMENT_CRITERION", *contains(gps_errors, "criterion is only a label")),
        ("F04_MALFORMED_CAN_FAIL_AUDIT_PARAGRAPH", *contains(malformed_errors, "malformed CAN-FAIL audit paragraph")),
        ("F05_STALE_CANONICAL_PACKAGE_FIELD", *contains(stale_errors, "stale canonical work_package_id field")),
        ("F06_REQUIREMENT_PACKAGE_PHASE_MISMATCH", *contains(mismatch_errors, "requirement/package phase mismatch")),
        ("F07_HARD_CODED_ZERO_FRAGMENT_REPORT", *contains(metric_errors, "zero fragments claimed")),
        ("F08_UNEXPLAINED_DAG_ROOT", *contains(root_errors, "unexplained root package")),
        ("F09_SAVED_VIEWS_AUTHORITY_MISSING", *contains(authority_errors, "durable concept lacks authority decision: Saved views")),
        ("F10_I0_ARCHIVE_INSTRUCTION", *contains(archive_errors, "I0 package instructs prohibited repository backup/archive")),
        ("F11_EXTERNAL_WRITE_DESTINATION", *contains(guard_errors, "outside Graphify")),
        ("F12_ANONYMOUS_SCHEMA_OBJECT", *contains(anonymous_errors, "anonymous object array")),
    ]
    results = [
        {
            "fixture": name,
            "status": "EXPECTED_FAILURE_OBSERVED" if observed else "EXPECTED_FAILURE_MISSED",
            "validatorErrors": errors,
        }
        for name, observed, errors in cases
    ]
    return {
        "fixtureCount": len(results),
        "expectedFailuresObserved": sum(row["status"] == "EXPECTED_FAILURE_OBSERVED" for row in results),
        "status": "PASS" if all(row["status"] == "EXPECTED_FAILURE_OBSERVED" for row in results) else "FAIL",
        "fixtures": results,
    }


def main() -> int:
    result = run()
    output = validator.safe_write_path(HERE / "adversarial-results.json")
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
