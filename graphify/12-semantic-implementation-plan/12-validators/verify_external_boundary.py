"""Compare the final non-Graphify tree with the immutable planning baseline."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


PLAN = Path(__file__).resolve().parents[1]
GRAPHIFY = PLAN.parent.resolve(strict=True)
BASELINE_PATH = PLAN / "13-reports" / "external-readonly-baseline.json"
sys.path.insert(0, str(GRAPHIFY))
from tools.write_guard import guard_write_path  # noqa: E402


def safe_write_path(path: Path) -> Path:
    return guard_write_path(path)


def digest(path: Path) -> dict[str, object]:
    hasher = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(block)
            hasher.update(block)
    return {"bytes": size, "sha256": hasher.hexdigest()}


def snapshot(lamha_root: Path, graphify_root: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for path in sorted(lamha_root.rglob("*")):
        if not path.is_file():
            continue
        try:
            path.resolve(strict=True).relative_to(graphify_root)
            continue
        except ValueError:
            pass
        value = digest(path)
        rows.append({"path": path.relative_to(lamha_root).as_posix(), "size": value["bytes"], "sha256": value["sha256"]})
    return rows


def update_manifest() -> None:
    rows = []
    for path in sorted(PLAN.rglob("*")):
        if path.is_file() and path.name != "PLAN-MANIFEST.json":
            data = path.read_bytes()
            rows.append({"path": path.relative_to(PLAN).as_posix(), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    manifest = {
        "generator": "graphify/build_semantic_plan.py", "semanticSource": "graphify/semantic-plan-source",
        "deterministic": True, "evidenceFinalized": True, "files": rows,
    }
    safe_write_path(PLAN / "PLAN-MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    lamha_root = Path(baseline["project_root"]).resolve(strict=True)
    baseline_graphify = Path(baseline["graphify_root"]).resolve(strict=True)
    if baseline_graphify != GRAPHIFY or baseline_graphify.parent != lamha_root:
        raise ValueError("baseline roots do not match the resolved Lamha/Graphify boundary")

    files = snapshot(lamha_root, GRAPHIFY)
    before = {row["path"]: row for row in baseline["files"]}
    after = {row["path"]: row for row in files}
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    modified = sorted(path for path in set(before) & set(after) if before[path]["size"] != after[path]["size"] or before[path]["sha256"] != after[path]["sha256"])
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
        "schemaVersion": "1.0", "verifiedAt": datetime.now(timezone.utc).isoformat(),
        "baselinePath": BASELINE_PATH.relative_to(GRAPHIFY).as_posix(),
        "lamhaRoot": str(lamha_root), "graphifyRoot": str(GRAPHIFY),
        "readOnlyScope": "Every Lamha file outside Graphify", "files": files,
        "fileCount": len(files), "byteCount": sum(int(row["size"]) for row in files),
        "comparison": {"status": status, "added": added, "removed": removed, "modified": modified, "renamed": renamed},
    }
    final_path = safe_write_path(PLAN / "13-reports" / "external-readonly-final.json")
    final_path.write_text(json.dumps(final, indent=2) + "\n", encoding="utf-8", newline="\n")
    report = f"""# External read-only integrity report

- Baseline files: {baseline['file_count']}
- Final files: {len(files)}
- Baseline bytes: {sum(int(row['size']) for row in baseline['files'])}
- Final bytes: {final['byteCount']}
- Added outside Graphify: {len(added)}
- Removed outside Graphify: {len(removed)}
- Modified outside Graphify: {len(modified)}
- Rename pairs detected: {len(renamed)}
- Result: **{status}**

Zero differences proves this planning run did not create a backup or alter application files outside Graphify.
"""
    safe_write_path(PLAN / "13-reports" / "external-integrity-report.md").write_text(report, encoding="utf-8", newline="\n")
    update_manifest()
    print(json.dumps({"status": status, "baselineFileCount": baseline["file_count"], "finalFileCount": len(files), "added": len(added), "removed": len(removed), "modified": len(modified), "renamed": len(renamed)}, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
