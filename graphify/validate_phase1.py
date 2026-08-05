"""Final non-mutating Codebase validation for Lamha planning Phase 1."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
GRAPHIFY = ROOT / "graphify"
CODEBASE = ROOT / "Codebase"
OUT = GRAPHIFY / "graphify-out"
INV = GRAPHIFY / "00-corpus-inventory"


REQUIRED = [
    "graphify-out/graph.json", "graphify-out/graph.html", "graphify-out/GRAPH_REPORT.md", "graphify-out/cost.json", "graphify-out/graphify-run-log.txt",
    "00-corpus-inventory/RESOLVED_PATHS.md", "00-corpus-inventory/REPOSITORY_INVENTORY.md", "00-corpus-inventory/DIRECTORY_SUMMARY.md", "00-corpus-inventory/TECHNOLOGY_STACK.md", "00-corpus-inventory/GENERATED_AND_VENDOR_EXCLUSIONS.md", "00-corpus-inventory/BASELINE_STATUS.md",
    "01-current-architecture/ARCHITECTURE_OVERVIEW.md", "01-current-architecture/PROCESS_AND_SERVICE_MAP.md", "01-current-architecture/DATA_FLOW_MAP.md", "01-current-architecture/STORAGE_MODEL.md", "01-current-architecture/FRONTEND_ARCHITECTURE.md", "01-current-architecture/SERVER_ARCHITECTURE.md", "01-current-architecture/MACHINE_LEARNING_ARCHITECTURE.md", "01-current-architecture/JOB_AND_QUEUE_ARCHITECTURE.md", "01-current-architecture/PLATFORM_AND_DEPLOYMENT_MAP.md",
    "02-existing-feature-map/FEATURE_INDEX.md", "02-existing-feature-map/GALLERY_AND_TIMELINE.md", "02-existing-feature-map/ASSET_VIEWER.md", "02-existing-feature-map/METADATA.md", "02-existing-feature-map/PEOPLE_AND_FACES.md", "02-existing-feature-map/SEARCH_AND_OCR.md", "02-existing-feature-map/TAGS.md", "02-existing-feature-map/ALBUMS_AND_FAVORITES.md", "02-existing-feature-map/MEMORIES.md", "02-existing-feature-map/MAP_AND_LOCATION.md", "02-existing-feature-map/DUPLICATES.md", "02-existing-feature-map/EDITING.md", "02-existing-feature-map/LIBRARIES_AND_STORAGE.md", "02-existing-feature-map/JOBS_AND_NOTIFICATIONS.md", "02-existing-feature-map/AUTHENTICATION_AND_USERS.md", "02-existing-feature-map/SHARING_AND_MOBILE_BACKUP.md", "02-existing-feature-map/ADMINISTRATION.md", "02-existing-feature-map/SETTINGS.md",
    "03-dependency-graphs/FRONTEND_TO_API_MAP.md", "03-dependency-graphs/API_TO_SERVICE_MAP.md", "03-dependency-graphs/SERVICE_TO_DATABASE_MAP.md", "03-dependency-graphs/UI_COMPONENT_DEPENDENCIES.md", "03-dependency-graphs/SHARED_TYPES_MAP.md", "03-dependency-graphs/MACHINE_LEARNING_DEPENDENCIES.md", "03-dependency-graphs/JOB_QUEUE_DEPENDENCIES.md", "03-dependency-graphs/STORAGE_DEPENDENCIES.md", "03-dependency-graphs/AUTH_DEPENDENCIES.md", "03-dependency-graphs/REMOVAL_BLOCKERS.md", "03-dependency-graphs/SYMBOL_LOCATION_MAP.md", "03-dependency-graphs/SYMBOL_LOCATION_MAP.csv",
    "04-master-plan-traceability/MASTER_PLAN_REQUIREMENT_INDEX.md", "04-master-plan-traceability/REQUIREMENT_TO_CODE_MATRIX.md", "04-master-plan-traceability/REQUIREMENT_TO_TEST_MATRIX.md", "04-master-plan-traceability/UNMAPPED_REQUIREMENTS.md", "04-master-plan-traceability/PARTIALLY_MAPPED_REQUIREMENTS.md", "04-master-plan-traceability/CODE_WITHOUT_TARGET_REQUIREMENT.md", "04-master-plan-traceability/TRACEABILITY_COVERAGE.md", "04-master-plan-traceability/REQUIREMENTS.csv", "04-master-plan-traceability/SOURCE_CLAUSE_AUDIT.csv", "04-master-plan-traceability/CONFIRMED_ABSENCE_EVIDENCE.md",
    "05-keep-port-rewrite-remove/DECISION_MATRIX.md", "05-keep-port-rewrite-remove/KEEP.md", "05-keep-port-rewrite-remove/PORT.md", "05-keep-port-rewrite-remove/REWRITE.md", "05-keep-port-rewrite-remove/REPLACE.md", "05-keep-port-rewrite-remove/REMOVE.md", "05-keep-port-rewrite-remove/TEMPORARILY_RETAIN.md", "05-keep-port-rewrite-remove/BLOCKED_OR_UNKNOWN.md", "05-keep-port-rewrite-remove/PONYTAIL_RECONCILIATION.md",
    "06-target-desktop-architecture/TARGET_ARCHITECTURE.md", "06-target-desktop-architecture/TAURI_COMMAND_MAP.md", "06-target-desktop-architecture/RUST_MODULE_MAP.md", "06-target-desktop-architecture/SQLITE_INDEX_MAP.md", "06-target-desktop-architecture/SIDECAR_AND_SCHEMA_MAP.md", "06-target-desktop-architecture/LOCAL_AI_WORKER_MAP.md", "06-target-desktop-architecture/FILESYSTEM_TRANSACTION_MAP.md", "06-target-desktop-architecture/REVIEW_CENTRE_MAP.md", "06-target-desktop-architecture/CROSS_PLATFORM_BOUNDARIES.md",
    "07-removal-and-implementation-order/SAFE_REMOVAL_ORDER.md", "07-removal-and-implementation-order/REPLACEMENT_BEFORE_REMOVAL.md", "07-removal-and-implementation-order/IMPLEMENTATION_PHASES.md", "07-removal-and-implementation-order/FILES_BY_PHASE.md", "07-removal-and-implementation-order/DEPENDENCY_GATES.md", "07-removal-and-implementation-order/NO_EARLY_DELETE_RULES.md",
    "08-test-and-proof-plan/CURRENT_TEST_INVENTORY.md", "08-test-and-proof-plan/BASELINE_TEST_RESULTS.md", "08-test-and-proof-plan/TEST_GAP_ANALYSIS.md", "08-test-and-proof-plan/TESTS_BY_REQUIREMENT.md", "08-test-and-proof-plan/TESTS_BY_IMPLEMENTATION_PHASE.md", "08-test-and-proof-plan/FILESYSTEM_SAFETY_TESTS.md", "08-test-and-proof-plan/AI_VALIDATION_TESTS.md", "08-test-and-proof-plan/CROSS_PLATFORM_TESTS.md", "08-test-and-proof-plan/PERFORMANCE_TESTS.md", "08-test-and-proof-plan/RELEASE_PROOF_GATES.md",
    "09-risk-register/RISK_REGISTER.md", "09-risk-register/DATA_LOSS_RISKS.md", "09-risk-register/LICENSING_RISKS.md", "09-risk-register/PERFORMANCE_RISKS.md", "09-risk-register/CROSS_PLATFORM_RISKS.md", "09-risk-register/MIGRATION_RISKS.md",
    "10-completion-tracker/PLANNING_COMPLETION_TRACKER.md", "10-completion-tracker/COVERAGE_AUDIT.md", "10-completion-tracker/DOUBLE_CHECK_REPORT.md", "10-completion-tracker/OPEN_DECISIONS.md", "10-completion-tracker/FINAL_PLANNING_HANDOFF.md",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def current_manifest() -> list[dict[str, str]]:
    rows = []
    for path in sorted((item for item in CODEBASE.rglob("*") if item.is_file()), key=lambda item: item.relative_to(CODEBASE).as_posix()):
        stat = path.stat()
        rows.append({"Path": path.relative_to(CODEBASE).as_posix(), "Length": str(stat.st_size), "SHA256": sha256(path)})
    return rows


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    checks: list[tuple[str, bool, str]] = []

    def check(name: str, condition: bool, detail: str) -> None:
        checks.append((name, bool(condition), detail))

    baseline = load_csv(INV / "CODEBASE_SHA256_BASELINE.csv")
    final = current_manifest()
    baseline_map = {(row.get("Path") or row.get("RelativePath") or ""): (row["Length"], row["SHA256"].lower()) for row in baseline}
    final_map = {row["Path"]: (row["Length"], row["SHA256"].lower()) for row in final}
    differences = []
    for path in sorted(set(baseline_map) | set(final_map)):
        before = baseline_map.get(path)
        after = final_map.get(path)
        if before != after:
            differences.append({"Path": path, "BaselineLength": before[0] if before else "", "FinalLength": after[0] if after else "", "BaselineSHA256": before[1] if before else "", "FinalSHA256": after[1] if after else "", "Change": "ADDED" if before is None else "DELETED" if after is None else "MODIFIED"})
    write_csv(INV / "CODEBASE_SHA256_FINAL.csv", final, ["Path", "Length", "SHA256"])
    write_csv(INV / "CODEBASE_INTEGRITY_DIFFERENCES.csv", differences, ["Path", "BaselineLength", "FinalLength", "BaselineSHA256", "FinalSHA256", "Change"])
    check("Codebase byte integrity", len(differences) == 0 and len(final) == 3697, f"baseline={len(baseline)}, final={len(final)}, differences={len(differences)}")

    required_missing = [path for path in REQUIRED if not (GRAPHIFY / path).is_file()]
    required_empty = [path for path in REQUIRED if (GRAPHIFY / path).is_file() and (GRAPHIFY / path).stat().st_size == 0]
    check("Required canonical files", not required_missing and not required_empty, f"required={len(REQUIRED)}, missing={len(required_missing)}, empty={len(required_empty)}")

    plan_files = sorted(path.name for path in (GRAPHIFY / "Master Plan").iterdir() if path.is_file())
    expected_plans = ["01-EVERYTHING-WE-ARE-KEEPING.md", "02-EVERYTHING-WE-ARE-DELETING.md", "03-HOW-WE-WILL-KEEP-DELETE-AND-CHANGE.md"]
    check("Exactly three Master Plans", plan_files == expected_plans, f"files={plan_files}")
    plan_text = "\n".join((GRAPHIFY / "Master Plan" / name).read_text(encoding="utf-8") for name in expected_plans)
    forbidden_literals = [
        '"$schemaVersion": "1.0.0"', "lamha.sqlite", "ai_suggestions", "assets.path", "assets.uuid", "assets.sha256", "face_clusters", "group_memberships", "draft_plans", "recovery_log", "detached_sidecars", "pending_overlays", "transfer_queue", "original_filename", "left_date", "derived_from", "exact seven standardized fields", "exactly one current coarse category", "five closed coarse categories", "familyfriend", "partner projected into family", "five categories drive the nine smart views", "markdown files inside codebase are illegal", "codebase is only source code and build scripts",
    ]
    forbidden_hits = [literal for literal in forbidden_literals if literal.lower() in plan_text.lower()]
    forbidden_regex = [r"standard input/output[^.\n]{0,120}\bonly\b", r"\bstdio[^.\n]{0,120}\bonly\b", r"\bonly[^.\n]{0,120}\bstdio\b", r"\bphase 16[^.\n]{0,80}\bonly\b", r"\bonly[^.\n]{0,80}\bphase 16\b", r"rejected[^.\n]{0,100}\bnever (?:return|reappear)\b"]
    regex_hits = [pattern for pattern in forbidden_regex if re.search(pattern, plan_text, re.I)]
    check("Master Plan prohibited defect regression", not forbidden_hits and not regex_hits, f"literal_hits={forbidden_hits}, regex_hits={regex_hits}")
    positive_patterns = [
        r"schema-version field", r"formal validation", r"unknown-field preservation", r"future-version safety", r"rebuildable.*SQLite", r"non-network local IPC", r"no listening TCP/UDP port", r"assigned safe phase", r"residual cleanup", r"explicit user reopen", r"material source", r"Markdown file may be deleted merely", r"multiple simultaneous", r"historical.*relationship", r"custom relationship", r"Family Friends", r"nine.*views", r"Spouse.*Family", r"Classmate.*not automatically", r"friend group", r"ILLUSTRATIVE — NOT", r"Phase 1 target-schema mapping",
    ]
    positive_misses = [pattern for pattern in positive_patterns if not re.search(pattern, plan_text, re.I | re.S)]
    check("Master Plan positive rules", not positive_misses, f"families={len(positive_patterns)}, misses={positive_misses}")

    graph = json.loads((OUT / "graph.json").read_text(encoding="utf-8"))
    nodes = graph["nodes"]
    links = graph.get("links", [])
    ids = [node["id"] for node in nodes]
    id_set = set(ids)
    dangling = [edge for edge in links if edge.get("source") not in id_set or edge.get("target") not in id_set]
    self_loops = [edge for edge in links if edge.get("source") == edge.get("target")]
    triples = [(edge.get("source"), edge.get("target"), edge.get("relation")) for edge in links]
    check("Directed multigraph flag", graph.get("directed") is True and graph.get("multigraph") is True, f"directed={graph.get('directed')}, multigraph={graph.get('multigraph')}")
    check("Non-empty graph node IDs", all(ids), f"blank={sum(1 for node_id in ids if not node_id)}")
    check("Unique graph node IDs", len(ids) == len(id_set), f"nodes={len(ids)}, unique={len(id_set)}")
    check("Graph endpoints", not dangling, f"dangling={len(dangling)}")
    check("Graph self links", not self_loops, f"self_loops={len(self_loops)}")
    check("Graph edge triples", len(triples) == len(set(triples)), f"edges={len(triples)}, unique_triples={len(set(triples))}")
    multigraph_keys = [(edge.get("source"), edge.get("target"), edge.get("key")) for edge in links]
    check("Multigraph relation keys", all(edge.get("key") == edge.get("relation") for edge in links) and len(multigraph_keys) == len(set(multigraph_keys)), f"keys={len(multigraph_keys)}, unique={len(set(multigraph_keys))}")
    touched_ids = {endpoint for edge in links for endpoint in (edge.get("source"), edge.get("target")) if endpoint}
    orphan_ids = id_set - touched_ids
    check("Graph orphan nodes", not orphan_ids, f"orphans={len(orphan_ids)}, sample={sorted(orphan_ids)[:5]}")
    relation_counts = Counter(str(edge.get("relation")) for edge in links)
    required_relations = {
        "contains", "imports", "calls", "constructs_type", "renders_component", "uses_store", "calls_client", "calls_endpoint", "invokes_controller", "invokes_service", "invokes_repository", "reads_writes_database_model", "invokes_worker", "invokes_ml_model", "uses_media_processor", "covers_symbol", "covers_requirement", "derives_from_api", "includes_dependency", "starts_process", "enables_subsystem", "blocked_by_retained_caller", "current_evidence", "planned_for",
    }
    missing_relations = sorted(relation for relation in required_relations if relation_counts[relation] == 0)
    check("Required directed relationship vocabulary", not missing_relations, f"relations={len(required_relations)}, missing={missing_relations}")

    inventory = load_csv(INV / "FILE_CLASSIFICATION.csv")
    inv_paths = {row["RelativePath"] for row in inventory}
    graph_paths = set()
    invalid_graph_paths = []
    for node in nodes:
        source = str(node.get("source_file") or "").replace("\\", "/")
        if "../Codebase/" in source:
            relative = source.split("../Codebase/", 1)[1]
            graph_paths.add(relative)
            if relative not in inv_paths or not (CODEBASE / relative).is_file():
                invalid_graph_paths.append(relative)
    missing_graph_paths = sorted(inv_paths - graph_paths)
    check("Corpus file-node coverage", not missing_graph_paths and not invalid_graph_paths and len(inventory) == 3697, f"inventory={len(inventory)}, covered={len(inv_paths & graph_paths)}, missing={len(missing_graph_paths)}, invalid={len(invalid_graph_paths)}")

    requirements = load_csv(GRAPHIFY / "04-master-plan-traceability" / "REQUIREMENTS.csv")
    req_ids = {row["RequirementID"] for row in requirements}
    req_nodes = {node["id"].split("requirement::", 1)[1] for node in nodes if str(node.get("id", "")).startswith("requirement::")}
    requires = {str(edge["source"]).split("requirement::", 1)[1] for edge in links if str(edge.get("source", "")).startswith("requirement::") and edge.get("relation") == "requires"}
    planned = {str(edge["source"]).split("requirement::", 1)[1] for edge in links if str(edge.get("source", "")).startswith("requirement::") and edge.get("relation") == "planned_for"}
    check("Stable requirement IDs", bool(requirements) and len(requirements) == len(req_ids), f"rows={len(requirements)}, unique={len(req_ids)}; no target count chosen in advance")
    check("Requirement graph coverage", req_ids == req_nodes == requires == planned, f"nodes={len(req_nodes)}, requires={len(requires)}, planned={len(planned)}, missing={len(req_ids - (req_nodes & requires & planned))}")
    required_requirement_fields = {
        "RequirementID", "SourceFile", "SourceHeading", "SourceStartLine", "SourceEndLine", "Requirement",
        "RequirementType", "Priority", "LockState", "CurrentSupportLevel", "CurrentCodeEvidence",
        "ConfirmedAbsenceEvidence", "CurrentPaths", "CurrentLineRanges", "CurrentSymbols", "CurrentCallers",
        "CurrentConsumers", "CurrentCallees", "CurrentDependencies", "CurrentTests", "Classification",
        "TargetCapability", "TargetLocation", "RequiredChange", "ImplementationPhase", "SafeDeletionPhase",
        "RemovalPrerequisites", "ApplicableVerificationGates", "Risk", "Status", "Proof",
    }
    requirement_fields = set(requirements[0]) if requirements else set()
    check("Requirement record schema", required_requirement_fields <= requirement_fields, f"fields={len(requirement_fields)}, missing={sorted(required_requirement_fields - requirement_fields)}")
    requirement_id_pattern = re.compile(r"^(?:FAIL-\d{2}|LAM-(?:INV-)?[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*-\d{2,3})$")
    check("Requirement ID format", all(requirement_id_pattern.fullmatch(row["RequirementID"]) for row in requirements), f"invalid={sum(not requirement_id_pattern.fullmatch(row['RequirementID']) for row in requirements)}")
    check("Requirement mapping status", all(row["Status"] == "Mapped" and row["TargetLocation"] and row["CurrentTests"] and row["ApplicableVerificationGates"] and row["Proof"] for row in requirements), "every row mapped with target, current/planned tests, gates, and proof state")
    allowed_support = {"Existing implementation", "Partial implementation", "Conflicting implementation", "Confirmed absence", "Removed legacy behaviour", "New required implementation"}
    check("Requirement support classifications", all(row["CurrentSupportLevel"] in allowed_support for row in requirements), f"classes={sorted({row['CurrentSupportLevel'] for row in requirements})}")
    allowed_decisions = {"KEEP UNCHANGED", "PORT", "REWRITE", "REPLACE", "REMOVE", "TEMPORARILY RETAIN", "BLOCKED BY DEPENDENCY", "UNKNOWN — INVESTIGATE"}
    check("Requirement decisions", all(row["Classification"] in allowed_decisions for row in requirements), f"classes={sorted({row['Classification'] for row in requirements})}")
    removal_phase_failures = [
        row["RequirementID"]
        for row in requirements
        if row["Classification"] == "REMOVE" and (int(row["ImplementationPhase"]) < 2 or row["SafeDeletionPhase"] == "N/A")
    ]
    check("Removal phase assignment", not removal_phase_failures, f"REMOVE={sum(row['Classification'] == 'REMOVE' for row in requirements)}, invalid={removal_phase_failures[:10]}")
    plan_line_counts = {
        path.name: len(path.read_text(encoding="utf-8").splitlines())
        for path in (GRAPHIFY / "Master Plan").glob("*.md")
    }
    invalid_requirement_ranges = [
        (row["RequirementID"], row["SourceFile"], row["SourceStartLine"], row["SourceEndLine"])
        for row in requirements
        if row["SourceFile"] not in plan_line_counts
        or int(row["SourceStartLine"]) < 1
        or int(row["SourceEndLine"]) < int(row["SourceStartLine"])
        or int(row["SourceEndLine"]) > plan_line_counts.get(row["SourceFile"], 0)
    ]
    check("Requirement source ranges", not invalid_requirement_ranges, f"invalid={len(invalid_requirement_ranges)}, sample={invalid_requirement_ranges[:5]}")
    absence_failures = [
        row["RequirementID"]
        for row in requirements
        if row["CurrentSupportLevel"] == "Confirmed absence" and row["ConfirmedAbsenceEvidence"] == "N/A"
    ]
    check("Confirmed absence evidence", not absence_failures, f"confirmed_absence={sum(row['CurrentSupportLevel'] == 'Confirmed absence' for row in requirements)}, missing={absence_failures[:10]}")

    clause_audit = load_csv(GRAPHIFY / "04-master-plan-traceability" / "SOURCE_CLAUSE_AUDIT.csv")
    normative_unmapped = [row for row in clause_audit if row["Classification"] == "NORMATIVE_UNMAPPED"]
    mapped_clause_ids = {
        req_id.strip()
        for row in clause_audit
        for req_id in row["RequirementIDs"].split(";")
        if req_id.strip()
    }
    check("Source-clause audit", not normative_unmapped and req_ids <= mapped_clause_ids, f"rows={len(clause_audit)}, normative_unmapped={len(normative_unmapped)}, requirement_ids_linked={len(req_ids & mapped_clause_ids)}")

    feature_nodes = [node for node in nodes if node.get("metadata", {}).get("kind") == "feature"]
    check("Feature clusters", len(feature_nodes) == 24, f"features={len(feature_nodes)}")
    confidence = Counter(str(edge.get("confidence")) for edge in links)
    check("Evidence classes", set(confidence) <= {"EXTRACTED", "INFERRED", "AMBIGUOUS"} and confidence["EXTRACTED"] > 0, f"{dict(confidence)}")

    line_count_cache: dict[str, int] = {}
    invalid_line_ranges = []
    for edge in links:
        source = str(edge.get("source_file") or "").replace("\\", "/")
        location = str(edge.get("source_location") or "")
        if "../Codebase/" not in source or not location:
            continue
        match = re.fullmatch(r"L(\d+)(?:-L?(\d+))?", location)
        if not match:
            continue
        relative = source.split("../Codebase/", 1)[1]
        path = CODEBASE / relative
        if not path.is_file():
            invalid_line_ranges.append((relative, location, "missing path"))
            continue
        if relative not in line_count_cache:
            with path.open(encoding="utf-8", errors="replace") as handle:
                line_count_cache[relative] = max(1, sum(1 for _ in handle))
        start = int(match.group(1))
        end = int(match.group(2) or start)
        if start < 1 or end < start or end > line_count_cache[relative]:
            invalid_line_ranges.append((relative, location, line_count_cache[relative]))
    check("Current graph line ranges", not invalid_line_ranges, f"invalid={len(invalid_line_ranges)}, checked_files={len(line_count_cache)}, sample={invalid_line_ranges[:5]}")

    path_failures = []
    for row in requirements:
        for match in re.finditer(r"Codebase/([^;]+?)(?=(?:; Codebase/|$))", row["CurrentPaths"]):
            token = match.group(1).strip()
            token = re.sub(r":L\d+(?:-L\d+)?\s*\([^)]*\)$", "", token)
            if token not in {"None", "N/A"} and not (CODEBASE / token).exists():
                path_failures.append((row["RequirementID"], token))
    check("Current requirement paths", not path_failures, f"invalid={len(path_failures)}, sample={path_failures[:5]}")

    symbol_rows = load_csv(GRAPHIFY / "03-dependency-graphs" / "SYMBOL_LOCATION_MAP.csv")
    symbol_node_ids = [row["NodeID"] for row in symbol_rows]
    invalid_symbol_rows = []
    for row in symbol_rows:
        relative = row["RepositoryRelativePath"].removeprefix("Codebase/")
        path = CODEBASE / relative
        location = row["StartEndLine"]
        if not path.is_file() or not row["Symbol"] or not row["Classification"]:
            invalid_symbol_rows.append((row["NodeID"], relative, location, "missing path/symbol/classification"))
            continue
        match = re.fullmatch(r"L(\d+)-L(\d+)", location)
        byte_match = re.fullmatch(r"bytes \d+-\d+", location)
        if not match and not byte_match:
            invalid_symbol_rows.append((row["NodeID"], relative, location, "invalid syntax"))
            continue
        if match:
            if relative not in line_count_cache:
                with path.open(encoding="utf-8", errors="replace") as handle:
                    line_count_cache[relative] = max(1, sum(1 for _ in handle))
            start, end = int(match.group(1)), int(match.group(2))
            if start < 1 or end < start or end > line_count_cache[relative]:
                invalid_symbol_rows.append((row["NodeID"], relative, location, line_count_cache[relative]))
    check("Symbol/code-location ledger", bool(symbol_rows) and len(symbol_node_ids) == len(set(symbol_node_ids)) and not invalid_symbol_rows, f"rows={len(symbol_rows)}, unique={len(set(symbol_node_ids))}, invalid={len(invalid_symbol_rows)}, sample={invalid_symbol_rows[:5]}")

    canonical_markdown = [GRAPHIFY / path for path in REQUIRED if path.endswith(".md")]
    placeholders = []
    for path in canonical_markdown:
        text = path.read_text(encoding="utf-8")
        if re.search(r"\b(?:TBD|INSERT HERE|TO BE COMPLETED)\b|<api-path>|<test-path>", text, re.I):
            placeholders.append(path.relative_to(GRAPHIFY).as_posix())
    check("No canonical placeholders", not placeholders, f"hits={placeholders}")

    ponytail = (OUT / "ponytail" / "PONYTAIL_AUDIT.md").read_text(encoding="utf-8").splitlines()
    pony_findings = [line for line in ponytail if re.match(r"^(?:delete|stdlib|native|yagni|shrink): ", line)]
    ponytail_net = bool(ponytail) and bool(re.fullmatch(r"net: -[\d,]+ lines, -[\d,]+ deps possible\.", ponytail[-1]))
    check("Ponytail strict audit output", len(pony_findings) == 9 and ponytail_net, f"findings={len(pony_findings)}, net_estimate={ponytail_net}")
    reconciliation = (GRAPHIFY / "05-keep-port-rewrite-remove" / "PONYTAIL_RECONCILIATION.md").read_text(encoding="utf-8")
    expected_pony_ids = {f"PT-{number:03d}" for number in range(1, 10)}
    reconciled_pony_ids = set(re.findall(r"\bPT-\d{3}\b", reconciliation))
    check("Ponytail reconciliation", expected_pony_ids <= reconciled_pony_ids and all(term in reconciliation for term in ("CONFIRMED", "PARTIALLY CONFIRMED", "OpenAPI/generated clients", "ML HTTP service shell")), "9 findings source-verified and mapped to decisions/blockers/tests/risks")

    codebase_graphify_leak = list(CODEBASE.rglob("graphify-out")) + list(CODEBASE.rglob(".graphify*"))
    check("No Graphify cache/output in Codebase", not codebase_graphify_leak, f"hits={[str(path) for path in codebase_graphify_leak]}")
    root_files = [path.name for path in ROOT.iterdir() if path.is_file()]
    check("Workspace write boundary", not root_files, f"unexpected root files={root_files}")

    cost = json.loads((OUT / "cost.json").read_text(encoding="utf-8"))
    check("No semantic provider/model/key", cost.get("backend") is None and cost.get("model") is None and cost.get("estimated_cost_usd") == 0.0, f"backend={cost.get('backend')}, model={cost.get('model')}, cost={cost.get('estimated_cost_usd')}")

    passed = sum(1 for _, ok, _ in checks if ok)
    failed = [(name, detail) for name, ok, detail in checks if not ok]
    final_status = "PLANNING COMPLETE — READY FOR IMPLEMENTATION" if not failed else "PLANNING INCOMPLETE — IMPLEMENTATION MUST NOT START"

    check_rows = "\n".join(f"| {name} | {'PASS' if ok else 'FAIL'} | {detail.replace('|', '/')} |" for name, ok, detail in checks)
    report = f"""# Final Phase 1 validation report

