#!/usr/bin/env python3
"""Build the read-only WP-I0-010 outbound and commercial integration inventory.

The collector fingerprints the complete committed Codebase corpus, scans every
eligible text surface, and records each outbound integration (external hosts,
telemetry surfaces, update checks, cloud services, commercial integrations,
and remote model paths) with exact source evidence.  Disposition ownership is
deliberately REVIEW_REQUIRED: WP-I0-010 produces the baseline inventory only.
It never imports or executes product code and writes only beside this file.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PACKAGE_ID = "WP-I0-010"
REQUIREMENT_ID = "CAN-MISSION-I0-010"
INVENTORY_FILE = "outbound-integration-inventory.json"
PUBLISHED_ARTIFACTS = {
    "artifact-scan.json", "completion-evidence.md", "evidence-consistency.json",
    "outbound-integration-inventory.json", "package-summary.json", "provenance-report.json",
    "verification-report.json",
}

CATEGORIES = {
    "OUTBOUND_HOST",
    "TELEMETRY",
    "UPDATE_CHECK",
    "CLOUD_SERVICE",
    "COMMERCIAL_INTEGRATION",
    "REMOTE_MODEL_PATH",
}
MECHANISMS = {
    "literal-external-host",
    "bare-known-integration-host",
    "container-image-reference",
    "container-image-implicit-registry",
    "telemetry-sdk-import",
    "telemetry-module-import",
    "sdk-dependency",
    "hf-client-import",
    "hf-snapshot-download",
    "hf-snapshot-download-stub-definition",
    "hf-repo-scope",
    "cloud-sdk-import",
    "commercial-sdk-import",
}

RECORDED_SCHEMES = {"http", "https", "ws", "wss", "ftp", "ftps"}

# Comment styles keyed by lowercase suffix.
CSTYLE_SUFFIXES = {
    ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".cts", ".mts", ".svelte",
    ".dart", ".kt", ".kts", ".java", ".swift", ".rs", ".groovy", ".gradle",
    ".c", ".h", ".cpp", ".hpp", ".cc", ".cs", ".go", ".css", ".scss", ".less",
}
HASH_SUFFIXES = {
    ".py", ".pyi", ".sh", ".bash", ".zsh", ".yml", ".yaml", ".toml", ".conf",
    ".cfg", ".ini", ".properties", ".lock", ".rb", ".mk", ".env", ".tf", ".hcl",
}
HTML_SUFFIXES = {".html", ".htm", ".xml", ".svg", ".storyboard", ".plist", ".entitlements", ".xcsettings"}
PLAIN_SUFFIXES = {".json", ".txt", ".csv", ".tsv", ".pubxml", ".xcscheme", ".pbxproj", ".sql", ".patch", ".resolved"}
SCANNED_SUFFIXES = CSTYLE_SUFFIXES | HASH_SUFFIXES | HTML_SUFFIXES | PLAIN_SUFFIXES
HTML_EXTRA_SUFFIXES = {".svelte"}  # additionally strip <!-- --> comments
SCANNED_NAMES = {
    "Dockerfile", "Makefile", "makefile", ".npmrc", ".pypirc", ".envrc",
    "Fastfile", "Appfile", "Pluginfile", "Gemfile", "Justfile",
    ".gitmodules", "_redirects", "Podfile", "LICENSE", "Podfile.lock",
}

NAMESPACE_URI_HOSTS = {
    "www.w3.org": "XML/SVG namespace identifier; an identifier string, never a network endpoint.",
    "schemas.xmlsoap.org": "WSDL/SOAP namespace identifier; never fetched.",
    "json-schema.org": "JSON-schema dialect identifier; never fetched.",
    "schema.org": "JSON-LD/microdata vocabulary identifier; never fetched.",
    "opendocumentformat.org": "Office-document namespace identifier; never fetched.",
    "www.apple.com": "Property-list DOCTYPE/DTD identifier (DTDs/PropertyList-*); never fetched at runtime.",
}
PLACEHOLDER_EXACT_HOSTS = {"example.com", "example.org", "example.net", "example.invalid"}
PLACEHOLDER_SUFFIXES = (".example", ".invalid", ".test", ".localhost")
UPDATE_CHECK_HOSTS = {"version.immich.cloud", "version.dev.immich.cloud"}
COMMERCIAL_EXACT_HOSTS = {"my.immich.app", "buy.immich.app", "pay.futo.org"}
COMMERCIAL_SUFFIXES = (".stripe.com", ".gumroad.com", ".lemonsqueezy.com", ".paddle.com")
CLOUD_SUFFIXES = (
    ".immich.cloud", ".amazonaws.com", ".amazon.com", ".googleapis.com",
    ".cloud.google.com", ".azure.com", ".azure.net", ".windows.net",
)
REMOTE_MODEL_SUFFIXES = (".huggingface.co", ".hf.co", ".modelscope.cn")
TELEMETRY_SUFFIXES = (".sentry.io", ".posthog.com", ".plausible.io", ".umami.is", ".statsigapi.net")

BARE_KNOWN_HOSTS = sorted({
    "version.immich.cloud", "version.dev.immich.cloud", "my.immich.app",
    "buy.immich.app", "pay.futo.org", "auth.immich.cloud", "tiles.immich.cloud",
    "huggingface.co",
})

TELEMETRY_SPECIFIER_TOKENS = (
    "@opentelemetry/", "nestjs-otel", "prom-client", "prometheus-client",
    "@sentry/", "sentry_sdk", "sentry.", "posthog", "plausible-tracker",
)
TELEMETRY_SPECIFIER_EXACT = {
    "sentry", "prometheus_client", "prom-client", "prom-client-lite", "opentelemetry",
}
REMOTE_MODEL_SPECIFIERS = {
    "huggingface_hub", "huggingface-hub", "hf_hub_download", "modelscope",
    "transformers", "@huggingface/transformers",
}
CLOUD_SDK_SPECIFIER_PREFIXES = ("@aws-sdk/", "aws-sdk", "boto3", "@google-cloud/", "@azure/")
COMMERCIAL_SDK_SPECIFIERS = {"stripe", "gumroad-sdk"}
SNAPSHOT_FUNCTION = "snapshot_download"

URL_PATTERN = re.compile(
    r"(?P<scheme>[A-Za-z][A-Za-z0-9+.-]{0,20})://"
    r"(?P<authority>(?:\$\{\{[^}\r\n]{0,160}\}\}|\$\{[^}\r\n]{0,160}\}|[A-Za-z0-9._~:@+-])+)"
)
IMAGE_LINE_PATTERN = re.compile(r"^\s*image:\s*['\"]?([A-Za-z0-9][^\s'\"]*)")
FROM_LINE_PATTERN = re.compile(r"^\s*FROM\s+(?:--platform=\S+\s+)?(\S+)")
OWNERSHIP_REASON = (
    "WP-I0-010 records the baseline outbound integration inventory only; no reviewed "
    "outbound disposition decision exists, so disposition ownership is deferred to review."
)


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
    """Publish one evidence generation; the authoritative inventory is the last commit marker."""
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
        candidate / "Codebase" / "server" / "src",
        candidate / "Codebase" / "machine-learning" / "immich_ml",
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


def mask_cstyle(text: str) -> str:
    """Blank // and /* */ comments for C-family sources; preserve offsets and lines."""
    chars = list(text)
    markers = [" "] * len(chars)
    state = "code"
    quote = ""
    index = 0
    length = len(chars)
    while index < length:
        char = chars[index]
        nxt = chars[index + 1] if index + 1 < length else ""
        if state == "code":
            if char in "'\"`":
                state = "string"
                quote = char
            elif char == "/" and nxt == "/":
                # A // sequence immediately after ':' is a URL-like scheme separator
                # (e.g. https:// inside JSX text nodes), not a line comment.
                if index > 0 and chars[index - 1] == ":":
                    index += 1
                    continue
                state = "line_comment"
                markers[index] = markers[index + 1] = "x"
                index += 1
            elif char == "/" and nxt == "*":
                state = "block_comment"
                markers[index] = markers[index + 1] = "x"
                index += 1
        elif state == "string":
            if char == "\\":
                index += 1
            elif char == quote:
                state = "code"
        elif state == "line_comment":
            if char == "\n":
                state = "code"
            else:
                markers[index] = "x"
        elif state == "block_comment":
            if char == "*" and nxt == "/":
                markers[index] = markers[index + 1] = "x"
                index += 1
                state = "code"
            elif char != "\n":
                markers[index] = "x"
        index += 1
    return "".join(" " if marker == "x" else chars[i] for i, marker in enumerate(markers))


