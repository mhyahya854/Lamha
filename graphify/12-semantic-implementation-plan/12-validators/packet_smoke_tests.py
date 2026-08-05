"""Exercise bounded prompt generation and its unknown-package failure path."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path


sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
PLAN = HERE.parent
CLI = PLAN / "11-model-packets" / "plan_cli.py"
SPEC = importlib.util.spec_from_file_location("lamha_validator", HERE / "validate_plan.py")
validator = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(validator)


def invoke(package_id: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["TEMP"] = str(PLAN / "13-reports")
    environment["TMP"] = environment["TEMP"]
    return subprocess.run([sys.executable, "-B", str(CLI), "prompt", package_id], cwd=PLAN, env=environment, capture_output=True, text=True, check=False)


def main() -> int:
    rows = []
    for package_id in ("WP-I0-001", "WP-I4-004", "WP-I10-001", "WP-I15-001"):
        completed = invoke(package_id)
        valid = completed.returncode == 0 and package_id in completed.stdout and "Canonical source:" in completed.stdout and "## Execution boundary" in completed.stdout
        rows.append({"case": package_id, "expected": "PROMPT", "status": "PASS" if valid else "FAIL", "exitCode": completed.returncode})
    completed = invoke("WP-UNKNOWN-999")
    valid = completed.returncode != 0 and "unknown work package" in completed.stderr
    rows.append({"case": "WP-UNKNOWN-999", "expected": "REJECT", "status": "PASS" if valid else "FAIL", "exitCode": completed.returncode})
    result = {"status": "PASS" if all(row["status"] == "PASS" for row in rows) else "FAIL", "testCount": len(rows), "tests": rows}
    path = validator.safe_write_path(HERE / "packet-smoke-results.json")
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
