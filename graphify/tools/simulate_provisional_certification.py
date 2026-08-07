"""Read-only simulation of the provisional / interrupted certification state.

Proves that every persisted state before the final atomic publication is
NOT CERTIFIED / IMPLEMENTATION BLOCKED and that WP-I0-001 is never authorized
until the final PASS record exists.  No files are written by this tool.
"""

from __future__ import annotations

import json
import pathlib
import sys

sys.dont_write_bytecode = True

GRAPHIFY = pathlib.Path(__file__).resolve().parents[1]
REPORTS = GRAPHIFY / "12-semantic-implementation-plan" / "13-reports"
sys.path.insert(0, str(GRAPHIFY / "tools"))
from certification_gates import (  # noqa: E402
    CERTIFICATION_GATES,
    DECLARATION,
    NOT_CERTIFIED_DECLARATION,
    PROVISIONAL_BLOCKER,
    PROVISIONAL_PENDING_GATES,
    verify_certificate_gate_states,
)
from final_certification import certification_payload  # noqa: E402


def provisional_gates() -> dict[str, str]:
    gates = {name: "PASS" for name in CERTIFICATION_GATES}
    for name in PROVISIONAL_PENDING_GATES:
        gates[name] = "PENDING"
    return gates


def initial_blocked_gates() -> dict[str, str]:
    return {name: "NOT_RUN" for name in CERTIFICATION_GATES}


def build_provisional_record(gates: dict[str, str]) -> dict[str, object]:
    return certification_payload(
        status="PROVISIONAL",
        blockers=[PROVISIONAL_BLOCKER],
        gates=gates,
        layer1={"sha256": "0" * 64, "fileCount": 0, "files": [], "fileHashes": {}},
        required_evidence={
            "hashes": {},
            "missingFiles": [],
            "mismatchedFiles": [],
            "unexpectedFiles": [],
            "unexplainedExclusions": [],
            "sourceRenderedMismatches": [],
        },
        full_manifest={"digest": "0" * 64, "file_count": 0, "files": {}},
        external_summary={"status": "PENDING"},
        validator_summary={"status": "PENDING"},
        adversarial_summary={"status": "PENDING"},
    )


def verify_blocked_record(record: dict[str, object], label: str, strict_provisional: bool) -> list[str]:
    errors: list[str] = []
    if record.get("status") != "PROVISIONAL":
        errors.append(f"{label}: status is not PROVISIONAL")
    if record.get("readiness_declaration") != NOT_CERTIFIED_DECLARATION:
        errors.append(f"{label}: declaration is not NOT CERTIFIED / IMPLEMENTATION BLOCKED")
    if record.get("implementation_planning_100_percent_complete") is not False:
        errors.append(f"{label}: implementation_planning flag is not false")
    if record.get("first_allowed_package") is not None:
        errors.append(f"{label}: first_allowed_package is not null (WP-I0-001 authorized early)")
    blockers = record.get("remaining_blockers")
    if not isinstance(blockers, list) or PROVISIONAL_BLOCKER not in blockers:
        errors.append(f"{label}: final-validation blocker missing")
    if strict_provisional:
        errors.extend(verify_certificate_gate_states(record))
    else:
        gates = record.get("certificationGates") or {}
        for name in CERTIFICATION_GATES:
            if gates.get(name) == "PASS":
                errors.append(f"{label}: gate marked PASS before execution: {name}")
    return errors


def main() -> int:
    report: dict[str, object] = {}
    initial = build_provisional_record(initial_blocked_gates())
    provisional = build_provisional_record(provisional_gates())
    initial_errors = verify_blocked_record(initial, "initial-blocked", strict_provisional=False)
    provisional_errors = verify_blocked_record(provisional, "provisional", strict_provisional=True)
    report["initial_blocked_record"] = {
        "status": initial.get("status"),
        "readiness_declaration": initial.get("readiness_declaration"),
        "implementation_planning_100_percent_complete": initial.get("implementation_planning_100_percent_complete"),
        "first_allowed_package": initial.get("first_allowed_package"),
        "remaining_blockers": initial.get("remaining_blockers"),
        "wp_i0_001_authorized": False,
        "errors": initial_errors,
    }
    report["provisional_record"] = {
        "status": provisional.get("status"),
        "readiness_declaration": provisional.get("readiness_declaration"),
        "implementation_planning_100_percent_complete": provisional.get("implementation_planning_100_percent_complete"),
        "first_allowed_package": provisional.get("first_allowed_package"),
        "remaining_blockers": provisional.get("remaining_blockers"),
        "certificationGates": provisional.get("certificationGates"),
        "wp_i0_001_authorized": False,
        "errors": provisional_errors,
    }

    final_path = REPORTS / "final-100-percent-certification.json"
    final: dict[str, object] = {}
    if final_path.exists():
        final = json.loads(final_path.read_text(encoding="utf-8"))
    final_errors: list[str] = []
    if final.get("status") != "PASS":
        final_errors.append("final certification status is not PASS")
    if final.get("readiness_declaration") != DECLARATION:
        final_errors.append("final certification declaration is not the published PASS declaration")
    if final.get("implementation_planning_100_percent_complete") is not True:
        final_errors.append("final certification implementation_planning flag is not true")
    if final.get("first_allowed_package") != "WP-I0-001":
        final_errors.append("final certification first_allowed_package is not WP-I0-001")
    if final.get("remaining_blockers"):
        final_errors.append("final certification still has remaining blockers")
    gates = final.get("certificationGates")
    if not isinstance(gates, dict) or any(gates.get(name) != "PASS" for name in CERTIFICATION_GATES):
        final_errors.append("final certification gates are not all PASS")
    report["final_record"] = {
        "status": final.get("status"),
        "readiness_declaration": final.get("readiness_declaration"),
        "implementation_planning_100_percent_complete": final.get("implementation_planning_100_percent_complete"),
        "first_allowed_package": final.get("first_allowed_package"),
        "remaining_blockers": final.get("remaining_blockers"),
        "certificationGates": gates,
        "wp_i0_001_authorized": final.get("status") == "PASS",
        "errors": final_errors,
    }
    passing = not initial_errors and not provisional_errors and not final_errors
    report["status"] = "PASS" if passing else "FAIL"
    report["conclusion"] = (
        "PASS published only after every gate completed; every earlier persisted state "
        "remains NOT CERTIFIED / IMPLEMENTATION BLOCKED and WP-I0-001 is not authorized."
        if passing
        else "simulation detected a blocked-state or publication-order violation"
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if passing else 1


if __name__ == "__main__":
    raise SystemExit(main())
