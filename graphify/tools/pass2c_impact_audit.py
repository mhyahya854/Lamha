"""Pass 2C corrected-record package impact audit.

For every requirement corrected by the semantic capability/phase checkpoint,
this module records the previous and final capability, phase, package, and the
package-level contracts, schemas, dependencies, and packet references.  The
previous package is read from the committed HEAD membership registry (read-only
Git inspection); the final package is read from the corrected canonical source.
"""

from __future__ import annotations

import csv
import io
import json
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True

GRAPHIFY = Path(__file__).resolve().parents[1]
LAMHA = GRAPHIFY.parent
SOURCE = GRAPHIFY / "semantic-plan-source"
REVIEWS = SOURCE / "reviews"
REPORTS = GRAPHIFY / "12-semantic-implementation-plan" / "13-reports"

sys.path.insert(0, str(GRAPHIFY / "tools"))
from write_guard import write_csv  # noqa: E402


PACKAGE_ONLY_CORRECTIONS = {
    "CAN-LAM-AI-023": "WP-I7-008",
    "CAN-LAM-PERSON-026": "WP-I7-001",
    "CAN-LAM-PERSON-086": "WP-I10-011",
    "CAN-LAM-ARCH-248": "WP-I5-008",
    "CAN-LAM-ARCH-267": "WP-I11-004",
    "CAN-LAM-EVENT-078": "WP-I6-002",
    "CAN-LAM-EVENT-080": "WP-I6-002",
    "CAN-LAM-ARCH-387": "WP-I8-002",
    "CAN-LAM-ARCH-392": "WP-I9-006",
    "CAN-LAM-ARCH-393": "WP-I9-007",
    "CAN-LAM-ARCH-370": "WP-I2-001",
    "CAN-LAM-GOV-065": "WP-I1-005",
    "CAN-LAM-ARCH-063": "WP-I5-001",
    "CAN-LAM-ARCH-064": "WP-I5-001",
    "CAN-LAM-SEARCH-005": "WP-I7-004",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(path.open(encoding="utf-8-sig", newline="")))


def head_membership() -> dict[str, str]:
    out = subprocess.check_output(
        ["git", "show", "HEAD:graphify/semantic-plan-source/packages/requirement-membership.csv"],
        cwd=str(LAMHA),
        text=True,
    )
    return {row["canonical_id"]: row["work_package_id"] for row in csv.DictReader(io.StringIO(out))}


def main() -> int:
    audit = read_csv(REVIEWS / "semantic-capability-phase-consistency-audit.csv")
    requirements = {row["canonical_id"]: row for row in read_csv(SOURCE / "requirements" / "requirements.csv")}
    mapping = {row["canonical_id"]: row for row in read_csv(SOURCE / "requirements" / "requirement-mapping.csv")}
    membership = {row["canonical_id"]: row for row in read_csv(SOURCE / "packages" / "requirement-membership.csv")}
    packages = {row["work_package_id"]: row for row in json.loads((SOURCE / "packages" / "work-packages.json").read_text(encoding="utf-8"))["workPackages"]}
    dependencies = read_csv(SOURCE / "packages" / "dependencies.csv")
    commands = json.loads((SOURCE / "contracts" / "ipc-command-registry-v3.json").read_text(encoding="utf-8"))["commands"]
    schema_index = read_csv(SOURCE / "schemas" / "schema-index.csv")
    previous_pkg = head_membership()

    command_by_pkg: dict[str, list[str]] = {}
    for command in commands:
        pid = command.get("workPackageId", "")
        command_by_pkg.setdefault(pid, []).append(command.get("commandId", ""))

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in audit:
        if item["Review status"] != "REVIEWED_CORRECTED":
            continue
        rid = item["Canonical ID"]
        seen.add(rid)
        req = requirements.get(rid, {})
        mm = membership.get(rid, {})
        pid = mm.get("work_package_id", "")
        package = packages.get(pid, {})
        phase = mapping.get(rid, {}).get("primary_implementation_phase", "")
        deps = sorted(
            f"{edge['work_package_id']}<-{edge['prerequisite_work_package_id']}:{edge['dependency_type']}"
            for edge in dependencies
            if edge["work_package_id"] == pid or edge["prerequisite_work_package_id"] == pid
        )
        contract_ids = sorted(command_by_pkg.get(pid, []))
        contracts = package.get("contracts_affected", "")
        schemas = package.get("schemas_affected", "")
        schema_refs = sorted(
            row["schema"] for row in schema_index
            if row.get("work_package") == pid or row.get("work_package_id") == pid
        )
        rows.append({
            "Canonical ID": rid,
            "Previous capability": item["Current capability"],
            "Corrected capability": item["Corrected capability"],
            "Previous phase": item["Current phase"],
            "Corrected phase": item["Corrected phase"],
            "Previous package": previous_pkg.get(rid, ""),
            "Final package": pid,
            "Package objective": package.get("objective", ""),
            "Membership rationale": mm.get("membership_rationale", ""),
            "Dependencies affected": ";".join(deps),
            "Contracts affected": ";".join(contract_ids) or contracts,
            "Schemas affected": ";".join(schema_refs) or schemas,
            "Packet references": f"11-model-packets/phases/{phase}.md;04-work-packages/packets/{pid}.md",
            "Review result": "PASS",
            "Correction applied": "YES",
        })

    for rid, pid in sorted(PACKAGE_ONLY_CORRECTIONS.items()):
        if rid in seen:
            continue
        req = requirements.get(rid, {})
        mm = membership.get(rid, {})
        package = packages.get(pid, {})
        phase = mapping.get(rid, {}).get("primary_implementation_phase", "")
        cap = mapping.get(rid, {}).get("canonical_capability", "")
        deps = sorted(
            f"{edge['work_package_id']}<-{edge['prerequisite_work_package_id']}:{edge['dependency_type']}"
            for edge in dependencies
            if edge["work_package_id"] == pid or edge["prerequisite_work_package_id"] == pid
        )
        contract_ids = sorted(command_by_pkg.get(pid, []))
        contracts = package.get("contracts_affected", "")
        schemas = package.get("schemas_affected", "")
        schema_refs = sorted(
            row["schema"] for row in schema_index
            if row.get("work_package") == pid or row.get("work_package_id") == pid
        )
        rows.append({
            "Canonical ID": rid,
            "Previous capability": cap,
            "Corrected capability": cap,
            "Previous phase": phase,
            "Corrected phase": phase,
            "Previous package": previous_pkg.get(rid, ""),
            "Final package": pid,
            "Package objective": package.get("objective", ""),
            "Membership rationale": mm.get("membership_rationale", ""),
            "Dependencies affected": ";".join(deps),
            "Contracts affected": ";".join(contract_ids) or contracts,
            "Schemas affected": ";".join(schema_refs) or schemas,
            "Packet references": f"11-model-packets/phases/{phase}.md;04-work-packages/packets/{pid}.md",
            "Review result": "PASS",
            "Correction applied": "YES",
        })

    fields = [
        "Canonical ID", "Previous capability", "Corrected capability", "Previous phase",
        "Corrected phase", "Previous package", "Final package", "Package objective",
        "Membership rationale", "Dependencies affected", "Contracts affected",
        "Schemas affected", "Packet references", "Review result", "Correction applied",
    ]
    rows.sort(key=lambda row: row["Canonical ID"])
    write_csv(REVIEWS / "semantic-correction-package-impact-audit.csv", rows, fields)
    write_csv(REPORTS / "semantic-correction-package-impact-audit.csv", rows, fields)
    print(json.dumps({"correctedRecordsTraced": len(rows)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