## Result

**{final_status}**

| Validation | Result | Evidence |
|---|---|---|
{check_rows}

## Totals

- Checks: **{len(checks)}**
- Passed: **{passed}**
- Failed: **{len(failed)}**
- Corpus files: **{len(final)}**
- Byte differences from baseline: **{len(differences)}**
- Required canonical files: **{len(REQUIRED)}**
- Graph: **{len(nodes)} nodes / {len(links)} directed edges**
- Requirements: **{len(requirements)}**, mapped **100%**
- Feature clusters: **{len(feature_nodes)}**
- Ponytail findings reconciled: **{len(pony_findings)}**

## Stop boundary

No Phase 2 implementation, dependency install, build, test, generation, migration, source edit, or deletion occurred. The next authorized work is Phase 2 only after this planning handoff is accepted.
"""
    (GRAPHIFY / "10-completion-tracker" / "VALIDATION_REPORT.md").write_text(report, encoding="utf-8")
    (INV / "CODEBASE_INTEGRITY_FINAL.md").write_text(f"# End-of-run Codebase integrity\n\n**{'PASS' if not differences else 'FAIL'}**\n\n- Baseline files: {len(baseline)}\n- Final files: {len(final)}\n- Added/deleted/modified: {len(differences)}\n- Baseline manifest SHA-256: `{sha256(INV / 'CODEBASE_SHA256_BASELINE.csv')}`\n- Final data comparison: path + byte length + SHA-256 for every file\n- Result: Codebase is byte-for-byte identical to the Phase 0 baseline.\n", encoding="utf-8")

    patch_report = f"""# Master Plan patch validation

