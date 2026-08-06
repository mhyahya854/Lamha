"""Pass 1 independent detector for legacy capability-template requirement output.

This script is deliberately independent from the legacy *builder* pipeline: it
reproduces the superseded ``criterion_statement`` oracle for exact comparison,
then applies structural, label-only, and source-relevance heuristics that the
legacy generator never used.  Output is written only through the Graphify write
guard, and the script never decides a review status or disposition.
"""

from __future__ import annotations

import csv
import importlib.util
import re
import sys
from collections import Counter
from pathlib import Path


sys.dont_write_bytecode = True

GRAPHIFY = Path(__file__).resolve().parents[1]
SOURCE = GRAPHIFY / "semantic-plan-source"
REPORTS = GRAPHIFY / "12-semantic-implementation-plan" / "13-reports"
LEGACY_SCRIPT = GRAPHIFY / "tools" / "superseded" / "seed_reviewed_registries.legacy.py"

sys.path.insert(0, str(GRAPHIFY / "tools"))
from write_guard import write_csv  # noqa: E402


def load_legacy_oracle():
    spec = importlib.util.spec_from_file_location("legacy_seed_oracle", LEGACY_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def normalize(value: str) -> str:
    text = re.sub(r"[^a-z0-9 ]", " ", (value or "").casefold())
    return re.sub(r"\s+", " ", text).strip()


def short_source(value: str) -> bool:
    text = (value or "").strip()
    if not text:
        return True
    return len(text) < 40


def meaningful_word_count(value: str) -> int:
    stop = {
        "the", "and", "for", "that", "with", "from", "must", "shall", "will",
        "into", "this", "are", "not", "all", "only", "where", "when", "after",
        "before", "lamha", "phase", "implementation", "provide", "satisfy", "a",
        "an", "to", "of", "or", "in", "on", "is", "be", "as", "by", "it", "its",
    }
    return sum(1 for word in re.findall(r"[A-Za-z0-9]+", value) if word.casefold() not in stop)


def looks_like_label(value: str, title: str) -> bool:
    text = (value or "").strip().rstrip(".;: ")
    if not text:
        return True
    if text == (title or "").strip():
        return True
    # A label usually has no finite verb and is a noun phrase or short fragment.
    if len(text) < 40 and not re.search(r"\b(is|are|must|shall|will|can|should|when|if|after|before)\b", text, re.I):
        return True
    return False


FAMILY_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("demonstrably_satisfy", ("must demonstrably satisfy:",)),
    ("generated_wrapper_honor", ("implementation must honor this constraint:",)),
    ("generated_wrapper_evidence", ("recorded evidence must demonstrate:",)),
    ("generated_wrapper_invariant", ("lamha must preserve this invariant:",)),
    ("section_parent_template", ("lamha must implement the ", "behavior for ", "and satisfy every linked acceptance criterion")),
    ("provide_do_not", ("lamha must provide do not",)),
    ("must_provide", ("lamha must provide ",)),
    ("local_ai_worker", ("when the local worker processes ",)),
    ("workflow_manages", ("when the workflow manages ",)),
    ("event_plan_requested", ("requested in ", "produce or update a reviewable event plan")),
    ("review_item_offers", ("when a review item offers ",)),
    ("library_encounters", ("when a configured library encounters ",)),
    ("query_index_uses", ("when a query or indexing task uses ",)),
    ("producing_evidence", ("when producing ", "evidence")),
    ("duplicates_evaluates", ("when duplicate analysis evaluates ",)),
    ("memory_shown", ("is shown in ", "derive the memory from local canonical asset references")),
    ("tags_proposed", ("is proposed or changed in ",)),
    ("desktop_shell_handles", ("when the desktop shell handles ",)),
    ("user_invokes", ("when the user invokes ",)),
    ("user_uses", ("when the user uses ",)),
    ("user_changes", ("when the user changes ",)),
    ("user_applies", ("when the user applies ",)),
    ("participates_in", ("participates in ",)),
    ("occurs_in", ("occurs in ",)),
    ("encountered_in", ("is encountered in ",)),
    ("is_used_in", (" is used in ",)),
    ("is_requested_in", (" is requested in ",)),
    ("fallback_exercised", ("when ", "is exercised in ", "must expose the resulting state and preserve the prior durable state")),
]


def detect_family(statement: str) -> str:
    lower = (statement or "").casefold()
    for name, needles in FAMILY_RULES:
        if all(needle in lower for needle in needles):
            return name
    return ""


def source_unrelated_flags(row: dict[str, str]) -> list[str]:
    """Return concrete reasons the current statement may ignore the source meaning."""
    flags: list[str] = []
    source = (row.get("source_text") or "").casefold()
    section = (row.get("source_section") or "").casefold()
    capability = (row.get("canonical_capability") or row.get("target_capability") or "").casefold()
    statement = (row.get("statement") or "").casefold()

    legal_terms = ("licence", "licenses", "license", "attribution", "legal", "redistribution", "provenance", "model card")
    if any(term in source or term in section for term in legal_terms) and "worker processes" in statement:
        flags.append("legal/licensing content routed through the AI inference-worker template")

    if re.search(r"\bopen\s+(person|people|event|folder)\b", source) and re.search(
        r"\b(create|update|mutat|persist|authorize|approve|transition)\b", statement
    ):
        flags.append("navigation/open wording rendered as an identity/plan/root mutation")

    if re.search(r"\b(large[-\s]?library|performance|scale|memory|ram)\b", source) and re.search(
        r"\bauthorized-root|root-authorization|access-mode|library encounters|storage root\b", statement
    ):
        flags.append("performance or resource wording rendered as a storage-root operation")

    if re.search(r"\bmemory\b", source) and "worker processes" in statement:
        flags.append("memory wording rendered as worker inference without resolving product/RAM meaning")

    if short_source(row.get("source_text", "")) and meaningful_word_count(statement) < 8:
        flags.append("short label or standalone noun expanded into a generic capability sentence")

    if re.search(r"\b(menu|button|tab|dialog|page|screen|settings|option)\b", source) and re.search(
        r"\b(processes|manages|persist|transition|authorize)\b", statement
    ):
        flags.append("menu/UI label treated as a complete feature mutation")

    return flags


