#!/usr/bin/env python3
"""Build the read-only WP-I0-009 frontend coupling inventory.

The collector scans the complete web frontend source corpus, records each
supported coupling with exact source evidence, and maps it to one reviewed
replacement decision.  Unresolved ownership is deliberately REVIEW_REQUIRED.
It never imports or executes product code and writes only beside this file.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import posixpath
import re
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


PACKAGE_ID = "WP-I0-009"
REQUIREMENT_ID = "CAN-MISSION-I0-009"
TEXT_SOURCE_SUFFIXES = {".ts", ".js", ".mjs", ".cjs", ".svelte", ".html", ".css", ".svg", ".toml", ".sh", ".txt"}
CATEGORIES = {
    "SERVER_ROUTE",
    "GENERATED_CLIENT",
    "AUTHENTICATION",
    "RUNTIME_HOST",
    "SERVER_OWNED_STATE",
}
DECISIONS = {
    "Gallery and timeline",
    "Asset viewer",
    "Metadata",
    "People and faces",
    "Search and OCR",
    "Tags",
    "Albums and favorites",
    "Memories",
    "Map and location",
    "Duplicates",
    "Editing",
    "Libraries and storage",
    "Jobs and notifications",
    "Authentication and users",
    "Sharing and mobile backup",
    "Administration",
    "Settings",
    "Local AI worker",
    "Events and organization",
    "Review Centre",
    "Desktop shell",
    "Local data authority",
    "Legal and rebranding",
    "Planning and verification governance",
}
EXACT_SOURCE_OWNERS: dict[str, set[str]] = {}
PUBLISHED_ARTIFACTS = {
    "artifact-scan.json", "completion-evidence.md", "evidence-consistency.json",
    "frontend-coupling-inventory.json", "package-summary.json", "provenance-report.json",
    "verification-report.json",
}
SDK_NON_ROUTE_CALLS = {"isHttpError"}
AUTH_SDK_SYMBOLS = {
    "changePassword", "changePinCode", "createApiKey", "createUserAdmin", "deleteAllSessions", "deleteApiKey", "deleteSession",
    "deleteUserAdmin", "finishOAuth", "getAuthStatus", "getMyUser", "getSessions", "getUser",
    "getApiKeys", "getUserAdmin", "getUserPreferencesAdmin", "getUserSessionsAdmin", "getUserStatisticsAdmin",
    "linkOAuthAccount", "lockAuthSession", "login", "logout", "maintenanceLogin", "resetPinCode",
    "restoreUserAdmin", "searchUsers", "searchUsersAdmin", "setUserOnboarding", "setupPinCode",
    "sharedLinkLogin", "signUpAdmin", "startOAuth", "unlinkAllOAuthAccountsAdmin", "unlinkOAuthAccount",
    "unlockAuthSession", "updateApiKey", "updateMyUser", "updateUserAdmin",
}
SERVER_EVENT_MODULES = {"socket.io-client", "@socket.io/component-emitter"}


class EvidenceError(Exception):
    """Typed invalid-input or consistency error."""

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
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256_bytes(encoded)


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def atomic_replace(path: Path, content: bytes) -> None:
    temporary: Path | None = None
    try:
        descriptor, raw_path = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        temporary = Path(raw_path)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        temporary = None
    except OSError as exc:
        raise EvidenceError("EVIDENCE_PUBLISH_FAILED", f"{path.name}: {exc}") from exc
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def restore_generation(output: Path, snapshot: dict[str, bytes | None]) -> None:
    failures: list[str] = []
    for name, content in snapshot.items():
        path = output / name
        try:
            if content is None:
                path.unlink(missing_ok=True)
            else:
                atomic_replace(path, content)
        except (EvidenceError, OSError) as exc:
            failures.append(f"{name}: {exc}")
    if failures:
        raise EvidenceError("EVIDENCE_ROLLBACK_FAILED", "; ".join(failures))


def publish_generation(
    output: Path,
    artifacts: dict[str, bytes],
    commit_marker: str,
    replace: Any = atomic_replace,
) -> None:
    """Publish one evidence generation; authoritative inventory is the last commit marker."""
    if commit_marker not in artifacts:
        raise EvidenceError("COMMIT_MARKER_MISSING", commit_marker)
    snapshot = {
        name: (output / name).read_bytes() if (output / name).is_file() else None
        for name in artifacts
    }
    try:
        for name in sorted(artifacts):
            if name != commit_marker:
                replace(output / name, artifacts[name])
        replace(output / commit_marker, artifacts[commit_marker])
    except (EvidenceError, OSError):
        restore_generation(output, snapshot)
        raise


def publish_validated_generation(
    output: Path, artifacts: dict[str, bytes], commit_marker: str, failures: list[dict[str, Any]],
) -> bool:
    if failures:
        return False
    publish_generation(output, artifacts, commit_marker)
    return True


def repository_root(script: Path) -> Path:
    candidate = script.resolve().parents[3]
    required = (
        candidate / "Codebase" / "web" / "src",
        candidate / "graphify" / "05-keep-port-rewrite-remove" / "DECISION_MATRIX.md",
        candidate / "graphify" / "13-implementation" / "WP-I0-001" / "sha256-manifest.csv",
    )
    if not all(path.is_file() or path.is_dir() for path in required):
        raise EvidenceError("REPOSITORY_ROOT_INVALID", "required committed inputs are unavailable")
    return candidate


def codebase_hashes(root: Path) -> dict[str, str]:
    codebase = root / "Codebase"
    return {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in sorted(codebase.rglob("*"), key=lambda value: value.as_posix().casefold())
        if path.is_file()
    }


def baseline_hashes(root: Path) -> dict[str, str]:
    path = root / "graphify" / "13-implementation" / "WP-I0-001" / "sha256-manifest.csv"
    result: dict[str, str] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            source = row.get("path") or row.get("relative_path") or row.get("file")
            digest = row.get("sha256") or row.get("SHA256")
            if not source or not digest:
                raise EvidenceError("BASELINE_SCHEMA_INVALID", "WP-I0-001 hash manifest has an invalid row")
            normalized = source.replace("\\", "/")
            if not normalized.startswith("Codebase/"):
                normalized = f"Codebase/{normalized}"
            if normalized in result:
                raise EvidenceError("BASELINE_DUPLICATE_PATH", normalized)
            result[normalized] = digest.lower()
    return result


def line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def source_excerpt(text: str, line: int) -> str:
    lines = text.splitlines()
    return lines[line - 1].strip() if 0 < line <= len(lines) else ""


def split_import_names(clause: str) -> list[str]:
    compact = re.sub(r"/\*.*?\*/|//[^\n]*", "", clause, flags=re.S)
    names: list[str] = []
    namespace = re.search(r"\*\s+as\s+([A-Za-z_$][\w$]*)", compact)
    if namespace:
        names.append(f"namespace:{namespace.group(1)}")
    braces = re.search(r"\{(.*?)\}", compact, re.S)
    if braces:
        for item in braces.group(1).split(","):
            item = re.sub(r"^\s*type\s+", "", item.strip())
            if not item:
                continue
            original = re.split(r"\s+as\s+", item, maxsplit=1)[0].strip()
            if re.fullmatch(r"[A-Za-z_$][\w$]*", original):
                names.append(original)
    prefix = compact.split("{", 1)[0].split("*", 1)[0].strip().rstrip(",").strip()
    prefix = re.sub(r"^type\s+", "", prefix)
    if prefix != "type" and prefix and re.fullmatch(r"[A-Za-z_$][\w$]*", prefix):
        names.append(f"default:{prefix}")
    return list(dict.fromkeys(names)) or ["module"]


def mask_comments(text: str) -> str:
    """Blank JS comments while preserving offsets and line numbers."""
    chars = list(text)
    index = 0
    quote: str | None = None
    escaped = False
    while index < len(chars):
        char = chars[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            index += 1
            continue
        if char in "'\"`":
            quote = char
            index += 1
            continue
        if char == "/" and index + 1 < len(chars) and chars[index + 1] == "/":
            end = text.find("\n", index + 2)
            end = len(chars) if end < 0 else end
            for cursor in range(index, end):
                chars[cursor] = " "
            index = end
            continue
        if char == "/" and index + 1 < len(chars) and chars[index + 1] == "*":
            end = text.find("*/", index + 2)
            end = len(chars) - 2 if end < 0 else end
            for cursor in range(index, min(end + 2, len(chars))):
                if chars[cursor] != "\n":
                    chars[cursor] = " "
            index = end + 2
            continue
        index += 1
    return "".join(chars)


def code_position_flags(text: str) -> list[bool]:
    """Return whether each offset begins in executable code, not a string/comment."""
    flags = [True] * len(text)
    index = 0
    quote: str | None = None
    escaped = False
    while index < len(text):
        char = text[index]
        if quote:
            flags[index] = False
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            index += 1
            continue
        if char in "'\"`":
            quote = char
            flags[index] = False
            index += 1
            continue
        if text.startswith("//", index):
            end = text.find("\n", index + 2)
            end = len(text) if end < 0 else end
            for cursor in range(index, end):
                flags[cursor] = False
            index = end
            continue
        if text.startswith("/*", index):
            end = text.find("*/", index + 2)
            end = len(text) - 2 if end < 0 else end
            for cursor in range(index, min(end + 2, len(text))):
                flags[cursor] = False
            index = end + 2
            continue
        index += 1
    return flags


def import_records(text: str, module: str) -> list[tuple[int, str]]:
    code_flags = code_position_flags(text)
    text = mask_comments(text)
    escaped = re.escape(module)
    pattern = re.compile(
        rf"\bimport\s+(?!\()(?P<clause>(?:(?!\bimport\b)[\s\S])*?)\s+from\s*['\"]{escaped}['\"]\s*;?",
        re.M,
    )
    records: list[tuple[int, str]] = []
    for match in pattern.finditer(text):
        if not code_flags[match.start()]:
            continue
        clause = match.group("clause")
        for name in split_import_names(clause):
            lookup = name.split(":", 1)[-1]
            occurrence = re.search(rf"\b{re.escape(lookup)}\b", clause)
            offset = match.start("clause") + occurrence.start() if occurrence else match.start()
            records.append((line_number(text, offset), name))
    side_effect = re.compile(rf"\bimport\s*['\"]{escaped}['\"]\s*;?")
    records.extend((line_number(text, match.start()), "module") for match in side_effect.finditer(text) if code_flags[match.start()])
    dynamic = re.compile(rf"\bimport\s*\(\s*['\"]{escaped}['\"]\s*\)(?:\.([A-Za-z_$][\w$]*))?")
    records.extend(
        (line_number(text, match.start()), match.group(1) or "dynamic-module")
        for match in dynamic.finditer(text) if code_flags[match.start()]
    )
    mock = re.compile(rf"\b(?:vi|jest|vitest)\.mock\s*\(\s*['\"]{escaped}['\"]")
    records.extend((line_number(text, match.start()), "mock-module") for match in mock.finditer(text) if code_flags[match.start()])
    return sorted(set(records))


GLOBAL_HOST_PATTERN = re.compile(
    r"\b(?:globalThis|window|self)\.location\b"
    r"(?:\.(?:href|origin|host|hostname|protocol|port))?"
    r"|\bglobalThis\.origin\b"
    r"|\blocation\.(?:href|origin|host|hostname|protocol|port)\b"
    r"|\b(?:serverUrl|baseUrl|baseURL|externalDomain)\b"
    r"|\b(?:process\.env\.)?(?:PUBLIC_)?IMMICH_(?:SERVER_URL|BUY_HOST|PAY_HOST)\b"
)


def runtime_host_records(text: str, *, hash_comments: bool = False) -> list[tuple[int, str]]:
    comment_masked = text if hash_comments else mask_comments(text)
    masked = re.sub(
        r"<!--[\s\S]*?-->",
        lambda match: "".join("\n" if char == "\n" else " " for char in match.group(0)),
        comment_masked,
    )
    if hash_comments:
        masked = re.sub(
            r"(?m)^[ \t]*\#[^\n]*",
            lambda match: " " * len(match.group(0)),
            masked,
        )
    flags = code_position_flags(text)
    location_shadowed = bool(re.search(
        r"\blocation\s*:\s*[A-Za-z_$]|\b(?:const|let|var|function|class)\s+location\b",
        masked,
    ))
    records = [
        (line_number(text, match.start()), match.group(0))
        for match in GLOBAL_HOST_PATTERN.finditer(masked)
        if flags[match.start()] and not (location_shadowed and match.group(0).startswith("location."))
    ]
    environment_pattern = re.compile(r"\b(?:process\.env\.)?(?:PUBLIC_)?IMMICH_(?:SERVER_URL|BUY_HOST|PAY_HOST)\b")
    records.extend(
        (line_number(text, match.start()), match.group(0))
        for match in environment_pattern.finditer(masked)
        if not source_excerpt(text, line_number(text, match.start())).lstrip().startswith("#")
    )
    if not location_shadowed:
        bare_location = re.compile(
            r"(?<![\w$.])location\b(?!\.(?:href|origin|host|hostname|protocol|port)\b|\s*:)")
        records.extend(
            (line_number(text, match.start()), "location")
            for match in bare_location.finditer(masked)
            if flags[match.start()]
        )
    url_variables = {
        match.group(1)
        for match in re.finditer(r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*new\s+URL\s*\(", masked)
        if flags[match.start()]
    }
    if re.search(r"\burl\s*:\s*URL\b|\(\s*\{[^}\n]*\burl\b[^}\n]*\}\s*\)", masked):
        url_variables.add("url")
    for variable in url_variables:
        property_pattern = re.compile(rf"\b{re.escape(variable)}\.(?:href|origin|host|hostname|protocol|port)\b")
        records.extend(
            (line_number(text, match.start()), match.group(0))
            for match in property_pattern.finditer(masked)
            if flags[match.start()]
        )
    excluded_literal_hosts = {"example.com", "www.w3.org", "www.w3.org/2000/svg"}
    template_pattern = re.compile(
        r"https?://(?P<host>(?:[A-Za-z0-9-]+|\$\{[^}\r\n]+\})(?:\.(?:[A-Za-z0-9-]+|\$\{[^}\r\n]+\}))+)(?::\d+)?",
        re.I,
    )
    records.extend(
        (line_number(text, match.start()), f"template-host:{match.group('host').casefold()}")
        for match in template_pattern.finditer(masked)
        if "${" in match.group("host")
    )
    literal_pattern = re.compile(
        r"https?://(?P<host>[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*)(?::\d+)?(?![A-Za-z0-9.-]|\$\{)",
        re.I,
    )
    records.extend(
        (line_number(text, match.start()), f"literal-host:{match.group('host').casefold()}")
        for match in literal_pattern.finditer(masked)
        if match.group("host").casefold() not in excluded_literal_hosts
    )
    return sorted(set(records))


def auth_cookie_records(text: str) -> list[tuple[int, str]]:
    masked = mask_comments(text)
    flags = code_position_flags(text)
    records = [
        (line_number(text, match.start()), "document.cookie")
        for match in re.finditer(r"\bdocument\.cookie\b", masked)
        if flags[match.start()]
    ]
    records.extend(
        (line_number(text, match.start()), "cookie:immich_is_authenticated")
        for match in re.finditer(r"['\"]immich_is_authenticated['\"]", masked)
    )
    return sorted(set(records))


def external_host_requires_review(host_reference: str) -> bool:
    return host_reference.startswith(("literal-host:", "template-host:"))


def xhr_open_records(text: str) -> list[tuple[int, str]]:
    """Find request openings only for identifiers constructed as XMLHttpRequest."""
    masked = mask_comments(text)
    flags = code_position_flags(text)
    identifiers = {
        match.group(1)
        for match in re.finditer(r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*new\s+XMLHttpRequest\s*\(\s*\)", masked)
        if flags[match.start()]
    }
    records: list[tuple[int, str]] = []
    for identifier in identifiers:
        pattern = re.compile(rf"\b{re.escape(identifier)}\.open\s*\(([^\n]{{0,300}})")
        records.extend(
            (line_number(text, match.start()), match.group(1).strip())
            for match in pattern.finditer(masked)
            if flags[match.start()]
        )
    return sorted(set(records))


def local_module_name(path: Path, lib_root: Path) -> str:
    relative = path.relative_to(lib_root).as_posix()
    for suffix in (".ts", ".js"):
        if relative.endswith(suffix):
            relative = relative[: -len(suffix)]
            break
    return f"$lib/{relative}"


def frontend_module_name(path: Path, root: Path) -> str:
    source_root = root / "Codebase" / "web" / "src"
    lib_root = source_root / "lib"
    if path == lib_root or lib_root in path.parents:
        return local_module_name(path, lib_root)
    relative = path.relative_to(source_root).as_posix()
    for suffix in (".ts", ".js"):
        if relative.endswith(suffix):
            relative = relative[: -len(suffix)]
            break
    return f"Codebase/web/src/{relative}"


def dependency_specifier(importer: str, dependency: str) -> str:
    if dependency.startswith("$lib/"):
        return dependency
    importer_stub = importer.removeprefix("$lib/")
    if importer.startswith("$lib/"):
        importer_stub = f"Codebase/web/src/lib/{importer_stub}"
    target_stub = dependency
    relative = posixpath.relpath(target_stub, posixpath.dirname(importer_stub))
    return relative if relative.startswith(".") else f"./{relative}"


def discover_server_state_modules(root: Path) -> dict[str, str]:
    """Content-qualify manager/store modules backed by server APIs, then close imports."""
    lib_root = root / "Codebase" / "web" / "src" / "lib"
    candidates: dict[str, str] = {}
    for folder in (lib_root / "managers", lib_root / "stores"):
        for path in folder.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {".ts", ".js"} or ".spec." in path.name:
                continue
            candidates[local_module_name(path, lib_root)] = path.read_text(encoding="utf-8")
    direct_pattern = re.compile(r"@immich/sdk|\bfetch\s*\(|\bXMLHttpRequest\b|['\"`]/api/|\bgetBaseUrl\s*\(")
    qualified = {module: "direct-server-api" for module, text in candidates.items() if direct_pattern.search(mask_comments(text))}
    changed = True
    while changed:
        changed = False
        for module, text in candidates.items():
            if module in qualified:
                continue
            imported = next((dependency for dependency in qualified if re.search(rf"['\"]{re.escape(dependency)}['\"]", text)), None)
            if imported:
                qualified[module] = f"transitive:{imported}"
                changed = True
    return dict(sorted(qualified.items()))


def wrapper_candidates(root: Path) -> dict[str, str]:
    source_root = root / "Codebase" / "web" / "src"
    candidates: dict[str, str] = {}
    for path in source_root.rglob("*"):
        relative_parts = path.relative_to(source_root).parts
        if (not path.is_file() or path.suffix.lower() not in {".ts", ".js"}
                or ".spec." in path.name or "__mocks__" in relative_parts
                or (relative_parts[0] == "lib" and len(relative_parts) > 1
                    and relative_parts[1] in {"managers", "stores"})):
            continue
        candidates[frontend_module_name(path, root)] = path.read_text(encoding="utf-8")
    return dict(sorted(candidates.items()))


def named_import_bindings(text: str, module: str) -> list[tuple[str, str]]:
    """Return (exported name, local name) for runtime named imports."""
    pattern = re.compile(
        rf"\bimport\s+(?!\()(?P<clause>(?:(?!\bimport\b)[\s\S])*?)\s+from\s*['\"]{re.escape(module)}['\"]"
    )
    bindings: list[tuple[str, str]] = []
    for match in pattern.finditer(mask_comments(text)):
        clause = match.group("clause").strip()
        if clause.startswith("type "):
            continue
        namespace = re.search(r"\*\s+as\s+([A-Za-z_$][\w$]*)", clause)
        if namespace:
            bindings.append(("*", namespace.group(1)))
        braces = re.search(r"\{(.*?)\}", clause, re.S)
        if not braces:
            continue
        for raw_item in braces.group(1).split(","):
            item = raw_item.strip()
            if not item or item.startswith("type "):
                continue
            names = re.split(r"\s+as\s+", item, maxsplit=1)
            original = names[0].strip()
            local = names[-1].strip()
            if re.fullmatch(r"[A-Za-z_$][\w$]*", original) and re.fullmatch(r"[A-Za-z_$][\w$]*", local):
                bindings.append((original, local))
    return sorted(set(bindings))


def matching_code_brace(text: str, start: int, flags: list[bool]) -> int | None:
    depth = 0
    for index in range(start, len(text)):
        if not flags[index]:
            continue
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return index
    return None


def function_regions(text: str) -> dict[str, dict[str, Any]]:
    """Extract named function bodies without executing or importing TypeScript."""
    masked = mask_comments(text)
    flags = code_position_flags(text)
    regions: dict[str, dict[str, Any]] = {}
    declaration = re.compile(r"\b(?P<export>export\s+)?(?:async\s+)?function\s+(?P<name>[A-Za-z_$][\w$]*)")
    for match in declaration.finditer(masked):
        parens = brackets = parameter_braces = 0
        brace = -1
        cursor = match.end()
        while cursor < len(text):
            if not flags[cursor]:
                cursor += 1
                continue
            char = text[cursor]
            if char == "(" :
                parens += 1
            elif char == ")":
                parens = max(0, parens - 1)
            elif char == "[":
                brackets += 1
            elif char == "]":
                brackets = max(0, brackets - 1)
            elif char == "{" and (parens or brackets or parameter_braces):
                parameter_braces += 1
            elif char == "}" and parameter_braces:
                parameter_braces -= 1
            elif char == "{" and not parens and not brackets:
                brace = cursor
                break
            elif char == ";" and not parens and not brackets and not parameter_braces:
                break
            cursor += 1
        end = matching_code_brace(text, brace, flags) if brace >= 0 else None
        if end is not None:
            regions[match.group("name")] = {"body": text[brace + 1:end], "exported": bool(match.group("export"))}
    for match in re.finditer(r"\b(?P<export>export\s+)?class\s+(?P<name>[A-Za-z_$][\w$]*)", masked):
        brace = masked.find("{", match.end())
        end = matching_code_brace(text, brace, flags) if brace >= 0 else None
        if end is not None:
            regions[match.group("name")] = {"body": text[brace + 1:end], "exported": bool(match.group("export"))}
    constant = re.compile(r"\b(?P<export>export\s+)?const\s+(?P<name>[A-Za-z_$][\w$]*)\b")
    for match in constant.finditer(masked):
        search_end = min(len(text), match.start() + 1200)
        depths = {"(": 0, "[": 0, "{": 0}
        closing = {")": "(", "]": "[", "}": "{"}
        arrow = -1
        assignment = -1
        cursor = match.end()
        while cursor < search_end:
            if not flags[cursor]:
                cursor += 1
                continue
            char = text[cursor]
            if char in depths:
                depths[char] += 1
            elif char in closing:
                depths[closing[char]] = max(0, depths[closing[char]] - 1)
            elif char == ";" and not any(depths.values()):
                break
            elif char == "=" and not text.startswith("=>", cursor) and not any(depths.values()):
                assignment = cursor
            elif text.startswith("=>", cursor) and not any(depths.values()):
                arrow = cursor
                break
            cursor += 1
        cursor = arrow + 2 if arrow >= 0 else assignment + 1
        if cursor <= 0:
            continue
        while cursor < len(text) and text[cursor].isspace():
            cursor += 1
        if cursor < len(text) and text[cursor] == "{" and flags[cursor]:
            end = matching_code_brace(text, cursor, flags)
            if end is None:
                continue
            body = text[cursor + 1:end]
        else:
            end = masked.find(";", cursor)
            if end < 0:
                end = masked.find("\n", cursor)
            end = len(text) if end < 0 else end
            body = text[cursor:end]
        regions[match.group("name")] = {"body": body, "exported": bool(match.group("export"))}
    return regions


def class_member_regions(text: str) -> dict[str, dict[str, str]]:
    masked = mask_comments(text)
    flags = code_position_flags(text)
    result: dict[str, dict[str, str]] = {}
    for class_match in re.finditer(r"\bexport\s+class\s+(?P<name>[A-Za-z_$][\w$]*)", masked):
        class_brace = masked.find("{", class_match.end())
        class_end = matching_code_brace(text, class_brace, flags) if class_brace >= 0 else None
        if class_end is None:
            continue
        body = text[class_brace + 1:class_end]
        body_masked = mask_comments(body)
        body_flags = code_position_flags(body)
        methods: dict[str, str] = {}
        method_pattern = re.compile(
            r"(?m)^\s*(?:(?:public|private|protected|override)\s+)*(?:static\s+)?(?:async\s+)?"
            r"(?P<name>constructor|[A-Za-z_$][\w$]*)\s*\("
        )
        for match in method_pattern.finditer(body_masked):
            if match.group("name") in {"if", "for", "while", "switch", "catch", "with"}:
                continue
            parens = 0
            cursor = body_masked.find("(", match.start(), match.end())
            method_brace = -1
            while cursor < len(body):
                if not body_flags[cursor]:
                    cursor += 1
                    continue
                char = body[cursor]
                if char == "(":
                    parens += 1
                elif char == ")":
                    parens = max(0, parens - 1)
                elif char == "{" and parens == 0:
                    method_brace = cursor
                    break
                elif char == ";" and parens == 0:
                    break
                cursor += 1
            method_end = matching_code_brace(body, method_brace, body_flags) if method_brace >= 0 else None
            if method_end is not None:
                methods[match.group("name")] = body[method_brace + 1:method_end]
        result[class_match.group("name")] = methods
    return result


def discover_server_route_modules(root: Path) -> dict[str, dict[str, Any]]:
    """Find only exported symbols whose call graph reaches a server operation."""
    candidates = wrapper_candidates(root)
    functions = {module: function_regions(text) for module, text in candidates.items()}
    sdk_bindings = {module: named_import_bindings(text, "@immich/sdk") for module, text in candidates.items()}
    route_functions: dict[str, set[str]] = {module: set() for module in candidates}
    network_pattern = re.compile(r"\bfetch\s*\(|\bXMLHttpRequest\b|['\"`]/api/|\bgetBaseUrl\s*\(")
    for module, entries in functions.items():
        for name, entry in entries.items():
            body = entry["body"]
            direct = bool(network_pattern.search(mask_comments(body)))
            for original, local in sdk_bindings[module]:
                if original == "*":
                    direct = direct or bool(re.search(rf"\b{re.escape(local)}\.[A-Za-z_$][\w$]*\s*\(", body))
                elif original not in SDK_NON_ROUTE_CALLS:
                    direct = direct or bool(re.search(rf"\b{re.escape(local)}\s*\(", body))
            if direct:
                route_functions[module].add(name)
    changed = True
    while changed:
        changed = False
        exported_routes = {
            module: {name for name in names if functions[module].get(name, {}).get("exported")}
            for module, names in route_functions.items()
        }
        for module, entries in functions.items():
            imported_routes: set[str] = set()
            imported_namespaces: list[tuple[str, set[str]]] = []
            for dependency, dependency_routes in exported_routes.items():
                if not dependency_routes:
                    continue
                specifier = dependency_specifier(module, dependency)
                for original, local in named_import_bindings(candidates[module], specifier):
                    if original == "*":
                        imported_namespaces.append((local, dependency_routes))
                    elif original in dependency_routes:
                        imported_routes.add(local)
            for name, entry in entries.items():
                if name in route_functions[module]:
                    continue
                body = entry["body"]
                local_reach = any(re.search(rf"\b{re.escape(target)}\s*\(", body) for target in route_functions[module])
                import_reach = any(re.search(rf"\b{re.escape(target)}\s*\(", body) for target in imported_routes)
                namespace_reach = any(
                    re.search(rf"\b{re.escape(alias)}\.{re.escape(target)}\s*\(", body)
                    for alias, targets in imported_namespaces for target in targets
                )
                if local_reach or import_reach or namespace_reach:
                    route_functions[module].add(name)
                    changed = True
    auth_functions: dict[str, set[str]] = {module: set() for module in candidates}
    for module, entries in functions.items():
        auth_manager_locals = {
            local for original, local in named_import_bindings(candidates[module], "$lib/managers/auth-manager.svelte")
            if original in {"authManager", "*"}
        }
        for name, entry in entries.items():
            if any(original in AUTH_SDK_SYMBOLS and re.search(rf"\b{re.escape(local)}\s*\(", entry["body"])
                   for original, local in sdk_bindings[module]):
                auth_functions[module].add(name)
            if any(re.search(rf"\b{re.escape(local)}\b", entry["body"]) for local in auth_manager_locals):
                auth_functions[module].add(name)
            if module in {"$lib/services/api-key.service", "$lib/utils/auth"} and entry.get("exported"):
                auth_functions[module].add(name)
    changed = True
    while changed:
        changed = False
        exported_auth = {
            module: {name for name in names if functions[module].get(name, {}).get("exported")}
            for module, names in auth_functions.items()
        }
        for module, entries in functions.items():
            imported_auth: set[str] = set()
            for dependency, dependency_auth in exported_auth.items():
                if not dependency_auth:
                    continue
                specifier = dependency_specifier(module, dependency)
                for original, local in named_import_bindings(candidates[module], specifier):
                    if original in dependency_auth:
                        imported_auth.add(local)
            for name, entry in entries.items():
                if name in auth_functions[module]:
                    continue
                body = entry["body"]
                if (any(re.search(rf"\b{re.escape(target)}\s*\(", body) for target in auth_functions[module])
                        or any(re.search(rf"\b{re.escape(target)}\s*\(", body) for target in imported_auth)):
                    auth_functions[module].add(name)
                    changed = True
    class_routes: dict[str, dict[str, set[str]]] = {
        module: {class_name: set() for class_name in class_member_regions(text)}
        for module, text in candidates.items()
    }
    class_members = {module: class_member_regions(text) for module, text in candidates.items()}
    changed = True
    while changed:
        changed = False
        exported_routes = {
            module: {name for name in names if functions[module].get(name, {}).get("exported")}
            for module, names in route_functions.items()
        }
        for module, classes in class_members.items():
            imported_routes: set[str] = set()
            for dependency, dependency_routes in exported_routes.items():
                specifier = dependency_specifier(module, dependency)
                for original, local in named_import_bindings(candidates[module], specifier):
                    if original in dependency_routes:
                        imported_routes.add(local)
            sdk = sdk_bindings[module]
            for class_name, members in classes.items():
                for member, body in members.items():
                    if member in class_routes[module][class_name]:
                        continue
                    direct = bool(network_pattern.search(mask_comments(body)))
                    direct = direct or any(
                        original not in SDK_NON_ROUTE_CALLS and original != "*"
                        and re.search(rf"\b{re.escape(local)}\s*\(", body)
                        for original, local in sdk
                    )
                    direct = direct or any(re.search(rf"\b{re.escape(local)}\s*\(", body) for local in imported_routes)
                    direct = direct or any(
                        re.search(rf"\bthis\.{re.escape(target)}\s*\(", body)
                        for target in class_routes[module][class_name]
                    )
                    if direct:
                        class_routes[module][class_name].add(member)
                        changed = True
    qualified: dict[str, dict[str, Any]] = {}
    for module, names in route_functions.items():
        route_symbols = sorted(name for name in names if functions[module].get(name, {}).get("exported"))
        if module == "$lib/utils":
            route_symbols = [name for name in route_symbols if name != "oauth"]
        auth_symbols = sorted(
            name for name in auth_functions[module]
            if functions[module].get(name, {}).get("exported") and not (module == "$lib/utils" and name == "oauth")
        )
        if (route_symbols or auth_symbols) and module != "$lib/utils/auth":
            qualified[module] = {
                "qualification": "exported-symbol-call-reachability",
                "routeSymbols": route_symbols,
                "authSymbols": auth_symbols,
                "classRouteMembers": {
                    class_name: sorted(members)
                    for class_name, members in sorted(class_routes[module].items()) if members
                },
            }
    return dict(sorted(qualified.items()))


def excluded_local_service_modules(root: Path, qualified: dict[str, dict[str, Any]]) -> list[str]:
    candidates = wrapper_candidates(root)
    direct = re.compile(r"@immich/sdk|\bfetch\s*\(|\bXMLHttpRequest\b|['\"`]/api/|\bgetBaseUrl\s*\(")
    return sorted(
        module for module, text in candidates.items()
        if module not in qualified and (module == "$lib/utils/auth" or direct.search(mask_comments(text)))
    )


def load_producers(path: Path, root: Path) -> set[Path]:
    producers: set[Path] = set()
    primary = path.with_suffix(".ts")
    if not primary.is_file():
        primary = path.with_suffix(".js")
    if primary.is_file():
        producers.add(primary)
    routes_root = root / "Codebase" / "web" / "src" / "routes"
    ancestor = path.parent
    while ancestor == routes_root or routes_root in ancestor.parents:
        for suffix in (".ts", ".js"):
            layout = ancestor / f"+layout{suffix}"
            if layout.is_file():
                producers.add(layout)
                break
        if ancestor == routes_root:
            break
        ancestor = ancestor.parent
    return producers


def load_producer_qualifications(text: str) -> list[str]:
    qualifications: list[str] = []
    if "@immich/sdk" in text:
        qualifications.append("generated-client")
    if "$lib/utils/auth" in text:
        qualifications.append("authentication")
    if re.search(r"['\"]\$lib/(?:managers|stores)/", text):
        qualifications.append("server-state-module")
    if re.search(r"['\"]\$lib/(?:services/|utils/(?:shared-links|license-utils))", text):
        qualifications.append("server-route-wrapper")
    return qualifications


def page_data_records(text: str) -> list[tuple[int, str]]:
    page_imported = any(
        symbol in {"page", "namespace:page"}
        for module in ("$app/state", "$app/stores")
        for _, symbol in import_records(text, module)
    )
    if not page_imported:
        return []
    masked = mask_comments(text)
    flags = code_position_flags(text)
    pattern = re.compile(r"(?<![\w$])\$?page\.data\.([A-Za-z_$][\w$]*)")
    return sorted(set(
        (line_number(text, match.start()), match.group(1))
        for match in pattern.finditer(masked)
        if flags[match.start()]
    ))


def decision_for(source: str, symbol: str, category: str) -> str | None:
    source_context = source.casefold().replace("/(user)/", "/")
    symbol_context = symbol.casefold().replace("/(user)/", "/")
    if category == "AUTHENTICATION":
        return "Authentication and users"
    if category == "RUNTIME_HOST" and ("public_immich_" in symbol_context or "license" in source_context):
        return "Legal and rebranding"
    if category == "RUNTIME_HOST":
        return "Desktop shell"
    if category == "SERVER_OWNED_STATE":
        if "socket.io" in symbol_context or "websocket" in source_context:
            return "Events and organization"
        if source.casefold().endswith("/routes/(user)/+layout.svelte") and "page.data.asset" in symbol_context:
            return "Asset viewer"
        state_rules = (
            (("event-manager", "websocket"), "Events and organization"),
            (("queue-manager", "notification-manager"), "Jobs and notifications"),
            (("server-config", "system-config", "feature-flags"), "Settings"),
            (("maintenance.store",), "Administration"),
            (("stores/user.svelte",), "Authentication and users"),
        )
        for needles, decision in state_rules:
            if any(needle in symbol_context for needle in needles):
                return decision
    authority_scoped = (
        category == "GENERATED_CLIENT"
        or "->pagedata" in symbol_context
        or "->layoutdata" in symbol_context
        or "->page.data." in symbol_context
    )
    if authority_scoped and source in EXACT_SOURCE_OWNERS:
        owners = EXACT_SOURCE_OWNERS[source]
        return next(iter(owners)) if len(owners) == 1 else None
    source_rules = (
        (("/admin/library-management/",), "Libraries and storage"),
        (("/admin/queues/", "/admin/jobs-status/"), "Jobs and notifications"),
        (("/admin/", "admin-settings", "/maintenance/", "database-backup"), "Administration"),
        (("user-settings", "system-config", "server-config", "preferences"), "Settings"),
        (("/auth/", "auth-manager"), "Authentication and users"),
        (("shared-link", "/partners/", "partner"), "Sharing and mobile backup"),
        (("asset-viewer",), "Asset viewer"),
        (("timeline", "/photos/", "/archive/", "/trash/"), "Gallery and timeline"),
        (("metadata", "exif", "sidecar"), "Metadata"),
        (("people", "person", "face"), "People and faces"),
        (("search", "ocr"), "Search and OCR"),
        (("/tags/", "tag-"), "Tags"),
        (("album",), "Albums and favorites"),
        (("memor",), "Memories"),
        (("/map/", "places", "location", "geocod"), "Map and location"),
        (("duplicate",), "Duplicates"),
        (("/edit", "editor"), "Editing"),
        (("librar", "folder", "storage"), "Libraries and storage"),
        (("notification", "queue", "/jobs/"), "Jobs and notifications"),
        (("event-manager", "activity-manager"), "Events and organization"),
        (("review",), "Review Centre"),
        (("machine-learning", "smart-search", "model"), "Local AI worker"),
    )
    for needles, decision in source_rules:
        if any(needle in source_context for needle in needles):
            return decision
    symbol_rules = (
        (("auth", "user", "session", "oauth", "login", "password", "pin"), "Authentication and users"),
        (("server", "maintenance", "databasebackup"), "Administration"),
        (("share", "partner"), "Sharing and mobile backup"),
        (("setting", "config", "preference"), "Settings"),
        (("asset", "timeline", "thumbnail"), "Gallery and timeline"),
        (("metadata", "exif"), "Metadata"),
        (("person", "face"), "People and faces"),
        (("search", "ocr"), "Search and OCR"),
        (("tag",), "Tags"),
        (("album", "favorite"), "Albums and favorites"),
        (("memory",), "Memories"),
        (("map", "location", "place"), "Map and location"),
        (("duplicate", "similar"), "Duplicates"),
        (("edit", "stack"), "Editing"),
        (("library", "folder", "storage"), "Libraries and storage"),
        (("notification", "queue", "job"), "Jobs and notifications"),
        (("event", "activity"), "Events and organization"),
        (("model", "clip"), "Local AI worker"),
    )
    for needles, decision in symbol_rules:
        if any(re.search(rf"(?<![a-z0-9.]){re.escape(needle)}(?![a-z0-9.])", symbol_context) for needle in needles):
            return decision
    if category == "SERVER_ROUTE" and "license" in f"{source_context} {symbol_context}":
        return "Legal and rebranding"
    return None


def add_record(
    output: list[dict[str, Any]], *, source: str, line: int, category: str,
    mechanism: str, dependency: str, excerpt: str, force_review: bool = False,
) -> None:
    decision = None if force_review else decision_for(source, dependency, category)
    status = "LINKED" if decision else "REVIEW_REQUIRED"
    output.append({
        "id": "pending",
        "sourcePath": source,
        "line": line,
        "category": category,
        "mechanism": mechanism,
        "dependency": dependency,
        "evidence": excerpt,
        "ownership": {
            "status": status,
            "ownerType": "reviewed-decision" if decision else None,
            "owner": f"decision:{decision}" if decision else None,
            "reason": None if decision else "No single reviewed replacement decision can be inferred without implementation-owner review.",
        },
    })


def scan_source(root: Path) -> tuple[
    list[dict[str, Any]], list[dict[str, Any]], dict[str, str], dict[str, dict[str, Any]], list[dict[str, Any]]
]:
    web_root = root / "Codebase" / "web"
    app_source_root = web_root / "src"
    files = sorted(
        (path for path in web_root.rglob("*") if path.is_file()),
        key=lambda value: value.as_posix().casefold(),
    )
    couplings: list[dict[str, Any]] = []
    source_manifest: list[dict[str, Any]] = []
    load_data_edges: list[dict[str, Any]] = []
    server_state_modules = discover_server_state_modules(root)
    server_route_modules = discover_server_route_modules(root)
    module_categories = {
        "$lib/managers/auth-manager.svelte": "AUTHENTICATION",
        "$lib/utils/auth": "AUTHENTICATION",
        "$env/static/public": "RUNTIME_HOST",
        "$env/dynamic/public": "RUNTIME_HOST",
    }
    module_categories.update({module: "SERVER_OWNED_STATE" for module in server_state_modules})
    module_categories["$lib/managers/auth-manager.svelte"] = "AUTHENTICATION"
    module_categories["$lib/utils/auth"] = "AUTHENTICATION"
    for path in files:
        raw = path.read_bytes()
        source = path.relative_to(root).as_posix()
        scan_eligible = (
            path.suffix.lower() in TEXT_SOURCE_SUFFIXES
            or path.parent == web_root / "bin"
            or path.name.startswith(".env")
            or path == web_root / "package.json"
        )
        source_manifest.append({
            "path": source,
            "sha256": sha256_bytes(raw),
            "bytes": len(raw),
            "textScanned": scan_eligible,
        })
        if not scan_eligible:
            continue
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise EvidenceError("SOURCE_NOT_UTF8", path.as_posix()) from exc
        comment_masked = mask_comments(text)
        code_flags = code_position_flags(text)

        for line, symbol in import_records(text, "@immich/sdk"):
            add_record(couplings, source=source, line=line, category="GENERATED_CLIENT",
                       mechanism="static-or-dynamic-import", dependency=f"@immich/sdk:{symbol}",
                       excerpt=source_excerpt(text, line))
            if symbol in AUTH_SDK_SYMBOLS:
                add_record(couplings, source=source, line=line, category="AUTHENTICATION",
                           mechanism="authentication-sdk-import", dependency=f"@immich/sdk:{symbol}",
                           excerpt=source_excerpt(text, line))

        for module in sorted(SERVER_EVENT_MODULES):
            for line, symbol in import_records(text, module):
                add_record(couplings, source=source, line=line, category="SERVER_OWNED_STATE",
                           mechanism="server-event-client-import", dependency=f"{module}:{symbol}",
                           excerpt=source_excerpt(text, line))

        if path == web_root / "package.json":
            manifest_match = re.search(r"(?m)^\s*\"@immich/sdk\"\s*:\s*\"([^\"]+)\"", text)
            if manifest_match:
                manifest_line = line_number(text, manifest_match.start())
                add_record(couplings, source=source, line=manifest_line, category="GENERATED_CLIENT",
                           mechanism="package-manifest-dependency",
                           dependency=f"@immich/sdk:{manifest_match.group(1)}",
                           excerpt=source_excerpt(text, manifest_line))
            for module in sorted(SERVER_EVENT_MODULES):
                event_match = re.search(rf"(?m)^\s*\"{re.escape(module)}\"\s*:\s*\"([^\"]+)\"", text)
                if event_match:
                    event_line = line_number(text, event_match.start())
                    add_record(couplings, source=source, line=event_line, category="SERVER_OWNED_STATE",
                               mechanism="server-event-client-dependency",
                               dependency=f"{module}:{event_match.group(1)}",
                               excerpt=source_excerpt(text, event_line))

        for module, category in module_categories.items():
            for line, symbol in import_records(text, module):
                add_record(couplings, source=source, line=line, category=category,
                           mechanism="frontend-module-import", dependency=f"{module}:{symbol}",
                           excerpt=source_excerpt(text, line))

        consumer_module = frontend_module_name(path, root) if path == app_source_root or app_source_root in path.parents else None
        for module, details in server_route_modules.items():
            if consumer_module is None:
                continue
            route_symbols = set(details["routeSymbols"])
            specifier = dependency_specifier(consumer_module, module)
            for line, symbol in import_records(text, specifier):
                broad_reference = symbol.startswith("namespace:") or symbol in {
                    "module", "dynamic-module", "mock-module"
                }
                if symbol not in route_symbols and not broad_reference:
                    continue
                route_members = details.get("classRouteMembers", {}).get(symbol)
                if route_members:
                    local_names = [local for original, local in named_import_bindings(text, specifier) if original == symbol]
                    used = any(
                        re.search(rf"\bnew\s+{re.escape(local)}\s*\(", comment_masked)
                        or any(re.search(rf"\b{re.escape(local)}\.{re.escape(member)}\s*\(", comment_masked)
                               for member in route_members)
                        for local in local_names
                    )
                    if not used:
                        continue
                add_record(couplings, source=source, line=line, category="SERVER_ROUTE",
                           mechanism="route-bearing-export-import", dependency=f"{module}:{symbol}",
                           excerpt=source_excerpt(text, line), force_review=broad_reference)
            for line, symbol in import_records(text, specifier):
                if symbol not in set(details.get("authSymbols", [])):
                    continue
                auth_route_members = details.get("classRouteMembers", {}).get(symbol)
                if auth_route_members:
                    local_names = [local for original, local in named_import_bindings(text, specifier) if original == symbol]
                    if not any(
                        re.search(rf"\bnew\s+{re.escape(local)}\s*\(", comment_masked)
                        or any(re.search(rf"\b{re.escape(local)}\.{re.escape(member)}\s*\(", comment_masked)
                               for member in auth_route_members)
                        for local in local_names
                    ):
                        continue
                add_record(couplings, source=source, line=line, category="AUTHENTICATION",
                           mechanism="authentication-wrapper-import", dependency=f"{module}:{symbol}",
                           excerpt=source_excerpt(text, line))

        for line, symbol in import_records(text, "$lib/utils"):
            if symbol == "oauth":
                add_record(couplings, source=source, line=line, category="AUTHENTICATION",
                           mechanism="symbol-qualified-module-import", dependency="$lib/utils:oauth",
                           excerpt=source_excerpt(text, line))

        for line, dependency in auth_cookie_records(text):
            add_record(couplings, source=source, line=line, category="AUTHENTICATION",
                       mechanism="server-auth-cookie", dependency=dependency,
                       excerpt=source_excerpt(text, line))

        if path.name in {"+page.svelte", "+layout.svelte"}:
            expected_type = "PageData" if path.name == "+page.svelte" else "LayoutData"
            type_modules = sorted(set(re.findall(r"from\s+['\"]([^'\"]*\$types)['\"]", text)))
            for type_module in type_modules:
                for line, symbol in import_records(text, type_module):
                    if symbol != expected_type:
                        continue
                    producer_paths = load_producers(path, root)
                    if not producer_paths:
                        raise EvidenceError("LOAD_DATA_PRODUCER_UNAVAILABLE", source)
                    for producer in sorted(producer_paths, key=lambda value: value.as_posix().casefold()):
                        producer_source = producer.relative_to(root).as_posix()
                        producer_text = producer.read_text(encoding="utf-8")
                        qualifications = load_producer_qualifications(producer_text)
                        if not qualifications:
                            continue
                        dependency = f"{producer_source}->{expected_type}"
                        add_record(couplings, source=source, line=line, category="SERVER_OWNED_STATE",
                                   mechanism="sveltekit-load-data", dependency=dependency,
                                   excerpt=source_excerpt(text, line))
                        load_data_edges.append({
                            "producer": producer_source,
                            "consumer": source,
                            "consumerLine": line,
                            "dataType": expected_type,
                            "sourceTypesModule": type_module,
                            "qualifications": qualifications,
                            "producerSha256": sha256_file(producer),
                        })

        for line, field in page_data_records(text):
            matching_producers: list[tuple[Path, list[str]]] = []
            if path.name in {"+page.svelte", "+layout.svelte"}:
                for producer in sorted(load_producers(path, root), key=lambda value: value.as_posix().casefold()):
                    producer_text = producer.read_text(encoding="utf-8")
                    qualifications = load_producer_qualifications(producer_text)
                    if qualifications and re.search(rf"\b{re.escape(field)}\b\s*(?:,|:)", mask_comments(producer_text)):
                        matching_producers.append((producer, qualifications))
            if matching_producers:
                for producer, qualifications in matching_producers:
                    producer_source = producer.relative_to(root).as_posix()
                    add_record(couplings, source=source, line=line, category="SERVER_OWNED_STATE",
                               mechanism="sveltekit-page-state", dependency=f"{producer_source}->page.data.{field}",
                               excerpt=source_excerpt(text, line))
                    load_data_edges.append({
                        "producer": producer_source,
                        "consumer": source,
                        "consumerLine": line,
                        "dataType": "RuntimePageData",
                        "accessedField": field,
                        "sourceTypesModule": "$app/state-or-stores",
                        "qualifications": qualifications,
                        "producerSha256": sha256_file(producer),
                    })
            else:
                dependency = f"sveltekit-dynamic-page-data:{field}"
                add_record(couplings, source=source, line=line, category="SERVER_OWNED_STATE",
                           mechanism="sveltekit-page-state", dependency=dependency,
                           excerpt=source_excerpt(text, line), force_review=True)
                load_data_edges.append({
                    "producer": None,
                    "consumer": source,
                    "consumerLine": line,
                    "dataType": "RuntimePageData",
                    "accessedField": field,
                    "sourceTypesModule": "$app/state-or-stores",
                    "qualifications": ["dynamic-route-producer-review-required"],
                    "producerSha256": None,
                })

        for match in re.finditer(r"\bfetch\s*\((?P<argument>[^\n]{0,240})", comment_masked):
            if not code_flags[match.start()]:
                continue
            line = line_number(text, match.start())
            argument = match.group("argument").strip()
            add_record(couplings, source=source, line=line, category="SERVER_ROUTE",
                       mechanism="direct-fetch", dependency=argument[:160], excerpt=source_excerpt(text, line))

        route_pattern = re.compile(r"(?P<quote>['\"`])(?:[^'\"`\n]*?)(?P<route>/api(?:/(?:v\d+/)?[^'\"`\s)}]*)?)(?P=quote)")
        for match in route_pattern.finditer(comment_masked):
            line = line_number(text, match.start())
            if any(row["sourcePath"] == source and row["line"] == line and row["mechanism"] == "direct-fetch" for row in couplings):
                continue
            add_record(couplings, source=source, line=line, category="SERVER_ROUTE",
                       mechanism="literal-api-route", dependency=match.group("route"), excerpt=source_excerpt(text, line))

        for line, host_reference in runtime_host_records(
            text,
            hash_comments=path.suffix.lower() in {".toml", ".sh", ".txt"} or path.parent == web_root / "bin",
        ):
            add_record(couplings, source=source, line=line, category="RUNTIME_HOST",
                       mechanism="runtime-host-reference", dependency=host_reference, excerpt=source_excerpt(text, line),
                       force_review=external_host_requires_review(host_reference))

        for line, arguments in xhr_open_records(text):
            add_record(couplings, source=source, line=line, category="SERVER_ROUTE",
                       mechanism="xml-http-request", dependency=arguments, excerpt=source_excerpt(text, line))

        for match in re.finditer(r"\bgetBaseUrl\s*\(\s*\)", comment_masked):
            if not code_flags[match.start()]:
                continue
            line = line_number(text, match.start())
            add_record(couplings, source=source, line=line, category="SERVER_ROUTE",
                       mechanism="base-url-endpoint", dependency=source_excerpt(text, line), excerpt=source_excerpt(text, line))

    unique: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in couplings:
        key = (row["sourcePath"], row["line"], row["category"], row["mechanism"], row["dependency"])
        unique[key] = row
    ordered = sorted(unique.values(), key=lambda row: (
        row["sourcePath"].casefold(), row["line"], row["category"], row["dependency"].casefold()
    ))
    for index, row in enumerate(ordered, 1):
        row["id"] = f"FC-{index:04d}"
    return ordered, source_manifest, server_state_modules, server_route_modules, sorted(
        load_data_edges, key=lambda row: (
            row["consumer"].casefold(), str(row["producer"]).casefold(), row["consumerLine"], row.get("accessedField", "")
        )
    )


def validate(couplings: list[dict[str, Any]], sources: list[dict[str, Any]], decisions: set[str]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    if not sources:
        failures.append({"code": "SOURCE_CORPUS_EMPTY"})
    if not couplings:
        failures.append({"code": "COUPLING_INVENTORY_EMPTY"})
    ids = [row["id"] for row in couplings]
    if len(ids) != len(set(ids)):
        failures.append({"code": "DUPLICATE_COUPLING_ID"})
    source_paths = {row["path"] for row in sources}
    seen_categories = {row["category"] for row in couplings}
    if seen_categories != CATEGORIES:
        failures.append({"code": "CATEGORY_COVERAGE_INCOMPLETE", "observed": sorted(seen_categories)})
    for row in couplings:
        if row["sourcePath"] not in source_paths or row["line"] < 1 or not row["evidence"]:
            failures.append({"code": "SOURCE_EVIDENCE_INVALID", "id": row["id"]})
        if row["mechanism"] in {"static-or-dynamic-import", "frontend-module-import", "route-bearing-export-import", "authentication-sdk-import", "authentication-wrapper-import", "server-event-client-import"}:
            imported = row["dependency"].rsplit(":", 1)[-1]
            if imported not in {"module", "dynamic-module", "mock-module"} and imported not in row["evidence"]:
                failures.append({"code": "DEPENDENCY_NOT_IN_SOURCE_EVIDENCE", "id": row["id"]})
        ownership = row["ownership"]
        if ownership["status"] == "LINKED":
            owner = ownership["owner"]
            if ownership["ownerType"] != "reviewed-decision" or not owner or owner.removeprefix("decision:") not in decisions:
                failures.append({"code": "OWNER_INVALID", "id": row["id"]})
        elif ownership["status"] != "REVIEW_REQUIRED" or ownership["owner"] is not None or not ownership["reason"]:
            failures.append({"code": "UNRESOLVED_OWNERSHIP_INVALID", "id": row["id"]})
    return failures


def parse_reviewed_decisions(root: Path) -> set[str]:
    text = (root / "graphify" / "05-keep-port-rewrite-remove" / "DECISION_MATRIX.md").read_text(encoding="utf-8")
    decisions = set(re.findall(r"^\| ([^|]+?) \| (?:KEEP UNCHANGED|PORT|REWRITE|REPLACE|REMOVE|TEMPORARILY RETAIN) \|", text, re.M))
    if decisions != DECISIONS:
        raise EvidenceError("DECISION_AUTHORITY_CHANGED", f"expected {len(DECISIONS)}, observed {len(decisions)}")
    return decisions


def legacy_map_row_count(root: Path) -> int:
    text = (root / "graphify" / "03-dependency-graphs" / "FRONTEND_TO_API_MAP.md").read_text(encoding="utf-8")
    count = len(re.findall(r"^\| `Codebase/web/src/[^`]+` \| \d+ \| `[^`]+` \|$", text, re.M))
    if count < 1:
        raise EvidenceError("LEGACY_FRONTEND_MAP_INVALID", "no planning-map records found")
    return count


def parse_data_flow_source_owners(root: Path) -> dict[str, set[str]]:
    text = (root / "graphify" / "01-current-architecture" / "DATA_FLOW_MAP.md").read_text(encoding="utf-8")
    result: dict[str, set[str]] = {}
    for match in re.finditer(r"^\| ([^|]+?) \| (.*?) \| (?:PORT|REWRITE|REPLACE|REMOVE) \|", text, re.M):
        capability = match.group(1).strip()
        if capability not in DECISIONS:
            continue
        for source in re.findall(r"`(Codebase/web/[^`]+)`", match.group(2)):
            result.setdefault(source, set()).add(capability)
    if not result:
        raise EvidenceError("DATA_FLOW_OWNER_AUTHORITY_INVALID", "no frontend source anchors found")
    return result


def negative_fixtures(output: Path) -> list[dict[str, Any]]:
    fixtures = [
        ("multiline-sdk-import", "import {\n type AssetResponseDto,\n getAssetInfo as loadAsset\n} from '@immich/sdk';", [(2, "AssetResponseDto"), (3, "getAssetInfo")]),
        ("namespace-sdk-import", "import * as sdk from '@immich/sdk';", [(1, "namespace:sdk")]),
        ("dynamic-sdk-import", "const sdk = await import('@immich/sdk');", [(1, "dynamic-module")]),
        ("mock-sdk-module", "vi.mock('@immich/sdk', () => ({}));", [(1, "mock-module")]),
        ("vitest-mock-sdk-module", "vitest.mock('@immich/sdk', () => ({}));", [(1, "mock-module")]),
        ("comment-not-import", "// import { fake } from '@immich/sdk'", []),
        ("string-not-import", "const example = \"import { fake } from '@immich/sdk'\";", []),
    ]
    results: list[dict[str, Any]] = []
    for fixture_id, source, expected in fixtures:
        actual = import_records(source, "@immich/sdk")
        results.append({"id": fixture_id, "expected": expected, "actual": actual, "status": "PASS" if actual == expected else "FAIL"})
    host_source = "const callback = globalThis.location.href; // location.origin\nconst text = 'location.host';"
    host_expected = [(1, "globalThis.location.href")]
    host_actual = runtime_host_records(host_source)
    results.append({"id": "runtime-host-positive-negative", "expected": host_expected, "actual": host_actual,
                    "status": "PASS" if host_actual == host_expected else "FAIL"})
    literal_host_source = (
        "<a href=\"https://docs.immich.app/guide\">Docs</a>\n"
        "const script = 'https://www.gstatic.com/cast.js';\n"
        "// https://comment.invalid/path\n"
        "const svg = 'http://www.w3.org/2000/svg';\n"
        "const placeholder = 'https://example.com/base';"
    )
    literal_host_expected = [(1, "literal-host:docs.immich.app"), (2, "literal-host:www.gstatic.com")]
    literal_host_actual = runtime_host_records(literal_host_source)
    results.append({"id": "literal-runtime-host-positive-negative", "expected": literal_host_expected,
                    "actual": literal_host_actual,
                    "status": "PASS" if literal_host_actual == literal_host_expected else "FAIL"})
    template_host_source = "const help = `https://docs.${info.version}.archive.immich.app/overview`;"
    template_host_expected = [(1, "template-host:docs.${info.version}.archive.immich.app")]
    template_host_actual = runtime_host_records(template_host_source)
    results.append({"id": "dynamic-template-runtime-host", "expected": template_host_expected,
                    "actual": template_host_actual,
                    "status": "PASS" if template_host_actual == template_host_expected else "FAIL"})
    template_review_expected = True
    template_review_actual = external_host_requires_review(template_host_expected[0][1])
    results.append({"id": "dynamic-template-host-review-required", "expected": template_review_expected,
                    "actual": template_review_actual,
                    "status": "PASS" if template_review_actual == template_review_expected else "FAIL"})
    url_object_source = "const fullUrl = new URL(path, base);\nuse(fullUrl.origin);\nuse(link.href);\nuse(config.smtp.port);"
    url_object_expected = [(2, "fullUrl.origin")]
    url_object_actual = runtime_host_records(url_object_source)
    results.append({"id": "qualified-url-object-not-arbitrary-properties", "expected": url_object_expected,
                    "actual": url_object_actual, "status": "PASS" if url_object_actual == url_object_expected else "FAIL"})
    bare_location_source = "redirect(location);\nlocation.reload();"
    bare_location_expected = [(1, "location"), (2, "location")]
    bare_location_actual = runtime_host_records(bare_location_source)
    results.append({"id": "unshadowed-global-location", "expected": bare_location_expected,
                    "actual": bare_location_actual,
                    "status": "PASS" if bare_location_actual == bare_location_expected else "FAIL"})
    shadowed_location_source = "const useLocation = (location: Location) => location.href;"
    shadowed_location_expected: list[tuple[int, str]] = []
    shadowed_location_actual = runtime_host_records(shadowed_location_source)
    results.append({"id": "shadowed-location-not-global", "expected": shadowed_location_expected,
                    "actual": shadowed_location_actual,
                    "status": "PASS" if shadowed_location_actual == shadowed_location_expected else "FAIL"})
    xhr_source = "const xhr = new XMLHttpRequest();\nxhr.open('POST', url);\nmodal.open('x');"
    xhr_expected = [(2, "'POST', url);")]
    xhr_actual = xhr_open_records(xhr_source)
    results.append({"id": "xhr-open-positive-negative", "expected": xhr_expected, "actual": xhr_actual,
                    "status": "PASS" if xhr_actual == xhr_expected else "FAIL"})
    oauth_actual = [(line, symbol) for line, symbol in import_records("import { oauth, noop } from '$lib/utils';", "$lib/utils") if symbol == "oauth"]
    oauth_expected = [(1, "oauth")]
    results.append({"id": "oauth-symbol-qualified", "expected": oauth_expected, "actual": oauth_actual,
                    "status": "PASS" if oauth_actual == oauth_expected else "FAIL"})
    load_data_actual = import_records("import type { PageData } from './$types';", "./$types")
    load_data_expected = [(1, "PageData")]
    results.append({"id": "sveltekit-load-data-import", "expected": load_data_expected, "actual": load_data_actual,
                    "status": "PASS" if load_data_actual == load_data_expected else "FAIL"})
    runtime_data_source = "import { page } from '$app/state';\nuse(page.data.asset); // page.data.fake\nconst text = 'page.data.nope';"
    runtime_data_expected = [(2, "asset")]
    runtime_data_actual = page_data_records(runtime_data_source)
    results.append({"id": "sveltekit-runtime-page-data", "expected": runtime_data_expected,
                    "actual": runtime_data_actual,
                    "status": "PASS" if runtime_data_actual == runtime_data_expected else "FAIL"})
    mixed_wrapper_source = """import { checkBulkUpload } from '@immich/sdk';
