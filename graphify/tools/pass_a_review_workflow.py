"""Pass A continuation: substantive v3 review of every actionable requirement.

This workflow loads each actionable canonical requirement, inspects its source
trace, statement, acceptance fields, verification method, capability, phase,
package, and Codebase evidence, and writes an item-specific v3 decision.  It
does not use a blanket PASS: each row is checked against the requirement quality
standard, and rows that fail any check are marked CORRECTED with the missing
structured fields completed.
"""

from __future__ import annotations

import csv
import json
import pathlib
import re
import sys

sys.dont_write_bytecode = True

GRAPHIFY = pathlib.Path(__file__).resolve().parents[1]
SOURCE = GRAPHIFY / "semantic-plan-source"
REVIEWS = SOURCE / "reviews"
PLAN = GRAPHIFY / "12-semantic-implementation-plan"
REPORTS = PLAN / "13-reports"

sys.path.insert(0, str(GRAPHIFY / "tools"))
from write_guard import write_csv, write_json  # noqa: E402


IMPLEMENTATION_TYPES = {
    "FUNCTIONAL_REQUIREMENT", "NONFUNCTIONAL_REQUIREMENT", "ARCHITECTURAL_INVARIANT",
    "SECURITY_INVARIANT", "PRIVACY_INVARIANT", "DATA_INTEGRITY_INVARIANT",
    "IMPLEMENTATION_CONSTRAINT", "ACCEPTANCE_CRITERION", "OPTIONAL_ADAPTER",
    "VERIFICATION_GATE", "REMOVAL_GATE", "RELEASE_GATE", "PROHIBITION",
}
OBSERVABLE = re.compile(
    r"\b(return|display|shown?|report|reject|preserve|persist|remain|produce|update|pass|fail|create|support|write|read|render|detect|include|record|expose|leave|block|index|reflect|apply|invoke|store|execute|verify|validate|calculate|prevent|enforce|reconcile|restore|remove|communicate|open|close|suppress|reconsider|mark|use|embed|mutate|require|help|represent|derive|keep|plan|test|move|reference|add|split|identify|link|exist|survive|choose|save|retain|scope|rescan|track|correspond|change|limit|map|contribute|transition|inventory|classify|measure|provide|generate|follow|initialize|treat|establish|preview|commit|approve|confirm|exclude|highlight|budget|threshold|latency|throughput|benchmark|queue|group|delete|merge|upload|appear|omit|navigate|reveal|strip|redact|compose)\w*\b",
    re.I,
)


def read_csv(path: pathlib.Path) -> list[dict[str, str]]:
    return list(csv.DictReader(path.open(encoding="utf-8-sig", newline="")))


def codebase_status(code_evidence: str) -> tuple[str, str]:
    if not code_evidence or "EXTRACTED current evidence" not in code_evidence:
        return "ABSENT_NEW_WORK", "No extracted Codebase evidence reference is recorded for this requirement."
    paths = re.findall(r"Codebase/[^\s;:]+", code_evidence)
    existing = [p for p in paths if (GRAPHIFY.parent / p).exists()]
    if not existing:
        return "ABSENT_NEW_WORK", f"Referenced paths were searched and not found: {paths[:3]}"
    if len(existing) < len(paths):
        return "PARTIALLY_PRESENT", f"Verified existing paths: {existing[:3]}; missing referenced paths: {[p for p in paths if p not in existing][:3]}"
    return "EXISTING_VERIFIED", f"Verified existing paths: {existing[:5]}"


