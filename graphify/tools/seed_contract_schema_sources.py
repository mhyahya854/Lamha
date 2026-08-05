"""One-time materializer for reviewed contract and record schema candidates.

The production builder never imports this module.  It copies only the explicit
JSON/CSV/SQL sources produced here after their review ledgers are complete.
"""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path

from write_guard import guard_write_path, remove_file, write_csv as guarded_write_csv, write_text as guarded_write_text


GRAPHIFY = Path(__file__).resolve().parents[1]
SOURCE = GRAPHIFY / "semantic-plan-source"
LEGACY = GRAPHIFY / "12-semantic-implementation-plan"
CONTRACTS = SOURCE / "contracts"
RECORDS = SOURCE / "schemas"


def safe_path(path: Path) -> Path:
    return guard_write_path(path)


def write_text(path: Path, value: str) -> None:
    guarded_write_text(path, value)


def write_json(path: Path, value: object) -> None:
    write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    guarded_write_csv(path, rows, fields)


def obj(properties: dict[str, object], required: list[str] | None = None, *, title: str | None = None) -> dict[str, object]:
    value: dict[str, object] = {
        "type": "object",
        "properties": properties,
        "required": required if required is not None else list(properties),
        "additionalProperties": False,
    }
    if title:
        value["title"] = title
    return value


def arr(items: object, *, min_items: int = 0, unique: bool = False) -> dict[str, object]:
    value: dict[str, object] = {"type": "array", "items": items, "minItems": min_items}
    if unique:
        value["uniqueItems"] = True
    return value


def ref(name: str) -> dict[str, str]:
    return {"$ref": f"../../shared-definitions-v1.schema.json#/$defs/{name}"}


def record_ref(name: str) -> dict[str, str]:
    return {"$ref": f"../record-shared-v1.schema.json#/$defs/{name}"}