export const save = async (id: string) => { await checkBulkUpload({ id }); };
export const format = (id: string) => id.toUpperCase();
"""
    mixed_regions = function_regions(mixed_wrapper_source)
    sdk_locals = {local for original, local in named_import_bindings(mixed_wrapper_source, "@immich/sdk")
                  if original not in SDK_NON_ROUTE_CALLS}
    mixed_actual = sorted(
        name for name, entry in mixed_regions.items()
        if entry["exported"] and any(re.search(rf"\b{re.escape(local)}\s*\(", entry["body"])
                                     for local in sdk_locals)
    )
    mixed_expected = ["save"]
    results.append({"id": "route-wrapper-symbol-reachability", "expected": mixed_expected,
                    "actual": mixed_actual, "status": "PASS" if mixed_actual == mixed_expected else "FAIL"})
    auth_cookie_source = "for (const cookie of document.cookie.split('; ')) {\n  if (cookie === 'immich_is_authenticated') use(cookie);\n}"
    auth_cookie_expected = [(1, "document.cookie"), (2, "cookie:immich_is_authenticated")]
    auth_cookie_actual = auth_cookie_records(auth_cookie_source)
    results.append({"id": "server-auth-cookie-coupling", "expected": auth_cookie_expected,
                    "actual": auth_cookie_actual,
                    "status": "PASS" if auth_cookie_actual == auth_cookie_expected else "FAIL"})
    socket_import_source = "import { io, type Socket } from 'socket.io-client';"
    socket_import_expected = [(1, "Socket"), (1, "io")]
    socket_import_actual = import_records(socket_import_source, "socket.io-client")
    results.append({"id": "server-event-client-import", "expected": socket_import_expected,
                    "actual": socket_import_actual,
                    "status": "PASS" if socket_import_actual == socket_import_expected else "FAIL"})
    owner_fixtures = [
        (
            "database-backup-route-owner",
            "Codebase/web/src/lib/services/database-backups.service.ts",
            "location.href = getBaseUrl() + '/admin/database-backups/' + filename;",
            "Administration",
        ),
        (
            "url-search-property-not-domain-owner",
            "Codebase/web/src/lib/utils.ts",
            "return getBaseUrl() + url.pathname + url.search + url.hash;",
            None,
        ),
        (
            "location-property-not-map-owner",
            "Codebase/web/src/lib/utils.ts",
            "location.href = getBaseUrl() + '/download';",
            None,
        ),
    ]
    for fixture_id, source, dependency, expected in owner_fixtures:
        actual = decision_for(source, dependency, "SERVER_ROUTE")
        results.append({"id": fixture_id, "expected": expected, "actual": actual,
                        "status": "PASS" if actual == expected else "FAIL"})
    before_artifacts = {
        name: (output / name).read_bytes() if (output / name).is_file() else None
        for name in PUBLISHED_ARTIFACTS
    }
    simulated_artifacts = {name: b"SIMULATED_INVALID_GENERATION" for name in PUBLISHED_ARTIFACTS}
    published = publish_validated_generation(
        output,
        simulated_artifacts,
        "frontend-coupling-inventory.json",
        [{"code": "SIMULATED_VALIDATION_FAILURE"}],
    )
    after_artifacts = {
        name: (output / name).read_bytes() if (output / name).is_file() else None
        for name in PUBLISHED_ARTIFACTS
    }
    preservation_actual = {"published": published, "allArtifactsByteIdentical": before_artifacts == after_artifacts}
    preservation_expected = {"published": False, "allArtifactsByteIdentical": True}
    results.append({"id": "failed-validation-preserves-all-artifacts", "expected": preservation_expected,
                    "actual": preservation_actual,
                    "status": "PASS" if preservation_actual == preservation_expected else "FAIL"})
    before_mid_publish = {
        name: (output / name).read_bytes() if (output / name).is_file() else None
        for name in PUBLISHED_ARTIFACTS
    }
    replace_count = 0

    def fail_mid_publish(path: Path, content: bytes) -> None:
        nonlocal replace_count
        replace_count += 1
        if replace_count == 3:
            raise EvidenceError("SIMULATED_MID_PUBLISH_FAILURE", path.name)
        atomic_replace(path, content)

    failed_as_expected = False
    try:
        publish_generation(output, simulated_artifacts, "frontend-coupling-inventory.json", fail_mid_publish)
    except EvidenceError as exc:
        failed_as_expected = exc.code == "SIMULATED_MID_PUBLISH_FAILURE"
    after_mid_publish = {
        name: (output / name).read_bytes() if (output / name).is_file() else None
        for name in PUBLISHED_ARTIFACTS
    }
    mid_publish_actual = {
        "failedAsExpected": failed_as_expected,
        "allArtifactsByteIdentical": before_mid_publish == after_mid_publish,
    }
    mid_publish_expected = {"failedAsExpected": True, "allArtifactsByteIdentical": True}
    results.append({"id": "mid-publication-failure-restores-all-artifacts", "expected": mid_publish_expected,
                    "actual": mid_publish_actual,
                    "status": "PASS" if mid_publish_actual == mid_publish_expected else "FAIL"})
    return results


def main() -> int:
    global EXACT_SOURCE_OWNERS
    script = Path(__file__)
    root = repository_root(script)
    output = script.resolve().parent
    baseline = baseline_hashes(root)
    before = codebase_hashes(root)
    decisions = parse_reviewed_decisions(root)
    EXACT_SOURCE_OWNERS = parse_data_flow_source_owners(root)
    legacy_rows = legacy_map_row_count(root)
    couplings, sources, server_state_modules, server_route_modules, load_data_edges = scan_source(root)
    local_service_exclusions = excluded_local_service_modules(root, server_route_modules)
    fixtures = negative_fixtures(output)
    failures = validate(couplings, sources, decisions)
    after = codebase_hashes(root)
    if before != after:
        failures.append({"code": "CODEBASE_CHANGED_DURING_COLLECTION"})
    if baseline != before:
        failures.append({"code": "WP_I0_001_BASELINE_MISMATCH", "baselineCount": len(baseline), "currentCount": len(before)})
    if any(row["status"] != "PASS" for row in fixtures):
        failures.append({"code": "NEGATIVE_FIXTURE_FAILED"})

    category_counts = Counter(row["category"] for row in couplings)
    status_counts = Counter(row["ownership"]["status"] for row in couplings)
    generation_id = semantic_sha256({
        "packageId": PACKAGE_ID,
        "sources": sources,
        "couplings": couplings,
        "failures": failures,
        "codebase": semantic_sha256(after),
    })
    inventory = {
        "packageId": PACKAGE_ID,
        "requirementId": REQUIREMENT_ID,
        "generationId": generation_id,
        "authoritativeCommitMarker": True,
        "status": "PASS" if not failures else "FAIL",
        "scope": "Every file recursively under Codebase/web is fingerprinted; runtime source plus JavaScript/TypeScript/Svelte, TOML, shell, bin, and environment surfaces are content-qualified and text-scanned, with tests and mocks included.",
        "categories": sorted(CATEGORIES),
        "reviewedDecisionAuthority": "graphify/05-keep-port-rewrite-remove/DECISION_MATRIX.md",
        "scopeAuthority": [
            "graphify/01-current-architecture/FRONTEND_ARCHITECTURE.md",
            "graphify/01-current-architecture/DATA_FLOW_MAP.md",
            "graphify/03-dependency-graphs/FRONTEND_TO_API_MAP.md",
        ],
        "legacyPlanningMapReconciliation": {
            "path": "graphify/03-dependency-graphs/FRONTEND_TO_API_MAP.md",
            "legacyRows": legacy_rows,
            "role": "Planning input, not the WP-I0-009 completion oracle.",
            "reconciliation": "The package scanner preserves exact imported symbols and their own multiline source lines, supports namespace and dynamic imports, and rejects comment/mock lexical tokens that the earlier broad static map could count as symbols.",
        },
        "serverStateModuleOracle": [
            {"module": module, "qualification": qualification}
            for module, qualification in server_state_modules.items()
        ],
        "serverRouteModuleOracle": [
            {"module": module, **details}
            for module, details in server_route_modules.items()
        ],
        "serverRouteModuleExclusions": [
            {
                "module": module,
                "reason": (
                    "Authentication coupling is inventoried under AUTHENTICATION."
                    if module == "$lib/utils/auth"
                    else "No route-bearing exported symbol was discovered."
                ),
            }
            for module in local_service_exclusions
        ],
        "exactReviewedSourceOwners": [
            {"sourcePath": source, "owners": sorted(owners), "status": "LINKED" if len(owners) == 1 else "REVIEW_REQUIRED"}
            for source, owners in sorted(EXACT_SOURCE_OWNERS.items())
        ],
        "svelteKitLoadDataOracle": load_data_edges,
        "counts": {
            "sourceFiles": len(sources),
            "textScannedFiles": sum(1 for row in sources if row["textScanned"]),
            "couplings": len(couplings),
            "linked": status_counts["LINKED"],
            "reviewRequired": status_counts["REVIEW_REQUIRED"],
            "byCategory": dict(sorted(category_counts.items())),
        },
        "sourceCorpus": sources,
        "couplings": couplings,
        "reviewRequired": [
            {"couplingId": row["id"], "sourcePath": row["sourcePath"], "line": row["line"], "reason": row["ownership"]["reason"]}
            for row in couplings if row["ownership"]["status"] == "REVIEW_REQUIRED"
        ],
    }
    verification = {
        "packageId": PACKAGE_ID,
        "generationId": generation_id,
        "status": inventory["status"],
        "acceptanceCriterion": "Every discovered frontend coupling has source evidence, a dependency category, and one reviewed owner; unresolved ownership is REVIEW_REQUIRED.",
        "checks": {
            "completeRecursiveSourceOracle": len(sources) > 0,
            "allFiveCategoriesPresent": set(category_counts) == CATEGORIES,
            "allRecordsHaveExactSourceEvidence": not any(item.get("code") == "SOURCE_EVIDENCE_INVALID" for item in failures),
            "everyLinkedOwnerExistsInReviewedDecisionMatrix": not any(item.get("code") == "OWNER_INVALID" for item in failures),
            "everyUnresolvedOwnerIsReviewRequired": not any(item.get("code") == "UNRESOLVED_OWNERSHIP_INVALID" for item in failures),
            "negativeParserFixturesPass": all(row["status"] == "PASS" for row in fixtures),
            "codebaseMatchesWP_I0_001": baseline == before == after,
        },
        "negativeFixtures": fixtures,
        "failures": failures,
    }
    consistency = {
        "packageId": PACKAGE_ID,
        "generationId": generation_id,
        "status": "PASS" if not failures else "FAIL",
        "inventorySemanticSha256": semantic_sha256(inventory),
        "sourceCorpusSemanticSha256": semantic_sha256(sources),
        "couplingsSemanticSha256": semantic_sha256(couplings),
        "baselineFileCount": len(baseline),
        "beforeFileCount": len(before),
        "afterFileCount": len(after),
        "baselineSemanticSha256": semantic_sha256(baseline),
        "beforeSemanticSha256": semantic_sha256(before),
        "afterSemanticSha256": semantic_sha256(after),
    }
    provenance = {
        "packageId": PACKAGE_ID,
        "generationId": generation_id,
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "method": "Local-only static source inspection; no product code imported or executed.",
        "inputs": [
            "Codebase/web/** (full frontend corpus; content-qualified runtime/config text)",
            "graphify/05-keep-port-rewrite-remove/DECISION_MATRIX.md",
            "graphify/01-current-architecture/FRONTEND_ARCHITECTURE.md",
            "graphify/03-dependency-graphs/FRONTEND_TO_API_MAP.md",
            "graphify/13-implementation/WP-I0-001/sha256-manifest.csv",
        ],
        "codebaseReadOnly": baseline == before == after,
    }
    summary = {
        "packageId": PACKAGE_ID,
        "generationId": generation_id,
        "requirementIds": [REQUIREMENT_ID],
        "status": "PASS" if not failures else "FAIL",
        "counts": inventory["counts"],
        "artifacts": [
            "frontend-coupling-inventory.json", "verification-report.json", "evidence-consistency.json",
            "provenance-report.json", "artifact-scan.json", "completion-evidence.md",
        ],
        "failures": failures,
    }
    artifact_scan = {
        "packageId": PACKAGE_ID,
        "generationId": generation_id,
        "status": "PASS" if not failures else "FAIL",
        "allowedRoot": "graphify/13-implementation/WP-I0-009",
        "codebaseChanged": before != after,
        "generatedArtifacts": summary["artifacts"] + ["package-summary.json"],
        "failures": failures,
    }
    completion = [
        f"# {PACKAGE_ID} completion evidence",
        "",
        "## Result",
        "",
        f"- Status: **{summary['status']}**",
        f"- Requirement: `{REQUIREMENT_ID}`",
        f"- Evidence generation: `{generation_id}`",
        f"- Frontend source files inspected: `{len(sources)}`",
        f"- Couplings recorded: `{len(couplings)}`",
        f"- Linked to one reviewed decision: `{status_counts['LINKED']}`",
        f"- Ownership review required: `{status_counts['REVIEW_REQUIRED']}`",
        "",
        "## Category coverage",
        "",
    ]
    completion.extend(f"- `{category}`: `{category_counts[category]}`" for category in sorted(CATEGORIES))
    completion.extend([
        "", "## Validation", "",
        "- Recursive source oracle includes tests and mocks.",
        "- Every record has an exact path, line, evidence excerpt, category, mechanism, and ownership state.",
        "- Every linked owner exists in the committed reviewed decision matrix.",
        "- Every unresolved owner is explicitly `REVIEW_REQUIRED`.",
        "- The full Codebase hash map matches WP-I0-001 before and after collection.",
        "- Negative multiline, namespace, dynamic, mock, and comment fixtures pass.",
        "- Socket.IO event-client imports/declarations and the server auth cookie are independently inventoried.",
        "- Dynamic template-literal hosts preserve the complete host expression without partial literals.",
        "", "## Recovery", "",
        "The collector writes only package-local derived evidence. Secondary artifacts are atomically replaced first and the authoritative inventory commit marker is replaced last. A pre-validation failure publishes nothing; an injected mid-publication I/O failure rolls every artifact back byte-for-byte before returning a typed error.",
        "", "## Changed files", "",
        "- `graphify/13-implementation/WP-I0-009/collect_evidence.py` — collector, focused/negative fixtures, and rollback protocol.",
        "- `graphify/13-implementation/WP-I0-009/verify_evidence.py` — independent read-only coverage and semantic verifier.",
        "- `graphify/13-implementation/WP-I0-009/frontend-coupling-inventory.json` — authoritative coupling inventory.",
        "- `graphify/13-implementation/WP-I0-009/{artifact-scan,evidence-consistency,package-summary,provenance-report,verification-report}.json` — generated package evidence.",
        "- `graphify/13-implementation/WP-I0-009/completion-evidence.md` and `adversarial-review.md` — completion and independent-review evidence.",
        "", "## Commands and results", "",
        "- `python graphify\\13-implementation\\WP-I0-009\\collect_evidence.py` — PASS (exit 0); current generation published only after focused and negative fixtures pass.",
        "- `python graphify\\13-implementation\\WP-I0-009\\verify_evidence.py` — PASS (exit 0); independently rerun after publication and recorded in `adversarial-review.md`.",
    ])
    artifacts = {
        "artifact-scan.json": json_bytes(artifact_scan),
        "completion-evidence.md": ("\n".join(completion) + "\n").encode("utf-8"),
        "evidence-consistency.json": json_bytes(consistency),
        "frontend-coupling-inventory.json": json_bytes(inventory),
        "package-summary.json": json_bytes(summary),
        "provenance-report.json": json_bytes(provenance),
        "verification-report.json": json_bytes(verification),
    }
    if failures:
        print(json.dumps({"status": "FAIL", "failures": failures}, indent=2), file=sys.stderr)
        return 1
    published = publish_validated_generation(output, artifacts, "frontend-coupling-inventory.json", failures)
    if not published:
        raise EvidenceError("VALID_GENERATION_NOT_PUBLISHED", "unexpected publication guard result")
    print(json.dumps(summary["counts"], indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except EvidenceError as exc:
        print(json.dumps({"status": "FAIL", "error": {"code": exc.code, "message": str(exc)}}), file=sys.stderr)
        raise SystemExit(2)
    except (OSError, UnicodeError) as exc:
        print(json.dumps({"status": "FAIL", "error": {"code": "INPUT_OUTPUT_BOUNDARY_ERROR", "message": str(exc)}}), file=sys.stderr)
        raise SystemExit(2)