def main() -> int:
    oracle = load_legacy_oracle()
    rows = list(csv.DictReader((SOURCE / "requirements" / "requirements.csv").open(encoding="utf-8-sig", newline="")))
    mappings = {r["canonical_id"]: r for r in csv.DictReader((SOURCE / "requirements" / "requirement-mapping.csv").open(encoding="utf-8-sig", newline=""))}
    memberships: dict[str, str] = {}
    for row in csv.DictReader((SOURCE / "packages" / "requirement-membership.csv").open(encoding="utf-8-sig", newline="")):
        memberships[row["canonical_id"]] = row["work_package_id"]
    by_id = {r["canonical_id"]: r for r in rows}

    audit: list[dict[str, str]] = []
    family_counter: Counter[str] = Counter()
    exact_counter = 0
    for row in rows:
        if row.get("supersession_status") != "ACTIVE":
            continue
        canonical_id = row["canonical_id"]
        statement = row.get("statement", "") or ""
        source_text = row.get("source_text", "") or ""
        title = row.get("title", "") or ""
        try:
            legacy_output = oracle.criterion_statement(row)
        except Exception as error:  # pragma: no cover - oracle robustness
            legacy_output = f"__oracle_error__:{error}"
        exact = normalize(statement) == normalize(legacy_output)
        family = detect_family(statement)
        flags = source_unrelated_flags(row)
        label_only = looks_like_label(source_text, title) and meaningful_word_count(statement) < 8
        is_section_parent = re.match(
            r"^Lamha must implement the .+ behavior for .+ and satisfy every linked acceptance criterion\.?$",
            statement,
            re.I | re.S,
        )
        matched: list[str] = []
        if exact:
            matched.append("EXACT_LEGACY_OUTPUT")
            exact_counter += 1
        if family:
            matched.append(f"FAMILY:{family}")
            family_counter[family] += 1
        if label_only:
            matched.append("LABEL_ONLY")
        if flags:
            matched.append("SOURCE_UNRELATED")
        if is_section_parent and not exact:
            matched.append("SECTION_PARENT_TEMPLATE")

        why: list[str] = []
        if exact:
            why.append("Statement exactly reproduces the superseded capability-template generator output.")
        if family and not exact:
            why.append(f"Statement follows the legacy {family} sentence family.")
        if is_section_parent and not exact:
            why.append("Section parent substitutes a capability label into a generic 'implement the section behavior' sentence without defining the section's observable behaviour.")
        if label_only:
            why.append("Statement is only a label fragment without an observable trigger or result.")
        why.extend(flags)
        if not why:
            continue

        parent = by_id.get(row.get("parent_requirement_id") or "", {})
        audit.append({
            "canonical_id": canonical_id,
            "title": title,
            "source_text": source_text,
            "current_statement": statement,
            "matched_template_family": ";".join(matched),
            "why_current_statement_may_be_semantically_wrong": " ".join(why),
            "current_capability": row.get("canonical_capability") or row.get("target_capability") or "",
            "current_phase": mappings.get(canonical_id, {}).get("primary_implementation_phase", ""),
            "current_package": memberships.get(canonical_id, ""),
            "required_disposition": "",
            "requirement_type": row.get("requirement_type", ""),
            "source_section": row.get("source_section", ""),
            "parent_requirement_id": row.get("parent_requirement_id", ""),
            "parent_title": parent.get("title", ""),
            "parent_statement": parent.get("statement", ""),
            "source_length_category": "SHORT" if short_source(source_text) else "LONG",
        })

    audit.sort(key=lambda r: (r["source_section"], r["canonical_id"]))
    fields = [
        "canonical_id", "title", "source_text", "current_statement", "matched_template_family",
        "why_current_statement_may_be_semantically_wrong", "current_capability", "current_phase",
        "current_package", "required_disposition", "requirement_type", "source_section",
        "parent_requirement_id", "parent_title", "parent_statement", "source_length_category",
    ]
    write_csv(REPORTS / "legacy-template-semantic-audit.csv", audit, fields)
    write_csv(SOURCE / "reviews" / "legacy-template-semantic-audit.csv", audit, fields)
    summary = {
        "active_canonical_records": sum(1 for r in rows if r.get("supersession_status") == "ACTIVE"),
        "detected_records": len(audit),
        "exact_legacy_output": exact_counter,
        "family_matches": dict(sorted(family_counter.items())),
        "output": "12-semantic-implementation-plan/13-reports/legacy-template-semantic-audit.csv",
    }
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
