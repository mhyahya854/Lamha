"""Package-local implementation governance primitives for WP-I0-011."""

from __future__ import annotations

import hashlib
import csv
import json
import os
import re
import tempfile
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable


STATUSES = {
    "NOT_STARTED",
    "READY",
    "SELECTED",
    "IN_PROGRESS",
    "REVIEW_PENDING",
    "COMPLETE",
    "BLOCKED",
}
ALLOWED_TRANSITIONS = {
    "NOT_STARTED": {"READY", "SELECTED", "BLOCKED"},
    "READY": {"SELECTED", "BLOCKED"},
    "SELECTED": {"IN_PROGRESS", "BLOCKED"},
    "IN_PROGRESS": {"REVIEW_PENDING", "BLOCKED"},
    "REVIEW_PENDING": {"IN_PROGRESS", "COMPLETE", "BLOCKED"},
    "BLOCKED": {"READY", "IN_PROGRESS"},
    "COMPLETE": set(),
}
PACKAGE_COMPLETE_GATES = {
    "focused_validation",
    "negative_validation",
    "regression_validation",
    "recovery_validation",
    "independent_review",
    "exit_gate",
    "github_verification",
}
REQUIREMENT_COMPLETE_GATES = {
    "focused_validation",
    "preservation_validation",
    "package_exit_gate",
    "github_verification",
}
PLACEHOLDER_PATTERN = re.compile(
    r"\b(?:TODO|FIXME|HACK|TEMP|stub|placeholder|unimplemented|todo!|unimplemented!)\b",
    re.IGNORECASE,
)


class GovernanceError(ValueError):
    """Typed validation failure with a stable machine-readable code."""

    def __init__(self, code: str, record: str, detail: str = "") -> None:
        self.code = code
        self.record = record
        self.detail = detail
        super().__init__(f"{code}:{record}" + (f":{detail}" if detail else ""))


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def semantic_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def revision_hash(revision: dict[str, Any]) -> str:
    material = {key: value for key, value in revision.items() if key != "revisionHash"}
    return semantic_hash(material)


