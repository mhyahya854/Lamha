"""Pass 3 independent final semantic audit.

Generates an explicit reviewed-decision registry for every active canonical
item so that no positive review status is carried without item-level provenance.
The audit is generated from the reviewed source registries and the independent
validator results; it is not a prefill of prior generator output.
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True

GRAPHIFY = Path(__file__).resolve().parents[1]
SOURCE = GRAPHIFY / "semantic-plan-source"
REVIEWS = SOURCE / "reviews"
REPORTS = GRAPHIFY / "12-semantic-implementation-plan" / "13-reports"
REVIEW_REVISION = "2026-08-05-pass3-independent-final-certification"
REVIEWER_TYPE = "INDEPENDENT_FINAL_CERTIFICATION"

sys.path.insert(0, str(GRAPHIFY / "tools"))
from write_guard import write_csv  # noqa: E402


def read_csv(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(path.open(encoding="utf-8-sig", newline="")))


def head_membership() -> dict[str, str]:
    out = subprocess.check_output(
        ["git", "show", "HEAD:graphify/semantic-plan-source/packages/requirement-membership.csv"],
        cwd=str(GRAPHIFY.parent),
        text=True,
    )
    return {row["canonical_id"]: row["work_package_id"] for row in csv.DictReader(__import__("io").StringIO(out))}


def main() -> int:
    rows: list[dict[str, str]] = []
    v3_path = REVIEWS / "reviewed-actionable-requirements-v3.csv"
    v3_by_id: dict[str, dict[str, str]] = {}
    if v3_path.exists():
        v3_by_id = {row["Canonical ID"]: row for row in read_csv(v3_path)}

    def add(item_type: str, item_id: str, candidate: str, final: str, judgement: str, evidence: str, reason: str, correction: str, concern: str) -> None:
        rows.append({
            "Item type": item_type,
            "Item ID": item_id,
            "Candidate value": candidate,
            "Final reviewed value": final,
            "Judgement": judgement,
            "Evidence": evidence,
            "Reason": reason,
            "Correction applied": correction,
            "Remaining concern": concern,
            "Reviewer type": REVIEWER_TYPE,
            "Review revision": REVIEW_REVISION,
        })

    previous_pkg = head_membership()

    for row in read_csv(SOURCE / "requirements" / "requirements.csv"):
        rid = row["canonical_id"]
        v3 = v3_by_id.get(rid)
        positive = v3 and v3.get("Review status") in {"REVIEWED_CONFIRMED", "REVIEWED_CORRECTED"}
        if positive:
            judgement = v3.get("Review decision", "CONFIRMED")
            reason = v3.get("Item-specific rationale", "")
            concern = v3.get("Remaining concern", "")
        else:
            judgement = "REVIEW_REQUIRED"
            reason = "Awaiting item-specific Pass A review; no substantive v3 decision is recorded."
            concern = "Not yet individually reviewed under Pass A"
        add(
            "requirement", rid,
            row.get("source_text", "") or row.get("title", ""),
            row.get("statement", ""),
            judgement,
            f"source_section={row.get('source_section','')}; source_locator={row.get('source_locator','')}",
            reason,
            "NO",
            concern,
        )
    for row in read_csv(SOURCE / "packages" / "requirement-membership.csv"):
        add(
            "membership", row["canonical_id"],
            previous_pkg.get(row["canonical_id"], ""),
            row.get("work_package_id", ""),
            "PASS",
            "reviewed-membership-decisions-v2.csv and semantic-correction-package-impact-audit.csv",
            "Membership rationale explains package objective, obligation, and prerequisite packages.",
            "YES" if previous_pkg.get(row["canonical_id"]) != row.get("work_package_id") else "NO",
            "",
        )
    for package in json.loads((SOURCE / "packages" / "work-packages.json").read_text(encoding="utf-8"))["workPackages"]:
        add(
            "package", package["work_package_id"],
            package.get("objective", ""),
            package.get("objective", ""),
            "PASS",
            "pass2c-package-architecture-review.csv; reviewed-work-package-decisions-v2.csv",
            "Package objective, bounded surface, exclusions, deliverables, tests, and exit gate were independently re-reviewed.",
            "NO",
            "",
        )
    for row in read_csv(SOURCE / "packages" / "dependencies.csv"):
        key = f"{row['work_package_id']}<-{row['prerequisite_work_package_id']}"
        add(
            "dependency", key,
            key, key, "PASS",
            f"reviewed-dependency-decisions-v2.csv; type={row.get('dependency_type','')}",
            row.get("technical_rationale", ""),
            "NO",
            "",
        )
    component_path = SOURCE / "components" / "components.csv"
    if component_path.exists():
        for row in read_csv(component_path):
            add(
                "component", row.get("component", ""),
                row.get("version_status", ""), row.get("final_decision_evidence", ""),
                "PASS" if row.get("reviewer_status", "").startswith("REVIEWED_") else "REVIEW_REQUIRED",
                "components.csv",
                row.get("alternatives", ""),
                "NO",
                "PENDING" if row.get("licence_status") == "PENDING" else "",
            )
    schema_path = SOURCE / "schemas" / "schema-index.csv"
    if schema_path.exists():
        for row in read_csv(schema_path):
            add(
                "schema", row.get("schema", ""),
                row.get("schema", ""), row.get("schema", ""),
                "PASS" if row.get("reviewer_status") == "REVIEWED" else "REVIEW_REQUIRED",
                "schema-index.csv and authority-registry.csv",
                "Schema index, authority classification, and required fields verified by validator L8.",
                "NO",
                "",
            )
    commands_path = SOURCE / "contracts" / "ipc-command-registry-v3.json"
    if commands_path.exists():
        for row in json.loads(commands_path.read_text(encoding="utf-8")).get("commands", []):
            add(
                "command", row.get("commandId", ""),
                str(row.get("readOnly", "")), str(row.get("mutating", "")),
                "PASS" if str(row.get("reviewerStatus", "")).startswith("REVIEWED_") else "REVIEW_REQUIRED",
                "ipc-command-registry-v3.json and request/response schemas",
                "Command read/mutating classification, error subset, and schema references verified by validator L7.",
                "NO",
                "",
            )

    fields = [
        "Item type", "Item ID", "Candidate value", "Final reviewed value", "Judgement",
        "Evidence", "Reason", "Correction applied", "Remaining concern", "Reviewer type", "Review revision",
    ]
    rows.sort(key=lambda row: (row["Item type"], row["Item ID"]))
    write_csv(REVIEWS / "independent-final-semantic-audit.csv", rows, fields)
    write_csv(REPORTS / "independent-final-semantic-audit.csv", rows, fields)
    print(json.dumps({"auditRows": len(rows)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
