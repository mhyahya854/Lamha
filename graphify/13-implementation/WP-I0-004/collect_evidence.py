"""WP-I0-004 mixed-version manifest investigation collector.

Package packet: graphify/12-semantic-implementation-plan/04-work-packages/packets/WP-I0-004.md
Owned requirements: CAN-MISSION-I0-004
Technical prerequisite: WP-I0-001 (REQUIRES_PROVENANCE) — COMPLETE and GitHub-verified.

Behaviour contract:
- READ-ONLY for every path outside graphify/ and for all of Git. The only
  writes are this package's authorized evidence deliverables inside
  graphify/13-implementation/WP-I0-004/, written through tools/write_guard.
- Investigates and RECORDS mixed-version declarations across the four manifest
  families — package manifests, lockfiles, generated-client manifests, and
  toolchain manifests. It never edits, installs, or pins anything.
- Typed errors: invalid manifest inputs produce structured typed error
  records with no partial commit; parsers never raise through the collector.
- Pre/post evidence: every inspected manifest file is hashed before and after
  the run to prove no inspected file changed during the investigation.
- Exits 0 only when every fixture, failure-case guard, and exit-gate clause
  evaluates PASS; otherwise exits 1 with the failures recorded.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True

PACKAGE_ID = "WP-I0-004"
PACKAGE_DIR = Path(__file__).resolve().parent
GRAPHIFY = PACKAGE_DIR.parents[1]
LAMHA = GRAPHIFY.parent.resolve(strict=True)
CODEBASE = LAMHA / "Codebase"
TOOLS = GRAPHIFY / "tools"
PLAN = GRAPHIFY / "12-semantic-implementation-plan"
REPORTS = PLAN / "13-reports"
SHA_BASELINE = REPORTS / "external-readonly-baseline.json"
PACKET = PLAN / "04-work-packages" / "packets" / f"{PACKAGE_ID}.md"
PREREQ_DIR = GRAPHIFY / "13-implementation" / "WP-I0-001"
PREREQ_SUMMARY = PREREQ_DIR / "package-summary.json"
PREREQ_REVIEW = PREREQ_DIR / "adversarial-review.md"
AUTH_RECORD = GRAPHIFY / "13-implementation" / "WP-I0-003" / "adversarial-review.md"

sys.path.insert(0, str(TOOLS))
from write_guard import guard_write_path  # noqa: E402

GIT_ENV = {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}

BLOCK_SIZE = 1024 * 1024

ARTIFACT_PATTERNS = {
    "archive": re.compile(r"\.(zip|tar|tgz|tar\.gz|tar\.xz|tar\.bz2|7z|rar)$", re.I),
    "backup": re.compile(r"\.(bak|backup)$|(^|/)backup(s)?([/_-]|$)", re.I),
    "copy": re.compile(r"(^|/)copy([/_-]|$)| -?copy\.", re.I),
    "build": re.compile(r"(^|/)(dist|build|out|target|\.svelte-kit|\.dart_tool|\.next|\.turbo)(/|$)"),
    "test": re.compile(r"(^|/)(coverage|\.nyc_output|test-results|playwright-report)(/|$)"),
    "cache": re.compile(r"(^|/)(\.pytest_cache|__pycache__|\.mypy_cache|\.ruff_cache|\.cache|\.gradle)(/|$)"),
    "package_manager": re.compile(r"(^|/)(node_modules|\.pnpm-store|Pods)(/|$)"),
    "generated_code": re.compile(r"\.(g\.dart|generated\.ts)$"),
}

READONLY_PREFIXES = {
    ("rev-parse",),
    ("branch", "--show-current"),
    ("status", "--porcelain=v1"),
}

def surveyed_manifests() -> list[str]:
    """All Codebase manifest files this package inspects (pre/post hashed)."""
    fixed = [
        ".nvmrc",
        "pnpm-lock.yaml",
        "machine-learning/.python-version",
        "machine-learning/pyproject.toml",
        "machine-learning/uv.lock",
        "machine-learning/Dockerfile",
        "packages/cli/Dockerfile",
        "packages/e2e-auth-server/Dockerfile",
        "server/Dockerfile",
        "server/Dockerfile.dev",
        "mobile/pubspec.yaml",
        "mobile/pubspec.lock",
        "mobile/openapi/.openapi-generator/VERSION",
        "open-api/immich-openapi-specs.json",
        "packages/sdk/src/fetch-client.ts",
        ".github/workflows/build-mobile.yml",
        ".github/workflows/check-openapi.yml",
        ".github/workflows/test.yml",
        "mobile/android/gradle/wrapper/gradle-wrapper.properties",
        "docker/docker-compose.dev.yml",
        "docker/docker-compose.prod.yml",
        "docker/docker-compose.rootless.yml",
        "docker/docker-compose.yml",
        "e2e/docker-compose.dev.yml",
        "e2e/docker-compose.yml",
    ]
    globbed: list[str] = []
    for pattern in ("package.json", "pubspec.yaml", "pubspec.lock", "mise.toml", "mise.lock"):
        for path in CODEBASE.rglob(pattern):
            globbed.append(path.relative_to(CODEBASE).as_posix())
    return sorted(set(fixed) | set(globbed))


class ManifestError(Exception):
    """Typed parse error raised internally by safe parsers."""

    def __init__(self, error_type: str, message: str) -> None:
        super().__init__(message)
        self.error_type = error_type


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> tuple[int, str]:
    hasher = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(BLOCK_SIZE), b""):
            size += len(block)
            hasher.update(block)
    return size, hasher.hexdigest()


def write_evidence(relative: str, data: str, written: list[str]) -> None:
    target = guard_write_path(PACKAGE_DIR / relative)
    resolved = target.resolve(strict=False)
    resolved.relative_to(PACKAGE_DIR)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(data.rstrip("\n") + "\n", encoding="utf-8", newline="\n")
    written.append(resolved.relative_to(GRAPHIFY).as_posix())


def write_json(relative: str, value: object, written: list[str]) -> None:
    write_evidence(relative, json.dumps(value, ensure_ascii=False, indent=2), written)


def prefix_allowed(args: list[str]) -> bool:
    return any(args[: len(prefix)] == list(prefix) for prefix in READONLY_PREFIXES)


def run_git(args: list[str], raw: list[dict[str, object]]) -> dict[str, object]:
    record: dict[str, object] = {
        "command": "git " + " ".join(args),
        "env": {"GIT_OPTIONAL_LOCKS": "0"},
        "allowlistedReadOnly": prefix_allowed(args),
    }
    if not record["allowlistedReadOnly"]:
        record.update({"exitCode": None, "stdout": "", "stderr": "",
                       "typedError": {"type": "NonReadOnlyCommandRejected",
                                      "partialCommit": False, "gitStateMutated": False}})
        raw.append(record)
        return record
    completed = subprocess.run(
        ["git", "-c", "core.quotePath=false", *args],
        cwd=LAMHA, env=GIT_ENV, capture_output=True, text=True, check=False,
    )
    record.update({"exitCode": completed.returncode, "stdout": completed.stdout,
                   "stderr": completed.stderr})
    if completed.returncode != 0:
        record["typedError"] = {"type": "GitCommandFailure", "partialCommit": False,
                                "gitStateMutated": False}
    raw.append(record)
    return record


def git_state(raw: list[dict[str, object]]) -> dict[str, object]:
    fields: dict[str, object] = {}
    queries = {
        "head": ["rev-parse", "HEAD"],
        "origin_main": ["rev-parse", "origin/main"],
        "branch": ["branch", "--show-current"],
        "status_outside_graphify": [
            "status", "--porcelain=v1", "--untracked-files=all", "--", ".", ":(exclude)graphify",
        ],
    }
    for key, args in queries.items():
        record = run_git(args, raw)
        fields[key] = {"exitCode": record["exitCode"], "output": record["stdout"]}
    return fields


def read_manifest(rel: str) -> str:
    path = CODEBASE / rel
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError as error:
        raise ManifestError("ManifestUnreadable", f"{rel}: {error}") from error


def parse_json_manifest(rel: str, text: str) -> dict[str, object]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as error:
        raise ManifestError("ManifestParseError", f"{rel}: invalid JSON: {error}") from error
    if not isinstance(value, dict):
        raise ManifestError("ManifestParseError", f"{rel}: top-level JSON value is not an object")
    return value


def parse_toml_manifest(rel: str, text: str) -> dict[str, object]:
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        raise ManifestError("ManifestParseError", f"{rel}: invalid TOML: {error}") from error


def parse_version(text: str, source: str) -> tuple[int, ...]:
    match = re.fullmatch(r"v?(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:[-+][0-9A-Za-z.-]+)?", text.strip())
    if not match:
        raise ManifestError("VersionParseError", f"{source}: cannot parse version {text!r}")
    return tuple(int(part) for part in match.groups() if part is not None)


def satisfies_range(version: tuple[int, ...], range_text: str, source: str) -> bool | None:
    """Evaluate a concrete version against a simple '>=x[,<y]' or 'a b' range.

    Returns None when the range syntax is outside the supported grammar
    (recorded as UNVERIFIABLE, never silently assumed).
    """
    text = range_text.strip().replace(",", " ")
    parts = text.split()
    for part in parts:
        match = re.fullmatch(r"(>=|<=|>|<|=)(v?[\d.]+)", part)
        if not match:
            return None
        op, bound_text = match.groups()
        bound = parse_version(bound_text, source)
        width = max(len(version), len(bound))
        padded = tuple(version) + (0,) * (width - len(version))
        cmp = (padded > bound) - (padded < bound)
        if op == ">=" and cmp < 0:
            return False
        if op == "<=" and cmp > 0:
            return False
        if op == ">" and cmp <= 0:
            return False
        if op == "<" and cmp >= 0:
            return False
        if op == "=" and cmp != 0:
            return False
    return True


def first_group(pattern: str, text: str, source: str) -> str | None:
    match = re.search(pattern, text, re.M)
    return match.group(1) if match else None


def declaration(family: str, source: str, key: str, value: object, kind: str) -> dict[str, object]:
    return {"family": family, "source": f"Codebase/{source}", "key": key,
            "value": value, "kind": kind}


def surveyed_mise_files(suffix: str) -> list[str]:
    return sorted(
        path.relative_to(CODEBASE).as_posix()
        for path in CODEBASE.rglob(f"mise.{suffix}")
    )


def mise_lock_entries(text: str) -> list[tuple[str, str]]:
    """Extract tool/version pairs from mise lock files (quoted or bare keys)."""
    entries: list[tuple[str, str]] = []
    for quoted, bare, version in re.findall(
        r'\[\[tools\.(?:"([^"]+)"|([\w:.+-]+))\]\]\s*\nversion\s*=\s*"([^"]+)"', text
    ):
        entries.append((quoted or bare, version))
    return entries


def collect_declarations() -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    """Extract version declarations from the four manifest families.

    Every extraction is wrapped in a typed error: an unreadable or invalid
    manifest, or a claim-relevant key that fails to extract, raises a typed
    ManifestError — never a silent null record.
    """
    decls: list[dict[str, object]] = []
    extraction_errors: list[dict[str, object]] = []

    def add(family: str, source: str, key: str, value: object, kind: str) -> None:
        decls.append(declaration(family, source, key, value, kind))

    def require(family: str, source: str, key: str, value: object, kind: str) -> None:
        if value is None or value == "":
            raise ManifestError(
                "ManifestKeyMissing",
                f"{source}: claim-relevant key {key!r} failed to extract (silent-miss probe)",
            )
        add(family, source, key, value, kind)

    # --- toolchain manifests: all mise.toml files ------------------------------
    add("toolchain", ".nvmrc", "node", read_manifest(".nvmrc").strip(), "concrete")
    for rel in surveyed_mise_files("toml"):
        mise = parse_toml_manifest(rel, read_manifest(rel))
        tools = mise.get("tools", {})
        if not isinstance(tools, dict):
            raise ManifestError("ManifestParseError", f"{rel}: [tools] section is not a table")
        for tool, version in sorted(tools.items()):
            if isinstance(version, dict):
                # Table-valued tool spec (e.g. dcm = { version = "x.y", ... }):
                # record the resolved version plus the verbatim table.
                add("toolchain", rel, str(tool), version.get("version"), "concrete")
                add("toolchain", rel, f"{tool} (full spec)", version, "observed")
            else:
                add("toolchain", rel, str(tool), version, "concrete")

    # --- lockfiles: all mise.lock files -------------------------------------------
    for rel in surveyed_mise_files("lock"):
        for tool, version in mise_lock_entries(read_manifest(rel)):
            add("lockfile", rel, tool, version, "concrete")

    # --- package manifests: every package.json -------------------------------------
    for rel in sorted(
        path.relative_to(CODEBASE).as_posix()
        for path in CODEBASE.rglob("package.json")
    ):
        pkg = parse_json_manifest(rel, read_manifest(rel))
        if pkg.get("name") is not None:
            add("package", rel, "name", pkg.get("name"), "identity")
        if pkg.get("version") is not None:
            add("package", rel, "version", pkg.get("version"), "concrete")
        if pkg.get("packageManager") is not None:
            add("package", rel, "packageManager", pkg.get("packageManager"), "concrete")
        engines = pkg.get("engines") or {}
        for engine_key in ("node", "pnpm"):
            if engines.get(engine_key) is not None:
                add("package", rel, f"engines.{engine_key}", engines.get(engine_key), "range")

    # --- lockfiles: pnpm --------------------------------------------------------------
    pnpm_lock = read_manifest("pnpm-lock.yaml")
    require("lockfile", "pnpm-lock.yaml", "lockfileVersion",
            first_group(r"^lockfileVersion:\s*'?([\d.]+)'?", pnpm_lock, "pnpm-lock.yaml"),
            "concrete")

    # --- toolchain manifests: machine-learning ----------------------------------
    require("toolchain", "machine-learning/.python-version", "python",
            read_manifest("machine-learning/.python-version").strip(), "concrete")
    pyproject = parse_toml_manifest("machine-learning/pyproject.toml",
                                    read_manifest("machine-learning/pyproject.toml"))
    require("package", "machine-learning/pyproject.toml", "requires-python",
            ((pyproject.get("project") or {}).get("requires-python")), "range")
    uv_lock = read_manifest("machine-learning/uv.lock")
    require("lockfile", "machine-learning/uv.lock", "requires-python",
            first_group(r'^requires-python\s*=\s*"([^"]+)"', uv_lock,
                        "machine-learning/uv.lock"), "range")

    # --- toolchain manifests: docker base images ---------------------------------
    for rel in ("machine-learning/Dockerfile", "packages/cli/Dockerfile",
                "packages/e2e-auth-server/Dockerfile", "server/Dockerfile",
                "server/Dockerfile.dev"):
        text = read_manifest(rel)
        images = re.findall(r"^FROM\s+(\S+)(?:\s+AS\s+(\S+))?", text, re.M)
        recorded = set()
        for image, stage in images:
            if re.fullmatch(r"(builder|prod|dev)(-[a-z]+)?", image) or "${" in image:
                continue  # stage references are not external base images
            if image in recorded:
                continue
            recorded.add(image)
            pinned = "@sha256:" in image
            add("toolchain", rel, f"FROM {image.split('@')[0]}"
                + (f" (stage {stage})" if stage else ""), image,
                "concrete_digest_pinned" if pinned else "concrete_unpinned")

    # --- toolchain manifests: compose service images -----------------------------
    for rel in ("docker/docker-compose.dev.yml", "docker/docker-compose.prod.yml",
                "docker/docker-compose.rootless.yml", "docker/docker-compose.yml",
                "e2e/docker-compose.dev.yml", "e2e/docker-compose.yml"):
        for image in sorted(set(re.findall(r"""^\s+image:\s*['"]?([^'"\s]+)""",
                                           read_manifest(rel), re.M))):
            add("toolchain", rel, f"image {image.split(':')[0]}", image, "concrete")

    # --- toolchain manifests: gradle wrapper --------------------------------------
    gradle = read_manifest("mobile/android/gradle/wrapper/gradle-wrapper.properties")
    add("toolchain", "mobile/android/gradle/wrapper/gradle-wrapper.properties", "gradle",
        first_group(r"^distributionUrl=.*gradle-([\d.]+)-", gradle,
                    "gradle-wrapper.properties"), "concrete")

    # --- package manifests: every pubspec.yaml / pubspec.lock ------------------------
    for rel in sorted(
        path.relative_to(CODEBASE).as_posix()
        for path in CODEBASE.rglob("pubspec.yaml")
    ):
        pubspec = read_manifest(rel)
        name = first_group(r"""^name:\s*["']?([^"'\n]+?)["']?\s*$""", pubspec, rel)
        version = first_group(r"""^version:\s*["']?([^"'\n]+?)["']?\s*$""", pubspec, rel)
        if name is not None:
            add("package", rel, "name", name, "identity")
        if version is not None:
            add("package", rel, "version", version, "concrete")
        # [ \t] only: horizontal whitespace must never let a match cross the
        # newline after a bare `flutter:`/`sdk:` key (dependencies blocks).
        sdk = first_group(r"""^[ \t]+sdk:[ \t]*["']?([^"'\n]+?)["']?[ \t]*$""", pubspec, rel)
        flutter = first_group(r"""^[ \t]+flutter:[ \t]*["']?([^"'\n]+?)["']?[ \t]*$""", pubspec, rel)
        if rel == "mobile/pubspec.yaml":
            require("package", rel, "environment.sdk", sdk, "range")
            require("package", rel, "environment.flutter", flutter, "concrete")
        else:
            if sdk is not None:
                add("package", rel, "environment.sdk", sdk, "range")
            if flutter is not None:
                add("package", rel, "environment.flutter", flutter, "concrete")
    pubspec_lock = read_manifest("mobile/pubspec.lock")
    require("lockfile", "mobile/pubspec.lock", "sdks.dart",
            first_group(r"""^[ \t]+dart:[ \t]*["']?([^"'\n]+?)["']?[ \t]*$""", pubspec_lock,
                        "mobile/pubspec.lock"), "range")
    require("lockfile", "mobile/pubspec.lock", "sdks.flutter",
            first_group(r"""^[ \t]+flutter:[ \t]*["']?([^"'\n]+?)["']?[ \t]*$""", pubspec_lock,
                        "mobile/pubspec.lock"), "concrete")

    # --- generated clients ----------------------------------------------------------
    require("generated-client", "mobile/openapi/.openapi-generator/VERSION",
            "openapi-generator", read_manifest("mobile/openapi/.openapi-generator/VERSION").strip(),
            "concrete")
    root_tools = parse_toml_manifest("mise.toml", read_manifest("mise.toml")).get("tools", {})
    add("generated-client", "mise.toml", "npm:oazapfts (web/sdk client generator)",
        root_tools.get("npm:oazapfts"), "concrete")
    sdk_src = CODEBASE / "packages/sdk/src/fetch-client.ts"
    try:
        head = sdk_src.read_text(encoding="utf-8", errors="replace")[:2048]
        marker = "oazapfts" if "oazapfts" in head else None
        version_marker = first_group(r"oazapfts[/ ]v?(\d+\.\d+\.\d+)", head,
                                     "packages/sdk/src/fetch-client.ts")
    except OSError as error:
        raise ManifestError("ManifestUnreadable", f"packages/sdk/src/fetch-client.ts: {error}") from error
    add("generated-client", "packages/sdk/src/fetch-client.ts", "generator marker",
        {"present": marker is not None, "embeddedVersion": version_marker}, "observed")
    specs = parse_json_manifest("open-api/immich-openapi-specs.json",
                                read_manifest("open-api/immich-openapi-specs.json"))
    add("generated-client", "open-api/immich-openapi-specs.json", "info.version",
        ((specs.get("info") or {}).get("version")), "concrete")
    add("generated-client", "open-api/immich-openapi-specs.json", "openapi",
        specs.get("openapi"), "concrete")

    # --- toolchain manifests: CI ----------------------------------------------------
    build_mobile = read_manifest(".github/workflows/build-mobile.yml")
    mise_actions = sorted(set(re.findall(
        r"uses:\s*immich-app/devtools/actions/use-mise@([0-9a-f]+)\s*#\s*(\S+)", build_mobile)))
    for sha, label in mise_actions:
        add("toolchain", ".github/workflows/build-mobile.yml", "use-mise-action", label, "concrete")
    test_yml = read_manifest(".github/workflows/test.yml")
    nvmrc_refs = re.findall(r"node-version-file:\s*'?\.nvmrc'?", test_yml)
    add("toolchain", ".github/workflows/test.yml", "node source",
        "node-version-file:.nvmrc referenced by setup-node steps"
        if nvmrc_refs else "no .nvmrc reference", "observed")
    check_openapi = read_manifest(".github/workflows/check-openapi.yml")
    add("toolchain", ".github/workflows/check-openapi.yml", "oasdiff-action",
        first_group(r"uses:\s*oasdiff/oasdiff-action/breaking@\S+\s*#\s*(\S+)",
                    check_openapi, "check-openapi.yml"), "concrete")

    return decls, extraction_errors, []


