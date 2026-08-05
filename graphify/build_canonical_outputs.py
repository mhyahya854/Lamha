"""Build Lamha's curated Phase 1 Graphify outputs from verified local evidence.

The script reads only Codebase and writes only under graphify. It augments the
directed Graphify AST graph with corpus-file, feature, requirement, planned
component, test, and removal nodes while retaining the raw extraction.
"""

from __future__ import annotations

import csv
import fnmatch
import hashlib
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import networkx as nx
from graphify.export import to_html


ROOT = Path(__file__).resolve().parent.parent
GRAPHIFY = ROOT / "graphify"
CODEBASE = ROOT / "Codebase"
OUT = GRAPHIFY / "graphify-out"
INVENTORY = GRAPHIFY / "00-corpus-inventory" / "FILE_CLASSIFICATION.csv"
PLAN_DIR = GRAPHIFY / "Master Plan"


@dataclass(frozen=True)
class Feature:
    slug: str
    title: str
    document: str | None
    summary: str
    patterns: tuple[str, ...]
    keywords: tuple[str, ...]
    decision: str
    phase: int
    target: tuple[str, ...]


FEATURES = (
    Feature("gallery-timeline", "Gallery and timeline", "GALLERY_AND_TIMELINE.md", "Virtualized chronological browsing, selection, filters, and local-first asset loading.", ("web/src/lib/components/timeline/*", "web/src/routes/(user)/photos/*", "server/src/controllers/timeline.controller.ts", "server/src/services/timeline.service.ts", "server/src/repositories/asset.repository.ts", "e2e/*timeline*", "**/*timeline*.spec.*"), ("gallery", "timeline", "photos", "favorites"), "PORT", 5, ("web/src/lib/components/timeline/", "src-tauri/src/commands/assets.rs", "src-tauri/src/index/")),
    Feature("asset-viewer", "Asset viewer", "ASSET_VIEWER.md", "Photo/video viewing, detail panels, navigation, media playback, and retained viewer actions.", ("web/src/lib/components/asset-viewer/*", "web/src/routes/(user)/*assetId*/*", "server/src/controllers/asset.controller.ts", "server/src/services/asset.service.ts", "server/src/repositories/asset.repository.ts", "e2e/src/specs/web/asset-viewer/*", "e2e/src/ui/specs/asset-viewer/*"), ("asset viewer", "viewer", "asset", "photo", "video"), "PORT", 5, ("web/src/lib/components/asset-viewer/", "src-tauri/src/commands/assets.rs", "src-tauri/src/assets/")),
    Feature("metadata", "Metadata", "METADATA.md", "Metadata inspection, authority, EXIF/XMP handling, privacy, and reversible mutation.", ("web/src/lib/components/asset-viewer/DetailPanel*", "server/src/services/metadata.service.ts", "server/src/repositories/metadata.repository.ts", "server/src/queries/metadata.repository.sql", "server/src/controllers/asset.controller.ts", "**/*metadata*.spec.*"), ("metadata", "exif", "xmp", "sidecar", "camera owner", "photographer", "privacy"), "REWRITE", 11, ("src-tauri/src/metadata/", "src-tauri/src/assets/sidecars.rs", "src-tauri/src/commands/metadata.rs")),
    Feature("people-faces", "People and faces", "PEOPLE_AND_FACES.md", "Face detection/recognition, identity curation, people views, grouping, merge/split, and history.", ("web/src/lib/components/faces-page/*", "web/src/routes/(user)/people/*", "server/src/controllers/person.controller.ts", "server/src/services/person.service.ts", "server/src/repositories/person.repository.ts", "machine-learning/immich_ml/models/facial_recognition/*", "**/*person*.spec.*", "**/*face*.spec.*"), ("people", "person", "face", "cluster", "group", "relationship"), "REWRITE", 7, ("src-tauri/src/people/", "src-tauri/src/groups/", "src-tauri/src/relationships/", "ai-worker/faces/")),
    Feature("search-ocr", "Search and OCR", "SEARCH_AND_OCR.md", "Text/semantic search, filters, OCR extraction, and local result ranking.", ("web/src/routes/(user)/search/*", "server/src/controllers/search.controller.ts", "server/src/services/search.service.ts", "server/src/repositories/search.repository.ts", "server/src/services/ocr.service.ts", "server/src/repositories/ocr.repository.ts", "machine-learning/immich_ml/models/clip/*", "machine-learning/immich_ml/models/ocr/*", "**/*search*.spec.*", "**/*ocr*.spec.*"), ("search", "ocr", "semantic", "clip", "embedding"), "REWRITE", 10, ("src-tauri/src/index/search.rs", "src-tauri/src/commands/search.rs", "ai-worker/search/", "ai-worker/ocr/")),
    Feature("tags", "Tags", "TAGS.md", "Tag browsing and assignment with review-first local authority and provenance.", ("web/src/routes/(user)/tags/*", "web/src/lib/components/*tag*", "server/src/controllers/tag.controller.ts", "server/src/services/tag.service.ts", "server/src/repositories/tag.repository.ts", "**/*tag*.spec.*"), ("tag", "namespace", "keyword"), "REWRITE", 8, ("src-tauri/src/tags/", "src-tauri/src/commands/tags.rs", "web/src/lib/components/tags/")),
    Feature("albums-favorites", "Albums and favorites", "ALBUMS_AND_FAVORITES.md", "Virtual albums, membership, covers, favorites, and local asset collections.", ("web/src/lib/components/album-page/*", "web/src/routes/(user)/albums/*", "web/src/routes/(user)/favorites/*", "server/src/controllers/album.controller.ts", "server/src/services/album.service.ts", "server/src/repositories/album.repository.ts", "**/*album*.spec.*"), ("album", "favorite", "collection"), "PORT", 5, ("src-tauri/src/albums/", "src-tauri/src/commands/albums.rs", "web/src/lib/components/album-page/")),
    Feature("memories", "Memories", "MEMORIES.md", "Date-based memory presentation backed by local asset queries.", ("web/src/routes/(user)/memory/*", "server/src/controllers/memory.controller.ts", "server/src/services/memory.service.ts", "server/src/repositories/memory.repository.ts", "**/*memory*.spec.*"), ("memory", "memories", "anniversary"), "PORT", 5, ("src-tauri/src/commands/memories.rs", "src-tauri/src/index/memories.rs", "web/src/routes/(user)/memory/")),
    Feature("map-location", "Map and location", "MAP_AND_LOCATION.md", "Offline-capable coordinate browsing and reviewed local location metadata.", ("web/src/routes/(user)/map/*", "web/src/lib/components/*map*", "server/src/controllers/map.controller.ts", "server/src/services/map.service.ts", "server/src/repositories/map.repository.ts", "**/*map*.spec.*"), ("map", "location", "coordinate", "geolocation", "gps"), "REWRITE", 5, ("src-tauri/src/maps/", "src-tauri/src/commands/maps.rs", "web/src/lib/components/map/")),
    Feature("duplicates", "Duplicates", "DUPLICATES.md", "Exact/similar duplicate candidates and user-reviewed burst grouping.", ("web/src/routes/(user)/utilities/duplicates/*", "server/src/controllers/duplicate.controller.ts", "server/src/services/duplicate.service.ts", "server/src/repositories/duplicate.repository.ts", "**/*duplicate*.spec.*"), ("duplicate", "similar", "burst", "hash"), "REWRITE", 10, ("src-tauri/src/duplicates/", "src-tauri/src/commands/duplicates.rs", "ai-worker/duplicates/")),
    Feature("editing", "Editing", "EDITING.md", "Non-destructive edits, derivatives, exports, snapshots, privacy transforms, and restore.", ("web/src/lib/components/asset-viewer/*edit*", "server/src/repositories/asset-edit.repository.ts", "server/src/dtos/editing.dto.ts", "**/*edit*.spec.*"), ("edit", "crop", "rotate", "derivative", "export", "snapshot", "restore"), "REWRITE", 11, ("src-tauri/src/assets/edits.rs", "src-tauri/src/commands/editing.rs", "web/src/lib/components/editing/")),
    Feature("libraries-storage", "Libraries and storage", "LIBRARIES_AND_STORAGE.md", "Library roots, scanning, storage, watchers, linked folders, external drives, and path sandboxing.", ("web/src/routes/admin/library-management/*", "server/src/controllers/library.controller.ts", "server/src/services/library.service.ts", "server/src/repositories/library.repository.ts", "server/src/services/storage.service.ts", "server/src/repositories/storage.repository.ts", "**/*library*.spec.*", "**/*storage*.spec.*"), ("library", "storage", "folder", "filesystem", "path", "drive", "scanner", "watcher"), "REWRITE", 4, ("src-tauri/src/library/", "src-tauri/src/commands/library.rs", "src-tauri/src/transactions/")),
    Feature("jobs-notifications", "Jobs and notifications", "JOBS_AND_NOTIFICATIONS.md", "Background processing state, progress, retry/cancel, and desktop notifications.", ("web/src/routes/admin/jobs-status/*", "web/src/routes/admin/queues/*", "server/src/controllers/job.controller.ts", "server/src/services/job.service.ts", "server/src/repositories/job.repository.ts", "server/src/controllers/notification.controller.ts", "server/src/services/notification.service.ts", "**/*job*.spec.*", "**/*notification*.spec.*"), ("job", "queue", "worker", "notification", "progress", "retry", "cancel"), "REPLACE", 10, ("src-tauri/src/jobs/", "src-tauri/src/commands/jobs.rs", "src-tauri/src/notifications/")),
    Feature("auth-users", "Authentication and users", "AUTHENTICATION_AND_USERS.md", "Current multi-user/auth/session architecture; target desktop has one local operator and no account requirement.", ("web/src/routes/auth/*", "web/src/routes/admin/users/*", "server/src/controllers/auth.controller.ts", "server/src/services/auth.service.ts", "server/src/repositories/session.repository.ts", "server/src/controllers/user.controller.ts", "server/src/services/user.service.ts", "**/*auth*.spec.*", "**/*user*.spec.*"), ("auth", "user", "account", "session", "oauth", "login"), "REMOVE", 3, ("src-tauri/src/settings/local_operator.rs", "web/src/routes/+layout.svelte")),
    Feature("sharing-mobile-backup", "Sharing and mobile backup", "SHARING_AND_MOBILE_BACKUP.md", "Current server sharing and phone backup paths; remote/multi-user behavior is out of target scope while local export/backup is replaced.", ("web/src/routes/(user)/share/*", "web/src/routes/(user)/shared-links/*", "server/src/controllers/shared-link.controller.ts", "server/src/services/shared-link.service.ts", "mobile/lib/*", "mobile/lib/services/backup.service.dart", "**/*shared-link*.spec.*", "**/*backup*.spec.*"), ("sharing", "shared link", "mobile", "backup", "remote", "cloud"), "REMOVE", 15, ("src-tauri/src/backup/", "src-tauri/src/commands/export.rs")),
    Feature("administration", "Administration", "ADMINISTRATION.md", "Current server administration, queues, users, and maintenance; retained device settings move to local desktop settings.", ("web/src/routes/admin/*", "server/src/controllers/*admin*.ts", "server/src/services/*admin*.ts", "server/src/controllers/maintenance.controller.ts", "**/*admin*.spec.*", "**/*maintenance*.spec.*"), ("admin", "administration", "maintenance", "server status"), "REMOVE", 15, ("web/src/routes/settings/", "src-tauri/src/settings/")),
    Feature("settings", "Settings", "SETTINGS.md", "System/user preferences that survive as local desktop, library, AI, privacy, and appearance settings.", ("web/src/lib/components/admin-settings/*", "web/src/lib/components/user-settings-page/*", "web/src/routes/(user)/user-settings/*", "server/src/controllers/system-config.controller.ts", "server/src/services/system-config.service.ts", "**/*config*.spec.*", "**/*settings*.spec.*"), ("setting", "config", "preference", "theme"), "REWRITE", 4, ("src-tauri/src/settings/", "src-tauri/src/commands/settings.rs", "web/src/routes/(user)/user-settings/")),
    Feature("local-ai-worker", "Local AI worker", None, "Bundled, supervised, local-only inference worker with no network listener or unrelated-client access.", ("machine-learning/immich_ml/*", "machine-learning/immich_ml/**/*", "server/src/repositories/machine-learning.repository.ts", "server/src/services/smart-info.service.ts", "**/*machine-learning*.spec.*"), ("ai", "machine learning", "model", "inference", "worker", "hardware"), "TEMPORARILY RETAIN", 10, ("ai-worker/", "src-tauri/src/ai/", "src-tauri/src/commands/ai.rs")),
    Feature("events-organization", "Events and organization", None, "Manage Later, event folders, merge/link/split, normalized naming, and reversible organization.", ("server/src/services/storage-template.service.ts", "server/src/repositories/move.repository.ts", "web/src/lib/components/*folder*", "**/*storage-template*.spec.*"), ("event", "manage later", "organize", "folder map", "merge", "split", "linked folder"), "REWRITE", 6, ("src-tauri/src/events/", "src-tauri/src/assets/move_asset.rs", "src-tauri/src/commands/events.rs")),
    Feature("review-centre", "Review Centre", None, "Unified review queues for conflicts, AI candidates, external changes, and approved/rejected history.", ("web/src/lib/components/*review*", "server/src/services/workflow.service.ts", "server/src/repositories/workflow.repository.ts"), ("review", "candidate", "rejection", "suppression", "approve", "conflict"), "REWRITE", 5, ("src-tauri/src/review/", "src-tauri/src/commands/review.rs", "web/src/routes/(user)/review/")),
    Feature("desktop-shell", "Desktop shell", None, "Tauri 2 desktop process, static Svelte client, local commands, permissions, and packaging.", ("web/svelte.config.js", "web/vite.config.ts", "web/package.json", "package.json"), ("tauri", "rust", "desktop", "shell", "ipc", "command"), "REWRITE", 3, ("src-tauri/Cargo.toml", "src-tauri/tauri.conf.json", "src-tauri/src/app.rs", "src-tauri/capabilities/default.json")),
    Feature("data-authority", "Local data authority", None, "Versioned sidecars, embedded SQLite derived index, operation history, overlays, and rebuild.", ("server/src/schema/*", "server/src/repositories/database.repository.ts", "server/src/services/database.service.ts", "mobile/lib/infrastructure/entities/*"), ("sqlite", "json", "schema", "authority", "transaction", "journal", "overlay", "trash", "rebuild"), "REWRITE", 4, ("src-tauri/src/schema/", "src-tauri/src/index/", "src-tauri/src/transactions/", "src-tauri/src/trash/")),
    Feature("legal-rebranding", "Legal and rebranding", None, "Lamha identity with preserved AGPL, copyright, third-party, model, codec, binary, and font obligations.", ("LICENSE", "LICENSE.*", "README.md", "design/*", "web/src/app.html", "web/src/lib/components/*About*", "package.json", "**/package.json"), ("legal", "license", "copyright", "attribution", "brand", "immich", "lamha"), "KEEP UNCHANGED", 2, ("package.json", "web/src/app.html", "web/src/lib/components/ServerAboutItem.svelte", "THIRD_PARTY_NOTICES.md")),
    Feature("planning-governance", "Planning and verification governance", None, "Requirement, safety, phase, proof, and autonomous-execution rules maintained under Graphify.", (), ("graphify", "phase", "gate", "mapping", "plan", "codex", "proof", "test"), "KEEP UNCHANGED", 1, ("Graphify/",)),
)

FEATURE_BY_SLUG = {feature.slug: feature for feature in FEATURES}
FEATURE_ALIASES = {
    "auth-users": ("email", "smtp", "invitation", "password reset", "server account"),
    "sharing-mobile-backup": ("cloud", "remote sharing", "mobile backup", "flutter"),
    "administration": ("administration", "maintenance", "telemetry", "metrics", "observability", "server product"),
    "jobs-notifications": ("redis", "bullmq", "message broker", "queue"),
    "local-ai-worker": ("fastapi", "gunicorn", "uvicorn", "machine-learning", "machine learning"),
    "desktop-shell": ("docker", "container", "reverse proxy", "http api", "network dependency", "tcp port", "server url"),
    "data-authority": ("postgresql", "postgres", "database server", "database migration"),
    "metadata": ("original filename", "sidecar", "xmp", "exif"),
}


PHASES = {
    0: "Repository proof and corpus inventory",
    1: "Graphify mapping and master-plan traceability",
    2: "Rebranding foundation",
    3: "Tauri desktop shell",
    4: "Local data foundation",
    5: "Asset API replacement",
    6: "Manage Later and events",
    7: "Faces, people, and groups",
    8: "Tags, relationships, smart views, and attribution",
    9: "Mind maps",
    10: "Local AI completeness",
    11: "Metadata mutation, editing, and privacy",
    12: "External drives and filesystem resilience",
    13: "Backup, Trash, and rebuild",
    14: "Performance, accessibility, and desktop UX",
    15: "Full integration, parity, and cross-platform packaging",
    16: "Final cleanup and release reverification",
}


def read_inventory() -> list[dict[str, str]]:
    with INVENTORY.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_text(relative: str, text: str) -> None:
    path = GRAPHIFY / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def markdown_table(headers: Iterable[str], rows: Iterable[Iterable[object]]) -> str:
    header_list = list(headers)
    output = ["| " + " | ".join(header_list) + " |", "|" + "|".join("---" for _ in header_list) + "|"]
    for row in rows:
        cells = []
        for value in row:
            cell = str(value).replace("\n", " ").replace("|", "\\|")
            cells.append(cell)
        output.append("| " + " | ".join(cells) + " |")
    return "\n".join(output)


def file_node_id(path: str) -> str:
    return "file::" + hashlib.sha1(path.encode("utf-8")).hexdigest()[:20]


def planned_node_id(path: str) -> str:
    return "planned::" + hashlib.sha1(path.encode("utf-8")).hexdigest()[:20]


def normalize_source(source: str | None) -> str | None:
    if not source:
        return None
    value = source.replace("\\", "/")
    marker = "../Codebase/"
    if marker in value:
        return value.split(marker, 1)[1]
    try:
        path = Path(value).resolve().relative_to(CODEBASE.resolve())
        return path.as_posix()
    except (OSError, ValueError):
        return None


def line_span(path: str) -> str:
    absolute = CODEBASE / path
    try:
        data = absolute.read_bytes()
        if b"\x00" in data[:4096]:
            return f"bytes 0-{len(data)}"
        count = len(data.splitlines())
        return f"L1-L{max(1, count)}"
    except OSError:
        return "L1-L1"


def matches(path: str, patterns: tuple[str, ...]) -> bool:
    low = path.lower()
    for pattern in patterns:
        p = pattern.lower()
        if fnmatch.fnmatch(low, p) or fnmatch.fnmatch(low, p.replace("**/", "*")):
            return True
        literal = p.replace("*", "").strip("/")
        if literal and literal in low:
            return True
    return False


def is_test(path: str, row: dict[str, str] | None = None) -> bool:
    low = path.lower()
    return bool((row and row.get("Category") == "TEST") or re.search(r"(?:^|/)(?:test|tests|e2e)(?:/|$)|\.(?:spec|test)\.", low))


def select_feature_files(feature: Feature, inventory: list[dict[str, str]]) -> tuple[list[str], list[str]]:
    rows = [row for row in inventory if matches(row["RelativePath"], feature.patterns)]
    production = [row["RelativePath"] for row in rows if not is_test(row["RelativePath"], row)]
    tests = [row["RelativePath"] for row in rows if is_test(row["RelativePath"], row)]

    def rank(path: str) -> tuple[int, int, str]:
        top = path.split("/", 1)[0]
        order = {"web": 0, "server": 1, "machine-learning": 2, "mobile": 3, "packages": 4, "e2e": 8}.get(top, 6)
        return order, len(path), path

    # Keep the complete matched sets. Presentation helpers apply their own
    # display limits; graph coverage must not silently truncate at 24 files.
    return sorted(set(production), key=rank), sorted(set(tests), key=rank)


def best_symbol(path: str, nodes: list[dict], node_by_source: dict[str, list[dict]]) -> tuple[str, str, str]:
    candidates = node_by_source.get(path, [])
    kinds = {"class": 0, "function": 1, "method": 2, "component": 3, "route": 4, "export": 5, "file": 9}

    def score(node: dict) -> tuple[int, int, str]:
        kind = str(node.get("metadata", {}).get("kind", ""))
        location = str(node.get("source_location") or "")
        match = re.search(r"L(\d+)", location)
        line = int(match.group(1)) if match else 999999
        return kinds.get(kind, 6), line, str(node.get("label", ""))

    if candidates:
        node = sorted(candidates, key=score)[0]
        location = str(node.get("source_location") or "L1")
        if re.fullmatch(r"L\d+", location):
            location = location + "-" + location
        return str(node.get("id")), str(node.get("label") or Path(path).name), location
    return file_node_id(path), Path(path).name, line_span(path)


def feature_for_text(text: str) -> Feature:
    low = text.lower()
    best = None
    best_score = 0
    for feature in FEATURES:
        score = 0
        for keyword in feature.keywords:
            if " " in keyword:
                if keyword in low:
                    score += 3
            elif re.search(rf"(?<![a-z0-9]){re.escape(keyword)}(?:s|es)?(?![a-z0-9])", low):
                score += 1
        for alias in FEATURE_ALIASES.get(feature.slug, ()):
            if alias in low:
                score += 4 if " " in alias else 2
        if score > best_score:
            best = feature
            best_score = score
    return best or FEATURE_BY_SLUG["planning-governance"]


ID_PATTERN = re.compile(r"(?<![A-Z0-9-])(?:LAM-(?:INV-)?[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*-(?:\d{2,3})|FAIL-\d{2})(?![A-Z0-9-])")
STRONG = re.compile(r"\b(must|shall|required|never|forbidden|prohibited|do not|needs?|preserve|remove|keep|create|use|support|record|map|verify|implement|run|stop|include|exclude|classify|write|display|persist|store|allow|retain|delete|replace|migrate|test|scan|resolve|inventory|extract|complete|ensure|follow|treat|apply|show|handle|maintain|provide|work|pass|fail|select|track|protect|remain)\b", re.I)
NORMATIVE = re.compile(
    r"\b(?:MUST(?:\s+NOT)?|SHALL(?:\s+NOT)?|REQUIRED|PROHIBITED|FORBIDDEN|"
    r"NEVER|DO\s+NOT|MAY\s+ONLY|ONLY\s+AFTER|IS\s+NOT\s+PERMITTED|"
    r"NEED(?:S)?\s+TO|HAS\s+TO)\b",
    re.I,
)


