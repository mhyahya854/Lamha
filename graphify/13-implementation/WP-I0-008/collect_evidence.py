#!/usr/bin/env python3
"""Classify every missing prerequisite observed by completed I0 inspection.

The collector is deliberately local-only. It reads committed WP-I0-005 and
WP-I0-007 evidence, verifies the WP-I0-001 Codebase baseline before and after
classification, and writes only the WP-I0-008 evidence directory.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import re
import shutil
import sys
import tempfile
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PACKAGE_ID = "WP-I0-008"
REQUIREMENT_ID = "CAN-MISSION-I0-008"
MAX_JSON_BYTES = 8 * 1024 * 1024
MAX_JSON_DEPTH = 128
MAX_INTEGER_DIGITS = 256
EXPECTED_TOOLCHAIN_SHA256 = "ada9fdcea124b09f4278743cf593a39e5a7821d00ca9c1fe97d0f57c066005fe"
EXPECTED_BASELINE_SHA256 = "a65e6729cb00715b32949793a8c7e1209ef91553c8a0d2fa87c0cb117c100261"
EXPECTED_TOOLCHAIN_SEMANTIC_SHA256 = "59c7b5997b332772f16f37f512cbda1ad29ca2b2dddf3501b05ae479a1c06d43"
EXPECTED_BASELINE_SEMANTIC_SHA256 = "958ed8de4d3d3d588a0305d1fb0e40d99381998ab2ecf4ab1ba0e12cece7b764"
EXPECTED_TOOLCHAIN_REVIEW_COUNT = 236
EXPECTED_TOOLCHAIN_MANIFEST_COUNT = 189
EXPECTED_TOOLCHAIN_DECLARATION_COUNT = 744
EXPECTED_BASELINE_ATTEMPT_COUNT = 51
TOOLCHAIN_TOP_LEVEL_FIELDS = {
    "categories", "counts", "gitSubmodules", "host", "hostToolProbes",
    "independentManifestOracle", "manifestRecords", "mixedVersionFindingsFromPrerequisite",
    "objective", "packageId", "repositoryAmbiguities", "reviewRequired", "status",
    "unmappedDeclaredTools", "versionDeclarations",
}
BASELINE_TOP_LEVEL_FIELDS = {
    "attemptCounts", "attempts", "authorization", "cleanup", "collectionWindowUtc",
    "externalOutputInventoryBeforeCleanup", "failures", "negativeFixtures", "packageId",
    "preservation", "recoveredIncidents", "requirementId", "runId", "scannerFixture",
    "status", "surfaceOracle",
}
TOOLCHAIN_REVIEW_FIELDS = {
    "applicableCategories", "categories", "category", "hostVersion", "item", "observedValue",
    "reason", "repositoryVersions", "source", "sources", "status", "url", "versions",
}
BASELINE_ATTEMPT_FIELDS = {
    "blocker", "declaredCommand", "durationMs", "executed", "exitCode", "id",
    "isolatedCommand", "kind", "output", "sourceCommand", "sourcePath", "status",
    "surface", "workingDirectory",
}
ALLOWED_CATEGORIES = {
    "FIXTURE",
    "GENERATED_ARTIFACT",
    "DEPENDENCY",
    "CREDENTIAL",
    "ENVIRONMENT_PREREQUISITE",
}
ALLOWED_STATUSES = {"REVIEW_REQUIRED", "BLOCKED"}
MISSING_TOOLCHAIN_REASONS = {
    "HOST_PROBE_UNMAPPED",
    "HOST_TOOL_UNAVAILABLE",
    "NO_DISCOVERABLE_REPOSITORY_VERSION",
    "NO_REPOSITORY_MANIFEST",
    "REFERENCED_MANIFEST_UNAVAILABLE",
    "SUBMODULE_REVISION_UNAVAILABLE",
    "VERSION_REFERENCE_UNRESOLVED",
}
NON_MISSING_TOOLCHAIN_REASONS = {
    "AMBIGUOUS_REPOSITORY_VERSION",
    "HOST_REPOSITORY_VERSION_DIFFERENCE",
}
BLOCKER_EXPANSIONS = {
    "PROJECT_DEPENDENCIES_UNAVAILABLE": (
        ("DEPENDENCY", "Codebase/node_modules", "Required workspace dependencies are absent."),
    ),
    "CONTAINER_RUNTIME_AND_PROJECT_DEPENDENCIES_UNAVAILABLE": (
        ("ENVIRONMENT_PREREQUISITE", "host-tool:docker", "A usable container runtime is unavailable."),
        ("DEPENDENCY", "Codebase/node_modules", "Required workspace dependencies are absent."),
    ),
    "CONTAINER_RUNTIME_AND_VOLUME_WRITES_UNAVAILABLE": (
        ("ENVIRONMENT_PREREQUISITE", "host-tool:docker", "A usable container runtime is unavailable."),
        ("ENVIRONMENT_PREREQUISITE", "container-volume-write-isolation", "Safe external volume-write isolation is unavailable."),
    ),
    "CONTAINER_RUNTIME_VOLUME_AND_NETWORK_UNAVAILABLE": (
        ("ENVIRONMENT_PREREQUISITE", "host-tool:docker", "A usable container runtime is unavailable."),
        ("ENVIRONMENT_PREREQUISITE", "container-volume-write-isolation", "Safe external volume-write isolation is unavailable."),
        ("ENVIRONMENT_PREREQUISITE", "network-connectivity", "Network-dependent resolution is unavailable in the authorized boundary."),
    ),
    "DECLARED_BUILD_OUTPUT_REDIRECTION_UNPROVEN": (
        ("ENVIRONMENT_PREREQUISITE", "build-output-redirection-proof", "Declared build outputs cannot yet be proven external to Codebase."),
    ),
    "TEST_SIDE_EFFECT_REDIRECTION_UNPROVEN": (
        ("ENVIRONMENT_PREREQUISITE", "test-side-effect-redirection-proof", "Test side effects cannot yet be proven external to Codebase."),
    ),
    "FLUTTER_OUTPUT_REDIRECTION_UNPROVEN": (
        ("ENVIRONMENT_PREREQUISITE", "flutter-output-redirection-proof", "Flutter build/test side effects cannot yet be proven external to Codebase."),
    ),
    "GENERATED_SOURCE_REDIRECTION_UNPROVEN": (
        ("ENVIRONMENT_PREREQUISITE", "generated-source-redirection-proof", "Generated source cannot yet be proven external to Codebase."),
    ),
    "PLATFORM_AND_DERIVED_DATA_REDIRECTION_UNAVAILABLE": (
        ("ENVIRONMENT_PREREQUISITE", "host-platform:xcode", "The required Apple build platform and safe derived-data redirection are unavailable."),
    ),
}


class EvidenceError(Exception):
    """Typed invalid-input or consistency failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def semantic_sha256(value: Any) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return sha256_bytes(canonical)


def reject_constant(value: str) -> None:
    raise EvidenceError("JSON_NONFINITE_NUMBER", f"non-finite JSON number: {value}")


def parse_integer(value: str) -> int:
    digits = value.lstrip("-")
    if len(digits) > MAX_INTEGER_DIGITS:
        raise EvidenceError("JSON_INTEGER_TOO_LARGE", "JSON integer exceeds the configured digit limit")
    return int(value)


def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise EvidenceError("JSON_DUPLICATE_KEY", f"duplicate JSON key: {key}")
        result[key] = value
    return result


def lexical_json_depth(text: str) -> int:
    depth = maximum = 0
    in_string = escaped = False
    for char in text:
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char in "[{":
            depth += 1
            maximum = max(maximum, depth)
        elif char in "]}":
            depth -= 1
            if depth < 0:
                raise EvidenceError("JSON_MALFORMED", "unbalanced JSON delimiters")
    if in_string or depth != 0:
        raise EvidenceError("JSON_MALFORMED", "unterminated JSON value")
    return maximum


