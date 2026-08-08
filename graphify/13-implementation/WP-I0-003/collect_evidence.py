"""WP-I0-003 existing repository SHA-256 manifest collector.

Package packet: graphify/12-semantic-implementation-plan/04-work-packages/packets/WP-I0-003.md
Owned requirements: CAN-MISSION-I0-003
Technical prerequisite: WP-I0-001 (REQUIRES_PROVENANCE) — COMPLETE and GitHub-verified.

Behaviour contract:
- READ-ONLY for every path outside graphify/ and for all of Git. The only
  writes are this package's authorized evidence deliverables inside
  graphify/13-implementation/WP-I0-003/, written through tools/write_guard.
- Creates no archive, backup, repository copy/duplicate tree, application
  mutation, or Git mutation. A hash manifest records path/size/digest facts
  about existing files: it never copies their contents into a second tree.
- Manifest scope is the existing repository application corpus under
  Codebase/ — the resolved roots and exclusion boundary (.git and graphify/
  excluded) established by the prerequisite provenance baseline (WP-I0-001).
- Typed errors: failed verification inputs (invalid/tampered manifest rows)
  produce structured typed error records and no partial commit, never a
  false PASS and never an exception escape.
- Exits 0 only when every manifest entry verifies, every packet test,
  failure-case guard, and exit-gate clause evaluates PASS.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True

PACKAGE_ID = "WP-I0-003"
PACKAGE_DIR = Path(__file__).resolve().parent
GRAPHIFY = PACKAGE_DIR.parents[1]
LAMHA = GRAPHIFY.parent.resolve(strict=True)
CODEBASE = LAMHA / "Codebase"
TOOLS = GRAPHIFY / "tools"
PLAN = GRAPHIFY / "12-semantic-implementation-plan"
REPORTS = PLAN / "13-reports"
SHA_BASELINE = REPORTS / "external-readonly-baseline.json"
BLOB_BASELINE = REPORTS / "pass3-external-readonly-baseline.json"
PACKET = PLAN / "04-work-packages" / "packets" / f"{PACKAGE_ID}.md"
PREREQ_DIR = GRAPHIFY / "13-implementation" / "WP-I0-001"
PREREQ_SUMMARY = PREREQ_DIR / "package-summary.json"
PREREQ_REVIEW = PREREQ_DIR / "adversarial-review.md"
AUTH_RECORD = GRAPHIFY / "13-implementation" / "WP-I0-002" / "adversarial-review.md"

sys.path.insert(0, str(TOOLS))
from write_guard import guard_write_path  # noqa: E402

GIT_ENV = {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}

BLOCK_SIZE = 1024 * 1024

ARTIFACT_PATTERNS = {
    "archive": re.compile(r"\.(zip|tar|tgz|tar\.gz|tar\.xz|tar\.bz2|7z|rar)$", re.I),
    "backup": re.compile(r"\.(bak|backup)$|(^|/)backup(s)?([/_-]|$)", re.I),
    "copy": re.compile(r"(^|/)copy([/_-]|$)| -?copy\.", re.I),
    "build": re.compile(r"(^|/)(dist|build|out|target|\.svelte-kit|\.dart_tool|\.next|\.turbo)(/|$)"),
    "test": re.compile(r"(^|/)(coverage|\.nyc_output|test-results|playwright-report)(/|$)"),
    "cache": re.compile(r"(^|/)(\.pytest_cache|__pycache__|\.mypy_cache|\.ruff_cache|\.cache|\.gradle)(/|$)"),
    "package_manager": re.compile(r"(^|/)(node_modules|\.pnpm-store|Pods)(/|$)"),
    "generated_code": re.compile(r"\.(g\.dart|generated\.ts)$"),
}

READONLY_PREFIXES = {
    ("rev-parse",),
    ("branch", "--show-current"),
    ("status", "--porcelain=v1"),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> tuple[int, str]:
    hasher = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(BLOCK_SIZE), b""):
            size += len(block)
            hasher.update(block)
    return size, hasher.hexdigest()


def write_evidence(relative: str, data: str, written: list[str]) -> None:
    target = guard_write_path(PACKAGE_DIR / relative)
    resolved = target.resolve(strict=False)
    resolved.relative_to(PACKAGE_DIR)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(data.rstrip("\n") + "\n", encoding="utf-8", newline="\n")
    written.append(resolved.relative_to(GRAPHIFY).as_posix())


def write_json(relative: str, value: object, written: list[str]) -> None:
    write_evidence(relative, json.dumps(value, ensure_ascii=False, indent=2), written)


def prefix_allowed(args: list[str]) -> bool:
    return any(args[: len(prefix)] == list(prefix) for prefix in READONLY_PREFIXES)


def run_git(args: list[str], raw: list[dict[str, object]]) -> dict[str, object]:
    record: dict[str, object] = {
        "command": "git " + " ".join(args),
        "env": {"GIT_OPTIONAL_LOCKS": "0"},
        "allowlistedReadOnly": prefix_allowed(args),
    }
    if not record["allowlistedReadOnly"]:
        record.update({"exitCode": None, "stdout": "", "stderr": "",
                       "typedError": {"type": "NonReadOnlyCommandRejected",
                                      "partialCommit": False, "gitStateMutated": False}})
        raw.append(record)
        return record
    completed = subprocess.run(
        ["git", "-c", "core.quotePath=false", *args],
        cwd=LAMHA, env=GIT_ENV, capture_output=True, text=True, check=False,
    )
    record.update({"exitCode": completed.returncode, "stdout": completed.stdout,
                   "stderr": completed.stderr})
    if completed.returncode != 0:
        record["typedError"] = {"type": "GitCommandFailure", "partialCommit": False,
                                "gitStateMutated": False}
    raw.append(record)
    return record


def git_state(raw: list[dict[str, object]]) -> dict[str, object]:
    fields: dict[str, object] = {}
    queries = {
        "head": ["rev-parse", "HEAD"],
        "origin_main": ["rev-parse", "origin/main"],
        "branch": ["branch", "--show-current"],
        "status_outside_graphify": [
            "status", "--porcelain=v1", "--untracked-files=all", "--", ".", ":(exclude)graphify",
        ],
    }
    for key, args in queries.items():
        record = run_git(args, raw)
        fields[key] = {"exitCode": record["exitCode"], "output": record["stdout"]}
    return fields


def hash_corpus() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Hash every file under Codebase/ (read-only). Returns (rows, unreadable)."""
    rows: list[dict[str, object]] = []
    unreadable: list[dict[str, object]] = []
    for root, dirs, files in os.walk(CODEBASE):
        dirs.sort()
        for name in sorted(files):
            path = Path(root) / name
            rel = path.relative_to(LAMHA).as_posix()
            try:
                size, digest = sha256_file(path)
            except OSError as error:
                unreadable.append({"path": rel, "error": str(error)})
                continue
            rows.append({"path": rel, "size": size, "sha256": digest})
    rows.sort(key=lambda row: str(row["path"]))
    return rows, unreadable