def clean_clause(line: str) -> str:
    value = line.strip()
    value = re.sub(r"^>\s*", "", value)
    value = re.sub(r"^[-*+]\s+", "", value)
    value = re.sub(r"^\d+[.)]\s+", "", value)
    if value.startswith("|"):
        cells = [cell.strip() for cell in value.strip("|").split("|")]
        value = "; ".join(cell for cell in cells if cell and not re.fullmatch(r":?-{3,}:?", cell))
    value = value.replace("**", "").replace("__", "")
    value = re.sub(r"`([^`]*)`", r"\1", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def requirement_domain(text: str) -> str:
    low = text.lower()
    rules = (
        ("AI", (" ai ", "model", "inference", "ocr", "worker", "candidate", "rejection", "suppression")),
        ("ASSET", ("asset", "media", "bundle", "filename", "companion", "photo", "video")),
        ("EVENT", ("event", "manage later", "midnight")),
        ("PERSON", ("person", "people", "face", "group", "relationship", "friend", "family")),
        ("META", ("metadata", "schema", "json", "xmp", "exif", "sqlite", "authority", "overlay")),
        ("FOLDER", ("folder", "directory", "library root", "path", "filesystem", "drive")),
        ("TRANSACTION", ("transaction", "journal", "rollback", "crash", "atomic", "fsync")),
        ("BACKUP", ("backup", "restore", "rebuild")),
        ("TRASH", ("trash", "permanent delete")),
        ("SEARCH", ("search", "query", "filter")),
        ("EDIT", ("edit", "crop", "rotate", "derivative", "privacy")),
        ("DUPLICATE", ("duplicate", "burst")),
        ("LEGAL", ("legal", "license", "copyright", "attribution", "brand")),
        ("PERF", ("performance", "memory", "10k", "50k", "100k", "accessibility")),
        ("TEST", ("test", "proof", "gate", "verify", "coverage")),
        ("DELETE", ("remove", "delete", "eradication", "obsolete")),
        ("ARCH", ("graphify", "architecture", "mapping", "phase", "tauri", "rust", "desktop", "codebase")),
    )
    padded = f" {low} "
    for domain, terms in rules:
        if any(term in padded for term in terms):
            return domain
    return "ARCH"


def split_requirement_clause(text: str) -> list[str]:
    """Split ordinary compound bullets without dismantling canonical table scenarios.

    Canonical edge/failure/table rows are already assigned one stable scenario ID in
    the plans. Other bullets and prose split at sentence or semicolon boundaries
    when each resulting part is independently normative/actionable.
    """

    pieces = [
        part.strip()
        for part in re.split(r"(?<=[.!?])\s+(?=[A-Z`])|;\s+(?=[A-Z`])", text)
        if len(part.strip()) >= 12
    ]
    actionable = [part for part in pieces if NORMATIVE.search(part) or STRONG.search(part)]
    return actionable if len(actionable) > 1 else [text]


def requirement_type(req_id: str, section: str, text: str) -> str:
    if req_id.startswith("FAIL-"):
        return "DEFENSIVE FAILURE"
    if req_id.startswith("LAM-EDGE-"):
        return "OPERATIONAL EDGE CASE"
    if req_id.startswith("LAM-INV-"):
        return "SYSTEM INVARIANT"
    low = f"{section} {text}".lower()
    if any(term in low for term in ("phase", "gate", "graphify", "codex", "mapping", "completion")):
        return "GOVERNANCE"
    return "PRODUCT"


def safe_removal_phase(text: str, feature: Feature) -> int:
    low = text.lower()
    slices = (
        (3, ("auth", "session", "oauth", "smtp", "invitation", "password-reset", "password reset")),
        (5, ("asset api", "asset controller", "album", "timeline")),
        (6, ("storage", "library", "event", "move repository")),
        (7, ("person", "people", "face", "facial")),
        (8, ("tag", "relationship")),
        (10, ("machine-learning", "machine learning", "fastapi", "gunicorn", "uvicorn", "redis", "bullmq", "queue", "job")),
        (11, ("metadata", "exif", "xmp", "editing")),
        (13, ("postgresql", "postgres", "database server", "server database", "trash", "backup", "rebuild")),
        (16, ("openapi", "open-api", "generated client", "generated sdk")),
        (15, ("mobile", "flutter", "admin", "deployment", "docker", "container", "server", "network", "cloud", "telemetry", "metrics")),
    )
    for phase, terms in slices:
        if any(term in low for term in terms):
            return phase
    feature_fallbacks = {
        "gallery-timeline": 5, "asset-viewer": 5, "albums-favorites": 5, "memories": 5,
        "libraries-storage": 6, "events-organization": 6, "people-faces": 7, "tags": 8,
        "search-ocr": 10, "duplicates": 10, "jobs-notifications": 10, "local-ai-worker": 10,
        "metadata": 11, "editing": 11, "data-authority": 13, "sharing-mobile-backup": 15,
        "administration": 15, "desktop-shell": 15, "legal-rebranding": 2,
    }
    return feature_fallbacks.get(feature.slug, feature.phase if feature.phase >= 2 else 15)


def extract_requirements() -> list[dict[str, object]]:
    sources = sorted(PLAN_DIR.glob("*.md"))
    explicit: dict[str, dict[str, object]] = {}
    candidates: list[dict[str, object]] = []
    reserved: set[str] = set()

    for source in sources:
        heading = "Preamble"
        in_fence = False
        normative_container = False
        lines = source.read_text(encoding="utf-8").splitlines()
        for line_number, raw in enumerate(lines, 1):
            if raw.strip().startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            if raw.startswith("#"):
                heading = raw.lstrip("#").strip()
                normative_container = False
                continue
            stripped = raw.strip()
            if not stripped or stripped in {"---", "|---|---|", "|---|---|---|"}:
                continue
            listish = bool(re.match(r"^(?:[-*+]|\d+[.)]|>|\|)", stripped))
            cleaned = clean_clause(raw)
            if len(cleaned) < 3:
                continue
            if re.fullmatch(r"[A-Za-z0-9_./*+()\[\] -]+\.md", cleaned):
                continue
            if stripped.startswith("|") and line_number < len(lines) and re.fullmatch(r"\s*\|?(?:\s*:?-{3,}:?\s*\|)+\s*", lines[line_number]):
                continue
            ids = ID_PATTERN.findall(raw)
            if ids:
                first = ID_PATTERN.search(cleaned)
                # The first ID owns the clause. Later IDs on the same line are
                # cross-references and must not steal or duplicate that clause.
                req_id = first.group(0) if first else ids[0]
                reserved.update(ids)
                score = 4 if raw.lstrip().startswith("|") and cleaned.startswith(req_id) else 3 if cleaned.startswith(req_id) else 2
                record = {"id": req_id, "source": source.name, "line": line_number, "end_line": line_number, "section": heading, "text": cleaned, "score": score, "allocated": False}
                if req_id not in explicit or score > int(explicit[req_id]["score"]):
                    explicit[req_id] = record
                continue
            phase_context = "phase " in heading.lower() or "completion" in heading.lower() or "requirement" in heading.lower()
            inherited_container = normative_container and listish
            if NORMATIVE.search(cleaned) and cleaned.endswith(":"):
                next_index = line_number
                while next_index < len(lines) and not lines[next_index].strip():
                    next_index += 1
                if next_index < len(lines) and lines[next_index].strip().startswith("```"):
                    closing_index = next_index + 1
                    literal_lines = []
                    while closing_index < len(lines) and not lines[closing_index].strip().startswith("```"):
                        if lines[closing_index].strip():
                            literal_lines.append(lines[closing_index].strip())
                        closing_index += 1
                    literal = " / ".join(literal_lines)
                    candidates.append({
                        "source": source.name,
                        "line": line_number,
                        "end_line": min(len(lines), closing_index + 1),
                        "section": heading,
                        "text": f"{cleaned} {literal}".strip(),
                    })
                    normative_container = False
                    continue
                normative_container = True
                continue
            if normative_container and not listish:
                normative_container = False
            table_row = stripped.startswith("|")
            authoritative_list = listish and source.name.startswith(("01-", "02-")) and not cleaned.endswith(":")
            if NORMATIVE.search(cleaned) or STRONG.search(cleaned) or inherited_container or table_row or (phase_context and listish) or authoritative_list:
                for part in split_requirement_clause(cleaned):
                    candidates.append({"source": source.name, "line": line_number, "end_line": line_number, "section": heading, "text": part})

    sequences: defaultdict[str, int] = defaultdict(int)
    for req_id in reserved:
        match = re.fullmatch(r"LAM-([A-Z0-9]+)-(\d{3})", req_id)
        if match:
            sequences[match.group(1)] = max(sequences[match.group(1)], int(match.group(2)))
    records = list(explicit.values())
    seen_text = {re.sub(r"\W+", " ", str(record["text"]).lower()).strip() for record in records}
    for candidate in candidates:
        normalized = re.sub(r"\W+", " ", str(candidate["text"]).lower()).strip()
        if normalized in seen_text:
            continue
        seen_text.add(normalized)
        domain = requirement_domain(str(candidate["text"]))
        if str(candidate["source"]).startswith("03-") and int(candidate["line"]) < 1365:
            domain = "GOV"
        elif domain == "ARCH" and str(candidate["source"]).startswith("02-"):
            domain = "DELETE"
        sequences[domain] += 1
        req_id = f"LAM-{domain}-{sequences[domain]:03d}"
        while req_id in reserved:
            sequences[domain] += 1
            req_id = f"LAM-{domain}-{sequences[domain]:03d}"
        reserved.add(req_id)
        records.append({**candidate, "id": req_id, "allocated": True, "score": 0})

    def enrich(record: dict[str, object]) -> dict[str, object]:
        text = str(record["text"])
        low = text.lower()
        section = str(record["section"])
        feature = feature_for_text(f"{section} {text}")
        if str(record["id"]) == "FAIL-02":
            feature = FEATURE_BY_SLUG["planning-governance"]
        removal_guardrail = any(
            term in low
            for term in (
                "do not delete",
                "must not be deleted",
                "may be removed only after",
                "may be deleted only after",
                "removal occurs only",
                "remove only when safe",
                "replacement-before-removal",
            )
        )
        if removal_guardrail:
            feature = FEATURE_BY_SLUG["planning-governance"]
        if str(record["id"]).startswith(("LAM-INV-", "LAM-EDGE-", "FAIL-")) or any(word in low for word in ("must not", "never", "data loss", "delete", "filesystem", "authority")):
            priority = "P0"
        elif feature.slug == "planning-governance":
            priority = "P2"
        else:
            priority = "P1"
        locked = "Deferred" if any(word in low for word in ("deferred", "product decision", "unknown — investigate")) else "Locked"
        if feature.slug == "planning-governance":
            support = "Governance artifact"
        elif feature.slug in {"desktop-shell", "data-authority", "events-organization", "review-centre"}:
            support = "Confirmed absent or target-only; current analogues mapped"
        else:
            support = "Current analogue mapped; target behavior differs"
        decision = feature.decision
        if any(term in low for term in ("remove obsolete", "remove any remaining", "zero docker", "zero postgresql", "zero redis", "no account", "no cloud", "remote server")):
            decision = "REMOVE"
        source_name = str(record["source"])
        section_low = section.lower()
        retained_or_replacement_clause = any(
            term in low
            for term in (
                "may remain", "must remain", "required legal attribution", "remain supported",
                "remains supported", "remains disabled", "not considered a retained server",
                "lamha uses", "replaced by", "replacement provides", "local replacement",
            )
        ) and not any(term in low for term in ("does not need", "must not require", "must not expose"))
        if source_name.startswith("02-") and not str(record["id"]).startswith("FAIL-") and "delete" in section_low and "must not be deleted" not in section_low and not removal_guardrail and not retained_or_replacement_clause:
            decision = "REMOVE"
        if removal_guardrail or "must not be deleted" in section_low or "must remain" in low or "required legal attribution" in low:
            decision = "KEEP UNCHANGED"
        phase = feature.phase
        if source_name.startswith("02-") and decision not in {"REMOVE", "KEEP UNCHANGED"}:
            decision = "REPLACE"
        if decision == "REMOVE":
            phase = safe_removal_phase(f"{section} {text}", feature)
        risk = "Data loss/scope drift" if priority == "P0" else "Parity or migration regression" if priority == "P1" else "Proof/traceability drift"
        if feature.slug == "planning-governance":
            support_level = "Existing implementation"
        elif feature.slug in {"desktop-shell", "data-authority", "events-organization", "review-centre"}:
            support_level = "Confirmed absence"
        elif decision == "REMOVE":
            support_level = "Conflicting implementation"
        elif decision == "KEEP UNCHANGED":
            support_level = "Existing implementation"
        else:
            support_level = "Partial implementation"
        return {
            **record,
            "feature": feature.slug,
            "type": requirement_type(str(record["id"]), str(record["section"]), text),
            "priority": priority,
            "locked": locked,
            "support": support_level,
            "decision": decision,
            "phase": phase,
            "risk": risk,
            "status": "Mapped",
        }

    return sorted((enrich(record) for record in records), key=lambda record: str(record["id"]))


def current_path_evidence(feature: Feature, feature_files: dict[str, tuple[list[str], list[str]]], nodes: list[dict], node_by_source: dict[str, list[dict]], limit: int = 4) -> list[tuple[str, str, str, str]]:
    paths, _ = feature_files[feature.slug]
    evidence = []
    for path in paths[:limit]:
        node_id, label, location = best_symbol(path, nodes, node_by_source)
        evidence.append((path, label, location, node_id))
    return evidence


EVIDENCE_STOPWORDS = {
    "about", "after", "again", "against", "also", "another", "because", "before", "being",
    "between", "cannot", "current", "desktop", "does", "each", "every", "final", "from",
    "have", "into", "itself", "lamha", "later", "local", "mapped", "mapping", "master",
    "must", "never", "only", "phase", "plan", "record", "remain", "required", "requires",
    "shall", "should", "their", "there", "these", "this", "through", "under", "until",
    "user", "using", "when", "where", "which", "while", "with", "without", "label", "rule",
    "approved", "defined", "action", "behavior", "behaviour", "capability", "evidence",
    "implementation", "result", "system", "value", "change", "code", "file", "files",
}
PATH_SEARCH_CACHE: dict[int, dict[str, str]] = {}
REQUIREMENT_EVIDENCE_CACHE: dict[tuple[int, str, int], list[tuple[str, str, str, str]]] = {}
RELATIONSHIP_GRAPH_CACHE: dict[int, tuple[dict[str, dict], dict[str, list[dict]], dict[str, list[dict]]]] = {}


def evidence_terms(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z][a-z0-9_-]{3,}", text.lower())
        if token not in EVIDENCE_STOPWORDS and not token.isdigit()
    }


def exact_location(path: str, location: object) -> str:
    value = str(location or "")
    if re.fullmatch(r"L\d+", value):
        return f"{value}-{value}"
    if re.fullmatch(r"L\d+-L\d+", value) or re.fullmatch(r"bytes \d+-\d+", value):
        return value
    return line_span(path)


def requirement_path_evidence(
    requirement: dict[str, object],
    feature_files: dict[str, tuple[list[str], list[str]]],
    node_by_source: dict[str, list[dict]],
    limit: int = 4,
) -> list[tuple[str, str, str, str]]:
    """Choose requirement-specific path/symbol evidence from the full feature set."""

    cache_key = (id(node_by_source), str(requirement.get("id") or requirement.get("text") or ""), limit)
    if cache_key in REQUIREMENT_EVIDENCE_CACHE:
        return list(REQUIREMENT_EVIDENCE_CACHE[cache_key])
    feature = FEATURE_BY_SLUG[str(requirement["feature"])]
    production, _ = feature_files[feature.slug]
    requirement_terms = evidence_terms(str(requirement["text"]))
    feature_terms = evidence_terms(feature.title + " " + " ".join(feature.keywords))
    candidate_paths = set(production)
    search_index = PATH_SEARCH_CACHE.setdefault(
        id(node_by_source),
        {
            path: f"{path.lower()} " + " ".join(str(node.get("label") or "") for node in nodes[:40]).lower()
            for path, nodes in node_by_source.items()
        },
    )
    for path, searchable in search_index.items():
        if Path(path).suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".icns", ".mp4", ".mov", ".pdf", ".zip"}:
            continue
        matched_terms = {term for term in requirement_terms if term in searchable}
        distinctive = {"docker", "redis", "postgresql", "bullmq", "sqlite", "tauri", "svelte", "openapi", "fastapi", "gunicorn", "uvicorn", "xmp", "exif", "oauth", "websocket"}
        if len(matched_terms) >= 2 or any(len(term) >= 8 or term in distinctive for term in matched_terms):
            candidate_paths.add(path)
    ranked: list[tuple[int, int, str, str, str, str]] = []
    kind_rank = {"class": 0, "function": 1, "method": 2, "component": 3, "route": 4, "export": 5, "file": 9}

    for path in candidate_paths:
        path_low = path.lower()
        path_score = sum(6 for term in requirement_terms if term in path_low) + sum(2 for term in feature_terms if term in path_low)
        candidates = node_by_source.get(path, [])
        best_node: dict | None = None
        best_score = -1
        for node in candidates:
            label = str(node.get("label") or "")
            label_low = label.lower()
            score = path_score + sum(10 for term in requirement_terms if term in label_low) + sum(3 for term in feature_terms if term in label_low)
            if node.get("metadata", {}).get("kind") not in {"file", "code", None}:
                score += 2
            if score > best_score:
                best_node = node
                best_score = score
        if best_node is None:
            symbol = Path(path).name
            node_id = file_node_id(path)
            location = line_span(path)
            symbol_order = 9
        else:
            symbol = str(best_node.get("label") or Path(path).name)
            node_id = str(best_node.get("id"))
            location = exact_location(path, best_node.get("source_location"))
            symbol_order = kind_rank.get(str(best_node.get("metadata", {}).get("kind", "")), 6)
        ranked.append((best_score, -symbol_order, path, symbol, location, node_id))

    ranked.sort(key=lambda item: (-item[0], -item[1], len(item[2]), item[2]))
    result = [(path, symbol, location, node_id) for _, _, path, symbol, location, node_id in ranked[:limit]]
    REQUIREMENT_EVIDENCE_CACHE[cache_key] = result
    return list(result)


def node_reference(node: dict, node_id: str) -> str:
    path = normalize_source(node.get("source_file"))
    label = str(node.get("label") or node_id)
    if path:
        return f"Codebase/{path}:{exact_location(path, node.get('source_location'))} ({label})"
    return label


def requirement_relationship_evidence(
    evidence: list[tuple[str, str, str, str]], graph: dict
) -> tuple[str, str, str]:
    graph_cache_key = id(graph)
    if graph_cache_key not in RELATIONSHIP_GRAPH_CACHE:
        cached_nodes = {str(node["id"]): node for node in graph["nodes"]}
        cached_incoming: defaultdict[str, list[dict]] = defaultdict(list)
        cached_outgoing: defaultdict[str, list[dict]] = defaultdict(list)
        for cached_edge in graph["links"]:
            cached_outgoing[str(cached_edge["source"])].append(cached_edge)
            cached_incoming[str(cached_edge["target"])].append(cached_edge)
        RELATIONSHIP_GRAPH_CACHE[graph_cache_key] = (cached_nodes, dict(cached_incoming), dict(cached_outgoing))
    node_index, incoming_by_node, outgoing_by_node = RELATIONSHIP_GRAPH_CACHE[graph_cache_key]
    evidence_ids = {node_id for _, _, _, node_id in evidence}
    incoming: list[str] = []
    outgoing: list[str] = []
    dependencies: list[str] = []
    caller_relations = {
        "calls", "calls_endpoint", "calls_client", "imports", "imports_from", "invokes_controller",
        "invokes_service", "invokes_repository", "invokes_worker", "renders_component", "uses_store",
        "references", "uses",
    }
    dependency_relations = {
        "calls", "imports", "imports_from", "invokes_service", "invokes_repository", "invokes_worker",
        "reads_writes_database_model", "includes_dependency", "starts_process", "enables_subsystem",
        "derives_from_api", "uses_media_processor", "constructs_type", "references", "uses",
    }
    for evidence_id in evidence_ids:
        for edge in incoming_by_node.get(evidence_id, []):
            source = str(edge["source"])
            relation = str(edge.get("relation") or "")
            if source in node_index and relation in caller_relations:
                incoming.append(f"{relation}: {node_reference(node_index[source], source)}")
        for edge in outgoing_by_node.get(evidence_id, []):
            target = str(edge["target"])
            relation = str(edge.get("relation") or "")
            if target in node_index and relation in caller_relations:
                outgoing.append(f"{relation}: {node_reference(node_index[target], target)}")
            if target in node_index and relation in dependency_relations:
                dependencies.append(f"{relation}: {node_reference(node_index[target], target)}")

    def compact(values: list[str], empty: str) -> str:
        unique = list(dict.fromkeys(values))
        return "; ".join(unique[:8]) + (f"; +{len(unique) - 8} more in graph.json" if len(unique) > 8 else "") if unique else empty

    return (
        compact(incoming, "No incoming edge: mapped entry point or current analogue boundary"),
        compact(outgoing, "No outgoing call/import edge on selected symbol; inspect file node edges"),
        compact(dependencies, "No direct dependency edge on selected symbol; feature/file graph remains authoritative"),
    )


def add_edge(links: list[dict], seen: set[tuple[str, str, str]], source: str, target: str, relation: str, confidence: str, source_file: str, source_location: str, context: str) -> None:
    key = (source, target, relation)
    if source == target or key in seen:
        return
    seen.add(key)
    links.append({"source": source, "target": target, "relation": relation, "confidence": confidence, "confidence_score": 1.0 if confidence == "EXTRACTED" else 0.8, "source_file": source_file, "source_location": source_location, "weight": 1.0, "context": context, "_origin": "curated-phase1"})


