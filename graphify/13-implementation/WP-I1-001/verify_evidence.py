#!/usr/bin/env python3
"""Independent verifier for the saved WP-I1-001 evidence."""

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
REQS = {
    "CAN-LAM-ARCH-001", "CAN-LAM-ARCH-368", "CAN-LAM-ARCH-434", "CAN-LAM-ARCH-439",
    "CAN-LAM-ARCH-442", "CAN-LAM-ARCH-443", "CAN-LAM-LEGAL-010",
}
DISPOSITIONS = {
    "RENAME_TO_LAMHA", "REPLACE_WITH_LAMHA_ASSET", "MIGRATE_TO_LAMHA_IDENTIFIER",
    "PRESERVE_LEGAL", "PRESERVE_UPSTREAM_ATTRIBUTION", "PRESERVE_TECHNICAL_COMPATIBILITY",
    "REMOVE_LATER", "REVIEW_REQUIRED", "NOT_PRODUCT_IDENTITY",
}
TYPES = {
    "USER_VISIBLE", "PACKAGE_IDENTITY", "INTERNAL_RUNTIME", "FILESYSTEM_DATA_PATH", "BUILD",
    "DISTRIBUTION", "LEGAL", "ASSET", "FONT", "DOCUMENTATION", "TEST_ONLY", "GENERATED",
    "COMPATIBILITY", "UPSTREAM_ATTRIBUTION",
}
OWNERS = {"WP-I1-002", "WP-I1-003", "WP-I1-004", "WP-I1-005"}
TEXT_SUFFIXES = {
    "", ".cjs", ".css", ".csv", ".dart", ".env", ".graphql", ".html", ".java", ".js",
    ".json", ".jsx", ".kt", ".kts", ".md", ".mdx", ".mjs", ".plist", ".properties",
    ".py", ".rb", ".rs", ".scss", ".sh", ".sql", ".svelte", ".svg", ".swift", ".toml",
    ".ts", ".tsx", ".txt", ".xml", ".yaml", ".yml",
}
IDENTITY = re.compile(
    r"(?i)((?-i:IMMICH_[A-Z0-9_]+)|app\.alextran\.immich(?:[._/-][a-z0-9_.-]+)*|"
    r"(?:com|io)\.immich(?:[._/-][a-z0-9_.-]+)*|ghcr\.io/immich-app(?:/[a-z0-9_.-]+)*|"
    r"github\.com/immich-app(?:/[a-z0-9_.-]+)*|(?:[a-z0-9-]+\.)*immich\.(?:app|cloud)|"
    r"(?-i:(?:[a-z][a-z0-9-]*\.)+immich(?:\.[A-Za-z0-9_-]+)*)|@immich/[a-z0-9_.-]+|"
    r"Immich::[A-Za-z0-9_:.-]+|(?:DCIM|Pictures|Documents)/Immich(?:[/A-Za-z0-9_.-]+)*|"
    r"immich://[a-z0-9_.?&=/#-]*|(?<![A-Za-z0-9])\.immich(?=[/\"'\s]|$)|immich:(?:changeToken|[A-Z][A-Za-z0-9_.:/-]*)|immich/(?:BackgroundWorker|MediaObserver|PeriodicBackgroundWorker)[A-Za-z0-9_.-]*|"
    r"~?/\.config/immich(?:/[A-Za-z0-9_.-]+)*|/\.well-known/immich|"
    r"immich[-_.](?:[a-z0-9_.-]*\.(?=[\"'])|[a-z0-9_.-]*[a-z0-9_-])|Immich[A-Z][A-Za-z0-9]*|\bimmich\b)"
)
FONT = re.compile(r"(?i)\b(GoogleSansCode|GoogleSans|OverpassMono|Overpass|Inconsolata)(?:[-A-Za-z0-9_]*)\b")
FUTO = re.compile(r"(?i)(FUTO\s+Holdings,\s*Inc\.|[A-Za-z0-9._%+-]+@futo\.org|(?:pay\.)?futo\.(?:org|tech)|Futo[A-Z][A-Za-z0-9]*|\bFUTO\b)")
BINARY = re.compile(r"(?i)\b(exiftool(?:-vendored)?|jellyfin-ffmpeg|ffmpeg|ffprobe|libvips|imagemagick)\b")
BINARY_DECL = re.compile(r"(?i)\b(tini|mise|uvx?|python(?:3(?:\.\d+)?)?|node|cuda|cudnn|openvino|rocm|armnn|rknn|onnxruntime|\.so(?:\.[0-9]+)*|/usr/local/bin|/bin/(?:tini|uvx?|python|mise)|apt-get\s+install|apk\s+add|dnf\s+install)\b")
BINARY_PACKAGE = re.compile(r"(?i)(https?://[^\s\"']+\.(?:deb|rpm|tar\.gz|tgz|zip)|\b[a-z0-9][a-z0-9_.+-]*\.(?:deb|rpm|so(?:\.[0-9]+)*)\b|\bdpkg\s+-i\b)")
LEGAL = re.compile(r"(?i)(\bcopyright\b|\blicen[cs]e(?:d|s)?\b|\battribution\b|\btrademark\b|\bthird[- ]party\b|\bSPDX\b|\bauthors?\b)")
DATA_ACCESS = re.compile(r"(?i)(getApplicationDocumentsDirectory|getApplicationSupportDirectory|getTemporaryDirectory|getLibraryDirectory|getDownloadsDirectory|context\.(?:cacheDir|filesDir)|applicationContext\.(?:cacheDir|filesDir)|FileManager\.default\.urls\(for:\s*\.(?:caches|document|applicationSupport)Directory)")
GENERATED = re.compile(r"(?i)(^Codebase/(?:mobile/openapi|server/open-api|web/src/lib/api)/|^Codebase/open-api/immich-openapi-specs\.json$|^Codebase/packages/sdk/src/fetch-client\.ts$|\.g\.dart$|\.freezed\.dart$)")
LEGAL_IDENTITY = re.compile(r"(?i)(\bcopyright\b|\battribution\b|\btrademark\b|\bSPDX\b)")
VISIBLE = re.compile(r"(?i)(title|label|description|placeholder|tooltip|message|toast|heading|subject|display|Text\(|<title|aria-label|alt=|Welcome|About|server URL|starting Immich)")
PACKAGE_LINE = re.compile(r"(?i)(package(?:name)?|bundle|applicationId|namespace|PRODUCT_BUNDLE_IDENTIFIER|CFBundle|app\.alextran\.immich|@immich/|immich-(?:mobile|web|server|cli|machine-learning)|docker|container|image:|ghcr\.io|executable|bin/immich)")
DATA_LINE = re.compile(r"(?i)(app[-_ ]?data|support directory|documents directory|(?<![A-Za-z0-9])\.immich(?:[/\\]|[\"'\s]|$)|immich[_-](?:data|cache|model|upload|library|postgres))")
COMPAT_LINE = re.compile(r"(?i)(migration|legacy|backward|compat|cookie|header|user-agent|x-immich|api key|env\(|IMMICH_[A-Z0-9_]+|database|protocol|oauth|redirect|volume|archive\.immich)")
TEST_PATH = re.compile(r"(?i)(^|/)(test|tests|test-data|integration_tests?|e2e|fixtures?|mocks?|__tests?__|__mocks__)(/|$)|\.(spec|test)\.")
DOC_PATH = re.compile(r"(?i)(^|/)(docs?|README|CONTRIBUTING|SECURITY|CODE_OF_CONDUCT)(/|\.|$)")
UPSTREAM = re.compile(r"(?i)(github\.com/immich-app|\btrademark\b|\bupstream\b|copyright\s+\(c\).*(?:immich|alex\s+tran))")
ASSET_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".ico", ".svg"}
BRAND_ASSET_SUFFIXES = ASSET_SUFFIXES | {".xml", ".json"}
FONT_SUFFIXES = {".ttf", ".otf", ".woff", ".woff2"}
MANIFEST_REQUIRED = {
    "app-data-inventory.json", "brand-asset-inventory.json", "bundled-binary-inventory.json",
    "codebase-integrity.json", "completion-evidence.md", "font-inventory.json", "generator-contracts.json",
    "identity-inventory.json", "inventory.py", "legal-attribution-inventory.json",
    "negative-fixture-results.json", "package-bundle-inventory.json", "package-summary.json",
    "risk-register.json", "scope-audit.json", "user-visible-inventory.json", "verification-report.json",
    "verify_evidence.py",
}
REQUIRED_FIXTURES = {
    "F01_UNCLASSIFIED", "F02_INVALID_SURFACE_TYPE", "F03_UNOWNED_RENAME", "F04_UNKNOWN_OWNER",
    "F05_DUPLICATE_ID", "F06_FONT_STATUS_MISSING", "F07_FONT_STATUS_GUESSED", "F08_LEGAL_RENAME",
    "F09_ATTRIBUTION_REMOVE", "F10_GENERATED_SOURCE_MISSING", "F11_SOURCE_PATH_MISSING",
    "F12_NON_PRODUCT_OWNER", "F13_UNOWNED_ASSET", "F14_UNOWNED_COMPATIBILITY",
    "F15_LEGAL_ASSET_REPLACE", "F16_INVALID_DISPOSITION_CASE", "F17_INVENTED_GENERATOR_CONTRACT",
    "F18_STRUCTURAL_VALUE_FORGED", "F19_MISSED_PBXPROJ_IDENTITY", "F20_MISSED_GENERIC_LAUNCHER_ASSET",
    "F21_MISSED_APP_DATA_ACCESS", "F22_DOMAIN_IS_NOT_APP_DATA", "F23_MISSED_DOCKER_BINARY_DECLARATION",
    "F24_VISIBLE_MANIFEST_WRONG_OWNER", "F25_AUTHORIZATION_IS_NOT_LEGAL",
    "F26_PRODUCT_PROSE_NOT_UPSTREAM_ATTRIBUTION", "F27_SYMBOL_IS_NOT_USER_VISIBLE",
    "F28_VISIBLE_TEST_FOLLOWS_UI_OWNER", "F29_MISSED_STRUCTURAL_BUNDLE_EXECUTABLE",
    "F30_MISSED_PERSISTENCE_DECLARATION",
    "F31_MISSED_FUTO_IDENTITY", "F32_MANIFEST_OMITS_REQUIRED_ARTIFACT",
    "F33_LONG_STYLE_TOKEN_IS_INTERNAL", "F34_FORGED_ASSET_CONSUMER",
    "F35_TEMP_DATA_MARKED_DURABLE", "F36_OMITTED_ASSET_CONSUMER",
    "F37_FORGED_ASSET_DIMENSIONS", "F38_SWAPPED_IDENTITY_CLASSIFICATION",
    "F39_FORGED_DATA_DECLARATION_SEMANTICS", "F40_FORGED_PATH_CLASSIFICATION",
    "F41_FORGED_EXECUTABLE_CLASSIFICATION", "F42_FORGED_BINARY_PAYLOAD",
    "F43_FORGED_FONT_PAYLOAD", "F44_FORGED_LEGAL_PAYLOAD",
    "F45_INTEGRATION_TEST_IS_TEST_ONLY", "F46_LOWER_CAMEL_SYMBOL_IS_INTERNAL",
    "F47_ENVIRONMENT_NAME_IS_COMPATIBILITY", "F48_MODULE_SPECIFIER_IS_PACKAGE_IDENTITY",
    "F49_TEST_MODULE_REMAINS_TEST_ONLY", "F50_TEST_STYLE_REMAINS_TEST_ONLY",
    "F51_NAMED_VOLUME_IS_APP_DATA",
    "F52_FULL_NAMED_VOLUME_SPAN", "F53_FULL_MODULE_SPECIFIER_SPAN",
    "F54_FULL_NAMESPACE_SPAN", "F55_FULL_UPSTREAM_URL_SPAN",
    "F56_FULL_REVERSE_DNS_SPAN", "F57_URI_SCHEME_IS_COMPATIBILITY",
    "F58_MIXED_DOC_PROSE_IS_VISIBLE", "F59_PROSE_FROM_IS_NOT_MODULE_IMPORT",
    "F60_RENDERED_HTML_BEATS_COMPAT_WORD", "F61_PRIVACY_POLICY_IS_LEGAL_DOCUMENT",
    "F62_ISSUE_TEMPLATE_IS_VISIBLE", "F63_STORE_METADATA_IS_VISIBLE",
    "F64_INSTALL_OUTPUT_IS_VISIBLE", "F65_ENV_COMMENT_IS_DOCUMENTATION",
    "F66_CLI_HELP_IS_VISIBLE", "F67_WIDGET_COPY_IS_VISIBLE", "F68_WORKFLOW_NAME_IS_VISIBLE",
    "F69_CANONICAL_API_DESCRIPTION_IS_DOCUMENTATION", "F70_EXPORTED_VISIBLE_STRING_IS_NOT_MODULE",
    "F71_FULL_SHARED_PREFERENCE_NAME", "F72_FULL_MEDIA_DESTINATION_PATH",
    "F73_UPPERCASE_INTERNAL_CONSTANT_NOT_ENV", "F74_GENERATOR_TEMPLATE_IS_CANONICAL",
    "F75_IDENTITY_IMAGE_IS_ASSET", "F76_BUSINESS_LICENSE_NOT_LEGAL",
    "F77_PLUGIN_AUTHOR_NOT_LEGAL", "F78_CLI_AUTHOR_FLAG_NOT_LEGAL",
    "F79_CONTRADICTORY_SEMANTICS_REJECTED",
    "F80_DOC_CODE_IDENTIFIER_NOT_PRODUCT_PROSE", "F81_FULL_CONFIG_PATH_IS_APP_DATA",
    "F82_LEGAL_EMAIL_IS_PRESERVED",
    "F83_FULL_PROCESS_ENV_SPAN", "F84_TEST_SYMBOL_NOT_ENV_COMPATIBILITY",
    "F85_PROSE_PUNCTUATION_NOT_IN_IDENTIFIER",
    "F86_HEREDOC_SUCCESS_IS_VISIBLE", "F87_WORKFLOW_COMMENT_IS_VISIBLE",
    "F88_MOBILE_SHARE_TEXT_IS_VISIBLE", "F89_CANONICAL_DTO_TEXT_IS_DOCUMENTATION",
    "F90_FULL_DEEP_LINK_SCHEME", "F91_DOT_MARKER_IS_APP_DATA", "F92_PERSISTED_KEY_IS_APP_DATA",
    "F93_COMPOSE_PROJECT_NAME_STRUCTURAL", "F94_PUBSPEC_DESCRIPTION_VISIBLE",
    "F95_API_TAG_DESCRIPTION_VISIBLE", "F96_COMPOSE_COMMENT_VISIBLE", "F97_SHELL_LOG_VISIBLE_WITH_ENV",
    "F98_BARE_DEEP_LINK_SCHEME_COMPATIBILITY", "F99_WELL_KNOWN_ROUTE_IS_COMPATIBILITY",
    "F100_I18N_PRECEDENCE_IS_VISIBLE", "F101_BUILD_PATH_NOT_APP_DATA", "F102_DOT_MARKER_BOUNDARY",
    "F103_CLOSING_TAG_NOT_APP_DATA", "F104_DART_IMPORT_NOT_APP_DATA",
    "F105_WEBLATE_COMPONENT_NOT_APP_DATA",
    "F106_SCHEDULER_KEYS_ARE_APP_DATA",
    "F107_CODEGEN_OUTPUT_PATH_IS_BUILD", "F108_APP_STORE_URL_IS_COMPATIBILITY",
    "F109_USER_AGENT_IS_COMPATIBILITY",
}


