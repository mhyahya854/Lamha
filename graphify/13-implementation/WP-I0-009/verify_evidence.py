#!/usr/bin/env python3
"""Independent, read-only verification for WP-I0-009 evidence."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import posixpath
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


MAX_JSON_BYTES = 16 * 1024 * 1024
MAX_JSON_DEPTH = 128
CATEGORIES = {"SERVER_ROUTE", "GENERATED_CLIENT", "AUTHENTICATION", "RUNTIME_HOST", "SERVER_OWNED_STATE"}
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
OWNER_DOMAIN_TOKENS = {
    "Administration": ("admin", "maintenance", "server", "database-backup"),
    "Albums and favorites": ("album", "favorite"),
    "Asset viewer": ("asset-viewer",),
    "Authentication and users": ("auth", "user", "session", "oauth", "login", "password", "pin"),
    "Desktop shell": ("desktop", "runtime", "host"),
    "Duplicates": ("duplicate", "similar"),
    "Editing": ("edit", "editor", "stack"),
    "Events and organization": ("event", "activity", "socket", "websocket"),
    "Gallery and timeline": ("asset", "gallery", "timeline", "photo", "archive", "trash", "thumbnail"),
    "Jobs and notifications": ("notification", "queue", "job"),
    "Legal and rebranding": ("license", "legal", "brand"),
    "Libraries and storage": ("library", "folder", "storage"),
    "Local AI worker": ("machine-learning", "smart-search", "model", "clip"),
    "Map and location": ("map", "location", "place", "geocod"),
    "Memories": ("memory",),
    "Metadata": ("metadata", "exif", "sidecar"),
    "People and faces": ("people", "person", "face"),
    "Review Centre": ("review",),
    "Search and OCR": ("search", "ocr"),
    "Settings": ("setting", "config", "preference", "feature-flag"),
    "Sharing and mobile backup": ("share", "partner", "backup"),
    "Tags": ("tag",),
}


class VerificationError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise VerificationError("JSON_DUPLICATE_KEY", key)
        result[key] = value
    return result


def reject_constant(value: str) -> None:
    raise VerificationError("JSON_NONFINITE_NUMBER", value)


def depth(value: Any, level: int = 0) -> int:
    if level > MAX_JSON_DEPTH:
        raise VerificationError("JSON_TOO_DEEP", str(level))
    if isinstance(value, dict):
        return max((depth(item, level + 1) for item in value.values()), default=level)
    if isinstance(value, list):
        return max((depth(item, level + 1) for item in value), default=level)
    if isinstance(value, float) and not math.isfinite(value):
        raise VerificationError("JSON_NONFINITE_NUMBER", str(value))
    return level


def load_json(path: Path) -> Any:
    raw = path.read_bytes()
    if len(raw) > MAX_JSON_BYTES:
        raise VerificationError("JSON_TOO_LARGE", path.name)
    try:
        text = raw.decode("utf-8")
        value = json.loads(text, object_pairs_hook=reject_duplicates, parse_constant=reject_constant)
    except UnicodeDecodeError as exc:
        raise VerificationError("JSON_INVALID_UTF8", path.name) from exc
    except json.JSONDecodeError as exc:
        raise VerificationError("JSON_MALFORMED", f"{path.name}:{exc.lineno}") from exc
    depth(value)
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def baseline(root: Path) -> dict[str, str]:
    manifest = root / "graphify" / "13-implementation" / "WP-I0-001" / "sha256-manifest.csv"
    result: dict[str, str] = {}
    with manifest.open("r", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            name = row.get("path") or row.get("relative_path") or row.get("file")
            digest = row.get("sha256") or row.get("SHA256")
            if not name or not digest:
                raise VerificationError("BASELINE_INVALID", "invalid row")
            name = name.replace("\\", "/")
            name = name if name.startswith("Codebase/") else f"Codebase/{name}"
            result[name] = digest.lower()
    return result


def oracle_mask_comments(text: str) -> str:
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
        if text.startswith("//", index):
            end = text.find("\n", index + 2)
            end = len(text) if end < 0 else end
            for cursor in range(index, end):
                chars[cursor] = " "
            index = end
            continue
        if text.startswith("/*", index):
            end = text.find("*/", index + 2)
            end = len(text) - 2 if end < 0 else end
            for cursor in range(index, min(end + 2, len(text))):
                if chars[cursor] != "\n":
                    chars[cursor] = " "
            index = end + 2
            continue
        index += 1
    return "".join(chars)


def oracle_code_flags(text: str) -> list[bool]:
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


def oracle_import_bindings(text: str, module: str) -> list[tuple[str, str]]:
    pattern = re.compile(
        rf"\bimport\s+(?!\()(?P<clause>(?:(?!\bimport\b)[\s\S])*?)\s+from\s*['\"]{re.escape(module)}['\"]"
    )
    result: list[tuple[str, str]] = []
    for match in pattern.finditer(oracle_mask_comments(text)):
        clause = match.group("clause").strip()
        if clause.startswith("type "):
            continue
        namespace = re.search(r"\*\s+as\s+([A-Za-z_$][\w$]*)", clause)
        if namespace:
            result.append(("*", namespace.group(1)))
        names = re.search(r"\{(.*?)\}", clause, re.S)
        if names:
            for raw in names.group(1).split(","):
                item = raw.strip()
                if not item or item.startswith("type "):
                    continue
                pair = re.split(r"\s+as\s+", item, maxsplit=1)
                original, local = pair[0].strip(), pair[-1].strip()
                if re.fullmatch(r"[A-Za-z_$][\w$]*", original) and re.fullmatch(r"[A-Za-z_$][\w$]*", local):
                    result.append((original, local))
    return sorted(set(result))


def oracle_import_records(text: str, module: str) -> list[tuple[int, str]]:
    pattern = re.compile(
        rf"\bimport\s+(?!\()(?P<clause>(?:(?!\bimport\b)[\s\S])*?)\s+from\s*['\"]{re.escape(module)}['\"]"
    )
    records: list[tuple[int, str]] = []
    for match in pattern.finditer(oracle_mask_comments(text)):
        clause = match.group("clause")
        namespace = re.search(r"\*\s+as\s+([A-Za-z_$][\w$]*)", clause)
        if namespace:
            offset = match.start("clause") + namespace.start(1)
            records.append((text.count("\n", 0, offset) + 1, f"namespace:{namespace.group(1)}"))
        names = re.search(r"\{(.*?)\}", clause, re.S)
        if names:
            for raw in names.group(1).split(","):
                item = raw.strip()
                if not item or item.startswith("type "):
                    continue
                original = re.split(r"\s+as\s+", item, maxsplit=1)[0].strip()
                occurrence = re.search(rf"\b{re.escape(original)}\b", clause)
                if occurrence:
                    offset = match.start("clause") + occurrence.start()
                    records.append((text.count("\n", 0, offset) + 1, original))
    escaped = re.escape(module)
    for match in re.finditer(rf"\bimport\s*['\"]{escaped}['\"]\s*;?", oracle_mask_comments(text)):
        records.append((text.count("\n", 0, match.start()) + 1, "module"))
    for match in re.finditer(rf"\bimport\s*\(\s*['\"]{escaped}['\"]\s*\)(?:\.([A-Za-z_$][\w$]*))?", oracle_mask_comments(text)):
        records.append((text.count("\n", 0, match.start()) + 1, match.group(1) or "dynamic-module"))
    for match in re.finditer(rf"\b(?:vi|jest|vitest)\.mock\s*\(\s*['\"]{escaped}['\"]", oracle_mask_comments(text)):
        records.append((text.count("\n", 0, match.start()) + 1, "mock-module"))
    return sorted(set(records))


def oracle_all_import_records(text: str, module: str) -> list[tuple[int, str]]:
    """Include type-only named imports when the dependency itself is in scope."""
    records = set(oracle_import_records(text, module))
    pattern = re.compile(
        rf"\bimport\s+(?!\()(?P<clause>(?:(?!\bimport\b)[\s\S])*?)\s+from\s*['\"]{re.escape(module)}['\"]"
    )
    for match in pattern.finditer(oracle_mask_comments(text)):
        names = re.search(r"\{(.*?)\}", match.group("clause"), re.S)
        if not names:
            continue
        for raw in names.group(1).split(","):
            item = re.sub(r"^\s*type\s+", "", raw.strip())
            original = re.split(r"\s+as\s+", item, maxsplit=1)[0].strip()
            occurrence = re.search(rf"\b{re.escape(original)}\b", match.group("clause")) if original else None
            if occurrence and re.fullmatch(r"[A-Za-z_$][\w$]*", original):
                offset = match.start("clause") + occurrence.start()
                records.add((text.count("\n", 0, offset) + 1, original))
    return sorted(records)


def oracle_matching_brace(text: str, start: int, flags: list[bool]) -> int | None:
    depth_value = 0
    for index in range(start, len(text)):
        if not flags[index]:
            continue
        if text[index] == "{":
            depth_value += 1
        elif text[index] == "}":
            depth_value -= 1
            if depth_value == 0:
                return index
    return None


def oracle_functions(text: str) -> dict[str, dict[str, Any]]:
    masked = oracle_mask_comments(text)
    flags = oracle_code_flags(text)
    result: dict[str, dict[str, Any]] = {}
    for match in re.finditer(r"\b(?P<export>export\s+)?(?:async\s+)?function\s+(?P<name>[A-Za-z_$][\w$]*)", masked):
        parens = brackets = parameter_braces = 0
        brace = -1
        cursor = match.end()
        while cursor < len(text):
            if not flags[cursor]:
                cursor += 1
                continue
            char = text[cursor]
            if char == "(":
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
        end = oracle_matching_brace(text, brace, flags)
        if end is not None:
            result[match.group("name")] = {"body": text[brace + 1:end], "exported": bool(match.group("export"))}
    for match in re.finditer(r"\b(?P<export>export\s+)?class\s+(?P<name>[A-Za-z_$][\w$]*)", masked):
        brace = masked.find("{", match.end())
        end = oracle_matching_brace(text, brace, flags) if brace >= 0 else None
        if end is not None:
            result[match.group("name")] = {"body": text[brace + 1:end], "exported": bool(match.group("export"))}
    for match in re.finditer(r"\b(?P<export>export\s+)?const\s+(?P<name>[A-Za-z_$][\w$]*)\b", masked):
        limit = min(len(text), match.start() + 1200)
        depths = {"(": 0, "[": 0, "{": 0}
        closing = {")": "(", "]": "[", "}": "{"}
        arrow = -1
        assignment = -1
        cursor = match.end()
        while cursor < limit:
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
            end = oracle_matching_brace(text, cursor, flags)
            if end is None:
                continue
            body = text[cursor + 1:end]
        else:
            end = masked.find(";", cursor)
            end = len(text) if end < 0 else end
            body = text[cursor:end]
        result[match.group("name")] = {"body": body, "exported": bool(match.group("export"))}
    return result


def oracle_class_members(text: str) -> dict[str, dict[str, str]]:
    masked = oracle_mask_comments(text)
    flags = oracle_code_flags(text)
    result: dict[str, dict[str, str]] = {}
    for class_match in re.finditer(r"\bexport\s+class\s+(?P<name>[A-Za-z_$][\w$]*)", masked):
        class_brace = masked.find("{", class_match.end())
        class_end = oracle_matching_brace(text, class_brace, flags) if class_brace >= 0 else None
        if class_end is None:
            continue
        body = text[class_brace + 1:class_end]
        body_masked = oracle_mask_comments(body)
        body_flags = oracle_code_flags(body)
        methods: dict[str, str] = {}
        pattern = re.compile(
            r"(?m)^\s*(?:(?:public|private|protected|override)\s+)*(?:static\s+)?(?:async\s+)?"
            r"(?P<name>constructor|[A-Za-z_$][\w$]*)\s*\("
        )
        for match in pattern.finditer(body_masked):
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
            method_end = oracle_matching_brace(body, method_brace, body_flags) if method_brace >= 0 else None
            if method_end is not None:
                methods[match.group("name")] = body[method_brace + 1:method_end]
        result[class_match.group("name")] = methods
    return result


def independent_route_oracle(root: Path) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    source_root = root / "Codebase" / "web" / "src"
    candidates: dict[str, str] = {}
    for path in source_root.rglob("*"):
        relative_parts = path.relative_to(source_root).parts
        if (not path.is_file() or path.suffix.lower() not in {".ts", ".js"}
                or ".spec." in path.name or "__mocks__" in relative_parts
                or (relative_parts[0] == "lib" and len(relative_parts) > 1
                    and relative_parts[1] in {"managers", "stores"})):
            continue
        relative = path.relative_to(source_root).as_posix()[:-3]
        module = f"$lib/{relative.removeprefix('lib/')}" if relative.startswith("lib/") else f"Codebase/web/src/{relative}"
        candidates[module] = path.read_text(encoding="utf-8")
    functions = {module: oracle_functions(text) for module, text in candidates.items()}
    route_functions: dict[str, set[str]] = {module: set() for module in candidates}
    network = re.compile(r"\bfetch\s*\(|\bXMLHttpRequest\b|['\"`]/api/|\bgetBaseUrl\s*\(")
    for module, entries in functions.items():
        sdk = oracle_import_bindings(candidates[module], "@immich/sdk")
        auth_manager_locals = {
            local for original, local in oracle_import_bindings(candidates[module], "$lib/managers/auth-manager.svelte")
            if original in {"authManager", "*"}
        }
        for name, entry in entries.items():
            body = entry["body"]
            direct = bool(network.search(oracle_mask_comments(body)))
            for original, local in sdk:
                if original == "*":
                    direct = direct or bool(re.search(rf"\b{re.escape(local)}\.[A-Za-z_$][\w$]*\s*\(", body))
                elif original not in SDK_NON_ROUTE_CALLS:
                    direct = direct or bool(re.search(rf"\b{re.escape(local)}\s*\(", body))
            if direct:
                route_functions[module].add(name)
    changed = True
    while changed:
        changed = False
        exported = {module: {name for name in names if functions[module].get(name, {}).get("exported")}
                    for module, names in route_functions.items()}
        for module, entries in functions.items():
            imported: set[str] = set()
            namespaces: list[tuple[str, set[str]]] = []
            for dependency, symbols in exported.items():
                if not symbols:
                    continue
                if dependency.startswith("$lib/"):
                    specifier = dependency
                else:
                    importer_stub = (f"Codebase/web/src/lib/{module.removeprefix('$lib/')}"
                                     if module.startswith("$lib/") else module)
                    relative = posixpath.relpath(dependency, posixpath.dirname(importer_stub))
                    specifier = relative if relative.startswith(".") else f"./{relative}"
                for original, local in oracle_import_bindings(candidates[module], specifier):
                    if original == "*":
                        namespaces.append((local, symbols))
                    elif original in symbols:
                        imported.add(local)
            for name, entry in entries.items():
                if name in route_functions[module]:
                    continue
                body = entry["body"]
                reaches = any(re.search(rf"\b{re.escape(target)}\s*\(", body) for target in route_functions[module])
                reaches = reaches or any(re.search(rf"\b{re.escape(target)}\s*\(", body) for target in imported)
                reaches = reaches or any(re.search(rf"\b{re.escape(alias)}\.{re.escape(target)}\s*\(", body)
                                          for alias, symbols in namespaces for target in symbols)
                if reaches:
                    route_functions[module].add(name)
                    changed = True
    auth_functions: dict[str, set[str]] = {module: set() for module in candidates}
    for module, entries in functions.items():
        sdk = oracle_import_bindings(candidates[module], "@immich/sdk")
        auth_manager_locals = {
            local for original, local in oracle_import_bindings(candidates[module], "$lib/managers/auth-manager.svelte")
            if original in {"authManager", "*"}
        }
        for name, entry in entries.items():
            if any(original in AUTH_SDK_SYMBOLS and re.search(rf"\b{re.escape(local)}\s*\(", entry["body"])
                   for original, local in sdk):
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
            for dependency, symbols in exported_auth.items():
                if not symbols:
                    continue
                if dependency.startswith("$lib/"):
                    specifier = dependency
                else:
                    importer_stub = (f"Codebase/web/src/lib/{module.removeprefix('$lib/')}"
                                     if module.startswith("$lib/") else module)
                    relative = posixpath.relpath(dependency, posixpath.dirname(importer_stub))
                    specifier = relative if relative.startswith(".") else f"./{relative}"
                for original, local in oracle_import_bindings(candidates[module], specifier):
                    if original in symbols:
                        imported_auth.add(local)
            for name, entry in entries.items():
                if name in auth_functions[module]:
                    continue
                body = entry["body"]
                if (any(re.search(rf"\b{re.escape(target)}\s*\(", body) for target in auth_functions[module])
                        or any(re.search(rf"\b{re.escape(target)}\s*\(", body) for target in imported_auth)):
                    auth_functions[module].add(name)
                    changed = True
    class_members = {module: oracle_class_members(text) for module, text in candidates.items()}
    class_routes: dict[str, dict[str, set[str]]] = {
        module: {class_name: set() for class_name in classes}
        for module, classes in class_members.items()
    }
    changed = True
    while changed:
        changed = False
        exported = {module: {name for name in names if functions[module].get(name, {}).get("exported")}
                    for module, names in route_functions.items()}
        for module, classes in class_members.items():
            imported: set[str] = set()
            for dependency, symbols in exported.items():
                if dependency.startswith("$lib/"):
                    specifier = dependency
                else:
                    importer_stub = (f"Codebase/web/src/lib/{module.removeprefix('$lib/')}"
                                     if module.startswith("$lib/") else module)
                    relative = posixpath.relpath(dependency, posixpath.dirname(importer_stub))
                    specifier = relative if relative.startswith(".") else f"./{relative}"
                for original, local in oracle_import_bindings(candidates[module], specifier):
                    if original in symbols:
                        imported.add(local)
            sdk = oracle_import_bindings(candidates[module], "@immich/sdk")
            for class_name, members in classes.items():
                for member, body in members.items():
                    if member in class_routes[module][class_name]:
                        continue
                    direct = bool(network.search(oracle_mask_comments(body)))
                    direct = direct or any(
                        original not in SDK_NON_ROUTE_CALLS and original != "*"
                        and re.search(rf"\b{re.escape(local)}\s*\(", body)
                        for original, local in sdk
                    )
                    direct = direct or any(re.search(rf"\b{re.escape(local)}\s*\(", body) for local in imported)
                    direct = direct or any(
                        re.search(rf"\bthis\.{re.escape(target)}\s*\(", body)
                        for target in class_routes[module][class_name]
                    )
                    if direct:
                        class_routes[module][class_name].add(member)
                        changed = True
    qualified = {
        module: {
            "qualification": "exported-symbol-call-reachability",
            "routeSymbols": sorted(
                name for name in names if functions[module].get(name, {}).get("exported")
                and not (module == "$lib/utils" and name == "oauth")
            ),
            "authSymbols": sorted(
                name for name in auth_functions[module]
                if functions[module].get(name, {}).get("exported")
                and not (module == "$lib/utils" and name == "oauth")
            ),
            "classRouteMembers": {
                class_name: sorted(members)
                for class_name, members in sorted(class_routes[module].items()) if members
            },
        }
        for module, names in route_functions.items()
        if module != "$lib/utils/auth"
        and (
            any(functions[module].get(name, {}).get("exported")
                and not (module == "$lib/utils" and name == "oauth") for name in names)
            or any(functions[module].get(name, {}).get("exported") for name in auth_functions[module])
        )
    }
    return dict(sorted(qualified.items())), dict(sorted(candidates.items()))


def verify() -> dict[str, Any]:
    package = Path(__file__).resolve().parent
    root = package.parents[2]
    inventory = load_json(package / "frontend-coupling-inventory.json")
    report = load_json(package / "verification-report.json")
    summary = load_json(package / "package-summary.json")
    consistency = load_json(package / "evidence-consistency.json")
    provenance = load_json(package / "provenance-report.json")
    artifact_scan = load_json(package / "artifact-scan.json")
    generation_ids = {
        value.get("generationId")
        for value in (inventory, report, summary, consistency, provenance, artifact_scan)
        if isinstance(value, dict)
    }
    generation_id = inventory.get("generationId") if isinstance(inventory, dict) else None
    if (len(generation_ids) != 1 or not isinstance(generation_id, str) or len(generation_id) != 64
            or inventory.get("authoritativeCommitMarker") is not True):
        raise VerificationError("EVIDENCE_GENERATION_MISMATCH", str(generation_ids))
    completion = (package / "completion-evidence.md").read_text(encoding="utf-8")
    if generation_id not in completion:
        raise VerificationError("COMPLETION_GENERATION_MISMATCH", generation_id)
    if inventory.get("packageId") != "WP-I0-009" or inventory.get("requirementId") != "CAN-MISSION-I0-009":
        raise VerificationError("IDENTITY_INVALID", "package or requirement")
    if inventory.get("status") != "PASS" or report.get("status") != "PASS" or summary.get("status") != "PASS":
        raise VerificationError("STATUS_NOT_PASS", "one or more evidence statuses are not PASS")
    fixtures = report.get("negativeFixtures")
    required_fixtures = {
        "database-backup-route-owner",
        "url-search-property-not-domain-owner",
        "location-property-not-map-owner",
        "dynamic-template-runtime-host",
        "dynamic-template-host-review-required",
        "server-auth-cookie-coupling",
        "server-event-client-import",
        "failed-validation-preserves-all-artifacts",
        "mid-publication-failure-restores-all-artifacts",
    }
    fixture_statuses = {
        row.get("id"): row.get("status")
        for row in fixtures if isinstance(row, dict)
    } if isinstance(fixtures, list) else {}
    if not required_fixtures.issubset(fixture_statuses) or any(status != "PASS" for status in fixture_statuses.values()):
        raise VerificationError("NEGATIVE_FIXTURES_INVALID", str(fixture_statuses))
    decision_text = (root / "graphify" / "05-keep-port-rewrite-remove" / "DECISION_MATRIX.md").read_text(encoding="utf-8")
    reviewed_decisions = set(re.findall(
        r"^\| ([^|]+?) \| (?:KEEP UNCHANGED|PORT|REWRITE|REPLACE|REMOVE|TEMPORARILY RETAIN) \|",
        decision_text,
        re.M,
    ))
    data_flow_text = (root / "graphify" / "01-current-architecture" / "DATA_FLOW_MAP.md").read_text(encoding="utf-8")
    exact_source_owners: dict[str, set[str]] = {}
    for match in re.finditer(r"^\| ([^|]+?) \| (.*?) \| (?:PORT|REWRITE|REPLACE|REMOVE) \|", data_flow_text, re.M):
        capability = match.group(1).strip()
        if capability not in reviewed_decisions:
            continue
        for anchor in re.findall(r"`(Codebase/web/[^`]+)`", match.group(2)):
            exact_source_owners.setdefault(anchor, set()).add(capability)

    source_root = root / "Codebase" / "web"
    actual_paths = sorted(path for path in source_root.rglob("*") if path.is_file())
    declared_sources = inventory.get("sourceCorpus")
    if not isinstance(declared_sources, list):
        raise VerificationError("SOURCE_CORPUS_INVALID", "not a list")
    declared_by_path = {row.get("path"): row for row in declared_sources if isinstance(row, dict)}
    actual_names = {path.relative_to(root).as_posix() for path in actual_paths}
    if set(declared_by_path) != actual_names or len(declared_by_path) != len(declared_sources):
        raise VerificationError("SOURCE_CORPUS_INCOMPLETE", "path set differs")
    source_text: dict[str, str] = {}
    for path in actual_paths:
        name = path.relative_to(root).as_posix()
        raw = path.read_bytes()
        row = declared_by_path[name]
        scan_eligible = (
            path.suffix.lower() in {".ts", ".js", ".mjs", ".cjs", ".svelte", ".html", ".css", ".svg", ".toml", ".sh", ".txt"}
            or path.parent == source_root / "bin"
            or path.name.startswith(".env")
            or path == source_root / "package.json"
        )
        if (row.get("sha256") != hashlib.sha256(raw).hexdigest() or row.get("bytes") != len(raw)
                or row.get("textScanned") is not scan_eligible):
            raise VerificationError("SOURCE_FINGERPRINT_MISMATCH", name)
        if not scan_eligible:
            continue
        try:
            source_text[name] = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise VerificationError("SOURCE_INVALID_UTF8", name) from exc

    couplings = inventory.get("couplings")
    if not isinstance(couplings, list) or not couplings:
        raise VerificationError("COUPLINGS_INVALID", "empty or not a list")
    ids: set[str] = set()
    categories: Counter[str] = Counter()
    sdk_files: set[str] = set()
    runtime_host_evidence: set[tuple[str, int]] = set()
    literal_host_evidence: set[tuple[str, int, str]] = set()
    config_environment_evidence: set[tuple[str, int, str]] = set()
    xhr_evidence: set[tuple[str, int]] = set()
    fetch_evidence: set[tuple[str, int]] = set()
    base_endpoint_evidence: set[tuple[str, int]] = set()
    literal_route_evidence: set[tuple[str, int, str]] = set()
    state_module_evidence: set[tuple[str, str]] = set()
    route_module_evidence: set[tuple[str, int, str]] = set()
    oauth_evidence: set[tuple[str, int]] = set()
    auth_sdk_evidence: set[tuple[str, int, str]] = set()
    auth_wrapper_evidence: set[tuple[str, int, str]] = set()
    sdk_mock_evidence: set[tuple[str, int]] = set()
    server_event_evidence: set[tuple[str, int, str]] = set()
    auth_cookie_evidence: set[tuple[str, int, str]] = set()
    load_data_evidence: set[tuple[str, int, str | None]] = set()
    for row in couplings:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str) or row["id"] in ids:
            raise VerificationError("COUPLING_ID_INVALID", str(row))
        ids.add(row["id"])
        source = row.get("sourcePath")
        line = row.get("line")
        category = row.get("category")
        if source not in source_text or not isinstance(line, int) or line < 1 or category not in CATEGORIES:
            raise VerificationError("COUPLING_SOURCE_INVALID", row["id"])
        lines = source_text[source].splitlines()
        expected_excerpt = lines[line - 1].strip() if line <= len(lines) else None
        if not expected_excerpt or row.get("evidence") != expected_excerpt:
            raise VerificationError("COUPLING_EXCERPT_INVALID", row["id"])
        if row.get("mechanism") in {"static-or-dynamic-import", "frontend-module-import", "route-bearing-export-import", "authentication-sdk-import", "authentication-wrapper-import", "server-event-client-import"}:
            imported = str(row.get("dependency", "")).rsplit(":", 1)[-1]
            if imported not in {"module", "dynamic-module", "mock-module"} and imported not in expected_excerpt:
                raise VerificationError("DEPENDENCY_NOT_IN_EXCERPT", row["id"])
        categories[category] += 1
        ownership = row.get("ownership")
        if not isinstance(ownership, dict):
            raise VerificationError("OWNERSHIP_INVALID", row["id"])
        if ownership.get("status") == "LINKED":
            owner = str(ownership.get("owner", ""))
            if (ownership.get("ownerType") != "reviewed-decision" or not owner.startswith("decision:")
                    or owner.removeprefix("decision:") not in reviewed_decisions):
                raise VerificationError("LINKED_OWNER_INVALID", row["id"])
            reviewed_owner = owner.removeprefix("decision:")
            exact_owner = source in exact_source_owners and reviewed_owner in exact_source_owners[source]
            special_owner = (
                reviewed_owner == "Asset viewer"
                and source.endswith("/routes/(user)/+layout.svelte")
                and "page.data.asset" in str(row.get("dependency", ""))
            )
            if category not in {"AUTHENTICATION", "RUNTIME_HOST"} and not exact_owner and not special_owner:
                dependency_context = str(row.get("dependency", "")).casefold()
                dependency_context = re.sub(r"\b(?:location|url)\.[A-Za-z_$][\w$]*", "", dependency_context)
                dependency_context = re.sub(r"\.[A-Za-z_$][\w$]*", "", dependency_context)
                semantic_context = f"{source.casefold()} {dependency_context}"
                tokens = OWNER_DOMAIN_TOKENS.get(reviewed_owner, ())
                if not tokens or not any(token in semantic_context for token in tokens):
                    raise VerificationError("LINKED_OWNER_SEMANTICALLY_UNSUPPORTED", f"{row['id']}:{owner}")
        elif ownership.get("status") == "REVIEW_REQUIRED":
            if ownership.get("owner") is not None or ownership.get("ownerType") is not None or not ownership.get("reason"):
                raise VerificationError("REVIEW_OWNER_INVALID", row["id"])
        else:
            raise VerificationError("OWNERSHIP_STATUS_INVALID", row["id"])
        if category == "GENERATED_CLIENT":
            sdk_files.add(source)
        if category == "RUNTIME_HOST" and row.get("mechanism") == "runtime-host-reference":
            runtime_host_evidence.add((source, line))
            dependency = str(row.get("dependency", ""))
            if dependency.startswith("literal-host:"):
                literal_host_evidence.add((source, line, dependency))
                if ownership.get("status") != "REVIEW_REQUIRED":
                    raise VerificationError("LITERAL_HOST_OWNER_NOT_REVIEWED", row["id"])
            if dependency.startswith("template-host:") and ownership.get("status") != "REVIEW_REQUIRED":
                raise VerificationError("TEMPLATE_HOST_OWNER_NOT_REVIEWED", row["id"])
            if re.fullmatch(r"(?:process\.env\.)?(?:PUBLIC_)?IMMICH_(?:SERVER_URL|BUY_HOST|PAY_HOST)", dependency):
                config_environment_evidence.add((source, line, dependency))
        if category == "SERVER_ROUTE" and row.get("mechanism") == "xml-http-request":
            xhr_evidence.add((source, line))
        if category == "SERVER_ROUTE" and row.get("mechanism") == "direct-fetch":
            fetch_evidence.add((source, line))
        if category == "SERVER_ROUTE" and row.get("mechanism") == "base-url-endpoint":
            base_endpoint_evidence.add((source, line))
        if category == "SERVER_ROUTE" and row.get("mechanism") == "literal-api-route":
            literal_route_evidence.add((source, line, str(row.get("dependency", ""))))
        if category == "SERVER_OWNED_STATE" and row.get("mechanism") == "frontend-module-import":
            state_module_evidence.add((source, str(row.get("dependency", "")).rsplit(":", 1)[0]))
        if category == "SERVER_ROUTE" and row.get("mechanism") == "route-bearing-export-import":
            route_module_evidence.add((source, line, str(row.get("dependency", ""))))
        if category == "AUTHENTICATION" and row.get("dependency") == "$lib/utils:oauth":
            oauth_evidence.add((source, line))
        if category == "AUTHENTICATION" and row.get("mechanism") == "authentication-sdk-import":
            auth_sdk_evidence.add((source, line, str(row.get("dependency", ""))))
            if ownership.get("owner") != "decision:Authentication and users":
                raise VerificationError("AUTH_SDK_OWNER_INVALID", row["id"])
        if category == "AUTHENTICATION" and row.get("mechanism") == "authentication-wrapper-import":
            auth_wrapper_evidence.add((source, line, str(row.get("dependency", ""))))
            if ownership.get("owner") != "decision:Authentication and users":
                raise VerificationError("AUTH_WRAPPER_OWNER_INVALID", row["id"])
        if category == "RUNTIME_HOST" and "PUBLIC_IMMICH_" in str(row.get("dependency", "")):
            if ownership.get("owner") != "decision:Legal and rebranding":
                raise VerificationError("COMMERCIAL_HOST_OWNER_INVALID", row["id"])
        specific_owner = None
        if "/routes/admin/library-management/" in source:
            specific_owner = "decision:Libraries and storage"
        elif "/routes/admin/queues/" in source or "/routes/admin/jobs-status/" in source:
            specific_owner = "decision:Jobs and notifications"
        if (specific_owner and (category == "GENERATED_CLIENT" or row.get("mechanism") in {
                "sveltekit-load-data", "sveltekit-page-state", "direct-fetch", "xml-http-request", "base-url-endpoint"
        }) and ownership.get("owner") != specific_owner):
            raise VerificationError("SPECIFIC_SOURCE_OWNER_INVALID", f"{row['id']}:{specific_owner}")
        if (source.endswith("/routes/(user)/+layout.svelte") and row.get("mechanism") == "sveltekit-page-state"
                and "page.data.asset" in str(row.get("dependency", ""))
                and ownership.get("owner") != "decision:Asset viewer"):
            raise VerificationError("ASSET_LAYOUT_OWNER_INVALID", row["id"])
        if (source in exact_source_owners and (category == "GENERATED_CLIENT" or row.get("mechanism") in {
                "sveltekit-load-data", "sveltekit-page-state"
        })):
            exact_owners = exact_source_owners[source]
            if len(exact_owners) == 1:
                expected_owner = f"decision:{next(iter(exact_owners))}"
                if ownership.get("owner") != expected_owner:
                    raise VerificationError("EXACT_AUTHORITY_OWNER_INVALID", f"{row['id']}:{expected_owner}")
            elif ownership.get("status") != "REVIEW_REQUIRED" or ownership.get("owner") is not None:
                raise VerificationError("EXACT_AUTHORITY_AMBIGUITY_INVALID", row["id"])
        if category == "GENERATED_CLIENT" and row.get("dependency") == "@immich/sdk:mock-module":
            sdk_mock_evidence.add((source, line))
        if category == "SERVER_OWNED_STATE" and row.get("mechanism") in {
            "server-event-client-import", "server-event-client-dependency"
        }:
            server_event_evidence.add((source, line, str(row.get("dependency", ""))))
            if ownership.get("owner") != "decision:Events and organization":
                raise VerificationError("SERVER_EVENT_OWNER_INVALID", row["id"])
        if category == "AUTHENTICATION" and row.get("mechanism") == "server-auth-cookie":
            auth_cookie_evidence.add((source, line, str(row.get("dependency", ""))))
            if ownership.get("owner") != "decision:Authentication and users":
                raise VerificationError("AUTH_COOKIE_OWNER_INVALID", row["id"])
        if category == "SERVER_OWNED_STATE" and row.get("mechanism") == "sveltekit-load-data":
            producer = str(row.get("dependency", "")).split("->", 1)[0]
            load_data_evidence.add((source, line, producer))
        if category == "SERVER_OWNED_STATE" and row.get("mechanism") == "sveltekit-page-state":
            dependency = str(row.get("dependency", ""))
            producer = None if dependency.startswith("sveltekit-dynamic-page-data:") else dependency.split("->", 1)[0]
            load_data_evidence.add((source, line, producer))

    if set(categories) != CATEGORIES or dict(sorted(categories.items())) != inventory.get("counts", {}).get("byCategory"):
        raise VerificationError("CATEGORY_COUNTS_INVALID", str(dict(categories)))
    if len(couplings) != inventory.get("counts", {}).get("couplings"):
        raise VerificationError("COUPLING_COUNT_INVALID", str(len(couplings)))
    raw_sdk_files = {
        name for name, text in source_text.items()
        if re.search(
            r"(?:\bimport\b[\s\S]{0,500}?\bfrom\s*|\bimport\s*\(|\b(?:vi|jest|vitest)\.mock\s*\()"
            r"['\"]@immich/sdk['\"]",
            text,
        )
    }
    package_manifest_text = source_text.get("Codebase/web/package.json", "")
    package_sdk_match = re.search(r"(?m)^\s*\"@immich/sdk\"\s*:\s*\"([^\"]+)\"", package_manifest_text)
    if package_sdk_match:
        raw_sdk_files.add("Codebase/web/package.json")
    false_comment_only = {
        name for name in raw_sdk_files
        if all(line.lstrip().startswith("//") for line in source_text[name].splitlines() if "@immich/sdk" in line)
    }
    if raw_sdk_files - false_comment_only != sdk_files:
        raise VerificationError("SDK_FILE_COVERAGE_INCOMPLETE", str(sorted((raw_sdk_files - false_comment_only) ^ sdk_files)))
    expected_server_events: set[tuple[str, int, str]] = set()
    for name, text in source_text.items():
        for module in SERVER_EVENT_MODULES:
            expected_server_events.update(
                (name, line_number, f"{module}:{symbol}")
                for line_number, symbol in oracle_all_import_records(text, module)
            )
    for module in SERVER_EVENT_MODULES:
        match = re.search(rf"(?m)^\s*\"{re.escape(module)}\"\s*:\s*\"([^\"]+)\"", package_manifest_text)
        if match:
            expected_server_events.add((
                "Codebase/web/package.json",
                package_manifest_text.count("\n", 0, match.start()) + 1,
                f"{module}:{match.group(1)}",
            ))
    if expected_server_events != server_event_evidence:
        raise VerificationError("SERVER_EVENT_CLIENT_COVERAGE_INCOMPLETE", str(sorted(expected_server_events ^ server_event_evidence)))
    expected_auth_cookies: set[tuple[str, int, str]] = set()
    for name, text in source_text.items():
        masked = oracle_mask_comments(text)
        expected_auth_cookies.update(
            (name, text.count("\n", 0, match.start()) + 1, "document.cookie")
            for match in re.finditer(r"\bdocument\.cookie\b", masked)
        )
        expected_auth_cookies.update(
            (name, text.count("\n", 0, match.start()) + 1, "cookie:immich_is_authenticated")
            for match in re.finditer(r"['\"]immich_is_authenticated['\"]", masked)
        )
    if expected_auth_cookies != auth_cookie_evidence:
        raise VerificationError("AUTH_COOKIE_COVERAGE_INCOMPLETE", str(sorted(expected_auth_cookies ^ auth_cookie_evidence)))
    expected_auth_sdk = {
        (name, line_number, f"@immich/sdk:{symbol}")
        for name, text in source_text.items()
        for line_number, symbol in oracle_import_records(text, "@immich/sdk")
        if symbol in AUTH_SDK_SYMBOLS
    }
    if expected_auth_sdk != auth_sdk_evidence:
        raise VerificationError("AUTH_SDK_COVERAGE_INCOMPLETE", str(sorted(expected_auth_sdk ^ auth_sdk_evidence)))
    required_auth_sdk = {
        ("Codebase/web/src/routes/auth/register/+page.svelte", 7, "@immich/sdk:signUpAdmin"),
        ("Codebase/web/src/routes/auth/pin-prompt/+page.svelte", 7, "@immich/sdk:unlockAuthSession"),
        ("Codebase/web/src/lib/components/user-settings-page/PinCodeCreateForm.svelte", 3, "@immich/sdk:setupPinCode"),
        ("Codebase/web/src/routes/(user)/user-settings/PinCodeChangeForm.svelte", 4, "@immich/sdk:changePinCode"),
        ("Codebase/web/src/lib/services/api-key.service.ts", 2, "@immich/sdk:createApiKey"),
        ("Codebase/web/src/lib/services/api-key.service.ts", 3, "@immich/sdk:deleteApiKey"),
        ("Codebase/web/src/lib/services/api-key.service.ts", 4, "@immich/sdk:updateApiKey"),
        ("Codebase/web/src/routes/(user)/user-settings/UserApiKeyList.svelte", 7, "@immich/sdk:getApiKeys"),
    }
    if not required_auth_sdk.issubset(auth_sdk_evidence):
        raise VerificationError("AUTH_SDK_FIXTURE_MISSING", str(sorted(required_auth_sdk - auth_sdk_evidence)))
    expected_hosts: set[tuple[str, int]] = set()
    expected_literal_hosts: set[tuple[str, int, str]] = set()
    expected_template_hosts: set[tuple[str, int, str]] = set()
    expected_config_environment: set[tuple[str, int, str]] = set()
    expected_xhr: set[tuple[str, int]] = set()
    expected_fetch: set[tuple[str, int]] = set()
    expected_base_endpoints: set[tuple[str, int]] = set()
    expected_literal_routes: set[tuple[str, int, str]] = set()
    global_host_pattern = re.compile(
        r"\b(?:globalThis|window|self)\.location\b"
        r"(?:\.(?:href|origin|host|hostname|protocol|port))?"
        r"|\bglobalThis\.origin\b"
        r"|\blocation\.(?:href|origin|host|hostname|protocol|port)\b"
        r"|\b(?:serverUrl|baseUrl|baseURL|externalDomain)\b"
        r"|\b(?:process\.env\.)?(?:PUBLIC_)?IMMICH_(?:SERVER_URL|BUY_HOST|PAY_HOST)\b"
    )
    for name, text in source_text.items():
        oracle_text = re.sub(
            r"/\*.*?\*/",
            lambda match: "".join("\n" if char == "\n" else " " for char in match.group(0)),
            text,
            flags=re.S,
        )
        oracle_text = re.sub(
            r"<!--[\s\S]*?-->",
            lambda match: "".join("\n" if char == "\n" else " " for char in match.group(0)),
            oracle_text,
        )
        location_shadowed = bool(re.search(
            r"\blocation\s*:\s*[A-Za-z_$]|\b(?:const|let|var|function|class)\s+location\b",
            oracle_text,
        ))
        url_variables = {
            match.group(1)
            for match in re.finditer(r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*new\s+URL\s*\(", oracle_text)
        }
        if re.search(r"\burl\s*:\s*URL\b|\(\s*\{[^}\n]*\burl\b[^}\n]*\}\s*\)", oracle_text):
            url_variables.add("url")
        url_property_pattern = re.compile(
            rf"\b(?:{'|'.join(re.escape(value) for value in sorted(url_variables))})\."
            r"(?:href|origin|host|hostname|protocol|port)\b"
        ) if url_variables else None
        for line_number, raw_line in enumerate(oracle_text.splitlines(), 1):
            code_line = re.sub(
                r"'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"|`(?:\\.|[^`\\])*`",
                "",
                raw_line,
            ).split("//", 1)[0]
            global_matches = [
                match for match in global_host_pattern.finditer(code_line)
                if not (location_shadowed and match.group(0).startswith("location."))
            ]
            bare_location = (
                not location_shadowed
                and re.search(r"(?<![\w$.])location\b(?!\.(?:href|origin|host|hostname|protocol|port)\b|\s*:)", code_line)
            )
            if global_matches or bare_location or (url_property_pattern and url_property_pattern.search(code_line)):
                expected_hosts.add((name, line_number))
        if "new XMLHttpRequest" in text:
            expected_xhr.update(
                (name, text.count("\n", 0, match.start()) + 1)
                for match in re.finditer(r"\b[A-Za-z_$][\w$]*\.open\s*\(", text)
            )
        for line_number, raw_line in enumerate(text.splitlines(), 1):
            code_line = re.sub(
                r"'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"|`(?:\\.|[^`\\])*`",
                "",
                raw_line,
            ).split("//", 1)[0]
            if re.search(r"\bfetch\s*\(", code_line):
                expected_fetch.add((name, line_number))
            if re.search(r"\bgetBaseUrl\s*\(\s*\)", code_line):
                expected_base_endpoints.add((name, line_number))
        source_path = Path(name)
        hash_comment_source = source_path.suffix.lower() in {".toml", ".sh", ".txt"} or "/bin/" in name
        literal_text = re.sub(
            r"<!--[\s\S]*?-->",
            lambda match: "".join("\n" if char == "\n" else " " for char in match.group(0)),
            text if hash_comment_source else oracle_mask_comments(text),
        )
        if hash_comment_source:
            literal_text = re.sub(
                r"(?m)^[ \t]*\#[^\n]*",
                lambda match: " " * len(match.group(0)),
                literal_text,
            )
        for match in re.finditer(
            r"\b(?:process\.env\.)?(?:PUBLIC_)?IMMICH_(?:SERVER_URL|BUY_HOST|PAY_HOST)\b",
            literal_text,
        ):
            line_number = text.count("\n", 0, match.start()) + 1
            if text.splitlines()[line_number - 1].lstrip().startswith("#"):
                continue
            expected_hosts.add((name, line_number))
            expected_config_environment.add((name, line_number, match.group(0)))
        for match in re.finditer(
            r"https?://(?P<host>(?:[A-Za-z0-9-]+|\$\{[^}\r\n]+\})(?:\.(?:[A-Za-z0-9-]+|\$\{[^}\r\n]+\}))+)(?::\d+)?",
            literal_text,
            re.I,
        ):
            if "${" not in match.group("host"):
                continue
            line_number = text.count("\n", 0, match.start()) + 1
            dependency = f"template-host:{match.group('host').casefold()}"
            expected_hosts.add((name, line_number))
            expected_template_hosts.add((name, line_number, dependency))
        for match in re.finditer(
            r"https?://(?P<host>[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*)(?::\d+)?(?![A-Za-z0-9.-]|\$\{)",
            literal_text,
            re.I,
        ):
            host = match.group("host").casefold()
            if host in {"example.com", "www.w3.org"}:
                continue
            line_number = text.count("\n", 0, match.start()) + 1
            dependency = f"literal-host:{host}"
            expected_hosts.add((name, line_number))
            expected_literal_hosts.add((name, line_number, dependency))
        for match in re.finditer(
            r"(?P<quote>['\"`])(?:[^'\"`\n]*?)(?P<route>/api(?:/(?:v\d+/)?[^'\"`\s)}]*)?)(?P=quote)",
            oracle_mask_comments(text),
        ):
            route_line = text.count("\n", 0, match.start()) + 1
            if (name, route_line) not in expected_fetch:
                expected_literal_routes.add((name, route_line, match.group("route")))
    if expected_hosts != runtime_host_evidence:
        raise VerificationError("RUNTIME_HOST_COVERAGE_INCOMPLETE", str(sorted(expected_hosts ^ runtime_host_evidence)))
    if expected_literal_hosts != literal_host_evidence:
        raise VerificationError("LITERAL_HOST_COVERAGE_INCOMPLETE", str(sorted(expected_literal_hosts ^ literal_host_evidence)))
    observed_template_hosts = {
        (source, line, dependency)
        for source, line, dependency in (
            (row.get("sourcePath"), row.get("line"), str(row.get("dependency", "")))
            for row in couplings
            if row.get("category") == "RUNTIME_HOST" and str(row.get("dependency", "")).startswith("template-host:")
        )
    }
    if expected_template_hosts != observed_template_hosts:
        raise VerificationError("TEMPLATE_HOST_COVERAGE_INCOMPLETE", str(sorted(expected_template_hosts ^ observed_template_hosts)))
    if expected_config_environment != config_environment_evidence:
        raise VerificationError("CONFIG_ENVIRONMENT_COVERAGE_INCOMPLETE", str(sorted(expected_config_environment ^ config_environment_evidence)))
    required_literal_hosts = {
        ("Codebase/web/src/routes/ErrorLayout.svelte", 69, "literal-host:discord.immich.app"),
        ("Codebase/web/src/routes/ErrorLayout.svelte", 75, "literal-host:github.com"),
        ("Codebase/web/src/routes/ErrorLayout.svelte", 81, "literal-host:docs.immich.app"),
        ("Codebase/web/src/lib/modals/AppDownloadModal.svelte", 12, "literal-host:play.google.com"),
        ("Codebase/web/src/lib/modals/AppDownloadModal.svelte", 16, "literal-host:apps.apple.com"),
        ("Codebase/web/src/lib/modals/AppDownloadModal.svelte", 20, "literal-host:f-droid.org"),
        ("Codebase/web/src/lib/utils/cast/gcast-destination.svelte.ts", 6, "literal-host:www.gstatic.com"),
    }
    if not required_literal_hosts.issubset(literal_host_evidence):
        raise VerificationError("LITERAL_HOST_FIXTURE_MISSING", str(sorted(required_literal_hosts - literal_host_evidence)))
    required_template_hosts = {
        ("Codebase/web/src/lib/modals/HelpAndFeedbackModal.svelte", 32,
         "template-host:docs.${info.version}.archive.immich.app"),
    }
    if not required_template_hosts.issubset(observed_template_hosts):
        raise VerificationError("TEMPLATE_HOST_FIXTURE_MISSING", str(sorted(required_template_hosts - observed_template_hosts)))
    required_frontend_config_hosts = {
        ("Codebase/web/svelte.config.js", 7, "literal-host:buy.immich.app"),
        ("Codebase/web/svelte.config.js", 8, "literal-host:pay.futo.org"),
        ("Codebase/web/vite.config.ts", 10, "literal-host:immich-server"),
        ("Codebase/web/mise.toml", 18, "literal-host:demo.immich.app"),
        ("Codebase/web/bin/immich-web", 8, "literal-host:immich-server"),
    }
    if not required_frontend_config_hosts.issubset(literal_host_evidence):
        raise VerificationError("FRONTEND_CONFIG_HOSTS_MISSING", str(sorted(required_frontend_config_hosts - literal_host_evidence)))
    required_frontend_environment = {
        ("Codebase/web/svelte.config.js", 7, "process.env.PUBLIC_IMMICH_BUY_HOST"),
        ("Codebase/web/svelte.config.js", 8, "process.env.PUBLIC_IMMICH_PAY_HOST"),
        ("Codebase/web/vite.config.ts", 10, "process.env.IMMICH_SERVER_URL"),
        ("Codebase/web/mise.toml", 18, "IMMICH_SERVER_URL"),
        ("Codebase/web/bin/immich-web", 8, "IMMICH_SERVER_URL"),
    }
    if not required_frontend_environment.issubset(config_environment_evidence):
        raise VerificationError("FRONTEND_CONFIG_ENVIRONMENT_MISSING", str(sorted(required_frontend_environment - config_environment_evidence)))
    required_static_metadata_host = {
        ("Codebase/web/static/.well-known/security.txt", 4, "literal-host:github.com"),
    }
    if not required_static_metadata_host.issubset(literal_host_evidence):
        raise VerificationError("STATIC_METADATA_HOST_MISSING", str(sorted(required_static_metadata_host - literal_host_evidence)))
    manifest_sdk_rows = {
        (str(row.get("sourcePath")), int(row.get("line", 0)), str(row.get("dependency")))
        for row in couplings if row.get("mechanism") == "package-manifest-dependency"
    }
    required_manifest_sdk = {("Codebase/web/package.json", 29, "@immich/sdk:workspace:*")}
    if manifest_sdk_rows != required_manifest_sdk:
        raise VerificationError("FRONTEND_SDK_MANIFEST_MISMATCH", str(sorted(manifest_sdk_rows ^ required_manifest_sdk)))
    if expected_xhr != xhr_evidence:
        raise VerificationError("XHR_COVERAGE_INCOMPLETE", str(sorted(expected_xhr ^ xhr_evidence)))
    if expected_fetch != fetch_evidence:
        raise VerificationError("FETCH_COVERAGE_INCOMPLETE", str(sorted(expected_fetch ^ fetch_evidence)))
    if expected_base_endpoints != base_endpoint_evidence:
        raise VerificationError("BASE_ENDPOINT_COVERAGE_INCOMPLETE", str(sorted(expected_base_endpoints ^ base_endpoint_evidence)))
    if expected_literal_routes != literal_route_evidence:
        raise VerificationError("LITERAL_ROUTE_COVERAGE_INCOMPLETE", str(sorted(expected_literal_routes ^ literal_route_evidence)))
    required_config_routes = {
        ("Codebase/web/vite.config.ts", 18, "/api"),
        ("Codebase/web/bin/immich-web", 10, "/api/server/config"),
    }
    if not required_config_routes.issubset(literal_route_evidence):
        raise VerificationError("FRONTEND_CONFIG_ROUTES_MISSING", str(sorted(required_config_routes - literal_route_evidence)))
    lib_root = root / "Codebase" / "web" / "src" / "lib"
    direct_state_modules: set[str] = set()
    for folder in (lib_root / "managers", lib_root / "stores"):
        for path in folder.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {".ts", ".js"} or ".spec." in path.name:
                continue
            if "@immich/sdk" not in path.read_text(encoding="utf-8"):
                continue
            relative = path.relative_to(lib_root).as_posix()
            relative = relative[:-3] if relative.endswith((".ts", ".js")) else relative
            module = f"$lib/{relative}"
            if module != "$lib/managers/auth-manager.svelte":
                direct_state_modules.add(module)
    expected_state_imports = {
        (name, module)
        for name, text in source_text.items()
        for module in direct_state_modules
        if re.search(rf"['\"]{re.escape(module)}['\"]", text)
    }
    if not expected_state_imports.issubset(state_module_evidence):
        raise VerificationError("SERVER_STATE_MODULE_COVERAGE_INCOMPLETE", str(sorted(expected_state_imports - state_module_evidence)))
    qualified_services, service_candidates = independent_route_oracle(root)
    expected_route_imports: set[tuple[str, int, str]] = set()
    expected_auth_wrappers: set[tuple[str, int, str]] = set()
    for name, text in source_text.items():
        for module, details in qualified_services.items():
            symbols = set(details["routeSymbols"])
            consumer = name
            consumer_stub = consumer[:-3] if consumer.endswith((".ts", ".js")) else consumer
            if module.startswith("$lib/"):
                specifier = module
            else:
                relative = posixpath.relpath(module, posixpath.dirname(consumer_stub))
                specifier = relative if relative.startswith(".") else f"./{relative}"
            for line_number, symbol in oracle_import_records(text, specifier):
                auth_candidate = symbol in set(details.get("authSymbols", []))
                broad = symbol.startswith("namespace:") or symbol in {"module", "dynamic-module", "mock-module"}
                members = details.get("classRouteMembers", {}).get(symbol)
                used = True
                if members:
                    local_names = [local for original, local in oracle_import_bindings(text, specifier) if original == symbol]
                    used = any(
                        re.search(rf"\bnew\s+{re.escape(local)}\s*\(", oracle_mask_comments(text))
                        or any(re.search(rf"\b{re.escape(local)}\.{re.escape(member)}\s*\(", oracle_mask_comments(text))
                               for member in members)
                        for local in local_names
                    )
                if auth_candidate and used:
                    expected_auth_wrappers.add((name, line_number, f"{module}:{symbol}"))
                if symbol not in symbols and not broad:
                    continue
                if not used:
                    continue
                if symbol in symbols or broad:
                    expected_route_imports.add((name, line_number, f"{module}:{symbol}"))
    if expected_route_imports != route_module_evidence:
        raise VerificationError("SERVER_ROUTE_MODULE_COVERAGE_INCOMPLETE", str(sorted(expected_route_imports ^ route_module_evidence)))
    if expected_auth_wrappers != auth_wrapper_evidence:
        raise VerificationError("AUTH_WRAPPER_COVERAGE_INCOMPLETE", str(sorted(expected_auth_wrappers ^ auth_wrapper_evidence)))
    required_route_edges = {
        ("Codebase/web/src/lib/components/asset-viewer/DetailPanelTags.svelte", 7,
         "$lib/utils/asset-utils:removeTag"),
        ("Codebase/web/src/routes/(user)/s/[slug]/[[photos=photos]]/[[assetId=id]]/+page.ts", 1,
         "$lib/utils/shared-links:loadSharedLink"),
        ("Codebase/web/src/routes/(user)/share/[key]/[[photos=photos]]/[[assetId=id]]/+page.ts", 1,
         "$lib/utils/shared-links:loadSharedLink"),
        ("Codebase/web/src/lib/components/asset-viewer/AssetViewer.svelte", 9,
         "$lib/components/asset-viewer/PreloadManager.svelte:preloadManager"),
        ("Codebase/web/src/lib/managers/cast-manager.svelte.ts", 4,
         "$lib/utils/cast/gcast-destination.svelte:GCastDestination"),
        ("Codebase/web/src/service-worker/index.ts", 6,
         "Codebase/web/src/service-worker/request:handleFetch"),
    }
    if not required_route_edges.issubset(route_module_evidence):
        raise VerificationError("SERVER_ROUTE_WRAPPER_FIXTURE_MISSING", str(sorted(required_route_edges - route_module_evidence)))
    required_auth_wrappers = {
        ("Codebase/web/src/lib/modals/PinCodeResetModal.svelte", 3,
         "$lib/services/user.service:handleResetPinCode"),
        ("Codebase/web/src/routes/(user)/user-settings/ChangePasswordSettings.svelte", 2,
         "$lib/services/user.service:handleChangePassword"),
        ("Codebase/web/src/lib/modals/ApiKeyCreateModal.svelte", 4,
         "$lib/services/api-key.service:handleCreateApiKey"),
        ("Codebase/web/src/lib/modals/ApiKeyUpdateModal.svelte", 3,
         "$lib/services/api-key.service:handleUpdateApiKey"),
        ("Codebase/web/src/routes/(user)/user-settings/UserApiKeyList.svelte", 5,
         "$lib/services/api-key.service:getApiKeyActions"),
        ("Codebase/web/src/routes/(user)/user-settings/UserApiKeyList.svelte", 5,
         "$lib/services/api-key.service:getApiKeysActions"),
    }
    if not required_auth_wrappers.issubset(auth_wrapper_evidence):
        raise VerificationError("AUTH_WRAPPER_FIXTURE_MISSING", str(sorted(required_auth_wrappers - auth_wrapper_evidence)))
    forbidden_route_dependencies = {
        "$lib/services/queue.service:asQueueItem",
        "$lib/services/shared-link.service:asUrl",
    }
    observed_dependencies = {dependency for _, _, dependency in route_module_evidence}
    if forbidden_route_dependencies & observed_dependencies:
        raise VerificationError("PURE_WRAPPER_EXPORT_FALSE_POSITIVE", str(sorted(forbidden_route_dependencies & observed_dependencies)))
    forbidden_route_edges = {
        ("Codebase/web/src/lib/services/app.service.ts", 5,
         "$lib/utils/cast/gcast-destination.svelte:GCastDestination"),
    }
    if forbidden_route_edges & route_module_evidence:
        raise VerificationError("PURE_CLASS_MEMBER_FALSE_POSITIVE", str(sorted(forbidden_route_edges & route_module_evidence)))
    expected_route_oracle = [
        {"module": module, **details}
        for module, details in sorted(qualified_services.items())
    ]
    forbidden_route_modules = {"$lib/components/shared-components/album-selection/album-selection-utils", "$lib/route"}
    observed_modules = {row["module"] for row in expected_route_oracle}
    if forbidden_route_modules & observed_modules:
        raise VerificationError("LOCAL_MODULE_FALSE_POSITIVE", str(sorted(forbidden_route_modules & observed_modules)))
    if inventory.get("serverRouteModuleOracle") != expected_route_oracle:
        raise VerificationError("SERVER_ROUTE_MODULE_ORACLE_MISMATCH", "service qualification differs")
    if "fileUploadHandler" not in set(qualified_services.get("$lib/utils/file-uploader", {}).get("routeSymbols", [])):
        raise VerificationError("NONPREFIX_SDK_ROUTE_UNREACHABLE", "checkBulkUpload -> fileUploadHandler")
    if "oauth" in set(qualified_services.get("$lib/utils", {}).get("routeSymbols", [])):
        raise VerificationError("AUTH_OBJECT_ROUTE_DUPLICATE", "$lib/utils:oauth")
    required_nonprefix_sdk = {
        ("Codebase/web/src/lib/utils/file-uploader.ts", "@immich/sdk:checkBulkUpload"),
        ("Codebase/web/src/lib/utils.ts", "@immich/sdk:unlinkOAuthAccount"),
    }
    actual_generated = {
        (str(row.get("sourcePath")), str(row.get("dependency")))
        for row in couplings if row.get("category") == "GENERATED_CLIENT"
    }
    if not required_nonprefix_sdk.issubset(actual_generated):
        raise VerificationError("NONPREFIX_SDK_EVIDENCE_MISSING", str(sorted(required_nonprefix_sdk - actual_generated)))
    expected_route_exclusions = [
        {
            "module": module,
            "reason": (
                "Authentication coupling is inventoried under AUTHENTICATION."
                if module == "$lib/utils/auth"
                else "No route-bearing exported symbol was discovered."
            ),
        }
        for module in sorted(
            module for module, text in service_candidates.items()
            if module not in qualified_services and (
                module == "$lib/utils/auth"
                or re.search(r"@immich/sdk|\bfetch\s*\(|\bXMLHttpRequest\b|['\"`]/api/|\bgetBaseUrl\s*\(",
                             oracle_mask_comments(text))
            )
        )
    ]
    if inventory.get("serverRouteModuleExclusions") != expected_route_exclusions:
        raise VerificationError("SERVER_ROUTE_MODULE_EXCLUSIONS_MISMATCH", "local-only service exclusions differ")
    expected_oauth = {
        (name, line_number)
        for name, text in source_text.items()
        for line_number, line in enumerate(text.splitlines(), 1)
        if "$lib/utils" in line and re.search(r"\boauth\b", line)
    }
    if expected_oauth != oauth_evidence:
        raise VerificationError("OAUTH_COUPLING_COVERAGE_INCOMPLETE", str(sorted(expected_oauth ^ oauth_evidence)))
    expected_sdk_mocks = {
        (name, line_number)
        for name, text in source_text.items()
        for line_number, line in enumerate(text.splitlines(), 1)
        if re.search(r"\b(?:vi|jest|vitest)\.mock\s*\(\s*['\"]@immich/sdk['\"]", line)
    }
    if expected_sdk_mocks != sdk_mock_evidence:
        raise VerificationError("SDK_MOCK_COVERAGE_INCOMPLETE", str(sorted(expected_sdk_mocks ^ sdk_mock_evidence)))
    expected_load_edges: set[tuple[str, int, str | None]] = set()
    expected_load_oracle: list[dict[str, Any]] = []
    routes_root = root / "Codebase" / "web" / "src" / "routes"
    for path in actual_paths:
        if path.name not in {"+page.svelte", "+layout.svelte"}:
            continue
        name = path.relative_to(root).as_posix()
        expected_type = "PageData" if path.name == "+page.svelte" else "LayoutData"
        for line_number, line in enumerate(source_text[name].splitlines(), 1):
            type_match = re.search(
                rf"\bimport\s+(?:type\s*)?\{{[^}}]*\b{expected_type}\b[^}}]*\}}\s+from\s+['\"]([^'\"]*\$types)['\"]",
                line,
            )
            if not type_match:
                continue
            producer_paths: set[Path] = set()
            primary = path.with_suffix(".ts")
            if not primary.is_file():
                primary = path.with_suffix(".js")
            if primary.is_file():
                producer_paths.add(primary)
            ancestor = path.parent
            while ancestor == routes_root or routes_root in ancestor.parents:
                for suffix in (".ts", ".js"):
                    layout = ancestor / f"+layout{suffix}"
                    if layout.is_file():
                        producer_paths.add(layout)
                        break
                if ancestor == routes_root:
                    break
                ancestor = ancestor.parent
            if not producer_paths:
                raise VerificationError("LOAD_DATA_PRODUCER_UNAVAILABLE", name)
            for producer_path in sorted(producer_paths, key=lambda value: value.as_posix().casefold()):
                producer = producer_path.relative_to(root).as_posix()
                producer_text = producer_path.read_text(encoding="utf-8")
                qualifications = []
                if "@immich/sdk" in producer_text:
                    qualifications.append("generated-client")
                if "$lib/utils/auth" in producer_text:
                    qualifications.append("authentication")
                if re.search(r"['\"]\$lib/(?:managers|stores)/", producer_text):
                    qualifications.append("server-state-module")
                if re.search(r"['\"]\$lib/(?:services/|utils/(?:shared-links|license-utils))", producer_text):
                    qualifications.append("server-route-wrapper")
                if not qualifications:
                    continue
                expected_load_edges.add((name, line_number, producer))
                expected_load_oracle.append({
                    "producer": producer,
                    "consumer": name,
                    "consumerLine": line_number,
                    "dataType": expected_type,
                    "sourceTypesModule": type_match.group(1),
                    "qualifications": qualifications,
                    "producerSha256": sha256_file(producer_path),
                })
    for path in actual_paths:
        name = path.relative_to(root).as_posix()
        if name not in source_text:
            continue
        text = source_text[name]
        if not re.search(r"import\s*\{[^}]*\bpage\b[^}]*\}\s*from\s*['\"]\$app/(?:state|stores)['\"]", text, re.S):
            continue
        oracle_text = re.sub(
            r"/\*.*?\*/",
            lambda match: "".join("\n" if char == "\n" else " " for char in match.group(0)),
            text,
            flags=re.S,
        )
        for line_number, raw_line in enumerate(oracle_text.splitlines(), 1):
            code_line = re.sub(
                r"'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"|`(?:\\.|[^`\\])*`",
                "",
                raw_line,
            ).split("//", 1)[0]
            fields = sorted(set(re.findall(r"(?<![\w$])\$?page\.data\.([A-Za-z_$][\w$]*)", code_line)))
            for field in fields:
                matches: list[tuple[Path, list[str]]] = []
                if path.name in {"+page.svelte", "+layout.svelte"}:
                    producer_paths: set[Path] = set()
                    primary = path.with_suffix(".ts")
                    if not primary.is_file():
                        primary = path.with_suffix(".js")
                    if primary.is_file():
                        producer_paths.add(primary)
                    ancestor = path.parent
                    while ancestor == routes_root or routes_root in ancestor.parents:
                        for suffix in (".ts", ".js"):
                            layout = ancestor / f"+layout{suffix}"
                            if layout.is_file():
                                producer_paths.add(layout)
                                break
                        if ancestor == routes_root:
                            break
                        ancestor = ancestor.parent
                    for producer_path in sorted(producer_paths, key=lambda value: value.as_posix().casefold()):
                        producer_text = producer_path.read_text(encoding="utf-8")
                        qualifications = []
                        if "@immich/sdk" in producer_text:
                            qualifications.append("generated-client")
                        if "$lib/utils/auth" in producer_text:
                            qualifications.append("authentication")
                        if re.search(r"['\"]\$lib/(?:managers|stores)/", producer_text):
                            qualifications.append("server-state-module")
                        if re.search(r"['\"]\$lib/(?:services/|utils/(?:shared-links|license-utils))", producer_text):
                            qualifications.append("server-route-wrapper")
                        if qualifications and re.search(rf"\b{re.escape(field)}\b\s*(?:,|:)", producer_text):
                            matches.append((producer_path, qualifications))
                if matches:
                    for producer_path, qualifications in matches:
                        producer = producer_path.relative_to(root).as_posix()
                        expected_load_edges.add((name, line_number, producer))
                        expected_load_oracle.append({
                            "producer": producer,
                            "consumer": name,
                            "consumerLine": line_number,
                            "dataType": "RuntimePageData",
                            "accessedField": field,
                            "sourceTypesModule": "$app/state-or-stores",
                            "qualifications": qualifications,
                            "producerSha256": sha256_file(producer_path),
                        })
                else:
                    expected_load_edges.add((name, line_number, None))
                    expected_load_oracle.append({
                        "producer": None,
                        "consumer": name,
                        "consumerLine": line_number,
                        "dataType": "RuntimePageData",
                        "accessedField": field,
                        "sourceTypesModule": "$app/state-or-stores",
                        "qualifications": ["dynamic-route-producer-review-required"],
                        "producerSha256": None,
                    })
    if expected_load_edges != load_data_evidence:
        raise VerificationError("LOAD_DATA_EDGE_COVERAGE_INCOMPLETE", str(sorted(expected_load_edges ^ load_data_evidence)))
    if sorted(expected_load_oracle, key=lambda row: (
        row["consumer"].casefold(), str(row["producer"]).casefold(), row["consumerLine"], row.get("accessedField", "")
    )) != inventory.get("svelteKitLoadDataOracle"):
        raise VerificationError("LOAD_DATA_ORACLE_MISMATCH", "producer/consumer oracle differs")

    current = {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in sorted((root / "Codebase").rglob("*")) if path.is_file()
    }
    expected = baseline(root)
    if current != expected:
        raise VerificationError("CODEBASE_BASELINE_MISMATCH", f"expected {len(expected)}, observed {len(current)}")
    return {
        "status": "PASS",
        "sourceFiles": len(actual_paths),
        "textScannedFiles": len(source_text),
        "couplings": len(couplings),
        "categoryCounts": dict(sorted(categories.items())),
        "generatedClientSourceFiles": len(sdk_files),
        "codebaseFiles": len(current),
    }


if __name__ == "__main__":
    try:
        print(json.dumps(verify(), indent=2))
    except VerificationError as exc:
        print(json.dumps({"status": "FAIL", "error": {"code": exc.code, "message": str(exc)}}), file=sys.stderr)
        raise SystemExit(1)