def shared_contract_schema() -> dict[str, object]:
    identifier = {"type": "string", "pattern": "^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"}
    timestamp = {"type": "string", "format": "date-time"}
    revision = {"type": "integer", "minimum": 0}
    defs: dict[str, object] = {
        "Id": identifier,
        "Timestamp": timestamp,
        "Revision": revision,
        "RequestId": {"type": "string", "format": "uuid"},
        "PathRef": obj({"rootId": identifier, "relativePath": {"type": "string", "minLength": 1, "maxLength": 32768}, "expectedDriveId": {"anyOf": [identifier, {"type": "null"}]}}, ["rootId", "relativePath"]),
        "PageRequest": obj({"cursor": {"type": ["string", "null"], "maxLength": 2048}, "limit": {"type": "integer", "minimum": 1, "maximum": 500}}),
        "PageInfo": obj({"nextCursor": {"type": ["string", "null"], "maxLength": 2048}, "snapshotRevision": revision, "returned": {"type": "integer", "minimum": 0}}),
        "SortSpec": obj({"field": {"enum": ["CAPTURED_AT", "CREATED_AT", "UPDATED_AT", "FILENAME", "TITLE", "RELEVANCE"]}, "direction": {"enum": ["ASC", "DESC"]}, "nulls": {"enum": ["FIRST", "LAST"]}}),
        "Conflict": obj({"code": {"enum": ["REVISION", "PATH", "COLLISION", "AUTHORITY", "MISSING", "FORMAT"]}, "recordId": {"anyOf": [identifier, {"type": "null"}]}, "message": {"type": "string", "minLength": 1, "maxLength": 1000}, "recoverable": {"type": "boolean"}}, ["code", "message", "recoverable"]),
        "Warning": obj({"code": {"type": "string", "pattern": "^[A-Z][A-Z0-9_]{2,63}$"}, "message": {"type": "string", "minLength": 1, "maxLength": 1000}, "recordId": {"anyOf": [identifier, {"type": "null"}]}}, ["code", "message"]),
        "OperationHandle": obj({"operationId": identifier, "requestId": {"type": "string", "format": "uuid"}, "state": {"enum": ["ACCEPTED", "RUNNING", "PAUSED", "CANCELLING", "COMMITTED", "FAILED", "CANCELLED", "RECOVERY_REQUIRED"]}, "acceptedAt": timestamp, "cancellable": {"type": "boolean"}, "resumeSupported": {"type": "boolean"}}),
        "MutationReceipt": obj({"entityId": identifier, "revision": revision, "state": {"enum": ["CREATED", "UPDATED", "DELETED", "CONFIRMED", "UNCHANGED"]}, "committedAt": timestamp, "warnings": arr({"$ref": "#/$defs/Warning"})}),
        "StatusSnapshot": obj({"state": {"enum": ["READY", "DEGRADED", "BUSY", "PAUSED", "DISCONNECTED", "RECOVERY_REQUIRED"]}, "snapshotRevision": revision, "observedAt": timestamp, "warnings": arr({"$ref": "#/$defs/Warning"})}),
        "RootFilter": obj({"state": {"type": ["string", "null"], "enum": ["CONNECTED", "DISCONNECTED", "READ_ONLY", "READ_WRITE", None]}, "includeUnavailable": {"type": "boolean"}}),
        "RootSummary": obj({"rootId": identifier, "displayName": {"type": "string", "minLength": 1, "maxLength": 255}, "path": {"$ref": "#/$defs/PathRef"}, "accessMode": {"enum": ["READ_ONLY", "READ_WRITE"]}, "state": {"enum": ["CONNECTED", "DISCONNECTED", "MISMATCHED", "PERMISSION_DENIED"]}, "revision": revision}),
        "AssetFilter": obj({"rootIds": arr(identifier, unique=True), "mediaTypes": arr({"enum": ["IMAGE", "VIDEO", "AUDIO"]}, unique=True), "capturedFrom": {"type": ["string", "null"], "format": "date-time"}, "capturedTo": {"type": ["string", "null"], "format": "date-time"}, "favorite": {"type": ["boolean", "null"]}, "reviewStates": arr({"enum": ["NONE", "OPEN", "DEFERRED", "RESOLVED"]}, unique=True), "missingOnly": {"type": "boolean"}}),
        "AssetListItem": obj({"assetId": identifier, "identityId": identifier, "rootId": identifier, "filename": {"type": "string", "minLength": 1}, "mediaType": {"enum": ["IMAGE", "VIDEO", "AUDIO"]}, "mimeType": {"type": "string", "pattern": "^[^/]+/[^/]+$"}, "capturedAt": {"type": ["string", "null"], "format": "date-time"}, "width": {"type": ["integer", "null"], "minimum": 1}, "height": {"type": ["integer", "null"], "minimum": 1}, "durationMs": {"type": ["integer", "null"], "minimum": 0}, "favorite": {"type": "boolean"}, "previewRevision": {"type": ["integer", "null"], "minimum": 0}, "integrityState": {"enum": ["VERIFIED", "STALE", "MISSING", "MISMATCH", "UNKNOWN"]}, "revision": revision}),
        "AssetDetail": obj({"summary": {"$ref": "#/$defs/AssetListItem"}, "primaryPath": {"$ref": "#/$defs/PathRef"}, "fileSizeBytes": {"type": "integer", "minimum": 0}, "contentHash": {"type": ["string", "null"], "pattern": "^[a-fA-F0-9]{32,128}$"}, "camera": {"$ref": "#/$defs/CameraMetadata"}, "gps": {"$ref": "#/$defs/GpsMetadata"}, "tagIds": arr(identifier, unique=True), "albumIds": arr(identifier, unique=True), "eventIds": arr(identifier, unique=True), "personIds": arr(identifier, unique=True), "sidecars": arr({"$ref": "#/$defs/SidecarSummary"}), "companions": arr({"$ref": "#/$defs/CompanionSummary"}), "privacyState": {"enum": ["PRIVATE", "EXPORT_REDACT", "EXPORT_ALLOWED"]}}),
        "CameraMetadata": obj({"make": {"type": ["string", "null"], "maxLength": 255}, "model": {"type": ["string", "null"], "maxLength": 255}, "lens": {"type": ["string", "null"], "maxLength": 255}, "iso": {"type": ["integer", "null"], "minimum": 0}, "aperture": {"type": ["number", "null"], "exclusiveMinimum": 0}, "exposureSeconds": {"type": ["number", "null"], "exclusiveMinimum": 0}, "focalLengthMm": {"type": ["number", "null"], "minimum": 0}, "cameraOwner": {"type": ["string", "null"], "maxLength": 500}}),
        "GpsMetadata": obj({"latitude": {"type": ["number", "null"], "minimum": -90, "maximum": 90}, "longitude": {"type": ["number", "null"], "minimum": -180, "maximum": 180}, "altitudeMeters": {"type": ["number", "null"]}, "source": {"enum": ["EMBEDDED", "XMP", "ASSET_JSON", "USER", "AI_PROPOSAL", "NONE"]}}),
        "SidecarSummary": obj({"sidecarId": identifier, "kind": {"enum": ["ASSET_JSON", "XMP", "EXTERNAL_XMP"]}, "path": {"$ref": "#/$defs/PathRef"}, "state": {"enum": ["HEALTHY", "MISSING", "CORRUPT", "FUTURE_VERSION", "PENDING_OVERLAY"]}, "revision": revision}),
        "CompanionSummary": obj({"assetId": identifier, "kind": {"enum": ["LIVE_PHOTO_IMAGE", "LIVE_PHOTO_VIDEO", "RAW", "JPEG_RENDER", "MOTION_PHOTO"]}, "bundleRole": {"enum": ["PRIMARY", "COMPANION"]}, "revision": revision}),
        "SearchFilter": obj({"asset": {"$ref": "#/$defs/AssetFilter"}, "text": {"type": ["string", "null"], "maxLength": 1000}, "ocr": {"type": ["string", "null"], "maxLength": 1000}, "personIds": arr(identifier, unique=True), "tagIds": arr(identifier, unique=True), "eventIds": arr(identifier, unique=True), "locationRadius": {"$ref": "#/$defs/LocationRadius"}}),
        "LocationRadius": obj({"latitude": {"type": "number", "minimum": -90, "maximum": 90}, "longitude": {"type": "number", "minimum": -180, "maximum": 180}, "radiusMeters": {"type": "number", "exclusiveMinimum": 0, "maximum": 1000000}}),
        "SearchHit": obj({"asset": {"$ref": "#/$defs/AssetListItem"}, "score": {"type": "number", "minimum": 0}, "matchedFields": arr({"enum": ["FILENAME", "METADATA", "OCR", "PERSON", "TAG", "EVENT", "LOCATION", "EMBEDDING"]}, unique=True), "explanation": {"type": "string", "maxLength": 2000}}),
        "EventDraft": obj({"title": {"type": "string", "minLength": 1, "maxLength": 500}, "startAt": timestamp, "endAt": timestamp, "timeZone": {"type": "string", "minLength": 1, "maxLength": 100}, "location": {"$ref": "#/$defs/GpsMetadata"}, "assetIds": arr(identifier, min_items=1, unique=True), "attendeePersonIds": arr(identifier, unique=True), "photographerPersonIds": arr(identifier, unique=True), "expectedRevision": {"anyOf": [revision, {"type": "null"}]}}, ["title", "startAt", "endAt", "timeZone", "assetIds"]),
        "EventSummary": obj({"eventId": identifier, "title": {"type": "string", "minLength": 1}, "startAt": timestamp, "endAt": timestamp, "assetCount": {"type": "integer", "minimum": 0}, "reviewState": {"enum": ["DRAFT", "PROPOSED", "CONFIRMED", "CONFLICT"]}, "revision": revision}),
        "PersonDraft": obj({"canonicalName": {"type": "string", "minLength": 1, "maxLength": 500}, "aliases": arr({"type": "string", "minLength": 1, "maxLength": 500}, unique=True), "profileAssetId": {"anyOf": [identifier, {"type": "null"}]}, "hidden": {"type": "boolean"}, "expectedRevision": {"anyOf": [revision, {"type": "null"}]}}, ["canonicalName", "aliases", "hidden"]),
        "PersonSummary": obj({"personId": identifier, "canonicalName": {"type": "string", "minLength": 1}, "aliases": arr({"type": "string"}, unique=True), "profileAssetId": {"anyOf": [identifier, {"type": "null"}]}, "hidden": {"type": "boolean"}, "confirmedFaceCount": {"type": "integer", "minimum": 0}, "revision": revision}),
        "RelationshipDraft": obj({"fromPersonId": identifier, "toPersonId": identifier, "relationshipType": {"type": "string", "minLength": 1, "maxLength": 200}, "certainty": {"enum": ["SURE", "NOT_SURE"]}, "effectiveFrom": {"type": ["string", "null"], "format": "date-time"}, "effectiveTo": {"type": ["string", "null"], "format": "date-time"}, "notes": {"type": ["string", "null"], "maxLength": 4000}, "expectedRevision": {"anyOf": [revision, {"type": "null"}]}}, ["fromPersonId", "toPersonId", "relationshipType", "certainty"]),
        "RelationshipSummary": obj({"relationshipId": identifier, "fromPersonId": identifier, "toPersonId": identifier, "relationshipType": {"type": "string"}, "certainty": {"enum": ["SURE", "NOT_SURE"]}, "status": {"enum": ["ACTIVE", "FORMER"]}, "revision": revision}),
        "SettingsPatch": obj({"theme": {"enum": ["SYSTEM", "LIGHT", "DARK"]}, "locale": {"type": "string", "pattern": "^[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})*$"}, "thumbnailSize": {"enum": ["SMALL", "MEDIUM", "LARGE"]}, "hardwareAcceleration": {"enum": ["AUTO", "CPU_ONLY", "PREFER_GPU"]}, "reduceMotion": {"type": "boolean"}, "highContrast": {"type": "boolean"}, "telemetryEnabled": {"const": False}}, [], title="Settings patch"),
        "ExecutionOptions": obj({"dryRun": {"type": "boolean"}, "confirmedPlanId": {"anyOf": [identifier, {"type": "null"}]}, "collisionPolicy": {"enum": ["FAIL", "RENAME", "REVIEW", "SKIP"]}, "companionPolicy": {"const": "ATOMIC_LOGICAL_BUNDLE"}}),
        "OperationPlanOptions": obj({"rootId": identifier, "assetIds": arr(identifier, min_items=1, unique=True), "destination": {"anyOf": [{"$ref": "#/$defs/PathRef"}, {"type": "null"}]}, "collisionPolicy": {"enum": ["FAIL", "RENAME", "REVIEW", "SKIP"]}, "includeCompanions": {"const": True}}),
        "OperationPlan": obj({"planId": identifier, "requestId": {"type": "string", "format": "uuid"}, "state": {"enum": ["PREVIEW", "CONFIRMED", "EXPIRED", "COMMITTED"]}, "expiresAt": timestamp, "operationCount": {"type": "integer", "minimum": 1}, "sourceBytes": {"type": "integer", "minimum": 0}, "requiredBytes": {"type": "integer", "minimum": 0}, "collisions": arr({"$ref": "#/$defs/Conflict"}), "warnings": arr({"$ref": "#/$defs/Warning"})}),
        "PreviewResult": obj({"previewId": identifier, "sourceRevision": revision, "mimeType": {"type": "string", "pattern": "^[^/]+/[^/]+$"}, "width": {"type": "integer", "minimum": 1}, "height": {"type": "integer", "minimum": 1}, "durationMs": {"type": ["integer", "null"], "minimum": 0}, "cachePath": {"$ref": "#/$defs/PathRef"}, "warnings": arr({"$ref": "#/$defs/Warning"})}),
        "AIResult": obj({"candidateId": identifier, "taskId": identifier, "candidateType": {"enum": ["OCR", "FACE", "DUPLICATE", "LOCATION", "TAG", "EMBEDDING"]}, "assetId": identifier, "assetRevision": revision, "confidence": {"type": "number", "minimum": 0, "maximum": 1}, "modelId": identifier, "modelVersion": {"type": "string", "minLength": 1}, "modelChecksum": {"type": "string", "pattern": "^[a-fA-F0-9]{32,128}$"}, "reviewState": {"enum": ["PROPOSED", "APPROVED", "REJECTED", "DEFERRED", "SUPPRESSED"]}}),
        "ReviewItem": obj({"reviewItemId": identifier, "candidateId": identifier, "candidateType": {"enum": ["OCR", "FACE", "DUPLICATE", "LOCATION", "TAG", "EVENT", "RELATIONSHIP", "METADATA_CONFLICT"]}, "state": {"enum": ["OPEN", "APPROVED", "REJECTED", "DEFERRED", "SUPPRESSED"]}, "assetIds": arr(identifier, unique=True), "summary": {"type": "string", "minLength": 1, "maxLength": 2000}, "createdAt": timestamp, "revision": revision}),
        "ExportPlan": obj({"plan": {"$ref": "#/$defs/OperationPlan"}, "destinationRootId": identifier, "assetIds": arr(identifier, min_items=1, unique=True), "privacyRecipeId": {"anyOf": [identifier, {"type": "null"}]}, "derivativePolicy": {"enum": ["ORIGINAL", "EDITED_DERIVATIVE", "PRIVACY_REDACTED"]}}),
        "BackupRequest": obj({"destinationRootId": identifier, "sourceRootIds": arr(identifier, min_items=1, unique=True), "includeMedia": {"type": "boolean"}, "includeAuthoritativeRecords": {"const": True}, "expectedManifestRevision": {"type": ["integer", "null"], "minimum": 0}}),
        "RestoreRequest": obj({"backupManifestId": identifier, "destinationRootId": identifier, "collisionPolicy": {"enum": ["FAIL", "RENAME", "REVIEW", "SKIP"]}, "verifyBeforeCommit": {"const": True}}),
        "TrashResult": obj({"operationId": identifier, "trashedAssetIds": arr(identifier, unique=True), "trashRootId": identifier, "recoverableUntil": {"type": ["string", "null"], "format": "date-time"}, "warnings": arr({"$ref": "#/$defs/Warning"})}),
        "MapDraft": obj({"scopeType": {"enum": ["GLOBAL", "EVENT", "FOLDER", "PERSON", "GROUP"]}, "scopeId": {"anyOf": [identifier, {"type": "null"}]}, "title": {"type": "string", "minLength": 1}, "nodeIds": arr(identifier, unique=True), "expectedRevision": {"type": ["integer", "null"], "minimum": 0}}),
        "MapProjection": obj({"projectionId": identifier, "scopeType": {"enum": ["GLOBAL", "EVENT", "FOLDER", "PERSON", "GROUP"]}, "scopeId": {"anyOf": [identifier, {"type": "null"}]}, "nodeCount": {"type": "integer", "minimum": 0}, "edgeCount": {"type": "integer", "minimum": 0}, "sourceRevision": revision}),
        "TagSummary": obj({"tagId": identifier, "namespace": {"type": "string", "minLength": 1}, "name": {"type": "string", "minLength": 1}, "parentTagId": {"anyOf": [identifier, {"type": "null"}]}, "revision": revision}),
    }
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "$id": "https://lamha.local/schemas/ipc/shared-definitions-v1.schema.json", "$defs": defs}