class Failure(RuntimeError):
    pass


def load(name: str) -> object:
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def is_text(path: Path) -> bool:
    if path.name == ".DS_Store" or path.stat().st_size > 20_000_000:
        return False
    with path.open("rb") as handle:
        return b"\0" not in handle.read(8192)


def is_brand_asset(rel: str) -> bool:
    path = Path(rel)
    if path.suffix.lower() not in BRAND_ASSET_SUFFIXES:
        return False
    low = rel.lower()
    if path.suffix.lower() in ASSET_SUFFIXES and IDENTITY.search(rel):
        return True
    role = r"(?i)(immich[-_ ]?logo|logo|favicon|app[-_ ]?icon|apple[-_ ]?icon|manifest[-_ ]?icon|splash|brand|wordmark|ic_launcher|notification_icon|screenshot|launchimage|launchscreen|launch[_-]?background|launchbackground)"
    if path.suffix.lower() in {".json", ".xml"}:
        asset_root = any(token in low for token in ("/assets/", "/res/", ".xcassets/", "/static/img/", "/design/"))
        return asset_root and (bool(re.search(role, path.name)) or any(token in low for token in (".appiconset/", ".imageset/")))
    return bool(re.search(role, rel)) or any(
        token in low for token in ("appicon.appiconset", "/phonescreenshots/", "/metadata/android/", "/fastlane/metadata/", "/mipmap-")
    )


def is_legal_file(rel: str) -> bool:
    path = Path(rel); stem = path.stem.lower()
    return stem in {"license", "licence", "notice", "copying", "copyright", "authors", "third-party-notices", "third_party_notices",
                    "privacy-policy", "privacy_policy", "terms-of-service", "terms_of_service", "terms"} or any(
        token in rel.lower() for token in ("/licenses/", "/licences/", "/legal/")
    ) or rel.lower().endswith("mobile/lib/utils/licenses.dart")


def legal_matches(rel: str, line: str) -> list[str]:
    explicit = re.compile(r"(?i)(\bcopyright\b|\battribution\b|\btrademark\b|\bSPDX\b|\bthird[- ]party\s+(?:licen[cs]e|notice))")
    prose = re.compile(r"(?i)(\blicen[cs]ed\s+under\b|\blicen[cs]e\s+(?:terms|notice|file)\b|\bopen[- ]source\s+licen[cs]e\b|\bsoftware\s+licen[cs]e\b)")
    matches = [m.group(0) for m in explicit.finditer(line)] + [m.group(0) for m in prose.finditer(line)]
    if Path(rel).name.lower() in {"package.json", "pyproject.toml", "pubspec.yaml"}:
        matches += [m.group(0) for m in re.finditer(r"(?i)[\"']?(?:author|authors|license|licence)[\"']?\s*[:=]", line)]
    return matches


def symbol_only(line: str) -> bool:
    stripped = line.strip()
    return bool(re.match(r"(?:import|export|type|interface|enum)\b", stripped)) or bool(re.search(r"(?<![\"'])\b(?:Immich[A-Z][A-Za-z0-9]*|IMMICH_[A-Z0-9_]+)\b(?![\"'])", stripped)) and not bool(re.search(r"[>\"']\s*Immich(?:\s|[<\"'])", stripped, re.I))