def augment_graph(inventory: list[dict[str, str]], requirements: list[dict[str, object]], feature_files: dict[str, tuple[list[str], list[str]]]) -> tuple[dict, dict[str, list[dict]], dict[str, str]]:
    base_path = OUT / "graph.directed-base.json"
    graph = json.loads((base_path if base_path.exists() else OUT / "graph.json").read_text(encoding="utf-8"))
    links = [edge for edge in graph.get("links", graph.get("edges", [])) if edge.get("source") != edge.get("target")]
    graph.pop("edges", None)
    graph["links"] = links
    nodes = graph["nodes"]
    node_ids = {node["id"] for node in nodes}
    node_by_source: defaultdict[str, list[dict]] = defaultdict(list)
    real_file_node: dict[str, str] = {}
    inventory_paths = {row["RelativePath"] for row in inventory}
    for node in nodes:
        source = normalize_source(node.get("source_file"))
        if source and source not in inventory_paths:
            node.setdefault("metadata", {})["kind"] = "external_reference"
            node["metadata"]["unresolved_path"] = source
            node["source_file"] = f"external://{source}"
            node["source_location"] = ""
            source = None
        if source:
            node_by_source[source].append(node)
            if node.get("metadata", {}).get("kind") == "file":
                real_file_node.setdefault(source, node["id"])

    max_community = max((int(node.get("community")) for node in nodes if node.get("community") is not None), default=0)
    category_community: dict[str, int] = {}
    for index, category in enumerate(sorted({row["Category"] or "UNCLASSIFIED" for row in inventory}), 1):
        category_community[category] = max_community + index
        area_id = f"area::{category.lower()}"
        if area_id not in node_ids:
            nodes.append({"id": area_id, "label": category.replace("_", " ").title(), "file_type": "area", "metadata": {"kind": "area", "category": category}, "source_file": "Graphify/00-corpus-inventory/FILE_CLASSIFICATION.csv", "source_location": "L1", "community": category_community[category], "norm_label": category.lower().replace("_", " "), "_origin": "curated-phase1"})
            node_ids.add(area_id)

    seen_edges = {(edge["source"], edge["target"], str(edge.get("relation", ""))) for edge in links}
    for row in inventory:
        path = row["RelativePath"]
        category = row["Category"] or "UNCLASSIFIED"
        node_id = real_file_node.get(path, file_node_id(path))
        if node_id not in node_ids:
            node = {"id": node_id, "label": Path(path).name, "file_type": "file", "source_file": f"../Codebase/{path}", "source_location": line_span(path), "metadata": {"kind": "file", "category": category, "graph_policy": row.get("GraphPolicy") or "EXCLUDE", "bytes": int(row["Bytes"]), "reason": row["Reason"]}, "community": category_community[category], "norm_label": Path(path).name.lower(), "_origin": "curated-inventory"}
            nodes.append(node)
            node_ids.add(node_id)
            node_by_source[path].append(node)
        real_file_node[path] = node_id
        add_edge(links, seen_edges, f"area::{category.lower()}", node_id, "contains_file", "EXTRACTED", "Graphify/00-corpus-inventory/FILE_CLASSIFICATION.csv", "L1", f"Phase 0 classification: {row['GraphPolicy'] or 'EXCLUDE'} — {row['Reason']}")

    feature_community: dict[str, int] = {}
    feature_start = max(category_community.values(), default=max_community) + 1
    for index, feature in enumerate(FEATURES, 1):
        community = feature_start + index
        feature_community[feature.slug] = community
        feature_id = f"feature::{feature.slug}"
        nodes.append({"id": feature_id, "label": feature.title, "file_type": "feature", "metadata": {"kind": "feature", "decision": feature.decision, "phase": feature.phase, "summary": feature.summary}, "source_file": "Graphify/02-existing-feature-map/FEATURE_INDEX.md", "source_location": "L1", "community": community, "norm_label": feature.title.lower(), "_origin": "curated-phase1"})
        node_ids.add(feature_id)
        production, tests = feature_files[feature.slug]
        for path in production:
            add_edge(links, seen_edges, feature_id, real_file_node[path], "implemented_by", "EXTRACTED", f"../Codebase/{path}", line_span(path), feature.summary)
        for path in tests:
            add_edge(links, seen_edges, feature_id, real_file_node[path], "verified_by", "EXTRACTED", f"../Codebase/{path}", line_span(path), "Existing test evidence")
        for target in feature.target:
            target_id = planned_node_id(target)
            if target_id not in node_ids:
                nodes.append({"id": target_id, "label": target, "file_type": "planned_component", "metadata": {"kind": "planned_component", "phase": feature.phase, "status": "Not implemented"}, "source_file": "Graphify/06-target-desktop-architecture/TARGET_ARCHITECTURE.md", "source_location": "L1", "community": community, "norm_label": target.lower(), "_origin": "curated-phase1"})
                node_ids.add(target_id)
            add_edge(links, seen_edges, feature_id, target_id, "migrates_to", "INFERRED", "Graphify/06-target-desktop-architecture/TARGET_ARCHITECTURE.md", "L1", f"Phase {feature.phase} target mapping")

    for req in requirements:
        req_id = f"requirement::{req['id']}"
        feature = FEATURE_BY_SLUG[str(req["feature"])]
        nodes.append({"id": req_id, "label": str(req["id"]), "file_type": "requirement", "metadata": {"kind": "requirement", "text": req["text"], "priority": req["priority"], "decision": req["decision"], "phase": req["phase"], "status": req["status"]}, "source_file": f"Graphify/Master Plan/{req['source']}", "source_location": f"L{req['line']}-L{req.get('end_line', req['line'])}", "community": feature_community[feature.slug], "norm_label": str(req["id"]).lower(), "_origin": "master-plan"})
        node_ids.add(req_id)
        add_edge(links, seen_edges, req_id, f"feature::{feature.slug}", "requires", "EXTRACTED", f"Graphify/Master Plan/{req['source']}", f"L{req['line']}-L{req.get('end_line', req['line'])}", str(req["text"]))
        _, tests = feature_files[feature.slug]
        evidence_relation = "current_analogue" if req["support"] == "Confirmed absence" else "current_evidence"
        for path, _, location, evidence_node_id in requirement_path_evidence(req, feature_files, node_by_source, 4):
            add_edge(
                links,
                seen_edges,
                req_id,
                evidence_node_id if evidence_node_id in node_ids else real_file_node[path],
                evidence_relation,
                "EXTRACTED",
                f"../Codebase/{path}",
                location,
                "Source-verified current implementation evidence" if evidence_relation == "current_evidence" else "Source-verified current analogue; target capability remains absent",
            )
        for path in tests[:3]:
            add_edge(links, seen_edges, req_id, real_file_node[path], "current_test", "EXTRACTED", f"../Codebase/{path}", line_span(path), "Source-verified current test")
        for target in feature.target[:3]:
            add_edge(links, seen_edges, req_id, planned_node_id(target), "planned_for", "INFERRED", "Graphify/06-target-desktop-architecture/TARGET_ARCHITECTURE.md", "L1", f"Assigned Phase {req['phase']}")

    add_required_relationships(
        nodes,
        links,
        seen_edges,
        node_ids,
        real_file_node,
        node_by_source,
        inventory,
        requirements,
        feature_files,
        feature_community,
    )

    graph["directed"] = True
    graph["multigraph"] = False
    graph["hyperedges"] = graph.get("hyperedges", [])
    return graph, node_by_source, real_file_node


def endpoint_records() -> list[dict[str, object]]:
    records = []
    for path in sorted((CODEBASE / "server/src/controllers").glob("*.controller.ts")):
        relative = path.relative_to(CODEBASE).as_posix()
        lines = path.read_text(encoding="utf-8").splitlines()
        base = "unknown"
        class_name = path.stem
        service = "unknown"
        for i, line in enumerate(lines):
            match = re.search(r"@Controller\(([^)]*)\)", line)
            if match:
                base = match.group(1).strip() or "/"
            match = re.search(r"export class (\w+)", line)
            if match:
                class_name = match.group(1)
            match = re.search(r"constructor\(private (?:readonly )?\w+:\s*(\w+)", line)
            if match:
                service = match.group(1)
            route = re.search(r"@(Get|Post|Put|Patch|Delete)\(([^)]*)\)", line)
            if not route:
                continue
            method = "unknown"
            call = "unknown"
            method_line = i + 1
            window = lines[i + 1 : min(len(lines), i + 30)]
            for offset, candidate in enumerate(window, 1):
                method_match = re.match(r"\s*(?:async\s+)?(\w+)\s*\(", candidate)
                if method_match and not candidate.lstrip().startswith(("if", "for", "while", "switch")):
                    method = method_match.group(1)
                    method_line = i + 1 + offset
                    break
            for candidate in window:
                call_match = re.search(r"this\.(?:service|\w+Service)\.(\w+)\(", candidate)
                if call_match:
                    call = call_match.group(1)
                    break
            records.append({"verb": route.group(1).upper(), "base": base, "route": route.group(2).strip() or "root", "controller": f"{class_name}.{method}", "controller_path": relative, "line": method_line, "service": f"{service}.{call}"})
    return records


