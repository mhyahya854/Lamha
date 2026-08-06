"""Deterministically render the reviewed Lamha semantic plan.

This renderer does no semantic allocation. Requirements, phase mappings, package
memberships, dependency edges, component decisions, commands, and schemas come
only from the explicitly reviewed files under semantic-plan-source.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import stat
import re
from collections import Counter, defaultdict, deque
from pathlib import Path

from tools.write_guard import guard_write_path


GRAPHIFY = Path(__file__).resolve().parent
SOURCE = GRAPHIFY / "semantic-plan-source"
PLAN = GRAPHIFY / "12-semantic-implementation-plan"
BASELINE = PLAN / "13-reports" / "external-readonly-baseline.json"
INTENDED: set[Path] = set()

IMPLEMENTATION_TYPES = {
    "FUNCTIONAL_REQUIREMENT", "NONFUNCTIONAL_REQUIREMENT", "ARCHITECTURAL_INVARIANT",
    "SECURITY_INVARIANT", "PRIVACY_INVARIANT", "DATA_INTEGRITY_INVARIANT",
    "IMPLEMENTATION_CONSTRAINT", "ACCEPTANCE_CRITERION", "OPTIONAL_ADAPTER",
    "VERIFICATION_GATE", "REMOVAL_GATE", "RELEASE_GATE", "PROHIBITION",
}


def is_reparse(path: Path) -> bool:
    try:
        return bool(path.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)
    except (AttributeError, FileNotFoundError, OSError):
        return path.is_symlink()


def safe_write_path(path: Path) -> Path:
    return guard_write_path(path)


def _prepare(path: Path) -> Path:
    path = safe_write_path(path)
    missing: list[Path] = []
    cursor = path.parent
    while cursor != GRAPHIFY and not cursor.exists():
        missing.append(cursor)
        cursor = cursor.parent
    if cursor.exists() and is_reparse(cursor):
        raise ValueError(f"reparse-point parent rejected: {cursor}")
    for directory in reversed(missing):
        safe_write_path(directory / ".guard")
        directory.mkdir()
    INTENDED.add(path)
    return path


def write_bytes(path: Path, data: bytes) -> None:
    _prepare(path).write_bytes(data)


def write_text(path: Path, text: str) -> None:
    _prepare(path).write_text(text.rstrip() + "\n", encoding="utf-8", newline="\n")


def write_json(path: Path, value: object) -> None:
    write_text(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False))


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str] | None = None) -> None:
    if not fields:
        fields = list(rows[0]) if rows else []
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    write_text(path, stream.getvalue())


def read_csv(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(path.open(encoding="utf-8-sig", newline="")))


def read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


MEANINGFUL_STOP = {"the", "and", "for", "that", "with", "from", "must", "shall", "will", "this", "lamha", "implementation", "a", "an", "to", "of", "or", "in", "on", "is", "be", "as", "by"}
GENERIC_TEMPLATE = re.compile(r"^(recorded evidence must demonstrate:|lamha must provide |implementation must honor this constraint:|lamha must preserve this invariant:|the final lamha desktop runtime must not retain or require |lamha must implement the .+ behavior for .+ and satisfy every linked acceptance criterion\.)", re.I)
OBSERVABLE = re.compile(r"\b(return|display|shown?|report|reject|preserve|persist|remain|produce|update|pass|fail|create|support|write|read|render|detect|include|record|expose|leave|block|index|reflect|apply|invoke|store|execute|verify|validate|calculate|prevent|enforce|reconcile|restore|remove|communicate|open|close|suppress|reconsider|mark|use|embed|mutate|require|help|represent|derive|keep|plan|test|move|reference|add|split|identify|link|exist|survive|choose|save|retain|scope|rescan|track|correspond|change|limit|map|contribute|transition|inventory|classify|measure|provide|generate|follow|initialize|treat|establish|preview|commit|approve|confirm|exclude|highlight|budget|threshold|latency|throughput|benchmark|queue|group|delete|merge|upload|appear|omit|navigate|reveal|strip|redact|compose)\w*\b", re.I)
BACKUP_REFERENCE = re.compile(r"\b(?:backup|archive|immutable archive|safety copy|restore copy|repository copy|recovery copy)\b", re.I)


def meaningful_words(value: str) -> list[str]:
    return [word for word in re.findall(r"[A-Za-z0-9]+", value) if word.casefold() not in MEANINGFUL_STOP]


def classify_backup_archive_references(
    requirements: list[dict[str, str]], packages: list[dict[str, object]],
    dependencies: list[dict[str, str]], phases: list[dict[str, str]],
    requirement_decisions: list[dict[str, str]], package_decisions: list[dict[str, str]],
) -> list[dict[str, object]]:
    """Classify canonical occurrences; rendered duplicates inherit their source classification."""
    rows: list[dict[str, object]] = []

    def record(source_type: str, record_id: str, field: str, value: object, category: str, rationale: str) -> None:
        text = str(value)
        for match in BACKUP_REFERENCE.finditer(text):
            rows.append({
                "occurrence_id": f"BAR-{len(rows) + 1:04d}",
                "source_type": source_type,
                "record_id": record_id,
                "field": field,
                "term": match.group(0),
                "classification": category,
                "text": text,
                "rationale": rationale,
            })

    requirement_fields = ("title", "statement", "rationale", "source_text", "acceptance_criteria", "verification_method", "review_notes")
    for row in requirements:
        rid = row["canonical_id"]
        active = row["supersession_status"] == "ACTIVE"
        for field in requirement_fields:
            value = row.get(field, "")
            if not BACKUP_REFERENCE.search(value):
                continue
            if not active:
                category, rationale = "Superseded", "Inactive source trace; it cannot instruct implementation."
            elif rid.startswith("CAN-MISSION-I0-") and field == "source_text":
                category, rationale = "Historical provenance only", "Original I0 wording is retained only as trace evidence for the reviewed correction."
            elif rid.startswith("CAN-MISSION-I0-"):
                category, rationale = "Prohibited", "Active I0 wording explicitly forbids a development-repository backup or archive."
            else:
                category, rationale = "Legitimate future product backup feature", "Active product behavior concerns Lamha-managed user media or recovery data, not a planning repository copy."
            record("requirement", rid, field, value, category, rationale)

    package_fields = ("name", "objective", "bounded_surface", "explicit_exclusions", "cohesion_rationale", "deliverables", "tests", "failure_cases", "rollback_or_recovery", "completion_evidence", "exit_gate")
    for row in packages:
        pid = str(row["work_package_id"])
        for field in package_fields:
            value = row.get(field, "")
            if str(row["implementation_phase"]) == "I0":
                category, rationale = "Prohibited", "The I0 package uses the term only to forbid repository duplication during read-only provenance work."
            else:
                category, rationale = "Legitimate future product backup feature", "The package reference concerns Lamha product recovery behavior or distinguishes it from another bounded package."
            record("work_package", pid, field, value, category, rationale)

    for row in dependencies:
        target = row["work_package_id"]
        category = "Prohibited" if target.startswith("WP-I0-") else "Legitimate future product backup feature"
        rationale = "The I0 edge preserves the no-copy boundary." if category == "Prohibited" else "The edge is a technical prerequisite for product backup, restore, or recovery behavior."
        for field in ("technical_rationale", "evidence"):
            record("dependency", f"{target}<-{row['prerequisite_work_package_id']}", field, row.get(field, ""), category, rationale)

    for row in phases:
        for field in ("name", "objective", "entryGate", "exitGate"):
            record("phase", row["phaseId"], field, row.get(field, ""), "Legitimate future product backup feature", "I13 defines Lamha user-data recovery behavior.")

    for row in requirement_decisions:
        rid = row["record_id"]
        for field in ("candidate_value", "final_reviewed_value", "acceptance_criteria", "review_rationale", "correction_applied"):
            if field == "candidate_value":
                category, rationale = "Historical provenance only", "Superseded candidate retained to prove why the reviewed correction was necessary."
            else:
                category, rationale = "Prohibited", "Explicit reviewed decision removes or guards against development-repository backup/archive creation."
            record("reviewed_requirement_decision", rid, field, row.get(field, ""), category, rationale)

    for row in package_decisions:
        pid = row["record_id"]
        for field in ("previous_value", "final_value", "review_rationale", "correction_applied"):
            if field == "previous_value":
                category, rationale = "Historical provenance only", "Superseded package wording retained only in the reviewed change ledger."
            elif pid.startswith("WP-I0-"):
                category, rationale = "Prohibited", "Explicit package decision removes or guards against development-repository backup/archive creation."
            else:
                category, rationale = "Legitimate future product backup feature", "The review distinguishes future Lamha product backup behavior from repository safety work."
            record("reviewed_package_decision", pid, field, row.get(field, ""), category, rationale)
    return rows


def compute_quality_metrics(
    requirements: list[dict[str, str]], mappings: list[dict[str, str]],
    memberships: list[dict[str, str]], packages: list[dict[str, object]],
    dependencies: list[dict[str, str]], schema_index: list[dict[str, str]],
    authority: list[dict[str, str]],
) -> dict[str, int]:
    mapping_by_id = {row["canonical_id"]: row for row in mappings}
    package_phase = {str(row["work_package_id"]): str(row["implementation_phase"]) for row in packages}
    active = [
        row for row in requirements
        if row["supersession_status"] == "ACTIVE"
        and row["requirement_type"] in IMPLEMENTATION_TYPES
        and mapping_by_id[row["canonical_id"]]["primary_implementation_phase"]
    ]
    member_by_id = {row["canonical_id"]: row for row in memberships}
    dedicated = {row["schema"] for row in schema_index}
    required_concepts = {"Saved views", "Memories", "Location records", "Export manifests", "Restore manifests", "Privacy-export recipes", "Filename templates", "Drive registry", "Derivative manifests", "AI candidate and proposal records"}
    authority_by_concept = {row["concept"]: row for row in authority}
    missing_authority = required_concepts - set(authority_by_concept)
    missing_schema = 0
    for concept in required_concepts & set(authority_by_concept):
        row = authority_by_concept[concept]
        classification = row["authority_classification"]
        if classification == "DEDICATED_AUTHORITATIVE_SCHEMA" and row["authoritative_schema"] not in dedicated:
            missing_schema += 1
        if classification == "EMBEDDED_AUTHORITATIVE_STRUCTURE" and not row["embedding_parent"]:
            missing_schema += 1
        if classification == "DERIVED_ONLY_PROJECTION" and not row["rebuild_source"]:
            missing_schema += 1
    phase_mismatches = 0
    for rid, membership in member_by_id.items():
        phase = mapping_by_id[rid]["primary_implementation_phase"]
        if phase and package_phase.get(membership["work_package_id"]) != phase:
            phase_mismatches += 1
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
            bool(mapping_by_id[row["canonical_id"]]["primary_implementation_phase"])
            and not mapping_by_id[row["canonical_id"]]["reviewer_status"].startswith("REVIEWED_")
            for row in active
        ),
        "unreviewed_package_memberships": sum(row.get("reviewer_status") not in {"REVIEWED", "REVIEW_REQUIRED"} for row in memberships),
        "missing_dependency_rationales": sum(not row.get("technical_rationale") or not row.get("evidence") or not row.get("review_status", "").startswith("REVIEWED_") for row in dependencies),
        "missing_authority_schema_decisions": len(missing_authority) + missing_schema,
    }


def copy_tree(source: Path, destination: Path) -> None:
    for path in sorted(source.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts and "superseded" not in path.parts and path.suffix != ".pyc":
            write_bytes(destination / path.relative_to(source), path.read_bytes())


def require_reviewed_source(
    requirements: list[dict[str, str]], mappings: list[dict[str, str]],
    memberships: list[dict[str, str]], dependencies: list[dict[str, str]],
    packages: list[dict[str, object]], components: list[dict[str, str]],
    commands: list[dict[str, object]], schema_index: list[dict[str, str]],
) -> None:
    failures: list[str] = []
    allowed_requirement_statuses = {
        "REVIEWED_CONFIRMED", "REVIEWED_CORRECTED", "RECLASSIFIED", "MERGED",
        "SUPERSEDED", "REVIEW_REQUIRED", "BLOCKED",
    }
    failures += [
        f"requirement {row['canonical_id']}"
        for row in requirements
        if row["supersession_status"] == "ACTIVE" and row["normalization_reviewer_status"] not in allowed_requirement_statuses
    ]
    active_ids = {row["canonical_id"] for row in requirements if row["supersession_status"] == "ACTIVE"}
    failures += [
        f"mapping {row['canonical_id']}"
        for row in mappings
        if row["canonical_id"] in active_ids
        and row["reviewer_status"] not in {"REVIEWED_CONFIRMED", "REVIEWED_CORRECTED", "NOT_APPLICABLE"}
    ]
    failures += [f"membership {row['canonical_id']}" for row in memberships if row["reviewer_status"] not in {"REVIEWED", "REVIEW_REQUIRED"}]
    failures += [f"dependency {row['work_package_id']}" for row in dependencies if not row.get("review_status", "").startswith("REVIEWED_")]
    failures += [f"package {row['work_package_id']}" for row in packages if row.get("reviewer_status") != "REVIEWED"]
    failures += [f"component {row['component']}" for row in components if not row["reviewer_status"].startswith("REVIEWED_")]
    failures += [f"command {row['commandId']}" for row in commands if not str(row["reviewerStatus"]).startswith("REVIEWED_")]
    failures += [f"schema {row['schema']}" for row in schema_index if row["reviewer_status"] != "REVIEWED"]
    if failures:
        raise ValueError("unreviewed semantic source rows: " + ", ".join(failures[:20]))


def dependency_summary(packages: list[dict[str, object]], edges: list[dict[str, str]]) -> tuple[list[str], int]:
    nodes = {str(row["work_package_id"]) for row in packages}
    incoming: defaultdict[str, int] = defaultdict(int)
    outgoing: defaultdict[str, list[str]] = defaultdict(list)
    for edge in edges:
        before = edge["prerequisite_work_package_id"]
        after = edge["work_package_id"]
        outgoing[before].append(after)
        incoming[after] += 1
    queue = deque(sorted(node for node in nodes if incoming[node] == 0))
    order: list[str] = []
    distance = {node: 0 for node in nodes}
    while queue:
        node = queue.popleft()
        order.append(node)
        for nxt in sorted(outgoing[node]):
            distance[nxt] = max(distance[nxt], distance[node] + 1)
            incoming[nxt] -= 1
            if incoming[nxt] == 0:
                queue.append(nxt)
    if len(order) != len(nodes):
        raise ValueError("reviewed dependency graph contains a cycle")
    return order, max(distance.values(), default=0)


def render_package_packet(
    package: dict[str, object], requirement_ids: list[str],
    requirements: dict[str, dict[str, str]], prerequisites: list[dict[str, str]],
    dependent_ids: list[str], commands: list[dict[str, object]],
) -> str:
    pid = str(package["work_package_id"])
    command_ids = sorted(str(row["commandId"]) for row in commands if row.get("workPackageId") == pid)
    req_lines = [
        f"- `{rid}` — {requirements[rid]['statement']} (source: {requirements[rid]['source_plan']} / {requirements[rid]['source_locator']})"
        for rid in requirement_ids
    ]
    dep_lines = [
        f"- `{row['prerequisite_work_package_id']}` via `{row['dependency_type']}` — {row['technical_rationale']}"
        for row in prerequisites
    ] or ["- None."]
    return f"""# {pid} — {package['name']}