def expected_identity(rel: str, line: str, start: int, end: int) -> tuple[str, str, str | None, str | None]:
    prefix = line[:start]; raw_token = line[start:end]; token = raw_token.lower(); low = rel.lower()
    spans = [m.span() for m in re.finditer(r"(?i)(?:class(?:Name)?|id|style)\s*=\s*[\"'][^\"']*[\"']|class:[^\s=>]+", line)]
    direct_style = token.startswith(("immich-dark", "immich-light", "immich-scrollbar", "immich-form", "immich-ui", "immich-asset")) or line[max(0,start-2):start] in {"--", ".", "#"} or bool(re.search(r"(?i)(?:bg|text|border|outline|ring|stroke|fill)[-:\w]*-$", prefix))
    quoted_spans = [m.span() for m in re.finditer(r"[\"'][^\"']*[\"']", line)]
    in_quoted = any(left <= start < right for left, right in quoted_spans)
    module_syntax = bool(re.match(r"^\s*import\b", line)) or bool(re.match(r"^\s*export\b.*\bfrom\s*[\"']", line)) or bool(re.search(r"\b(?:require|import)\s*\(\s*[\"']", line))
    module_specifier = in_quoted and module_syntax
    if "/i18n/" in low and low.endswith(".json"):
        return "USER_VISIBLE", "RENAME_TO_LAMHA", "WP-I1-002", "localized-copy"
    if TEST_PATH.search(rel):
        token_compat = raw_token.startswith("IMMICH_") or bool(re.fullmatch(r"(?i)(?:[a-z0-9-]+\.)*immich\.(?:app|cloud)", raw_token)) or prefix.lower().endswith("x-")
        if token_compat: return "TEST_ONLY", "PRESERVE_TECHNICAL_COMPATIBILITY", "WP-I1-003", None
        if any(a <= start < b for a, b in spans) or direct_style or module_specifier or re.match(r"immich[A-Z]", raw_token): return "TEST_ONLY", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003", None
        if VISIBLE.search(line) or re.search(r"(?i)[\"'](?:Welcome to |About )?Immich(?:\s|[\"'])", line): return "TEST_ONLY", "RENAME_TO_LAMHA", "WP-I1-002", None
        return "TEST_ONLY", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003", None
    if is_legal_file(rel):
        return "UPSTREAM_ATTRIBUTION", "PRESERVE_UPSTREAM_ATTRIBUTION", "WP-I1-005", "legal-document-identity"
    if raw_token.lower().startswith("immich://"):
        return "COMPATIBILITY", "PRESERVE_TECHNICAL_COMPATIBILITY", "WP-I1-003", "deep-link-scheme"
    if raw_token.startswith(".immich") or "::" in raw_token or re.match(r"(?i)(?:DCIM|Pictures|Documents)/Immich", raw_token) or re.match(r"(?i)immich(?::|/)", raw_token):
        return "FILESYSTEM_DATA_PATH", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003", "persisted-storage-name"
    if raw_token.startswith(("/", "~/")):
        if raw_token.lower().startswith("/.well-known/"):
            return "COMPATIBILITY", "PRESERVE_TECHNICAL_COMPATIBILITY", "WP-I1-003", "well-known-route"
        if raw_token.lower().startswith("~/.config/"):
            return "FILESYSTEM_DATA_PATH", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003", "filesystem-path"
        if re.search(r"(?i)https?://[^\s\"']*$", prefix): return "COMPATIBILITY", "PRESERVE_TECHNICAL_COMPATIBILITY", "WP-I1-003", "external-url-path"
        build_context = any(token in low for token in ("/.github/", "/open-api/", "package.json", "mise.toml", "/scripts/", "/bin/")) or bool(re.search(r"(?i)(openapi|source|output|artifact|template|image)", line))
        route_context = bool(DOC_PATH.search(rel)) or bool(re.search(r"(?i)(route|url|endpoint|href|src=)", line))
        if build_context: return "BUILD", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003", "build-artifact-path"
        if route_context: return "COMPATIBILITY", "PRESERVE_TECHNICAL_COMPATIBILITY", "WP-I1-003", "route-resource-path"
        return "FILESYSTEM_DATA_PATH", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003", "filesystem-path"
    if re.fullmatch(r"(?i)(?:[a-z][a-z0-9-]*\.)+immich(?:\.[a-z0-9_-]+)*", raw_token):
        return ("COMPATIBILITY", "PRESERVE_TECHNICAL_COMPATIBILITY", "WP-I1-003", "uri-scheme") if line[end:].startswith(":/") else ("PACKAGE_IDENTITY", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003", "reverse-dns-identifier")
    if re.search(r"(?i)(?:^|\s)(?:-v|--volume(?:=)?)\s*$", prefix):
        return "FILESYSTEM_DATA_PATH", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003", "container-volume"
    if any(a <= start < b for a, b in spans) or direct_style:
        return "INTERNAL_RUNTIME", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003", "style-token"
    if module_specifier and (raw_token.lower().startswith("@immich/") or line[max(0, start - 8):start].lower().endswith("package:") or "immich" in raw_token.lower()):
        return "PACKAGE_IDENTITY", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003", "module-specifier"
    env_context = low.endswith((".env", "example.env")) or any(token in low for token in ("docker-compose", "/env.", "/env/", ".devcontainer")) or bool(re.search(r"(?i)(?:process|import\.meta)\.env|\benv\s*\(|\$\{?IMMICH_|^\s*IMMICH_[A-Z0-9_]+\s*=", line)) or bool(DOC_PATH.search(rel))
    if raw_token.startswith("IMMICH_") and env_context:
        return "COMPATIBILITY", "PRESERVE_TECHNICAL_COMPATIBILITY", "WP-I1-003", "environment-contract"
    if re.match(r"immich[A-Z]", raw_token) and not TEST_PATH.search(rel):
        return "INTERNAL_RUNTIME", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003", "code-symbol"
    if raw_token.lower() == "immich" and (re.search(r"(?i)\.name\s*\(\s*[\"']$", prefix) or re.search(r"(?i)--filter\s+$", prefix)):
        return "PACKAGE_IDENTITY", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003", "command-package-identity"
    if raw_token.lower() == "immich" and re.search(r"(?i)(\.scheme\b|android:scheme|CFBundleURLSchemes|URL\s*scheme)", line):
        return "COMPATIBILITY", "PRESERVE_TECHNICAL_COMPATIBILITY", "WP-I1-003", "deep-link-scheme"
    if raw_token.lower() == "immich" and ("db.repository" in low or re.search(r"(?i)(sqlite|databaseName|driftDatabase|export_)", line)):
        return "FILESYSTEM_DATA_PATH", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003", "database-storage-name"
    if re.search(r"(?i)https?://[^\s\"']*$", prefix):
        return "COMPATIBILITY", "PRESERVE_TECHNICAL_COMPATIBILITY", "WP-I1-003", "external-url"
    if "user_agent" in low or re.search(r"(?i)user[-_ ]agent", line):
        return "COMPATIBILITY", "PRESERVE_TECHNICAL_COMPATIBILITY", "WP-I1-003", "user-agent"
    if "/mobile/pigeon/" in low and in_quoted and re.search(r"(?i)\.g\.(?:kt|swift|dart)[\"']?", line):
        return "BUILD", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003", "codegen-output-path"
    if re.search(r"(?i)(kotlinOut|dartOut|swiftOut|javaOut|outputPath|generatedPath)\s*:", line):
        return "BUILD", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003", "codegen-output-path"
    documentation = bool(DOC_PATH.search(rel)) or low.endswith((".md", ".mdx"))
    inline_code = any(left <= start < right for left, right in (m.span() for m in re.finditer(r"`[^`]+`", line)))
    technical_prefix = bool(re.search(r"(?i)(?:image:|docker\s+(?:run|pull)|container_name:|package\s+)\s*$", prefix))
    technical_doc = documentation and (inline_code or bool(re.match(r"(?i)\s*(?:client_id|database|DB_[A-Z_]+|cd\s+|[/~.]|[A-Z_]+=)", line)) or bool(re.search(r"(?i)(/\.well-known/|/workspaces/|\.config/|:\s*[\"']immich)", line)))
    external_url = bool(re.search(r"(?i)https?://[^\s\"']*$", prefix))
    if documentation and raw_token.lower() == "immich" and (technical_doc or technical_prefix):
        return "COMPATIBILITY", "PRESERVE_TECHNICAL_COMPATIBILITY", "WP-I1-003", "documented-technical-identifier"
    if documentation and external_url:
        return "COMPATIBILITY", "PRESERVE_TECHNICAL_COMPATIBILITY", "WP-I1-003", "external-url"
    product_domain = bool(re.fullmatch(r"(?i)(?:[a-z0-9-]+\.)*immich\.(?:app|cloud)", raw_token))
    if documentation and not is_legal_file(rel) and (raw_token.lower() == "immich" or product_domain) and not inline_code and not technical_prefix:
        return "DOCUMENTATION", "RENAME_TO_LAMHA", "WP-I1-002", "published-product-copy"
    rendered_source = low.endswith((".svelte", ".html", ".tsx", ".email.tsx"))
    if rendered_source and raw_token.lower() == "immich" and (in_quoted or not symbol_only(line)):
        return "USER_VISIBLE", "RENAME_TO_LAMHA", "WP-I1-002", "rendered-product-copy"
    canonical_api_copy = "/server/src/" in low and not GENERATED.search(rel) and (".describe(" in line or "description:" in line or "[ApiTag." in line or "/dtos/" in low or low.endswith("server/src/enum.ts")) and in_quoted
    if canonical_api_copy:
        return "DOCUMENTATION", "RENAME_TO_LAMHA", "WP-I1-002", "canonical-api-copy"
    mobile_human = any(ext in low for ext in (".dart", ".swift", ".kt", ".java")) and in_quoted
    shell_human = low.endswith(".sh") and bool(re.search(r"(?i)(log_message|echo|printf)", line))
    human_quoted = in_quoted and raw_token.lower() == "immich" and (mobile_human or shell_human or bool(re.search(r"(?i)(welcome|login|starting|initializ|listening|error|failed|throw|exception|compatible|export|server URL|API key|description)", line)))
    if human_quoted:
        return "USER_VISIBLE", "RENAME_TO_LAMHA", "WP-I1-002", "runtime-message"
    visible_template = any(token in low for token in ("/.github/issue_template/", "/.github/discussion_template/", "/fastlane/metadata/", "/android/metadata/")) or low.startswith("codebase/.github/issue_template/") or low.startswith("codebase/.github/discussion_template/")
    operator_output = low.endswith("install.sh") and raw_token.lower() == "immich"
    operator_instruction = low.endswith("docker/example.env") and line.lstrip().startswith("#")
    compose_instruction = "docker-compose" in low and line.lstrip().startswith("#") and raw_token.lower() == "immich"
    cli_help = "/packages/cli/" in low and in_quoted and bool(re.search(r"(?i)(server URL|API key|description|help|option)", line))
    widget_copy = ("widgetextension" in low or "/res/values/strings.xml" in low) and bool(re.search(r"(?i)(login|description|title|label|message)", line))
    workflow_label = "/.github/workflows/" in low and raw_token.lower() == "immich"
    if visible_template or operator_output or cli_help or widget_copy or workflow_label:
        return "USER_VISIBLE", "RENAME_TO_LAMHA", "WP-I1-002", "published-operator-copy"
    if operator_instruction or compose_instruction:
        return "DOCUMENTATION", "RENAME_TO_LAMHA", "WP-I1-002", "operator-instruction"
    attrs = list(re.finditer(r"android:(label|name)\s*=\s*[\"'][^\"']*$", prefix, re.I))
    if attrs:
        attr = attrs[-1].group(1).lower()
        return ("USER_VISIBLE", "RENAME_TO_LAMHA", "WP-I1-002", "android:label") if attr == "label" else ("PACKAGE_IDENTITY", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003", "android:name")
    key = re.search(r'[\"\'](name|short_name)[\"\']\s*:\s*[\"\'][^\"\']*$', prefix, re.I)
    if key and low.endswith("manifest.json"):
        return "USER_VISIBLE", "RENAME_TO_LAMHA", "WP-I1-002", key.group(1).lower()
    generated = bool(GENERATED.search(rel)); test = bool(TEST_PATH.search(rel))
    if "/i18n/" in low and low.endswith(".json"): return "USER_VISIBLE", "RENAME_TO_LAMHA", "WP-I1-002", None
    if is_legal_file(rel) or LEGAL_IDENTITY.search(line):
        return ("UPSTREAM_ATTRIBUTION", "PRESERVE_UPSTREAM_ATTRIBUTION", "WP-I1-005", None) if UPSTREAM.search(line) or "license" in low or "licence" in low else ("LEGAL", "PRESERVE_LEGAL", "WP-I1-005", None)
    if generated: return "GENERATED", "PRESERVE_TECHNICAL_COMPATIBILITY", "WP-I1-003", None
    if test:
        if VISIBLE.search(line) or re.search(r"(?i)[\"'](?:Welcome to |About )?Immich(?:\s|[\"'])", line): return "TEST_ONLY", "RENAME_TO_LAMHA", "WP-I1-002", None
        if COMPAT_LINE.search(line): return "TEST_ONLY", "PRESERVE_TECHNICAL_COMPATIBILITY", "WP-I1-003", None
        return "TEST_ONLY", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003", None
    if symbol_only(line): return "INTERNAL_RUNTIME", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003", None
    if PACKAGE_LINE.search(line) or low.endswith(("package.json", "pubspec.yaml", "androidmanifest.xml", "info.plist")):
        return ("DISTRIBUTION" if any(x in low for x in ("docker", "compose", "release", "fastlane", "helm")) else "PACKAGE_IDENTITY", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003", None)
    if DATA_LINE.search(line): return "FILESYSTEM_DATA_PATH", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003", None
    if COMPAT_LINE.search(line): return "COMPATIBILITY", "PRESERVE_TECHNICAL_COMPATIBILITY", "WP-I1-003", None
    if re.search(r"[\"'`]([^\"'`]*\bImmich(?:\s+[A-Z][A-Za-z]+|\s)[^\"'`]*)[\"'`]", line): return "USER_VISIBLE", "RENAME_TO_LAMHA", "WP-I1-002", None
    if documentation:
        return ("UPSTREAM_ATTRIBUTION", "PRESERVE_UPSTREAM_ATTRIBUTION", "WP-I1-005", None) if UPSTREAM.search(line) else ("DOCUMENTATION", "RENAME_TO_LAMHA", "WP-I1-002", None)
    if VISIBLE.search(line) or low.endswith((".svelte", ".html", ".tsx", ".email.tsx")): return "USER_VISIBLE", "RENAME_TO_LAMHA", "WP-I1-002", None
    if any(x in low for x in ("build", "mise", "vite", "webpack", "scripts/", "bin/")): return "BUILD", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003", None
    return "INTERNAL_RUNTIME", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003", None


def image_dimensions(path: Path) -> tuple[object, object, object | None]:
    data = path.read_bytes(); suffix = path.suffix.lower()
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24: return (*struct.unpack(">II", data[16:24]), None)
    if data[:6] in {b"GIF87a", b"GIF89a"} and len(data) >= 10: return (*struct.unpack("<HH", data[6:10]), None)
    if data.startswith(b"\x00\x00\x01\x00") and len(data) >= 8: return (data[6] or 256, data[7] or 256, None)
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        chunk = data[12:16]
        if chunk == b"VP8X" and len(data) >= 30: return (1 + int.from_bytes(data[24:27], "little"), 1 + int.from_bytes(data[27:30], "little"), None)
        if chunk == b"VP8 ":
            pos = data.find(b"\x9d\x01\x2a", 20)
            if pos >= 0: return (int.from_bytes(data[pos+3:pos+5], "little") & 0x3FFF, int.from_bytes(data[pos+5:pos+7], "little") & 0x3FFF, None)
        if chunk == b"VP8L" and len(data) >= 25:
            bits = int.from_bytes(data[21:25], "little"); return ((bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1, None)
    if data.startswith(b"\xff\xd8"):
        pos = 2
        while pos + 9 < len(data):
            if data[pos] != 0xFF: pos += 1; continue
            marker = data[pos + 1]; pos += 2
            if marker in {0xD8, 0xD9}: continue
            length = int.from_bytes(data[pos:pos+2], "big")
            if marker in set(range(0xC0, 0xC4)) | set(range(0xC5, 0xC8)) | set(range(0xC9, 0xCC)) | set(range(0xCD, 0xD0)):
                return (int.from_bytes(data[pos+5:pos+7], "big"), int.from_bytes(data[pos+3:pos+5], "big"), None)
            pos += max(length, 2)
    if suffix == ".json":
        payload = json.loads(data.decode("utf-8"))
        if isinstance(payload, dict) and isinstance(payload.get("w"), (int, float)) and isinstance(payload.get("h"), (int, float)): return payload["w"], payload["h"], None
        return "manifest-defined variants", "manifest-defined variants", None
    if suffix == ".xml":
        text = data[:10000].decode("utf-8", "ignore"); w = re.search(r'(?:android:)?(?:width|viewportWidth)=["\']([^"\']+)', text); h = re.search(r'(?:android:)?(?:height|viewportHeight)=["\']([^"\']+)', text)
        return w.group(1) if w else "resource-defined", h.group(1) if h else "resource-defined", None
    if suffix == ".svg":
        text = data[:10000].decode("utf-8", "ignore"); w = re.search(r'\bwidth=["\']([^"\']+)', text); h = re.search(r'\bheight=["\']([^"\']+)', text); v = re.search(r'\bviewBox=["\']([^"\']+)', text)
        view = v.group(1) if v else None; parts = re.split(r"[ ,]+", view.strip()) if view else []
        return (w.group(1) if w else parts[2] if len(parts) == 4 else "scalable/unspecified", h.group(1) if h else parts[3] if len(parts) == 4 else "scalable/unspecified", view)
    return (None, None, None)


def structural_expected(rel: str, line: str, next_line: str) -> list[tuple[str, str, str, str]]:
    low = rel.lower()
    expected: list[tuple[str, str, str, str]] = []
    plist = re.search(r"<key>(CFBundleExecutable|CFBundleDisplayName|CFBundleName|CFBundleIdentifier|CFBundleURLSchemes)</key>", line)
    if plist:
        key = plist.group(1); visible = key == "CFBundleDisplayName"; compatibility = key == "CFBundleURLSchemes"
        expected.append((key, "USER_VISIBLE" if visible else "COMPATIBILITY" if compatibility else "PACKAGE_IDENTITY", "WP-I1-002" if visible else "WP-I1-003", "RENAME_TO_LAMHA" if visible else "PRESERVE_TECHNICAL_COMPATIBILITY" if compatibility else "MIGRATE_TO_LAMHA_IDENTIFIER"))
    if low.endswith(".pbxproj"):
        match = re.search(r"\b(PRODUCT_BUNDLE_IDENTIFIER|PRODUCT_NAME|TARGET_NAME|CUSTOM_GROUP_ID|INFOPLIST_KEY_CFBundleDisplayName)\s*=\s*([^;]+);", line)
        if not match: match = re.search(r"\b(productName|name)\s*=\s*(Runner|WidgetExtension|ShareExtension);", line)
        if match:
            visible = match.group(1) == "INFOPLIST_KEY_CFBundleDisplayName"
            expected.append((match.group(1), "USER_VISIBLE" if visible else "PACKAGE_IDENTITY", "WP-I1-002" if visible else "WP-I1-003", "RENAME_TO_LAMHA" if visible else "MIGRATE_TO_LAMHA_IDENTIFIER"))
    if low.endswith("package.json"):
        match = re.search(r'^\s*"(name|bin)"\s*:\s*(.+?)[,]?\s*$', line)
        if match:
            branded = "immich" in match.group(2).lower(); is_bin = match.group(1) == "bin"
            expected.append((f"package.json:{match.group(1)}", "PACKAGE_IDENTITY" if branded or is_bin else "INTERNAL_RUNTIME",
                             "WP-I1-003" if branded or is_bin else None,
                             "MIGRATE_TO_LAMHA_IDENTIFIER" if branded or is_bin else "NOT_PRODUCT_IDENTITY"))
    if low.endswith("pubspec.yaml"):
        match = re.search(r"^name:\s*(\S+)", line)
        if match:
            branded = "immich" in match.group(1).lower()
            expected.append(("pubspec:name", "PACKAGE_IDENTITY" if branded else "INTERNAL_RUNTIME",
                             "WP-I1-003" if branded else None, "MIGRATE_TO_LAMHA_IDENTIFIER" if branded else "NOT_PRODUCT_IDENTITY"))
        description = re.search(r"^description:\s*(.+)", line)
        if description and "immich" in description.group(1).lower(): expected.append(("pubspec:description", "USER_VISIBLE", "WP-I1-002", "RENAME_TO_LAMHA"))
    if low.endswith(("build.gradle", "build.gradle.kts")):
        match = re.search(r"\b(applicationId|applicationIdSuffix|namespace)\s*(?:=\s*)?[\"']([^\"']+)", line)
        if match: expected.append((f"android:{match.group(1)}", "PACKAGE_IDENTITY", "WP-I1-003", "MIGRATE_TO_LAMHA_IDENTIFIER"))
    if low.endswith("androidmanifest.xml"):
        for match in re.finditer(r"android:(label|name)\s*=\s*[\"']([^\"']+)", line, re.I):
            label = match.group(1).lower() == "label"; branded_label = label and "immich" in match.group(2).lower()
            app_owned = (not label) and ("immich" in match.group(2).lower() or match.group(2).startswith("."))
            expected.append((f"android:{match.group(1).lower()}", "USER_VISIBLE" if branded_label else "PACKAGE_IDENTITY" if app_owned else "INTERNAL_RUNTIME",
                             "WP-I1-002" if branded_label else "WP-I1-003" if app_owned else None,
                             "RENAME_TO_LAMHA" if branded_label else "MIGRATE_TO_LAMHA_IDENTIFIER" if app_owned else "NOT_PRODUCT_IDENTITY"))
    if Path(rel).name.lower().startswith("dockerfile"):
        match = re.match(r"\s*(ENTRYPOINT|CMD)\s+(.+)", line, re.I)
        if match:
            app_owned = "immich" in match.group(2).lower()
            expected.append((f"docker:{match.group(1).upper()}", "DISTRIBUTION" if app_owned else "COMPATIBILITY", "WP-I1-003",
                             "MIGRATE_TO_LAMHA_IDENTIFIER" if app_owned else "PRESERVE_TECHNICAL_COMPATIBILITY"))
    if re.search(r"(?i)docker-compose.*\.ya?ml$", rel):
        project_name = re.match(r"^name:\s*([^\s#]+)", line)
        if project_name: expected.append(("compose:project-name", "DISTRIBUTION", "WP-I1-003", "MIGRATE_TO_LAMHA_IDENTIFIER"))
        match = re.match(r"^\s{2}([a-zA-Z0-9_.-]+):\s*$", line)
        if match and match.group(1) not in {"services", "volumes", "networks", "configs", "secrets"}:
            value = match.group(1); app_owned = "immich" in value.lower() or value.lower() in {"server", "web", "machine-learning", "machine_learning"}
            expected.append(("compose:application-service" if app_owned else "compose:external-infrastructure",
                             "DISTRIBUTION" if app_owned else "COMPATIBILITY", "WP-I1-003",
                             "MIGRATE_TO_LAMHA_IDENTIFIER" if app_owned else "PRESERVE_TECHNICAL_COMPATIBILITY"))
    return expected


def expected_structural_values(rel: str, line: str, next_line: str, key: str) -> set[str]:
    low = rel.lower(); values: set[str] = set()
    if key.startswith("CFBundle"):
        match = re.search(r"<(?:string|array)>(.*?)</(?:string|array)>", next_line)
        values.add(match.group(1) if match else next_line.strip())
    elif low.endswith(".pbxproj"):
        match = re.search(rf"\b{re.escape(key)}\s*=\s*([^;]+);", line)
        if match: values.add(match.group(1).strip().strip('"'))
    elif key.startswith("package.json:"):
        match = re.search(r'^\s*"(?:name|bin)"\s*:\s*(.+?)[,]?\s*$', line)
        if match: values.add(match.group(1))
    elif key == "pubspec:name":
        match = re.search(r"^name:\s*(\S+)", line)
        if match: values.add(match.group(1))
    elif key == "pubspec:description":
        match = re.search(r"^description:\s*(.+)", line)
        if match: values.add(match.group(1))
    elif key.startswith("android:"):
        attr = key.split(":", 1)[1]
        values.update(match.group(1) for match in re.finditer(rf"android:{re.escape(attr)}\s*=\s*[\"']([^\"']+)", line, re.I))
        if not values:
            match = re.search(rf"\b{re.escape(attr)}\s*(?:=\s*)?[\"']([^\"']+)", line)
            if match: values.add(match.group(1))
    elif key.startswith("docker:"):
        match = re.match(r"\s*(?:ENTRYPOINT|CMD)\s+(.+)", line, re.I)
        if match: values.add(match.group(1))
    elif key.startswith("compose:"):
        match = re.match(r"^name:\s*([^\s#]+)", line) if key == "compose:project-name" else re.match(r"^\s{2}([a-zA-Z0-9_.-]+):\s*$", line)
        if match: values.add(match.group(1))
    return values


def expected_data_declaration(rel: str, line: str) -> tuple[str, str] | None:
    low = rel.lower()
    env = re.match(r"\s*(UPLOAD_LOCATION|DB_DATA_LOCATION|IMMICH_MEDIA_LOCATION|THUMB_LOCATION|PROFILE_LOCATION|BACKUP_LOCATION)\s*=\s*(.+)", line)
    if env: return f"env:{env.group(1)}", env.group(2).strip()
    if "docker-compose" in low and low.endswith((".yml", ".yaml")):
        volume = re.match(r"\s*-\s+([^#]+?):(/[^#\s]+)\s*$", line)
        if volume and re.search(r"(?i)(?:^|[/_.-])(data|upload|library|postgres|redis|models?|cache|thumbs?|profiles?|backups?)(?:$|[/_.-])", f"{volume.group(1)}:{volume.group(2)}"):
            return "compose:volume-mount", f"{volume.group(1).strip()}:{volume.group(2)}"
    if Path(rel).name.lower().startswith("dockerfile") and re.match(r"\s*VOLUME\s+(.+)", line, re.I):
        match = re.match(r"\s*VOLUME\s+(.+)", line, re.I); return "docker:VOLUME", match.group(1).strip()
    if low.endswith("server/src/enum.ts") and line.strip() in {"EncodedVideo = 'encoded-video',", "Library = 'library',", "Upload = 'upload',", "Profile = 'profile',", "Thumbnails = 'thumbs',", "Backups = 'backups',"}:
        match = re.match(r"\s*(EncodedVideo|Library|Upload|Profile|Thumbnails|Backups)\s*=\s*[\"']([^\"']+)", line); return f"StorageFolder:{match.group(1)}", match.group(2)
    if low.endswith("server/src/maintenance/maintenance-worker.service.ts") and re.search(r"[\"']/(?:data|usr/src/app/upload)[\"']", line):
        paths = re.findall(r"[\"'](/(?:data|usr/src/app/upload))[\"']", line); return "maintenance:legacy-storage-root", " | ".join(paths)
    return None


def expected_app_data(rel: str, line: str, value: str) -> dict[str, object]:
    low = rel.lower(); platform = "Android" if "/android/" in low else "iOS/macOS" if "/ios/" in low or "/macos/" in low else "Flutter cross-platform" if "/mobile/" in low else "Server/distribution"
    durable_mount = bool(re.search(r"(?i)(?:^|\s)(?:-v|--volume(?:=)?)\s+|volume-mount|docker-compose", line))
    temporary = bool(re.search(r"(?i)(temporary|cacheDir|cachesDirectory|[_-]cache)", line)) and not durable_mount
    result: dict[str, object] = {"platform": platform, "persistentData": not temporary}
    if temporary:
        result.update({"migrationDecision": "NO DATA MIGRATION; cache/temporary data may be recreated after identifier change",
                       "backwardCompatibility": "No durable-data compatibility obligation; avoid cache-key collision and safely ignore/clean stale cache",
                       "migrationTest": "Switch identity with a populated cache, verify startup and regeneration succeed, durable records remain intact, and no stale cache is treated as authoritative."})
    else:
        result.update({"migrationDecision": "MIGRATION REQUIRED; do not strand or overwrite existing Immich data",
                       "backwardCompatibility": "WP-I1-003 must probe the legacy location and preserve rollback/read compatibility",
                       "migrationTest": "Seed legacy-path data, migrate once, verify byte/record preservation, idempotence, rollback visibility, and no fresh writes to the legacy name."})
    return result


def baseline() -> list[dict[str, str]]:
    with BASELINE.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def exact_review_pass(text: str) -> bool:
    lines = []
    for raw in text.splitlines():
        line = raw.strip().strip("#>*- ").replace("**", "").replace("__", "").strip()
        if line:
            lines.append(line.upper())
    return "PACKAGE REVIEW PASS" in lines and not any("PACKAGE REVIEW FAIL" in line or "NOT PACKAGE REVIEW PASS" in line for line in lines)


def verify(pre_review: bool) -> dict[str, object]:
    rows = baseline()
    if len(rows) != 3697:
        raise Failure(f"BASELINE_COUNT:{len(rows)}")
    expected_paths = {row["path"] for row in rows}
    actual_paths = {
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "Codebase").rglob("*") if path.is_file() and ".git" not in path.parts
    }
    if actual_paths != expected_paths:
        raise Failure(f"CODEBASE_PATH_DRIFT:+{len(actual_paths-expected_paths)} -{len(expected_paths-actual_paths)}")
    for row in rows:
        path = ROOT / row["path"]
        if path.stat().st_size != int(row["size"]) or digest(path) != row["sha256"]:
            raise Failure(f"CODEBASE_BYTE_DRIFT:{row['path']}")

    inv = load("identity-inventory.json")
    if inv.get("packageId") != PACKAGE or not isinstance(inv.get("records"), list):
        raise Failure("INVENTORY_SCHEMA")
    records = inv["records"]
    generator_contracts = load("generator-contracts.json")
    contract_ids = {contract.get("id") for contract in generator_contracts.get("contracts", [])}
    if contract_ids != {"generator-contract:openapi", "generator-contract:dart-codegen"}:
        raise Failure("GENERATOR_CONTRACT_SET")
    for contract in generator_contracts.get("contracts", []):
        for source_root in contract.get("sourceRoots", []):
            if not (ROOT / source_root).exists():
                raise Failure(f"GENERATOR_SOURCE_ROOT_MISSING:{source_root}")
        for output_root in contract.get("outputRoots", []):
            if not (ROOT / output_root).exists():
                raise Failure(f"GENERATOR_OUTPUT_ROOT_MISSING:{output_root}")
    ids = [record.get("surfaceId") for record in records]
    if len(ids) != len(set(ids)):
        raise Failure("DUPLICATE_SURFACE_ID")
    semantic_groups: dict[tuple[str, str, str], set[tuple[object, object, object]]] = {}
    for record in records:
        locator = str(record.get("locator", "")); line_key = locator.split(":")[1] if locator.startswith("line:") else locator
        if ":identity:" in locator or ":third-party:" in locator:
            line_key = f"{line_key}:{record.get('matchStart')}:{record.get('matchEnd')}"
        key = (str(record.get("path")), line_key, str(record.get("currentValue")))
        semantic_groups.setdefault(key, set()).add((record.get("surfaceType"), record.get("disposition"), record.get("futureOwner")))
    if any(len(values) > 1 for values in semantic_groups.values()):
        raise Failure("SEMANTIC_CONFLICT")
    indexed = {(record.get("path"), record.get("locator"), record.get("surfaceType")) for record in records}
    identity_locators = {(record.get("path"), record.get("locator")) for record in records}
    identity_lines = {(record.get("path"), int(str(record.get("locator")).split(":")[1])) for record in records if ":identity:" in str(record.get("locator"))}
    identity_counts = Counter((record.get("path"), int(str(record.get("locator")).split(":")[1])) for record in records if ":identity:" in str(record.get("locator")))
    third_party_counts = Counter((record.get("path"), int(str(record.get("locator")).split(":")[1])) for record in records if ":third-party:" in str(record.get("locator")))
    structural_index = {(record.get("path"), int(str(record.get("locator")).split(":")[1]), record.get("structuralKey"), record.get("surfaceType"), record.get("futureOwner"), record.get("disposition")) for record in records if ":structural:" in str(record.get("locator"))}
    asset_variants: dict[str, list[str]] = {}
    for asset in records:
        if asset.get("surfaceType") == "ASSET" and asset.get("locator") == "file":
            asset_variants.setdefault(Path(str(asset.get("path"))).name.lower(), []).append(str(asset.get("path")))
    for record in records:
        sid = record.get("surfaceId")
        if record.get("surfaceType") not in TYPES or record.get("disposition") not in DISPOSITIONS:
            raise Failure(f"UNCLASSIFIED:{sid}")
        if record.get("binding") and record.get("disposition") != "NOT_PRODUCT_IDENTITY" and record.get("futureOwner") not in OWNERS:
            raise Failure(f"UNOWNED:{sid}")
        if record.get("surfaceType") == "FONT" and record.get("legalStatus") not in {"LICENSE_CONFIRMED", "LICENSE_REVIEW_REQUIRED"}:
            raise Failure(f"FONT_LEGAL_STATUS:{sid}")
        if record.get("surfaceType") == "ASSET" and record.get("locator") == "file":
            if record.get("width") is None or record.get("height") is None or not record.get("consumerResolution") or not isinstance(record.get("consumerPaths"), list):
                raise Failure(f"ASSET_METADATA_MISSING:{sid}")
            asset_path = ROOT / str(record.get("path")); expected_width, expected_height, expected_viewbox = image_dimensions(asset_path)
            if record.get("fileSha256") != digest(asset_path) or (record.get("width"), record.get("height"), record.get("viewBox")) != (expected_width, expected_height, expected_viewbox):
                raise Failure(f"ASSET_BYTE_METADATA:{sid}")
            variants = sorted(asset_variants.get(Path(str(record.get("path"))).name.lower(), []))
            if len(variants) > 1 and (record.get("variantGroup") != Path(str(record.get("path"))).name.lower() or record.get("variantPaths") != variants):
                raise Failure(f"ASSET_VARIANT_GROUP:{sid}")
            for consumer in record.get("consumerPaths", []):
                consumer_path = ROOT / consumer
                if not consumer_path.is_file() or Path(str(record.get("path"))).name.lower() not in consumer_path.read_text(encoding="utf-8").lower():
                    raise Failure(f"ASSET_CONSUMER_INVALID:{sid}")
            if "futo" in str(record.get("path", "")).lower() and (record.get("thirdPartyIdentity"), record.get("coordinationOwner"), record.get("legalSensitivity")) != ("FUTO", "WP-I1-005", True):
                raise Failure(f"FUTO_ASSET_CONSTRAINT:{sid}")
        if record.get("surfaceType") in {"LEGAL", "UPSTREAM_ATTRIBUTION"} and record.get("disposition") in {"RENAME_TO_LAMHA", "REPLACE_WITH_LAMHA_ASSET", "REMOVE_LATER"}:
            raise Failure(f"UNSAFE_LEGAL_ACTION:{sid}")
        if record.get("surfaceType") in {"USER_VISIBLE", "DOCUMENTATION"} and not record.get("observationContext"):
            raise Failure(f"VISIBLE_CONTEXT_MISSING:{sid}")
        if record.get("semanticKey") in {"name", "short_name", "android:label"} and (record.get("surfaceType"), record.get("disposition"), record.get("futureOwner")) != ("USER_VISIBLE", "RENAME_TO_LAMHA", "WP-I1-002"):
            raise Failure(f"VISIBLE_MANIFEST_OWNER_INVALID:{sid}")
        if record.get("surfaceType") == "TEST_ONLY" and record.get("productionSurfaceOwner") != record.get("futureOwner"):
            raise Failure(f"TEST_PRODUCTION_OWNER_MISMATCH:{sid}")
        if "/i18n/" in str(record.get("path", "")).lower() and ":identity:" in str(record.get("locator")) and record.get("surfaceType") != "USER_VISIBLE":
            raise Failure(f"I18N_NOT_VISIBLE:{sid}")
        if record.get("surfaceType") == "FILESYSTEM_DATA_PATH":
            required_data = {"platform", "currentNameOrExpression", "accessRole", "persistentData", "futureTarget", "migrationDecision", "backwardCompatibility", "migrationTest"}
            if not required_data <= set(record):
                raise Failure(f"APP_DATA_FIELDS_MISSING:{sid}")
            if re.search(r"(?i)\b(?:[a-z0-9-]+\.)+immich\.(?:app|cloud)\b", str(record.get("currentValue", ""))):
                raise Failure(f"DOMAIN_MISCLASSIFIED_AS_APP_DATA:{sid}")
        allowed = {
            "USER_VISIBLE": {("RENAME_TO_LAMHA", "WP-I1-002")},
            "DOCUMENTATION": {("RENAME_TO_LAMHA", "WP-I1-002")},
            "ASSET": {("REPLACE_WITH_LAMHA_ASSET", "WP-I1-004")},
            "FONT": {("REVIEW_REQUIRED", "WP-I1-005")},
            "LEGAL": {("PRESERVE_LEGAL", "WP-I1-005"), ("REVIEW_REQUIRED", "WP-I1-005")},
            "UPSTREAM_ATTRIBUTION": {("PRESERVE_UPSTREAM_ATTRIBUTION", "WP-I1-005")},
            "FILESYSTEM_DATA_PATH": {("MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003"), ("PRESERVE_TECHNICAL_COMPATIBILITY", "WP-I1-003")},
            "PACKAGE_IDENTITY": {("MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003")},
            "COMPATIBILITY": {("PRESERVE_TECHNICAL_COMPATIBILITY", "WP-I1-003")},
            "GENERATED": {("PRESERVE_TECHNICAL_COMPATIBILITY", "WP-I1-003")},
            "INTERNAL_RUNTIME": {("MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003"), ("NOT_PRODUCT_IDENTITY", None)},
            "BUILD": {("MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003"), ("NOT_PRODUCT_IDENTITY", None)},
            "DISTRIBUTION": {("MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003"), ("REVIEW_REQUIRED", "WP-I1-005")},
            "TEST_ONLY": {("RENAME_TO_LAMHA", "WP-I1-002"), ("MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003"), ("PRESERVE_TECHNICAL_COMPATIBILITY", "WP-I1-003")},
        }
        if (record.get("disposition"), record.get("futureOwner")) not in allowed.get(str(record.get("surfaceType")), set()):
            raise Failure(f"TYPE_OWNER_DISPOSITION_INVALID:{sid}")
        source = ROOT / str(record.get("path", ""))
        if not source.is_file():
            raise Failure(f"SOURCE_MISSING:{sid}")
        locator = str(record.get("locator", ""))
        rel = str(record.get("path", "")); low_rel = rel.lower()
        if locator == "file" and record.get("surfaceType") == "FONT":
            expected_family = source.stem.split("-")[0]
            if (record.get("currentValue"), record.get("fontFamily"), record.get("fileSha256"), record.get("legalStatus"), record.get("attributionStatus")) != (source.name, expected_family, digest(source), "LICENSE_REVIEW_REQUIRED", "REVIEW_REQUIRED"):
                raise Failure(f"FONT_FILE_PAYLOAD:{sid}")
        if locator == "file" and record.get("surfaceType") == "LEGAL":
            if (record.get("currentValue"), record.get("fileSha256"), record.get("legalStatus"), record.get("disposition"), record.get("futureOwner")) != (source.name, digest(source), "PRESERVE_VERBATIM_UNTIL_COUNSELLED_CHANGE", "PRESERVE_LEGAL", "WP-I1-005"):
                raise Failure(f"LEGAL_FILE_PAYLOAD:{sid}")
        if locator == "path":
            suffix = source.suffix.lower(); legal_path = is_legal_file(rel)
            expected_path = (rel, "ASSET", "REPLACE_WITH_LAMHA_ASSET", "WP-I1-004", True) if any(part in low_rel for part in ("/assets/", "/static/img/", "/design/")) and suffix in ASSET_SUFFIXES | {".json"} else (rel, "LEGAL", "PRESERVE_LEGAL", "WP-I1-005", True) if legal_path else (rel, "PACKAGE_IDENTITY", "MIGRATE_TO_LAMHA_IDENTIFIER", "WP-I1-003", True)
            observed_path = (record.get("currentValue"), record.get("surfaceType"), record.get("disposition"), record.get("futureOwner"), record.get("pathIdentity"))
            if observed_path != expected_path:
                raise Failure(f"PATH_CLASSIFICATION:{sid}")
        if locator == "path:executable":
            branded = "immich" in source.name.lower()
            expected_executable = (source.name, "DISTRIBUTION" if branded else "BUILD", "MIGRATE_TO_LAMHA_IDENTIFIER" if branded else "NOT_PRODUCT_IDENTITY", "WP-I1-003" if branded else None, "executable-path", "Reviewed Lamha executable name" if branded else "Keep generic tool name")
            observed_executable = (record.get("currentValue"), record.get("surfaceType"), record.get("disposition"), record.get("futureOwner"), record.get("structuralKey"), record.get("futureTarget"))
            if observed_executable != expected_executable:
                raise Failure(f"EXECUTABLE_CLASSIFICATION:{sid}")
        if locator.startswith("line:"):
            number = int(locator.split(":")[1])
            lines = source.read_text(encoding="utf-8").splitlines()
            if number < 1 or number > len(lines) or hashlib.sha256(lines[number-1].encode()).hexdigest() != record.get("lineDigest"):
                raise Failure(f"LOCATOR_DRIFT:{sid}")
            if record.get("sourceExcerpt") != lines[number-1].strip()[:1000]:
                raise Failure(f"SOURCE_EXCERPT_DRIFT:{sid}")
            line = lines[number-1]
            if ":identity:" in locator:
                start, end = record.get("matchStart"), record.get("matchEnd")
                if not isinstance(start, int) or not isinstance(end, int) or lines[number-1][start:end] != record.get("currentValue") or record.get("sourceExcerpt") != lines[number-1].strip()[:1000]:
                    raise Failure(f"IDENTITY_OCCURRENCE_DRIFT:{sid}")
                expected = expected_identity(str(record.get("path")), lines[number-1], start, end)
                if (record.get("surfaceType"), record.get("disposition"), record.get("futureOwner"), record.get("semanticKey")) != expected:
                    raise Failure(f"IDENTITY_CLASSIFICATION:{sid}")
            if ":third-party:" in locator:
                start, end = record.get("matchStart"), record.get("matchEnd")
                if not isinstance(start, int) or not isinstance(end, int) or lines[number-1][start:end] != record.get("currentValue") or record.get("thirdPartyIdentity") != "FUTO":
                    raise Failure(f"THIRD_PARTY_OCCURRENCE_DRIFT:{sid}")
                documentation_context = bool(re.search(r"(?i)(^|/)(docs?|README|CONTRIBUTING|SECURITY|CODE_OF_CONDUCT)(/|\.|$)", str(record.get("path")))) or str(record.get("path", "")).lower().endswith((".md", ".mdx"))
                legal_or_visible = documentation_context or "/emails/" in str(record.get("path", "")).lower() or "/fastlane/" in str(record.get("path", "")).lower() or bool(re.search(r"(?i)(Holdings|Distribution|label|alt=|logo|href)", lines[number-1]))
                expected_futo = ("UPSTREAM_ATTRIBUTION", "PRESERVE_UPSTREAM_ATTRIBUTION", "WP-I1-005") if legal_or_visible else ("COMPATIBILITY", "PRESERVE_TECHNICAL_COMPATIBILITY", "WP-I1-003")
                if (record.get("surfaceType"), record.get("disposition"), record.get("futureOwner")) != expected_futo:
                    raise Failure(f"THIRD_PARTY_OWNER_INVALID:{sid}")
            if ":structural:" in locator and str(record.get("currentValue")) not in expected_structural_values(str(record.get("path")), lines[number-1], lines[number] if number < len(lines) else "", str(record.get("structuralKey"))):
                raise Failure(f"STRUCTURAL_VALUE_DRIFT:{sid}")
            if locator.endswith(":app-data-declaration"):
                expected_data = expected_data_declaration(str(record.get("path")), lines[number-1])
                if not expected_data or str(record.get("currentValue")) != expected_data[1]:
                    raise Failure(f"APP_DATA_VALUE_DRIFT:{sid}")
                declaration_fields = expected_app_data(str(record.get("path")), lines[number-1], expected_data[1])
                declaration_fields.update({
                    "accessRole": "authoritative persistence-path declaration",
                    "futureTarget": "Retain stable storage path unless WP-I1-003 proves and tests a migration",
                    "migrationDecision": "PRESERVE_TECHNICAL_COMPATIBILITY; generic persistent paths are not brand-renamed",
                    "backwardCompatibility": "Existing mounts, bytes, database data, thumbnails, profiles, libraries, and backups must remain readable",
                })
                for field, expected_value in declaration_fields.items():
                    if record.get(field) != expected_value:
                        raise Failure(f"APP_DATA_DECLARATION_SEMANTICS:{sid}:{field}")
            if record.get("surfaceType") == "FILESYSTEM_DATA_PATH" and not locator.endswith(":app-data-declaration"):
                expected_fields = expected_app_data(str(record.get("path")), lines[number-1], str(record.get("currentNameOrExpression")))
                for field, expected_value in expected_fields.items():
                    if record.get(field) != expected_value:
                        raise Failure(f"APP_DATA_SEMANTICS:{sid}:{field}")
            if locator.endswith(":font-reference"):
                matches = [m.group(0) for m in FONT.finditer(line)]; value = " | ".join(dict.fromkeys(matches))
                if (record.get("currentValue"), record.get("fontFamily"), record.get("occurrenceCount"), record.get("legalStatus"), record.get("attributionStatus")) != (value, value, len(matches), "LICENSE_REVIEW_REQUIRED", "REVIEW_REQUIRED"):
                    raise Failure(f"FONT_PAYLOAD:{sid}")
            elif locator.endswith(":bundled-binary"):
                matches = [m.group(0) for m in BINARY.finditer(line)]; value = " | ".join(dict.fromkeys(matches))
                if (record.get("currentValue"), record.get("binaryName"), record.get("occurrenceCount"), record.get("legalStatus")) != (value, value, len(matches), "ATTRIBUTION_REVIEW_REQUIRED"):
                    raise Failure(f"BINARY_PAYLOAD:{sid}")
            elif locator.endswith(":binary-declaration"):
                matches = [m.group(0) for m in BINARY_DECL.finditer(line)] + [m.group(0) for m in BINARY_PACKAGE.finditer(line)]
                value = line.strip()[:1000]
                expected_payload = (value, value, value, list(dict.fromkeys(matches)), rel, True, "BINARY_NOTICE_REVIEW_REQUIRED", "WP-I1-001-RISK-BINARY-NOTICES", max(1, len(matches)))
                observed_payload = (record.get("currentValue"), record.get("binaryName"), record.get("binarySource"), record.get("matchedBinaryTokens"), record.get("distributionPath"), record.get("bundledBinaryDeclaration"), record.get("legalStatus"), record.get("noticeRecord"), record.get("occurrenceCount"))
                if observed_payload != expected_payload:
                    raise Failure(f"BINARY_DECLARATION_PAYLOAD:{sid}")
            elif locator.endswith(":legal"):
                matches = legal_matches(rel, line); value = " | ".join(dict.fromkeys(matches))
                exact = bool(re.search(r"(?i)(copyright|attribution|SPDX|trademark|third[- ]party)", line))
                if (record.get("currentValue"), record.get("occurrenceCount"), record.get("legalStatus"), record.get("disposition")) != (value, len(matches), "MUST_PRESERVE" if exact else "LEGAL_REVIEW_REQUIRED", "PRESERVE_LEGAL" if exact else "REVIEW_REQUIRED"):
                    raise Failure(f"LEGAL_PAYLOAD:{sid}")
            elif locator.endswith(":app-data"):
                matches = [m.group(0) for m in DATA_ACCESS.finditer(line)]; value = " | ".join(dict.fromkeys(matches))
                if record.get("currentValue") != value or record.get("currentNameOrExpression") != value or record.get("occurrenceCount") != len(matches):
                    raise Failure(f"APP_DATA_PAYLOAD:{sid}")
        expected_generated = bool(GENERATED.search(str(record.get("path", ""))))
        if bool(record.get("isGenerated")) != expected_generated:
            raise Failure(f"GENERATED_CLASSIFICATION_FALSE:{sid}")
        if record.get("isGenerated"):
            canonical = str(record.get("canonicalSourcePath", ""))
            if canonical.startswith("Codebase/"):
                if not (ROOT / canonical).is_file():
                    raise Failure(f"GENERATED_SOURCE_INVALID:{sid}")
            elif canonical not in contract_ids:
                raise Failure(f"GENERATED_SOURCE_INVALID:{sid}")

    # Re-discover candidate coverage from source bytes without importing the generator.
    missing = []
    expected_asset_consumers = {path: set() for paths in asset_variants.values() for path in paths}
    asset_name_re = re.compile("|".join(re.escape(name) for name in sorted(asset_variants, key=len, reverse=True)), re.I)
    for row in rows:
        rel = row["path"]
        path = ROOT / rel
        suffix = path.suffix.lower()
        if suffix in FONT_SUFFIXES and (rel, "file", "FONT") not in indexed:
            missing.append(f"FONT_FILE:{rel}")
        if is_brand_asset(rel):
            if (rel, "file", "ASSET") not in indexed:
                missing.append(f"ASSET_FILE:{rel}")
            else:
                asset_record = next(r for r in records if r.get("path") == rel and r.get("locator") == "file" and r.get("surfaceType") == "ASSET")
                if not isinstance(asset_record.get("consumerPaths"), list):
                    missing.append(f"ASSET_CONSUMERS:{rel}")
        if IDENTITY.search(rel) and not is_brand_asset(rel):
            if (rel, "path") not in identity_locators:
                missing.append(f"IDENTITY_PATH:{rel}")
        if "/bin/" in rel.lower() and suffix not in ASSET_SUFFIXES | FONT_SUFFIXES:
            expected_type = "DISTRIBUTION" if "immich" in path.name.lower() else "BUILD"
            if (rel, "path:executable", expected_type) not in indexed:
                missing.append(f"EXECUTABLE_PATH:{rel}")
        if is_legal_file(rel) and suffix not in FONT_SUFFIXES:
            if (rel, "file", "LEGAL") not in indexed:
                missing.append(f"LEGAL_FILE:{rel}")
        if not is_text(path):
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for number, line in enumerate(lines, 1):
            for asset_match in asset_name_re.finditer(line):
                candidates = set(asset_variants.get(asset_match.group(0).lower(), []))
                module = rel.split("/", 2)[1] if rel.startswith("Codebase/") and "/" in rel[9:] else ""
                same_module = {candidate for candidate in candidates if candidate.split("/", 2)[1] == module}
                resolved = same_module if len(same_module) == 1 else candidates if len(candidates) == 1 else set()
                for candidate in resolved:
                    if candidate != rel: expected_asset_consumers[candidate].add(rel)
            expected_structures = structural_expected(rel, line, lines[number] if number < len(lines) else "")
            structural_values: set[str] = set()
            for key, stype, owner, disposition in expected_structures:
                if (rel, number, key, stype, owner, disposition) not in structural_index:
                    missing.append(f"STRUCTURAL_IDENTITY:{rel}:{number}:{key}")
                structural_values.update(expected_structural_values(rel, line, lines[number] if number < len(lines) else "", key))
            if expected_data_declaration(rel, line) and (rel, f"line:{number}:app-data-declaration", "FILESYSTEM_DATA_PATH") not in indexed:
                missing.append(f"APP_DATA_DECLARATION:{rel}:{number}")
            source_identity_count = sum(match.group(0) not in structural_values for match in IDENTITY.finditer(line))
            if source_identity_count != identity_counts.get((rel, number), 0):
                missing.append(f"IDENTITY_OCCURRENCES:{rel}:{number}:{source_identity_count}")
            source_futo_count = len(list(FUTO.finditer(line)))
            if source_futo_count != third_party_counts.get((rel, number), 0):
                missing.append(f"THIRD_PARTY_OCCURRENCES:{rel}:{number}:{source_futo_count}")
            if FONT.search(line) and (rel, f"line:{number}:font-reference", "FONT") not in indexed:
                missing.append(f"FONT_REFERENCE:{rel}:{number}")
            if BINARY.search(line) and (rel, f"line:{number}:bundled-binary", "UPSTREAM_ATTRIBUTION") not in indexed:
                missing.append(f"BINARY_REFERENCE:{rel}:{number}")
            docker_declaration = path.name.lower().startswith("dockerfile") and (
                bool(re.match(r"\s*FROM\b", line, re.I)) or bool(BINARY_DECL.search(line)) or bool(BINARY_PACKAGE.search(line))
            )
            if docker_declaration and (rel, f"line:{number}:binary-declaration", "DISTRIBUTION") not in indexed:
                missing.append(f"BINARY_DECLARATION:{rel}:{number}")
            legal_file = is_legal_file(rel)
            if legal_matches(rel, line) and not legal_file and (rel, f"line:{number}:legal", "LEGAL") not in indexed:
                missing.append(f"LEGAL_REFERENCE:{rel}:{number}")
            if DATA_ACCESS.search(line) and (rel, f"line:{number}:app-data", "FILESYSTEM_DATA_PATH") not in indexed:
                missing.append(f"APP_DATA_ACCESS:{rel}:{number}")
    if missing:
        raise Failure("DISCOVERY_COVERAGE:" + ",".join(missing[:20]))
    for asset in records:
        if asset.get("surfaceType") != "ASSET" or asset.get("locator") != "file": continue
        rel = str(asset.get("path")); variants = sorted(asset_variants[Path(rel).name.lower()])
        expected_resolution = "PLATFORM_OR_MODULE_VARIANT_GROUP" if len(variants) > 1 else "EXACT_FILENAME_REFERENCE_OR_PLATFORM_PACKAGING"
        if asset.get("consumerPaths") != sorted(expected_asset_consumers[rel]) or asset.get("consumerResolution") != expected_resolution:
            raise Failure(f"ASSET_CONSUMER_SET:{asset.get('surfaceId')}")
        low = rel.lower(); platform = "Apple asset-catalog packaging" if ".xcassets/" in low else "Android resource packaging" if "/res/" in low else "Mobile store listing" if "/phonescreenshots/" in low else "Published web/docs static asset" if "/static/" in low else None
        if asset.get("platformConsumer") != platform:
            raise Failure(f"ASSET_PLATFORM_CONSUMER:{asset.get('surfaceId')}")

    summary = load("package-summary.json")
    if set(summary.get("requirements", [])) != REQS or summary.get("technicalPrerequisite") != "WP-I0-001":
        raise Failure("AUTHORITY_MISMATCH")
    if summary.get("totalSurfaces") != len(records):
        raise Failure("SUMMARY_COUNT")
    binding = sum(bool(record.get("binding")) for record in records)
    if summary.get("bindingSurfaces") != binding or summary.get("classifiedBindingSurfaces") != binding:
        raise Failure("BINDING_COUNT")
    if any(summary.get(key) != 0 for key in ("unclassifiedBindingSurfaces", "unownedRequiredTransformations", "unresolvedUnsafeLegalDeletions", "nextPackageImplementationChanges")):
        raise Failure("ZERO_INVARIANT")
    if summary.get("downstreamPackagesAuthorized") != []:
        raise Failure("EARLY_DOWNSTREAM_AUTHORIZATION")
    if summary.get("surfaceTypeCounts") != dict(sorted(Counter(str(r["surfaceType"]) for r in records).items())):
        raise Failure("TYPE_COUNTS")
    if summary.get("dispositionCounts") != dict(sorted(Counter(str(r["disposition"]) for r in records).items())):
        raise Failure("DISPOSITION_COUNTS")
    if summary.get("futureOwnerCounts") != dict(sorted(Counter(str(r["futureOwner"]) for r in records if r.get("futureOwner")).items())):
        raise Failure("OWNER_COUNTS")
    if summary.get("generatedSurfaces") != sum(bool(r.get("isGenerated")) for r in records):
        raise Failure("GENERATED_COUNT")
    completion = (OUT / "completion-evidence.md").read_text(encoding="utf-8")
    completion_fragments = {
        f"Discovered identity/legal surfaces: {len(records):,}",
        f"Binding surfaces classified: {binding:,} / {binding:,}",
        f"Negative fixtures: {len(REQUIRED_FIXTURES)} / {len(REQUIRED_FIXTURES)} PASS",
        f"Future owners: {json.dumps(dict(sorted(Counter(str(r['futureOwner']) for r in records if r.get('futureOwner')).items())), sort_keys=True)}",
        "Immutable Codebase baseline: 3,697 files, 0 added, 0 removed, 0 modified, 0 renamed",
        "Next-package implementation changes: 0",
    }
    if not all(fragment in completion for fragment in completion_fragments):
        raise Failure("COMPLETION_EVIDENCE_DRIFT")
    actual_unowned = sum(bool(r.get("binding")) and r.get("disposition") != "NOT_PRODUCT_IDENTITY" and r.get("futureOwner") not in OWNERS for r in records)
    actual_unsafe = sum(r.get("surfaceType") in {"LEGAL", "UPSTREAM_ATTRIBUTION"} and r.get("disposition") in {"RENAME_TO_LAMHA", "REPLACE_WITH_LAMHA_ASSET", "REMOVE_LATER"} for r in records)
    if actual_unowned or actual_unsafe:
        raise Failure("ACTUAL_ZERO_INVARIANT")
    derived_discovery = {
        "textLines": len({(r.get("path"), str(r.get("locator")).split(":")[1]) for r in records if ":identity:" in str(r.get("locator"))}),
        "textOccurrences": sum(1 for r in records if ":identity:" in str(r.get("locator"))),
        "brandAssetFiles": sum(r.get("surfaceType") == "ASSET" and r.get("locator") == "file" for r in records),
        "fontFiles": sum(r.get("surfaceType") == "FONT" and r.get("locator") == "file" for r in records),
        "fontReferenceLines": sum(str(r.get("locator")).endswith(":font-reference") for r in records),
        "identityPaths": sum(bool(r.get("pathIdentity")) for r in records),
        "bundledBinaryReferenceLines": sum(str(r.get("locator")).endswith(":bundled-binary") for r in records),
        "bundledBinaryDeclarationLines": sum(str(r.get("locator")).endswith(":binary-declaration") for r in records),
        "legalFiles": sum(r.get("surfaceType") == "LEGAL" and r.get("locator") == "file" for r in records),
        "legalReferenceLines": sum(str(r.get("locator")).endswith(":legal") for r in records),
        "appDataAccessLines": sum(str(r.get("locator")).endswith(":app-data") for r in records),
        "appDataDeclarationLines": sum(str(r.get("locator")).endswith(":app-data-declaration") for r in records),
        "structuralIdentitySurfaces": sum(":structural:" in str(r.get("locator")) for r in records),
        "executablePaths": sum(r.get("locator") == "path:executable" for r in records),
    }
    for key, value in derived_discovery.items():
        if summary.get("discoveryCounts", {}).get(key, 0) != value:
            raise Failure(f"DISCOVERY_COUNT:{key}")

    subset_specs = {
        "user-visible-inventory.json": {"USER_VISIBLE", "DOCUMENTATION"},
        "package-bundle-inventory.json": {"PACKAGE_IDENTITY", "BUILD", "DISTRIBUTION", "INTERNAL_RUNTIME", "COMPATIBILITY", "GENERATED", "TEST_ONLY"},
        "app-data-inventory.json": {"FILESYSTEM_DATA_PATH"},
        "brand-asset-inventory.json": {"ASSET"}, "font-inventory.json": {"FONT"},
        "legal-attribution-inventory.json": {"LEGAL", "UPSTREAM_ATTRIBUTION"},
    }
    for name, types in subset_specs.items():
        subset = load(name)
        expected = [r["surfaceId"] for r in records if r["surfaceType"] in types]
        observed = [r["surfaceId"] for r in subset.get("records", [])]
        if observed != expected or subset.get("recordCount") != len(expected):
            raise Failure(f"SUBSET_MISMATCH:{name}")
    binary = load("bundled-binary-inventory.json")
    expected_binary = [r["surfaceId"] for r in records if r.get("binaryName")]
    if binary.get("recordCount") != len(expected_binary) or [r["surfaceId"] for r in binary.get("records", [])] != expected_binary:
        raise Failure("BINARY_SUBSET_MISMATCH")
    risks = load("risk-register.json")
    font_risk = next((r for r in risks.get("risks", []) if r.get("riskId") == "WP-I1-001-RISK-FONT-LICENSING"), None)
    binary_risk = next((r for r in risks.get("risks", []) if r.get("riskId") == "WP-I1-001-RISK-BINARY-NOTICES"), None)
    futo_risk = next((r for r in risks.get("risks", []) if r.get("riskId") == "WP-I1-001-RISK-FUTO-COBRANDING"), None)
    distributed_fonts = sum(r.get("surfaceType") == "FONT" and r.get("locator") == "file" for r in records)
    font_refs = sum(r.get("surfaceType") == "FONT" and r.get("locator") != "file" for r in records)
    if not font_risk or font_risk.get("owner") != "WP-I1-005" or font_risk.get("status") != "REVIEW_REQUIRED" or font_risk.get("affectedDistributedFontFiles") != distributed_fonts or font_risk.get("affectedReferenceSurfaces") != font_refs:
        raise Failure("FONT_RISK_NOT_BOUND")
    if not binary_risk or binary_risk.get("owner") != "WP-I1-005" or binary_risk.get("status") != "REVIEW_REQUIRED" or binary_risk.get("affectedBinarySurfaces") != len(expected_binary):
        raise Failure("BINARY_RISK_NOT_BOUND")
    futo_assets = sum(r.get("surfaceType") == "ASSET" and r.get("thirdPartyIdentity") == "FUTO" for r in records)
    if not futo_risk or futo_risk.get("owner") != "WP-I1-005" or futo_risk.get("affectedAssetSurfaces") != futo_assets:
        raise Failure("FUTO_RISK_NOT_BOUND")

    fixtures = load("negative-fixture-results.json")
    if fixtures.get("status") != "PASS" or fixtures.get("passed") != fixtures.get("total") or fixtures.get("total", 0) < 14:
        raise Failure("NEGATIVE_FIXTURES")
    if set(fixtures.get("results", [{}])[0]) != {"fixtureId", "expectedError", "observedErrors", "status"}:
        raise Failure("FIXTURE_RESULT_SCHEMA")
    fixture_rows = fixtures.get("results", [])
    fixture_ids = [row.get("fixtureId") for row in fixture_rows]
    if set(fixture_ids) != REQUIRED_FIXTURES or len(fixture_ids) != len(REQUIRED_FIXTURES) or any(row.get("status") != "PASS" or not row.get("expectedError") for row in fixture_rows):
        raise Failure("FIXTURE_SET_OR_STATUS")
    report = load("verification-report.json")
    if report.get("status") != "PASS" or set(report.get("requirementResults", {})) != REQS:
        raise Failure("VERIFICATION_REPORT")
    integrity = load("codebase-integrity.json")
    if integrity.get("status") != "PASS" or any(integrity.get(key) for key in ("added", "removed", "modified", "renamed")):
        raise Failure("SAVED_CODEBASE_INTEGRITY")

    manifest = load("artifact-manifest.json")
    manifest_items = manifest.get("files", [])
    listed = {item["path"]: item for item in manifest_items}
    expected_manifest_paths = {f"graphify/13-implementation/{PACKAGE}/{name}" for name in MANIFEST_REQUIRED}
    if len(listed) != len(manifest_items) or set(listed) != expected_manifest_paths:
        raise Failure("MANIFEST_PATH_SET")
    for rel, item in listed.items():
        path = ROOT / rel
        if not path.is_file() or path.stat().st_size != item.get("size") or digest(path) != item.get("sha256"):
            raise Failure(f"MANIFEST_DRIFT:{rel}")
    changed_output = subprocess.check_output(["git", "status", "--porcelain=v1", "--untracked-files=all"], cwd=ROOT, text=True)
    changed = [line[3:].replace("\\", "/") for line in changed_output.splitlines() if line]
    outside = [path for path in changed if not path.startswith(f"graphify/13-implementation/{PACKAGE}/")]
    if outside or any(path.startswith("Codebase/") for path in changed):
        raise Failure("LIVE_SCOPE:" + ",".join(outside))
    if not pre_review:
        review = OUT / "adversarial-review.md"
        if not review.is_file() or not exact_review_pass(review.read_text(encoding="utf-8")):
            raise Failure("CURRENT_REVIEW_NOT_EXACT_PASS")
    return {"status": "PASS", "files": len(rows), "surfaces": len(records), "fixtures": fixtures["total"], "reviewRequired": not pre_review}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pre-review", action="store_true")
    args = parser.parse_args()
    try:
        result = verify(args.pre_review)
    except (Failure, OSError, ValueError, KeyError, TypeError) as error:
        print(f"PACKAGE VERIFICATION FAIL: {error}")
        raise SystemExit(1)
    print("PACKAGE VERIFICATION PASS " + json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