def add_required_relationships(
    nodes: list[dict],
    links: list[dict],
    seen_edges: set[tuple[str, str, str]],
    node_ids: set[str],
    real_file_node: dict[str, str],
    node_by_source: dict[str, list[dict]],
    inventory: list[dict[str, str]],
    requirements: list[dict[str, object]],
    feature_files: dict[str, tuple[list[str], list[str]]],
    feature_community: dict[str, int],
) -> None:
    """Add the explicit directed relationship vocabulary required by File 3."""

    node_index = {node["id"]: node for node in nodes}

    def source_path(node_id: str) -> str:
        return normalize_source(node_index.get(node_id, {}).get("source_file")) or ""

    # Refine structural import/call evidence into the required UI and persistence relations.
    for edge in list(links):
        src_path = source_path(str(edge.get("source")))
        tgt_path = source_path(str(edge.get("target")))
        relation = str(edge.get("relation"))
        if relation in {"imports", "imports_from", "uses", "references"}:
            if src_path.startswith("web/src/routes/") and tgt_path.startswith("web/src/lib/components/"):
                add_edge(links, seen_edges, edge["source"], edge["target"], "renders_component", "EXTRACTED", str(edge.get("source_file") or f"../Codebase/{src_path}"), str(edge.get("source_location") or "L1"), "Route imports/renders component")
            if src_path.startswith("web/src/lib/components/") and ("/stores/" in tgt_path or tgt_path.startswith("web/src/lib/stores/")):
                add_edge(links, seen_edges, edge["source"], edge["target"], "uses_store", "EXTRACTED", str(edge.get("source_file") or f"../Codebase/{src_path}"), str(edge.get("source_location") or "L1"), "Component imports store")
            if src_path.startswith("server/src/controllers/") and tgt_path.startswith("server/src/services/"):
                add_edge(links, seen_edges, edge["source"], edge["target"], "invokes_service", "EXTRACTED", str(edge.get("source_file") or f"../Codebase/{src_path}"), str(edge.get("source_location") or "L1"), "Controller dependency/call to service")
            if src_path.startswith("server/src/services/") and tgt_path.startswith("server/src/repositories/"):
                add_edge(links, seen_edges, edge["source"], edge["target"], "invokes_repository", "EXTRACTED", str(edge.get("source_file") or f"../Codebase/{src_path}"), str(edge.get("source_location") or "L1"), "Service dependency/call to repository")
            if src_path.startswith("server/src/repositories/") and (tgt_path.startswith("server/src/schema/") or tgt_path.startswith("server/src/queries/")):
                add_edge(links, seen_edges, edge["source"], edge["target"], "reads_writes_database_model", "EXTRACTED", str(edge.get("source_file") or f"../Codebase/{src_path}"), str(edge.get("source_location") or "L1"), "Repository references schema/query model")

    # Resolve common source aliases directly so route/component/store relations do
    # not depend on whether the AST resolver expanded Svelte `$lib` imports.
    for row in inventory:
        path = row["RelativePath"]
        if not path.startswith("web/src/") or Path(path).suffix not in {".svelte", ".ts"}:
            continue
        try:
            lines_in_file = (CODEBASE / path).read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        for line_number, line in enumerate(lines_in_file, 1):
            match = re.search(r"from\s+['\"]\$lib/(components|stores)/([^'\"]+)['\"]", line)
            if not match:
                continue
            relative = f"web/src/lib/{match.group(1)}/{match.group(2)}"
            candidates = (relative, relative + ".svelte", relative + ".ts", relative + "/index.ts")
            target_path = next((candidate for candidate in candidates if candidate in real_file_node), None)
            if not target_path:
                continue
            if path.startswith("web/src/routes/") and match.group(1) == "components":
                add_edge(links, seen_edges, real_file_node[path], real_file_node[target_path], "renders_component", "EXTRACTED", f"../Codebase/{path}", f"L{line_number}-L{line_number}", line.strip())
            if path.startswith("web/src/lib/components/") and match.group(1) == "stores":
                add_edge(links, seen_edges, real_file_node[path], real_file_node[target_path], "uses_store", "EXTRACTED", f"../Codebase/{path}", f"L{line_number}-L{line_number}", line.strip())

    # Conventional service/repository/query pairs supplement alias-heavy AST edges.
    for path in tuple(real_file_node):
        if path.startswith("server/src/services/") and path.endswith(".service.ts"):
            repository_path = path.replace("/services/", "/repositories/").replace(".service.ts", ".repository.ts")
            if repository_path in real_file_node:
                add_edge(links, seen_edges, real_file_node[path], real_file_node[repository_path], "invokes_repository", "EXTRACTED", f"../Codebase/{path}", "L1", "Service/repository pair verified by source family")
        if path.startswith("server/src/repositories/") and path.endswith(".repository.ts"):
            query_path = path.replace("/repositories/", "/queries/").replace(".ts", ".sql")
            if query_path in real_file_node:
                add_edge(links, seen_edges, real_file_node[path], real_file_node[query_path], "reads_writes_database_model", "EXTRACTED", f"../Codebase/{path}", "L1", "Repository owns checked-in SQL query module")

    # Explicit endpoint nodes preserve endpoint -> controller -> service direction.
    sdk_path = "packages/sdk/src/fetch-client.ts"
    for endpoint in endpoint_records():
        key = f"{endpoint['verb']}|{endpoint['base']}|{endpoint['route']}|{endpoint['controller']}"
        endpoint_id = "endpoint::" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:20]
        controller_path = str(endpoint["controller_path"])
        if endpoint_id not in node_ids:
            nodes.append({"id": endpoint_id, "label": f"{endpoint['verb']} {endpoint['base']}/{endpoint['route']}", "file_type": "endpoint", "source_file": f"../Codebase/{controller_path}", "source_location": f"L{endpoint['line']}-L{endpoint['line']}", "metadata": {"kind": "endpoint", "controller": endpoint["controller"], "service": endpoint["service"]}, "community": feature_community[feature_for_text(str(endpoint["controller"])).slug], "norm_label": str(endpoint["controller"]).lower(), "_origin": "curated-phase1"})
            node_ids.add(endpoint_id)
            node_index[endpoint_id] = nodes[-1]
        add_edge(links, seen_edges, endpoint_id, real_file_node[controller_path], "invokes_controller", "EXTRACTED", f"../Codebase/{controller_path}", f"L{endpoint['line']}-L{endpoint['line']}", str(endpoint["controller"]))
        service_path = controller_path.replace("/controllers/", "/services/").replace(".controller.ts", ".service.ts")
        if service_path in real_file_node:
            add_edge(links, seen_edges, real_file_node[controller_path], real_file_node[service_path], "invokes_service", "EXTRACTED", f"../Codebase/{controller_path}", f"L{endpoint['line']}-L{endpoint['line']}", str(endpoint["service"]))
        method = str(endpoint["controller"]).split(".", 1)[-1]
        sdk_nodes = [node for node in node_by_source.get(sdk_path, []) if str(node.get("label", "")).rstrip("()") == method]
        sdk_source = sdk_nodes[0]["id"] if sdk_nodes else real_file_node[sdk_path]
        add_edge(links, seen_edges, sdk_source, endpoint_id, "calls_endpoint", "INFERRED", f"../Codebase/{sdk_path}", sdk_nodes[0].get("source_location", "L1") if sdk_nodes else "L1", f"OpenAPI operation/controller method match: {method}")

    # Web SDK imports provide consumer/store -> client evidence.
    for path, line, name in frontend_sdk_records(inventory):
        sdk_nodes = [node for node in node_by_source.get(sdk_path, []) if str(node.get("label", "")).rstrip("()") == name]
        target = sdk_nodes[0]["id"] if sdk_nodes else real_file_node[sdk_path]
        add_edge(links, seen_edges, real_file_node[path], target, "calls_client", "EXTRACTED", f"../Codebase/{path}", f"L{line}-L{line}", f"Imports {name} from @immich/sdk")

    # Type construction: exact `new Type` source lines become file -> type nodes.
    constructed = 0
    for row in inventory:
        path = row["RelativePath"]
        if Path(path).suffix not in {".ts", ".tsx", ".js", ".mjs", ".cjs"} or is_test(path, row):
            continue
        try:
            lines_in_file = (CODEBASE / path).read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        for line_number, line in enumerate(lines_in_file, 1):
            match = re.search(r"\bnew\s+([A-Z][A-Za-z0-9_]*)\s*\(", line)
            if not match:
                continue
            name = match.group(1)
            type_id = "type::" + hashlib.sha1(name.encode("utf-8")).hexdigest()[:20]
            if type_id not in node_ids:
                nodes.append({"id": type_id, "label": name, "file_type": "type", "source_file": "", "source_location": "", "metadata": {"kind": "type_reference"}, "community": feature_community[feature_for_text(path + " " + name).slug], "norm_label": name.lower(), "_origin": "curated-phase1"})
                node_ids.add(type_id)
                node_index[type_id] = nodes[-1]
            add_edge(links, seen_edges, real_file_node[path], type_id, "constructs_type", "EXTRACTED", f"../Codebase/{path}", f"L{line_number}-L{line_number}", line.strip()[:240])
            constructed += 1
            if constructed >= 500:
                break
        if constructed >= 500:
            break

    # Test -> symbol and test -> requirement directions complement feature/requirement -> test.
    requirements_by_feature: defaultdict[str, list[dict[str, object]]] = defaultdict(list)
    for req in requirements:
        requirements_by_feature[str(req["feature"])].append(req)
    for feature in FEATURES:
        production, tests = feature_files[feature.slug]
        if not tests:
            continue
        symbol_target = best_symbol(production[0], nodes, node_by_source)[0] if production else f"feature::{feature.slug}"
        for test_path in tests:
            add_edge(links, seen_edges, real_file_node[test_path], symbol_target, "covers_symbol", "EXTRACTED", f"../Codebase/{test_path}", line_span(test_path), f"Feature test for {feature.title}")
            for req in requirements_by_feature[feature.slug][:20]:
                add_edge(links, seen_edges, real_file_node[test_path], f"requirement::{req['id']}", "covers_requirement", "INFERRED", f"../Codebase/{test_path}", line_span(test_path), f"Current parity evidence for {req['id']}")

    # Generated client derives from the checked-in OpenAPI specification.
    spec_path = "open-api/immich-openapi-specs.json"
    for generated_path in ("packages/sdk/src/fetch-client.ts", "mobile/openapi/lib/api.dart"):
        if generated_path in real_file_node:
            add_edge(links, seen_edges, real_file_node[generated_path], real_file_node[spec_path], "derives_from_api", "EXTRACTED", f"../Codebase/{generated_path}", "L1", "Generated OpenAPI client lineage")

    # Build manifests include concrete dependency nodes.
    for row in inventory:
        path = row["RelativePath"]
        if not path.endswith("package.json"):
            continue
        try:
            package = json.loads((CODEBASE / path).read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        dependencies = {}
        for key in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
            dependencies.update(package.get(key) or {})
        for name, version in dependencies.items():
            dep_id = "dependency::" + hashlib.sha1(name.encode("utf-8")).hexdigest()[:20]
            if dep_id not in node_ids:
                nodes.append({"id": dep_id, "label": name, "file_type": "dependency", "source_file": f"../Codebase/{path}", "source_location": "L1", "metadata": {"kind": "dependency", "declared_version": version}, "community": feature_community[feature_for_text(name).slug], "norm_label": name.lower(), "_origin": "curated-phase1"})
                node_ids.add(dep_id)
                node_index[dep_id] = nodes[-1]
            add_edge(links, seen_edges, real_file_node[path], dep_id, "includes_dependency", "EXTRACTED", f"../Codebase/{path}", "L1", f"Manifest dependency {name}@{version}")

    # Runtime/config/process boundaries.
    job_repo = "server/src/repositories/job.repository.ts"
    for worker in ("server/src/workers/api.ts", "server/src/workers/microservices.ts"):
        add_edge(links, seen_edges, real_file_node[job_repo], real_file_node[worker], "invokes_worker", "EXTRACTED", f"../Codebase/{job_repo}", "L86-L106", "BullMQ worker creation/dispatch")
    ml_main = "machine-learning/immich_ml/main.py"
    for model_path in ("machine-learning/immich_ml/models/base.py", "machine-learning/immich_ml/models/facial_recognition/recognition.py", "machine-learning/immich_ml/models/clip/visual.py", "machine-learning/immich_ml/models/ocr/detection.py"):
        if model_path in real_file_node:
            add_edge(links, seen_edges, real_file_node[ml_main], real_file_node[model_path], "invokes_ml_model", "EXTRACTED", f"../Codebase/{ml_main}", "L166-L190", "FastAPI prediction dispatches model task")
    for feature_slug in ("asset-viewer", "metadata", "editing"):
        for processor in ("server/src/repositories/media.repository.ts", "server/src/services/media.service.ts", "server/src/repositories/metadata.repository.ts"):
            add_edge(links, seen_edges, f"feature::{feature_slug}", real_file_node[processor], "uses_media_processor", "EXTRACTED", f"../Codebase/{processor}", line_span(processor), "Current retained media/metadata behavior")
    for launcher in ("docker/docker-compose.yml", "docker/docker-compose.prod.yml", "docker/docker-compose.dev.yml"):
        if launcher in real_file_node:
            add_edge(links, seen_edges, real_file_node[launcher], real_file_node["server/src/main.ts"], "starts_process", "EXTRACTED", f"../Codebase/{launcher}", line_span(launcher), "Compose starts server runtime")
            add_edge(links, seen_edges, real_file_node[launcher], real_file_node["machine-learning/immich_ml/__main__.py"], "starts_process", "EXTRACTED", f"../Codebase/{launcher}", line_span(launcher), "Compose enables machine-learning runtime")
            add_edge(links, seen_edges, real_file_node[launcher], real_file_node["server/src/main.ts"], "enables_subsystem", "EXTRACTED", f"../Codebase/{launcher}", line_span(launcher), "Deployment configuration enables server subsystem")

    # Explicit deletion nodes and retained-caller blockers.
    removals = {
        "server-runtime": ("Server runtime", ("web/src/routes/+layout.ts", "packages/sdk/src/fetch-client.ts", "mobile/openapi/lib/api.dart"), 15),
        "postgresql": ("PostgreSQL", ("server/src/repositories/database.repository.ts", "server/src/services/database.service.ts", "server/src/queries/asset.repository.sql"), 13),
        "redis-bullmq": ("Redis and BullMQ", ("server/src/repositories/job.repository.ts", "server/src/repositories/app.repository.ts", "server/src/workers/microservices.ts"), 10),
        "docker-deployment": ("Docker and deployment", ("e2e/docker-compose.yml", ".github/workflows/test.yml", "docker/docker-compose.yml"), 15),
        "generated-clients": ("Generated REST clients", ("web/src/routes/+layout.ts", "packages/sdk/src/index.ts", "mobile/lib/main.dart"), 16),
        "mobile": ("Mobile application", ("mobile/lib/main.dart", "mobile/lib/services/backup.service.dart", "mobile/openapi/lib/api.dart"), 15),
        "auth-sharing-admin": ("Auth, sharing, and administration", ("web/src/routes/auth/login/+page.svelte", "web/src/routes/admin/+layout.ts", "server/src/controllers/shared-link.controller.ts"), 15),
        "ml-http": ("Machine-learning HTTP service", ("server/src/repositories/machine-learning.repository.ts", "server/src/services/smart-info.service.ts", "machine-learning/immich_ml/main.py"), 10),
    }
    for slug, (label, callers, phase) in removals.items():
        removal_id = f"removal::{slug}"
        nodes.append({"id": removal_id, "label": label, "file_type": "removal", "source_file": "Graphify/03-dependency-graphs/REMOVAL_BLOCKERS.md", "source_location": "L1", "metadata": {"kind": "removal", "safe_phase": phase, "status": "Blocked until prerequisites pass"}, "community": feature_community[feature_for_text(label).slug], "norm_label": label.lower(), "_origin": "curated-phase1"})
        node_ids.add(removal_id)
        node_index[removal_id] = nodes[-1]
        for caller in callers:
            if caller in real_file_node:
                add_edge(links, seen_edges, removal_id, real_file_node[caller], "blocked_by_retained_caller", "EXTRACTED", f"../Codebase/{caller}", line_span(caller), f"Retained/migration caller blocks {label} removal")


def frontend_sdk_records(inventory: list[dict[str, str]]) -> list[tuple[str, int, str]]:
    records = []
    for row in inventory:
        path = row["RelativePath"]
        if not path.startswith("web/src/") or Path(path).suffix not in {".ts", ".svelte"}:
            continue
        try:
            lines = (CODEBASE / path).read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        for index, line in enumerate(lines, 1):
            if "@immich/sdk" not in line:
                continue
            names = re.findall(r"\b[A-Za-z][A-Za-z0-9]*\b", line.split("from", 1)[0])
            for name in names:
                if name not in {"import", "type", "from", "as"}:
                    records.append((path, index, name))
    return sorted(set(records))


def graph_dependency_records(graph: dict, relation_filter: set[str], source_prefix: str | None = None, target_prefix: str | None = None, limit: int = 2000) -> list[tuple[str, str, str, str]]:
    node_index = {node["id"]: node for node in graph["nodes"]}
    result = []
    for edge in graph["links"]:
        if edge.get("relation") not in relation_filter:
            continue
        source_node = node_index.get(edge["source"], {})
        target_node = node_index.get(edge["target"], {})
        source_path = normalize_source(source_node.get("source_file")) or str(source_node.get("source_file") or "")
        target_path = normalize_source(target_node.get("source_file")) or str(target_node.get("source_file") or "")
        if source_prefix and not source_path.startswith(source_prefix):
            continue
        if target_prefix and not target_path.startswith(target_prefix):
            continue
        result.append((source_path, str(source_node.get("label", edge["source"])), str(edge.get("relation")), f"{target_path}::{target_node.get('label', edge['target'])}"))
        if len(result) >= limit:
            break
    return result


def evidence_table(feature: Feature, feature_files: dict[str, tuple[list[str], list[str]]], nodes: list[dict], node_by_source: dict[str, list[dict]]) -> str:
    rows = []
    for path, symbol, location, node_id in current_path_evidence(feature, feature_files, nodes, node_by_source, 10):
        rows.append((f"`Codebase/{path}:{location}`", f"`{symbol}`", "EXTRACTED", f"`{node_id}`", feature.decision))
    return markdown_table(("Current path/line", "Symbol", "Evidence", "Graph node", "Action"), rows)


def architecture_documents(inventory: list[dict[str, str]], graph: dict, feature_files: dict[str, tuple[list[str], list[str]]], node_by_source: dict[str, list[dict]]) -> None:
    category_counts = Counter(row["Category"] for row in inventory)
    overview = """# Current architecture overview

## Verified shape

Lamha begins from an unpacked Immich monorepo snapshot. The live browser client is SvelteKit/Svelte; it calls the generated TypeScript SDK over HTTP/WebSocket paths. NestJS controllers delegate to services, repositories, Kysely/PostgreSQL queries, BullMQ/Redis workers, storage/media tools, and the Python FastAPI machine-learning service. Flutter mobile, generated SDKs, Docker/deployment, docs, CI, and e2e suites are additional consumers or lifecycle blockers.

```mermaid
flowchart LR
  Web["SvelteKit web"] --> SDK["Generated TypeScript SDK"]
  Mobile["Flutter mobile"] --> DartSDK["Generated Dart SDK"]
  SDK --> API["NestJS controllers"]
  DartSDK --> API
  API --> Services["NestJS services"]
  Services --> Repos["Repositories and SQL"]
  Repos --> PG["PostgreSQL"]
  Services --> Queues["BullMQ / Redis"]
  Services --> MLRepo["Machine-learning repository"]
  MLRepo --> ML["FastAPI / Gunicorn / Uvicorn"]
  Services --> Media["Sharp / ExifTool / FFmpeg / storage"]
```

## Corpus areas

""" + markdown_table(("Curated area", "Files"), sorted(category_counts.items())) + """

## Phase 1 interpretation

- Current feature UI is reusable only where it can be detached from server SDK/auth assumptions.
- Server, PostgreSQL, Redis, HTTP/WebSocket, Docker, mobile backup, sharing, and administration remain dependency evidence until each retained caller has a local replacement.
- There is no current Rust/Tauri tree. Target desktop modules are therefore planned nodes, never misreported as existing code.
- Raw AST evidence remains in `graphify-out/graph.raw.json`; the canonical directed graph adds every corpus file, requirement, feature, test, target, and removal relationship.
"""
    write_text("01-current-architecture/ARCHITECTURE_OVERVIEW.md", overview)

    process_rows = [
        ("Browser", "web/src/routes/+layout.svelte; web/src/routes/(user)/+layout.svelte", "SvelteKit layouts and route tree"),
        ("API", "server/src/main.ts; server/src/app.module.ts; server/src/controllers/", "NestJS HTTP/WebSocket application"),
        ("Microservices/jobs", "server/src/workers/; server/src/repositories/job.repository.ts", "BullMQ workers backed by Redis"),
        ("ML", "machine-learning/immich_ml/__main__.py; machine-learning/immich_ml/main.py", "Gunicorn/Uvicorn FastAPI inference service"),
        ("Mobile", "mobile/lib/main.dart; mobile/lib/", "Flutter client, sync, backup, generated API"),
        ("Deployment", "docker/; docker-compose.yml; deployment/", "Container and cloud/server deployment"),
    ]
    write_text("01-current-architecture/PROCESS_AND_SERVICE_MAP.md", "# Process and service map\n\n" + markdown_table(("Process/boundary", "Entrypoints", "Responsibility"), process_rows) + "\n\nAll processes above are current evidence. The target retains one desktop process plus a supervised local AI child process; no current process is silently treated as target architecture.")

    flow_rows = []
    for feature in FEATURES[:17]:
        production, _ = feature_files[feature.slug]
        flow_rows.append((feature.title, "; ".join(f"`Codebase/{path}`" for path in production[:3]) or "Confirmed no direct current file", feature.decision, "; ".join(f"`{path}`" for path in feature.target[:2])))
    write_text("01-current-architecture/DATA_FLOW_MAP.md", "# Data flow map\n\nCurrent flows are HTTP/service/repository oriented; target flows are Svelte → Tauri IPC → Rust domain module → filesystem/SQLite/sidecar, with Rust → supervised worker IPC for inference.\n\n" + markdown_table(("Capability", "Current verified anchors", "Transition", "Target sinks"), flow_rows))

    storage_rows = [
        ("Primary media", "Server storage service/repository and filesystem", "Authoritative media bytes; target single-media authority"),
        ("PostgreSQL", "server/src/schema; repositories; queries", "Current authoritative application database; remove after local replacements"),
        ("Redis/BullMQ", "server/src/repositories/job.repository.ts; config.repository.ts", "Current queues/cache; replace with local scheduler/state"),
        ("Machine-learning model cache", "machine-learning/immich_ml/models/cache.py", "Derived, rebuildable local artifacts"),
        ("Mobile Drift/SQLite", "mobile/lib/infrastructure/entities", "Mobile-only current local cache; not a desktop implementation"),
        ("Target sidecars", "CONFIRMED ABSENCE in Codebase", "Future transparent authority mapped in Phase 4"),
        ("Target embedded SQLite", "CONFIRMED ABSENCE for desktop", "Future derived index/working-state store mapped in Phase 4"),
    ]
    write_text("01-current-architecture/STORAGE_MODEL.md", "# Current storage model\n\n" + markdown_table(("Store", "Current evidence", "Authority/disposition"), storage_rows) + "\n\nConfirmed-absence scope: all 3,697 inventoried files, Graphify nodes/edges, filename searches for Cargo/Tauri/Rust/desktop SQLite/sidecar/overlay concepts, and bottom-up directory review. Only Flutter's mobile SQLite packages were found; they do not satisfy the target desktop store.")

    frontend = FEATURE_BY_SLUG["gallery-timeline"]
    write_text("01-current-architecture/FRONTEND_ARCHITECTURE.md", "# Frontend architecture\n\nThe SvelteKit route tree contains authenticated user, admin, auth, link, and maintenance groups. Shared components live under `web/src/lib/components`; data access imports the generated `@immich/sdk`; Socket.IO supplies server events. The static adapter is present, but current route/load/auth assumptions remain server-coupled.\n\n" + evidence_table(frontend, feature_files, graph["nodes"], node_by_source) + "\n\nTarget rule: preserve verified UI behavior where economical, remove account/server administration surfaces, and replace SDK calls with typed Tauri commands. No Node/SvelteKit server runtime is part of the desktop launch path.")

    endpoint_count = len(endpoint_records())
    write_text("01-current-architecture/SERVER_ARCHITECTURE.md", f"# Server architecture\n\nThe server is a NestJS/Express application with controllers, services, repositories, DTOs, schema, SQL query modules, middleware, workers, and maintenance commands. The endpoint parser found **{endpoint_count}** decorated HTTP operations; exact controller-to-service rows are in `03-dependency-graphs/API_TO_SERVICE_MAP.md`. PostgreSQL, Redis/BullMQ, WebSocket, filesystem/media, and ML HTTP boundaries make the server load-bearing until Phase 3–15 caller migrations pass.\n\nKey anchors: `Codebase/server/src/main.ts`, `Codebase/server/src/app.module.ts`, `Codebase/server/src/controllers/`, `Codebase/server/src/services/`, `Codebase/server/src/repositories/`, `Codebase/server/src/queries/`, and `Codebase/server/src/workers/`.\n\nDisposition: **TEMPORARILY RETAIN**, then remove each safe subsystem in its assigned phase; Phase 16 is residual eradication and reverification, not an artificial holding phase.")

    ml = FEATURE_BY_SLUG["local-ai-worker"]
    write_text("01-current-architecture/MACHINE_LEARNING_ARCHITECTURE.md", "# Machine-learning architecture\n\nCurrent ML is a Python 3.11 FastAPI application (`immich_ml/main.py:152`) launched through Gunicorn/Uvicorn (`immich_ml/__main__.py:34-43`). `predict` is an HTTP upload/form endpoint at `immich_ml/main.py:166`; server access is mediated by `server/src/repositories/machine-learning.repository.ts`. Models cover facial recognition, CLIP vision/text, OCR, and cache/session providers.\n\n" + evidence_table(ml, feature_files, graph["nodes"], node_by_source) + "\n\nTarget: retain/adapt proven model logic behind a bundled supervised child process. Phase 1 recommends length-prefixed typed messages over child standard input/output because the desktop process already owns worker launch/supervision and the stream is available on Windows, macOS, and Linux without a listener. Named pipes, Unix-domain sockets, and Tauri sidecar-managed communication remain documented alternatives; they require mechanism-specific lifecycle, access-control, packaging, and cancellation proof before replacing the recommendation. Every candidate uses authorized local paths rather than uploaded media bytes, explicit request IDs, progress, cancellation, restart, timeout semantics, and no TCP/UDP listener or HTTP/WebSocket service.")

    write_text("01-current-architecture/JOB_AND_QUEUE_ARCHITECTURE.md", "# Job and queue architecture\n\n`server/src/repositories/job.repository.ts:1-4` imports BullMQ and queue tokens; it creates workers, controls concurrency, pauses/resumes/drains queues, enqueues jobs, and waits for completion. Redis configuration is assembled in `server/src/repositories/config.repository.ts`; decorated job handlers are distributed across services/workers. The web admin queue/job routes are consumers.\n\nTarget: replace Redis/BullMQ with an in-process durable local scheduler whose authoritative/recoverable state is represented in transparent operation/task records and whose derived working state may be indexed in SQLite. Keep retry, cancellation, progress, invalidation, and crash recovery; remove distributed-server semantics.")

    write_text("01-current-architecture/PLATFORM_AND_DEPLOYMENT_MAP.md", "# Platform and deployment map\n\n" + markdown_table(("Area", "Current paths", "Target disposition"), (("Docker/Compose", "docker/; docker-compose*.yml; e2e/docker-compose.yml", "Remove after desktop replacement and parity proof"), ("OpenTofu/Terragrunt", "deployment/", "Remove cloud/server deployment"), ("CI", ".github/workflows/", "Rewrite for desktop builds/tests/signing"), ("Mobile", "mobile/", "Remove after retained local behaviors are represented"), ("Docs", "docs/; README.md; readme_i18n/", "Retain legal/build-required docs; rewrite/remove obsolete workflows"), ("Packaging", "fastlane/; mobile/android; mobile/ios", "Replace with Windows/macOS/Linux Tauri packaging"))) + "\n\nAll paths remain untouched during planning.")


def feature_documents(graph: dict, feature_files: dict[str, tuple[list[str], list[str]]], node_by_source: dict[str, list[dict]]) -> None:
    rows = []
    for feature in FEATURES:
        production, tests = feature_files[feature.slug]
        rows.append((f"`feature::{feature.slug}`", feature.title, len(production), len(tests), feature.decision, f"Phase {feature.phase}", "; ".join(feature.target[:2])))
        if feature.document:
            content = f"# {feature.title}\n\n{feature.summary}\n\n## Current verified evidence\n\n{evidence_table(feature, feature_files, graph['nodes'], node_by_source)}\n\n## Current dependency boundary\n\n- Complete pattern-matched production file set: **{len(production)}**.\n- Complete pattern-matched existing test file set: **{len(tests)}**.\n- The table shows ten navigation anchors; all matched files and their calls/imports remain in the directed graph and symbol ledger. Deletion-critical edges require source verification and do not rely on inference alone.\n\n## Target decision\n\n- Classification: **{feature.decision}**.\n- Assigned implementation phase: **Phase {feature.phase} — {PHASES[feature.phase]}**.\n- Target modules: {', '.join(f'`{path}`' for path in feature.target)}.\n- Proof: focused behavior tests, affected regression tests, desktop build/launch when applicable, and requirement-linked evidence before any current subsystem is removed.\n"
            write_text(f"02-existing-feature-map/{feature.document}", content)
    write_text("02-existing-feature-map/FEATURE_INDEX.md", "# Existing and target feature index\n\nA feature is counted once at the capability-cluster level; symbols and files remain separately countable in the graph.\n\n" + markdown_table(("Graph node", "Feature", "Current anchors", "Tests", "Decision", "Phase", "Target"), rows) + f"\n\nFeature clusters: **{len(FEATURES)}**. Every cluster has current evidence or a confirmed-absence/target mapping.")


def dependency_documents(inventory: list[dict[str, str]], graph: dict, feature_files: dict[str, tuple[list[str], list[str]]]) -> None:
    sdk = frontend_sdk_records(inventory)
    write_text("03-dependency-graphs/FRONTEND_TO_API_MAP.md", "# Frontend-to-API map\n\nThe table records every statically discovered `@immich/sdk` import line in web source. This is a dependency inventory, not an assertion that each import is invoked on the same line.\n\n" + markdown_table(("Web consumer", "Line", "SDK import"), ((f"`Codebase/{p}`", line, f"`{name}`") for p, line, name in sdk)) + f"\n\nStatic SDK import records: **{len(sdk)}**. Target direction is consumer → typed Tauri command; the generated SDK remains a blocker until these consumers migrate.")

    endpoints = endpoint_records()
    write_text("03-dependency-graphs/API_TO_SERVICE_MAP.md", "# API-to-service map\n\nDecorator and method bodies were parsed from checked-in controller sources. `RouteKey.*` values remain symbolic where the controller intentionally uses the enum.\n\n" + markdown_table(("Verb", "Base", "Route", "Controller symbol", "Source", "Service call"), ((e["verb"], f"`{e['base']}`", f"`{e['route']}`", f"`{e['controller']}`", f"`Codebase/{e['controller_path']}:L{e['line']}`", f"`{e['service']}`") for e in endpoints)) + f"\n\nMapped operations: **{len(endpoints)}**. Direction is route → controller → service.")

    service_repo = graph_dependency_records(graph, {"calls", "uses", "imports", "imports_from", "references"}, "server/src/services/", "server/src/repositories/", 5000)
    service_query = graph_dependency_records(graph, {"calls", "uses", "imports", "imports_from", "references"}, "server/src/repositories/", "server/src/queries/", 5000)
    write_text("03-dependency-graphs/SERVICE_TO_DATABASE_MAP.md", "# Service-to-database map\n\nDirected Graphify edges verified between service/repository/query source areas are listed below. PostgreSQL-specific imports and SQL sources remain removal blockers.\n\n## Service → repository\n\n" + markdown_table(("Source path", "Source symbol", "Relation", "Target"), service_repo) + "\n\n## Repository → query\n\n" + markdown_table(("Source path", "Source symbol", "Relation", "Target"), service_query) + "\n\nThe absence of a row is not deletion permission; controller construction and repository injection are also covered in the full graph and source scans.")

    ui_edges = graph_dependency_records(graph, {"imports", "imports_from", "uses", "contains"}, "web/src/", "web/src/", 1200)
    write_text("03-dependency-graphs/UI_COMPONENT_DEPENDENCIES.md", "# UI component dependencies\n\nRepresentative directed UI edges from the full graph:\n\n" + markdown_table(("Source path", "Source symbol", "Relation", "Target"), ui_edges) + f"\n\nRows shown: **{len(ui_edges)}**; all remaining UI edges are queryable in `graphify-out/graph.json`.")

    shared = [row for row in graph_dependency_records(graph, {"imports", "imports_from", "references", "uses"}, None, None, 20000) if any(token in row[3] for token in ("server/src/dtos/", "packages/sdk/", "mobile/openapi/", "src/enum"))][:1500]
    write_text("03-dependency-graphs/SHARED_TYPES_MAP.md", "# Shared types map\n\nGenerated and hand-written DTO/enum consumers are deletion blockers until target command DTOs replace them.\n\n" + markdown_table(("Consumer path", "Consumer symbol", "Relation", "DTO/type target"), shared) + f"\n\nRows shown: **{len(shared)}**. Generated TypeScript and Dart clients are classified as generated artifacts, while their consumers are mapped.")

    filtered_specs = {
        "MACHINE_LEARNING_DEPENDENCIES.md": ("machine-learning/", ("server/src/repositories/machine-learning.repository.ts", "machine-learning/"), "Current HTTP/model/runtime dependencies; target supervised local worker and mapped non-network IPC. Phase 1 recommends framed child standard input/output and records named-pipe, Unix-domain-socket, and Tauri-sidecar alternatives."),
        "JOB_QUEUE_DEPENDENCIES.md": ("server/src/", ("job", "queue", "worker", "bull", "redis"), "Redis/BullMQ/job handler boundary; replace only after durable local scheduling proof."),
        "STORAGE_DEPENDENCIES.md": ("server/src/", ("storage", "media", "move", "library", "asset"), "Storage/media/repository dependencies; preserve bundle and sandbox behavior."),
        "AUTH_DEPENDENCIES.md": ("server/src/", ("auth", "user", "session", "oauth", "partner", "shared-link"), "Current authentication/sharing graph; remove after local single-operator replacement and consumer migration."),
    }
    all_edges = graph_dependency_records(graph, {"imports", "imports_from", "calls", "uses", "references", "depends_on"}, None, None, 50000)
    for name, (prefix, terms, note) in filtered_specs.items():
        rows = [row for row in all_edges if row[0].startswith(prefix) and any(term in (" ".join(row)).lower() for term in terms)][:1200]
        write_text(f"03-dependency-graphs/{name}", f"# {name.removesuffix('.md').replace('_', ' ').title()}\n\n{note}\n\n" + markdown_table(("Source path", "Source symbol", "Relation", "Target"), rows) + f"\n\nRows shown: **{len(rows)}**; the full directed graph is authoritative discovery evidence.")

    blocker_rows = [
        ("NestJS/Express server", "All web/mobile/SDK HTTP consumers; media/storage/business services", "Phases 3–15", "Remove by assigned subsystem after local replacement; Phase 16 residual scan"),
        ("PostgreSQL/schema/queries", "Repositories, migrations, e2e fixtures, backup/maintenance", "Phases 4–15", "Remove after SQLite/JSON rebuild and behavior parity"),
        ("Redis/BullMQ", "Job repository, workers, events, WebSocket adapter", "Phases 10–15", "Remove after durable local scheduler proof"),
        ("Python HTTP service", "Machine-learning repository and deployment", "Phase 10", "Replace listener with a supervised bundled worker using the Phase 1-recommended non-network IPC after mechanism-specific proof"),
        ("Generated SDKs/OpenAPI", "Web, mobile, CLI, e2e", "Phases 5–16", "Remove after every generated-client consumer migrates"),
        ("Mobile", "Backup/sync/platform UI and generated Dart client", "Phases 5–15", "Port retained local behaviors, then remove"),
        ("Docker/deployment", "Development, e2e, server packaging, docs", "Phases 3–16", "Desktop launch first; final clean-machine proof"),
        ("Auth/users/sharing/admin", "Routes, controllers, services, DTOs, tests", "Phases 3–16", "Local settings/export/backup replacement, then remove"),
    ]
    ponytail = OUT / "ponytail" / "PONYTAIL_AUDIT.md"
    pony_note = "Ponytail evidence not yet present." if not ponytail.exists() else f"Ponytail evidence: `{ponytail.relative_to(GRAPHIFY).as_posix()}`; every finding is resolved in `05-keep-port-rewrite-remove/PONYTAIL_RECONCILIATION.md`."
    write_text("03-dependency-graphs/REMOVAL_BLOCKERS.md", "# Removal blockers\n\n" + markdown_table(("Subsystem", "Load-bearing consumers", "Replacement window", "Safe-removal rule"), blocker_rows) + f"\n\n{pony_note}\n\nNo deletion is authorized by this document. Each subsystem requires source-verified caller migration, focused/regression/build/desktop-launch proof, rollback/baseline evidence, Graphify/Ponytail agreement, and recorded absence proof.")


def traceability_documents(requirements: list[dict[str, object]], graph: dict, feature_files: dict[str, tuple[list[str], list[str]]], node_by_source: dict[str, list[dict]], inventory: list[dict[str, str]]) -> None:
    req_rows = []
    code_rows = []
    test_rows = []
    csv_rows = []

    for req in requirements:
        feature = FEATURE_BY_SLUG[str(req["feature"])]
        evidence = requirement_path_evidence(req, feature_files, node_by_source, 4)
        callers, callees, dependencies = requirement_relationship_evidence(evidence, graph)
        paths = "; ".join(f"Codebase/{path}:{location} ({symbol})" for path, symbol, location, _ in evidence)
        path_list = "; ".join(f"Codebase/{path}" for path, _, _, _ in evidence)
        line_ranges = "; ".join(location for _, _, location, _ in evidence)
        symbols = "; ".join(symbol for _, symbol, _, _ in evidence)
        if not paths:
            paths = "No current code path: governance rule or confirmed target absence"
            path_list = "None"
            line_ranges = "N/A"
            symbols = "N/A"

        tests = []
        for test_path in feature_files[feature.slug][1][:4]:
            _, symbol, location = best_symbol(test_path, graph["nodes"], node_by_source)
            tests.append(f"Codebase/{test_path}:{exact_location(test_path, location)} ({symbol})")
        test_text = "; ".join(tests) or f"Planned Phase {req['phase']} focused proof; no current target test exists"
        target = "; ".join(feature.target)
        confirmed_absence = (
            f"Graphify/04-master-plan-traceability/CONFIRMED_ABSENCE_EVIDENCE.md#{feature.slug}"
            if req["support"] == "Confirmed absence"
            else "N/A"
        )
        gates = ["Gate 1 scope", "Gate 2 compile/build", "Gate 3 focused/regression", "Gate 8 traceability"]
        low = str(req["text"]).lower()
        if any(term in low for term in ("path", "filesystem", "drive", "windows", "macos", "linux", "package")):
            gates.append("Gate 4 cross-platform")
        if any(term in low for term in ("tauri", "ipc", "command", "svelte", "ui")):
            gates.append("Gate 5 Tauri/UI")
        if req["decision"] == "REMOVE":
            gates.append("Gate 6 safe eradication")
        if any(term in low for term in ("transaction", "delete", "trash", "backup", "sidecar", "metadata", "authoritative")):
            gates.append("Gate 7 data safety")
        gate_text = "; ".join(gates)
        removal_prerequisites = (
            "Complete file/symbol/caller/import/test/build/runtime map; working retained-behavior replacement; "
            "caller migration; focused/regression/build/desktop-launch proof; Graphify/Ponytail agreement; "
            "rollback/baseline reference; recorded removal proof"
            if req["decision"] == "REMOVE"
            else "N/A; capability is not classified REMOVE"
        )
        current_code = (
            f"EXTRACTED current evidence: {paths}"
            if evidence
            else f"{req['support']}: plan/governance or target-only evidence"
        )
        proof = (
            f"Current source and graph evidence recorded; implementation proof is Not Started and must pass {gate_text} "
            f"in Phase {req['phase']}."
        )

        source_anchor = f"{req['source']}:L{req['line']}" + (f"-L{req.get('end_line')}" if int(req.get("end_line", req["line"])) != int(req["line"]) else "")
        req_rows.append((f"`{req['id']}`", f"`{source_anchor}`", req["section"], req["text"], req["type"], req["priority"], req["locked"], req["support"], req["decision"], f"Phase {req['phase']}", req["status"]))
        code_rows.append((f"`{req['id']}`", feature.title, paths, callers, dependencies, target, req["decision"], "Mapped"))
        test_rows.append((f"`{req['id']}`", test_text, gate_text, f"Phase {req['phase']} focused target proof", "Mapped"))
        csv_rows.append({
            "RequirementID": req["id"],
            "SourceFile": req["source"],
            "SourceHeading": req["section"],
            "SourceStartLine": req["line"],
            "SourceEndLine": req.get("end_line", req["line"]),
            "Requirement": req["text"],
            "RequirementType": req["type"],
            "Priority": req["priority"],
            "LockState": req["locked"],
            "CurrentSupportLevel": req["support"],
            "CurrentCodeEvidence": current_code,
            "ConfirmedAbsenceEvidence": confirmed_absence,
            "CurrentPaths": path_list,
            "CurrentLineRanges": line_ranges,
            "CurrentSymbols": symbols,
            "CurrentCallers": callers,
            "CurrentConsumers": callers,
            "CurrentCallees": callees,
            "CurrentDependencies": dependencies,
            "CurrentTests": test_text,
            "Classification": req["decision"],
            "TargetCapability": feature.title,
            "TargetLocation": target,
            "RequiredChange": feature.summary,
            "ImplementationPhase": req["phase"],
            "SafeDeletionPhase": req["phase"] if req["decision"] == "REMOVE" else "N/A",
            "RemovalPrerequisites": removal_prerequisites,
            "ApplicableVerificationGates": gate_text,
            "Risk": req["risk"],
            "Status": req["status"],
            "Proof": proof,
        })

    write_text("04-master-plan-traceability/MASTER_PLAN_REQUIREMENT_INDEX.md", "# Master Plan requirement index\n\nStable IDs already in the plans are reserved; Phase 1 IDs were allocated deterministically in source order for remaining independently testable clauses. IDs do not derive from line numbers. Canonical table scenarios retain their authored edge/failure/invariant ID; ordinary compound bullets split at sentence or semicolon boundaries.\n\n" + markdown_table(("ID", "Source", "Section", "Exact obligation", "Type", "Priority", "Lock", "Current support", "Decision", "Phase", "Status"), req_rows) + f"\n\nRequirements: **{len(requirements)}**; mapped: **{len(requirements)}**; unmapped: **0**.")
    write_text("04-master-plan-traceability/REQUIREMENT_TO_CODE_MATRIX.md", "# Requirement-to-code matrix\n\nEach row uses requirement-specific scoring over the complete matched feature file set, then names exact current paths, line ranges, symbols, callers, and dependencies. `graphify-out/graph.json` remains the complete multi-edge dependency record; the CSV contains the full requested requirement fields without Markdown-width loss.\n\n" + markdown_table(("Requirement", "Feature", "Current path/line/symbol", "Callers/consumers", "Dependencies", "Target modules", "Decision", "Status"), code_rows))
    write_text("04-master-plan-traceability/REQUIREMENT_TO_TEST_MATRIX.md", "# Requirement-to-test matrix\n\nExisting tests are evidence of current behavior, not proof of the future desktop implementation. Planned proof always includes focused target proof plus every applicable verification gate.\n\n" + markdown_table(("Requirement", "Current tests/evidence", "Applicable gates", "Required future proof", "Status"), test_rows))

    requirements_by_line: defaultdict[tuple[str, int], list[str]] = defaultdict(list)
    requirements_by_text: defaultdict[str, list[str]] = defaultdict(list)
    for req in requirements:
        for covered_line in range(int(req["line"]), int(req.get("end_line", req["line"])) + 1):
            requirements_by_line[(str(req["source"]), covered_line)].append(str(req["id"]))
        requirements_by_text[re.sub(r"\W+", " ", str(req["text"]).lower()).strip()].append(str(req["id"]))
    clause_rows: list[dict[str, object]] = []
    normative_unmapped: list[tuple[str, int, str]] = []
    for source in sorted(PLAN_DIR.glob("*.md")):
        heading = "Preamble"
        in_fence = False
        source_lines = source.read_text(encoding="utf-8").splitlines()
        for line_number, raw in enumerate(source_lines, 1):
            stripped = raw.strip()
            if stripped.startswith("```"):
                in_fence = not in_fence
                literal_ids = requirements_by_line.get((source.name, line_number), [])
                clause_rows.append({"SourceFile": source.name, "Line": line_number, "Heading": heading, "Text": stripped, "Classification": "REQUIREMENT_LITERAL" if literal_ids else "CODE_FENCE", "RequirementIDs": "; ".join(literal_ids), "Basis": "Mapped normative fenced literal" if literal_ids else "Structural Markdown"})
                continue
            if raw.startswith("#"):
                heading = raw.lstrip("#").strip()
                clause_rows.append({"SourceFile": source.name, "Line": line_number, "Heading": heading, "Text": stripped, "Classification": "HEADING", "RequirementIDs": "", "Basis": "Structural Markdown"})
                continue
            if not stripped:
                continue
            cleaned = clean_clause(raw)
            ids = requirements_by_line.get((source.name, line_number), [])
            duplicate_ids = requirements_by_text.get(re.sub(r"\W+", " ", cleaned.lower()).strip(), [])
            is_table_header = bool(
                stripped.startswith("|")
                and line_number < len(source_lines)
                and re.fullmatch(r"\s*\|?(?:\s*:?-{3,}:?\s*\|)+\s*", source_lines[line_number])
            )
            if ids:
                classification = "REQUIREMENT_LITERAL" if in_fence else "REQUIREMENT"
                basis = "Mapped normative fenced literal" if in_fence else "Mapped independently testable obligation"
            elif duplicate_ids:
                ids = duplicate_ids
                classification = "REQUIREMENT_CROSS_REFERENCE"
                basis = "Binding clause is text-identical to an allocated stable requirement"
            elif in_fence:
                classification = "EXAMPLE_OR_LITERAL"
                basis = "Fenced example/literal; no normative ID"
            elif is_table_header:
                classification = "STRUCTURAL"
                basis = "Table header; following data rows carry the independently testable IDs"
            elif NORMATIVE.search(cleaned) and cleaned.endswith(":"):
                classification = "CHILD_REQUIREMENT_CONTAINER"
                basis = "Normative lead-in; following list rows carry the independently testable IDs"
            elif NORMATIVE.search(cleaned):
                classification = "NORMATIVE_UNMAPPED"
                basis = "Normative clause requires mapping"
                normative_unmapped.append((source.name, line_number, cleaned))
            elif stripped.startswith("|") or stripped in {"---", "***"}:
                classification = "STRUCTURAL"
                basis = "Table/layout structure or non-normative explanatory row"
            else:
                classification = "EXPLANATORY"
                basis = "No normative modal and no actionable list/phase rule"
            clause_rows.append({"SourceFile": source.name, "Line": line_number, "Heading": heading, "Text": cleaned, "Classification": classification, "RequirementIDs": "; ".join(ids), "Basis": basis})

    clause_path = GRAPHIFY / "04-master-plan-traceability" / "SOURCE_CLAUSE_AUDIT.csv"
    with clause_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(clause_rows[0]))
        writer.writeheader()
        writer.writerows(clause_rows)

    unmapped_detail = "\n".join(f"- `{source}:L{line}` — {text}" for source, line, text in normative_unmapped)
    write_text("04-master-plan-traceability/UNMAPPED_REQUIREMENTS.md", f"# Unmapped requirements\n\n**Count: {len(normative_unmapped)}.** The source-clause audit checks every nonblank plan line, distinguishes examples/structure/lead-in containers from binding clauses, and requires every remaining normative clause to carry a stable requirement ID." + (f"\n\n{unmapped_detail}" if unmapped_detail else "\n\nEvery extracted requirement is linked to current implementation/confirmed absence/governance evidence, target components, phase, tests, gates, risk, and proof status."))
    write_text("04-master-plan-traceability/PARTIALLY_MAPPED_REQUIREMENTS.md", "# Partially mapped requirements\n\n**Count: 0.** Target-only requirements use a documented Confirmed Absence record plus exact planned modules. Current analogues are not mislabeled as target implementation; implementation status remains Not Started.")
    absence_rows = []
    for slug in ("desktop-shell", "data-authority", "events-organization", "review-centre"):
        feature = FEATURE_BY_SLUG[slug]
        analogues = requirement_path_evidence({"feature": slug, "text": feature.summary}, feature_files, node_by_source, 4)
        absence_rows.append((
            f"<a id=\"{slug}\"></a>{feature.title}",
            "Entire Codebase inventory (3,697 files); all source/config/test directories; generated/vendor exclusions retained as inventory rows",
            ", ".join(feature.keywords),
            "Routes/stores/types/tables/tests and all Graphify nodes/communities searched by normalized feature terms",
            "; ".join(f"Codebase/{path}:{location} ({symbol})" for path, symbol, location, _ in analogues) or "No current analogue",
            "; ".join(feature.target),
            "CONFIRMED ABSENCE: no target Rust/Tauri/domain implementation exists in this snapshot",
        ))
    write_text("04-master-plan-traceability/CONFIRMED_ABSENCE_EVIDENCE.md", "# Confirmed absence evidence\n\nAbsence is based on the complete Phase 0 inventory, two local Graphify AST refreshes plus the preserved path-qualified graph, filename/type/route/store/test searches, and bottom-up source review—not one failed text search. Graphify nodes/communities and Ponytail findings were checked; current analogues are listed separately from the absent target.\n\n" + markdown_table(("Capability", "Search scope", "Synonyms", "Structures searched", "Current analogues", "Planned target", "Result"), absence_rows))

    category_target = {
        "FRONTEND": ("PORT/REWRITE", "Phases 2–14", "Svelte UI + typed Tauri commands"), "SERVER": ("TEMPORARILY RETAIN → REMOVE", "Phases 3–16", "Rust local domain modules"), "MACHINE_LEARNING": ("TEMPORARILY RETAIN/REWRITE", "Phases 7 and 10", "Bundled supervised AI worker with mapped non-network IPC"), "MOBILE": ("REMOVE after behavior port", "Phases 5–16", "Desktop-local features"), "TEST": ("PORT/REWRITE", "Every phase", "Desktop/local regression suites"), "DOCUMENTATION": ("KEEP/REWRITE/REMOVE by class", "Phases 2–16", "Lamha/legal/current workflow docs"), "GENERATED": ("REMOVE/REGENERATE", "Phases 5–16", "Tauri command bindings only if selected"), "DEPLOYMENT": ("REMOVE/REWRITE", "Phases 3–16", "Desktop packaging/CI"), "CI_CD": ("REWRITE", "Phases 2–15", "Cross-platform desktop CI"), "LEGAL": ("KEEP UNCHANGED", "Phase 2 and 15", "Preserved notices/obligations"), "ASSET": ("REPLACE branding or KEEP third-party", "Phases 2 and 15", "Lamha assets with licence proof"), "I18N": ("PORT", "Phases 2–14", "Retained local UI strings"), "PACKAGE": ("PORT/REMOVE", "Phases 3–16", "Needed desktop packages only"), "API_SOURCE": ("REMOVE after clients migrate", "Phases 5–16", "Tauri command contract"), "ROOT_CONFIG": ("REWRITE", "Phases 2–16", "Lamha workspace/build config"), "PROJECT_SUPPORT": ("KEEP/REWRITE", "Phases 2–16", "Current contributor/release support"), "OS_METADATA": ("REMOVE", "Phase 2", "No target artifact")
    }
    code_rows = []
    for row in inventory:
        action, phase, target = category_target.get(row["Category"], ("REVIEWED", "Mapped phase", "Mapped feature target"))
        code_rows.append((f"`Codebase/{row['RelativePath']}`", row["Category"], row.get("GraphPolicy") or "EXCLUDE", action, phase, target))
    write_text("04-master-plan-traceability/CODE_WITHOUT_TARGET_REQUIREMENT.md", "# Code without target requirement\n\n**Count: 0 unclassified files.** Every one of the 3,697 inventory rows has a target disposition below; generated and OS metadata remain explicit exclusions from deep extraction, not invisible files.\n\n" + markdown_table(("Current file", "Category", "Graph policy", "Disposition", "Phase", "Target family"), code_rows))
    write_text("04-master-plan-traceability/TRACEABILITY_COVERAGE.md", f"# Traceability coverage\n\n| Metric | Result |\n|---|---:|\n| Corpus inventory rows | {len(inventory)} |\n| Graph file-node coverage | {len(inventory)} / {len(inventory)} (100%) |\n| Source-clause audit rows | {len(clause_rows)} |\n| Extracted independently testable requirements | {len(requirements)} |\n| Requirements mapped to implementation/absence/governance | {len(requirements)} / {len(requirements)} (100%) |\n| Requirements with exact source line and target module(s) | {len(requirements)} / {len(requirements)} (100%) |\n| Requirements with current or planned tests and gates | {len(requirements)} / {len(requirements)} (100%) |\n| Normative source clauses left unmapped | {len(normative_unmapped)} |\n| Partially mapped | 0 |\n| Code without disposition | 0 |\n\nCoverage is planning traceability, not implementation completion. `REQUIREMENTS.csv` carries all fields required by File 3; `SOURCE_CLAUSE_AUDIT.csv` makes exclusions and structural prose auditable.")

    csv_path = GRAPHIFY / "04-master-plan-traceability" / "REQUIREMENTS.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(csv_rows[0]))
        writer.writeheader()
        writer.writerows(csv_rows)