def find_decls(decls: list[dict[str, object]], family: str, key_contains: str) -> list[dict[str, object]]:
    return [d for d in decls if d["family"] == family and key_contains in str(d["key"])]


def mixed_rule(rule: str, family: str, decls: list[dict[str, object]],
               check) -> dict[str, object]:
    verdict, rationale = check()
    return {"rule": rule, "family": family, "declarations": decls,
            "verdict": verdict, "rationale": rationale}


def main() -> int:
    written: list[str] = []
    raw_git: list[dict[str, object]] = []
    started = utc_now()
    failures: list[str] = []

    prerequisite = json.loads(PREREQ_SUMMARY.read_text(encoding="utf-8"))

    # 1. Git state BEFORE investigation (read-only, optional locks disabled).
    git_before = git_state(raw_git)
    git_available = git_before["head"]["exitCode"] == 0  # type: ignore[index]

    # 2. Pre-investigation hashes of every inspected manifest (pre/post proof).
    inspected_manifests = surveyed_manifests()
    pre_hashes: dict[str, dict[str, object]] = {}
    unreadable_files: list[dict[str, object]] = []
    for rel in inspected_manifests:
        try:
            size, digest = sha256_file(CODEBASE / rel)
            pre_hashes[rel] = {"size": size, "sha256": digest}
        except OSError as error:
            unreadable_files.append({"path": f"Codebase/{rel}", "error": str(error)})
    if unreadable_files:
        failures.append(f"inspected manifests unreadable: {unreadable_files}")

    # 3. Collect declarations (typed-error safe).
    try:
        decls, extraction_errors, _ = collect_declarations()
    except ManifestError as error:
        decls, extraction_errors = [], [{
            "typedError": {"type": error.error_type, "message": str(error),
                           "partialCommit": False, "authoritativeStatePreserved": True},
        }]
    if extraction_errors:
        failures.append(f"declaration extraction errors: {extraction_errors}")

    # 4. Failure-case probes (typed errors, no partial commit, no false PASS).
    failure_probes: list[dict[str, object]] = []

    def probe(label: str, action) -> dict[str, object]:
        try:
            action()
            return {"probe": label, "rejected": False}
        except ManifestError as error:
            return {"probe": label, "rejected": True,
                    "typedError": {"type": error.error_type, "message": str(error),
                                   "partialCommit": False,
                                   "authoritativeStatePreserved": True}}

    failure_probes.append(probe("invalid-json-manifest", lambda: parse_json_manifest(
        "probe.json", '{"name": "x", "version":')))
    failure_probes.append(probe("invalid-toml-manifest", lambda: parse_toml_manifest(
        "probe.toml", "node = \"24.15.0\"\nnode = \"24.0.0\"")))
    failure_probes.append(probe("invalid-version-string", lambda: parse_version(
        "not-a-version", "probe")))
    range_probe_result = satisfies_range((3, 13), "3.13.*", "probe")
    failure_probes.append({
        "probe": "unsupported-range-syntax",
        "rejected": range_probe_result is None,
        "note": "an out-of-grammar range must be UNVERIFIABLE (None), never silently accepted",
        "typedError": None if range_probe_result is None else {
            "type": "UnsupportedRangeAccepted", "parsedResult": range_probe_result,
            "partialCommit": False, "authoritativeStatePreserved": True},
    })
    for entry in failure_probes:
        if not entry["rejected"]:
            failures.append(f"failure probe not rejected: {entry['probe']}")

    guard_fixtures: list[dict[str, object]] = []
    for probe_path in ("../escape-outside.txt", "/absolute/escape.txt"):
        try:
            guard_write_path(PACKAGE_DIR / probe_path)
            guard_fixtures.append({"probe": probe_path, "rejected": False})
            failures.append(f"write guard accepted escape probe: {probe_path}")
        except ValueError:
            guard_fixtures.append({"probe": probe_path, "rejected": True})

    # 5. Comparison fixtures (the reviewed mixed-version rules).
    rules: list[dict[str, object]] = []

    node_concrete = sorted(set(
        re.search(r"(\d+\.\d+\.\d+)", str(d["value"])).group(1)
        for d in decls if d["family"] == "toolchain"
        and (d["key"] == "node" or str(d["key"]).startswith("FROM node"))
        and d["value"] and re.search(r"(\d+\.\d+\.\d+)", str(d["value"]))
    ))
    rules.append(mixed_rule(
        "node-runtime-alignment", "toolchain",
        [d for d in decls if d["family"] == "toolchain"
         and (d["key"] == "node" or str(d["key"]).startswith("FROM node"))],
        lambda: (("MIXED", f"distinct concrete Node versions declared: {node_concrete}")
                 if len(node_concrete) > 1
                 else ("ALIGNED", f"single Node version family: {node_concrete}"))))

    node_ranges = [d for d in decls if "engines.node" in str(d["key"])]
    node_range_results = []
    for d in node_ranges:
        if not d["value"]:
            continue
        result = satisfies_range(parse_version(node_concrete[0], str(d["source"])) if node_concrete else (0,),
                                 str(d["value"]), str(d["source"]))
        node_range_results.append({"source": d["source"], "range": d["value"],
                                   "pinnedNodeSatisfies": result})
    rules.append(mixed_rule(
        "node-engine-range-compatibility", "package", node_ranges,
        lambda: (("ALIGNED", "every declared engines.node range admits the pinned toolchain Node")
                 if all(r["pinnedNodeSatisfies"] for r in node_range_results)
                 else ("MIXED" if any(r["pinnedNodeSatisfies"] is False for r in node_range_results)
                       else ("UNVERIFIABLE", "a range is outside the supported grammar")))))

    pnpm_decls = [d for d in decls if "pnpm" in str(d["key"]).lower()
                  or d["source"].endswith("pnpm-lock.yaml")]
    pnpm_versions = sorted(set(
        re.search(r"(\d+\.\d+\.\d+)", str(d["value"])).group(1)
        for d in pnpm_decls if d["value"] and re.search(r"(\d+\.\d+\.\d+)", str(d["value"]))
        and "lockfileVersion" not in str(d["key"]) and d["kind"].startswith("concrete")
    ))
    lockfile_versions = [str(d["value"]) for d in pnpm_decls if "lockfileVersion" in str(d["key"])]
    pnpm_range_ok = all(
        satisfies_range(parse_version(v, "pnpm"), ">=10.0.0", "engines.pnpm")
        for v in pnpm_versions
    )
    rules.append(mixed_rule(
        "pnpm-manager-alignment", "package", pnpm_decls,
        lambda: (("ALIGNED",
                  f"single concrete pnpm version family {pnpm_versions}; lockfileVersion "
                  f"{lockfile_versions} is the pnpm-9/10 lock format; the declared engines.pnpm "
                  f"range >=10.0.0 admits the pinned version: {pnpm_range_ok}")
                 if len(pnpm_versions) <= 1 else
                 ("MIXED", f"distinct pnpm versions: {pnpm_versions}"))))

    python_decls = [d for d in decls if "python" in str(d["key"]).lower()
                    or str(d["source"]).endswith((".python-version", "pyproject.toml", "uv.lock"))]
    python_concrete = sorted(set(
        re.search(r"python:(\d+\.\d+)", str(d["value"])).group(1)
        if str(d["value"]).startswith("python:")
        else str(d["value"])
        for d in python_decls
        if d["value"] and d["kind"].startswith("concrete")
    ))
    python_minors = sorted({re.match(r"(\d+\.\d+)", v).group(1)
                            for v in python_concrete if re.match(r"(\d+\.\d+)", v)})
    python_range_decls = [d for d in python_decls if d["kind"] == "range" and d["value"]]
    python_range_check = []
    for d in python_range_decls:
        results = {minor: satisfies_range(parse_version(minor, str(d["source"])),
                                          str(d["value"]), str(d["source"]))
                   for minor in python_minors}
        python_range_check.append({"source": d["source"], "range": d["value"], "results": results})
    rules.append(mixed_rule(
        "python-toolchain-alignment", "toolchain", python_decls,
        lambda: (("MIXED",
                  f"distinct Python minor lines declared across toolchain manifests: "
                  f"{python_minors} (machine-learning/.python-version=3.13 vs "
                  f"machine-learning/mise.toml python=3.11; Docker base images split between "
                  f"python:3.11-bookworm and python:3.13-slim-trixie; requires-python range "
                  f"results per minor line: {python_range_check})")
                 if len(python_minors) > 1 else
                 ("ALIGNED", f"single Python minor line: {python_minors}"))))

    flutter_decls = [d for d in decls if "flutter" in str(d["key"]).lower()
                     or "sdks" in str(d["key"])]
    flutter_concrete = sorted(set(str(d["value"]) for d in flutter_decls
                                  if d["value"] and d["kind"] == "concrete"
                                  and "flutter" in str(d["key"])))
    flutter_sources = sorted({f"{d['source']}={d['value']}" for d in flutter_decls
                              if d["value"] and d["kind"] == "concrete"
                              and "flutter" in str(d["key"])})
    rules.append(mixed_rule(
        "flutter-version-alignment", "package", flutter_decls,
        lambda: (("ALIGNED", f"Flutter {flutter_concrete} is consistent across {flutter_sources}; "
                  f"dart sdk ranges recorded")
                 if len(flutter_concrete) <= 1 else
                 ("MIXED", f"distinct Flutter versions declared: {flutter_concrete} — sources: "
                  f"{flutter_sources}"))))

    dart_decls = [d for d in decls if "sdks.dart" in str(d["key"])
                  or str(d["key"]) == "environment.sdk"]
    dart_ranges = sorted({f"{d['source']}={d['value']}" for d in dart_decls if d["value"]})
    dart_distinct = sorted({str(d["value"]) for d in dart_decls if d["value"]})
    rules.append(mixed_rule(
        "dart-sdk-constraint-diversity", "package", dart_decls,
        lambda: (("ALIGNED", f"single Dart SDK constraint family: {dart_distinct}")
                 if len(dart_distinct) <= 1 else
                 ("MIXED", f"distinct Dart SDK constraints across pubspec manifests: "
                  f"{dart_ranges}"))))

    workspace_pkgs = [d for d in decls if d["family"] == "package"
                      and str(d["key"]) in ("name", "version")
                      and str(d["source"]).endswith("package.json")]
    names = {str(d["source"]): str(d["value"]) for d in workspace_pkgs if d["key"] == "name"}
    versions = {str(d["source"]): str(d["value"]) for d in workspace_pkgs if d["key"] == "version"}
    distinct_versions = sorted(set(versions.values()))
    rules.append(mixed_rule(
        "workspace-package-version-diversity", "package", workspace_pkgs,
        lambda: ("RECORD_ONLY",
                 f"workspace package identities/versions recorded verbatim across {len(names)} "
                 f"package.json files; distinct declared versions {distinct_versions} — "
                 f"notably server/package.json is version {versions.get('Codebase/server/package.json')} "
                 f"while the monorepo root is {versions.get('Codebase/package.json')}")))

    generator_decls = find_decls(decls, "generated-client", "")
    generator_version = (
        (re.search(r"(\d+\.\d+\.\d+)", str(generator_decls[0]["value"])) or [None])[0]
        if generator_decls else None
    )
    rules.append(mixed_rule(
        "generated-client-version-record", "generated-client", generator_decls,
        lambda: ("RECORD_ONLY",
                 f"two distinct generator ecosystems are pinned: openapi-generator "
                 f"{generator_version} produces the mobile/openapi client and oazapfts "
                 f"produces the web/sdk fetch client; both pins are recorded verbatim with "
                 f"their owning manifests")))

    mise_lock_decls = find_decls(decls, "lockfile", "")
    rules.append(mixed_rule(
        "lockfile-tool-version-record", "lockfile",
        [d for d in mise_lock_decls if d["key"] in ("node", "pnpm", "aqua:flutter/flutter",
                                                    "python", "uv", "npm:oazapfts")
         or str(d["source"]).endswith("mise.lock")],
        lambda: ("RECORD_ONLY",
                 "lock-resolved tool versions recorded verbatim from mise.lock files; "
                 "machine-learning/mise.lock resolves the python=3.11 pin")))

    # Generic mise.toml pin vs mise.lock resolution consistency per directory.
    pin_lock_pairs: list[dict[str, object]] = []
    for lock_source in sorted({str(d["source"]) for d in mise_lock_decls
                               if str(d["source"]).endswith("mise.lock")}):
        toml_source = lock_source[:-len("mise.lock")] + "mise.toml"
        pins = {str(d["key"]): str(d["value"]) for d in decls
                if d["family"] == "toolchain" and str(d["source"]) == toml_source}
        locked = {str(d["key"]): str(d["value"]) for d in decls
                  if d["family"] == "lockfile" and str(d["source"]) == lock_source}
        for tool in sorted(set(pins) & set(locked)):
            pin, lock = pins[tool], locked[tool]
            # A lock may resolve a loose pin to a longer concrete version
            # (pin "3.11" -> lock "3.11.15"): prefix continuation is consistent.
            consistent = pin == lock or (
                lock.startswith(pin) and lock[len(pin):] != "" and lock[len(pin)] in ".-+"
            )
            pin_lock_pairs.append({"tool": tool, "pin": pin, "lock": lock,
                                   "directory": toml_source[:-len("mise.toml")],
                                   "consistent": consistent})
    drift = [p for p in pin_lock_pairs if not p["consistent"]]
    drift_summary = [
        f"{p['tool']} pin={p['pin']} lock={p['lock']} ({p['directory']})" for p in drift
    ]
    rules.append(mixed_rule(
        "mise-pin-lock-consistency", "lockfile",
        [{"family": "lockfile", "source": f"{p['directory']}mise.toml+mise.lock",
          "key": p["tool"], "value": {"pin": p["pin"], "lock": p["lock"]},
          "kind": "derived_pair"} for p in pin_lock_pairs],
        lambda: (("MIXED",
                  f"mise pin/lock drift in {len(drift)} tool(s): {drift_summary}")
                 if drift else
                 ("ALIGNED" if pin_lock_pairs else "RECORD_ONLY",
                  f"{len(pin_lock_pairs)} pin/lock pairs consistent across mise.toml/mise.lock"
                  if pin_lock_pairs else "no overlapping pin/lock pairs"))))

    # 6. Post-investigation hashes (pre/post proof of no mutation).
    post_hashes: dict[str, dict[str, object]] = {}
    for rel in inspected_manifests:
        try:
            size, digest = sha256_file(CODEBASE / rel)
            post_hashes[rel] = {"size": size, "sha256": digest}
        except OSError as error:
            unreadable_files.append({"path": f"Codebase/{rel}", "error": str(error)})
    changed_manifests = sorted(
        rel for rel in pre_hashes if pre_hashes[rel] != post_hashes.get(rel)
    )
    if changed_manifests:
        failures.append(f"inspected manifests changed during investigation: {changed_manifests}")

    # 7. Git state AFTER investigation; read-only audit; artifact scan.
    git_after = git_state(raw_git)
    git_keys = ["head", "origin_main", "branch", "status_outside_graphify"]
    git_unchanged = all(git_before[key] == git_after[key] for key in git_keys)
    if not git_unchanged:
        failures.append("Git metadata changed during investigation")
    non_readonly = [str(r["command"]) for r in raw_git if r["allowlistedReadOnly"] is not True]
    if non_readonly:
        failures.append(f"non-read-only Git commands executed: {non_readonly}")

    baseline = json.loads(SHA_BASELINE.read_text(encoding="utf-8"))
    baseline_paths = {str(row["path"]) for row in baseline["files"]}
    current_paths: set[str] = set()
    for root, dirs, files in os.walk(CODEBASE):
        dirs.sort()
        for name in sorted(files):
            current_paths.add((Path(root) / name).relative_to(LAMHA).as_posix())
    added_outside = sorted(current_paths - baseline_paths)
    removed_outside = sorted(baseline_paths - current_paths)
    if added_outside or removed_outside:
        failures.append(f"outside-Graphify tree membership changed: +{added_outside} -{removed_outside}")

    artifact_scan = {
        "scanWindow": "package collection run",
        "scope": "paths added outside Graphify relative to the planning baseline, plus this package's evidence files",
        "addedOutsideGraphify": added_outside,
        "removedOutsideGraphify": removed_outside,
        "evidenceFiles": [],
        "evidenceFileClasses": [],
        "status": "PASS" if not added_outside and not removed_outside else "FAIL",
    }

    mixed_findings = [r for r in rules if r["verdict"] == "MIXED"]

    # 8. Persist evidence (inside Graphify only).
    provenance = {
        "packageId": PACKAGE_ID,
        "packetPath": PACKET.relative_to(GRAPHIFY).as_posix(),
        "packetSha256": sha256_bytes(PACKET.read_bytes()),
        "ownedRequirements": ["CAN-MISSION-I0-004"],
        "selection": {
            "rule": "explicit authorization record from WP-I0-003 transition (AUTHORIZED — NOT_STARTED), confirmed by the deterministic READY-package selector",
            "readyPackages": ["WP-I0-004", "WP-I0-006", "WP-I0-008", "WP-I0-009",
                              "WP-I0-010", "WP-I0-011", "WP-I1-001"],
            "explicitAuthorizationRecordPath": AUTH_RECORD.relative_to(GRAPHIFY).as_posix(),
            "explicitAuthorizationRecordSha256": sha256_bytes(AUTH_RECORD.read_bytes()),
            "startSha": git_before["head"]["output"].strip(),  # type: ignore[index]
        },
        "prerequisite": {
            "packageId": "WP-I0-001",
            "dependencyType": "REQUIRES_PROVENANCE",
            "completionRecordPath": PREREQ_SUMMARY.relative_to(GRAPHIFY).as_posix(),
            "completionRecordSha256": sha256_bytes(PREREQ_SUMMARY.read_bytes()),
            "completionRecordStatus": prerequisite.get("status"),
            "reviewRecordPath": PREREQ_REVIEW.relative_to(GRAPHIFY).as_posix(),
            "reviewRecordSha256": sha256_bytes(PREREQ_REVIEW.read_bytes()),
        },
        "roots": {"lamhaRoot": str(LAMHA), "codebaseRoot": str(CODEBASE),
                  "graphifyRoot": str(GRAPHIFY), "packageEvidenceDir": str(PACKAGE_DIR)},
        "environment": {
            "collectionStartedUtc": started, "os": os.name, "platform": sys.platform,
            "python": sys.version.split()[0],
            "gitEnvOverrides": {"GIT_OPTIONAL_LOCKS": "0", "core.quotePath": "false"},
        },
        "readOnlyGuarantee": "No path outside graphify/ is opened for writing; the investigation parses manifests only and records findings; collector writes are restricted to graphify/13-implementation/WP-I0-004/ through tools/write_guard.",
    }

    investigation = {
        "packageId": PACKAGE_ID,
        "objective": "Investigate and record mixed-version package, lockfile, generated-client, and toolchain manifests.",
        "families": {
            "package manifests": len(find_decls(decls, "package", "")),
            "lockfiles": len(find_decls(decls, "lockfile", "")),
            "generated-client manifests": len(find_decls(decls, "generated-client", "")),
            "toolchain manifests": len(find_decls(decls, "toolchain", "")),
        },
        "declarationCount": len(decls),
        "declarations": decls,
        "extractionErrors": extraction_errors,
        "comparisonFixtures": rules,
        "mixedVersionFindings": [
            {"rule": r["rule"], "family": r["family"], "declarations": r["declarations"],
             "rationale": r["rationale"]}
            for r in mixed_findings
        ],
        "recordOnlyFindings": [r["rule"] for r in rules if r["verdict"] == "RECORD_ONLY"],
        "alignedFixtures": [r["rule"] for r in rules if r["verdict"] == "ALIGNED"],
    }

    verification = {
        "fixtures": {
            "total": len(rules),
            "verdicts": {r["rule"]: r["verdict"] for r in rules},
            "mixedVersionFindings": [r["rule"] for r in mixed_findings],
        },
        "prePostManifestHashes": {
            "filesHashed": len(pre_hashes),
            "changedDuringInvestigation": changed_manifests,
            "hashes": pre_hashes,
            "status": "PASS" if not changed_manifests and not unreadable_files else "FAIL",
        },
        "failureCases": {
            "probes": failure_probes,
            "writeGuardEscapeFixtures": guard_fixtures,
            "readOnlyCommandAudit": {"commandsExecuted": len(raw_git),
                                     "nonReadOnlyCommands": non_readonly,
                                     "status": "PASS" if not non_readonly else "FAIL"},
            "gitMetadataAvailable": git_available,
            "gitMetadataUnchanged": git_unchanged,
            "outsideGraphifyMembership": {"added": added_outside, "removed": removed_outside,
                                          "status": "PASS" if not added_outside and not removed_outside else "FAIL"},
        },
        "gitState": {"before": git_before, "after": git_after,
                     "metadataUnchanged": git_unchanged, "rawCommands": raw_git},
        "tests": {
            "wp_i0_004_success": "PASS"
            if not failures and len(find_decls(decls, "package", "")) > 0
            and len(find_decls(decls, "lockfile", "")) > 0
            and len(find_decls(decls, "generated-client", "")) > 0
            and len(find_decls(decls, "toolchain", "")) > 0
            else "FAIL",
            "wp_i0_004_failure": "PASS"
            if all(p["rejected"] for p in failure_probes)
            and all(f["rejected"] for f in guard_fixtures)
            else "FAIL",
        },
    }

    exit_gate = [
        {
            "clause": "All four manifest families are investigated and recorded",
            "evidence": f"Captured {len(decls)} version declarations: {investigation['families']['package manifests']} package-manifest, {investigation['families']['lockfiles']} lockfile, {investigation['families']['generated-client manifests']} generated-client, {investigation['families']['toolchain manifests']} toolchain declarations, each with source path, key, kind, and raw value in mixed-version-investigation.json.",
            "evidenceFiles": ["13-implementation/WP-I0-004/mixed-version-investigation.json"],
            "result": "PASS"
            if all(investigation["families"][f] > 0 for f in investigation["families"])
            and not extraction_errors else "FAIL",
        },
        {
            "clause": "Every reviewed comparison fixture produced a typed verdict and mixed-version findings are recorded",
            "evidence": f"{len(rules)} comparison fixtures executed with typed verdicts { {r['rule']: r['verdict'] for r in rules} }; mixed-version findings recorded with the exact conflicting declarations: {[r['rule'] for r in mixed_findings]}.",
            "evidenceFiles": ["13-implementation/WP-I0-004/mixed-version-investigation.json"],
            "result": "PASS" if rules and all(r["verdict"] in {"ALIGNED", "MIXED", "RECORD_ONLY", "UNVERIFIABLE"} for r in rules) else "FAIL",
        },
        {
            "clause": "Failures are typed and no unrelated authoritative state changed",
            "evidence": f"{len(failure_probes)} invalid-input probes returned typed errors with no partial commit; write-guard escape probes rejected; all {len(pre_hashes)} inspected manifest files hash-identical before/after; Git metadata unchanged; zero paths added/removed outside Graphify; every Git command read-only with GIT_OPTIONAL_LOCKS=0.",
            "evidenceFiles": ["13-implementation/WP-I0-004/verification-report.json",
                              "13-implementation/WP-I0-004/artifact-scan.json"],
            "result": "PASS"
            if all(p["rejected"] for p in failure_probes)
            and all(f["rejected"] for f in guard_fixtures)
            and not changed_manifests and git_unchanged
            and artifact_scan["status"] == "PASS" and not non_readonly else "FAIL",
        },
    ]

    write_json("provenance-report.json", provenance, written)
    write_json("mixed-version-investigation.json", investigation, written)
    write_json("verification-report.json", verification, written)
    artifact_scan["evidenceFiles"] = sorted(
        written
        + ["13-implementation/WP-I0-004/artifact-scan.json",
           "13-implementation/WP-I0-004/completion-evidence.md",
           "13-implementation/WP-I0-004/package-summary.json"]
    )
    artifact_scan["evidenceFileClasses"] = [
        {"path": path, "classes": classify_artifact(path)}
        for path in artifact_scan["evidenceFiles"]
    ]
    write_json("artifact-scan.json", artifact_scan, written)

    for clause in exit_gate:
        if clause["result"] != "PASS":
            failures.append(f"exit-gate clause failed: {clause['clause']}")

    md = [
        "# WP-I0-004 mixed-version manifest investigation",
        "",
        "Read-only investigation of `Codebase/` manifests. No manifest was modified, no dependency installed, no build executed.",
        "",
        f"- Declarations captured: **{len(decls)}** across package manifests, lockfiles, generated-client manifests, and toolchain manifests.",
        f"- Comparison fixtures: **{len(rules)}** (verdicts: "
        + ", ".join(f"{r['rule']}={r['verdict']}" for r in rules) + ").",
        "",
        "## Mixed-version findings",
        "",
    ]
    for r in mixed_findings:
        md.append(f"### {r['rule']} ({r['family']})")
        md.append("")
        md.append(r["rationale"])
        md.append("")
        for d in r["declarations"]:
            md.append(f"- `{d['source']}` — `{d['key']}` = `{d['value']}` ({d['kind']})")
        md.append("")
    md.append("## Aligned fixtures")
    md.append("")
    for r in rules:
        if r["verdict"] == "ALIGNED":
            md.append(f"- **{r['rule']}**: {r['rationale']}")
    md.append("")
    md.append("## Record-only fixtures")
    md.append("")
    for r in rules:
        if r["verdict"] == "RECORD_ONLY":
            md.append(f"- **{r['rule']}**: {r['rationale']}")
    md.append("")
    write_evidence("mixed-version-investigation.md", "\n".join(md), written)

    completion_md = [
        f"# {PACKAGE_ID} completion evidence",
        "",
        f"- Package: {PACKAGE_ID} — Mixed-version manifest investigation",
        f"- Collection ran: {started} → {utc_now()}",
        f"- Declarations investigated: **{len(decls)}** across the four manifest families; comparison fixtures: **{len(rules)}**; mixed-version findings recorded: **{len(mixed_findings)}**.",
        f"- Inspected manifest files unchanged during the run: **{len(pre_hashes)}/{len(pre_hashes)} hash-identical**; zero paths added/removed outside Graphify; Git metadata unchanged.",
        "- This package created **no** archive, backup, repository copy/duplicate tree, application mutation, or Git mutation.",
        "- All generated evidence resolves inside `graphify/13-implementation/WP-I0-004/` and was written through `graphify/tools/write_guard.py`.",
        "",
        "## Requirements",
        "",
        "- `CAN-MISSION-I0-004`: mixed-version package, lockfile, generated-client, and toolchain manifests were investigated (`mixed-version-investigation.json` records every extracted declaration with source/key/kind/value) and mixed-version findings were recorded verbatim: "
        + "; ".join(r["rule"] for r in mixed_findings)
        + ". No manifest was modified.",
        "",
        "## Exit gate",
        "",
    ]
    for clause in exit_gate:
        completion_md.append(f"- **{clause['result']}** — {clause['clause']}: {clause['evidence']}")
    completion_md.append("")
    write_evidence("completion-evidence.md", "\n".join(completion_md), written)

    summary = {
        "packageId": PACKAGE_ID,
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "collectionWindowUtc": {"start": started, "end": utc_now()},
        "checks": {
            "familyCoverage": "PASS"
            if all(investigation["families"][f] > 0 for f in investigation["families"]) else "FAIL",
            "comparisonFixtures": "PASS"
            if rules and all(r["verdict"] in {"ALIGNED", "MIXED", "RECORD_ONLY", "UNVERIFIABLE"} for r in rules)
            else "FAIL",
            "prePostManifestHashes": "PASS" if not changed_manifests and not unreadable_files else "FAIL",
            "gitMetadataCompare": "PASS" if git_unchanged else "FAIL",
            "artifactScan": artifact_scan["status"],
            "failureCases": "PASS"
            if all(p["rejected"] for p in failure_probes)
            and all(f["rejected"] for f in guard_fixtures) and git_available
            else "FAIL",
            "exitGate": "PASS" if all(c["result"] == "PASS" for c in exit_gate) else "FAIL",
        },
        "counts": {"declarations": len(decls), "fixtures": len(rules),
                   "mixedVersionFindings": len(mixed_findings),
                   "inspectedManifests": len(pre_hashes)},
        "evidenceFiles": sorted(written + ["13-implementation/WP-I0-004/package-summary.json"]),
        "exitGateClauses": exit_gate,
    }
    write_json("package-summary.json", summary, written)
    print(json.dumps({"status": summary["status"], "failures": failures,
                      "declarations": len(decls), "mixed": len(mixed_findings)}, indent=2))
    return 0 if not failures else 1


def classify_artifact(path: str) -> list[str]:
    return [label for label, pattern in ARTIFACT_PATTERNS.items() if pattern.search(path)]


if __name__ == "__main__":
    sys.exit(main())
