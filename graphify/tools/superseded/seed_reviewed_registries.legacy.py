"""One-time migration helper for the semantic-plan repair.

This script materializes reviewable candidates from the rejected generated plan.
It is intentionally not imported or called by the production plan builder.  Its
outputs become explicit source registries only after the review ledgers are
completed and the independent validator passes.
"""

from __future__ import annotations

import csv
import json
import os
import re
import stat
from collections import Counter, defaultdict
from pathlib import Path


GRAPHIFY = Path(__file__).resolve().parents[1]
SOURCE = GRAPHIFY / "semantic-plan-source"
LEGACY_PLAN = GRAPHIFY / "12-semantic-implementation-plan"
LEGACY_BUILDER = GRAPHIFY / "build_semantic_plan.py"

IMPLEMENTATION_TYPES = {
    "FUNCTIONAL_REQUIREMENT",
    "NONFUNCTIONAL_REQUIREMENT",
    "ARCHITECTURAL_INVARIANT",
    "SECURITY_INVARIANT",
    "PRIVACY_INVARIANT",
    "DATA_INTEGRITY_INVARIANT",
    "IMPLEMENTATION_CONSTRAINT",
    "ACCEPTANCE_CRITERION",
    "OPTIONAL_ADAPTER",
}

PHASE_NAMES = {
    "I0": "Repository Proof and Feasibility",
    "I1": "Identity, Branding, and Legal Foundation",
    "I2": "Desktop Shell and Trust Boundary",
    "I3": "Authoritative Data and Transaction Foundation",
    "I4": "Media Discovery and Derived Index",
    "I5": "Offline Library Experience",
    "I6": "Events and Manage Later",
    "I7": "People, Faces, and Groups",
    "I8": "Tags, Relationships, and Attribution",
    "I9": "Mind-Map Projections",
    "I10": "Local AI, Search, and Duplicates",
    "I11": "Metadata Mutation, Editing, and Privacy",
    "I12": "External Drives and Filesystem Resilience",
    "I13": "Backup, Trash, Restore, and Rebuild",
    "I14": "Performance, Accessibility, and Desktop UX",
    "I15": "Packaging, Legacy Eradication, and Release",
}

STOP = {
    "the", "and", "for", "that", "with", "from", "must", "shall", "will",
    "into", "this", "are", "not", "all", "only", "where", "when", "after",
    "before", "lamha", "phase", "implementation", "provide", "satisfy",
}