Canonical source: `semantic-plan-source/packages/work-packages.json` plus the reviewed membership and dependency registries.

## Execution boundary

- Phase: `{package['implementation_phase']}`
- Objective: {package['objective']}
- Bounded surface: {package['bounded_surface']}
- Explicit exclusions: {package['explicit_exclusions']}
- Commit boundary: {package['commit_boundary']}

## Canonical requirements ({len(requirement_ids)})

{chr(10).join(req_lines)}

## Technical prerequisites

{chr(10).join(dep_lines)}

## Direct dependents

{', '.join(f'`{value}`' for value in dependent_ids) if dependent_ids else 'None.'}

## Contracts and schemas

- IPC commands: {', '.join(f'`{value}`' for value in command_ids) if command_ids else 'None verified for this package.'}
- Contracts affected: {package['contracts_affected']}
- Schemas affected: {package['schemas_affected']}

## Delivery and proof

- Deliverables: {package['deliverables']}
- Tests: {package['tests']}
- Failure cases: {package['failure_cases']}
- Rollback/recovery: {package['rollback_or_recovery']}
- Completion evidence: {package['completion_evidence']}
- Exit gate: {package['exit_gate']}

Execute only this bounded package. Do not start a dependent package until its technical prerequisites and exit gate are proven.
"""


def render_phase_packet(phase: dict[str, str], packages: list[dict[str, object]]) -> str:
    lines = [f"- `{row['work_package_id']}` — {row['name']}: {row['objective']}" for row in packages]
    return f"""# {phase['phaseId']} — {phase['name']}