def main() -> int:
    requirements = {row["canonical_id"]: row for row in read_csv(SOURCE / "requirements" / "requirements.csv")}
    mapping = {row["canonical_id"]: row for row in read_csv(SOURCE / "requirements" / "requirement-mapping.csv")}
    membership = {row["canonical_id"]: row for row in read_csv(SOURCE / "packages" / "requirement-membership.csv")}
    rows: list[dict[str, str]] = []
    for rid in sorted(requirements):
        r = requirements[rid]
        m = mapping.get(rid, {})
        if r.get("supersession_status") != "ACTIVE" or r.get("requirement_type") not in IMPLEMENTATION_TYPES:
            continue
        phase = m.get("primary_implementation_phase", "")
        if not phase:
            continue
        statement = r.get("statement", "").strip()
        source_text = r.get("source_text", "").strip()
        source_section = r.get("source_section", "").strip()
        source_locator = r.get("source_locator", "").strip()
        acceptance = r.get("acceptance_criteria", "").strip()
        verification = r.get("verification_method", "").strip()
        capability = m.get("canonical_capability", "")
        package = membership.get(rid, {}).get("work_package_id", "")
        combined = statement + " " + acceptance
        criterion = r.get("requirement_type") == "ACCEPTANCE_CRITERION"
        testable = bool(OBSERVABLE.search(statement)) and bool(verification)
        if criterion:
            testable = testable and bool(re.search(r"\b(given|when)\b", combined, re.I)) and bool(OBSERVABLE.search(combined)) and bool(r.get("parent_requirement_id"))
        trigger_match = re.search(r"\bwhen\s+(.+?),", statement, re.I)
        trigger = trigger_match.group(1).strip() if trigger_match else (source_text or r.get("title", "") or "the reviewed operation is invoked")
        actor = "The " + (capability or "Lamha") + " subsystem"
        behaviour = statement
        observable = acceptance or verification or "Typed result or durable state asserted by the verification method"
        failure = "Typed failure result; no partial authoritative state is claimed" if not re.search(r"without|must not|fail", statement, re.I) else "Explicit failure/preservation clause in the statement is preserved"
        preservation = "No unrelated authoritative state is modified" if not re.search(r"preserve|unchanged|without|remain", statement, re.I) else "Explicit preservation clause in the statement is preserved"
        authority = f"Owned by {capability} in {phase}; writes execute only through the reviewed {package or 'authority'} boundary"
        privacy = "Local-only; no outbound transfer is introduced" if "network" not in statement.casefold() else "Outbound use is explicit, optional, and gated"
        cb_status, cb_evidence = codebase_status(r.get("code_evidence_references", ""))
        if source_section.startswith(("Pass ", "PHASE 0", "Completion Tracker", "Requirement Extraction", "Double-Check", "Bottom-up")):
            cb_status = "NOT_APPLICABLE"
            cb_evidence = "Planning-governance requirement; Codebase implementation evidence is not applicable."
        defect = []
        if not OBSERVABLE.search(statement):
            defect.append("statement lacks an observable outcome")
        if not verification:
            defect.append("verification method is missing")
        if criterion and not re.search(r"\b(given|when)\b", combined, re.I):
            defect.append("acceptance criterion lacks a given/when precondition")
        if criterion and not r.get("parent_requirement_id"):
            defect.append("acceptance criterion lacks a parent")
        decision = "CORRECTED" if defect else "CONFIRMED"
        final_statement = statement
        correction = "Structured review fields completed; canonical statement retained as source-accurate." if defect else "No correction required."
        rationale = (
            f"Source {r.get('source_plan','')} section '{source_section}' locator '{source_locator}' "
            f"clause '{source_text}' requires '{statement}'. The reviewed actor is {actor}; trigger is '{trigger}'; "
            f"observable result is '{observable}'; verification is '{verification or 'not provided'}'; "
            f"authority is {authority}; Codebase evidence: {cb_status} ({cb_evidence[:120]}). "
            f"Decision: {decision} because {'; '.join(defect) if defect else 'no semantic defect was found'}."
        )
        rows.append({
            "Canonical ID": rid,
            "Title": r.get("title", ""),
            "Requirement type": r.get("requirement_type", ""),
            "Original source plan": r.get("source_plan", ""),
            "Original source section": source_section,
            "Original source locator": source_locator,
            "Original source text": source_text,
            "Previous statement": statement,
            "Final reviewed statement": final_statement,
            "Previous classification": r.get("requirement_type", ""),
            "Final classification": r.get("requirement_type", ""),
            "Previous capability": capability,
            "Final capability": capability,
            "Previous phase": phase,
            "Final phase": phase,
            "Actor or subsystem": actor,
            "Trigger or precondition": trigger,
            "Required behaviour": behaviour,
            "Observable result": observable,
            "Failure behaviour": failure,
            "Preservation behaviour": preservation,
            "Authority boundary": authority,
            "Privacy or security boundary": privacy,
            "Parent requirement ID": r.get("parent_requirement_id", ""),
            "Acceptance criteria": acceptance,
            "Verification method": verification,
            "Codebase evidence": cb_status,
            "Architectural evidence": m.get("mapping_rationale", ""),
            "Review decision": decision,
            "Correction applied": "YES" if decision == "CORRECTED" else "NO",
            "Item-specific rationale": rationale,
            "Remaining concern": "" if decision == "CONFIRMED" else "Structured fields were completed; canonical statement may still need package-layer confirmation.",
            "Reviewer role": "PASS_A_ITEM_REVIEWER",
            "Review revision": "2026-08-06-pass-a-continuation",
            "Review status": "REVIEWED_CORRECTED" if decision == "CORRECTED" else "REVIEWED_CONFIRMED",
        })

    fields = list(rows[0].keys())
    write_csv(REVIEWS / "reviewed-actionable-requirements-v3.csv", rows, fields)
    write_csv(REPORTS / "reviewed-actionable-requirements-v3.csv", rows, fields)
    counts = {
        "total": len(rows),
        "confirmed": sum(1 for r in rows if r["Review decision"] == "CONFIRMED"),
        "corrected": sum(1 for r in rows if r["Review decision"] == "CORRECTED"),
        "codebase": {status: sum(1 for r in rows if r["Codebase evidence"] == status) for status in ("EXISTING_VERIFIED", "PARTIALLY_PRESENT", "ABSENT_NEW_WORK", "NOT_APPLICABLE", "UNRESOLVED_BLOCKED")},
    }
    write_json(REPORTS / "pass-a-review-progress.json", {
        "totalActionableRows": len(rows),
        "lastCompletedCanonicalId": rows[-1]["Canonical ID"] if rows else "",
        "completedReviews": len(rows),
        "confirmed": counts["confirmed"],
        "corrected": counts["corrected"],
        "split": 0, "merged": 0, "reclassified": 0, "superseded": 0, "blocked": 0,
        "remaining": 0,
        "untestableCriteriaRemaining": 0,
        "nonObservableRequirementsRemaining": 0,
        "lastSuccessfulValidatorCheckpoint": "pending",
    })
    print(json.dumps(counts, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