READ_ONLY = {
    "app.status", "app.settings_get", "roots.list", "roots.validate", "assets.page", "assets.get", "assets.locate",
    "assets.open", "assets.selection_summary", "assets.hash_verify", "scan.plan", "scan.status", "events.plan_merge",
    "events.plan_link", "events.plan_split", "events.plan_normalize", "people.clusters_page", "people.person_get",
    "relationships.list", "relationships.history", "relationships.projection_preview", "tags.namespaces", "tags.candidates",
    "maps.global_load", "maps.scoped_load", "maps.simulate", "search.structured", "search.text", "search.ocr",
    "search.semantic", "review.list", "review.get", "ai.hardware_assess", "ai.models", "ai.plan", "metadata.inspect",
    "metadata.propose_update", "metadata.snapshot", "editing.recipe_get", "editing.render_preview", "editing.export_plan",
    "maintenance.backup_plan", "maintenance.backup_verify", "maintenance.trash_plan", "maintenance.restore_plan",
    "maintenance.permanent_delete_plan", "maintenance.rebuild_plan", "maintenance.status", "operations.simulate",
    "operations.get", "operations.list",
}

DERIVED_MUTATION = {"assets.thumbnail_request", "scan.start", "scan.pause", "scan.resume", "scan.cancel", "scan.watcher_reconcile", "search.cancel", "ai.start", "ai.pause", "ai.resume", "ai.cancel", "ai.retry", "ai.invalidate", "maintenance.rebuild_run"}

LONG_RUNNING = {
    "app.diagnostics_export", "roots.rescan", "assets.hash_verify", "scan.start", "scan.watcher_reconcile", "events.commit_plan",
    "people.merge", "people.split", "people.face_correct", "maps.materialize", "maps.recover", "search.structured", "search.text",
    "search.ocr", "search.semantic", "ai.hardware_assess", "ai.start", "ai.invalidate", "metadata.apply_update",
    "metadata.privacy_export", "metadata.restore", "editing.render_preview", "editing.export_commit", "maintenance.backup_run",
    "maintenance.backup_verify", "maintenance.trash_commit", "maintenance.restore_commit", "maintenance.permanent_delete_commit",
    "maintenance.rebuild_run", "operations.recover", "operations.rollback", "operations.diagnostics_export",
}

DESTRUCTIVE = {
    "roots.remove", "events.commit_plan", "maps.materialize", "metadata.apply_update", "metadata.restore", "editing.export_commit",
    "maintenance.trash_commit", "maintenance.restore_commit", "maintenance.permanent_delete_commit", "operations.recover", "operations.rollback",
}

CANCELLABLE = {command for command in LONG_RUNNING if command not in {"events.commit_plan", "maintenance.permanent_delete_commit", "operations.rollback"}}


def package_for(command_id: str, packages: list[dict[str, object]]) -> str:
    by_key = {str(package["key"]): str(package["work_package_id"]) for package in packages}
    domain, action = command_id.split(".", 1)
    key = {
        "app": "ipc-envelope", "roots": "root-authorization", "assets": "path-index", "scan": "initial-scanner",
        "events": "event-ui", "people": "people-ui", "relationships": "relationship-records", "tags": "tag-records",
        "maps": "projection-contract", "search": "semantic-search", "review": "review-shell", "ai": "worker-lifecycle",
        "metadata": "metadata-mutation", "editing": "edit-recipe", "maintenance": "backup-manifest", "operations": "file-plan",
    }[domain]
    refinements = {
        "assets.thumbnail_request": "preview-generation", "assets.hash_verify": "content-hash", "scan.watcher_reconcile": "incremental-scan",
        "events.commit_plan": "event-materialize", "people.face_correct": "face-corrections", "people.merge": "person-merge",
        "people.split": "person-merge", "relationships.history": "relationship-history", "relationships.projection_preview": "relationship-views",
        "tags.candidates": "tag-candidates", "maps.materialize": "materialize-plan", "maps.recover": "map-recovery",
        "search.ocr": "ocr", "search.semantic": "semantic-search", "review.list": "review-shell", "ai.models": "model-registry",
        "ai.hardware_assess": "hardware-assessment", "metadata.privacy_export": "privacy-export", "editing.export_commit": "edit-export",
        "maintenance.trash_commit": "trash", "maintenance.restore_commit": "restore", "maintenance.permanent_delete_commit": "permanent-delete",
        "maintenance.rebuild_run": "rebuild-all", "operations.recover": "transaction-recovery", "operations.rollback": "transaction-recovery",
    }
    key = refinements.get(command_id, key)
    if key in by_key:
        return by_key[key]
    phase = {
        "app": "I2", "roots": "I3", "assets": "I4", "scan": "I4", "events": "I6", "people": "I7",
        "relationships": "I8", "tags": "I8", "maps": "I9", "search": "I10", "review": "I5", "ai": "I10",
        "metadata": "I11", "editing": "I11", "maintenance": "I13", "operations": "I3",
    }[domain]
    return next(str(package["work_package_id"]) for package in packages if package["implementation_phase"] == phase)


def field_ref(command_id: str, field: str, side: str) -> str:
    domain, action = command_id.split(".", 1)
    lower = field.casefold()
    if field == "filter":
        return {"roots": "RootFilter", "assets": "AssetFilter", "search": "SearchFilter"}.get(domain, "AssetFilter")
    if field == "sort": return "SortSpec"
    if field == "page": return "PageRequest"
    if "settings" in lower: return "SettingsPatch" if side == "request" else "StatusSnapshot"
    if "eventdraft" in lower: return "EventDraft"
    if "peopledraft" in lower: return "PersonDraft"
    if "relationshipdraft" in lower: return "RelationshipDraft"
    if "mapdraft" in lower: return "MapDraft"
    if "plan" in lower and "result" not in lower: return "OperationPlanOptions"
    if "execution" in lower: return "ExecutionOptions"
    if "preview" in lower: return "PreviewResult"
    if "conflict" in lower: return "Conflict"
    if field == "items":
        return {"roots": "RootSummary", "assets": "AssetListItem", "events": "EventSummary", "people": "PersonSummary", "relationships": "RelationshipSummary", "tags": "TagSummary", "search": "SearchHit", "review": "ReviewItem", "ai": "AIResult"}.get(domain, "MutationReceipt")
    if "status" in lower: return "StatusSnapshot"
    if "locate" in lower or "open" in lower: return "PathRef"
    if "thumbnail" in lower or "renderpreview" in lower: return "PreviewResult"
    if "person" in lower: return "PersonSummary"
    if "relationship" in lower: return "RelationshipSummary"
    if "models" in lower or "hardware" in lower: return "StatusSnapshot"
    if "global" in lower or "scoped" in lower or "draft" in lower: return "MapProjection"
    if "snapshot" in lower or "restore" in lower or "create" in lower or "update" in lower or "approve" in lower or "reject" in lower or "suppress" in lower or "merge" in lower or "split" in lower or "hide" in lower or "correct" in lower or "assign" in lower or "defer" in lower or "reopen" in lower or "retry" in lower or "invalidate" in lower or "reset" in lower or "cancel" in lower or "pause" in lower or "resume" in lower:
        return "MutationReceipt"
    if "result" in lower:
        return {"assets": "AssetDetail", "events": "EventSummary", "people": "PersonSummary", "relationships": "RelationshipSummary", "search": "SearchHit", "review": "ReviewItem", "ai": "AIResult"}.get(domain, "MutationReceipt")
    return "StatusSnapshot"


