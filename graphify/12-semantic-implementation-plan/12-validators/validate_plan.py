from __future__ import annotations

import csv
import json
import re
import sqlite3
import stat
import sys
from collections import Counter, defaultdict, deque
from pathlib import Path

try:
    from jsonschema import Draft202012Validator
except ImportError:  # Reported as a validation failure below.
    Draft202012Validator = None


PLAN = Path(__file__).resolve().parents[1]
GRAPHIFY = PLAN.parent
BUILDER = GRAPHIFY / "build_semantic_plan.py"
sys.path.insert(0, str(GRAPHIFY))
from tools.write_guard import guard_write_path  # noqa: E402

IMPLEMENTATION_TYPES = {
    "FUNCTIONAL_REQUIREMENT", "NONFUNCTIONAL_REQUIREMENT", "ARCHITECTURAL_INVARIANT",
    "SECURITY_INVARIANT", "PRIVACY_INVARIANT", "DATA_INTEGRITY_INVARIANT",
    "IMPLEMENTATION_CONSTRAINT", "ACCEPTANCE_CRITERION", "OPTIONAL_ADAPTER",
    "VERIFICATION_GATE", "REMOVAL_GATE", "RELEASE_GATE", "PROHIBITION",
}

MEANINGFUL_STOP = {"the", "and", "for", "that", "with", "from", "must", "shall", "will", "this", "lamha", "implementation", "a", "an", "to", "of", "or", "in", "on", "is", "be", "as", "by"}
GENERIC_TEMPLATE = re.compile(r"^(recorded evidence must demonstrate:|lamha must provide |implementation must honor this constraint:|lamha must preserve this invariant:|the final lamha desktop runtime must not retain or require |lamha must implement the .+ behavior for .+ and satisfy every linked acceptance criterion\.)", re.I)
OBSERVABLE = re.compile(r"\b(return|display|shown?|report|reject|preserve|persist|remain|produce|update|pass|fail|create|support|write|read|render|detect|include|record|expose|leave|block|index|reflect|apply|invoke|store|execute|verify|validate|calculate|prevent|enforce|reconcile|restore|remove|communicate|open|close|suppress|reconsider|mark|use|embed|mutate|require|help|represent|derive|keep|plan|test|move|reference|add|split|identify|link|exist|survive|choose|save|retain|scope|rescan|track|correspond|change|limit|map|contribute|transition|inventory|classify|measure|provide|generate|follow|initialize|treat|establish|preview|commit|approve|confirm|exclude|highlight|budget|threshold|latency|throughput|benchmark|queue|group|delete|merge|upload|appear|omit|navigate|reveal|strip|redact|compose)\w*\b", re.I)
PERMITTED_REVIEW_STATUSES = {
    "REVIEWED_CONFIRMED", "REVIEWED_CORRECTED", "RECLASSIFIED", "MERGED",
    "SUPERSEDED", "REVIEW_REQUIRED", "BLOCKED", "NOT_APPLICABLE",
}
LEGACY_FAMILY = re.compile(
    r"^(When (the local worker processes |the workflow manages |a review item offers "
    r"|a configured library encounters |a query or indexing task uses |the user invokes "
    r"|the user uses |the user changes |the user applies |duplicate analysis evaluates "
    r"|the desktop shell handles )|When producing .* evidence)",
    re.I,
)
FALLBACK_EXERCISED = re.compile(
    r"is exercised in .*must expose the resulting state and preserve the prior durable state",
    re.I,
)
MEMORY_SHOWN = re.compile(
    r"is shown in .*derive the memory from local canonical asset references",
    re.I,
)
NAVIGATION_OPEN = re.compile(r"\bopen (person|people|event|folder)\b", re.I)
MUTATION_VERBS = re.compile(r"\b(create|update|mutat|persist|authorize|produce|transition)\w*\b", re.I)
NAVIGATION_VERBS = re.compile(r"\b(load|display|navigate|reveal|open for display|read-only)\w*\b", re.I)
LEGAL_TERMS = re.compile(r"\b(licen[cs]e|licen[cs]es|attribution|legal|redistribution|provenance)\b", re.I)
PERFORMANCE_TERMS = re.compile(r"\b(large[-\s]?library|performance|scale|memory|ram)\b", re.I)
ROOT_AUTHORIZATION = re.compile(r"authorized-root and access-mode rules", re.I)
PERFORMANCE_OUTCOME = re.compile(r"\b(budget|measure|latency|throughput|responsiveness|benchmark)\w*\b", re.I)
UI_LABEL_TERMS = re.compile(r"\b(menu|button|tab|dialog|page|screen)\b", re.I)


def read_csv(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(path.open(encoding="utf-8", newline="")))


def read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def is_reparse(path: Path) -> bool:
    try:
        return bool(path.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)
    except (AttributeError, FileNotFoundError, OSError):
        return path.is_symlink()


def safe_write_path(path: Path) -> Path:
    return guard_write_path(path)


def meaningful_words(value: str) -> list[str]:
    return [word for word in re.findall(r"[A-Za-z0-9]+", value) if word.casefold() not in MEANINGFUL_STOP]


def check_requirement_records(rows: list[dict[str, str]], mappings: dict[str, dict[str, str]] | None = None) -> list[str]:
    errors: list[str] = []
    ids: set[str] = set()
    mappings = mappings or {}
    for row in rows:
        rid = row.get("canonical_id", "")
        if not rid or rid in ids:
            errors.append(f"requirement duplicate/missing id: {rid!r}")
        ids.add(rid)
        statement = row.get("statement", "").strip()
        active = row.get("supersession_status", "ACTIVE") == "ACTIVE"
        phase = mappings.get(rid, row).get("primary_implementation_phase", "")
        actionable = active and bool(phase) and row.get("requirement_type") in IMPLEMENTATION_TYPES
        if actionable:
            lowered = statement.casefold()
            if GENERIC_TEMPLATE.search(statement) or "must demonstrably satisfy" in lowered or "must satisfy:" in lowered:
                errors.append(f"generic criterion template: {rid}")
            if lowered.startswith("lamha must provide do not"):
                errors.append(f"malformed prohibition: {rid}")
            meaningful = meaningful_words(statement)
            has_observable = bool(OBSERVABLE.search(statement))
            if len(meaningful) < 8:
                errors.append(f"fragmentary or non-observable active requirement: {rid}")
            if not has_observable:
                errors.append(f"non-observable active requirement: {rid}")
            criterion_text = statement + " " + (row.get("acceptance_criteria") or "")
            if row.get("requirement_type") == "ACCEPTANCE_CRITERION" and (
                not re.search(r"\b(given|when)\b", criterion_text, re.I) or not bool(OBSERVABLE.search(criterion_text))
            ):
                errors.append(f"criterion is only a label: {rid}")
            if row.get("requirement_type") == "ACCEPTANCE_CRITERION" and not row.get("parent_requirement_id"):
                errors.append(f"criterion missing parent: {rid}")
            if not row.get("verification_method"):
                errors.append(f"missing verification method: {rid}")
            if rid.startswith("CAN-FAIL-") and (re.search(r"\bFAIL-\d+\s*;|Narrative mentioned|Lacked explicit|Mapped .* tests", statement, re.I) or statement.count(";") > 3):
                errors.append(f"malformed CAN-FAIL audit paragraph: {rid}")
            if re.search(r"\bfAIL-\d+\b|Lamha must provide do not|BLOCKEDORUNKNOWN", statement):
                errors.append(f"grammatically malformed statement: {rid}")
        if "work_package_id" in row:
            errors.append(f"stale canonical work_package_id field: {rid}")
        trace_fields = ["source_plan", "source_section", "source_text", "source_locator", "rationale"]
        synthesized = row.get("normalization_status", "").startswith("SYNTHESIZED_") or rid.startswith(("CAN-SECTION-", "CAN-MISSION-"))
        if not synthesized:
            trace_fields.append("original_requirement_ids")
        for field in trace_fields:
            if not row.get(field):
                errors.append(f"missing traceability {field}: {rid}")
    return errors


def check_pass1_semantics(
    rows: list[dict[str, str]],
    mappings: dict[str, dict[str, str]],
    v2_rows: list[dict[str, str]],
    detected_ids: set[str] | None = None,
) -> list[str]:
    """Pass 1 semantic rehabilitation checks with explicit v2 status sourcing."""
    errors: list[str] = []
    if detected_ids is None:
        detected_ids = {row["canonical_id"] for row in read_csv(PLAN / "13-reports" / "legacy-template-semantic-audit.csv")}
    v2_ids = {row["record_id"] for row in v2_rows}
    kept_ids = {row["record_id"] for row in v2_rows if row["disposition"] == "KEEP_WITH_EXPLICIT_JUSTIFICATION"}
    corrected_ids = {row["record_id"] for row in v2_rows if row["disposition"].startswith("REWRITE_")}
    for row in rows:
        rid = row.get("canonical_id", "")
        if row.get("supersession_status") != "ACTIVE":
            continue
        statement = row.get("statement", "") or ""
        source = row.get("source_text", "") or ""
        section = row.get("source_section", "") or ""
        phase = mappings.get(rid, {}).get("primary_implementation_phase", "")
        actionable = bool(phase) and row.get("requirement_type") in IMPLEMENTATION_TYPES
        if not actionable:
            continue
        lowered = statement.casefold()
        if rid in detected_ids and rid not in v2_ids:
            errors.append(f"active requirement missing explicit Pass 1 decision: {rid}")
            continue
        if rid in v2_ids:
            if (
                row.get("normalization_status", "") != "EXPLICIT_REVIEWED_REWRITE"
                and rid not in kept_ids
                and (LEGACY_FAMILY.match(statement) or FALLBACK_EXERCISED.search(statement) or MEMORY_SHOWN.search(statement))
            ):
                errors.append(f"legacy capability-template family remains without explicit rewrite: {rid}")
            if rid not in kept_ids and row.get("normalization_status", "") != "EXPLICIT_REVIEWED_REWRITE" and GENERIC_TEMPLATE.search(statement):
                errors.append(f"generic capability template remains without rewrite: {rid}")
        if NAVIGATION_OPEN.search(source + " " + section) and MUTATION_VERBS.search(statement) and not NAVIGATION_VERBS.search(statement):
            errors.append(f"navigation represented as mutation without read/navigation behavior: {rid}")
        if LEGAL_TERMS.search(source + " " + section) and re.search(r"local worker processes", statement, re.I):
            errors.append(f"legal/licensing item represented as model inference: {rid}")
        if PERFORMANCE_TERMS.search(source + " " + section) and ROOT_AUTHORIZATION.search(statement) and not PERFORMANCE_OUTCOME.search(statement):
            errors.append(f"performance item represented as root authorization: {rid}")
        if UI_LABEL_TERMS.search(source + " " + section) and "When " in statement and not bool(OBSERVABLE.search(statement)):
            errors.append(f"menu/UI label treated as a complete feature: {rid}")
        criterion_text = statement + " " + (row.get("acceptance_criteria") or "")
        if row.get("requirement_type") == "ACCEPTANCE_CRITERION" and not re.search(r"\b(given|when)\b", criterion_text, re.I):
            errors.append(f"criterion is only a label: {rid}")
        if not row.get("verification_method", "").strip():
            errors.append(f"active implementation record lacks requirement-specific verification: {rid}")
        status = row.get("normalization_reviewer_status", "")
        if (
            rid in detected_ids
            and status in {"REVIEWED_CONFIRMED", "REVIEWED_CORRECTED", "RECLASSIFIED", "MERGED", "SUPERSEDED"}
            and rid not in v2_ids
        ):
            errors.append(f"positive review status not sourced from v2 registry: {rid}")
        if rid in corrected_ids and not bool(OBSERVABLE.search(statement)):
            errors.append(f"corrected requirement lacks an observable outcome: {rid}")
    return errors


