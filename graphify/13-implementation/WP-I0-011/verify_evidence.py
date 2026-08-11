"""Independent, read-only verifier for WP-I0-011 evidence."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from governance import GovernanceError, validate_runtime_risk_gates


PACKAGE_ID = "WP-I0-011"
START_SHA = "ef1cdd4a5755e813a650aa6f0988d84b82e1085c"
EXPECTED_OWNED = {
    "CAN-FAIL-02", "CAN-FAIL-19", "CAN-FAIL-23", "CAN-FAIL-24",
    "CAN-FAIL-27", "CAN-FAIL-32", "CAN-LAM-ARCH-444", "CAN-LAM-GOV-052",
    "CAN-LAM-GOV-054", "CAN-LAM-GOV-165", "CAN-LAM-GOV-179",
    "CAN-LAM-GOV-180", "CAN-LAM-GOV-264", "CAN-LAM-GOV-265",
    "CAN-LAM-GOV-266", "CAN-LAM-GOV-270", "CAN-LAM-GOV-273",
    "CAN-LAM-RISK-TEST-030", "CAN-LAM-RISK-TEST-032",
    "CAN-LAM-TEST-020", "CAN-LAM-TEST-021", "CAN-MISSION-I0-011",
}
PACKAGE_GATES = {
    "focused_validation", "negative_validation", "regression_validation",
    "recovery_validation", "independent_review", "exit_gate", "github_verification",
}
REQUIREMENT_GATES = {
    "focused_validation", "preservation_validation", "package_exit_gate", "github_verification",
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
PACKAGE_FILES = {
    "governance.py", "collect_evidence.py", "verify_evidence.py", "risk_governance_test.py",
    "implementation-state.json", "planning-governance-report.json",
    "blocker-record.schema.json", "verification-report.json",
    "evidence-consistency.json", "provenance-report.json", "artifact-scan.json",
    "package-summary.json", "completion-evidence.md", "adversarial-review.md",
    "bottom-up-audit.json", "artifact-manifest.json",
}
CERTIFICATION_MIRRORS = {
    "graphify/12-semantic-implementation-plan/12-validators/adversarial-results.json",
    "graphify/12-semantic-implementation-plan/13-reports/final-100-percent-certification.json",
    "graphify/12-semantic-implementation-plan/13-reports/final-content-manifest.json",
    "graphify/12-semantic-implementation-plan/13-reports/final-determinism-proof.json",
    "graphify/12-semantic-implementation-plan/13-reports/final-release-envelope.json",
    "graphify/12-semantic-implementation-plan/14-handoff/gpt-review-sha-manifest.json",
    "graphify/12-semantic-implementation-plan/PLAN-MANIFEST.json",
    "graphify/semantic-plan-source/handoff-gpt/gpt-review-sha-manifest.json",
    "graphify/semantic-plan-source/reviews/final-100-percent-certification.json",
    "graphify/semantic-plan-source/reviews/final-content-manifest.json",
    "graphify/semantic-plan-source/reviews/final-determinism-proof.json",
    "graphify/semantic-plan-source/reviews/final-release-envelope.json",
}


class VerificationError(ValueError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        super().__init__(f"{code}" + (f":{detail}" if detail else ""))


def reject_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise VerificationError("JSON_DUPLICATE_KEY", key)
        result[key] = value
    return result


def reject_constant(value: str) -> None:
    raise VerificationError("JSON_NONFINITE", value)


def depth(value: Any, level: int = 0) -> int:
    if level > 80:
        raise VerificationError("JSON_TOO_DEEP")
    if isinstance(value, dict):
        return max((depth(item, level + 1) for item in value.values()), default=level)
    if isinstance(value, list):
        return max((depth(item, level + 1) for item in value), default=level)
    if isinstance(value, float) and not math.isfinite(value):
        raise VerificationError("JSON_NONFINITE")
    return level


def load_json(path: Path) -> Any:
    raw = path.read_bytes()
    if len(raw) > 32 * 1024 * 1024:
        raise VerificationError("JSON_TOO_LARGE", path.name)
    try:
        value = json.loads(
            raw.decode("utf-8"), object_pairs_hook=reject_pairs, parse_constant=reject_constant
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VerificationError("JSON_INVALID", path.name) from exc
    depth(value)
    return value


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def semantic_hash(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def revision_hash(revision: dict[str, Any]) -> str:
    return semantic_hash({key: value for key, value in revision.items() if key != "revisionHash"})


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True,
        encoding="utf-8", errors="strict",
    ).stdout.strip()


def changed_paths(root: Path) -> set[str]:
    paths = set(filter(None, git(root, "diff", "--name-only", f"{START_SHA}..HEAD").splitlines()))
    status = subprocess.run(
        ["git", "-c", "core.quotepath=false", "status", "--porcelain=v1", "-uall"],
        cwd=root, check=True, capture_output=True, text=True, encoding="utf-8",
    ).stdout
    for line in status.splitlines():
        value = line[3:]
        if " -> " in value:
            paths.update(value.split(" -> ", 1))
        elif value:
            paths.add(value)
    return {path.replace("\\", "/") for path in paths}


def evidence_status(value: dict[str, Any]) -> str | None:
    tests = value.get("tests")
    derived_tests = (
        "PASS" if isinstance(tests, dict) and tests
        and all(item == "PASS" for item in tests.values())
        and isinstance(value.get("failureCases"), dict) else None
    )
    return (
        value.get("status") or value.get("finalStatus") or value.get("overallStatus")
        or value.get("recompute", {}).get("status")
        or value.get("checks", {}).get("exitGate") or value.get("result") or derived_tests
    )


def normalized_review_lines(text: str) -> list[str]:
    normalized: list[str] = []
    for line in text.splitlines():
        clean = re.sub(r"^[\s#>*+-]+", "", line.strip())
        clean = clean.replace("**", "").replace("__", "").replace("`", "").strip().upper()
        clean = re.sub(r"^FINAL VERDICT\s*:\s*", "", clean)
        normalized.append(re.sub(r"\s+", " ", clean))
    return normalized


def exact_review_pass(text: str) -> bool:
    lines = normalized_review_lines(text)
    return "PACKAGE REVIEW PASS" in lines and not any(
        "PACKAGE REVIEW FAIL" in line
        or re.search(r"\b(?:FINAL|OVERALL) VERDICT\s*[:=-]?\s*FAIL\b", line)
        or ("PACKAGE REVIEW PASS" in line and line != "PACKAGE REVIEW PASS")
        for line in lines
    )


def historical_review_pass(text: str) -> bool:
    verdicts: list[str] = []
    for line in normalized_review_lines(text):
        if "PACKAGE REVIEW FAIL" in line:
            verdicts.append("FAIL")
        if line.startswith("PACKAGE REVIEW PASS") and not re.search(
            r"^[\s.—:(),-]*(?:BUT|NOT|FAIL|BLOCKING|UNRESOLVED|SUBJECT TO|PENDING|EXCEPT)\b",
            line[len("PACKAGE REVIEW PASS"):],
        ):
            verdicts.append("PASS")
    return bool(verdicts) and verdicts[-1] == "PASS"


def verify_evidence_links(root: Path, tracker: dict[str, Any], package_dir: Path) -> None:
    records = list(tracker.get("importedBaselines", [])) + list(tracker.get("revisions", []))
    for record in records:
        record_id = record.get("revisionId", record.get("subjectId", "?"))
        links = list(record.get("evidenceLinks", []))
        for gate in record.get("applicableGates", []):
            links.extend(gate.get("evidenceLinks", []))
            command = gate.get("commandOrInspection", "")
            if command.startswith("python "):
                target = command.split()[1].replace("\\", "/")
                if not (root / target).is_file():
                    raise VerificationError("GATE_COMMAND_TARGET_MISSING", f"{record_id}:{target}")
        for link in links:
            if link.startswith("git-origin:"):
                sha = link.split(":", 1)[1]
                if not re.fullmatch(r"[0-9a-f]{40}", sha):
                    raise VerificationError("GIT_EVIDENCE_INVALID", str(link))
                if subprocess.run(
                    ["git", "merge-base", "--is-ancestor", sha, "origin/main"],
                    cwd=root, capture_output=True,
                ).returncode != 0:
                    raise VerificationError("GIT_EVIDENCE_NOT_ON_ORIGIN", sha)
                continue
            normalized = str(link).replace("\\", "/")
            candidate = Path(normalized)
            if candidate.is_absolute() or ".." in candidate.parts:
                raise VerificationError("EVIDENCE_PATH_ESCAPE", normalized)
            if not (root / candidate).is_file():
                raise VerificationError("EVIDENCE_TARGET_MISSING", normalized)


def verify_prior_package(root: Path, package_id: str) -> None:
    base = root / "graphify/13-implementation" / package_id
    summary = load_json(base / "package-summary.json")
    verification_path = next(
        (path for path in (base / "verification-report.json", base / "verification-results.json") if path.exists()),
        None,
    )
    if verification_path is None:
        raise VerificationError("PRIOR_VERIFICATION_MISSING", package_id)
    verification = load_json(verification_path)
    if (
        evidence_status(summary) != "PASS" or evidence_status(verification) != "PASS"
        or summary.get("failures")
    ):
        raise VerificationError("PRIOR_EVIDENCE_NOT_PASS", package_id)
    review = (base / "adversarial-review.md").read_text(encoding="utf-8")
    if not historical_review_pass(review):
        raise VerificationError("PRIOR_REVIEW_NOT_PASS", package_id)


def baseline(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    rows = read_csv(root / "graphify/13-implementation/WP-I0-001/sha256-manifest.csv")
    for row in rows:
        path = row.get("path") or row.get("relative_path") or row.get("file")
        digest = row.get("sha256") or row.get("SHA256")
        if not path or not digest:
            raise VerificationError("BASELINE_INVALID")
        path = path.replace("\\", "/")
        if not path.startswith("Codebase/"):
            path = f"Codebase/{path}"
        result[path] = digest.lower()
    return result


def actual_codebase(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in sorted((root / "Codebase").rglob("*")) if path.is_file()
    }


def verify_tracker(
    tracker: dict[str, Any], canonical_ids: set[str], package_ids: set[str],
    required_current_keys: set[str] | None = None,
) -> None:
    if tracker.get("schemaVersion") != 2:
        raise VerificationError("TRACKER_SCHEMA_INVALID")
    baselines = tracker.get("importedBaselines")
    if not isinstance(baselines, list):
        raise VerificationError("BASELINES_INVALID")
    revisions = tracker.get("revisions")
    if not isinstance(revisions, list) or not revisions:
        raise VerificationError("TRACKER_EMPTY")
    seen: set[str] = set()
    previous: dict[tuple[str, str], str] = {}
    status: dict[tuple[str, str], str] = {}
    last_time: dict[tuple[str, str], datetime] = {}
    open_blocker: dict[tuple[str, str], str] = {}
    for baseline_item in baselines:
        kind = baseline_item.get("subjectType")
        subject = baseline_item.get("subjectId")
        key = (kind, subject)
        if kind not in {"PACKAGE", "REQUIREMENT"}:
            raise VerificationError("BASELINE_SUBJECT_TYPE_INVALID", str(key))
        registry = package_ids if kind == "PACKAGE" else canonical_ids
        if subject not in registry or baseline_item.get("status") != "COMPLETE" or key in status:
            raise VerificationError("BASELINE_INVALID", str(key))
        if not baseline_item.get("evidenceLinks") or not baseline_item.get("importedAt"):
            raise VerificationError("BASELINE_EVIDENCE_INVALID", str(key))
        try:
            imported_time = datetime.fromisoformat(baseline_item["importedAt"].replace("Z", "+00:00"))
            if imported_time.utcoffset() is None:
                raise ValueError("timezone offset required")
        except (AttributeError, ValueError) as exc:
            raise VerificationError("BASELINE_TIMESTAMP_INVALID", str(key)) from exc
        gates = baseline_item.get("applicableGates", [])
        expected = PACKAGE_GATES if kind == "PACKAGE" else REQUIREMENT_GATES
        if not expected <= {gate.get("gate") for gate in gates if gate.get("status") == "PASS"}:
            raise VerificationError("BASELINE_GATES_MISSING", str(key))
        for gate in gates:
            if not isinstance(gate, dict):
                raise VerificationError("BASELINE_GATE_TYPE_INVALID", str(key))
            for field in ("gate", "status", "method", "commandOrInspection", "observableOutput", "evidenceLinks"):
                if not gate.get(field):
                    raise VerificationError("BASELINE_GATE_FIELD_MISSING", f"{key}:{field}")
            if any(not isinstance(gate[field], str) for field in ("gate", "status", "method", "commandOrInspection", "observableOutput")):
                raise VerificationError("BASELINE_GATE_FIELD_TYPE", str(key))
            if not isinstance(gate.get("evidenceLinks"), list) or not all(isinstance(item, str) and item for item in gate["evidenceLinks"]):
                raise VerificationError("BASELINE_GATE_FIELD_TYPE", str(key))
            if type(gate.get("exitCode")) is not int or gate.get("exitCode") != 0 or not isinstance(gate.get("changedSymbols"), list):
                raise VerificationError("BASELINE_GATE_EXECUTION_INVALID", str(key))
            if not gate["changedSymbols"] and not gate.get("changedSymbolsNotApplicableReason"):
                raise VerificationError("BASELINE_GATE_CHANGED_SYMBOLS_UNEXPLAINED", str(key))
        status[key] = "COMPLETE"
    for revision in revisions:
        rid = revision.get("revisionId")
        if not rid or rid in seen:
            raise VerificationError("REVISION_ID_INVALID", str(rid))
        seen.add(rid)
        kind = revision.get("subjectType")
        subject = revision.get("subjectId")
        if kind == "PACKAGE":
            if subject not in package_ids:
                raise VerificationError("PACKAGE_ID_UNKNOWN", str(subject))
        elif kind == "REQUIREMENT":
            if subject not in canonical_ids:
                raise VerificationError("CANONICAL_ID_UNKNOWN", str(subject))
        else:
            raise VerificationError("SUBJECT_TYPE_INVALID", str(kind))
        if "statement" in revision:
            raise VerificationError("EMBEDDED_STATEMENT", rid)
        if not revision.get("evidenceLinks"):
            raise VerificationError("REVISION_EVIDENCE_MISSING", rid)
        key = (kind, subject)
        if revision.get("previousRevisionHash") != previous.get(key, "GENESIS"):
            raise VerificationError("PREDECESSOR_INVALID", rid)
        if key in status and revision.get("fromStatus") != status[key]:
            raise VerificationError("STATUS_CHAIN_INVALID", rid)
        source = revision.get("fromStatus")
        target = revision.get("toStatus")
        if source == target or target not in ALLOWED_TRANSITIONS.get(source, set()):
            raise VerificationError("TRANSITION_INVALID", rid)
        try:
            parsed = datetime.fromisoformat(revision.get("timestamp", "").replace("Z", "+00:00"))
            if parsed.utcoffset() is None:
                raise ValueError("timezone offset required")
        except ValueError as exc:
            raise VerificationError("TIMESTAMP_INVALID", rid) from exc
        if key in last_time and parsed < last_time[key]:
            raise VerificationError("TIMESTAMP_ORDER_INVALID", rid)
        if revision_hash(revision) != revision.get("revisionHash"):
            raise VerificationError("REVISION_HASH_INVALID", rid)
        gates = revision.get("applicableGates")
        if not isinstance(gates, list):
            raise VerificationError("GATES_INVALID", rid)
        for gate in gates:
            if not isinstance(gate, dict):
                raise VerificationError("GATE_TYPE_INVALID", rid)
            for field in ("gate", "status", "method", "commandOrInspection", "observableOutput", "evidenceLinks"):
                if not gate.get(field):
                    raise VerificationError("GATE_FIELD_MISSING", f"{rid}:{field}")
            if any(not isinstance(gate[field], str) for field in ("gate", "status", "method", "commandOrInspection", "observableOutput")):
                raise VerificationError("GATE_FIELD_TYPE", rid)
            if not isinstance(gate.get("evidenceLinks"), list) or not all(isinstance(item, str) and item for item in gate["evidenceLinks"]):
                raise VerificationError("GATE_FIELD_TYPE", rid)
            if type(gate.get("exitCode")) is not int or gate.get("exitCode") != 0 or not isinstance(gate.get("changedSymbols"), list):
                raise VerificationError("GATE_EXECUTION_INVALID", rid)
            if not all(isinstance(item, str) and item for item in gate["changedSymbols"]):
                raise VerificationError("GATE_EXECUTION_INVALID", rid)
            if not gate["changedSymbols"] and not gate.get("changedSymbolsNotApplicableReason"):
                raise VerificationError("GATE_CHANGED_SYMBOLS_UNEXPLAINED", rid)
            if gate["status"] not in {"PASS", "NOT_APPLICABLE"}:
                raise VerificationError("GATE_STATUS_INVALID", rid)
            if gate["status"] == "NOT_APPLICABLE" and not gate.get("rationale"):
                raise VerificationError("GATE_NA_UNEXPLAINED", rid)
        if revision.get("toStatus") == "COMPLETE":
            expected = PACKAGE_GATES if kind == "PACKAGE" else REQUIREMENT_GATES
            found = {gate["gate"] for gate in gates if gate["status"] == "PASS"}
            if not expected <= found:
                raise VerificationError("COMPLETE_GATES_MISSING", rid)
        if revision.get("toStatus") == "BLOCKED":
            blocker = revision.get("blocker", {})
            required = {
                "blockerId", "affectedRecord", "knownFacts", "exactUnknown",
                "safeChecksExhausted", "evidenceLinks", "independentWork",
            }
            if any(not blocker.get(field) for field in required):
                raise VerificationError("BLOCKER_INVALID", rid)
            if any(blocker.get(field) for field in ("guessedPath", "guessedField", "guessedSchema")):
                raise VerificationError("BLOCKER_GUESS", rid)
            for field in ("knownFacts", "safeChecksExhausted", "evidenceLinks", "independentWork"):
                if not isinstance(blocker.get(field), list) or not all(isinstance(item, str) and item for item in blocker[field]):
                    raise VerificationError("BLOCKER_TYPE_INVALID", rid)
            if blocker.get("affectedRecord") != subject:
                raise VerificationError("BLOCKER_AFFECTED_RECORD_MISMATCH", rid)
        if revision.get("fromStatus") == "BLOCKED" and revision.get("toStatus") in {"READY", "IN_PROGRESS"}:
            resolution = revision.get("resolution", {})
            if any(not resolution.get(field) for field in ("resolvedBlockerId", "reason", "evidenceLinks")):
                raise VerificationError("BLOCKER_RESOLUTION_MISSING", rid)
            if resolution.get("resolvedBlockerId") != open_blocker.get(key):
                raise VerificationError("BLOCKER_RESOLUTION_ID_MISMATCH", rid)
        previous[key] = revision["revisionHash"]
        status[key] = revision["toStatus"]
        last_time[key] = parsed
        if revision.get("toStatus") == "BLOCKED":
            open_blocker[key] = revision["blocker"]["blockerId"]
        if revision.get("fromStatus") == "BLOCKED":
            open_blocker.pop(key, None)
    expected_current = {f"{kind}:{subject}": value for (kind, subject), value in status.items()}
    if tracker.get("current") != expected_current:
        raise VerificationError("CURRENT_STATE_INVALID")
    missing = sorted((required_current_keys or set()) - set(expected_current))
    if missing:
        raise VerificationError("TRACKER_OWNED_COVERAGE_MISSING", ",".join(missing))
    completed = {subject for (kind, subject), value in status.items() if kind == "PACKAGE" and value == "COMPLETE"}
    if set(tracker.get("completedPackages", [])) != completed:
        raise VerificationError("TRACKER_COMPLETED_PACKAGES_MISMATCH")
    ready = tracker.get("readyPackages")
    if not isinstance(ready, list) or any(item not in package_ids for item in ready):
        raise VerificationError("TRACKER_READY_PACKAGES_INVALID")
    if tracker.get("selectedPackage") is not None and tracker["selectedPackage"] not in ready:
        raise VerificationError("TRACKER_SELECTED_PACKAGE_INVALID")
    if tracker.get("explicitAuthorizedPackage") is not None and tracker["explicitAuthorizedPackage"] not in ready:
        raise VerificationError("TRACKER_AUTHORIZATION_INVALID")


def expect_failure(code: str, function: Any) -> dict[str, str]:
    try:
        function()
    except VerificationError as exc:
        if exc.code == code:
            return {"expected": code, "observed": exc.code, "status": "PASS"}
        raise
    raise VerificationError("INDEPENDENT_FIXTURE_UNEXPECTED_PASS", code)


def main() -> int:
    package_dir = Path(__file__).resolve().parent
    root = package_dir.parents[2]
    names = {
        "tracker": "implementation-state.json",
        "planning": "planning-governance-report.json",
        "verification": "verification-report.json",
        "consistency": "evidence-consistency.json",
        "provenance": "provenance-report.json",
        "summary": "package-summary.json",
        "scan": "artifact-scan.json",
        "blocker": "blocker-record.schema.json",
        "bottomup": "bottom-up-audit.json",
        "manifest": "artifact-manifest.json",
    }
    artifacts = {key: load_json(package_dir / name) for key, name in names.items()}
    generation_ids = {
        value.get("generationId") for key, value in artifacts.items()
        if key != "blocker"
    }
    if len(generation_ids) != 1 or None in generation_ids:
        raise VerificationError("GENERATION_ID_MISMATCH")
    generation = next(iter(generation_ids))
    if any(artifacts[key].get("status") != "PASS" for key in ("planning", "verification", "consistency", "summary", "scan", "bottomup", "manifest")):
        raise VerificationError("ARTIFACT_STATUS_NOT_PASS")
    if artifacts["provenance"].get("startingSha") != START_SHA:
        raise VerificationError("START_SHA_MISMATCH")

    head = git(root, "rev-parse", "HEAD")
    origin = git(root, "rev-parse", "origin/main")
    provenance = artifacts["provenance"]
    if provenance.get("headSha") != head or provenance.get("originMainSha") != origin:
        raise VerificationError("PROVENANCE_SHA_STALE")
    if provenance.get("headEqualsOriginMain") != (head == origin):
        raise VerificationError("PROVENANCE_EQUALITY_INVALID")
    if provenance.get("branch") != git(root, "branch", "--show-current") or provenance.get("branch") != "main":
        raise VerificationError("PROVENANCE_BRANCH_INVALID")
    if provenance.get("remote") != git(root, "remote", "get-url", "origin"):
        raise VerificationError("PROVENANCE_REMOTE_INVALID")

    requirements = read_csv(root / "graphify/semantic-plan-source/requirements/requirements.csv")
    canonical_ids = {row["canonical_id"] for row in requirements}
    canonical_by_id = {row["canonical_id"]: row for row in requirements}
    actionable_by_id = {
        row["Canonical ID"]: row for row in read_csv(
            root / "graphify/semantic-plan-source/reviews/reviewed-actionable-requirements-v3.csv"
        )
    }
    packages = load_json(root / "graphify/semantic-plan-source/packages/work-packages.json")["workPackages"]
    package_ids = {row["work_package_id"] for row in packages}
    package_by_id = {row["work_package_id"]: row for row in packages}
    membership = read_csv(root / "graphify/semantic-plan-source/packages/requirement-membership.csv")
    if {row["canonical_id"] for row in membership if row["work_package_id"] == PACKAGE_ID} != EXPECTED_OWNED:
        raise VerificationError("OWNED_REQUIREMENTS_MISMATCH")
    if set(artifacts["summary"].get("requirementIds", [])) != EXPECTED_OWNED:
        raise VerificationError("SUMMARY_REQUIREMENTS_MISMATCH")
    required_current = {f"REQUIREMENT:{rid}" for rid in EXPECTED_OWNED} | {f"PACKAGE:{PACKAGE_ID}"}
    verify_tracker(artifacts["tracker"], canonical_ids, package_ids, required_current)
    completed_requirement_count = sum(
        key.startswith("REQUIREMENT:") and value == "COMPLETE"
        for key, value in artifacts["tracker"]["current"].items()
    )
    expected_completed_requirements = 35 if artifacts["tracker"]["current"][f"PACKAGE:{PACKAGE_ID}"] == "COMPLETE" else 13
    if completed_requirement_count != expected_completed_requirements:
        raise VerificationError("TRACKER_COMPLETED_REQUIREMENT_COUNT_INVALID", str(completed_requirement_count))
    current_review = (package_dir / "adversarial-review.md").read_text(encoding="utf-8")
    if not exact_review_pass(current_review):
        raise VerificationError("CURRENT_REVIEW_NOT_PASS", PACKAGE_ID)
    for imported in artifacts["tracker"].get("importedBaselines", []):
        source_commit = imported.get("sourceCommit", "")
        if not re.fullmatch(r"[0-9a-f]{40}", source_commit):
            raise VerificationError("BASELINE_SOURCE_COMMIT_INVALID", imported.get("subjectId", "?"))
        if imported.get("subjectType") == "PACKAGE":
            changed = set(git(root, "show", "--format=", "--name-only", source_commit).splitlines())
            prefix = f"graphify/13-implementation/{imported['subjectId']}/"
            if not any(path.startswith(prefix) for path in changed):
                raise VerificationError("BASELINE_SOURCE_COMMIT_UNRELATED", imported["subjectId"])
        if imported.get("subjectType") == "REQUIREMENT":
            rid = imported["subjectId"]
            if imported.get("canonicalVerification") != canonical_by_id[rid]["verification_method"]:
                raise VerificationError("BASELINE_CANONICAL_VERIFICATION_INVALID", rid)
    verify_evidence_links(root, artifacts["tracker"], package_dir)
    for prior_package in artifacts["tracker"].get("completedPackages", []):
        if prior_package != PACKAGE_ID:
            verify_prior_package(root, prior_package)

    planning_passes = artifacts["planning"].get("planningPasses", {})
    for name in ("pass1", "pass2", "pass3", "doubleCheck", "validator"):
        if planning_passes.get(name, {}).get("status") != "PASS" or planning_passes[name].get("missing") != 0 or not planning_passes[name].get("evidenceLinks"):
            raise VerificationError("PLANNING_PASS_NOT_COMPLETE", name)
        for link in planning_passes[name]["evidenceLinks"]:
            if not (root / link).is_file():
                raise VerificationError("PLANNING_EVIDENCE_MISSING", link)
    coverage = planning_passes.get("canonicalIdCoverage", {})
    if coverage.get("actionable") != 756 or coverage.get("memberships") != 756 or coverage.get("unique") != 756:
        raise VerificationError("ACTIONABLE_COVERAGE_INVALID")
    if artifacts["planning"].get("bottomUpAudit") != {"records": 756, "missing": 0}:
        raise VerificationError("BOTTOM_UP_COVERAGE_INVALID")
    bottom_records = artifacts["bottomup"].get("records", [])
    membership_map = {row["canonical_id"]: row["work_package_id"] for row in membership}
    if len(bottom_records) != 756 or {row.get("canonicalId") for row in bottom_records} != set(membership_map):
        raise VerificationError("BOTTOM_UP_SET_INVALID")
    codebase_paths = set(baseline(root))
    reference_pattern = re.compile(r"(Codebase/[^;\r\n]+?):(L\d+-L\d+)\s+\(([^)]*)\)")
    for row in bottom_records:
        rid = row["canonicalId"]
        if row.get("targetOwner") != membership_map[rid]:
            raise VerificationError("BOTTOM_UP_OWNER_INVALID", rid)
        references = [
            {"path": path, "locator": locator, "symbol": symbol}
            for path, locator, symbol in reference_pattern.findall(
                canonical_by_id[rid].get("code_evidence_references", "")
            )
        ]
        exact_paths = sorted({item["path"] for item in references})
        if any(path not in codebase_paths for path in exact_paths):
            raise VerificationError("BOTTOM_UP_PATH_INVALID", rid)
        expected_class = "KEPT" if references else "TARGET_ONLY"
        expected_current = "; ".join(exact_paths) if references else "NOT_APPLICABLE"
        expected_symbols = [
            f"{item['path']}:{item['locator']} ({item['symbol']})" for item in references
        ] or [f"canonical:{rid}@{canonical_by_id[rid]['source_locator']}"]
        if (
            row.get("classification") != expected_class
            or row.get("currentPathOrEvidence") != expected_current
            or row.get("codebasePaths") != exact_paths
            or row.get("codebaseEvidence") != references
            or row.get("symbolOrRecord") != expected_symbols
            or row.get("retainedBehavior") != actionable_by_id[rid]["Required behaviour"]
        ):
            raise VerificationError("BOTTOM_UP_PATH_INVALID", rid)
        if (
            not row.get("symbolOrRecord") or not row.get("packageTestObligation")
            or row.get("verification") != canonical_by_id[rid]["verification_method"]
        ):
            raise VerificationError("BOTTOM_UP_PROOF_INVALID", rid)
        if row.get("runnableVerification") != "python graphify/12-semantic-implementation-plan/12-validators/validate_plan.py":
            raise VerificationError("BOTTOM_UP_RUNNABLE_INVALID", rid)
        for link in row.get("evidenceLinks", []):
            path = link.split("#", 1)[0]
            if not (root / path).is_file():
                raise VerificationError("BOTTOM_UP_EVIDENCE_MISSING", rid)
    risk_links = artifacts["planning"].get("riskGateLinks", [])
    if len(risk_links) != 32 or {row.get("riskId") for row in risk_links} != {f"R-{index:02d}" for index in range(1, 33)}:
        raise VerificationError("RISK_COUNT_INVALID")
    runtime_ids = []
    for risk in risk_links:
        rid = risk.get("riskId", "?")
        runtime_ids.append(risk.get("runtimeRequirementId"))
        owner = risk.get("testOwnerPackage")
        if risk.get("severity") not in {"P0", "P1"} or owner not in package_ids:
            raise VerificationError("RISK_OWNER_INVALID", rid)
        if risk.get("runtimeRequirementId") not in canonical_ids:
            raise VerificationError("RISK_REQUIREMENT_INVALID", rid)
        expected_runtime_id = f"CAN-LAM-RISK-TEST-{int(rid.split('-')[1]):03d}"
        canonical = canonical_by_id.get(risk.get("runtimeRequirementId"), {})
        if (
            risk.get("runtimeRequirementId") != expected_runtime_id
            or canonical.get("parent_requirement_id") != "CAN-LAM-TEST-020"
            or canonical.get("requirement_type") != "VERIFICATION_GATE"
            or canonical.get("original_requirement_ids") != rid
            or canonical.get("risk_links") != rid
            or membership_map.get(expected_runtime_id) != owner
            or canonical.get("primary_implementation_phase") != package_by_id[owner]["implementation_phase"]
        ):
            raise VerificationError("RISK_REQUIREMENT_BINDING_INVALID", rid)
        if risk.get("blockingPackageGate") != f"{owner}:EXIT" or risk.get("blockingReleaseGate") != "I15:RELEASE":
            raise VerificationError("RISK_GATE_LINK_INVALID", rid)
        if risk.get("prerequisitesSatisfied") is not True or not risk.get("requiredTest"):
            raise VerificationError("RISK_PREREQUISITE_OR_TEST_INVALID", rid)
        if risk.get("governanceCheckType") != "MAPPING_ENFORCEMENT_NOT_PRODUCT_TEST":
            raise VerificationError("RISK_GOVERNANCE_PRODUCT_CONFUSION", rid)
        if owner == PACKAGE_ID and risk.get("testClass") != "GOVERNANCE_MITIGATION_BOUNDARY":
            raise VerificationError("RISK_PRODUCT_TEST_FALSELY_EXECUTED", rid)
        for link in risk.get("mappingEvidence", []):
            if not (root / link).is_file():
                raise VerificationError("RISK_MAPPING_EVIDENCE_MISSING", f"{rid}:{link}")
        contract = risk.get("packageGateContract", {})
        if contract.get("packageId") != owner or not contract.get("tests") or not contract.get("exitGate"):
            raise VerificationError("RISK_GATE_CONTRACT_INVALID", rid)
        result = subprocess.run(
            [sys.executable, "graphify/13-implementation/WP-I0-011/risk_governance_test.py", "--risk", rid],
            cwd=root, check=True, capture_output=True, text=True, encoding="utf-8",
        )
        executed = json.loads(result.stdout)
        if executed != {"status": "PASS", "riskId": rid, "checkType": "GOVERNANCE_ENFORCEMENT_NOT_PRODUCT_RUNTIME"}:
            raise VerificationError("RISK_GOVERNANCE_EXECUTION_INVALID", rid)
    if len(runtime_ids) != len(set(runtime_ids)):
        raise VerificationError("RISK_RUNTIME_REQUIREMENT_DUPLICATE")
    runtime_ledger = artifacts["tracker"].get("runtimeRiskEvidence")
    if not isinstance(runtime_ledger, list) or not artifacts["tracker"].get("runtimeRiskEvidenceAggregationPolicy"):
        raise VerificationError("RISK_RUNTIME_LEDGER_MISSING")
    package_statuses = {
        key.split(":", 1)[1]: value
        for key, value in artifacts["tracker"]["current"].items()
        if key.startswith("PACKAGE:")
    }
    try:
        validate_runtime_risk_gates(risk_links, package_statuses, runtime_ledger, "PENDING", root)
    except GovernanceError as exc:
        raise VerificationError("RISK_RUNTIME_LEDGER_INVALID", str(exc)) from exc
    reached_risks = {row["riskId"] for row in risk_links if package_statuses.get(row["testOwnerPackage"]) == "COMPLETE"}
    if {row.get("riskId") for row in runtime_ledger} != reached_risks:
        raise VerificationError("RISK_RUNTIME_LEDGER_COVERAGE_INVALID")
    mitigation_evidence = artifacts["verification"].get("governanceMitigationEvidence", [])
    if {item.get("riskId") for item in mitigation_evidence} != {"R-30", "R-32"}:
        raise VerificationError("GOVERNANCE_MITIGATION_EVIDENCE_MISSING")
    r30_observed = next(item for item in mitigation_evidence if item["riskId"] == "R-30")["observedOutput"]
    r32_observed = next(item for item in mitigation_evidence if item["riskId"] == "R-32")["observedOutput"]
    if r30_observed.get("phaseCount") != 16 or r30_observed.get("packageCount") != 155:
        raise VerificationError("R30_SCOPE_EVIDENCE_INVALID")
    if set(r32_observed.get("guessDimensionsRejected", [])) != {"path", "field", "schema", "ownership"}:
        raise VerificationError("R32_SCOPE_EVIDENCE_INVALID")

    fixtures = artifacts["verification"].get("fixtures", [])
    fixture_ids = [item.get("id") for item in fixtures]
    if len(fixtures) < 50 or len(fixture_ids) != len(set(fixture_ids)):
        raise VerificationError("FIXTURE_SET_INVALID")
    if any(item.get("status") != "PASS" for item in fixtures):
        raise VerificationError("FIXTURE_NOT_PASS")
    required_fixtures = {
        "missing-gate-output", "blocker-guessed-path", "unknown-canonical-edge",
        "compound-edge-not-split", "pass1-incomplete", "pass2-missing-flow",
        "bottom-up-missing-symbol", "risk-missing-test", "production-todo",
        "production-empty-success", "mid-publication-rollback", "graphify-dotdot-codebase",
        "graphify-dotdot-git", "publication-path-traversal", "self-transition-rejected",
        "revision-evidence-required", "revision-timestamp-required",
        "blocker-resolution-required", "risk-missing-governance-check",
        "risk-missing-release-gate", "bottom-up-nonexistent-path",
        "gate-field-wrong-type", "bottom-up-bogus-path-text",
        "gate-evidence-target-missing",
        "revision-timezone-required", "blocker-resolution-id-match",
        "qualified-review-rejected", "package-local-git", "package-local-cache",
        "package-local-node-modules",
        "risk-high-critical-risk-no-test-owner",
        "risk-high-critical-risk-nonexistent-owner",
        "risk-test-owner-earlier-than-mitigation",
        "risk-missing-blocking-package-gate",
        "risk-metadata-only-fake-product-test",
        "risk-package-complete-risk-test-absent",
        "risk-package-complete-risk-test-fail",
        "risk-release-pass-high-critical-risk-unresolved",
        "risk-duplicate-conflicting-risk-test-owner",
        "risk-test-evidence-wrong-risk",
        "risk-test-evidence-wrong-commit-package",
        "risk-test-evidence-wrong-commit",
        "risk-synthetic-governance-fixture-as-runtime-evidence",
        "risk-omitted-mitigation-prerequisite",
        "risk-unrelated-canonical-risk-requirement",
        "risk-unrelated-owner-document-as-raw-evidence",
        "risk-R-30-per-phase-simplicity-real-test",
        "risk-R-32-blocked-protocol-real-test",
        "risk-R-30-other-phase-violation-rejected",
        "risk-R-32-guessed-ownership-rejected",
        "baseline-subject-type-rejected", "tracker-owned-coverage-required",
        "tracker-completed-set-exact", "tracker-risk-context-fail-closed",
        "negated-review-rejected", "forbidden-phrase-review-rejected", "mixed-review-rejected",
    }
    if not required_fixtures <= set(fixture_ids):
        raise VerificationError("REQUIRED_FIXTURE_MISSING")

    actual = actual_codebase(root)
    expected = baseline(root)
    if actual != expected:
        raise VerificationError("CODEBASE_BASELINE_MISMATCH")
    if len(actual) != 3697:
        raise VerificationError("CODEBASE_COUNT_INVALID", str(len(actual)))

    observed = changed_paths(root)
    observed.update(
        f"graphify/13-implementation/{PACKAGE_ID}/{path.name}"
        for path in package_dir.iterdir() if path.is_file()
    )
    package_prefix = f"graphify/13-implementation/{PACKAGE_ID}/"
    authorized = {path for path in observed if path.startswith(package_prefix) or path in CERTIFICATION_MIRRORS}
    unauthorized = observed - authorized
    forbidden_names = {".git", "__pycache__", "node_modules", ".pnpm-store", ".cache", "cache", "dist", "build", "target"}
    forbidden = {
        path for path in observed
        if path.startswith("Codebase/")
        or any(part.lower() in forbidden_names for part in Path(path).parts)
        or path.endswith((".pyc", ".pyo", ".tmp", ".bak"))
    }
    next_package = artifacts["scan"].get("nextPackage")
    next_changes = {
        path for path in observed
        if next_package and path.startswith(f"graphify/13-implementation/{next_package}/")
    }
    if unauthorized or forbidden or next_changes:
        raise VerificationError("LIVE_SCOPE_INVALID", ",".join(sorted(unauthorized | forbidden | next_changes)))
    scan = artifacts["scan"]
    if (
        set(scan.get("changedPaths", [])) != observed
        or set(scan.get("authorizedPaths", [])) != authorized
        or scan.get("unauthorizedPaths") != [] or scan.get("forbiddenArtifacts") != []
        or scan.get("nextPackageImplementationChanges") != 0
    ):
        raise VerificationError("ARTIFACT_SCAN_STALE")

    tracker_without_generation = dict(artifacts["tracker"])
    tracker_without_generation.pop("generationId", None)
    basis = {
        "packageId": PACKAGE_ID,
        "startingSha": START_SHA,
        "tracker": tracker_without_generation,
        "planning": planning_passes,
        "bottomUpHash": semantic_hash(bottom_records),
        "riskLinks": risk_links,
        "fixtureIds": fixture_ids,
        "codebaseManifestHash": semantic_hash(actual),
    }
    if semantic_hash(basis) != generation:
        raise VerificationError("GENERATION_HASH_INVALID")
    expected_hashes = {
        "implementationState": semantic_hash(artifacts["tracker"]),
        "planningGovernance": semantic_hash(artifacts["planning"]),
        "verification": semantic_hash(artifacts["verification"]),
        "packageSummary": semantic_hash(artifacts["summary"]),
        "provenance": semantic_hash(artifacts["provenance"]),
        "artifactScan": semantic_hash(artifacts["scan"]),
        "bottomUpAudit": semantic_hash(bottom_records),
        "blockerSchema": semantic_hash(artifacts["blocker"]),
    }
    if artifacts["consistency"].get("semanticHashes") != expected_hashes:
        raise VerificationError("SEMANTIC_HASH_MISMATCH")
    schema = artifacts["blocker"]
    if schema.get("type") != "object" or schema.get("additionalProperties") is not False:
        raise VerificationError("BLOCKER_SCHEMA_OPEN")
    if set(schema.get("required", [])) != {
        "blockerId", "affectedRecord", "knownFacts", "exactUnknown",
        "safeChecksExhausted", "evidenceLinks", "independentWork",
    }:
        raise VerificationError("BLOCKER_SCHEMA_REQUIRED_INVALID")
    properties = schema.get("properties", {})
    for field in ("knownFacts", "safeChecksExhausted", "evidenceLinks", "independentWork"):
        if properties.get(field, {}).get("type") != "array" or properties[field].get("items", {}).get("type") != "string":
            raise VerificationError("BLOCKER_SCHEMA_ARRAY_INVALID", field)
    for field in ("blockerId", "affectedRecord", "exactUnknown"):
        if properties.get(field, {}).get("type") != "string":
            raise VerificationError("BLOCKER_SCHEMA_STRING_INVALID", field)

    manifest = artifacts["manifest"]
    manifest_files = manifest.get("files", {})
    actual_package_names = {path.name for path in package_dir.iterdir() if path.is_file()}
    expected_manifest_names = actual_package_names - {"artifact-manifest.json"}
    if set(manifest_files) != expected_manifest_names:
        raise VerificationError("ARTIFACT_MANIFEST_COVERAGE_INVALID")
    for name, digest in manifest_files.items():
        if not re.fullmatch(r"[0-9a-f]{64}", str(digest)) or sha256_file(package_dir / name) != digest:
            raise VerificationError("ARTIFACT_MANIFEST_HASH_INVALID", name)
    if not manifest.get("selfExcluded") or "artifact-manifest.json" not in manifest["selfExcluded"]:
        raise VerificationError("ARTIFACT_MANIFEST_SELF_EXCLUSION_MISSING")

    independent_fixtures = []
    tampered = json.loads(json.dumps(artifacts["tracker"]))
    tampered["revisions"][0]["revisionHash"] = "0" * 64
    independent_fixtures.append(expect_failure("REVISION_HASH_INVALID", lambda: verify_tracker(tampered, canonical_ids, package_ids)))
    tampered = json.loads(json.dumps(artifacts["tracker"]))
    tampered["importedBaselines"][0]["applicableGates"] = []
    independent_fixtures.append(expect_failure("BASELINE_GATES_MISSING", lambda: verify_tracker(tampered, canonical_ids, package_ids)))
    tampered = json.loads(json.dumps(artifacts["tracker"]))
    tampered["importedBaselines"][0]["subjectType"] = "BOGUS"
    independent_fixtures.append(expect_failure("BASELINE_SUBJECT_TYPE_INVALID", lambda: verify_tracker(tampered, canonical_ids, package_ids)))
    tampered = json.loads(json.dumps(artifacts["tracker"]))
    tampered["revisions"][0]["statement"] = "copied divergent text"
    tampered["revisions"][0]["revisionHash"] = revision_hash(tampered["revisions"][0])
    independent_fixtures.append(expect_failure("EMBEDDED_STATEMENT", lambda: verify_tracker(tampered, canonical_ids, package_ids)))
    tampered = json.loads(json.dumps(artifacts["tracker"]))
    tampered["current"] = {}
    independent_fixtures.append(expect_failure("CURRENT_STATE_INVALID", lambda: verify_tracker(tampered, canonical_ids, package_ids)))
    tampered = json.loads(json.dumps(artifacts["tracker"]))
    missing_rid = "CAN-LAM-RISK-TEST-030"
    tampered["revisions"] = [item for item in tampered["revisions"] if item.get("subjectId") != missing_rid]
    tampered["current"].pop(f"REQUIREMENT:{missing_rid}")
    required_current = {f"REQUIREMENT:{rid}" for rid in EXPECTED_OWNED} | {f"PACKAGE:{PACKAGE_ID}"}
    independent_fixtures.append(expect_failure("TRACKER_OWNED_COVERAGE_MISSING", lambda: verify_tracker(tampered, canonical_ids, package_ids, required_current)))
    tampered = json.loads(json.dumps(artifacts["tracker"]))
    tampered["completedPackages"].append("WP-I3-014")
    independent_fixtures.append(expect_failure("TRACKER_COMPLETED_PACKAGES_MISMATCH", lambda: verify_tracker(tampered, canonical_ids, package_ids)))
    tampered = json.loads(json.dumps(artifacts["tracker"]))
    tampered["revisions"][0]["toStatus"] = tampered["revisions"][0]["fromStatus"]
    tampered["revisions"][0]["revisionHash"] = revision_hash(tampered["revisions"][0])
    independent_fixtures.append(expect_failure("TRANSITION_INVALID", lambda: verify_tracker(tampered, canonical_ids, package_ids)))
    tampered = json.loads(json.dumps(artifacts["tracker"]))
    tampered["revisions"][0]["evidenceLinks"] = []
    tampered["revisions"][0]["revisionHash"] = revision_hash(tampered["revisions"][0])
    independent_fixtures.append(expect_failure("REVISION_EVIDENCE_MISSING", lambda: verify_tracker(tampered, canonical_ids, package_ids)))
    tampered = json.loads(json.dumps(artifacts["tracker"]))
    tampered["revisions"][0]["timestamp"] = "not-a-timestamp"
    tampered["revisions"][0]["revisionHash"] = revision_hash(tampered["revisions"][0])
    independent_fixtures.append(expect_failure("TIMESTAMP_INVALID", lambda: verify_tracker(tampered, canonical_ids, package_ids)))
    tampered = json.loads(json.dumps(artifacts["tracker"]))
    tampered["revisions"][0]["timestamp"] = "2026-08-11T12:00:00"
    tampered["revisions"][0]["revisionHash"] = revision_hash(tampered["revisions"][0])
    independent_fixtures.append(expect_failure("TIMESTAMP_INVALID", lambda: verify_tracker(tampered, canonical_ids, package_ids)))
    tampered = json.loads(json.dumps(artifacts["tracker"]))
    gate_revision = next(item for item in tampered["revisions"] if item.get("applicableGates"))
    gate_revision["applicableGates"][0]["method"] = 123
    gate_revision["revisionHash"] = revision_hash(gate_revision)
    independent_fixtures.append(expect_failure("GATE_FIELD_TYPE", lambda: verify_tracker(tampered, canonical_ids, package_ids)))
    for text in (
        "PACKAGE REVIEW PASS - BUT BLOCKING DEFECTS REMAIN",
        "NOT PACKAGE REVIEW PASS",
        "The phrase PACKAGE REVIEW PASS is forbidden; final verdict FAIL",
        "PACKAGE REVIEW PASS\nPACKAGE REVIEW FAIL",
    ):
        if exact_review_pass(text):
            raise VerificationError("QUALIFIED_REVIEW_ACCEPTED")
        independent_fixtures.append({"expected": "invalid review rejected", "observed": "rejected", "status": "PASS"})
    blocker = {
        "blockerId": "B1", "affectedRecord": PACKAGE_ID, "knownFacts": ["fact"],
        "exactUnknown": "unknown", "safeChecksExhausted": ["check"],
        "evidenceLinks": ["graphify/13-implementation/WP-I0-011/completion-evidence.md"],
        "independentWork": ["work"],
    }
    blocked = {
        "revisionId": "fixture-blocked", "subjectType": "PACKAGE", "subjectId": PACKAGE_ID,
        "fromStatus": "NOT_STARTED", "toStatus": "BLOCKED", "actor": "fixture",
        "timestamp": "2026-08-11T12:00:00+00:00", "evidenceLinks": blocker["evidenceLinks"],
        "applicableGates": [], "previousRevisionHash": "GENESIS", "blocker": blocker,
    }
    blocked["revisionHash"] = revision_hash(blocked)
    recovered = {
        "revisionId": "fixture-recovered", "subjectType": "PACKAGE", "subjectId": PACKAGE_ID,
        "fromStatus": "BLOCKED", "toStatus": "IN_PROGRESS", "actor": "fixture",
        "timestamp": "2026-08-11T12:00:01+00:00", "evidenceLinks": blocker["evidenceLinks"],
        "applicableGates": [], "previousRevisionHash": blocked["revisionHash"],
        "resolution": {"resolvedBlockerId": "DIFFERENT", "reason": "fixture", "evidenceLinks": blocker["evidenceLinks"]},
    }
    recovered["revisionHash"] = revision_hash(recovered)
    mismatch_tracker = {
        "schemaVersion": 2, "importedBaselines": [], "revisions": [blocked, recovered],
        "current": {f"PACKAGE:{PACKAGE_ID}": "IN_PROGRESS"},
    }
    independent_fixtures.append(expect_failure(
        "BLOCKER_RESOLUTION_ID_MISMATCH",
        lambda: verify_tracker(mismatch_tracker, canonical_ids, package_ids),
    ))

    print(json.dumps({
        "status": "PASS",
        "packageId": PACKAGE_ID,
        "generationId": generation,
        "trackerRevisions": len(artifacts["tracker"]["revisions"]),
        "completedPackages": len(artifacts["tracker"]["completedPackages"]),
        "readyPackages": artifacts["tracker"]["readyPackages"],
        "planningRequirements": coverage["actionable"],
        "riskLinks": len(risk_links),
        "packageFixtures": len(fixtures),
        "independentFixtures": len(independent_fixtures),
        "codebaseFiles": len(actual),
    }, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (VerificationError, OSError, subprocess.CalledProcessError) as exc:
        code = exc.code if isinstance(exc, VerificationError) else type(exc).__name__
        print(json.dumps({"status": "FAIL", "errorCode": code, "detail": str(exc)}, indent=2), file=sys.stderr)
        raise SystemExit(1)