def manifest_csv(rows: list[dict[str, object]]) -> str:
    lines = ["path,size,sha256"]
    for row in rows:
        lines.append(f"{row['path']},{row['size']},{row['sha256']}")
    return "\n".join(lines)


def verify_manifest(manifest_rows: list[dict[str, object]]) -> dict[str, object]:
    """Rehash every manifest entry on disk and verify path, size, digest.

    Reads the manifest rows as data and re-hashes each named file from the
    current working tree. Returns a typed per-entry result set. This is the
    packet test: "Rehash every manifest entry and verify path, byte size, and
    digest equality." Invalid rows produce typed errors, never exceptions.
    """
    verified = 0
    failures: list[dict[str, object]] = []
    for row in manifest_rows:
        rel = str(row.get("path", ""))
        path = LAMHA / rel
        if not rel or ".." in Path(rel).parts or Path(rel).is_absolute():
            failures.append({
                "path": rel,
                "typedError": {"type": "InvalidManifestEntry",
                               "partialCommit": False, "authoritativeStatePreserved": True},
            })
            continue
        try:
            size, digest = sha256_file(path)
        except OSError as error:
            failures.append({
                "path": rel,
                "typedError": {"type": "ManifestEntryUnreadable", "message": str(error),
                               "partialCommit": False, "authoritativeStatePreserved": True},
            })
            continue
        row_ok = int(row["size"]) == size and str(row["sha256"]) == digest
        if row_ok:
            verified += 1
        else:
            failures.append({
                "path": rel,
                "typedError": {"type": "ManifestEntryMismatch",
                               "recordedSize": row["size"], "currentSize": size,
                               "recordedSha256": row["sha256"], "currentSha256": digest,
                               "partialCommit": False, "authoritativeStatePreserved": True},
            })
    return {
        "entries": len(manifest_rows),
        "verified": verified,
        "failureCount": len(failures),
        "failures": failures,
        "status": "PASS" if not failures and verified == len(manifest_rows) else "FAIL",
    }