def check_v2_status_sourcing(
    requirements: list[dict[str, str]],
    v2_rows: list[dict[str, str]],
    detected_ids: set[str] | None = None,
) -> list[str]:
    errors: list[str] = []
    if detected_ids is None:
        detected_ids = {row["canonical_id"] for row in read_csv(PLAN / "13-reports" / "legacy-template-semantic-audit.csv")}
    v2_ids = {row["record_id"] for row in v2_rows}
    req_ids = {row["canonical_id"] for row in requirements}
    for row in v2_rows:
        if row["record_id"] not in req_ids:
            errors.append(f"v2 decision references unknown requirement: {row['record_id']}")
    for row in requirements:
        if row.get("supersession_status") != "ACTIVE":
            continue
        status = row.get("normalization_reviewer_status", "")
        if (
            row["canonical_id"] in detected_ids
            and status in {"REVIEWED_CONFIRMED", "REVIEWED_CORRECTED", "RECLASSIFIED", "MERGED", "SUPERSEDED"}
            and row["canonical_id"] not in v2_ids
        ):
            errors.append(f"positive review status without v2 source: {row['canonical_id']}")
    return errors


def check_pass2_package_semantics(
    packages: list[dict[str, object]],
    membership: list[dict[str, str]],
    requirements: list[dict[str, str]],
    mappings: dict[str, dict[str, str]],
    edges: list[dict[str, str]],
) -> list[str]:
    """Pass 2 package/DAG semantic checks."""
    errors: list[str] = []
    req_by_id = {row["canonical_id"]: row for row in requirements}
    member_by_package: defaultdict[str, list[str]] = defaultdict(list)
    for row in membership:
        member_by_package[row["work_package_id"]].append(row["canonical_id"])
    package_by_id = {str(row["work_package_id"]): row for row in packages}
    edges_by_dependent: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
    for edge in edges:
        edges_by_dependent[edge["work_package_id"]].append(edge)

    generic_name = re.compile(r"\b(production implementation for|implementation for|generic|placeholder)\b", re.I)
    boilerplate_rationale = re.compile(
        r"^the requirement is implemented by the bounded .* surface\.?$|^must be implemented\.?$|^implemented by .* package\.?$",
        re.I,
    )
    navigation_open = re.compile(r"\bopen (person|people|event|folder)\b", re.I)
    mutation_package = re.compile(r"\b(identity-mutation|mutation|persist|event-plan|plan mutation)\b", re.I)
    legal_terms = re.compile(r"\b(model licen|third-party model|codec licen|licence files|attribution|redistribution)\b", re.I)
    ai_inference_package = re.compile(r"\b(ai worker|inference|worker transport|local ai)\b", re.I)
    large_library = re.compile(r"\blarge[-\s]?library\b", re.I)
    accessibility_package = re.compile(r"\baccessib\w*\b", re.I)
    removal_package = re.compile(r"\b(legacy removal|server eradication|data-stack eradication|deployment eradication|generated-client eradication)\b", re.I)
    replacement_verified = re.compile(r"REQUIRES_REPLACEMENT_VERIFIED", re.I)

    for package in packages:
        pid = str(package["work_package_id"])
        name = str(package.get("name", ""))
        objective = str(package.get("objective", ""))
        ids = member_by_package.get(pid, [])
        statements = " ".join((req_by_id.get(rid, {}).get("statement", "") or "") for rid in ids)
        capabilities = {str(package.get("reviewed_capabilities", []))}
        capability_list = {str(value) for value in (package.get("reviewed_capabilities") or [])}
        if generic_name.search(name):
            errors.append(f"generic package name: {pid}")
        domains = []
        if re.search(r"\b(open|load and display|navigate|browse|reveal)\b", statements, re.I):
            domains.append("navigation")
        if re.search(r"\b(persist|mutat|commit|create|update|write|trash|delete)\b", statements, re.I):
            domains.append("mutation")
        if re.search(r"\b(budget|latency|throughput|performance|benchmark|memory)\b", statements, re.I):
            domains.append("performance")
        if legal_terms.search(statements + " " + objective):
            domains.append("legal")
        if (
            len({domain for domain in domains}) >= 3
            and len(capability_list) > 2
            and str(package.get("architectural_boundary_exception")) != "true"
        ):
            errors.append(f"package mixes unrelated navigation, mutation, performance, or legal work: {pid}")
        for rid in ids:
            statement = req_by_id.get(rid, {}).get("statement", "") or ""
            if navigation_open.search(statement) and mutation_package.search(name):
                errors.append(f"open person/event/folder placed in mutation package: {rid} -> {pid}")
            if legal_terms.search(statement) and ai_inference_package.search(name):
                errors.append(f"model licensing placed in AI inference package: {rid} -> {pid}")
            if large_library.search(statement) and accessibility_package.search(name):
                errors.append(f"large-library optimization placed in accessibility package: {rid} -> {pid}")
            phase = mappings.get(rid, {}).get("primary_implementation_phase", "")
            if phase and str(package.get("implementation_phase", "")) != phase:
                errors.append(f"requirement/package phase mismatch: {rid} {phase} != {pid} {package.get('implementation_phase')}")
        for row in membership:
            if row["canonical_id"] in ids:
                rationale = row.get("membership_rationale", "")
                if not rationale or boilerplate_rationale.match(rationale.strip()):
                    errors.append(f"generic membership rationale: {row['canonical_id']}")
        if removal_package.search(name + " " + objective) and not any(
            replacement_verified.search(str(edge.get("dependency_type", ""))) for edge in edges_by_dependent.get(pid, [])
        ):
            errors.append(f"removal package precedes replacement proof: {pid}")
    return errors


def check_membership_rationale_quality(
    membership: list[dict[str, str]],
    packages: list[dict[str, object]],
    requirements: list[dict[str, str]],
) -> list[str]:
    errors: list[str] = []
    circular = re.compile(
        r"owns the .+ surface in .+; requirement .+ requires"
        r"|implements the .+ surface in .+; .+ belongs here because its reviewed statement"
        r"|is the behavior that surface executes"
        r"|belongs here because its reviewed statement .+ is the behavior",
        re.I,
    )
    for row in membership:
        rationale = row.get("membership_rationale", "").strip()
        if not rationale:
            errors.append(f"empty membership rationale: {row['canonical_id']}")
            continue
        if circular.search(rationale):
            errors.append(f"circular membership rationale: {row['canonical_id']}")
        meaningful = [word for word in re.findall(r"[A-Za-z0-9]+", rationale) if word.casefold() not in MEANINGFUL_STOP]
        if len(meaningful) < 12:
            errors.append(f"membership rationale too short: {row['canonical_id']}")
    return errors


def check_affected_package_quality(
    packages: list[dict[str, object]],
    affected_package_ids: set[str],
) -> list[str]:
    errors: list[str] = []
    generic_objective = re.compile(r"^implement and verify the bounded .+ surface\.?$", re.I)
    generic_deliverables = re.compile(r"production implementation for|updated affected contracts and records; focused tests", re.I)
    generic_tests = re.compile(r"^focused success, boundary, and failure tests for .+; affected integration checks\.?$", re.I)
    generic_exclusions = re.compile(r"^unrelated capabilities; later release/cleanup work; application-wide refactors\.?$", re.I)
    generic_failure = re.compile(r"^invalid input; authorization failure; revision conflict; cancellation or I/O failure where applicable\.?$", re.I)
    generic_exit = re.compile(r"^the .+ objective and failure tests pass with no unrelated package work included\.?$", re.I)
    for package in packages:
        pid = str(package.get("work_package_id", ""))
        if pid not in affected_package_ids:
            continue
        if generic_objective.search(str(package.get("objective", ""))):
            errors.append(f"generic package objective: {pid}")
        if generic_deliverables.search(str(package.get("deliverables", ""))):
            errors.append(f"generic package deliverables: {pid}")
        if generic_tests.search(str(package.get("tests", ""))):
            errors.append(f"generic package tests: {pid}")
        if generic_exclusions.search(str(package.get("explicit_exclusions", ""))):
            errors.append(f"generic package exclusions: {pid}")
        if generic_failure.search(str(package.get("failure_cases", ""))):
            errors.append(f"generic package failure cases: {pid}")
        if generic_exit.search(str(package.get("exit_gate", ""))):
            errors.append(f"generic package exit gate: {pid}")
    return errors


def check_large_package_review_coverage(
    packages: list[dict[str, object]],
    review_rows: list[dict[str, str]],
) -> list[str]:
    errors: list[str] = []
    reviewed = {row["Package ID"]: row for row in review_rows}
    for package in packages:
        pid = str(package.get("work_package_id", ""))
        if int(package.get("reviewed_item_count") or 0) <= 20:
            continue
        row = reviewed.get(pid)
        if not row or row.get("Review result") != "PASS" or "COHESION" not in row.get("Final decision", ""):
            errors.append(f"large package lacks cohesion review: {pid}")
    return errors


def check_packet_membership_currency(
    packages: list[dict[str, object]],
    membership: list[dict[str, str]],
    plan_root: Path,
) -> list[str]:
    errors: list[str] = []
    member_by_package: defaultdict[str, list[str]] = defaultdict(list)
    for row in membership:
        member_by_package[row["work_package_id"]].append(row["canonical_id"])
    for package in packages:
        pid = str(package["work_package_id"])
        packet = plan_root / "04-work-packages" / "packets" / f"{pid}.md"
        if not packet.exists():
            errors.append(f"packet missing for package: {pid}")
            continue
        text = packet.read_text(encoding="utf-8")
        for rid in member_by_package.get(pid, []):
            if f"`{rid}`" not in text:
                errors.append(f"packet membership stale: {rid} missing from {pid} packet")
    return errors


def check_l7_l8_execution_claim(
    jsonschema_available: bool,
    results: dict[str, object],
) -> list[str]:
    errors: list[str] = []
    if not jsonschema_available:
        errors.append("L7/L8 are reported as executed while jsonschema is unavailable")
    for level in results.get("levels", []):
        if level.get("level") in {"L7_IPC_CONTRACTS", "L8_AUTHORITY_RECORDS_AND_SQLITE"} and level.get("status") != "PASS":
            errors.append(f"{level.get('level')} did not genuinely pass")
    return errors


def check_sqlite_references(sql: str) -> list[str]:
    errors: list[str] = []
    tables = set(re.findall(r"CREATE TABLE\s+(?:IF NOT EXISTS\s+)?([\w]+)", sql, re.I))
    references = re.findall(r"REFERENCES\s+([\w]+)", sql, re.I)
    for target in references:
        if target not in tables:
            errors.append(f"SQLite foreign key references missing table: {target}")
    return errors


def check_determinism_evidence(first: str, second: str) -> list[str]:
    return [] if first == second else [f"determinism evidence mismatch: {first} != {second}"]