def validate_json_scalars(value: Any, location: str = "$") -> None:
    if value is None or isinstance(value, (bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise EvidenceError("JSON_NONFINITE_NUMBER", f"{location} is non-finite")
        return
    if isinstance(value, str):
        if "\x00" in value or any(0xD800 <= ord(char) <= 0xDFFF for char in value):
            raise EvidenceError("JSON_INVALID_STRING", f"{location} contains NUL or an unpaired surrogate")
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            validate_json_scalars(child, f"{location}[{index}]")
        return
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str):
                raise EvidenceError("JSON_INVALID_KEY", f"{location} has a non-string key")
            validate_json_scalars(key, f"{location}.<key>")
            validate_json_scalars(child, f"{location}.{key}")
        return
    raise EvidenceError("JSON_INVALID_TYPE", f"{location} has unsupported type {type(value).__name__}")


def strict_json_loads(raw: bytes, source: str) -> Any:
    if len(raw) > MAX_JSON_BYTES:
        raise EvidenceError("JSON_TOO_LARGE", f"{source} exceeds {MAX_JSON_BYTES} bytes")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise EvidenceError("JSON_INVALID_UTF8", f"{source} is not UTF-8") from exc
    if lexical_json_depth(text) > MAX_JSON_DEPTH:
        raise EvidenceError("JSON_TOO_DEEP", f"{source} exceeds depth {MAX_JSON_DEPTH}")
    try:
        value = json.loads(
            text,
            object_pairs_hook=reject_duplicates,
            parse_int=parse_integer,
            parse_constant=reject_constant,
        )
    except EvidenceError:
        raise
    except (json.JSONDecodeError, RecursionError, ValueError, OverflowError) as exc:
        raise EvidenceError("JSON_MALFORMED", f"{source} is invalid JSON") from exc
    validate_json_scalars(value)
    return value


def load_json(path: Path) -> Any:
    try:
        return strict_json_loads(path.read_bytes(), path.as_posix())
    except OSError as exc:
        raise EvidenceError("INPUT_READ_FAILED", f"cannot read {path.as_posix()}") from exc


def require_dict(value: Any, location: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise EvidenceError("SCHEMA_TYPE", f"{location} must be an object")
    return value


def require_list(value: Any, location: str) -> list[Any]:
    if not isinstance(value, list):
        raise EvidenceError("SCHEMA_TYPE", f"{location} must be an array")
    return value


def require_string(value: Any, location: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value):
        raise EvidenceError("SCHEMA_TYPE", f"{location} must be a{' non-empty' if not allow_empty else ''} string")
    return value


def validate_repo_source(value: Any, location: str, repo_root: Path) -> str:
    source = require_string(value, location).replace("\\", "/")
    if not source.startswith("Codebase/") or source.startswith("Codebase//") or "/../" in f"/{source}/":
        raise EvidenceError("SOURCE_PATH_INVALID", f"{location} is not a canonical Codebase path")
    candidate = repo_root.joinpath(*source.split("/"))
    try:
        candidate.resolve(strict=True).relative_to((repo_root / "Codebase").resolve(strict=True))
    except (OSError, RuntimeError, ValueError) as exc:
        raise EvidenceError("SOURCE_PATH_UNAVAILABLE", f"{location} does not resolve inside Codebase") from exc
    return source


def require_exact_fields(value: dict[str, Any], expected: set[str], location: str) -> None:
    actual = set(value)
    if actual != expected:
        raise EvidenceError(
            "SCHEMA_FIELDS",
            f"{location} fields differ; missing={sorted(expected - actual)}, unexpected={sorted(actual - expected)}",
        )


def validate_inputs(toolchain: Any, baseline: Any, repo_root: Path, *, enforce_fingerprint: bool = True) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    toolchain_obj = require_dict(toolchain, "toolchain")
    baseline_obj = require_dict(baseline, "baseline")
    if enforce_fingerprint and (
        semantic_sha256(toolchain_obj) != EXPECTED_TOOLCHAIN_SEMANTIC_SHA256
        or semantic_sha256(baseline_obj) != EXPECTED_BASELINE_SEMANTIC_SHA256
    ):
        raise EvidenceError("UPSTREAM_CONTENT_MISMATCH", "upstream evidence differs from the authorized semantic content")
    require_exact_fields(toolchain_obj, TOOLCHAIN_TOP_LEVEL_FIELDS, "toolchain")
    require_exact_fields(baseline_obj, BASELINE_TOP_LEVEL_FIELDS, "baseline")
    if toolchain_obj.get("packageId") != "WP-I0-005" or toolchain_obj.get("status") != "PASS":
        raise EvidenceError("UPSTREAM_STATUS", "WP-I0-005 evidence is not a PASS artifact")
    if baseline_obj.get("packageId") != "WP-I0-007" or baseline_obj.get("requirementId") != "CAN-MISSION-I0-007" or baseline_obj.get("status") != "PASS":
        raise EvidenceError("UPSTREAM_STATUS", "WP-I0-007 evidence is not a PASS artifact")
    reviews = require_list(toolchain_obj.get("reviewRequired"), "toolchain.reviewRequired")
    attempts = require_list(baseline_obj.get("attempts"), "baseline.attempts")
    declarations = require_list(toolchain_obj.get("versionDeclarations"), "toolchain.versionDeclarations")
    manifests = require_list(toolchain_obj.get("manifestRecords"), "toolchain.manifestRecords")
    if (
        len(reviews) != EXPECTED_TOOLCHAIN_REVIEW_COUNT
        or len(manifests) != EXPECTED_TOOLCHAIN_MANIFEST_COUNT
        or len(declarations) != EXPECTED_TOOLCHAIN_DECLARATION_COUNT
        or len(attempts) != EXPECTED_BASELINE_ATTEMPT_COUNT
    ):
        raise EvidenceError("UPSTREAM_COUNT_MISMATCH", "upstream evidence is coherently truncated or expanded")
    toolchain_counts = require_dict(toolchain_obj.get("counts"), "toolchain.counts")
    if (
        type(toolchain_counts.get("reviewRequired")) is not int
        or toolchain_counts["reviewRequired"] != len(reviews)
        or type(toolchain_counts.get("versionDeclarations")) is not int
        or toolchain_counts["versionDeclarations"] != len(declarations)
        or type(toolchain_counts.get("manifestFiles")) is not int
        or toolchain_counts["manifestFiles"] != len(manifests)
    ):
        raise EvidenceError("UPSTREAM_COUNT_MISMATCH", "WP-I0-005 reviewRequired count does not reconcile")
    review_ids: set[tuple[str, str, str]] = set()
    for index, raw in enumerate(reviews):
        row = require_dict(raw, f"toolchain.reviewRequired[{index}]")
        if not set(row) <= TOOLCHAIN_REVIEW_FIELDS:
            raise EvidenceError("SCHEMA_FIELDS", f"unexpected toolchain review fields at row {index}")
        reason = require_string(row.get("reason"), f"toolchain.reviewRequired[{index}].reason")
        item = require_string(row.get("item"), f"toolchain.reviewRequired[{index}].item")
        require_string(row.get("category"), f"toolchain.reviewRequired[{index}].category")
        status = require_string(row.get("status"), f"toolchain.reviewRequired[{index}].status")
        if status != "REVIEW_REQUIRED":
            raise EvidenceError("UPSTREAM_STATUS", f"toolchain review row {index} is not REVIEW_REQUIRED")
        identity = (reason, item, str(row.get("category", "")))
        if identity in review_ids:
            raise EvidenceError("UPSTREAM_DUPLICATE", f"duplicate toolchain review identity at row {index}")
        review_ids.add(identity)
        for source in source_paths(row):
            validate_repo_source(source, f"toolchain.reviewRequired[{index}].source", repo_root)
    attempt_ids: set[str] = set()
    for index, raw in enumerate(attempts):
        row = require_dict(raw, f"baseline.attempts[{index}]")
        require_exact_fields(row, BASELINE_ATTEMPT_FIELDS, f"baseline.attempts[{index}]")
        attempt_id = require_string(row.get("id"), f"baseline.attempts[{index}].id")
        if attempt_id in attempt_ids:
            raise EvidenceError("UPSTREAM_DUPLICATE", f"duplicate attempt id: {attempt_id}")
        attempt_ids.add(attempt_id)
        validate_repo_source(row.get("sourcePath"), f"baseline.attempts[{index}].sourcePath", repo_root)
        for field in ("surface", "kind", "sourceCommand", "declaredCommand", "workingDirectory", "output"):
            require_string(row.get(field), f"baseline.attempts[{index}].{field}", allow_empty=field == "output")
        status = require_string(row.get("status"), f"baseline.attempts[{index}].status")
        if status not in {"SUCCESS", "FAILURE", "BLOCKED"}:
            raise EvidenceError("UPSTREAM_STATUS", f"unsupported attempt status: {status}")
        if type(row.get("executed")) is not bool:
            raise EvidenceError("SCHEMA_TYPE", f"baseline.attempts[{index}].executed must be boolean")
        blocker = row.get("blocker")
        if status == "SUCCESS" and blocker is not None:
            raise EvidenceError("UPSTREAM_CONTRADICTION", f"successful attempt {attempt_id} has a blocker")
        if status != "SUCCESS" and not isinstance(blocker, str):
            raise EvidenceError("UPSTREAM_CONTRADICTION", f"non-success attempt {attempt_id} lacks a blocker")
        if status == "BLOCKED" and row["executed"]:
            raise EvidenceError("UPSTREAM_CONTRADICTION", f"blocked attempt {attempt_id} was executed")
        if status == "FAILURE" and not row["executed"]:
            raise EvidenceError("UPSTREAM_CONTRADICTION", f"failed attempt {attempt_id} was not executed")
        exit_code = row.get("exitCode")
        if status == "SUCCESS" and (not row["executed"] or exit_code != 0):
            raise EvidenceError("UPSTREAM_CONTRADICTION", f"successful attempt {attempt_id} lacks executed exit-0 evidence")
        if status == "FAILURE" and (type(exit_code) is not int or exit_code == 0):
            raise EvidenceError("UPSTREAM_CONTRADICTION", f"failed attempt {attempt_id} lacks a nonzero integer exit code")
        if status == "BLOCKED" and exit_code is not None:
            raise EvidenceError("UPSTREAM_CONTRADICTION", f"blocked attempt {attempt_id} has an exit code")
    attempt_counts = require_dict(baseline_obj.get("attemptCounts"), "baseline.attemptCounts")
    actual_counts = Counter(row["status"] for row in attempts)
    if set(attempt_counts) != {"SUCCESS", "FAILURE", "BLOCKED"} or any(
        type(attempt_counts[key]) is not int or attempt_counts[key] != actual_counts[key]
        for key in ("SUCCESS", "FAILURE", "BLOCKED")
    ):
        raise EvidenceError("UPSTREAM_COUNT_MISMATCH", "WP-I0-007 attempt counts do not reconcile")
    for index, raw in enumerate(declarations):
        row = require_dict(raw, f"toolchain.versionDeclarations[{index}]")
        if set(row) != {"family", "source", "key", "value", "kind", "categories"}:
            raise EvidenceError("SCHEMA_FIELDS", f"unexpected version declaration fields at row {index}")
        validate_repo_source(row.get("source"), f"toolchain.versionDeclarations[{index}].source", repo_root)
        for field in ("family", "key", "kind"):
            require_string(row.get(field), f"toolchain.versionDeclarations[{index}].{field}")
        if "value" not in row:
            raise EvidenceError("SCHEMA_FIELDS", f"toolchain.versionDeclarations[{index}].value is required")
        categories = require_list(row.get("categories"), f"toolchain.versionDeclarations[{index}].categories")
        if not categories or any(not isinstance(value, str) or not value for value in categories):
            raise EvidenceError("SCHEMA_TYPE", f"toolchain.versionDeclarations[{index}].categories must contain strings")
    for index, raw in enumerate(manifests):
        row = require_dict(raw, f"toolchain.manifestRecords[{index}]")
        require_exact_fields(row, {"path", "size", "sha256", "categories"}, f"toolchain.manifestRecords[{index}]")
        source = validate_repo_source(row.get("path"), f"toolchain.manifestRecords[{index}].path", repo_root)
        if type(row.get("size")) is not int or row["size"] < 0 or not re.fullmatch(r"[0-9a-f]{64}", str(row.get("sha256", ""))):
            raise EvidenceError("SCHEMA_TYPE", f"invalid manifest size/hash at row {index}")
        path = repo_root.joinpath(*source.split("/"))
        if path.stat().st_size != row["size"] or sha256_file(path) != row["sha256"]:
            raise EvidenceError("UPSTREAM_CONTENT_MISMATCH", f"manifest record no longer matches {source}")
        categories = require_list(row.get("categories"), f"toolchain.manifestRecords[{index}].categories")
        if not categories or any(not isinstance(value, str) or not value for value in categories):
            raise EvidenceError("SCHEMA_TYPE", f"toolchain.manifestRecords[{index}].categories must contain strings")
    return reviews, attempts, declarations, manifests


def source_paths(row: dict[str, Any]) -> list[str]:
    result: list[str] = []
    raw_sources = row.get("sources", [])
    if "sources" in row:
        if not isinstance(raw_sources, list) or any(not isinstance(value, str) or not value for value in raw_sources):
            raise EvidenceError("SCHEMA_TYPE", "toolchain review sources must be an array of non-empty strings")
        result.extend(raw_sources)
    if "source" in row:
        if not isinstance(row["source"], str) or not row["source"]:
            raise EvidenceError("SCHEMA_TYPE", "toolchain review source must be a non-empty string")
        result.append(row["source"])
    item = row.get("item")
    if isinstance(item, str) and item.startswith("declaration:Codebase/"):
        result.append(item[len("declaration:") :].split("#", 1)[0])
    return sorted(set(result))


def package_surface(source: str) -> str:
    parts = source.split("/")
    if len(parts) < 3:
        return "root"
    if parts[1] == ".devcontainer":
        return parts[2] if len(parts) > 3 and parts[2] in {"mobile", "server"} else "repository"
    if parts[1] == ".github" and len(parts) > 3 and parts[2] == "workflows":
        name = Path(parts[3]).stem.lower()
        if "mobile" in name or name == "prepare-release":
            return "mobile"
        if "docs" in name:
            return "docs"
        if name == "cli":
            return "packages/cli"
        if name == "docker":
            return "docker"
        if "translation" in name or "weblate" in name:
            return "i18n"
        return "repository"
    if parts[1] == "packages" and len(parts) > 3:
        return f"packages/{parts[2]}"
    if parts[1] == "mobile" and len(parts) > 3 and parts[2] == "packages":
        return f"mobile/packages/{parts[3]}"
    return parts[1]


def item_surface(item: str) -> str | None:
    candidate = item
    for prefix in ("submodule-revision:", "declaration:"):
        if candidate.startswith(prefix):
            candidate = candidate[len(prefix) :]
    candidate = candidate.split("#", 1)[0]
    return package_surface(candidate) if candidate.startswith("Codebase/") else None


def valid_affected_packages(packages: list[str]) -> bool:
    forbidden = {"node_modules", "Pods", "Target Support Files", "${RENOVATE_REMOTE}"}
    return bool(packages) and all(
        package not in forbidden and "$" not in package and "{" not in package and "}" not in package
        for package in packages
    )


def generated_path(item: str) -> bool:
    lowered = item.lower().replace("\\", "/")
    generated_markers = (
        "/.svelte-kit/",
        "/generated.xcconfig",
        "/local.properties",
        "/.dart_tool/",
        "/deriveddata/",
        "/pods/",
    )
    return any(marker in lowered for marker in generated_markers)


def classify_toolchain(row: dict[str, Any]) -> str:
    reason = row["reason"]
    item = row["item"]
    if reason == "SUBMODULE_REVISION_UNAVAILABLE" or "e2e/test-assets" in item:
        return "FIXTURE"
    if reason == "REFERENCED_MANIFEST_UNAVAILABLE" and generated_path(item):
        return "GENERATED_ARTIFACT"
    if reason in {"HOST_PROBE_UNMAPPED", "HOST_TOOL_UNAVAILABLE"}:
        return "ENVIRONMENT_PREREQUISITE"
    return "DEPENDENCY"


def canonical_item(category: str, item: str, reason: str) -> str:
    if category == "ENVIRONMENT_PREREQUISITE" and (
        reason in {"HOST_PROBE_UNMAPPED", "HOST_TOOL_UNAVAILABLE", "CREDENTIAL_RESOLVER_UNAVAILABLE"}
        or item.startswith("host-tool:")
    ):
        return "host-tool:" + item.removeprefix("host-tool:").lower()
    return item


def record_key(category: str, item: str) -> str:
    return f"{category}:{item}"


def add_record(records: dict[str, dict[str, Any]], *, category: str, item: str, status: str,
               evidence_source: str, reason: str, blocking_effect: str, sources: list[str],
               affected_packages: list[str], affected_work_packages: list[str],
               attempt_ids: list[str] | None = None) -> None:
    if category not in ALLOWED_CATEGORIES or status not in ALLOWED_STATUSES:
        raise EvidenceError("CLASSIFICATION_INVALID", f"invalid classification {category}/{status}")
    item = canonical_item(category, item, reason)
    key = record_key(category, item)
    row = records.setdefault(key, {
        "classificationId": "missing-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:16],
        "category": category,
        "item": item,
        "status": status,
        "reasons": [],
        "blockingEffects": [],
        "evidenceSources": [],
        "sourcePaths": [],
        "attemptIds": [],
        "affectedPackages": [],
        "affectedWorkPackages": [],
        "supplyAction": "NOT_PERFORMED",
    })
    if status == "BLOCKED":
        row["status"] = "BLOCKED"
    for field, values in (
        ("reasons", [reason]),
        ("blockingEffects", [blocking_effect]),
        ("evidenceSources", [evidence_source]),
        ("sourcePaths", sources),
        ("attemptIds", attempt_ids or []),
        ("affectedPackages", affected_packages),
        ("affectedWorkPackages", affected_work_packages),
    ):
        row[field] = sorted(set(row[field]).union(values))


def toolchain_blocking_effect(reason: str) -> str:
    effects = {
        "HOST_PROBE_UNMAPPED": "Host availability cannot be established by a safe mapped probe.",
        "HOST_TOOL_UNAVAILABLE": "The declared host tool cannot be used on this host.",
        "NO_DISCOVERABLE_REPOSITORY_VERSION": "No repository version can be selected safely.",
        "NO_REPOSITORY_MANIFEST": "No repository manifest establishes the required toolchain.",
        "REFERENCED_MANIFEST_UNAVAILABLE": "A mandatory referenced manifest is absent, so its consumer is not reproducible.",
        "SUBMODULE_REVISION_UNAVAILABLE": "The fixture submodule revision is absent, so fixture contents are not reproducible.",
        "VERSION_REFERENCE_UNRESOLVED": "The dependency/tool reference is floating or unresolved and cannot be reproduced exactly.",
    }
    return effects[reason]


TOOL_DECLARATION_ALIASES = {
    "armnn": ("armnn",),
    "binaryen": ("binaryen",),
    "bun": ("bun",),
    "bundler": ("bundler",),
    "ccache": ("ccache",),
    "cmake": ("cmake",),
    "conda": ("conda:",),
    "dart": ("dart",),
    "dcm": ("dcm",),
    "docker": ("compose-image:", "docker-", "from "),
    "extism": ("extism",),
    "extism-js-pdk": ("extism-js-pdk", "extism/js-pdk"),
    "fastlane": ("fastlane",),
    "flutter": ("flutter",),
    "g++": ("g++", "cxx-standard"),
    "gradle": ("gradle",),
    "java": ("java-", "jvm"),
    "mise": ("mise-",),
    "ninja": ("ninja",),
    "oazapfts": ("oazapfts",),
    "openapi-generator-cli": ("openapi-generator",),
    "pod": ("cocoapods", "podfile"),
    "renovate": ("renovate",),
    "ruby": ("ruby",),
    "rust": ("rust", "cargo"),
    "swift": ("swift",),
    "terragrunt": ("terragrunt",),
    "tofu": ("opentofu", "tofu", "terraform-provider"),
    "wrangler": ("wrangler",),
    "xcodebuild": ("xcode", "ios-deployment-target"),
    "yarn": ("yarn",),
}


def declaration_consumer_sources(item: str, declarations: list[dict[str, Any]]) -> list[str]:
    terms = TOOL_DECLARATION_ALIASES.get(item.lower(), (item.lower(),))
    sources: set[str] = set()
    for row in declarations:
        haystack = " ".join(str(row[field]).lower() for field in ("family", "key", "value"))
        matched = False
        for term in terms:
            if term.endswith((":", "-", " ")):
                matched = term in haystack
            else:
                matched = re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", haystack) is not None
            if matched:
                break
        if matched:
            sources.add(row["source"])
    return sorted(sources)


def command_failure_expansion(attempt: dict[str, Any]) -> tuple[tuple[str, str, str], ...]:
    output = str(attempt.get("output", ""))
    if attempt["id"] == "ml-unit-test" and "opencv-python-headless==4.13.0.92" in output:
        return (("DEPENDENCY", "python-package:opencv-python-headless==4.13.0.92", "Required Python wheel is absent from the authorized offline cache."),)
    if attempt["id"] == "ml-package-build" and "hatchling" in output and "not found in the cache" in output:
        return (("DEPENDENCY", "python-package:hatchling", "Required Python build backend is absent from the authorized offline cache."),)
    raise EvidenceError("UNCLASSIFIED_FAILURE", f"executed failure {attempt['id']} has no missing-prerequisite classifier")


def discover_missing_env_files(repo_root: Path) -> list[dict[str, Any]]:
    """Find absent Compose env_file paths and credential fields in local examples."""
    discoveries: dict[str, dict[str, Any]] = {}
    for compose in sorted((repo_root / "Codebase").rglob("docker-compose*.yml")):
        try:
            lines = compose.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError) as exc:
            raise EvidenceError("ENV_REFERENCE_READ_FAILED", f"cannot read {compose.as_posix()}") from exc
        env_indent: int | None = None
        for line_number, line in enumerate(lines, 1):
            stripped = line.lstrip()
            indent = len(line) - len(stripped)
            if re.match(r"env_file\s*:\s*$", stripped):
                env_indent = indent
                continue
            if env_indent is None:
                continue
            if stripped and not stripped.startswith("#") and indent <= env_indent:
                env_indent = None
                continue
            match = re.match(r"\s*-\s*['\"]?([^'\"\s#]+)['\"]?\s*(?:#.*)?$", line)
            if not match:
                continue
            reference = match.group(1)
            if "${" in reference:
                continue
            resolved = (compose.parent / reference).resolve(strict=False)
            try:
                resolved.relative_to((repo_root / "Codebase").resolve(strict=True))
            except ValueError as exc:
                raise EvidenceError("ENV_REFERENCE_ESCAPE", f"env_file reference escapes Codebase: {reference}") from exc
            if resolved.exists():
                continue
            relative = resolved.relative_to(repo_root).as_posix()
            entry = discoveries.setdefault(relative, {"path": relative, "sources": [], "credentialNames": []})
            entry["sources"].append(f"{compose.relative_to(repo_root).as_posix()}:{line_number}")
            example = compose.parent / "example.env"
            if example.is_file():
                for example_line_number, example_line in enumerate(example.read_text(encoding="utf-8").splitlines(), 1):
                    variable = re.match(r"\s*([A-Z][A-Z0-9_]*)\s*=", example_line)
                    if variable and re.search(r"(?:PASSWORD|SECRET|TOKEN|API_KEY|CREDENTIAL)", variable.group(1)):
                        entry["credentialNames"].append({
                            "name": variable.group(1),
                            "source": f"{example.relative_to(repo_root).as_posix()}:{example_line_number}",
                        })
    for entry in discoveries.values():
        entry["sources"] = sorted(set(entry["sources"]))
        entry["credentialNames"] = sorted(
            {value["name"]: value for value in entry["credentialNames"]}.values(), key=lambda value: value["name"]
        )
    return sorted(discoveries.values(), key=lambda value: value["path"])


def discover_unresolved_env_values(repo_root: Path) -> list[dict[str, str]]:
    """Classify local env-manifest references without resolving or supplying them."""
    discoveries: list[dict[str, str]] = []
    for env_file in sorted((repo_root / "Codebase").rglob(".env")):
        if not env_file.is_file():
            continue
        try:
            lines = env_file.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError) as exc:
            raise EvidenceError("ENV_REFERENCE_READ_FAILED", f"cannot read {env_file.as_posix()}") from exc
        for line_number, line in enumerate(lines, 1):
            match = re.match(r"\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$", line)
            if not match or line.lstrip().startswith("#"):
                continue
            name, raw_value = match.groups()
            value = raw_value.strip("'\"")
            source = f"{env_file.relative_to(repo_root).as_posix()}:{line_number}"
            if value.startswith("op://"):
                discoveries.append({"category": "CREDENTIAL", "name": name, "reference": value, "source": source})
                continue
            variable = re.fullmatch(r"\$\{?([A-Z][A-Z0-9_]*)\}?", value)
            if variable:
                discoveries.append({
                    "category": "ENVIRONMENT_PREREQUISITE",
                    "name": variable.group(1),
                    "reference": value,
                    "source": source,
                })
    return discoveries


