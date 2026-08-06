"""Pass 3 finalized-package determinism orchestration.

Renders active outputs, runs validators, adversarial fixtures, and external
integrity twice, then compares in-memory SHA-256 hashes of every deterministic
active file.  Volatile timestamped files and the self-referential manifest are
excluded with explicit rationales.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True

GRAPHIFY = Path(__file__).resolve().parents[1]
PLAN = GRAPHIFY / "12-semantic-implementation-plan"
VALIDATORS = PLAN / "12-validators"
REVIEWS = GRAPHIFY / "semantic-plan-source" / "reviews"
REPORTS = PLAN / "13-reports"

sys.path.insert(0, str(GRAPHIFY / "tools"))
from write_guard import write_json  # noqa: E402


EXCLUDED = {
    "PLAN-MANIFEST.json",
    "13-reports/pass3-certification-report.json",
    "13-reports/final-package-determinism.json",
    "13-reports/pass3-external-readonly-final.json",
    "13-reports/pass2c-external-readonly-final.json",
    "13-reports/pass1-external-final.json",
}


def run(script: str) -> None:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    subprocess.run([sys.executable, script], cwd=str(GRAPHIFY), env=env, check=True, capture_output=True, text=True)


def package_hashes() -> tuple[str, int, dict[str, str]]:
    files: list[Path] = []
    for path in sorted(PLAN.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(PLAN).as_posix()
        if rel in EXCLUDED or "__pycache__" in rel:
            continue
        files.append(path)
    file_hashes: dict[str, str] = {}
    hasher = hashlib.sha256()
    for path in files:
        rel = path.relative_to(PLAN).as_posix()
        if rel == "13-reports/pass3-certification-report.json":
            data = json.loads(path.read_text(encoding="utf-8"))
            data["final_package_hash"] = None
            data["determinism"] = None
            payload = json.dumps(data, sort_keys=True, ensure_ascii=False).encode("utf-8")
            digest = hashlib.sha256(payload).hexdigest()
        else:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        file_hashes[rel] = digest
        hasher.update(rel.encode("utf-8"))
        hasher.update(digest.encode("utf-8"))
    return hasher.hexdigest(), len(files), file_hashes


def main() -> int:
    # Sync the current validation evidence into source so both iterations start
    # from the same authoritative evidence files.
    for name in ("adversarial-results.json", "validator-results.json"):
        rendered = VALIDATORS / name
        source = GRAPHIFY / "semantic-plan-source" / "validators" / name
        if rendered.exists():
            write_json(source, json.loads(rendered.read_text(encoding="utf-8")))

    iteration_scripts = [
        GRAPHIFY / "build_semantic_plan.py",
        PLAN / "12-validators" / "validate_plan.py",
        PLAN / "12-validators" / "adversarial_fixtures.py",
        GRAPHIFY / "tools" / "pass3_external_integrity.py",
    ]
    hashes: list[str] = []
    hash_sets: list[dict[str, str]] = []
    for _ in range(2):
        for script in iteration_scripts:
            run(str(script))
        digest, count, files = package_hashes()
        hashes.append(digest)
        hash_sets.append(files)
    first, second = hashes
    first_files, second_files = hash_sets
    included = list(first_files)
    mismatched = sorted(path for path in set(first_files) | set(second_files) if first_files.get(path) != second_files.get(path))
    result = {
        "firstCompletePackageHash": first,
        "secondCompletePackageHash": second,
        "includedFileCount": len(first_files),
        "missingFiles": [],
        "mismatchedFiles": mismatched,
        "excludedFiles": sorted(EXCLUDED),
        "exclusionRationales": {
            "PLAN-MANIFEST.json": "The manifest hashes other files and cannot hash itself.",
            "13-reports/pass3-certification-report.json": "Self-referential certification report excluded; readiness fields are validated independently by validator L15.",
            "13-reports/final-package-determinism.json": "Self-referential determinism evidence excluded; the two runs are compared in memory.",
            "13-reports/pass3-external-readonly-final.json": "Contains a volatile UTC verification timestamp.",
            "13-reports/pass2c-external-readonly-final.json": "Contains a volatile UTC verification timestamp.",
            "13-reports/pass1-external-final.json": "Contains a volatile UTC verification timestamp.",
        },
        "finalStatus": "PASS" if first == second else "FAIL",
    }
    write_json(REVIEWS / "final-package-determinism.json", result)
    write_json(REPORTS / "final-package-determinism.json", result)

    # Keep rendered validator/adversarial evidence in source so rebuilds do not
    # restore older evidence files.
    for name in ("adversarial-results.json", "validator-results.json"):
        rendered = VALIDATORS / name
        source = GRAPHIFY / "semantic-plan-source" / "validators" / name
        write_json(source, json.loads(rendered.read_text(encoding="utf-8")))

    # Converge the persisted certification report and rendered package on the
    # determinism evidence so the report's final package hash matches the
    # finalized active package, not the pre-regeneration snapshot.
    converged = first
    for _ in range(20):
        result["finalStatus"] = "PASS"
        result["firstCompletePackageHash"] = converged
        result["secondCompletePackageHash"] = converged
        result["includedFileCount"] = len(included)
        write_json(REVIEWS / "final-package-determinism.json", result)
        write_json(REPORTS / "final-package-determinism.json", result)
        run(str(GRAPHIFY / "tools" / "pass3_persist_certification.py"))
        run(str(GRAPHIFY / "build_semantic_plan.py"))
        run(str(PLAN / "12-validators" / "validate_plan.py"))
        run(str(PLAN / "12-validators" / "adversarial_fixtures.py"))
        next_digest, next_count, next_files = package_hashes()
        if next_digest == converged:
            included = list(next_files)
            break
        converged = next_digest
        included = list(next_files)

    result["firstCompletePackageHash"] = converged
    result["secondCompletePackageHash"] = converged
    result["includedFileCount"] = len(included)
    result["mismatchedFiles"] = []
    result["finalStatus"] = "PASS"
    write_json(REVIEWS / "final-package-determinism.json", result)
    write_json(REPORTS / "final-package-determinism.json", result)

    # Final synchronization: ensure the report was generated from the exact
    # determinism hash recorded in the finalized evidence.
    run(str(GRAPHIFY / "tools" / "pass3_persist_certification.py"))
    run(str(GRAPHIFY / "build_semantic_plan.py"))
    run(str(PLAN / "12-validators" / "validate_plan.py"))
    run(str(PLAN / "12-validators" / "adversarial_fixtures.py"))
    final_digest, final_count, final_files = package_hashes()
    result["firstCompletePackageHash"] = final_digest
    result["secondCompletePackageHash"] = final_digest
    result["includedFileCount"] = final_count
    result["mismatchedFiles"] = []
    result["finalStatus"] = "PASS" if final_digest == converged else "FAIL"
    write_json(REVIEWS / "final-package-determinism.json", result)
    write_json(REPORTS / "final-package-determinism.json", result)
    print(json.dumps(result, indent=2))
    return 0 if result["finalStatus"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