def _nonempty(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return bool(value)
    return value is not None


def validate_evidence_gate(
    gate: dict[str, Any], record: str, repository_root: Path,
    pending_evidence: set[str] | None = None,
) -> None:
    if not isinstance(gate, dict):
        raise GovernanceError("GATE_TYPE_INVALID", record)
    required = (
        "gate", "status", "method", "commandOrInspection", "exitCode",
        "observableOutput", "changedSymbols", "evidenceLinks",
    )
    for key in required:
        if key not in gate or (key != "changedSymbols" and not _nonempty(gate.get(key))):
            raise GovernanceError("GATE_FIELD_MISSING", record, key)
    for key in ("gate", "status", "method", "commandOrInspection", "observableOutput"):
        if not isinstance(gate[key], str) or not gate[key].strip():
            raise GovernanceError("GATE_FIELD_TYPE", record, key)
    if type(gate["exitCode"]) is not int:
        raise GovernanceError("GATE_FIELD_TYPE", record, "exitCode")
    if not isinstance(gate["evidenceLinks"], list) or not all(
        isinstance(item, str) and item.strip() for item in gate["evidenceLinks"]
    ):
        raise GovernanceError("GATE_FIELD_TYPE", record, "evidenceLinks")
    if gate["status"] not in {"PASS", "NOT_APPLICABLE"}:
        raise GovernanceError("GATE_NOT_PASS", record, str(gate["status"]))
    if gate["status"] == "NOT_APPLICABLE" and not _nonempty(gate.get("rationale")):
        raise GovernanceError("GATE_NA_RATIONALE_MISSING", record, gate["gate"])
    if gate["status"] == "PASS" and gate.get("rationale") == "generic":
        raise GovernanceError("GATE_GENERIC_PROOF", record, gate["gate"])
    if not isinstance(gate["changedSymbols"], list) or not all(
        isinstance(item, str) and item.strip() for item in gate["changedSymbols"]
    ):
        raise GovernanceError("GATE_CHANGED_SYMBOLS_INVALID", record, gate["gate"])
    if not gate["changedSymbols"] and not _nonempty(gate.get("changedSymbolsNotApplicableReason")):
        raise GovernanceError("GATE_CHANGED_SYMBOLS_RATIONALE_MISSING", record, gate["gate"])
    if gate["status"] == "PASS" and gate["exitCode"] != 0:
        raise GovernanceError("GATE_EXIT_CODE_INVALID", record, gate["gate"])
    pending = pending_evidence or set()
    for raw in gate["evidenceLinks"]:
        if raw.startswith("git-origin:"):
            sha = raw.split(":", 1)[1]
            if not re.fullmatch(r"[0-9a-f]{40}", sha) or subprocess.run(
                ["git", "merge-base", "--is-ancestor", sha, "origin/main"],
                cwd=repository_root, capture_output=True,
            ).returncode != 0:
                raise GovernanceError("GATE_GIT_EVIDENCE_INVALID", record, raw)
            continue
        normalized = raw.replace("\\", "/").split("#", 1)[0]
        candidate = Path(normalized)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise GovernanceError("GATE_EVIDENCE_PATH_ESCAPE", record, raw)
        if normalized not in pending and not (repository_root / candidate).is_file():
            raise GovernanceError("GATE_EVIDENCE_MISSING", record, raw)


def validate_blocker(blocker: dict[str, Any], record: str) -> None:
    required = (
        "blockerId",
        "affectedRecord",
        "knownFacts",
        "exactUnknown",
        "safeChecksExhausted",
        "evidenceLinks",
        "independentWork",
    )
    allowed = set(required) | {"guessedPath", "guessedField", "guessedSchema", "guessedOwnership"}
    if set(blocker) - allowed:
        raise GovernanceError("BLOCKER_UNKNOWN_FIELD", record, ",".join(sorted(set(blocker) - allowed)))
    for key in required:
        if not _nonempty(blocker.get(key)):
            raise GovernanceError("BLOCKER_FIELD_MISSING", record, key)
    for key in ("knownFacts", "safeChecksExhausted", "evidenceLinks", "independentWork"):
        value = blocker[key]
        if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
            raise GovernanceError("BLOCKER_FIELD_TYPE", record, key)
    for key in ("blockerId", "affectedRecord", "exactUnknown"):
        if not isinstance(blocker[key], str):
            raise GovernanceError("BLOCKER_FIELD_TYPE", record, key)
    if any(blocker.get(field) for field in ("guessedPath", "guessedField", "guessedSchema", "guessedOwnership")):
        raise GovernanceError("BLOCKER_GUESS_PROHIBITED", record)
    if not all(isinstance(item, str) and item.strip() for item in blocker["safeChecksExhausted"]):
        raise GovernanceError("BLOCKER_CHECK_INVALID", record)


def validate_revision(
    revision: dict[str, Any],
    canonical_ids: set[str],
    package_ids: set[str],
    repository_root: Path,
    pending_evidence: set[str] | None = None,
) -> None:
    required = (
        "revisionId",
        "subjectType",
        "subjectId",
        "fromStatus",
        "toStatus",
        "actor",
        "timestamp",
        "evidenceLinks",
        "applicableGates",
        "previousRevisionHash",
        "revisionHash",
    )
    for key in required:
        if key not in revision:
            raise GovernanceError("REVISION_FIELD_MISSING", revision.get("revisionId", "?"), key)
    rid = revision["revisionId"]
    if revision["subjectType"] not in {"PACKAGE", "REQUIREMENT"}:
        raise GovernanceError("REVISION_SUBJECT_TYPE", rid)
    subject_id = revision["subjectId"]
    registry = package_ids if revision["subjectType"] == "PACKAGE" else canonical_ids
    if subject_id not in registry:
        raise GovernanceError("CANONICAL_ID_MISSING", rid, subject_id)
    if "statement" in revision:
        raise GovernanceError("EMBEDDED_STATEMENT_PROHIBITED", rid)
    if not _nonempty(revision["evidenceLinks"]):
        raise GovernanceError("REVISION_EVIDENCE_MISSING", rid)
    source = revision["fromStatus"]
    target = revision["toStatus"]
    if source not in STATUSES or target not in STATUSES:
        raise GovernanceError("STATUS_UNKNOWN", rid)
    if source == target or target not in ALLOWED_TRANSITIONS[source]:
        raise GovernanceError("STATUS_TRANSITION_INVALID", rid, f"{source}->{target}")
    if not _nonempty(revision["actor"]) or not _nonempty(revision["timestamp"]):
        raise GovernanceError("REVISION_AUDIT_FIELD_MISSING", rid)
    try:
        parsed = datetime.fromisoformat(revision["timestamp"].replace("Z", "+00:00"))
        if parsed.utcoffset() is None:
            raise ValueError("timezone offset required")
    except (TypeError, ValueError) as exc:
        raise GovernanceError("REVISION_TIMESTAMP_INVALID", rid) from exc
    for gate in revision["applicableGates"]:
        validate_evidence_gate(gate, rid, repository_root, pending_evidence)
    gate_names = {gate["gate"] for gate in revision["applicableGates"]}
    if target == "COMPLETE":
        expected = (
            PACKAGE_COMPLETE_GATES
            if revision["subjectType"] == "PACKAGE"
            else REQUIREMENT_COMPLETE_GATES
        )
        missing = sorted(expected - gate_names)
        if missing:
            raise GovernanceError("COMPLETE_GATE_MISSING", rid, ",".join(missing))
        if any(gate["status"] != "PASS" for gate in revision["applicableGates"] if gate["gate"] in expected):
            raise GovernanceError("COMPLETE_GATE_NOT_PASS", rid)
    if target == "BLOCKED":
        validate_blocker(revision.get("blocker", {}), rid)
        if revision["blocker"]["affectedRecord"] != subject_id:
            raise GovernanceError("BLOCKER_AFFECTED_RECORD_MISMATCH", rid)
    if source == "BLOCKED" and target in {"READY", "IN_PROGRESS"}:
        resolution = revision.get("resolution", {})
        for field in ("resolvedBlockerId", "reason", "evidenceLinks"):
            if not _nonempty(resolution.get(field)):
                raise GovernanceError("BLOCKER_RESOLUTION_MISSING", rid, field)
    if revision_hash(revision) != revision["revisionHash"]:
        raise GovernanceError("REVISION_HASH_MISMATCH", rid)


def validate_tracker(
    tracker: dict[str, Any],
    canonical_ids: set[str],
    package_ids: set[str],
    repository_root: Path,
    pending_evidence: set[str] | None = None,
    risk_ownership: Iterable[dict[str, Any]] | None = None,
    runtime_risk_evidence: Iterable[dict[str, Any]] | None = None,
    release_status: str = "PENDING",
    required_current_keys: set[str] | None = None,
) -> None:
    if tracker.get("schemaVersion") != 2:
        raise GovernanceError("TRACKER_SCHEMA_VERSION", "tracker")
    baselines = tracker.get("importedBaselines")
    if not isinstance(baselines, list):
        raise GovernanceError("TRACKER_BASELINES_MISSING", "tracker")
    revisions = tracker.get("revisions")
    if not isinstance(revisions, list) or not revisions:
        raise GovernanceError("TRACKER_REVISIONS_MISSING", "tracker")
    seen_ids: set[str] = set()
    last_by_subject: dict[tuple[str, str], str] = {}
    last_status: dict[tuple[str, str], str] = {}
    last_timestamp: dict[tuple[str, str], datetime] = {}
    open_blocker: dict[tuple[str, str], str] = {}
    for baseline in baselines:
        kind = baseline.get("subjectType")
        subject = baseline.get("subjectId")
        key = (kind, subject)
        if kind not in {"PACKAGE", "REQUIREMENT"}:
            raise GovernanceError("BASELINE_SUBJECT_TYPE", str(key))
        if key in last_status:
            raise GovernanceError("BASELINE_DUPLICATE", str(key))
        registry = package_ids if kind == "PACKAGE" else canonical_ids
        if subject not in registry or baseline.get("status") != "COMPLETE":
            raise GovernanceError("BASELINE_INVALID", str(key))
        if not _nonempty(baseline.get("evidenceLinks")) or not _nonempty(baseline.get("importedAt")):
            raise GovernanceError("BASELINE_EVIDENCE_MISSING", str(key))
        try:
            imported_time = datetime.fromisoformat(baseline["importedAt"].replace("Z", "+00:00"))
            if imported_time.utcoffset() is None:
                raise ValueError("timezone offset required")
        except (AttributeError, ValueError) as exc:
            raise GovernanceError("BASELINE_TIMESTAMP_INVALID", str(key)) from exc
        expected = PACKAGE_COMPLETE_GATES if kind == "PACKAGE" else REQUIREMENT_COMPLETE_GATES
        gates = baseline.get("applicableGates", [])
        for evidence_gate in gates:
            validate_evidence_gate(evidence_gate, f"baseline:{kind}:{subject}", repository_root, pending_evidence)
        if not expected <= {item["gate"] for item in gates if item["status"] == "PASS"}:
            raise GovernanceError("BASELINE_COMPLETE_GATES_MISSING", str(key))
        last_status[key] = "COMPLETE"
    for revision in revisions:
        rid = revision.get("revisionId", "?")
        if rid in seen_ids:
            raise GovernanceError("REVISION_ID_DUPLICATE", rid)
        seen_ids.add(rid)
        validate_revision(revision, canonical_ids, package_ids, repository_root, pending_evidence)
        key = (revision["subjectType"], revision["subjectId"])
        expected_previous = last_by_subject.get(key, "GENESIS")
        if revision["previousRevisionHash"] != expected_previous:
            raise GovernanceError("REVISION_PREDECESSOR_MISMATCH", rid)
        if key in last_status and revision["fromStatus"] != last_status[key]:
            raise GovernanceError("REVISION_STATUS_CHAIN_BROKEN", rid)
        parsed_timestamp = datetime.fromisoformat(revision["timestamp"].replace("Z", "+00:00"))
        if key in last_timestamp and parsed_timestamp < last_timestamp[key]:
            raise GovernanceError("REVISION_TIMESTAMP_ORDER", rid)
        last_by_subject[key] = revision["revisionHash"]
        last_status[key] = revision["toStatus"]
        last_timestamp[key] = parsed_timestamp
        if revision["toStatus"] == "BLOCKED":
            open_blocker[key] = revision["blocker"]["blockerId"]
        if revision["fromStatus"] == "BLOCKED":
            if revision.get("resolution", {}).get("resolvedBlockerId") != open_blocker.get(key):
                raise GovernanceError("BLOCKER_RESOLUTION_ID_MISMATCH", rid)
            open_blocker.pop(key, None)
    current = tracker.get("current", {})
    expected_current = {
        f"{kind}:{subject}": status for (kind, subject), status in last_status.items()
    }
    if current != expected_current:
        raise GovernanceError("TRACKER_CURRENT_MISMATCH", "tracker")
    missing_current = sorted((required_current_keys or set()) - set(current))
    if missing_current:
        raise GovernanceError("TRACKER_OWNED_COVERAGE_MISSING", "tracker", ",".join(missing_current))
    completed_packages = {
        subject for (kind, subject), status in last_status.items()
        if kind == "PACKAGE" and status == "COMPLETE"
    }
    declared_completed = tracker.get("completedPackages")
    if not isinstance(declared_completed, list) or set(declared_completed) != completed_packages:
        raise GovernanceError("TRACKER_COMPLETED_PACKAGES_MISMATCH", "tracker")
    ready_packages = tracker.get("readyPackages")
    if not isinstance(ready_packages, list) or any(package not in package_ids for package in ready_packages):
        raise GovernanceError("TRACKER_READY_PACKAGES_INVALID", "tracker")
    selected = tracker.get("selectedPackage")
    if selected is not None and selected not in ready_packages:
        raise GovernanceError("TRACKER_SELECTED_PACKAGE_INVALID", "tracker")
    explicit = tracker.get("explicitAuthorizedPackage")
    if explicit is not None and explicit not in ready_packages:
        raise GovernanceError("TRACKER_AUTHORIZATION_INVALID", "tracker")
    if completed_packages and risk_ownership is None:
        raise GovernanceError("RISK_ENFORCEMENT_CONTEXT_MISSING", "tracker")
    if risk_ownership is not None:
        package_statuses = {
            subject: status for (kind, subject), status in last_status.items() if kind == "PACKAGE"
        }
        validate_runtime_risk_gates(
            risk_ownership, package_statuses, runtime_risk_evidence or [], release_status,
            repository_root,
        )


def make_revision(
    *,
    revision_id: str,
    subject_type: str,
    subject_id: str,
    from_status: str,
    to_status: str,
    actor: str,
    timestamp: str,
    evidence_links: list[str],
    gates: list[dict[str, Any]],
    previous_hash: str = "GENESIS",
    blocker: dict[str, Any] | None = None,
    resolution: dict[str, Any] | None = None,
) -> dict[str, Any]:
    revision: dict[str, Any] = {
        "revisionId": revision_id,
        "subjectType": subject_type,
        "subjectId": subject_id,
        "fromStatus": from_status,
        "toStatus": to_status,
        "actor": actor,
        "timestamp": timestamp,
        "evidenceLinks": evidence_links,
        "applicableGates": gates,
        "previousRevisionHash": previous_hash,
    }
    if blocker is not None:
        revision["blocker"] = blocker
    if resolution is not None:
        revision["resolution"] = resolution
    revision["revisionHash"] = revision_hash(revision)
    return revision


def validate_new_binding_edge_case(
    record: dict[str, Any],
    canonical_records: dict[str, dict[str, str]],
    memberships: dict[str, str],
    package_phases: dict[str, str],
) -> None:
    rid = record.get("canonicalId", "?")
    canonical = canonical_records.get(rid)
    if canonical is None:
        raise GovernanceError("EDGE_CASE_CANONICAL_RECORD_MISSING", rid)
    package_id = record.get("packageId")
    if package_id not in package_phases:
        raise GovernanceError("EDGE_CASE_PACKAGE_MISSING", rid)
    if memberships.get(rid) != package_id:
        raise GovernanceError("EDGE_CASE_MEMBERSHIP_MISMATCH", rid)
    if record.get("phase") != package_phases[package_id]:
        raise GovernanceError("EDGE_CASE_PHASE_MISMATCH", rid)
    if not _nonempty(record.get("sourceEvidence")):
        raise GovernanceError("EDGE_CASE_SOURCE_MISSING", rid)
    if record.get("canonicalStatementHash") != semantic_hash(canonical.get("statement", "")):
        raise GovernanceError("EDGE_CASE_CANONICAL_CONTENT_MISMATCH", rid)
    if record.get("reviewStatus") != "REVIEWED_CONFIRMED":
        raise GovernanceError("EDGE_CASE_REVIEW_MISSING", rid)
    if record.get("atomic") is not True:
        raise GovernanceError("COMPOUND_REQUIREMENT_NOT_SPLIT", rid)
    if not _nonempty(record.get("verification")):
        raise GovernanceError("EDGE_CASE_VERIFICATION_MISSING", rid)


def validate_planning_passes(report: dict[str, Any]) -> None:
    required = ("pass1", "pass2", "pass3", "doubleCheck", "validator")
    for name in required:
        item = report.get(name, {})
        if item.get("status") != "PASS":
            raise GovernanceError("PLANNING_PASS_INCOMPLETE", name)
        if item.get("missing", 0) != 0:
            raise GovernanceError("PLANNING_PASS_GAP", name, str(item.get("missing")))
        if not _nonempty(item.get("evidenceLinks")):
            raise GovernanceError("PLANNING_PASS_EVIDENCE_MISSING", name)


def validate_bottom_up(
    records: Iterable[dict[str, Any]],
    canonical_ids: set[str] | None = None,
    package_ids: set[str] | None = None,
    valid_codebase_paths: set[str] | None = None,
) -> None:
    required = (
        "canonicalId", "currentPathOrEvidence", "codebasePaths", "codebaseEvidence",
        "symbolOrRecord", "retainedBehavior", "classification", "targetOwner",
        "verification", "packageTestObligation", "runnableVerification", "evidenceLinks",
    )
    count = 0
    for record in records:
        count += 1
        rid = record.get("canonicalId", "?")
        for key in required:
            if key not in record or (key not in {"codebasePaths", "codebaseEvidence"} and not _nonempty(record.get(key))):
                raise GovernanceError("BOTTOM_UP_FIELD_MISSING", rid, key)
        if canonical_ids is not None and rid not in canonical_ids:
            raise GovernanceError("BOTTOM_UP_CANONICAL_ID_MISSING", rid)
        if package_ids is not None and record.get("targetOwner") not in package_ids:
            raise GovernanceError("BOTTOM_UP_OWNER_MISSING", rid)
        if valid_codebase_paths is not None:
            evidence = str(record.get("currentPathOrEvidence", ""))
            declared = record.get("codebasePaths")
            if not isinstance(declared, list) or not all(isinstance(path, str) for path in declared):
                raise GovernanceError("BOTTOM_UP_PATH_LIST_INVALID", rid)
            details = record.get("codebaseEvidence")
            if not isinstance(details, list):
                raise GovernanceError("BOTTOM_UP_EVIDENCE_LIST_INVALID", rid)
            if record.get("classification") == "TARGET_ONLY":
                if declared or details or evidence != "NOT_APPLICABLE":
                    raise GovernanceError("BOTTOM_UP_TARGET_ONLY_INVALID", rid)
            else:
                if record.get("classification") != "KEPT" or not declared or set(declared) - valid_codebase_paths:
                    raise GovernanceError("BOTTOM_UP_PATH_MISSING", rid)
                if evidence != "; ".join(sorted(set(declared))):
                    raise GovernanceError("BOTTOM_UP_PATH_TEXT_INVALID", rid)
                detail_paths = []
                symbols = []
                for item in details:
                    if not isinstance(item, dict) or any(
                        not isinstance(item.get(field), str) or not item[field].strip()
                        for field in ("path", "locator", "symbol")
                    ):
                        raise GovernanceError("BOTTOM_UP_EVIDENCE_ITEM_INVALID", rid)
                    if not re.fullmatch(r"L\d+-L\d+", item["locator"]):
                        raise GovernanceError("BOTTOM_UP_LOCATOR_INVALID", rid)
                    detail_paths.append(item["path"])
                    symbols.append(f"{item['path']}:{item['locator']} ({item['symbol']})")
                if set(detail_paths) != set(declared) or record.get("symbolOrRecord") != symbols:
                    raise GovernanceError("BOTTOM_UP_SYMBOL_INVALID", rid)
    if count == 0:
        raise GovernanceError("BOTTOM_UP_EMPTY", "bottom-up")


def validate_risk_links(
    records: Iterable[dict[str, Any]],
    package_ids: set[str],
    canonical_ids: set[str] | None = None,
    repository_root: Path | None = None,
) -> None:
    """Validate ownership mappings; this never claims a downstream product test ran."""
    records = list(records)
    expected = {f"R-{index:02d}" for index in range(1, 33)}
    risk_ids = [str(record.get("riskId", "")) for record in records]
    if set(risk_ids) != expected or len(risk_ids) != len(set(risk_ids)):
        raise GovernanceError("RISK_COVERAGE_INVALID", "risks")
    runtime_ids: list[str] = []
    canonical_records: dict[str, dict[str, str]] = {}
    memberships: dict[str, str] = {}
    package_phases: dict[str, str] = {}
    adjacency: dict[str, set[str]] = {}
    if repository_root is not None:
        source = repository_root / "graphify/semantic-plan-source"
        with (source / "requirements/requirements.csv").open(encoding="utf-8-sig", newline="") as stream:
            canonical_records = {row["canonical_id"]: row for row in csv.DictReader(stream)}
        with (source / "packages/requirement-membership.csv").open(encoding="utf-8-sig", newline="") as stream:
            memberships = {row["canonical_id"]: row["work_package_id"] for row in csv.DictReader(stream)}
        packages = json.loads((source / "packages/work-packages.json").read_text(encoding="utf-8"))["workPackages"]
        package_phases = {row["work_package_id"]: row["implementation_phase"] for row in packages}
        with (source / "packages/dependencies.csv").open(encoding="utf-8-sig", newline="") as stream:
            for edge in csv.DictReader(stream):
                adjacency.setdefault(edge["prerequisite_work_package_id"], set()).add(edge["work_package_id"])

    def reaches(start: str, target: str) -> bool:
        pending, seen = [start], {start}
        while pending:
            node = pending.pop()
            if node == target:
                return True
            for successor in adjacency.get(node, set()):
                if successor not in seen:
                    seen.add(successor)
                    pending.append(successor)
        return False

    for record in records:
        rid = record["riskId"]
        runtime_id = str(record.get("runtimeRequirementId", ""))
        runtime_ids.append(runtime_id)
        if record.get("severity") not in {"P0", "P1"}:
            raise GovernanceError("RISK_SEVERITY_INVALID", rid)
        if canonical_ids is not None and runtime_id not in canonical_ids:
            raise GovernanceError("RISK_REQUIREMENT_MISSING", rid, runtime_id)
        expected_runtime_id = f"CAN-LAM-RISK-TEST-{int(rid.split('-')[1]):03d}"
        if runtime_id != expected_runtime_id:
            raise GovernanceError("RISK_REQUIREMENT_BINDING_INVALID", rid, runtime_id)
        mitigation = record.get("mitigationOwnerPackages")
        test_owner = record.get("testOwnerPackage")
        required_after = record.get("requiredAfterPackages")
        if not isinstance(mitigation, list) or not mitigation or any(owner not in package_ids for owner in mitigation):
            raise GovernanceError("RISK_MITIGATION_OWNER_INVALID", rid)
        if test_owner not in package_ids:
            raise GovernanceError("RISK_TEST_OWNER_INVALID", rid, str(test_owner))
        expected_after = sorted(owner for owner in mitigation if owner != test_owner)
        if not isinstance(required_after, list) or sorted(required_after) != expected_after:
            raise GovernanceError("RISK_PREREQUISITE_INVALID", rid)
        if repository_root is not None and any(not reaches(owner, test_owner) for owner in mitigation):
            raise GovernanceError("RISK_TEST_OWNER_UPSTREAM", rid, str(test_owner))
        if repository_root is None and record.get("prerequisitesSatisfied") is not True:
            raise GovernanceError("RISK_TEST_OWNER_UPSTREAM", rid, str(test_owner))
        if canonical_records:
            canonical = canonical_records.get(runtime_id, {})
            if (
                canonical.get("parent_requirement_id") != "CAN-LAM-TEST-020"
                or canonical.get("requirement_type") != "VERIFICATION_GATE"
                or canonical.get("original_requirement_ids") != rid
                or canonical.get("risk_links") != rid
                or canonical.get("source_locator") != rid
                or canonical.get("priority") != record.get("severity")
                or memberships.get(runtime_id) != test_owner
                or canonical.get("primary_implementation_phase") != package_phases.get(test_owner)
            ):
                raise GovernanceError("RISK_REQUIREMENT_BINDING_INVALID", rid, runtime_id)
        if record.get("blockingPackageGate") != f"{test_owner}:EXIT":
            raise GovernanceError("RISK_PACKAGE_GATE_INVALID", rid)
        if record.get("blockingReleaseGate") != "I15:RELEASE":
            raise GovernanceError("RISK_RELEASE_GATE_INVALID", rid)
        if not _nonempty(record.get("requiredTest")) or not _nonempty(record.get("testTarget")):
            raise GovernanceError("RISK_TEST_MISSING", rid)
        if record.get("governanceCheck") != f"python graphify/13-implementation/WP-I0-011/risk_governance_test.py --risk {rid}":
            raise GovernanceError("RISK_GOVERNANCE_CHECK_INVALID", rid)
        if record.get("governanceCheckType") != "MAPPING_ENFORCEMENT_NOT_PRODUCT_TEST":
            raise GovernanceError("RISK_GOVERNANCE_CHECK_MISCLASSIFIED", rid)
        if record.get("testClass") not in {"BASELINE_REAL_EXECUTION", "GOVERNANCE_MITIGATION_BOUNDARY", "PRODUCT_FAILURE_BOUNDARY"}:
            raise GovernanceError("RISK_TEST_CLASS_INVALID", rid)
        if test_owner == "WP-I0-011" and record.get("testClass") != "GOVERNANCE_MITIGATION_BOUNDARY":
            raise GovernanceError("RISK_PRODUCT_TEST_FALSELY_OWNED_BY_GOVERNANCE", rid)
        status = record.get("verificationStatus")
        evidence = record.get("runtimeEvidence")
        commit = record.get("implementationCommit")
        if status == "PENDING":
            if evidence or commit:
                raise GovernanceError("RISK_PENDING_HAS_EVIDENCE", rid)
        elif status == "VERIFIED":
            if not isinstance(evidence, list) or not evidence or not re.fullmatch(r"[0-9a-f]{40}", str(commit)):
                raise GovernanceError("RISK_VERIFIED_EVIDENCE_INVALID", rid)
            if repository_root is not None:
                if subprocess.run(
                    ["git", "merge-base", "--is-ancestor", str(commit), "origin/main"], cwd=repository_root,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                ).returncode != 0:
                    raise GovernanceError("RISK_VERIFIED_COMMIT_NOT_ON_ORIGIN", rid)
                subject = subprocess.run(
                    ["git", "show", "-s", "--format=%s", str(commit)], cwd=repository_root,
                    capture_output=True, text=True, encoding="utf-8", errors="replace",
                ).stdout.strip()
                if not subject.startswith(f"Complete {test_owner}"):
                    raise GovernanceError("RISK_VERIFIED_WRONG_COMMIT", rid)
                for link in evidence:
                    normalized = str(link).replace("\\", "/")
                    committed = subprocess.run(
                        ["git", "show", f"{commit}:{normalized}"], cwd=repository_root,
                        capture_output=True, text=True, encoding="utf-8", errors="replace",
                    )
                    if committed.returncode != 0 or test_owner not in committed.stdout:
                        raise GovernanceError("RISK_VERIFIED_EVIDENCE_NOT_COMMITTED", rid, normalized)
        else:
            raise GovernanceError("RISK_STATUS_INVALID", rid, str(status))
    if len(runtime_ids) != len(set(runtime_ids)):
        raise GovernanceError("RISK_TEST_REQUIREMENT_DUPLICATE", "risks")


def validate_runtime_risk_gates(
    ownership: Iterable[dict[str, Any]],
    package_statuses: dict[str, str],
    runtime_evidence: Iterable[dict[str, Any]],
    release_status: str,
    repository_root: Path | None = None,
) -> None:
    """Block package/release completion until each applicable real boundary test passes."""
    records = list(ownership)
    evidence_rows = list(runtime_evidence)
    by_risk: dict[str, dict[str, Any]] = {}
    for evidence in evidence_rows:
        rid = str(evidence.get("riskId", ""))
        if rid in by_risk:
            raise GovernanceError("RISK_RUNTIME_EVIDENCE_DUPLICATE", rid)
        by_risk[rid] = evidence
    expected_risks = {record["riskId"] for record in records}
    if release_status == "PASS" and set(by_risk) != expected_risks:
        raise GovernanceError("RISK_RELEASE_UNRESOLVED", "I15:RELEASE")
    for record in records:
        rid = record["riskId"]
        owner = record["testOwnerPackage"]
        evidence = by_risk.get(rid)
        gate_reached = package_statuses.get(owner) == "COMPLETE" or release_status == "PASS"
        if not gate_reached:
            continue
        if evidence is None:
            raise GovernanceError("RISK_RUNTIME_EVIDENCE_MISSING", rid)
        if evidence.get("riskId") != rid or evidence.get("runtimeRequirementId") != record["runtimeRequirementId"]:
            raise GovernanceError("RISK_RUNTIME_WRONG_RISK", rid)
        if evidence.get("testOwnerPackage") != owner:
            raise GovernanceError("RISK_RUNTIME_WRONG_PACKAGE", rid)
        if evidence.get("status") != "PASS":
            raise GovernanceError("RISK_RUNTIME_TEST_NOT_PASS", rid)
        if evidence.get("synthetic") is not False:
            raise GovernanceError("RISK_RUNTIME_SYNTHETIC_EVIDENCE", rid)
        expected_kind = (
            "GOVERNANCE_MITIGATION_TEST"
            if record.get("testClass") == "GOVERNANCE_MITIGATION_BOUNDARY"
            else "REAL_PRODUCT_RISK_TEST"
        )
        if evidence.get("evidenceKind") != expected_kind:
            raise GovernanceError("RISK_RUNTIME_EVIDENCE_KIND", rid)
        commit = str(evidence.get("implementationCommit", ""))
        if not re.fullmatch(r"[0-9a-f]{40}", commit):
            raise GovernanceError("RISK_RUNTIME_COMMIT_INVALID", rid)
        links = evidence.get("evidenceLinks")
        if not isinstance(links, list) or not links:
            raise GovernanceError("RISK_RUNTIME_EVIDENCE_LINKS_MISSING", rid)
        if repository_root is not None:
            if subprocess.run(
                ["git", "merge-base", "--is-ancestor", commit, "origin/main"], cwd=repository_root,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            ).returncode != 0:
                raise GovernanceError("RISK_RUNTIME_COMMIT_NOT_ON_ORIGIN", rid)
            subject = subprocess.run(
                ["git", "show", "-s", "--format=%s", commit], cwd=repository_root,
                capture_output=True, text=True, encoding="utf-8", errors="replace",
            ).stdout.strip()
            if not subject.startswith(f"Complete {owner}"):
                raise GovernanceError("RISK_RUNTIME_WRONG_COMMIT", rid)
            committed_payloads: dict[str, bytes] = {}
            for link in links:
                normalized = str(link).replace("\\", "/")
                committed = subprocess.run(
                    ["git", "show", f"{commit}:{normalized}"], cwd=repository_root,
                    capture_output=True,
                )
                if committed.returncode != 0 or owner.encode() not in committed.stdout:
                    raise GovernanceError("RISK_RUNTIME_EVIDENCE_NOT_COMMITTED", rid, normalized)
                committed_payloads[normalized] = committed.stdout
            raw_path = str(evidence.get("rawEvidencePath", "")).replace("\\", "/")
            raw = committed_payloads.get(raw_path)
            if raw is None:
                raise GovernanceError("RISK_RUNTIME_RAW_EVIDENCE_MISSING", rid)
            if hashlib.sha256(raw).hexdigest() != evidence.get("rawEvidenceSha256"):
                raise GovernanceError("RISK_RUNTIME_RAW_EVIDENCE_HASH", rid)
            try:
                raw_json = json.loads(raw.decode("utf-8-sig"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise GovernanceError("RISK_RUNTIME_RAW_EVIDENCE_INVALID", rid) from exc
            validate_raw_risk_observation(record, raw_json)


def validate_raw_risk_observation(record: dict[str, Any], raw_json: dict[str, Any]) -> None:
    rid = record["riskId"]
    owner = record["testOwnerPackage"]
    test_class = record.get("testClass")
    if test_class == "BASELINE_REAL_EXECUTION":
        if (
            raw_json.get("packageId") != owner
            or raw_json.get("status") != "PASS"
            or raw_json.get("surfaceOracle", {}).get("result") != "PASS"
            or not isinstance(raw_json.get("attempts"), list)
            or not raw_json["attempts"]
            or raw_json.get("preservation", {}).get("protectedRepository", {}).get("result") != "PASS"
        ):
            raise GovernanceError("RISK_RUNTIME_RAW_EVIDENCE_INVALID", rid)
        return
    field = (
        "governanceMitigationEvidence"
        if test_class == "GOVERNANCE_MITIGATION_BOUNDARY"
        else "productRiskTestEvidence"
    )
    observations = raw_json.get(field, [])
    match = next((item for item in observations if item.get("riskId") == rid), None)
    if not match or (
        match.get("runtimeRequirementId") != record["runtimeRequirementId"]
        or match.get("testOwnerPackage") != owner
        or match.get("status") != "PASS"
        or match.get("synthetic") is not False
        or not match.get("commandOrInspection")
        or not match.get("observedOutput")
    ):
        raise GovernanceError("RISK_RUNTIME_RAW_EVIDENCE_INVALID", rid)


def validate_simplicity_review(package: dict[str, Any]) -> None:
    pid = str(package.get("work_package_id", "?"))
    if package.get("capacity_split") is not False or package.get("source_section_split") is not False:
        raise GovernanceError("SIMPLICITY_MECHANICAL_SPLIT", pid)
    if not _nonempty(package.get("bounded_surface")) or not _nonempty(package.get("cohesion_rationale")):
        raise GovernanceError("SIMPLICITY_BOUNDARY_MISSING", pid)
    if int(package.get("reviewed_item_count") or 0) > 20 and str(package.get("architectural_boundary_exception")) != "true":
        raise GovernanceError("SIMPLICITY_LARGE_PACKAGE_UNREVIEWED", pid)


def scan_changed_production_text(records: Iterable[tuple[str, str]]) -> None:
    for path, text in records:
        match = PLACEHOLDER_PATTERN.search(text)
        if match:
            raise GovernanceError("PRODUCTION_PLACEHOLDER", path, match.group(0))
        if re.search(r"\breturn\s+(?:None|null|true|\{\}|\[\])\s*;?\s*(?://.*)?$", text, re.MULTILINE):
            raise GovernanceError("EMPTY_SUCCESS_RETURN", path)
        if re.search(r"\bmock(?:Data|Dataset)\b", text, re.IGNORECASE):
            raise GovernanceError("PRODUCTION_MOCK_DATA", path)


def ensure_graphify_only(paths: Iterable[str], repository_root: Path) -> None:
    repository_root = repository_root.resolve()
    graphify_root = (repository_root / "graphify").resolve()
    for raw in paths:
        candidate = Path(raw)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise GovernanceError("WRITE_OUTSIDE_GRAPHIFY", raw)
        forbidden = {".git", "__pycache__", "node_modules", ".pnpm-store", ".cache", "cache", "dist", "build", "target"}
        if any(part.lower() in forbidden for part in candidate.parts):
            raise GovernanceError("FORBIDDEN_ARTIFACT_PATH", raw)
        resolved = (repository_root / candidate).resolve(strict=False)
        try:
            resolved.relative_to(graphify_root)
        except ValueError as exc:
            raise GovernanceError("WRITE_OUTSIDE_GRAPHIFY", raw) from exc
        normalized = candidate.as_posix().lstrip("./")
        if normalized.startswith("graphify/Master Plan/"):
            raise GovernanceError("MASTER_PLAN_EXPANSION", normalized)


def publish_files(
    destination: Path,
    payloads: dict[str, bytes],
    replace: Callable[[str, str], None] = os.replace,
) -> None:
    """Publish a set atomically enough to roll every file back on any replace failure."""
    destination.mkdir(parents=True, exist_ok=True)
    resolved_destination = destination.resolve()
    for name in payloads:
        candidate = Path(name)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise GovernanceError("PUBLICATION_PATH_ESCAPE", name)
        target = (resolved_destination / candidate).resolve(strict=False)
        try:
            target.relative_to(resolved_destination)
        except ValueError as exc:
            raise GovernanceError("PUBLICATION_PATH_ESCAPE", name) from exc
    before = {
        name: (destination / name).read_bytes() if (destination / name).exists() else None
        for name in payloads
    }
    staged: dict[str, Path] = {}
    with tempfile.TemporaryDirectory(prefix="lamha-wp-i0-011-") as temp_dir:
        temp = Path(temp_dir)
        for name, data in payloads.items():
            path = temp / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            staged[name] = path
        try:
            for name in sorted(payloads):
                target = destination / name
                target.parent.mkdir(parents=True, exist_ok=True)
                replace(str(staged[name]), str(target))
        except Exception:
            for name, data in before.items():
                target = destination / name
                if data is None:
                    target.unlink(missing_ok=True)
                else:
                    target.write_bytes(data)
            raise


BLOCKER_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://lamha.local/schemas/governance/blocker-record.schema.json",
    "title": "Lamha implementation blocker record",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "blockerId",
        "affectedRecord",
        "knownFacts",
        "exactUnknown",
        "safeChecksExhausted",
        "evidenceLinks",
        "independentWork",
    ],
    "properties": {
        "blockerId": {"type": "string", "minLength": 1},
        "affectedRecord": {"type": "string", "minLength": 1},
        "knownFacts": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}},
        "exactUnknown": {"type": "string", "minLength": 1},
        "safeChecksExhausted": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}},
        "evidenceLinks": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}},
        "independentWork": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}},
        "guessedPath": {"const": False},
        "guessedField": {"const": False},
        "guessedSchema": {"const": False},
    },
}
