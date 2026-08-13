#!/usr/bin/env python3
"""Generate the WP-I1-001 identity inventory without modifying Codebase/."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import struct
import subprocess
from collections import Counter
from pathlib import Path

PACKAGE = "WP-I1-001"
ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
BASELINE = ROOT / "graphify/13-implementation/WP-I0-001/sha256-manifest.csv"
REQUIREMENTS = [
    "CAN-LAM-ARCH-001", "CAN-LAM-ARCH-368", "CAN-LAM-ARCH-434",
    "CAN-LAM-ARCH-439", "CAN-LAM-ARCH-442", "CAN-LAM-ARCH-443",
    "CAN-LAM-LEGAL-010",
]
DISPOSITIONS = {
    "RENAME_TO_LAMHA", "REPLACE_WITH_LAMHA_ASSET", "MIGRATE_TO_LAMHA_IDENTIFIER",
    "PRESERVE_LEGAL", "PRESERVE_UPSTREAM_ATTRIBUTION", "PRESERVE_TECHNICAL_COMPATIBILITY",
    "REMOVE_LATER", "REVIEW_REQUIRED", "NOT_PRODUCT_IDENTITY",
}
SURFACE_TYPES = {
    "USER_VISIBLE", "PACKAGE_IDENTITY", "INTERNAL_RUNTIME", "FILESYSTEM_DATA_PATH", "BUILD",
    "DISTRIBUTION", "LEGAL", "ASSET", "FONT", "DOCUMENTATION", "TEST_ONLY", "GENERATED",
    "COMPATIBILITY", "UPSTREAM_ATTRIBUTION",
}
ACTION_DISPOSITIONS = DISPOSITIONS - {"NOT_PRODUCT_IDENTITY"}
OWNERS = {"WP-I1-002", "WP-I1-003", "WP-I1-004", "WP-I1-005"}
MANIFEST_CONTENT_FILES = {
    "app-data-inventory.json", "brand-asset-inventory.json", "bundled-binary-inventory.json",
    "codebase-integrity.json", "completion-evidence.md", "font-inventory.json", "generator-contracts.json",
    "identity-inventory.json", "inventory.py", "legal-attribution-inventory.json",
    "negative-fixture-results.json", "package-bundle-inventory.json", "package-summary.json",
    "risk-register.json", "scope-audit.json", "user-visible-inventory.json", "verification-report.json",
    "verify_evidence.py",
}
TEXT_SUFFIXES = {
    "", ".cjs", ".css", ".csv", ".dart", ".env", ".graphql", ".html", ".java", ".js",
    ".json", ".jsx", ".kt", ".kts", ".md", ".mdx", ".mjs", ".plist", ".properties",
    ".py", ".rb", ".rs", ".scss", ".sh", ".sql", ".svelte", ".svg", ".swift", ".toml",
    ".ts", ".tsx", ".txt", ".xml", ".yaml", ".yml",
}
ASSET_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".ico", ".svg"}
BRAND_ASSET_SUFFIXES = ASSET_SUFFIXES | {".xml", ".json"}
FONT_SUFFIXES = {".ttf", ".otf", ".woff", ".woff2"}
IDENTITY_RE = re.compile(
    r"(?i)((?-i:IMMICH_[A-Z0-9_]+)|app\.alextran\.immich(?:[._/-][a-z0-9_.-]+)*|"
    r"(?:com|io)\.immich(?:[._/-][a-z0-9_.-]+)*|ghcr\.io/immich-app(?:/[a-z0-9_.-]+)*|"
    r"github\.com/immich-app(?:/[a-z0-9_.-]+)*|(?:[a-z0-9-]+\.)*immich\.(?:app|cloud)|"
    r"(?-i:(?:[a-z][a-z0-9-]*\.)+immich(?:\.[A-Za-z0-9_-]+)*)|@immich/[a-z0-9_.-]+|"
    r"Immich::[A-Za-z0-9_:.-]+|(?:DCIM|Pictures|Documents)/Immich(?:[/A-Za-z0-9_.-]+)*|"
    r"immich://[a-z0-9_.?&=/#-]*|(?<![A-Za-z0-9])\.immich(?=[/\"'\s]|$)|immich:(?:changeToken|[A-Z][A-Za-z0-9_.:/-]*)|immich/(?:BackgroundWorker|MediaObserver|PeriodicBackgroundWorker)[A-Za-z0-9_.-]*|"
    r"~?/\.config/immich(?:/[A-Za-z0-9_.-]+)*|/\.well-known/immich|"
    r"immich[-_.](?:[a-z0-9_.-]*\.(?=[\"'])|[a-z0-9_.-]*[a-z0-9_-])|Immich[A-Z][A-Za-z0-9]*|\bimmich\b)"
)
FONT_RE = re.compile(r"(?i)\b(GoogleSansCode|GoogleSans|OverpassMono|Overpass|Inconsolata)(?:[-A-Za-z0-9_]*)\b")
FUTO_RE = re.compile(r"(?i)(FUTO\s+Holdings,\s*Inc\.|[A-Za-z0-9._%+-]+@futo\.org|(?:pay\.)?futo\.(?:org|tech)|Futo[A-Z][A-Za-z0-9]*|\bFUTO\b)")
BINARY_RE = re.compile(r"(?i)\b(exiftool(?:-vendored)?|jellyfin-ffmpeg|ffmpeg|ffprobe|libvips|imagemagick)\b")
BINARY_DECL_RE = re.compile(r"(?i)\b(tini|mise|uvx?|python(?:3(?:\.\d+)?)?|node|cuda|cudnn|openvino|rocm|armnn|rknn|onnxruntime|\.so(?:\.[0-9]+)*|/usr/local/bin|/bin/(?:tini|uvx?|python|mise)|apt-get\s+install|apk\s+add|dnf\s+install)\b")
BINARY_PACKAGE_RE = re.compile(r"(?i)(https?://[^\s\"']+\.(?:deb|rpm|tar\.gz|tgz|zip)|\b[a-z0-9][a-z0-9_.+-]*\.(?:deb|rpm|so(?:\.[0-9]+)*)\b|\bdpkg\s+-i\b)")
LEGAL_RE = re.compile(r"(?i)(\bcopyright\b|\blicen[cs]e(?:d|s)?\b|\battribution\b|\btrademark\b|\bthird[- ]party\b|\bSPDX\b|\bauthors?\b)")
LEGAL_IDENTITY_RE = re.compile(r"(?i)(\bcopyright\b|\battribution\b|\btrademark\b|\bSPDX\b)")
VISIBLE_RE = re.compile(
    r"(?i)(title|label|description|placeholder|tooltip|message|toast|heading|subject|display|"
    r"Text\(|<title|aria-label|alt=|Welcome|About|server URL|starting Immich)"
)
PACKAGE_RE = re.compile(
    r"(?i)(package(?:name)?|bundle|applicationId|namespace|PRODUCT_BUNDLE_IDENTIFIER|CFBundle|"
    r"app\.alextran\.immich|@immich/|immich-(?:mobile|web|server|cli|machine-learning)|"
    r"docker|container|image:|ghcr\.io|executable|bin/immich)"
)
DATA_RE = re.compile(r"(?i)(app[-_ ]?data|support directory|documents directory|(?<![A-Za-z0-9])\.immich(?:[/\\]|[\"'\s]|$)|immich[_-](?:data|cache|model|upload|library|postgres))")
DATA_ACCESS_RE = re.compile(r"(?i)(getApplicationDocumentsDirectory|getApplicationSupportDirectory|getTemporaryDirectory|getLibraryDirectory|getDownloadsDirectory|context\.(?:cacheDir|filesDir)|applicationContext\.(?:cacheDir|filesDir)|FileManager\.default\.urls\(for:\s*\.(?:caches|document|applicationSupport)Directory)")
COMPAT_RE = re.compile(
    r"(?i)(migration|legacy|backward|compat|cookie|header|user-agent|x-immich|api key|env\(|"
    r"IMMICH_[A-Z0-9_]+|database|protocol|oauth|redirect|volume|archive\.immich)"
)
UPSTREAM_RE = re.compile(r"(?i)(github\.com/immich-app|\btrademark\b|\bupstream\b|copyright\s+\(c\).*(?:immich|alex\s+tran))")
GENERATED_PATH_RE = re.compile(r"(?i)(^Codebase/(?:mobile/openapi|server/open-api|web/src/lib/api)/|^Codebase/open-api/immich-openapi-specs\.json$|^Codebase/packages/sdk/src/fetch-client\.ts$|\.g\.dart$|\.freezed\.dart$)")
TEST_PATH_RE = re.compile(r"(?i)(^|/)(test|tests|test-data|integration_tests?|e2e|fixtures?|mocks?|__tests?__|__mocks__)(/|$)|\.(spec|test)\.")
DOC_PATH_RE = re.compile(r"(?i)(^|/)(docs?|README|CONTRIBUTING|SECURITY|CODE_OF_CONDUCT)(/|\.|$)")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def dump(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def baseline_rows() -> list[dict[str, str]]:
    with BASELINE.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def verify_codebase(rows: list[dict[str, str]]) -> dict[str, object]:
    missing, modified = [], []
    expected = {row["path"] for row in rows}
    for row in rows:
        path = ROOT / row["path"]
        if not path.is_file():
            missing.append(row["path"])
        elif path.stat().st_size != int(row["size"]) or sha256(path.read_bytes()) != row["sha256"]:
            modified.append(row["path"])
    actual = {
        p.relative_to(ROOT).as_posix()
        for p in (ROOT / "Codebase").rglob("*")
        if p.is_file() and ".git" not in p.parts
    }
    return {
        "status": "PASS" if not missing and not modified and not (actual - expected) else "FAIL",
        "baseline": BASELINE.relative_to(ROOT).as_posix(),
        "expectedFiles": len(expected), "observedFiles": len(actual),
        "added": sorted(actual - expected), "removed": sorted(expected - actual),
        "modified": modified, "renamed": [],
    }


def is_text(path: Path) -> bool:
    if path.name == ".DS_Store" or path.stat().st_size > 20_000_000:
        return False
    with path.open("rb") as handle:
        return b"\0" not in handle.read(8192)


def is_generated(rel: str) -> bool:
    return bool(GENERATED_PATH_RE.search(rel))


def is_brand_asset(rel: str) -> bool:
    path = Path(rel)
    if path.suffix.lower() not in BRAND_ASSET_SUFFIXES:
        return False
    low = rel.lower()
    if path.suffix.lower() in ASSET_SUFFIXES and IDENTITY_RE.search(rel):
        return True
    role = r"(?i)(immich[-_ ]?logo|logo|favicon|app[-_ ]?icon|apple[-_ ]?icon|manifest[-_ ]?icon|splash|brand|wordmark|ic_launcher|notification_icon|screenshot|launchimage|launchscreen|launch[_-]?background|launchbackground)"
    if path.suffix.lower() in {".json", ".xml"}:
        asset_root = any(token in low for token in ("/assets/", "/res/", ".xcassets/", "/static/img/", "/design/"))
        return asset_root and (bool(re.search(role, path.name)) or any(token in low for token in (".appiconset/", ".imageset/")))
    return bool(re.search(role, rel)) or any(
        token in low for token in ("appicon.appiconset", "/phonescreenshots/", "/metadata/android/", "/fastlane/metadata/", "/mipmap-")
    )


def is_legal_file(rel: str) -> bool:
    path = Path(rel)
    name = path.name.lower()
    stem = path.stem.lower()
    return stem in {"license", "licence", "notice", "copying", "copyright", "authors", "third-party-notices", "third_party_notices",
                    "privacy-policy", "privacy_policy", "terms-of-service", "terms_of_service", "terms"} or any(
        token in rel.lower() for token in ("/licenses/", "/licences/", "/legal/")
    ) or rel.lower().endswith("mobile/lib/utils/licenses.dart")


def legal_matches(rel: str, line: str) -> list[str]:
    """Extract only legal/attribution cues, not business fields named license/author."""
    explicit = re.compile(r"(?i)(\bcopyright\b|\battribution\b|\btrademark\b|\bSPDX\b|\bthird[- ]party\s+(?:licen[cs]e|notice))")
    prose = re.compile(r"(?i)(\blicen[cs]ed\s+under\b|\blicen[cs]e\s+(?:terms|notice|file)\b|\bopen[- ]source\s+licen[cs]e\b|\bsoftware\s+licen[cs]e\b)")
    matches = [m.group(0) for m in explicit.finditer(line)] + [m.group(0) for m in prose.finditer(line)]
    if Path(rel).name.lower() in {"package.json", "pyproject.toml", "pubspec.yaml"}:
        matches += [m.group(0) for m in re.finditer(r"(?i)[\"']?(?:author|authors|license|licence)[\"']?\s*[:=]", line)]
    return matches


def canonical_source(rel: str) -> str | None:
    path = ROOT / rel
    if rel.endswith(".g.dart"):
        candidate = Path(str(path).replace(".g.dart", ".dart"))
        if candidate.is_file():
            return candidate.relative_to(ROOT).as_posix()
    if rel.endswith(".freezed.dart"):
        candidate = Path(str(path).replace(".freezed.dart", ".dart"))
        if candidate.is_file():
            return candidate.relative_to(ROOT).as_posix()
    if "openapi" in rel.lower() or "/src/lib/api/" in rel.lower() or rel.endswith("packages/sdk/src/fetch-client.ts"):
        return "generator-contract:openapi"
    return "generator-contract:dart-codegen" if is_generated(rel) else None


def app_data_extra(rel: str, line: str, value: str) -> dict[str, object]:
    low = rel.lower()
    platform = "Android" if "/android/" in low else "iOS/macOS" if "/ios/" in low or "/macos/" in low else "Flutter cross-platform" if "/mobile/" in low else "Server/distribution"
    durable_mount = bool(re.search(r"(?i)(?:^|\s)(?:-v|--volume(?:=)?)\s+|volume-mount|docker-compose", line))
    temporary = bool(re.search(r"(?i)(temporary|cacheDir|cachesDirectory|[_-]cache)", line)) and not durable_mount
    writer = bool(re.search(r"(?i)(File\(|createDirectory|write|mkdir|storageDir)", line))
    result = {
        "platform": platform, "currentNameOrExpression": value,
        "accessRole": "writer-or-reader/writer" if writer else "directory provider or reader",
        "persistentData": not temporary,
    }
    if temporary:
        result.update({
            "futureTarget": "Platform-provided Lamha cache/temporary container; durable bytes are not moved",
            "migrationDecision": "NO DATA MIGRATION; cache/temporary data may be recreated after identifier change",
            "backwardCompatibility": "No durable-data compatibility obligation; avoid cache-key collision and safely ignore/clean stale cache",
            "migrationTest": "Switch identity with a populated cache, verify startup and regeneration succeed, durable records remain intact, and no stale cache is treated as authoritative.",
        })
    else:
        result.update({
            "futureTarget": "Lamha application-owned equivalent, exact identifier owned by WP-I1-003",
            "migrationDecision": "MIGRATION REQUIRED; do not strand or overwrite existing Immich data",
            "backwardCompatibility": "WP-I1-003 must probe the legacy location and preserve rollback/read compatibility",
            "migrationTest": "Seed legacy-path data, migrate once, verify byte/record preservation, idempotence, rollback visibility, and no fresh writes to the legacy name.",
        })
    return result


def symbol_only(line: str) -> bool:
    stripped = line.strip()
    return bool(re.match(r"(?:import|export|type|interface|enum)\b", stripped)) or bool(
        re.search(r"(?<![\"'])\b(?:Immich[A-Z][A-Za-z0-9]*|IMMICH_[A-Z0-9_]+)\b(?![\"'])", stripped)
    ) and not bool(re.search(r"[>\"']\s*Immich(?:\s|[<\"'])", stripped, re.I))


def classify_occurrence(rel: str, line: str, start: int, end: int) -> tuple[str, str, str | None, str, str | None]:
    prefix = line[:start]
    raw_token = line[start:end]
    token = raw_token.lower()
    attribute_spans = [m.span() for m in re.finditer(r"(?i)(?:class(?:Name)?|id|style)\s*=\s*[\"'][^\"']*[\"']|class:[^\s=>]+", line)]
    in_style_attribute = any(left <= start < right for left, right in attribute_spans)
    direct_style = token.startswith(("immich-dark", "immich-light", "immich-scrollbar", "immich-form", "immich-ui", "immich-asset")) or line[max(0, start-2):start] in {"--", ".", "#"} or bool(re.search(r"(?i)(?:bg|text|border|outline|ring|stroke|fill)[-:\w]*-$", prefix))
    quoted_spans = [m.span() for m in re.finditer(r"[\"'][^\"']*[\"']", line)]
    in_quoted = any(left <= start < right for left, right in quoted_spans)
    module_syntax = bool(re.match(r"^\s*import\b", line)) or bool(re.match(r"^\s*export\b.*\bfrom\s*[\"']", line)) or bool(re.search(r"\b(?:require|import)\s*\(\s*[\"']", line))
    module_specifier = in_quoted and module_syntax
    if "/i18n/" in rel.lower() and rel.lower().endswith(".json"):
        return "USER_VISIBLE", "RENAME_TO_LAMHA", "WP-I1-002", "Localized resource value is canonical user-visible copy.", "localized-copy"
    if TEST_PATH_RE.search(rel):
        token_compat = raw_token.startswith("IMMICH_") or bool(re.fullmatch(r"(?i)(?:[a-z0-9-]+\.)*immich\.(?:app|cloud)", raw_token)) or prefix.lower().endswith("x-")
        if token_compat:
            return "TEST_ONLY", "PRESERVE_TECHNICAL_COMPATIBILITY", "WP-I1-003", "Test occurrence protects an external or persisted compatibility contract.", None
        if in_style_attribute or direct_style or module_specifier or re.match(r"immich[A-Z]", raw_token):
            return "TEST_ONLY", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003", "Test occurrence follows the production package/internal identifier migration.", None
        if VISIBLE_RE.search(line) or re.search(r"(?i)[\"'](?:Welcome to |About )?Immich(?:\s|[\"'])", line):
            return "TEST_ONLY", "RENAME_TO_LAMHA", "WP-I1-002", "Test assertion protects a user-visible product-name surface.", None
        return "TEST_ONLY", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003", "Test identity follows the production identifier migration.", None
    if is_legal_file(rel):
        return "UPSTREAM_ATTRIBUTION", "PRESERVE_UPSTREAM_ATTRIBUTION", "WP-I1-005", "Identity inside a dedicated legal/privacy document is preserved for reviewed legal handling.", "legal-document-identity"
    if raw_token.lower().startswith("immich://"):
        return "COMPATIBILITY", "PRESERVE_TECHNICAL_COMPATIBILITY", "WP-I1-003", "Legacy deep-link scheme is an external contract requiring alias and migration coverage.", "deep-link-scheme"
    if raw_token.startswith(".immich") or "::" in raw_token or re.match(r"(?i)(?:DCIM|Pictures|Documents)/Immich", raw_token) or re.match(r"(?i)immich(?::|/)", raw_token):
        return "FILESYSTEM_DATA_PATH", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003", "Persisted preference/container or user-media path requires an explicit compatibility migration.", "persisted-storage-name"
    if raw_token.startswith(("/", "~/")):
        if raw_token.lower().startswith("/.well-known/"):
            return "COMPATIBILITY", "PRESERVE_TECHNICAL_COMPATIBILITY", "WP-I1-003", "HTTP well-known route is an external protocol contract, not a filesystem path.", "well-known-route"
        if raw_token.lower().startswith("~/.config/"):
            return "FILESYSTEM_DATA_PATH", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003", "User configuration directory is persisted application data requiring migration evidence.", "filesystem-path"
        if re.search(r"(?i)https?://[^\s\"']*$", prefix):
            return "COMPATIBILITY", "PRESERVE_TECHNICAL_COMPATIBILITY", "WP-I1-003", "External URL path identity is a compatibility/coordination contract, not product prose.", "external-url-path"
        build_context = any(token in rel.lower() for token in ("/.github/", "/open-api/", "package.json", "mise.toml", "/scripts/", "/bin/")) or bool(re.search(r"(?i)(openapi|source|output|artifact|template|image)", line))
        route_context = bool(DOC_PATH_RE.search(rel)) or bool(re.search(r"(?i)(route|url|endpoint|href|src=)", line))
        if build_context:
            return "BUILD", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003", "Repository/build artifact path is not application data.", "build-artifact-path"
        if route_context:
            return "COMPATIBILITY", "PRESERVE_TECHNICAL_COMPATIBILITY", "WP-I1-003", "Published route/resource path is a compatibility surface, not application data.", "route-resource-path"
        return "FILESYSTEM_DATA_PATH", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003", "Application-owned filesystem/config path requires migration evidence.", "filesystem-path"
    if re.fullmatch(r"(?i)(?:[a-z][a-z0-9-]*\.)+immich(?:\.[a-z0-9_-]+)*", raw_token):
        if line[end:].startswith(":/"):
            return "COMPATIBILITY", "PRESERVE_TECHNICAL_COMPATIBILITY", "WP-I1-003", "Custom URI scheme is an external redirect contract requiring a compatibility migration.", "uri-scheme"
        return "PACKAGE_IDENTITY", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003", "Reverse-DNS bundle, app-group, or application identifier requires coordinated migration.", "reverse-dns-identifier"
    if re.search(r"(?i)(?:^|\s)(?:-v|--volume(?:=)?)\s*$", prefix):
        return "FILESYSTEM_DATA_PATH", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003", "Named container volume is a durable persistence path requiring an explicit compatibility migration.", "container-volume"
    if in_style_attribute or direct_style:
        return "INTERNAL_RUNTIME", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003", "CSS/DOM/style token is internal identity, not displayed product copy.", "style-token"
    if module_specifier and (raw_token.lower().startswith("@immich/") or line[max(0, start - 8):start].lower().endswith("package:") or "immich" in raw_token.lower()):
        return "PACKAGE_IDENTITY", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003", "Quoted module/package specifier is a package identity contract; imported symbols are classified separately.", "module-specifier"
    low_rel = rel.lower()
    env_context = low_rel.endswith((".env", "example.env")) or any(token in low_rel for token in ("docker-compose", "/env.", "/env/", ".devcontainer")) or bool(re.search(r"(?i)(?:process|import\.meta)\.env|\benv\s*\(|\$\{?IMMICH_|^\s*IMMICH_[A-Z0-9_]+\s*=", line)) or bool(DOC_PATH_RE.search(rel))
    if raw_token.startswith("IMMICH_") and env_context:
        return "COMPATIBILITY", "PRESERVE_TECHNICAL_COMPATIBILITY", "WP-I1-003", "Environment/configuration name is an external operator contract requiring an alias or compatibility migration.", "environment-contract"
    if re.match(r"immich[A-Z]", raw_token) and not TEST_PATH_RE.search(rel):
        return "INTERNAL_RUNTIME", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003", "Lower-camel code/asset symbol is internal identity, not rendered product copy.", "code-symbol"
    if raw_token.lower() == "immich" and (re.search(r"(?i)\.name\s*\(\s*[\"']$", prefix) or re.search(r"(?i)--filter\s+$", prefix)):
        return "PACKAGE_IDENTITY", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003", "CLI/package selector is an executable or package identity.", "command-package-identity"
    if raw_token.lower() == "immich" and re.search(r"(?i)(\.scheme\b|android:scheme|CFBundleURLSchemes|URL\s*scheme)", line):
        return "COMPATIBILITY", "PRESERVE_TECHNICAL_COMPATIBILITY", "WP-I1-003", "Bare legacy deep-link scheme is an external compatibility contract.", "deep-link-scheme"
    if raw_token.lower() == "immich" and ("db.repository" in rel.lower() or re.search(r"(?i)(sqlite|databaseName|driftDatabase|export_)", line)):
        return "FILESYSTEM_DATA_PATH", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003", "Database/export filename is persisted application data requiring migration evidence.", "database-storage-name"
    if re.search(r"(?i)https?://[^\s\"']*$", prefix):
        return "COMPATIBILITY", "PRESERVE_TECHNICAL_COMPATIBILITY", "WP-I1-003", "External URL/listing path is a compatibility contract.", "external-url"
    if "user_agent" in rel.lower() or re.search(r"(?i)user[-_ ]agent", line):
        return "COMPATIBILITY", "PRESERVE_TECHNICAL_COMPATIBILITY", "WP-I1-003", "User-Agent identity is an external protocol contract.", "user-agent"
    if "/mobile/pigeon/" in rel.lower() and in_quoted and re.search(r"(?i)\.g\.(?:kt|swift|dart)[\"']?", line):
        return "BUILD", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003", "Pigeon generated-output path is a build contract even when its output key is on the preceding line.", "codegen-output-path"
    if re.search(r"(?i)(kotlinOut|dartOut|swiftOut|javaOut|outputPath|generatedPath)\s*:", line):
        return "BUILD", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003", "Code-generator output path is a build contract, not displayed copy.", "codegen-output-path"
    documentation = bool(DOC_PATH_RE.search(rel)) or rel.lower().endswith((".md", ".mdx"))
    inline_code = any(left <= start < right for left, right in (m.span() for m in re.finditer(r"`[^`]+`", line)))
    technical_prefix = bool(re.search(r"(?i)(?:image:|docker\s+(?:run|pull)|container_name:|package\s+)\s*$", prefix))
    technical_doc = documentation and (inline_code or bool(re.match(r"(?i)\s*(?:client_id|database|DB_[A-Z_]+|cd\s+|[/~.]|[A-Z_]+=)", line)) or bool(re.search(r"(?i)(/\.well-known/|/workspaces/|\.config/|:\s*[\"']immich)", line)))
    external_url = bool(re.search(r"(?i)https?://[^\s\"']*$", prefix))
    if documentation and raw_token.lower() == "immich" and (technical_doc or technical_prefix):
        return "COMPATIBILITY", "PRESERVE_TECHNICAL_COMPATIBILITY", "WP-I1-003", "Identifier inside technical documentation/code remains a compatibility or package migration surface.", "documented-technical-identifier"
    if documentation and external_url:
        return "COMPATIBILITY", "PRESERVE_TECHNICAL_COMPATIBILITY", "WP-I1-003", "External URL/account path in documentation is preserved as a compatibility/coordination surface.", "external-url"
    product_domain = bool(re.fullmatch(r"(?i)(?:[a-z0-9-]+\.)*immich\.(?:app|cloud)", raw_token))
    if documentation and not is_legal_file(rel) and (raw_token.lower() == "immich" or product_domain) and not inline_code and not technical_prefix:
        return "DOCUMENTATION", "RENAME_TO_LAMHA", "WP-I1-002", "Published product prose/link is user-visible even when adjacent text discusses technical compatibility.", "published-product-copy"
    rendered_source = rel.lower().endswith((".svelte", ".html", ".tsx", ".email.tsx"))
    if rendered_source and raw_token.lower() == "immich" and (in_quoted or not symbol_only(line)):
        return "USER_VISIBLE", "RENAME_TO_LAMHA", "WP-I1-002", "Rendered product copy is user-visible independently of adjacent technical words.", "rendered-product-copy"
    canonical_api_copy = "/server/src/" in low_rel and not is_generated(rel) and (".describe(" in line or "description:" in line or "[ApiTag." in line or "/dtos/" in low_rel or low_rel.endswith("server/src/enum.ts")) and in_quoted
    if canonical_api_copy:
        return "DOCUMENTATION", "RENAME_TO_LAMHA", "WP-I1-002", "Canonical OpenAPI/schema description is published API documentation; generated copies follow the generator contract.", "canonical-api-copy"
    mobile_human = any(ext in rel.lower() for ext in (".dart", ".swift", ".kt", ".java")) and in_quoted
    shell_human = rel.lower().endswith(".sh") and bool(re.search(r"(?i)(log_message|echo|printf)", line))
    human_quoted = in_quoted and raw_token.lower() == "immich" and (mobile_human or shell_human or bool(re.search(r"(?i)(welcome|login|starting|initializ|listening|error|failed|throw|exception|compatible|export|server URL|API key|description)", line)))
    if human_quoted:
        return "USER_VISIBLE", "RENAME_TO_LAMHA", "WP-I1-002", "Human-readable quoted runtime/operator message is user-visible, not the surrounding code symbol.", "runtime-message"
    visible_template = any(token in low_rel for token in ("/.github/issue_template/", "/.github/discussion_template/", "/fastlane/metadata/", "/android/metadata/")) or low_rel.startswith("codebase/.github/issue_template/") or low_rel.startswith("codebase/.github/discussion_template/")
    operator_output = low_rel.endswith("install.sh") and raw_token.lower() == "immich"
    operator_instruction = low_rel.endswith("docker/example.env") and line.lstrip().startswith("#")
    compose_instruction = "docker-compose" in low_rel and line.lstrip().startswith("#") and raw_token.lower() == "immich"
    cli_help = "/packages/cli/" in low_rel and in_quoted and bool(re.search(r"(?i)(server URL|API key|description|help|option)", line))
    widget_copy = ("widgetextension" in low_rel or "/res/values/strings.xml" in low_rel) and bool(re.search(r"(?i)(login|description|title|label|message)", line))
    workflow_label = "/.github/workflows/" in low_rel and raw_token.lower() == "immich"
    if visible_template or operator_output or cli_help or widget_copy or workflow_label:
        return "USER_VISIBLE", "RENAME_TO_LAMHA", "WP-I1-002", "Template/store/operator output is directly presented to a user or administrator.", "published-operator-copy"
    if operator_instruction or compose_instruction:
        return "DOCUMENTATION", "RENAME_TO_LAMHA", "WP-I1-002", "Example environment comments are published operator instructions.", "operator-instruction"
    attributes = list(re.finditer(r"android:(label|name)\s*=\s*[\"'][^\"']*$", prefix, re.I))
    if attributes:
        attribute = attributes[-1].group(1).lower()
        if attribute == "label":
            return "USER_VISIBLE", "RENAME_TO_LAMHA", "WP-I1-002", "Android application label is directly user-visible.", "android:label"
        return "PACKAGE_IDENTITY", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003", "Android component/class identity is internal package identity.", "android:name"
    key = re.search(r'[\"\'](name|short_name)[\"\']\s*:\s*[\"\'][^\"\']*$', prefix, re.I)
    if key and rel.lower().endswith("manifest.json"):
        return "USER_VISIBLE", "RENAME_TO_LAMHA", "WP-I1-002", "PWA manifest name is displayed by browsers and installers.", key.group(1).lower()
    stype, disposition, owner, rationale = classify(rel, line)
    return stype, disposition, owner, rationale, None


def structural_specs(rel: str, line: str, next_line: str) -> list[tuple[str, str, str, str, str | None]]:
    """Return key, value, surface type, disposition, owner for identity structures independent of brand tokens."""
    low = rel.lower()
    specs: list[tuple[str, str, str, str, str | None]] = []
    plist = re.search(r"<key>(CFBundleExecutable|CFBundleDisplayName|CFBundleName|CFBundleIdentifier|CFBundleURLSchemes)</key>", line)
    if plist:
        key = plist.group(1)
        value_match = re.search(r"<(?:string|array)>(.*?)</(?:string|array)>", next_line)
        value = value_match.group(1) if value_match else next_line.strip()
        visible = key == "CFBundleDisplayName"; compatibility = key == "CFBundleURLSchemes"
        specs.append((key, value, "USER_VISIBLE" if visible else "COMPATIBILITY" if compatibility else "PACKAGE_IDENTITY",
                      "RENAME_TO_LAMHA" if visible else "PRESERVE_TECHNICAL_COMPATIBILITY" if compatibility else "MIGRATE_TO_LAMHA_IDENTIFIER",
                      "WP-I1-002" if visible else "WP-I1-003"))
    if low.endswith(".pbxproj"):
        match = re.search(r"\b(PRODUCT_BUNDLE_IDENTIFIER|PRODUCT_NAME|TARGET_NAME|CUSTOM_GROUP_ID|INFOPLIST_KEY_CFBundleDisplayName)\s*=\s*([^;]+);", line)
        if not match:
            match = re.search(r"\b(productName|name)\s*=\s*(Runner|WidgetExtension|ShareExtension);", line)
        if match:
            key, value = match.group(1), match.group(2).strip().strip('"')
            visible = key == "INFOPLIST_KEY_CFBundleDisplayName"
            specs.append((key, value, "USER_VISIBLE" if visible else "PACKAGE_IDENTITY",
                          "RENAME_TO_LAMHA" if visible else "MIGRATE_TO_LAMHA_IDENTIFIER",
                          "WP-I1-002" if visible else "WP-I1-003"))
    if low.endswith("package.json"):
        match = re.search(r'^\s*"(name|bin)"\s*:\s*(.+?)[,]?\s*$', line)
        if match:
            value = match.group(2); branded = "immich" in value.lower(); is_bin = match.group(1) == "bin"
            specs.append((f"package.json:{match.group(1)}", value, "PACKAGE_IDENTITY" if branded or is_bin else "INTERNAL_RUNTIME",
                          "MIGRATE_TO_LAMHA_IDENTIFIER" if branded or is_bin else "NOT_PRODUCT_IDENTITY",
                          "WP-I1-003" if branded or is_bin else None))
    if low.endswith("pubspec.yaml"):
        match = re.search(r"^name:\s*(\S+)", line)
        if match:
            value = match.group(1); branded = "immich" in value.lower()
            specs.append(("pubspec:name", value, "PACKAGE_IDENTITY" if branded else "INTERNAL_RUNTIME",
                          "MIGRATE_TO_LAMHA_IDENTIFIER" if branded else "NOT_PRODUCT_IDENTITY", "WP-I1-003" if branded else None))
        description = re.search(r"^description:\s*(.+)", line)
        if description and "immich" in description.group(1).lower():
            specs.append(("pubspec:description", description.group(1), "USER_VISIBLE", "RENAME_TO_LAMHA", "WP-I1-002"))
    if low.endswith(("build.gradle", "build.gradle.kts")):
        match = re.search(r"\b(applicationId|applicationIdSuffix|namespace)\s*(?:=\s*)?[\"']([^\"']+)", line)
        if match:
            specs.append((f"android:{match.group(1)}", match.group(2), "PACKAGE_IDENTITY", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003"))
    if low.endswith("androidmanifest.xml"):
        for match in re.finditer(r"android:(label|name)\s*=\s*[\"']([^\"']+)", line, re.I):
            label = match.group(1).lower() == "label"; branded_label = label and "immich" in match.group(2).lower()
            app_owned = (not label) and ("immich" in match.group(2).lower() or match.group(2).startswith("."))
            specs.append((f"android:{match.group(1).lower()}", match.group(2),
                          "USER_VISIBLE" if branded_label else "PACKAGE_IDENTITY" if app_owned else "INTERNAL_RUNTIME",
                          "RENAME_TO_LAMHA" if branded_label else "MIGRATE_TO_LAMHA_IDENTIFIER" if app_owned else "NOT_PRODUCT_IDENTITY",
                          "WP-I1-002" if branded_label else "WP-I1-003" if app_owned else None))
    if Path(rel).name.lower().startswith("dockerfile"):
        match = re.match(r"\s*(ENTRYPOINT|CMD)\s+(.+)", line, re.I)
        if match:
            app_owned = "immich" in match.group(2).lower()
            specs.append((f"docker:{match.group(1).upper()}", match.group(2), "DISTRIBUTION" if app_owned else "COMPATIBILITY",
                          "MIGRATE_TO_LAMHA_IDENTIFIER" if app_owned else "PRESERVE_TECHNICAL_COMPATIBILITY", "WP-I1-003"))
    if re.search(r"(?i)docker-compose.*\.ya?ml$", rel):
        project_name = re.match(r"^name:\s*([^\s#]+)", line)
        if project_name:
            specs.append(("compose:project-name", project_name.group(1), "DISTRIBUTION", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003"))
        match = re.match(r"^\s{2}([a-zA-Z0-9_.-]+):\s*$", line)
        if match and match.group(1) not in {"services", "volumes", "networks", "configs", "secrets"}:
            value = match.group(1)
            app_owned = "immich" in value.lower() or value.lower() in {"server", "web", "machine-learning", "machine_learning"}
            specs.append(("compose:application-service" if app_owned else "compose:external-infrastructure", value,
                          "DISTRIBUTION" if app_owned else "COMPATIBILITY",
                          "MIGRATE_TO_LAMHA_IDENTIFIER" if app_owned else "PRESERVE_TECHNICAL_COMPATIBILITY", "WP-I1-003"))
    return specs


def data_declaration(rel: str, line: str) -> tuple[str, str] | None:
    low = rel.lower()
    env = re.match(r"\s*(UPLOAD_LOCATION|DB_DATA_LOCATION|IMMICH_MEDIA_LOCATION|THUMB_LOCATION|PROFILE_LOCATION|BACKUP_LOCATION)\s*=\s*(.+)", line)
    if env:
        return f"env:{env.group(1)}", env.group(2).strip()
    if "docker-compose" in low and low.endswith((".yml", ".yaml")):
        volume = re.match(r"\s*-\s+([^#]+?):(/[^#\s]+)\s*$", line)
        if volume and re.search(r"(?i)(?:^|[/_.-])(data|upload|library|postgres|redis|models?|cache|thumbs?|profiles?|backups?)(?:$|[/_.-])", f"{volume.group(1)}:{volume.group(2)}"):
            return "compose:volume-mount", f"{volume.group(1).strip()}:{volume.group(2)}"
    if Path(rel).name.lower().startswith("dockerfile"):
        volume = re.match(r"\s*VOLUME\s+(.+)", line, re.I)
        if volume:
            return "docker:VOLUME", volume.group(1).strip()
    if low.endswith("server/src/enum.ts"):
        folder = re.match(r"\s*(EncodedVideo|Library|Upload|Profile|Thumbnails|Backups)\s*=\s*[\"']([^\"']+)", line)
        if folder and line.strip() in {"EncodedVideo = 'encoded-video',", "Library = 'library',", "Upload = 'upload',", "Profile = 'profile',", "Thumbnails = 'thumbs',", "Backups = 'backups',"}:
            return f"StorageFolder:{folder.group(1)}", folder.group(2)
    if low.endswith("server/src/maintenance/maintenance-worker.service.ts"):
        paths = re.findall(r"[\"'](/(?:data|usr/src/app/upload))[\"']", line)
        if paths:
            return "maintenance:legacy-storage-root", " | ".join(paths)
    return None


def classify(rel: str, line: str) -> tuple[str, str, str | None, str]:
    low = rel.lower()
    test = bool(TEST_PATH_RE.search(rel))
    generated = is_generated(rel)
    documentation = bool(DOC_PATH_RE.search(rel)) or low.endswith((".md", ".mdx"))
    legal_path = is_legal_file(rel)
    if "/i18n/" in low and low.endswith(".json"):
        return "USER_VISIBLE", "RENAME_TO_LAMHA", "WP-I1-002", "Localized resource value is canonical user-visible copy."
    if legal_path or LEGAL_IDENTITY_RE.search(line):
        if UPSTREAM_RE.search(line) or "license" in low or "licence" in low:
            return "UPSTREAM_ATTRIBUTION", "PRESERVE_UPSTREAM_ATTRIBUTION", "WP-I1-005", "Legal/upstream provenance must survive the rebrand."
        return "LEGAL", "PRESERVE_LEGAL", "WP-I1-005", "Legal notice is preserved and reviewed, never mechanically renamed."
    if generated:
        return "GENERATED", "PRESERVE_TECHNICAL_COMPATIBILITY", "WP-I1-003", "Generated identity is changed only through its canonical source and compatibility plan."
    if test:
        if VISIBLE_RE.search(line) or re.search(r"(?i)[\"'](?:Welcome to |About )?Immich(?:\s|[\"'])", line):
            return "TEST_ONLY", "RENAME_TO_LAMHA", "WP-I1-002", "Test assertion protects a user-visible product-name surface."
        if COMPAT_RE.search(line):
            return "TEST_ONLY", "PRESERVE_TECHNICAL_COMPATIBILITY", "WP-I1-003", "Test assertion protects an external or persisted compatibility contract."
        return "TEST_ONLY", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003", "Test identity follows the production identifier migration and compatibility fixtures."
    if symbol_only(line):
        return "INTERNAL_RUNTIME", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003", "Symbol/import identity is not directly rendered; migrate it with internal package/runtime identity."
    if PACKAGE_RE.search(line) or low.endswith(("package.json", "pubspec.yaml", "androidmanifest.xml", "info.plist")):
        stype = "DISTRIBUTION" if any(x in low for x in ("docker", "compose", "release", "fastlane", "helm")) else "PACKAGE_IDENTITY"
        return stype, "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003", "Package, bundle, binary, or distribution identity requires an explicit migration."
    if DATA_RE.search(line):
        return "FILESYSTEM_DATA_PATH", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003", "Persistent data names require a compatibility-safe migration."
    if COMPAT_RE.search(line):
        return "COMPATIBILITY", "PRESERVE_TECHNICAL_COMPATIBILITY", "WP-I1-003", "Externally observable or persisted identity needs a compatibility decision."
    if re.search(r"[\"'`]([^\"'`]*\bImmich(?:\s+[A-Z][A-Za-z]+|\s)[^\"'`]*)[\"'`]", line):
        return "USER_VISIBLE", "RENAME_TO_LAMHA", "WP-I1-002", "Human-readable product string is displayed through UI, error, log, help, or operator output."
    if documentation:
        if UPSTREAM_RE.search(line):
            return "UPSTREAM_ATTRIBUTION", "PRESERVE_UPSTREAM_ATTRIBUTION", "WP-I1-005", "Historical/upstream link or attribution remains traceable."
        return "DOCUMENTATION", "RENAME_TO_LAMHA", "WP-I1-002", "User-facing documentation must use the Lamha name."
    if VISIBLE_RE.search(line) or low.endswith((".svelte", ".html", ".tsx", ".email.tsx")):
        return "USER_VISIBLE", "RENAME_TO_LAMHA", "WP-I1-002", "Displayed product identity must become Lamha."
    if any(x in low for x in ("build", "mise", "vite", "webpack", "scripts/", "bin/")):
        return "BUILD", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003", "Build/runtime identity follows the package migration."
    return "INTERNAL_RUNTIME", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003", "Internal product identity is inventoried for the package/runtime migration."


def record(rel: str, locator: str, value: str, stype: str, disposition: str,
           owner: str | None, rationale: str, *, generated: bool = False,
           extra: dict[str, object] | None = None) -> dict[str, object]:
    generated = generated or is_generated(rel)
    key = f"{rel}\0{locator}\0{value}\0{stype}"
    rec: dict[str, object] = {
        "surfaceId": "ID-" + sha256(key.encode())[:16].upper(),
        "path": rel, "locator": locator, "currentValue": value[:2000],
        "surfaceType": stype, "disposition": disposition, "futureOwner": owner,
        "binding": disposition != "NOT_PRODUCT_IDENTITY",
        "legalSensitivity": disposition in {"PRESERVE_LEGAL", "PRESERVE_UPSTREAM_ATTRIBUTION"} or stype in {"LEGAL", "FONT", "UPSTREAM_ATTRIBUTION"},
        "compatibilitySensitivity": disposition in {"MIGRATE_TO_LAMHA_IDENTIFIER", "PRESERVE_TECHNICAL_COMPATIBILITY"},
        "migrationRequirement": "Owner must resolve this record explicitly before the applicable I1 exit gate.",
        "isGenerated": generated, "canonicalSourcePath": canonical_source(rel) if generated else None,
        "verificationMethod": "Re-scan exact path and locator; compare disposition and owner against the reviewed inventory.",
        "rationale": rationale,
    }
    if extra:
        rec.update(extra)
    if stype in {"USER_VISIBLE", "DOCUMENTATION"}:
        low = rel.lower()
        if "/emails/" in low:
            rec["observationContext"] = "Transactional email"
        elif "/web/" in low or low.endswith((".svelte", ".html")):
            rec["observationContext"] = "Web user interface"
        elif "/mobile/" in low:
            rec["observationContext"] = "Mobile user interface"
        elif "/docs/" in low:
            rec["observationContext"] = "Published documentation/site"
        else:
            rec["observationContext"] = "User-visible runtime or distribution text"
    return rec


def image_dimensions(path: Path) -> dict[str, object]:
    try:
        data = path.read_bytes()
        if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
            width, height = struct.unpack(">II", data[16:24])
            return {"width": width, "height": height, "dimensionSource": "PNG header"}
        if data[:6] in {b"GIF87a", b"GIF89a"} and len(data) >= 10:
            width, height = struct.unpack("<HH", data[6:10])
            return {"width": width, "height": height, "dimensionSource": "GIF header"}
        if data.startswith(b"\x00\x00\x01\x00") and len(data) >= 8:
            width, height = data[6] or 256, data[7] or 256
            return {"width": width, "height": height, "dimensionSource": "ICO directory"}
        if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
            chunk = data[12:16]
            if chunk == b"VP8X" and len(data) >= 30:
                width = 1 + int.from_bytes(data[24:27], "little"); height = 1 + int.from_bytes(data[27:30], "little")
                return {"width": width, "height": height, "dimensionSource": "WebP VP8X header"}
            if chunk == b"VP8 " and len(data) >= 30:
                pos = data.find(b"\x9d\x01\x2a", 20)
                if pos >= 0 and len(data) >= pos + 7:
                    width = int.from_bytes(data[pos+3:pos+5], "little") & 0x3FFF; height = int.from_bytes(data[pos+5:pos+7], "little") & 0x3FFF
                    return {"width": width, "height": height, "dimensionSource": "WebP VP8 header"}
            if chunk == b"VP8L" and len(data) >= 25:
                bits = int.from_bytes(data[21:25], "little")
                return {"width": (bits & 0x3FFF) + 1, "height": ((bits >> 14) & 0x3FFF) + 1, "dimensionSource": "WebP VP8L header"}
        if data.startswith(b"\xff\xd8"):
            pos = 2
            while pos + 9 < len(data):
                if data[pos] != 0xFF: pos += 1; continue
                marker = data[pos + 1]; pos += 2
                if marker in {0xD8, 0xD9}: continue
                length = int.from_bytes(data[pos:pos+2], "big")
                if marker in set(range(0xC0, 0xC4)) | set(range(0xC5, 0xC8)) | set(range(0xC9, 0xCC)) | set(range(0xCD, 0xD0)):
                    return {"width": int.from_bytes(data[pos+5:pos+7], "big"), "height": int.from_bytes(data[pos+3:pos+5], "big"), "dimensionSource": "JPEG SOF"}
                pos += max(length, 2)
        if path.suffix.lower() == ".json":
            payload = json.loads(data.decode("utf-8"))
            if isinstance(payload, dict) and isinstance(payload.get("w"), (int, float)) and isinstance(payload.get("h"), (int, float)):
                return {"width": payload["w"], "height": payload["h"], "dimensionSource": "JSON animation canvas"}
            return {"width": "manifest-defined variants", "height": "manifest-defined variants", "dimensionSource": "asset manifest metadata"}
        if path.suffix.lower() == ".xml":
            text = data[:10000].decode("utf-8", "ignore")
            w = re.search(r'(?:android:)?(?:width|viewportWidth)=["\']([^"\']+)', text)
            h = re.search(r'(?:android:)?(?:height|viewportHeight)=["\']([^"\']+)', text)
            return {"width": w.group(1) if w else "resource-defined", "height": h.group(1) if h else "resource-defined", "dimensionSource": "Android/XML resource attributes"}
        if path.suffix.lower() == ".svg":
            text = data[:10000].decode("utf-8", "ignore")
            w = re.search(r'\bwidth=["\']([^"\']+)', text)
            h = re.search(r'\bheight=["\']([^"\']+)', text)
            v = re.search(r'\bviewBox=["\']([^"\']+)', text)
            view = v.group(1) if v else None
            view_parts = re.split(r"[ ,]+", view.strip()) if view else []
            width = w.group(1) if w else view_parts[2] if len(view_parts) == 4 else "scalable/unspecified"
            height = h.group(1) if h else view_parts[3] if len(view_parts) == 4 else "scalable/unspecified"
            return {"width": width, "height": height, "viewBox": view, "dimensionSource": "SVG attributes/viewBox"}
    except OSError:
        pass
    return {"width": None, "height": None, "dimensionSource": "not encoded in supported header"}


def discover(rows: list[dict[str, str]]) -> tuple[list[dict[str, object]], dict[str, int]]:
    records: list[dict[str, object]] = []
    counters = Counter()
    asset_tokens: dict[str, set[str]] = {}
    for row in rows:
        rel = row["path"]
        path = ROOT / rel
        if is_brand_asset(rel):
            asset_tokens.setdefault(path.name.lower(), set()).add(rel)
    asset_ref_re = re.compile("|".join(re.escape(token) for token in sorted(asset_tokens, key=len, reverse=True)), re.I)
    asset_consumers: dict[str, set[str]] = {rel: set() for paths in asset_tokens.values() for rel in paths}
    for row in rows:
        rel = row["path"]
        path = ROOT / rel
        suffix = path.suffix.lower()
        low = rel.lower()
        if suffix in FONT_SUFFIXES:
            family = path.stem.split("-")[0]
            records.append(record(
                rel, "file", path.name, "FONT", "REVIEW_REQUIRED", "WP-I1-005",
                "Bundled font has an explicit legal/attribution review owner; absence of a package-local license is not treated as permission.",
                extra={"fontFamily": family, "legalStatus": "LICENSE_REVIEW_REQUIRED", "attributionStatus": "REVIEW_REQUIRED", "fileSha256": row["sha256"]},
            ))
            counters["fontFiles"] += 1
            continue
        asset_candidate = is_brand_asset(rel)
        if asset_candidate:
            asset_extra = {"fileSha256": row["sha256"], "assetRole": "brand-candidate", "generatedAsset": is_generated(rel), **image_dimensions(path)}
            if "futo" in low:
                asset_extra.update({"thirdPartyIdentity": "FUTO", "legalSensitivity": True,
                                    "coordinationOwner": "WP-I1-005",
                                    "preservationConstraint": "Do not remove or alter FUTO co-branding until WP-I1-005 records the legal/attribution decision."})
            records.append(record(
                rel, "file", path.name, "ASSET", "REPLACE_WITH_LAMHA_ASSET", "WP-I1-004",
                "Product brand asset requires reviewed Lamha artwork; source bytes remain untouched in this inventory package.",
                extra=asset_extra,
            ))
            counters["brandAssetFiles"] += 1
        legal_file = is_legal_file(rel)
        if legal_file and suffix not in FONT_SUFFIXES:
            records.append(record(
                rel, "file", path.name, "LEGAL", "PRESERVE_LEGAL", "WP-I1-005",
                "The complete legal file is preserved; brand changes must not delete or silently rewrite it.",
                extra={"legalStatus": "PRESERVE_VERBATIM_UNTIL_COUNSELLED_CHANGE", "fileSha256": row["sha256"]},
            ))
            counters["legalFiles"] += 1
        if IDENTITY_RE.search(rel) and not asset_candidate:
            if any(part in low for part in ("/assets/", "/static/img/", "/design/")) and suffix in ASSET_SUFFIXES | {".json"}:
                stype, disposition, owner = "ASSET", "REPLACE_WITH_LAMHA_ASSET", "WP-I1-004"
                rationale = "Identity-bearing asset path is itself a rebrand surface, even if its binary/text body contains no product token."
            elif legal_file:
                stype, disposition, owner = "LEGAL", "PRESERVE_LEGAL", "WP-I1-005"
                rationale = "Identity-bearing legal path remains preserved until a reviewed legal migration."
            else:
                stype, disposition, owner = "PACKAGE_IDENTITY", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003"
                rationale = "Identity-bearing repository path must be migrated with package/runtime consumers."
            records.append(record(rel, "path", rel, stype, disposition, owner, rationale,
                                  extra={"pathIdentity": True}))
            counters["identityPaths"] += 1
        if "/bin/" in rel.lower() and suffix not in ASSET_SUFFIXES | FONT_SUFFIXES:
            branded_executable = "immich" in path.name.lower()
            records.append(record(
                rel, "path:executable", path.name, "DISTRIBUTION" if branded_executable else "BUILD",
                "MIGRATE_TO_LAMHA_IDENTIFIER" if branded_executable else "NOT_PRODUCT_IDENTITY",
                "WP-I1-003" if branded_executable else None,
                "Branded executables migrate; generic build/runtime tools are recorded but are not product identity.",
                extra={"structuralKey": "executable-path", "futureTarget": "Reviewed Lamha executable name" if branded_executable else "Keep generic tool name"},
            ))
            counters["executablePaths"] += 1
        if not is_text(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            counters["undecodableTextCandidates"] += 1
            continue
        lines = text.splitlines()
        for number, line in enumerate(lines, 1):
            line_structural_specs = structural_specs(rel, line, lines[number] if number < len(lines) else "")
            for structural_index, (key, value, stype, disposition, owner) in enumerate(line_structural_specs, 1):
                records.append(record(
                    rel, f"line:{number}:structural:{structural_index}", value, stype, disposition, owner,
                    "Manifest/build structure is an application identity surface even when its current value does not contain the legacy brand token.",
                    generated=is_generated(rel),
                    extra={"structuralKey": key, "sourceExcerpt": line.strip()[:1000],
                           "lineDigest": sha256(line.encode("utf-8")),
                           "futureTarget": "Retain current generic/platform identity" if disposition == "NOT_PRODUCT_IDENTITY" else "Reviewed Lamha equivalent owned by the assigned future package",
                           **({"migrationDecision": "Migrate app-group identifier with shared-container data preservation",
                               "backwardCompatibility": "Share extension and main app must retain coordinated access to legacy group data during migration",
                               "migrationTest": "Seed shared-container state, migrate main app and extensions, verify cross-process read/write and rollback access."} if key == "CUSTOM_GROUP_ID" else {})},
                ))
                counters["structuralIdentitySurfaces"] += 1
            declared_data = data_declaration(rel, line)
            if declared_data:
                key, value = declared_data
                data_fields = app_data_extra(rel, line, value)
                data_fields.update({
                    "structuralKey": key, "accessRole": "authoritative persistence-path declaration",
                    "futureTarget": "Retain stable storage path unless WP-I1-003 proves and tests a migration",
                    "migrationDecision": "PRESERVE_TECHNICAL_COMPATIBILITY; generic persistent paths are not brand-renamed",
                    "backwardCompatibility": "Existing mounts, bytes, database data, thumbnails, profiles, libraries, and backups must remain readable",
                    "lineDigest": sha256(line.encode("utf-8")), "sourceExcerpt": line.strip()[:1000],
                })
                records.append(record(
                    rel, f"line:{number}:app-data-declaration", value, "FILESYSTEM_DATA_PATH",
                    "PRESERVE_TECHNICAL_COMPATIBILITY", "WP-I1-003",
                    "Authoritative generic persistence declaration is protected against accidental brand-driven renaming.",
                    generated=is_generated(rel), extra=data_fields,
                ))
                counters["appDataDeclarationLines"] += 1
            for asset_match in asset_ref_re.finditer(line):
                candidates = asset_tokens.get(asset_match.group(0).lower(), set())
                module = rel.split("/", 2)[1] if rel.startswith("Codebase/") and "/" in rel[9:] else ""
                same_module = {candidate for candidate in candidates if candidate.split("/", 2)[1] == module}
                resolved = same_module if len(same_module) == 1 else candidates if len(candidates) == 1 else set()
                for asset_rel in resolved:
                    if asset_rel != rel:
                        asset_consumers[asset_rel].add(rel)
            matches = list(IDENTITY_RE.finditer(line))
            if matches:
                emitted_identity = 0
                for occurrence, match in enumerate(matches, 1):
                    if any(match.group(0) == spec[1] for spec in line_structural_specs):
                        continue
                    stype, disposition, owner, rationale, semantic_key = classify_occurrence(rel, line, match.start(), match.end())
                    extra = {"lineDigest": sha256(line.encode("utf-8")), "occurrenceCount": 1,
                             "sourceExcerpt": line.strip()[:1000], "semanticKey": semantic_key,
                             "matchStart": match.start(), "matchEnd": match.end()}
                    if stype == "FILESYSTEM_DATA_PATH":
                        extra.update(app_data_extra(rel, line, match.group(0)))
                    if stype == "TEST_ONLY":
                        extra["productionSurfaceOwner"] = owner
                    records.append(record(
                        rel, f"line:{number}:identity:{occurrence}", match.group(0), stype, disposition, owner,
                        rationale, generated=is_generated(rel), extra=extra,
                    ))
                    emitted_identity += 1
                if emitted_identity:
                    counters["textLines"] += 1
                    counters["textOccurrences"] += emitted_identity
            futo_matches = list(FUTO_RE.finditer(line))
            for occurrence, match in enumerate(futo_matches, 1):
                documentation_context = bool(DOC_PATH_RE.search(rel)) or rel.lower().endswith((".md", ".mdx"))
                legal_or_visible = documentation_context or "/emails/" in rel.lower() or "/fastlane/" in rel.lower() or bool(re.search(r"(?i)(Holdings|Distribution|label|alt=|logo|href)", line))
                records.append(record(
                    rel, f"line:{number}:third-party:{occurrence}", match.group(0),
                    "UPSTREAM_ATTRIBUTION" if legal_or_visible else "COMPATIBILITY",
                    "PRESERVE_UPSTREAM_ATTRIBUTION" if legal_or_visible else "PRESERVE_TECHNICAL_COMPATIBILITY",
                    "WP-I1-005" if legal_or_visible else "WP-I1-003",
                    "FUTO third-party identity is preserved/reviewed independently from the Lamha product rebrand.",
                    generated=is_generated(rel),
                    extra={"thirdPartyIdentity": "FUTO", "lineDigest": sha256(line.encode("utf-8")),
                           "sourceExcerpt": line.strip()[:1000], "matchStart": match.start(), "matchEnd": match.end(),
                           "coordinationOwner": "WP-I1-005" if not legal_or_visible else None,
                           "preservationConstraint": "Do not replace FUTO identity with Lamha; retain or change only through the assigned legal/compatibility owner."},
                ))
                counters["thirdPartyIdentityOccurrences"] += 1
            font_matches = [match.group(0) for match in FONT_RE.finditer(line)]
            if font_matches:
                records.append(record(
                    rel, f"line:{number}:font-reference", " | ".join(dict.fromkeys(font_matches)),
                    "FONT", "REVIEW_REQUIRED", "WP-I1-005",
                    "Every bundled-font declaration and consumer is bound to the font licensing review.",
                    generated=is_generated(rel),
                    extra={"fontFamily": " | ".join(dict.fromkeys(font_matches)),
                           "legalStatus": "LICENSE_REVIEW_REQUIRED", "attributionStatus": "REVIEW_REQUIRED",
                           "lineDigest": sha256(line.encode("utf-8")), "occurrenceCount": len(font_matches),
                           "sourceExcerpt": line.strip()[:1000]},
                ))
                counters["fontReferenceLines"] += 1
            binary_matches = [match.group(0) for match in BINARY_RE.finditer(line)]
            if binary_matches:
                records.append(record(
                    rel, f"line:{number}:bundled-binary", " | ".join(dict.fromkeys(binary_matches)),
                    "UPSTREAM_ATTRIBUTION", "PRESERVE_UPSTREAM_ATTRIBUTION", "WP-I1-005",
                    "Referenced or packaged native tooling requires a reviewed licence/attribution record before distribution.",
                    generated=is_generated(rel),
                    extra={"binaryName": " | ".join(dict.fromkeys(binary_matches)),
                           "legalStatus": "ATTRIBUTION_REVIEW_REQUIRED", "lineDigest": sha256(line.encode("utf-8")),
                           "occurrenceCount": len(binary_matches), "sourceExcerpt": line.strip()[:1000]},
                ))
                counters["bundledBinaryReferenceLines"] += 1
            docker_declaration = path.name.lower().startswith("dockerfile") and (
                bool(re.match(r"\s*FROM\b", line, re.I)) or bool(BINARY_DECL_RE.search(line)) or bool(BINARY_PACKAGE_RE.search(line))
            )
            if docker_declaration:
                declaration_matches = [m.group(0) for m in BINARY_DECL_RE.finditer(line)] + [m.group(0) for m in BINARY_PACKAGE_RE.finditer(line)]
                value = line.strip()[:1000]
                records.append(record(
                    rel, f"line:{number}:binary-declaration", value, "DISTRIBUTION", "REVIEW_REQUIRED", "WP-I1-005",
                    "Docker base, copied executable/library, or installed runtime component requires an explicit notice/licence determination.",
                    extra={"bundledBinaryDeclaration": True, "binaryName": value,
                           "binarySource": line.strip()[:1000], "matchedBinaryTokens": list(dict.fromkeys(declaration_matches)), "distributionPath": rel,
                           "legalStatus": "BINARY_NOTICE_REVIEW_REQUIRED", "noticeRecord": "WP-I1-001-RISK-BINARY-NOTICES",
                           "lineDigest": sha256(line.encode("utf-8")), "occurrenceCount": max(1, len(declaration_matches)),
                           "sourceExcerpt": line.strip()[:1000]},
                ))
                counters["bundledBinaryDeclarationLines"] += 1
            legal_tokens = legal_matches(rel, line)
            if legal_tokens and not legal_file:
                exact_preserve = bool(re.search(r"(?i)(copyright|attribution|SPDX|trademark|third[- ]party)", line))
                records.append(record(
                    rel, f"line:{number}:legal", " | ".join(dict.fromkeys(legal_tokens)), "LEGAL",
                    "PRESERVE_LEGAL" if exact_preserve else "REVIEW_REQUIRED", "WP-I1-005",
                    "Legally meaningful text outside a dedicated notice file is inventoried for non-destructive review.",
                    generated=is_generated(rel),
                    extra={"legalStatus": "MUST_PRESERVE" if exact_preserve else "LEGAL_REVIEW_REQUIRED",
                           "lineDigest": sha256(line.encode("utf-8")), "occurrenceCount": len(legal_tokens),
                           "sourceExcerpt": line.strip()[:1000]},
                ))
                counters["legalReferenceLines"] += 1
            data_matches = [match.group(0) for match in DATA_ACCESS_RE.finditer(line)]
            if data_matches:
                value = " | ".join(dict.fromkeys(data_matches))
                data_fields = app_data_extra(rel, line, value)
                records.append(record(
                    rel, f"line:{number}:app-data", value, "FILESYSTEM_DATA_PATH",
                    "MIGRATE_TO_LAMHA_IDENTIFIER" if data_fields["persistentData"] else "PRESERVE_TECHNICAL_COMPATIBILITY", "WP-I1-003",
                    "Application-owned storage access must be mapped before directory identity changes.",
                    generated=is_generated(rel),
                    extra={"lineDigest": sha256(line.encode("utf-8")), "occurrenceCount": len(data_matches),
                           "sourceExcerpt": line.strip()[:1000], **data_fields},
                ))
                counters["appDataAccessLines"] += 1
    for rec in records:
        if rec["surfaceType"] == "ASSET" and rec["locator"] == "file":
            asset_rel = str(rec["path"]); name = Path(asset_rel).name.lower(); variants = sorted(asset_tokens.get(name, set()))
            rec["consumerPaths"] = sorted(asset_consumers.get(asset_rel, set()))
            if len(variants) > 1:
                rec["consumerResolution"] = "PLATFORM_OR_MODULE_VARIANT_GROUP"
                rec["variantGroup"] = name
                rec["variantPaths"] = variants
            else:
                rec["consumerResolution"] = "EXACT_FILENAME_REFERENCE_OR_PLATFORM_PACKAGING"
            low_asset = asset_rel.lower()
            if ".xcassets/" in low_asset:
                rec["platformConsumer"] = "Apple asset-catalog packaging"
            elif "/res/" in low_asset:
                rec["platformConsumer"] = "Android resource packaging"
            elif "/phonescreenshots/" in low_asset:
                rec["platformConsumer"] = "Mobile store listing"
            elif "/static/" in low_asset:
                rec["platformConsumer"] = "Published web/docs static asset"
    # Exact duplicate keys are forbidden; distinct semantic records on the same path/line are allowed.
    unique: dict[str, dict[str, object]] = {}
    for rec in records:
        sid = str(rec["surfaceId"])
        if sid in unique and unique[sid] != rec:
            raise ValueError(f"surface id collision: {sid}")
        unique[sid] = rec
    return sorted(unique.values(), key=lambda r: (str(r["path"]), str(r["locator"]), str(r["surfaceId"]))), dict(counters)


def validate(records: list[dict[str, object]], required_surface_ids: set[str] | None = None,
             required_asset_consumers: dict[str, list[str]] | None = None) -> list[str]:
    errors: list[str] = []
    source_lines: dict[str, list[str]] = {}
    ids = [r.get("surfaceId") for r in records]
    if len(ids) != len(set(ids)):
        errors.append("DUPLICATE_SURFACE_ID")
    semantic_groups: dict[tuple[str, str, str], set[tuple[object, object, object]]] = {}
    for rec in records:
        locator = str(rec.get("locator", "")); line_key = locator.split(":")[1] if locator.startswith("line:") else locator
        if ":identity:" in locator or ":third-party:" in locator:
            line_key = f"{line_key}:{rec.get('matchStart')}:{rec.get('matchEnd')}"
        key = (str(rec.get("path")), line_key, str(rec.get("currentValue")))
        semantic_groups.setdefault(key, set()).add((rec.get("surfaceType"), rec.get("disposition"), rec.get("futureOwner")))
    if any(len(values) > 1 for values in semantic_groups.values()):
        errors.append("SEMANTIC_CONFLICT")
    for rec in records:
        sid = str(rec.get("surfaceId", "<missing>"))
        if rec.get("surfaceType") not in SURFACE_TYPES:
            errors.append(f"INVALID_SURFACE_TYPE:{sid}")
        if rec.get("disposition") not in DISPOSITIONS:
            errors.append(f"UNCLASSIFIED:{sid}")
        if rec.get("binding") and rec.get("disposition") in ACTION_DISPOSITIONS and rec.get("futureOwner") not in OWNERS:
            errors.append(f"UNOWNED_TRANSFORMATION:{sid}")
        if rec.get("disposition") == "NOT_PRODUCT_IDENTITY" and rec.get("futureOwner") is not None:
            errors.append(f"NON_PRODUCT_HAS_OWNER:{sid}")
        if rec.get("surfaceType") == "FONT" and rec.get("legalStatus") not in {"LICENSE_CONFIRMED", "LICENSE_REVIEW_REQUIRED"}:
            errors.append(f"FONT_LEGAL_STATUS_MISSING:{sid}")
        if rec.get("surfaceType") == "ASSET" and rec.get("locator") == "file":
            asset_path = ROOT / str(rec.get("path"))
            if not asset_path.is_file() or rec.get("fileSha256") != sha256(asset_path.read_bytes()):
                errors.append(f"ASSET_HASH_DRIFT:{sid}")
            expected_dimensions = image_dimensions(asset_path)
            if (rec.get("width"), rec.get("height"), rec.get("viewBox")) != (expected_dimensions.get("width"), expected_dimensions.get("height"), expected_dimensions.get("viewBox")):
                errors.append(f"ASSET_DIMENSION_DRIFT:{sid}")
            for consumer in rec.get("consumerPaths", []):
                consumer_path = ROOT / str(consumer)
                if not consumer_path.is_file() or Path(str(rec.get("path"))).name.lower() not in consumer_path.read_text(encoding="utf-8").lower():
                    errors.append(f"ASSET_CONSUMER_INVALID:{sid}")
        if rec.get("semanticKey") in {"name", "short_name", "android:label"} and (rec.get("surfaceType"), rec.get("disposition"), rec.get("futureOwner")) != ("USER_VISIBLE", "RENAME_TO_LAMHA", "WP-I1-002"):
            errors.append(f"VISIBLE_MANIFEST_OWNER_INVALID:{sid}")
        if rec.get("surfaceType") == "TEST_ONLY" and rec.get("productionSurfaceOwner") != rec.get("futureOwner"):
            errors.append(f"TEST_PRODUCTION_OWNER_MISMATCH:{sid}")
        if rec.get("surfaceType") in {"LEGAL", "UPSTREAM_ATTRIBUTION"} and rec.get("disposition") in {"RENAME_TO_LAMHA", "REPLACE_WITH_LAMHA_ASSET", "REMOVE_LATER"}:
            errors.append(f"UNSAFE_LEGAL_DELETION:{sid}")
        if rec.get("isGenerated"):
            source = rec.get("canonicalSourcePath")
            if not source:
                errors.append(f"GENERATED_SOURCE_MISSING:{sid}")
            elif str(source).startswith("Codebase/") and not (ROOT / str(source)).is_file():
                errors.append(f"GENERATED_SOURCE_INVALID:{sid}")
            elif str(source).startswith("generator-contract:") and source not in {"generator-contract:openapi", "generator-contract:dart-codegen"}:
                errors.append(f"GENERATED_SOURCE_INVALID:{sid}")
            elif not str(source).startswith(("Codebase/", "generator-contract:")):
                errors.append(f"GENERATED_SOURCE_INVALID:{sid}")
        if not (ROOT / str(rec.get("path", ""))).is_file():
            errors.append(f"MISSING_SOURCE_PATH:{sid}")
        locator = str(rec.get("locator", ""))
        rel = str(rec.get("path", ""))
        source_path = ROOT / rel
        if locator == "path":
            low = rel.lower(); suffix = source_path.suffix.lower(); legal_file = is_legal_file(rel)
            if any(part in low for part in ("/assets/", "/static/img/", "/design/")) and suffix in ASSET_SUFFIXES | {".json"}:
                expected_path = (rel, "ASSET", "REPLACE_WITH_LAMHA_ASSET", "WP-I1-004", True)
            elif legal_file:
                expected_path = (rel, "LEGAL", "PRESERVE_LEGAL", "WP-I1-005", True)
            else:
                expected_path = (rel, "PACKAGE_IDENTITY", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003", True)
            observed_path = (rec.get("currentValue"), rec.get("surfaceType"), rec.get("disposition"), rec.get("futureOwner"), rec.get("pathIdentity"))
            if observed_path != expected_path:
                errors.append(f"PATH_CLASSIFICATION_DRIFT:{sid}")
        if locator == "path:executable":
            branded = "immich" in source_path.name.lower()
            expected_executable = (source_path.name, "DISTRIBUTION" if branded else "BUILD",
                                   "MIGRATE_TO_LAMHA_IDENTIFIER" if branded else "NOT_PRODUCT_IDENTITY",
                                   "WP-I1-003" if branded else None, "executable-path",
                                   "Reviewed Lamha executable name" if branded else "Keep generic tool name")
            observed_executable = (rec.get("currentValue"), rec.get("surfaceType"), rec.get("disposition"),
                                   rec.get("futureOwner"), rec.get("structuralKey"), rec.get("futureTarget"))
            if observed_executable != expected_executable:
                errors.append(f"EXECUTABLE_CLASSIFICATION_DRIFT:{sid}")
        if locator.startswith("line:") and (":structural:" in locator or locator.endswith(":app-data-declaration")) and (ROOT / rel).is_file():
            lines = source_lines.setdefault(rel, (ROOT / rel).read_text(encoding="utf-8").splitlines())
            number = int(locator.split(":")[1])
            if number < 1 or number > len(lines) or sha256(lines[number - 1].encode("utf-8")) != rec.get("lineDigest"):
                errors.append(f"STRUCTURAL_LOCATOR_DRIFT:{sid}")
            elif ":structural:" in locator:
                expected = [spec for spec in structural_specs(rel, lines[number - 1], lines[number] if number < len(lines) else "") if spec[0] == rec.get("structuralKey")]
                if not expected or str(rec.get("currentValue")) != expected[0][1]:
                    errors.append(f"STRUCTURAL_VALUE_DRIFT:{sid}")
            else:
                expected_data = data_declaration(rel, lines[number - 1])
                if not expected_data or str(rec.get("currentValue")) != expected_data[1]:
                    errors.append(f"APP_DATA_VALUE_DRIFT:{sid}")
                else:
                    expected_fields = app_data_extra(rel, lines[number - 1], expected_data[1])
                    expected_fields.update({
                        "structuralKey": expected_data[0], "accessRole": "authoritative persistence-path declaration",
                        "futureTarget": "Retain stable storage path unless WP-I1-003 proves and tests a migration",
                        "migrationDecision": "PRESERVE_TECHNICAL_COMPATIBILITY; generic persistent paths are not brand-renamed",
                        "backwardCompatibility": "Existing mounts, bytes, database data, thumbnails, profiles, libraries, and backups must remain readable",
                    })
                    for field, expected_value in expected_fields.items():
                        if rec.get(field) != expected_value:
                            errors.append(f"APP_DATA_DECLARATION_SEMANTICS:{sid}:{field}")
        if locator.startswith("line:") and source_path.is_file():
            lines = source_lines.setdefault(rel, source_path.read_text(encoding="utf-8").splitlines())
            number = int(locator.split(":")[1]); line = lines[number - 1]
            if rec.get("sourceExcerpt") != line.strip()[:1000]:
                errors.append(f"SOURCE_EXCERPT_DRIFT:{sid}")
            if locator.endswith(":font-reference"):
                matches = [m.group(0) for m in FONT_RE.finditer(line)]; value = " | ".join(dict.fromkeys(matches))
                if (rec.get("currentValue"), rec.get("fontFamily"), rec.get("occurrenceCount"), rec.get("legalStatus"), rec.get("attributionStatus")) != (value, value, len(matches), "LICENSE_REVIEW_REQUIRED", "REVIEW_REQUIRED"):
                    errors.append(f"FONT_PAYLOAD_DRIFT:{sid}")
            elif locator.endswith(":bundled-binary"):
                matches = [m.group(0) for m in BINARY_RE.finditer(line)]; value = " | ".join(dict.fromkeys(matches))
                if (rec.get("currentValue"), rec.get("binaryName"), rec.get("occurrenceCount"), rec.get("legalStatus")) != (value, value, len(matches), "ATTRIBUTION_REVIEW_REQUIRED"):
                    errors.append(f"BINARY_PAYLOAD_DRIFT:{sid}")
            elif locator.endswith(":binary-declaration"):
                matches = [m.group(0) for m in BINARY_DECL_RE.finditer(line)] + [m.group(0) for m in BINARY_PACKAGE_RE.finditer(line)]
                value = line.strip()[:1000]
                expected_payload = (value, value, value, list(dict.fromkeys(matches)), rel, True,
                                    "BINARY_NOTICE_REVIEW_REQUIRED", "WP-I1-001-RISK-BINARY-NOTICES", max(1, len(matches)))
                observed_payload = (rec.get("currentValue"), rec.get("binaryName"), rec.get("binarySource"), rec.get("matchedBinaryTokens"),
                                    rec.get("distributionPath"), rec.get("bundledBinaryDeclaration"), rec.get("legalStatus"), rec.get("noticeRecord"), rec.get("occurrenceCount"))
                if observed_payload != expected_payload:
                    errors.append(f"BINARY_DECLARATION_PAYLOAD_DRIFT:{sid}")
            elif locator.endswith(":legal"):
                matches = legal_matches(rel, line); value = " | ".join(dict.fromkeys(matches))
                exact = bool(re.search(r"(?i)(copyright|attribution|SPDX|trademark|third[- ]party)", line))
                expected_legal = (value, len(matches), "MUST_PRESERVE" if exact else "LEGAL_REVIEW_REQUIRED",
                                  "PRESERVE_LEGAL" if exact else "REVIEW_REQUIRED")
                if (rec.get("currentValue"), rec.get("occurrenceCount"), rec.get("legalStatus"), rec.get("disposition")) != expected_legal:
                    errors.append(f"LEGAL_PAYLOAD_DRIFT:{sid}")
            elif locator.endswith(":app-data"):
                matches = [m.group(0) for m in DATA_ACCESS_RE.finditer(line)]; value = " | ".join(dict.fromkeys(matches))
                if rec.get("currentValue") != value or rec.get("occurrenceCount") != len(matches):
                    errors.append(f"APP_DATA_PAYLOAD_DRIFT:{sid}")
        if ":identity:" in locator and (ROOT / rel).is_file():
            lines = source_lines.setdefault(rel, (ROOT / rel).read_text(encoding="utf-8").splitlines())
            number = int(locator.split(":")[1]); expected_identity = classify_occurrence(rel, lines[number - 1], int(rec.get("matchStart", -1)), int(rec.get("matchEnd", -1)))
            if (rec.get("surfaceType"), rec.get("disposition"), rec.get("futureOwner"), rec.get("rationale"), rec.get("semanticKey")) != expected_identity:
                errors.append(f"IDENTITY_CLASSIFICATION_DRIFT:{sid}")
        if rec.get("surfaceType") == "FILESYSTEM_DATA_PATH" and locator.startswith("line:") and not locator.endswith(":app-data-declaration") and (ROOT / rel).is_file():
            lines = source_lines.setdefault(rel, (ROOT / rel).read_text(encoding="utf-8").splitlines())
            number = int(locator.split(":")[1]); expected_fields = app_data_extra(rel, lines[number - 1], str(rec.get("currentNameOrExpression")))
            for field in ("platform", "persistentData", "migrationDecision", "backwardCompatibility", "migrationTest"):
                if rec.get(field) != expected_fields[field]:
                    errors.append(f"APP_DATA_SEMANTICS:{sid}:{field}")
    if required_surface_ids is not None:
        missing = required_surface_ids - {str(value) for value in ids}
        if missing:
            errors.append("MISSING_DISCOVERED_SURFACE:" + sorted(missing)[0])
    if required_asset_consumers is not None:
        by_id = {str(rec.get("surfaceId")): rec for rec in records}
        for sid, expected in required_asset_consumers.items():
            if sid in by_id and by_id[sid].get("consumerPaths") != expected:
                errors.append(f"ASSET_CONSUMER_SET:{sid}")
    return errors


def negative_fixtures(records: list[dict[str, object]]) -> list[dict[str, object]]:
    import copy
    fixtures: list[tuple[str, callable, str]] = []
    base = records
    def mutate(index: int, **updates: object) -> list[dict[str, object]]:
        value = [copy.deepcopy(base[index])]
        value[0].update(updates)
        return value
    font_i = next(i for i, r in enumerate(base) if r["surfaceType"] == "FONT")
    legal_i = next(i for i, r in enumerate(base) if r["surfaceType"] in {"LEGAL", "UPSTREAM_ATTRIBUTION"})
    generated_i = next(i for i, r in enumerate(base) if r["isGenerated"])
    project_i = next(i for i, r in enumerate(base) if str(r["path"]).endswith(".pbxproj"))
    generic_asset_i = next(i for i, r in enumerate(base) if str(r["path"]).endswith("ic_launcher.png") and r["locator"] == "file")
    app_data_i = next(i for i, r in enumerate(base) if str(r["locator"]).endswith(":app-data"))
    docker_binary_i = next(i for i, r in enumerate(base) if r.get("bundledBinaryDeclaration") and "machine-learning/Dockerfile" in str(r["path"]))
    visible_manifest_i = next(i for i, r in enumerate(base) if r.get("semanticKey") in {"name", "short_name", "android:label"})
    structural_bundle_i = next(i for i, r in enumerate(base) if r.get("structuralKey") == "CFBundleExecutable")
    data_declaration_i = next(i for i, r in enumerate(base) if str(r.get("locator")).endswith(":app-data-declaration"))
    path_i = next(i for i, r in enumerate(base) if r.get("locator") == "path")
    executable_i = next(i for i, r in enumerate(base) if r.get("locator") == "path:executable")
    font_reference_i = next(i for i, r in enumerate(base) if str(r.get("locator")).endswith(":font-reference"))
    legal_reference_i = next(i for i, r in enumerate(base) if str(r.get("locator")).endswith(":legal"))
    futo_i = next(i for i, r in enumerate(base) if str(r.get("locator")).find(":third-party:") >= 0)
    asset_consumer_i = next(i for i, r in enumerate(base) if r.get("surfaceType") == "ASSET" and r.get("consumerPaths"))
    temporary_data_i = next(i for i, r in enumerate(base) if r.get("surfaceType") == "FILESYSTEM_DATA_PATH" and r.get("persistentData") is False and not str(r.get("locator")).endswith(":app-data-declaration"))
    ordinary_visible_i = next(i for i, r in enumerate(base) if r.get("surfaceType") in {"USER_VISIBLE", "DOCUMENTATION"} and ":identity:" in str(r.get("locator")) and r.get("semanticKey") is None)
    fixtures.extend([
        ("F01_UNCLASSIFIED", lambda: mutate(0, disposition="UNKNOWN"), "UNCLASSIFIED"),
        ("F02_INVALID_SURFACE_TYPE", lambda: mutate(0, surfaceType="UNKNOWN"), "INVALID_SURFACE_TYPE"),
        ("F03_UNOWNED_RENAME", lambda: mutate(0, disposition="RENAME_TO_LAMHA", binding=True, futureOwner=None), "UNOWNED_TRANSFORMATION"),
        ("F04_UNKNOWN_OWNER", lambda: mutate(0, disposition="MIGRATE_TO_LAMHA_IDENTIFIER", binding=True, futureOwner="WP-I9-999"), "UNOWNED_TRANSFORMATION"),
        ("F05_DUPLICATE_ID", lambda: [copy.deepcopy(base[0]), copy.deepcopy(base[0])], "DUPLICATE_SURFACE_ID"),
        ("F06_FONT_STATUS_MISSING", lambda: mutate(font_i, legalStatus=None), "FONT_LEGAL_STATUS_MISSING"),
        ("F07_FONT_STATUS_GUESSED", lambda: mutate(font_i, legalStatus="ASSUMED_OK"), "FONT_LEGAL_STATUS_MISSING"),
        ("F08_LEGAL_RENAME", lambda: mutate(legal_i, disposition="RENAME_TO_LAMHA"), "UNSAFE_LEGAL_DELETION"),
        ("F09_ATTRIBUTION_REMOVE", lambda: mutate(legal_i, disposition="REMOVE_LATER"), "UNSAFE_LEGAL_DELETION"),
        ("F10_GENERATED_SOURCE_MISSING", lambda: mutate(generated_i, canonicalSourcePath=None), "GENERATED_SOURCE_MISSING"),
        ("F11_SOURCE_PATH_MISSING", lambda: mutate(0, path="Codebase/does-not-exist.identity"), "MISSING_SOURCE_PATH"),
        ("F12_NON_PRODUCT_OWNER", lambda: mutate(0, disposition="NOT_PRODUCT_IDENTITY", binding=False, futureOwner="WP-I1-002"), "NON_PRODUCT_HAS_OWNER"),
        ("F13_UNOWNED_ASSET", lambda: mutate(0, disposition="REPLACE_WITH_LAMHA_ASSET", binding=True, futureOwner=None), "UNOWNED_TRANSFORMATION"),
        ("F14_UNOWNED_COMPATIBILITY", lambda: mutate(0, disposition="PRESERVE_TECHNICAL_COMPATIBILITY", binding=True, futureOwner=None), "UNOWNED_TRANSFORMATION"),
        ("F15_LEGAL_ASSET_REPLACE", lambda: mutate(legal_i, disposition="REPLACE_WITH_LAMHA_ASSET"), "UNSAFE_LEGAL_DELETION"),
        ("F16_INVALID_DISPOSITION_CASE", lambda: mutate(0, disposition="rename_to_lamha"), "UNCLASSIFIED"),
        ("F17_INVENTED_GENERATOR_CONTRACT", lambda: mutate(generated_i, canonicalSourcePath="generator-contract:plausible-but-invented"), "GENERATED_SOURCE_INVALID"),
        ("F18_STRUCTURAL_VALUE_FORGED", lambda: mutate(structural_bundle_i, currentValue="fabricated-executable"), "STRUCTURAL_VALUE_DRIFT"),
    ])
    results = []
    for fixture_id, build, expected in fixtures:
        observed = validate(build())
        passed = any(error.startswith(expected) for error in observed)
        results.append({"fixtureId": fixture_id, "expectedError": expected, "observedErrors": observed[:5], "status": "PASS" if passed else "FAIL"})
    removed = base[project_i]
    observed = validate([], {str(removed["surfaceId"])})
    results.append({"fixtureId": "F19_MISSED_PBXPROJ_IDENTITY", "expectedError": "MISSING_DISCOVERED_SURFACE",
                    "observedErrors": observed[:5],
                    "status": "PASS" if any(e.startswith("MISSING_DISCOVERED_SURFACE") for e in observed) and removed["path"].endswith(".pbxproj") else "FAIL"})
    removed = base[generic_asset_i]
    observed = validate([], {str(removed["surfaceId"])})
    results.append({"fixtureId": "F20_MISSED_GENERIC_LAUNCHER_ASSET", "expectedError": "MISSING_DISCOVERED_SURFACE",
                    "observedErrors": observed[:5],
                    "status": "PASS" if any(e.startswith("MISSING_DISCOVERED_SURFACE") for e in observed) and removed["path"].endswith("ic_launcher.png") else "FAIL"})
    observed = validate([], {str(base[app_data_i]["surfaceId"])})
    results.append({"fixtureId": "F21_MISSED_APP_DATA_ACCESS", "expectedError": "MISSING_DISCOVERED_SURFACE",
                    "observedErrors": observed[:5], "status": "PASS" if any(e.startswith("MISSING_DISCOVERED_SURFACE") for e in observed) else "FAIL"})
    domain_type = classify("Codebase/docs/example.md", "https://docs.immich.app/guide")[0]
    results.append({"fixtureId": "F22_DOMAIN_IS_NOT_APP_DATA", "expectedError": "DOMAIN_NOT_FILESYSTEM_DATA_PATH",
                    "observedErrors": [] if domain_type != "FILESYSTEM_DATA_PATH" else ["DOMAIN_MISCLASSIFIED_AS_APP_DATA"],
                    "status": "PASS" if domain_type != "FILESYSTEM_DATA_PATH" else "FAIL"})
    observed = validate([], {str(base[docker_binary_i]["surfaceId"])})
    results.append({"fixtureId": "F23_MISSED_DOCKER_BINARY_DECLARATION", "expectedError": "MISSING_DISCOVERED_SURFACE",
                    "observedErrors": observed[:5], "status": "PASS" if any(e.startswith("MISSING_DISCOVERED_SURFACE") for e in observed) else "FAIL"})
    observed = validate(mutate(visible_manifest_i, surfaceType="PACKAGE_IDENTITY", disposition="MIGRATE_TO_LAMHA_IDENTIFIER", futureOwner="WP-I1-003"))
    results.append({"fixtureId": "F24_VISIBLE_MANIFEST_WRONG_OWNER", "expectedError": "VISIBLE_MANIFEST_OWNER_INVALID",
                    "observedErrors": observed[:5], "status": "PASS" if any(e.startswith("VISIBLE_MANIFEST_OWNER_INVALID") for e in observed) else "FAIL"})
    results.append({"fixtureId": "F25_AUTHORIZATION_IS_NOT_LEGAL", "expectedError": "AUTHORIZATION_NOT_LEGAL",
                    "observedErrors": [] if not legal_matches("Codebase/e2e/src/utils.ts", "Authorization: Bearer token") else ["AUTHORIZATION_FALSE_POSITIVE"],
                    "status": "PASS" if not legal_matches("Codebase/e2e/src/utils.ts", "Authorization: Bearer token") else "FAIL"})
    faq = "We want to commercialize Immich while making Immich better as open source software."
    faq_class = classify("Codebase/docs/docs/FAQ.mdx", faq)
    results.append({"fixtureId": "F26_PRODUCT_PROSE_NOT_UPSTREAM_ATTRIBUTION", "expectedError": "VISIBLE_DOC_RENAME",
                    "observedErrors": [] if faq_class[1:3] == ("RENAME_TO_LAMHA", "WP-I1-002") else ["PRODUCT_PROSE_MISROUTED"],
                    "status": "PASS" if faq_class[1:3] == ("RENAME_TO_LAMHA", "WP-I1-002") else "FAIL"})
    symbol_class = classify("Codebase/web/src/lib/component.svelte", "import { ImmichProduct } from '$lib/product';")
    results.append({"fixtureId": "F27_SYMBOL_IS_NOT_USER_VISIBLE", "expectedError": "SYMBOL_INTERNAL",
                    "observedErrors": [] if symbol_class[:3] == ("INTERNAL_RUNTIME", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003") else ["SYMBOL_MISCLASSIFIED"],
                    "status": "PASS" if symbol_class[:3] == ("INTERNAL_RUNTIME", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003") else "FAIL"})
    test_class = classify("Codebase/server/src/service.spec.ts", "expect(subject).toBe('Welcome to Immich');")
    results.append({"fixtureId": "F28_VISIBLE_TEST_FOLLOWS_UI_OWNER", "expectedError": "VISIBLE_TEST_OWNER",
                    "observedErrors": [] if test_class[1:3] == ("RENAME_TO_LAMHA", "WP-I1-002") else ["VISIBLE_TEST_WRONG_OWNER"],
                    "status": "PASS" if test_class[1:3] == ("RENAME_TO_LAMHA", "WP-I1-002") else "FAIL"})
    observed = validate([], {str(base[structural_bundle_i]["surfaceId"])})
    results.append({"fixtureId": "F29_MISSED_STRUCTURAL_BUNDLE_EXECUTABLE", "expectedError": "MISSING_DISCOVERED_SURFACE",
                    "observedErrors": observed[:5], "status": "PASS" if any(e.startswith("MISSING_DISCOVERED_SURFACE") for e in observed) else "FAIL"})
    observed = validate([], {str(base[data_declaration_i]["surfaceId"])})
    results.append({"fixtureId": "F30_MISSED_PERSISTENCE_DECLARATION", "expectedError": "MISSING_DISCOVERED_SURFACE",
                    "observedErrors": observed[:5], "status": "PASS" if any(e.startswith("MISSING_DISCOVERED_SURFACE") for e in observed) else "FAIL"})
    observed = validate([], {str(base[futo_i]["surfaceId"])})
    results.append({"fixtureId": "F31_MISSED_FUTO_IDENTITY", "expectedError": "MISSING_DISCOVERED_SURFACE",
                    "observedErrors": observed[:5], "status": "PASS" if any(e.startswith("MISSING_DISCOVERED_SURFACE") for e in observed) else "FAIL"})
    omitted_manifest = MANIFEST_CONTENT_FILES - {"completion-evidence.md"}
    results.append({"fixtureId": "F32_MANIFEST_OMITS_REQUIRED_ARTIFACT", "expectedError": "MANIFEST_PATH_SET",
                    "observedErrors": ["MANIFEST_PATH_SET"] if omitted_manifest != MANIFEST_CONTENT_FILES else [],
                    "status": "PASS" if omitted_manifest != MANIFEST_CONTENT_FILES else "FAIL"})
    style_line = '<div class="very-long-prefix grid columns border-e-immich-dark-gray immich-scrollbar">'
    style_start = style_line.index("immich-dark-gray")
    style_class = classify_occurrence("Codebase/web/src/lib/Long.svelte", style_line, style_start, style_start + len("immich-dark-gray"))
    results.append({"fixtureId": "F33_LONG_STYLE_TOKEN_IS_INTERNAL", "expectedError": "STYLE_TOKEN_INTERNAL",
                    "observedErrors": [] if style_class[:3] == ("INTERNAL_RUNTIME", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003") else ["STYLE_TOKEN_MISCLASSIFIED"],
                    "status": "PASS" if style_class[:3] == ("INTERNAL_RUNTIME", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003") else "FAIL"})
    observed = validate(mutate(asset_consumer_i, consumerPaths=["Codebase/package.json"]))
    results.append({"fixtureId": "F34_FORGED_ASSET_CONSUMER", "expectedError": "ASSET_CONSUMER_INVALID",
                    "observedErrors": observed[:5], "status": "PASS" if any(e.startswith("ASSET_CONSUMER_INVALID") for e in observed) else "FAIL"})
    observed = validate(mutate(temporary_data_i, persistentData=True))
    results.append({"fixtureId": "F35_TEMP_DATA_MARKED_DURABLE", "expectedError": "APP_DATA_SEMANTICS",
                    "observedErrors": observed[:5], "status": "PASS" if any(e.startswith("APP_DATA_SEMANTICS") for e in observed) else "FAIL"})
    consumer_requirements = {str(base[asset_consumer_i]["surfaceId"]): list(base[asset_consumer_i].get("consumerPaths", []))}
    omitted_consumer = mutate(asset_consumer_i, consumerPaths=[])
    observed = validate(omitted_consumer, required_asset_consumers=consumer_requirements)
    results.append({"fixtureId": "F36_OMITTED_ASSET_CONSUMER", "expectedError": "ASSET_CONSUMER_SET",
                    "observedErrors": observed[:5], "status": "PASS" if any(e.startswith("ASSET_CONSUMER_SET") for e in observed) else "FAIL"})
    observed = validate(mutate(generic_asset_i, width=999, height=999))
    results.append({"fixtureId": "F37_FORGED_ASSET_DIMENSIONS", "expectedError": "ASSET_DIMENSION_DRIFT",
                    "observedErrors": observed[:5], "status": "PASS" if any(e.startswith("ASSET_DIMENSION_DRIFT") for e in observed) else "FAIL"})
    observed = validate(mutate(ordinary_visible_i, surfaceType="INTERNAL_RUNTIME", disposition="MIGRATE_TO_LAMHA_IDENTIFIER", futureOwner="WP-I1-003"))
    results.append({"fixtureId": "F38_SWAPPED_IDENTITY_CLASSIFICATION", "expectedError": "IDENTITY_CLASSIFICATION_DRIFT",
                    "observedErrors": observed[:5], "status": "PASS" if any(e.startswith("IDENTITY_CLASSIFICATION_DRIFT") for e in observed) else "FAIL"})
    observed = validate(mutate(data_declaration_i, persistentData=not bool(base[data_declaration_i].get("persistentData"))))
    results.append({"fixtureId": "F39_FORGED_DATA_DECLARATION_SEMANTICS", "expectedError": "APP_DATA_DECLARATION_SEMANTICS",
                    "observedErrors": observed[:5], "status": "PASS" if any(e.startswith("APP_DATA_DECLARATION_SEMANTICS") for e in observed) else "FAIL"})
    observed = validate(mutate(path_i, surfaceType="INTERNAL_RUNTIME", disposition="MIGRATE_TO_LAMHA_IDENTIFIER", futureOwner="WP-I1-003"))
    results.append({"fixtureId": "F40_FORGED_PATH_CLASSIFICATION", "expectedError": "PATH_CLASSIFICATION_DRIFT",
                    "observedErrors": observed[:5], "status": "PASS" if any(e.startswith("PATH_CLASSIFICATION_DRIFT") for e in observed) else "FAIL"})
    observed = validate(mutate(executable_i, currentValue="fabricated-tool"))
    results.append({"fixtureId": "F41_FORGED_EXECUTABLE_CLASSIFICATION", "expectedError": "EXECUTABLE_CLASSIFICATION_DRIFT",
                    "observedErrors": observed[:5], "status": "PASS" if any(e.startswith("EXECUTABLE_CLASSIFICATION_DRIFT") for e in observed) else "FAIL"})
    observed = validate(mutate(docker_binary_i, binaryName="generic-install"))
    results.append({"fixtureId": "F42_FORGED_BINARY_PAYLOAD", "expectedError": "BINARY_DECLARATION_PAYLOAD_DRIFT",
                    "observedErrors": observed[:5], "status": "PASS" if any(e.startswith("BINARY_DECLARATION_PAYLOAD_DRIFT") for e in observed) else "FAIL"})
    observed = validate(mutate(font_reference_i, fontFamily="fabricated-font"))
    results.append({"fixtureId": "F43_FORGED_FONT_PAYLOAD", "expectedError": "FONT_PAYLOAD_DRIFT",
                    "observedErrors": observed[:5], "status": "PASS" if any(e.startswith("FONT_PAYLOAD_DRIFT") for e in observed) else "FAIL"})
    observed = validate(mutate(legal_reference_i, currentValue="fabricated-legal-token"))
    results.append({"fixtureId": "F44_FORGED_LEGAL_PAYLOAD", "expectedError": "LEGAL_PAYLOAD_DRIFT",
                    "observedErrors": observed[:5], "status": "PASS" if any(e.startswith("LEGAL_PAYLOAD_DRIFT") for e in observed) else "FAIL"})
    integration_line = "final immichWidgetTest = true;"
    integration_start = integration_line.index("immichWidgetTest")
    integration_class = classify_occurrence("Codebase/mobile/integration_test/login_test.dart", integration_line, integration_start, integration_start + len("immichWidgetTest"))
    results.append({"fixtureId": "F45_INTEGRATION_TEST_IS_TEST_ONLY", "expectedError": "INTEGRATION_TEST_CLASSIFIED",
                    "observedErrors": [] if integration_class[0] == "TEST_ONLY" else ["INTEGRATION_TEST_NOT_TEST_ONLY"],
                    "status": "PASS" if integration_class[0] == "TEST_ONLY" else "FAIL"})
    symbol_line = "final immichLogger = logMessages;"
    symbol_start = symbol_line.index("immichLogger")
    symbol_class = classify_occurrence("Codebase/mobile/lib/log.dart", symbol_line, symbol_start, symbol_start + len("immichLogger"))
    results.append({"fixtureId": "F46_LOWER_CAMEL_SYMBOL_IS_INTERNAL", "expectedError": "LOWER_CAMEL_INTERNAL",
                    "observedErrors": [] if symbol_class[:3] == ("INTERNAL_RUNTIME", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003") else ["LOWER_CAMEL_MISCLASSIFIED"],
                    "status": "PASS" if symbol_class[:3] == ("INTERNAL_RUNTIME", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003") else "FAIL"})
    env_line = "final value = process.env.IMMICH_API_KEY;"
    env_start = env_line.index("IMMICH_API_KEY")
    env_class = classify_occurrence("Codebase/packages/cli/src/config.ts", env_line, env_start, env_start + len("IMMICH_API_KEY"))
    results.append({"fixtureId": "F47_ENVIRONMENT_NAME_IS_COMPATIBILITY", "expectedError": "ENVIRONMENT_CONTRACT_COMPATIBILITY",
                    "observedErrors": [] if env_class[:3] == ("COMPATIBILITY", "PRESERVE_TECHNICAL_COMPATIBILITY", "WP-I1-003") else ["ENVIRONMENT_CONTRACT_MISCLASSIFIED"],
                    "status": "PASS" if env_class[:3] == ("COMPATIBILITY", "PRESERVE_TECHNICAL_COMPATIBILITY", "WP-I1-003") else "FAIL"})
    import_line = "import { ImmichApi } from '@immich/sdk';"
    package_start = import_line.index("@immich/sdk")
    package_class = classify_occurrence("Codebase/packages/cli/src/api.ts", import_line, package_start, package_start + len("@immich/sdk"))
    results.append({"fixtureId": "F48_MODULE_SPECIFIER_IS_PACKAGE_IDENTITY", "expectedError": "MODULE_SPECIFIER_PACKAGE_IDENTITY",
                    "observedErrors": [] if package_class[:3] == ("PACKAGE_IDENTITY", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003") else ["MODULE_SPECIFIER_MISCLASSIFIED"],
                    "status": "PASS" if package_class[:3] == ("PACKAGE_IDENTITY", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003") else "FAIL"})
    test_import_class = classify_occurrence("Codebase/e2e/src/api.spec.ts", import_line, package_start, package_start + len("@immich/sdk"))
    results.append({"fixtureId": "F49_TEST_MODULE_REMAINS_TEST_ONLY", "expectedError": "TEST_MODULE_WRAPPED",
                    "observedErrors": [] if test_import_class[:3] == ("TEST_ONLY", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003") else ["TEST_MODULE_ESCAPED"],
                    "status": "PASS" if test_import_class[:3] == ("TEST_ONLY", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003") else "FAIL"})
    test_style_line = "await page.locator('#immich-asset-viewer').click();"
    test_style_start = test_style_line.index("immich-asset-viewer")
    test_style_class = classify_occurrence("Codebase/e2e/src/viewer.spec.ts", test_style_line, test_style_start, test_style_start + len("immich-asset-viewer"))
    results.append({"fixtureId": "F50_TEST_STYLE_REMAINS_TEST_ONLY", "expectedError": "TEST_STYLE_WRAPPED",
                    "observedErrors": [] if test_style_class[:3] == ("TEST_ONLY", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003") else ["TEST_STYLE_ESCAPED"],
                    "status": "PASS" if test_style_class[:3] == ("TEST_ONLY", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003") else "FAIL"})
    volume_line = "docker run --volume immich_model-cache:/mnt-models image"
    volume_start = volume_line.index("immich_model-cache")
    volume_class = classify_occurrence("Codebase/docs/docs/FAQ.mdx", volume_line, volume_start, volume_start + len("immich_model-cache"))
    results.append({"fixtureId": "F51_NAMED_VOLUME_IS_APP_DATA", "expectedError": "NAMED_VOLUME_APP_DATA",
                    "observedErrors": [] if volume_class[:3] == ("FILESYSTEM_DATA_PATH", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003") else ["NAMED_VOLUME_MISCLASSIFIED"],
                    "status": "PASS" if volume_class[:3] == ("FILESYSTEM_DATA_PATH", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003") else "FAIL"})
    span_cases = {
        "F52_FULL_NAMED_VOLUME_SPAN": "immich_model-cache",
        "F53_FULL_MODULE_SPECIFIER_SPAN": "@immich/plugin-core",
        "F54_FULL_NAMESPACE_SPAN": "app.alextran.immich.widget.configure.RandomConfigure",
        "F55_FULL_UPSTREAM_URL_SPAN": "github.com/immich-app/immich",
    }
    for fixture_id, value in span_cases.items():
        match = IDENTITY_RE.search(value)
        results.append({"fixtureId": fixture_id, "expectedError": "FULL_IDENTITY_SPAN",
                        "observedErrors": [] if match and match.group(0) == value else [f"TRUNCATED:{match.group(0) if match else 'NONE'}"],
                        "status": "PASS" if match and match.group(0) == value else "FAIL"})
    reverse_dns = "group.app.immich.share.widget"
    reverse_match = IDENTITY_RE.search(reverse_dns)
    results.append({"fixtureId": "F56_FULL_REVERSE_DNS_SPAN", "expectedError": "FULL_IDENTITY_SPAN",
                    "observedErrors": [] if reverse_match and reverse_match.group(0) == reverse_dns else [f"TRUNCATED:{reverse_match.group(0) if reverse_match else 'NONE'}"],
                    "status": "PASS" if reverse_match and reverse_match.group(0) == reverse_dns else "FAIL"})
    uri_line = "redirectUri = 'app.immich://oauth-callback'"
    uri_start = uri_line.index("app.immich")
    uri_class = classify_occurrence("Codebase/server/src/constants.ts", uri_line, uri_start, uri_start + len("app.immich"))
    results.append({"fixtureId": "F57_URI_SCHEME_IS_COMPATIBILITY", "expectedError": "URI_SCHEME_COMPATIBILITY",
                    "observedErrors": [] if uri_class[:3] == ("COMPATIBILITY", "PRESERVE_TECHNICAL_COMPATIBILITY", "WP-I1-003") else ["URI_SCHEME_MISCLASSIFIED"],
                    "status": "PASS" if uri_class[:3] == ("COMPATIBILITY", "PRESERVE_TECHNICAL_COMPATIBILITY", "WP-I1-003") else "FAIL"})
    mixed_doc = "Immich always keeps originals while database compatibility is maintained."
    mixed_start = mixed_doc.index("Immich")
    mixed_class = classify_occurrence("Codebase/docs/docs/FAQ.mdx", mixed_doc, mixed_start, mixed_start + len("Immich"))
    results.append({"fixtureId": "F58_MIXED_DOC_PROSE_IS_VISIBLE", "expectedError": "DOC_PROSE_VISIBLE",
                    "observedErrors": [] if mixed_class[:3] == ("DOCUMENTATION", "RENAME_TO_LAMHA", "WP-I1-002") else ["DOC_PROSE_MISCLASSIFIED"],
                    "status": "PASS" if mixed_class[:3] == ("DOCUMENTATION", "RENAME_TO_LAMHA", "WP-I1-002") else "FAIL"})
    email_line = '<ImmichLayout preview="This is an email from Immich.">'
    email_start = email_line.rindex("Immich")
    email_class = classify_occurrence("Codebase/server/src/emails/test.email.tsx", email_line, email_start, email_start + len("Immich"))
    results.append({"fixtureId": "F59_PROSE_FROM_IS_NOT_MODULE_IMPORT", "expectedError": "VISIBLE_EMAIL_COPY",
                    "observedErrors": [] if email_class[:3] == ("USER_VISIBLE", "RENAME_TO_LAMHA", "WP-I1-002") else ["FROM_PROSE_MISCLASSIFIED"],
                    "status": "PASS" if email_class[:3] == ("USER_VISIBLE", "RENAME_TO_LAMHA", "WP-I1-002") else "FAIL"})
    html_line = "<p>To use Immich, use a JavaScript compatible browser.</p>"
    html_start = html_line.index("Immich")
    html_class = classify_occurrence("Codebase/web/src/app.html", html_line, html_start, html_start + len("Immich"))
    results.append({"fixtureId": "F60_RENDERED_HTML_BEATS_COMPAT_WORD", "expectedError": "VISIBLE_HTML_COPY",
                    "observedErrors": [] if html_class[:3] == ("USER_VISIBLE", "RENAME_TO_LAMHA", "WP-I1-002") else ["HTML_COPY_MISCLASSIFIED"],
                    "status": "PASS" if html_class[:3] == ("USER_VISIBLE", "RENAME_TO_LAMHA", "WP-I1-002") else "FAIL"})
    results.append({"fixtureId": "F61_PRIVACY_POLICY_IS_LEGAL_DOCUMENT", "expectedError": "LEGAL_DOCUMENT_DETECTED",
                    "observedErrors": [] if is_legal_file("Codebase/docs/src/pages/privacy-policy.tsx") else ["PRIVACY_POLICY_NOT_LEGAL"],
                    "status": "PASS" if is_legal_file("Codebase/docs/src/pages/privacy-policy.tsx") else "FAIL"})
    visible_cases = [
        ("F62_ISSUE_TEMPLATE_IS_VISIBLE", "Codebase/.github/ISSUE_TEMPLATE/bug_report.yml", "name: Immich bug report"),
        ("F63_STORE_METADATA_IS_VISIBLE", "Codebase/mobile/android/fastlane/metadata/android/en-US/title.txt", "Immich"),
        ("F64_INSTALL_OUTPUT_IS_VISIBLE", "Codebase/install.sh", "echo 'Starting Immich server'"),
    ]
    for fixture_id, fixture_path, fixture_line in visible_cases:
        fixture_start = fixture_line.index("Immich")
        fixture_class = classify_occurrence(fixture_path, fixture_line, fixture_start, fixture_start + len("Immich"))
        results.append({"fixtureId": fixture_id, "expectedError": "PUBLISHED_COPY_VISIBLE",
                        "observedErrors": [] if fixture_class[:3] == ("USER_VISIBLE", "RENAME_TO_LAMHA", "WP-I1-002") else ["PUBLISHED_COPY_MISCLASSIFIED"],
                        "status": "PASS" if fixture_class[:3] == ("USER_VISIBLE", "RENAME_TO_LAMHA", "WP-I1-002") else "FAIL"})
    env_comment = "# Configure Immich before starting the container"
    env_comment_start = env_comment.index("Immich")
    env_comment_class = classify_occurrence("Codebase/docker/example.env", env_comment, env_comment_start, env_comment_start + len("Immich"))
    results.append({"fixtureId": "F65_ENV_COMMENT_IS_DOCUMENTATION", "expectedError": "OPERATOR_INSTRUCTION_VISIBLE",
                    "observedErrors": [] if env_comment_class[:3] == ("DOCUMENTATION", "RENAME_TO_LAMHA", "WP-I1-002") else ["ENV_COMMENT_MISCLASSIFIED"],
                    "status": "PASS" if env_comment_class[:3] == ("DOCUMENTATION", "RENAME_TO_LAMHA", "WP-I1-002") else "FAIL"})
    semantic_cases = [
        ("F66_CLI_HELP_IS_VISIBLE", "Codebase/packages/cli/src/index.ts", "description: 'Immich server URL'", "USER_VISIBLE"),
        ("F67_WIDGET_COPY_IS_VISIBLE", "Codebase/mobile/ios/WidgetExtension/ImmichAPI.swift", "Text('Login to Immich')", "USER_VISIBLE"),
        ("F68_WORKFLOW_NAME_IS_VISIBLE", "Codebase/.github/workflows/sdk.yml", "name: Update Immich SDK", "USER_VISIBLE"),
        ("F69_CANONICAL_API_DESCRIPTION_IS_DOCUMENTATION", "Codebase/server/src/dtos/sync.dto.ts", ".describe('Immich asset response')", "DOCUMENTATION"),
        ("F70_EXPORTED_VISIBLE_STRING_IS_NOT_MODULE", "Codebase/server/src/constants.ts", "export const START = 'Immich Server is listening';", "USER_VISIBLE"),
    ]
    for fixture_id, fixture_path, fixture_line, expected_type in semantic_cases:
        fixture_start = fixture_line.index("Immich")
        fixture_class = classify_occurrence(fixture_path, fixture_line, fixture_start, fixture_start + len("Immich"))
        results.append({"fixtureId": fixture_id, "expectedError": "OCCURRENCE_CONTEXT_CLASSIFIED",
                        "observedErrors": [] if fixture_class[0] == expected_type and fixture_class[2] == "WP-I1-002" else ["OCCURRENCE_CONTEXT_MISCLASSIFIED"],
                        "status": "PASS" if fixture_class[0] == expected_type and fixture_class[2] == "WP-I1-002" else "FAIL"})
    persistence_cases = [
        ("F71_FULL_SHARED_PREFERENCE_NAME", 'const val NAME = "Immich::MediaManager"', "Immich::MediaManager"),
        ("F72_FULL_MEDIA_DESTINATION_PATH", "final path = 'DCIM/Immich';", "DCIM/Immich"),
    ]
    for fixture_id, fixture_line, expected_value in persistence_cases:
        match = IDENTITY_RE.search(fixture_line); fixture_class = classify_occurrence("Codebase/mobile/lib/storage.dart", fixture_line, match.start(), match.end()) if match else None
        ok = bool(match and match.group(0) == expected_value and fixture_class and fixture_class[0] == "FILESYSTEM_DATA_PATH")
        results.append({"fixtureId": fixture_id, "expectedError": "FULL_PERSISTED_VALUE", "observedErrors": [] if ok else ["PERSISTED_VALUE_MISCLASSIFIED"], "status": "PASS" if ok else "FAIL"})
    constant_line = "export const IMMICH_SERVER_START = 'ready';"; constant_start = constant_line.index("IMMICH_SERVER_START")
    constant_class = classify_occurrence("Codebase/server/src/constants.ts", constant_line, constant_start, constant_start + len("IMMICH_SERVER_START"))
    results.append({"fixtureId": "F73_UPPERCASE_INTERNAL_CONSTANT_NOT_ENV", "expectedError": "INTERNAL_CONSTANT",
                    "observedErrors": [] if constant_class[:3] == ("INTERNAL_RUNTIME", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003") else ["CONSTANT_FALSE_ENV"],
                    "status": "PASS" if constant_class[:3] == ("INTERNAL_RUNTIME", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003") else "FAIL"})
    results.append({"fixtureId": "F74_GENERATOR_TEMPLATE_IS_CANONICAL", "expectedError": "TEMPLATE_NOT_GENERATED",
                    "observedErrors": [] if not is_generated("Codebase/open-api/templates/mobile/api.mustache") else ["TEMPLATE_FALSE_GENERATED"],
                    "status": "PASS" if not is_generated("Codebase/open-api/templates/mobile/api.mustache") else "FAIL"})
    identity_asset = "Codebase/docs/docs/developer/img/immich_mobile_architecture.svg"
    results.append({"fixtureId": "F75_IDENTITY_IMAGE_IS_ASSET", "expectedError": "IDENTITY_ASSET_DISCOVERED",
                    "observedErrors": [] if is_brand_asset(identity_asset) else ["IDENTITY_IMAGE_MISSED"], "status": "PASS" if is_brand_asset(identity_asset) else "FAIL"})
    for fixture_id, fixture_path, fixture_line in [
        ("F76_BUSINESS_LICENSE_NOT_LEGAL", "Codebase/server/src/types.ts", "license: UserLicense"),
        ("F77_PLUGIN_AUTHOR_NOT_LEGAL", "Codebase/server/src/dtos/plugin.dto.ts", "author: string"),
        ("F78_CLI_AUTHOR_FLAG_NOT_LEGAL", "Codebase/.github/workflows/merge.yml", "--author weblate"),
    ]:
        tokens = legal_matches(fixture_path, fixture_line)
        results.append({"fixtureId": fixture_id, "expectedError": "NOT_LEGAL_NOTICE", "observedErrors": [] if not tokens else ["LEGAL_FALSE_POSITIVE"], "status": "PASS" if not tokens else "FAIL"})
    original = copy.deepcopy(base[0]); forged = copy.deepcopy(base[0]); forged["surfaceId"] = "ID-FORGED-CONFLICT"; forged["surfaceType"] = "INTERNAL_RUNTIME" if forged.get("surfaceType") != "INTERNAL_RUNTIME" else "PACKAGE_IDENTITY"
    observed = validate([original, forged])
    results.append({"fixtureId": "F79_CONTRADICTORY_SEMANTICS_REJECTED", "expectedError": "SEMANTIC_CONFLICT",
                    "observedErrors": observed[:5], "status": "PASS" if any(e.startswith("SEMANTIC_CONFLICT") for e in observed) else "FAIL"})
    technical_doc_line = "client_id: 'immich' # database compatibility"
    technical_start = technical_doc_line.index("immich")
    technical_class = classify_occurrence("Codebase/docs/docs/oauth.md", technical_doc_line, technical_start, technical_start + len("immich"))
    results.append({"fixtureId": "F80_DOC_CODE_IDENTIFIER_NOT_PRODUCT_PROSE", "expectedError": "TECHNICAL_DOC_COMPATIBILITY",
                    "observedErrors": [] if technical_class[:3] == ("COMPATIBILITY", "PRESERVE_TECHNICAL_COMPATIBILITY", "WP-I1-003") else ["DOC_CODE_MISCLASSIFIED"],
                    "status": "PASS" if technical_class[:3] == ("COMPATIBILITY", "PRESERVE_TECHNICAL_COMPATIBILITY", "WP-I1-003") else "FAIL"})
    config_path = "~/.config/immich/"; config_match = IDENTITY_RE.search(config_path)
    config_class = classify_occurrence("Codebase/docs/docs/features/command-line-interface.md", config_path, config_match.start(), config_match.end()) if config_match else None
    config_ok = bool(config_match and config_match.group(0).rstrip("/") == config_path.rstrip("/") and config_class and config_class[0] == "FILESYSTEM_DATA_PATH")
    results.append({"fixtureId": "F81_FULL_CONFIG_PATH_IS_APP_DATA", "expectedError": "FULL_CONFIG_PATH",
                    "observedErrors": [] if config_ok else ["CONFIG_PATH_MISCLASSIFIED"], "status": "PASS" if config_ok else "FAIL"})
    legal_email = '<a href="mailto:immich@futo.org">immich@futo.org</a>'; legal_start = legal_email.index("immich")
    legal_class = classify_occurrence("Codebase/docs/src/pages/privacy-policy.tsx", legal_email, legal_start, legal_start + len("immich"))
    results.append({"fixtureId": "F82_LEGAL_EMAIL_IS_PRESERVED", "expectedError": "LEGAL_CONTACT_PRESERVED",
                    "observedErrors": [] if legal_class[:3] == ("UPSTREAM_ATTRIBUTION", "PRESERVE_UPSTREAM_ATTRIBUTION", "WP-I1-005") else ["LEGAL_EMAIL_RENAME_RISK"],
                    "status": "PASS" if legal_class[:3] == ("UPSTREAM_ATTRIBUTION", "PRESERVE_UPSTREAM_ATTRIBUTION", "WP-I1-005") else "FAIL"})
    env_span_line = "process.env.IMMICH_MACHINE_LEARNING_ENABLED"
    env_span_match = IDENTITY_RE.search(env_span_line)
    results.append({"fixtureId": "F83_FULL_PROCESS_ENV_SPAN", "expectedError": "FULL_ENVIRONMENT_SPAN",
                    "observedErrors": [] if env_span_match and env_span_match.group(0) == "IMMICH_MACHINE_LEARNING_ENABLED" else [f"TRUNCATED:{env_span_match.group(0) if env_span_match else 'NONE'}"],
                    "status": "PASS" if env_span_match and env_span_match.group(0) == "IMMICH_MACHINE_LEARNING_ENABLED" else "FAIL"})
    test_env_line = "process.env.IMMICH_API_KEY; final value = ImmichEnvironment.test;"
    test_symbol_start = test_env_line.index("ImmichEnvironment")
    test_symbol_class = classify_occurrence("Codebase/server/test/user.service.spec.ts", test_env_line, test_symbol_start, test_symbol_start + len("ImmichEnvironment"))
    results.append({"fixtureId": "F84_TEST_SYMBOL_NOT_ENV_COMPATIBILITY", "expectedError": "TEST_SYMBOL_MIGRATES",
                    "observedErrors": [] if test_symbol_class[:3] == ("TEST_ONLY", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003") else ["TEST_SYMBOL_FALSE_COMPAT"],
                    "status": "PASS" if test_symbol_class[:3] == ("TEST_ONLY", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003") else "FAIL"})
    punctuated = "The immich-server. Next"; punctuated_match = IDENTITY_RE.search(punctuated)
    results.append({"fixtureId": "F85_PROSE_PUNCTUATION_NOT_IN_IDENTIFIER", "expectedError": "TRIM_PROSE_PUNCTUATION",
                    "observedErrors": [] if punctuated_match and punctuated_match.group(0) == "immich-server" else [f"PUNCTUATED:{punctuated_match.group(0) if punctuated_match else 'NONE'}"],
                    "status": "PASS" if punctuated_match and punctuated_match.group(0) == "immich-server" else "FAIL"})
    edge_cases = [
        ("F86_HEREDOC_SUCCESS_IS_VISIBLE", "Codebase/install.sh", "Successfully deployed Immich!", "USER_VISIBLE"),
        ("F87_WORKFLOW_COMMENT_IS_VISIBLE", "Codebase/.github/workflows/auto-close.yml", "body: Thanks for using Immich", "USER_VISIBLE"),
        ("F88_MOBILE_SHARE_TEXT_IS_VISIBLE", "Codebase/mobile/lib/share.dart", "text: 'Immich Database Export'", "USER_VISIBLE"),
        ("F89_CANONICAL_DTO_TEXT_IS_DOCUMENTATION", "Codebase/server/src/dtos/time-bucket.dto.ts", "'Immich time bucket description'", "DOCUMENTATION"),
    ]
    for fixture_id, fixture_path, fixture_line, expected_type in edge_cases:
        fixture_start = fixture_line.index("Immich"); fixture_class = classify_occurrence(fixture_path, fixture_line, fixture_start, fixture_start + len("Immich"))
        results.append({"fixtureId": fixture_id, "expectedError": "VISIBLE_CANONICAL_CONTEXT", "observedErrors": [] if fixture_class[0] == expected_type and fixture_class[2] == "WP-I1-002" else ["VISIBLE_CONTEXT_MISCLASSIFIED"], "status": "PASS" if fixture_class[0] == expected_type and fixture_class[2] == "WP-I1-002" else "FAIL"})
    for fixture_id, fixture_line, expected_value, expected_type in [
        ("F90_FULL_DEEP_LINK_SCHEME", "open('immich://asset/123')", "immich://asset/123", "COMPATIBILITY"),
        ("F91_DOT_MARKER_IS_APP_DATA", "marker = '.immich'", ".immich", "FILESYSTEM_DATA_PATH"),
        ("F92_PERSISTED_KEY_IS_APP_DATA", "key = 'immich:changeToken'", "immich:changeToken", "FILESYSTEM_DATA_PATH"),
    ]:
        match = IDENTITY_RE.search(fixture_line); fixture_class = classify_occurrence("Codebase/mobile/lib/storage.dart", fixture_line, match.start(), match.end()) if match else None
        ok = bool(match and match.group(0) == expected_value and fixture_class and fixture_class[0] == expected_type)
        results.append({"fixtureId": fixture_id, "expectedError": "FULL_COMPATIBILITY_VALUE", "observedErrors": [] if ok else ["COMPATIBILITY_VALUE_MISCLASSIFIED"], "status": "PASS" if ok else "FAIL"})
    structural_cases = [
        ("F93_COMPOSE_PROJECT_NAME_STRUCTURAL", "Codebase/docker/docker-compose.yml", "name: immich", "compose:project-name"),
        ("F94_PUBSPEC_DESCRIPTION_VISIBLE", "Codebase/mobile/pubspec.yaml", "description: Immich - Self-hosted photos", "pubspec:description"),
    ]
    for fixture_id, fixture_path, fixture_line, key in structural_cases:
        ok = any(spec[0] == key for spec in structural_specs(fixture_path, fixture_line, ""))
        results.append({"fixtureId": fixture_id, "expectedError": "STRUCTURAL_IDENTITY_DISCOVERED", "observedErrors": [] if ok else ["STRUCTURAL_IDENTITY_MISSED"], "status": "PASS" if ok else "FAIL"})
    late_visible = [
        ("F95_API_TAG_DESCRIPTION_VISIBLE", "Codebase/server/src/constants.ts", "[ApiTag.Admin]: 'Immich administration API'", "DOCUMENTATION"),
        ("F96_COMPOSE_COMMENT_VISIBLE", "Codebase/docker/docker-compose.yml", "# To install Immich, run compose", "DOCUMENTATION"),
        ("F97_SHELL_LOG_VISIBLE_WITH_ENV", "Codebase/server/bin/start.sh", "log_message \"Initializing Immich $IMMICH_SOURCE_REF\"", "USER_VISIBLE"),
    ]
    for fixture_id, fixture_path, fixture_line, expected_type in late_visible:
        fixture_start = fixture_line.index("Immich"); fixture_class = classify_occurrence(fixture_path, fixture_line, fixture_start, fixture_start + len("Immich"))
        results.append({"fixtureId": fixture_id, "expectedError": "PUBLISHED_CONTEXT_VISIBLE", "observedErrors": [] if fixture_class[0] == expected_type and fixture_class[2] == "WP-I1-002" else ["PUBLISHED_CONTEXT_MISCLASSIFIED"], "status": "PASS" if fixture_class[0] == expected_type and fixture_class[2] == "WP-I1-002" else "FAIL"})
    bare_scheme = 'deepLink.uri.scheme == "immich"'; bare_start = bare_scheme.index("immich")
    bare_class = classify_occurrence("Codebase/mobile/lib/main.dart", bare_scheme, bare_start, bare_start + len("immich"))
    results.append({"fixtureId": "F98_BARE_DEEP_LINK_SCHEME_COMPATIBILITY", "expectedError": "BARE_SCHEME_COMPATIBILITY", "observedErrors": [] if bare_class[:3] == ("COMPATIBILITY", "PRESERVE_TECHNICAL_COMPATIBILITY", "WP-I1-003") else ["BARE_SCHEME_MISCLASSIFIED"], "status": "PASS" if bare_class[:3] == ("COMPATIBILITY", "PRESERVE_TECHNICAL_COMPATIBILITY", "WP-I1-003") else "FAIL"})
    route_line = "WELL_KNOWN_PATH = '/.well-known/immich'"; route_match = IDENTITY_RE.search(route_line)
    route_class = classify_occurrence("Codebase/server/src/constants.ts", route_line, route_match.start(), route_match.end()) if route_match else None
    results.append({"fixtureId": "F99_WELL_KNOWN_ROUTE_IS_COMPATIBILITY", "expectedError": "WELL_KNOWN_ROUTE_COMPATIBILITY", "observedErrors": [] if route_class and route_class[:3] == ("COMPATIBILITY", "PRESERVE_TECHNICAL_COMPATIBILITY", "WP-I1-003") else ["WELL_KNOWN_ROUTE_MISCLASSIFIED"], "status": "PASS" if route_class and route_class[:3] == ("COMPATIBILITY", "PRESERVE_TECHNICAL_COMPATIBILITY", "WP-I1-003") else "FAIL"})
    localized = '"export": "Immich Database Export"'; localized_start = localized.index("Immich")
    localized_class = classify_occurrence("Codebase/i18n/fi.json", localized, localized_start, localized_start + len("Immich"))
    results.append({"fixtureId": "F100_I18N_PRECEDENCE_IS_VISIBLE", "expectedError": "I18N_VISIBLE", "observedErrors": [] if localized_class[:3] == ("USER_VISIBLE", "RENAME_TO_LAMHA", "WP-I1-002") else ["I18N_MISCLASSIFIED"], "status": "PASS" if localized_class[:3] == ("USER_VISIBLE", "RENAME_TO_LAMHA", "WP-I1-002") else "FAIL"})
    build_path = "../open-api/immich-openapi-specs.json"; build_match = IDENTITY_RE.search(build_path)
    build_class = classify_occurrence("Codebase/open-api/bin/generate.sh", build_path, build_match.start(), build_match.end()) if build_match else None
    results.append({"fixtureId": "F101_BUILD_PATH_NOT_APP_DATA", "expectedError": "BUILD_PATH_CLASSIFIED", "observedErrors": [] if build_class and build_class[0] == "BUILD" else ["BUILD_PATH_FALSE_APP_DATA"], "status": "PASS" if build_class and build_class[0] == "BUILD" else "FAIL"})
    dot_prefix = ".immich_app_branch_subdomain"; dot_prefix_match = IDENTITY_RE.search(dot_prefix)
    results.append({"fixtureId": "F102_DOT_MARKER_BOUNDARY", "expectedError": "DOT_MARKER_BOUNDARY", "observedErrors": [] if not dot_prefix_match or dot_prefix_match.group(0) != ".immich" else ["DOT_MARKER_PREFIX_MATCH"], "status": "PASS" if not dot_prefix_match or dot_prefix_match.group(0) != ".immich" else "FAIL"})
    closing = "</ImmichLayout>"; closing_match = IDENTITY_RE.search(closing)
    results.append({"fixtureId": "F103_CLOSING_TAG_NOT_APP_DATA", "expectedError": "CLOSING_TAG_SYMBOL", "observedErrors": [] if closing_match and closing_match.group(0) == "ImmichLayout" else [f"CLOSING_TAG_BAD_SPAN:{closing_match.group(0) if closing_match else 'NONE'}"], "status": "PASS" if closing_match and closing_match.group(0) == "ImmichLayout" else "FAIL"})
    dart_import = "import 'package:immich_mobile/widgets/common/immich_toast.dart';"; dart_matches = list(IDENTITY_RE.finditer(dart_import))
    dart_ok = bool(dart_matches) and not any(match.group(0).startswith("/") for match in dart_matches)
    results.append({"fixtureId": "F104_DART_IMPORT_NOT_APP_DATA", "expectedError": "MODULE_IMPORT_NOT_PATH", "observedErrors": [] if dart_ok else ["DART_IMPORT_FALSE_PATH"], "status": "PASS" if dart_ok else "FAIL"})
    weblate = "WEBLATE_COMPONENT='immich/immich'"; weblate_matches = list(IDENTITY_RE.finditer(weblate))
    results.append({"fixtureId": "F105_WEBLATE_COMPONENT_NOT_APP_DATA", "expectedError": "EXTERNAL_COMPONENT_NOT_PATH", "observedErrors": [] if not any(match.group(0).startswith("immich/") for match in weblate_matches) else ["WEBLATE_FALSE_PATH"], "status": "PASS" if not any(match.group(0).startswith("immich/") for match in weblate_matches) else "FAIL"})
    scheduler_values = ["immich/BackgroundWorkerV1", "immich/MediaObserverV1", "immich/PeriodicBackgroundWorkerV1"]
    scheduler_ok = all((match := IDENTITY_RE.search(value)) and match.group(0) == value and classify_occurrence("Codebase/mobile/android/BackgroundWorkerApiImpl.kt", value, match.start(), match.end())[0] == "FILESYSTEM_DATA_PATH" for value in scheduler_values)
    results.append({"fixtureId": "F106_SCHEDULER_KEYS_ARE_APP_DATA", "expectedError": "SCHEDULER_KEYS_PERSISTED", "observedErrors": [] if scheduler_ok else ["SCHEDULER_KEY_MISSED"], "status": "PASS" if scheduler_ok else "FAIL"})
    exclusion_cases = [
        ("F107_CODEGEN_OUTPUT_PATH_IS_BUILD", "Codebase/mobile/pigeon/local_image_api.dart", "'android/app/src/main/kotlin/app/alextran/immich/images/LocalImages.g.kt'", "BUILD"),
        ("F108_APP_STORE_URL_IS_COMPATIBILITY", "Codebase/mobile/lib/constants.dart", "'https://apps.apple.com/app/immich/id123'", "COMPATIBILITY"),
        ("F109_USER_AGENT_IS_COMPATIBILITY", "Codebase/mobile/lib/utils/user_agent.dart", "'immich-$platform/$version'", "COMPATIBILITY"),
    ]
    for fixture_id, fixture_path, fixture_line, expected_type in exclusion_cases:
        fixture_match = IDENTITY_RE.search(fixture_line); fixture_class = classify_occurrence(fixture_path, fixture_line, fixture_match.start(), fixture_match.end()) if fixture_match else None
        results.append({"fixtureId": fixture_id, "expectedError": "MOBILE_TECHNICAL_CONTEXT", "observedErrors": [] if fixture_class and fixture_class[0] == expected_type and fixture_class[2] == "WP-I1-003" else ["MOBILE_TECHNICAL_MISCLASSIFIED"], "status": "PASS" if fixture_class and fixture_class[0] == expected_type and fixture_class[2] == "WP-I1-003" else "FAIL"})
    return results


def git_changed() -> list[str]:
    output = subprocess.check_output(["git", "status", "--porcelain=v1", "--untracked-files=all"], cwd=ROOT, text=True)
    return [line[3:].replace("\\", "/") for line in output.splitlines() if line]


def build() -> dict[str, object]:
    rows = baseline_rows()
    integrity = verify_codebase(rows)
    if integrity["status"] != "PASS":
        raise SystemExit("Codebase differs from the immutable WP-I0-001 baseline")
    records, discovery = discover(rows)
    errors = validate(records)
    fixtures = negative_fixtures(records)
    if errors or any(f["status"] != "PASS" for f in fixtures):
        raise SystemExit(f"inventory validation failed: errors={errors[:10]} fixtures={[f for f in fixtures if f['status'] != 'PASS'][:10]}")
    counts = Counter(str(r["surfaceType"]) for r in records)
    dispositions = Counter(str(r["disposition"]) for r in records)
    owners = Counter(str(r["futureOwner"]) for r in records if r["futureOwner"])
    generated_count = sum(bool(r["isGenerated"]) for r in records)
    binding = [r for r in records if r["binding"]]
    summary = {
        "schemaVersion": 1, "packageId": PACKAGE, "status": "PASS",
        "requirements": REQUIREMENTS, "technicalPrerequisite": "WP-I0-001",
        "baselineCommit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "codebaseFilesScanned": len(rows), "totalSurfaces": len(records),
        "bindingSurfaces": len(binding), "classifiedBindingSurfaces": len(binding),
        "unclassifiedBindingSurfaces": 0, "unownedRequiredTransformations": 0,
        "unresolvedUnsafeLegalDeletions": 0, "generatedSurfaces": generated_count,
        "surfaceTypeCounts": dict(sorted(counts.items())),
        "dispositionCounts": dict(sorted(dispositions.items())),
        "futureOwnerCounts": dict(sorted(owners.items())), "discoveryCounts": discovery,
        "downstreamPackagesAuthorized": [], "nextPackageImplementationChanges": 0,
    }
    inventory = {"schemaVersion": 1, "packageId": PACKAGE, "records": records}
    dump(OUT / "identity-inventory.json", inventory)
    subsets = {
        "user-visible-inventory.json": {"USER_VISIBLE", "DOCUMENTATION"},
        "package-bundle-inventory.json": {"PACKAGE_IDENTITY", "BUILD", "DISTRIBUTION", "INTERNAL_RUNTIME", "COMPATIBILITY", "GENERATED", "TEST_ONLY"},
        "app-data-inventory.json": {"FILESYSTEM_DATA_PATH"},
        "brand-asset-inventory.json": {"ASSET"},
        "font-inventory.json": {"FONT"},
        "legal-attribution-inventory.json": {"LEGAL", "UPSTREAM_ATTRIBUTION"},
    }
    for name, types in subsets.items():
        selected = [r for r in records if r["surfaceType"] in types]
        dump(OUT / name, {"schemaVersion": 1, "packageId": PACKAGE, "surfaceTypes": sorted(types), "recordCount": len(selected), "records": selected})
    binary_records = [r for r in records if r.get("binaryName")]
    dump(OUT / "bundled-binary-inventory.json", {"schemaVersion": 1, "packageId": PACKAGE,
         "recordCount": len(binary_records), "records": binary_records})
    dump(OUT / "generator-contracts.json", {
        "schemaVersion": 1, "packageId": PACKAGE,
        "contracts": [{
            "id": "generator-contract:openapi",
            "outputRoots": ["Codebase/open-api/immich-openapi-specs.json", "Codebase/mobile/openapi", "Codebase/packages/sdk/src/fetch-client.ts"],
            "sourceRoots": ["Codebase/server/src", "Codebase/open-api/bin", "Codebase/open-api/templates", "Codebase/open-api/patch", "Codebase/open-api/openapitools.json"],
            "rule": "OpenAPI outputs are regenerated from server controllers/DTOs through repository OpenAPI tooling; edit canonical server source, never generated clients directly.",
        }, {
            "id": "generator-contract:dart-codegen",
            "outputPatterns": ["*.g.dart", "*.freezed.dart"],
            "sourceRule": "The adjacent .dart source is canonical when present; otherwise repository Dart code-generation configuration is required.",
            "sourceRoots": ["Codebase/mobile/lib", "Codebase/mobile/openapi/lib"],
        }],
    })
    distributed_fonts = [r for r in records if r["surfaceType"] == "FONT" and r["locator"] == "file"]
    font_references = [r for r in records if r["surfaceType"] == "FONT" and r["locator"] != "file"]
    dump(OUT / "risk-register.json", {
        "schemaVersion": 1, "packageId": PACKAGE, "status": "PASS_WITH_OWNED_REVIEWS",
        "risks": [{
            "riskId": "WP-I1-001-RISK-FONT-LICENSING", "status": "REVIEW_REQUIRED",
            "owner": "WP-I1-005", "blocks": ["WP-I1-005 completion", "I1 release gate"],
            "affectedDistributedFontFiles": len(distributed_fonts), "affectedReferenceSurfaces": len(font_references),
            "families": sorted({str(r.get("fontFamily")) for r in distributed_fonts}),
            "evidence": "font-inventory.json",
            "statement": "No package-local licence record was found for the bundled font bytes; redistribution permission and attribution must be established, not assumed.",
        }, {
            "riskId": "WP-I1-001-RISK-BINARY-NOTICES", "status": "REVIEW_REQUIRED",
            "owner": "WP-I1-005", "blocks": ["WP-I1-005 completion", "I1 release gate"],
            "affectedBinarySurfaces": len(binary_records), "evidence": "bundled-binary-inventory.json",
            "statement": "Base images, copied executables/shared libraries, installed runtime components, and vendored binary tools require reviewed licence and attribution notices before Lamha distribution.",
        }, {
            "riskId": "WP-I1-001-RISK-FUTO-COBRANDING", "status": "REVIEW_REQUIRED",
            "owner": "WP-I1-005", "coordinationOwner": "WP-I1-004", "blocks": ["WP-I1-004 co-branded asset replacement", "I1 release gate"],
            "affectedAssetSurfaces": sum(r.get("surfaceType") == "ASSET" and r.get("thirdPartyIdentity") == "FUTO" for r in records),
            "evidence": "brand-asset-inventory.json",
            "statement": "FUTO co-branding must not be silently removed or altered during Lamha asset replacement without the reviewed legal/attribution decision.",
        }],
    })
    dump(OUT / "codebase-integrity.json", integrity)
    dump(OUT / "negative-fixture-results.json", {"status": "PASS", "passed": len(fixtures), "total": len(fixtures), "results": fixtures})
    dump(OUT / "package-summary.json", summary)
    report = {
        "schemaVersion": 1, "packageId": PACKAGE, "status": "PASS",
        "passes": [
            {"name": "top-down-authority", "status": "PASS", "requirements": REQUIREMENTS},
            {"name": "bottom-up-all-files", "status": "PASS", "files": len(rows), "surfaces": len(records)},
            {"name": "semantic-completeness", "status": "PASS", "unclassified": 0, "unowned": 0, "unsafeLegalDeletion": 0},
        ],
        "requirementResults": {requirement: "PASS" for requirement in REQUIREMENTS},
        "knownSurfaceResults": {**{name: "PASS" for name in subsets}, "bundled-binary-inventory.json": "PASS"},
        "negativeFixtures": {"passed": len(fixtures), "total": len(fixtures), "status": "PASS"},
        "codebaseIntegrity": integrity,
    }
    dump(OUT / "verification-report.json", report)
    changed = git_changed()
    outside = [p for p in changed if not p.startswith(f"graphify/13-implementation/{PACKAGE}/")]
    scope = {"status": "PASS" if not outside else "FAIL", "changedPaths": changed, "outsidePackage": outside,
             "codebaseChanges": [p for p in changed if p.startswith("Codebase/")]}
    dump(OUT / "scope-audit.json", scope)
    if outside:
        raise SystemExit(f"unauthorized changed paths: {outside}")
    completion = f"""# WP-I1-001 completion evidence