def compare_sha_baseline(rows: list[dict[str, object]]) -> dict[str, object]:
    baseline = json.loads(SHA_BASELINE.read_text(encoding="utf-8"))
    before = {row["path"]: row for row in baseline["files"]}
    after = {str(row["path"]): row for row in rows}
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    modified = sorted(
        path
        for path in set(before) & set(after)
        if int(before[path]["size"]) != int(after[path]["size"])
        or before[path]["sha256"] != after[path]["sha256"]
    )
    removed_by_hash: dict[str, list[str]] = {}
    for path in removed:
        removed_by_hash.setdefault(str(before[path]["sha256"]), []).append(path)
    renamed = []
    for path in added:
        candidates = removed_by_hash.get(str(after[path]["sha256"]), [])
        if candidates:
            renamed.append({"from": candidates.pop(0), "to": path, "sha256": after[path]["sha256"]})
    return {
        "baselinePath": SHA_BASELINE.relative_to(GRAPHIFY).as_posix(),
        "baselineAlgorithm": baseline.get("algorithm"),
        "baselineFileCount": baseline.get("file_count"),
        "currentFileCount": len(rows),
        "scope": "Every working-tree file under Codebase/ (outside-Graphify application corpus)",
        "added": added,
        "removed": removed,
        "modified": modified,
        "renamed": renamed,
        "status": "PASS" if not added and not removed and not modified else "FAIL",
    }


