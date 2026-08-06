"""Pass 2 semantic capability/phase consistency correction.

This module is the explicit correction ledger for the Pass 2 semantic audit.
It updates the reviewed v2 requirement decisions, the canonical requirement
registry, and the phase mapping registry, then writes the full audit CSV.
It does not infer corrections from keywords alone: every changed row is listed
in EXPLICIT_CORRECTIONS or is a non-implementation record whose phase is cleared
because GLOSSARY/UI_LABEL/INFORMATIONAL/DUPLICATE records cannot own an
implementation phase.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.dont_write_bytecode = True

GRAPHIFY = Path(__file__).resolve().parents[1]
SOURCE = GRAPHIFY / "semantic-plan-source"
REVIEWS = SOURCE / "reviews"
REPORTS = GRAPHIFY / "12-semantic-implementation-plan" / "13-reports"

sys.path.insert(0, str(GRAPHIFY / "tools"))
from write_guard import write_csv  # noqa: E402


NON_IMPLEMENTATION = {"GLOSSARY", "UI_LABEL", "INFORMATIONAL", "DUPLICATE"}

# Explicit capability/phase corrections. The corrected package is decided by
# pass2_rebuild.py from the same corrected semantic meaning.
EXPLICIT_CORRECTIONS = {
    # Filesystem reveal/open actions belong to Libraries and storage in I5.
    "CAN-LAM-FOLDER-032": ("Libraries and storage", "I5"),
    "CAN-LAM-FOLDER-014": ("Libraries and storage", "I5"),
    "CAN-LAM-FOLDER-041": ("Libraries and storage", "I5"),
    # Reversible trash operations belong to Backup, trash, restore and rebuild.
    "CAN-LAM-TRASH-004": ("Backup, trash, restore and rebuild", "I13"),
    # Asset JSON authority is a sidecar write-protocol responsibility.
    "CAN-LAM-ASSET-138": ("Sidecars and metadata authority", "I3"),
    # Inspector raw-data copy/export is an asset-metadata export, not AI work.
    "CAN-LAM-ARCH-193": ("Editing", "I11"),
    # Duplicate candidate creation is duplicate-analysis work, not Review UI.
    "CAN-LAM-AI-018": ("Duplicates", "I10"),
    # Hardware-assessment library metrics are Local AI worker results.
    "CAN-LAM-ASSET-117": ("Local AI worker", "I10"),
    "CAN-LAM-ASSET-118": ("Local AI worker", "I10"),
    # Hardware-profile recording is performance measurement, not AI inference.
    "CAN-LAM-PERF-008": ("Performance and scale", "I14"),
    # Corpus/architecture/feature mapping are planning-governance obligations.
    "CAN-LAM-GOV-264": ("Planning and verification governance", "I0"),
    "CAN-LAM-GOV-265": ("Planning and verification governance", "I0"),
    "CAN-LAM-GOV-266": ("Planning and verification governance", "I0"),
}

# Corrections for active canonical rows that were not part of the Pass 1 v2
# rewrite set but still violate the same semantic rules.
EXTRA_CORRECTIONS = {
    "CAN-LAM-ASSET-147": ("Performance and scale", "I14"),
    "CAN-MISSION-I14-001": ("Performance and scale", "I14"),
    "CAN-MISSION-I14-003": ("Jobs and notifications", "I14"),
    "CAN-MISSION-I14-004": ("Performance and scale", "I14"),
    "CAN-MISSION-I15-001": ("Packaging and legacy eradication", "I15"),
    "CAN-MISSION-I15-003": ("Packaging and legacy eradication", "I15"),
    "CAN-LAM-GOV-052": ("Planning and verification governance", "I0"),
    "CAN-LAM-GOV-054": ("Planning and verification governance", "I0"),
    "CAN-LAM-GOV-165": ("Planning and verification governance", "I0"),
    "CAN-LAM-ARCH-376": ("Gallery and timeline", "I5"),
    "CAN-LAM-BACKUP-004": ("Backup, trash, restore and rebuild", "I13"),
    "CAN-LAM-FOLDER-076": ("External drives and path resilience", "I12"),
    "CAN-LAM-FOLDER-077": ("External drives and path resilience", "I12"),
}

REASONS = {
    "CAN-LAM-FOLDER-032": "Final statement is an OS file-manager reveal action with explicit no-mutation and no-root-authorization constraints.",
    "CAN-LAM-FOLDER-014": "Final statement is an OS file-manager reveal action with explicit no-mutation constraints.",
    "CAN-LAM-FOLDER-041": "Final statement is an OS file-manager reveal action with explicit no-mutation constraints.",
    "CAN-LAM-TRASH-004": "Final statement concerns reversible trash state and belongs to the trash/restore subsystem.",
    "CAN-LAM-ASSET-138": "Final statement governs read/write authority of the schema-valid Asset JSON record.",
    "CAN-LAM-ARCH-193": "Source section 20.6 Inspector capabilities and legacy Editing/WP-I11-005 evidence identify asset-metadata export, not AI worker data.",
    "CAN-LAM-AI-018": "Final statement creates duplicate candidates from local analysis; capability is Duplicates, not Review Centre.",
    "CAN-LAM-ASSET-117": "Final statement reports a library metric during hardware assessment; capability is Local AI worker.",
    "CAN-LAM-ASSET-118": "Final statement reports a library metric during hardware assessment; capability is Local AI worker.",
    "CAN-LAM-PERF-008": "Final statement records hardware profile for performance reproducibility; capability is Performance and scale.",
    "CAN-LAM-GOV-264": "Pass 1 corpus inventory is a planning-governance obligation, not product map browsing.",
    "CAN-LAM-GOV-265": "Pass 2 current-architecture mapping is a planning-governance obligation, not product map browsing.",
    "CAN-LAM-GOV-266": "Pass 3 feature mapping is a planning-governance obligation, not product map browsing.",
    "CAN-LAM-ASSET-147": "Final statement executes release performance validation and records budgets; capability is Performance and scale.",
    "CAN-MISSION-I14-001": "I14 performance validation is performance measurement, not a gallery feature.",
    "CAN-MISSION-I14-003": "I14 background-job responsiveness validation is a jobs/notifications obligation.",
    "CAN-MISSION-I14-004": "I14 cross-platform performance/accessibility evidence is performance measurement.",
    "CAN-MISSION-I15-001": "Clean-machine packaging obligation belongs to Packaging and legacy eradication.",
    "CAN-MISSION-I15-003": "Final outbound-traffic verification belongs to Packaging and legacy eradication.",
    "CAN-LAM-GOV-052": "Implementation-tracker ID integrity is a planning-governance obligation.",
    "CAN-LAM-GOV-054": "Planning-tracker edge-case recording is a planning-governance obligation.",
    "CAN-LAM-GOV-165": "Requirement-extraction identity rule is a planning-governance obligation.",
    "CAN-LAM-ARCH-376": "Timeline rendering is an Offline Library Experience behavior, not media ingestion.",
    "CAN-LAM-BACKUP-004": "Backup manifest persistence belongs to the backup subsystem, not the sidecar read/write foundation.",
    "CAN-LAM-FOLDER-076": "Cross-drive interruption and transaction recovery belong to External drives and path resilience.",
    "CAN-LAM-FOLDER-077": "Durable external-drive identity and reconnection consistency belong to External drives and path resilience.",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(path.open(encoding="utf-8-sig", newline="")))


def main() -> int:
    v2_path = REVIEWS / "reviewed-requirement-decisions-v2.csv"
    req_path = SOURCE / "requirements" / "requirements.csv"
    map_path = SOURCE / "requirements" / "requirement-mapping.csv"
    v2_rows = read_csv(v2_path)
    req_rows = read_csv(req_path)
    map_rows = read_csv(map_path)
    req_by_id = {row["canonical_id"]: row for row in req_rows}
    map_by_id = {row["canonical_id"]: row for row in map_rows}

    corrections: dict[str, tuple[str, str]] = dict(EXPLICIT_CORRECTIONS)
    corrections.update(EXTRA_CORRECTIONS)

    audit_rows: list[dict[str, str]] = []
    changed_ids: set[str] = set()

    # 1) Pass 1 v2 decisions: build corrected values and update v2/req/mapping.
    for row in v2_rows:
        rid = row["record_id"]
        req = req_by_id[rid]
        mapping = map_by_id[rid]
        current_cap = row["capability"]
        current_phase = row["primary_phase"]
        corrected_cap = current_cap
        corrected_phase = current_phase
        reason = "Confirmed consistent with source text, rewritten statement, capability, phase, and package surface."
        status = "REVIEWED_CONFIRMED"

        if row["final_classification"] in NON_IMPLEMENTATION:
            corrected_phase = ""
            reason = "Non-implementation record (GLOSSARY/UI_LABEL/INFORMATIONAL/DUPLICATE) cannot retain an implementation phase."
            status = "REVIEWED_CORRECTED"
        elif rid in corrections:
            corrected_cap, corrected_phase = corrections[rid]
            reason = REASONS[rid]
            status = "REVIEWED_CORRECTED"

        if (current_cap, current_phase) != (corrected_cap, corrected_phase):
            changed_ids.add(rid)
            row["capability"] = corrected_cap
            row["primary_phase"] = corrected_phase
            row["review_status"] = "REVIEWED_CORRECTED"
            row["review_revision"] = "2026-08-05-pass2-semantic-consistency-correction"
            row["review_rationale"] = (row.get("review_rationale", "") + " | " + reason).strip(" |")
            req["canonical_capability"] = corrected_cap
            req["primary_implementation_phase"] = corrected_phase
            mapping["canonical_capability"] = corrected_cap
            mapping["primary_implementation_phase"] = corrected_phase
            mapping["previous_capability"] = current_cap
            mapping["previous_primary_phase"] = current_phase
            mapping["mapping_rationale"] = reason
            mapping["reviewer_status"] = "REVIEWED_CORRECTED"

        audit_rows.append({
            "Canonical ID": rid,
            "Source text": row["original_source_text"],
            "Final statement": row["final_statement"],
            "Current capability": current_cap,
            "Current phase": current_phase,
            "Corrected capability": corrected_cap,
            "Corrected phase": corrected_phase,
            "Reason": reason,
            "Evidence": row["evidence"],
            "Review status": status,
        })

    # 2) Extra active rows corrected outside the v2 rewrite set.
    for rid, (corrected_cap, corrected_phase) in EXTRA_CORRECTIONS.items():
        req = req_by_id[rid]
        mapping = map_by_id[rid]
        current_cap = mapping["canonical_capability"]
        current_phase = mapping["primary_implementation_phase"]
        reason = REASONS[rid]
        req["canonical_capability"] = corrected_cap
        req["primary_implementation_phase"] = corrected_phase
        mapping["canonical_capability"] = corrected_cap
        mapping["primary_implementation_phase"] = corrected_phase
        mapping["previous_capability"] = current_cap
        mapping["previous_primary_phase"] = current_phase
        mapping["mapping_rationale"] = reason
        mapping["reviewer_status"] = "REVIEWED_CORRECTED"
        changed_ids.add(rid)
        audit_rows.append({
            "Canonical ID": rid,
            "Source text": req["source_text"],
            "Final statement": req["statement"],
            "Current capability": current_cap,
            "Current phase": current_phase,
            "Corrected capability": corrected_cap,
            "Corrected phase": corrected_phase,
            "Reason": reason,
            "Evidence": f"Source section: {req['source_section']}; legacy package: {req['legacy_work_package_id'] or 'none'}.",
            "Review status": "REVIEWED_CORRECTED",
        })

    # 3) Also clear any active canonical requirement phase that still carries a
    #    phase for a non-implementation classification (defensive sync).
    for row in req_rows:
        rid = row["canonical_id"]
        if row["requirement_type"] in NON_IMPLEMENTATION and row["primary_implementation_phase"]:
            row["primary_implementation_phase"] = ""
            if rid in map_by_id:
                map_by_id[rid]["primary_implementation_phase"] = ""
                map_by_id[rid]["reviewer_status"] = "NOT_APPLICABLE"

    write_csv(v2_path, v2_rows, list(v2_rows[0]))
    write_csv(req_path, req_rows, list(req_rows[0]))
    write_csv(map_path, map_rows, list(map_rows[0]))
    fields = [
        "Canonical ID", "Source text", "Final statement", "Current capability",
        "Current phase", "Corrected capability", "Corrected phase", "Reason",
        "Evidence", "Review status",
    ]
    audit_rows.sort(key=lambda row: row["Canonical ID"])
    write_csv(REVIEWS / "semantic-capability-phase-consistency-audit.csv", audit_rows, fields)
    write_csv(REPORTS / "semantic-capability-phase-consistency-audit.csv", audit_rows, fields)

    print(f"audit_rows={len(audit_rows)} corrected={len(changed_ids)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