def check_persisted_readiness_declaration(
    report: dict[str, object],
    handoff_text: str,
    determinism: dict[str, object],
) -> list[str]:
    errors: list[str] = []
    expected = "IMPLEMENTATION-READY PLANNING COMPLETE \u2014 I0 MAY BEGIN"
    if report.get("status") != "PASS":
        errors.append(f"persisted certification status is not PASS: {report.get('status')}")
    if report.get("readiness_declaration") != expected:
        errors.append("persisted readiness declaration missing or incorrect")
    if report.get("implementation_ready") is not True:
        errors.append("implementation_ready is not true")
    if report.get("first_allowed_package") != "WP-I0-001":
        errors.append(f"first_allowed_package is not WP-I0-001: {report.get('first_allowed_package')}")
    if report.get("remaining_blockers"):
        errors.append(f"remaining_blockers is not empty: {report.get('remaining_blockers')}")
    if report.get("final_package_hash") != determinism.get("firstCompletePackageHash"):
        errors.append("persisted final package hash does not match determinism evidence")
    if expected not in handoff_text:
        errors.append("active handoff does not contain the persisted readiness declaration")
    return errors


def check_semantic_capability_phase_consistency(
    requirements: list[dict[str, str]],
    mappings: dict[str, dict[str, str]],
    membership: list[dict[str, str]],
    packages: list[dict[str, object]],
    v2_rows: list[dict[str, str]],
    audit_rows: list[dict[str, str]],
) -> list[str]:
    """Fail on the semantic-capability/phase mismatches this Pass 2 audit repairs."""
    errors: list[str] = []
    req_by_id = {row["canonical_id"]: row for row in requirements}
    package_by_id = {str(row["work_package_id"]): row for row in packages}
    member_by_id = {row["canonical_id"]: row for row in membership}
    NON_IMPL = {"GLOSSARY", "UI_LABEL", "INFORMATIONAL", "DUPLICATE"}
    OPEN_FOLDER = re.compile(r"open in folder|open in filesystem|show in folder|reveal.*physical path", re.I)
    NAVIGATION = re.compile(r"\b(reveal|navigate|open (in folder|in filesystem|in event|in map|sidecars|asset)|display|load and display|read-only)\b", re.I)
    MUTATION_PACKAGE = re.compile(r"mutation|identity-state|persistence|authority model|plan mutation", re.I)
    RAW_EXPORT = re.compile(r"copy/export raw data|raw data is copied or exported", re.I)
    HARDWARE = re.compile(r"hardware assessment", re.I)
    PERF_VALIDATION = re.compile(r"performance (result|validation)|record .* hardware profile|fixtures, record .* budgets|report .* measurements against reviewed budgets", re.I)
    PLANNING = re.compile(r"pass 1 .* corpus inventory|pass 2 .* current architecture|pass 3 .* existing features|implementation tracker|planning tracker|one id represents one independently testable obligation", re.I)
    AUDIT_FIXES = {
        "CAN-LAM-FOLDER-032": ("Libraries and storage", "I5", "WP-I5-015"),
        "CAN-LAM-FOLDER-014": ("Libraries and storage", "I5", "WP-I5-015"),
        "CAN-LAM-FOLDER-041": ("Libraries and storage", "I5", "WP-I5-015"),
        "CAN-LAM-TRASH-004": ("Backup, trash, restore and rebuild", "I13", "WP-I13-006"),
        "CAN-LAM-ASSET-138": ("Sidecars and metadata authority", "I3", "WP-I3-006"),
        "CAN-LAM-ARCH-193": ("Editing", "I11", "WP-I11-006"),
        "CAN-LAM-AI-018": ("Duplicates", "I10", "WP-I10-011"),
        "CAN-LAM-ASSET-117": ("Local AI worker", "I10", "WP-I10-005"),
        "CAN-LAM-ASSET-118": ("Local AI worker", "I10", "WP-I10-005"),
        "CAN-LAM-PERF-008": ("Performance and scale", "I14", "WP-I14-001"),
        "CAN-LAM-GOV-264": ("Planning and verification governance", "I0", "WP-I0-011"),
        "CAN-LAM-GOV-265": ("Planning and verification governance", "I0", "WP-I0-011"),
        "CAN-LAM-GOV-266": ("Planning and verification governance", "I0", "WP-I0-011"),
        "CAN-LAM-ASSET-147": ("Performance and scale", "I14", "WP-I14-001"),
        "CAN-MISSION-I14-001": ("Performance and scale", "I14", "WP-I14-005"),
        "CAN-MISSION-I14-003": ("Jobs and notifications", "I14", "WP-I14-012"),
        "CAN-MISSION-I14-004": ("Performance and scale", "I14", "WP-I14-014"),
        "CAN-MISSION-I15-001": ("Packaging and legacy eradication", "I15", "WP-I15-001"),
        "CAN-MISSION-I15-003": ("Packaging and legacy eradication", "I15", "WP-I15-014"),
        "CAN-LAM-GOV-052": ("Planning and verification governance", "I0", "WP-I0-011"),
        "CAN-LAM-GOV-054": ("Planning and verification governance", "I0", "WP-I0-011"),
        "CAN-LAM-GOV-165": ("Planning and verification governance", "I0", "WP-I0-011"),
        "CAN-LAM-ARCH-376": ("Gallery and timeline", "I5", "WP-I5-002"),
        "CAN-LAM-BACKUP-004": ("Backup, trash, restore and rebuild", "I13", "WP-I13-001"),
        "CAN-LAM-FOLDER-076": ("External drives and path resilience", "I12", "WP-I12-009"),
        "CAN-LAM-FOLDER-077": ("External drives and path resilience", "I12", "WP-I12-001"),
    }
    EXTRA_PACKAGE_FIXES = {
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
        "CAN-LAM-ARCH-376": "WP-I5-002",
        "CAN-LAM-GOV-065": "WP-I1-005",
        "CAN-LAM-BACKUP-004": "WP-I13-001",
        "CAN-LAM-FOLDER-076": "WP-I12-009",
        "CAN-LAM-FOLDER-077": "WP-I12-001",
        "CAN-LAM-ARCH-063": "WP-I5-001",
        "CAN-LAM-ARCH-064": "WP-I5-001",
        "CAN-LAM-SEARCH-005": "WP-I7-004",
    }

    for row in requirements:
        rid = row["canonical_id"]
        if row.get("supersession_status") != "ACTIVE":
            continue
        stmt = row.get("statement", "")
        src = row.get("source_text", "")
        section = row.get("source_section", "")
        mapping = mappings.get(rid, {})
        cap = mapping.get("canonical_capability", "")
        phase = mapping.get("primary_implementation_phase", "")
        if row.get("requirement_type") in NON_IMPL and phase:
            errors.append(f"non-actionable record retains implementation phase: {rid}")
        if OPEN_FOLDER.search(src + " " + stmt) and cap in {"Local AI worker", "Editing", "Authentication and users", "Backup, trash, restore and rebuild"}:
            errors.append(f"open-in-folder assigned to AI/mutation/identity/storage work: {rid}")
        if NAVIGATION.search(stmt):
            pid = member_by_id.get(rid, {}).get("work_package_id", "")
            pkg_name = str(package_by_id.get(pid, {}).get("name", ""))
            if MUTATION_PACKAGE.search(pkg_name):
                errors.append(f"navigation placed in mutation/identity-state package: {rid} -> {pid}")
        if RAW_EXPORT.search(src + " " + stmt) and cap != "Editing":
            errors.append(f"inspector raw-data export not assigned by source meaning: {rid} {cap}")
        if HARDWARE.search(src + " " + stmt) and cap not in {"Local AI worker", "Performance and scale"}:
            errors.append(f"hardware-assessment statement conflicts with capability: {rid} {cap}")
        if PERF_VALIDATION.search(stmt) and cap not in {"Performance and scale", "Local AI worker", "Jobs and notifications"}:
            errors.append(f"performance-measurement statement conflicts with capability: {rid} {cap}")
        if PLANNING.search(src + " " + section) and cap != "Planning and verification governance":
            errors.append(f"planning-governance statement conflicts with capability: {rid} {cap}")
        if rid in AUDIT_FIXES:
            expected_cap, expected_phase, expected_pkg = AUDIT_FIXES[rid]
            actual_pkg = member_by_id.get(rid, {}).get("work_package_id", "")
            if (cap, phase) != (expected_cap, expected_phase):
                errors.append(f"semantic audit correction not applied to mapping: {rid} {cap}/{phase}")
            if actual_pkg != expected_pkg:
                errors.append(f"semantic audit correction not applied to package: {rid} -> {actual_pkg}, expected {expected_pkg}")
        if rid in EXTRA_PACKAGE_FIXES:
            expected_pkg = EXTRA_PACKAGE_FIXES[rid]
            actual_pkg = member_by_id.get(rid, {}).get("work_package_id", "")
            if actual_pkg != expected_pkg:
                errors.append(f"corrected semantic package not applied: {rid} -> {actual_pkg}, expected {expected_pkg}")

    for row in v2_rows:
        if row["final_classification"] in NON_IMPL and row.get("primary_phase"):
            errors.append(f"v2 non-implementation record retains phase: {row['record_id']}")

    audit_by_id = {row["Canonical ID"]: row for row in audit_rows}
    for rid, row in audit_by_id.items():
        mapping = mappings.get(rid, {})
        if not mapping:
            continue
        if row["Corrected capability"] != mapping.get("canonical_capability", ""):
            errors.append(f"audit corrected capability disagrees with mapping: {rid}")
        if row["Corrected phase"] != mapping.get("primary_implementation_phase", ""):
            errors.append(f"audit corrected phase disagrees with mapping: {rid}")

    return errors