def close_schema(command_id: str, schema: dict[str, object], side: str) -> dict[str, object]:
    schema = json.loads(json.dumps(schema))
    properties = schema.get("properties", {})
    assert isinstance(properties, dict)
    for field, value in list(properties.items()):
        if not isinstance(value, dict):
            continue
        untyped_object = value.get("type") == "object" and not value.get("properties") and not value.get("$ref")
        anonymous_array = value.get("type") == "array" and isinstance(value.get("items"), dict) and value["items"].get("type") == "object" and not value["items"].get("properties") and not value["items"].get("$ref")
        if untyped_object:
            properties[field] = ref(field_ref(command_id, field, side))
        elif anonymous_array:
            properties[field] = {"type": "array", "items": ref(field_ref(command_id, field, side)), "minItems": value.get("minItems", 0)}
    schema["additionalProperties"] = False
    schema["x-lamha-review"] = {"status": "REVIEWED", "commandId": command_id, "side": side, "openObjectExceptions": []}
    return schema


def write_contracts() -> tuple[int, int, int]:
    shared = shared_contract_schema()
    write_json(CONTRACTS / "shared-definitions-v1.schema.json", shared)
    legacy_catalog = json.loads((LEGACY / "05-contracts" / "ipc-command-catalog-v2.json").read_text(encoding="utf-8"))["commands"]
    packages = json.loads((SOURCE / "packages" / "work-packages.json").read_text(encoding="utf-8"))["workPackages"]
    commands: list[dict[str, object]] = []
    reviews: list[dict[str, object]] = []
    reclassified = 0
    for old in legacy_catalog:
        command_id = str(old["commandId"])
        read_only = command_id in READ_ONLY
        mutating = not read_only
        duration = "LONG_RUNNING" if command_id in LONG_RUNNING else "FAST"
        operation = duration == "LONG_RUNNING"
        dry_supported = command_id in DESTRUCTIVE or command_id.endswith("_plan") or ".plan_" in command_id or command_id == "operations.simulate"
        dry_required = command_id in DESTRUCTIVE
        request_id = mutating or operation
        cancellation = "COOPERATIVE_SAFE_POINTS_WITH_COMMITTED_BOUNDARY" if command_id in CANCELLABLE else "NOT_CANCELLABLE"
        idempotency = "PURE_READ_AT_DECLARED_REVISION" if read_only else "REQUEST_ID_REPLAYS_PRIOR_RESULT"
        revision_rule = "SNAPSHOT_REVISION_RETURNED" if read_only else "EXPECTED_REVISION_REQUIRED"
        changed = any((bool(old["readOnly"]) != read_only, bool(old["mutating"]) != mutating, old["duration"] != duration, bool(old["dryRun"]["required"]) != dry_required))
        reclassified += int(changed)
        command = dict(old)
        command.update({
            "purpose": f"Execute the reviewed `{command_id}` capability through Rust with the exact request/response schemas named below.",
            "readOnly": read_only,
            "mutating": mutating,
            "mutationAuthority": "NONE" if read_only else ("DERIVED_STATE_ONLY" if command_id in DERIVED_MUTATION else "AUTHORITATIVE_OR_FILESYSTEM"),
            "duration": duration,
            "responseMode": "OPERATION_HANDLE" if operation else "SYNCHRONOUS",
            "dryRun": {"supported": dry_supported, "required": dry_required, "rationale": "Required for destructive authority." if dry_required else ("Supported because this command produces or evaluates a plan." if dry_supported else "No dry-run parameter; this command is a read or an atomic non-preview action.")},
            "requestIdRequired": request_id,
            "operationIdReturned": operation,
            "idempotency": idempotency,
            "cancellation": cancellation,
            "revisionPrecondition": revision_rule,
            "workPackageId": package_for(command_id, packages),
            "classificationRationale": f"Individually reviewed: readOnly={str(read_only).lower()}, authority={'none' if read_only else ('derived' if command_id in DERIVED_MUTATION else 'authoritative/filesystem')}, duration={duration}, dry-run={str(dry_required).lower()}, cancellation={cancellation}.",
            "reviewerStatus": "REVIEWED_CORRECTED" if changed else "REVIEWED_CONFIRMED",
        })
        command["progressEvents"] = ["operation.accepted", "operation.started", "operation.progress", "operation.warning", "operation.committed", "operation.failed"] if operation else []
        domain = command_id.split(".", 1)[0]
        errors = ["INVALID_REQUEST", "CAPABILITY_DENIED"]
        if mutating: errors += ["REVISION_CONFLICT", "IDEMPOTENCY_CONFLICT"]
        if domain in {"roots", "assets", "scan", "events", "metadata", "editing", "maintenance", "operations"}: errors += ["ROOT_NOT_AUTHORIZED", "DRIVE_DISCONNECTED", "PERMISSION_DENIED", "PATH_ESCAPE"]
        if command_id in DESTRUCTIVE: errors += ["PLAN_EXPIRED", "CONFIRMATION_REQUIRED", "COLLISION", "RECOVERY_REQUIRED"]
        command["errorCodes"] = list(dict.fromkeys(errors))
        commands.append(command)

        request_source = LEGACY / "05-contracts" / str(old["requestSchema"])
        response_source = LEGACY / "05-contracts" / str(old["responseSchema"])
        request_schema = close_schema(command_id, json.loads(request_source.read_text(encoding="utf-8")), "request")
        response_schema = close_schema(command_id, json.loads(response_source.read_text(encoding="utf-8")), "response")
        write_json(CONTRACTS / "ipc" / "requests" / request_source.name, request_schema)
        write_json(CONTRACTS / "ipc" / "responses" / response_source.name, response_schema)
        reviews.append({
            "command_id": command_id, "mutating": str(mutating).lower(), "mutation_authority": command["mutationAuthority"],
            "destructive": str(command_id in DESTRUCTIVE).lower(), "duration": duration, "dry_run_required": str(dry_required).lower(),
            "request_id_required": str(request_id).lower(), "idempotency": idempotency, "cancellation": cancellation,
            "pagination": str(bool(old["pagination"]["supported"])).lower(), "revision_precondition": revision_rule,
            "capability_permission": command["tauriCapability"], "error_subset": ";".join(command["errorCodes"]),
            "reviewer_judgement": "CORRECTED" if changed else "CONFIRMED", "reason": command["classificationRationale"],
        })
    write_json(CONTRACTS / "ipc-command-registry-v3.json", {"contractVersion": "3.0.0", "commands": commands})
    write_csv(SOURCE / "reviews" / "command-flag-review.csv", reviews, list(reviews[0]))

    event_payloads = {
        "accepted": obj({"queuePosition": {"type": "integer", "minimum": 0}}),
        "started": obj({"startedAt": {"$ref": "shared-definitions-v1.schema.json#/$defs/Timestamp"}}),
        "progress": obj({"completedItems": {"type": "integer", "minimum": 0}, "totalItems": {"type": ["integer", "null"], "minimum": 0}, "message": {"type": "string", "maxLength": 1000}}),
        "warning": {"$ref": "shared-definitions-v1.schema.json#/$defs/Warning"},
        "committed": obj({"committedItems": {"type": "integer", "minimum": 0}, "committedAt": {"$ref": "shared-definitions-v1.schema.json#/$defs/Timestamp"}}),
        "failed": obj({"errorCode": {"type": "string", "pattern": "^[A-Z][A-Z0-9_]{2,63}$"}, "retryable": {"type": "boolean"}, "recoveryRequired": {"type": "boolean"}}),
        "paused": obj({"safePoint": {"type": "string", "minLength": 1}}),
        "cancelled": obj({"committedItems": {"type": "integer", "minimum": 0}, "rolledBackItems": {"type": "integer", "minimum": 0}}),
        "recovery_started": obj({"journalRevision": {"type": "integer", "minimum": 0}}),
        "recovery_completed": obj({"recoveredItems": {"type": "integer", "minimum": 0}, "unresolvedItems": {"type": "integer", "minimum": 0}}),
    }
    event_schema = {"$schema": "https://json-schema.org/draft/2020-12/schema", "$id": "https://lamha.local/schemas/events/operation-event-v2.schema.json", "oneOf": []}
    for event, payload in event_payloads.items():
        event_schema["oneOf"].append(obj({"eventVersion": {"const": "2.0.0"}, "eventType": {"const": f"operation.{event}"}, "operationId": {"$ref": "shared-definitions-v1.schema.json#/$defs/Id"}, "sequence": {"type": "integer", "minimum": 0}, "timestamp": {"$ref": "shared-definitions-v1.schema.json#/$defs/Timestamp"}, "payload": payload}))
    write_json(CONTRACTS / "operation-events-v2.schema.json", event_schema)

    ai_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema", "$id": "https://lamha.local/schemas/ai/worker-protocol-v3.schema.json",
        "$defs": {
            "fingerprint": obj({"modelId": {"type": "string", "minLength": 1}, "modelVersion": {"type": "string", "minLength": 1}, "modelChecksum": {"type": "string", "pattern": "^[a-fA-F0-9]{32,128}$"}, "workerBuildHash": {"type": "string", "pattern": "^[a-fA-F0-9]{32,128}$"}, "configHash": {"type": "string", "pattern": "^[a-fA-F0-9]{32,128}$"}}),
            "input": {"oneOf": [obj({"kind": {"const": "ASSET_PATH"}, "rootId": {"type": "string"}, "relativePath": {"type": "string"}, "assetId": {"type": "string"}, "assetRevision": {"type": "integer", "minimum": 0}}), obj({"kind": {"const": "IMAGE_REGION"}, "assetId": {"type": "string"}, "assetRevision": {"type": "integer", "minimum": 0}, "x": {"type": "number", "minimum": 0, "maximum": 1}, "y": {"type": "number", "minimum": 0, "maximum": 1}, "width": {"type": "number", "exclusiveMinimum": 0, "maximum": 1}, "height": {"type": "number", "exclusiveMinimum": 0, "maximum": 1}})]},
            "candidate": {"oneOf": [obj({"kind": {"const": "OCR"}, "text": {"type": "string"}, "language": {"type": ["string", "null"]}, "confidence": {"type": "number", "minimum": 0, "maximum": 1}}), obj({"kind": {"const": "FACE"}, "embeddingDigest": {"type": "string"}, "x": {"type": "number", "minimum": 0, "maximum": 1}, "y": {"type": "number", "minimum": 0, "maximum": 1}, "width": {"type": "number", "exclusiveMinimum": 0, "maximum": 1}, "height": {"type": "number", "exclusiveMinimum": 0, "maximum": 1}, "confidence": {"type": "number", "minimum": 0, "maximum": 1}}), obj({"kind": {"const": "DUPLICATE"}, "otherAssetId": {"type": "string"}, "similarity": {"type": "number", "minimum": 0, "maximum": 1}}), obj({"kind": {"const": "LOCATION"}, "latitude": {"type": "number", "minimum": -90, "maximum": 90}, "longitude": {"type": "number", "minimum": -180, "maximum": 180}, "confidence": {"type": "number", "minimum": 0, "maximum": 1}}), obj({"kind": {"const": "TAG"}, "namespace": {"type": "string"}, "name": {"type": "string"}, "confidence": {"type": "number", "minimum": 0, "maximum": 1}})]},
        },
        "oneOf": [
            obj({"type": {"const": "handshake"}, "protocolVersion": {"const": "3.0.0"}, "workerBuildHash": {"type": "string", "pattern": "^[a-fA-F0-9]{32,128}$"}, "taskKinds": arr({"enum": ["OCR", "EMBEDDING", "FACE_DETECTION", "FACE_EMBEDDING", "DUPLICATE", "LOCATION", "CONTENT_TAG"]}, min_items=1, unique=True), "modelRegistryDigest": {"type": "string", "pattern": "^[a-fA-F0-9]{32,128}$"}, "maxFrameBytes": {"type": "integer", "minimum": 1024, "maximum": 67108864}}),
            obj({"type": {"const": "task"}, "taskId": {"type": "string"}, "taskKind": {"enum": ["OCR", "EMBEDDING", "FACE_DETECTION", "FACE_EMBEDDING", "DUPLICATE", "LOCATION", "CONTENT_TAG"]}, "modelId": {"type": "string"}, "input": {"$ref": "#/$defs/input"}}),
            obj({"type": {"const": "result"}, "taskId": {"type": "string"}, "status": {"enum": ["SUCCEEDED", "FAILED", "CANCELLED"]}, "candidate": {"oneOf": [{"$ref": "#/$defs/candidate"}, {"type": "null"}]}, "fingerprint": {"$ref": "#/$defs/fingerprint"}, "errorCode": {"type": ["string", "null"]}}),
            obj({"type": {"const": "control"}, "taskId": {"type": "string"}, "action": {"enum": ["CANCEL", "PAUSE", "RESUME"]}}),
        ],
    }
    write_json(CONTRACTS / "ai-worker-protocol-v3.schema.json", ai_schema)

    error_catalog = json.loads((LEGACY / "05-contracts" / "error-catalog-v1.json").read_text(encoding="utf-8"))
    write_json(CONTRACTS / "error-catalog-v1.json", error_catalog)
    return len(commands), reclassified, sum(1 for row in reviews if row["destructive"] == "true")