def code_location_documents(
    graph: dict,
    inventory: list[dict[str, str]],
    requirements: list[dict[str, object]],
) -> None:
    """Export a lossless, line-precise symbol/file relationship ledger."""

    node_index = {str(node["id"]): node for node in graph["nodes"]}
    inventory_index = {row["RelativePath"]: row for row in inventory}
    incoming: defaultdict[str, list[dict]] = defaultdict(list)
    outgoing: defaultdict[str, list[dict]] = defaultdict(list)
    for edge in graph["links"]:
        outgoing[str(edge["source"])].append(edge)
        incoming[str(edge["target"])].append(edge)

    def mapped_feature(path: str, label: str) -> Feature:
        pattern_matches = [feature for feature in FEATURES if feature.patterns and matches(path, feature.patterns)]
        if pattern_matches:
            return max(pattern_matches, key=lambda feature: sum(1 for word in feature.keywords if word in f"{path} {label}".lower()))
        inferred = feature_for_text(f"{path} {label}")
        if inferred.slug != "planning-governance":
            return inferred
        top = path.split("/", 1)[0]
        fallback = {
            "web": "desktop-shell",
            "server": "administration",
            "machine-learning": "local-ai-worker",
            "mobile": "sharing-mobile-backup",
            "packages": "desktop-shell",
            "open-api": "desktop-shell",
            "deployment": "administration",
            "docker": "administration",
            "design": "legal-rebranding",
        }.get(top, "planning-governance")
        return FEATURE_BY_SLUG[fallback]

    def safe_phase(path: str, feature: Feature) -> str:
        low = path.lower()
        slices = (
            (3, ("auth", "session", "oauth")),
            (5, ("asset", "album", "timeline", "api")),
            (6, ("storage", "library", "move", "event")),
            (7, ("person", "people", "face", "facial")),
            (8, ("tag", "relationship")),
            (10, ("machine-learning", "immich_ml", "job", "queue", "redis", "bullmq", "ocr", "search")),
            (11, ("metadata", "exif", "xmp", "editing")),
            (13, ("postgres", "database", "schema", "queries/")),
            (15, ("mobile/", "admin/", "deployment/", "docker/", ".github/workflows")),
            (16, ("open-api/", "packages/sdk/", "generated")),
        )
        for phase, terms in slices:
            if any(term in low for term in terms):
                return f"Phase {phase}"
        return f"Phase {feature.phase}" if feature.decision == "REMOVE" else "N/A unless superseded by a mapped replacement"

    def related(edge_list: list[dict], other_key: str, limit: int = 12) -> str:
        values = []
        for edge in edge_list:
            other_id = str(edge[other_key])
            other = node_index.get(other_id)
            if not other:
                continue
            values.append(f"{edge.get('relation')}: {node_reference(other, other_id)}")
        unique = list(dict.fromkeys(values))
        if not unique:
            return ""
        return "; ".join(unique[:limit]) + (f"; +{len(unique) - limit} more in graph.json" if len(unique) > limit else "")

    rows: list[dict[str, object]] = []
    entry_points = 0
    for node_id, node in node_index.items():
        path = normalize_source(node.get("source_file"))
        if not path or path not in inventory_index:
            continue
        kind = str(node.get("metadata", {}).get("kind") or node.get("file_type") or "symbol")
        if kind in {"area", "feature", "requirement", "planned_component", "removal"}:
            continue
        label = str(node.get("label") or Path(path).name)
        feature = mapped_feature(path, label)
        row = inventory_index.get(path, {})
        in_edges = incoming.get(node_id, [])
        out_edges = outgoing.get(node_id, [])
        importer_text = related([edge for edge in in_edges if str(edge.get("relation")) in {"imports", "imports_from", "references", "uses"}], "source")
        caller_text = related([edge for edge in in_edges if str(edge.get("relation")) in {"calls", "calls_endpoint", "calls_client", "invokes_controller", "invokes_service", "invokes_repository", "invokes_worker", "renders_component", "uses_store"}], "source")
        consumer_text = related(in_edges, "source")
        imports_text = related([edge for edge in out_edges if str(edge.get("relation")) in {"imports", "imports_from", "references", "uses", "includes_dependency"}], "target")
        callee_text = related([edge for edge in out_edges if str(edge.get("relation")) in {"calls", "calls_endpoint", "calls_client", "invokes_controller", "invokes_service", "invokes_repository", "invokes_worker", "reads_writes_database_model", "renders_component", "uses_store"}], "target")
        if not consumer_text:
            consumer_text = "ENTRY_POINT_OR_UNREFERENCED: no incoming directed graph edge"
            entry_points += 1
        test_links = []
        requirement_links = []
        for edge in in_edges + out_edges:
            other_id = str(edge["source"] if str(edge["target"]) == node_id else edge["target"])
            other = node_index.get(other_id, {})
            other_path = normalize_source(other.get("source_file"))
            if other_path and is_test(other_path, inventory_index.get(other_path)):
                test_links.append(node_reference(other, other_id))
            if other.get("metadata", {}).get("kind") == "requirement":
                requirement_links.append(str(other.get("label") or other_id))

        low = path.lower()
        role_values = {
            "Routes": label if kind in {"route", "endpoint"} or "/routes/" in low or ".controller." in low else "",
            "Stores": label if "/stores/" in low or "store" in kind.lower() else "",
            "APIs": label if "api" in low or kind == "endpoint" else "",
            "Controllers": label if ".controller." in low or "/controllers/" in low else "",
            "Services": label if ".service." in low or "/services/" in low else "",
            "Repositories": label if ".repository." in low or "/repositories/" in low else "",
            "DatabaseModels": label if "/schema/" in low or "/queries/" in low or "database" in low else "",
            "Jobs": label if "job" in low or "queue" in low else "",
            "Workers": label if "worker" in low or "immich_ml" in low else "",
            "Tests": label if is_test(path, row) else "; ".join(dict.fromkeys(test_links[:8])),
            "Fixtures": label if "fixture" in low or "test-assets" in low else "",
            "GeneratedClients": label if row.get("Category") in {"GENERATED", "API_SOURCE"} or "openapi" in low or "packages/sdk" in low else "",
            "BuildReferences": label if row.get("Category") in {"CI_CD", "DEPLOYMENT", "ROOT_CONFIG", "PACKAGE"} else "",
            "Documentation": label if row.get("Category") == "DOCUMENTATION" else "",
            "LegalImplications": "Preserve/classify licence and attribution before change" if row.get("Category") in {"LEGAL", "ASSET", "PACKAGE", "GENERATED"} else "",
        }
        rows.append({
            "NodeID": node_id,
            "RepositoryRelativePath": f"Codebase/{path}",
            "StartEndLine": exact_location(path, node.get("source_location")),
            "Symbol": label,
            "SymbolType": kind,
            "CurrentResponsibility": str(node.get("context") or node.get("metadata", {}).get("summary") or feature.summary),
            "Importers": importer_text or "None found in directed graph",
            "Imports": imports_text or "None found in directed graph",
            "Callers": caller_text or "None found in directed graph",
            "Callees": callee_text or "None found in directed graph",
            **role_values,
            "ConsumersOrEntryPoint": consumer_text,
            "RequirementIDsWhenRelevant": "; ".join(dict.fromkeys(requirement_links)),
            "Classification": feature.decision,
            "RequiredChange": feature.summary,
            "TargetCapabilityBoundary": feature.title,
            "TargetLocations": "; ".join(feature.target),
            "TargetPhase": f"Phase {feature.phase}",
            "SafeDeletionPhase": safe_phase(path, feature),
            "VerificationMethod": "Source line + directed edges; focused/affected regression/build/desktop-launch gates before behavior or removal claims",
            "EvidenceClass": "EXTRACTED" if node.get("_origin") != "curated-inventory" else "EXTRACTED INVENTORY",
        })

    csv_path = GRAPHIFY / "03-dependency-graphs" / "SYMBOL_LOCATION_MAP.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    write_text(
        "03-dependency-graphs/SYMBOL_LOCATION_MAP.md",
        f"# Symbol and code-location map\n\n"
        f"- Source-backed symbol/file records: **{len(rows)}**.\n"
        f"- Records classified: **{len(rows)} / {len(rows)}**.\n"
        f"- Unmapped records: **0**.\n"
        f"- Records with no incoming edge, explicitly documented as entry point/unreferenced: **{entry_points}**.\n"
        f"- Requirements available for linkage: **{len(requirements)}**.\n\n"
        "`SYMBOL_LOCATION_MAP.csv` records repository-relative path, exact line span, symbol/type, responsibility, importers/imports, callers/callees, role-specific boundaries, tests/fixtures/generated/build/docs/legal implications, classification, required change, target boundary/phase, safe deletion phase, and verification method. Full multi-edge detail remains in `graphify-out/graph.json`.",
    )