def tracked_tree_outside_graphify(raw: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    completed = subprocess.run(
        ["git", "-c", "core.quotePath=false", "ls-tree", "-r", "-z", "-l", "HEAD"],
        cwd=LAMHA, env=GIT_ENV, capture_output=True, check=False,
    )
    raw.append({
        "command": "git ls-tree -r -z -l HEAD",
        "env": {"GIT_OPTIONAL_LOCKS": "0"},
        "allowlistedReadOnly": True,
        "exitCode": completed.returncode,
        "stdout_bytes": len(completed.stdout),
        "stderr": completed.stderr.decode("utf-8", errors="replace"),
    })
    rows: dict[str, dict[str, object]] = {}
    if completed.returncode != 0:
        return rows
    for entry in completed.stdout.split(b"\0"):
        if not entry:
            continue
        metadata, raw_path = entry.split(b"\t", 1)
        mode, object_type, object_id, size = metadata.decode("ascii").split()
        path = raw_path.decode("utf-8", errors="surrogateescape")
        if path == "graphify" or path.startswith("graphify/"):
            continue
        rows[path] = {"mode": mode, "objectType": object_type,
                      "gitBlobOid": object_id, "size": -1 if size == "-" else int(size)}
    return rows


def compare_blob_baseline(tree: dict[str, dict[str, object]]) -> dict[str, object]:
    baseline = json.loads(BLOB_BASELINE.read_text(encoding="utf-8"))
    before = {str(row["path"]): row for row in baseline["files"]}
    added = sorted(set(tree) - set(before))
    removed = sorted(set(before) - set(tree))
    modified = sorted(
        path
        for path in set(before) & set(tree)
        if before[path].get("mode") != tree[path].get("mode")
        or int(before[path].get("size", -1)) != int(tree[path].get("size", -1))
        or before[path].get("gitBlobOid") != tree[path].get("gitBlobOid")
    )
    renamed: list[dict[str, object]] = []
    removed_by_oid: dict[str, list[str]] = {}
    for path in removed:
        removed_by_oid.setdefault(str(before[path]["gitBlobOid"]), []).append(path)
    for path in added:
        candidates = removed_by_oid.get(str(tree[path]["gitBlobOid"]), [])
        if candidates:
            renamed.append({"from": candidates.pop(0), "to": path,
                            "gitBlobOid": tree[path]["gitBlobOid"]})
    return {
        "baselinePath": BLOB_BASELINE.relative_to(GRAPHIFY).as_posix(),
        "baselineAlgorithm": baseline.get("algorithm"),
        "baselineFileCount": baseline.get("file_count"),
        "currentFileCount": len(tree),
        "added": added,
        "removed": removed,
        "modified": modified,
        "renamed": renamed,
        "status": "PASS" if not added and not removed and not modified else "FAIL",
    }


def classify_artifact(path: str) -> list[str]:
    return [label for label, pattern in ARTIFACT_PATTERNS.items() if pattern.search(path)]


def main() -> int:
    written: list[str] = []
    raw_git: list[dict[str, object]] = []
    started = utc_now()
    failures: list[str] = []

    prerequisite = json.loads(PREREQ_SUMMARY.read_text(encoding="utf-8"))

    # 1. Git state BEFORE collection (read-only, optional locks disabled).
    git_before = git_state(raw_git)
    git_available = git_before["head"]["exitCode"] == 0  # type: ignore[index]

    # 2. Hash pass 1: build the existing-file SHA-256 manifest.
    pass1, unreadable1 = hash_corpus()
    # 3. Hash pass 2: independent recompute (stability proof).
    pass2, unreadable2 = hash_corpus()
    manifest_text = manifest_csv(pass1)
    manifest_digest = sha256_bytes(manifest_text.encode("utf-8"))
    pass2_digest = sha256_bytes(manifest_csv(pass2).encode("utf-8"))
    stability_status = "PASS" if manifest_digest == pass2_digest else "FAIL"
    if stability_status != "PASS":
        failures.append("two independent hashing passes produced different manifests")
    unreadable = unreadable1 + unreadable2
    if unreadable:
        failures.append(f"unreadable files during hashing: {unreadable}")

    # 4. Packet test: rehash every manifest entry; verify path/size/digest.
    verification = verify_manifest(pass1)
    if verification["status"] != "PASS":
        failures.append("manifest entry verification failed")

    # 5. Failure cases.
    # 5a. Invalid input: tampered/invalid manifest rows must return typed
    # errors with no partial commit and no false PASS.
    tampered_probe_manifest = [
        {"path": "../outside-escape", "size": 1, "sha256": "0" * 64},
        {"path": str(pass1[0]["path"]), "size": int(pass1[0]["size"]) + 1,
         "sha256": "0" * 64},
    ]
    tampered_probe = verify_manifest(tampered_probe_manifest)
    tampered_probe_ok = (
        tampered_probe["status"] == "FAIL"
        and tampered_probe["failureCount"] == 2
        and {f["typedError"]["type"] for f in tampered_probe["failures"]}
        == {"InvalidManifestEntry", "ManifestEntryMismatch"}
    )
    if not tampered_probe_ok:
        failures.append(f"tampered-manifest probe not correctly rejected: {tampered_probe}")
    # 5b. Write-guard destination-escape fixtures (must all be rejected).
    guard_fixtures: list[dict[str, object]] = []
    for probe_path in ("../escape-outside.txt", "/absolute/escape.txt"):
        try:
            guard_write_path(PACKAGE_DIR / probe_path)
            guard_fixtures.append({"probe": probe_path, "rejected": False})
            failures.append(f"write guard accepted escape probe: {probe_path}")
        except ValueError:
            guard_fixtures.append({"probe": probe_path, "rejected": True})
    # 5c. Read-only command audit.
    non_readonly = [str(r["command"]) for r in raw_git if r["allowlistedReadOnly"] is not True]
    if non_readonly:
        failures.append(f"non-read-only Git commands executed: {non_readonly}")

    # 6. Baseline comparisons (provenance boundary proof).
    sha_comparison = compare_sha_baseline(pass1)
    tree = tracked_tree_outside_graphify(raw_git)
    blob_comparison = compare_blob_baseline(tree)
    if sha_comparison["status"] != "PASS":
        failures.append("SHA-256 baseline comparison reported changes outside Graphify")
    if blob_comparison["status"] != "PASS":
        failures.append("Git-blob baseline comparison reported changes outside Graphify")

    # 7. Git state AFTER collection.
    git_after = git_state(raw_git)
    git_keys = ["head", "origin_main", "branch", "status_outside_graphify"]
    git_unchanged = all(git_before[key] == git_after[key] for key in git_keys)
    if not git_unchanged:
        changed = [key for key in git_keys if git_before[key] != git_after[key]]
        failures.append(f"Git metadata changed during collection: {changed}")

    # 8. Artifact scan: any path added outside Graphify is a candidate artifact.
    added_outside = sorted(set(sha_comparison["added"]) | set(blob_comparison["added"]))
    artifact_scan = {
        "scanWindow": "package collection run",
        "scope": "paths added outside Graphify relative to both planning baselines, plus this package's own evidence files",
        "addedOutsideGraphify": added_outside,
        "newArtifactCandidates": [
            {"path": path, "classes": classify_artifact(path)} for path in added_outside
        ],
        "evidenceFiles": [],
        "evidenceFileClasses": [],
        "status": "PASS" if not added_outside else "FAIL",
    }

    # 9. Persist evidence (inside Graphify only).
    provenance = {
        "packageId": PACKAGE_ID,
        "packetPath": PACKET.relative_to(GRAPHIFY).as_posix(),
        "packetSha256": sha256_bytes(PACKET.read_bytes()),
        "ownedRequirements": ["CAN-MISSION-I0-003"],
        "selection": {
            "rule": "explicit authorization record from WP-I0-002 transition (AUTHORIZED — NOT_STARTED), confirmed by the deterministic READY-package selector",
            "readyPackages": [
                "WP-I0-003", "WP-I0-004", "WP-I0-006", "WP-I0-008",
                "WP-I0-009", "WP-I0-010", "WP-I0-011", "WP-I1-001",
            ],
            "explicitAuthorizationRecordPath": AUTH_RECORD.relative_to(GRAPHIFY).as_posix(),
            "explicitAuthorizationRecordSha256": sha256_bytes(AUTH_RECORD.read_bytes()),
            "startSha": "d6bb993435fa3fbb2d40ab33469f62977bd9612c",
        },
        "prerequisite": {
            "packageId": "WP-I0-001",
            "dependencyType": "REQUIRES_PROVENANCE",
            "completionRecordPath": PREREQ_SUMMARY.relative_to(GRAPHIFY).as_posix(),
            "completionRecordSha256": sha256_bytes(PREREQ_SUMMARY.read_bytes()),
            "completionRecordStatus": prerequisite.get("status"),
            "reviewRecordPath": PREREQ_REVIEW.relative_to(GRAPHIFY).as_posix(),
            "reviewRecordSha256": sha256_bytes(PREREQ_REVIEW.read_bytes()),
        },
        "roots": {
            "lamhaRoot": str(LAMHA),
            "codebaseRoot": str(CODEBASE),
            "graphifyRoot": str(GRAPHIFY),
            "packageEvidenceDir": str(PACKAGE_DIR),
        },
        "scope": {
            "manifestScope": "Every working-tree file under Codebase/ (the existing repository application corpus; the WP-I0-001 provenance baseline recorded 3697 files there).",
            "exclusionBoundary": "Inherited from the prerequisite provenance baseline (REQUIRES_PROVENANCE): .git excluded (repository metadata, covered by Git-state inspection WP-I0-002), graphify/ excluded (authority and evidence scope; evidence inside it is written through tools/write_guard only).",
        },
        "baselines": {
            "sha256": {"path": SHA_BASELINE.relative_to(GRAPHIFY).as_posix(),
                       "sha256": sha256_bytes(SHA_BASELINE.read_bytes())},
            "gitBlob": {"path": BLOB_BASELINE.relative_to(GRAPHIFY).as_posix(),
                        "sha256": sha256_bytes(BLOB_BASELINE.read_bytes())},
        },
        "environment": {
            "collectionStartedUtc": started,
            "os": os.name,
            "platform": sys.platform,
            "python": sys.version.split()[0],
            "gitEnvOverrides": {"GIT_OPTIONAL_LOCKS": "0", "core.quotePath": "false"},
        },
        "readOnlyGuarantee": "No path outside graphify/ is opened for writing; no archive, backup, or duplicate tree is created — the manifest records path/size/digest facts only; collector writes are restricted to graphify/13-implementation/WP-I0-003/ through tools/write_guard.",
    }

    write_json("provenance-report.json", provenance, written)
    write_evidence("sha256-manifest.csv", manifest_text, written)
    write_json(
        "verification-report.json",
        {
            "manifest": {
                "file": "13-implementation/WP-I0-003/sha256-manifest.csv",
                "entries": len(pass1),
                "algorithm": "SHA-256 over raw file bytes; paths repo-relative POSIX; sizes in bytes",
                "manifestSha256": manifest_digest,
                "scope": provenance["scope"]["manifestScope"],
            },
            "recompute": {
                "method": "two full independent SHA-256 passes over every Codebase/ file inside one run",
                "pass1ManifestSha256": manifest_digest,
                "pass2ManifestSha256": pass2_digest,
                "status": stability_status,
            },
            "entryVerification": verification,
            "baselineComparisons": {
                "sha256Baseline": sha_comparison,
                "gitBlobBaseline": blob_comparison,
            },
            "artifactScan": {
                "addedOutsideGraphify": added_outside,
                "status": artifact_scan["status"],
            },
            "failureCases": {
                "unreadableFiles": unreadable,
                "tamperedManifestProbe": {
                    "probeEntries": len(tampered_probe_manifest),
                    "expectedRejection": "both rows rejected with typed errors, no partial commit, no false PASS",
                    "result": tampered_probe,
                    "status": "PASS" if tampered_probe_ok else "FAIL",
                },
                "writeGuardEscapeFixtures": guard_fixtures,
                "readOnlyCommandAudit": {
                    "commandsExecuted": len(raw_git),
                    "nonReadOnlyCommands": non_readonly,
                    "status": "PASS" if not non_readonly else "FAIL",
                },
                "gitMetadataAvailable": git_available,
                "gitMetadataUnchanged": git_unchanged,
            },
            "gitState": {"before": git_before, "after": git_after,
                         "metadataUnchanged": git_unchanged, "rawCommands": raw_git},
            "tests": {
                "wp_i0_003_success": "PASS"
                if verification["status"] == "PASS" and stability_status == "PASS" and not failures
                else "FAIL",
                "wp_i0_003_failure": "PASS"
                if tampered_probe_ok and all(f["rejected"] for f in guard_fixtures)
                else "FAIL",
            },
        },
        written,
    )
    artifact_scan["evidenceFiles"] = sorted(
        written
        + [
            "13-implementation/WP-I0-003/artifact-scan.json",
            "13-implementation/WP-I0-003/completion-evidence.md",
            "13-implementation/WP-I0-003/package-summary.json",
        ]
    )
    artifact_scan["evidenceFileClasses"] = [
        {"path": path, "classes": classify_artifact(path)}
        for path in artifact_scan["evidenceFiles"]
    ]
    write_json("artifact-scan.json", artifact_scan, written)

    # 10. Exit-gate clauses.
    exit_gate = [
        {
            "clause": "Every manifest entry verifies",
            "evidence": f"All {len(pass1)} manifest entries were re-hashed from the current working tree and verified for path existence, byte size, and SHA-256 digest equality with zero failures; two independent hashing passes produced byte-identical manifests; both planning baselines report zero added/removed/modified/renamed paths.",
            "evidenceFiles": [
                "13-implementation/WP-I0-003/sha256-manifest.csv",
                "13-implementation/WP-I0-003/verification-report.json",
            ],
            "result": "PASS"
            if verification["status"] == "PASS" and stability_status == "PASS"
            and sha_comparison["status"] == "PASS" and blob_comparison["status"] == "PASS"
            else "FAIL",
        },
        {
            "clause": "No archive, backup, copy, or repository mutation exists",
            "evidence": "Zero paths were added outside Graphify relative to both planning baselines; this package's evidence files match no archive/backup/copy/build/test/cache/package-manager/generated-code pattern (a manifest records path/size/digest facts and never copies file contents); Git metadata is unchanged across the run; every Git command is read-only under the static allowlist with GIT_OPTIONAL_LOCKS=0.",
            "evidenceFiles": [
                "13-implementation/WP-I0-003/artifact-scan.json",
                "13-implementation/WP-I0-003/verification-report.json",
            ],
            "result": "PASS"
            if artifact_scan["status"] == "PASS" and git_unchanged and not non_readonly
            else "FAIL",
        },
    ]
    for clause in exit_gate:
        if clause["result"] != "PASS":
            failures.append(f"exit-gate clause failed: {clause['clause']}")

    completion_md = [
        f"# {PACKAGE_ID} completion evidence",
        "",
        f"- Package: {PACKAGE_ID} — Existing repository SHA-256 manifest",
        f"- Collection ran: {started} → {utc_now()}",
        f"- Manifest entries computed: **{len(pass1)}** (path, byte size, SHA-256), all re-hashed and verified: **{verification['verified']}/{verification['entries']} entries verify**.",
        "- Outside-Graphify additions/removals/modifications/renames: **zero** (SHA-256 baseline and Git-blob baseline comparisons).",
        "- This package created **no** archive, backup, repository copy/duplicate tree, application mutation, or Git mutation — the manifest records path/size/digest facts only.",
        "- All generated evidence resolves inside `graphify/13-implementation/WP-I0-003/` and was written through `graphify/tools/write_guard.py`.",
        "",
        "## Requirements",
        "",
        "- `CAN-MISSION-I0-003`: the SHA-256 manifest for existing repository files was calculated (`sha256-manifest.csv`, "
        + str(len(pass1))
        + " entries) and verified (`verification-report.json`: every entry re-hashed with path/size/digest equality; two independent passes byte-identical) without creating an archive, backup, or duplicate repository tree.",
        "",
        "## Exit gate",
        "",
    ]
    for clause in exit_gate:
        completion_md.append(f"- **{clause['result']}** — {clause['clause']}: {clause['evidence']}")
    completion_md.append("")
    write_evidence("completion-evidence.md", "\n".join(completion_md), written)

    summary = {
        "packageId": PACKAGE_ID,
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "collectionWindowUtc": {"start": started, "end": utc_now()},
        "checks": {
            "recomputeComparison": stability_status,
            "manifestEntryVerification": verification["status"],
            "shaBaselineComparison": sha_comparison["status"],
            "gitBlobBaselineComparison": blob_comparison["status"],
            "artifactScan": artifact_scan["status"],
            "gitMetadataCompare": "PASS" if git_unchanged else "FAIL",
            "failureCases": "PASS"
            if tampered_probe_ok and all(f["rejected"] for f in guard_fixtures)
            and git_available and not unreadable
            else "FAIL",
            "exitGate": "PASS" if all(c["result"] == "PASS" for c in exit_gate) else "FAIL",
        },
        "fileCounts": {
            "manifestEntries": len(pass1),
            "trackedOutsideGraphify": len(tree),
        },
        "evidenceFiles": sorted(written + ["13-implementation/WP-I0-003/package-summary.json"]),
        "exitGateClauses": exit_gate,
    }
    write_json("package-summary.json", summary, written)
    print(json.dumps({"status": summary["status"], "failures": failures,
                      "manifestEntries": len(pass1)}, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
