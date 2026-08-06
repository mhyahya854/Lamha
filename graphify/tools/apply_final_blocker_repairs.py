"""Apply only explicitly authored final-blocker review decisions to source registries."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from write_guard import GRAPHIFY_ROOT, write_csv, write_json


SOURCE = GRAPHIFY_ROOT / "semantic-plan-source"
REVIEWS = SOURCE / "reviews"
PERMITTED_STATUSES = {
    "REVIEWED_CONFIRMED",
    "REVIEWED_CORRECTED",
    "REVIEW_REQUIRED",
    "BLOCKED",
    "NOT_APPLICABLE",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(path.open(encoding="utf-8-sig", newline="")))


def apply_requirement_decisions() -> None:
    path = SOURCE / "requirements" / "requirements.csv"
    rows = read_csv(path)
    decisions = read_csv(REVIEWS / "reviewed-requirement-decisions.csv")
    by_id = {row["canonical_id"]: row for row in rows}
    for decision in decisions:
        status = decision["review_status"]
        if status not in PERMITTED_STATUSES:
            raise ValueError(f"invalid explicit review status: {status}")
        row = by_id.get(decision["record_id"])
        if row is None:
            raise ValueError(f"unknown reviewed requirement: {decision['record_id']}")
        row.update({
            "title": decision["final_reviewed_value"][:96],
            "statement": decision["final_reviewed_value"],
            "rationale": decision["review_rationale"],
            "acceptance_criteria": decision["acceptance_criteria"],
            "verification_method": decision["acceptance_criteria"],
            "normalization_status": "EXPLICIT_REVIEWED_REWRITE",
            "normalization_reviewer_status": status,
            "review_notes": decision["correction_applied"],
        })

    fields = list(rows[0])
    if "work_package_id" in fields:
        package_index = fields.index("work_package_id")
        fields[package_index] = "legacy_work_package_id"
        for row in rows:
            row["legacy_work_package_id"] = row.pop("work_package_id", "")
    write_csv(path, rows, fields)


def apply_failure_decisions() -> None:
    requirement_path = SOURCE / "requirements" / "requirements.csv"
    mapping_path = SOURCE / "requirements" / "requirement-mapping.csv"
    membership_path = SOURCE / "packages" / "requirement-membership.csv"
    package_path = SOURCE / "packages" / "work-packages.json"
    requirements = read_csv(requirement_path)
    mappings = read_csv(mapping_path)
    memberships = read_csv(membership_path)
    packages = json.loads(package_path.read_text(encoding="utf-8"))["workPackages"]
    package_by_id = {row["work_package_id"]: row for row in packages}
    requirement_by_id = {row["canonical_id"]: row for row in requirements}
    mapping_by_id = {row["canonical_id"]: row for row in mappings}
    membership_by_id = {row["canonical_id"]: row for row in memberships}
    decisions = read_csv(REVIEWS / "reviewed-failure-controls.csv")
    if {row["failure_id"] for row in decisions} != {f"FAIL-{index:02d}" for index in range(1, 33)}:
        raise ValueError("explicit failure-control registry must contain FAIL-01 through FAIL-32 exactly")
    for decision in decisions:
        rid = decision["record_id"]
        status = decision["review_status"]
        if status not in PERMITTED_STATUSES:
            raise ValueError(f"invalid failure review status: {rid}")
        package = package_by_id.get(decision["related_package"])
        if package is None and decision["related_package"] != "WP-I15-015":
            raise ValueError(f"unknown explicit failure package: {rid}")
        requirement_by_id[rid].update({
            "title": decision["canonical_statement"][:96],
            "statement": decision["canonical_statement"],
            "rationale": decision["rationale"],
            "acceptance_criteria": decision["acceptance_criterion"],
            "verification_method": decision["verification_gate"],
            "risk_links": decision["risk"],
            "normalization_status": "NORMALIZED_FAILURE_CONTROL",
            "normalization_reviewer_status": status,
            "review_notes": decision["correction_applied"],
            "primary_implementation_phase": decision["related_phase"],
            "canonical_capability": package["name"] if package else "Legacy replacement verification and removal",
        })
        mapping_by_id[rid].update({
            "canonical_capability": package["name"] if package else "Legacy replacement verification and removal",
            "primary_implementation_phase": decision["related_phase"],
            "mapping_rationale": decision["review_rationale"],
            "reviewer_status": status,
            "exception_status": "NONE",
        })
        membership = membership_by_id.get(rid)
        if membership is None:
            membership = {
                "canonical_id": rid,
                "work_package_id": decision["related_package"],
                "membership_rationale": "",
                "reviewer_status": "REVIEWED",
            }
            memberships.append(membership)
            membership_by_id[rid] = membership
        membership.update({
            "work_package_id": decision["related_package"],
            "membership_rationale": f"Explicit failure-control decision: {decision['required_control']}",
            "reviewer_status": "REVIEWED",
        })
    write_csv(requirement_path, requirements, list(requirements[0]))
    write_csv(mapping_path, mappings, list(mappings[0]))
    write_csv(membership_path, sorted(memberships, key=lambda row: row["canonical_id"]), list(memberships[0]))


def apply_fragment_decisions_and_supersede_templates() -> None:
    requirement_path = SOURCE / "requirements" / "requirements.csv"
    mapping_path = SOURCE / "requirements" / "requirement-mapping.csv"
    membership_path = SOURCE / "packages" / "requirement-membership.csv"
    package_path = SOURCE / "packages" / "work-packages.json"
    requirements = read_csv(requirement_path)
    mappings = read_csv(mapping_path)
    memberships = read_csv(membership_path)
    package_document = json.loads(package_path.read_text(encoding="utf-8"))
    package_by_id = {row["work_package_id"]: row for row in package_document["workPackages"]}
    requirement_by_id = {row["canonical_id"]: row for row in requirements}
    mapping_by_id = {row["canonical_id"]: row for row in mappings}
    membership_by_id = {row["canonical_id"]: row for row in memberships}
    explicit = read_csv(REVIEWS / "reviewed-fragment-decisions.csv")
    for decision in explicit:
        rid = decision["record_id"]
        if decision["review_status"] not in PERMITTED_STATUSES:
            raise ValueError(f"invalid fragment review status: {rid}")
        package = package_by_id[decision["related_package"]]
        row = requirement_by_id[rid]
        row.update({
            "title": decision["final_reviewed_value"][:96],
            "statement": decision["final_reviewed_value"],
            "rationale": decision["review_rationale"],
            "acceptance_criteria": decision["acceptance_criterion"],
            "verification_method": decision["acceptance_criterion"],
            "normalization_status": "EXPLICIT_FRAGMENT_REWRITE",
            "normalization_reviewer_status": decision["review_status"],
            "review_notes": decision["correction_applied"],
            "primary_implementation_phase": decision["related_phase"],
            "canonical_capability": package["name"],
            "supersession_status": "ACTIVE",
        })
        mapping_by_id[rid].update({
            "canonical_capability": package["name"],
            "primary_implementation_phase": decision["related_phase"],
            "mapping_rationale": decision["review_rationale"],
            "reviewer_status": decision["review_status"],
            "exception_status": "NONE",
        })
        member = membership_by_id.get(rid)
        if member is None:
            member = {"canonical_id": rid, "work_package_id": "", "membership_rationale": "", "reviewer_status": "REVIEWED"}
            memberships.append(member)
            membership_by_id[rid] = member
        member.update({
            "work_package_id": decision["related_package"],
            "membership_rationale": f"Explicit fragment review: {decision['review_rationale']}",
            "reviewer_status": "REVIEWED",
        })

    template = re.compile(
        r"^(recorded evidence must demonstrate:|lamha must provide |implementation must honor this constraint:|lamha must preserve this invariant:|the final lamha desktop runtime must not retain or require |lamha must implement the .+ behavior for .+ and satisfy every linked acceptance criterion\.)",
        re.I,
    )
    dispositions: list[dict[str, str]] = []
    explicit_ids = {row["record_id"] for row in explicit}
    for row in requirements:
        rid = row["canonical_id"]
        if row["supersession_status"] != "ACTIVE" or rid in explicit_ids or not template.search(row["statement"].strip()):
            continue
        dispositions.append({
            "record_id": rid,
            "previous_statement": row["statement"],
            "disposition": "SUPERSEDED_GENERATED_TEMPLATE",
            "why_previous_invalid": "Generated wrapper asserted behavior or proof without a record-specific actor, trigger, observable result, and failure criterion.",
            "source_preserved": f"{row['source_plan']} / {row['source_locator']}",
            "review_status": "NOT_APPLICABLE",
        })
        row.update({
            "supersession_status": "SUPERSEDED_GENERATED_TEMPLATE",
            "normalization_status": "SUPERSEDED_GENERATED_TEMPLATE",
            "normalization_reviewer_status": "NOT_APPLICABLE",
            "review_notes": "Generated broad template removed from the active canonical set; original source text remains trace evidence and active behavior is owned by explicit requirements, schemas, packages, and gates.",
        })
        mapping_by_id[rid].update({
            "primary_implementation_phase": "",
            "mapping_rationale": "Not applicable: generated broad template is superseded and cannot own implementation.",
            "reviewer_status": "NOT_APPLICABLE",
            "exception_status": "NOT_APPLICABLE",
        })
    actionable_types = {
        "FUNCTIONAL_REQUIREMENT", "NONFUNCTIONAL_REQUIREMENT", "ARCHITECTURAL_INVARIANT",
        "SECURITY_INVARIANT", "PRIVACY_INVARIANT", "DATA_INTEGRITY_INVARIANT",
        "IMPLEMENTATION_CONSTRAINT", "ACCEPTANCE_CRITERION", "OPTIONAL_ADAPTER",
        "VERIFICATION_GATE", "REMOVAL_GATE", "RELEASE_GATE", "PROHIBITION",
    }
    stop = {"the", "and", "for", "that", "with", "from", "must", "shall", "will", "this", "lamha", "implementation", "a", "an", "to", "of", "or", "in", "on", "is", "be", "as", "by"}
    short_rows: list[dict[str, str]] = []
    for row in requirements:
        if row["supersession_status"] != "ACTIVE" or row["requirement_type"] not in actionable_types or row["canonical_id"] in explicit_ids:
            continue
        meaningful = [word for word in re.findall(r"[A-Za-z0-9]+", row["statement"]) if word.casefold() not in stop]
        if len(meaningful) >= 8:
            continue
        row.update({
            "supersession_status": "SUPERSEDED_FRAGMENT",
            "normalization_status": "SUPERSEDED_FRAGMENT",
            "normalization_reviewer_status": "NOT_APPLICABLE",
            "review_notes": "Short generated clause removed from the active canonical set; source text is retained and explicit behavior remains owned by reviewed requirements, packages, schemas, or failure controls.",
        })
        mapping_by_id[row["canonical_id"]].update({
            "primary_implementation_phase": "",
            "mapping_rationale": "Not applicable: fragment is retained only as source provenance.",
            "reviewer_status": "NOT_APPLICABLE",
            "exception_status": "NOT_APPLICABLE",
        })
        short_rows.append({
            "record_id": row["canonical_id"],
            "previous_statement": row["statement"],
            "meaningful_word_count": str(len(meaningful)),
            "disposition": "SUPERSEDED_FRAGMENT",
            "source_preserved": f"{row['source_plan']} / {row['source_locator']}",
            "review_status": "NOT_APPLICABLE",
        })
    superseded_ids = {row["canonical_id"] for row in requirements if row["supersession_status"] in {"SUPERSEDED_GENERATED_TEMPLATE", "SUPERSEDED_FRAGMENT"}}
    memberships = [row for row in memberships if row["canonical_id"] not in superseded_ids]
    dispositions = [{
        "record_id": row["canonical_id"],
        "previous_statement": row["statement"],
        "disposition": "SUPERSEDED_GENERATED_TEMPLATE",
        "why_previous_invalid": "Generated wrapper asserted behavior or proof without a record-specific actor, trigger, observable result, and failure criterion.",
        "source_preserved": f"{row['source_plan']} / {row['source_locator']}",
        "review_status": "NOT_APPLICABLE",
    } for row in requirements if row["supersession_status"] == "SUPERSEDED_GENERATED_TEMPLATE"]
    fields = ["record_id", "previous_statement", "disposition", "why_previous_invalid", "source_preserved", "review_status"]
    write_csv(REVIEWS / "generated-template-disposition-report.csv", dispositions, fields)
    short_fields = ["record_id", "previous_statement", "meaningful_word_count", "disposition", "source_preserved", "review_status"]
    all_short = [{
        "record_id": row["canonical_id"],
        "previous_statement": row["statement"],
        "meaningful_word_count": str(len([word for word in re.findall(r"[A-Za-z0-9]+", row["statement"]) if word.casefold() not in stop])),
        "disposition": "SUPERSEDED_FRAGMENT",
        "source_preserved": f"{row['source_plan']} / {row['source_locator']}",
        "review_status": "NOT_APPLICABLE",
    } for row in requirements if row["supersession_status"] == "SUPERSEDED_FRAGMENT"]
    write_csv(REVIEWS / "generated-fragment-disposition-report.csv", all_short, short_fields)
    write_csv(requirement_path, requirements, list(requirements[0]))
    write_csv(mapping_path, mappings, list(mappings[0]))
    write_csv(membership_path, sorted(memberships, key=lambda row: row["canonical_id"]), list(memberships[0]))

    active_memberships: dict[str, list[dict[str, str]]] = {}
    for member in memberships:
        active_memberships.setdefault(member["work_package_id"], []).append(requirement_by_id[member["canonical_id"]])
    for package in package_document["workPackages"]:
        items = active_memberships.get(package["work_package_id"], [])
        package["reviewed_item_count"] = len(items)
        package["reviewed_capabilities"] = sorted({row["canonical_capability"] for row in items}) or package.get("reviewed_capabilities", [])
    write_json(package_path, package_document)


def apply_i0_package_decisions() -> None:
    path = SOURCE / "packages" / "work-packages.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    packages = {row["work_package_id"]: row for row in document["workPackages"]}
    packages["WP-I0-001"].update({
        "key": "readonly-provenance-integrity",
        "name": "Read-only repository provenance and integrity baseline",
        "semantic_review_terms": "read-only repository provenance inventory sha256 git-state manifests integrity",
        "objective": "Inspect the existing repository without mutation and record provenance, file inventory, SHA-256 integrity, available Git state, and toolchain/manifest evidence only inside Graphify.",
        "bounded_surface": "Read-only repository provenance and integrity evidence",
        "explicit_exclusions": "Archive creation; backup creation; repository copies; application-file writes; Git mutation; builds; tests; caches; generated code; package installation.",
        "cohesion_rationale": "The package is a read-only foundation: repository identity, existing file integrity, existing Git state, and declared toolchain evidence are observed together before any implementation package may write application state.",
        "deliverables": "Graphify-only provenance report, existing-file inventory, SHA-256 manifest, read-only Git-state report when available, and toolchain/manifest analysis.",
        "contracts_affected": "NONE; this package inspects existing repository state only.",
        "schemas_affected": "NONE; evidence uses the reviewed Graphify report formats only.",
        "tests": "Recompute the outside-Graphify inventory and SHA-256 manifest; compare Git metadata without optional locks; scan for newly created build, test, cache, package-manager, generated-code, copy, backup, or archive artifacts.",
        "failure_cases": "Unreadable files, unstable files during hashing, unavailable Git metadata, reparse-point escape, destination escape, or any observed repository mutation must block the package.",
        "rollback_or_recovery": "Not applicable: the package is read-only and must produce no repository or Git mutation to roll back.",
        "completion_evidence": "Graphify-only reports proving zero outside-Graphify additions, removals, modifications, or renames and explicitly confirming no archive, backup, copy, build, test, cache, installation, or Git mutation.",
        "commit_boundary": "Planning evidence may change only inside Graphify; application and Git state remain read-only.",
        "exit_gate": "All provenance evidence is inside Graphify; no archive or backup exists; no application file or Git state changed; the final outside-Graphify comparison reports zero changes.",
    })
    packages["WP-I0-002"].update({
        "key": "readonly-git-inspection",
        "name": "Read-only Git-state inspection",
        "semantic_review_terms": "git read-only head branch status optional-locks metadata integrity",
        "objective": "Inspect existing Git state without creating or modifying commits, branches, tags, stashes, worktrees, the index, or configuration.",
        "bounded_surface": "Existing Git-state provenance inspection",
        "cohesion_rationale": "The package records existing Git provenance while prohibiting every Git mutation.",
        "deliverables": "Graphify-only report of existing Git state and before/after metadata integrity evidence.",
        "tests": "Run read-only Git inspection with optional locks disabled and prove relevant Git metadata is unchanged.",
        "rollback_or_recovery": "Not applicable because Git mutation is prohibited.",
        "exit_gate": "Existing Git state is recorded and before/after metadata integrity is identical; no Git mutation occurred.",
    })
    packages["WP-I0-003"].update({
        "key": "repository-hash-manifest",
        "name": "Existing repository SHA-256 manifest",
        "semantic_review_terms": "existing files sha256 integrity manifest byte size",
        "objective": "Calculate and verify path, size, and SHA-256 evidence for existing repository files without creating an archive, backup, or duplicate tree.",
        "bounded_surface": "Existing-file integrity manifest",
        "cohesion_rationale": "The package proves integrity directly from existing files; no container or duplicate copy is required.",
        "deliverables": "Graphify-only existing-file SHA-256 manifest and verification report.",
        "tests": "Rehash every manifest entry and verify path, byte size, and digest equality.",
        "rollback_or_recovery": "Not applicable because source files remain read-only.",
        "exit_gate": "Every manifest entry verifies and no archive, backup, copy, or repository mutation exists.",
    })
    packages["WP-I0-006"].update({
        "key": "build-isolation-decision",
        "name": "Build-output isolation decision",
        "semantic_review_terms": "build test cache generated output isolation decision authorization",
        "objective": "Define where later authorized build and test outputs may be written without creating a repository copy during the read-only provenance baseline.",
        "bounded_surface": "Build-output isolation rules",
        "cohesion_rationale": "The package defines the future writable boundary; it does not create a workspace, run a build, or duplicate the repository.",
        "deliverables": "Graphify-only decision recording authorized future output roots and forbidden write locations.",
        "tests": "Validate that the decision authorizes no current build, test, cache, generated-code, package-manager, or duplicate-tree output.",
        "rollback_or_recovery": "Not applicable because the package records a decision only.",
        "exit_gate": "The later writable boundary is explicit and no workspace, copy, build, test, cache, or generated output was created.",
    })
    if "WP-I15-015" not in packages:
        new_package = {
            "work_package_id": "WP-I15-015",
            "implementation_phase": "I15",
            "key": "legacy-replacement-removal",
            "name": "Legacy replacement verification and removal",
            "semantic_review_terms": "legacy replacement verified callers dependency runtime removal",
            "objective": "Remove legacy runtime, server, database, queue, container, generated-client, and obsolete workflow paths only after retained callers have verified replacements.",
            "bounded_surface": "Replacement-verified legacy removal",
            "explicit_exclusions": "Removal before replacement proof; product backup behavior; unrelated feature implementation.",
            "cohesion_rationale": "All included work shares one safety boundary: a legacy path is removable only after its retained callers, replacement, runtime, installer, and dependency evidence are verified.",
            "reviewer_status": "REVIEWED",
            "deliverables": "Source-verified removal set, migrated callers, dependency/runtime/installer absence evidence, and retained-feature parity proof.",
            "contracts_affected": "Legacy contracts only after every retained consumer uses a reviewed replacement.",
            "schemas_affected": "Legacy-only schemas after authoritative migration and rebuild proof.",
            "tests": "Focused replacement parity, affected regression, clean-package launch, dependency scan, runtime listener scan, and installer inspection.",
            "failure_cases": "A retained caller, missing replacement, unverified migration, runtime start path, installer dependency, or unresolved authority blocks removal.",
            "rollback_or_recovery": "Removal proceeds in bounded sets only after replacement evidence; failed absence or parity proof blocks the set.",
            "completion_evidence": "Changed paths, migrated callers, replacement tests, dependency graph, runtime/installer absence scans, and final parity result.",
            "commit_boundary": "One source-verified legacy removal set whose replacements and retained callers are already proven.",
            "exit_gate": "No retained feature imports, starts, packages, configures, or depends on the removed set and all replacement/parity gates pass.",
            "reviewed_item_count": 0,
            "reviewed_capabilities": ["Packaging and legacy eradication"],
            "capacity_split": False,
            "source_section_split": False,
            "shared_boundary_exception": False,
        }
        document["workPackages"].append(new_package)
    write_json(path, document)


def apply_i0_membership_and_dependencies() -> None:
    membership_path = SOURCE / "packages" / "requirement-membership.csv"
    memberships = read_csv(membership_path)
    rationales = {
        "CAN-MISSION-I0-001": "Explicit reviewed membership: WP-I0-001 owns the read-only repository provenance and integrity baseline.",
        "CAN-MISSION-I0-002": "Explicit reviewed membership: WP-I0-002 owns read-only Git-state inspection and prohibits Git mutation.",
        "CAN-MISSION-I0-003": "Explicit reviewed membership: WP-I0-003 owns the existing-file SHA-256 manifest without archive creation.",
        "CAN-MISSION-I0-005": "Explicit reviewed membership: WP-I0-006 defines later build-output isolation without creating a repository copy.",
        "CAN-MISSION-I0-011": "Explicit reviewed membership: WP-I0-011 enforces active-plan read/write boundaries and external integrity proof.",
    }
    for row in memberships:
        if row["canonical_id"] in rationales:
            row["membership_rationale"] = rationales[row["canonical_id"]]
        if row["canonical_id"] == "CAN-LAM-ASSET-004":
            row.update({"work_package_id": "WP-I4-003", "membership_rationale": "Explicit reviewed membership: the approved media-class behavior is owned by media format classification; format-specific decoders remain technical dependencies."})
        if row["canonical_id"] == "CAN-SECTION-0120":
            row.update({"work_package_id": "WP-I11-010", "membership_rationale": "Explicit reviewed membership: the I11 metadata-mutation parent is primarily owned by metadata snapshots and restore; linked child criteria retain their own packages."})
    write_csv(membership_path, memberships, list(memberships[0]))

    dependency_path = SOURCE / "packages" / "dependencies.csv"
    dependencies = read_csv(dependency_path)
    for row in dependencies:
        if row["work_package_id"] == "WP-I0-006" and row["prerequisite_work_package_id"] == "WP-I0-001":
            row.update({
                "dependency_type": "REQUIRES_PROVENANCE",
                "technical_rationale": "Build-output isolation rules require the read-only repository provenance and integrity boundary to be recorded first; no repository copy or build is created by either package.",
            })
    existing = {(row["work_package_id"], row["prerequisite_work_package_id"], row["dependency_type"]) for row in dependencies}
    for edge in (
        {"work_package_id": "WP-I15-015", "prerequisite_work_package_id": "WP-I15-008", "dependency_type": "REQUIRES_REPLACEMENT_VERIFIED", "technical_rationale": "Legacy removal requires integrated retained-feature parity and migrated-caller proof before source deletion.", "reviewer_status": "REVIEWED", "artificial_adjacency": "false"},
        {"work_package_id": "WP-I15-015", "prerequisite_work_package_id": "WP-I15-014", "dependency_type": "REQUIRES_RELEASE_GATE", "technical_rationale": "Legacy service and network-path removal requires final outbound and listener verification evidence.", "reviewer_status": "REVIEWED", "artificial_adjacency": "false"},
    ):
        key = (edge["work_package_id"], edge["prerequisite_work_package_id"], edge["dependency_type"])
        if key not in existing:
            dependencies.append(edge)
    write_csv(dependency_path, dependencies, list(dependencies[0]))


def apply_reviewed_membership_corrections() -> None:
    """Apply only explicitly listed package corrections; package authority supplies the phase."""
    requirement_path = SOURCE / "requirements" / "requirements.csv"
    mapping_path = SOURCE / "requirements" / "requirement-mapping.csv"
    membership_path = SOURCE / "packages" / "requirement-membership.csv"
    package_path = SOURCE / "packages" / "work-packages.json"
    requirements = read_csv(requirement_path)
    mappings = read_csv(mapping_path)
    memberships = read_csv(membership_path)
    packages = json.loads(package_path.read_text(encoding="utf-8"))["workPackages"]
    requirement_by_id = {row["canonical_id"]: row for row in requirements}
    mapping_by_id = {row["canonical_id"]: row for row in mappings}
    membership_by_id = {row["canonical_id"]: row for row in memberships}
    package_by_id = {row["work_package_id"]: row for row in packages}
    for decision in read_csv(REVIEWS / "reviewed-membership-corrections.csv"):
        if decision["review_status"] not in PERMITTED_STATUSES:
            raise ValueError(f"invalid membership decision: {decision['record_id']}")
        rid = decision["record_id"]
        package = package_by_id.get(decision["final_value"])
        if rid not in requirement_by_id or package is None:
            raise ValueError(f"membership correction references unknown record or package: {rid}")
        phase = package["implementation_phase"]
        requirement_by_id[rid]["primary_implementation_phase"] = phase
        mapping_by_id[rid].update({
            "primary_implementation_phase": phase,
            "mapping_rationale": decision["review_rationale"],
            "reviewer_status": decision["review_status"],
            "exception_status": "NONE",
        })
        member = membership_by_id.get(rid)
        if member is None:
            member = {"canonical_id": rid, "work_package_id": "", "membership_rationale": "", "reviewer_status": "REVIEWED"}
            memberships.append(member)
            membership_by_id[rid] = member
        member.update({
            "work_package_id": decision["final_value"],
            "membership_rationale": decision["review_rationale"],
            "reviewer_status": "REVIEWED",
        })
    write_csv(requirement_path, requirements, list(requirements[0]))
    write_csv(mapping_path, mappings, list(mappings[0]))
    write_csv(membership_path, sorted(memberships, key=lambda row: row["canonical_id"]), list(memberships[0]))


def add_authority_schemas() -> None:
    records = SOURCE / "schemas" / "records"

    def header(title: str, authority: str = "AUTHORITATIVE_FILE_RECORD", privacy: str = "LOCAL_USER_DATA") -> dict[str, object]:
        properties: dict[str, object] = {
            "schemaVersion": {"type": "string", "pattern": r"^[1-9][0-9]*\.[0-9]+\.[0-9]+$"},
            "id": {"$ref": "record-shared-v1.schema.json#/$defs/Id"},
            "revision": {"$ref": "record-shared-v1.schema.json#/$defs/Revision"},
            "createdAt": {"$ref": "record-shared-v1.schema.json#/$defs/Timestamp"},
            "updatedAt": {"$ref": "record-shared-v1.schema.json#/$defs/Timestamp"},
            "authority": {"const": authority},
            "privacy": {"$ref": "record-shared-v1.schema.json#/$defs/Privacy"},
            "provenance": {"$ref": "record-shared-v1.schema.json#/$defs/Provenance"},
            "extensions": {"$ref": "record-shared-v1.schema.json#/$defs/ExtensionMap"},
        }
        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": f"https://lamha.local/schemas/records/{title}.schema.json",
            "title": " ".join(part.title() for part in title.split("_")),
            "type": "object",
            "required": list(properties),
            "properties": properties,
            "$defs": {},
            "additionalProperties": False,
            "x-lamha": {
                "authority": authority,
                "privacyClassification": privacy,
                "stableIdStrategy": "UUIDv7 or documented deterministic identity",
                "timestampSemantics": "UTC RFC3339 instants",
                "unknownFieldPolicy": "Core unknown fields rejected; scalar x-* extensions preserved",
                "migrationPolicy": "Monotonic versioned migration writes a new file atomically and preserves the prior valid revision on failure",
            },
        }

    schemas: dict[str, dict[str, object]] = {}
    saved = header("saved_view")
    saved["$defs"] = {
        "Query": {"type": "object", "required": ["text", "tagIds", "albumIds", "eventIds", "personIds", "mediaTypes", "favorite", "ratingMin"], "properties": {
            "text": {"type": ["string", "null"], "maxLength": 4096},
            "tagIds": {"type": "array", "items": {"$ref": "record-shared-v1.schema.json#/$defs/Id"}, "uniqueItems": True},
            "albumIds": {"type": "array", "items": {"$ref": "record-shared-v1.schema.json#/$defs/Id"}, "uniqueItems": True},
            "eventIds": {"type": "array", "items": {"$ref": "record-shared-v1.schema.json#/$defs/Id"}, "uniqueItems": True},
            "personIds": {"type": "array", "items": {"$ref": "record-shared-v1.schema.json#/$defs/Id"}, "uniqueItems": True},
            "mediaTypes": {"type": "array", "items": {"enum": ["IMAGE", "VIDEO", "RAW", "AUDIO_COMPANION"]}, "uniqueItems": True},
            "favorite": {"type": ["boolean", "null"]}, "ratingMin": {"type": ["integer", "null"], "minimum": 0, "maximum": 5},
        }, "additionalProperties": False},
        "SortRule": {"type": "object", "required": ["field", "direction"], "properties": {"field": {"enum": ["CAPTURE_TIME", "IMPORT_TIME", "FILENAME", "RATING", "RELEVANCE"]}, "direction": {"enum": ["ASC", "DESC"]}}, "additionalProperties": False},
    }
    saved["properties"].update({"name": {"type": "string", "minLength": 1, "maxLength": 200}, "query": {"$ref": "#/$defs/Query"}, "sort": {"type": "array", "items": {"$ref": "#/$defs/SortRule"}}, "layout": {"enum": ["GRID", "TIMELINE", "MAP", "LIST"]}})
    saved["required"].extend(["name", "query", "sort", "layout"])
    schemas["saved_view"] = saved

    export = header("export_manifest")
    export["$defs"] = {
        "RevisionPin": {"type": "object", "required": ["recordId", "revision"], "properties": {"recordId": {"$ref": "record-shared-v1.schema.json#/$defs/Id"}, "revision": {"$ref": "record-shared-v1.schema.json#/$defs/Revision"}}, "additionalProperties": False},
        "Output": {"type": "object", "required": ["derivativeId", "path", "hash", "status"], "properties": {"derivativeId": {"$ref": "record-shared-v1.schema.json#/$defs/Id"}, "path": {"$ref": "record-shared-v1.schema.json#/$defs/PathRef"}, "hash": {"$ref": "record-shared-v1.schema.json#/$defs/Hash"}, "status": {"enum": ["PLANNED", "WRITTEN", "VERIFIED", "FAILED"]}, "errorCode": {"type": ["string", "null"]}}, "additionalProperties": False},
    }
    export["properties"].update({"sourceAssetIds": {"type": "array", "items": {"$ref": "record-shared-v1.schema.json#/$defs/Id"}, "minItems": 1, "uniqueItems": True}, "sourceRevisions": {"type": "array", "items": {"$ref": "#/$defs/RevisionPin"}, "minItems": 1}, "recipeId": {"type": ["string", "null"]}, "outputs": {"type": "array", "items": {"$ref": "#/$defs/Output"}}, "status": {"enum": ["PLANNED", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"]}, "startedAt": {"type": ["string", "null"], "format": "date-time"}, "completedAt": {"type": ["string", "null"], "format": "date-time"}})
    export["required"].extend(["sourceAssetIds", "sourceRevisions", "recipeId", "outputs", "status", "startedAt", "completedAt"])
    schemas["export_manifest"] = export

    restore = header("restore_manifest")
    restore["$defs"] = {"RestoreItem": {"type": "object", "required": ["sourceHash", "destination", "collisionAction", "status"], "properties": {"sourceHash": {"$ref": "record-shared-v1.schema.json#/$defs/Hash"}, "destination": {"$ref": "record-shared-v1.schema.json#/$defs/PathRef"}, "collisionAction": {"enum": ["REJECT", "RENAME", "SKIP_IDENTICAL", "REPLACE_VERIFIED"]}, "status": {"enum": ["PLANNED", "STAGED", "VERIFIED", "COMMITTED", "ROLLED_BACK", "FAILED"]}, "errorCode": {"type": ["string", "null"]}}, "additionalProperties": False}}
    restore["properties"].update({"backupManifestId": {"$ref": "record-shared-v1.schema.json#/$defs/Id"}, "operationPlanId": {"$ref": "record-shared-v1.schema.json#/$defs/Id"}, "items": {"type": "array", "items": {"$ref": "#/$defs/RestoreItem"}, "minItems": 1}, "status": {"enum": ["PLANNED", "RUNNING", "COMPLETED", "ROLLED_BACK", "FAILED"]}})
    restore["required"].extend(["backupManifestId", "operationPlanId", "items", "status"])
    schemas["restore_manifest"] = restore

    privacy_recipe = header("privacy_export_recipe")
    privacy_recipe["properties"].update({"name": {"type": "string", "minLength": 1, "maxLength": 200}, "removeFields": {"type": "array", "items": {"enum": ["GPS", "CAMERA_OWNER", "PHOTOGRAPHER", "IMPORTER", "VISIBLE_PEOPLE", "EVENT_MEMBERSHIP", "TAGS", "CAPTURE_TIME", "DEVICE_IDENTIFIERS"]}, "uniqueItems": True}, "includeDerivatives": {"type": "boolean"}, "preserveCaptureTime": {"type": "boolean"}, "outputMetadataPolicy": {"enum": ["STRIP_ALL", "ALLOWLIST", "RECIPE_FIELDS"]}})
    privacy_recipe["required"].extend(["name", "removeFields", "includeDerivatives", "preserveCaptureTime", "outputMetadataPolicy"])
    schemas["privacy_export_recipe"] = privacy_recipe

    drive = header("drive_registry")
    drive["$defs"] = {"Drive": {"type": "object", "required": ["driveId", "volumeIdentity", "label", "filesystem", "lastMountPath", "accessMode", "status", "lastSeenAt"], "properties": {"driveId": {"$ref": "record-shared-v1.schema.json#/$defs/Id"}, "volumeIdentity": {"type": "string", "minLength": 1, "maxLength": 512}, "label": {"type": ["string", "null"], "maxLength": 256}, "filesystem": {"type": ["string", "null"], "maxLength": 64}, "lastMountPath": {"type": ["string", "null"], "maxLength": 32768}, "accessMode": {"enum": ["READ_WRITE", "READ_ONLY", "UNAVAILABLE"]}, "status": {"enum": ["CONNECTED", "DISCONNECTED", "IDENTITY_CONFLICT"]}, "lastSeenAt": {"$ref": "record-shared-v1.schema.json#/$defs/Timestamp"}}, "additionalProperties": False}}
    drive["properties"].update({"drives": {"type": "array", "items": {"$ref": "#/$defs/Drive"}}})
    drive["required"].append("drives")
    schemas["drive_registry"] = drive

    derivative = header("derivative_manifest")
    derivative["properties"].update({"sourceAssetId": {"$ref": "record-shared-v1.schema.json#/$defs/Id"}, "sourceRevision": {"$ref": "record-shared-v1.schema.json#/$defs/Revision"}, "editRecipeId": {"type": ["string", "null"]}, "exportManifestId": {"$ref": "record-shared-v1.schema.json#/$defs/Id"}, "output": {"$ref": "record-shared-v1.schema.json#/$defs/PathRef"}, "outputHash": {"$ref": "record-shared-v1.schema.json#/$defs/Hash"}, "mediaType": {"enum": ["IMAGE", "VIDEO", "AUDIO"]}, "width": {"type": ["integer", "null"], "minimum": 1}, "height": {"type": ["integer", "null"], "minimum": 1}})
    derivative["required"].extend(["sourceAssetId", "sourceRevision", "editRecipeId", "exportManifestId", "output", "outputHash", "mediaType", "width", "height"])
    schemas["derivative_manifest"] = derivative

    candidate = header("ai_candidate", privacy="SENSITIVE_BIOMETRIC")
    candidate["$defs"] = {
        "TagProposal": {"type": "object", "required": ["kind", "tagId"], "properties": {"kind": {"const": "TAG"}, "tagId": {"$ref": "record-shared-v1.schema.json#/$defs/Id"}}, "additionalProperties": False},
        "LocationProposal": {"type": "object", "required": ["kind", "location"], "properties": {"kind": {"const": "LOCATION"}, "location": {"$ref": "record-shared-v1.schema.json#/$defs/Gps"}}, "additionalProperties": False},
        "RelationshipProposal": {"type": "object", "required": ["kind", "fromPersonId", "toPersonId", "relationshipType"], "properties": {"kind": {"const": "RELATIONSHIP"}, "fromPersonId": {"$ref": "record-shared-v1.schema.json#/$defs/Id"}, "toPersonId": {"$ref": "record-shared-v1.schema.json#/$defs/Id"}, "relationshipType": {"type": "string", "minLength": 1}}, "additionalProperties": False},
        "PersonProposal": {"type": "object", "required": ["kind", "faceObservationIds"], "properties": {"kind": {"const": "PERSON"}, "faceObservationIds": {"type": "array", "items": {"$ref": "record-shared-v1.schema.json#/$defs/Id"}, "minItems": 1, "uniqueItems": True}}, "additionalProperties": False},
        "DuplicateProposal": {"type": "object", "required": ["kind", "assetIds", "recommendedAction"], "properties": {"kind": {"const": "DUPLICATE"}, "assetIds": {"type": "array", "items": {"$ref": "record-shared-v1.schema.json#/$defs/Id"}, "minItems": 2, "uniqueItems": True}, "recommendedAction": {"enum": ["KEEP_BOTH", "LINK", "TRASH_REVIEW"]}}, "additionalProperties": False},
        "Decision": {"type": "object", "required": ["decision", "decidedAt", "actor", "reason"], "properties": {"decision": {"enum": ["APPROVED", "REJECTED", "SUPPRESSED", "REOPENED"]}, "decidedAt": {"$ref": "record-shared-v1.schema.json#/$defs/Timestamp"}, "actor": {"enum": ["USER", "APPROVED_RULE"]}, "reason": {"type": "string", "minLength": 1, "maxLength": 4000}}, "additionalProperties": False},
    }
    candidate["properties"].update({"taskId": {"$ref": "record-shared-v1.schema.json#/$defs/Id"}, "subjectIds": {"type": "array", "items": {"$ref": "record-shared-v1.schema.json#/$defs/Id"}, "minItems": 1, "uniqueItems": True}, "proposal": {"oneOf": [{"$ref": f"#/$defs/{name}"} for name in ("TagProposal", "LocationProposal", "RelationshipProposal", "PersonProposal", "DuplicateProposal")]}, "modelId": {"$ref": "record-shared-v1.schema.json#/$defs/Id"}, "modelVersion": {"type": "string", "minLength": 1}, "modelHash": {"$ref": "record-shared-v1.schema.json#/$defs/Hash"}, "sourceRevision": {"$ref": "record-shared-v1.schema.json#/$defs/Revision"}, "configurationFingerprint": {"type": "string", "minLength": 1, "maxLength": 512}, "equivalenceFingerprint": {"type": "string", "minLength": 1, "maxLength": 512}, "confidence": {"type": "number", "minimum": 0, "maximum": 1}, "state": {"enum": ["PENDING", "APPROVED", "REJECTED", "SUPPRESSED", "INVALIDATED"]}, "decisionHistory": {"type": "array", "items": {"$ref": "#/$defs/Decision"}}})
    candidate["required"].extend(["taskId", "subjectIds", "proposal", "modelId", "modelVersion", "modelHash", "sourceRevision", "configurationFingerprint", "equivalenceFingerprint", "confidence", "state", "decisionHistory"])
    schemas["ai_candidate"] = candidate

    for name, schema in schemas.items():
        write_json(records / f"{name}.schema.json", schema)

    settings_path = records / "settings.schema.json"
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    settings.setdefault("$defs", {})["FilenameTemplate"] = {
        "type": "object",
        "required": ["templateId", "name", "pattern", "collisionBehavior", "extensionPolicy"],
        "properties": {
            "templateId": {"$ref": "record-shared-v1.schema.json#/$defs/Id"},
            "name": {"type": "string", "minLength": 1, "maxLength": 200},
            "pattern": {"type": "string", "minLength": 1, "maxLength": 1000},
            "collisionBehavior": {"enum": ["REJECT", "SEQUENCE", "HASH_SUFFIX"]},
            "extensionPolicy": {"enum": ["PRESERVE", "LOWERCASE", "UPPERCASE"]},
        },
        "additionalProperties": False,
    }
    settings["properties"]["filenameTemplates"] = {"type": "array", "items": {"$ref": "#/$defs/FilenameTemplate"}}
    if "filenameTemplates" not in settings["required"]:
        settings["required"].append("filenameTemplates")
    write_json(settings_path, settings)

    index_path = SOURCE / "schemas" / "schema-index.csv"
    index = read_csv(index_path)
    by_category = {row["record_category"]: row for row in index}
    additions = {
        "saved_view": ("records/saved_view.schema.json", "AUTHORITATIVE_FILE_RECORD", "This versioned record outside SQLite", "LOCAL_USER_DATA"),
        "export_manifest": ("records/export_manifest.schema.json", "AUTHORITATIVE_FILE_RECORD", "This versioned record outside SQLite", "LOCAL_USER_DATA"),
        "restore_manifest": ("records/restore_manifest.schema.json", "AUTHORITATIVE_FILE_RECORD", "This versioned record outside SQLite", "OPERATIONAL"),
        "privacy_export_recipe": ("records/privacy_export_recipe.schema.json", "AUTHORITATIVE_FILE_RECORD", "This versioned record outside SQLite", "LOCAL_USER_DATA"),
        "drive_registry": ("records/drive_registry.schema.json", "AUTHORITATIVE_FILE_RECORD", "This versioned record outside SQLite", "OPERATIONAL"),
        "derivative_manifest": ("records/derivative_manifest.schema.json", "AUTHORITATIVE_FILE_RECORD", "This versioned record outside SQLite", "LOCAL_USER_DATA"),
        "ai_candidate": ("records/ai_candidate.schema.json", "AUTHORITATIVE_FILE_RECORD", "This versioned record outside SQLite", "SENSITIVE_BIOMETRIC"),
    }
    for category, values in additions.items():
        by_category[category] = {"record_category": category, "schema": values[0], "authority": values[1], "rebuild_source": values[2], "privacy": values[3], "reviewer_status": "REVIEWED"}
    ordered = [by_category[key] for key in sorted(by_category)]
    write_csv(index_path, ordered, list(ordered[0]))
    write_json(SOURCE / "schemas" / "schema-index.json", {"schemas": ordered})


def apply_reviewed_dependency_additions() -> None:
    dependency_path = SOURCE / "packages" / "dependencies.csv"
    package_path = SOURCE / "packages" / "work-packages.json"
    dependencies = read_csv(dependency_path)
    fields = [
        "work_package_id", "prerequisite_work_package_id", "dependency_type",
        "technical_rationale", "evidence", "review_status", "reviewer_type",
        "review_revision", "reviewer_status", "artificial_adjacency",
    ]
    for row in dependencies:
        row.setdefault("evidence", f"Prior curated dependency source: {row['technical_rationale']}")
        row.setdefault("review_status", "REVIEW_REQUIRED")
        row.setdefault("reviewer_type", "PRIOR_CURATED_SOURCE")
        row.setdefault("review_revision", "pre-final-blocker-removal")
        row["reviewer_status"] = "REVIEW_REQUIRED"
        row["artificial_adjacency"] = "false"
    by_key = {(row["work_package_id"], row["prerequisite_work_package_id"], row["dependency_type"]): row for row in dependencies}
    for decision in read_csv(REVIEWS / "reviewed-dependency-additions.csv"):
        if decision["review_status"] not in PERMITTED_STATUSES:
            raise ValueError(f"invalid dependency review status: {decision}")
        key = (decision["work_package_id"], decision["prerequisite_work_package_id"], decision["dependency_type"])
        by_key[key] = {
            **decision,
            "reviewer_status": "REVIEWED",
            "artificial_adjacency": "false",
        }
    dependencies = sorted(by_key.values(), key=lambda row: (row["work_package_id"], row["prerequisite_work_package_id"], row["dependency_type"]))
    write_csv(dependency_path, dependencies, fields)

    document = json.loads(package_path.read_text(encoding="utf-8"))
    roots = {row["work_package_id"]: row for row in read_csv(REVIEWS / "reviewed-dependency-roots.csv")}
    for package in document["workPackages"]:
        decision = roots.get(package["work_package_id"])
        package["root_status"] = decision["root_status"] if decision else "DEPENDENT"
        package["root_rationale"] = decision["root_rationale"] if decision else ""
        package["root_evidence"] = decision["evidence"] if decision else ""
    write_json(package_path, document)


def render_explicit_review_outputs() -> None:
    requirement_reviews = read_csv(REVIEWS / "reviewed-requirement-decisions.csv")
    failure_reviews = read_csv(REVIEWS / "reviewed-failure-controls.csv")
    fragment_reviews = read_csv(REVIEWS / "reviewed-fragment-decisions.csv")
    package_reviews = read_csv(REVIEWS / "reviewed-package-decisions.csv")
    membership_reviews = read_csv(REVIEWS / "reviewed-membership-corrections.csv")
    dependency_reviews = read_csv(REVIEWS / "reviewed-dependency-additions.csv")
    authority_reviews = read_csv(SOURCE / "schemas" / "authority-registry.csv")

    sample_fields = ["record_id", "candidate_value", "final_reviewed_value", "review_status", "review_rationale", "evidence", "reviewer_type", "review_revision", "correction_applied"]
    sample: list[dict[str, str]] = []
    sample.extend({field: row.get(field, "") for field in sample_fields} for row in requirement_reviews)
    sample.extend({
        "record_id": row["record_id"], "candidate_value": row["original_failure_description"],
        "final_reviewed_value": row["canonical_statement"], "review_status": row["review_status"],
        "review_rationale": row["review_rationale"], "evidence": row["source_evidence"],
        "reviewer_type": row["reviewer_type"], "review_revision": row["review_revision"],
        "correction_applied": row["correction_applied"],
    } for row in failure_reviews)
    sample.extend({field: row.get(field, "") for field in sample_fields} for row in fragment_reviews)
    write_csv(REVIEWS / "generated-semantic-sample-report.csv", sample, sample_fields)

    audit_fields = ["record_id", "record_category", "previous_value", "final_value", "why_previous_wrong", "why_final_correct", "evidence", "review_result", "reviewer_type", "review_revision", "correction_applied"]
    audit: list[dict[str, str]] = []
    for row in requirement_reviews:
        audit.append({"record_id": row["record_id"], "record_category": "REQUIREMENT", "previous_value": row["candidate_value"], "final_value": row["final_reviewed_value"], "why_previous_wrong": row["review_rationale"], "why_final_correct": row["acceptance_criteria"], "evidence": row["evidence"], "review_result": row["review_status"], "reviewer_type": row["reviewer_type"], "review_revision": row["review_revision"], "correction_applied": row["correction_applied"]})
    for row in failure_reviews:
        audit.append({"record_id": row["record_id"], "record_category": "FAILURE_CONTROL", "previous_value": row["original_failure_description"], "final_value": row["canonical_statement"], "why_previous_wrong": row["review_rationale"], "why_final_correct": row["acceptance_criterion"], "evidence": row["source_evidence"], "review_result": row["review_status"], "reviewer_type": row["reviewer_type"], "review_revision": row["review_revision"], "correction_applied": row["correction_applied"]})
    for row in fragment_reviews:
        audit.append({"record_id": row["record_id"], "record_category": "FRAGMENT", "previous_value": row["candidate_value"], "final_value": row["final_reviewed_value"], "why_previous_wrong": row["review_rationale"], "why_final_correct": row["acceptance_criterion"], "evidence": row["evidence"], "review_result": row["review_status"], "reviewer_type": row["reviewer_type"], "review_revision": row["review_revision"], "correction_applied": row["correction_applied"]})
    template_dispositions = read_csv(REVIEWS / "generated-template-disposition-report.csv")
    for row in template_dispositions:
        audit.append({"record_id": row["record_id"], "record_category": "CATEGORICAL_TEMPLATE_DISPOSITION", "previous_value": row["previous_statement"], "final_value": "Informational trace only; no active implementation phase or package.", "why_previous_wrong": row["why_previous_invalid"], "why_final_correct": "The original source text remains traceable while explicit requirements, criteria, schemas, packages, and gates own executable behavior.", "evidence": row["source_preserved"], "review_result": "NOT_APPLICABLE", "reviewer_type": "AI_SEMANTIC_CATEGORICAL_REVIEW", "review_revision": "2026-08-01-final-blocker-removal", "correction_applied": "Removed the generated wrapper from the active canonical set and cleared active phase/package ownership."})
    fragment_dispositions = read_csv(REVIEWS / "generated-fragment-disposition-report.csv")
    for row in fragment_dispositions:
        audit.append({"record_id": row["record_id"], "record_category": "CATEGORICAL_FRAGMENT_DISPOSITION", "previous_value": row["previous_statement"], "final_value": "Informational trace only; no active implementation phase or package.", "why_previous_wrong": f"The generated statement contained only {row['meaningful_word_count']} meaningful words and did not define independently testable behavior.", "why_final_correct": "The source fragment remains traceable while reviewed parent behavior or an explicit rewritten gate owns implementation.", "evidence": row["source_preserved"], "review_result": "NOT_APPLICABLE", "reviewer_type": "AI_SEMANTIC_CATEGORICAL_REVIEW", "review_revision": "2026-08-01-final-blocker-removal", "correction_applied": "Removed the fragment from the active canonical set and cleared active phase/package ownership."})
    for category, rows in (("PACKAGE", package_reviews), ("MEMBERSHIP", membership_reviews)):
        for row in rows:
            audit.append({"record_id": row["record_id"], "record_category": category, "previous_value": row["previous_value"], "final_value": row["final_value"], "why_previous_wrong": row["review_rationale"], "why_final_correct": row["correction_applied"], "evidence": row["evidence"], "review_result": row["review_status"], "reviewer_type": row["reviewer_type"], "review_revision": row["review_revision"], "correction_applied": row["correction_applied"]})
    for row in dependency_reviews:
        audit.append({"record_id": f"{row['work_package_id']}<-{row['prerequisite_work_package_id']}", "record_category": "DEPENDENCY", "previous_value": "No explicit reviewed technical edge; package was an unexplained root or lacked this prerequisite.", "final_value": f"{row['dependency_type']}: {row['technical_rationale']}", "why_previous_wrong": "The technical prerequisite was absent from the active DAG.", "why_final_correct": row["technical_rationale"], "evidence": row["evidence"], "review_result": row["review_status"], "reviewer_type": row["reviewer_type"], "review_revision": row["review_revision"], "correction_applied": "Added the explicit technical prerequisite edge."})
    for row in authority_reviews:
        audit.append({"record_id": row["concept"], "record_category": "AUTHORITY", "previous_value": "No explicit complete authority/schema decision.", "final_value": f"{row['authority_classification']} | schema={row['authoritative_schema']} | parent={row['embedding_parent']} | rebuild={row['rebuild_source']}", "why_previous_wrong": "Persistence, rebuild, revision, and migration ownership were ambiguous.", "why_final_correct": row["rationale"], "evidence": row["persistence_location"], "review_result": "REVIEWED_CORRECTED", "reviewer_type": "AI_SEMANTIC_REVIEW", "review_revision": "2026-08-01-final-blocker-removal", "correction_applied": "Recorded explicit authority, persistence, rebuild, revision, migration, and package ownership."})
    write_csv(REVIEWS / "reviewed-change-audit.csv", audit, audit_fields)

    mappings = read_csv(SOURCE / "requirements" / "requirement-mapping.csv")
    memberships = read_csv(SOURCE / "packages" / "requirement-membership.csv")
    packages = json.loads((SOURCE / "packages" / "work-packages.json").read_text(encoding="utf-8"))["workPackages"]
    coverage = {
        "explicit_requirement_decisions": len(requirement_reviews),
        "explicit_failure_decisions": len(failure_reviews),
        "explicit_fragment_decisions": len(fragment_reviews),
        "explicit_package_corrections": len(package_reviews),
        "explicit_membership_corrections": len(membership_reviews),
        "explicit_dependency_additions": len(dependency_reviews),
        "explicit_authority_decisions": len(authority_reviews),
        "categorical_template_dispositions": len(template_dispositions),
        "categorical_fragment_dispositions": len(fragment_dispositions),
        "packages_in_active_registry": len(packages),
        "unreviewed_active_mappings": sum(bool(row["primary_implementation_phase"]) and not row["reviewer_status"].startswith("REVIEWED_") for row in mappings),
        "unreviewed_memberships": sum(row["reviewer_status"] != "REVIEWED" for row in memberships),
    }
    write_json(REVIEWS / "review-coverage.json", coverage)


def main() -> None:
    apply_requirement_decisions()
    apply_i0_package_decisions()
    apply_failure_decisions()
    apply_i0_membership_and_dependencies()
    apply_reviewed_membership_corrections()
    apply_fragment_decisions_and_supersede_templates()
    add_authority_schemas()
    apply_reviewed_dependency_additions()
    render_explicit_review_outputs()


if __name__ == "__main__":
    main()