def workflow_affected_packages(source: str) -> list[str]:
    name = Path(source).stem.lower()
    if "mobile" in name or name == "prepare-release":
        return ["mobile"]
    if "docs" in name:
        return ["deployment", "docs"]
    if name == "cli":
        return ["packages/cli"]
    if name == "docker":
        return ["docker", "machine-learning", "server"]
    if "translation" in name or "weblate" in name:
        return ["i18n"]
    return ["repository"]


def discover_manifest_references(repo_root: Path, manifests: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Discover credential/environment references in already-inspected manifests."""
    discoveries: dict[tuple[str, str], dict[str, Any]] = {}
    for manifest in manifests:
        source = manifest["path"]
        path = repo_root.joinpath(*source.split("/"))
        if not (
            source.startswith("Codebase/.github/workflows/") and path.suffix.lower() in {".yml", ".yaml"}
            or path.suffix.lower() in {".hcl", ".tf"}
        ):
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError) as exc:
            raise EvidenceError("REFERENCE_READ_FAILED", f"cannot read {source}") from exc
        for line_number, line in enumerate(lines, 1):
            references: list[tuple[str, str, str]] = []
            references.extend(("CREDENTIAL", match.group(1), "GITHUB_ACTIONS_SECRET_REFERENCE") for match in re.finditer(r"\$\{\{\s*secrets\.([A-Za-z_][A-Za-z0-9_]*)\s*\}\}", line))
            if re.search(r"\$\{\{\s*github\.token\s*\}\}", line):
                references.append(("CREDENTIAL", "GITHUB_TOKEN", "GITHUB_ACTIONS_TOKEN_REFERENCE"))
            for match in re.finditer(r"get_env\(\s*['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]\s*\)", line):
                name = match.group(1)
                credential = re.search(r"(?:PASSWORD|SECRET|TOKEN|API_KEY|ACCOUNT_ID|CONN_STR|CREDENTIAL)", name) is not None
                references.append(("CREDENTIAL" if credential else "ENVIRONMENT_PREREQUISITE", name, "ENVIRONMENT_REFERENCE_UNRESOLVED"))
            for category, name, reason in references:
                key = (category, name)
                row = discoveries.setdefault(key, {"category": category, "name": name, "reasons": [], "sources": [], "affectedPackages": []})
                row["reasons"].append(reason)
                row["sources"].append(f"{source}:{line_number}")
                row["affectedPackages"].extend(workflow_affected_packages(source) if source.startswith("Codebase/.github/workflows/") else [package_surface(source)])
    for row in discoveries.values():
        for field in ("reasons", "sources", "affectedPackages"):
            row[field] = sorted(set(row[field]))
    return sorted(discoveries.values(), key=lambda row: (row["category"], row["name"]))


def build_classifications(reviews: list[dict[str, Any]], attempts: list[dict[str, Any]], declarations: list[dict[str, Any]], manifests: list[dict[str, Any]], repo_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    included_review_rows = excluded_review_rows = 0
    unknown_reasons: set[str] = set()
    for index, row in enumerate(reviews):
        reason = row["reason"]
        if reason in NON_MISSING_TOOLCHAIN_REASONS:
            excluded_review_rows += 1
            continue
        if reason not in MISSING_TOOLCHAIN_REASONS:
            unknown_reasons.add(reason)
            continue
        included_review_rows += 1
        sources = source_paths(row)
        if not sources and reason in {"HOST_PROBE_UNMAPPED", "HOST_TOOL_UNAVAILABLE", "NO_DISCOVERABLE_REPOSITORY_VERSION", "NO_REPOSITORY_MANIFEST"}:
            sources = declaration_consumer_sources(row["item"], declarations)
        affected_set = {package_surface(source) for source in sources}
        inferred_surface = item_surface(row["item"])
        if inferred_surface and (not affected_set or reason == "SUBMODULE_REVISION_UNAVAILABLE"):
            affected_set.add(inferred_surface)
        affected = sorted(affected_set) or ["repository"]
        add_record(
            records,
            category=classify_toolchain(row),
            item=row["item"],
            status="REVIEW_REQUIRED",
            evidence_source=f"WP-I0-005/toolchain-inventory.json#reviewRequired[{index}]",
            reason=reason,
            blocking_effect=toolchain_blocking_effect(reason),
            sources=sources,
            affected_packages=affected,
            affected_work_packages=["WP-I0-005"],
        )
    if unknown_reasons:
        raise EvidenceError("UNCLASSIFIED_REASON", f"unclassified toolchain reasons: {sorted(unknown_reasons)}")

    covered_attempts: set[str] = set()
    for index, attempt in enumerate(attempts):
        if attempt["status"] == "SUCCESS":
            continue
        blocker = attempt["blocker"]
        expansions = command_failure_expansion(attempt) if blocker == "COMMAND_EXIT_NONZERO" else BLOCKER_EXPANSIONS.get(blocker)
        if not expansions:
            raise EvidenceError("UNCLASSIFIED_BLOCKER", f"unclassified baseline blocker: {blocker}")
        covered_attempts.add(attempt["id"])
        source = attempt["sourcePath"]
        for category, item, effect in expansions:
            add_record(
                records,
                category=category,
                item=item,
                status="BLOCKED",
                evidence_source=f"WP-I0-007/baseline-attempts.json#attempts[{index}]",
                reason=blocker,
                blocking_effect=effect,
                sources=[source],
                affected_packages=[attempt["surface"]],
                affected_work_packages=["WP-I0-007"],
                attempt_ids=[attempt["id"]],
            )
    expected_non_success = {attempt["id"] for attempt in attempts if attempt["status"] != "SUCCESS"}
    if covered_attempts != expected_non_success:
        raise EvidenceError("ATTEMPT_COVERAGE", "not every non-success baseline attempt was classified")

    missing_env_files = discover_missing_env_files(repo_root)
    for discovery in missing_env_files:
        source_paths_without_lines = sorted({source.rsplit(":", 1)[0] for source in discovery["sources"]})
        affected_attempts = sorted(
            attempt["id"] for attempt in attempts
            if attempt["status"] != "SUCCESS"
            and attempt["id"].startswith(("docker-dev-", "docker-prod-"))
        )
        add_record(
            records,
            category="ENVIRONMENT_PREREQUISITE",
            item=discovery["path"],
            status="BLOCKED" if affected_attempts else "REVIEW_REQUIRED",
            evidence_source=";".join(discovery["sources"]),
            reason="COMPOSE_ENV_FILE_UNAVAILABLE",
            blocking_effect="A mandatory Compose environment file is absent, so affected container surfaces cannot resolve required configuration.",
            sources=source_paths_without_lines,
            affected_packages=sorted({package_surface(source) for source in source_paths_without_lines}),
            affected_work_packages=["WP-I0-007"],
            attempt_ids=affected_attempts,
        )
        for credential in discovery["credentialNames"]:
            add_record(
                records,
                category="CREDENTIAL",
                item=f"{discovery['path']}#{credential['name']}",
                status="BLOCKED" if affected_attempts else "REVIEW_REQUIRED",
                evidence_source=f"{credential['source']};" + ";".join(discovery["sources"]),
                reason="CREDENTIAL_VALUE_UNAVAILABLE",
                blocking_effect="A declared credential value is absent with its required Compose environment file.",
                sources=source_paths_without_lines + [credential["source"].rsplit(":", 1)[0]],
                affected_packages=sorted({package_surface(source) for source in source_paths_without_lines}),
                affected_work_packages=["WP-I0-007"],
                attempt_ids=affected_attempts,
            )

    unresolved_env_values = discover_unresolved_env_values(repo_root)
    for discovery in unresolved_env_values:
        source_path = discovery["source"].rsplit(":", 1)[0]
        category = discovery["category"]
        add_record(
            records,
            category=category,
            item=("credential-reference:" if category == "CREDENTIAL" else "environment-variable:") + discovery["name"],
            status="REVIEW_REQUIRED",
            evidence_source=discovery["source"],
            reason="CREDENTIAL_REFERENCE_UNRESOLVED" if category == "CREDENTIAL" else "ENVIRONMENT_VALUE_UNAVAILABLE",
            blocking_effect=(
                "The committed manifest contains only an external credential reference; the credential value was not resolved or supplied."
                if category == "CREDENTIAL"
                else "The committed manifest references an environment value that was not present or supplied during read-only inspection."
            ),
            sources=[source_path],
            affected_packages=[package_surface(source_path)],
            affected_work_packages=["WP-I0-005"],
        )
    manifest_references = discover_manifest_references(repo_root, manifests)
    for discovery in manifest_references:
        source_paths_without_lines = sorted({source.rsplit(":", 1)[0] for source in discovery["sources"]})
        for reason in discovery["reasons"]:
            add_record(
                records,
                category=discovery["category"],
                item=("credential-reference:" if discovery["category"] == "CREDENTIAL" else "environment-variable:") + discovery["name"],
                status="REVIEW_REQUIRED",
                evidence_source=";".join(discovery["sources"]),
                reason=reason,
                blocking_effect=(
                    "A committed workflow or deployment manifest references a credential whose value is intentionally absent from the repository and was not supplied."
                    if discovery["category"] == "CREDENTIAL"
                    else "A committed deployment manifest references an environment value that was not supplied during read-only inspection."
                ),
                sources=source_paths_without_lines,
                affected_packages=discovery["affectedPackages"],
                affected_work_packages=["WP-I0-005"],
            )
    op_references = [value for value in unresolved_env_values if value["reference"].startswith("op://")]
    op_tool_unavailable = bool(op_references) and shutil.which("op") is None
    if op_tool_unavailable:
        op_sources = sorted({value["source"].rsplit(":", 1)[0] for value in op_references})
        add_record(
            records,
            category="ENVIRONMENT_PREREQUISITE",
            item="host-tool:op",
            status="REVIEW_REQUIRED",
            evidence_source=";".join(sorted(value["source"] for value in op_references)),
            reason="CREDENTIAL_RESOLVER_UNAVAILABLE",
            blocking_effect="The 1Password CLI required by committed op:// credential references is unavailable on this host.",
            sources=op_sources,
            affected_packages=sorted({package_surface(source) for source in op_sources}),
            affected_work_packages=["WP-I0-005"],
        )

    result = sorted(records.values(), key=lambda row: (row["category"], row["item"], row["classificationId"]))
    for row in result:
        if not row["evidenceSources"] or not row["blockingEffects"] or not row["affectedPackages"]:
            raise EvidenceError("CLASSIFICATION_INCOMPLETE", f"incomplete classification {row['classificationId']}")
        if not valid_affected_packages(row["affectedPackages"]):
            raise EvidenceError("AFFECTED_PACKAGE_INVALID", f"pseudo-package context in {row['classificationId']}")
    oracle = {
        "toolchainReviewRows": len(reviews),
        "includedMissingRows": included_review_rows,
        "excludedNonMissingRows": excluded_review_rows,
        "excludedReasons": sorted(NON_MISSING_TOOLCHAIN_REASONS),
        "baselineAttempts": len(attempts),
        "successfulAttemptsNotMissing": len(attempts) - len(expected_non_success),
        "nonSuccessAttempts": len(expected_non_success),
        "coveredNonSuccessAttempts": len(covered_attempts),
        "unclassifiedToolchainReasons": [],
        "unclassifiedBaselineBlockers": [],
        "independentlyDiscoveredMissingEnvFiles": len(missing_env_files),
        "independentlyDiscoveredMissingCredentials": sum(len(value["credentialNames"]) for value in missing_env_files),
        "independentlyDiscoveredUnresolvedEnvValues": len(unresolved_env_values),
        "independentlyDiscoveredManifestReferences": len(manifest_references),
        "credentialResolverUnavailable": op_tool_unavailable,
        "result": "PASS",
    }
    return result, oracle


def has_reparse_attribute(path: Path) -> bool:
    try:
        stat = path.lstat()
    except OSError as exc:
        raise EvidenceError("CODEBASE_SCAN_FAILED", f"cannot stat {path.as_posix()}") from exc
    return bool(getattr(stat, "st_file_attributes", 0) & 0x400) or path.is_symlink()


def snapshot_codebase(codebase: Path) -> dict[str, tuple[int, str]]:
    if not codebase.is_dir() or has_reparse_attribute(codebase):
        raise EvidenceError("CODEBASE_ROOT_INVALID", "Codebase must be a real directory")
    result: dict[str, tuple[int, str]] = {}
    for root, dirs, files in os.walk(codebase, topdown=True, followlinks=False):
        root_path = Path(root)
        for name in sorted(dirs):
            if has_reparse_attribute(root_path / name):
                raise EvidenceError("CODEBASE_REPARSE_POINT", f"reparse directory: {(root_path / name).as_posix()}")
        for name in sorted(files):
            path = root_path / name
            if has_reparse_attribute(path):
                raise EvidenceError("CODEBASE_REPARSE_POINT", f"reparse file: {path.as_posix()}")
            relative = path.relative_to(codebase.parent).as_posix()
            try:
                size = path.stat().st_size
                digest = sha256_file(path)
            except OSError as exc:
                raise EvidenceError("CODEBASE_SCAN_FAILED", f"cannot hash {relative}") from exc
            result[relative] = (size, digest)
    return result


def load_authoritative_manifest(path: Path) -> dict[str, tuple[int, str]]:
    result: dict[str, tuple[int, str]] = {}
    try:
        with path.open("r", encoding="utf-8", newline="") as stream:
            rows = csv.DictReader(stream)
            if rows.fieldnames != ["path", "size", "sha256"]:
                raise EvidenceError("MANIFEST_SCHEMA", "unexpected WP-I0-001 manifest header")
            for index, row in enumerate(rows):
                source = row.get("path", "")
                if not source.startswith("Codebase/") or source in result:
                    raise EvidenceError("MANIFEST_SCHEMA", f"invalid manifest path at row {index + 2}")
                size_text = row.get("size", "")
                digest = row.get("sha256", "")
                if not size_text.isdigit() or not re.fullmatch(r"[0-9a-f]{64}", digest):
                    raise EvidenceError("MANIFEST_SCHEMA", f"invalid manifest value at row {index + 2}")
                result[source] = (int(size_text), digest)
    except OSError as exc:
        raise EvidenceError("MANIFEST_READ_FAILED", "cannot read WP-I0-001 manifest") from exc
    return result


def compare_snapshots(expected: dict[str, tuple[int, str]], current: dict[str, tuple[int, str]]) -> dict[str, Any]:
    expected_paths, current_paths = set(expected), set(current)
    mismatched = sorted(path for path in expected_paths & current_paths if expected[path] != current[path])
    result = {
        "expectedFiles": len(expected),
        "currentFiles": len(current),
        "missing": sorted(expected_paths - current_paths),
        "unexpected": sorted(current_paths - expected_paths),
        "mismatched": mismatched,
    }
    result["result"] = "PASS" if not result["missing"] and not result["unexpected"] and not mismatched else "FAIL"
    return result


def negative_fixtures(toolchain: dict[str, Any], baseline: dict[str, Any], repo_root: Path) -> list[dict[str, str]]:
    fixtures: list[tuple[str, Any, Any, str]] = []
    fixtures.append(("toolchain-wrong-root-type", [], baseline, "SCHEMA_TYPE"))
    fixtures.append(("baseline-wrong-attempts-type", toolchain, {**baseline, "attempts": {}}, "SCHEMA_TYPE"))
    bad = deepcopy(baseline)
    bad["attempts"][0]["executed"] = "false"
    fixtures.append(("attempt-boolean-string", toolchain, bad, "SCHEMA_TYPE"))
    bad = deepcopy(baseline)
    bad["attempts"][0]["sourcePath"] = "../Codebase/package.json"
    fixtures.append(("source-path-traversal", toolchain, bad, "SOURCE_PATH_INVALID"))
    bad = deepcopy(baseline)
    bad["attempts"][0]["blocker"] = "UNKNOWN_BLOCKER"
    fixtures.append(("unknown-blocker", toolchain, bad, "UNCLASSIFIED_BLOCKER"))
    bad = deepcopy(toolchain)
    bad["counts"]["reviewRequired"] += 1
    fixtures.append(("toolchain-count-mismatch", bad, baseline, "UPSTREAM_COUNT_MISMATCH"))
    bad = deepcopy(baseline)
    bad["attemptCounts"]["BLOCKED"] -= 1
    fixtures.append(("attempt-count-mismatch", toolchain, bad, "UPSTREAM_COUNT_MISMATCH"))
    bad = deepcopy(baseline)
    bad["attempts"][0]["exitCode"] = 0
    fixtures.append(("blocked-exit-code-contradiction", toolchain, bad, "UPSTREAM_CONTRADICTION"))
    bad = deepcopy(toolchain)
    sourced_index = next(index for index, row in enumerate(bad["reviewRequired"]) if "sources" in row)
    bad["reviewRequired"][sourced_index]["sources"] = "Codebase/package.json"
    fixtures.append(("toolchain-sources-wrong-type", bad, baseline, "SCHEMA_TYPE"))
    bad = deepcopy(toolchain)
    bad["reviewRequired"][0]["reason"] = "UNKNOWN_MISSING_REASON"
    fixtures.append(("unknown-toolchain-reason", bad, baseline, "UNCLASSIFIED_REASON"))
    bad = deepcopy(toolchain)
    bad["reviewRequired"] = []
    bad["counts"]["reviewRequired"] = 0
    fixtures.append(("coherently-truncated-toolchain", bad, baseline, "UPSTREAM_COUNT_MISMATCH"))
    bad = deepcopy(baseline)
    bad["attempts"] = []
    bad["attemptCounts"] = {"SUCCESS": 0, "FAILURE": 0, "BLOCKED": 0}
    fixtures.append(("coherently-truncated-baseline", toolchain, bad, "UPSTREAM_COUNT_MISMATCH"))
    bad = deepcopy(toolchain)
    bad["unexpected"] = True
    fixtures.append(("unexpected-toolchain-field", bad, baseline, "SCHEMA_FIELDS"))
    bad = deepcopy(baseline)
    bad["unexpected"] = True
    fixtures.append(("unexpected-baseline-field", toolchain, bad, "SCHEMA_FIELDS"))
    results: list[dict[str, str]] = []
    for name, tool_value, base_value, expected in fixtures:
        actual = "ACCEPTED"
        try:
            reviews, attempts, declarations, manifests = validate_inputs(tool_value, base_value, repo_root, enforce_fingerprint=False)
            build_classifications(reviews, attempts, declarations, manifests, repo_root)
        except EvidenceError as exc:
            actual = exc.code
        results.append({"fixture": name, "expected": expected, "actual": actual, "result": "PASS" if actual == expected else "FAIL"})
    mutated = deepcopy(baseline)
    mutated["attempts"][0]["output"] += " altered"
    actual = "ACCEPTED"
    try:
        validate_inputs(toolchain, mutated, repo_root)
    except EvidenceError as exc:
        actual = exc.code
    results.append({
        "fixture": "coherent-content-replacement",
        "expected": "UPSTREAM_CONTENT_MISMATCH",
        "actual": actual,
        "result": "PASS" if actual == "UPSTREAM_CONTENT_MISMATCH" else "FAIL",
    })

    raw_fixtures = (
        ("duplicate-key", b'{"status":"PASS","status":"FAIL"}', "JSON_DUPLICATE_KEY"),
        ("malformed-json", b'{"status":', "JSON_MALFORMED"),
        ("nonfinite-json", b'{"value":NaN}', "JSON_NONFINITE_NUMBER"),
        ("invalid-utf8", b'{"value":"\xff"}', "JSON_INVALID_UTF8"),
        ("unpaired-surrogate", b'{"value":"\\ud800"}', "JSON_INVALID_STRING"),
        ("deep-json", (b'[' * 129) + b'0' + (b']' * 129), "JSON_TOO_DEEP"),
        ("large-integer", b'{"value":' + (b'9' * 257) + b'}', "JSON_INTEGER_TOO_LARGE"),
    )
    for name, raw, expected in raw_fixtures:
        actual = "ACCEPTED"
        try:
            strict_json_loads(raw, name)
        except EvidenceError as exc:
            actual = exc.code
        results.append({"fixture": name, "expected": expected, "actual": actual, "result": "PASS" if actual == expected else "FAIL"})
    pods_paths = (
        "Codebase/mobile/ios/Pods/Target Support Files/Pods-Runner/Pods-Runner-frameworks.sh",
        "Codebase/mobile/ios/Pods/Target Support Files/Pods-Runner/Pods-Runner.release.xcconfig",
        "Codebase/mobile/ios/Pods/Manifest.lock",
    )
    pods_actual = all(generated_path(value) for value in pods_paths)
    results.append({
        "fixture": "cocoapods-generated-path-family",
        "expected": "GENERATED_ARTIFACT",
        "actual": "GENERATED_ARTIFACT" if pods_actual else "DEPENDENCY",
        "result": "PASS" if pods_actual else "FAIL",
    })
    dedupe_records: dict[str, dict[str, Any]] = {}
    add_record(
        dedupe_records, category="ENVIRONMENT_PREREQUISITE", item="docker", status="REVIEW_REQUIRED",
        evidence_source="toolchain", reason="HOST_TOOL_UNAVAILABLE", blocking_effect="unavailable",
        sources=[], affected_packages=["repository"], affected_work_packages=["WP-I0-005"],
    )
    add_record(
        dedupe_records, category="ENVIRONMENT_PREREQUISITE", item="host-tool:docker", status="BLOCKED",
        evidence_source="baseline", reason="CONTAINER_RUNTIME_VOLUME_AND_NETWORK_UNAVAILABLE",
        blocking_effect="blocked", sources=["Codebase/mise.toml"], affected_packages=["root"],
        affected_work_packages=["WP-I0-007"], attempt_ids=["docker-prod-build"],
    )
    dedupe_actual = len(dedupe_records) == 1 and next(iter(dedupe_records.values()))["status"] == "BLOCKED"
    results.append({
        "fixture": "semantic-host-tool-deduplication",
        "expected": "ONE_BLOCKED_RECORD",
        "actual": "ONE_BLOCKED_RECORD" if dedupe_actual else "DUPLICATE_OR_WEAK_STATUS",
        "result": "PASS" if dedupe_actual else "FAIL",
    })
    cmake_sources = declaration_consumer_sources("cmake", toolchain["versionDeclarations"])
    cmake_expected = "Codebase/mobile/android/app/CMakeLists.txt"
    results.append({
        "fixture": "host-tool-consumer-linkage",
        "expected": cmake_expected,
        "actual": cmake_expected if cmake_expected in cmake_sources else "MISSING",
        "result": "PASS" if cmake_expected in cmake_sources else "FAIL",
    })
    for tool, expected_source in (
        ("g++", "Codebase/machine-learning/Dockerfile"),
        ("extism-js-pdk", "Codebase/mise.toml"),
    ):
        actual_sources = declaration_consumer_sources(tool, toolchain["versionDeclarations"])
        results.append({
            "fixture": f"host-tool-consumer-linkage-{tool}",
            "expected": expected_source,
            "actual": expected_source if expected_source in actual_sources else "MISSING",
            "result": "PASS" if expected_source in actual_sources else "FAIL",
        })
    for name, source, expected_surface in (
        ("devcontainer-mobile-surface", "Codebase/.devcontainer/mobile/container-compose-overrides.yml", "mobile"),
        ("devcontainer-server-surface", "Codebase/.devcontainer/server/container-compose-overrides.yml", "server"),
        ("workflow-mobile-surface", "Codebase/.github/workflows/build-mobile.yml", "mobile"),
    ):
        actual_surface = package_surface(source)
        results.append({
            "fixture": name,
            "expected": expected_surface,
            "actual": actual_surface,
            "result": "PASS" if actual_surface == expected_surface else "FAIL",
        })
    pseudo_packages = ["${RENOVATE_REMOTE}", "node_modules", "Pods"]
    pseudo_actual = all(not valid_affected_packages([value]) for value in pseudo_packages)
    results.append({
        "fixture": "pseudo-package-context-rejection",
        "expected": "ALL_REJECTED",
        "actual": "ALL_REJECTED" if pseudo_actual else "PSEUDO_PACKAGE_ACCEPTED",
        "result": "PASS" if pseudo_actual else "FAIL",
    })
    return results


def atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False, sort_keys=False) + "\n").encode("utf-8")


def main() -> int:
    package_dir = Path(__file__).resolve().parent
    repo_root = package_dir.parents[2]
    toolchain_path = repo_root / "graphify/13-implementation/WP-I0-005/toolchain-inventory.json"
    baseline_path = repo_root / "graphify/13-implementation/WP-I0-007/baseline-attempts.json"
    manifest_path = repo_root / "graphify/13-implementation/WP-I0-001/sha256-manifest.csv"
    started = datetime.now(timezone.utc)
    if sha256_file(toolchain_path) != EXPECTED_TOOLCHAIN_SHA256:
        raise EvidenceError("UPSTREAM_HASH_MISMATCH", "WP-I0-005 toolchain evidence bytes differ from the authorized artifact")
    if sha256_file(baseline_path) != EXPECTED_BASELINE_SHA256:
        raise EvidenceError("UPSTREAM_HASH_MISMATCH", "WP-I0-007 baseline evidence bytes differ from the authorized artifact")
    toolchain = load_json(toolchain_path)
    baseline = load_json(baseline_path)
    reviews, attempts, declarations, manifests = validate_inputs(toolchain, baseline, repo_root)
    authoritative = load_authoritative_manifest(manifest_path)
    before_snapshot = snapshot_codebase(repo_root / "Codebase")
    before = compare_snapshots(authoritative, before_snapshot)
    classifications, oracle = build_classifications(reviews, attempts, declarations, manifests, repo_root)
    fixtures = negative_fixtures(toolchain, baseline, repo_root)
    after_snapshot = snapshot_codebase(repo_root / "Codebase")
    after = compare_snapshots(authoritative, after_snapshot)
    unchanged = before_snapshot == after_snapshot

    category_counts = Counter(row["category"] for row in classifications)
    status_counts = Counter(row["status"] for row in classifications)
    supply_counts = Counter(row["supplyAction"] for row in classifications)
    failures: list[str] = []
    if before["result"] != "PASS" or after["result"] != "PASS" or not unchanged:
        failures.append("Codebase differs from the WP-I0-001 authoritative manifest or changed during classification")
    if oracle["result"] != "PASS":
        failures.append("classification oracle failed")
    if any(row["result"] != "PASS" for row in fixtures):
        failures.append("negative fixture failed")
    if supply_counts != {"NOT_PERFORMED": len(classifications)}:
        failures.append("a prerequisite was generated, installed, or supplied")
    status = "PASS" if not failures else "FAIL"
    ended = datetime.now(timezone.utc)

    classification_document = {
        "packageId": PACKAGE_ID,
        "requirementId": REQUIREMENT_ID,
        "objective": "Classify each missing prerequisite observed during completed read-only I0 inspection without supplying it.",
        "collectionWindowUtc": {"start": started.isoformat(), "end": ended.isoformat()},
        "sourceEvidence": [
            {"path": toolchain_path.relative_to(repo_root).as_posix(), "sha256": sha256_file(toolchain_path)},
            {"path": baseline_path.relative_to(repo_root).as_posix(), "sha256": sha256_file(baseline_path)},
            {"path": manifest_path.relative_to(repo_root).as_posix(), "sha256": sha256_file(manifest_path)},
        ],
        "categoryDefinitions": {
            "FIXTURE": "Missing test or sample corpus content or provenance.",
            "GENERATED_ARTIFACT": "Missing derived configuration or generated build metadata.",
            "DEPENDENCY": "Missing, floating, or unresolved package, manifest, revision, or dependency reference.",
            "CREDENTIAL": "Missing credential or secret required by an observed surface.",
            "ENVIRONMENT_PREREQUISITE": "Missing host tool, platform, network capability, or safe output-isolation proof.",
        },
        "classifications": classifications,
        "counts": {
            "records": len(classifications),
            "byCategory": {category: category_counts.get(category, 0) for category in sorted(ALLOWED_CATEGORIES)},
            "byStatus": {value: status_counts.get(value, 0) for value in sorted(ALLOWED_STATUSES)},
            "supplyActions": dict(sorted(supply_counts.items())),
        },
        "oracle": oracle,
        "status": status,
        "failures": failures,
    }
    verification = {
        "packageId": PACKAGE_ID,
        "checks": {
            "strictUpstreamSchemas": "PASS",
            "missingObservationCompleteness": oracle["result"],
            "classificationFieldCompleteness": "PASS" if all(row["evidenceSources"] and row["blockingEffects"] and row["affectedPackages"] for row in classifications) else "FAIL",
            "statusVocabulary": "PASS" if set(status_counts) <= ALLOWED_STATUSES else "FAIL",
            "noSupplyAction": "PASS" if supply_counts == {"NOT_PERFORMED": len(classifications)} else "FAIL",
            "negativeFixtures": "PASS" if all(row["result"] == "PASS" for row in fixtures) else "FAIL",
            "codebaseBaselineBefore": before["result"],
            "codebaseBaselineAfter": after["result"],
            "codebaseUnchangedDuringCollection": "PASS" if unchanged else "FAIL",
        },
        "negativeFixtures": fixtures,
        "preservation": {"before": before, "after": after, "unchanged": unchanged},
        "result": status,
    }
    consistency = {
        "packageId": PACKAGE_ID,
        "assertions": {
            "classificationCountMatches": len(classifications) == classification_document["counts"]["records"],
            "categoryCountMatches": sum(classification_document["counts"]["byCategory"].values()) == len(classifications),
            "statusCountMatches": sum(classification_document["counts"]["byStatus"].values()) == len(classifications),
            "everyRecordHasEvidence": all(row["evidenceSources"] for row in classifications),
            "everyRecordHasBlockingEffect": all(row["blockingEffects"] for row in classifications),
            "everyRecordNamesAffectedPackages": all(row["affectedPackages"] for row in classifications),
            "everyNonSuccessAttemptCovered": oracle["nonSuccessAttempts"] == oracle["coveredNonSuccessAttempts"],
            "noSupplyActionPerformed": supply_counts == {"NOT_PERFORMED": len(classifications)},
            "codebasePreserved": unchanged and before["result"] == after["result"] == "PASS",
        },
    }
    consistency["result"] = "PASS" if all(consistency["assertions"].values()) else "FAIL"
    provenance = {
        "packageId": PACKAGE_ID,
        "requirementId": REQUIREMENT_ID,
        "repositoryRoot": str(repo_root),
        "codebaseRoot": str(repo_root / "Codebase"),
        "classificationSources": [str(toolchain_path), str(baseline_path)],
        "authoritativeBaseline": str(manifest_path),
        "networkUsed": False,
        "dependenciesInstalled": False,
        "fixturesGenerated": False,
        "credentialsSupplied": False,
        "environmentPrerequisitesSupplied": False,
        "codebaseMutationAuthorized": False,
        "outputBoundary": str(package_dir),
        "result": status,
    }
    artifact_scan = {
        "packageId": PACKAGE_ID,
        "scope": "Codebase compared to WP-I0-001 SHA-256 manifest before and after classification",
        "before": before,
        "after": after,
        "unchanged": unchanged,
        "generatedOrInstalledInsideCodebase": [],
        "result": status,
    }
    evidence_files = [
        "13-implementation/WP-I0-008/artifact-scan.json",
        "13-implementation/WP-I0-008/authoring-incident.md",
        "13-implementation/WP-I0-008/completion-evidence.md",
        "13-implementation/WP-I0-008/evidence-consistency.json",
        "13-implementation/WP-I0-008/missing-prerequisite-classification.json",
        "13-implementation/WP-I0-008/package-summary.json",
        "13-implementation/WP-I0-008/provenance-report.json",
        "13-implementation/WP-I0-008/verification-report.json",
    ]
    summary = {
        "packageId": PACKAGE_ID,
        "status": status,
        "failures": failures,
        "collectionWindowUtc": {"start": started.isoformat(), "end": ended.isoformat()},
        "checks": {
            "classification": status,
            "focused": verification["checks"]["missingObservationCompleteness"],
            "negative": verification["checks"]["negativeFixtures"],
            "regression": verification["checks"]["codebaseUnchangedDuringCollection"],
            "artifactScan": artifact_scan["result"],
            "evidenceConsistency": consistency["result"],
            "exitGate": status,
        },
        "counts": classification_document["counts"],
        "evidenceFiles": evidence_files,
        "exitGateClauses": [
            {
                "clause": "Every missing prerequisite observed by completed read-only I0 inspection is classified",
                "evidence": f"{oracle['includedMissingRows']} toolchain missing-observation rows and all {oracle['nonSuccessAttempts']} non-success baseline attempts reconcile to {len(classifications)} deduplicated typed records.",
                "result": oracle["result"],
            },
            {
                "clause": "Every record names evidence, affected packages, blocking effect, and REVIEW_REQUIRED or BLOCKED status",
                "evidence": f"All {len(classifications)} records satisfy the required fields and status vocabulary.",
                "result": consistency["result"],
            },
            {
                "clause": "No missing item is generated, installed, supplied, or written into Codebase",
                "evidence": f"All {len(classifications)} supply actions are NOT_PERFORMED; {len(before_snapshot)} Codebase files match the authoritative manifest before and after.",
                "result": "PASS" if unchanged and supply_counts == {"NOT_PERFORMED": len(classifications)} else "FAIL",
            },
        ],
    }
    completion = f"""# WP-I0-008 completion evidence

- Requirement: `{REQUIREMENT_ID}`.
- Result: **{status}**.
- Classified records: {len(classifications)}.
- Source reconciliation: {oracle['includedMissingRows']} missing toolchain rows included; {oracle['excludedNonMissingRows']} non-missing ambiguity/difference rows explicitly excluded; {oracle['coveredNonSuccessAttempts']}/{oracle['nonSuccessAttempts']} non-success baseline attempts covered.
- Statuses: {dict(sorted(status_counts.items()))}.
- Categories: {dict(sorted(category_counts.items()))}; zero-observation categories remain explicit in the JSON count map.
- Supply actions: {dict(sorted(supply_counts.items()))}; no fixture, generated artifact, dependency, credential, or environment prerequisite was supplied.
- Preservation: {len(before_snapshot)} Codebase files matched the WP-I0-001 SHA-256 manifest before and after; no reparse point or content change was observed.
- Negative fixtures: {sum(row['result'] == 'PASS' for row in fixtures)}/{len(fixtures)} PASS.
- Authoring cleanup: the initial syntax check created only the package-local `__pycache__/collect_evidence.cpython-311.pyc`; that exact file and now-empty directory were removed before the final collection and are retained as an incident record.

## Exit gate

Every observed missing prerequisite has typed category, evidence, affected package context, blocking effect, and `REVIEW_REQUIRED` or `BLOCKED` status. Evidence was produced only under `graphify/13-implementation/WP-I0-008/`.
"""

    outputs = {
        package_dir / "missing-prerequisite-classification.json": json_bytes(classification_document),
        package_dir / "verification-report.json": json_bytes(verification),
        package_dir / "evidence-consistency.json": json_bytes(consistency),
        package_dir / "provenance-report.json": json_bytes(provenance),
        package_dir / "artifact-scan.json": json_bytes(artifact_scan),
        package_dir / "package-summary.json": json_bytes(summary),
        package_dir / "completion-evidence.md": completion.encode("utf-8"),
    }
    for path, content in outputs.items():
        atomic_write(path, content)
    print(json.dumps({"packageId": PACKAGE_ID, "status": status, "records": len(classifications), "fixtures": len(fixtures)}))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except EvidenceError as exc:
        print(json.dumps({"status": "FAIL", "error": {"code": exc.code, "message": str(exc)}}), file=sys.stderr)
        raise SystemExit(2)