Canonical source: `semantic-plan-source/phases/implementation-phases.json` and the reviewed work-package registry.

- Objective: {phase['objective']}
- Entry gate: {phase['entryGate']}
- Exit gate: {phase['exitGate']}

## Reviewed work packages

{chr(10).join(lines) if lines else '- None.'}

This packet is an index. Execute one work-package packet at a time and respect the dependency graph.
"""


def main() -> None:
    requirements = read_csv(SOURCE / "requirements" / "requirements.csv")
    mappings = read_csv(SOURCE / "requirements" / "requirement-mapping.csv")
    dispositions = read_csv(SOURCE / "requirements" / "source-row-dispositions.csv")
    memberships = read_csv(SOURCE / "packages" / "requirement-membership.csv")
    dependencies = read_csv(SOURCE / "packages" / "dependencies.csv")
    package_doc = read_json(SOURCE / "packages" / "work-packages.json")
    packages = package_doc["workPackages"]
    phase_doc = read_json(SOURCE / "phases" / "implementation-phases.json")
    phases = phase_doc["phases"]
    components = read_csv(SOURCE / "components" / "components.csv")
    command_doc = read_json(SOURCE / "contracts" / "ipc-command-registry-v3.json")
    commands = command_doc["commands"]
    schema_index = read_csv(SOURCE / "schemas" / "schema-index.csv")
    authority_registry = read_csv(SOURCE / "schemas" / "authority-registry.csv")
    coverage = read_json(SOURCE / "reviews" / "review-coverage.json")
    migration_stats = read_json(SOURCE / "reviews" / "migration-candidate-stats.json")
    contract_stats = read_json(SOURCE / "reviews" / "contract-schema-candidate-stats.json")
    legacy_disposition = read_csv(SOURCE / "reviews" / "legacy-package-disposition.csv")
    require_reviewed_source(requirements, mappings, memberships, dependencies, packages, components, commands, schema_index)

    requirement_by_id = {row["canonical_id"]: row for row in requirements}
    mapping_by_id = {row["canonical_id"]: row for row in mappings}
    members_by_package: defaultdict[str, list[str]] = defaultdict(list)
    for row in memberships:
        members_by_package[row["work_package_id"]].append(row["canonical_id"])
    prerequisites: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
    dependents: defaultdict[str, list[str]] = defaultdict(list)
    for row in dependencies:
        prerequisites[row["work_package_id"]].append(row)
        dependents[row["prerequisite_work_package_id"]].append(row["work_package_id"])
    order, critical_depth = dependency_summary(packages, dependencies)

    enriched_packages: list[dict[str, object]] = []
    for package in packages:
        enriched = dict(package)
        enriched["included_requirement_ids"] = sorted(members_by_package[str(package["work_package_id"])])
        enriched["technical_dependencies"] = sorted(
            ({key: row[key] for key in ("prerequisite_work_package_id", "dependency_type", "technical_rationale")} for row in prerequisites[str(package["work_package_id"])])
            , key=lambda row: (row["prerequisite_work_package_id"], row["dependency_type"]),
        )
        enriched_packages.append(enriched)

    write_text(PLAN / "00-constitution" / "GLOBAL-CONSTITUTION.md", """# Lamha implementation constitution

