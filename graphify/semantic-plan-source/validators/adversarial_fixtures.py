"""Eighty-four negative fixtures proving every final-blocker regression is rejected."""

from __future__ import annotations

import importlib.util
import copy
import json
import sys
import tempfile
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

    v2_rewrite = {
        "record_id": "FIX-PASS1",
        "disposition": "REWRITE_AS_REQUIREMENT",
        "review_status": "REVIEWED_CORRECTED",
    }
    family = requirement_row(
        "FIX-PASS1",
        "When the local worker processes GPS for the fixture, it must return a typed candidate carrying model provenance.",
        "IMPLEMENTATION_CONSTRAINT",
    )
    family_errors = validator.check_pass1_semantics(
        [family], {"FIX-PASS1": {"primary_implementation_phase": "I10"}}, [v2_rewrite]
    )

    nav = requirement_row(
        "FIX-PASS1",
        "When Open person is used, the system must create a new person record.",
        "FUNCTIONAL_REQUIREMENT",
    )
    nav["source_text"] = "Open person"
    nav_errors = validator.check_pass1_semantics(
        [nav], {"FIX-PASS1": {"primary_implementation_phase": "I7"}}, [v2_rewrite]
    )

    legal = requirement_row(
        "FIX-PASS1",
        "When the local worker processes AI model licences for the fixture, it must return a typed candidate.",
        "IMPLEMENTATION_CONSTRAINT",
    )
    legal["source_text"] = "AI model licences"
    legal_errors = validator.check_pass1_semantics(
        [legal], {"FIX-PASS1": {"primary_implementation_phase": "I1"}}, [v2_rewrite]
    )

    perf = requirement_row(
        "FIX-PASS1",
        "When a configured library encounters Large-library optimization, Rust must apply authorized-root and access-mode rules and expose the resulting state.",
        "IMPLEMENTATION_CONSTRAINT",
    )
    perf["source_text"] = "Large-library optimization"
    perf_errors = validator.check_pass1_semantics(
        [perf], {"FIX-PASS1": {"primary_implementation_phase": "I14"}}, [v2_rewrite]
    )

    menu = requirement_row(
        "FIX-PASS1",
        "When the Cancel button is exercised in Settings, Lamha must handle the complete behavior.",
        "FUNCTIONAL_REQUIREMENT",
    )
    menu["source_text"] = "Cancel button"
    menu_errors = validator.check_pass1_semantics(
        [menu], {"FIX-PASS1": {"primary_implementation_phase": "I3"}}, [v2_rewrite]
    )

    unsourced = requirement_row("FIX-UNSOURCED", "When a fixture runs, the system must return a typed result.")
    unsourced["normalization_reviewer_status"] = "REVIEWED_CORRECTED"
    unsourced_errors = validator.check_v2_status_sourcing([unsourced], [], {"FIX-UNSOURCED"})

    with tempfile.TemporaryDirectory() as tmp:
        fake_report = Path(tmp)
        (fake_report / "template-report.md").write_text("# Template report\n\nTemplate matches: 0\n", encoding="utf-8")
        zero_errors = validator.check_zero_template_claim(fake_report)

    missing_verification = requirement_row("FIX-PASS1", "When a fixture runs, the system must return a typed result.")
    missing_verification["verification_method"] = ""
    verification_errors = validator.check_pass1_semantics(
        [missing_verification], {"FIX-PASS1": {"primary_implementation_phase": "I4"}}, [v2_rewrite]
    )

    def pkg(pid: str, name: str, phase: str, caps: list[str] | None = None) -> dict[str, object]:
        return {
            "work_package_id": pid,
            "implementation_phase": phase,
            "name": name,
            "objective": name,
            "bounded_surface": name,
            "reviewed_capabilities": caps or [],
            "reviewer_status": "REVIEWED",
            "root_status": "NOT_ROOT",
            "root_rationale": "",
            "root_evidence": "",
            "capacity_split": False,
            "source_section_split": False,
        }

    def req_row(rid: str, statement: str, cap: str = "Fixture validation") -> dict[str, str]:
        return {
            "canonical_id": rid,
            "statement": statement,
            "requirement_type": "FUNCTIONAL_REQUIREMENT",
            "supersession_status": "ACTIVE",
            "canonical_capability": cap,
            "normalization_reviewer_status": "REVIEWED_CORRECTED",
            "acceptance_criteria": "",
            "verification_method": "fixture",
        }

    open_person = req_row("FIX-OPEN-PERSON", "When Open person is invoked, Lamha must load and display the person profile.", "People and faces")
    open_person_pkg = pkg("WP-FIX-MUT", "Person identity mutation", "I7")
    p2_open_person = validator.check_pass2_package_semantics(
        [open_person_pkg],
        [{"canonical_id": "FIX-OPEN-PERSON", "work_package_id": "WP-FIX-MUT", "membership_rationale": "Specific rationale for the fixture.", "reviewer_status": "REVIEWED"}],
        [open_person],
        {"FIX-OPEN-PERSON": {"primary_implementation_phase": "I7"}},
        [],
    )

    open_event = req_row("FIX-OPEN-EVENT", "When Open event is invoked, Lamha must load and display the event.", "Events and organization")
    open_event_pkg = pkg("WP-FIX-EV", "Event plan mutation", "I6")
    p2_open_event = validator.check_pass2_package_semantics(
        [open_event_pkg],
        [{"canonical_id": "FIX-OPEN-EVENT", "work_package_id": "WP-FIX-EV", "membership_rationale": "Specific rationale for the fixture.", "reviewer_status": "REVIEWED"}],
        [open_event],
        {"FIX-OPEN-EVENT": {"primary_implementation_phase": "I6"}},
        [],
    )

    licensing = req_row("FIX-LICENSING", "AI model licences must be inventoried with attribution and redistribution review.", "Legal and rebranding")
    licensing_pkg = pkg("WP-FIX-AI", "Local AI worker inference", "I10")
    p2_licensing = validator.check_pass2_package_semantics(
        [licensing_pkg],
        [{"canonical_id": "FIX-LICENSING", "work_package_id": "WP-FIX-AI", "membership_rationale": "Specific rationale for the fixture.", "reviewer_status": "REVIEWED"}],
        [licensing],
        {"FIX-LICENSING": {"primary_implementation_phase": "I10"}},
        [],
    )

    large_lib = req_row("FIX-LARGE", "Large-library optimization must define measurable performance budgets.", "Performance and scale")
    large_pkg = pkg("WP-FIX-ACC", "Accessibility semantics", "I14")
    p2_large = validator.check_pass2_package_semantics(
        [large_pkg],
        [{"canonical_id": "FIX-LARGE", "work_package_id": "WP-FIX-ACC", "membership_rationale": "Specific rationale for the fixture.", "reviewer_status": "REVIEWED"}],
        [large_lib],
        {"FIX-LARGE": {"primary_implementation_phase": "I14"}},
        [],
    )

    mixed_members = [
        req_row("FIX-M-NAV", "When Open folder is used, the viewer must reveal the path.", "Libraries and storage"),
        req_row("FIX-M-MUT", "When a mutation runs, the system must persist the value.", "Local data authority"),
        req_row("FIX-M-PERF", "The benchmark must measure latency and throughput.", "Performance and scale"),
        req_row("FIX-M-LEGAL", "Third-party licences must be recorded with attribution.", "Legal and rebranding"),
    ]
    mixed_pkg = pkg("WP-FIX-MIX", "Mixed navigation mutation performance legal surface", "I5", ["Libraries and storage", "Local data authority", "Performance and scale", "Legal and rebranding"])
    mixed_membership = [
        {"canonical_id": row["canonical_id"], "work_package_id": "WP-FIX-MIX", "membership_rationale": f"Specific rationale for {row['canonical_id']}.", "reviewer_status": "REVIEWED"}
        for row in mixed_members
    ]
    p2_mixed = validator.check_pass2_package_semantics(
        [mixed_pkg], mixed_membership, mixed_members,
        {row["canonical_id"]: {"primary_implementation_phase": "I5"} for row in mixed_members},
        [],
    )

    title_pkg = pkg("WP-FIX-TITLE", "Production implementation for fixtures", "I5")
    p2_title = validator.check_pass2_package_semantics(
        [title_pkg],
        [{"canonical_id": "FIX-OPEN-PERSON", "work_package_id": "WP-FIX-TITLE", "membership_rationale": "Specific rationale for the fixture.", "reviewer_status": "REVIEWED"}],
        [open_person],
        {"FIX-OPEN-PERSON": {"primary_implementation_phase": "I7"}},
        [],
    )

    generic_membership = validator.check_pass2_package_semantics(
        [pkg("WP-FIX-GEN", "Cohesive surface", "I5")],
        [{"canonical_id": "FIX-OPEN-PERSON", "work_package_id": "WP-FIX-GEN", "membership_rationale": "The requirement is implemented by the bounded X surface.", "reviewer_status": "REVIEWED"}],
        [open_person],
        {"FIX-OPEN-PERSON": {"primary_implementation_phase": "I5"}},
        [],
    )

    adjacency_edges = [{
        "work_package_id": "WP-FIX-B", "prerequisite_work_package_id": "WP-FIX-A",
        "dependency_type": "REQUIRES_SCHEMA", "technical_rationale": "previous package in the array order",
        "evidence": "", "review_status": "REVIEWED_CONFIRMED", "artificial_adjacency": "true",
    }]
    adjacency_errors = validator.check_dependency_records([pkg("WP-FIX-A", "A", "I3"), pkg("WP-FIX-B", "B", "I3")], adjacency_edges)

    missing_schema_edges = [
        {"work_package_id": "WP-FIX-LEAF", "prerequisite_work_package_id": "WP-FIX-ROOT", "dependency_type": "REQUIRES_SCHEMA", "technical_rationale": "Explicit technical prerequisite.", "evidence": "evidence", "review_status": "REVIEWED_CONFIRMED", "artificial_adjacency": "false"}
    ]
    missing_schema_errors = validator.check_dependency_records(
        [pkg("WP-FIX-ROOT", "Root", "I4", ["Fixture validation"]), pkg("WP-FIX-LEAF", "Leaf", "I4", ["Fixture validation"])],
        missing_schema_edges,
    )

    root_pkg = pkg("WP-FIX-ROOT2", "Unexplained root", "I0")
    root_pkg["root_status"] = "TRUE_ROOT"
    root_errors = validator.check_dependency_records([root_pkg], [])

    phase_reqs = [req_row("FIX-PHASE", "When the fixture runs, the system must return a typed result.")]
    phase_pkgs = [pkg("WP-FIX-PKG", "Phase mismatch package", "I5", ["Fixture validation"])]
    phase_membership = [{"canonical_id": "FIX-PHASE", "work_package_id": "WP-FIX-PKG", "reviewer_status": "REVIEWED"}]
    phase_errors = validator.check_phase_package_consistency(
        phase_reqs, {"FIX-PHASE": {"primary_implementation_phase": "I4", "canonical_capability": "Fixture validation"}},
        phase_pkgs, phase_membership,
    )

    removal_pkg = pkg("WP-FIX-REM", "Legacy removal", "I15")
    removal_errors = validator.check_pass2_package_semantics(
        [removal_pkg],
        [{"canonical_id": "FIX-OPEN-PERSON", "work_package_id": "WP-FIX-REM", "membership_rationale": "Specific rationale for the fixture.", "reviewer_status": "REVIEWED"}],
        [open_person],
        {"FIX-OPEN-PERSON": {"primary_implementation_phase": "I15"}},
        [],
    )

    open_folder = req_row("FIX-OPEN-FOLDER", "When Open in folder is invoked, Lamha must reveal the asset's physical path in the OS file manager without moving files.", "Local AI worker")
    open_folder["source_text"] = "Open in folder"
    open_folder["source_section"] = "20.6 Inspector capabilities"
    open_folder["requirement_type"] = "ACCEPTANCE_CRITERION"
    open_folder["parent_requirement_id"] = "FIX-PARENT"
    sem_open_folder = validator.check_semantic_capability_phase_consistency(
        [open_folder],
        {"FIX-OPEN-FOLDER": {"canonical_capability": "Local AI worker", "primary_implementation_phase": "I10"}},
        [], [], [], [],
    )

    raw = req_row("FIX-RAW", "When raw data is copied or exported, Lamha must produce a copy of the local source data with provenance and leave the original unchanged.", "Local AI worker")
    raw["source_text"] = "Copy/export raw data"
    raw["source_section"] = "20.6 Inspector capabilities"
    sem_raw = validator.check_semantic_capability_phase_consistency(
        [raw],
        {"FIX-RAW": {"canonical_capability": "Local AI worker", "primary_implementation_phase": "I10"}},
        [], [], [], [],
    )

    perfval = req_row("FIX-PERFVAL", "Before release, Lamha performance validation must execute declared 10,000-, 50,000-, and 100,000-asset workloads and report latency and throughput.", "Asset viewer")
    perfval["source_section"] = "38. Performance and Scale"
    sem_perfval = validator.check_semantic_capability_phase_consistency(
        [perfval],
        {"FIX-PERFVAL": {"canonical_capability": "Asset viewer", "primary_implementation_phase": "I14"}},
        [], [], [], [],
    )

    planning = req_row("FIX-PLAN", "Pass 1 must map all meaningful code and exclusions and must not declare the map complete while exclusions remain.", "Map and location")
    planning["source_section"] = "Pass 1 — Corpus inventory"
    sem_planning = validator.check_semantic_capability_phase_consistency(
        [planning],
        {"FIX-PLAN": {"canonical_capability": "Map and location", "primary_implementation_phase": "I5"}},
        [], [], [], [],
    )

    nonact = req_row("FIX-GLOSS", "Glossary is a definition.", "GLOSSARY")
    nonact["requirement_type"] = "GLOSSARY"
    nonact["source_section"] = "11. People"
    sem_nonact = validator.check_semantic_capability_phase_consistency(
        [nonact],
        {"FIX-GLOSS": {"canonical_capability": "People and faces", "primary_implementation_phase": "I7"}},
        [], [], [], [],
    )

    corrected_old_pkg = req_row("CAN-LAM-FOLDER-032", "When Open in folder is invoked, Lamha must reveal the asset's physical path in the OS file manager without moving files.", "Libraries and storage")
    corrected_old_pkg["source_text"] = "Open in folder"
    corrected_old_pkg["source_section"] = "20.6 Inspector capabilities"
    corrected_old_pkg["requirement_type"] = "ACCEPTANCE_CRITERION"
    corrected_old_pkg["parent_requirement_id"] = "FIX-PARENT"
    sem_old_pkg = validator.check_semantic_capability_phase_consistency(
        [corrected_old_pkg],
        {"CAN-LAM-FOLDER-032": {"canonical_capability": "Libraries and storage", "primary_implementation_phase": "I5"}},
        [{"canonical_id": "CAN-LAM-FOLDER-032", "work_package_id": "WP-I10-002"}],
        [pkg("WP-I10-002", "Private local worker transport", "I10")],
        [], [],
    )

    rationale_errors = validator.check_membership_rationale_quality(
        [{
            "canonical_id": "FIX-RATIONAL",
            "work_package_id": "WP-FIX-GEN2",
            "membership_rationale": "WP-FIX-GEN2 implements the bounded X surface; FIX-RATIONAL belongs here because its reviewed statement is the behavior that surface executes.",
        }],
        [pkg("WP-FIX-GEN2", "Cohesive surface", "I5")],
        [req_row("FIX-RATIONAL", "When X runs, the system must persist a typed value.")],
    )

    large_pkg_fixture = pkg("WP-FIX-LARGE2", "Large surface", "I5")
    large_pkg_fixture["reviewed_item_count"] = "21"
    large_coverage_errors = validator.check_large_package_review_coverage([large_pkg_fixture], [])

    cycle_edges = [
        {"work_package_id": "WP-FIX-C1", "prerequisite_work_package_id": "WP-FIX-C2", "dependency_type": "REQUIRES_SCHEMA", "technical_rationale": "Explicit technical prerequisite.", "evidence": "evidence", "review_status": "REVIEWED_CONFIRMED", "artificial_adjacency": "false"},
        {"work_package_id": "WP-FIX-C2", "prerequisite_work_package_id": "WP-FIX-C1", "dependency_type": "REQUIRES_SCHEMA", "technical_rationale": "Explicit technical prerequisite.", "evidence": "evidence", "review_status": "REVIEWED_CONFIRMED", "artificial_adjacency": "false"},
    ]
    cycle_errors = validator.check_dependency_records([pkg("WP-FIX-C1", "C1", "I3"), pkg("WP-FIX-C2", "C2", "I3")], cycle_edges)

    with tempfile.TemporaryDirectory() as tmp2:
        fake_plan = Path(tmp2)
        packet_dir = fake_plan / "04-work-packages" / "packets"
        packet_dir.mkdir(parents=True)
        (packet_dir / "WP-FIX-PKT.md").write_text("# WP-FIX-PKT\n", encoding="utf-8")
        packet_errors = validator.check_packet_membership_currency(
            [pkg("WP-FIX-PKT", "Pkt", "I5")],
            [{"canonical_id": "FIX-MEMBER", "work_package_id": "WP-FIX-PKT"}],
            fake_plan,
        )

    execution_claim_errors = validator.check_l7_l8_execution_claim(False, {
        "levels": [
            {"level": "L7_IPC_CONTRACTS", "status": "PASS"},
            {"level": "L8_AUTHORITY_RECORDS_AND_SQLITE", "status": "PASS"},
        ]
    })

    component_errors = validator.check_component_records([{
        "component": "FIX-COMP", "owning_phase": "", "decision_package": "",
        "blocking_work_package": "", "required_before_packages": "", "version_status": "",
        "licence_status": "", "redistribution_status": "", "platform_impact": "",
        "packaging_impact": "", "alternatives": "", "final_decision_evidence": "", "reviewer_status": "",
    }], [])

    sqlite_ref_errors = validator.check_sqlite_references(
        "CREATE TABLE a(id INTEGER PRIMARY KEY); CREATE TABLE b(id INTEGER REFERENCES missing(id));"
    )

    superseded_handoff_errors = validator.check_handoff_text("Phase 2 first package is WP-I2-001.")

    determinism_errors = validator.check_determinism_evidence("hash-a", "hash-b")

    readiness_errors = validator.check_persisted_readiness_declaration(
        {"status": "PASS", "implementation_ready": True, "first_allowed_package": "WP-I0-001", "remaining_blockers": [], "final_package_hash": "hash"},
        "IMPLEMENTATION-READY PLANNING COMPLETE \u2014 I0 MAY BEGIN",
        {"firstCompletePackageHash": "hash"},
    )

    missing_v3_errors = validator.check_v3_requirement_ledger(
        [requirement_row("FIX-REQ", "When the fixture runs, the system must return a typed result.")],
        {"FIX-REQ": {"primary_implementation_phase": "I5"}},
        [],
    )

    generic_v3_errors = validator.check_v3_requirement_ledger(
        [requirement_row("FIX-REQ", "When the fixture runs, the system must return a typed result.")],
        {"FIX-REQ": {"primary_implementation_phase": "I5"}},
        [{
            "Canonical ID": "FIX-REQ", "Review status": "REVIEWED_CONFIRMED",
            "Final reviewed statement": "When the fixture runs, the system must return a typed result.",
            "Verification method": "fixture", "Item-specific rationale": "Reviewed.",
            "Actor or subsystem": "fixture", "Observable result": "typed result", "Acceptance criteria": "given when then",
        }],
    )

    id_only_v3_errors = validator.check_v3_requirement_ledger(
        [requirement_row("FIX-REQ", "When the fixture runs, the system must return a typed result.")],
        {"FIX-REQ": {"primary_implementation_phase": "I5"}},
        [{
            "Canonical ID": "FIX-REQ", "Review status": "REVIEWED_CONFIRMED",
            "Final reviewed statement": "", "Verification method": "", "Item-specific rationale": "",
            "Actor or subsystem": "", "Observable result": "", "Acceptance criteria": "",
        }],
    )

    with tempfile.TemporaryDirectory() as tmp3:
        fake_tools = Path(tmp3)
        (fake_tools / "pass3_independent_semantic_audit.py").write_text(
            "for row in rows:\n    row[\"reviewer_status\"] = \"REVIEWED\"\n",
            encoding="utf-8",
        )
        allowlist_errors = validator.check_active_scripts_for_automatic_certification(fake_tools)

    empty_member_errors = validator.check_pass_b_independent_evidence([], [], [], [], [])
    empty_contract_errors = validator.check_pass_b_independent_evidence([{}], [], [], [], [])
    empty_test_errors = validator.check_pass_b_independent_evidence([{}], [{}], [], [], [])
    missing_i3_errors = validator.check_pass_b_independent_evidence(
        [],
        [{"Package ID": "X", "Verification status": "VERIFIED", "Evidence": "source", "Item-specific rationale": "a"*50}],
        [{"Package ID": "X", "Verification status": "VERIFIED", "Evidence": "source", "Item-specific rationale": "a"*50}],
        [{"Package ID": "X", "Verification status": "VERIFIED", "Evidence": "source", "Item-specific rationale": "a"*50}],
        [{"Package ID": "X", "Verification status": "VERIFIED", "Evidence": "source", "Item-specific rationale": "a"*50}],
    )
    # Missing WP-I3-001 genuine member reassessment is represented by an
    # empty member ledger; the member ledger must contain all WP-I3-001 members.

    def component_row(**overrides) -> dict[str, str]:
        base = {
            "component": "FIX-COMP", "final_status": "SELECTED", "version_status": "RESOLVED",
            "licence_status": "APPROVED", "redistribution_status": "BUNDLED_SOURCE",
            "decision_package": "WP-I0-001", "version_rule": "pinned from lockfile",
            "reason": "a" * 60, "consumer_packages": "WP-I0-001",
        }
        base.update(overrides)
        return base

    edge = [{"work_package_id": "WP-I0-001", "prerequisite_work_package_id": "WP-I0-001"}]
    c_pending = validator.check_component_licence_completeness([component_row(final_status="PENDING")], edge)
    c_licence = validator.check_component_licence_completeness([component_row(licence_status="PENDING")], edge)
    c_redist = validator.check_component_licence_completeness([component_row(redistribution_status="")], edge)
    c_decision = validator.check_component_licence_completeness([component_row(decision_package="")], edge)
    c_version = validator.check_component_licence_completeness([component_row(version_rule="")], edge)
    c_generic = validator.check_component_licence_completeness([component_row(reason="Reviewed.")], edge)
    c_consumer = validator.check_component_licence_completeness([component_row(consumer_packages="WP-I2-001")], edge)
    c_rejected = validator.check_component_licence_completeness([component_row(final_status="REJECTED", consumer_packages="WP-I2-001")], edge)

    am_req = requirement_row("CAN-LAM-AI-090", "Lamha MUST NOT prevent a stronger compatible model due to slow estimates.", "ACCEPTANCE_CRITERION")
    am_membership = [{"canonical_id": "CAN-LAM-AI-090", "work_package_id": "WP-I10-003"}]
    am_components = [{"component": "ONNX Runtime", "model_selection_rule": "stronger model remains manually selectable"}]
    am_amendment = {"contract_concepts": ["estimated_duration", "estimated_memory", "estimated_storage", "user_override", "scheduled_start", "pause_on_battery", "selected_scope", "hard_block_reason", "insufficient", "storage", "runtime", "checksum", "licensing", "silent", "quantized", "provenance", "invalidation"]}
    with tempfile.TemporaryDirectory() as tmp4:
        fake_plan = Path(tmp4)
        (fake_plan / "13-reports").mkdir(parents=True)
        (fake_plan / "13-reports" / "ai-model-override-amendment.json").write_text(json.dumps(am_amendment), encoding="utf-8")
        am_full = validator.check_ai_model_override_amendment([am_req], am_membership, am_components, fake_plan)
        am_missing_req = validator.check_ai_model_override_amendment([], am_membership, am_components, fake_plan)
        am_short_stmt = requirement_row("CAN-LAM-AI-090", "Lamha may recommend a model.", "ACCEPTANCE_CRITERION")
        am_missing_phrase = validator.check_ai_model_override_amendment([am_short_stmt], am_membership, am_components, fake_plan)
        am_no_accept = dict(am_req); am_no_accept["acceptance_criteria"] = ""
        am_missing_accept = validator.check_ai_model_override_amendment([am_no_accept], am_membership, am_components, fake_plan)
        am_no_verify = dict(am_req); am_no_verify["verification_method"] = ""
        am_missing_verify = validator.check_ai_model_override_amendment([am_no_verify], am_membership, am_components, fake_plan)
        am_missing_membership = validator.check_ai_model_override_amendment([am_req], [], am_components, fake_plan)
        am_missing_artifact = validator.check_ai_model_override_amendment([am_req], am_membership, am_components, Path(tmp4) / "nope")
        am_missing_component_rule = validator.check_ai_model_override_amendment([am_req], am_membership, [{"component": "Face model/runtime", "model_selection_rule": ""}], fake_plan)
        am_bad_artifact = {"contract_concepts": []}
        (fake_plan / "13-reports" / "ai-model-override-amendment.json").write_text(json.dumps(am_bad_artifact), encoding="utf-8")
    am_missing_concepts = validator.check_ai_model_override_amendment([am_req], am_membership, am_components, fake_plan)

    def valid_amendment():
        return {
            "contract_concepts": ["selected_model_id","recommended_model_id","selection_source","user_override","compatibility_status","hard_block_reason","estimated_duration","estimated_memory","estimated_storage","processing_mode","scheduled_start","pause_on_battery","selected_scope"],
            "planned_commands": ["ai.models.list_compatible","ai.models.select","ai.models.estimates","ai.models.override","ai.jobs.schedule","ai.jobs.pause","ai.jobs.resume","ai.jobs.scope"],
            "behavioural_rules": {k: True for k in ["slow_processing_alone_is_not_a_hard_block","stronger_compatible_model_remains_selectable","recommendation_is_not_prohibition","silent_model_substitution_is_prohibited","quantized_variant_has_distinct_identity","selected_model_provenance_is_persisted","model_change_invalidates_derived_results"]},
            "hard_block_reasons": ["insufficient_safe_memory","insufficient_storage","unsupported_model_operations","unsupported_runtime_or_provider","invalid_or_corrupted_model","checksum_failure","unresolved_licensing_restriction"],
            "components": {name: {k: True for k in ["stronger_compatible_models_manually_selectable","slow_estimates_do_not_block","hard_incompatibility_may_block","no_silent_fallback","provenance_required"]} for name in ["ONNX Runtime","OCR model/runtime","Embedding model/runtime","Face model/runtime","Python runtime or alternative AI host"]},
            "affected_packages": {pid: {"impact_type": "X", "reason": "R"} for pid in ["WP-I10-003","WP-I10-005","WP-I10-006","WP-I10-008","WP-I10-013"]},
        }

    def valid_packet_text():
        return ("# WP-I10-003\n\nObjective: CAN-LAM-AI-090\n\n## Canonical requirements (3)\n\nCAN-LAM-AI-032\nCAN-LAM-AI-090\nCAN-LAM-ARCH-394\n\n"
                "## Contracts and schemas\n\nCAN-LAM-AI-090\n\n## Delivery and proof\n\nCAN-LAM-AI-090 slow-compatible-selectable\n\n"
                "Exit gate\n\nCAN-LAM-AI-090\n")

    amendment_extra = []
    concepts = ["selected_model_id","recommended_model_id","selection_source","user_override","compatibility_status","hard_block_reason","estimated_duration","estimated_memory","estimated_storage","processing_mode","scheduled_start","pause_on_battery","selected_scope"]
    for idx, concept in enumerate(concepts):
        with tempfile.TemporaryDirectory() as td:
            rootp = Path(td)
            (rootp / "13-reports").mkdir(parents=True)
            (rootp / "04-work-packages" / "packets").mkdir(parents=True)
            bad = valid_amendment(); bad["contract_concepts"] = [c for c in concepts if c != concept]
            (rootp / "13-reports" / "ai-model-override-amendment.json").write_text(json.dumps(bad), encoding="utf-8")
            (rootp / "04-work-packages" / "packets" / "WP-I10-003.md").write_text(valid_packet_text(), encoding="utf-8")
            errs = validator.check_ai_model_override_amendment([am_req], am_membership, [{"component":"ONNX Runtime","model_selection_rule":"manually selectable slow"}], rootp)
            amendment_extra.append((f"F{90+idx}_INDEPENDENT_CONCEPT_{concept}", *contains(errs, f"ai_model_override_concept_missing:{concept}")))
    for idx, command in enumerate(["ai.models.list_compatible","ai.models.select","ai.models.estimates","ai.models.override","ai.jobs.schedule","ai.jobs.pause","ai.jobs.resume","ai.jobs.scope"]):
        with tempfile.TemporaryDirectory() as td:
            rootp = Path(td)
            (rootp / "13-reports").mkdir(parents=True)
            (rootp / "04-work-packages" / "packets").mkdir(parents=True)
            bad = valid_amendment(); bad["planned_commands"] = [c for c in bad["planned_commands"] if c != command]
            (rootp / "13-reports" / "ai-model-override-amendment.json").write_text(json.dumps(bad), encoding="utf-8")
            (rootp / "04-work-packages" / "packets" / "WP-I10-003.md").write_text(valid_packet_text(), encoding="utf-8")
            errs = validator.check_ai_model_override_amendment([am_req], am_membership, [{"component":"ONNX Runtime","model_selection_rule":"manually selectable slow"}], rootp)
            amendment_extra.append((f"F{98+idx}_INDEPENDENT_COMMAND_{command}", *contains(errs, f"ai_model_override_command_missing:{command}")))
    for idx, rule in enumerate(["slow_processing_alone_is_not_a_hard_block","stronger_compatible_model_remains_selectable","recommendation_is_not_prohibition","silent_model_substitution_is_prohibited","quantized_variant_has_distinct_identity","selected_model_provenance_is_persisted","model_change_invalidates_derived_results"]):
        with tempfile.TemporaryDirectory() as td:
            rootp = Path(td)
            (rootp / "13-reports").mkdir(parents=True)
            (rootp / "04-work-packages" / "packets").mkdir(parents=True)
            bad = valid_amendment(); bad["behavioural_rules"][rule] = False
            (rootp / "13-reports" / "ai-model-override-amendment.json").write_text(json.dumps(bad), encoding="utf-8")
            (rootp / "04-work-packages" / "packets" / "WP-I10-003.md").write_text(valid_packet_text(), encoding="utf-8")
            errs = validator.check_ai_model_override_amendment([am_req], am_membership, [{"component":"ONNX Runtime","model_selection_rule":"manually selectable slow"}], rootp)
            amendment_extra.append((f"F{106+idx}_INDEPENDENT_RULE_{rule}", *contains(errs, f"ai_model_override_rule_missing:{rule}")))
    for idx, reason in enumerate(["insufficient_safe_memory","insufficient_storage","unsupported_model_operations","unsupported_runtime_or_provider","invalid_or_corrupted_model","checksum_failure","unresolved_licensing_restriction"]):
        with tempfile.TemporaryDirectory() as td:
            rootp = Path(td)
            (rootp / "13-reports").mkdir(parents=True)
            (rootp / "04-work-packages" / "packets").mkdir(parents=True)
            bad = valid_amendment(); bad["hard_block_reasons"] = [r for r in bad["hard_block_reasons"] if r != reason]
            (rootp / "13-reports" / "ai-model-override-amendment.json").write_text(json.dumps(bad), encoding="utf-8")
            (rootp / "04-work-packages" / "packets" / "WP-I10-003.md").write_text(valid_packet_text(), encoding="utf-8")
            errs = validator.check_ai_model_override_amendment([am_req], am_membership, [{"component":"ONNX Runtime","model_selection_rule":"manually selectable slow"}], rootp)
            amendment_extra.append((f"F{113+idx}_INDEPENDENT_HARD_{reason}", *contains(errs, f"ai_model_override_hard_block_reason_missing:{reason}")))
    for idx, mutation in enumerate([
        ("OBJECTIVE", valid_packet_text().replace("Objective: CAN-LAM-AI-090", "Objective: CAN-LAM-AI-032")),
        ("CONTRACTS", valid_packet_text().replace("## Contracts and schemas\n\nCAN-LAM-AI-090", "## Contracts and schemas\n\nCAN-LAM-AI-032")),
        ("TESTS", valid_packet_text().replace("CAN-LAM-AI-090 slow-compatible-selectable", "CAN-LAM-AI-032")),
        ("EXIT", valid_packet_text().replace("Exit gate\n\nCAN-LAM-AI-090", "Exit gate\n\nCAN-LAM-AI-032")),
    ]):
        with tempfile.TemporaryDirectory() as td:
            rootp = Path(td)
            (rootp / "13-reports").mkdir(parents=True)
            (rootp / "04-work-packages" / "packets").mkdir(parents=True)
            (rootp / "13-reports" / "ai-model-override-amendment.json").write_text(json.dumps(valid_amendment()), encoding="utf-8")
            (rootp / "04-work-packages" / "packets" / "WP-I10-003.md").write_text(mutation[1], encoding="utf-8")
            errs = validator.check_ai_model_override_amendment([am_req], am_membership, [{"component":"ONNX Runtime","model_selection_rule":"manually selectable slow"}], rootp)
            expected = "ai_override_packet_objective_missing_requirement" if mutation[0]=="OBJECTIVE" else "ai_override_packet_contracts_missing_requirement" if mutation[0]=="CONTRACTS" else "ai_override_packet_tests_missing_requirement" if mutation[0]=="TESTS" else "ai_override_packet_exit_gate_missing_requirement"
            amendment_extra.append((f"F{120+idx}_INDEPENDENT_PACKET_{mutation[0]}", *contains(errs, expected)))

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
        ("F13_LEGACY_FAMILY_REMAINS", *contains(family_errors, "legacy capability-template family remains")),
        ("F14_NAVIGATION_AS_MUTATION", *contains(nav_errors, "navigation represented as mutation")),
        ("F15_LEGAL_AS_INFERENCE", *contains(legal_errors, "legal/licensing item represented as model inference")),
        ("F16_PERFORMANCE_AS_ROOT", *contains(perf_errors, "performance item represented as root authorization")),
        ("F17_MENU_LABEL_AS_FEATURE", *contains(menu_errors, "menu/UI label treated as a complete feature")),
        ("F18_POSITIVE_STATUS_UNSOURCED", *contains(unsourced_errors, "positive review status without v2 source")),
        ("F19_ZERO_TEMPLATE_CLAIM", *contains(zero_errors, "zero-template claim lacks independent audit evidence")),
        ("F20_VERIFICATION_MISSING", *contains(verification_errors, "active implementation record lacks requirement-specific verification")),
        ("F21_OPEN_PERSON_IN_MUTATION", *contains(p2_open_person, "open person/event/folder placed in mutation package")),
        ("F22_OPEN_EVENT_IN_PLAN_MUTATION", *contains(p2_open_event, "open person/event/folder placed in mutation package")),
        ("F23_MODEL_LICENSING_IN_AI_INFERENCE", *contains(p2_licensing, "model licensing placed in AI inference package")),
        ("F24_LARGE_LIBRARY_IN_ACCESSIBILITY", *contains(p2_large, "large-library optimization placed in accessibility package")),
        ("F25_MIXED_PACKAGE", *contains(p2_mixed, "package mixes unrelated navigation, mutation, performance, or legal work")),
        ("F26_PACKAGE_TITLE_MISMATCH", *contains(p2_title, "generic package name")),
        ("F27_GENERIC_MEMBERSHIP_RATIONALE", *contains(generic_membership, "generic membership rationale")),
        ("F28_ADJACENCY_DEPENDENCY", *contains(adjacency_errors, "artificial adjacency dependency")),
        ("F29_REQUIRED_SCHEMA_DEPENDENCY_MISSING", *contains(missing_schema_errors, "required technical prerequisite absent")),
        ("F30_UNEXPLAINED_ROOT", *contains(root_errors, "unexplained root package")),
        ("F31_PHASE_MISMATCH", *contains(phase_errors, "requirement/package phase mismatch")),
        ("F32_REMOVAL_BEFORE_REPLACEMENT", *contains(removal_errors, "removal package precedes replacement proof")),
        ("F33_OPEN_FOLDER_IN_AI_WORK", *contains(sem_open_folder, "open-in-folder assigned to AI/mutation/identity/storage work")),
        ("F34_RAW_EXPORT_BY_KEYWORD", *contains(sem_raw, "inspector raw-data export not assigned by source meaning")),
        ("F35_PERFORMANCE_VALIDATION_IN_FEATURE_PACKAGE", *contains(sem_perfval, "performance-measurement statement conflicts with capability")),
        ("F36_PLANNING_GOVERNANCE_IN_PRODUCT_PACKAGE", *contains(sem_planning, "planning-governance statement conflicts with capability")),
        ("F37_NON_ACTIONABLE_RECORD_RETAINS_PHASE", *contains(sem_nonact, "non-actionable record retains implementation phase")),
        ("F38_CORRECTED_REQUIREMENT_REMAINS_IN_OLD_PACKAGE", *contains(sem_old_pkg, "semantic audit correction not applied to package")),
        ("F39_GENERIC_MEMBERSHIP_RATIONALE_NEW", *contains(rationale_errors, "circular membership rationale")),
        ("F40_LARGE_PACKAGE_LACKS_COHESION_REVIEW", *contains(large_coverage_errors, "large package lacks cohesion review")),
        ("F41_DEPENDENCY_CYCLE", *contains(cycle_errors, "dependency cycle detected")),
        ("F42_PACKET_STALE_MEMBERSHIP", *contains(packet_errors, "packet membership stale")),
        ("F43_L7_L8_CLAIM_WITHOUT_EXECUTION", *contains(execution_claim_errors, "L7/L8 are reported as executed while jsonschema is unavailable")),
        ("F44_MISSING_COMPONENT_DECISION", *contains(component_errors, "component missing owning_phase")),
        ("F45_INVALID_SQLITE_REFERENCE", *contains(sqlite_ref_errors, "SQLite foreign key references missing table")),
        ("F46_SUPERSEDED_ACTIVE_HANDOFF", *contains(superseded_handoff_errors, "active handoff points to superseded phase")),
        ("F47_NON_DETERMINISTIC_FINAL_EVIDENCE", *contains(determinism_errors, "determinism evidence mismatch")),
        ("F48_CONSOLE_SUCCESS_WITHOUT_PERSISTED_DECLARATION", *contains(readiness_errors, "persisted readiness declaration missing or incorrect")),
        ("F49_MISSING_V3_REQUIREMENT_REVIEW", *contains(missing_v3_errors, "actionable requirement missing v3 review row")),
        ("F50_GENERIC_V3_RATIONALE", *contains(generic_v3_errors, "v3 rationale too short")),
        ("F51_ID_ONLY_V3_PROVENANCE", *contains(id_only_v3_errors, "lacks substantive fields")),
        ("F52_ACTIVE_SCRIPT_ALLOWLIST_REMOVED", *contains(allowlist_errors, "automatic positive review certification")),
        ("F53_GENERATED_MEMBER_EVIDENCE_ACCEPTED", *contains(empty_member_errors, "independent member verification ledger is empty")),
        ("F54_GENERATED_CONTRACT_SCHEMA_EVIDENCE_ACCEPTED", *contains(empty_contract_errors, "independent contract/schema verification ledger is empty")),
        ("F55_GENERATED_TEST_EXIT_EVIDENCE_ACCEPTED", *contains(empty_test_errors, "independent test verification ledger is empty")),
        ("F56_WP_I3_001_UNCHANGED_WITHOUT_REASSESSMENT", *contains(missing_i3_errors, "independent member verification ledger is empty")),
        ("F57_COMPONENT_PENDING", *contains(c_pending, "component decision pending")),
        ("F58_COMPONENT_LICENCE_PENDING", *contains(c_licence, "component licence pending")),
        ("F59_COMPONENT_REDISTRIBUTION_MISSING", *contains(c_redist, "component redistribution missing")),
        ("F60_COMPONENT_DECISION_PACKAGE_MISSING", *contains(c_decision, "component decision package missing")),
        ("F61_COMPONENT_VERSION_RULE_MISSING", *contains(c_version, "component version rule missing")),
        ("F62_COMPONENT_RATIONALE_GENERIC", *contains(c_generic, "component rationale generic")),
        ("F63_COMPONENT_CONSUMER_MISSING_DEPENDENCY", *contains(c_consumer, "component consumer lacks decision dependency")),
        ("F64_REJECTED_COMPONENT_STILL_CONSUMED", *contains(c_rejected, "rejected component still has consumers")),
        ("F65_AMENDMENT_REQUIREMENT_MISSING", *contains(am_missing_req, "ai_model_user_override_requirement_present")),
        ("F66_AMENDMENT_PHRASE_MISSING", *contains(am_missing_phrase, "ai_model_override_phrase_missing")),
        ("F67_AMENDMENT_ACCEPTANCE_MISSING", *contains(am_missing_accept, "ai_model_override_acceptance_missing")),
        ("F68_AMENDMENT_VERIFICATION_MISSING", *contains(am_missing_verify, "ai_model_override_verification_missing")),
        ("F69_AMENDMENT_MEMBERSHIP_MISSING", *contains(am_missing_membership, "requirement_membership_present")),
        ("F70_AMENDMENT_ARTIFACT_MISSING", *contains(am_missing_artifact, "ai_model_override_amendment_artifact_missing")),
        ("F71_AMENDMENT_COMPONENT_RULE_MISSING", *contains(am_missing_component_rule, "component_model_selection_rule_missing")),
    ]
    cases = cases + amendment_extra
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