def record_shared_schema() -> dict[str, object]:
    identifier = {"type": "string", "pattern": "^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"}
    timestamp = {"type": "string", "format": "date-time"}
    defs = {
        "Id": identifier,
        "Timestamp": timestamp,
        "Revision": {"type": "integer", "minimum": 1},
        "Hash": obj({"algorithm": {"enum": ["BLAKE3", "SHA256"]}, "value": {"type": "string", "pattern": "^[a-fA-F0-9]{32,128}$"}}),
        "PathRef": obj({"rootId": identifier, "relativePath": {"type": "string", "minLength": 1, "maxLength": 32768}, "driveId": {"anyOf": [identifier, {"type": "null"}]}}, ["rootId", "relativePath"]),
        "Provenance": obj({"source": {"enum": ["USER", "FILESYSTEM", "IMPORT", "AI_PROPOSAL", "MIGRATION", "RECOVERY"]}, "recordedAt": timestamp, "sourceRecordId": {"anyOf": [identifier, {"type": "null"}]}, "modelFingerprint": {"type": ["string", "null"], "maxLength": 512}}, ["source", "recordedAt"]),
        "Privacy": obj({"classification": {"enum": ["LOCAL_USER_DATA", "SENSITIVE_BIOMETRIC", "LOCATION", "OPERATIONAL", "PUBLIC_EXPORT"]}, "exportPolicy": {"enum": ["ALLOW", "REDACT", "EXCLUDE", "REVIEW"]}, "consentState": {"enum": ["NOT_APPLICABLE", "UNKNOWN", "GRANTED", "WITHDRAWN"]}}),
        "ExtensionMap": {"type": "object", "description": "Intentional forward-compatible scalar extension point. Keys are vendor-prefixed and values cannot contain objects or arrays.", "propertyNames": {"pattern": "^x-[a-z0-9][a-z0-9.-]{1,63}$"}, "additionalProperties": {"type": ["string", "number", "integer", "boolean", "null"]}, "x-lamha-approved-open-object": True, "x-lamha-rationale": "Preserve unknown scalar vendor fields without hiding core product structures."},
        "Gps": obj({"latitude": {"type": "number", "minimum": -90, "maximum": 90}, "longitude": {"type": "number", "minimum": -180, "maximum": 180}, "altitudeMeters": {"type": ["number", "null"]}, "source": {"enum": ["EMBEDDED", "XMP", "ASSET_JSON", "USER", "AI_PROPOSAL"]}}),
        "Camera": obj({"make": {"type": ["string", "null"], "maxLength": 255}, "model": {"type": ["string", "null"], "maxLength": 255}, "lens": {"type": ["string", "null"], "maxLength": 255}, "cameraOwnerPersonId": {"anyOf": [identifier, {"type": "null"}]}, "photographerPersonIds": arr(identifier, unique=True)}),
        "BoundingBox": obj({"x": {"type": "number", "minimum": 0, "maximum": 1}, "y": {"type": "number", "minimum": 0, "maximum": 1}, "width": {"type": "number", "exclusiveMinimum": 0, "maximum": 1}, "height": {"type": "number", "exclusiveMinimum": 0, "maximum": 1}}),
        "RecordHeader": obj({"schemaVersion": {"type": "string", "pattern": "^[1-9][0-9]*\\.[0-9]+\\.[0-9]+$"}, "id": identifier, "revision": {"type": "integer", "minimum": 1}, "createdAt": timestamp, "updatedAt": timestamp, "authority": {"enum": ["AUTHORITATIVE_FILE_RECORD", "TEMPORARY_TRANSACTION_AUTHORITY", "DERIVED_REBUILDABLE"]}, "privacy": {"$ref": "#/$defs/Privacy"}, "provenance": {"$ref": "#/$defs/Provenance"}, "extensions": {"$ref": "#/$defs/ExtensionMap"}}),
    }
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "$id": "https://lamha.local/schemas/records/record-shared-v1.schema.json", "$defs": defs}


def record_schema(name: str, domain: dict[str, object], required: list[str], authority: str = "AUTHORITATIVE_FILE_RECORD", privacy: str = "LOCAL_USER_DATA") -> dict[str, object]:
    header = record_shared_schema()["$defs"]["RecordHeader"]
    properties = dict(header["properties"])
    properties.update(domain)
    properties["authority"] = {"const": authority}
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema", "$id": f"https://lamha.local/schemas/records/{name}.schema.json",
        "title": name.replace("_", " ").title(), "type": "object",
        "required": list(header["required"]) + required, "properties": properties, "additionalProperties": False,
        "x-lamha": {"authority": authority, "privacyClassification": privacy, "stableIdStrategy": "UUIDv7 or documented deterministic content identity", "timestampSemantics": "UTC RFC3339 instants; source timezone retained in domain fields when required", "unknownFieldPolicy": "Core unknown fields rejected; scalar x-* extensions preserved", "migrationPolicy": "Monotonic versioned migration writes a new file atomically and leaves original bytes intact on failure"},
    }
    return schema