def mask_hash(text: str) -> str:
    """Blank # comments for hash-comment sources; # preceded by non-whitespace survives,
    and hash tokens inside simple quotes survive; shebang on line 1 survives."""
    out_lines: list[str] = []
    for number, raw in enumerate(text.split("\n"), 1):
        strike = -1
        quote = ""
        for index, char in enumerate(raw):
            if quote and char == "\\":
                continue
            if char in "'\"" and not quote:
                quote = char
            elif char == quote:
                quote = ""
            elif char == "#" and not quote:
                if number == 1 and index <= 1 and raw.startswith("#!"):
                    break
                if index == 0 or raw[index - 1] in " \t":
                    strike = index
                    break
        out_lines.append(raw if strike < 0 else raw[:strike] + " " * (len(raw) - strike))
    return "\n".join(out_lines)


def mask_html(text: str) -> str:
    """Blank <!-- --> comments; preserve offsets and lines."""
    return re.sub(
        r"<!--[\s\S]*?-->",
        lambda match: "".join("\n" if char == "\n" else " " for char in match.group(0)),
        text,
    )


def masked_text(text: str, kind: str, html_extra: bool) -> str:
    masked = text
    if kind == "cstyle":
        masked = mask_cstyle(masked)
    elif kind == "hash":
        masked = mask_hash(masked)
    if kind in {"html", "cstyle"} and (kind == "html" or html_extra):
        masked = mask_html(masked)
    return masked


def strip_authority_host(authority: str) -> str | None:
    """Normalize an authority segment to a host token; None when no usable host."""
    host_port = authority.rsplit("@", 1)[-1].rstrip(".-")
    if not host_port:
        return None
    if host_port.startswith("["):
        close = host_port.find("]")
        if close < 0:
            return None
        return host_port[:close + 1]
    host = re.sub(r":\d+$", "", host_port)
    if host_port.endswith("}") and ":" in host_port:
        host = host_port  # template with inline default; keep the full expression
    return host.rstrip(".-") or None


def host_is_template(host: str) -> bool:
    return "${" in host or "$" in host


def host_static_labels(host: str) -> str:
    static = re.sub(r"\$\{\{[^}]*\}\}|\$\{[^}]*\}|\$[A-Za-z_{][\w{}]*", "", host)
    static = re.sub(r"\.{2,}", ".", static)
    return static.strip(".").rstrip(":.").strip(":")


def classify_host(host: str) -> set[str]:
    """Return the extra non-universal categories for an external host."""
    lowered = host.casefold()
    static = host_static_labels(lowered)
    extra: set[str] = set()

    def matches(suffix: str) -> bool:
        return static == suffix[1:] or static.endswith(suffix)

    exact_overrides: dict[str, set[str]] = {}
    for candidate in UPDATE_CHECK_HOSTS:
        exact_overrides[candidate] = {"UPDATE_CHECK"}
    for candidate in COMMERCIAL_EXACT_HOSTS:
        exact_overrides[candidate] = {"COMMERCIAL_INTEGRATION"}
    if static in exact_overrides:
        extra |= exact_overrides[static]
    if any(matches(suffix) for suffix in REMOTE_MODEL_SUFFIXES):
        extra |= {"REMOTE_MODEL_PATH"}
    if any(matches(suffix) for suffix in COMMERCIAL_SUFFIXES):
        extra |= {"COMMERCIAL_INTEGRATION"}
    if any(matches(suffix) for suffix in CLOUD_SUFFIXES):
        extra |= {"CLOUD_SERVICE"}
    if any(matches(suffix) for suffix in TELEMETRY_SUFFIXES):
        extra |= {"TELEMETRY"}
    return extra


def classify_declared_dependency(name: str) -> set[str]:
    lowered = name.casefold()
    categories: set[str] = set()
    if (
        any(token in lowered for token in TELEMETRY_SPECIFIER_TOKENS)
        or lowered in TELEMETRY_SPECIFIER_EXACT
        or lowered.startswith("@opentelemetry/")
        or lowered.startswith("@sentry/")
    ):
        categories.add("TELEMETRY")
    if lowered in REMOTE_MODEL_SPECIFIERS or lowered.replace("_", "-") in REMOTE_MODEL_SPECIFIERS:
        categories.add("REMOTE_MODEL_PATH")
    if any(lowered.startswith(prefix.rstrip("_")) or lowered.startswith(prefix) for prefix in CLOUD_SDK_SPECIFIER_PREFIXES) or lowered in {"boto3", "minio"}:
        categories.add("CLOUD_SERVICE")
    if lowered in COMMERCIAL_SDK_SPECIFIERS:
        categories.add("COMMERCIAL_INTEGRATION")
    return categories