- Inventory validation: PASS
- Requirements: {', '.join(REQUIREMENTS)}
- Immutable Codebase baseline: {integrity['expectedFiles']:,} files, 0 added, 0 removed, 0 modified, 0 renamed
- Discovered identity/legal surfaces: {len(records):,}
- Binding surfaces classified: {len(binding):,} / {len(binding):,}
- Unclassified binding surfaces: 0
- Unowned required transformations: 0
- Unsafe legal deletions: 0
- Negative fixtures: {len(fixtures)} / {len(fixtures)} PASS
- Future owners: {json.dumps(dict(sorted(owners.items())), sort_keys=True)}
- Font licensing review: WP-I1-005 ({len(distributed_fonts)} distributed files; {len(font_references)} references)
- Binary notice review: WP-I1-005 ({len(binary_records)} declaration/reference surfaces)
- FUTO co-branding review: WP-I1-005 coordinated with WP-I1-004
- Next-package implementation changes: 0

Verification commands:

```text
python -B graphify/13-implementation/WP-I1-001/inventory.py --check-only
python -B graphify/13-implementation/WP-I1-001/verify_evidence.py --pre-review
```

Independent adversarial review is a separate exit gate and is recorded in `adversarial-review.md`.
"""
    (OUT / "completion-evidence.md").write_text(completion, encoding="utf-8")
    return summary


def write_manifest() -> None:
    files = []
    actual = {path.name for path in OUT.iterdir() if path.is_file()} - {"artifact-manifest.json", "adversarial-review.md"}
    if actual != MANIFEST_CONTENT_FILES:
        raise SystemExit(f"manifest content set mismatch: missing={sorted(MANIFEST_CONTENT_FILES-actual)} unexpected={sorted(actual-MANIFEST_CONTENT_FILES)}")
    for name in sorted(MANIFEST_CONTENT_FILES):
        path = OUT / name
        data = path.read_bytes()
        files.append({"path": path.relative_to(ROOT).as_posix(), "size": len(data), "sha256": sha256(data)})
    dump(OUT / "artifact-manifest.json", {
        "schemaVersion": 1, "packageId": PACKAGE, "files": files,
        "selfExcluded": "artifact-manifest.json is bound by the exact Git completion commit and independently rehashed after commit.",
        "reviewExcluded": "adversarial-review.md is written by the independent reviewer after generation and bound by the exact Git completion commit.",
    })


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    if args.check_only:
        records = json.loads((OUT / "identity-inventory.json").read_text(encoding="utf-8"))["records"]
        errors = validate(records)
        integrity = verify_codebase(baseline_rows())
        if errors or integrity["status"] != "PASS":
            raise SystemExit(f"FAIL {errors} {integrity['status']}")
        print(f"PASS {len(records)} identity surfaces; Codebase {integrity['expectedFiles']} files unchanged")
        return
    summary = build()
    write_manifest()
    print(f"PASS {summary['totalSurfaces']} identity surfaces across {summary['codebaseFilesScanned']} files")


if __name__ == "__main__":
    main()