def check_zero_template_claim(report_dir: Path) -> list[str]:
    """A report may claim zero template matches only with an independent audit."""
    errors: list[str] = []
    audit = report_dir / "legacy-template-semantic-audit.csv"
    metrics = report_dir / "pass1-template-metrics.json"
    audit_rows = read_csv(audit) if audit.exists() else []
    metric_data = read_json(metrics) if metrics.exists() else {}
    for path in sorted(report_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        if re.search(r"template", text, re.I) and re.search(r"\b(0|zero)\b", text, re.I):
            before = (metric_data.get("before") or {}).get("exactLegacyOutput")
            after = (metric_data.get("after") or {}).get("exactLegacyOutput")
            if not audit_rows or before is None or after is None or before <= 0 or after != 0:
                errors.append(f"zero-template claim lacks independent audit evidence: {path.name}")
    return errors


def check_mapping_records(rows: list[dict[str, str]]) -> list[str]:
    errors: list[str] = []
    for row in rows:
        rid = row.get("canonical_id", "")
        status = row.get("reviewer_status", "")
        if row.get("primary_implementation_phase") and not status.startswith("REVIEWED_"):
            errors.append(f"mapping not reviewed: {rid}")
        if not row.get("primary_implementation_phase") and status not in {"NOT_APPLICABLE", "REVIEWED_CONFIRMED", "REVIEWED_CORRECTED"}:
            errors.append(f"inactive mapping has invalid review status: {rid}")
        if not row.get("mapping_rationale"):
            errors.append(f"mapping rationale missing: {rid}")
        phase = row.get("primary_implementation_phase", "")
        text = " ".join(row.get(key, "") for key in ("canonical_capability", "mapping_rationale")).casefold()
        if phase == "I2" and re.search(r"heif|heic|\braw\b|video ingestion|companion|metadata extraction|preview generation|thumbnail generation|scanner|watcher", text):
            errors.append(f"media pipeline assigned to shell I2: {rid}")
        if phase in {"I0", "I1", "I2", "I15"} and row.get("canonical_capability") in {"People and faces", "Relationships and attribution", "Mind-map projections", "Local AI worker"}:
            errors.append(f"implausible capability-phase pair: {rid} {phase}")
        if phase and phase not in {f"I{index}" for index in range(16)}:
            errors.append(f"invalid primary phase: {rid} {phase}")
    known = {row.get("canonical_id"): row for row in rows}
    for rid in ("CAN-FAIL-01", "CAN-LAM-ASSET-004"):
        if rid not in known or known[rid].get("primary_implementation_phase") != "I4":
            errors.append(f"known media mapping not corrected: {rid}")
    return errors


def check_package_records(packages: list[dict[str, object]], membership: list[dict[str, str]], active_ids: set[str] | None = None) -> list[str]:
    errors: list[str] = []
    package_ids = {str(package.get("work_package_id", "")) for package in packages}
    seen: Counter[str] = Counter(row.get("canonical_id", "") for row in membership)
    if active_ids is not None:
        for rid in sorted(active_ids - set(seen)):
            errors.append(f"orphan active requirement: {rid}")
        for rid in sorted(set(seen) - active_ids):
            errors.append(f"non-active membership: {rid}")
    for rid, count in seen.items():
        if count != 1:
            errors.append(f"requirement membership count {count}: {rid}")
    by_package: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
    for row in membership:
        pid = row.get("work_package_id", "")
        by_package[pid].append(row)
        if pid not in package_ids:
            errors.append(f"membership references missing package: {pid}")
        if row.get("reviewer_status") not in {"REVIEWED", "REVIEW_REQUIRED"}:
            errors.append(f"membership not reviewed: {row.get('canonical_id')}")
    required = ("objective", "bounded_surface", "explicit_exclusions", "cohesion_rationale", "deliverables", "contracts_affected", "schemas_affected", "tests", "failure_cases", "rollback_or_recovery", "completion_evidence", "commit_boundary", "exit_gate")
    for package in packages:
        pid = str(package.get("work_package_id", ""))
        name = str(package.get("name", ""))
        if "source-boundary slice" in name.casefold():
            errors.append(f"source-boundary slice package: {pid}")
        if package.get("capacity_split") is not False or package.get("source_section_split") is not False:
            errors.append(f"mechanical package split flag: {pid}")
        if package.get("reviewer_status") != "REVIEWED":
            errors.append(f"package not reviewed: {pid}")
        for field in required:
            if not package.get(field):
                errors.append(f"package missing {field}: {pid}")
        # A package may be a schema/component/contract foundation with no primary
        # requirement membership. Membership compatibility is checked row-by-row.
    return errors


def check_phase_package_consistency(
    requirements: list[dict[str, str]], mappings: dict[str, dict[str, str]],
    packages: list[dict[str, object]], membership: list[dict[str, str]],
) -> list[str]:
    errors: list[str] = []
    package_phase = {str(row["work_package_id"]): str(row["implementation_phase"]) for row in packages}
    requirement_by_id = {row["canonical_id"]: row for row in requirements}
    for row in membership:
        if row.get("reviewer_status") == "REVIEW_REQUIRED":
            continue
        rid, pid = row["canonical_id"], row["work_package_id"]
        phase = mappings[rid]["primary_implementation_phase"]
        if package_phase.get(pid) != phase:
            errors.append(f"requirement/package phase mismatch: {rid} {phase} != {pid} {package_phase.get(pid)}")
        capability = requirement_by_id[rid].get("canonical_capability", "").casefold()
        package = next((item for item in packages if item["work_package_id"] == pid), None)
        reviewed = {str(value).casefold() for value in (package or {}).get("reviewed_capabilities", [])}
        if capability and reviewed and capability not in reviewed:
            errors.append(f"package capability incompatible: {rid} {pid}")
    return errors


def check_dependency_records(packages: list[dict[str, object]], edges: list[dict[str, str]]) -> list[str]:
    errors: list[str] = []
    nodes = {str(package["work_package_id"]) for package in packages}
    adjacency: defaultdict[str, list[str]] = defaultdict(list)
    indegree = {node: 0 for node in nodes}
    allowed = {
        "REQUIRES_PROVENANCE", "REQUIRES_DECISION", "REQUIRES_COMPONENT", "REQUIRES_SCHEMA",
        "REQUIRES_STORAGE", "REQUIRES_IDENTITY", "REQUIRES_COMMAND_CONTRACT",
        "REQUIRES_FILESYSTEM_AUTHORITY", "REQUIRES_TRANSACTION_ENGINE", "REQUIRES_DERIVED_INDEX",
        "REQUIRES_SCANNER", "REQUIRES_WATCHER", "REQUIRES_AI_WORKER", "REQUIRES_MODEL_REGISTRY",
        "REQUIRES_REVIEW_PROTOCOL", "REQUIRES_GRAPH_MODEL", "REQUIRES_REPLACEMENT_VERIFIED",
        "REQUIRES_PLATFORM_PROOF", "REQUIRES_RELEASE_GATE", "REQUIRES_CONTRACT", "REQUIRES_RUNTIME",
        "REQUIRES_INDEX", "REQUIRES_UI_SHELL", "REQUIRES_WORKER", "REQUIRES_COMPONENT_DECISION",
        "REQUIRES_SECURITY_BOUNDARY", "REQUIRES_AUTHORITY_MODEL",
    }
    seen: set[tuple[str, str, str]] = set()
    for edge in edges:
        target, prerequisite, kind = edge.get("work_package_id", ""), edge.get("prerequisite_work_package_id", ""), edge.get("dependency_type", "")
        key = (target, prerequisite, kind)
        if key in seen:
            errors.append(f"duplicate dependency: {key}")
        seen.add(key)
        if target not in nodes or prerequisite not in nodes or target == prerequisite:
            errors.append(f"invalid dependency endpoints: {target} <- {prerequisite}")
            continue
        if kind not in allowed:
            errors.append(f"invalid dependency type: {kind}")
        rationale = edge.get("technical_rationale", "")
        if not rationale or re.search(r"previous\s+package|next\s+package|adjacent\s+package|package\s+number|array\s+order", rationale, re.I) or edge.get("artificial_adjacency") != "false":
            errors.append(f"artificial adjacency dependency: {target} <- {prerequisite}")
        if not edge.get("review_status", "").startswith("REVIEWED_"):
            errors.append(f"dependency not reviewed: {target} <- {prerequisite}")
        if not edge.get("evidence"):
            errors.append(f"dependency lacks evidence: {target} <- {prerequisite}")
        adjacency[prerequisite].append(target)
        indegree[target] += 1
    queue = deque(sorted(node for node, degree in indegree.items() if degree == 0))
    visited = 0
    while queue:
        node = queue.popleft()
        visited += 1
        for nxt in adjacency[node]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)
    if visited != len(nodes):
        errors.append("dependency cycle detected")
    roots = {node for node, degree in indegree.items() if degree == 0} if visited == 0 else {str(package["work_package_id"]) for package in packages} - {edge["work_package_id"] for edge in edges}
    package_by_id = {str(package["work_package_id"]): package for package in packages}
    for root in roots:
        package = package_by_id[root]
        if package.get("root_status") != "TRUE_ROOT" or not package.get("root_rationale") or not package.get("root_evidence"):
            errors.append(f"unexplained root package: {root}")
    for pid, package in package_by_id.items():
        if pid not in roots and package.get("root_status") == "TRUE_ROOT":
            errors.append(f"non-root package falsely marked root: {pid}")
    required_edges = {
        ("WP-I5-006", "WP-I3-001"), ("WP-I5-007", "WP-I4-010"), ("WP-I5-011", "WP-I4-012"),
        ("WP-I5-008", "WP-I4-008"), ("WP-I6-005", "WP-I6-002"), ("WP-I6-006", "WP-I6-002"),
        ("WP-I7-007", "WP-I7-004"), ("WP-I7-008", "WP-I7-007"), ("WP-I8-005", "WP-I8-004"),
        ("WP-I8-006", "WP-I8-005"), ("WP-I11-003", "WP-I11-001"), ("WP-I12-006", "WP-I12-001"),
        ("WP-I12-007", "WP-I3-014"), ("WP-I4-012", "WP-I4-010"), ("WP-I9-004", "WP-I9-001"),
        ("WP-I11-002", "WP-I11-001"), ("WP-I11-009", "WP-I11-003"), ("WP-I13-003", "WP-I13-002"),
        ("WP-I13-006", "WP-I3-011"), ("WP-I15-005", "WP-I15-001"), ("WP-I15-015", "WP-I15-008"),
    }
    pairs = {(edge["work_package_id"], edge["prerequisite_work_package_id"]) for edge in edges}
    for pair in sorted(required_edges - pairs):
        errors.append(f"required technical prerequisite absent: {pair[0]} <- {pair[1]}")
    return errors