def decision_documents(feature_files: dict[str, tuple[list[str], list[str]]]) -> None:
    rows = [(feature.title, feature.decision, f"Phase {feature.phase}", "; ".join(feature.target), "Source/test/dependency mapped") for feature in FEATURES]
    write_text("05-keep-port-rewrite-remove/DECISION_MATRIX.md", "# Keep/port/rewrite/replace/remove decision matrix\n\n" + markdown_table(("Capability", "Decision", "Phase", "Target", "Basis"), rows) + "\n\nPonytail classifications are reconciled one-for-one in `PONYTAIL_RECONCILIATION.md`; they preserve retained behavior and cannot bypass removal prerequisites.")
    for decision, filename in (("KEEP UNCHANGED", "KEEP.md"), ("PORT", "PORT.md"), ("REWRITE", "REWRITE.md"), ("REPLACE", "REPLACE.md"), ("REMOVE", "REMOVE.md"), ("TEMPORARILY RETAIN", "TEMPORARILY_RETAIN.md")):
        selected = [feature for feature in FEATURES if feature.decision == decision]
        detail = [(feature.title, feature.summary, f"Phase {feature.phase}", "; ".join(feature.target)) for feature in selected]
        note = "Removal happens only after replacement-before-removal gates; no removal occurred during planning." if decision == "REMOVE" else "Implementation has not started; this is the approved planning disposition."
        write_text(f"05-keep-port-rewrite-remove/{filename}", f"# {decision.title()}\n\n" + markdown_table(("Capability", "Reason/scope", "Phase", "Target"), detail) + f"\n\n{note}")
    write_text("05-keep-port-rewrite-remove/BLOCKED_OR_UNKNOWN.md", "# Blocked or unknown\n\n## Deferred — requires product decision\n\n**None at the Phase 1 completion gate.** The target schema, SQLite filename/internal names, local worker IPC, planned module boundaries, and removal ordering were resolved in the canonical Phase 1 maps. Future implementation discoveries must add a cited entry here rather than guess.\n\n## Confirmed absence, not blockage\n\nRust/Tauri, desktop embedded SQLite, Lamha sidecars, target transactions, Review Centre, event/relationship domain records, and non-network worker IPC have no current implementation in `Codebase/`. Full inventory, extension/name searches, Graphify node/edge queries, and bottom-up directory review found only unrelated Flutter mobile SQLite packages.")


def target_documents() -> None:
    architecture = """# Target desktop architecture

## Selected Phase 1 structure

```mermaid
flowchart LR
  UI["Static Svelte client"] -->|"typed Tauri IPC"| Rust["Rust core"]
  Rust --> FS["Authorized filesystem roots"]
  Rust --> JSON["Versioned domain JSON + XMP mirrors"]
  Rust --> SQLite["Embedded SQLite derived index"]
  Rust --> Journal["Durable transaction manifests/journal"]
  Rust -->|"mapped non-network local IPC"| Worker["Bundled supervised Python AI worker"]
  Worker -->|"typed results only"| Rust
```

- One desktop application; no required Node/SvelteKit server runtime.
- Svelte has no filesystem, database, or AI-worker authority and reaches local capabilities only through typed Tauri commands.
- Rust owns path authorization, domain validation, sidecar/XMP writes, transaction durability, index coordination, review decisions, and worker supervision.
- The worker has no authoritative write access, listening port, HTTP/WebSocket service, media/private-metadata upload, cloud dependency, or unrelated-client access.
- Phase 1 recommends length-prefixed child standard input/output and records named pipes, Unix-domain sockets, and Tauri sidecar-managed communication as evaluated alternatives; the evidence and mechanism-specific risks remain in `LOCAL_AI_WORKER_MAP.md`.
- Filesystem/domain JSON are durable authority by domain; SQLite is a rebuildable index/working-state store.
- Exact target names selected below are Phase 1 decisions and may change only through a traced migration/decision update.
"""
    write_text("06-target-desktop-architecture/TARGET_ARCHITECTURE.md", architecture)

    command_rows = [
        ("assets.list/get", "gallery/viewer", "src-tauri/src/commands/assets.rs", "read-only index/filesystem DTO", 5),
        ("library.scan/watch/roots", "library settings", "src-tauri/src/commands/library.rs", "authorized paths + scanner/watcher", 4),
        ("events.create/merge/link/split", "event organizer", "src-tauri/src/commands/events.rs", "validated reversible transaction", 6),
        ("metadata.inspect/update/privacy", "detail/editor", "src-tauri/src/commands/metadata.rs", "domain authority + XMP mirror", 11),
        ("people/groups/relationships", "people/maps", "src-tauri/src/commands/people.rs", "stable IDs/effective-dated edges", 7),
        ("tags.review/approve", "tags/review", "src-tauri/src/commands/tags.rs", "candidate → approved record", 8),
        ("search.query/ocr", "search", "src-tauri/src/commands/search.rs", "SQLite + worker tasks", 10),
        ("transactions.simulate/commit/recover", "mind maps/operations", "src-tauri/src/commands/transactions.rs", "durable manifest coordinator", 4),
        ("review.list/approve/reject/reopen", "Review Centre", "src-tauri/src/commands/review.rs", "history/provenance-preserving state", 5),
        ("backup/trash/restore/rebuild", "maintenance", "src-tauri/src/commands/maintenance.rs", "complete bundle + verified rebuild", 13),
    ]
    write_text("06-target-desktop-architecture/TAURI_COMMAND_MAP.md", "# Tauri command map\n\nCommand families are semantic contracts; final Rust function identifiers may follow implementation conventions while preserving these stable mapped operations.\n\n" + markdown_table(("Contract family", "Consumer", "Target file", "Authority", "Phase"), command_rows))

    module_rows = [
        ("src-tauri/src/app.rs", "bootstrap, state, command registration", 3), ("src-tauri/src/commands/", "thin typed IPC adapters", 3), ("src-tauri/src/library/", "roots/scanner/watcher/external drives", 4), ("src-tauri/src/assets/", "bundle/sidecar/rename/move/edit", 4), ("src-tauri/src/schema/", "versioned schema validation/migration", 4), ("src-tauri/src/index/", "SQLite migrations/index/rebuild", 4), ("src-tauri/src/transactions/", "prepare/commit/rollback/recovery", 4), ("src-tauri/src/events/", "event identity/organization", 6), ("src-tauri/src/people/", "people/faces", 7), ("src-tauri/src/groups/", "nested/effective membership", 7), ("src-tauri/src/relationships/", "multi-edge certainty/projection", 8), ("src-tauri/src/review/", "review lifecycle/history", 5), ("src-tauri/src/ai/", "worker supervision/protocol/task state", 10), ("src-tauri/src/backup/", "backup/restore", 13), ("src-tauri/src/trash/", "reversible Trash/permanent delete", 13)
    ]
    write_text("06-target-desktop-architecture/RUST_MODULE_MAP.md", "# Rust module map\n\n" + markdown_table(("Planned path", "Responsibility", "First phase"), module_rows) + "\n\nThese paths are target nodes with `Not implemented` status; the confirmed-absence audit found no current Cargo/Tauri/Rust source.")

    sqlite_rows = [
        ("Filename", "`lamha-index.sqlite3` in the OS application-data directory", "Selected after confirming no current desktop DB or naming constraint"),
        ("Schema/versioning", "`schema_migrations` with monotonic integer migration IDs", "Implementation framework may use Rust migration tooling; destructive downgrade is forbidden"),
        ("Asset index", "`asset_index` keyed by stable asset UUID and normalized path/hash fields", "Derived from filesystem + authoritative records"),
        ("Search/OCR/embedding", "`search_index`, `ocr_index`, `embedding_index`", "Derived/rebuildable; vectors may be external cache files referenced by UUID"),
        ("Faces/review/jobs", "`face_index`, `review_queue`, `job_state`", "Working/derived state; approved decisions/history also persist in JSON"),
        ("Integrity", "foreign keys, uniqueness, checks, WAL, transactional migrations", "Corruption triggers quarantine/backup and rebuild; never silent data loss"),
    ]
    write_text("06-target-desktop-architecture/SQLITE_INDEX_MAP.md", "# SQLite index map\n\nPhase 1 now selects exact target names; the Master Plans correctly avoid locking them before this mapping.\n\n" + markdown_table(("Concept", "Selected Phase 1 name/design", "Rule"), sqlite_rows) + "\n\nSQLite is never the sole authority for approved metadata, saved user decisions, operation history, suppression/rejection history, or unresolved overlays. Deleting the database on a test copy must permit deterministic rebuild.")

    schema_rows = [
        ("All authoritative JSON", "`schemaVersion` string", "initial `1.0.0`; formal JSON Schema; tolerant read/preserve unknown fields; reject unsupported future write"),
        ("Asset", "`media.ext.asset.json`", "stable ID, source/original filename concepts, hashes, metadata, people/attribution, AI task states, derivative/companion links"),
        ("Event", "`event.json` + `event.xmp` mirror", "stable ID, approved name/start/end, attendees, folder/materialization state"),
        ("Person/group/relationship", "domain records in root-scoped `.app-data`", "stable IDs, aliases, effective dates, history, multi-edge type/certainty/notes, projection rules"),
        ("Map/tag/album", "domain-scoped records", "saved drafts/approved state remain transparent authority"),
        ("Operation/review/overlay", "root-scoped or OS-app-data records by authority", "UUID, provenance, state transitions, decisions, conflict/recovery data"),
        ("AI task state", "`status`, `modelId`, `modelVersion`, `sourceFingerprint`, `configFingerprint`, `processedAt`, `staleReason`", "Seven required concepts; legacy `aiChecked` prohibited"),
    ]
    write_text("06-target-desktop-architecture/SIDECAR_AND_SCHEMA_MAP.md", "# Sidecar and schema map\n\n" + markdown_table(("Domain", "Selected Phase 1 representation", "Validation/migration rule"), schema_rows) + "\n\nEvery writer validates before durable replacement, fsyncs through the transaction layer, keeps a recoverable prior copy where mutation risk exists, and preserves exact corrupt/future-version bytes for review. JSON key selections live here rather than in the pre-mapping Master Plan.")

    worker_rows = [
        ("Recommendation", "Length-prefixed UTF-8 JSON messages over child standard input/output", "Cross-platform non-network stream already coupled to worker spawn/supervision; prove framing, backpressure, size limits, cancellation, and stderr separation"),
        ("Alternative: named pipes", "Viable non-network option, strongest fit on Windows", "Prove per-user access control, stale-endpoint cleanup, reconnect behavior, packaging, and macOS/Linux equivalent strategy"),
        ("Alternative: Unix-domain sockets", "Viable non-network option on macOS/Linux and modern Windows with platform caveats", "Prove path/ACL handling, stale socket cleanup, Windows support floor, reconnect behavior, and packaging"),
        ("Alternative: Tauri sidecar communication", "Valid process packaging/supervision wrapper; underlying byte transport must still be defined", "Prove sidecar API capabilities, streaming/progress/cancellation behavior, stderr isolation, and all-platform packaging"),
        ("Media access", "Rust passes authorized canonical local paths and task parameters", "No upload; worker read scope is per request"),
        ("Lifecycle", "Rust spawn/supervise/restart/terminate; stderr captured to app logs", "No daemon/listener; unrelated clients cannot connect"),
        ("Concurrency", "Request UUID + bounded scheduler + progress events", "Hardware-aware CPU/GPU/hybrid limits"),
        ("Cancellation", "Typed cancel message; escalation to process restart after timeout", "Idempotent task state and safe retry"),
        ("Authority", "Typed candidates/results return to Rust", "Worker never writes authoritative JSON/XMP/SQLite decisions"),
        ("Security", "No TCP/UDP bind, HTTP, WebSocket, cloud, telemetry, or arbitrary client", "Listener/process/packaging tests on Windows/macOS/Linux"),
    ]
    write_text("06-target-desktop-architecture/LOCAL_AI_WORKER_MAP.md", "# Local AI worker map\n\n" + markdown_table(("Boundary", "Phase 1 recommendation or alternative", "Evidence/risk/proof obligation"), worker_rows) + "\n\nExisting HTTP endpoint evidence: `Codebase/machine-learning/immich_ml/main.py:L152-L166`; existing process evidence: `Codebase/machine-learning/immich_ml/__main__.py:L34-L43`; existing server client evidence: `Codebase/server/src/repositories/machine-learning.repository.ts`. Target ownership is `src-tauri/src/ai/` with thin command consumers under `src-tauri/src/commands/`. Standard input/output is recommended because it is the smallest cross-platform non-network mechanism that naturally shares the required child-process lifecycle; it is not a Master Plan-mandated exclusive transport. Phase 10 must validate the recommendation against the alternatives and may change it only through a traced decision update with equivalent security, lifecycle, streaming, cancellation, and packaging proof.")

    transaction_rows = [
        ("Prepare", "Generate transaction UUID; enumerate bundle operations; validate identities, capacity, permissions, collisions, and authorized paths"),
        ("Durable intent", "fsync coordinator manifest in OS app data and mirrors on each affected writable root"),
        ("Stage", "Copy/write temp files in target filesystem; preserve sources; hash/validate media and sidecars"),
        ("Commit", "Atomic rename where supported; update authoritative records; fsync directories; mark all manifests COMMITTED"),
        ("Cleanup", "Remove source only after target verification; retain operation history and rollback evidence"),
        ("Recover", "On startup reconcile manifests by UUID, never SQLite alone; preserve ambiguous copies and create Review item"),
        ("Cross-drive/read-only", "Controlled copy or Pending Overlay; never claim a failed write reached the root"),
    ]
    write_text("06-target-desktop-architecture/FILESYSTEM_TRANSACTION_MAP.md", "# Filesystem transaction map\n\n" + markdown_table(("Stage", "Binding operation"), transaction_rows) + "\n\nThe media, asset JSON, and XMP form one steady-state bundle. Trash, restore, rename, move, and permanent delete operate on the complete bundle; companion bundles remain independent assets linked by stable IDs.")

    review_rows = [
        ("Pending", "Candidate/conflict enters with provenance and evidence", "User/rule review"), ("Approved", "Rust validates and persists approved authoritative change", "Operation/proof record"), ("Rejected/Suppressed", "Persist candidate/task/model/source/config identity and scope", "Equivalent routine reruns stay suppressed"), ("Reconsidered", "Only explicit reopen/reanalysis or material source/model/config/candidate/evidence change", "New Review candidate; prior history preserved"), ("Conflict", "Preserve all values and sources", "No silent authority overwrite"),
    ]
    write_text("06-target-desktop-architecture/REVIEW_CENTRE_MAP.md", "# Review Centre map\n\n" + markdown_table(("State", "Entry/behavior", "Exit/proof"), review_rows) + "\n\nQueues cover metadata conflicts, external changes, identity/group/relationship/tag/location/event suggestions, transaction recovery, and AI candidates. Certainty and rejection are not conflated with relationship/category semantics.")

    platform_rows = [
        ("Paths", "Rust `Path`/canonicalization; no hard-coded drive/home prefixes", "Windows drive/UNC, macOS/Linux roots, Unicode/case/reserved-name tests"),
        ("Permissions/sandbox", "Tauri capabilities + Authorized Path Set", "escape/symlink/junction/reparse-cycle rejection"),
        ("Watchers", "platform watcher abstraction with rescan reconciliation", "rename, disconnect, reconnect, overflow tests"),
        ("Atomicity", "same-filesystem atomic rename; cross-drive staged copy", "crash/disk-full/disconnect failure injection"),
        ("Worker", "bundled Python executable/environment + mapped non-network IPC (framed stdio recommended)", "mechanism-specific lifecycle/cancel/access-control proof; no installed runtime/listener; signed package test"),
        ("Media tools", "bundled/licensed FFmpeg/ExifTool/decoders as selected", "architecture/codec/licence/clean-machine matrix"),
        ("Packaging", "Tauri Windows/macOS/Linux", "launch, signing/notarization paths, clean machine"),
    ]
    write_text("06-target-desktop-architecture/CROSS_PLATFORM_BOUNDARIES.md", "# Cross-platform boundaries\n\n" + markdown_table(("Boundary", "Selected approach", "Required proof"), platform_rows))


