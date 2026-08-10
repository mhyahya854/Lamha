#!/usr/bin/env python3
"""Independent, read-only verification for WP-I0-010 outbound integration evidence.

This verifier never imports or executes the collector.  Every corpus rule,
parser rule, classifier rule, and exclusion rule is re-implemented here and
recomputed from the raw Codebase bytes; the published inventory must reconcile
with the independently derived oracle, record-for-record.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

MAX_JSON_BYTES = 32 * 1024 * 1024
MAX_JSON_DEPTH = 128

PACKAGE_ID = "WP-I0-010"
REQUIREMENT_ID = "CAN-MISSION-I0-010"
INVENTORY_FILE = "outbound-integration-inventory.json"

CATEGORIES = {
    "OUTBOUND_HOST", "TELEMETRY", "UPDATE_CHECK", "CLOUD_SERVICE",
    "COMMERCIAL_INTEGRATION", "REMOTE_MODEL_PATH",
}
MECHANISMS = {
    "literal-external-host", "bare-known-integration-host", "container-image-reference",
    "container-image-implicit-registry", "telemetry-sdk-import", "telemetry-module-import",
    "sdk-dependency", "hf-client-import", "hf-snapshot-download",
    "hf-snapshot-download-stub-definition", "hf-repo-scope", "cloud-sdk-import",
    "commercial-sdk-import",
}
RECORDED_SCHEMES = {"http", "https", "ws", "wss", "ftp", "ftps"}

C_STYLE = {
    ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".cts", ".mts", ".svelte",
    ".dart", ".kt", ".kts", ".java", ".swift", ".rs", ".groovy", ".gradle",
    ".c", ".h", ".cpp", ".hpp", ".cc", ".cs", ".go", ".css", ".scss", ".less",
}
HASH_STYLE = {
    ".py", ".pyi", ".sh", ".bash", ".zsh", ".yml", ".yaml", ".toml", ".conf",
    ".cfg", ".ini", ".properties", ".lock", ".rb", ".mk", ".env", ".tf", ".hcl",
}
HTML_STYLE = {".html", ".htm", ".xml", ".svg", ".storyboard", ".plist", ".entitlements", ".xcsettings"}
PLAIN_STYLE = {".json", ".txt", ".csv", ".tsv", ".pubxml", ".xcscheme", ".pbxproj", ".sql", ".patch", ".resolved"}
EXTRA_HTML = {".svelte"}
SCANNED_NAMES = {
    "Dockerfile", "Makefile", "makefile", ".npmrc", ".pypirc", ".envrc",
    "Fastfile", "Appfile", "Pluginfile", "Gemfile", "Justfile",
    ".gitmodules", "_redirects", "Podfile", "LICENSE", "Podfile.lock",
}

NAMESPACE_URI_HOSTS = {"www.w3.org", "schemas.xmlsoap.org", "json-schema.org", "schema.org", "opendocumentformat.org", "www.apple.com"}
PLACEHOLDER_EXACT = {"example.com", "example.org", "example.net", "example.invalid"}
PLACEHOLDER_SUFFIXES = (".example", ".invalid", ".test", ".localhost")
UPDATE_HOSTS = {"version.immich.cloud", "version.dev.immich.cloud"}
COMMERCIAL_EXACT = {"my.immich.app", "buy.immich.app", "pay.futo.org"}
COMMERCIAL_SUFFIXES = (".stripe.com", ".gumroad.com", ".lemonsqueezy.com", ".paddle.com")
CLOUD_SUFFIXES = (
    ".immich.cloud", ".amazonaws.com", ".amazon.com", ".googleapis.com",
    ".cloud.google.com", ".azure.com", ".azure.net", ".windows.net",
)
MODEL_SUFFIXES = (".huggingface.co", ".hf.co", ".modelscope.cn")
TELEMETRY_SUFFIXES = (".sentry.io", ".posthog.com", ".plausible.io", ".umami.is", ".statsigapi.net")
BARE_HOSTS = sorted({
    "version.immich.cloud", "version.dev.immich.cloud", "my.immich.app",
    "buy.immich.app", "pay.futo.org", "auth.immich.cloud", "tiles.immich.cloud",
    "huggingface.co",
})
TEL_TOKENS = (
    "@opentelemetry/", "nestjs-otel", "prom-client", "prometheus-client",
    "@sentry/", "sentry_sdk", "sentry.", "posthog", "plausible-tracker",
)
TEL_EXACT = {"sentry", "prometheus_client", "prom-client", "prom-client-lite", "opentelemetry"}
MODEL_MODULES = {
    "huggingface_hub", "huggingface-hub", "hf_hub_download", "modelscope",
    "transformers", "@huggingface/transformers",
}
CLOUD_PREFIXES = ("@aws-sdk/", "aws-sdk", "boto3", "@google-cloud/", "@azure/")
COMMERCIAL_MODULES = {"stripe", "gumroad-sdk"}

REQUIRED_FIXTURES = {
    "cstyle-comments-masked", "hash-comments-masked", "hash-fragment-survives",
    "html-comments-masked", "authority-userinfo-port", "authority-ipv6-loopback-excluded",
    "authority-private-ipv4-excluded", "authority-public-ipv4-kept",
    "single-label-excluded", "placeholder-excluded", "namespace-uri-excluded",
    "subdomain-w3-not-namespace", "classifier-update-check-exact",
    "classifier-update-check-dev", "classifier-not-version-prefix",
    "classifier-commercial-exact", "classifier-commercial-boundary",
    "classifier-cloud-suffix", "classifier-remote-model-suffix",
    "classifier-remote-model-boundary", "classifier-plain-external",
    "classifier-template-host-preserved", "bare_known_host_skips_scheme_qualified",
    "jsx-text-node-url-not-comment", "dtd-namespace-excluded", "subdomain-apple-not-namespace",
    "container-image-registry-prefix", "container-image-implicit-registry",
    "telemetry-sdk-import-multiline", "hf-client-import", "hf-module-predicate",
    "declared-dependency-classification", "hf-snapshot-download-callsite",
    "failed-validation-preserves-all-artifacts", "mid-publication-failure-restores-all-artifacts",
}
REQUIRED_RECORDS = {
    ("Codebase/server/src/repositories/config.repository.ts", 321, "literal-external-host", "literal-host:version.immich.cloud", "UPDATE_CHECK"),
    ("Codebase/server/src/repositories/config.repository.ts", 321, "literal-external-host", "literal-host:version.dev.immich.cloud", "UPDATE_CHECK"),
    ("Codebase/server/src/repositories/config.repository.ts", 321, "literal-external-host", "literal-host:version.immich.cloud", "CLOUD_SERVICE"),
    ("Codebase/server/src/config.ts", 281, "literal-external-host", "literal-host:tiles.immich.cloud", "CLOUD_SERVICE"),
    ("Codebase/server/src/config.ts", 282, "literal-external-host", "literal-host:tiles.immich.cloud", "CLOUD_SERVICE"),
    ("Codebase/server/src/utils/misc.ts", 53, "literal-external-host", "literal-host:my.immich.app", "COMMERCIAL_INTEGRATION"),
    ("Codebase/machine-learning/immich_ml/models/base.py", 8, "hf-client-import", "huggingface_hub:snapshot_download", "REMOTE_MODEL_PATH"),
    ("Codebase/machine-learning/immich_ml/models/base.py", 75, "hf-snapshot-download", "huggingface_hub:snapshot_download", "REMOTE_MODEL_PATH"),
    ("Codebase/machine-learning/immich_ml/models/base.py", 76, "hf-repo-scope", "hf-repo-scope:immich-app", "REMOTE_MODEL_PATH"),
    ("Codebase/machine-learning/pyproject.toml", 12, "sdk-dependency", "declared:huggingface-hub", "REMOTE_MODEL_PATH"),
    ("Codebase/server/package.json", 50, "sdk-dependency", "declared:@opentelemetry/api", "TELEMETRY"),
    ("Codebase/server/package.json", 96, "sdk-dependency", "declared:nestjs-otel", "TELEMETRY"),
    ("Codebase/web/src/routes/admin/system-settings/NewVersionCheckSettings.svelte", 19, "bare-known-integration-host", "bare-host:version.immich.cloud", "UPDATE_CHECK"),
    ("Codebase/docker/docker-compose.yml", 15, "container-image-reference", "container-image-reference:ghcr.io:ghcr.io/immich-app/immich-server", "OUTBOUND_HOST"),
    ("Codebase/install.sh", 75, "literal-external-host", "literal-host:github.com", "OUTBOUND_HOST"),
    ("Codebase/web/svelte.config.js", 7, "literal-external-host", "literal-host:buy.immich.app", "COMMERCIAL_INTEGRATION"),
    ("Codebase/web/svelte.config.js", 8, "literal-external-host", "literal-host:pay.futo.org", "COMMERCIAL_INTEGRATION"),
    ("Codebase/machine-learning/conftest.py", 183, "hf-snapshot-download-stub-definition", "test-stub:snapshot_download", "REMOTE_MODEL_PATH"),
    ("Codebase/server/src/emails/license.email.tsx", 40, "literal-external-host", "literal-host:my.immich.app", "COMMERCIAL_INTEGRATION"),
    ("Codebase/.gitmodules", 3, "literal-external-host", "literal-host:github.com", "OUTBOUND_HOST"),
    ("Codebase/mobile/ios/Runner.xcodeproj/project.xcworkspace/xcshareddata/swiftpm/Package.resolved", 6, "literal-external-host", "literal-host:github.com", "OUTBOUND_HOST"),
    ("Codebase/docs/static/_redirects", 31, "literal-external-host", "literal-host:awesome.immich.app", "OUTBOUND_HOST"),
    ("Codebase/LICENSE", 4, "literal-external-host", "literal-host:fsf.org", "OUTBOUND_HOST"),
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


def sha256_canonical(value: Any) -> str:
    serial = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serial.encode("utf-8")).hexdigest()


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


# ---------------------------------------------------------------------------
# Independent oracle machinery (separate implementation, same documented rules)
# ---------------------------------------------------------------------------

def own_mask_cstyle(text: str) -> str:
    result: list[str] = []
    i = 0
    n = len(text)
    mode = 0  # 0 code, 1 string, 2 //, 3 /* */
    quote = ""
    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if mode == 0:
            if ch in "'\"`":
                mode, quote = 1, ch
                result.append(ch)
            elif ch == "/" and nxt == "/":
                if i > 0 and text[i - 1] == ":":
                    # A // immediately after ':' is a scheme separator (JSX text URLs), not a comment.
                    result.extend((ch, nxt))
                    i += 2
                    continue
                result.extend((" ", " "))
                mode, i = 2, i + 2
                continue
            elif ch == "/" and nxt == "*":
                result.extend((" ", " "))
                mode, i = 3, i + 2
                continue
            else:
                result.append(ch)
        elif mode == 1:
            result.append(ch)
            if ch == "\\":
                if i + 1 < n:
                    result.append(text[i + 1])
                i += 2
                continue
            if ch == quote:
                mode = 0
        elif mode == 2:
            if ch == "\n":
                result.append(ch)
                mode = 0
            else:
                result.append(" ")
        else:
            if ch == "*" and nxt == "/":
                result.extend((" ", " "))
                mode, i = 0, i + 2
                continue
            result.append("\n" if ch == "\n" else " ")
        i += 1
    return "".join(result)


def own_mask_hash(text: str) -> str:
    lines: list[str] = []
    for lineno, line in enumerate(text.split("\n"), 1):
        cut = None
        quote = ""
        for pos, char in enumerate(line):
            if quote and char == "\\":
                continue
            if char in "'\"":
                quote = "" if char == quote else (char if not quote else quote)
            elif char == "#" and not quote:
                if lineno == 1 and line.startswith("#!"):
                    break
                if pos == 0 or line[pos - 1] in " \t":
                    cut = pos
                    break
        lines.append(line if cut is None else line[:cut] + " " * (len(line) - cut))
    return "\n".join(lines)


def own_mask_markup(text: str) -> str:
    out: list[str] = []
    pos = 0
    for match in re.finditer(r"<!--[\s\S]*?-->", text):
        out.append(text[pos:match.start()])
        out.append("".join("\n" if c == "\n" else " " for c in match.group(0)))
        pos = match.end()
    out.append(text[pos:])
    return "".join(out)


def own_masked(text: str, style: str, extra_html: bool) -> str:
    if style == "c":
        text = own_mask_cstyle(text)
        if extra_html:
            text = own_mask_markup(text)
    elif style == "hash":
        text = own_mask_hash(text)
    elif style == "html":
        text = own_mask_markup(text)
    return text


def own_style(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in C_STYLE:
        return "c"
    if suffix in HASH_STYLE:
        return "hash"
    if suffix in HTML_STYLE:
        return "html"
    if suffix in PLAIN_STYLE:
        return "plain"
    name = path.name
    if name in SCANNED_NAMES or name.startswith(".env") or name.startswith("Dockerfile") or name.endswith(".dockerfile"):
        return "hash"
    return ""


def own_static_labels(host: str) -> str:
    static = re.sub(r"\$\{\{[^}]*\}\}|\$\{[^}]*\}|\$[A-Za-z_{][\w{}]*", "", host)
    static = re.sub(r"\.{2,}", ".", static)
    return static.strip(".").rstrip(":.").strip(":")


def own_exclusion(host: str) -> str | None:
    lowered = host.casefold()
    static = own_static_labels(lowered)
    if static in NAMESPACE_URI_HOSTS:
        return "namespace-uri-identifier"
    if (any(static == p or static.endswith("." + p) for p in PLACEHOLDER_EXACT)
            or any(static.endswith(s) for s in PLACEHOLDER_SUFFIXES)):
        return "rfc-2606-placeholder-host"
    if re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", static):
        octets = [int(part) for part in static.split(".")]
        if octets[0] in {0, 10, 127} or (octets[0] == 172 and 16 <= octets[1] <= 31) or \
                (octets[0] == 192 and octets[1] == 168) or (octets[0] == 169 and octets[1] == 254):
            return "loopback-or-private-address"
        return None
    if static in {"[::1]", "[0:0:0:0:0:0:0:1]", "[::]", "[fe80::1]"} or static.startswith("[fe80"):
        return "loopback-or-private-address"
    if "$" in host and host.endswith(":") and not static:
        return "dynamic-userinfo-expression"
    if "$" not in host and "." not in static:
        return "single-label-internal-address"
    return None


def own_extra_categories(host: str) -> set[str]:
    lowered = host.casefold()
    static = own_static_labels(lowered)
    extras: set[str] = set()
    if static in UPDATE_HOSTS:
        extras.add("UPDATE_CHECK")
    if static in COMMERCIAL_EXACT:
        extras.add("COMMERCIAL_INTEGRATION")
    if any(static == s[1:] or static.endswith(s) for s in MODEL_SUFFIXES):
        extras.add("REMOTE_MODEL_PATH")
    if any(static.endswith(s) for s in COMMERCIAL_SUFFIXES):
        extras.add("COMMERCIAL_INTEGRATION")
    if any(static == s[1:] or static.endswith(s) for s in CLOUD_SUFFIXES):
        extras.add("CLOUD_SERVICE")
    if any(static.endswith(s) for s in TELEMETRY_SUFFIXES):
        extras.add("TELEMETRY")
    return extras


def own_dependency_categories(name: str) -> set[str]:
    lowered = name.casefold()
    found: set[str] = set()
    if (any(token in lowered for token in TEL_TOKENS) or lowered in TEL_EXACT
            or lowered.startswith("@opentelemetry/") or lowered.startswith("@sentry/")):
        found.add("TELEMETRY")
    if lowered in MODEL_MODULES or lowered.replace("_", "-") in MODEL_MODULES:
        found.add("REMOTE_MODEL_PATH")
    if any(lowered.startswith(prefix) for prefix in CLOUD_PREFIXES) or lowered in {"boto3", "minio"}:
        found.add("CLOUD_SERVICE")
    if lowered in COMMERCIAL_MODULES:
        found.add("COMMERCIAL_INTEGRATION")
    return found


OWN_URL = re.compile(
    r"(?P<scheme>[A-Za-z][A-Za-z0-9+.-]{0,20})://"
    r"(?P<authority>(?:\$\{\{[^}\r\n]{0,160}\}\}|\$\{[^}\r\n]{0,160}\}|[A-Za-z0-9._~:@+-])+)"
)


def own_authority_host(authority: str) -> str | None:
    host_port = authority.rsplit("@", 1)[-1].rstrip(".-")
    if not host_port:
        return None
    if host_port.startswith("["):
        end = host_port.find("]")
        if end < 0:
            return None
        return host_port[:end + 1]
    host = re.sub(r":\d+$", "", host_port)
    if host_port.endswith("}") and ":" in host_port:
        host = host_port
    return host.rstrip(".-") or None


OWN_JS_FROM = re.compile(
    r"\b(?:import|export)\s+(?P<clause>[^{};]*?\{.*?\}|[A-Za-z_$][\w$]*(?:\s+as\s+[A-Za-z_$][\w$]*)?|\*\s+as\s+[A-Za-z_$][\w$]*)\s*from\s*[\"'](?P<module>[^'\"]+)[\"']",
    re.S,
)
OWN_JS_SIDE = re.compile(r"\bimport\s*[\"'](?P<module>[^'\"]+)[\"']")
OWN_JS_DYNAMIC = re.compile(r"\bimport\s*\(\s*[\"'](?P<module>[^'\"]+)[\"']\s*\)")
OWN_JS_MOCK = re.compile(r"\b(?:vi|vitest|jest)\.mock\s*\(\s*[\"'](?P<module>[^'\"]+)[\"']")
OWN_PY_FROM = re.compile(
    r"(?m)^[ \t]*from[ \t]+(?P<module>[A-Za-z_][\w.]*)[ \t]+import[ \t]+(?P<names>\([^)]*\)|[^\n#]+)"
)
OWN_PY_PLAIN = re.compile(r"(?m)^[ \t]*import[ \t]+(?P<module>[A-Za-z_][\w.]*)")


def own_symbols(clause: str) -> list[str]:
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
    if prefix and prefix != "type" and re.fullmatch(r"[A-Za-z_$][\w$]*", prefix):
        names.append(f"default:{prefix}")
    return list(dict.fromkeys(names)) or ["module"]


def own_js_imports(masked: str) -> list[tuple[int, str, str]]:
    rows: list[tuple[int, str, str]] = []
    for m in OWN_JS_FROM.finditer(masked):
        clause = m.group("clause")
        start = m.start("clause")
        cursor = 0
        for symbol in own_symbols(" ".join(clause.split())):
            token = symbol.split(":", 1)[-1]
            found = re.search(rf"\b{re.escape(token)}\b", clause[cursor:])
            offset = start + cursor + (found.start() if found else 0)
            cursor += (found.start() + len(token)) if found else 0
            rows.append((offset, m.group("module"), symbol))
    for pattern, symbol in ((OWN_JS_SIDE, "module"), (OWN_JS_DYNAMIC, "dynamic-module"), (OWN_JS_MOCK, "mock-module")):
        for m in pattern.finditer(masked):
            rows.append((m.start(), m.group("module"), symbol))
    return [(masked.count("\n", 0, offset) + 1, module, symbol) for offset, module, symbol in rows]


def own_py_imports(masked: str) -> list[tuple[int, str, str]]:
    rows: list[tuple[int, str, str]] = []
    for m in OWN_PY_FROM.finditer(masked):
        names = m.group("names")
        names_start = m.start("names")
        if names.startswith("("):
            names = names[1:-1] if names.endswith(")") else names[1:]
            names_start += 1
        cursor = 0
        for item in names.split(","):
            symbol = item.strip().split(" as ", 1)[0].strip().rstrip(",")
            if re.fullmatch(r"[A-Za-z_][\w]{0,200}", symbol):
                found = re.search(rf"\b{re.escape(symbol)}\b", names[cursor:])
                offset = names_start + cursor + (found.start() if found else 0)
                rows.append((offset, m.group("module"), symbol))
            cursor += len(item) + 1
    for m in OWN_PY_PLAIN.finditer(masked):
        rows.append((m.start("module"), m.group("module"), "module"))
    return [(masked.count("\n", 0, offset) + 1, module, symbol) for offset, module, symbol in rows]


def own_tel(module: str) -> bool:
    lowered = module.casefold()
    return lowered in TEL_EXACT or any(token in lowered for token in TEL_TOKENS)


def own_tel_module(module: str) -> bool:
    return bool(re.search(r"(?:^|[./])telemetry(?:[.-]|$)", module.casefold()))


def own_model(module: str) -> bool:
    lowered = module.casefold()
    return (lowered in MODEL_MODULES or lowered.replace("_", "-") in {x.replace("_", "-") for x in MODEL_MODULES}
            or lowered.startswith("huggingface_hub.") or lowered.startswith("modelscope."))


def own_cloud(module: str) -> bool:
    lowered = module.casefold()
    return any(lowered.startswith(prefix) for prefix in CLOUD_PREFIXES) or lowered in {"boto3", "minio"}


def own_commercial(module: str) -> bool:
    return module.casefold() in COMMERCIAL_MODULES


OWN_IMAGE = re.compile(r"^\s*image:\s*['\"]?([A-Za-z0-9][^\s'\"]*)")
OWN_FROM = re.compile(r"^\s*FROM\s+(?:--platform=\S+\s+)?(\S+)")


def own_container_refs(path: Path, masked: str) -> list[tuple[int, str, str]]:
    rows: list[tuple[int, str, str]] = []
    dockerfile = path.name.startswith("Dockerfile") or path.name.endswith(".dockerfile")
    for lineno, raw in enumerate(masked.splitlines(), 1):
        reference: str | None = None
        if dockerfile:
            found = OWN_FROM.match(raw)
            if found and not found.group(1).casefold().startswith("scratch"):
                reference = found.group(1)
        else:
            found = OWN_IMAGE.match(raw)
            if found:
                reference = found.group(1)
        if reference is None:
            continue
        reference = reference.rstrip("'\"")
        repo = re.sub(r":\$\{[^}]*\}$", "", reference.split("@", 1)[0])
        repo = re.sub(r":[^:/]+$", "", repo)
        first = repo.split("/", 1)[0]
        if "." in first or ":" in first:
            registry = first.rsplit(":", 1)[0].casefold()
            rows.append((lineno, "container-image-reference", f"container-image-reference:{registry}:{repo}"))
        else:
            rows.append((lineno, "container-image-implicit-registry", f"container-image-implicit-registry:docker.io-or-local:{repo}"))
    return rows


def own_manifest_rows(path: Path, detect: str, evidence_text: str) -> list[tuple[int, str, str]]:
    rows: list[tuple[int, str, str]] = []
    names: list[tuple[str, int]] = []
    if path.name == "package.json":
        section = None
        for lineno, raw in enumerate(detect.splitlines(), 1):
            stripped = raw.strip()
            sec = re.fullmatch(
                r'"(dependencies|devDependencies|peerDependencies|optionalDependencies|resolutions|overrides|pnpm\.overrides)"\s*:\s*\{',
                stripped.rstrip(","),
            )
            if sec:
                section = sec.group(1)
                continue
            if section and stripped.startswith("}"):
                section = None
            entry = re.match(r'"([^"\\]+)"\s*:', stripped)
            if section and entry:
                names.append((entry.group(1), lineno))
    elif path.name == "pyproject.toml":
        for lineno, raw in enumerate(detect.splitlines(), 1):
            for quoted in re.finditer(r'"([^"]+)"', raw):
                token = re.match(r"([A-Za-z0-9][A-Za-z0-9._-]*)(?:\[[^\]]*\])?(?:[<>=!~; ]|$)", quoted.group(1))
                if token:
                    names.append((token.group(1), lineno))
    else:
        for lineno, raw in enumerate(detect.splitlines(), 1):
            dep = re.match(r"^\s*-\s*([A-Za-z0-9_][A-Za-z0-9_-]*)=\S", raw)
            if dep:
                names.append((dep.group(1).casefold(), lineno))
    seen: set[tuple[str, str]] = set()
    for name, lineno in names:
        cats = own_dependency_categories(name)
        key = (name, str(sorted(cats)))
        if not cats or key in seen:
            continue
        seen.add(key)
        for category in sorted(cats):
            rows.append((lineno, "sdk-dependency", f"declared:{name}"))
    return rows


def verify() -> dict[str, Any]:
    package = Path(__file__).resolve().parent
    root = package.parents[2]
    inventory = load_json(package / INVENTORY_FILE)
    report = load_json(package / "verification-report.json")
    summary = load_json(package / "package-summary.json")
    consistency = load_json(package / "evidence-consistency.json")
    provenance = load_json(package / "provenance-report.json")
    artifact_scan = load_json(package / "artifact-scan.json")

    # --- artifact identity / generation ---
    documents = [inventory, report, summary, consistency, provenance, artifact_scan]
    generation_ids = {doc.get("generationId") for doc in documents if isinstance(doc, dict)}
    if (len(generation_ids) != 1 or not isinstance(inventory.get("generationId"), str)
            or len(inventory["generationId"]) != 64 or inventory.get("authoritativeCommitMarker") is not True):
        raise VerificationError("EVIDENCE_GENERATION_MISMATCH", str(generation_ids))
    completion = (package / "completion-evidence.md").read_text(encoding="utf-8")
    if inventory["generationId"] not in completion:
        raise VerificationError("COMPLETION_GENERATION_MISMATCH", inventory["generationId"])
    if inventory.get("packageId") != PACKAGE_ID or inventory.get("requirementId") != REQUIREMENT_ID:
        raise VerificationError("IDENTITY_INVALID", "package or requirement mismatch")
    if inventory.get("status") != "PASS" or report.get("status") != "PASS" or summary.get("status") != "PASS":
        raise VerificationError("STATUS_NOT_PASS", "one or more evidence statuses are not PASS")
    if consistency.get("status") != "PASS" or artifact_scan.get("status") != "PASS":
        raise VerificationError("STATUS_NOT_PASS", "secondary evidence statuses are not PASS")

    # --- fixtures ---
    fixtures = report.get("negativeFixtures")
    fixture_statuses = {row.get("id"): row.get("status") for row in fixtures if isinstance(row, dict)} \
        if isinstance(fixtures, list) else {}
    if not REQUIRED_FIXTURES.issubset(fixture_statuses) or any(status != "PASS" for status in fixture_statuses.values()):
        raise VerificationError("NEGATIVE_FIXTURES_INVALID", str(fixture_statuses))
    checks = report.get("checks")
    if not isinstance(checks, dict) or not checks or not all(value is True for value in checks.values()):
        raise VerificationError("VERIFICATION_CHECKS_INCOMPLETE", str(checks))
    if report.get("failures") not in ([], None):
        raise VerificationError("FAILURES_PRESENT", str(report.get("failures")))

    # --- corpus reconciliation ---
    codebase = root / "Codebase"
    actual_files = sorted(
        (path for path in codebase.rglob("*") if path.is_file()),
        key=lambda value: value.as_posix().casefold(),
    )
    actual_names = {path.relative_to(root).as_posix() for path in actual_files}
    declared = inventory.get("sourceCorpus")
    if not isinstance(declared, list) or not declared:
        raise VerificationError("SOURCE_CORPUS_INVALID", "missing corpus manifest")
    declared_by_path = {row.get("path"): row for row in declared if isinstance(row, dict)}
    if set(declared_by_path) != actual_names or len(declared_by_path) != len(declared):
        raise VerificationError("SOURCE_CORPUS_INCOMPLETE", "path set differs from the live corpus")
    base = baseline(root)
    if set(base) != actual_names:
        raise VerificationError("BASELINE_PATH_SET_CHANGED", "corpus path set differs from WP-I0-001")
    source_text: dict[str, str] = {}
    scanned_names: set[str] = set()
    for path in actual_files:
        name = path.relative_to(root).as_posix()
        raw = path.read_bytes()
        row = declared_by_path[name]
        style = own_style(path)
        expected_scanned = bool(style)
        if (row.get("sha256") != hashlib.sha256(raw).hexdigest() or row.get("bytes") != len(raw)
                or row.get("textScanned") is not expected_scanned):
            raise VerificationError("SOURCE_FINGERPRINT_MISMATCH", name)
        if base.get(name) != row.get("sha256"):
            raise VerificationError("BASELINE_HASH_MISMATCH", name)
        if expected_scanned:
            scanned_names.add(name)
            try:
                source_text[name] = raw.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise VerificationError("SOURCE_INVALID_UTF8", name) from exc

    # --- record-level structural verification ---
    records = inventory.get("integrations")
    if not isinstance(records, list) or not records:
        raise VerificationError("RECORDS_INVALID", "missing integration records")
    ids: set[str] = set()
    categories: Counter[str] = Counter()
    mechanisms: Counter[str] = Counter()
    keyed: set[tuple[str, int, str, str, str]] = set()
    for index, row in enumerate(records, 1):
        if not isinstance(row, dict):
            raise VerificationError("RECORD_NOT_OBJECT", str(index))
        rid = row.get("id")
        if not isinstance(rid, str) or not re.fullmatch(r"OI-\d{4}", rid) or rid in ids \
                or rid != f"OI-{index:04d}":
            raise VerificationError("RECORD_ID_INVALID", str(rid))
        ids.add(rid)
        source = row.get("sourcePath")
        line = row.get("line")
        category = row.get("category")
        mechanism = row.get("mechanism")
        dependency = row.get("dependency")
        if source not in source_text or not isinstance(line, int) or not (1 <= line) \
                or category not in CATEGORIES or mechanism not in MECHANISMS or not isinstance(dependency, str):
            raise VerificationError("RECORD_FIELD_INVALID", rid)
        lines = source_text[source].splitlines()
        expected_excerpt = lines[line - 1].strip() if line <= len(lines) else ""
        if not expected_excerpt or row.get("evidence") != expected_excerpt:
            raise VerificationError("RECORD_EXCERPT_INVALID", rid)
        key = (source, line, category, mechanism, dependency)
        if key in keyed:
            raise VerificationError("RECORD_DUPLICATE", rid)
        keyed.add(key)
        categories[category] += 1
        mechanisms[mechanism] += 1
        ownership = row.get("ownership")
        if not isinstance(ownership, dict):
            raise VerificationError("OWNERSHIP_INVALID", rid)
        if (ownership.get("status") != "REVIEW_REQUIRED" or ownership.get("owner") is not None
                or ownership.get("ownerType") is not None or not ownership.get("reason")):
            raise VerificationError("OWNERSHIP_INVALID", rid)
        if ownership["reason"] != (
            "WP-I0-010 records the baseline outbound integration inventory only; no reviewed "
            "outbound disposition decision exists, so disposition ownership is deferred to review."
        ):
            raise VerificationError("OWNERSHIP_REASON_INVALID", rid)

    if set(categories) != CATEGORIES:
        raise VerificationError("CATEGORY_COVERAGE_INCOMPLETE", str(dict(categories)))
    counts = inventory.get("counts", {})
    if dict(sorted(categories.items())) != counts.get("byCategory"):
        raise VerificationError("CATEGORY_COUNTS_INVALID", str(dict(categories)))
    if dict(sorted(mechanisms.items())) != counts.get("byMechanism"):
        raise VerificationError("MECHANISM_COUNTS_INVALID", str(dict(mechanisms)))
    if len(records) != counts.get("records"):
        raise VerificationError("RECORD_COUNT_INVALID", str(len(records)))
    if counts.get("sourceFiles") != len(actual_names) or counts.get("textScannedFiles") != len(scanned_names):
        raise VerificationError("CORPUS_COUNTS_INVALID", str(counts))

    # classification rules must be documented identically to the oracle constants
    rules = inventory.get("classificationRules", {})
    if (set(rules.get("recordedSchemes", [])) != RECORDED_SCHEMES
            or set(rules.get("updateCheckHosts", [])) != UPDATE_HOSTS
            or set(rules.get("commercialExactHosts", [])) != COMMERCIAL_EXACT
            or tuple(rules.get("commercialSuffixes", ())) != COMMERCIAL_SUFFIXES
            or tuple(rules.get("cloudSuffixes", ())) != CLOUD_SUFFIXES
            or tuple(rules.get("remoteModelSuffixes", ())) != MODEL_SUFFIXES
            or tuple(rules.get("telemetrySuffixes", ())) != TELEMETRY_SUFFIXES
            or list(rules.get("bareKnownHosts", [])) != BARE_HOSTS):
        raise VerificationError("CLASSIFICATION_RULES_MISMATCH", "inventory rules diverge from the oracle")
    if set(rules.get("namespaceHosts", [])) != NAMESPACE_URI_HOSTS:
        raise VerificationError("CLASSIFICATION_RULES_MISMATCH", "namespace hosts diverge")
    if inventory.get("categories") != sorted(CATEGORIES) or inventory.get("mechanisms") != sorted(MECHANISMS):
        raise VerificationError("KIND_ENUMERATION_INVALID", "categories/mechanisms listing mismatch")

    # ------------------------------------------------------------------
    # Independent oracle recomputation of every mechanism
    # ------------------------------------------------------------------
    expected_records: set[tuple[str, int, str, str, str]] = set()
    expected_exclusions: Counter[str] = Counter()
    bare_pattern = re.compile(
        rf"(?<![A-Za-z0-9._/-])(?P<host>{'|'.join(re.escape(h) for h in sorted(BARE_HOSTS, key=len, reverse=True))})(?![A-Za-z0-9.-])",
        re.I,
    )
    registry_extras = {"OUTBOUND_HOST"}

    for name, text in sorted(source_text.items()):
        path = root / name
        style = own_style(path)
        if style == "c":
            masked = own_masked(text, "c", path.suffix.lower() in EXTRA_HTML)
        elif style == "html":
            masked = own_mask_markup(text)
        elif style == "hash":
            masked = own_mask_hash(text)
        else:
            masked = text
        suffix = path.suffix.lower()

        literal_rows: set[tuple[str, int, str]] = set()
        for m in OWN_URL.finditer(masked):
            scheme = m.group("scheme").casefold()
            authority = m.group("authority")
            lineno = masked.count("\n", 0, m.start()) + 1
            if scheme not in RECORDED_SCHEMES:
                expected_exclusions["unrecorded-scheme"] += 1
                continue
            host = own_authority_host(authority)
            if not host:
                continue
            bucket = own_exclusion(host)
            if bucket:
                expected_exclusions[bucket] += 1
                continue
            for category in sorted({"OUTBOUND_HOST"} | own_extra_categories(host)):
                expected_records.add((name, lineno, "literal-external-host", f"literal-host:{host.casefold()}", category))
                literal_rows.add((name, lineno, f"literal-host:{host.casefold()}"))

        for m in bare_pattern.finditer(masked):
            lineno = masked.count("\n", 0, m.start()) + 1
            host = m.group("host").casefold()
            if (name, lineno, f"literal-host:{host}") in literal_rows:
                continue
            for category in sorted({"OUTBOUND_HOST"} | own_extra_categories(host)):
                expected_records.add((name, lineno, "bare-known-integration-host", f"bare-host:{host}", category))

        if suffix in {".yml", ".yaml"} or path.name.startswith("Dockerfile") or path.name.endswith(".dockerfile"):
            for lineno, mechanism, dep in own_container_refs(path, masked):
                if mechanism == "container-image-implicit-registry":
                    expected_records.add((name, lineno, mechanism, dep, "OUTBOUND_HOST"))
                else:
                    registry = dep.split(":", 2)[1]
                    for category in sorted(registry_extras | own_extra_categories(registry)):
                        expected_records.add((name, lineno, mechanism, dep, category))

        if style == "c":
            for lineno, module, symbol in own_js_imports(masked):
                for category, mechanism, predicate in (
                    ("TELEMETRY", "telemetry-sdk-import", own_tel),
                    ("TELEMETRY", "telemetry-module-import", own_tel_module),
                    ("REMOTE_MODEL_PATH", "hf-client-import", own_model),
                    ("CLOUD_SERVICE", "cloud-sdk-import", own_cloud),
                    ("COMMERCIAL_INTEGRATION", "commercial-sdk-import", own_commercial),
                ):
                    if predicate(module):
                        expected_records.add((name, lineno, mechanism, f"{module}:{symbol}", category))
        if suffix in {".py", ".pyi"}:
            for lineno, module, symbol in own_py_imports(masked):
                for category, mechanism, predicate in (
                    ("TELEMETRY", "telemetry-sdk-import", own_tel),
                    ("TELEMETRY", "telemetry-module-import", own_tel_module),
                    ("REMOTE_MODEL_PATH", "hf-client-import", own_model),
                    ("CLOUD_SERVICE", "cloud-sdk-import", own_cloud),
                    ("COMMERCIAL_INTEGRATION", "commercial-sdk-import", own_commercial),
                ):
                    if predicate(module):
                        expected_records.add((name, lineno, mechanism, f"{module}:{symbol}", category))
            for call in re.finditer(r"\bsnapshot_download\s*\(", masked):
                lineno = masked.count("\n", 0, call.start()) + 1
                prefix = masked[max(0, call.start() - 10):call.start()]
                if re.search(r"\bdef\s+$", prefix):
                    expected_records.add(
                        (name, lineno, "hf-snapshot-download-stub-definition", "test-stub:snapshot_download", "REMOTE_MODEL_PATH")
                    )
                    continue
                bound = (
                    re.search(r"(?m)^\s*from\s+huggingface_hub\s+import\s+[^\n]*\bsnapshot_download\b", masked) is not None
                    or (
                        re.search(r"(?m)^\s*import\s+huggingface_hub\b", masked) is not None
                        and re.search(r"\bhuggingface_hub\.snapshot_download\s*\(", masked) is not None
                    )
                )
                dep = f"huggingface_hub:snapshot_download"
                if not bound:
                    dep = f"unbound:{dep}"
                expected_records.add((name, lineno, "hf-snapshot-download", dep, "REMOTE_MODEL_PATH"))
                scope = re.search(r"immich-app/", masked[call.end():call.end() + 400])
                if scope:
                    scope_line = masked.count("\n", 0, call.end() + scope.start()) + 1
                    expected_records.add((name, scope_line, "hf-repo-scope", "hf-repo-scope:immich-app", "REMOTE_MODEL_PATH"))

        if path.name in {"package.json", "pyproject.toml"} or (
            suffix in {".yml", ".yaml"} and path.name in {"environment.yml", "environment.yaml", "env.yaml", "env.yml"}
        ):
            for lineno, mechanism, dep in own_manifest_rows(path, masked, text):
                for category in sorted(own_dependency_categories(dep.split(":", 1)[-1])):
                    expected_records.add((name, lineno, mechanism, dep, category))

    actual_records = {
        (row["sourcePath"], row["line"], row["mechanism"], row["dependency"], row["category"])
        for row in records
    }
    if expected_records != actual_records:
        missing = sorted(expected_records - actual_records)
        extra = sorted(actual_records - expected_records)
        raise VerificationError(
            "ORACLE_RECORD_MISMATCH",
            json.dumps({"missing": missing[:10], "extra": extra[:10],
                        "missingCount": len(missing), "extraCount": len(extra)}),
        )

    declared_exclusions = inventory.get("exclusions")
    if not isinstance(declared_exclusions, list):
        raise VerificationError("EXCLUSIONS_INVALID", "missing exclusion ledger")
    exclusion_counts = {row.get("class"): row.get("occurrences") for row in declared_exclusions if isinstance(row, dict)}
    if exclusion_counts != dict(expected_exclusions):
        raise VerificationError("ORACLE_EXCLUSION_MISMATCH",
                                json.dumps({"declared": exclusion_counts, "oracle": dict(expected_exclusions)}))
    for row in declared_exclusions:
        if set(row) != {"class", "reason", "occurrences", "examples"}:
            raise VerificationError("EXCLUSION_ROW_INVALID", str(row.get("class")))
        if not row.get("reason") or not isinstance(row.get("examples"), list) or row["examples"] != sorted(row["examples"]):
            raise VerificationError("EXCLUSION_ROW_INVALID", str(row.get("class")))
        if row.get("occurrences") != expected_exclusions.get(row.get("class")):
            raise VerificationError("EXCLUSION_COUNT_INVALID", str(row.get("class")))
    if set(counts.get("exclusions", {})) != set(exclusion_counts):
        raise VerificationError("EXCLUSION_COUNT_INVALID", "count roll-up mismatch")

    if set(REQUIRED_RECORDS) - actual_records:
        raise VerificationError("REQUIRED_RECORDS_MISSING", str(sorted(REQUIRED_RECORDS - actual_records)))

    # --- cross-artifact consistency ---
    if consistency.get("inventorySemanticSha256") != sha256_canonical(inventory):
        raise VerificationError("CONSISTENCY_INVENTORY_HASH", "inventory semantic hash mismatch")
    if consistency.get("sourceCorpusSemanticSha256") != sha256_canonical(inventory.get("sourceCorpus")):
        raise VerificationError("CONSISTENCY_CORPUS_HASH", "corpus semantic hash mismatch")
    if consistency.get("recordsSemanticSha256") != sha256_canonical(records):
        raise VerificationError("CONSISTENCY_RECORDS_HASH", "record semantic hash mismatch")
    if consistency.get("exclusionsSemanticSha256") != sha256_canonical(declared_exclusions):
        raise VerificationError("CONSISTENCY_EXCLUSIONS_HASH", "exclusion semantic hash mismatch")
    if (consistency.get("baselineFileCount") != len(base) or consistency.get("beforeFileCount") != len(actual_names)
            or consistency.get("afterFileCount") != len(actual_names)):
        raise VerificationError("CONSISTENCY_COUNTS", "file counts mismatch")
    if consistency.get("baselineSemanticSha256") != sha256_canonical(base):
        raise VerificationError("CONSISTENCY_BASELINE_HASH", "baseline hash mismatch")
    if summary.get("counts") != inventory.get("counts"):
        raise VerificationError("SUMMARY_COUNTS_MISMATCH", "summary diverges from inventory")
    if summary.get("requirementIds") != [REQUIREMENT_ID] or summary.get("failures") != []:
        raise VerificationError("SUMMARY_INVALID", "summary requirements or failures invalid")
    declared_artifacts = artifact_scan.get("generatedArtifacts")
    if not isinstance(declared_artifacts, list) or set(declared_artifacts) != {
        INVENTORY_FILE, "verification-report.json", "evidence-consistency.json", "provenance-report.json",
        "artifact-scan.json", "completion-evidence.md", "package-summary.json",
    }:
        raise VerificationError("ARTIFACT_LIST_INVALID", str(declared_artifacts))
    for name in declared_artifacts:
        if not (package / name).is_file():
            raise VerificationError("ARTIFACT_MISSING", str(name))
    if artifact_scan.get("allowedRoot") != "graphify/13-implementation/WP-I0-010":
        raise VerificationError("ALLOWED_ROOT_INVALID", str(artifact_scan.get("allowedRoot")))
    if artifact_scan.get("codebaseChanged") is not False or provenance.get("codebaseReadOnly") is not True:
        raise VerificationError("READ_ONLY_VIOLATION", "corpus mutation suspected")
    if provenance.get("method", "").find("no product code") < 0:
        raise VerificationError("PROVENANCE_METHOD_INVALID", "method declaration missing")

    return {
        "status": "PASS",
        "generationId": inventory["generationId"],
        "records": len(records),
        "sourceFiles": len(actual_names),
        "textScannedFiles": len(scanned_names),
        "categories": dict(sorted(categories.items())),
        "exclusions": dict(expected_exclusions),
        "verifiedAnchors": len(REQUIRED_RECORDS),
        "verifiedFixtures": len(fixture_statuses),
    }


def main() -> int:
    try:
        result = verify()
    except VerificationError as exc:
        print(json.dumps({"status": "FAIL", "error": {"code": exc.code, "message": str(exc)}}, indent=2), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