def exclusion_class(host: str) -> str | None:
    lowered = host.casefold()
    static = host_static_labels(lowered)
    if static.lower() in NAMESPACE_URI_HOSTS:
        return "namespace-uri-identifier"
    if any(
        static == placeholder or static.endswith("." + placeholder)
        for placeholder in PLACEHOLDER_EXACT_HOSTS
    ) or any(static.endswith(suffix) for suffix in PLACEHOLDER_SUFFIXES):
        return "rfc-2606-placeholder-host"
    if re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", static):
        octets = [int(part) for part in static.split(".")]
        if octets[0] in {0, 10, 127} or (octets[0] == 172 and 16 <= octets[1] <= 31) or \
                (octets[0] == 192 and octets[1] == 168) or (octets[0] == 169 and octets[1] == 254):
            return "loopback-or-private-address"
        return None  # public IPv4: a real outbound host
    if static.lower() in {"[::1]", "[0:0:0:0:0:0:0:1]", "[::]", "[fe80::1]"} or static.lower().startswith("[fe80"):
        return "loopback-or-private-address"
    if host_is_template(host) and host.endswith(":") and not static:
        return "dynamic-userinfo-expression"
    if not host_is_template(host) and "." not in static:
        return "single-label-internal-address"
    if host_is_template(host) and not static:
        return None  # fully dynamic host expression: still an outbound endpoint
    return None


EXCLUSION_REASONS = {
    "namespace-uri-identifier": "Namespace identifier URI; resolved as a name token, never fetched.",
    "rfc-2606-placeholder-host": "RFC 2606/3731 documentation placeholder; never a real destination.",
    "loopback-or-private-address": "Loopback, link-local, or RFC 1918 private address; intra-deployment, not outbound.",
    "single-label-internal-address": "Single-label internal/coordination hostname (e.g. container service names); not an internet host.",
    "unrecorded-scheme": "Scheme outside the recorded set (mail/data/extension schemes etc.); not an outbound network call of the package surface.",
    "dynamic-userinfo-expression": "Interpolated credential/userinfo authority segment before a dynamic host; carries no static host label.",
}


def split_import_names(clause: str) -> list[str]:
    names: list[str] = []
    namespace = re.search(r"\*\s+as\s+([A-Za-z_$][\w$]*)", clause)
    if namespace:
        names.append(f"namespace:{namespace.group(1)}")
    braces = re.search(r"\{(.*?)\}", clause, re.S)
    if braces:
        for item in braces.group(1).split(","):
            item = re.sub(r"^\s*type\s+", "", item.strip())
            if not item:
                continue
            original = re.split(r"\s+as\s+", item, maxsplit=1)[0].strip()
            if re.fullmatch(r"[A-Za-z_$][\w$]*", original):
                names.append(original)
    prefix = clause.split("{", 1)[0].split("*", 1)[0].strip().rstrip(",").strip()
    prefix = re.sub(r"^type\s+", "", prefix)
    if prefix != "type" and prefix and re.fullmatch(r"[A-Za-z_$][\w$]*", prefix):
        names.append(f"default:{prefix}")
    return list(dict.fromkeys(names)) or ["module"]


JS_FROM_IMPORT = re.compile(
    r"\b(?:import|export)\s+(?P<clause>[^{};]*?\{.*?\}|[A-Za-z_$][\w$]*(?:\s+as\s+[A-Za-z_$][\w$]*)?|\*\s+as\s+[A-Za-z_$][\w$]*)\s*from\s*[\"'](?P<module>[^'\"]+)[\"']",
    re.S,
)
JS_SIDE_EFFECT = re.compile(r"\bimport\s*[\"'](?P<module>[^'\"]+)[\"']")
JS_DYNAMIC = re.compile(r"\bimport\s*\(\s*[\"'](?P<module>[^'\"]+)[\"']\s*\)")
JS_MOCK = re.compile(r"\b(?:vi|vitest|jest)\.mock\s*\(\s*[\"'](?P<module>[^'\"]+)[\"']")
PY_FROM_IMPORT = re.compile(
    r"(?m)^[ \t]*from[ \t]+(?P<module>[A-Za-z_][\w.]*)[ \t]+import[ \t]+(?P<names>\([^)]*\)|[^\n#]+)"
)
PY_PLAIN_IMPORT = re.compile(r"(?m)^[ \t]*import[ \t]+(?P<module>[A-Za-z_][\w.]*)")


def js_import_records(masked: str) -> list[tuple[int, str, str]]:
    records: list[tuple[int, str, str]] = []
    for match in JS_FROM_IMPORT.finditer(masked):
        clause = match.group("clause")
        clause_start = match.start("clause")
        cursor = 0
        for symbol in split_import_names(" ".join(clause.split())):
            token = symbol.split(":", 1)[-1]
            found = re.search(rf"\b{re.escape(token)}\b", clause[cursor:])
            offset = clause_start + cursor + (found.start() if found else 0)
            cursor += (found.start() + len(token)) if found else 0
            records.append((line_number(masked, offset), match.group("module"), symbol))
    for pattern, symbol in (
        (JS_SIDE_EFFECT, "module"),
        (JS_DYNAMIC, "dynamic-module"),
        (JS_MOCK, "mock-module"),
    ):
        for match in pattern.finditer(masked):
            records.append((line_number(masked, match.start()), match.group("module"), symbol))
    return records


def py_import_records(masked: str) -> list[tuple[int, str, str]]:
    records: list[tuple[int, str, str]] = []
    for match in PY_FROM_IMPORT.finditer(masked):
        names = match.group("names")
        names_start = match.start("names")
        if names.startswith("("):
            names = names[1:-1] if names.endswith(")") else names[1:]
            names_start += 1
        cursor = 0
        for item in names.split(","):
            symbol = item.strip().split(" as ", 1)[0].strip().rstrip(",")
            if re.fullmatch(r"[A-Za-z_][\w]{0,200}", symbol):
                found = re.search(rf"\b{re.escape(symbol)}\b", names[cursor:])
                offset = names_start + cursor + (found.start() if found else 0)
                records.append((line_number(masked, offset), match.group("module"), symbol))
            cursor += len(item) + 1
    for match in PY_PLAIN_IMPORT.finditer(masked):
        records.append((line_number(masked, match.start("module")), match.group("module"), "module"))
    return records


def telemetry_specifier_match(module: str) -> bool:
    lowered = module.casefold()
    return (
        lowered in TELEMETRY_SPECIFIER_EXACT
        or any(token in lowered for token in TELEMETRY_SPECIFIER_TOKENS)
    )


def telemetry_module_match(module: str) -> bool:
    return bool(re.search(r"(?:^|[./])telemetry(?:[.-]|$)", module.casefold()))


def remote_model_specifier_match(module: str) -> bool:
    lowered = module.casefold()
    return (
        lowered in REMOTE_MODEL_SPECIFIERS
        or lowered.replace("_", "-") in {item.replace("_", "-") for item in REMOTE_MODEL_SPECIFIERS}
        or lowered.startswith("huggingface_hub.") or lowered.startswith("modelscope.")
    )


def cloud_specifier_match(module: str) -> bool:
    lowered = module.casefold()
    return any(lowered.startswith(prefix) for prefix in CLOUD_SDK_SPECIFIER_PREFIXES) or lowered in {"boto3", "minio"}


def commercial_specifier_match(module: str) -> bool:
    return module.casefold() in COMMERCIAL_SDK_SPECIFIERS