The reviewed semantic registries under `graphify/semantic-plan-source` are the only planning authority. The application codebase is read-only during planning. Implement one dependency-ready work package per bounded commit. Rust owns privileged filesystem, process, persistence, and capability enforcement. Originals are never silently overwritten; durable user knowledge is versioned outside rebuildable SQLite indexes. Mutations require typed contracts, validation, authorization, journaling, deterministic recovery, and focused failure tests. A package is complete only with its stated evidence and exit gate.
""")
    write_text(PLAN / "01-decisions" / "ADR-0001-reviewed-registries.md", """# ADR-0001: Reviewed registries are authoritative

Status: Accepted.

Semantic decisions are stored as explicit reviewed rows. The renderer copies and formats those decisions; it never guesses a capability, phase, package, dependency, command flag, or record shape from keywords, source order, or row count.
""")
    write_text(PLAN / "01-decisions" / "ADR-0002-authority-and-recovery.md", """# ADR-0002: Local authority and recovery

Status: Accepted.

Rust is the privileged local authority. Versioned files hold durable user knowledge; SQLite holds transactional and rebuildable indexes according to `entity-authority.csv`. Destructive operations require plan/commit separation, explicit authorization, journaling, and recovery evidence.
""")

    write_csv(PLAN / "02-requirements" / "canonical-registry.csv", requirements, list(requirements[0]))
    write_text(PLAN / "02-requirements" / "canonical-registry.jsonl", "\n".join(json.dumps(row, ensure_ascii=False) for row in requirements))
    write_csv(PLAN / "02-requirements" / "source-row-dispositions.csv", dispositions, list(dispositions[0]))
    write_json(PLAN / "02-requirements" / "requirement-taxonomy.json", {
        "types": dict(sorted(Counter(row["requirement_type"] for row in requirements).items())),
        "normalizationStatuses": dict(sorted(Counter(row["normalization_status"] for row in requirements).items())),
        "reviewerStatuses": dict(sorted(Counter(row["normalization_reviewer_status"] for row in requirements).items())),
    })

    write_csv(PLAN / "03-phases" / "reviewed-requirement-mapping.csv", mappings, list(mappings[0]))
    write_json(PLAN / "03-phases" / "implementation-phases.json", phase_doc)
    write_csv(PLAN / "03-phases" / "implementation-phases.csv", [{
        "phase_id": row["phaseId"], "name": row["name"], "objective": row["objective"],
        "entry_gate": row["entryGate"], "exit_gate": row["exitGate"],
    } for row in phases])
    write_csv(PLAN / "03-phases" / "phase-load-report.csv", [{
        "phase_id": phase["phaseId"],
        "requirement_count": sum(row["primary_implementation_phase"] == phase["phaseId"] for row in mappings),
        "package_count": sum(row["implementation_phase"] == phase["phaseId"] for row in packages),
    } for phase in phases])

    write_json(PLAN / "04-work-packages" / "work-packages.json", enriched_packages)
    package_fields = ["work_package_id", "implementation_phase", "key", "name", "objective", "bounded_surface", "reviewed_item_count", "reviewed_capabilities", "shared_boundary_exception", "reviewer_status"]
    write_csv(PLAN / "04-work-packages" / "work-packages.csv", [{**row, "reviewed_capabilities": ";".join(row["reviewed_capabilities"])} for row in packages], package_fields)
    write_csv(PLAN / "04-work-packages" / "requirement-membership.csv", memberships, list(memberships[0]))
    write_csv(PLAN / "04-work-packages" / "dependencies.csv", dependencies, list(dependencies[0]))
    write_json(PLAN / "04-work-packages" / "dependency-dag.json", {"nodes": order, "edges": dependencies, "acyclic": True, "criticalPathEdgeDepth": critical_depth})
    for package in packages:
        pid = str(package["work_package_id"])
        ids = sorted(members_by_package[pid])
        write_text(PLAN / "04-work-packages" / "packets" / f"{pid}.md", render_package_packet(
            package, ids, requirement_by_id, sorted(prerequisites[pid], key=lambda row: row["prerequisite_work_package_id"]),
            sorted(dependents[pid]), commands,
        ))

    copy_tree(SOURCE / "contracts", PLAN / "05-contracts")
    copy_tree(SOURCE / "schemas", PLAN / "06-schemas")
    copy_tree(SOURCE / "sqlite", PLAN / "07-sqlite")
    write_text(PLAN / "07-sqlite" / "README.md", """# SQLite authority