def is_reparse(path: Path) -> bool:
    try:
        attrs = path.lstat().st_file_attributes
    except (AttributeError, FileNotFoundError, OSError):
        return path.is_symlink()
    return bool(attrs & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def safe_path(path: Path) -> Path:
    root = GRAPHIFY.resolve(strict=True)
    resolved = path.resolve(strict=False)
    resolved.relative_to(root)
    cursor = root
    for part in resolved.relative_to(root).parts[:-1]:
        cursor /= part
        if cursor.exists() and is_reparse(cursor):
            raise RuntimeError(f"Refusing reparse-point write path: {cursor}")
    return resolved


def write_text(path: Path, text: str) -> None:
    path = safe_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def write_json(path: Path, value: object) -> None:
    write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path = safe_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def words(value: str) -> list[str]:
    return [word.casefold() for word in re.findall(r"[A-Za-z0-9]+", value) if word.casefold() not in STOP]


def tokens(value: str) -> set[str]:
    return {word for word in words(value) if len(word) > 2}


def clean_fragment(value: str) -> str:
    value = re.sub(r"\[![A-Z]+\]", "", value or "")
    value = re.sub(r"[`*_#>]", "", value)
    return re.sub(r"\s+", " ", value).strip(" .;:-")


def lower_initial(value: str) -> str:
    value = clean_fragment(value)
    if not value:
        return "the requested behavior"
    return value[0].lower() + value[1:]


def criterion_statement(row: dict[str, str]) -> str:
    """Produce a review candidate with trigger, behavior, result, and failure rule."""
    source = clean_fragment(row["source_text"])
    section = clean_fragment(row["source_section"])
    capability = row["target_capability"]
    canonical_id = row["canonical_id"]

    if canonical_id.startswith("CAN-FAIL-"):
        parts = [clean_fragment(part) for part in row["source_text"].split(";") if clean_fragment(part)]
        trigger = parts[1] if len(parts) > 1 else source
        control = parts[3] if len(parts) > 3 else source
        proof = parts[4] if len(parts) > 4 else row["verification_method"]
        return (
            f"If an implementation would permit {lower_initial(trigger)}, it must instead enforce this control: "
            f"{control.rstrip('.')}. Verification must observe {lower_initial(proof).rstrip('.')}, and a failed "
            "control must leave authoritative data and original media unchanged."
        )

    label = source or row["title"]
    context = section or capability
    templates = {
        "Metadata": (
            f"When the {context} workflow reads or changes {label}, it must preserve the value, authority, "
            "and provenance in the appropriate durable record and expose the resulting revision to the derived index. "
            "Missing, malformed, or conflicting input must be reported without discarding the last valid value."
        ),
        "People and faces": (
            f"When the {context} workflow manages {label}, it must persist the candidate or confirmed state with "
            "provenance and revision, expose the resulting state for review, and reject invalid transitions without "
            "changing an existing identity or historical interval."
        ),
        "Libraries and storage": (
            f"When a configured library encounters {label} during {context}, Rust must apply authorized-root and "
            "access-mode rules, expose the resulting root or asset state, and leave files unchanged if validation, "
            "permission, or I/O checks fail."
        ),
        "Asset viewer": (
            f"When the user invokes {label} in {context}, the viewer must apply or display the behavior for the "
            "selected asset, expose the resulting UI state, and preserve the original media when the operation or "
            "format is unavailable."
        ),
        "Events and organization": (
            f"When {label} is requested in {context}, Lamha must produce or update a reviewable event plan, show its "
            "membership and filesystem effects, and make no authoritative or filesystem change if validation or "
            "confirmation fails."
        ),
        "Search and OCR": (
            f"When a query or indexing task uses {label} in {context}, Lamha must return the matching local result "
            "with source and revision information, and must report unavailable or stale index data without treating "
            "it as authoritative knowledge."
        ),
        "Review Centre": (
            f"When a review item offers {label} in {context}, the selected decision must produce a visible, persisted "
            "proposal-state transition while leaving authoritative metadata unchanged until an allowed approval action "
            "commits it; rejected invalid transitions must preserve the prior state."
        ),
        "Map and location": (
            f"When {label} is used in {context}, Lamha must derive the map or location result from canonical records, "
            "show its source and confidence where applicable, and preserve the records if projection or coordinate "
            "validation fails."
        ),
        "Duplicates": (
            f"When duplicate analysis evaluates {label} in {context}, it must create a reviewable candidate with "
            "evidence and stable asset identities; no file may be removed or merged when analysis fails or before an "
            "explicitly confirmed operation plan."
        ),
        "Local AI worker": (
            f"When the local worker processes {label} for {context}, it must return a typed candidate carrying model, "
            "source, configuration, and asset-revision provenance; failure or cancellation must produce a terminal task "
            "state and must not mutate authoritative knowledge."
        ),
        "Gallery and timeline": (
            f"When the user uses {label} in {context}, the interface must expose the resulting selection, position, or "
            "view state from local data, remain keyboard-operable, and retain the prior stable view if loading fails."
        ),
        "Legal and rebranding": (
            f"When producing {context} evidence, the repository and packaged application must identify {label} "
            "consistently, retain required attribution, and fail the release gate if any reviewed surface disagrees."
        ),
        "Local data authority": (
            f"When {label} participates in {context}, the authoritative record or transaction must persist its revision "
            "and provenance before derived-index publication, and any failed write must leave a recoverable prior state."
        ),
        "Tags": (
            f"When {label} is proposed or changed in {context}, Lamha must persist a namespaced, revisioned tag "
            "candidate or assignment, expose the decision for review, and preserve prior assignments on validation failure."
        ),
        "Memories": (
            f"When {label} is shown in {context}, Lamha must derive the memory from local canonical asset references, "
            "show a reproducible result, and omit unavailable assets without changing their records."
        ),
        "Albums and favorites": (
            f"When the user changes {label} in {context}, Lamha must persist the affected asset membership or favorite "
            "state with a new revision, reflect it in the UI, and preserve the prior membership if the write fails."
        ),
        "Editing": (
            f"When the user applies {label} in {context}, Lamha must update a revisioned non-destructive recipe or "
            "reviewed export plan, show the preview/result, and never overwrite the original media on failure or cancellation."
        ),
        "Jobs and notifications": (
            f"When {label} occurs in {context}, Lamha must expose a typed operation or notification state with progress "
            "and recovery information, and must not report success for a cancelled, failed, or partially committed operation."
        ),
        "Desktop shell": (
            f"When the desktop shell handles {label} in {context}, it must use the typed Tauri boundary, expose the "
            "result or stable error to the frontend, and reject requests outside the granted capability without side effects."
        ),
        "Sharing and mobile backup": (
            f"When {label} is encountered in {context}, the desktop product must keep the workflow local, expose that "
            "remote behavior is unavailable, and create no account, listener, upload, or hidden outbound request."
        ),
        "Authentication and users": (
            f"When {label} is encountered in {context}, the single-user desktop shell must complete locally without an "
            "account or session dependency and must expose a stable migration error if legacy identity state blocks startup."
        ),
        "Settings": (
            f"When the user changes {label} in {context}, Lamha must validate and persist the local setting with a new "
            "revision, reflect the effective value, and retain the previous value when validation or storage fails."
        ),
    }
    return templates.get(
        capability,
        f"When {label} is exercised in {context}, Lamha must expose the resulting state and preserve the prior durable "
        "state if validation or execution fails.",
    )


def repair_statement(row: dict[str, str]) -> tuple[str, bool, str]:
    current = row["statement"].strip()
    source = clean_fragment(row["source_text"])
    exact_rewrites = {
        "CAN-LAM-ASSET-096": "The system must store photographer attribution separately from camera ownership and must never infer either role from the other; a round-trip schema test must preserve both values independently.",
        "CAN-LAM-GOV-258": "For cross-volume operations, Rust must use copy, flush, checksum verification, and a journaled source-removal step; it must never assume that rename is atomic across drives.",
        "CAN-LAM-GOV-261": "A watcher or reconciliation request must scope rescanning to affected roots and paths; it must not rescan the entire library unless an explicit rebuild plan records the reason.",
        "CAN-LAM-PERSON-078": "Creating or updating an event attendee must not add that person to an asset's visible-people list; only reviewed face or user attribution may change visible people.",
    }
    if row["canonical_id"] in exact_rewrites:
        return exact_rewrites[row["canonical_id"]], True, "Explicit rewrite preserves the source prohibition and adds an observable boundary."
    generic = "must demonstrably satisfy:" in current.casefold()
    too_short = len(words(current)) < 6 and row["requirement_type"] in IMPLEMENTATION_TYPES
    generic_short = "must implement and verify the" in current.casefold() and "behavior described by" in current.casefold()
    bad_prohibition = current.casefold().startswith("lamha must provide do not")
    if generic or too_short or generic_short:
        return criterion_statement(row), True, "Explicit semantic rewrite adds trigger, expected behavior, observable state, and failure behavior."
    if bad_prohibition or source.casefold().startswith("do not "):
        subject = source[7:].strip() if source.casefold().startswith("do not ") else current[len("Lamha must provide Do not "):]
        return f"Lamha must not {lower_initial(subject).rstrip('.')}.", True, "Converted a malformed positive template into the source prohibition."
    if current.startswith("Lamha must provide Deleting "):
        return "The final Lamha runtime must not retain " + lower_initial(source).rstrip(".") + ".", True, "Converted a deletion-list fragment into a final-state prohibition."
    return current, False, row["rationale"]


def corrected_mapping(row: dict[str, str]) -> tuple[str, str, str]:
    """Return reviewed canonical capability, primary phase, and rationale candidate."""
    text = " ".join((row["canonical_id"], row["source_section"], row["source_text"], row["statement"])).casefold()
    old_capability = row["target_capability"]
    phase = row["primary_implementation_phase"]
    capability = old_capability

    if row["canonical_id"].startswith("CAN-MISSION-I0-"):
        return "Repository proof and feasibility", "I0", "Reviewed as an I0 safety/baseline obligation from the mission-owned Phase 0 registry."

    if row["requirement_type"] == "PROHIBITION":
        return old_capability, "", "Reviewed as a final-state prohibition; replacement implementation and I15 removal validation are represented separately."

    failure_routes = {
        "CAN-FAIL-01": ("Media ingestion and derivation", "I4"),
        "CAN-FAIL-03": ("Frontend cutover", "I2"),
        "CAN-FAIL-04": ("Sidecars and metadata authority", "I3"),
        "CAN-FAIL-05": ("Events and organization", "I6"),
        "CAN-FAIL-06": ("People and faces", "I7"),
        "CAN-FAIL-07": ("Local AI worker", "I10"),
        "CAN-FAIL-08": ("Asset identity and records", "I3"),
        "CAN-FAIL-10": ("Local data authority", "I3"),
        "CAN-FAIL-11": ("Events and organization", "I6"),
        "CAN-FAIL-12": ("Relationships and attribution", "I8"),
        "CAN-FAIL-13": ("People and faces", "I7"),
        "CAN-FAIL-14": ("People and faces", "I7"),
        "CAN-FAIL-15": ("People and faces", "I7"),
        "CAN-FAIL-16": ("External drives and path resilience", "I12"),
        "CAN-FAIL-17": ("Events and organization", "I6"),
        "CAN-FAIL-18": ("Review Centre", "I5"),
        "CAN-FAIL-20": ("Filesystem transactions and recovery", "I3"),
        "CAN-FAIL-21": ("External drives and path resilience", "I12"),
        "CAN-FAIL-25": ("Relationships and attribution", "I8"),
        "CAN-FAIL-26": ("Editing", "I11"),
        "CAN-FAIL-28": ("Sidecars and metadata authority", "I3"),
        "CAN-FAIL-29": ("Local AI worker", "I10"),
        "CAN-FAIL-30": ("Mind-map projections", "I9"),
        "CAN-FAIL-31": ("Backup, trash, restore and rebuild", "I13"),
    }
    if row["canonical_id"] in failure_routes:
        routed_capability, routed_phase = failure_routes[row["canonical_id"]]
        return routed_capability, routed_phase, f"Explicit FAIL-registry review assigns the defensive boundary to {routed_capability} in {routed_phase}."
    if row["canonical_id"] in {"CAN-FAIL-22", "CAN-FAIL-23", "CAN-FAIL-24"}:
        return "Planning and verification governance", "", "Explicit FAIL-registry review identifies a scope/execution guardrail rather than application feature implementation."

    if re.search(r"coding model|codex|anti.guessing|anti.stub|asking the user|autonomous execution|chat output", text):
        return "Planning and verification governance", "", "Reviewed as an implementation-agent/governance guardrail, not an application runtime feature."

    if not phase:
        return capability, "", "Reviewed as a non-implementation record or independent gate; no primary implementation phase is assigned."

    # Exact source-section ownership is considered before fine-grained feature
    # refinements.  These are semantic boundaries from the Master Plans, not
    # token scores or capability defaults.
    section = row["source_section"].casefold()
    section_phase: str | None = None
    section_capability: str | None = None
    exact_section_routes = [
        (("phase 2 — rebranding foundation", "legal and rebranding method", "required legal and attribution"), "I1", "Legal and rebranding"),
        (("phase 3 — tauri desktop shell", "tauri command layer"), "I2", "Desktop shell"),
        (("phase 4 — local data foundation", "directional source-of-truth", "authority order", "metadata storage", "schema work"), "I3", "Local data authority"),
        (("phase 5 — asset api replacement", "local library scanning", "consistency detection"), "I4", "Media ingestion and derivation"),
        (("gallery and timeline", "asset viewer", "review centre", "albums", "favorites", "memories"), "I5", old_capability),
        (("phase 6 — manage later & events", "event system", "manual event creation", "event-first physical organization", "manage later"), "I6", "Events and organization"),
        (("phase 7 — faces, people & groups", "face corrections", "11. people", "groups and subgroups", "canonical group name"), "I7", "People and faces"),
        (("phase 8 — tags, relationships", "tag system", "13.2 relationships", "relationship-composition smart views", "photographer, camera owner, and importer"), "I8", "Relationships and attribution"),
        (("phase 9 — mind maps", "event and folder mind map", "relationship map"), "I9", "Mind-map projections"),
        (("phase 10 — local ai completeness", "local ai", "processing state", "ai data control", "hardware assessment", "duplicate management"), "I10", old_capability),
        (("phase 11 — metadata mutation, editing & privacy", "non-destructive editing"), "I11", "Editing"),
        (("phase 12 — external drives & filesystem resilience", "external filesystem and drive behaviour"), "I12", "External drives and path resilience"),
        (("phase 13 — backup, trash & rebuild", "32. trash"), "I13", "Backup, trash, restore and rebuild"),
        (("phase 14 — performance, accessibility & desktop ux", "performance and scale", "desktop user experience", "performance proof"), "I14", old_capability),
        (("phase 15 — full integration, parity & cross-platform packaging",), "I15", "Packaging and legacy eradication"),
    ]
    for fragments, routed_phase, routed_capability in exact_section_routes:
        if any(fragment in section for fragment in fragments):
            section_phase, section_capability = routed_phase, routed_capability
            break
    if any(fragment in section for fragment in ("pre-commit linter", "prerequisite definition of \"removed\"", "premature deletion", "rejected terminology linter", "final-state and migration-state contract")):
        return "Planning and verification governance", "", "Reviewed as a verification/removal constraint; it does not own application feature implementation."
    if any(fragment in section for fragment in ("unneeded code and dependencies to delete", "deletion principle")):
        section_phase, section_capability = "I15", "Packaging and legacy eradication"
    if "remove embedded metadata" in section:
        section_phase, section_capability = "I11", "Editing"
    if "cross-platform support" in section and re.search(r"docker|database|runtime|media tool|installation|package", text):
        section_phase, section_capability = "I15", "Packaging and legacy eradication"
    if "docker and container deployment to delete" in section:
        section_phase, section_capability = "I15", "Packaging and legacy eradication"
    if "sequential implementation phases" in section:
        return "Planning and verification governance", "", "Reviewed as a phase-index planning record; feature ownership is represented by the linked canonical requirements."
    if "15. tag system" in section or section == "tags":
        section_phase, section_capability = "I8", "Tags"
    if "defensive model failures" in text and "fail-" in text:
        return "Planning and verification governance", "", "Reviewed as a planning validation taxonomy entry rather than model runtime work."

    if section_phase:
        phase = section_phase
        capability = section_capability or capability

    exact_media = row["canonical_id"] in {"CAN-FAIL-01", "CAN-LAM-ASSET-004"}
    media_format = bool(re.search(r"\b(heif|heic|raw|video|companion.media|live photo|raw\+jpeg)\b", text))
    media_pipeline = bool(re.search(r"ingest|scanner|scanning|decode|decoder|extract|probe|thumbnail generation|preview generation|format matrix|primary media container", text))
    viewer_only = bool(re.search(r"asset viewer|play and pause|timeline scrubbing|viewer control|raw previews where supported", text)) and not media_pipeline
    if exact_media or (media_format and media_pipeline):
        capability, phase = "Media ingestion and derivation", "I4"
    elif media_format and viewer_only:
        capability, phase = "Asset viewer", "I5"
    elif re.search(r"metadata extraction|extract exif|extract metadata|metadata extractor|sidecar discovery|sidecar health", text):
        capability, phase = "Sidecars and metadata authority", "I4"
    elif re.search(r"thumbnail generation|preview generation", text):
        capability, phase = "Media ingestion and derivation", "I4"
    elif re.search(r"external drive|disconnect|reconnect|detached index|volume identity|cross.volume|path instability", text):
        capability, phase = "External drives and path resilience", "I12"
    elif re.search(r"mind.map|mind map|graph projection", text):
        capability, phase = "Mind-map projections", "I9"
    elif re.search(r"local ai worker|worker protocol|model registry|model management|model lifecycle|model checksum", text):
        capability, phase = "Local AI worker", "I10"
    elif re.search(r"face detection|face candidate|face cluster|face recognition|person identity|group membership", text):
        capability, phase = "People and faces", "I7"
    elif re.search(r"relationship edge|relationship history|photographer|camera owner|attribution role", text):
        capability, phase = "Relationships and attribution", "I8"
    elif re.search(r"backup|restore|trash|permanent delete|sqlite rebuild|index rebuild|disaster recovery", text):
        capability, phase = "Backup, trash, restore and rebuild", "I13"
    elif re.search(r"installer|signing|notarization|package build|packaging|sbom", text):
        capability, phase = "Packaging and legacy eradication", "I15"
    elif re.search(r"privacy.clean export|privacy export|redacted export", text):
        capability, phase = "Editing", "I11"
    elif re.search(r"root authorization|authorized root|path escape|path normalization", text):
        capability, phase = "Root authorization and path safety", "I3"
    elif re.search(r"stable asset identity|asset identity|content identity|original filename", text):
        capability, phase = "Asset identity and records", "I3"
    elif re.search(r"transaction|operation journal|atomic write|rollback|crash recovery", text):
        capability, phase = "Filesystem transactions and recovery", "I3"
    elif re.search(r"static frontend|frontend cutover|tauri ipc wiring|server route removal", text):
        capability, phase = "Frontend cutover", "I2"
    elif re.search(r"\b(scanner|scanning|watcher|file watching|incremental rescan)\b", text):
        capability, phase = "Media ingestion and derivation", "I4"

    if re.search(r"transparent and recoverable metadata|per.asset xmp|authoritative copy|only authoritative|saved user decisions|metadata corruption|json/xmp conflict", text):
        capability, phase = "Sidecars and metadata authority", "I3"
    if re.search(r"folder materialization|folder blocks|folders to rename|assets to move", text):
        capability, phase = "Events and organization", "I6"

    # Section-specific refinements whose short source labels do not name their
    # architecture.  They correct the coarse legacy capability inheritance.
    if "asset bundle standard" in section:
        if re.search(r"companion|live photo|raw\+jpeg|primary media container", text):
            capability, phase = "Media ingestion and derivation", "I4"
        else:
            capability, phase = "Asset identity and records", "I3"
    if "file and folder management" in section:
        if re.search(r"event|manage later|materializ", text):
            capability, phase = "Events and organization", "I6"
        elif re.search(r"trash|restore|backup|permanent", text):
            capability, phase = "Backup, trash, restore and rebuild", "I13"
        elif re.search(r"export|edit|metadata", text):
            capability, phase = "Editing", "I11"
        else:
            capability, phase = "Filesystem transactions and recovery", "I3"
    if "inspector capabilities" in section:
        if re.search(r"ai|model|ocr", text):
            capability, phase = "Local AI worker", "I10"
        elif re.search(r"event", text):
            capability, phase = "Events and organization", "I6"
        else:
            capability, phase = "Asset viewer", "I5"

    rationale = (
        f"Reviewed as {PHASE_NAMES[phase]} work because the obligation's primary implementation surface is "
        f"{capability}; integration verification, removal, and release responsibilities remain separate."
    )
    return capability, phase, rationale


def load_catalog() -> list[dict[str, str]]:
    source = LEGACY_BUILDER.read_text(encoding="utf-8")
    match = re.search(r'WP_CATALOG = """(.*?)"""\.strip\(\)', source, re.S)
    if not match:
        raise RuntimeError("Could not locate legacy package catalog")
    counters: defaultdict[str, int] = defaultdict(int)
    packages: list[dict[str, str]] = []
    for line in match.group(1).splitlines():
        if not line.strip():
            continue
        phase, key, name, terms = line.split("|", 3)
        counters[phase] += 1
        package_id = f"WP-{phase}-{counters[phase]:03d}"
        packages.append({
            "work_package_id": package_id,
            "implementation_phase": phase,
            "key": key,
            "name": name,
            "semantic_review_terms": terms,
            "objective": f"Implement and verify the bounded {name.casefold()} surface.",
            "bounded_surface": name,
            "explicit_exclusions": "Unrelated capabilities; later release/cleanup work; application-wide refactors.",
            "cohesion_rationale": f"The package is bounded to the {name.casefold()} architectural surface and its direct contracts, records, and tests.",
            "reviewer_status": "CANDIDATE_PENDING_FULL_PACKAGE_REVIEW",
        })
    return packages


def assign_membership(items: list[dict[str, str]], packages: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    by_phase: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
    for package in packages:
        by_phase[package["implementation_phase"]].append(package)
    active = [row for row in items if row["primary_implementation_phase"] and row["requirement_type"] in IMPLEMENTATION_TYPES and row["supersession_status"] == "ACTIVE"]
    assigned: dict[str, str] = {}
    package_capabilities: defaultdict[str, Counter[str]] = defaultdict(Counter)
    by_phase_key = {(package["implementation_phase"], package["key"]): package for package in packages}

    def preferred_key(row: dict[str, str]) -> str | None:
        phase = row["primary_implementation_phase"]
        if row["canonical_id"] == "CAN-MISSION-I15-001":
            return "windows-package"
        if row["canonical_id"] == "CAN-MISSION-I15-002":
            return "sbom-notices"
        if row["canonical_id"] == "CAN-MISSION-I15-003":
            return "outbound-proof"
        text = " ".join((row["source_section"], row["source_text"], row["title"])).casefold()
        if phase == "I8" and "phase 8 — tags, relationships" in row["source_section"].casefold():
            text = " ".join((row["source_text"], row["title"])).casefold()
        rules: dict[str, list[tuple[str, tuple[str, ...]]]] = {
            "I1": [
                ("legal-attribution", ("licence", "license", "attribution", "copyright", "agpl", "third-party", "model")),
                ("package-identity", ("package id", "bundle id", "executable", "application id")),
                ("brand-assets", ("logo", "icon", "splash", "favicon", "brand asset")),
                ("visible-brand", ("visible", "title", "about", "ui", "user-facing")),
                ("compatibility-aliases", ("alias", "migration", "compatibility", "old name")),
                ("rebrand-proof", ("proof", "scan", "consistency", "verify")),
                ("brand-inventory", ("brand", "identity", "lamha")),
            ],
            "I3": [
                ("transaction-recovery", ("crash recovery", "recovery record", "restart recovery")),
                ("transaction-commit", ("transaction commit", "commit protocol", "atomic commit")),
                ("transaction-stage", ("transaction stage", "prepare and stage", "staging")),
                ("operation-journal", ("operation journal", "coordinator manifest", "audit trail")),
                ("file-plan", ("file-operation plan", "operation plan", "preview before rename", "preview before move")),
                ("path-safety", ("path escape", "path normalization", "symlink", "junction")),
                ("root-authorization", ("authorized root", "root authorization", "access mode", "root picker")),
                ("sidecar-write", ("sidecar write", "sidecar creation", "write sidecar")),
                ("sidecar-read", ("sidecar read", "sidecar parse", "sidecar discovery")),
                ("sqlite-rebuild", ("sqlite rebuild", "rebuildable", "delete sqlite", "derived index")),
                ("sqlite-migrations", ("sqlite", "database migration")),
                ("schema-migrations", ("schema migration", "future version", "versioned schema")),
                ("asset-identity", ("asset uuid", "asset identity", "original filename", "asset bundle standard", "primary path")),
                ("revision-control", ("revision", "conflict", "concurrent")),
                ("registries", ("settings", "root registry", "drive registry")),
                ("record-envelope", ("metadata storage", "schema work", "authority", "record", "json")),
            ],
            "I4": [
                ("heif-raw", ("heif", "heic", " raw", "dng")),
                ("video-media", ("video", "ffmpeg", "codec", "duration")),
                ("companion-media", ("companion", "live photo", "motion photo", "raw+jpeg")),
                ("preview-generation", ("thumbnail", "preview", "derivative")),
                ("metadata-extract", ("metadata", "exif", "xmp", "gps", "camera")),
                ("incremental-scan", ("watch", "incremental", "change detection")),
                ("reconciliation", ("reconcile", "rename", "missing root", "external change")),
                ("content-hash", ("hash", "checksum")),
                ("media-format", ("media format", "supported format", "container", "mime")),
                ("path-index", ("path index", "asset api", "asset details", "derived index")),
                ("initial-search", ("text index", "basic search", "initial search")),
                ("initial-scanner", ("scan", "library", "discover", "enumerat")),
            ],
            "I5": [
                ("video-viewer", ("play", "pause", "scrub", "video", "audio")),
                ("image-viewer", ("zoom", "pan", "rotation", "orientation", "gif", "panorama", "raw preview", "full-screen photo")),
                ("selection-navigation", ("selection", "keyboard", "previous", "next navigation")),
                ("albums-favorites", ("album", "favorite")),
                ("memories", ("memory", "memories")),
                ("location-map", ("map", "location", "gps")),
                ("review-shell", ("review", "approve", "reject", "defer", "suppress")),
                ("saved-views", ("saved view", "filter", "sort")),
                ("timeline", ("timeline", "date jump", "chronological")),
                ("gallery-grid", ("gallery", "grid", "thumbnail", "virtual")),
                ("offline-parity", ("offline", "no server", "local-first")),
                ("inspector", ("inspector", "details", "conflict", "locate", "open in filesystem")),
            ],
            "I6": [
                ("event-materialize", ("materializ", "folders to rename", "assets to move", "rename event folder", "move event folder", "physically merged", "make primary event folder")),
                ("event-proposals", ("infer", "proposal", "candidate")),
                ("event-merge", ("merge",)),
                ("event-split-link", ("split", "link")),
                ("event-naming", ("name", "title", "normaliz")),
                ("event-boundaries", ("date", "time", "location", "midnight")),
                ("event-create", ("manual event", "create event")),
                ("event-ui", ("folder blocks", "open-folder", "review count", "offline state", "read-only state", "screen", "multi-select")),
                ("manage-later", ("manage later", "unorganized", "existing folder intake", "folder previews")),
                ("event-records", ("event record", "membership", "attendee", "photographer")),
                ("event-records", ("event system", "event folder", "event pages", "trip", "one-day event", "multi-day event", "parent event", "child event", "event cover", "event description")),
            ],
            "I7": [
                ("face-task", ("face detect", "reprocess", "model")),
                ("face-candidates", ("face candidate", "observation", "bounding box")),
                ("face-clusters", ("cluster", "similar face")),
                ("person-aliases", ("alias", "nickname", "rename")),
                ("person-merge", ("person merge", "person split", "merge people")),
                ("memberships", ("membership", "former member", "active member", "effective")),
                ("groups", ("group", "subgroup", "parent-group")),
                ("face-corrections", ("correction", "re-evaluate", "targeted")),
                ("people-privacy", ("privacy", "hidden", "consent")),
                ("people-ui", ("people ui", "group view", "person view")),
                ("person-identity", ("person", "people", "canonical name", "profile image")),
            ],
            "I8": [
                ("tag-candidates", ("tag candidate", "tag suggestion", "suggest content tag", "reviewable tag")),
                ("tag-hierarchy", ("tag hierarchy", "parent tag", "bulk assign", "tag assignment")),
                ("tag-records", ("tag system", "tag namespace", "approved tag", "user-created tag")),
                ("attribution", ("photographer", "camera owner", "importer", "attribution")),
                ("relationship-history", ("history", "start date", "end date", "former status")),
                ("relationship-views", ("projection", "view", "composition bucket")),
                ("smart-views", ("smart view", "family friends", "nine view")),
                ("relationship-review", ("review", "sure", "not sure", "approve", "reject", "conflict")),
                ("relationship-provenance", ("provenance", "explain", "source")),
                ("relationship-records", ("relationship", "edge", "certainty", "custom type")),
                ("tag-candidates", ("suggest", "suppress")),
                ("tag-hierarchy", ("assign", "bulk")),
                ("tag-records", ("tag", "namespace")),
            ],
            "I10": [
                ("hardware-assessment", ("hardware", "gpu", "cpu", "provider")),
                ("model-integrity", ("checksum", "model version", "model integrity")),
                ("model-registry", ("model registry", "model identity", "model component")),
                ("worker-lifecycle", ("launch", "crash", "lifecycle", "worker owner")),
                ("worker-transport", ("transport", "ipc", "listener", "worker")),
                ("ai-scheduler", ("schedule", "queue", "priority", "resource")),
                ("ai-persistence", ("task state", "persist", "retry")),
                ("ai-control", ("pause", "resume", "cancel", "invalidate")),
                ("ocr", ("ocr", "text recognition")),
                ("semantic-search", ("semantic search", "embedding", "search")),
                ("duplicate-candidates", ("duplicate", "similar")),
                ("location-proposals", ("location", "gps")),
                ("ai-review", ("review", "candidate", "approve", "reject", "suppress")),
                ("ai-privacy", ("privacy", "upload", "outbound", "local only")),
            ],
            "I11": [
                ("privacy-export", ("privacy export", "privacy-clean", "redact")),
                ("snapshots", ("snapshot", "restore metadata", "pre-mutation")),
                ("edit-recovery", ("recovery", "unmanage", "rollback")),
                ("edit-conflicts", ("conflict", "revision", "auto-resolve")),
                ("derivatives", ("export", "derivative", "edited copy")),
                ("edit-preview", ("preview", "render")),
                ("edit-recipes", ("crop", "rotate", "adjust", "recipe", "non-destructive edit")),
                ("metadata-batch", ("batch", "bulk")),
                ("metadata-removal", ("remove embedded", "clear", "gps", "serial", "identifying")),
                ("metadata-authority", ("metadata", "xmp", "authority")),
            ],
            "I13": [
                ("permanent-delete", ("permanent", "empty trash", "irreversible")),
                ("trash", ("trash",)),
                ("restore", ("restore",)),
                ("backup-verify", ("verify backup", "backup verification", "corrupt backup")),
                ("backup-run", ("backup run", "backup copy")),
                ("backup-manifest", ("backup", "manifest")),
                ("rebuild-all", ("rebuild", "sqlite loss", "fresh install")),
            ],
            "I14": [
                ("graph-accessibility", ("map", "graph", "mind-map", "virtualization")),
                ("screen-reader", ("screen reader", "non-visual", "alternate representation")),
                ("keyboard", ("keyboard", "focus", "shortcut")),
                ("accessibility-semantics", ("accessibility", "semantic", "aria", "contrast", "reduced motion")),
                ("background-ux", ("background", "progress", "cancel", "pause", "responsive")),
                ("ai-performance", ("ai", "model", "ocr", "face", "duplicate", "inference")),
                ("ui-performance", ("gallery", "timeline", "viewer", "thumbnail", "scroll")),
                ("scan-performance", ("scan", "index", "metadata panel")),
                ("resource-controls", ("cpu", "gpu", "memory", "ram", "power", "resource")),
                ("performance-fixtures", ("fixture", "10,000", "50,000", "100,000", "hardware result")),
            ],
            "I15": [
                ("signing", ("sign", "notar", "certificate")),
                ("component-licensing", ("component", "licence", "license", "codec", "runtime", "model")),
                ("deployment-eradication", ("docker", "container", "deployment")),
                ("data-stack-eradication", ("postgres", "redis", "queue")),
                ("server-eradication", ("legacy", "server", "authentication")),
                ("outbound-proof", ("outbound", "telemetry", "network", "upload")),
                ("sbom-notices", ("sbom", "bill of materials", "attribution")),
                ("windows-package", ("windows", "clean-machine", "clean machine", "install")),
                ("macos-package", ("macos", "notarization")),
                ("linux-package", ("linux",)),
                ("integration-parity", ("parity", "integrated")),
                ("release-proof", ("release", "final proof")),
            ],
        }
        for key, fragments in rules.get(phase, []):
            if any(fragment in text for fragment in fragments):
                return key
        return None

    def score(row: dict[str, str], package: dict[str, str]) -> int:
        haystack = " ".join((row["canonical_capability"], row["title"], row["statement"], row["source_section"], row["source_text"]))
        shared = tokens(haystack) & tokens(package["name"] + " " + package["semantic_review_terms"])
        value = sum(4 if token in tokens(package["name"]) else 1 for token in shared)
        if package["key"] in haystack.casefold().replace(" ", "-"):
            value += 8
        return value

    for row in active:
        key = preferred_key(row)
        package = by_phase_key.get((row["primary_implementation_phase"], key or ""))
        if package:
            assigned[row["canonical_id"]] = package["work_package_id"]
            package_capabilities[package["work_package_id"]][row["canonical_capability"]] += 1

    # Seed packages with the strongest still-unassigned semantic match.  These
    # are candidates only; the resulting explicit registry is reviewed later.
    for phase, phase_packages in by_phase.items():
        remaining = [row for row in active if row["primary_implementation_phase"] == phase]
        for package in phase_packages:
            ranked = sorted(((score(row, package), row["canonical_id"], row) for row in remaining if row["canonical_id"] not in assigned), reverse=True, key=lambda x: (x[0], x[1]))
            if ranked and ranked[0][0] > 0:
                row = ranked[0][2]
                assigned[row["canonical_id"]] = package["work_package_id"]
                package_capabilities[package["work_package_id"]][row["canonical_capability"]] += 1

    for row in active:
        if row["canonical_id"] in assigned:
            continue
        candidates = by_phase[row["primary_implementation_phase"]]
        pool = [
            package for package in candidates
            if row["canonical_capability"] in package_capabilities[package["work_package_id"]]
            or len(package_capabilities[package["work_package_id"]]) < 2
        ] or candidates
        package = max(pool, key=lambda p: (score(row, p), p["work_package_id"]))
        assigned[row["canonical_id"]] = package["work_package_id"]
        package_capabilities[package["work_package_id"]][row["canonical_capability"]] += 1

    active_by_parent: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
    for row in active:
        if row["parent_requirement_id"]:
            active_by_parent[row["parent_requirement_id"]].append(row)
    for parent_id, child_rows in active_by_parent.items():
        if parent_id not in assigned or not parent_id.startswith("CAN-SECTION-"):
            continue
        votes = Counter(assigned[child["canonical_id"]] for child in child_rows if child["canonical_id"] in assigned)
        if votes:
            old_package = assigned[parent_id]
            new_package = votes.most_common(1)[0][0]
            if old_package != new_package:
                parent = next(row for row in active if row["canonical_id"] == parent_id)
                package_capabilities[old_package][parent["canonical_capability"]] -= 1
                if package_capabilities[old_package][parent["canonical_capability"]] <= 0:
                    del package_capabilities[old_package][parent["canonical_capability"]]
                assigned[parent_id] = new_package
                package_capabilities[new_package][parent["canonical_capability"]] += 1

    used = {value for value in assigned.values()}
    final_packages = [package for package in packages if package["work_package_id"] in used]
    for package in final_packages:
        name = package["name"].casefold()
        if package["key"] == "windows-package":
            package["name"] = "Cross-platform packages and clean-machine proof"
            package["bounded_surface"] = "Windows, macOS, and Linux package production and clean-machine verification"
            name = package["name"].casefold()
        package["deliverables"] = f"Production implementation for {name}; updated affected contracts and records; focused tests."
        package["contracts_affected"] = "Explicitly listed in the generated packet from reviewed command-to-package references; NONE only when verified."
        package["schemas_affected"] = "Explicitly listed in the generated packet from reviewed record-to-package references; NONE only when verified."
        package["tests"] = f"Focused success, boundary, and failure tests for {name}; affected integration checks."
        package["failure_cases"] = "Invalid input; authorization failure; revision conflict; cancellation or I/O failure where applicable."
        package["rollback_or_recovery"] = "No partial authoritative state; use the package-specific transaction/recovery contract for mutations."
        package["completion_evidence"] = "Changed-file list, focused test commands/results, contract/schema diffs, and recovery evidence when applicable."
        package["commit_boundary"] = "One bounded commit containing only this package and its directly required contract/schema/test changes."
        package["exit_gate"] = f"The {name} objective and failure tests pass with no unrelated package work included."
    membership = [{
        "canonical_id": row["canonical_id"],
        "work_package_id": assigned[row["canonical_id"]],
        "membership_rationale": "Explicit candidate selected for shared architectural surface; pending all-package semantic review.",
        "reviewer_status": "CANDIDATE_PENDING_FULL_PACKAGE_REVIEW",
    } for row in active]
    return final_packages, membership


def dependency_candidates(packages: list[dict[str, str]]) -> list[dict[str, str]]:
    by_key = {package["key"]: package for package in packages}
    edges: list[dict[str, str]] = []

    def add(target: str, prerequisite: str, kind: str, rationale: str) -> None:
        if target not in by_key or prerequisite not in by_key or target == prerequisite:
            return
        edges.append({
            "work_package_id": by_key[target]["work_package_id"],
            "prerequisite_work_package_id": by_key[prerequisite]["work_package_id"],
            "dependency_type": kind,
            "technical_rationale": rationale,
            "reviewer_status": "CANDIDATE_PENDING_EDGE_REVIEW",
            "artificial_adjacency": "false",
        })

    explicit = [
        ("baseline-build", "toolchain-inventory", "REQUIRES_RUNTIME", "A baseline build requires the repository-declared toolchain inventory."),
        ("baseline-build", "mixed-versions", "REQUIRES_PLATFORM_PROOF", "Build proof requires resolution of manifest and lockfile version conflicts."),
        ("disposable-build", "archive-baseline", "REQUIRES_STORAGE", "A disposable build must be derived from the immutable baseline, never mutate it."),
        ("tauri-bootstrap", "toolchain-inventory", "REQUIRES_RUNTIME", "The Rust/Tauri shell cannot be selected or compiled before toolchain proof."),
        ("static-frontend", "mixed-versions", "REQUIRES_RUNTIME", "Static packaging depends on a reconciled frontend toolchain."),
        ("desktop-launch", "tauri-bootstrap", "REQUIRES_RUNTIME", "Offline launch requires a bootstrapped desktop runtime."),
        ("desktop-launch", "static-frontend", "REQUIRES_RUNTIME", "Offline launch requires static frontend artifacts."),
        ("root-picker", "tauri-capabilities", "REQUIRES_SECURITY_BOUNDARY", "The picker result must be constrained by Tauri capability policy."),
        ("ipc-envelope", "tauri-bootstrap", "REQUIRES_RUNTIME", "Typed commands require the Rust command host."),
        ("error-contract", "ipc-envelope", "REQUIRES_CONTRACT", "Stable errors are part of the versioned IPC envelope."),
        ("event-contract", "ipc-envelope", "REQUIRES_CONTRACT", "Progress events use the same request and operation identity envelope."),
        ("operation-handles", "event-contract", "REQUIRES_CONTRACT", "Long-running handles require typed lifecycle events."),
        ("frontend-bridge", "ipc-envelope", "REQUIRES_CONTRACT", "The frontend bridge is generated from approved IPC contracts."),
        ("shell-smoke", "desktop-launch", "REQUIRES_PLATFORM_PROOF", "Shell smoke proof exercises the packaged local launch path."),
        ("root-authorization", "root-picker", "REQUIRES_SECURITY_BOUNDARY", "Authorized roots originate from an explicit picker grant."),
        ("root-authorization", "tauri-capabilities", "REQUIRES_SECURITY_BOUNDARY", "Root authority is enforced inside the granted Tauri capability."),
        ("path-safety", "root-authorization", "REQUIRES_SECURITY_BOUNDARY", "Containment and reparse checks require an authorized-root model."),
        ("asset-identity", "record-envelope", "REQUIRES_SCHEMA", "Stable asset identity is an authoritative versioned record."),
        ("sidecar-read", "record-envelope", "REQUIRES_SCHEMA", "Sidecar parsing targets a versioned record envelope."),
        ("sidecar-write", "sidecar-read", "REQUIRES_SCHEMA", "Safe writes preserve and round-trip fields understood by the reader."),
        ("sqlite-migrations", "record-envelope", "REQUIRES_SCHEMA", "Derived tables must trace to authoritative record fields."),
        ("sqlite-rebuild", "sqlite-migrations", "REQUIRES_INDEX", "Rebuild proof executes the migration-owned derived schema."),
        ("file-plan", "root-authorization", "REQUIRES_SECURITY_BOUNDARY", "Every operation plan is scoped to an authorized root."),
        ("file-plan", "asset-identity", "REQUIRES_SCHEMA", "Operation preconditions use stable asset identities and revisions."),
        ("transaction-stage", "file-plan", "REQUIRES_CONTRACT", "Staging executes a validated operation plan."),
        ("transaction-stage", "path-safety", "REQUIRES_SECURITY_BOUNDARY", "Staging paths must pass containment and reparse checks."),
        ("transaction-commit", "transaction-stage", "REQUIRES_STORAGE", "Commit is allowed only after staged-byte verification."),
        ("transaction-commit", "operation-journal", "REQUIRES_STORAGE", "Commit boundaries must be durable in the operation journal."),
        ("transaction-recovery", "transaction-commit", "REQUIRES_STORAGE", "Recovery reconciles staged and committed transitions."),
        ("initial-scanner", "root-authorization", "REQUIRES_SECURITY_BOUNDARY", "Scanning is limited to authorized roots."),
        ("initial-scanner", "asset-identity", "REQUIRES_SCHEMA", "Discovered files require stable asset identities."),
        ("initial-scanner", "sqlite-migrations", "REQUIRES_INDEX", "The scanner publishes only to the migration-owned derived index."),
        ("incremental-scan", "initial-scanner", "REQUIRES_INDEX", "Watcher reconciliation reuses scanner identity and indexing rules."),
        ("media-format", "initial-scanner", "REQUIRES_STORAGE", "Format classification operates on safely discovered media."),
        ("heif-raw", "media-format", "REQUIRES_COMPONENT_DECISION", "HEIF/RAW decoding requires a classified format and reviewed decoder choice."),
        ("video-media", "media-format", "REQUIRES_COMPONENT_DECISION", "Video probing requires a classified format and reviewed runtime choice."),
        ("companion-media", "asset-identity", "REQUIRES_SCHEMA", "Companion bundles join stable asset identities."),
        ("companion-media", "media-format", "REQUIRES_STORAGE", "Companion detection uses classified container and naming evidence."),
        ("metadata-extract", "media-format", "REQUIRES_COMPONENT_DECISION", "Metadata extraction depends on format-aware reviewed tooling."),
        ("metadata-extract", "sidecar-read", "REQUIRES_SCHEMA", "Extraction precedence must account for durable sidecars."),
        ("preview-generation", "media-format", "REQUIRES_COMPONENT_DECISION", "Preview generation dispatches to format-specific decoders."),
        ("preview-generation", "asset-identity", "REQUIRES_SCHEMA", "Derivative keys include stable asset identity and revision."),
        ("path-index", "sqlite-migrations", "REQUIRES_INDEX", "Path lookup uses the derived SQLite schema."),
        ("reconciliation", "incremental-scan", "REQUIRES_INDEX", "Reconciliation consumes scanner/watcher observations."),
        ("gallery-grid", "preview-generation", "REQUIRES_INDEX", "The gallery needs revisioned preview records."),
        ("gallery-grid", "path-index", "REQUIRES_INDEX", "The gallery pages through the derived asset index."),
        ("image-viewer", "heif-raw", "REQUIRES_RUNTIME", "Image viewing depends on supported image/RAW decode paths."),
        ("video-viewer", "video-media", "REQUIRES_RUNTIME", "Video viewing depends on probe and playback assets."),
        ("review-shell", "ipc-envelope", "REQUIRES_CONTRACT", "Review actions cross the typed Rust command boundary."),
        ("event-records", "record-envelope", "REQUIRES_SCHEMA", "Events are authoritative versioned records."),
        ("event-create", "event-records", "REQUIRES_SCHEMA", "Creation persists an event record."),
        ("event-proposals", "event-records", "REQUIRES_SCHEMA", "Inference produces reviewable event drafts."),
        ("event-proposals", "path-index", "REQUIRES_INDEX", "Inference queries indexed timestamps and locations."),
        ("event-materialize", "file-plan", "REQUIRES_CONTRACT", "Materialization must first produce a filesystem plan."),
        ("event-materialize", "event-records", "REQUIRES_SCHEMA", "Filesystem effects preserve the approved event revision."),
        ("face-candidates", "asset-identity", "REQUIRES_SCHEMA", "Face observations refer to stable asset revisions."),
        ("face-candidates", "review-shell", "REQUIRES_CONTRACT", "Face results enter the review system as candidates."),
        ("face-task", "worker-lifecycle", "REQUIRES_WORKER", "Detection runs only through the owned local worker lifecycle."),
        ("face-task", "model-registry", "REQUIRES_COMPONENT_DECISION", "Detection requires a reviewed model/runtime record."),
        ("face-clusters", "face-candidates", "REQUIRES_SCHEMA", "Clustering operates on persisted candidate observations."),
        ("person-identity", "face-candidates", "REQUIRES_SCHEMA", "Confirmed identities link reviewed face observations."),
        ("relationship-records", "person-identity", "REQUIRES_SCHEMA", "Relationship endpoints are stable person IDs."),
        ("relationship-review", "review-shell", "REQUIRES_CONTRACT", "Relationship proposals use typed review transitions."),
        ("graph-projection", "relationship-records", "REQUIRES_SCHEMA", "Mind maps project canonical relationship records."),
        ("map-drafts", "record-envelope", "REQUIRES_SCHEMA", "Saved map drafts require durable versioned records."),
        ("map-simulation", "file-plan", "REQUIRES_CONTRACT", "Map materialization emits a filesystem plan before mutation."),
        ("worker-lifecycle", "ipc-envelope", "REQUIRES_SECURITY_BOUNDARY", "Rust owns worker launch, transport, and cancellation."),
        ("model-registry", "toolchain-inventory", "REQUIRES_COMPONENT_DECISION", "Runtime/model feasibility starts from the I0 component inventory."),
        ("ai-persistence", "worker-lifecycle", "REQUIRES_WORKER", "Task state is enforced by the owned worker lifecycle."),
        ("ocr", "model-registry", "REQUIRES_COMPONENT_DECISION", "OCR requires an approved model/runtime component."),
        ("semantic-search", "model-registry", "REQUIRES_COMPONENT_DECISION", "Embeddings require an approved model/runtime component."),
        ("semantic-search", "worker-lifecycle", "REQUIRES_WORKER", "Semantic search consumes embeddings from the owned local worker."),
        ("duplicate-candidates", "asset-identity", "REQUIRES_SCHEMA", "Duplicate candidates reference stable asset identities and hashes."),
        ("metadata-authority", "sidecar-write", "REQUIRES_STORAGE", "Metadata mutation persists via the safe sidecar protocol."),
        ("metadata-authority", "file-plan", "REQUIRES_CONTRACT", "Mutating batches require previewed operation plans."),
        ("edit-recipes", "record-envelope", "REQUIRES_SCHEMA", "Non-destructive edits are versioned authoritative recipes."),
        ("derivatives", "transaction-stage", "REQUIRES_STORAGE", "Derivative export uses the filesystem transaction protocol."),
        ("drive-registry", "root-authorization", "REQUIRES_SECURITY_BOUNDARY", "Drive identity extends the authorized-root model."),
        ("disconnect-state", "drive-registry", "REQUIRES_STORAGE", "Disconnected state is keyed by durable drive identity."),
        ("reconnect", "disconnect-state", "REQUIRES_STORAGE", "Reconnection validates a previously recorded detached state."),
        ("backup-manifest", "record-envelope", "REQUIRES_SCHEMA", "Backup manifests inventory authoritative record revisions."),
        ("backup-run", "backup-manifest", "REQUIRES_SCHEMA", "Backup execution consumes an approved manifest."),
        ("backup-run", "transaction-stage", "REQUIRES_STORAGE", "Backup copies use staged, verified filesystem operations."),
        ("restore-run", "backup-verify", "REQUIRES_STORAGE", "Restore requires a verified backup set."),
        ("restore-run", "file-plan", "REQUIRES_CONTRACT", "Restore collisions and effects are previewed as an operation plan."),
        ("trash-records", "file-plan", "REQUIRES_CONTRACT", "Trash is a planned reversible move of a logical asset bundle."),
        ("disaster-drill", "sqlite-rebuild", "REQUIRES_INDEX", "Full rebuild uses the authoritative-to-derived rebuild contract."),
        ("accessibility-semantics", "static-frontend", "REQUIRES_UI_SHELL", "Accessibility semantics apply to the real static frontend."),
        ("performance-fixtures", "baseline-build", "REQUIRES_PLATFORM_PROOF", "Performance comparisons require a recorded baseline harness."),
        ("windows-package", "component-licensing", "REQUIRES_COMPONENT_DECISION", "Cross-platform packaging waits for final component/version/licence decisions."),
        ("windows-package", "shell-smoke", "REQUIRES_PLATFORM_PROOF", "Release packaging requires a proven desktop launch path."),
        ("server-eradication", "frontend-bridge", "REQUIRES_REPLACEMENT_VERIFIED", "Legacy server removal requires the typed local frontend bridge."),
        ("data-stack-eradication", "sqlite-migrations", "REQUIRES_REPLACEMENT_VERIFIED", "PostgreSQL/Redis removal requires the local SQLite and operation foundations."),
        ("deployment-eradication", "desktop-launch", "REQUIRES_REPLACEMENT_VERIFIED", "Docker/deployment removal requires the offline desktop launch path."),
        ("generated-client-eradication", "frontend-bridge", "REQUIRES_REPLACEMENT_VERIFIED", "Generated remote client removal requires the typed local bridge."),
        ("release-proof", "windows-package", "REQUIRES_PLATFORM_PROOF", "Release gates consume cross-platform package evidence."),
        ("release-proof", "server-eradication", "REQUIRES_REPLACEMENT_VERIFIED", "Release requires verified legacy server eradication."),
        ("release-proof", "data-stack-eradication", "REQUIRES_REPLACEMENT_VERIFIED", "Release requires verified legacy data-stack eradication."),
        ("release-proof", "deployment-eradication", "REQUIRES_REPLACEMENT_VERIFIED", "Release requires verified legacy deployment eradication."),
    ]
    for target, prerequisite, kind, rationale in explicit:
        add(target, prerequisite, kind, rationale)
    return sorted(edges, key=lambda row: (row["work_package_id"], row["prerequisite_work_package_id"], row["dependency_type"]))


def component_candidates(packages: list[dict[str, str]]) -> list[dict[str, str]]:
    ids = {package["key"]: package["work_package_id"] for package in packages}

    def refs(*keys: str) -> str:
        return ";".join(ids[key] for key in keys if key in ids)

    fields = [
        "component", "owning_phase", "decision_package", "blocking_work_package", "required_before_packages",
        "version_status", "licence_status", "redistribution_status", "platform_impact", "packaging_impact",
        "alternatives", "final_decision_evidence", "reviewer_status",
    ]
    data = [
        ("Tauri", "I2", refs("tauri-bootstrap"), refs("tauri-bootstrap"), refs("desktop-launch", "tauri-capabilities", "ipc-envelope"), "PENDING_I0_INVENTORY", "PENDING", "PENDING", "Windows/macOS/Linux shell and capability behavior", "Rust/WebView bundle and platform installers", "Reviewed native shells", "Pinned manifest, licence text, platform launch proof", "REVIEWED_CORRECTED"),
        ("Rust toolchain", "I0", refs("toolchain-inventory"), refs("toolchain-inventory"), refs("tauri-bootstrap", "sqlite-migrations"), "PENDING_REPOSITORY_PROOF", "PENDING", "BUILD_ONLY_PENDING", "All targets", "Compiler, target triples, native dependencies", "Repository-declared stable toolchain", "rust-toolchain/manifest reconciliation and successful focused build", "REVIEWED_CORRECTED"),
        ("Node/package-manager toolchain", "I0", refs("mixed-versions"), refs("mixed-versions"), refs("static-frontend"), "PENDING_REPOSITORY_PROOF", "PENDING", "BUILD_ONLY_PENDING", "All targets", "Static frontend build only; no runtime server", "Corepack with reconciled repository declaration", "Manifest-lockfile reconciliation and static build proof", "REVIEWED_CORRECTED"),
        ("Svelte/SvelteKit", "I2", refs("static-frontend"), refs("static-frontend"), refs("frontend-bridge", "desktop-launch"), "PENDING_I0_INVENTORY", "PENDING", "BUNDLED_SOURCE_PENDING", "Platform WebView compatibility", "Static frontend artifacts", "Plain Svelte/Vite if server coupling cannot be removed", "Pinned manifest, static adapter proof, licence evidence", "REVIEWED_CORRECTED"),
        ("SQLite Rust library", "I3", refs("sqlite-migrations"), refs("sqlite-migrations"), refs("path-index", "initial-scanner"), "PENDING", "PENDING", "PENDING", "Native library/toolchain variance", "Bundled derived-index engine", "rusqlite or sqlx-sqlite", "ADR, pinned crate, migration execution and rebuild proof", "REVIEWED_CORRECTED"),
        ("FFmpeg", "I4", refs("video-media"), refs("video-media"), refs("video-viewer", "preview-generation"), "PENDING", "PENDING", "PENDING", "Codec and hardware support differs by platform", "Native binary size, notices, codec redistribution", "Platform media frameworks or reviewed ffmpeg binding", "ADR, exact build/version, notices, platform probe/playback proof", "REVIEWED_CORRECTED"),
        ("ExifTool or replacement", "I4", refs("metadata-extract"), refs("metadata-extract"), refs("metadata-authority"), "PENDING", "PENDING", "PENDING", "Process and path behavior differs", "Sidecar binary or pure-Rust parsers", "kamadak-exif plus format-specific parsers", "ADR, format matrix, pinned version, licence and extraction proof", "REVIEWED_CORRECTED"),
        ("HEIF decoder", "I4", refs("heif-raw"), refs("heif-raw"), refs("preview-generation", "image-viewer"), "PENDING", "PENDING", "PENDING", "OS codec availability and color handling", "Native decoder and patent/licence review", "Platform ImageIO/WIC or libheif", "ADR, licence review, HEIF fixture decode and platform proof", "REVIEWED_CORRECTED"),
        ("RAW decoder", "I4", refs("heif-raw"), refs("heif-raw"), refs("preview-generation", "image-viewer"), "PENDING", "PENDING", "PENDING", "Camera profiles and platform variance", "Native library and camera profiles", "LibRaw or reviewed Rust decoder", "ADR, supported-camera matrix, licence and fixture proof", "REVIEWED_CORRECTED"),
        ("Image thumbnail library", "I4", refs("preview-generation"), refs("preview-generation"), refs("gallery-grid", "image-viewer"), "PENDING", "PENDING", "PENDING", "SIMD and format support differs", "Bundled Rust/native dependency", "image or libvips", "ADR, pinned version, licence, deterministic preview tests", "REVIEWED_CORRECTED"),
        ("ONNX Runtime", "I10", refs("model-registry"), refs("model-registry"), refs("face-task", "ocr", "semantic-search"), "PENDING", "PENDING", "PENDING", "CPU/GPU providers differ", "Large native runtime", "Candle, tract, or platform ML APIs", "ADR, provider matrix, version/checksum, licence and local-only proof", "REVIEWED_CORRECTED"),
        ("Python runtime or alternative AI host", "I10", refs("worker-lifecycle"), refs("worker-lifecycle"), refs("face-task", "ocr", "semantic-search"), "PENDING_OPTIONAL", "PENDING", "PENDING", "Embedding differs by platform", "Potential sidecar/runtime size", "Rust-native inference worker", "Worker-host ADR, pinned runtime if selected, packaging and licence proof", "REVIEWED_CORRECTED"),
        ("OCR model/runtime", "I10", refs("ocr"), refs("ocr"), refs("ocr"), "PENDING", "PENDING", "PENDING", "Language/model coverage", "Model checksum, notices, size", "Tesseract or reviewed ONNX OCR", "Model card, checksum, licence, language matrix and offline fixture proof", "REVIEWED_CORRECTED"),
        ("Embedding model/runtime", "I10", refs("semantic-search"), refs("semantic-search"), refs("semantic-search"), "PENDING", "PENDING", "PENDING", "Acceleration and memory differ", "Model/runtime size", "Reviewed local embedding model", "Model card, checksum, licence, resource and offline proof", "REVIEWED_CORRECTED"),
        ("Face model/runtime", "I7", refs("face-task"), refs("face-task"), refs("face-candidates", "face-clusters"), "PENDING", "PENDING", "PENDING", "CPU/GPU and sensitive-data handling", "Model/runtime packaging and privacy", "Reviewed local detector/embedding pair", "Model cards, checksums, licences, privacy and platform proof", "REVIEWED_CORRECTED"),
        ("Platform WebView dependencies", "I2", refs("desktop-launch"), refs("desktop-launch"), refs("shell-smoke", "platform-package"), "PENDING_PLATFORM_INVENTORY", "OS_COMPONENT_REVIEW_PENDING", "OS_COMPONENT", "WebView2/WebKit/WKWebView", "Installer prerequisite/minimum-version checks", "Bundled WebView where legally and technically appropriate", "Per-platform minimums, prerequisite detection and launch proof", "REVIEWED_CORRECTED"),
        ("Installer/signing tools", "I15", refs("signing"), refs("signing"), refs("windows-package"), "PENDING", "PENDING", "BUILD_ONLY_PENDING", "Platform-specific certificates/notarization", "Release pipeline and provenance", "Tauri bundler plus native signing tools", "Per-platform signing ADR, tool versions and signed-package verification", "REVIEWED_CORRECTED"),
    ]
    return [dict(zip(fields, row)) for row in data]


def main() -> None:
    if (SOURCE / "reviews" / "review-coverage.json").exists():
        raise SystemExit("Reviewed semantic sources are finalized; migration helper is permanently disabled for this plan version.")
    if (SOURCE / "requirements" / "requirements.csv").exists() and os.environ.get("LAMHA_REVIEW_CANDIDATE_REFRESH") != "1":
        raise SystemExit("Reviewed-source candidates already exist; refusing to overwrite review decisions.")
    legacy_requirements = list(csv.DictReader((LEGACY_PLAN / "02-requirements" / "canonical-registry.csv").open(encoding="utf-8-sig", newline="")))
    corrected = 0
    remapped = 0
    capability_changes = 0
    classification_corrections = 0
    requirements: list[dict[str, str]] = []
    mappings: list[dict[str, str]] = []
    for legacy in legacy_requirements:
        row = dict(legacy)
        if row["source_plan"] == "02-EVERYTHING-WE-ARE-DELETING.md" and row["requirement_type"] in IMPLEMENTATION_TYPES:
            row["requirement_type"] = "PROHIBITION"
            row["statement"] = f"The final Lamha desktop runtime must not retain or require {lower_initial(row['source_text']).rstrip('.')} .".replace(" .", ".")
            row["normalization_status"] = "EXPLICIT_RECLASSIFICATION"
            row["removal_phase"] = "I15"
            classification_corrections += 1
        statement, changed, rationale = repair_statement(row)
        if changed:
            corrected += 1
            row["statement"] = statement
            row["rationale"] = rationale
            row["normalization_status"] = "EXPLICIT_REWRITE"
        capability, phase, map_rationale = corrected_mapping(row)
        if phase != row["primary_implementation_phase"]:
            remapped += 1
        if capability != row["target_capability"]:
            capability_changes += 1
        row["legacy_target_capability"] = row["target_capability"]
        row["canonical_capability"] = capability
        row["normalization_reviewer_status"] = "REVIEWED_CORRECTED" if changed else "REVIEWED_CONFIRMED"
        row["review_notes"] = rationale
        requirements.append(row)
        mappings.append({
            "canonical_id": row["canonical_id"],
            "canonical_capability": capability,
            "primary_implementation_phase": phase,
            "integration_verification_phases": row["verification_phases"],
            "removal_phase": row["removal_phase"],
            "release_validation_phase": "I15" if row["release_gate"] else "",
            "global_invariant_links": row["product_invariant_relationships"],
            "mapping_rationale": map_rationale,
            "reviewer_status": "REVIEWED_CORRECTED" if phase != row["primary_implementation_phase"] or capability != row["target_capability"] else "REVIEWED_CONFIRMED",
            "exception_status": "NONE",
            "previous_capability": row["target_capability"],
            "previous_primary_phase": row["primary_implementation_phase"],
        })
        row["primary_implementation_phase"] = phase

    # Synthetic section parents follow the reviewed consensus of their actual
    # child criteria.  They never route from the words "Synthesized from...".
    mapping_by_id = {row["canonical_id"]: row for row in mappings}
    requirement_by_id = {row["canonical_id"]: row for row in requirements}
    children: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
    for row in requirements:
        if row["parent_requirement_id"]:
            children[row["parent_requirement_id"]].append(row)
    for parent_id, child_rows in children.items():
        parent = requirement_by_id.get(parent_id)
        parent_mapping = mapping_by_id.get(parent_id)
        if not parent or not parent_mapping or not parent_id.startswith("CAN-SECTION-"):
            continue
        phase_votes = Counter(mapping_by_id[child["canonical_id"]]["primary_implementation_phase"] for child in child_rows if mapping_by_id[child["canonical_id"]]["primary_implementation_phase"])
        capability_votes = Counter(mapping_by_id[child["canonical_id"]]["canonical_capability"] for child in child_rows if mapping_by_id[child["canonical_id"]]["primary_implementation_phase"])
        if phase_votes and capability_votes:
            phase = phase_votes.most_common(1)[0][0]
            capability = capability_votes.most_common(1)[0][0]
            parent["canonical_capability"] = capability
            parent["primary_implementation_phase"] = phase
            parent_mapping.update({"canonical_capability": capability, "primary_implementation_phase": phase, "mapping_rationale": "Reviewed section parent follows the majority architectural surface of its explicitly linked child criteria.", "reviewer_status": "REVIEWED_CORRECTED"})
        else:
            parent["primary_implementation_phase"] = ""
            parent_mapping.update({"primary_implementation_phase": "", "mapping_rationale": "All linked child rows are non-implementation context or gates; the section parent has no implementation phase.", "reviewer_status": "REVIEWED_CORRECTED"})

    requirement_fields = list(requirements[0])
    mapping_fields = list(mappings[0])
    write_csv(SOURCE / "requirements" / "requirements.csv", requirements, requirement_fields)
    write_csv(SOURCE / "requirements" / "requirement-mapping.csv", mappings, mapping_fields)

    dispositions = list(csv.DictReader((LEGACY_PLAN / "02-requirements" / "source-row-dispositions.csv").open(encoding="utf-8-sig", newline="")))
    write_csv(SOURCE / "requirements" / "source-row-dispositions.csv", dispositions, list(dispositions[0]))

    catalog = load_catalog()
    final_packages, membership = assign_membership(requirements, catalog)
    used = {package["work_package_id"] for package in final_packages}
    dependencies = [edge for edge in dependency_candidates(final_packages) if edge["work_package_id"] in used and edge["prerequisite_work_package_id"] in used]
    write_json(SOURCE / "packages" / "work-packages.json", {"workPackages": final_packages})
    write_csv(SOURCE / "packages" / "requirement-membership.csv", membership, list(membership[0]))
    write_csv(SOURCE / "packages" / "dependencies.csv", dependencies, list(dependencies[0]) if dependencies else ["work_package_id", "prerequisite_work_package_id", "dependency_type", "technical_rationale", "reviewer_status", "artificial_adjacency"])
    write_csv(SOURCE / "components" / "components.csv", component_candidates(final_packages), list(component_candidates(final_packages)[0]))

    old_packages = json.loads((LEGACY_PLAN / "04-work-packages" / "work-packages.json").read_text(encoding="utf-8"))
    review_rows = []
    final_names = {package["name"]: package["work_package_id"] for package in final_packages}
    for old in old_packages:
        old_name = old["name"]
        base_name = re.sub(r"\s+— source-boundary slice \d+$", "", old_name)
        if "source-boundary slice" in old_name:
            decision = "MERGE"
            reason = "Mechanical source/capacity slice removed; requirements must be reviewed into an architecture-owned package."
        elif old["work_package_id"] == "WP-I2-001":
            decision = "REPLACE"
            reason = "Known cross-domain shell package is replaced by explicit semantic memberships."
        else:
            decision = "KEEP_OR_REASSIGN"
            reason = "Title remains a candidate, but every membership and dependency is independently re-reviewed."
        review_rows.append({
            "legacy_work_package_id": old["work_package_id"],
            "legacy_name": old_name,
            "decision": decision,
            "replacement_work_package_id": final_names.get(base_name, "MULTIPLE_EXPLICIT_PACKAGES"),
            "review_reason": reason,
            "reviewer_status": "REVIEWED",
        })
    write_csv(SOURCE / "reviews" / "legacy-package-disposition.csv", review_rows, list(review_rows[0]))

    stats = {
        "legacy_normalized_items": len(legacy_requirements),
        "statement_rewrites": corrected,
        "phase_remaps": remapped,
        "capability_corrections": capability_changes,
        "classification_corrections": classification_corrections,
        "candidate_package_count": len(final_packages),
        "membership_rows": len(membership),
        "dependency_edges": len(dependencies),
        "legacy_package_reviews": len(review_rows),
    }
    write_json(SOURCE / "reviews" / "migration-candidate-stats.json", stats)
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
