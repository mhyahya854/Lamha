"""Pass 3 independent legacy-template reproduction.

Reproduces the old generated-template families without importing the active
repair detector and reports any matches in active canonical statements.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True

GRAPHIFY = Path(__file__).resolve().parents[1]
SOURCE = GRAPHIFY / "semantic-plan-source"
REVIEWS = SOURCE / "reviews"
REPORTS = GRAPHIFY / "12-semantic-implementation-plan" / "13-reports"

sys.path.insert(0, str(GRAPHIFY / "tools"))
from write_guard import write_csv, write_json  # noqa: E402


IMPLEMENTATION_TYPES = {
    "FUNCTIONAL_REQUIREMENT", "NONFUNCTIONAL_REQUIREMENT", "ARCHITECTURAL_INVARIANT",
    "SECURITY_INVARIANT", "PRIVACY_INVARIANT", "DATA_INTEGRITY_INVARIANT",
    "IMPLEMENTATION_CONSTRAINT", "ACCEPTANCE_CRITERION", "OPTIONAL_ADAPTER",
    "VERIFICATION_GATE", "REMOVAL_GATE", "RELEASE_GATE", "PROHIBITION",
}

FAMILIES = {
    "EXACT_LEGACY_TEMPLATE": re.compile(r"lamha must implement the .+ behavior for .+ and satisfy every linked acceptance criterion\.", re.I),
    "NORMALIZED_GENERIC_WRAPPER": re.compile(r"must demonstrably satisfy|must satisfy:|recorded evidence must demonstrate:", re.I),
    "CAPABILITY_TEMPLATE_FAMILY": re.compile(
        r"when (the local worker processes|the workflow manages|a review item offers|a configured library encounters|a query or indexing task uses|duplicate analysis evaluates|the desktop shell handles)",
        re.I,
    ),
    "EXERCISED_FALLBACK": re.compile(r"is exercised in .*must expose the resulting state and preserve the prior durable state", re.I),
    "MEMORY_SHOWN_FALLBACK": re.compile(r"is shown in .*derive the memory from local canonical asset references", re.I),
    "NAVIGATION_AS_MUTATION": re.compile(r"\bopen (person|people|event|folder)\b", re.I),
    "LICENSING_AS_INFERENCE": re.compile(r"(licen[cs]e|attribution|redistribution).*local worker processes|local worker processes.*(licen[cs]e|attribution|redistribution)", re.I),
    "PERFORMANCE_AS_STORAGE_AUTHORIZATION": re.compile(r"large[-\s]?library.*authorized-root and access-mode|authorized-root and access-mode.*large[-\s]?library", re.I),
    "GENERIC_ACCEPTANCE_CRITERION": re.compile(r"must support \w+ without (defining|specifying)|must provide do not|malformed prohibition", re.I),
}


def main() -> int:
    requirements = list(csv.DictReader((SOURCE / "requirements" / "requirements.csv").open(encoding="utf-8-sig", newline="")))
    mapping = {row["canonical_id"]: row for row in csv.DictReader((SOURCE / "requirements" / "requirement-mapping.csv").open(encoding="utf-8-sig", newline=""))}
    matches: list[dict[str, str]] = []
    for row in requirements:
        rid = row["canonical_id"]
        if row.get("supersession_status") != "ACTIVE" or row.get("requirement_type") not in IMPLEMENTATION_TYPES:
            continue
        if not mapping.get(rid, {}).get("primary_implementation_phase"):
            continue
        statement = row.get("statement", "")
        source = row.get("source_text", "")
        section = row.get("source_section", "")
        for family, pattern in FAMILIES.items():
            if family == "NAVIGATION_AS_MUTATION":
                if pattern.search(statement) and re.search(r"\b(create|update|persist|mutat|authorize)\w*\b", statement, re.I) and not re.search(r"\b(load|display|navigate|reveal|read-only)\w*\b", statement, re.I):
                    matches.append({"Canonical ID": rid, "Template family": family, "Statement": statement, "Source": source, "Section": section})
            elif family == "LICENSING_AS_INFERENCE":
                if pattern.search(source + " " + section + " " + statement):
                    matches.append({"Canonical ID": rid, "Template family": family, "Statement": statement, "Source": source, "Section": section})
            elif family == "PERFORMANCE_AS_STORAGE_AUTHORIZATION":
                if pattern.search(statement):
                    matches.append({"Canonical ID": rid, "Template family": family, "Statement": statement, "Source": source, "Section": section})
            else:
                if pattern.search(statement):
                    matches.append({"Canonical ID": rid, "Template family": family, "Statement": statement, "Source": source, "Section": section})

    fields = ["Canonical ID", "Template family", "Statement", "Source", "Section"]
    write_csv(REVIEWS / "pass3-legacy-template-reproduction.csv", matches, fields)
    write_csv(REPORTS / "pass3-legacy-template-reproduction.csv", matches, fields)
    result = {"templateMatches": len(matches), "families": sorted({row["Template family"] for row in matches})}
    write_json(REVIEWS / "pass3-legacy-template-reproduction.json", result)
    write_json(REPORTS / "pass3-legacy-template-reproduction.json", result)
    print(json.dumps(result, indent=2))
    return 0 if not matches else 1


if __name__ == "__main__":
    raise SystemExit(main())
