"""Pass 2C external read-only integrity snapshot.

Snapshots every Lamha file outside Graphify except root ``.git`` metadata and
compares the baseline taken at the start of Pass 2C with the final snapshot.
All outputs stay inside Graphify and use the reviewed write guard.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True

GRAPHIFY = Path(__file__).resolve().parents[1]
LAMHA = GRAPHIFY.parent.resolve(strict=True)
REPORTS = GRAPHIFY / "12-semantic-implementation-plan" / "13-reports"
SOURCE_REVIEWS = GRAPHIFY / "semantic-plan-source" / "reviews"
BASELINE = REPORTS / "pass2c-external-readonly-baseline.json"
FINAL = REPORTS / "pass2c-external-readonly-final.json"
REPORT = REPORTS / "pass2c-external-integrity-report.md"

sys.path.insert(0, str(GRAPHIFY / "tools"))
from write_guard import write_json, write_text  # noqa: E402


def digest(path: Path) -> dict[str, object]:
    hasher = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(block)
            hasher.update(block)
    return {"size": size, "sha256": hasher.hexdigest()}


def snapshot() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for path in sorted(LAMHA.rglob("*")):
        if not path.is_file():
            continue
        try:
            path.resolve(strict=True).relative_to(GRAPHIFY)
            continue
        except ValueError:
            pass
        relative = path.relative_to(LAMHA)
        if relative.parts and relative.parts[0] == ".git":
            continue
        value = digest(path)
        rows.append({"path": relative.as_posix(), "size": value["size"], "sha256": value["sha256"]})
    return rows


def main() -> int:
    files = snapshot()
    if not BASELINE.exists():
        baseline = {
            "schema_version": 1,
            "project_root": str(LAMHA),
            "graphify_root": str(GRAPHIFY),
            "algorithm": "SHA-256",
            "exclusion": "Root .git metadata directory excluded as Git bookkeeping; all other files outside Graphify are included.",
            "file_count": len(files),
            "byte_count": sum(int(row["size"]) for row in files),
            "files": files,
        }
        write_json(BASELINE, baseline)
        write_json(SOURCE_REVIEWS / "pass2c-external-readonly-baseline.json", baseline)
        print(json.dumps({"mode": "pass2c-baseline", "file_count": len(files), "byte_count": baseline["byte_count"]}, indent=2))
        return 0

    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    before = {row["path"]: row for row in baseline["files"]}
    after = {row["path"]: row for row in files}
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    modified = sorted(
        path for path in set(before) & set(after)
        if before[path]["size"] != after[path]["size"] or before[path]["sha256"] != after[path]["sha256"]
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
    final = {
        "schemaVersion": "1.0",
        "verifiedAt": datetime.now(timezone.utc).isoformat(),
        "baselinePath": BASELINE.relative_to(GRAPHIFY).as_posix(),
        "lamhaRoot": str(LAMHA),
        "graphifyRoot": str(GRAPHIFY),
        "readOnlyScope": "Every Lamha file outside Graphify except the root .git metadata directory",
        "files": files,
        "fileCount": len(files),
        "byteCount": sum(int(row["size"]) for row in files),
        "comparison": {"status": status, "added": added, "removed": removed, "modified": modified, "renamed": renamed},
    }
    write_json(FINAL, final)
    write_json(SOURCE_REVIEWS / "pass2c-external-readonly-final.json", final)
    write_text(REPORT, f"""# Pass 2C external read-only integrity report

- Baseline files: {baseline['file_count']}
- Final files: {len(files)}
- Baseline bytes: {baseline['byte_count']}
- Final bytes: {final['byteCount']}
- Added outside Graphify: {len(added)}
- Removed outside Graphify: {len(removed)}
- Modified outside Graphify: {len(modified)}
- Rename pairs detected: {len(renamed)}
- Result: **{status}**

Scope excludes only the root `.git` metadata directory. Zero differences proves
Pass 2C did not create or alter project files outside Graphify.
""")
    write_text(SOURCE_REVIEWS / "pass2c-external-integrity-report.md", (REPORT.read_text(encoding="utf-8")))
    print(json.dumps({
        "mode": "pass2c-verify", "status": status, "baselineFileCount": baseline["file_count"],
        "finalFileCount": len(files), "added": len(added), "removed": len(removed),
        "modified": len(modified), "renamed": len(renamed),
    }, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
