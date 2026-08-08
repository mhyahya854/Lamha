"""Pass 3 external read-only integrity snapshot and comparison.

The committed Git tree is the byte authority.  Hashing working-tree bytes is
not portable because Git may materialize text files as LF or CRLF according to
``core.autocrlf``.  This tool therefore records canonical blob object IDs and
blob sizes, then separately rejects any working-tree change outside Graphify.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True

GRAPHIFY = Path(__file__).resolve().parents[1]
LAMHA = GRAPHIFY.parent.resolve(strict=True)
REPORTS = GRAPHIFY / "12-semantic-implementation-plan" / "13-reports"
SOURCE_REVIEWS = GRAPHIFY / "semantic-plan-source" / "reviews"
BASELINE = REPORTS / "pass3-external-readonly-baseline.json"
FINAL = REPORTS / "pass3-external-readonly-final.json"
REPORT = REPORTS / "pass3-external-integrity-report.md"

SCHEMA_VERSION = 2
ALGORITHM = "Git blob object identity and canonical blob size"
SCOPE = "Every tracked Lamha path outside Graphify; uncommitted and untracked paths outside Graphify are rejected"

sys.path.insert(0, str(GRAPHIFY / "tools"))
from write_guard import write_json, write_text  # noqa: E402


def git(*args: str) -> bytes:
    return subprocess.run(
        ["git", "-c", "core.quotePath=false", *args],
        cwd=LAMHA,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout


def snapshot() -> list[dict[str, object]]:
    """Return the canonical committed tree outside Graphify.

    ``ls-tree`` reports blob IDs and sizes from Git's object database, so this
    evidence is independent of checkout path, username, and EOL conversion.
    """
    rows: list[dict[str, object]] = []
    for raw in git("ls-tree", "-r", "-z", "-l", "HEAD").split(b"\0"):
        if not raw:
            continue
        metadata, raw_path = raw.split(b"\t", 1)
        mode, object_type, object_id, size = metadata.decode("ascii").split()
        path = raw_path.decode("utf-8", errors="surrogateescape")
        if path == "graphify" or path.startswith("graphify/"):
            continue
        if object_type != "blob":
            raise RuntimeError(f"unsupported external Git object type for {path}: {object_type}")
        rows.append({"path": path, "mode": mode, "size": int(size), "gitBlobOid": object_id})
    return sorted(rows, key=lambda row: str(row["path"]))


def working_tree_changes() -> dict[str, list[object]]:
    """Classify every non-Graphify working-tree/index change."""
    payload = git(
        "status", "--porcelain=v1", "-z", "--untracked-files=all",
        "--", ".", ":(exclude)graphify",
    ).split(b"\0")
    result: dict[str, list[object]] = {"added": [], "removed": [], "modified": [], "renamed": []}
    index = 0
    while index < len(payload):
        raw = payload[index]
        index += 1
        if not raw:
            continue
        status = raw[:2].decode("ascii")
        path = raw[3:].decode("utf-8", errors="surrogateescape")
        if "R" in status or "C" in status:
            if index >= len(payload) or not payload[index]:
                raise RuntimeError(f"malformed Git rename status for {path}")
            previous = payload[index].decode("utf-8", errors="surrogateescape")
            index += 1
            result["renamed"].append({"from": previous, "to": path})
        elif status == "??" or "A" in status:
            result["added"].append(path)
        elif "D" in status:
            result["removed"].append(path)
        else:
            result["modified"].append(path)
    for key in ("added", "removed", "modified"):
        result[key] = sorted(set(result[key]))
    result["renamed"] = sorted(result["renamed"], key=lambda row: (str(row["from"]), str(row["to"])))
    return result


def baseline_record(files: list[dict[str, object]]) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "project_root": ".",
        "graphify_root": "graphify",
        "algorithm": ALGORITHM,
        "scope": SCOPE,
        "exclusion": "Graphify is the writable planning scope; root .git metadata is repository state rather than a tracked product path.",
        "file_count": len(files),
        "byte_count": sum(int(row["size"]) for row in files),
        "files": files,
    }


def main() -> int:
    files = snapshot()
    existing = json.loads(BASELINE.read_text(encoding="utf-8")) if BASELINE.exists() else None
    if not isinstance(existing, dict) or existing.get("schema_version") != SCHEMA_VERSION:
        baseline = baseline_record(files)
        write_json(BASELINE, baseline)
        write_json(SOURCE_REVIEWS / "pass3-external-readonly-baseline.json", baseline)
        print(json.dumps({"mode": "pass3-baseline", "schemaVersion": SCHEMA_VERSION, "file_count": len(files), "byte_count": baseline["byte_count"]}, indent=2))
        return 0

    baseline = existing
    before = {row["path"]: row for row in baseline["files"]}
    after = {row["path"]: row for row in files}
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    modified = sorted(
        path for path in set(before) & set(after)
        if before[path].get("mode") != after[path].get("mode")
        or before[path].get("size") != after[path].get("size")
        or before[path].get("gitBlobOid") != after[path].get("gitBlobOid")
    )
    working = working_tree_changes()
    added = sorted(set(added) | set(working["added"]))
    removed = sorted(set(removed) | set(working["removed"]))
    modified = sorted(set(modified) | set(working["modified"]))
    renamed = working["renamed"]
    status = "PASS" if not added and not removed and not modified and not renamed else "FAIL"
    final = {
        "schemaVersion": "2.0",
        "baselinePath": BASELINE.relative_to(GRAPHIFY).as_posix(),
        "lamhaRoot": ".",
        "graphifyRoot": "graphify",
        "algorithm": ALGORITHM,
        "readOnlyScope": SCOPE,
        "files": files,
        "fileCount": len(files),
        "byteCount": sum(int(row["size"]) for row in files),
        "comparison": {"status": status, "added": added, "removed": removed, "modified": modified, "renamed": renamed},
    }
    write_json(FINAL, final)
    write_json(SOURCE_REVIEWS / "pass3-external-readonly-final.json", final)
    write_text(REPORT, f"""# Pass 3 external read-only integrity report

- Authority: canonical Git blob identities plus a separate working-tree/index check
- Baseline files: {baseline['file_count']}
- Final files: {len(files)}
- Added outside Graphify: {len(added)}
- Removed outside Graphify: {len(removed)}
- Modified outside Graphify: {len(modified)}
- Renamed outside Graphify: {len(renamed)}
- Result: **{status}**
""")
    write_text(SOURCE_REVIEWS / "pass3-external-integrity-report.md", REPORT.read_text(encoding="utf-8"))
    print(json.dumps({"mode": "pass3-verify", "schemaVersion": SCHEMA_VERSION, "status": status, "baselineFileCount": baseline["file_count"], "finalFileCount": len(files), "added": len(added), "removed": len(removed), "modified": len(modified), "renamed": len(renamed)}, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