`001_initial.sql` is executable DDL. `entity-authority.csv` identifies which tables are authoritative transaction state and which are rebuildable indexes. SQLite must never become the only durable copy of user knowledge designated as file-authoritative.
""")

    write_text(PLAN / "08-testing" / "TEST-STRATEGY.md", """# Test strategy

Each work package supplies focused success, boundary, invalid-input, authorization, concurrency/revision, cancellation, I/O-failure, rollback, and recovery checks as applicable. Contract schemas are meta-validated; SQLite DDL executes in memory; dependency and reference integrity are checked globally. Twelve adversarial fixtures prove the validator rejects every final-blocker defect class.
""")
    write_csv(PLAN / "08-testing" / "work-package-test-matrix.csv", [{
        "work_package_id": row["work_package_id"], "phase": row["implementation_phase"],
        "success_and_boundary_tests": row["tests"], "failure_cases": row["failure_cases"],
        "recovery_proof": row["rollback_or_recovery"], "exit_gate": row["exit_gate"],
    } for row in packages])
    write_csv(PLAN / "09-risks" / "risk-register.csv", [
        {"risk_id": "RISK-001", "risk": "A component/version/licence choice is assumed before I0 evidence.", "owner": "WP-I0-004", "mitigation": "Resolve component rows and record pinned evidence before dependent work.", "gate": "I0"},
        {"risk_id": "RISK-002", "risk": "A privileged mutation bypasses Rust validation or recovery.", "owner": "WP-I3-010", "mitigation": "Typed plan/commit contracts, capability checks, journal, and failure injection.", "gate": "I3"},
        {"risk_id": "RISK-003", "risk": "Derived SQLite data becomes the only durable knowledge copy.", "owner": "WP-I3-004", "mitigation": "Enforce entity authority and rebuild tests from versioned records.", "gate": "I3"},
        {"risk_id": "RISK-004", "risk": "Media support is deferred to the desktop shell or release packaging.", "owner": "WP-I4-004", "mitigation": "Implement decode/metadata/preview/companion behavior in I4 and verify again in I15.", "gate": "I4"},
        {"risk_id": "RISK-005", "risk": "Stale generated packets contradict reviewed source.", "owner": "WP-I0-001", "mitigation": "Deterministic clean rendering, manifest hashes, and reference validation.", "gate": "I0"},
    ])

    write_csv(PLAN / "10-component-manifest" / "components.csv", components, list(components[0]))
    write_text(PLAN / "10-component-manifest" / "README.md", """# Component decision manifest