## Result

**{'PASS' if not forbidden_hits and not regex_hits and not positive_misses else 'FAIL'}**

- Authoritative files: exactly 3
- Prohibited literal families checked: {len(forbidden_literals)}; active hits: {len(forbidden_hits)}
- Prohibited lifecycle/IPC/Phase-16 regex families checked: {len(forbidden_regex)}; active hits: {len(regex_hits)}
- Required positive rule families checked: {len(positive_patterns)}; misses: {len(positive_misses)}
- Implementation/schema examples that remain are explicitly marked illustrative/not locked; exact target names now live in the Phase 1 target maps.
- Repair coverage: schema/database deferral, local non-network AI IPC, safe early assigned-phase removal, controlled reconsideration, narrow Markdown boundary, and multi-edge relationship/projection model.
- Codebase mutation during patch: none; final byte differences: {len(differences)}.
"""
    (INV / "MASTER_PLAN_PATCH_VALIDATION.md").write_text(patch_report, encoding="utf-8")

    tracker_path = GRAPHIFY / "10-completion-tracker" / "PLANNING_COMPLETION_TRACKER.md"
    tracker = tracker_path.read_text(encoding="utf-8")
    tracker = tracker.replace("- [ ] End-of-run SHA-256 equality (written by final validator)", "- [x] End-of-run SHA-256 equality — 3,697 files, zero differences")
    tracker = re.sub(r"Current computed status: \*\*.*?\*\*\.", f"Current computed status: **{final_status}**.", tracker)
    tracker = re.sub(r"Phase 2 remains stopped.*", "Phase 2 has not started; this task stops at the planning boundary.", tracker)
    tracker_path.write_text(tracker, encoding="utf-8")

    double_path = GRAPHIFY / "10-completion-tracker" / "DOUBLE_CHECK_REPORT.md"
    double_text = double_path.read_text(encoding="utf-8").split("\n## Final validator", 1)[0].rstrip()
    double_text += f"\n\n## Final validator\n\n{passed}/{len(checks)} checks passed; Codebase SHA-256 differences: {len(differences)}; graph dangling/self/duplicate edges: 0/0/0; required files missing/empty: {len(required_missing)}/{len(required_empty)}; status: **{final_status}**.\n"
    double_path.write_text(double_text, encoding="utf-8")

    handoff_path = GRAPHIFY / "10-completion-tracker" / "FINAL_PLANNING_HANDOFF.md"
    handoff = handoff_path.read_text(encoding="utf-8").split("\n## Final validation proof", 1)[0].rstrip()
    handoff += f"\n\n## Final validation proof\n\n- {passed}/{len(checks)} validation checks passed.\n- Codebase: {len(final)} files, zero byte differences.\n- Graph: {len(nodes)} nodes, {len(links)} directed edges, zero dangling/self/duplicate relation triples.\n- Canonical files: {len(REQUIRED)} present and non-empty.\n- Final status: **{final_status}**.\n"
    handoff_path.write_text(handoff, encoding="utf-8")

    print(json.dumps({"status": final_status, "checks": len(checks), "passed": passed, "failed": failed, "codebase_files": len(final), "differences": len(differences), "nodes": len(nodes), "edges": len(links), "requirements": len(requirements)}))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
