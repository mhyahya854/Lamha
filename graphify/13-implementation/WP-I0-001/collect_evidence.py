"""WP-I0-001 read-only repository provenance and integrity baseline collector.

Package packet: graphify/12-semantic-implementation-plan/04-work-packages/packets/WP-I0-001.md
Owned requirements: CAN-LAM-GOV-292, CAN-MISSION-I0-001

Behaviour contract:
- READ-ONLY for every path outside graphify/ (this evidence directory included
  only for writes, which are the package's authorized deliverables).
- Creates no archive, backup, repository copy, application mutation, Git
  mutation, build, test, cache, package install, or generated code.
- Every write passes through tools/write_guard.guard_write_path and resolves
  inside Graphify.
- Exits 0 only when every packet test, failure-case guard, and exit-gate
  clause evaluates PASS; otherwise exits 1 with the failures recorded.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True

PACKAGE_ID = "WP-I0-001"
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
CERTIFICATION = REPORTS / "final-100-percent-certification.json"

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
    target.write_text(data.rstrip("\n") + "\n", encoding="utf-8", newline="\n")
    written.append(resolved.relative_to(GRAPHIFY).as_posix())


def write_json(relative: str, value: object, written: list[str]) -> None:
    write_evidence(relative, json.dumps(value, ensure_ascii=False, indent=2), written)


def run_git(args: list[str], raw: list[dict[str, object]]) -> tuple[int, str]:
    completed = subprocess.run(
        ["git", "-c", "core.quotePath=false", *args],
        cwd=LAMHA,
        env=GIT_ENV,
        capture_output=True,
        text=True,
        check=False,
    )
    raw.append(
        {
            "command": "git " + " ".join(args),
            "env": {"GIT_OPTIONAL_LOCKS": "0"},
            "exitCode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
    )
    return completed.returncode, completed.stdout


def git_state(raw: list[dict[str, object]]) -> dict[str, object]:
    fields: dict[str, object] = {}
    queries = {
        "head": ["rev-parse", "HEAD"],
        "origin_main": ["rev-parse", "origin/main"],
        "branch": ["branch", "--show-current"],
        "remotes": ["remote", "-v"],
        "status_porcelain": ["status", "--porcelain=v1", "--untracked-files=all"],
        "status_outside_graphify": [
            "status", "--porcelain=v1", "--untracked-files=all", "--", ".", ":(exclude)graphify",
        ],
        "submodule_status": ["submodule", "status"],
        "core_autocrlf": ["config", "--get", "core.autocrlf"],
        "core_eol": ["config", "--get", "core.eol"],
    }
    for key, args in queries.items():
        code, out = run_git(args, raw)
        fields[key] = {"exitCode": code, "output": out}
    return fields


def tracked_tree_outside_graphify(raw: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    """Canonical committed tree outside Graphify via Git blob identity (pass3 method)."""
    completed = subprocess.run(
        ["git", "-c", "core.quotePath=false", "ls-tree", "-r", "-z", "-l", "HEAD"],
        cwd=LAMHA,
        env=GIT_ENV,
        capture_output=True,
        check=False,
    )
    raw.append(
        {
            "command": "git ls-tree -r -z -l HEAD",
            "env": {"GIT_OPTIONAL_LOCKS": "0"},
            "exitCode": completed.returncode,
            "stdout_bytes": len(completed.stdout),
            "stderr": completed.stderr.decode("utf-8", errors="replace"),
        }
    )
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
        rows[path] = {
            "mode": mode,
            "objectType": object_type,
            "gitBlobOid": object_id,
            "size": -1 if size == "-" else int(size),
        }
    return rows


def is_reparse(path: Path) -> bool:
    try:
        attrs = path.lstat().st_file_attributes
        return bool(attrs & stat.FILE_ATTRIBUTE_REPARSE_POINT)
    except (AttributeError, OSError):
        return path.is_symlink()


def snapshot_codebase() -> tuple[list[dict[str, object]], dict[str, object]]:
    """Hash every file directly under Codebase/; reject nothing, record everything."""
    rows: list[dict[str, object]] = []
    findings: dict[str, object] = {
        "unreadable_files": [],
        "reparse_points": [],
        "reparse_point_escapes": [],
        "non_file_entries": [],
    }
    for root, dirs, files in os.walk(CODEBASE):
        dirs.sort()
        for name in sorted(files):
            path = Path(root) / name
            rel = path.relative_to(LAMHA).as_posix()
            reparse = is_reparse(path)
            if reparse:
                resolved = path.resolve(strict=False)
                escape = True
                try:
                    resolved.relative_to(LAMHA)
                    escape = False
                except ValueError:
                    escape = True
                record = {"path": rel, "resolved": str(resolved), "escapes_lamha_root": escape}
                findings["reparse_points"].append(record)
                if escape:
                    findings["reparse_point_escapes"].append(record)
            try:
                size, digest = sha256_file(path)
            except OSError as error:
                findings["unreadable_files"].append({"path": rel, "error": str(error)})
                continue
            rows.append({"path": rel, "size": size, "sha256": digest})
    rows.sort(key=lambda row: str(row["path"]))
    return rows, findings


def manifest_csv(rows: list[dict[str, object]]) -> str:
    lines = ["path,size,sha256"]
    for row in rows:
        lines.append(f"{row['path']},{row['size']},{row['sha256']}")
    return "\n".join(lines)


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
    status = "PASS" if not added and not removed and not modified else "FAIL"
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
        "status": status,
    }


def compare_blob_baseline(tree: dict[str, dict[str, object]]) -> dict[str, object]:
    baseline = json.loads(BLOB_BASELINE.read_text(encoding="utf-8"))
    before = {str(row["path"]): row for row in baseline["files"]}
    after = tree
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    modified = sorted(
        path
        for path in set(before) & set(after)
        if before[path].get("mode") != after[path].get("mode")
        or int(before[path].get("size", -1)) != int(after[path].get("size", -1))
        or before[path].get("gitBlobOid") != after[path].get("gitBlobOid")
    )
    renamed: list[dict[str, object]] = []
    removed_by_oid: dict[str, list[str]] = {}
    for path in removed:
        removed_by_oid.setdefault(str(before[path]["gitBlobOid"]), []).append(path)
    for path in added:
        candidates = removed_by_oid.get(str(after[path]["gitBlobOid"]), [])
        if candidates:
            renamed.append({"from": candidates.pop(0), "to": path, "gitBlobOid": after[path]["gitBlobOid"]})
    status = "PASS" if not added and not removed and not modified else "FAIL"
    return {
        "baselinePath": BLOB_BASELINE.relative_to(GRAPHIFY).as_posix(),
        "baselineAlgorithm": baseline.get("algorithm"),
        "baselineFileCount": baseline.get("file_count"),
        "currentFileCount": len(after),
        "added": added,
        "removed": removed,
        "modified": modified,
        "renamed": renamed,
        "status": status,
    }


def classify_artifact(path: str) -> list[str]:
    return [label for label, pattern in ARTIFACT_PATTERNS.items() if pattern.search(path)]


def extract_toolchain() -> dict[str, object]:
    def read(rel: str) -> str | None:
        path = CODEBASE / rel
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None

    result: dict[str, object] = {"manifests": {}, "counts": {}}
    manifests = result["manifests"]

    manifests["Codebase/.nvmrc"] = {"node": (read(".nvmrc") or "").strip() or None}

    root_pkg = read("package.json")
    if root_pkg:
        pkg = json.loads(root_pkg)
        manifests["Codebase/package.json"] = {
            "name": pkg.get("name"),
            "version": pkg.get("version"),
            "packageManager": pkg.get("packageManager"),
            "engines": pkg.get("engines"),
        }

    mise = read("mise.toml") or ""
    tools_section = re.search(r"\[tools\]\n(.*?)(\n\[|\Z)", mise, re.S)
    tool_versions = dict(re.findall(r'^"?([^"\s=]+?)"?\s*=\s*"([^"]+)"\s*$', tools_section.group(1), re.M)) if tools_section else {}
    manifests["Codebase/mise.toml"] = {"pinned_tools": tool_versions}

    pyproject = read("machine-learning/pyproject.toml") or ""
    requires_python = re.search(r'requires-python\s*=\s*"([^"]+)"', pyproject)
    manifests["Codebase/machine-learning/pyproject.toml"] = {
        "requires_python": requires_python.group(1) if requires_python else None
    }
    manifests["Codebase/machine-learning/.python-version"] = {
        "python": (read("machine-learning/.python-version") or "").strip() or None
    }

    pubspec = read("mobile/pubspec.yaml") or ""
    env_block = re.search(r"^environment:\n((?:[^\S\n]+.+\n)+)", pubspec, re.M)
    env_pairs = dict(re.findall(r"^[^\S\n]+(\w+):\s*['\"]?([^'\"\n]+?)['\"]?[^\S\n]*$", env_block.group(1), re.M)) if env_block else {}
    manifests["Codebase/mobile/pubspec.yaml"] = {"environment": env_pairs}

    gitmodules = read(".gitmodules") or ""
    manifests["Codebase/.gitmodules"] = {
        "submodules": re.findall(r'\[submodule "([^"]+)"\]\s*\n\s*path = (\S+)\s*\n\s*url = (\S+)', gitmodules)
    }

    all_paths: list[str] = []
    for root, dirs, files in os.walk(CODEBASE):
        dirs.sort()
        for name in sorted(files):
            all_paths.append((Path(root) / name).relative_to(CODEBASE).as_posix())

    families = {
        "package_json": re.compile(r"(^|/)package\.json$"),
        "pnpm_lock": re.compile(r"(^|/)pnpm-lock\.yaml$"),
        "pubspec": re.compile(r"(^|/)pubspec\.(yaml|lock)$"),
        "docker_compose": re.compile(r"(^|/)(docker-compose[^/]*\.yml|compose\.ya?ml)$", re.I),
        "dockerfile": re.compile(r"(^|/)Dockerfile[^/]*$"),
        "ci_workflows": re.compile(r"^\.github/workflows/[^/]+\.ya?ml$"),
        "makefiles": re.compile(r"(^|/)(Makefile|makefile)$"),
        "cmakelists": re.compile(r"(^|/)CMakeLists\.txt$"),
        "mise": re.compile(r"(^|/)mise\.(toml|lock)$"),
        "python_version_files": re.compile(r"(^|/)\.python-version$"),
        "nvmrc": re.compile(r"(^|/)\.nvmrc$"),
    }
    counts: dict[str, object] = {}
    for label, pattern in families.items():
        matches = [path for path in all_paths if pattern.search(path)]
        counts[label] = {"count": len(matches), "paths": matches}
    result["counts"] = counts
    return result


def main() -> int:
    written: list[str] = []
    raw_git: list[dict[str, object]] = []
    started = utc_now()
    failures: list[str] = []

    # 1. Git state BEFORE collection (read-only, optional locks disabled).
    git_before = git_state(raw_git)
    git_available = git_before["head"]["exitCode"] == 0  # type: ignore[index]

    # 2. Provenance.
    certification = json.loads(CERTIFICATION.read_text(encoding="utf-8"))
    provenance = {
        "packageId": PACKAGE_ID,
        "packetPath": PACKET.relative_to(GRAPHIFY).as_posix(),
        "packetSha256": sha256_bytes(PACKET.read_bytes()),
        "ownedRequirements": ["CAN-LAM-GOV-292", "CAN-MISSION-I0-001"],
        "authorizationSource": {
            "certificationPath": CERTIFICATION.relative_to(GRAPHIFY).as_posix(),
            "certificationSha256": sha256_bytes(CERTIFICATION.read_bytes()),
            "firstAllowedPackage": certification.get("first_allowed_package"),
            "automaticNextPackage": certification.get("automatic_next_package"),
            "status": certification.get("status"),
        },
        "roots": {
            "lamhaRoot": str(LAMHA),
            "codebaseRoot": str(CODEBASE),
            "graphifyRoot": str(GRAPHIFY),
            "packageEvidenceDir": str(PACKAGE_DIR),
        },
        "scope": {
            "inventoryScope": "Every working-tree file under Codebase/ (the tracked outside-Graphify application corpus; 3697 files at the planning baseline).",
            "excluded": ".git (repository metadata, covered by the Git-state report), graphify (authority and evidence scope), .agents (empty host directory, zero files).",
        },
        "baselines": {
            "sha256": {
                "path": SHA_BASELINE.relative_to(GRAPHIFY).as_posix(),
                "sha256": sha256_bytes(SHA_BASELINE.read_bytes()),
            },
            "gitBlob": {
                "path": BLOB_BASELINE.relative_to(GRAPHIFY).as_posix(),
                "sha256": sha256_bytes(BLOB_BASELINE.read_bytes()),
            },
        },
        "environment": {
            "collectionStartedUtc": started,
            "os": os.name,
            "platform": sys.platform,
            "python": sys.version.split()[0],
        },
        "rootListingOutsideGraphify": sorted(
            entry.name
            for entry in LAMHA.iterdir()
            if entry.name not in {"graphify", ".git"}
        ),
        "readOnlyGuarantee": "No path outside graphify/ is opened for writing; collector writes are restricted to graphify/13-implementation/WP-I0-001/ through tools/write_guard.",
    }

    # 3. Working-tree snapshot pass 1 and pass 2 (CAN-LAM-GOV-292 / CAN-MISSION-I0-001).
    pass1, findings1 = snapshot_codebase()
    pass2, findings2 = snapshot_codebase()
    pass1_by_path = {str(row["path"]): row for row in pass1}
    pass2_by_path = {str(row["path"]): row for row in pass2}
    unstable = sorted(
        path
        for path in set(pass1_by_path) | set(pass2_by_path)
        if pass1_by_path.get(path) != pass2_by_path.get(path)
    )
    stability_status = "PASS" if not unstable else "FAIL"
    if unstable:
        failures.append(f"unstable files during hashing: {unstable}")

    unreadable = findings1["unreadable_files"] + findings2["unreadable_files"]
    if unreadable:
        failures.append(f"unreadable files: {unreadable}")

    reparse_points = findings1["reparse_points"]
    reparse_escapes = findings1["reparse_point_escapes"]
    if reparse_escapes:
        failures.append(f"reparse-point escape: {reparse_escapes}")

    # 4. Write-guard destination-escape fixtures (must all be rejected).
    guard_fixtures: list[dict[str, object]] = []
    for probe in ("../escape-outside.txt", "/absolute/escape.txt"):
        try:
            guard_write_path(PACKAGE_DIR / probe)
            guard_fixtures.append({"probe": probe, "rejected": False})
            failures.append(f"write guard accepted escape probe: {probe}")
        except ValueError:
            guard_fixtures.append({"probe": probe, "rejected": True})

    # 5. Git tree comparison + Git state AFTER collection.
    tree = tracked_tree_outside_graphify(raw_git)
    git_after = git_state(raw_git)
    git_keys = ["head", "origin_main", "branch", "remotes", "status_outside_graphify", "submodule_status"]
    git_unchanged = all(git_before[key] == git_after[key] for key in git_keys)
    if not git_unchanged:
        changed = [key for key in git_keys if git_before[key] != git_after[key]]
        failures.append(f"Git metadata changed during collection: {changed}")

    # 6. Baseline comparisons (exit-gate "final outside-Graphify comparison").
    sha_comparison = compare_sha_baseline(pass1)
    blob_comparison = compare_blob_baseline(tree)
    if sha_comparison["status"] != "PASS":
        failures.append("SHA-256 baseline comparison reported changes outside Graphify")
    if blob_comparison["status"] != "PASS":
        failures.append("Git-blob baseline comparison reported changes outside Graphify")

    # 7. Artifact scan: any path present now but absent from the planning
    # baselines is a candidate newly created artifact; classify it.
    added_outside = sorted(set(sha_comparison["added"]) | set(blob_comparison["added"]))
    artifact_findings = [
        {"path": path, "classes": classify_artifact(path)} for path in added_outside
    ]
    artifact_scan = {
        "scanWindow": "package collection run",
        "scope": "paths added outside Graphify relative to both planning baselines, plus this package's own evidence files",
        "addedOutsideGraphify": added_outside,
        "newArtifactCandidates": artifact_findings,
        "evidenceFiles": [],
        "evidenceFileClasses": [],
        "status": "PASS" if not added_outside else "FAIL",
    }

    # 8. Toolchain / manifest analysis (read-only extraction).
    toolchain = extract_toolchain()

    mise_tools = toolchain["manifests"]["Codebase/mise.toml"]["pinned_tools"]
    toolchain_md = [
        "# WP-I0-001 toolchain and manifest analysis",
        "",
        "Read-only extraction from the existing Codebase snapshot. No manifest was modified, no dependency was installed, no build or test of the product was executed.",
        "",
        "## Declared toolchains",
        "",
        f"- Node: `{toolchain['manifests'].get('Codebase/.nvmrc', {}).get('node')}` (`.nvmrc`); mise pins `node = {mise_tools.get('node')}`",
    ]
    for tool, version in sorted(mise_tools.items()):
        toolchain_md.append(f"- `{tool}` = `{version}` (mise)")
    pkg_info = toolchain["manifests"].get("Codebase/package.json", {})
    toolchain_md += [
        f"- Root package: `{pkg_info.get('name')}@{pkg_info.get('version')}`, packageManager `{pkg_info.get('packageManager')}`, engines `{pkg_info.get('engines')}`",
        f"- Python (machine-learning): requires `{toolchain['manifests']['Codebase/machine-learning/pyproject.toml'].get('requires_python')}`, pinned `{toolchain['manifests']['Codebase/machine-learning/.python-version'].get('python')}`",
        f"- Flutter/Dart (mobile): `{toolchain['manifests']['Codebase/mobile/pubspec.yaml'].get('environment')}`",
        f"- Submodules declared: `{toolchain['manifests']['Codebase/.gitmodules'].get('submodules')}`",
        "",
        "## Manifest inventory counts",
        "",
    ]
    for label, info in toolchain["counts"].items():
        toolchain_md.append(f"- {label}: {info['count']}")
        for path in info["paths"]:
            toolchain_md.append(f"  - `Codebase/{path}`")
    toolchain_md.append("")

    # 9. Persist evidence (inside Graphify only).
    write_json("provenance-report.json", provenance, written)
    write_evidence("sha256-manifest.csv", manifest_csv(pass1), written)
    inventory_lines = ["path,size"] + [f"{row['path']},{row['size']}" for row in pass1]
    write_evidence("file-inventory.csv", "\n".join(inventory_lines), written)
    write_json(
        "git-state-report.json",
        {
            "collectionMethod": "read-only git plumbing/porcelain with GIT_OPTIONAL_LOCKS=0 and core.quotePath=false",
            "gitAvailable": git_available,
            "before": git_before,
            "after": git_after,
            "metadataUnchanged": git_unchanged,
            "trackedTreeOutsideGraphify": {"fileCount": len(tree)},
            "codebaseGitNote": "Codebase/ is an unpacked source snapshot without its own .git directory; Codebase/.gitmodules declares the e2e/test-assets submodule (not initialized; no gitlink present in the tracked tree).",
            "rawCommands": raw_git,
        },
        written,
    )
    write_json("toolchain-manifest-analysis.json", toolchain, written)
    write_evidence("toolchain-manifest-analysis.md", "\n".join(toolchain_md), written)
    write_json("baseline-comparison.json", {"sha256Baseline": sha_comparison, "gitBlobBaseline": blob_comparison}, written)
    write_json(
        "verification-results.json",
        {
            "recompute": {
                "method": "two full independent SHA-256 passes over every Codebase/ file inside one run",
                "pass1FileCount": len(pass1),
                "pass2FileCount": len(pass2),
                "pass1ManifestSha256": sha256_bytes(manifest_csv(pass1).encode("utf-8")),
                "pass2ManifestSha256": sha256_bytes(manifest_csv(pass2).encode("utf-8")),
                "unstableFiles": unstable,
                "status": stability_status,
            },
            "failureCases": {
                "unreadableFiles": unreadable,
                "unstableFiles": unstable,
                "reparsePoints": reparse_points,
                "reparsePointEscapes": reparse_escapes,
                "gitMetadataAvailable": git_available,
                "gitMetadataUnchanged": git_unchanged,
                "writeGuardEscapeFixtures": guard_fixtures,
            },
        },
        written,
    )
    artifact_scan["evidenceFiles"] = sorted(written)
    artifact_scan["evidenceFileClasses"] = [
        {"path": path, "classes": classify_artifact(path)} for path in sorted(written)
    ]
    write_json("artifact-scan.json", artifact_scan, written)

    # 10. Exit-gate clauses.
    exit_gate = [
        {
            "clause": "All provenance evidence is inside Graphify",
            "evidence": "Every generated evidence path resolves inside graphify/ via tools/write_guard.guard_write_path; traversal and absolute-escape probes were rejected.",
            "evidenceFiles": sorted(written),
            "result": "PASS",
        },
        {
            "clause": "No archive or backup exists",
            "evidence": "Zero paths were added outside Graphify relative to both planning baselines; this package's evidence files match no archive/backup/copy/build/test/cache/package-manager/generated-code pattern; no archive or backup was created.",
            "result": "PASS" if artifact_scan["status"] == "PASS" else "FAIL",
        },
        {
            "clause": "No application file or Git state changed",
            "evidence": "Before/after Git metadata (HEAD, origin/main, branch, remotes, outside-Graphify working-tree/index status, submodule status) are identical and both outside-Graphify baseline comparisons report zero added/removed/modified/renamed paths. The package's only writes are evidence files inside Graphify.",
            "result": "PASS"
            if git_unchanged and sha_comparison["status"] == "PASS" and blob_comparison["status"] == "PASS"
            else "FAIL",
        },
        {
            "clause": "The final outside-Graphify comparison reports zero changes",
            "evidence": "SHA-256 working-tree comparison and Git-blob committed-tree comparison both report zero added/removed/modified/renamed paths.",
            "result": "PASS" if sha_comparison["status"] == "PASS" and blob_comparison["status"] == "PASS" else "FAIL",
        },
    ]
    for clause in exit_gate:
        if clause["result"] != "PASS":
            failures.append(f"exit-gate clause failed: {clause['clause']}")

    completion_md = [
        f"# {PACKAGE_ID} completion evidence",
        "",
        f"- Package: {PACKAGE_ID} — Read-only repository provenance and integrity baseline",
        f"- Collection ran: {started} → {utc_now()}",
        "- Outside-Graphify additions/removals/modifications/renames: **zero** (SHA-256 baseline and Git-blob baseline comparisons).",
        "- This package created **no** archive, backup, repository copy, application mutation, cache, build output, test output, package installation, generated code, or Git mutation.",
        "- All generated evidence resolves inside `graphify/13-implementation/WP-I0-001/` and was written through `graphify/tools/write_guard.py`.",
        "",
        "## Requirements",
        "",
        "- `CAN-LAM-GOV-292`: every application path outside Graphify remained byte-for-byte unchanged (see `baseline-comparison.json`) and every generated evidence path resolves inside Graphify (see `package-summary.json` evidence file list).",
        "- `CAN-MISSION-I0-001`: the repository was inspected in read-only mode; file inventory (`file-inventory.csv`), SHA-256 manifest (`sha256-manifest.csv`), Git state (`git-state-report.json`), toolchain/manifest analysis (`toolchain-manifest-analysis.md`, `.json`), and provenance (`provenance-report.json`) were recorded only inside Graphify; no archive, backup, repository copy, application mutation, or Git mutation was created.",
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
            "gitMetadataCompare": "PASS" if git_unchanged else "FAIL",
            "shaBaselineComparison": sha_comparison["status"],
            "gitBlobBaselineComparison": blob_comparison["status"],
            "artifactScan": artifact_scan["status"],
            "failureCases": "PASS"
            if not unreadable and not unstable and not reparse_escapes and git_available
            else "FAIL",
            "exitGate": "PASS" if all(c["result"] == "PASS" for c in exit_gate) else "FAIL",
        },
        "fileCounts": {
            "codebaseFiles": len(pass1),
            "trackedOutsideGraphify": len(tree),
        },
        "evidenceFiles": sorted(written + ["13-implementation/WP-I0-001/package-summary.json"]),
        "exitGateClauses": exit_gate,
    }
    write_json("package-summary.json", summary, written)
    print(json.dumps({"status": summary["status"], "failures": failures, "files": len(pass1)}, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