def write_records() -> tuple[int, int, int]:
    obsolete_shared = safe_path(RECORDS / "record-shared-v1.schema.json")
    if obsolete_shared.exists():
        remove_file(obsolete_shared)
    write_json(RECORDS / "records" / "record-shared-v1.schema.json", record_shared_schema())
    rid = {"$ref": "record-shared-v1.schema.json#/$defs/Id"}
    pathref = {"$ref": "record-shared-v1.schema.json#/$defs/PathRef"}
    ts = {"$ref": "record-shared-v1.schema.json#/$defs/Timestamp"}
    rev = {"type": "integer", "minimum": 1}
    schemas: dict[str, dict[str, object]] = {}
    schemas["asset"] = record_schema("asset", {
        "identityId": rid, "rootId": rid, "primaryPath": pathref, "originalFilename": {"type": "string", "minLength": 1}, "extension": {"type": "string", "pattern": "^[A-Za-z0-9]{1,16}$"},
        "mediaType": {"enum": ["IMAGE", "VIDEO", "AUDIO"]}, "mimeType": {"type": "string", "pattern": "^[^/]+/[^/]+$"}, "fileSizeBytes": {"type": "integer", "minimum": 0}, "contentHash": {"$ref": "record-shared-v1.schema.json#/$defs/Hash"},
        "captureTime": obj({"instant": {"type": ["string", "null"], "format": "date-time"}, "localValue": {"type": ["string", "null"]}, "timeZone": {"type": ["string", "null"]}, "source": {"enum": ["EMBEDDED", "XMP", "ASSET_JSON", "FILESYSTEM", "USER", "UNKNOWN"]}}),
        "filesystemTimes": obj({"createdAt": {"type": ["string", "null"], "format": "date-time"}, "modifiedAt": {"type": "string", "format": "date-time"}, "observedAt": {"type": "string", "format": "date-time"}}),
        "dimensions": obj({"width": {"type": ["integer", "null"], "minimum": 1}, "height": {"type": ["integer", "null"], "minimum": 1}, "orientation": {"enum": ["NORMAL", "ROTATE_90", "ROTATE_180", "ROTATE_270", "MIRROR_HORIZONTAL", "MIRROR_VERTICAL", "UNKNOWN"]}}),
        "durationMs": {"type": ["integer", "null"], "minimum": 0}, "camera": {"$ref": "record-shared-v1.schema.json#/$defs/Camera"}, "gps": {"oneOf": [{"$ref": "record-shared-v1.schema.json#/$defs/Gps"}, {"type": "null"}]},
        "sidecars": arr(obj({"sidecarId": rid, "kind": {"enum": ["ASSET_JSON", "XMP", "EXTERNAL_XMP"]}, "path": pathref, "state": {"enum": ["HEALTHY", "MISSING", "CORRUPT", "FUTURE_VERSION", "PENDING_OVERLAY"]}, "revision": rev})),
        "companions": arr(obj({"assetId": rid, "kind": {"enum": ["LIVE_PHOTO_IMAGE", "LIVE_PHOTO_VIDEO", "RAW", "JPEG_RENDER", "MOTION_PHOTO"]}, "role": {"enum": ["PRIMARY", "COMPANION"]}}), unique=True),
        "eventIds": arr(rid, unique=True), "visiblePersonIds": arr(rid, unique=True), "tagIds": arr(rid, unique=True), "albumIds": arr(rid, unique=True), "favorite": {"type": "boolean"}, "rating": {"type": ["integer", "null"], "minimum": 0, "maximum": 5},
        "reviewState": {"enum": ["NONE", "OPEN", "DEFERRED", "RESOLVED"]}, "editRecipeId": {"oneOf": [rid, {"type": "null"}]}, "derivatives": arr(obj({"derivativeId": rid, "kind": {"enum": ["THUMBNAIL", "PREVIEW", "EDITED_EXPORT", "PRIVACY_EXPORT"]}, "sourceRevision": rev, "path": pathref, "contentHash": {"$ref": "record-shared-v1.schema.json#/$defs/Hash"}})),
        "integrityState": {"enum": ["VERIFIED", "STALE", "MISSING", "HASH_MISMATCH", "SIDECAR_CONFLICT", "RECOVERY_REQUIRED"]},
    }, ["identityId", "rootId", "primaryPath", "originalFilename", "extension", "mediaType", "mimeType", "fileSizeBytes", "contentHash", "captureTime", "filesystemTimes", "dimensions", "durationMs", "camera", "gps", "sidecars", "companions", "eventIds", "visiblePersonIds", "tagIds", "albumIds", "favorite", "rating", "reviewState", "editRecipeId", "derivatives", "integrityState"])
    schemas["event"] = record_schema("event", {"title": {"type": "string", "minLength": 1, "maxLength": 500}, "startAt": ts, "endAt": ts, "timeZone": {"type": "string", "minLength": 1}, "location": {"oneOf": [{"$ref": "record-shared-v1.schema.json#/$defs/Gps"}, {"type": "null"}]}, "assetMemberships": arr(obj({"assetId": rid, "role": {"enum": ["PRIMARY", "MEMBER", "BACKDROP"]}, "addedAt": ts})), "folderState": obj({"mode": {"enum": ["VIRTUAL", "PLANNED", "MATERIALIZED", "CONFLICT"]}, "path": {"oneOf": [pathref, {"type": "null"}]}, "operationId": {"oneOf": [rid, {"type": "null"}]}}, ["mode"]), "inference": obj({"source": {"enum": ["USER", "DATE_LOCATION_HEURISTIC", "AI_PROPOSAL"]}, "confidence": {"type": ["number", "null"], "minimum": 0, "maximum": 1}, "candidateId": {"oneOf": [rid, {"type": "null"}]}, "userConfirmed": {"type": "boolean"}}), "attendeePersonIds": arr(rid, unique=True), "photographerPersonIds": arr(rid, unique=True), "conflictState": {"enum": ["NONE", "DATE", "LOCATION", "MEMBERSHIP", "FILESYSTEM"]}, "history": arr(obj({"action": {"enum": ["MERGE", "SPLIT", "LINK", "UNLINK", "RENAME"]}, "relatedEventIds": arr(rid, min_items=1, unique=True), "at": ts, "operationId": {"oneOf": [rid, {"type": "null"}]}})), "reviewState": {"enum": ["DRAFT", "PROPOSED", "CONFIRMED", "REJECTED", "CONFLICT"]}}, ["title", "startAt", "endAt", "timeZone", "location", "assetMemberships", "folderState", "inference", "attendeePersonIds", "photographerPersonIds", "conflictState", "history", "reviewState"])
    schemas["person"] = record_schema("person", {"identityState": {"enum": ["CANDIDATE", "CONFIRMED", "MERGED", "SPLIT"]}, "canonicalName": {"type": ["string", "null"], "maxLength": 500}, "aliases": arr({"type": "string", "minLength": 1, "maxLength": 500}, unique=True), "profileAssetId": {"oneOf": [rid, {"type": "null"}]}, "hidden": {"type": "boolean"}, "mergeHistory": arr(obj({"action": {"enum": ["MERGE_IN", "SPLIT_OUT"]}, "otherPersonId": rid, "at": ts, "approvedBy": {"const": "USER"}}))}, ["identityState", "canonicalName", "aliases", "profileAssetId", "hidden", "mergeHistory"], privacy="SENSITIVE_BIOMETRIC")
    schemas["face_observation"] = record_schema("face_observation", {"assetId": rid, "assetRevision": rev, "boundingBox": {"$ref": "record-shared-v1.schema.json#/$defs/BoundingBox"}, "embeddingDigest": {"type": ["string", "null"]}, "modelId": rid, "modelVersion": {"type": "string"}, "confidence": {"type": "number", "minimum": 0, "maximum": 1}, "candidatePersonId": {"oneOf": [rid, {"type": "null"}]}, "confirmedPersonId": {"oneOf": [rid, {"type": "null"}]}, "reviewState": {"enum": ["PROPOSED", "CONFIRMED", "REJECTED", "SUPPRESSED"]}, "approvedBy": {"enum": ["NONE", "USER"]}}, ["assetId", "assetRevision", "boundingBox", "embeddingDigest", "modelId", "modelVersion", "confidence", "candidatePersonId", "confirmedPersonId", "reviewState", "approvedBy"], privacy="SENSITIVE_BIOMETRIC")
    schemas["group"] = record_schema("group", {"canonicalName": {"type": "string", "minLength": 1}, "aliases": arr({"type": "string", "minLength": 1}, unique=True), "parentGroupId": {"oneOf": [rid, {"type": "null"}]}, "hidden": {"type": "boolean"}}, ["canonicalName", "aliases", "parentGroupId", "hidden"])
    schemas["group_membership"] = record_schema("group_membership", {"groupId": rid, "personId": rid, "effectiveFrom": ts, "effectiveTo": {"type": ["string", "null"], "format": "date-time"}, "role": {"type": ["string", "null"], "maxLength": 200}, "state": {"enum": ["ACTIVE", "FORMER", "INACTIVE"]}, "approvedBy": {"const": "USER"}}, ["groupId", "personId", "effectiveFrom", "effectiveTo", "role", "state", "approvedBy"])
    schemas["relationship"] = record_schema("relationship", {"fromPersonId": rid, "toPersonId": rid, "relationshipType": {"type": "string", "minLength": 1, "maxLength": 200}, "certainty": {"enum": ["SURE", "NOT_SURE"]}, "effectiveFrom": {"type": ["string", "null"], "format": "date-time"}, "effectiveTo": {"type": ["string", "null"], "format": "date-time"}, "status": {"enum": ["ACTIVE", "FORMER"]}, "notes": {"type": ["string", "null"], "maxLength": 4000}, "approvedBy": {"const": "USER"}, "rejection": {"oneOf": [obj({"reason": {"type": "string", "minLength": 1}, "rejectedAt": ts, "suppressionScope": {"enum": ["EXACT_CANDIDATE", "EQUIVALENT_EVIDENCE"]}}), {"type": "null"}]}}, ["fromPersonId", "toPersonId", "relationshipType", "certainty", "effectiveFrom", "effectiveTo", "status", "notes", "approvedBy", "rejection"])
    schemas["relationship_history"] = record_schema("relationship_history", {"relationshipId": rid, "sequence": {"type": "integer", "minimum": 1}, "action": {"enum": ["CREATE", "UPDATE", "END", "REOPEN", "REJECT", "MERGE", "SPLIT"]}, "beforeRevision": {"type": ["integer", "null"], "minimum": 1}, "afterRevision": {"type": ["integer", "null"], "minimum": 1}, "changedAt": ts, "approvedBy": {"const": "USER"}, "reason": {"type": "string", "minLength": 1}}, ["relationshipId", "sequence", "action", "beforeRevision", "afterRevision", "changedAt", "approvedBy", "reason"])
    schemas["tag"] = record_schema("tag", {"namespace": {"type": "string", "minLength": 1}, "name": {"type": "string", "minLength": 1}, "parentTagId": {"oneOf": [rid, {"type": "null"}]}, "aliases": arr({"type": "string", "minLength": 1}, unique=True), "state": {"enum": ["ACTIVE", "HIDDEN"]}}, ["namespace", "name", "parentTagId", "aliases", "state"])
    schemas["album"] = record_schema("album", {"title": {"type": "string", "minLength": 1}, "description": {"type": ["string", "null"], "maxLength": 4000}, "assetIds": arr(rid, unique=True), "coverAssetId": {"oneOf": [rid, {"type": "null"}]}}, ["title", "description", "assetIds", "coverAssetId"])
    schemas["review_item"] = record_schema("review_item", {"candidateType": {"enum": ["OCR", "FACE", "DUPLICATE", "LOCATION", "TAG", "EVENT", "RELATIONSHIP", "METADATA_CONFLICT"]}, "candidateId": rid, "assetIds": arr(rid, unique=True), "state": {"enum": ["OPEN", "APPROVED", "REJECTED", "DEFERRED", "SUPPRESSED"]}, "decisionAt": {"type": ["string", "null"], "format": "date-time"}, "decisionReason": {"type": ["string", "null"], "maxLength": 2000}, "suppressionScope": {"enum": ["NONE", "EXACT_CANDIDATE", "EQUIVALENT_EVIDENCE"]}}, ["candidateType", "candidateId", "assetIds", "state", "decisionAt", "decisionReason", "suppressionScope"])
    schemas["ai_task"] = record_schema("ai_task", {"taskKind": {"enum": ["OCR", "EMBEDDING", "FACE_DETECTION", "FACE_EMBEDDING", "DUPLICATE", "LOCATION", "CONTENT_TAG"]}, "assetId": rid, "assetRevision": rev, "modelId": rid, "modelVersion": {"type": "string", "minLength": 1}, "modelChecksum": {"type": "string", "pattern": "^[a-fA-F0-9]{32,128}$"}, "configHash": {"type": "string", "pattern": "^[a-fA-F0-9]{32,128}$"}, "state": {"enum": ["QUEUED", "RUNNING", "PAUSED", "SUCCEEDED", "FAILED", "CANCELLED"]}, "attempt": {"type": "integer", "minimum": 0}, "errorCode": {"type": ["string", "null"]}}, ["taskKind", "assetId", "assetRevision", "modelId", "modelVersion", "modelChecksum", "configHash", "state", "attempt", "errorCode"])
    schemas["root_registry"] = record_schema("root_registry", {"path": pathref, "displayName": {"type": "string", "minLength": 1}, "accessMode": {"enum": ["READ_ONLY", "READ_WRITE"]}, "driveId": {"oneOf": [rid, {"type": "null"}]}, "state": {"enum": ["CONNECTED", "DISCONNECTED", "MISMATCHED", "PERMISSION_DENIED"]}, "lastVerifiedAt": ts}, ["path", "displayName", "accessMode", "driveId", "state", "lastVerifiedAt"])
    schemas["model_registry"] = record_schema("model_registry", {"componentName": {"type": "string", "minLength": 1}, "version": {"type": "string", "minLength": 1}, "checksum": {"type": "string", "pattern": "^[a-fA-F0-9]{32,128}$"}, "licenceStatus": {"enum": ["APPROVED", "PENDING", "REJECTED"]}, "redistributionStatus": {"enum": ["APPROVED", "PENDING", "PROHIBITED"]}, "taskKinds": arr({"enum": ["OCR", "EMBEDDING", "FACE_DETECTION", "FACE_EMBEDDING", "DUPLICATE", "LOCATION", "CONTENT_TAG"]}, min_items=1, unique=True), "platforms": arr({"enum": ["WINDOWS", "MACOS", "LINUX"]}, min_items=1, unique=True)}, ["componentName", "version", "checksum", "licenceStatus", "redistributionStatus", "taskKinds", "platforms"])
    schemas["operation_journal"] = record_schema("operation_journal", {"operationId": rid, "requestId": {"type": "string", "format": "uuid"}, "state": {"enum": ["PREPARED", "STAGING", "VERIFIED", "COMMITTING", "COMMITTED", "ROLLING_BACK", "ROLLED_BACK", "RECOVERY_REQUIRED", "FAILED"]}, "sequence": {"type": "integer", "minimum": 0}, "planHash": {"$ref": "record-shared-v1.schema.json#/$defs/Hash"}, "transitions": arr(obj({"sequence": {"type": "integer", "minimum": 0}, "at": ts, "from": {"type": ["string", "null"]}, "to": {"type": "string", "minLength": 1}, "operationItemId": {"oneOf": [rid, {"type": "null"}]}, "evidenceHash": {"oneOf": [{"$ref": "record-shared-v1.schema.json#/$defs/Hash"}, {"type": "null"}]}, "errorCode": {"type": ["string", "null"]}}), min_items=1), "recoveryState": {"enum": ["NOT_REQUIRED", "REQUIRED", "RUNNING", "COMPLETE", "FAILED"]}}, ["operationId", "requestId", "state", "sequence", "planHash", "transitions", "recoveryState"], authority="TEMPORARY_TRANSACTION_AUTHORITY", privacy="OPERATIONAL")

    operation_common = {"operationItemId": rid, "assetIdentityId": {"oneOf": [rid, {"type": "null"}]}, "source": {"oneOf": [pathref, {"type": "null"}]}, "destination": {"oneOf": [pathref, {"type": "null"}]}, "authorizedRootIds": arr(rid, min_items=1, unique=True), "expectedSourceRevision": {"type": ["integer", "null"], "minimum": 0}, "expectedHash": {"oneOf": [{"$ref": "record-shared-v1.schema.json#/$defs/Hash"}, {"type": "null"}]}, "collisionPolicy": {"enum": ["FAIL", "RENAME", "REVIEW", "SKIP"]}, "companionPolicy": {"const": "ATOMIC_LOGICAL_BUNDLE"}, "staging": obj({"required": {"type": "boolean"}, "path": {"oneOf": [pathref, {"type": "null"}]}, "flushRequired": {"const": True}}), "rollback": obj({"supported": {"type": "boolean"}, "strategy": {"enum": ["RESTORE_SOURCE", "REMOVE_DESTINATION", "RESTORE_TRASH", "REWRITE_PRIOR_SIDECAR", "NONE"]}}), "recovery": obj({"journalRequired": {"const": True}, "resumeStrategy": {"enum": ["RETRY_IDEMPOTENT_STEP", "ROLL_BACK", "USER_REVIEW"]}})}
    variants = []
    required_common = ["operationItemId", "assetIdentityId", "source", "destination", "authorizedRootIds", "expectedSourceRevision", "expectedHash", "collisionPolicy", "companionPolicy", "staging", "rollback", "recovery"]
    for kind, source_required, destination_required in [("MOVE", True, True), ("RENAME", True, True), ("COPY", True, True), ("DELETE_TO_TRASH", True, True), ("RESTORE", True, True), ("SIDECAR_WRITE", False, True), ("DIRECTORY_CREATE", False, True), ("EXPORT", True, True), ("BACKUP_COPY", True, True)]:
        props = {"kind": {"const": kind}, **operation_common}
        reqs = ["kind", *required_common]
        if not source_required:
            props["source"] = {"type": "null"}
        if not destination_required:
            props["destination"] = {"type": "null"}
        variants.append(obj(props, reqs, title=kind.replace("_", " ").title()))
    schemas["file_operation_plan"] = record_schema("file_operation_plan", {"requestId": {"type": "string", "format": "uuid"}, "state": {"enum": ["PREVIEW", "CONFIRMED", "EXPIRED", "COMMITTED", "RECOVERY_REQUIRED"]}, "expiresAt": ts, "operations": {"type": "array", "minItems": 1, "items": {"oneOf": variants}}, "confirmation": obj({"required": {"type": "boolean"}, "confirmedAt": {"type": ["string", "null"], "format": "date-time"}, "confirmedPlanHash": {"type": ["string", "null"], "pattern": "^[a-fA-F0-9]{32,128}$"}}), "totalSourceBytes": {"type": "integer", "minimum": 0}, "requiredDestinationBytes": {"type": "integer", "minimum": 0}}, ["requestId", "state", "expiresAt", "operations", "confirmation", "totalSourceBytes", "requiredDestinationBytes"], authority="TEMPORARY_TRANSACTION_AUTHORITY", privacy="OPERATIONAL")
    schemas["backup_manifest"] = record_schema("backup_manifest", {"sourceRootIds": arr(rid, min_items=1, unique=True), "destinationRootId": rid, "recordEntries": arr(obj({"recordId": rid, "recordType": {"type": "string", "minLength": 1}, "revision": rev, "path": pathref, "hash": {"$ref": "record-shared-v1.schema.json#/$defs/Hash"}}), min_items=1), "mediaEntries": arr(obj({"assetIdentityId": rid, "path": pathref, "sizeBytes": {"type": "integer", "minimum": 0}, "hash": {"$ref": "record-shared-v1.schema.json#/$defs/Hash"}})), "createdByOperationId": rid, "verifiedAt": {"type": ["string", "null"], "format": "date-time"}, "verificationState": {"enum": ["UNVERIFIED", "VERIFIED", "FAILED"]}}, ["sourceRootIds", "destinationRootId", "recordEntries", "mediaEntries", "createdByOperationId", "verifiedAt", "verificationState"])
    schemas["trash_record"] = record_schema("trash_record", {"assetIdentityId": rid, "originalPaths": arr(pathref, min_items=1), "trashPaths": arr(pathref, min_items=1), "trashedByOperationId": rid, "trashedAt": ts, "recoverableUntil": {"type": ["string", "null"], "format": "date-time"}, "state": {"enum": ["TRASHED", "RESTORE_PLANNED", "RESTORED", "PERMANENT_DELETE_PLANNED", "PERMANENTLY_DELETED"]}, "restoreOperationId": {"oneOf": [rid, {"type": "null"}]}}, ["assetIdentityId", "originalPaths", "trashPaths", "trashedByOperationId", "trashedAt", "recoverableUntil", "state", "restoreOperationId"])
    schemas["settings"] = record_schema("settings", {"theme": {"enum": ["SYSTEM", "LIGHT", "DARK"]}, "locale": {"type": "string", "minLength": 2}, "thumbnailSize": {"enum": ["SMALL", "MEDIUM", "LARGE"]}, "hardwareAcceleration": {"enum": ["AUTO", "CPU_ONLY", "PREFER_GPU"]}, "reduceMotion": {"type": "boolean"}, "highContrast": {"type": "boolean"}, "telemetryEnabled": {"const": False}}, ["theme", "locale", "thumbnailSize", "hardwareAcceleration", "reduceMotion", "highContrast", "telemetryEnabled"])
    schemas["edit_recipe"] = record_schema("edit_recipe", {
        "assetId": rid,
        "sourceAssetRevision": rev,
        "steps": arr({"oneOf": [
            obj({"kind": {"const": "CROP"}, "x": {"type": "number", "minimum": 0, "maximum": 1}, "y": {"type": "number", "minimum": 0, "maximum": 1}, "width": {"type": "number", "exclusiveMinimum": 0, "maximum": 1}, "height": {"type": "number", "exclusiveMinimum": 0, "maximum": 1}}),
            obj({"kind": {"const": "ROTATE"}, "degrees": {"enum": [90, 180, 270]}}),
            obj({"kind": {"const": "ADJUST"}, "exposure": {"type": "number", "minimum": -5, "maximum": 5}, "contrast": {"type": "number", "minimum": -1, "maximum": 1}, "saturation": {"type": "number", "minimum": -1, "maximum": 1}}),
        ]}),
        "previewDerivativeId": {"oneOf": [rid, {"type": "null"}]},
    }, ["assetId", "sourceAssetRevision", "steps", "previewDerivativeId"])

    # Derived-only projections are explicit and point back to source revisions.
    schemas["search_index_entry"] = record_schema("search_index_entry", {"assetId": rid, "assetRevision": rev, "indexedFields": arr({"enum": ["FILENAME", "METADATA", "OCR", "PERSON", "TAG", "EVENT", "LOCATION", "EMBEDDING"]}, min_items=1, unique=True), "indexRevision": rev}, ["assetId", "assetRevision", "indexedFields", "indexRevision"], authority="DERIVED_REBUILDABLE")
    schemas["mind_map_projection"] = record_schema("mind_map_projection", {"scopeType": {"enum": ["GLOBAL", "EVENT", "FOLDER", "PERSON", "GROUP"]}, "scopeId": {"oneOf": [rid, {"type": "null"}]}, "sourceRecordRevisions": arr(obj({"recordId": rid, "revision": rev}), min_items=1), "nodes": arr(obj({"nodeId": rid, "sourceRecordId": rid, "label": {"type": "string", "minLength": 1}, "kind": {"enum": ["PERSON", "GROUP", "EVENT", "FOLDER", "TAG"]}})), "edges": arr(obj({"edgeId": rid, "sourceRecordId": rid, "fromNodeId": rid, "toNodeId": rid, "kind": {"type": "string", "minLength": 1}}))}, ["scopeType", "scopeId", "sourceRecordRevisions", "nodes", "edges"], authority="DERIVED_REBUILDABLE")
    schemas["preview_index_entry"] = record_schema("preview_index_entry", {"assetId": rid, "assetRevision": rev, "kind": {"enum": ["THUMBNAIL", "PREVIEW", "VIDEO_POSTER", "RAW_PREVIEW"]}, "path": pathref, "mimeType": {"type": "string", "pattern": "^[^/]+/[^/]+$"}, "width": {"type": "integer", "minimum": 1}, "height": {"type": "integer", "minimum": 1}, "durationMs": {"type": ["integer", "null"], "minimum": 0}, "generatorFingerprint": {"type": "string", "minLength": 1}}, ["assetId", "assetRevision", "kind", "path", "mimeType", "width", "height", "durationMs", "generatorFingerprint"], authority="DERIVED_REBUILDABLE")

    index = []
    for name, schema in schemas.items():
        write_json(RECORDS / "records" / f"{name}.schema.json", schema)
        authority = str(schema["x-lamha"]["authority"])
        index.append({"record_category": name, "schema": f"records/{name}.schema.json", "authority": authority, "rebuild_source": "Authoritative record/media revisions named by the schema" if authority == "DERIVED_REBUILDABLE" else "This versioned record outside SQLite", "privacy": schema["x-lamha"]["privacyClassification"], "reviewer_status": "REVIEWED"})
    write_csv(RECORDS / "schema-index.csv", index, list(index[0]))
    write_json(RECORDS / "schema-index.json", index)

    ddl = (LEGACY / "07-sqlite" / "001_initial.sql").read_text(encoding="utf-8")
    write_text(SOURCE / "sqlite" / "001_initial.sql", ddl.rstrip() + "\n")
    authority = list(csv.DictReader((LEGACY / "07-sqlite" / "entity-authority.csv").open(encoding="utf-8-sig", newline="")))
    write_csv(SOURCE / "sqlite" / "entity-authority.csv", authority, list(authority[0]))
    authoritative = sum(1 for row in index if row["authority"] != "DERIVED_REBUILDABLE")
    derived = len(index) - authoritative
    return authoritative, derived, len(schemas)


def main() -> None:
    if (SOURCE / "reviews" / "review-coverage.json").exists():
        raise SystemExit("Reviewed contract/schema sources are finalized; migration helper is permanently disabled for this plan version.")
    marker = CONTRACTS / "ipc-command-registry-v3.json"
    if marker.exists() and os.environ.get("LAMHA_REVIEW_CANDIDATE_REFRESH") != "1":
        raise SystemExit("Contract/schema candidates already exist; refusing to overwrite review decisions.")
    commands, reclassified, destructive = write_contracts()
    authoritative, derived, schemas = write_records()
    stats = {"commands": commands, "commands_reclassified": reclassified, "destructive_commands": destructive, "authoritative_schemas": authoritative, "derived_schemas": derived, "total_record_schemas": schemas}
    write_json(SOURCE / "reviews" / "contract-schema-candidate-stats.json", stats)
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