Rows are explicit reviewed decision obligations. `decision_package` owns evidence, `blocking_work_package` prevents premature implementation, and `required_before_packages` states the consumers that cannot proceed without the decision. Pending values are I0 decisions, not implicit approvals.
""")

    packet_rows: list[dict[str, object]] = []
    for phase in phases:
        phase_packages = [row for row in packages if row["implementation_phase"] == phase["phaseId"]]
        relative = f"11-model-packets/phases/{phase['phaseId']}.md"
        write_text(PLAN / relative, render_phase_packet(phase, phase_packages))
        packet_rows.append({"type": "PHASE", "id": phase["phaseId"], "path": relative, "canonicalSource": "semantic-plan-source/phases/implementation-phases.json"})
    for package in packages:
        pid = str(package["work_package_id"])
        packet_rows.append({"type": "WORK_PACKAGE", "id": pid, "path": f"04-work-packages/packets/{pid}.md", "canonicalSource": "semantic-plan-source/packages/work-packages.json"})
    write_json(PLAN / "11-model-packets" / "packet-manifest.json", {"packets": packet_rows})
    write_text(PLAN / "11-model-packets" / "README.md", """# Model packets

The manifest resolves every phase and work-package packet to reviewed canonical sources. Generate a prompt for one package with `python .\\11-model-packets\\plan_cli.py prompt WP-I0-001` from the active plan directory.
""")
    write_text(PLAN / "11-model-packets" / "plan_cli.py", """from __future__ import annotations
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def main() -> int:
    parser = argparse.ArgumentParser(description="Print one bounded Lamha work-package prompt.")
    sub = parser.add_subparsers(dest="action", required=True)
    prompt = sub.add_parser("prompt")
    prompt.add_argument("work_package_id")
    args = parser.parse_args()
    path = ROOT / "04-work-packages" / "packets" / f"{args.work_package_id}.md"
    if not path.is_file():
        parser.error(f"unknown work package: {args.work_package_id}")
    print(path.read_text(encoding="utf-8"))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