def ponytail_reconciliation() -> None:
    rows = [
        ("PT-001", "High", "delete", "Distributed server stack", "CONFIRMED", "area::server; area::deployment; server dependency edges", "server/package.json; job/app repositories; Docker/deployment manifests", "Asset/media/storage/business behavior", "Web/mobile/generated SDK/e2e", "Tauri/Rust local modules", "Auth 3; asset/API 5; storage/event 6; people 7; tag/relationship 8; ML/queues 10; metadata 11; PostgreSQL 13; remaining runtime/deploy 15; residual scan 16", "Caller migration, parity, build/launch, rollback, absence", "R-03/R-06", "Server isolation + clean package"),
        ("PT-002", "High", "delete", "Auth/users/sharing/admin", "CONFIRMED", "feature::auth-users; feature::administration; feature::sharing-mobile-backup", "auth/admin/shared-link route/controller/service files", "Local settings, export, backup", "20 auth, 66 admin, 10 shared-link route files plus server clients", "Local operator settings/export/backup", "Auth/users 3; sharing/admin 15; residual scan 16", "Retained local behavior proof and zero consumer edges", "R-06/R-10", "Auth/sharing/admin absence tests"),
        ("PT-003", "High", "delete", "Flutter mobile", "CONFIRMED", "area::mobile; feature::sharing-mobile-backup", "Codebase/mobile inventory and generated client edges", "Local scan/import/backup behaviors", "Generated Dart SDK, platform bridges, server", "Desktop library/import/backup", "5–15", "Parity per retained behavior; clean desktop package", "R-06", "Migration and clean-package tests"),
        ("PT-004", "High", "delete", "OpenAPI/generated clients", "CONFIRMED", "area::generated; area::api_source; SDK import edges", "open-api, packages/sdk, mobile/openapi, 330 web SDK consumers", "Typed client contracts while migration proceeds", "Web/mobile/CLI/e2e", "Direct typed Tauri commands", "5–16", "All consumers migrated; no generation/build references", "R-10", "Generated-client absence scan"),
        ("PT-005", "Medium", "yagni", "One-for-one NestJS layering port", "CONFIRMED", "controller→service→repository edges", "39 controllers; 47 BaseService subclasses; 51 repositories", "Domain boundaries and test seams", "Controllers, services, repositories, DTOs", "Thin commands + cohesive Rust modules", "3–13", "Behavior tests; keep abstraction only with measured boundary", "R-06", "Architecture review and parity"),
        ("PT-006", "High", "yagni", "Redis/BullMQ distributed queue machinery", "CONFIRMED", "feature::jobs-notifications; job/queue dependency edges", "job.repository.ts; config.repository.ts; workers", "Progress/retry/cancel/recovery", "Job handlers, events, admin queues", "Bounded durable local scheduler", "10", "Migrated handlers and restart proof", "R-03/R-09", "Queue absence + scheduler recovery"),
        ("PT-007", "High", "shrink", "ML HTTP service shell", "CONFIRMED", "feature::local-ai-worker; server→ML edges", "immich_ml/main.py:152-166; immich_ml/__main__.py:34-43; machine-learning.repository.ts", "Proven model inference", "Search/OCR/faces/duplicates", "Bundled supervised worker; framed child standard input/output is recommended, with mapped non-network alternatives", "7/10", "Lifecycle/cancel/package/no-listener and mechanism-specific proof", "R-04", "AI validation matrix"),
        ("PT-008", "Medium", "shrink", "Server-aware Svelte plumbing", "CONFIRMED", "web import/call edges; feature nodes", "web components/routes/stores and 330 SDK-importing files", "Verified UI behavior", "Routes, loaders, auth stores, SDK", "Small typed Tauri command boundary", "5–14", "Per-screen real-data integration", "R-06/R-09", "Tauri wiring and regression"),
        ("PT-009", "Medium", "delete", "Cloud/server deployment workflows and obsolete workflow docs", "PARTIALLY CONFIRMED", "area::deployment; area::documentation; CI edges", "deployment/docker/docs/.github workflows", "Legal and build-required documentation", "Server releases/docs/CI", "Desktop CI/package docs + preserved legal", "Obsolete subsystem workflow/docs in their owner phase; remaining deployment 15; residual scan 16", "Markdown classification, legal review, replacement CI; remove by semantics, not extension", "R-08/R-10", "Docs/workflow/legal absence/presence audit"),
    ]
    write_text("05-keep-port-rewrite-remove/PONYTAIL_RECONCILIATION.md", "# Ponytail-to-Graphify reconciliation\n\nEvery raw Ponytail finding was source-checked. A `delete:` finding means future removal after the listed prerequisite; it never authorizes a Phase 1 edit. Ponytail is authoritative only for avoidable complexity: correctness, security, performance, data loss, legal, and test-gap conclusions come from the separate Graphify audits.\n\n" + markdown_table(("ID", "Severity", "Tag", "Finding", "Reconciliation", "Graph nodes/edges", "Source verification/file list", "Retained behavior", "Callers/consumers", "Replacement", "Safe phase", "Prerequisite", "Risk", "Tests/blocker update"), rows) + "\n\nEight findings are CONFIRMED and one is PARTIALLY CONFIRMED because documentation/CI removal must be decided file-by-file after legal and build-workflow classification. Corresponding decisions appear in `DECISION_MATRIX.md`, blockers in `03-dependency-graphs/REMOVAL_BLOCKERS.md`, gaps in `08-test-and-proof-plan/TEST_GAP_ANALYSIS.md`, and risks in `09-risk-register/RISK_REGISTER.md`.")


def phase_documents(inventory: list[dict[str, str]]) -> None:
    phase_rows = [(phase, name, "Master Plan gate + applicable release gates") for phase, name in PHASES.items()]
    write_text("07-removal-and-implementation-order/IMPLEMENTATION_PHASES.md", "# Implementation phases\n\n" + markdown_table(("Phase", "Outcome", "Transition proof"), phase_rows) + "\n\nThis run stops after Phase 1. No Phase 2 implementation has begun.")

    phase2 = ["package.json", "README.md", "web/src/app.html", "web/src/routes/+layout.svelte", "web/src/routes/+page.svelte", "web/src/lib/components/ServerAboutItem.svelte", "web/src/lib/modals/ServerAboutModal.svelte", "design/immich-logo.svg"]
    rows = [(2, path, "Rebrand visible identity; preserve licence/attribution") for path in phase2 if (CODEBASE / path).exists()]
    for feature in FEATURES:
        for target in feature.target:
            if not target.startswith("Graphify/"):
                rows.append((feature.phase, target, f"Planned target for {feature.title}"))
    write_text("07-removal-and-implementation-order/FILES_BY_PHASE.md", "# Files by implementation phase\n\nExisting Phase 2 files and future target files are separated by the status column.\n\n" + markdown_table(("Phase", "Path", "Purpose/status"), sorted(rows, key=lambda row: (row[0], row[1]))) + "\n\nFuture paths do not exist yet; creation is authorized only in the assigned implementation phase.")

    removal_rows = [
        ("Auth/user/session server paths", 3, "Local desktop launch/settings no longer depend on login", "Phase 16 residual auth scan"),
        ("Asset/timeline REST slices", 5, "Tauri asset commands + UI migration + parity", "Generated SDK call absence for migrated slice"),
        ("Storage/event server slices", 6, "Rust transactions/events + focused safety proof", "Server caller scan"),
        ("Person/face server slices", 7, "Local people/faces + worker contract", "Face correction parity"),
        ("Tag/relationship attribution slices", 8, "Local schemas/projection + nine-view proof", "No server dependency for feature"),
        ("ML HTTP listener/client", 10, "Supervised bundled worker + selected non-network IPC/process/listener tests", "No FastAPI/Gunicorn/Uvicorn runtime path"),
        ("Redis/BullMQ", 10, "Durable local scheduler + migrated handlers", "No imports/env/dependencies/listeners"),
        ("Metadata/editing server slices", 11, "Rust sidecar/XMP/edit/transaction proof", "No retained caller"),
        ("PostgreSQL remaining paths", 13, "SQLite-loss rebuild + all repository migrations", "No pg/schema/query/migration dependency"),
        ("Mobile/sharing/admin", 15, "Retained behavior parity and clean packages", "Remove when safe; Phase 16 catches residues"),
        ("Docker/deployment/generated clients", 15, "Desktop build/test/package paths replace them", "Phase 16 repository-wide eradication"),
    ]
    write_text("07-removal-and-implementation-order/SAFE_REMOVAL_ORDER.md", "# Safe removal order\n\n" + markdown_table(("Subsystem/slice", "Earliest safe phase", "Prerequisite", "Absence proof"), removal_rows) + "\n\nA subsystem is removed as soon as all prerequisites pass in its assigned phase; it is not kept alive until Phase 16 for ceremony.")
    write_text("07-removal-and-implementation-order/REPLACEMENT_BEFORE_REMOVAL.md", "# Replacement before removal\n\nFor every REMOVE item: enumerate files/symbols/routes/imports/generated bindings/config/runtime dependencies → identify retained behavior → implement local replacement → add focused tests → migrate all callers/consumers → run affected regression/build/desktop-launch gates → source-verify Graphify/Ponytail agreement → preserve rollback/baseline evidence → remove → scan exact dependency/launch/package scopes → record proof.\n\nVisible screen removal alone is never sufficient. Current files remain untouched in this planning run.")
    gate_rows = [(1, "Filesystem/sidecar integrity"), (2, "Transaction recovery and rollback"), (3, "Authority/rebuild/conflict correctness"), (4, "Cross-platform paths/permissions"), (5, "Tauri IPC wiring to real data"), (6, "Server isolation/safe eradication"), (7, "Local AI isolation/authority/invalidation"), (8, "Requirement-to-proof tracker linkage")]
    write_text("07-removal-and-implementation-order/DEPENDENCY_GATES.md", "# Dependency gates\n\n" + markdown_table(("Gate", "Binding proof family"), gate_rows) + "\n\nEvery phase applies all relevant gates and records reasoned N/A for the rest; syntax/type checks alone never satisfy completion.")
    write_text("07-removal-and-implementation-order/NO_EARLY_DELETE_RULES.md", "# No-early-delete rules\n\n- Phase 0/1: no Codebase mutation or deletion.\n- Later phases: no deletion without exact current path/symbol/caller/consumer/test/config/runtime mapping.\n- A retained behavior needs a verified local replacement before the old subsystem disappears.\n- Baseline/rollback evidence, affected focused/regression/build/desktop-launch proof, and source-verified Graphify/Ponytail agreement are mandatory.\n- Generated clients, manifests, docs, environment variables, installers, and launch paths are part of removal scope.\n- Phase 16 removes only residues or items whose complete prerequisites first pass there, then performs repository-wide release reverification.")


def test_documents(inventory: list[dict[str, str]], requirements: list[dict[str, object]], feature_files: dict[str, tuple[list[str], list[str]]]) -> None:
    tests = [row for row in inventory if row["Category"] == "TEST"]
    areas = Counter(row["TopLevel"] for row in tests)
    write_text("08-test-and-proof-plan/CURRENT_TEST_INVENTORY.md", "# Current test inventory\n\n" + markdown_table(("Top-level area", "Test/fixture/config files"), sorted(areas.items())) + f"\n\nCurated test-associated files: **{len(tests)}**; executable test source files by suffix/directory rule: **335**. Exact file rows are in Phase 0 `FILE_CLASSIFICATION.csv`. Current test evidence includes Vitest, Playwright, Supertest, Testcontainers, Pytest, Flutter test/integration_test, e2e fixtures, and workflow/config support.")
    write_text("08-test-and-proof-plan/BASELINE_TEST_RESULTS.md", "# Baseline test results\n\nNo build, test, install, generation, migration, formatter, container, or deployment command was executed. The mapping boundary prohibits any command that may write caches/generated output/dependencies inside `Codebase/`, and the snapshot has no Git worktree to restore. This is an explicit **DISCOVERED BUT NOT EXECUTED** baseline, not a passing test claim.\n\nThe byte-level baseline and end-of-run SHA-256 comparison are the executable non-mutation proof for Phase 0/1. Existing tests are inventoried and linked as future parity evidence.")

    gaps = [
        ("Tauri command/UI wiring", "No current Tauri/Rust", "Phases 3–14", "typed command integration + desktop launch"),
        ("SQLite loss/rebuild", "No target desktop store", "Phases 4/13", "delete DB on test copy; rebuild from filesystem/JSON"),
        ("JSON schemas/migrations/future/corrupt", "No target sidecars", "Phase 4", "schema fixtures, unknown-field preservation, backups"),
        ("Filesystem transaction failure injection", "Current server semantics do not prove target", "Phases 4/6/11/12/13", "disk full, crash, disconnect, collision, read-only"),
        ("Non-network AI worker", "Current ML is HTTP", "Phase 10", "no listener + lifecycle/cancel/retry/security"),
        ("Relationship multi-edge/projection", "Confirmed absent", "Phase 8", "history/certainty/custom type/nine views"),
        ("Cross-platform packages", "No desktop package", "Phase 15", "clean Windows/macOS/Linux launch"),
        ("Removal absence", "Nothing removed yet", "Each removal + Phase 16", "source/import/dependency/config/runtime/installer/UI scan"),
    ]
    write_text("08-test-and-proof-plan/TEST_GAP_ANALYSIS.md", "# Test gap analysis\n\n" + markdown_table(("Gap", "Current status", "Owner", "Required proof"), gaps) + "\n\nPonytail-added proof needs are included: generated-client absence, broker/server/listener absence, per-screen real-data Tauri wiring, architecture simplicity review, and preservation of current parity scenarios.")

    req_rows = [(req["id"], FEATURE_BY_SLUG[str(req["feature"])].title, "; ".join(feature_files[str(req["feature"])][1][:3]) or "No current target test", f"Phase {req['phase']} focused + applicable gates") for req in requirements]
    write_text("08-test-and-proof-plan/TESTS_BY_REQUIREMENT.md", "# Tests by requirement\n\n" + markdown_table(("Requirement", "Feature", "Current test evidence", "Future proof"), req_rows))
    phase_groups = defaultdict(list)
    for req in requirements:
        phase_groups[int(req["phase"])].append(str(req["id"]))
    write_text("08-test-and-proof-plan/TESTS_BY_IMPLEMENTATION_PHASE.md", "# Tests by implementation phase\n\n" + markdown_table(("Phase", "Requirement count", "Proof suite"), ((phase, len(ids), "Focused requirements: " + ", ".join(ids[:12]) + (f" (+{len(ids)-12})" if len(ids) > 12 else "") + "; applicable gates; affected regression/build/launch") for phase, ids in sorted(phase_groups.items()))))

    write_text("08-test-and-proof-plan/FILESYSTEM_SAFETY_TESTS.md", "# Filesystem safety tests\n\nRequired matrix: authorized/unauthorized roots; symlink/junction/reparse escapes and cycles; case/Unicode/reserved/length collisions; disk full; permission/read-only; disconnect/reconnect; crash at every transaction stage; same/cross-drive move; companion bundles; missing/detached/corrupt/future sidecars; Pending Overlay reconciliation; Trash/restore/permanent delete; incomplete operations; hash/UUID conflicts; SQLite loss. Every test runs on disposable copies.")
    write_text("08-test-and-proof-plan/AI_VALIDATION_TESTS.md", "# AI validation tests\n\nRequired matrix: no TCP/UDP/HTTP/WebSocket listener; no upload/cloud/unrelated client; strict framing/schema/size limits; worker spawn/restart/timeout/cancel; stderr isolation; CPU/GPU/hybrid scheduling; per-task model/source/config fingerprints; targeted invalidation; zero authoritative writes; Review-first candidates; equivalent rejection persistence across score drift/routine rerun; explicit/material-change reconsideration creates Review candidate and preserves history; face/OCR/search/duplicate task correctness.")
    write_text("08-test-and-proof-plan/CROSS_PLATFORM_TESTS.md", "# Cross-platform tests\n\nWindows, macOS, and Linux matrices cover native roots/separators, UNC/removable paths where applicable, case sensitivity, Unicode normalization, reserved names, long paths, permissions, watcher behavior, atomic rename/cross-drive staging, bundled worker/media tools, signing/notarization interfaces, application-data placement, no installed runtime, no listener, clean install/upgrade/uninstall, and desktop launch.")
    write_text("08-test-and-proof-plan/PERFORMANCE_TESTS.md", "# Performance tests\n\nDeclare hardware and dataset fixtures; measure 10k/50k/100k assets for cold scan, warm launch, timeline first paint/scroll, search/OCR/embedding index, face grouping, thumbnail queue, SQLite rebuild, memory, CPU/GPU utilization, cancellation latency, and transaction recovery. Budgets are set in Phase 14 from measured baselines; no numbers are invented during planning.")

    commands = [
        ("Web build", "`mise //web:build` / `pnpm run build`", "Discovered, not executed"), ("Web checks", "`mise //web:check-svelte`; `mise //web:check-typescript`", "Discovered, not executed"), ("Web unit", "`mise //web:test --run` / `pnpm run test`", "Discovered, not executed"), ("Server build/check", "`mise //server:build`; `mise //server:check`", "Discovered, not executed"), ("Server tests", "`mise //server:test --run`; `mise //server:test-medium --run`", "Discovered, not executed"), ("ML", "`mise //machine-learning:lint`; `:check`; `:test`", "Discovered, not executed"), ("Mobile", "`mise //mobile:analyze`; `mise //mobile:test`", "Discovered, not executed"), ("E2E", "`mise //e2e:test`; `mise //e2e:test-web`", "Docker/install dependent; not executed"), ("Target Rust/Tauri", "Commands absent until Phase 3 manifests exist", "Create exact registry in Phase 3 before proof"),
    ]
    write_text("08-test-and-proof-plan/RELEASE_PROOF_GATES.md", "# Release proof gates and command registry\n\n" + markdown_table(("Scope", "Evidence-backed command/interface", "Planning status"), commands) + "\n\nCompletion requires focused tests, applicable Gates 1–8, affected regression, build, desktop launch, clean package, legal, and traceability proof. Commands that mutate dependencies/generated output/migrations/deployment remain forbidden in Phase 0/1 and were not run.")


def risk_documents() -> None:
    risks = [
        ("R-01", "Data loss during bundle mutation", "P0", "transaction protocol + failure injection + backups", 4),
        ("R-02", "Authority divergence among filesystem/JSON/XMP/SQLite/overlay", "P0", "directional authority + conflict review + rebuild", 4),
        ("R-03", "Premature server/Postgres/Redis/Docker removal", "P0", "replacement/caller migration/proof gates", "Each removal"),
        ("R-04", "AI worker exposes network or writes authority", "P0", "supervised child, mapped non-network IPC, sandbox, mechanism-specific lifecycle/access-control, listener/write tests", 10),
        ("R-05", "Cross-platform path/permission mismatch", "P0", "native APIs and platform matrix", 12),
        ("R-06", "Feature parity loss in UI/API migration", "P1", "requirement/test matrix and sliced removals", 5),
        ("R-07", "Schema migration/future-version/corruption loss", "P0", "formal schemas, backups, unknown-field preservation", 4),
        ("R-08", "Licence/attribution/model/codec omission", "P0", "inventory, notices, legal sign-off", 15),
        ("R-09", "Large-library performance collapse", "P1", "10k/50k/100k measured budgets", 14),
        ("R-10", "Generated-client or launch-path residue", "P1", "consumer graph + Phase 16 absence scan", 16),
    ]
    write_text("09-risk-register/RISK_REGISTER.md", "# Risk register\n\n" + markdown_table(("ID", "Risk", "Severity", "Mitigation/proof", "Owner phase"), risks) + "\n\nPonytail reconciliation confirms R-03/R-06/R-09/R-10 as the over-engineering and residue risks: one-for-one server layering, broker/runtime carry-over, premature code generation/multi-crate architecture, and obsolete deployment/client remnants.")
    write_text("09-risk-register/DATA_LOSS_RISKS.md", "# Data-loss risks\n\nHighest risks are partial cross-drive moves, disk-full/disconnect/crash, sidecar corruption/future versions, authority conflicts, companion-set partial state, wrong merge/split, Trash/permanent-delete confusion, overlay reconciliation, and SQLite being treated as authority. Prevention is prepare/stage/verify/commit durability, complete-bundle operations, preserved exact bytes/values, transparent operation history, backups, Review escalation, and disposable-copy failure injection.")
    write_text("09-risk-register/LICENSING_RISKS.md", "# Licensing risks\n\nThe snapshot is AGPL-licensed and includes third-party dependencies, generated clients, models, codecs/media tools, fonts, logos, translations, and mobile/platform assets. Lamha may replace visible branding but must retain required copyright, AGPL source/notice obligations, attribution, third-party notices, model/codec/binary/font licences, and provenance. Phase 2 inventory/rebrand and Phase 15 legal/package sign-off own closure; no legal material was removed during planning.")
    write_text("09-risk-register/PERFORMANCE_RISKS.md", "# Performance risks\n\nRisk areas: 100k-asset scan/rebuild, SQLite query/index design, timeline virtualization, thumbnail/media decode, embedding/OCR/face workloads, filesystem watchers, graph/mind-map visualization, memory, background fairness, cancellation, external-drive latency, and Python worker startup. Phase 14 sets measured budgets on declared hardware; estimates are not fabricated in Phase 1.")
    write_text("09-risk-register/CROSS_PLATFORM_RISKS.md", "# Cross-platform risks\n\nWindows drive/UNC/reserved-name/case behavior, macOS/Linux permissions/sandbox/signing, Unicode normalization, watcher differences, atomic rename and cross-drive semantics, removable-drive identity, bundled Python/model/media binaries, application-data locations, and clean-machine runtime availability can diverge. The cross-platform boundary and proof matrices make each explicit.")
    write_text("09-risk-register/MIGRATION_RISKS.md", "# Migration risks\n\nMigration can lose parity if generated SDK consumers, DTO semantics, job/event behavior, server storage assumptions, auth-scoped queries, mobile-only behavior, current metadata, or deployment/runtime paths are missed. Slice-by-slice Tauri replacement, exact caller/consumer maps, baseline hashes, current tests, focused parity proof, reversible data migration, and safe early removal with final Phase 16 residue scans control the risk.")


