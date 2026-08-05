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
OBSERVABLE = re.compile(r"\b(return|display|shown?|report|reject|preserve|persist|remain|produce|update|pass|fail|create|support|write|read|render|detect|include|record|expose|leave|block|index|reflect|apply|invoke|store|execute|verify|validate|calculate|prevent|enforce|reconcile|restore|remove|communicate|open|close|suppress|reconsider|mark|use|embed|mutate|require|help|represent|derive|keep|plan|test|move|reference|add|split|identify|link|exist|survive|choose|save|retain|scope|rescan|track|correspond|change|limit|map|contribute|transition|inventory|classify|measure|provide|generate|follow|initialize|treat|establish)\w*\b", re.I)
PERMITTED_REVIEW_STATUSES = {"REVIEWED_CONFIRMED", "REVIEWED_CORRECTED", "REVIEW_REQUIRED", "BLOCKED", "NOT_APPLICABLE"}


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
            if row.get("requirement_type") == "ACCEPTANCE_CRITERION" and (not re.search(r"\b(given|when)\b", statement, re.I) or not has_observable):
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
        if row.get("reviewer_status") != "REVIEWED":
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
        "REQUIRES_SECURITY_BOUNDARY",
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
        ("WP-I12-007", "WP-I3-014"), ("WP-I4-012", "WP-I4-010"), ("WP-I9-003", "WP-I9-001"),
        ("WP-I11-002", "WP-I11-001"), ("WP-I11-009", "WP-I11-003"), ("WP-I13-003", "WP-I13-002"),
        ("WP-I13-007", "WP-I13-006"), ("WP-I15-005", "WP-I15-001"), ("WP-I15-015", "WP-I15-008"),
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
    active = [row for row in requirements if row["supersession_status"] == "ACTIVE" and row["requirement_type"] in IMPLEMENTATION_TYPES]
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
        "untestable_criteria": sum(row["requirement_type"] == "ACCEPTANCE_CRITERION" and (not re.search(r"\b(given|when)\b", row["statement"], re.I) or not OBSERVABLE.search(row["statement"])) for row in active),
        "missing_parent_relationships": sum(row["requirement_type"] == "ACCEPTANCE_CRITERION" and not row["parent_requirement_id"] for row in active),
        "missing_verification_methods": sum(not row["verification_method"] for row in active),
        "phase_package_mismatches": phase_mismatches,
        "stale_package_references": sum("work_package_id" in row for row in requirements),
        "unreviewed_mappings": sum(not mappings[row["canonical_id"]]["reviewer_status"].startswith("REVIEWED_") for row in active),
        "unreviewed_package_memberships": sum(row.get("reviewer_status") != "REVIEWED" for row in membership),
        "missing_dependency_rationales": sum(not row.get("technical_rationale") or not row.get("evidence") or not row.get("review_status", "").startswith("REVIEWED_") for row in edges),
        "missing_authority_schema_decisions": missing_authority_schema,
    }


def check_metrics_honesty(report: dict[str, object], computed: dict[str, int], builder_text: str) -> list[str]:
    errors: list[str] = []
    reported = report.get("computedQualityMetrics", {})
    if reported != computed:
        errors.append(f"reported quality metrics differ from independent computation: {reported} != {computed}")
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
    mapping_errors = check_mapping_records(mappings_list)
    if set(mappings) != {row["canonical_id"] for row in requirements}:
        mapping_errors.append("requirement/mapping ID sets differ")
    level("L3_EXPLICIT_SEMANTIC_MAPPING", mapping_errors)
    active_ids = {row["canonical_id"] for row in requirements if mappings[row["canonical_id"]]["primary_implementation_phase"] and row["requirement_type"] in IMPLEMENTATION_TYPES and row["supersession_status"] == "ACTIVE"}
    level("L4_WORK_PACKAGES", check_package_records(packages, membership, active_ids) + check_phase_package_consistency(requirements, mappings, packages, membership))
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
        con.executescript((PLAN / "07-sqlite" / "001_initial.sql").read_text(encoding="utf-8"))
    except sqlite3.Error as error:
        schema_errors.append(f"SQLite DDL execution failed: {error}")
    finally:
        con.close()
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
    if int(coverage.get("unreviewed_active_mappings", -1)) != 0 or int(coverage.get("unreviewed_memberships", -1)) != 0:
        audit_errors.append("review coverage reports unresolved mappings or memberships")
    level("L9_AUDIT_AUTHENTICITY", audit_errors)
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
    level("L11_SCOPE_SAFETY", check_scope_safety(packages, handoff))
    level("L12_PACKETS_AND_HANDOFF", packet_errors)
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