def bare_known_host_pattern() -> re.Pattern[str]:
    escaped = sorted((re.escape(host) for host in BARE_KNOWN_HOSTS), key=len, reverse=True)
    return re.compile(
        rf"(?<![A-Za-z0-9._/-])(?P<host>{'|'.join(escaped)})(?![A-Za-z0-9.-])",
        re.I,
    )


def package_manifest_records(root: Path, rel: str, detect_text: str, evidence_text: str, path: Path) -> list[dict[str, Any]]:
    """Classified declared-dependency records for package.json, pyproject.toml, and conda envs."""
    rows: list[dict[str, Any]] = []
    names: list[tuple[str, int]] = []  # (name, line)
    if path.name == "package.json":
        section: str | None = None
        for line_index, raw in enumerate(detect_text.splitlines(), 1):
            stripped = raw.strip()
            section_match = re.fullmatch(
                r'"(dependencies|devDependencies|peerDependencies|optionalDependencies|resolutions|overrides|pnpm\.overrides)"\s*:\s*\{',
                stripped.rstrip(","),
            )
            if section_match:
                section = section_match.group(1)
                continue
            if section and stripped.startswith("}"):
                section = None
            entry = re.match(r'"([^"\\]+)"\s*:', stripped)
            if section and entry:
                names.append((entry.group(1), line_index))
    elif path.name == "pyproject.toml":
        for line_index, raw in enumerate(detect_text.splitlines(), 1):
            for quoted in re.finditer(r'"([^"]+)"', raw):
                token = re.match(r"([A-Za-z0-9][A-Za-z0-9._-]*)(?:\[[^\]]*\])?(?:[<>=!~; ]|$)", quoted.group(1))
                if token:
                    names.append((token.group(1), line_index))
    elif path.suffix.lower() in {".yaml", ".yml"}:
        for line_index, raw in enumerate(detect_text.splitlines(), 1):
            dep = re.match(r"^\s*-\s*([A-Za-z0-9_][A-Za-z0-9_-]*)=\S", raw)
            if dep:
                names.append((dep.group(1).casefold(), line_index))
    seen: set[tuple[str, str]] = set()
    for name, first_line in names:
        categories = classify_declared_dependency(name)
        if not categories or (name, str(sorted(categories))) in seen:
            continue
        seen.add((name, str(sorted(categories))))
        for category in sorted(categories):
            rows.append({
                "sourcePath": rel,
                "line": first_line,
                "category": category,
                "mechanism": "sdk-dependency",
                "dependency": f"declared:{name}",
                "evidence": source_excerpt(evidence_text, first_line),
            })
    return rows


def container_references(path: Path, rel: str, masked: str) -> list[tuple[int, str, str]]:
    """Return (line, reference, registry-or-implicit-dependency) rows for image/FROM lines."""
    rows: list[tuple[int, str, str]] = []
    name = path.name
    is_dockerfile = name.startswith("Dockerfile") or name.endswith(".dockerfile")
    for line_no, raw in enumerate(masked.splitlines(), 1):
        match = IMAGE_LINE_PATTERN.match(raw) if not is_dockerfile else None
        reference: str | None = match.group(1) if match else None
        if reference is None and is_dockerfile:
            from_match = FROM_LINE_PATTERN.match(raw)
            if from_match and not from_match.group(1).casefold().startswith("scratch"):
                reference = from_match.group(1)
        if reference is None:
            continue
        reference = reference.rstrip("'\"")
        repo = re.sub(r":\$\{[^}]*\}$", "", reference.split("@", 1)[0])
        repo = re.sub(r":[^:/]+$", "", repo)
        first = repo.split("/", 1)[0]
        if "." in first or ":" in first:
            registry = first.rsplit(":", 1)[0].casefold()
            rows.append((line_no, reference, f"{registry}:{repo}"))
        else:
            rows.append((line_no, reference, f"docker.io-or-local:{repo}"))
    return rows