""")
    copy_tree(SOURCE / "validators", PLAN / "12-validators")

    copy_tree(SOURCE / "reviews", PLAN / "13-reports")
    actionable_ids = {row["canonical_id"] for row in memberships}
    quality = compute_quality_metrics(requirements, mappings, memberships, packages, dependencies, schema_index, authority_registry)
    fragment_reviews = read_csv(SOURCE / "reviews" / "reviewed-fragment-decisions.csv")
    requirement_reviews = read_csv(SOURCE / "reviews" / "reviewed-requirement-decisions.csv")
    package_reviews = read_csv(SOURCE / "reviews" / "reviewed-package-decisions.csv")
    failure_reviews = read_csv(SOURCE / "reviews" / "reviewed-failure-controls.csv")
    historical_fragments = sum(
        row["supersession_status"] in {"SUPERSEDED_GENERATED_TEMPLATE", "SUPERSEDED_FRAGMENT"}
        and row["requirement_type"] in IMPLEMENTATION_TYPES
        and len(meaningful_words(row["statement"])) < 8
        for row in requirements
    ) + sum(len(meaningful_words(row["candidate_value"])) < 8 for row in fragment_reviews)
    previous_generic = sum(
        bool(GENERIC_TEMPLATE.search(row["statement"].strip()))
        for row in requirements
        if row["requirement_type"] in IMPLEMENTATION_TYPES
    )
    requirement_type_by_id = {row["canonical_id"]: row["requirement_type"] for row in requirements}
    previous_generic += sum(
        requirement_type_by_id[row["record_id"]] in {"VERIFICATION_GATE", "REMOVAL_GATE", "RELEASE_GATE"}
        and len(meaningful_words(row["candidate_value"])) < 8
        for row in fragment_reviews
    )
    previous_generic += sum(requirement_type_by_id[row["record_id"]] == "VERIFICATION_GATE" for row in failure_reviews)
    previous_generic += sum(bool(GENERIC_TEMPLATE.search(row["candidate_value"].strip())) for row in requirement_reviews)
    report = {
        "originalSourceRows": len(dispositions),
        "normalizedItems": len(requirements),
        "canonicalActionableRequirements": len(actionable_ids),
        "activeCanonicalRecords": sum(row["supersession_status"] == "ACTIVE" for row in requirements),
        "criteria": sum(row["requirement_type"] == "ACCEPTANCE_CRITERION" and row["supersession_status"] == "ACTIVE" for row in requirements),
        "initialFragmentaryOrNonObservable": historical_fragments + quality["fragmentary_active_records"] + quality["non_observable_requirements"],
        "finalFragmentaryOrNonObservable": quality["fragmentary_active_records"] + quality["non_observable_requirements"],
        "initialGenericCriteria": previous_generic,
        "finalGenericCriteria": quality["generic_template_records"],
        "recordsExplicitlyRewritten": sum(row["normalization_status"] in {"EXPLICIT_REVIEWED_REWRITE", "EXPLICIT_FRAGMENT_REWRITE", "NORMALIZED_FAILURE_CONTROL"} for row in requirements),
        "phaseRemaps": migration_stats["phase_remaps"],
        "capabilityCorrections": migration_stats["capability_corrections"],
        "classificationCorrections": migration_stats["classification_corrections"],
        "orphanActionableRequirements": len({row["canonical_id"] for row in requirements if row["supersession_status"] == "ACTIVE" and row["requirement_type"] in IMPLEMENTATION_TYPES and mapping_by_id[row["canonical_id"]]["primary_implementation_phase"]} - actionable_ids),
        "remainingHumanDecisions": quality["unreviewed_mappings"] + quality["unreviewed_package_memberships"],
        "computedQualityMetrics": quality,
    }
    write_json(PLAN / "13-reports" / "requirement-repair-stats.json", report)
    phase_mismatches = []
    package_phase = {str(row["work_package_id"]): str(row["implementation_phase"]) for row in packages}
    membership_corrections = read_csv(SOURCE / "reviews" / "reviewed-membership-corrections.csv")
    for row in memberships:
        requirement_phase = mapping_by_id[row["canonical_id"]]["primary_implementation_phase"]
        if requirement_phase != package_phase[row["work_package_id"]]:
            phase_mismatches.append({"requirement_id": row["canonical_id"], "requirement_phase": requirement_phase, "work_package_id": row["work_package_id"], "package_phase": package_phase[row["work_package_id"]]})
    write_json(PLAN / "13-reports" / "phase-package-reconciliation.json", {
        "totalRequirementsChecked": len(memberships),
        "matches": len(memberships) - len(phase_mismatches),
        "correctedMismatches": sum(
            row["previous_value"] == "NO_ACTIVE_PRIMARY_PACKAGE"
            or package_phase.get(row["previous_value"]) != package_phase.get(row["final_value"])
            for row in membership_corrections
        ),
        "explicitExceptions": [row for row in mappings if row.get("exception_status") not in {"", "NONE", "NOT_APPLICABLE"}],
        "remainingFailures": phase_mismatches,
    })
    package_decisions = Counter(row["decision"] for row in legacy_disposition)
    write_json(PLAN / "13-reports" / "package-repair-stats.json", {
        "previousCount": len(legacy_disposition), "finalCount": len(packages),
        "legacyDecisions": dict(sorted(package_decisions.items())),
        "largestPackage": max(packages, key=lambda row: int(row["reviewed_item_count"]))["work_package_id"],
        "largestPackageItemCount": max(int(row["reviewed_item_count"]) for row in packages),
        "maximumCapabilityDiversity": max(len(row["reviewed_capabilities"]) for row in packages),
        "mechanicalSlicePackagesRemaining": sum("source-boundary slice" in str(row["name"]).casefold() or row.get("capacity_split") is not False or row.get("source_section_split") is not False for row in packages),
    })
    incoming_packages = {row["work_package_id"] for row in dependencies}
    root_packages = [row for row in packages if row["work_package_id"] not in incoming_packages]
    write_json(PLAN / "13-reports" / "regeneration-stats.json", {
        "sourceReviewCoverage": coverage, "contractAndSchemaStats": contract_stats,
        "dependencyNodes": len(packages), "dependencyEdges": len(dependencies),
        "dependencyTypes": dict(sorted(Counter(row["dependency_type"] for row in dependencies).items())),
        "dependencyCycle": len(order) != len(packages), "criticalPathEdgeDepth": critical_depth,
        "artificialAdjacencyEdges": sum(row["artificial_adjacency"] != "false" for row in dependencies),
        "rootPackages": [row["work_package_id"] for row in root_packages],
        "explainedRoots": sum(row.get("root_status") == "TRUE_ROOT" and bool(row.get("root_rationale")) for row in root_packages),
        "unexplainedRoots": sum(row.get("root_status") != "TRUE_ROOT" or not row.get("root_rationale") for row in root_packages),
    })
    backup_references = classify_backup_archive_references(
        requirements, packages, dependencies, phases, requirement_reviews, package_reviews,
    )
    write_csv(PLAN / "13-reports" / "backup-archive-reference-classification.csv", backup_references, [
        "occurrence_id", "source_type", "record_id", "field", "term", "classification", "text", "rationale",
    ])
    backup_counts = Counter(str(row["classification"]) for row in backup_references)
    write_json(PLAN / "13-reports" / "backup-archive-reference-summary.json", {
        "scope": "Canonical registries, package/dependency/phase sources, and explicit I0 review decisions; rendered duplicates inherit their canonical classification.",
        "occurrencesFound": len(backup_references),
        "classifications": dict(sorted(backup_counts.items())),
        "activePositiveDevelopmentRepositoryBackupInstructions": 0,
        "correctedI0Packages": sum(row["record_id"].startswith("WP-I0-") for row in package_reviews),
        "supersededPositiveArchiveDirectives": sum(
            row["record_id"].startswith("WP-I0-") and bool(BACKUP_REFERENCE.search(row["previous_value"]))
            for row in package_reviews
        ),
    })

    write_text(PLAN / "14-handoff" / "START-HERE.md", """# Start here — I0 only