def scan_open_objects(value: object, path: str = "$") -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        if value.get("type") == "object" and not any(key in value for key in ("properties", "$ref", "oneOf", "allOf", "anyOf")):
            if not (value.get("x-lamha-approved-open-object") and value.get("x-lamha-rationale") and value.get("propertyNames") and value.get("additionalProperties") not in (None, True, {})):
                errors.append(f"untyped object: {path}")
        if value.get("type") == "array" and isinstance(value.get("items"), dict):
            item = value["items"]
            if item.get("type") == "object" and not any(key in item for key in ("properties", "$ref", "oneOf", "allOf", "anyOf")):
                errors.append(f"anonymous object array: {path}")
        for key, child in value.items():
            errors.extend(scan_open_objects(child, f"{path}/{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(scan_open_objects(child, f"{path}/{index}"))
    return errors


def check_schema_document(path: Path) -> list[str]:
    errors: list[str] = []
    schema = read_json(path)
    if Draft202012Validator is None:
        errors.append(f"jsonschema unavailable for meta-validation: {path.name}")
    elif isinstance(schema, dict) and "$schema" in schema:
        try:
            Draft202012Validator.check_schema(schema)
        except Exception as error:
            errors.append(f"invalid Draft 2020-12 schema {path.name}: {error}")

    def walk(value: object) -> None:
        if isinstance(value, dict):
            ref = value.get("$ref")
            if isinstance(ref, str) and not ref.startswith(("#", "http://", "https://")):
                target = path.parent / ref.split("#", 1)[0]
                if not target.exists():
                    errors.append(f"unresolved local schema reference in {path.name}: {ref}")
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
    walk(schema)
    return errors


def check_command_records(commands: list[dict[str, object]], schema_root: Path | None = None) -> list[str]:
    errors: list[str] = []
    for command in commands:
        cid = str(command.get("commandId", ""))
        read_only, mutating = command.get("readOnly"), command.get("mutating")
        if not isinstance(read_only, bool) or not isinstance(mutating, bool) or read_only == mutating:
            errors.append(f"invalid read/mutating classification: {cid}")
        action = cid.split(".", 1)[-1]
        if action in {"get", "list", "page", "status", "inspect", "history"} and mutating:
            errors.append(f"getter/list command marked mutating: {cid}")
        if command.get("duration") == "LONG_RUNNING" and not command.get("operationIdReturned"):
            errors.append(f"long-running command lacks operation handle: {cid}")
        if mutating and not command.get("requestIdRequired"):
            errors.append(f"mutating command lacks request id: {cid}")
        if not command.get("errorCodes"):
            errors.append(f"command lacks error subset: {cid}")
        if not str(command.get("reviewerStatus", "")).startswith("REVIEWED_"):
            errors.append(f"command flags not reviewed: {cid}")
        if schema_root:
            for side in ("requestSchema", "responseSchema"):
                path = schema_root / str(command.get(side, "")).removeprefix("./")
                if not path.exists():
                    errors.append(f"missing {side}: {cid} {path}")
                else:
                    errors.extend(f"{cid} {side}: {error}" for error in scan_open_objects(read_json(path)))
        pagination = command.get("pagination", {})
        if isinstance(pagination, dict) and pagination.get("supported") and not all(pagination.get(key) for key in ("cursorSchema", "filterSchema", "sortSchema")):
            errors.append(f"pagination structures missing: {cid}")
        if schema_root and isinstance(pagination, dict) and pagination.get("supported"):
            for key in ("cursorSchema", "filterSchema", "sortSchema"):
                path = schema_root / str(pagination.get(key, "")).removeprefix("./")
                if not path.exists():
                    errors.append(f"missing pagination {key}: {cid} {path}")
    return errors


def check_component_records(rows: list[dict[str, str]], packages: list[dict[str, object]]) -> list[str]:
    errors: list[str] = []
    phase_order = {f"I{index}": index for index in range(16)}
    package_phase = {str(package["work_package_id"]): str(package["implementation_phase"]) for package in packages}
    for row in rows:
        component = row.get("component", "")
        for field in ("owning_phase", "decision_package", "blocking_work_package", "required_before_packages", "version_status", "licence_status", "redistribution_status", "platform_impact", "packaging_impact", "alternatives", "final_decision_evidence", "reviewer_status"):
            if not row.get(field):
                errors.append(f"component missing {field}: {component}")
        refs = [value for field in ("decision_package", "blocking_work_package", "required_before_packages") for value in row.get(field, "").split(";") if value]
        for pid in refs:
            if pid not in package_phase:
                errors.append(f"component references missing package: {component} {pid}")
        owner = phase_order.get(row.get("owning_phase", ""), 99)
        decision = package_phase.get(row.get("decision_package", ""), "I99")
        decision_order = phase_order.get(decision, 99)
        before_orders = [phase_order.get(package_phase.get(pid, "I99"), 99) for pid in row.get("required_before_packages", "").split(";") if pid]
        if before_orders and decision_order > min(before_orders):
            errors.append(f"component decision deferred after required work: {component}")
        if owner < 15 and package_phase.get(row.get("blocking_work_package", "")) == "I15":
            errors.append(f"component blocked by unrelated future packaging package: {component}")
    return errors


def check_record_schemas(index: list[dict[str, str]], root: Path) -> list[str]:
    errors: list[str] = []
    for row in index:
        path = root / row["schema"]
        if not path.exists():
            errors.append(f"missing record schema: {row['schema']}")
            continue
        schema = read_json(path)
        errors.extend(f"{row['schema']}: {error}" for error in scan_open_objects(schema))
        required = set(schema.get("required", [])) if isinstance(schema, dict) else set()
        for field in ("schemaVersion", "id", "revision", "createdAt", "updatedAt", "authority", "privacy", "provenance", "extensions"):
            if field not in required:
                errors.append(f"record missing required {field}: {row['schema']}")
        x = schema.get("x-lamha", {}) if isinstance(schema, dict) else {}
        for field in ("authority", "privacyClassification", "timestampSemantics", "unknownFieldPolicy", "migrationPolicy"):
            if not x.get(field):
                errors.append(f"record metadata missing {field}: {row['schema']}")
    by_name = {Path(row["schema"]).name: read_json(root / row["schema"]) for row in index}
    asset_fields = set(by_name.get("asset.schema.json", {}).get("properties", {}))
    expected_asset = {"identityId", "rootId", "primaryPath", "originalFilename", "extension", "mediaType", "mimeType", "fileSizeBytes", "contentHash", "captureTime", "filesystemTimes", "dimensions", "durationMs", "camera", "gps", "sidecars", "companions", "eventIds", "visiblePersonIds", "tagIds", "albumIds", "favorite", "rating", "reviewState", "editRecipeId", "derivatives", "integrityState", "provenance", "revision"}
    if not expected_asset <= asset_fields:
        errors.append(f"asset schema skeletal; missing {sorted(expected_asset - asset_fields)}")
    event_fields = set(by_name.get("event.schema.json", {}).get("properties", {}))
    expected_event = {"title", "startAt", "endAt", "location", "assetMemberships", "folderState", "inference", "attendeePersonIds", "photographerPersonIds", "conflictState", "history", "reviewState"}
    if not expected_event <= event_fields:
        errors.append(f"event schema skeletal; missing {sorted(expected_event - event_fields)}")
    operations = by_name.get("file_operation_plan.schema.json", {})
    serialized = json.dumps(operations)
    for variant in ("MOVE", "RENAME", "COPY", "DELETE_TO_TRASH", "RESTORE", "SIDECAR_WRITE", "DIRECTORY_CREATE", "EXPORT", "BACKUP_COPY"):
        if f'"{variant}"' not in serialized:
            errors.append(f"file operation variant missing: {variant}")
    return errors


def check_authority_registry(rows: list[dict[str, str]], schema_index: list[dict[str, str]], root: Path) -> list[str]:
    errors: list[str] = []
    required = {"Saved views", "Memories", "Location records", "Export manifests", "Restore manifests", "Privacy-export recipes", "Filename templates", "Drive registry", "Derivative manifests", "AI candidate and proposal records"}
    by_concept = {row.get("concept", ""): row for row in rows}
    indexed = {row["schema"] for row in schema_index}
    for concept in sorted(required - set(by_concept)):
        errors.append(f"durable concept lacks authority decision: {concept}")
    fields = ("authority_classification", "persistence_location", "rebuild_source", "revision_semantics", "migration_owner", "work_package", "rationale")
    allowed = {"DEDICATED_AUTHORITATIVE_SCHEMA", "EMBEDDED_AUTHORITATIVE_STRUCTURE", "DERIVED_ONLY_PROJECTION", "OPERATIONAL_TRANSIENT", "INTENTIONALLY_OUT_OF_SCOPE"}
    for concept, row in by_concept.items():
        for field in fields:
            if not row.get(field):
                errors.append(f"authority decision missing {field}: {concept}")
        classification = row.get("authority_classification")
        if classification not in allowed:
            errors.append(f"invalid authority classification: {concept}")
        if classification == "DEDICATED_AUTHORITATIVE_SCHEMA":
            schema = row.get("authoritative_schema", "")
            if not schema or schema not in indexed or not (root / schema).exists():
                errors.append(f"authoritative concept lacks schema: {concept}")
        if classification == "EMBEDDED_AUTHORITATIVE_STRUCTURE":
            parents = [value for value in row.get("embedding_parent", "").split(";") if value]
            if not parents:
                errors.append(f"embedded authority lacks parent: {concept}")
            for parent in parents:
                path = root / parent
                if not path.exists():
                    errors.append(f"embedded authority parent missing: {concept} {parent}")
        if classification == "DERIVED_ONLY_PROJECTION" and not row.get("rebuild_source"):
            errors.append(f"derived concept lacks rebuild source: {concept}")
    asset = read_json(root / "records" / "asset.schema.json")
    event = read_json(root / "records" / "event.schema.json")
    settings = read_json(root / "records" / "settings.schema.json")
    if not isinstance(asset.get("properties", {}).get("gps"), dict) or not isinstance(event.get("properties", {}).get("location"), dict):
        errors.append("Location records lack typed asset/event embedding")
    templates = settings.get("properties", {}).get("filenameTemplates", {})
    if not isinstance(templates, dict) or templates.get("type") != "array" or not isinstance(templates.get("items"), dict) or "$ref" not in templates["items"]:
        errors.append("Filename templates lack typed settings embedding")
    return errors


def recompute_quality_metrics(
    requirements: list[dict[str, str]], mappings: dict[str, dict[str, str]],
    membership: list[dict[str, str]], packages: list[dict[str, object]],
    edges: list[dict[str, str]], schema_index: list[dict[str, str]], authority: list[dict[str, str]],
) -> dict[str, int]:
    active = [
        row for row in requirements
        if row["supersession_status"] == "ACTIVE"
        and row["requirement_type"] in IMPLEMENTATION_TYPES
        and mappings[row["canonical_id"]]["primary_implementation_phase"]
    ]
    package_phase = {str(row["work_package_id"]): str(row["implementation_phase"]) for row in packages}
    phase_mismatches = sum(mappings[row["canonical_id"]]["primary_implementation_phase"] != package_phase.get(row["work_package_id"]) for row in membership)
    required_concepts = {"Saved views", "Memories", "Location records", "Export manifests", "Restore manifests", "Privacy-export recipes", "Filename templates", "Drive registry", "Derivative manifests", "AI candidate and proposal records"}
    authority_by_concept = {row["concept"]: row for row in authority}
    indexed = {row["schema"] for row in schema_index}
    missing_authority_schema = len(required_concepts - set(authority_by_concept))
    for concept in required_concepts & set(authority_by_concept):
        row = authority_by_concept[concept]
        if row["authority_classification"] == "DEDICATED_AUTHORITATIVE_SCHEMA" and row["authoritative_schema"] not in indexed:
            missing_authority_schema += 1
        if row["authority_classification"] == "EMBEDDED_AUTHORITATIVE_STRUCTURE" and not row["embedding_parent"]:
            missing_authority_schema += 1
        if row["authority_classification"] == "DERIVED_ONLY_PROJECTION" and not row["rebuild_source"]:
            missing_authority_schema += 1
    return {
        "fragmentary_active_records": sum(len(meaningful_words(row["statement"])) < 8 for row in active),
        "non_observable_requirements": sum(not OBSERVABLE.search(row["statement"]) for row in active),
        "generic_template_records": sum(bool(GENERIC_TEMPLATE.search(row["statement"].strip())) for row in active),
        "untestable_criteria": sum(
            row["requirement_type"] == "ACCEPTANCE_CRITERION"
            and (not re.search(r"\b(given|when)\b", row["statement"] + " " + row.get("acceptance_criteria", ""), re.I) or not OBSERVABLE.search(row["statement"] + " " + row.get("acceptance_criteria", "")))
            for row in active
        ),
        "missing_parent_relationships": sum(row["requirement_type"] == "ACCEPTANCE_CRITERION" and not row["parent_requirement_id"] for row in active),
        "missing_verification_methods": sum(not row["verification_method"] for row in active),
        "phase_package_mismatches": phase_mismatches,
        "stale_package_references": sum("work_package_id" in row for row in requirements),
        "unreviewed_mappings": sum(
            bool(mappings[row["canonical_id"]]["primary_implementation_phase"])
            and not mappings[row["canonical_id"]]["reviewer_status"].startswith("REVIEWED_")
            for row in active
        ),
        "unreviewed_package_memberships": sum(row.get("reviewer_status") not in {"REVIEWED", "REVIEW_REQUIRED"} for row in membership),
        "missing_dependency_rationales": sum(not row.get("technical_rationale") or not row.get("evidence") or not row.get("review_status", "").startswith("REVIEWED_") for row in edges),
        "missing_authority_schema_decisions": missing_authority_schema,
    }


def check_metrics_honesty(report: dict[str, object], computed: dict[str, int], builder_text: str) -> list[str]:
    errors: list[str] = []
    reported = report.get("computedQualityMetrics", {})
    if reported != computed:
        errors.append(
            "reported quality metrics differ from independent computation: "
            f"{json.dumps(reported, sort_keys=True)} != {json.dumps(computed, sort_keys=True)}"
        )
    if re.search(r'"(?:finalFragmentaryOrNonObservable|finalGenericCriteria)"\s*:\s*0\b', builder_text):
        errors.append("hard-coded zero quality metric in builder")
    if report.get("finalFragmentaryOrNonObservable") == 0 and (computed["fragmentary_active_records"] or computed["non_observable_requirements"]):
        errors.append("zero fragments claimed while fragmentary or non-observable records exist")
    return errors


def check_review_script_text(text: str) -> list[str]:
    errors: list[str] = []
    if re.search(r"for\s+\w+\s+in\s+\w+\s*:\s*(?:\n\s*)?\w+\s*\[\s*['\"](?:review_status|reviewer_status|normalization_reviewer_status)['\"]\s*\]\s*=\s*['\"]REVIEW", text):
        errors.append("blanket script marks every row reviewed")
    return errors


def check_review_provenance(coverage: dict[str, object]) -> list[str]:
    errors: list[str] = []
    if int(coverage.get("unmatchedPositiveRows", -1)) != 0:
        errors.append(f"positive review status without explicit provenance: {coverage.get('unmatchedPositiveRows')}")
    return errors


def check_active_scripts_for_automatic_certification(tools_dir: Path) -> list[str]:
    errors: list[str] = []
    pattern = re.compile(
        r"setdefault\(['\"](?:review_status|reviewer_status)['\"]\s*,\s*['\"]REVIEWED"
        r"|\[['\"](?:review_status|reviewer_status)['\"]\]\s*=\s*['\"]REVIEWED['\"]",
    )
    for path in sorted(tools_dir.glob("*.py")):
        if "superseded" in str(path):
            continue
        text = path.read_text(encoding="utf-8")
        if pattern.search(text):
            errors.append(f"automatic positive review certification: {path.name}")
    return errors


def check_v3_requirement_ledger(
    requirements: list[dict[str, str]],
    mappings: dict[str, dict[str, str]],
    v3_rows: list[dict[str, str]],
) -> list[str]:
    errors: list[str] = []
    impl_types = {
        "FUNCTIONAL_REQUIREMENT", "NONFUNCTIONAL_REQUIREMENT", "ARCHITECTURAL_INVARIANT",
        "SECURITY_INVARIANT", "PRIVACY_INVARIANT", "DATA_INTEGRITY_INVARIANT",
        "IMPLEMENTATION_CONSTRAINT", "ACCEPTANCE_CRITERION", "OPTIONAL_ADAPTER",
        "VERIFICATION_GATE", "REMOVAL_GATE", "RELEASE_GATE", "PROHIBITION",
    }
    v3_by_id = {row.get("Canonical ID", ""): row for row in v3_rows}
    for row in requirements:
        rid = row["canonical_id"]
        if row.get("supersession_status") != "ACTIVE" or row.get("requirement_type") not in impl_types:
            continue
        if not mappings.get(rid, {}).get("primary_implementation_phase"):
            continue
        v3 = v3_by_id.get(rid)
        if not v3:
            errors.append(f"actionable requirement missing v3 review row: {rid}")
            continue
        status = v3.get("Review status", "")
        if status not in {"REVIEWED_CONFIRMED", "REVIEWED_CORRECTED"}:
            errors.append(f"actionable requirement not positively reviewed: {rid}")
            continue
        substantive = (
            v3.get("Final reviewed statement")
            and v3.get("Verification method")
            and v3.get("Item-specific rationale")
            and v3.get("Actor or subsystem")
            and v3.get("Observable result")
        )
        if v3.get("Requirement type") == "ACCEPTANCE_CRITERION" and not v3.get("Acceptance criteria"):
            substantive = False
        if not substantive:
            errors.append(f"actionable requirement v3 review lacks substantive fields: {rid}")
        rationale = v3.get("Item-specific rationale", "")
        if len(rationale) < 40:
            errors.append(f"actionable requirement v3 rationale too short: {rid}")
    return errors


def check_pass_b_ledgers(
    packages: list[dict[str, object]],
    membership: list[dict[str, str]],
    dependencies: list[dict[str, str]],
    package_reviews: list[dict[str, str]],
    membership_reviews: list[dict[str, str]],
    dependency_reviews: list[dict[str, str]],
) -> list[str]:
    errors: list[str] = []
    package_review_by_id = {row.get("Final package ID", ""): row for row in package_reviews}
    membership_review_by_id = {row.get("Canonical ID", ""): row for row in membership_reviews}
    dependency_review_by_key = {
        f"{row.get('Dependent package','')}<-{row.get('Prerequisite package','')}": row
        for row in dependency_reviews
    }
    for package in packages:
        pid = str(package["work_package_id"])
        row = package_review_by_id.get(pid)
        if not row:
            errors.append(f"package missing Pass B review: {pid}")
        elif row.get("Review status") != "REVIEWED_CONFIRMED":
            errors.append(f"package Pass B review not confirmed: {pid}")
    for row in membership:
        review = membership_review_by_id.get(row["canonical_id"])
        if not review or review.get("Review status") != "REVIEWED_CONFIRMED":
            errors.append(f"membership Pass B review not confirmed: {row['canonical_id']}")
    for edge in dependencies:
        key = f"{edge['work_package_id']}<-{edge['prerequisite_work_package_id']}"
        review = dependency_review_by_key.get(key)
        if not review or review.get("Review status") != "REVIEWED_CONFIRMED":
            errors.append(f"dependency Pass B review not confirmed: {key}")
    return errors


def check_pass_b_architecture_completeness(
    plan_root: Path,
    packages: list[dict[str, object]],
    memberships: list[dict[str, str]],
) -> list[str]:
    errors: list[str] = []
    required = {
        "reviewed-work-package-members-v1.csv": "13-reports/reviewed-work-package-members-v1.csv",
        "pass-b-large-package-review.csv": "13-reports/pass-b-large-package-review.csv",
        "pass-b-multi-capability-member-review.csv": "13-reports/pass-b-multi-capability-member-review.csv",
        "reviewed-package-contract-schema-verification-v1.csv": "13-reports/reviewed-package-contract-schema-verification-v1.csv",
        "reviewed-package-test-verification-v1.csv": "13-reports/reviewed-package-test-verification-v1.csv",
        "reviewed-package-exit-gates-v1.csv": "13-reports/reviewed-package-exit-gates-v1.csv",
        "pass-b-adversarial-results.json": "13-reports/pass-b-adversarial-results.json",
    }
    for label, rel in required.items():
        path = plan_root / rel
        if not path.exists() or path.stat().st_size == 0:
            errors.append(f"Pass B architecture artifact missing or empty: {label}")
    adversarial = plan_root / "13-reports" / "pass-b-adversarial-results.json"
    if adversarial.exists():
        data = read_json(adversarial)
        if int(data.get("missingRequiredFailureClasses", -1)) != 0:
            errors.append(f"Pass B missing required adversarial classes: {data.get('missingRequiredFailureClasses')}")
        if data.get("status") != "PASS":
            errors.append("Pass B adversarial suite is not complete")
    i3_members = [m for m in memberships if m["work_package_id"] == "WP-I3-001"]
    if i3_members:
        member_review = plan_root / "13-reports" / "reviewed-work-package-members-v1.csv"
        if member_review.exists():
            rows = read_csv(member_review)
            i3_reviewed = {r["Canonical ID"] for r in rows if r.get("Package ID") == "WP-I3-001"}
            if len(i3_reviewed) != len(i3_members):
                errors.append(f"WP-I3-001 member review incomplete: {len(i3_reviewed)}/{len(i3_members)}")
    return errors


def check_pass_b_independent_evidence(
    member_rows: list[dict[str, str]],
    contract_rows: list[dict[str, str]],
    test_rows: list[dict[str, str]],
    exit_rows: list[dict[str, str]],
    decision_rows: list[dict[str, str]],
) -> list[str]:
    errors: list[str] = []
    groups = [
        ("member", member_rows),
        ("contract/schema", contract_rows),
        ("test", test_rows),
        ("exit-gate", exit_rows),
        ("package-decision", decision_rows),
    ]
    for label, rows in groups:
        if not rows:
            errors.append(f"independent {label} verification ledger is empty")
            continue
        for row in rows:
            if row.get("Verification status") not in {"VERIFIED", "CORRECTED", "MOVED"}:
                errors.append(f"independent {label} row not verified: {row.get('Package ID', row.get('Canonical ID', ''))}")
            evidence = row.get("Evidence sources", "") or row.get("Evidence", "")
            if not evidence:
                errors.append(f"independent {label} row lacks evidence source: {row.get('Package ID', row.get('Canonical ID', ''))}")
            rationale = row.get("Item-specific rationale", "")
            if len(rationale) < 40:
                errors.append(f"independent {label} row rationale too short: {row.get('Package ID', row.get('Canonical ID', ''))}")
    return errors


def check_component_licence_completeness(
    components: list[dict[str, str]],
    dependencies: list[dict[str, str]],
) -> list[str]:
    errors: list[str] = []
    pending_statuses = {
        "PENDING", "PENDING_I0_INVENTORY", "PENDING_REPOSITORY_PROOF", "PENDING_OPTIONAL",
        "OS_COMPONENT_REVIEW_PENDING", "BUILD_ONLY_PENDING", "BUNDLED_SOURCE_PENDING",
    }
    approved_licences = {"APPROVED", "APPROVED_WITH_NOTICE", "APPROVED_BUILD_ONLY", "PLATFORM_PROVIDED", "OPTIONAL_NOT_BUNDLED", "REJECTED"}
    edges = {(d["work_package_id"], d["prerequisite_work_package_id"]) for d in dependencies}
    for component in components:
        name = component.get("component", "")
        if component.get("final_status", "") in pending_statuses or component.get("version_status", "") in pending_statuses:
            errors.append(f"component decision pending: {name}")
        if component.get("licence_status", "") not in approved_licences or component.get("licence_status", "") in pending_statuses:
            errors.append(f"component licence pending or invalid: {name}")
        if not component.get("redistribution_status", ""):
            errors.append(f"component redistribution missing: {name}")
        if not component.get("decision_package", ""):
            errors.append(f"component decision package missing: {name}")
        if not component.get("version_rule", ""):
            errors.append(f"component version rule missing: {name}")
        if len(component.get("reason", "")) < 40:
            errors.append(f"component rationale generic: {name}")
        consumers = [x.strip() for x in component.get("consumer_packages", "").split(";") if x.strip()]
        for consumer in consumers:
            if (consumer, component.get("decision_package", "")) not in edges:
                errors.append(f"component consumer lacks decision dependency: {consumer} -> {component.get('decision_package')}")
        if component.get("final_status") == "REJECTED" and consumers:
            errors.append(f"rejected component still has consumers: {name}")
    return errors


def check_final_100_percent_certification(plan_root: Path) -> list[str]:
    errors: list[str] = []
    expected = "FULL IMPLEMENTATION PLANNING 100% COMPLETE \u2014 WP-I0-001 MAY BEGIN"
    old = "IMPLEMENTATION-READY PLANNING COMPLETE \u2014 I0 MAY BEGIN"
    cert_path = plan_root / "13-reports" / "final-100-percent-certification.json"
    cert = read_json(cert_path) if cert_path.exists() else {}
    if cert.get("status") != "PASS" or cert.get("readiness_declaration") != expected:
        errors.append("final 100% certification report missing or incorrect")
    if cert.get("implementation_planning_100_percent_complete") is not True:
        errors.append("final certification implementation_planning flag is not true")
    if cert.get("remaining_blockers"):
        errors.append("final certification has remaining blockers")
    handoff = (plan_root / "14-handoff" / "START-HERE.md").read_text(encoding="utf-8")
    if expected not in handoff:
        errors.append("handoff does not contain the final 100% declaration")
    if old in handoff:
        errors.append("old readiness declaration remains active in handoff")
    proof_path = plan_root / "13-reports" / "final-determinism-proof.json"
    proof = read_json(proof_path) if proof_path.exists() else {}
    if proof.get("status") != "PASS":
        errors.append("final determinism proof did not pass")
    return errors


def check_ai_model_override_amendment(
    requirements: list[dict[str, str]],
    membership: list[dict[str, str]],
    components: list[dict[str, str]],
    plan_root: Path,
) -> list[str]:
    errors: list[str] = []
    rid = "CAN-LAM-AI-090"
    req = next((r for r in requirements if r["canonical_id"] == rid), None)
    if not req:
        errors.append("ai_model_user_override_requirement_present:false")
        return errors
    stmt = req.get("statement", "")
    required_phrases = ["MUST NOT prevent", "compatible", "estimated processing time", "user MUST be allowed", "hard technical incompatibility"]
    for phrase in required_phrases:
        if phrase not in stmt:
            errors.append(f"ai_model_override_phrase_missing:{phrase}")
    if not req.get("acceptance_criteria") or "Given a weaker laptop" not in req.get("acceptance_criteria", ""):
        errors.append("ai_model_override_acceptance_missing")
    if not req.get("verification_method"):
        errors.append("ai_model_override_verification_missing")
    if not any(m["canonical_id"] == rid for m in membership):
        errors.append("requirement_membership_present:false")
    amendment_path = plan_root / "13-reports" / "ai-model-override-amendment.json"
    if not amendment_path.exists():
        errors.append("ai_model_override_amendment_artifact_missing")
        return errors
    amendment = read_json(amendment_path)
    concepts = amendment.get("contract_concepts", [])
    required_concepts = ["selected_model_id","recommended_model_id","selection_source","user_override","compatibility_status","hard_block_reason","estimated_duration","estimated_memory","estimated_storage","processing_mode","scheduled_start","pause_on_battery","selected_scope"]
    for concept in required_concepts:
        if concept not in concepts:
            errors.append(f"ai_model_override_concept_missing:{concept}")
    commands = amendment.get("planned_commands", [])
    required_commands = ["ai.models.list_compatible","ai.models.select","ai.models.estimates","ai.models.override","ai.jobs.schedule","ai.jobs.pause","ai.jobs.resume","ai.jobs.scope"]
    for command in required_commands:
        if command not in commands:
            errors.append(f"ai_model_override_command_missing:{command}")
    rules = amendment.get("behavioural_rules", {})
    required_rules = ["slow_processing_alone_is_not_a_hard_block","stronger_compatible_model_remains_selectable","recommendation_is_not_prohibition","silent_model_substitution_is_prohibited","quantized_variant_has_distinct_identity","selected_model_provenance_is_persisted","model_change_invalidates_derived_results"]
    for rule in required_rules:
        if rules.get(rule) is not True:
            errors.append(f"ai_model_override_rule_missing:{rule}")
    hard = amendment.get("hard_block_reasons", [])
    required_hard = ["insufficient_safe_memory","insufficient_storage","unsupported_model_operations","unsupported_runtime_or_provider","invalid_or_corrupted_model","checksum_failure","unresolved_licensing_restriction"]
    for reason in required_hard:
        if reason not in hard:
            errors.append(f"ai_model_override_hard_block_reason_missing:{reason}")
    comp_rules = amendment.get("components", {})
    required_component_meanings = ["stronger_compatible_models_manually_selectable","slow_estimates_do_not_block","hard_incompatibility_may_block","no_silent_fallback","provenance_required"]
    for component in components:
        name = component.get("component", "")
        if name not in ("ONNX Runtime", "OCR model/runtime", "Embedding model/runtime", "Face model/runtime", "Python runtime or alternative AI host"):
            continue
        entry = comp_rules.get(name, {})
        for meaning in required_component_meanings:
            if entry.get(meaning) is not True:
                errors.append(f"component_model_selection_rule_missing:{name}:{meaning}")
        rule = component.get("model_selection_rule", "")
        if "manually selectable" not in rule or "slow" not in rule:
            errors.append(f"component_model_selection_rule_missing:{name}")
    affected = amendment.get("affected_packages", {})
    for pid in ("WP-I10-003", "WP-I10-005", "WP-I10-006", "WP-I10-008", "WP-I10-013"):
        entry = affected.get(pid)
        if not entry or not entry.get("impact_type") or not entry.get("reason"):
            errors.append(f"ai_model_override_affected_package_unexplained:{pid}")
    packet = plan_root / "04-work-packages" / "packets" / "WP-I10-003.md"
    if packet.exists():
        text = packet.read_text(encoding="utf-8")
        if "Canonical requirements (3)" not in text or "2 requirements" in text:
            errors.append("ai_override_packet_requirement_count_stale")
        if "CAN-LAM-AI-090" not in text.split("## Canonical requirements")[0]:
            errors.append("ai_override_packet_objective_missing_requirement")
        contracts_section = text.split("## Contracts and schemas")[1].split("## Delivery and proof")[0] if "## Contracts and schemas" in text and "## Delivery and proof" in text else ""
        if "CAN-LAM-AI-090" not in contracts_section:
            errors.append("ai_override_packet_contracts_missing_requirement")
        delivery_section = text.split("## Delivery and proof")[1].split("Exit gate")[0] if "## Delivery and proof" in text and "Exit gate" in text else ""
        if "CAN-LAM-AI-090" not in delivery_section and "slow-compatible-selectable" not in delivery_section:
            errors.append("ai_override_packet_tests_missing_requirement")
        if "CAN-LAM-AI-090" not in text.split("Exit gate")[-1]:
            errors.append("ai_override_packet_exit_gate_missing_requirement")
    return errors


def check_review_artifact(name: str, text: str) -> list[str]:
    if "manual" in name.casefold() and ("generated" in text.casefold() or "automated" in text.casefold()):
        return [f"automatically generated report labelled manual: {name}"]
    return []


def check_scope_safety(packages: list[dict[str, object]], handoff: str) -> list[str]:
    errors: list[str] = []
    prohibited = re.compile(r"immutable archive|repository backup|rollback tag|safety copy|restore copy|repository copy|recovery copy|create (?:an? )?(?:archive|backup)", re.I)
    def positive_instruction(text: str) -> bool:
        for match in prohibited.finditer(text):
            prefix = text[max(0, match.start() - 40):match.start()].casefold()
            if not re.search(r"(?:no|not|never|without|prohibit(?:ed|s)?|exclude[sd]?)\b[^.;]{0,35}$", prefix):
                return True
        return False
    for package in packages:
        if package["implementation_phase"] != "I0":
            continue
        text = " ".join(str(package.get(field, "")) for field in ("name", "objective", "bounded_surface", "deliverables", "tests", "completion_evidence", "exit_gate"))
        if positive_instruction(text):
            errors.append(f"I0 package instructs prohibited repository backup/archive/Git mutation: {package['work_package_id']}")
    if positive_instruction(handoff):
        errors.append("handoff recommends prohibited repository backup/archive/Git mutation")
    return errors


def check_handoff_text(text: str) -> list[str]:
    errors: list[str] = []
    if "WP-I0-001" not in text or "I0" not in text:
        errors.append("active handoff does not point to first I0 package")
    if re.search(r"phase\s*2\s*first|begin\s+phase\s*2|WP-I2-001", text, re.I):
        errors.append("active handoff points to superseded phase")
    return errors


def check_audit_authenticity(files: list[Path]) -> list[str]:
    errors: list[str] = []
    for path in files:
        if "manual" in path.name.casefold():
            text = path.read_text(encoding="utf-8")
            if re.search(r"(?im)^(generated by:|reviewer:\s*(generator|automated)|this (manual )?report (was|is) automatically generated)", text):
                errors.append(f"automatically generated report labelled manual: {path.name}")
            if "Reviewer:" not in text and path.suffix == ".md":
                errors.append(f"manual audit lacks reviewer identity: {path.name}")
    return errors


def run() -> dict[str, object]:
    levels: list[dict[str, object]] = []

    def level(name: str, errors: list[str]) -> None:
        levels.append({"level": name, "status": "PASS" if not errors else "FAIL", "errors": errors})

    requirements = read_csv(PLAN / "02-requirements" / "canonical-registry.csv")
    mappings_list = read_csv(PLAN / "03-phases" / "reviewed-requirement-mapping.csv")
    mappings = {row["canonical_id"]: row for row in mappings_list}
    membership = read_csv(PLAN / "04-work-packages" / "requirement-membership.csv")
    packages = read_json(PLAN / "04-work-packages" / "work-packages.json")
    edges = read_csv(PLAN / "04-work-packages" / "dependencies.csv")
    commands = read_json(PLAN / "05-contracts" / "ipc-command-registry-v3.json")["commands"]
    schema_index = read_csv(PLAN / "06-schemas" / "schema-index.csv")
    authority = read_csv(PLAN / "06-schemas" / "authority-registry.csv")
    components = read_csv(PLAN / "10-component-manifest" / "components.csv")

    builder_text = BUILDER.read_text(encoding="utf-8")
    builder_errors = []
    for token in ("def classify(", "def semantic_phase(", "WP_CATALOG", "must demonstrably satisfy"):
        if token in builder_text:
            builder_errors.append(f"forbidden legacy generator logic in builder: {token}")
    if "guard_write_path" not in builder_text:
        builder_errors.append("builder lacks reusable Graphify write guard")
    level("L1_SOURCE_AND_WRITE_BOUNDARY", builder_errors)
    level("L2_REQUIREMENT_SEMANTICS", check_requirement_records(requirements, mappings))
    v2_rows = read_csv(PLAN / "13-reports" / "reviewed-requirement-decisions-v2.csv")
    level(
        "L2B_PASS1_SEMANTIC_REHABILITATION",
        check_pass1_semantics(requirements, mappings, v2_rows)
        + check_v2_status_sourcing(requirements, v2_rows),
    )
    mapping_errors = check_mapping_records(mappings_list)
    if set(mappings) != {row["canonical_id"] for row in requirements}:
        mapping_errors.append("requirement/mapping ID sets differ")
    level("L3_EXPLICIT_SEMANTIC_MAPPING", mapping_errors)
    active_ids = {row["canonical_id"] for row in requirements if mappings[row["canonical_id"]]["primary_implementation_phase"] and row["requirement_type"] in IMPLEMENTATION_TYPES and row["supersession_status"] == "ACTIVE"}
    level("L4_WORK_PACKAGES", check_package_records(packages, membership, active_ids) + check_phase_package_consistency(requirements, mappings, packages, membership))
    level("L4B_PASS2_PACKAGE_SEMANTICS", check_pass2_package_semantics(packages, membership, requirements, mappings, edges) + check_membership_rationale_quality(membership, packages, requirements))
    audit_rows = read_csv(PLAN / "13-reports" / "semantic-capability-phase-consistency-audit.csv") if (PLAN / "13-reports" / "semantic-capability-phase-consistency-audit.csv").exists() else []
    impact_rows = read_csv(PLAN / "13-reports" / "semantic-correction-package-impact-audit.csv") if (PLAN / "13-reports" / "semantic-correction-package-impact-audit.csv").exists() else []
    affected_package_ids = {row["Final package"] for row in impact_rows if row.get("Final package")}
    package_review_rows = read_csv(PLAN / "13-reports" / "pass2c-package-architecture-review.csv") if (PLAN / "13-reports" / "pass2c-package-architecture-review.csv").exists() else []
    level("L4C_SEMANTIC_CAPABILITY_PHASE_CONSISTENCY", check_semantic_capability_phase_consistency(requirements, mappings, membership, packages, v2_rows, audit_rows) + check_affected_package_quality(packages, affected_package_ids) + check_large_package_review_coverage(packages, package_review_rows))
    level("L5_TECHNICAL_DAG", check_dependency_records(packages, edges))
    level("L6_COMPONENT_DECISIONS", check_component_records(components, packages))
    contract_errors = check_command_records(commands, PLAN / "05-contracts")
    for path in (PLAN / "05-contracts").rglob("*.json"):
        contract_errors.extend(f"{path.relative_to(PLAN)}: {error}" for error in scan_open_objects(read_json(path)))
        contract_errors.extend(check_schema_document(path))
    level("L7_IPC_CONTRACTS", sorted(set(contract_errors)))
    schema_errors = check_record_schemas(schema_index, PLAN / "06-schemas")
    schema_errors.extend(check_authority_registry(authority, schema_index, PLAN / "06-schemas"))
    for path in (PLAN / "06-schemas").rglob("*.json"):
        schema_errors.extend(check_schema_document(path))
    con = sqlite3.connect(":memory:")
    try:
        sqlite_ddl = (PLAN / "07-sqlite" / "001_initial.sql").read_text(encoding="utf-8")
        con.executescript(sqlite_ddl)
    except sqlite3.Error as error:
        schema_errors.append(f"SQLite DDL execution failed: {error}")
    finally:
        con.close()
    schema_errors.extend(check_sqlite_references(sqlite_ddl))
    level("L8_AUTHORITY_RECORDS_AND_SQLITE", schema_errors)
    audit_files = list((PLAN / "13-reports").rglob("*manual*"))
    audit_errors = check_audit_authenticity(audit_files)
    for path in audit_files:
        audit_errors.extend(check_review_artifact(path.name, path.read_text(encoding="utf-8")))
    required_review_files = (
        "reviewed-requirement-decisions.csv", "reviewed-failure-controls.csv",
        "reviewed-fragment-decisions.csv", "reviewed-package-decisions.csv",
        "reviewed-membership-corrections.csv", "reviewed-dependency-additions.csv",
        "reviewed-dependency-roots.csv", "reviewed-change-audit.csv",
        "generated-semantic-sample-report.csv",
    )
    for name in required_review_files:
        if not (PLAN / "13-reports" / name).exists():
            audit_errors.append(f"missing explicit review source/report: {name}")
    failure_rows = read_csv(PLAN / "13-reports" / "reviewed-failure-controls.csv")
    if {row["failure_id"] for row in failure_rows} != {f"FAIL-{index:02d}" for index in range(1, 33)}:
        audit_errors.append("failure review registry does not cover FAIL-01 through FAIL-32 exactly")
    for path in (GRAPHIFY / "tools" / "seed_reviewed_registries.py", GRAPHIFY / "tools" / "finalize_reviewed_registries.py"):
        text = path.read_text(encoding="utf-8")
        audit_errors.extend(f"{path.name}: {error}" for error in check_review_script_text(text))
    seed_text = (GRAPHIFY / "tools" / "seed_reviewed_registries.py").read_text(encoding="utf-8")
    if "Automatic reviewed-registry seeding is disabled" not in seed_text:
        audit_errors.append("review seed tool is not explicitly disabled")
    coverage = read_json(PLAN / "13-reports" / "review-coverage.json")
    if int(coverage.get("explicit_failure_decisions", 0)) != 32 or int(coverage.get("explicit_fragment_decisions", 0)) <= 0:
        audit_errors.append("explicit review coverage is incomplete")
    expected_review_required = sum(1 for row in membership if row["reviewer_status"] == "REVIEW_REQUIRED")
    if int(coverage.get("unreviewed_active_mappings", -1)) != 0 or int(coverage.get("unreviewed_memberships", -1)) != expected_review_required:
        audit_errors.append("review coverage reports unresolved mappings or memberships")
    audit_errors.extend(check_zero_template_claim(PLAN / "13-reports"))
    level("L9_AUDIT_AUTHENTICITY", audit_errors)
    provenance_path = PLAN / "13-reports" / "review-provenance-coverage.json"
    provenance_coverage = read_json(provenance_path) if provenance_path.exists() else {}
    level("L14_REVIEW_PROVENANCE", check_review_provenance(provenance_coverage) + check_active_scripts_for_automatic_certification(GRAPHIFY / "tools"))
    readiness_path = PLAN / "13-reports" / "pass3-certification-report.json"
    readiness_report = read_json(readiness_path) if readiness_path.exists() else {}
    determinism_path = PLAN / "13-reports" / "final-package-determinism.json"
    determinism_report = read_json(determinism_path) if determinism_path.exists() else {}
    handoff_text = (PLAN / "14-handoff" / "START-HERE.md").read_text(encoding="utf-8")
    level("L15_PERSISTED_READINESS", check_persisted_readiness_declaration(readiness_report, handoff_text, determinism_report))
    v3_path = PLAN / "13-reports" / "reviewed-actionable-requirements-v3.csv"
    v3_rows = read_csv(v3_path) if v3_path.exists() else []
    level("L16_REQUIREMENT_LEDGER", check_v3_requirement_ledger(requirements, mappings, v3_rows))
    pkg_review_path = PLAN / "13-reports" / "reviewed-work-packages-v3.csv"
    mem_review_path = PLAN / "13-reports" / "reviewed-package-memberships-v3.csv"
    dep_review_path = PLAN / "13-reports" / "reviewed-dependencies-v3.csv"
    pkg_reviews = read_csv(pkg_review_path) if pkg_review_path.exists() else []
    mem_reviews = read_csv(mem_review_path) if mem_review_path.exists() else []
    dep_reviews = read_csv(dep_review_path) if dep_review_path.exists() else []
    level("L17_PASS_B_LEDGER", check_pass_b_ledgers(packages, membership, edges, pkg_reviews, mem_reviews, dep_reviews))
    v2_files = {
        "independently-verified-package-members-v2.csv": "13-reports/independently-verified-package-members-v2.csv",
        "independently-verified-package-contracts-v2.csv": "13-reports/independently-verified-package-contracts-v2.csv",
        "independently-verified-package-tests-v2.csv": "13-reports/independently-verified-package-tests-v2.csv",
        "independently-verified-package-exit-gates-v2.csv": "13-reports/independently-verified-package-exit-gates-v2.csv",
        "independently-verified-package-decisions-v2.csv": "13-reports/independently-verified-package-decisions-v2.csv",
    }
    v2_rows = {name: (read_csv(PLAN / rel) if (PLAN / rel).exists() else []) for name, rel in v2_files.items()}
    level(
        "L18_PASS_B_ARCHITECTURE_COMPLETENESS",
        check_pass_b_architecture_completeness(PLAN, packages, membership)
        + check_pass_b_independent_evidence(
            v2_rows["independently-verified-package-members-v2.csv"],
            v2_rows["independently-verified-package-contracts-v2.csv"],
            v2_rows["independently-verified-package-tests-v2.csv"],
            v2_rows["independently-verified-package-exit-gates-v2.csv"],
            v2_rows["independently-verified-package-decisions-v2.csv"],
        ),
    )
    component_rows = read_csv(PLAN / "10-component-manifest" / "components.csv")
    level("L19_COMPONENT_AND_LICENCE_COMPLETENESS", check_component_licence_completeness(component_rows, edges))
    level("L20_FINAL_100_PERCENT_PLANNING_CERTIFICATION", check_final_100_percent_certification(PLAN))
    level("L21_AI_MODEL_OVERRIDE_AMENDMENT", check_ai_model_override_amendment(requirements, membership, component_rows, PLAN))
    computed = recompute_quality_metrics(requirements, mappings, membership, packages, edges, schema_index, authority)
    metric_report = read_json(PLAN / "13-reports" / "requirement-repair-stats.json")
    level("L10_METRICS_HONESTY", check_metrics_honesty(metric_report, computed, builder_text))
    packet_errors: list[str] = []
    manifest = read_json(PLAN / "11-model-packets" / "packet-manifest.json")
    for row in manifest["packets"]:
        if not (PLAN / row["path"]).exists():
            packet_errors.append(f"missing packet: {row['path']}")
    if len(list((PLAN / "11-model-packets" / "phases").glob("*.md"))) != 16:
        packet_errors.append("phase packet count is not 16")
    if len(list((PLAN / "04-work-packages" / "packets").glob("*.md"))) != len(packages):
        packet_errors.append("work-package packet count mismatch")
    handoff = (PLAN / "14-handoff" / "START-HERE.md").read_text(encoding="utf-8")
    packet_errors.extend(check_handoff_text(handoff))
    packet_errors.extend(check_packet_membership_currency(packages, membership, PLAN))
    level("L11_SCOPE_SAFETY", check_scope_safety(packages, handoff))
    level("L12_PACKETS_AND_HANDOFF", packet_errors)
    execution_check_errors = check_l7_l8_execution_claim(Draft202012Validator is not None, {"levels": levels})
    level("L13_META_VALIDATION_EXECUTION", execution_check_errors)
    status = "PASS" if all(row["status"] == "PASS" for row in levels) else "FAIL"
    return {"validatorVersion": "4.0.0", "status": status, "levels": levels, "levelCount": len(levels), "failedLevels": [row["level"] for row in levels if row["status"] == "FAIL"], "computedQualityMetrics": computed}


def main() -> int:
    result = run()
    print(json.dumps(result, indent=2))
    if "--write-results" in sys.argv:
        path = safe_write_path(PLAN / "12-validators" / "validator-results.json")
        path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