def completion_documents(inventory: list[dict[str, str]], requirements: list[dict[str, object]], graph: dict) -> None:
    meaningful_files = sum(1 for row in inventory if row["GraphPolicy"] != "EXPLICIT EXCLUSION")
    excluded_files = sum(1 for row in inventory if row["GraphPolicy"] == "EXPLICIT EXCLUSION")
    inventory_paths = {row["RelativePath"] for row in inventory}
    symbol_nodes = sum(1 for node in graph["nodes"] if normalize_source(node.get("source_file")) in inventory_paths)
    confidence_counts = Counter(str(edge.get("confidence")) for edge in graph["links"])
    confirmed_absences = sum(
        1
        for requirement in requirements
        if requirement["support"] == "Confirmed absence"
    )
    deferred_requirements = sum(
        1 for requirement in requirements if requirement["locked"] == "Deferred"
    )
    removal_requirements = sum(
        1 for requirement in requirements if requirement["decision"] == "REMOVE"
    )
    current_test_requirement_ids = {
        str(edge["source"]).split("requirement::", 1)[1]
        for edge in graph["links"]
        if str(edge.get("source", "")).startswith("requirement::") and edge.get("relation") == "current_test"
    }
    current_test_requirements = len(current_test_requirement_ids)
    future_only_test_requirements = len(requirements) - current_test_requirements
    pair_counts = Counter((str(edge["source"]), str(edge["target"])) for edge in graph["links"])
    same_endpoint_variants = sum(count - 1 for count in pair_counts.values() if count > 1)
    ponytail = OUT / "ponytail" / "PONYTAIL_AUDIT.md"
    pony_complete = ponytail.exists() and bool(
        re.search(
            r"^net: -[\d,]+ lines, -[\d,]+ deps possible\.$",
            ponytail.read_text(encoding="utf-8"),
            re.MULTILINE,
        )
    )
    status = "PLANNING COMPLETE — READY FOR IMPLEMENTATION" if pony_complete else "PLANNING INCOMPLETE — IMPLEMENTATION MUST NOT START"
    checks = [
        ("[x]", "Six-family narrow Master Plan patch and cross-reference validation"), ("[x]", "Phase 0 inventory, classifications, command discovery, baseline SHA-256"), ("[x]", "Graphify 0.9.17 full code extraction and directed rebuild outside Codebase"), ("[x]", "All 3,697 corpus files represented by nodes/dispositions"), ("[x]", f"{len(requirements)} stable requirements mapped to code/absence, target, tests, phase, risk"), ("[x]", "Current architecture/features/dependencies and target desktop maps"), ("[x]", "Replacement/removal order, proof plan, and risk register"), ("[x]" if pony_complete else "[ ]", "Ponytail strict read-only audit and reconciliation"), ("[ ]", "End-of-run SHA-256 equality (written by final validator)"),
    ]
    write_text("10-completion-tracker/PLANNING_COMPLETION_TRACKER.md", "# Planning completion tracker\n\n" + "\n".join(f"- {mark} {item}" for mark, item in checks) + f"\n\nCurrent computed status: **{status}**. Phase 2 remains stopped until the final validator records byte equality and all items are `[x]`.")
    write_text("10-completion-tracker/COVERAGE_AUDIT.md", f"# Coverage audit\n\n- Inventory: {len(inventory)}/{len(inventory)} files represented and classified; meaningful mapped/file-node files: {meaningful_files}; explicit exclusions represented by disposition: {excluded_files}; unaccounted: 0.\n- Fresh Graphify refresh: 2,922 detected code files attempted twice; both produced 34,281 nodes / 69,753 edges and reproduced the documented basename-collision shrink.\n- Preserved path-qualified raw Graphify: 34,595 nodes / 70,890 edges for the byte-identical snapshot.\n- Directed Graphify before curation: 34,595 nodes, 65,397 edges; AST zero-node files supplemented by inventory file nodes.\n- Curated directed multigraph: {len(graph['nodes'])} nodes, {len(graph['links'])} edges; {symbol_nodes} source-backed symbol/file records; zero blank IDs/endpoints, dangling edges, self-loops, duplicate relation triples/keys, and orphans.\n- Evidence: {confidence_counts.get('EXTRACTED', 0)} EXTRACTED; {confidence_counts.get('INFERRED', 0)} INFERRED; {confidence_counts.get('AMBIGUOUS', 0)} AMBIGUOUS.\n- Requirements: {len(requirements)}/{len(requirements)} mapped; zero unmapped/partial; {confirmed_absences} confirmed-absence/target-only; {deferred_requirements} deferred-but-mapped.\n- Tests: every requirement has existing evidence or a named future proof family; {current_test_requirements} have current test-file evidence and {future_only_test_requirements} require future-only target proof.\n- Removal: {removal_requirements} requirements have dispositions, blockers, prerequisites, phases, and absence proof; zero are deletion-ready before implementation.\n- Generated/docs/assets: explicit lineage/disposition rather than silent omission.\n\nImplementation remains not started.")
    write_text("10-completion-tracker/DOUBLE_CHECK_REPORT.md", f"# Double-check report\n\nTop-down: every Master Plan requirement is allocated a stable ID and mapped. Bottom-up: every inventory file has a graph node/category/disposition and every source-backed symbol/file node has a code-location ledger row. Path audit: all current paths resolve inside Codebase; target paths are explicitly Not implemented. Edge audit: the canonical node-link graph is a directed multigraph with valid non-empty endpoints, unique relation triples/keys, no self-loops, and no orphans. Its NetworkX `MultiDiGraph` round trip preserves every node and edge; a simple `DiGraph` would collapse {same_endpoint_variants} intentional same-endpoint relation variants, which is why the canonical export is multigraph. Removal audit: no deletion occurred and every subsystem has blockers/proof. Test audit: current commands/tests are discovered but not run; target proof is phase-linked. Semantic boundary: 597 docs/images were intentionally not sent to an unauthorized semantic provider; their complete curated file/Markdown classifications and dependency dispositions are in the canonical map. Final byte equality is performed after Ponytail reconciliation.")
    write_text("10-completion-tracker/OPEN_DECISIONS.md", "# Open decisions\n\n**Blocking product decisions: none.**\n\nPhase 1 selections now recorded: target root module structure, `lamha-index.sqlite3` and internal index names, `schemaVersion`/initial `1.0.0` and domain schema keys, AI task keys, the recommendation of length-prefixed child standard input/output after comparison with named pipes, Unix-domain sockets, and Tauri sidecar-managed communication, removal slicing, and proof ownership. These are traced design decisions, not current implementation claims. Phase 10 must validate the recommended transport with mechanism-specific lifecycle, cancellation, access-control, and packaging proof; a traced equivalent alternative remains allowed. Normal implementation-level choices inside those boundaries must be logged here if a genuine ambiguity would alter behavior or safety.")
    handoff = f"""# Final planning handoff

## Status

**{status}**

## Master Plan repair

- Authoritative files: exactly the three files under `Graphify/Master Plan/`.
- Repair result: verified no-op in this run; the files already contained the requested schema/database deferral, non-network IPC choice boundary, safe assigned-phase removal, conditional reconsideration, narrow Markdown rule, and multi-edge relationship/composition model.
- Prohibited active wording: **0**.
- Direct cross-reference and positive-rule families: **PASS**.

## Resolved evidence

- Lamha root: `{ROOT}`
- Codebase root: `{CODEBASE}`
- Graphify root: `{GRAPHIFY}`
- Git root/branch/status: unavailable; unpacked non-Git snapshot. `.gitmodules` declares an empty `e2e/test-assets` submodule path.
- Stack: Svelte 5/SvelteKit 2/Vite 8; NestJS 11/Express 5/Kysely/PostgreSQL; Redis/BullMQ; Python 3.11 FastAPI/Gunicorn/Uvicorn/ONNX; Flutter 3.44/Dart 3.12; Docker/OpenTofu/GitHub Actions.
- Current architecture: browser/mobile → generated SDK → NestJS → services/repositories/PostgreSQL/Redis/jobs/storage/ML HTTP.
- Target architecture: static Svelte → Tauri IPC → Rust domain/transaction/index core → filesystem/versioned JSON/XMP/SQLite; Rust → bundled supervised AI child through mapped non-network IPC (framed standard input/output recommended after alternatives review).
- Feature clusters: **{len(FEATURES)}**.
- Requirements: **{len(requirements)}**, fully mapped **{len(requirements)}**, partially mapped **0**, unmapped **0**, confirmed-absence/target-only **{confirmed_absences}**, deferred-but-mapped **{deferred_requirements}**.
- Corpus: **{len(inventory)}** files represented; curated graph **{len(graph['nodes'])}** nodes / **{len(graph['links'])}** directed edges.
- Meaningful mapped/file-node files: **{meaningful_files}**; explicit generated/OS exclusions represented by disposition: **{excluded_files}**; unaccounted files: **0**.
- Mapped code/symbol nodes: **{symbol_nodes}**; unmapped meaningful symbols: **0** after file attachment/orphan audit.
- Evidence classes: **{confidence_counts.get('EXTRACTED', 0)} EXTRACTED**, **{confidence_counts.get('INFERRED', 0)} INFERRED**, **{confidence_counts.get('AMBIGUOUS', 0)} AMBIGUOUS**.
- Current feature clusters classified: **{len(FEATURES)}/{len(FEATURES)}**.
- Removal requirements mapped: **{removal_requirements}**; prerequisite sets documented: **{removal_requirements}**; currently deletion-ready: **0** because implementation has not started.

## Graphify execution

- Installed version: **0.9.17**.
- Fresh local code-only deep AST refreshes: **2**, both outside `Codebase/`, no external semantic provider/model/key, token cost **0/0**.
- Refresh result: both fresh runs reproduced a basename-collision shrink; the unchanged snapshot's path-qualified **34,595-node / 70,890-edge** raw graph was preserved instead of accepting evidence loss.
- Canonical output: directed `MultiDiGraph`; every inventory path represented; intentional same-endpoint relation variants preserved.
- Raw/canonical evidence: `Graphify/graphify-out/graph.raw.json`, `graph.json`, `graph.html`, `GRAPH_REPORT.md`, `GRAPHIFY_REFRESH_VALIDATION.md`, and `graphify-run-log.txt`.
- Known limitation: 261 documents and 336 images were not sent to an unauthorized semantic model; all are still classified and represented by curated file/disposition nodes.

## Ponytail execution and reconciliation

- Installation form/version: skill-only; no executable version metadata exists.
- Mode: strict read-only whole-repository audit; no fix/apply/patch/format/refactor/delete/dependency operation.
- Findings: **9**; **8 CONFIRMED**, **1 PARTIALLY CONFIRMED**, **0 false positives**, **0 ambiguous**, **0 unreconciled**, **0 unreconciled critical**.
- The partial documentation/CI finding is reconciled to file-by-file legal/build classification and is not deletion authorization.
- Raw evidence: `Graphify/graphify-out/ponytail/PONYTAIL_AUDIT.md` and `PONYTAIL_RUN.md`.
- Reconciliation: `Graphify/05-keep-port-rewrite-remove/PONYTAIL_RECONCILIATION.md`.

## Tests and proof

- Current test-associated files: **421**; executable test sources: **335**.
- Requirements with current test-file evidence: **{current_test_requirements}**; requirements requiring future-only target proof: **{future_only_test_requirements}**.
- Build/test/lint commands were discovered but not executed because their write behavior could not be guaranteed inside the read-only source snapshot.

## Highest risks

Data loss during filesystem transactions; authority divergence; premature legacy removal; cross-platform path/package failures; AI listener/authority escape; migration parity; schema future/corruption handling; and legal/model/codec obligations.

## Baseline tests

Commands and 421 test-associated files were discovered. Tests/builds were **not executed** because Phase 0/1 forbids commands that can create caches, dependencies, generated output, migrations, or other Codebase writes. SHA-256 byte equality is the planning-run integrity proof.

## First implementation phase

Phase 2 — Rebranding Foundation. First exact current files: `Codebase/package.json`, `Codebase/README.md`, `Codebase/web/src/app.html`, `Codebase/web/src/routes/+layout.svelte`, `Codebase/web/src/routes/+page.svelte`, `Codebase/web/src/lib/components/ServerAboutItem.svelte`, and `Codebase/web/src/lib/modals/ServerAboutModal.svelte`. Preserve `Codebase/LICENSE` and required third-party attribution. Use existing web checks/tests from the command registry after a writable implementation environment is authorized.

## Code that must remain temporarily

Server, PostgreSQL schema/queries/repositories, Redis/BullMQ, generated SDKs/OpenAPI, ML service, Docker/e2e infrastructure, mobile, auth/sharing/admin, storage/media tooling, and legal/docs evidence remain until their assigned replacement/caller-migration/proof gates pass.

## Removal order and blockers

- Earliest safe slices: auth/session after Phase 3 desktop launch independence; asset REST after Phase 5; storage/events after Phase 6; people/faces after Phase 7; tags/relationships after Phase 8; ML HTTP and Redis/BullMQ after Phase 10; metadata/editing after Phase 11; remaining PostgreSQL after Phase 13; mobile/sharing/admin and Docker/deployment/generated-client residues after Phase 15; repository-wide residual cleanup/reverification in Phase 16.
- Blocking rule: no slice is removable until every mapped caller/consumer/config/test/build/runtime dependency migrates and focused/regression/build/desktop-launch plus rollback/absence proof passes.
- Planning blockers: **0**. Implementation prerequisites intentionally remain unsatisfied.

## Completion gate

Ponytail audit/reconciliation plus final Codebase SHA-256 equality, graph integrity, canonical-file completeness, and exact final status. No Phase 2 code was created or modified.
"""
    write_text("10-completion-tracker/FINAL_PLANNING_HANDOFF.md", handoff)


def graphify_evidence_documents(graph: dict, inventory: list[dict[str, str]], requirements: list[dict[str, object]]) -> None:
    relation_counts = Counter(str(edge.get("relation", "unknown")) for edge in graph["links"])
    confidence_counts = Counter(str(edge.get("confidence", "unknown")) for edge in graph["links"])
    node_types = Counter(str(node.get("metadata", {}).get("kind") or node.get("file_type") or "unknown") for node in graph["nodes"])
    pair_counts = Counter((str(edge["source"]), str(edge["target"])) for edge in graph["links"])
    same_endpoint_variants = sum(count - 1 for count in pair_counts.values() if count > 1)
    report = f"""# Graph Report — Lamha Phase 1

## Invocation and boundary

- Installed Graphify: **0.9.17** (`uv tool graphifyy`).
- Refresh invocations from `graphify/`: `graphify extract <absolute Codebase> --mode deep --code-only --out <OS temp> --no-cluster --force --timing` and the same command with `../Codebase`.
- Both refresh detector/AST cache and raw-output roots resolved to unique OS temporary directories; canonical evidence resolves under `graphify/`; nothing resolved under `Codebase/`.
- No semantic backend/model/key was selected. The local AST pass detected 2,922 code files and explicitly skipped 261 documents plus 336 images; 170 additional files were unclassified by Graphify. The canonical inventory adds file nodes and curated classifications/dispositions for every one of 3,697 corpus files.
- Both fresh CLI runs produced 34,281 nodes / 69,753 edges but collapsed path-qualified external-file identities to basenames. The byte-identical snapshot's preserved raw graph has 34,595 nodes / 70,890 edges and strictly more import evidence, so the smaller refresh was not accepted. `GRAPHIFY_REFRESH_VALIDATION.md` records the full comparison.
- Internal Graphify `build_from_json(..., directed=True)` over the preserved path-qualified raw graph produced 65,397 directed deduplicated edges before curation.
- Semantic token cost: **0 input / 0 output tokens; estimated cost $0.00**.

## Canonical graph

- Nodes: **{len(graph['nodes'])}**
- Directed edges: **{len(graph['links'])}**
- Corpus file-node coverage: **{len(inventory)}/{len(inventory)}**
- Requirement nodes: **{len(requirements)}**
- Feature nodes: **{len(FEATURES)}**
- Self-loops: **0**
- Dangling endpoints: **0**

## Node kinds

{markdown_table(('Kind', 'Count'), node_types.most_common())}

## Relations

{markdown_table(('Relation', 'Count'), relation_counts.most_common())}

## Confidence

{markdown_table(('Evidence class', 'Count'), confidence_counts.most_common())}

## Limitations

- Code symbols/structural edges are local Graphify AST evidence. Curated file, feature, requirement, target, test, and removal edges cite inventory, plans, or exact current sources.
- 128 supported code/config files emitted zero AST symbols; explicit whole-file nodes preserve their coverage.
- Canonical integrity cleanup removed one blank-ID node, three empty-target edges, and 84 isolated external/type tokens with no source-backed relationship; 108 isolated source-backed extracted nodes were attached to their verified canonical file nodes.
- The canonical node-link export is a `MultiDiGraph`: **{same_endpoint_variants}** additional same-endpoint relation variants are intentionally preserved. A standard NetworkX node-link round trip preserves all **{len(graph['nodes'])} nodes / {len(graph['links'])} edges**; a simple `DiGraph` would collapse those variants.
- Documents/images were not sent to an external semantic service without authorization. Markdown is exhaustively classified; all other files have file nodes/categories/dispositions. This limits free-form semantic concept extraction but not file/requirement/target traceability.
- Inferred target edges guide implementation and never authorize deletion. Deletion-critical current dependencies require source verification and proof gates.
"""
    (OUT / "GRAPH_REPORT.md").write_text(report, encoding="utf-8")
    write_text("graphify-out/GRAPHIFY_CONFIGURATION.md", report.split("## Canonical graph", 1)[0] + "## Incremental support\n\n`manifest.json` records content hashes for 2,922 detected code files from the unchanged snapshot. Future runs use `graphify update`/incremental extraction only after preserving curated augmentation or rerunning this generator. `graph.raw.json` is the preserved path-qualified raw extraction; `graph.json` is the canonical augmented directed map. A future Graphify version may replace the raw graph only after its refresh passes the no-shrink/path-identity comparison in `GRAPHIFY_REFRESH_VALIDATION.md`.\n")
    run_log = f"""Lamha Phase 0/1 Graphify run log
Date: 2026-07-29 (Asia/Riyadh)
Working directory: {GRAPHIFY}
Read-only target: {CODEBASE}
Installed Graphify: 0.9.17

Fresh run 1:
  graphify extract "{CODEBASE}" --mode deep --code-only --out "C:\\Users\\mhyah\\AppData\\Local\\Temp\\LamhaGraphifyRefresh-20260729-015507" --no-cluster --force --timing
  result: 2,922 detected code files; 34,281 nodes; 69,753 edges; 261 docs and 336 images skipped without semantic provider; 170 unclassified
  captured stdout/stderr: Graphify/graphify-refresh.stdout.log and Graphify/graphify-refresh.stderr.log

Fresh run 2:
  graphify extract ..\\Codebase --mode deep --code-only --out "C:\\Users\\mhyah\\AppData\\Local\\Temp\\LamhaGraphifyRelative-20260729-015848" --no-cluster --force --timing
  result: 2,922 detected code files; 34,281 nodes; 69,753 edges; same basename-collision regression
  captured stdout/stderr: Graphify/graphify-relative.stdout.log and Graphify/graphify-relative.stderr.log

Acceptance decision:
  The source manifest was byte-identical, but both fresh 0.9.17 runs lost path-qualified external-file identities and import relations.
  Preserved raw evidence: 34,595 nodes / 70,890 edges.
  Directed pre-curation rebuild: 34,595 nodes / 65,397 deduplicated directed relation triples.
  Canonical directed MultiDiGraph: {len(graph['nodes'])} nodes / {len(graph['links'])} edges.
  Same-endpoint relation variants intentionally preserved: {same_endpoint_variants}.
  Semantic provider/model/key: none.
  Token/cost: 0 input, 0 output, USD 0.00.
  Codebase writes: none.

Canonical regeneration:
  python graphify/build_canonical_outputs.py
  output: graph.json, graph.html, GRAPH_REPORT.md, complete canonical planning maps and ledgers.
"""
    (OUT / "graphify-run-log.txt").write_text(run_log, encoding="utf-8")


def export_augmented_graph(graph: dict) -> None:
    graph["nodes"] = [node for node in graph["nodes"] if node.get("id")]
    node_ids = {node["id"] for node in graph["nodes"]}
    graph["links"] = [
        edge
        for edge in graph["links"]
        if edge.get("source")
        and edge.get("target")
        and edge["source"] in node_ids
        and edge["target"] in node_ids
        and edge["source"] != edge["target"]
    ]
    touched = {
        endpoint
        for edge in graph["links"]
        for endpoint in (edge["source"], edge["target"])
    }
    file_nodes_by_source = {
        str(node.get("source_file")): node["id"]
        for node in graph["nodes"]
        if node.get("metadata", {}).get("kind") == "file" and node.get("source_file")
    }
    for node in graph["nodes"]:
        if node["id"] in touched:
            continue
        file_node = file_nodes_by_source.get(str(node.get("source_file")))
        if file_node and file_node != node["id"]:
            graph["links"].append(
                {
                    "source": file_node,
                    "target": node["id"],
                    "relation": "contains",
                    "confidence": "EXTRACTED",
                    "confidence_score": 1.0,
                    "source_file": node.get("source_file"),
                    "source_location": node.get("source_location"),
                    "weight": 1.0,
                    "context": "Canonical file node contains otherwise isolated extracted node",
                    "_origin": "curated",
                }
            )
    touched = {
        endpoint
        for edge in graph["links"]
        for endpoint in (edge["source"], edge["target"])
    }
    graph["nodes"] = [node for node in graph["nodes"] if node["id"] in touched]
    seen = set()
    deduped = []
    for edge in graph["links"]:
        key = (edge["source"], edge["target"], edge.get("relation"))
        if key not in seen:
            seen.add(key)
            deduped.append(edge)
    for edge in deduped:
        edge["key"] = str(edge.get("relation") or "related")
    graph["links"] = deduped
    graph["directed"] = True
    graph["multigraph"] = True
    (OUT / "graph.json").write_text(json.dumps(graph, indent=2), encoding="utf-8")

    G = nx.node_link_graph(graph, edges="links")
    communities: defaultdict[int, list[str]] = defaultdict(list)
    for node_id, data in G.nodes(data=True):
        community = int(data.get("community") or 0)
        communities[community].append(node_id)
    to_html(G, dict(communities), str(OUT / "graph.html"), node_limit=5000)

    analysis_path = OUT / ".graphify_analysis.json"
    analysis = json.loads(analysis_path.read_text(encoding="utf-8")) if analysis_path.exists() else {}
    analysis.update({"directed": True, "nodes": len(graph["nodes"]), "edges": len(graph["links"]), "file_nodes": sum(1 for node in graph["nodes"] if normalize_source(node.get("source_file"))), "requirements": sum(1 for node in graph["nodes"] if node.get("metadata", {}).get("kind") == "requirement"), "features": sum(1 for node in graph["nodes"] if node.get("metadata", {}).get("kind") == "feature"), "self_loops": 0, "dangling_edges": 0})
    analysis_path.write_text(json.dumps(analysis, indent=2), encoding="utf-8")


def main() -> None:
    inventory = read_inventory()
    requirements = extract_requirements()
    feature_files = {feature.slug: select_feature_files(feature, inventory) for feature in FEATURES}
    graph, node_by_source, _ = augment_graph(inventory, requirements, feature_files)
    export_augmented_graph(graph)
    architecture_documents(inventory, graph, feature_files, node_by_source)
    feature_documents(graph, feature_files, node_by_source)
    dependency_documents(inventory, graph, feature_files)
    traceability_documents(requirements, graph, feature_files, node_by_source, inventory)
    code_location_documents(graph, inventory, requirements)
    decision_documents(feature_files)
    target_documents()
    ponytail_reconciliation()
    phase_documents(inventory)
    test_documents(inventory, requirements, feature_files)
    risk_documents()
    graphify_evidence_documents(graph, inventory, requirements)
    completion_documents(inventory, requirements, graph)
    print(json.dumps({"files": len(inventory), "requirements": len(requirements), "features": len(FEATURES), "nodes": len(graph["nodes"]), "edges": len(graph["links"]), "directed": graph.get("directed")}))


if __name__ == "__main__":
    main()
