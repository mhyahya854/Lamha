"""Render the explicitly authored Pass 1 decision spec into the v2 reviewed registry.

The spec (``semantic-plan-source/reviews/pass1-decision-spec.jsonl``) contains
one explicit decision per detected record.  This script never invents a status,
disposition, or statement; it only renders the authored values and provenance
into ``reviewed-requirement-decisions-v2.csv`` and updates the audit report's
``required_disposition`` column.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path


sys.dont_write_bytecode = True

GRAPHIFY = Path(__file__).resolve().parents[1]
SOURCE = GRAPHIFY / "semantic-plan-source"
REPORTS = GRAPHIFY / "12-semantic-implementation-plan" / "13-reports"
SPEC = SOURCE / "reviews" / "pass1-decision-spec.jsonl"
OUT = SOURCE / "reviews" / "reviewed-requirement-decisions-v2.csv"
AUDIT = REPORTS / "legacy-template-semantic-audit.csv"

sys.path.insert(0, str(GRAPHIFY / "tools"))
from write_guard import write_csv  # noqa: E402

PERMITTED_STATUSES = {
    "REVIEWED_CONFIRMED", "REVIEWED_CORRECTED", "MERGED", "RECLASSIFIED",
    "SUPERSEDED", "REVIEW_REQUIRED", "BLOCKED",
}
PERMITTED_DISPOSITIONS = {
    "REWRITE_AS_REQUIREMENT", "REWRITE_AS_ACCEPTANCE_CRITERION",
    "MERGE_INTO_PARENT", "RECLASSIFY_INFORMATIONAL", "RECLASSIFY_GLOSSARY",
    "RECLASSIFY_UI_LABEL", "RECLASSIFY_DECISION", "RECLASSIFY_CONSTRAINT",
    "SUPERSEDE_DUPLICATE", "SUPERSEDE_NON_REQUIREMENT",
    "KEEP_WITH_EXPLICIT_JUSTIFICATION",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(path.open(encoding="utf-8-sig", newline="")))


def main() -> int:
    spec_rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for line in SPEC.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        if row.get("id") == "__placeholder__":
            continue
        rid = row["id"]
        if rid in seen:
            raise ValueError(f"duplicate spec decision: {rid}")
        seen.add(rid)
        if row["d"] not in PERMITTED_DISPOSITIONS:
            raise ValueError(f"invalid disposition for {rid}: {row['d']}")
        if row["s"] not in PERMITTED_STATUSES:
            raise ValueError(f"invalid status for {rid}: {row['s']}")
        spec_rows.append(row)

    audit = read_csv(AUDIT)
    audit_by_id = {row["canonical_id"]: row for row in audit}
    requirements = read_csv(SOURCE / "requirements" / "requirements.csv")
    req_by_id = {row["canonical_id"]: row for row in requirements}
    mappings = read_csv(SOURCE / "requirements" / "requirement-mapping.csv")
    map_by_id = {row["canonical_id"]: row for row in mappings}

    missing = sorted(set(audit_by_id) - set(spec_by_id := {row["id"] for row in spec_rows}))
    unknown = sorted(set(spec_by_id) - set(audit_by_id))
    if missing:
        raise ValueError(f"detected records missing explicit decision: {missing[:20]} ... ({len(missing)} total)")
    if unknown:
        raise ValueError(f"spec decisions for unknown records: {unknown[:20]} ... ({len(unknown)} total)")

    out: list[dict[str, str]] = []
    audit_update: list[dict[str, str]] = []
    for audit_row in audit:
        rid = audit_row["canonical_id"]
        spec = next(row for row in spec_rows if row["id"] == rid)
        req = req_by_id.get(rid, {})
        previous = audit_row["current_statement"]
        final_statement = (spec.get("st") or "").strip() or previous
        classification = (spec.get("t") or "").strip() or req.get("requirement_type", "")
        acceptance = (spec.get("ac") or "").strip()
        if not acceptance and spec["d"] in {"KEEP_WITH_EXPLICIT_JUSTIFICATION", "REWRITE_AS_ACCEPTANCE_CRITERION"}:
            acceptance = final_statement
        capability = (spec.get("cap") or "").strip() or audit_row["current_capability"]
        phase = (spec.get("ph") or "").strip() or audit_row["current_phase"]
        verification = (spec.get("vm") or "").strip()
        if not verification:
            verification = req.get("verification_method", "") or acceptance or "Pass 1 reviewed acceptance criterion in reviewed-requirement-decisions-v2.csv."
        evidence = (
            "Pass 1 semantic rehabilitation; "
            f"matched=[{audit_row['matched_template_family']}]; "
            f"section={audit_row['source_section']}; "
            f"parent={audit_row['parent_requirement_id'] or 'none'}"
        )
        out.append({
            "record_id": rid,
            "original_source_text": audit_row["source_text"],
            "previous_statement": previous,
            "final_statement": final_statement,
            "final_classification": classification,
            "parent_requirement": (spec.get("par") or "").strip() or audit_row["parent_requirement_id"],
            "acceptance_criteria": acceptance,
            "capability": capability,
            "primary_phase": phase,
            "verification_method": verification,
            "review_rationale": spec.get("r", ""),
            "evidence": evidence,
            "disposition": spec["d"],
            "reviewer_type": "AI_SEMANTIC_REVIEW_PASS1",
            "review_revision": "2026-08-05-pass1-semantic-rehabilitation",
            "review_status": spec["s"],
        })
        updated = dict(audit_row)
        updated["required_disposition"] = spec["d"]
        audit_update.append(updated)

    fields = [
        "record_id", "original_source_text", "previous_statement", "final_statement",
        "final_classification", "parent_requirement", "acceptance_criteria", "capability",
        "primary_phase", "verification_method", "review_rationale", "evidence", "disposition",
        "reviewer_type", "review_revision", "review_status",
    ]
    write_csv(OUT, out, fields)
    write_csv(AUDIT, audit_update, list(audit[0]))
    print(json.dumps({
        "rendered": len(out),
        "missingDecisions": len(missing),
        "unknownIds": len(unknown),
        "statuses": {status: sum(1 for row in out if row["review_status"] == status) for status in sorted(PERMITTED_STATUSES)},
        "dispositions": {disp: sum(1 for row in out if row["disposition"] == disp) for disp in sorted(PERMITTED_DISPOSITIONS)},
        "output": str(OUT),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