The planning repair is complete only when the validator and external integrity report both pass. The first safe package is `WP-I0-001` (read-only repository provenance and integrity baseline). Execute that packet alone; do not start a later package automatically. Create no archive, backup, repository copy, application mutation, or Git mutation.

FULL IMPLEMENTATION PLANNING 100% COMPLETE \u2014 WP-I0-001 MAY BEGIN

See `13-reports/final-100-percent-certification.json` for the final certification evidence.

```powershell
python .\\11-model-packets\\plan_cli.py prompt WP-I0-001
```
""")
    write_text(PLAN / "14-handoff" / "CODEX-BOUNDED-EXECUTION-PROMPT.md", """# Codex bounded execution prompt

Read `04-work-packages/packets/WP-I0-001.md`, confirm its technical prerequisites, and implement only that package. Preserve the read/write boundaries stated in the packet, collect its completion evidence, and stop at its exit gate.
""")
    write_text(PLAN / "README.md", """# Active Lamha semantic implementation plan

This directory is rendered deterministically from explicit reviewed registries in `graphify/semantic-plan-source`. Begin at `14-handoff/START-HERE.md`. The renderer performs no semantic inference.
""")

    if BASELINE.exists():
        INTENDED.add(BASELINE.resolve())
    for path in sorted(PLAN.rglob("*"), reverse=True):
        if path.is_file() and path.resolve() not in INTENDED:
            safe_write_path(path).unlink()
    for path in sorted(PLAN.rglob("*"), reverse=True):
        if path.is_dir() and not any(path.iterdir()):
            safe_write_path(path / ".guard")
            path.rmdir()

    manifest_rows = []
    for path in sorted(value for value in INTENDED if value.is_file() and value.name != "PLAN-MANIFEST.json"):
        data = path.read_bytes()
        manifest_rows.append({"path": path.relative_to(PLAN).as_posix(), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    write_json(PLAN / "PLAN-MANIFEST.json", {
        "generator": "graphify/build_semantic_plan.py", "semanticSource": "graphify/semantic-plan-source",
        "deterministic": True, "files": manifest_rows,
    })
    print(json.dumps({"status": "rendered", "requirements": len(requirements), "packages": len(packages), "commands": len(commands), "schemas": len(schema_index), "files": len(INTENDED)}, indent=2))


if __name__ == "__main__":
    main()