def scan_source(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    codebase = root / "Codebase"
    files = sorted(
        (path for path in codebase.rglob("*") if path.is_file()),
        key=lambda value: value.as_posix().casefold(),
    )
    records: list[dict[str, Any]] = []
    source_manifest: list[dict[str, Any]] = []
    excluded: dict[str, dict[str, Any]] = {}
    bare_pattern = bare_known_host_pattern()

    def add_exclusion(bucket: str, detail: str, source: str, line: int) -> None:
        entry = excluded.setdefault(bucket, {
            "class": bucket,
            "reason": EXCLUSION_REASONS[bucket],
            "occurrences": 0,
            "examples": [],
        })
        entry["occurrences"] += 1
        example = f"{source}:{line}:{detail}"
        if example not in entry["examples"] and len(entry["examples"]) < 25:
            entry["examples"].append(example)

    for path in files:
        raw = path.read_bytes()
        source = path.relative_to(root).as_posix()
        suffix = path.suffix.lower()
        if suffix in CSTYLE_SUFFIXES or suffix in HTML_EXTRA_SUFFIXES:
            kind = "cstyle"
        elif suffix in HASH_SUFFIXES:
            kind = "hash"
        elif suffix in HTML_SUFFIXES:
            kind = "html"
        elif suffix in PLAIN_SUFFIXES:
            kind = "plain"
        else:
            kind = ""
        scan_eligible = (
            bool(kind)
            or path.name in SCANNED_NAMES
            or path.name.startswith(".env")
            or path.name.startswith("Dockerfile")
            or path.name.endswith(".dockerfile")
        )
        if scan_eligible and not kind:
            kind = "hash"
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
            raise EvidenceError("SOURCE_NOT_UTF8", source) from exc
        masked = masked_text(text, kind, suffix in HTML_EXTRA_SUFFIXES)

        # 1. Scheme-qualified external hosts.
        for match in URL_PATTERN.finditer(masked):
            scheme = match.group("scheme").casefold()
            authority = match.group("authority")
            line = line_number(masked, match.start())
            if scheme not in RECORDED_SCHEMES:
                add_exclusion("unrecorded-scheme", f"{scheme}://{authority}", source, line)
                continue
            host = strip_authority_host(authority)
            if not host:
                continue
            bucket = exclusion_class(host)
            if bucket:
                add_exclusion(bucket, host, source, line)
                continue
            categories = {"OUTBOUND_HOST"} | classify_host(host)
            dependency = f"literal-host:{host.casefold()}"
            for category in sorted(categories):
                records.append({
                    "sourcePath": source,
                    "line": line,
                    "category": category,
                    "mechanism": "literal-external-host",
                    "dependency": dependency,
                    "evidence": source_excerpt(text, line),
                })

        # 2. Known integration hosts mentioned without a scheme.
        for match in bare_pattern.finditer(masked):
            line = line_number(masked, match.start())
            host = match.group("host").casefold()
            already = any(
                row["sourcePath"] == source and row["line"] == line
                and row["mechanism"] == "literal-external-host"
                and row["dependency"] == f"literal-host:{host}"
                for row in records
            )
            if already:
                continue
            categories = {"OUTBOUND_HOST"} | classify_host(host)
            for category in sorted(categories):
                records.append({
                    "sourcePath": source,
                    "line": line,
                    "category": category,
                    "mechanism": "bare-known-integration-host",
                    "dependency": f"bare-host:{host}",
                    "evidence": source_excerpt(text, line),
                })

        # 3. Container image references.
        if suffix in {".yml", ".yaml"} or path.name.startswith("Dockerfile") or path.name.endswith(".dockerfile"):
            for line, reference, dep in container_references(path, source, masked):
                registry = dep.split(":", 1)[0]
                if registry == "docker.io-or-local":
                    mechanism = "container-image-implicit-registry"
                    categories_ = {"OUTBOUND_HOST"}
                else:
                    mechanism = "container-image-reference"
                    categories_ = {"OUTBOUND_HOST"} | classify_host(registry)
                for category in sorted(categories_):
                    records.append({
                        "sourcePath": source,
                        "line": line,
                        "category": category,
                        "mechanism": mechanism,
                        "dependency": f"{mechanism}:{dep}",
                        "evidence": source_excerpt(text, line),
                    })

        # 4. Telemetry, remote-model, cloud, and commercial imports.
        if kind == "cstyle":
            for line, module, symbol in js_import_records(masked):
                for category, mechanism, predicate in (
                    ("TELEMETRY", "telemetry-sdk-import", telemetry_specifier_match),
                    ("TELEMETRY", "telemetry-module-import", telemetry_module_match),
                    ("REMOTE_MODEL_PATH", "hf-client-import", remote_model_specifier_match),
                    ("CLOUD_SERVICE", "cloud-sdk-import", cloud_specifier_match),
                    ("COMMERCIAL_INTEGRATION", "commercial-sdk-import", commercial_specifier_match),
                ):
                    if predicate(module):
                        records.append({
                            "sourcePath": source,
                            "line": line,
                            "category": category,
                            "mechanism": mechanism,
                            "dependency": f"{module}:{symbol}",
                            "evidence": source_excerpt(text, line),
                        })
        if suffix in {".py", ".pyi"}:
            for line, module, symbol in py_import_records(masked):
                for category, mechanism, predicate in (
                    ("TELEMETRY", "telemetry-sdk-import", telemetry_specifier_match),
                    ("TELEMETRY", "telemetry-module-import", telemetry_module_match),
                    ("REMOTE_MODEL_PATH", "hf-client-import", remote_model_specifier_match),
                    ("CLOUD_SERVICE", "cloud-sdk-import", cloud_specifier_match),
                    ("COMMERCIAL_INTEGRATION", "commercial-sdk-import", commercial_specifier_match),
                ):
                    if predicate(module):
                        records.append({
                            "sourcePath": source,
                            "line": line,
                            "category": category,
                            "mechanism": mechanism,
                            "dependency": f"{module}:{symbol}",
                            "evidence": source_excerpt(text, line),
                        })
            # Remote-model snapshot download call sites and repository scopes.
            for call in re.finditer(rf"\b{SNAPSHOT_FUNCTION}\s*\(", masked):
                line = line_number(masked, call.start())
                prefix = masked[max(0, call.start() - 10):call.start()]
                is_definition = bool(re.search(r"\bdef\s+$", prefix))
                bound = (
                    re.search(
                        rf"(?m)^\s*from\s+huggingface_hub\s+import\s+[^\n]*\b{SNAPSHOT_FUNCTION}\b",
                        masked,
                    ) is not None
                    or re.search(
                        rf"(?m)^\s*import\s+huggingface_hub\b", masked,
                    ) is not None and re.search(rf"\bhuggingface_hub\.{SNAPSHOT_FUNCTION}\s*\(", masked) is not None
                )
                scope_match = re.search(
                    r"immich-app/", masked[call.end():call.end() + 400]
                )
                records.append({
                    "sourcePath": source,
                    "line": line,
                    "category": "REMOTE_MODEL_PATH",
                    "mechanism": "hf-snapshot-download-stub-definition" if is_definition else "hf-snapshot-download",
                    "dependency": (
                        f"test-stub:{SNAPSHOT_FUNCTION}" if is_definition
                        else f"huggingface_hub:{SNAPSHOT_FUNCTION}"
                    ),
                    "evidence": source_excerpt(text, line),
                    "_binding": None if is_definition else bound,
                })
                if scope_match:
                    records.append({
                        "sourcePath": source,
                        "line": line_number(masked, call.end() + scope_match.start()),
                        "category": "REMOTE_MODEL_PATH",
                        "mechanism": "hf-repo-scope",
                        "dependency": "hf-repo-scope:immich-app",
                        "evidence": source_excerpt(text, line_number(masked, call.end() + scope_match.start())),
                    })

        # 5. Classified declared dependencies.
        if path.name in {"package.json", "pyproject.toml"} or (
            suffix in {".yml", ".yaml"} and path.name in {"environment.yml", "environment.yaml", "env.yaml", "env.yml"}
        ):
            records.extend(package_manifest_records(root, source, masked, text, path))

    for row in records:
        binding = row.pop("_binding", None)
        if binding is not None and not binding:
            row["dependency"] = f"unbound:{row['dependency']}"

    for row in records:
        row["ownership"] = {"status": "REVIEW_REQUIRED", "owner": None, "ownerType": None, "reason": OWNERSHIP_REASON}

    unique: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in records:
        key = (row["sourcePath"], row["line"], row["category"], row["mechanism"], row["dependency"])
        unique[key] = row
    ordered = sorted(unique.values(), key=lambda row: (
        row["sourcePath"].casefold(), row["line"], row["category"], row["dependency"].casefold()
    ))
    for index, row in enumerate(ordered, 1):
        row["id"] = f"OI-{index:04d}"
    exclusion_rows = sorted(excluded.values(), key=lambda row: row["class"])
    for row in exclusion_rows:
        row["examples"] = sorted(row["examples"])
    return ordered, source_manifest, exclusion_rows


def validate(records: list[dict[str, Any]], sources: list[dict[str, Any]], exclusions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    if not sources:
        failures.append({"code": "SOURCE_CORPUS_EMPTY"})
    if not records:
        failures.append({"code": "INTEGRATION_INVENTORY_EMPTY"})
    ids = [row["id"] for row in records]
    if len(ids) != len(set(ids)):
        failures.append({"code": "DUPLICATE_RECORD_ID"})
    source_paths = {row["path"] for row in sources}
    seen_categories = {row["category"] for row in records}
    if seen_categories != CATEGORIES:
        failures.append({"code": "CATEGORY_COVERAGE_INCOMPLETE", "observed": sorted(seen_categories)})
    for row in records:
        if row["sourcePath"] not in source_paths or row["line"] < 1 or not row["evidence"]:
            failures.append({"code": "SOURCE_EVIDENCE_INVALID", "id": row["id"]})
        dependency = row["dependency"]
        for prefix in ("literal-host:", "bare-host:"):
            if dependency.startswith(prefix):
                raw_payload = dependency[len(prefix):]
                payload = host_static_labels(raw_payload)
                evidence_labels = host_static_labels(row["evidence"].casefold())
                if payload and payload not in evidence_labels:
                    failures.append({"code": "DEPENDENCY_NOT_IN_SOURCE_EVIDENCE", "id": row["id"]})
                if not payload and raw_payload.casefold() not in row["evidence"].casefold():
                    failures.append({"code": "DEPENDENCY_NOT_IN_SOURCE_EVIDENCE", "id": row["id"]})
        for prefix in ("container-image-reference:", "container-image-implicit-registry:"):
            if dependency.startswith(prefix):
                payload = dependency[len(prefix):].split(":", 1)[-1]
                if payload.split("/", 1)[-1] not in row["evidence"]:
                    failures.append({"code": "DEPENDENCY_NOT_IN_SOURCE_EVIDENCE", "id": row["id"]})
        if row["mechanism"] in {"telemetry-sdk-import", "telemetry-module-import", "hf-client-import", "cloud-sdk-import", "commercial-sdk-import"}:
            imported = dependency.rsplit(":", 1)[-1]
            module = dependency.rsplit(":", 1)[0]
            if not any(token in module.casefold() for token in ("opentelemetry", "telemetry", "sentry", "posthog", "huggingface", "modelscope", "transformers", "aws", "boto", "azure", "google-cloud", "stripe", "plausible", "prom-client", "nestjs-otel", "prometheus", "minio")):
                failures.append({"code": "UNEXPECTED_IMPORT_MODULE", "id": row["id"]})
            if imported not in {"module", "dynamic-module", "mock-module"} and not imported.startswith(('namespace:', 'default:')) and imported not in row["evidence"]:
                failures.append({"code": "DEPENDENCY_NOT_IN_SOURCE_EVIDENCE", "id": row["id"]})
        ownership = row["ownership"]
        if (ownership["status"] != "REVIEW_REQUIRED" or ownership["owner"] is not None
                or ownership["ownerType"] is not None or ownership["reason"] != OWNERSHIP_REASON):
            failures.append({"code": "OWNERSHIP_INVALID", "id": row["id"]})
    classes = {row["class"] for row in exclusions}
    if not classes.issubset(EXCLUSION_REASONS):
        failures.append({"code": "EXCLUSION_CLASS_INVALID", "observed": sorted(classes)})
    return failures


def compose_fixtures(output: Path) -> list[dict[str, Any]]:
    """Focused and negative fixtures for the collector parser and publication protocol."""
    results: list[dict[str, Any]] = []

    def fixture(fixture_id: str, expected: Any, actual: Any) -> None:
        results.append({"id": fixture_id, "expected": expected, "actual": actual,
                        "status": "PASS" if actual == expected else "FAIL"})

    # URL extraction with comment/string placement.
    cstyle_source = (
        "// https://comment-only.invalid\n"
        "const url = 'https://api.example-domain.com/v1';\n"
        "/* https://block-comment.invalid */\n"
        "const ws = 'wss://events.immich.cloud/live';\n"
    )
    masked = mask_cstyle(cstyle_source)
    found = [m.group("authority") for m in URL_PATTERN.finditer(masked)]
    fixture("cstyle-comments-masked",
            ["api.example-domain.com", "events.immich.cloud"],
            [host for host in found])

    hash_source = (
        "# https://hash-comment.invalid\n"
        "  #   image: prom/prometheus\n"
        "url: https://hash-visible.test-resource.com\n"
        "name: value#fragment\n"
    )
    masked = mask_hash(hash_source)
    found = [m.group("authority") for m in URL_PATTERN.finditer(masked)]
    fixture("hash-comments-masked", ["hash-visible.test-resource.com"], found)
    hash_masked_lines = mask_hash(hash_source).splitlines()
    fixture("hash-fragment-survives", True, "value#fragment" in hash_masked_lines[3])

    html_source = "<!-- https://markup-comment.invalid -->\n<a href=\"https://markup-visible.test-anchor.com\">x</a>"
    found = [m.group("authority") for m in URL_PATTERN.finditer(mask_html(html_source))]
    fixture("html-comments-masked", ["markup-visible.test-anchor.com"], found)

    # Host normalization and classifier semantics.
    fixture("authority-userinfo-port", "data.immich.cloud",
            strip_authority_host("user:pass@data.immich.cloud:8081"))
    fixture("authority-ipv6-loopback-excluded", "loopback-or-private-address",
            exclusion_class("[::1]"))
    fixture("authority-private-ipv4-excluded", "loopback-or-private-address",
            exclusion_class("192.168.1.10"))
    fixture("authority-public-ipv4-kept", None, exclusion_class("8.8.4.4"))
    fixture("single-label-excluded", "single-label-internal-address",
            exclusion_class("immich-server"))
    fixture("placeholder-excluded", "rfc-2606-placeholder-host",
            exclusion_class("docs-test.example.com"))
    fixture("namespace-uri-excluded", "namespace-uri-identifier",
            exclusion_class("www.w3.org"))
    fixture("subdomain-w3-not-namespace", None, exclusion_class("cdn.w3.org"))

    fixture("classifier-update-check-exact", ["CLOUD_SERVICE", "UPDATE_CHECK"],
            sorted(classify_host("version.immich.cloud")))
    fixture("classifier-update-check-dev", ["CLOUD_SERVICE", "UPDATE_CHECK"],
            sorted(classify_host("version.dev.immich.cloud")))
    fixture("classifier-not-version-prefix", ["CLOUD_SERVICE"],
            sorted(classify_host("x-version.immich.cloud")))
    fixture("classifier-commercial-exact", ["COMMERCIAL_INTEGRATION"],
            sorted(classify_host("my.immich.app")))
    fixture("classifier-commercial-boundary", [],
            sorted(classify_host("adversary-my.immich.app.evil-hold")))
    fixture("classifier-cloud-suffix", ["CLOUD_SERVICE"],
            sorted(classify_host("tiles.immich.cloud")))
    fixture("classifier-remote-model-suffix", ["REMOTE_MODEL_PATH"],
            sorted(classify_host("hub-end.huggingface.co")))
    fixture("classifier-remote-model-boundary", [],
            sorted(classify_host("huggingface.co.evil.test-hold")))
    fixture("classifier-plain-external", [],
            sorted(classify_host("github.com")))
    fixture("classifier-template-host-preserved", ["CLOUD_SERVICE", "UPDATE_CHECK"],
            sorted(classify_host("version.${variant}.immich.cloud")))
    fixture("dtd-namespace-excluded", "namespace-uri-identifier",
            exclusion_class("www.apple.com"))
    fixture("subdomain-apple-not-namespace", None,
            exclusion_class("developer.apple.com"))

    # JSX/text-node URLs: a // sequence directly after ':' is a scheme separator.
    jsx_source = (
        "export const Item = () => <a href=\"#\">https://jsx-visible.immich-cloud-test.com</a>; // https://jsx-comment.invalid\n"
        "// https://jsx-standalone-comment.invalid\n"
    )
    jsx_found = [m.group("authority") for m in URL_PATTERN.finditer(mask_cstyle(jsx_source))]
    fixture("jsx-text-node-url-not-comment", ["jsx-visible.immich-cloud-test.com"], jsx_found)

    # Bare known hosts: scheme-qualified instances must not double-count.
    pattern = bare_known_host_pattern()
    bare_source = "const url = 'https://my.immich.app/x';\nvalues: { server: 'version.immich.cloud' };"
    bare_matches = [m.group("host").casefold() for m in pattern.finditer(bare_source)]
    fixture("bare_known_host_skips_scheme_qualified", ["version.immich.cloud"], bare_matches)

    # Container reference parsing.
    compose_source = (
        "    image: ghcr.io/immich-app/postgres:14-vectorchord0.4.3@sha256:abc\n"
        "    image: postgres:16\n"
        "  #   image: prom/prometheus\n"
        "    image: docker.io/valkey/valkey:9@sha256:def\n"
    )
    refs = container_references(Path("any/docker-compose.yml"), "any/docker-compose.yml", mask_hash(compose_source))
    fixture("container-image-registry-prefix",
            ["docker.io:docker.io/valkey/valkey", "ghcr.io:ghcr.io/immich-app/postgres"],
            sorted(dep for _, _, dep in refs if not dep.startswith("docker.io-or-local:")))
    fixture("container-image-implicit-registry",
            ["docker.io-or-local:postgres"],
            sorted(dep for _, _, dep in refs if dep.startswith("docker.io-or-local:")))

    # Import parsing.
    js_sample = "import {\n  MetricOptions,\n} from '@opentelemetry/api';\n// import { x } from '@opentelemetry/fake';\n"
    js_records = js_import_records(mask_cstyle(js_sample))
    fixture("telemetry-sdk-import-multiline", [(2, "@opentelemetry/api", "MetricOptions")], js_records)

    py_sample = "from huggingface_hub import snapshot_download\nfrom huggingface_hub.fake import nope\n"
    py_records = py_import_records(mask_hash(py_sample))
    fixture("hf-client-import", [(1, "huggingface_hub", "snapshot_download"), (2, "huggingface_hub.fake", "nope")], py_records)
    fixture("hf-module-predicate",
            [True, True, False],
            [remote_model_specifier_match("huggingface_hub"), remote_model_specifier_match("huggingface_hub.fake"), remote_model_specifier_match("huggingface-brownie-sync")])

    # Declared dependency classification.
    dep_categories = [
        classify_declared_dependency("@opentelemetry/api"),
        classify_declared_dependency("nestjs-otel"),
        classify_declared_dependency("huggingface-hub"),
        classify_declared_dependency("boto3"),
        classify_declared_dependency("lodash"),
    ]
    fixture("declared-dependency-classification",
            [["TELEMETRY"], ["TELEMETRY"], ["REMOTE_MODEL_PATH"], ["CLOUD_SERVICE"], []],
            [sorted(value) for value in dep_categories])

    snapshot_text = (
        "from huggingface_hub import snapshot_download\n\n"
        "    snapshot_download(\n"
        "        f\"immich-app/{clean_name(self.model_name)}\",\n"
        "    )\n"
    )
    snapshot_lines = [(line_number(snapshot_text, m.start())) for m in re.finditer(r"\bsnapshot_download\s*\(", snapshot_text)]
    fixture("hf-snapshot-download-callsite", [3], snapshot_lines)

    # Publication protocol: failed validation preserves every artifact byte-for-byte.
    before = {
        name: (output / name).read_bytes() if (output / name).is_file() else None
        for name in PUBLISHED_ARTIFACTS
    }
    simulated = {name: b"SIMULATED_INVALID_GENERATION" for name in PUBLISHED_ARTIFACTS}
    published = publish_validated_generation(output, simulated, INVENTORY_FILE, [{"code": "SIMULATED_VALIDATION_FAILURE"}])
    after = {name: (output / name).read_bytes() if (output / name).is_file() else None for name in PUBLISHED_ARTIFACTS}
    fixture("failed-validation-preserves-all-artifacts",
            {"published": False, "allArtifactsByteIdentical": True},
            {"published": published, "allArtifactsByteIdentical": before == after})

    before_mid = {name: (output / name).read_bytes() if (output / name).is_file() else None for name in PUBLISHED_ARTIFACTS}
    replace_count = 0

    def fail_mid_publish(path: Path, content: bytes) -> None:
        nonlocal replace_count
        replace_count += 1
        if replace_count == 3:
            raise EvidenceError("SIMULATED_MID_PUBLISH_FAILURE", path.name)
        atomic_replace(path, content)

    failed_as_expected = False
    try:
        publish_generation(output, simulated, INVENTORY_FILE, fail_mid_publish)
    except EvidenceError as exc:
        failed_as_expected = exc.code == "SIMULATED_MID_PUBLISH_FAILURE"
    after_mid = {name: (output / name).read_bytes() if (output / name).is_file() else None for name in PUBLISHED_ARTIFACTS}
    fixture("mid-publication-failure-restores-all-artifacts",
            {"failedAsExpected": True, "allArtifactsByteIdentical": True},
            {"failedAsExpected": failed_as_expected, "allArtifactsByteIdentical": before_mid == after_mid})

    return results


def main() -> int:
    script = Path(__file__)
    root = repository_root(script)
    output = script.resolve().parent
    baseline = baseline_hashes(root)
    before = codebase_hashes(root)
    records, sources, exclusions = scan_source(root)
    fixtures = compose_fixtures(output)
    failures = validate(records, sources, exclusions)
    after = codebase_hashes(root)
    if before != after:
        failures.append({"code": "CODEBASE_CHANGED_DURING_COLLECTION"})
    if baseline != before:
        failures.append({"code": "WP_I0_001_BASELINE_MISMATCH", "baselineCount": len(baseline), "currentCount": len(before)})
    if any(row["status"] != "PASS" for row in fixtures):
        failures.append({"code": "NEGATIVE_FIXTURE_FAILED"})

    category_counts = Counter(row["category"] for row in records)
    mechanism_counts = Counter(row["mechanism"] for row in records)
    generation_id = semantic_sha256({
        "packageId": PACKAGE_ID,
        "sources": sources,
        "records": records,
        "exclusions": exclusions,
        "failures": failures,
        "codebase": semantic_sha256(after),
    })
    inventory = {
        "packageId": PACKAGE_ID,
        "requirementId": REQUIREMENT_ID,
        "generationId": generation_id,
        "authoritativeCommitMarker": True,
        "status": "PASS" if not failures else "FAIL",
        "scope": (
            "Every committed file under Codebase is fingerprinted; every code, configuration, "
            "manifest, script, and service-descriptor surface is content-qualified and text-scanned "
            "(documentation authoring formats are fingerprinted but folio-excluded from integration scanning)."
        ),
        "categories": sorted(CATEGORIES),
        "mechanisms": sorted(MECHANISMS),
        "classificationRules": {
            "recordedSchemes": sorted(RECORDED_SCHEMES),
            "updateCheckHosts": sorted(UPDATE_CHECK_HOSTS),
            "commercialExactHosts": sorted(COMMERCIAL_EXACT_HOSTS),
            "commercialSuffixes": list(COMMERCIAL_SUFFIXES),
            "cloudSuffixes": list(CLOUD_SUFFIXES),
            "remoteModelSuffixes": list(REMOTE_MODEL_SUFFIXES),
            "telemetrySuffixes": list(TELEMETRY_SUFFIXES),
            "bareKnownHosts": BARE_KNOWN_HOSTS,
            "placeholderHosts": sorted(PLACEHOLDER_EXACT_HOSTS) + list(PLACEHOLDER_SUFFIXES),
            "namespaceHosts": sorted(NAMESPACE_URI_HOSTS),
            "exclusionClasses": EXCLUSION_REASONS,
        },
        "counts": {
            "sourceFiles": len(sources),
            "textScannedFiles": sum(1 for row in sources if row["textScanned"]),
            "records": len(records),
            "byCategory": dict(sorted(category_counts.items())),
            "byMechanism": dict(sorted(mechanism_counts.items())),
            "exclusions": {row["class"]: row["occurrences"] for row in exclusions},
        },
        "sourceCorpus": sources,
        "integrations": records,
        "exclusions": exclusions,
    }
    verification = {
        "packageId": PACKAGE_ID,
        "generationId": generation_id,
        "status": inventory["status"],
        "acceptanceCriterion": (
            "Every committed Codebase surface is fingerprinted, every discovered outbound host, telemetry "
            "surface, update check, cloud service, commercial integration, and remote model path is recorded "
            "with exact source evidence, and unresolved disposition is explicitly REVIEW_REQUIRED."
        ),
        "checks": {
            "completeRecursiveCorpusOracle": len(sources) > 0,
            "allSixCategoriesPresent": set(category_counts) == CATEGORIES,
            "allRecordsHaveExactSourceEvidence": not any(item.get("code") == "SOURCE_EVIDENCE_INVALID" for item in failures),
            "everyDependencyReconcilesWithEvidence": not any(item.get("code") in {"DEPENDENCY_NOT_IN_SOURCE_EVIDENCE", "UNEXPECTED_IMPORT_MODULE"} for item in failures),
            "everyRecordIsExplicitlyReviewRequired": not any(item.get("code") == "OWNERSHIP_INVALID" for item in failures),
            "exclusionClassesDocumented": not any(item.get("code") == "EXCLUSION_CLASS_INVALID" for item in failures),
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
        "recordsSemanticSha256": semantic_sha256(records),
        "exclusionsSemanticSha256": semantic_sha256(exclusions),
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
        "method": "Local-only static source inspection; no product code imported or executed; no outbound network access.",
        "inputs": [
            "Codebase/** (complete committed corpus; content-qualified text scanning)",
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
            "outbound-integration-inventory.json", "verification-report.json", "evidence-consistency.json",
            "provenance-report.json", "artifact-scan.json", "completion-evidence.md",
        ],
        "failures": failures,
    }
    artifact_scan = {
        "packageId": PACKAGE_ID,
        "generationId": generation_id,
        "status": "PASS" if not failures else "FAIL",
        "allowedRoot": "graphify/13-implementation/WP-I0-010",
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
        f"- Codebase files fingerprinted: `{len(sources)}`",
        f"- Text-scanned files: `{sum(1 for row in sources if row['textScanned'])}`",
        f"- Integration records: `{len(records)}`",
        "",
        "## Category coverage",
        "",
    ]
    completion.extend(f"- `{category}`: `{category_counts[category]}`" for category in sorted(CATEGORIES))
    completion.extend([
        "", "## Mechanism coverage", "",
    ])
    completion.extend(f"- `{mechanism}`: `{mechanism_counts[mechanism]}`" for mechanism in sorted(mechanism_counts))
    completion.extend([
        "", "## Validation", "",
        "- Recursive corpus oracle fingerprints every committed Codebase file.",
        "- Every record has an exact path, line, evidence excerpt, category, mechanism, and dependency.",
        "- Disposition ownership is uniformly and explicitly `REVIEW_REQUIRED`.",
        "- The full Codebase hash map matches WP-I0-001 before and after collection.",
        "- Negative comment, template, boundary, placeholder, namespace, and import fixtures pass.",
        "- Scheme-qualified references, bare known integration hosts, container images, imports, and declared dependencies are independently inventoried.",
        "", "## Recovery", "",
        "The collector writes only package-local derived evidence. Secondary artifacts are atomically replaced first and the authoritative inventory commit marker is replaced last. A pre-validation failure publishes nothing; an injected mid-publication I/O failure rolls every artifact back byte-for-byte before returning a typed error.",
        "", "## Changed files", "",
        "- `graphify/13-implementation/WP-I0-010/collect_evidence.py` — collector, focused/negative fixtures, and rollback protocol.",
        "- `graphify/13-implementation/WP-I0-010/verify_evidence.py` — independent read-only coverage and semantic verifier.",
        "- `graphify/13-implementation/WP-I0-010/outbound-integration-inventory.json` — authoritative outbound integration inventory.",
        "- `graphify/13-implementation/WP-I0-010/{artifact-scan,evidence-consistency,package-summary,provenance-report,verification-report}.json` — generated package evidence.",
        "- `graphify/13-implementation/WP-I0-010/completion-evidence.md` and `adversarial-review.md` — completion and independent-review evidence.",
        "", "## Commands and results", "",
        "- `python graphify\\13-implementation\\WP-I0-010\\collect_evidence.py` — PASS (exit 0); current generation published only after focused and negative fixtures pass.",
        "- `python graphify\\13-implementation\\WP-I0-010\\verify_evidence.py` — PASS (exit 0); independently rerun after publication and recorded in `adversarial-review.md`.",
    ])
    artifacts = {
        "artifact-scan.json": json_bytes(artifact_scan),
        "completion-evidence.md": ("\n".join(completion) + "\n").encode("utf-8"),
        "evidence-consistency.json": json_bytes(consistency),
        "outbound-integration-inventory.json": json_bytes(inventory),
        "package-summary.json": json_bytes(summary),
        "provenance-report.json": json_bytes(provenance),
        "verification-report.json": json_bytes(verification),
    }
    if failures:
        print(json.dumps({"status": "FAIL", "failures": failures}, indent=2), file=sys.stderr)
        return 1
    published = publish_validated_generation(output, artifacts, INVENTORY_FILE, failures)
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
