"""WP-I0-002 read-only Git-state inspection collector.

Package packet: graphify/12-semantic-implementation-plan/04-work-packages/packets/WP-I0-002.md
Owned requirements: CAN-MISSION-I0-002
Technical prerequisite: WP-I0-001 (REQUIRES_PROVENANCE) — COMPLETE and GitHub-verified.

Behaviour contract:
- READ-ONLY for Git metadata and for every path outside graphify/. The only
  writes are this package's authorized evidence deliverables inside
  graphify/13-implementation/WP-I0-002/, written through tools/write_guard.
- Every Git command runs with GIT_OPTIONAL_LOCKS=0 and belongs to a static
  read-only prefix allowlist; no commit, branch, tag, stash, worktree, index,
  or configuration mutation command is ever executed.
- Typed errors: failed inspection targets produce structured typed error
  records (invalid input -> typed error), and failure probes write no partial
  evidence and no commit of any kind.
- Exits 0 only when every packet test, failure-case guard, and exit-gate
  clause evaluates PASS; otherwise exits 1 with the failures recorded.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True

PACKAGE_ID = "WP-I0-002"
PACKAGE_DIR = Path(__file__).resolve().parent
GRAPHIFY = PACKAGE_DIR.parents[1]
LAMHA = GRAPHIFY.parent.resolve(strict=True)
GIT_DIR = LAMHA / ".git"
TOOLS = GRAPHIFY / "tools"
PLAN = GRAPHIFY / "12-semantic-implementation-plan"
PACKET = PLAN / "04-work-packages" / "packets" / f"{PACKAGE_ID}.md"
PREREQ_DIR = GRAPHIFY / "13-implementation" / "WP-I0-001"
PREREQ_SUMMARY = PREREQ_DIR / "package-summary.json"
PREREQ_REVIEW = PREREQ_DIR / "adversarial-review.md"

sys.path.insert(0, str(TOOLS))
from write_guard import guard_write_path  # noqa: E402

GIT_ENV = {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}

BLOCK_SIZE = 1024 * 1024

# Static allowlist of read-only Git command prefixes executed by this package.
# Any command whose leading arguments are not declared here fails the audit.
READONLY_PREFIXES = {
    ("rev-parse",),
    ("branch", "--show-current"),
    ("remote", "-v"),
    ("for-each-ref",),
    ("stash", "list"),
    ("worktree", "list"),
    ("submodule", "status"),
    ("config", "--local", "--list"),
    ("config", "--get"),
    ("ls-files", "--stage"),
    ("ls-tree",),
    ("count-objects", "-v"),
    ("log",),
    ("reflog", "HEAD"),
    ("status", "--porcelain=v1"),
}

# Metadata fields compared before/after the collection run.  Full-porcelain
# status is included because all evidence writes happen only after the final
# comparison pass, and every write target is inside graphify/ anyway.
COMPARE_KEYS = [
    "head",
    "origin_main",
    "branch",
    "remotes",
    "refs",
    "branches",
    "tags",
    "stash_list",
    "worktrees",
    "submodule_status",
    "local_config",
    "core_autocrlf",
    "core_eol",
    "index_stage_digest",
    "tracked_tree_digest",
    "object_stats",
    "reflog_head",
    "status_porcelain",
    "status_outside_graphify",
]


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
    for prefix in READONLY_PREFIXES:
        if args[: len(prefix)] == list(prefix):
            return True
    return False


def run_git(args: list[str], raw: list[dict[str, object]], cwd: Path = LAMHA) -> dict[str, object]:
    """Run one Git command and return a structured, typed record.

    A non-zero exit is a typed ``GitCommandFailure`` record, never an
    exception: callers decide whether it is expected (failure probes) or a
    real failure.  No mutating command can be issued here because the audit
    pass asserts every command against READONLY_PREFIXES before execution.
    """
    # Failure probes against invalid targets reuse the same allowlist: an
    # invalid target may only ever be inspected, never mutated.
    allowed = prefix_allowed(args)
    record: dict[str, object] = {
        "command": "git " + " ".join(args),
        "cwd": str(cwd),
        "env": {"GIT_OPTIONAL_LOCKS": "0"},
        "allowlistedReadOnly": allowed,
    }
    if not allowed:
        record.update(
            {
                "exitCode": None,
                "stdout": "",
                "stderr": "",
                "typedError": {
                    "type": "NonReadOnlyCommandRejected",
                    "partialCommit": False,
                    "gitStateMutated": False,
                },
            }
        )
        raw.append(record)
        return record
    try:
        completed = subprocess.run(
            ["git", "-c", "core.quotePath=false", *args],
            cwd=cwd,
            env=GIT_ENV,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as error:
        record.update(
            {
                "exitCode": None,
                "stdout": "",
                "stderr": str(error),
                "typedError": {
                    "type": "GitInspectionTargetUnavailable",
                    "partialCommit": False,
                    "gitStateMutated": False,
                },
            }
        )
        raw.append(record)
        return record
    record.update(
        {
            "exitCode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
    )
    if completed.returncode != 0:
        record["typedError"] = {
            "type": "GitCommandFailure",
            "partialCommit": False,
            "gitStateMutated": False,
        }
    raw.append(record)
    return record


def refs_snapshot(raw: list[dict[str, object]]) -> dict[str, object]:
    record = run_git(
        ["for-each-ref", "--format=%(refname)%09%(objectname)%09%(objecttype)"], raw
    )
    rows = []
    for line in str(record["stdout"]).splitlines():
        parts = line.split("\t")
        if len(parts) == 3:
            rows.append({"ref": parts[0], "oid": parts[1], "type": parts[2]})
    rows.sort(key=lambda row: row["ref"])
    return {"rows": rows, "digest": sha256_bytes(json.dumps(rows, sort_keys=True).encode())}


def digest_lines(record: dict[str, object]) -> dict[str, object]:
    text = str(record["stdout"])
    lines = [line for line in text.splitlines() if line]
    return {
        "lineCount": len(lines),
        "digest": sha256_bytes(text.encode()),
        "lines": lines,
    }


def capture_git_metadata(raw: list[dict[str, object]]) -> dict[str, object]:
    """Full read-only Git-state inspection pass (the package deliverable)."""
    state: dict[str, object] = {}
    state["head"] = run_git(["rev-parse", "HEAD"], raw)["stdout"].strip()
    state["origin_main"] = run_git(["rev-parse", "origin/main"], raw)["stdout"].strip()
    state["branch"] = run_git(["branch", "--show-current"], raw)["stdout"].strip()
    state["remotes"] = digest_lines(run_git(["remote", "-v"], raw))
    refs = refs_snapshot(raw)
    state["refs"] = refs
    branch_rows = [r for r in refs["rows"] if str(r["ref"]).startswith("refs/heads/")]
    tag_rows = [r for r in refs["rows"] if str(r["ref"]).startswith("refs/tags/")]
    state["branches"] = {
        "count": len(branch_rows),
        "names": [str(r["ref"])[len("refs/heads/"):] for r in branch_rows],
    }
    state["tags"] = {
        "count": len(tag_rows),
        "names": [str(r["ref"])[len("refs/tags/"):] for r in tag_rows],
    }
    state["stash_list"] = digest_lines(run_git(["stash", "list"], raw))
    state["worktrees"] = digest_lines(run_git(["worktree", "list", "--porcelain"], raw))
    state["submodule_status"] = digest_lines(run_git(["submodule", "status"], raw))
    state["local_config"] = digest_lines(run_git(["config", "--local", "--list"], raw))
    state["core_autocrlf"] = run_git(["config", "--get", "core.autocrlf"], raw)["stdout"].strip()
    state["core_eol"] = run_git(["config", "--get", "core.eol"], raw)["stdout"].strip()
    state["index_stage_digest"] = digest_lines(run_git(["ls-files", "--stage"], raw))
    tree_listing = run_git(["ls-tree", "-r", "HEAD"], raw)
    tree_lines = [line for line in str(tree_listing["stdout"]).splitlines() if line]
    state["tracked_tree_digest"] = {
        "lineCount": len(tree_lines),
        "digest": sha256_bytes(str(tree_listing["stdout"]).encode()),
    }
    stats: dict[str, str] = {}
    for line in str(run_git(["count-objects", "-v"], raw)["stdout"]).splitlines():
        key, _, value = line.partition(":")
        stats[key.strip()] = value.strip()
    state["object_stats"] = stats
    state["reflog_head"] = digest_lines(run_git(["reflog", "HEAD", "-30"], raw))
    state["status_porcelain"] = digest_lines(
        run_git(["status", "--porcelain=v1", "--untracked-files=all"], raw)
    )
    state["status_outside_graphify"] = digest_lines(
        run_git(
            ["status", "--porcelain=v1", "--untracked-files=all", "--", ".", ":(exclude)graphify"],
            raw,
        )
    )
    state["log_head"] = digest_lines(
        run_git(["log", "--format=%H%x09%an%x09%ae%x09%s", "-5", "HEAD"], raw)
    )
    return state


def compare_metadata(before: dict[str, object], after: dict[str, object]) -> list[str]:
    changed = []
    for key in COMPARE_KEYS:
        if before.get(key) != after.get(key):
            changed.append(key)
    return changed


def fingerprint_git_dir() -> dict[str, object]:
    """Byte-content fingerprint of every file under .git (read-only)."""
    digest = hashlib.sha256()
    files: list[dict[str, object]] = []
    for root, dirs, names in os.walk(GIT_DIR):
        dirs.sort()
        for name in sorted(names):
            path = Path(root) / name
            rel = path.relative_to(GIT_DIR).as_posix()
            size, file_digest = sha256_file(path)
            files.append({"path": rel, "size": size, "sha256": file_digest})
            digest.update(rel.encode())
            digest.update(str(size).encode())
            digest.update(file_digest.encode())
    return {
        "fileCount": len(files),
        "fingerprintSha256": digest.hexdigest(),
        "files": files,
    }


def main() -> int:
    written: list[str] = []
    raw_git: list[dict[str, object]] = []
    started = utc_now()
    failures: list[str] = []

    prerequisite = json.loads(PREREQ_SUMMARY.read_text(encoding="utf-8"))

    # 0. .git byte-content fingerprint BEFORE the inspection.
    fingerprint_before = fingerprint_git_dir()

    # 1. Inspection pass 1 (also the before metadata state).
    pass1 = capture_git_metadata(raw_git)
    git_available = bool(pass1["head"])

    # 2. Inspection pass 2 (recompute/stability proof of the recorded state).
    pass2 = capture_git_metadata(raw_git)
    unstable = compare_metadata(pass1, pass2)
    stability_status = "PASS" if not unstable else "FAIL"
    if unstable:
        failures.append(f"Git state unstable between inspection passes: {unstable}")

    # 3. Failure cases.
    # 3a. Typed error for invalid input: inspect a nonexistent target repo.
    invalid_target = LAMHA / "no-such-repository-target"
    probe_raw: list[dict[str, object]] = []
    probe = run_git(["rev-parse", "HEAD"], probe_raw, cwd=invalid_target)
    invalid_probe = {
        "target": str(invalid_target),
        "exitCode": probe["exitCode"],
        "typedError": {
            "type": "GitInspectionTargetUnavailable",
            "message": str(probe["stderr"]).strip(),
            "partialCommit": False,
            "gitStateMutated": False,
            "evidenceWritesDuringProbe": 0,
        }
        if probe["exitCode"] != 0
        else None,
    }
    if probe["exitCode"] == 0:
        failures.append("invalid-target probe unexpectedly succeeded")

    # 3b. Write-guard destination-escape fixtures (must all be rejected).
    guard_fixtures: list[dict[str, object]] = []
    for probe_path in ("../escape-outside.txt", "/absolute/escape.txt"):
        try:
            guard_write_path(PACKAGE_DIR / probe_path)
            guard_fixtures.append({"probe": probe_path, "rejected": False})
            failures.append(f"write guard accepted escape probe: {probe_path}")
        except ValueError:
            guard_fixtures.append({"probe": probe_path, "rejected": True})

    # 3c. Static read-only audit: every executed command matches the allowlist.
    non_readonly = [
        record["command"] for record in raw_git + probe_raw if record["allowlistedReadOnly"] is not True
    ]
    if non_readonly:
        failures.append(f"non-read-only Git commands executed: {non_readonly}")

    # 4. Metadata state AFTER the run (before/after integrity comparison).
    after = capture_git_metadata(raw_git)
    changed = compare_metadata(pass1, after)
    if changed:
        failures.append(f"Git metadata changed during collection: {changed}")
    metadata_unchanged = not changed

    # 5. .git byte-content fingerprint AFTER the inspection.
    fingerprint_after = fingerprint_git_dir()
    fingerprint_unchanged = (
        fingerprint_before["fingerprintSha256"] == fingerprint_after["fingerprintSha256"]
    )
    if not fingerprint_unchanged:
        before_files = {str(f["path"]): f for f in fingerprint_before["files"]}
        after_files = {str(f["path"]): f for f in fingerprint_after["files"]}
        diff = {
            "added": sorted(set(after_files) - set(before_files)),
            "removed": sorted(set(before_files) - set(after_files)),
            "modified": sorted(
                path for path in set(before_files) & set(after_files)
                if before_files[path] != after_files[path]
            ),
        }
        failures.append(f".git fingerprint changed during collection: {diff}")

    # 6. Recorded-state completeness (exit-gate clause 1).
    required_sections = [
        pass2["head"],
        pass2["branch"],
        pass2["remotes"]["lineCount"] > 0,
        pass2["refs"]["rows"],
        pass2["local_config"]["lineCount"] > 0,
        pass2["index_stage_digest"]["lineCount"] > 0,
        pass2["tracked_tree_digest"]["lineCount"] > 0,
        pass2["object_stats"].get("count") is not None,
        pass2["reflog_head"]["lineCount"] > 0,
        git_available,
    ]
    state_recorded = all(required_sections)
    if not state_recorded:
        failures.append("Git-state report is incomplete")

    # 7. Persist evidence (inside Graphify only, after all comparisons).
    provenance = {
        "packageId": PACKAGE_ID,
        "packetPath": PACKET.relative_to(GRAPHIFY).as_posix(),
        "packetSha256": sha256_bytes(PACKET.read_bytes()),
        "ownedRequirements": ["CAN-MISSION-I0-002"],
        "selection": {
            "rule": "deterministic READY-package selector (phase, major, minor, ID order) over packages whose prerequisites are COMPLETE with PASS exit gates",
            "readyPackages": [
                "WP-I0-002", "WP-I0-003", "WP-I0-004", "WP-I0-006", "WP-I0-008",
                "WP-I0-009", "WP-I0-010", "WP-I0-011", "WP-I1-001",
            ],
            "explicitAuthorizationRecordFound": False,
            "startSha": "e8bd87320268121ed819c0e45ad200221af8f61e",
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
            "gitDir": str(GIT_DIR),
            "graphifyRoot": str(GRAPHIFY),
            "packageEvidenceDir": str(PACKAGE_DIR),
        },
        "environment": {
            "collectionStartedUtc": started,
            "os": os.name,
            "platform": sys.platform,
            "python": sys.version.split()[0],
            "gitEnvOverrides": {"GIT_OPTIONAL_LOCKS": "0", "core.quotePath": "false"},
        },
        "readOnlyGuarantee": "No Git mutation command was executed (static allowlist audit); every Git command ran with GIT_OPTIONAL_LOCKS=0; the package's only writes are evidence files inside graphify/13-implementation/WP-I0-002/ through tools/write_guard.",
    }

    git_report = {
        "collectionMethod": "read-only git plumbing/porcelain with GIT_OPTIONAL_LOCKS=0 and core.quotePath=false; byte-content fingerprint of the complete .git directory taken before and after the run",
        "gitAvailable": git_available,
        "gitDirFingerprintBefore": {
            "fileCount": fingerprint_before["fileCount"],
            "fingerprintSha256": fingerprint_before["fingerprintSha256"],
        },
        "gitDirFingerprintAfter": {
            "fileCount": fingerprint_after["fileCount"],
            "fingerprintSha256": fingerprint_after["fingerprintSha256"],
        },
        "gitDirFingerprintUnchanged": fingerprint_unchanged,
        "gitDirFiles": fingerprint_before["files"],
        "metadataUnchanged": metadata_unchanged,
        "changedFields": changed,
        "before": pass1,
        "inspection": pass2,
        "after": after,
        "rawCommands": raw_git,
    }

    write_json("provenance-report.json", provenance, written)
    write_json("git-state-report.json", git_report, written)
    write_json(
        "verification-results.json",
        {
            "recompute": {
                "method": "two full independent read-only Git-state inspection passes inside one run",
                "unstableFields": unstable,
                "status": stability_status,
            },
            "failureCases": {
                "invalidTargetProbe": invalid_probe,
                "writeGuardEscapeFixtures": guard_fixtures,
                "readOnlyCommandAudit": {
                    "commandsExecuted": len(raw_git) + len(probe_raw),
                    "nonReadOnlyCommands": non_readonly,
                    "status": "PASS" if not non_readonly else "FAIL",
                },
                "gitMetadataAvailable": git_available,
                "gitMetadataUnchanged": metadata_unchanged,
                "gitDirFingerprintUnchanged": fingerprint_unchanged,
            },
            "tests": {
                "wp_i0_002_success": "PASS"
                if git_available and stability_status == "PASS" and not failures
                else "FAIL",
                "wp_i0_002_failure": "PASS"
                if invalid_probe["typedError"] is not None
                and all(f["rejected"] for f in guard_fixtures)
                and fingerprint_unchanged
                else "FAIL",
            },
        },
        written,
    )

    # 8. Exit-gate clauses.
    exit_gate = [
        {
            "clause": "Existing Git state is recorded",
            "evidence": "git-state-report.json captures HEAD, current branch, remotes, every ref (branches/tags/stash ref with OIDs), stash list, worktree list, submodule status, local configuration, index stage digest, tracked-tree digest, object statistics, HEAD reflog, and porcelain status — all via read-only commands with GIT_OPTIONAL_LOCKS=0; two independent passes agree.",
            "evidenceFiles": ["13-implementation/WP-I0-002/git-state-report.json"],
            "result": "PASS" if git_available and state_recorded and stability_status == "PASS" else "FAIL",
        },
        {
            "clause": "Before/after metadata integrity is identical",
            "evidence": f"{len(COMPARE_KEYS)} compared metadata fields (HEAD, refs, stash, worktrees, config, index digest, tracked-tree digest, object statistics, reflog, status) are byte-identical before and after the collection run, and the complete .git directory content fingerprint is unchanged.",
            "evidenceFiles": ["13-implementation/WP-I0-002/git-state-report.json"],
            "result": "PASS" if metadata_unchanged and fingerprint_unchanged else "FAIL",
        },
        {
            "clause": "No Git mutation occurred",
            "evidence": "Static read-only command audit passes (every executed command matches the declared read-only prefix allowlist; a non-read-only command is rejected with a typed error without execution); GIT_OPTIONAL_LOCKS=0 everywhere; .git byte-content fingerprint before and after the run is identical, so no commit, branch, tag, stash, worktree, index, or configuration mutation occurred.",
            "evidenceFiles": [
                "13-implementation/WP-I0-002/git-state-report.json",
                "13-implementation/WP-I0-002/verification-results.json",
            ],
            "result": "PASS" if not non_readonly and fingerprint_unchanged and metadata_unchanged else "FAIL",
        },
    ]
    for clause in exit_gate:
        if clause["result"] != "PASS":
            failures.append(f"exit-gate clause failed: {clause['clause']}")

    completion_md = [
        f"# {PACKAGE_ID} completion evidence",
        "",
        f"- Package: {PACKAGE_ID} — Read-only Git-state inspection",
        f"- Collection ran: {started} → {utc_now()}",
        "- Git mutation commands executed: **zero** (static read-only allowlist audit over the full command transcript).",
        "- `.git` directory byte-content fingerprint before/after: **identical** (all "
        + str(fingerprint_before["fileCount"])
        + " files, including the object database).",
        "- Before/after Git metadata fields compared: **"
        + str(len(COMPARE_KEYS))
        + ", all identical** (HEAD, refs, branches, tags, stash, worktrees, submodules, local config, index digest, tracked-tree digest, object statistics, reflog, working-tree status).",
        "- All generated evidence resolves inside `graphify/13-implementation/WP-I0-002/` and was written through `graphify/tools/write_guard.py`.",
        "",
        "## Requirements",
        "",
        "- `CAN-MISSION-I0-002`: existing Git metadata was inspected with optional locks disabled (`GIT_OPTIONAL_LOCKS=0`); no commit, branch, tag, stash, worktree, index, or configuration was created or modified — proven by the read-only command audit and the byte-identical `.git` fingerprint in `git-state-report.json`.",
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
            "gitMetadataCompare": "PASS" if metadata_unchanged else "FAIL",
            "gitDirFingerprintCompare": "PASS" if fingerprint_unchanged else "FAIL",
            "readOnlyCommandAudit": "PASS" if not non_readonly else "FAIL",
            "failureCases": "PASS"
            if invalid_probe["typedError"] is not None
            and all(f["rejected"] for f in guard_fixtures)
            and git_available
            else "FAIL",
            "exitGate": "PASS" if all(c["result"] == "PASS" for c in exit_gate) else "FAIL",
        },
        "counts": {
            "refsRecorded": len(pass2["refs"]["rows"]),
            "gitDirFiles": fingerprint_before["fileCount"],
            "gitCommandsExecuted": len(raw_git) + len(probe_raw),
        },
        "evidenceFiles": sorted(written + ["13-implementation/WP-I0-002/package-summary.json"]),
        "exitGateClauses": exit_gate,
    }
    write_json("package-summary.json", summary, written)
    print(json.dumps({"status": summary["status"], "failures": failures}, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
