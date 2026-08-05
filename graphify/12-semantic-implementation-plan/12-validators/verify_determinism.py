"""Render twice and prove byte-identical deterministic plan output."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path


sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
PLAN = HERE.parent
GRAPHIFY = PLAN.parent
BUILDER = GRAPHIFY / "build_semantic_plan.py"
SPEC = importlib.util.spec_from_file_location("lamha_validator", HERE / "validate_plan.py")
validator = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(validator)


def build() -> tuple[str, dict[str, str]]:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["TEMP"] = str(PLAN / "13-reports")
    environment["TMP"] = environment["TEMP"]
    completed = subprocess.run([sys.executable, "-B", str(BUILDER)], cwd=GRAPHIFY, env=environment, capture_output=True, text=True, check=False)
    if completed.returncode:
        raise RuntimeError(completed.stderr or completed.stdout)
    manifest = PLAN / "PLAN-MANIFEST.json"
    data = manifest.read_bytes()
    document = json.loads(data)
    return hashlib.sha256(data).hexdigest(), {row["path"]: row["sha256"] for row in document["files"]}


def main() -> int:
    first_hash, first_files = build()
    second_hash, second_files = build()
    identical = first_hash == second_hash and first_files == second_files
    result = {
        "status": "PASS" if identical else "FAIL", "renderCount": 2,
        "firstManifestSha256": first_hash, "secondManifestSha256": second_hash,
        "fileHashesIdentical": first_files == second_files, "manifestIdentical": first_hash == second_hash,
    }
    path = validator.safe_write_path(HERE / "determinism-results.json")
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, indent=2))
    return 0 if identical else 1


if __name__ == "__main__":
    raise SystemExit(main())
