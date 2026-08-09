"""Execute and evidence WP-I0-007 baseline attempts inside one isolated output root."""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
import tomllib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PACKAGE_ID = "WP-I0-007"
REQUIREMENT_ID = "CAN-MISSION-I0-007"
ROOT = Path(__file__).resolve().parents[3]
GRAPHIFY = ROOT / "graphify"
PACKAGE_DIR = Path(__file__).resolve().parent
AUTHORIZATION = PACKAGE_DIR / "run-authorization.json"
ISOLATED_OUTPUT_BASE = ROOT.parent / f"{ROOT.name}-isolated-output"
BASELINE = GRAPHIFY / "13-implementation" / "WP-I0-001" / "sha256-manifest.csv"
PREREQUISITES = ("WP-I0-004", "WP-I0-005")
ISOLATION_AUTHORITY = "WP-I0-006"
OUTPUT_CLASSES = {
    "build": "build",
    "test": "test",
    "cache": "cache",
    "generated": "generated",
    "package-manager": "package-manager",
    "temporary": "temporary",
}
RUN_ID_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,63}\Z")
WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL", "CLOCK$", "CONIN$", "CONOUT$",
    *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10)),
    *(f"COM{i}" for i in "¹²³"), *(f"LPT{i}" for i in "¹²³"),
}

sys.path.insert(0, str(GRAPHIFY / "tools"))
from write_guard import write_json, write_text  # noqa: E402


class EvidenceError(ValueError):
    def __init__(self, code: str, field: str, message: str):
        super().__init__(message)
        self.code = code
        self.field = field


@dataclass(frozen=True)
class Attempt:
    id: str
    surface: str
    kind: str
    cwd: str
    argv: tuple[str, ...]
    declared: str
    source_path: str
    source_command: str
    expected_tool: str | None = None
    isolation_proven: bool = True
    blocker: str | None = None


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_reparse(path: Path) -> bool:
    try:
        return bool(path.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)
    except (AttributeError, FileNotFoundError, OSError):
        return path.is_symlink()


def strict_json_text(raw: str) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise EvidenceError("AUTHORIZATION_DUPLICATE_KEY", key, f"duplicate key: {key}")
            result[key] = value
        return result

    try:
        value = json.loads(raw, object_pairs_hook=pairs)
    except EvidenceError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError, RecursionError, ValueError) as error:
        raise EvidenceError("AUTHORIZATION_JSON_INVALID", "$", str(error)) from error
    if not isinstance(value, dict):
        raise EvidenceError("AUTHORIZATION_TYPE_INVALID", "$", "authorization must be an object")
    return value


def strict_json(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise EvidenceError("AUTHORIZATION_JSON_INVALID", "$", str(error)) from error
    return strict_json_text(raw)


def command_templates() -> dict[str, str]:
    return {item.id: item.declared for item in build_plan(Path("${OUTPUT_ROOT}"))}


def validate_windows_output_path(raw: str) -> None:
    lowered = raw.replace("/", "\\").casefold()
    if lowered.startswith(("\\\\?\\", "\\\\.\\", "\\??\\")):
        raise EvidenceError("OUTPUT_ROOT_NAMESPACE_INVALID", "resolvedAbsoluteOutputRoot", "Win32 device and extended path namespaces are forbidden")
    if lowered.startswith("\\\\"):
        raise EvidenceError("OUTPUT_ROOT_UNC_FORBIDDEN", "resolvedAbsoluteOutputRoot", "UNC roots are forbidden when network access is not authorized")
    path = Path(raw)
    parts = path.parts[1:] if path.anchor else path.parts
    for component in parts:
        if len(component) > 255:
            raise EvidenceError("OUTPUT_ROOT_COMPONENT_INVALID", "resolvedAbsoluteOutputRoot", "path component exceeds the portable Windows length")
        if component != component.rstrip(" ."):
            raise EvidenceError("OUTPUT_ROOT_COMPONENT_INVALID", "resolvedAbsoluteOutputRoot", "path components cannot end in a dot or space")
        if ":" in component or any(char in '<>"|?*' for char in component):
            raise EvidenceError("OUTPUT_ROOT_COMPONENT_INVALID", "resolvedAbsoluteOutputRoot", "path component contains a Windows-invalid character or alternate data stream")
        stem = component.split(".", 1)[0].upper()
        if stem in WINDOWS_RESERVED:
            raise EvidenceError("OUTPUT_ROOT_COMPONENT_INVALID", "resolvedAbsoluteOutputRoot", "path component is a reserved DOS device name")
    if os.path.normcase(os.path.normpath(raw)) != os.path.normcase(raw):
        raise EvidenceError("OUTPUT_ROOT_NOT_CANONICAL", "resolvedAbsoluteOutputRoot", "output root must use canonical path spelling")


def validate_authorization(value: dict[str, Any], *, require_empty_root: bool = True) -> Path:
    required = {
        "schemaVersion", "packageId", "requirementId", "runId", "startSha",
        "resolvedAbsoluteOutputRoot", "sourceWorkspace", "outputClasses", "fixtureCommands",
        "networkAuthorized", "repositoryCopyAuthorized", "cleanupPolicy", "commands",
    }
    missing = sorted(required - value.keys())
    unexpected = sorted(value.keys() - required)
    if missing:
        raise EvidenceError("AUTHORIZATION_FIELD_MISSING", missing[0], "required field missing")
    if unexpected:
        raise EvidenceError("AUTHORIZATION_FIELD_UNEXPECTED", unexpected[0], "unexpected field")
    if type(value["schemaVersion"]) is not int or value["schemaVersion"] != 1:
        raise EvidenceError("AUTHORIZATION_VERSION_INVALID", "schemaVersion", "expected integer 1")
    if value["packageId"] != PACKAGE_ID:
        raise EvidenceError("PACKAGE_ID_MISMATCH", "packageId", "wrong package")
    if value["requirementId"] != REQUIREMENT_ID:
        raise EvidenceError("REQUIREMENT_ID_MISMATCH", "requirementId", "wrong requirement")
    if not isinstance(value["runId"], str) or not RUN_ID_RE.fullmatch(value["runId"]):
        raise EvidenceError("RUN_ID_INVALID", "runId", "runId is not a portable identifier")
    if not isinstance(value["startSha"], str) or not re.fullmatch(r"[0-9a-f]{40}", value["startSha"]):
        raise EvidenceError("START_SHA_INVALID", "startSha", "startSha must be lowercase SHA-1")
    if not isinstance(value["sourceWorkspace"], str) or not value["sourceWorkspace"] or any(ord(char) < 32 for char in value["sourceWorkspace"]):
        raise EvidenceError("SOURCE_WORKSPACE_INVALID", "sourceWorkspace", "source workspace must be a string")
    if not isinstance(value["resolvedAbsoluteOutputRoot"], str) or not value["resolvedAbsoluteOutputRoot"] or any(ord(char) < 32 for char in value["resolvedAbsoluteOutputRoot"]):
        raise EvidenceError("OUTPUT_ROOT_TYPE_INVALID", "resolvedAbsoluteOutputRoot", "output root must be a string")
    try:
        source = Path(value["sourceWorkspace"])
        if not source.is_absolute() or source.resolve(strict=True) != ROOT.resolve(strict=True):
            raise EvidenceError("SOURCE_WORKSPACE_INVALID", "sourceWorkspace", "source must be this checkout")
    except EvidenceError:
        raise
    except (OSError, RuntimeError, ValueError) as error:
        raise EvidenceError("SOURCE_WORKSPACE_INVALID", "sourceWorkspace", str(error)) from error
    try:
        output = Path(value["resolvedAbsoluteOutputRoot"])
        validate_windows_output_path(value["resolvedAbsoluteOutputRoot"])
        if not output.is_absolute():
            raise EvidenceError("OUTPUT_ROOT_NOT_ABSOLUTE", "resolvedAbsoluteOutputRoot", "root must be absolute")
        lexical = Path(output.anchor)
        for component in output.parts[1:]:
            lexical /= component
            try:
                lexical.lstat()
            except FileNotFoundError:
                break
            if is_reparse(lexical):
                raise EvidenceError("OUTPUT_ROOT_REPARSE", "resolvedAbsoluteOutputRoot", f"reparse lexical component: {lexical}")
        resolved = output.resolve(strict=False)
        repo = ROOT.resolve(strict=True)
        if resolved == repo or repo in resolved.parents or resolved in repo.parents:
            raise EvidenceError("OUTPUT_ROOT_NOT_EXTERNAL", "resolvedAbsoluteOutputRoot", "root overlaps repository")
        cursor = resolved
        while not cursor.exists() and cursor != cursor.parent:
            cursor = cursor.parent
        while True:
            if is_reparse(cursor):
                raise EvidenceError("OUTPUT_ROOT_REPARSE", "resolvedAbsoluteOutputRoot", f"reparse ancestor: {cursor}")
            if cursor == cursor.parent:
                break
            cursor = cursor.parent
        if resolved.exists() and not resolved.is_dir():
            raise EvidenceError("OUTPUT_ROOT_NOT_DIRECTORY", "resolvedAbsoluteOutputRoot", "existing output root must be a directory")
        if require_empty_root and resolved.exists() and any(resolved.iterdir()):
            raise EvidenceError("OUTPUT_ROOT_NOT_EMPTY", "resolvedAbsoluteOutputRoot", "run root must be absent or empty")
        expected_output = ISOLATED_OUTPUT_BASE / PACKAGE_ID / value["runId"]
        if os.path.normcase(os.path.normpath(str(output))) != os.path.normcase(os.path.normpath(str(expected_output))):
            raise EvidenceError("OUTPUT_ROOT_TEMPLATE_INVALID", "resolvedAbsoluteOutputRoot", f"expected exact package/run root: {expected_output}")
    except EvidenceError:
        raise
    except (OSError, RuntimeError, ValueError) as error:
        raise EvidenceError("OUTPUT_ROOT_INVALID", "resolvedAbsoluteOutputRoot", str(error)) from error
    if not isinstance(value["outputClasses"], dict) or set(value["outputClasses"]) != set(OUTPUT_CLASSES):
        raise EvidenceError("OUTPUT_CLASS_SET_INVALID", "outputClasses", "six exact output classes required")
    children = list(value["outputClasses"].values())
    if any(not isinstance(item, str) for item in children):
        raise EvidenceError("OUTPUT_CLASS_SET_INVALID", "outputClasses", "output children must be strings")
    if len({item.casefold() for item in children}) != len(children):
        raise EvidenceError("OUTPUT_CHILD_COLLISION", "outputClasses", "children must be unique")
    if value["outputClasses"] != OUTPUT_CLASSES:
        raise EvidenceError("OUTPUT_CLASS_SET_INVALID", "outputClasses", "output child mapping mismatch")
    if value["networkAuthorized"] is not False or value["repositoryCopyAuthorized"] is not False:
        raise EvidenceError("UNSAFE_AUTHORIZATION", "networkAuthorized", "network and copy must be false")
    if value["cleanupPolicy"] != "record inventory, then delete the run root":
        raise EvidenceError("CLEANUP_POLICY_INVALID", "cleanupPolicy", "cleanup policy mismatch")
    expected_fixture = ["cmd.exe /d /c mklink /J ${OUTPUT_ROOT}/test/scanner-fixture/linked-dir ${OUTPUT_ROOT}/test/scanner-fixture/target-dir"]
    if value["fixtureCommands"] != expected_fixture:
        raise EvidenceError("FIXTURE_COMMAND_SET_INVALID", "fixtureCommands", "fixture command mismatch")
    commands = value["commands"]
    if not isinstance(commands, list) or any(not isinstance(item, dict) for item in commands):
        raise EvidenceError("COMMAND_SET_INVALID", "commands", "commands must be objects")
    expected = command_templates()
    actual: dict[str, str] = {}
    for item in commands:
        if set(item) != {"id", "command"} or not isinstance(item["id"], str) or not isinstance(item["command"], str):
            raise EvidenceError("COMMAND_SET_INVALID", "commands", "command shape invalid")
        if item["id"] in actual:
            raise EvidenceError("COMMAND_DUPLICATE", item["id"], "duplicate command")
        actual[item["id"]] = item["command"]
    if actual != expected:
        raise EvidenceError("COMMAND_SET_INVALID", "commands", "authorized commands differ from reviewed plan")
    return resolved


def p(root: Path, *parts: str) -> str:
    return str(root.joinpath(*parts))


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def discover_node_surfaces() -> list[dict[str, str]]:
    """Build-plan discovery for every non-watch build/test package script."""
    rows: list[dict[str, str]] = []
    codebase = ROOT / "Codebase"
    for manifest in sorted(codebase.rglob("package.json")):
        if "node_modules" in manifest.parts:
            continue
        value = strict_json(manifest)
        scripts = value.get("scripts", {})
        if not isinstance(scripts, dict):
            continue
        directory = manifest.parent.relative_to(codebase).as_posix()
        if directory == ".":
            directory = ""
        for name, source_command in sorted(scripts.items()):
            if not isinstance(source_command, str) or not re.match(r"^(build|test)(:|$)", name) or "watch" in name:
                continue
            surface = directory or "root"
            identifier = f"node-{slug(surface)}-{slug(name)}"
            working = "Codebase" + (f"/{directory}" if directory else "")
            rows.append({
                "id": identifier,
                "surface": surface,
                "kind": "build" if name.startswith("build") else "test",
                "sourcePath": manifest.relative_to(ROOT).as_posix(),
                "sourceCommand": source_command,
                "scriptName": name,
                "workingDirectory": working,
                "authorizedCommand": f"pnpm --dir {working} run {name}",
            })
    return rows


MISE_IDS = {
    ("machine-learning", "test"): "ml-unit-test",
    ("mobile", "test"): "mobile-unit-test",
    ("mobile", "build:android"): "mobile-android-build",
    ("root", "prod"): "docker-prod-build",
    ("root", "dev-update"): "docker-dev-update-build",
    ("root", "dev-scale"): "docker-dev-scale-build",
    ("root", "prod-scale"): "docker-prod-scale-build",
    ("root", "e2e-update"): "docker-e2e-update-build",
}


def mise_command(run: Any) -> str | None:
    if isinstance(run, str):
        return run
    if isinstance(run, list) and run and all(isinstance(item, str) for item in run):
        return " && ".join(run)
    if isinstance(run, dict) and isinstance(run.get("task"), str):
        args = run.get("args", [])
        if isinstance(args, list) and all(isinstance(item, str) for item in args):
            return "mise run " + " ".join([run["task"], *args])
    return None


def discover_mise_surfaces() -> list[dict[str, str]]:
    """Build-plan discovery for exact build/test tasks declared by mise manifests."""
    rows: list[dict[str, str]] = []
    codebase = ROOT / "Codebase"
    for manifest in sorted(codebase.rglob("mise.toml")):
        value = tomllib.loads(manifest.read_text(encoding="utf-8"))
        tasks = value.get("tasks", {})
        if not isinstance(tasks, dict):
            continue
        directory = manifest.parent.relative_to(codebase).as_posix()
        if directory == ".":
            directory = "root"
        for name, task in sorted(tasks.items()):
            if not isinstance(task, dict):
                continue
            source_command = mise_command(task.get("run"))
            if source_command is None:
                continue
            run_value = task.get("run")
            table_build = isinstance(run_value, dict) and isinstance(run_value.get("args"), list) and "--build" in run_value["args"]
            build_producing = table_build or bool(re.search(r"\bdocker\s+compose\b.*(?:\sbuild(?:\s|$)|--build(?:\s|$))", source_command))
            if not isinstance(name, str) or not (re.match(r"^(build|test)([-:]|$)", name) or build_producing):
                continue
            identifier = MISE_IDS.get((directory, name), f"mise-{slug(directory)}-{name}")
            kind = "build" if name.startswith("build") or build_producing else "test"
            rows.append({
                "id": identifier,
                "surface": directory,
                "kind": kind,
                "sourcePath": manifest.relative_to(ROOT).as_posix(),
                "sourceCommand": source_command,
                "taskName": name,
                "workingDirectory": f"Codebase/{directory}" if directory != "root" else "Codebase",
            })
    return rows


def build_plan(output: Path) -> list[Attempt]:
    token = str(output).replace("\\", "/")
    def declared(value: str) -> str:
        return value.replace(token, "${OUTPUT_ROOT}")

    specs: list[Attempt] = []
    for row in discover_node_surfaces():
        command = row["authorizedCommand"]
        specs.append(Attempt(
            row["id"], row["surface"], row["kind"], ".",
            tuple(command.split(" ")), command, row["sourcePath"], row["sourceCommand"],
            "pnpm", False,
            "DECLARED_BUILD_OUTPUT_REDIRECTION_UNPROVEN" if row["kind"] == "build" else "TEST_SIDE_EFFECT_REDIRECTION_UNPROVEN",
        ))
    for row in discover_mise_surfaces():
        if row["id"] == "ml-unit-test":
            specs.append(Attempt(
                row["id"], row["surface"], row["kind"], row["workingDirectory"],
                ("uv", "run", "--offline", "--frozen", "pytest", "--cov=immich_ml", "--cov-report", "term-missing", f"--basetemp={p(output,'test','pytest-temp')}", "-o", f"cache_dir={p(output,'cache','pytest')}"),
                declared(f"uv run --offline --frozen pytest --cov=immich_ml --cov-report term-missing --basetemp={token}/test/pytest-temp -o cache_dir={token}/cache/pytest"),
                row["sourcePath"], row["sourceCommand"], "uv",
            ))
            continue
        command = f"mise run {row['taskName']}"
        blocker = "DECLARED_BUILD_OUTPUT_REDIRECTION_UNPROVEN" if row["kind"] == "build" else "TEST_SIDE_EFFECT_REDIRECTION_UNPROVEN"
        if row["id"].startswith("docker-"):
            blocker = "CONTAINER_RUNTIME_VOLUME_AND_NETWORK_UNAVAILABLE"
        elif row["surface"] == "e2e":
            blocker = "CONTAINER_RUNTIME_AND_PROJECT_DEPENDENCIES_UNAVAILABLE"
        elif row["sourceCommand"].startswith("flutter "):
            blocker = "FLUTTER_OUTPUT_REDIRECTION_UNPROVEN"
        specs.append(Attempt(
            row["id"], row["surface"], row["kind"], row["workingDirectory"],
            ("mise", "run", row["taskName"]), command,
            row["sourcePath"], row["sourceCommand"], "mise", False, blocker,
        ))
    specs.extend([
        Attempt("ml-bytecode-build", "machine-learning", "build", ".", (sys.executable, "-m", "compileall", "-q", "Codebase/machine-learning/immich_ml"), "python -m compileall -q Codebase/machine-learning/immich_ml", "Codebase/machine-learning/pyproject.toml", "Python source bytecode compilation"),
        Attempt("ml-package-build", "machine-learning", "build", ".", ("uv", "build", "--project", "Codebase/machine-learning", "--out-dir", p(output,"build","machine-learning"), "--offline"), declared(f"uv build --project Codebase/machine-learning --out-dir {token}/build/machine-learning --offline"), "Codebase/machine-learning/pyproject.toml", "[build-system] package build"),
        Attempt("mobile-ui-unit-test", "mobile-ui", "test", "Codebase/mobile/packages/ui", ("flutter", "test"), "flutter test", "Codebase/mobile/packages/ui/test", "flutter test", "flutter", False, "FLUTTER_OUTPUT_REDIRECTION_UNPROVEN"),
        Attempt("open-api-dart-build", "open-api-dart", "build", "Codebase/open-api", ("bash", "./bin/generate-dart-sdk.sh"), "bash ./bin/generate-dart-sdk.sh", "Codebase/mise.toml", "[tasks.open-api-dart] bash ./bin/generate-dart-sdk.sh", "bash", False, "GENERATED_SOURCE_REDIRECTION_UNPROVEN"),
        Attempt("ios-build", "ios", "build", "Codebase/mobile/ios", ("xcodebuild", "-project", "Runner.xcodeproj", "-scheme", "Runner", "build"), "xcodebuild -project Runner.xcodeproj -scheme Runner build", "Codebase/mobile/ios/Runner.xcodeproj/project.pbxproj", "Xcode Runner build", "xcodebuild", False, "PLATFORM_AND_DERIVED_DATA_REDIRECTION_UNAVAILABLE"),
        Attempt("docker-e2e-test", "docker-e2e", "test", "Codebase/e2e", ("docker", "compose", "-f", "./docker-compose.yml", "up", "--remove-orphans"), "docker compose -f ./docker-compose.yml up --remove-orphans", "Codebase/mise.toml", "[tasks.e2e] docker compose -f ./docker-compose.yml up --remove-orphans", "docker", False, "CONTAINER_RUNTIME_AND_VOLUME_WRITES_UNAVAILABLE"),
    ])
    return specs


def independent_surface_oracle() -> dict[str, tuple[str, str, str, str, str, bool, str | None]]:
    """Independently inventory source manifests and expected full attempt semantics."""
    expected: dict[str, tuple[str, str, str, str, str, bool, str | None]] = {}
    codebase = ROOT / "Codebase"
    for manifest in sorted(codebase.rglob("package.json")):
        if "node_modules" in manifest.parts:
            continue
        value = json.loads(manifest.read_text(encoding="utf-8"))
        scripts = value.get("scripts", {})
        if not isinstance(scripts, dict):
            continue
        directory = manifest.parent.relative_to(codebase).as_posix()
        if directory == ".":
            directory = ""
        for name, source_command in sorted(scripts.items()):
            if not isinstance(source_command, str) or not re.match(r"^(build|test)(:|$)", name) or "watch" in name:
                continue
            surface = directory or "root"
            identifier = f"node-{slug(surface)}-{slug(name)}"
            working = "Codebase" + (f"/{directory}" if directory else "")
            kind = "build" if name.startswith("build") else "test"
            blocker = "DECLARED_BUILD_OUTPUT_REDIRECTION_UNPROVEN" if kind == "build" else "TEST_SIDE_EFFECT_REDIRECTION_UNPROVEN"
            expected[identifier] = (
                manifest.relative_to(ROOT).as_posix(), source_command,
                f"pnpm --dir {working} run {name}", ".", kind, False, blocker,
            )
    mise_overrides = {
        ("machine-learning", "test"): "ml-unit-test", ("mobile", "test"): "mobile-unit-test",
        ("mobile", "build:android"): "mobile-android-build", ("root", "prod"): "docker-prod-build",
        ("root", "dev-update"): "docker-dev-update-build", ("root", "dev-scale"): "docker-dev-scale-build",
        ("root", "prod-scale"): "docker-prod-scale-build", ("root", "e2e-update"): "docker-e2e-update-build",
    }
    for manifest in sorted(codebase.rglob("mise.toml")):
        value = tomllib.loads(manifest.read_text(encoding="utf-8"))
        tasks = value.get("tasks", {})
        if not isinstance(tasks, dict):
            continue
        directory = manifest.parent.relative_to(codebase).as_posix()
        if directory == ".":
            directory = "root"
        for name, task in sorted(tasks.items()):
            if not isinstance(task, dict):
                continue
            run = task.get("run")
            if isinstance(run, str):
                source_command = run
            elif isinstance(run, list) and run and all(isinstance(item, str) for item in run):
                source_command = " && ".join(run)
            elif isinstance(run, dict) and isinstance(run.get("task"), str) and isinstance(run.get("args", []), list) and all(isinstance(item, str) for item in run.get("args", [])):
                source_command = "mise run " + " ".join([run["task"], *run.get("args", [])])
            else:
                continue
            table_build = isinstance(run, dict) and "--build" in run.get("args", [])
            build_producing = table_build or bool(re.search(r"\bdocker\s+compose\b.*(?:\sbuild(?:\s|$)|--build(?:\s|$))", source_command))
            if not isinstance(name, str) or not (re.match(r"^(build|test)([-:]|$)", name) or build_producing):
                continue
            identifier = mise_overrides.get((directory, name), f"mise-{slug(directory)}-{name}")
            cwd = f"Codebase/{directory}" if directory != "root" else "Codebase"
            if identifier == "ml-unit-test":
                declared_command = "uv run --offline --frozen pytest --cov=immich_ml --cov-report term-missing --basetemp=${OUTPUT_ROOT}/test/pytest-temp -o cache_dir=${OUTPUT_ROOT}/cache/pytest"
                expected[identifier] = (manifest.relative_to(ROOT).as_posix(), source_command, declared_command, cwd, name, True, None)
                continue
            kind = "build" if name.startswith("build") or build_producing else "test"
            blocker = "DECLARED_BUILD_OUTPUT_REDIRECTION_UNPROVEN" if kind == "build" else "TEST_SIDE_EFFECT_REDIRECTION_UNPROVEN"
            if identifier.startswith("docker-"):
                blocker = "CONTAINER_RUNTIME_VOLUME_AND_NETWORK_UNAVAILABLE"
            elif directory == "e2e":
                blocker = "CONTAINER_RUNTIME_AND_PROJECT_DEPENDENCIES_UNAVAILABLE"
            elif source_command.startswith("flutter "):
                blocker = "FLUTTER_OUTPUT_REDIRECTION_UNPROVEN"
            expected[identifier] = (
                manifest.relative_to(ROOT).as_posix(), source_command,
                f"mise run {name}", cwd, kind, False, blocker,
            )
    expected.update({
        "ml-bytecode-build": ("Codebase/machine-learning/pyproject.toml", "Python source bytecode compilation", "python -m compileall -q Codebase/machine-learning/immich_ml", ".", "build", True, None),
        "ml-package-build": ("Codebase/machine-learning/pyproject.toml", "[build-system] package build", "uv build --project Codebase/machine-learning --out-dir ${OUTPUT_ROOT}/build/machine-learning --offline", ".", "build", True, None),
        "mobile-ui-unit-test": ("Codebase/mobile/packages/ui/test", "flutter test", "flutter test", "Codebase/mobile/packages/ui", "test", False, "FLUTTER_OUTPUT_REDIRECTION_UNPROVEN"),
        "open-api-dart-build": ("Codebase/mise.toml", "[tasks.open-api-dart] bash ./bin/generate-dart-sdk.sh", "bash ./bin/generate-dart-sdk.sh", "Codebase/open-api", "build", False, "GENERATED_SOURCE_REDIRECTION_UNPROVEN"),
        "ios-build": ("Codebase/mobile/ios/Runner.xcodeproj/project.pbxproj", "Xcode Runner build", "xcodebuild -project Runner.xcodeproj -scheme Runner build", "Codebase/mobile/ios", "build", False, "PLATFORM_AND_DERIVED_DATA_REDIRECTION_UNAVAILABLE"),
        "docker-e2e-test": ("Codebase/mise.toml", "[tasks.e2e] docker compose -f ./docker-compose.yml up --remove-orphans", "docker compose -f ./docker-compose.yml up --remove-orphans", "Codebase/e2e", "test", False, "CONTAINER_RUNTIME_AND_VOLUME_WRITES_UNAVAILABLE"),
    })
    return expected


def git(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["GIT_OPTIONAL_LOCKS"] = "0"
    return subprocess.run(["git", *args], cwd=ROOT, env=env, text=True, capture_output=True, check=False)


CERTIFICATION_PATHS = {
    "graphify/12-semantic-implementation-plan/12-validators/adversarial-results.json",
    "graphify/12-semantic-implementation-plan/13-reports/final-100-percent-certification.json",
    "graphify/12-semantic-implementation-plan/13-reports/final-content-manifest.json",
    "graphify/12-semantic-implementation-plan/13-reports/final-determinism-proof.json",
    "graphify/12-semantic-implementation-plan/13-reports/final-release-envelope.json",
    "graphify/12-semantic-implementation-plan/14-handoff/gpt-review-sha-manifest.json",
    "graphify/12-semantic-implementation-plan/PLAN-MANIFEST.json",
    "graphify/semantic-plan-source/handoff-gpt/gpt-review-sha-manifest.json",
    "graphify/semantic-plan-source/reviews/final-100-percent-certification.json",
    "graphify/semantic-plan-source/reviews/final-content-manifest.json",
    "graphify/semantic-plan-source/reviews/final-determinism-proof.json",
    "graphify/semantic-plan-source/reviews/final-release-envelope.json",
}
PACKAGE_PREFIX = "graphify/13-implementation/WP-I0-007/"


def allowed_repository_path(path: str) -> bool:
    normalized = path.replace("\\", "/").rstrip("/")
    return normalized == PACKAGE_PREFIX.rstrip("/") or normalized.startswith(PACKAGE_PREFIX) or normalized in CERTIFICATION_PATHS


def unauthorized_git_status() -> list[str]:
    result = git("status", "--porcelain=v1", "--untracked-files=all")
    if result.returncode:
        raise EvidenceError("GIT_STATUS_FAILED", "git", result.stderr.strip())
    rows = []
    for line in result.stdout.splitlines():
        path = line[3:].replace("\\", "/")
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if not allowed_repository_path(path):
            rows.append(line)
    return rows


def protected_snapshot() -> dict[str, Any]:
    """Hash every repository file except .git and exact authorized write paths."""
    files: dict[str, tuple[int, str]] = {}
    reparse: list[str] = []
    for current_dir, dirs, names in os.walk(ROOT, topdown=True, followlinks=False):
        base = Path(current_dir)
        for name in list(dirs):
            path = base / name
            rel = path.relative_to(ROOT).as_posix()
            if rel == ".git" or allowed_repository_path(rel + "/"):
                dirs.remove(name)
                continue
            if is_reparse(path):
                reparse.append(rel)
                dirs.remove(name)
        for name in names:
            path = base / name
            rel = path.relative_to(ROOT).as_posix()
            if allowed_repository_path(rel):
                continue
            if is_reparse(path):
                reparse.append(rel)
                continue
            files[rel] = (path.stat().st_size, sha256(path))
    digest = hashlib.sha256()
    for path, value in sorted(files.items()):
        digest.update(f"{path}\0{value[0]}\0{value[1]}\n".encode())
    return {"files": files, "reparsePoints": sorted(reparse), "fileCount": len(files), "digest": digest.hexdigest()}


def compare_protected(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    old, new = before["files"], after["files"]
    added = sorted(new.keys() - old.keys())
    removed = sorted(old.keys() - new.keys())
    modified = sorted(path for path in old.keys() & new.keys() if old[path] != new[path])
    reparse_changed = before["reparsePoints"] != after["reparsePoints"]
    return {
        "beforeFileCount": before["fileCount"], "afterFileCount": after["fileCount"],
        "beforeDigest": before["digest"], "afterDigest": after["digest"],
        "added": added, "removed": removed, "modified": modified,
        "reparseBefore": before["reparsePoints"], "reparseAfter": after["reparsePoints"],
        "result": "PASS" if not (added or removed or modified or reparse_changed) else "FAIL",
    }


FORBIDDEN_ARTIFACT_NAMES = {"node_modules", ".pnpm", ".cache", ".venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".dart_tool", "coverage"}


def scan_artifact_tree(root: Path, expected_dirs: set[str] | None = None) -> dict[str, Any]:
    expected_dirs = expected_dirs or set()
    forbidden: list[str] = []
    reparse: list[str] = []
    for current_dir, dirs, files in os.walk(root, topdown=True, followlinks=False):
        base = Path(current_dir)
        for name in list(dirs):
            path = base / name
            rel = path.relative_to(root).as_posix()
            if is_reparse(path):
                reparse.append(rel)
                dirs.remove(name)
            if name.casefold() in FORBIDDEN_ARTIFACT_NAMES and rel not in expected_dirs:
                forbidden.append(rel)
        for name in files:
            path = base / name
            if is_reparse(path):
                reparse.append(path.relative_to(root).as_posix())
    return {"forbiddenArtifacts": sorted(set(forbidden)), "reparsePoints": sorted(set(reparse))}


def scanner_fixture(root: Path, auth: dict[str, Any]) -> dict[str, Any]:
    fixture = root / "test" / "scanner-fixture"
    forbidden = fixture / "nested" / "node_modules"
    target = fixture / "target-dir"
    link = fixture / "linked-dir"
    forbidden.mkdir(parents=True)
    (forbidden / "value.txt").write_text("fixture", encoding="utf-8")
    target.mkdir()
    (target / "value.txt").write_text("target", encoding="utf-8")
    try:
        result = subprocess.run(["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(target)], text=True, capture_output=True, timeout=30, check=False)
        reparse_created = result.returncode == 0 and is_reparse(link)
        reparse_error = None if reparse_created else (result.stdout + result.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as error:
        reparse_created = False
        reparse_error = str(error)
    validator_actual = "NOT_RUN"
    if reparse_created:
        candidate = copy.deepcopy(auth)
        candidate["resolvedAbsoluteOutputRoot"] = str(link)
        validator_actual = "VALID"
        try:
            validate_authorization(candidate, require_empty_root=False)
        except EvidenceError as error:
            validator_actual = error.code
    scan = scan_artifact_tree(fixture)
    passed = "nested/node_modules" in scan["forbiddenArtifacts"] and "linked-dir" in scan["reparsePoints"] and validator_actual == "OUTPUT_ROOT_REPARSE"
    return {
        "reparseCreated": reparse_created,
        "reparseError": reparse_error,
        "junctionValidatorExpected": "OUTPUT_ROOT_REPARSE",
        "junctionValidatorActual": validator_actual,
        **scan,
        "result": "PASS" if passed else "FAIL",
    }


def compare_codebase() -> dict[str, Any]:
    expected: dict[str, tuple[int, str]] = {}
    with BASELINE.open("r", encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            expected[row["path"].replace("\\", "/")] = (int(row["size"]), row["sha256"])
    expected_dirs = {str(Path(path).parent).replace("\\", "/") for path in expected}
    current: dict[str, tuple[int, str]] = {}
    codebase = ROOT / "Codebase"
    artifact_scan = scan_artifact_tree(codebase, expected_dirs)
    for current_dir, dirs, files in os.walk(codebase, topdown=True, followlinks=False):
        base = Path(current_dir)
        for name in list(dirs):
            path = base / name
            rel = path.relative_to(ROOT).as_posix()
            if is_reparse(path):
                dirs.remove(name)
        for name in files:
            path = base / name
            rel = path.relative_to(ROOT).as_posix()
            if is_reparse(path):
                continue
            current[rel] = (path.stat().st_size, sha256(path))
    missing = sorted(expected.keys() - current.keys())
    unexpected = sorted(current.keys() - expected.keys())
    mismatched = sorted(path for path in expected.keys() & current.keys() if expected[path] != current[path])
    return {
        "expectedFiles": len(expected), "currentFiles": len(current),
        "missing": missing, "unexpected": unexpected, "mismatched": mismatched,
        **artifact_scan,
        "result": "PASS" if not (missing or unexpected or mismatched or artifact_scan["forbiddenArtifacts"] or artifact_scan["reparsePoints"]) else "FAIL",
    }


def isolated_env(root: Path) -> dict[str, str]:
    env = os.environ.copy()
    values = {
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPYCACHEPREFIX": p(root, "cache", "python"),
        "TEMP": p(root, "temporary"), "TMP": p(root, "temporary"), "TMPDIR": p(root, "temporary"),
        "XDG_CACHE_HOME": p(root, "cache", "xdg"),
        "npm_config_cache": p(root, "package-manager", "npm-cache"),
        "npm_config_offline": "true", "npm_config_update_notifier": "false",
        "COREPACK_HOME": p(root, "package-manager", "corepack"),
        "PNPM_HOME": p(root, "package-manager", "pnpm-home"),
        "PNPM_STORE_DIR": p(root, "package-manager", "pnpm-store"),
        "UV_CACHE_DIR": p(root, "cache", "uv"),
        "UV_PROJECT_ENVIRONMENT": p(root, "generated", "machine-learning-venv"),
        "COVERAGE_FILE": p(root, "test", ".coverage"),
        "CARGO_HOME": p(root, "package-manager", "cargo-home"),
        "CARGO_TARGET_DIR": p(root, "build", "cargo"),
        "GRADLE_USER_HOME": p(root, "package-manager", "gradle-home"),
        "PUB_CACHE": p(root, "package-manager", "pub-cache"),
        "NO_COLOR": "1",
    }
    env.update(values)
    return env


def execute_attempt(spec: Attempt, root: Path, env: dict[str, str]) -> dict[str, Any]:
    record: dict[str, Any] = {
        "id": spec.id, "surface": spec.surface, "kind": spec.kind,
        "sourcePath": spec.source_path, "sourceCommand": spec.source_command,
        "declaredCommand": spec.declared,
        "isolatedCommand": subprocess.list2cmdline(list(spec.argv)),
        "workingDirectory": str((ROOT / spec.cwd).resolve()),
        "executed": False, "status": "BLOCKED", "exitCode": None,
        "blocker": None, "output": "", "durationMs": 0,
    }
    if spec.argv[0] == "pnpm" and not (ROOT / "Codebase" / "node_modules").exists():
        record["blocker"] = "PROJECT_DEPENDENCIES_UNAVAILABLE"
        record["output"] = "Codebase/node_modules is absent; no install or network resolution is authorized."
        return record
    if not spec.isolation_proven:
        record["blocker"] = spec.blocker or "OUTPUT_REDIRECTION_UNPROVEN"
        return record
    if spec.expected_tool and shutil.which(spec.expected_tool) is None:
        local_bins = list((ROOT / "Codebase").glob(f"**/node_modules/.bin/{spec.expected_tool}*"))
        if spec.expected_tool not in {"flutter", "dart"} and shutil.which("pnpm") and not local_bins:
            pass  # execute pnpm to capture the exact missing-local-tool failure
        else:
            record["blocker"] = "HOST_TOOL_UNAVAILABLE"
            return record
    started = time.monotonic()
    argv = list(spec.argv)
    resolved_executable = shutil.which(argv[0])
    use_command_processor = bool(resolved_executable and resolved_executable.lower().endswith((".cmd", ".bat")))
    if resolved_executable and not use_command_processor:
        argv[0] = resolved_executable
    try:
        if use_command_processor:
            command_line = subprocess.list2cmdline([resolved_executable, *argv[1:]])
            command_processor = os.environ.get("ComSpec", r"C:\Windows\System32\cmd.exe")
            run_value: list[str] | str = command_line
        else:
            command_processor = None
            run_value = argv
        result = subprocess.run(
            run_value, cwd=ROOT / spec.cwd, env=env, stdin=subprocess.DEVNULL,
            text=True, encoding="utf-8", errors="replace", capture_output=True,
            timeout=120, check=False, shell=use_command_processor, executable=command_processor,
        )
        combined = (result.stdout + result.stderr).strip()
        record.update({
            "executed": True,
            "status": "SUCCESS" if result.returncode == 0 else "FAILURE",
            "exitCode": result.returncode,
            "blocker": None if result.returncode == 0 else "COMMAND_EXIT_NONZERO",
            "output": combined[:12000],
        })
    except FileNotFoundError as error:
        record["blocker"] = "HOST_TOOL_UNAVAILABLE"
        record["output"] = str(error)
    except subprocess.TimeoutExpired as error:
        record.update({"executed": True, "status": "FAILURE", "blocker": "COMMAND_TIMEOUT", "output": str(error)})
    record["durationMs"] = round((time.monotonic() - started) * 1000)
    return record


def inventory_output(root: Path) -> dict[str, Any]:
    files = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            files.append({"path": path.relative_to(root).as_posix(), "size": path.stat().st_size, "sha256": sha256(path)})
    counts = {name: 0 for name in OUTPUT_CLASSES}
    for item in files:
        first = item["path"].split("/", 1)[0]
        for name, child in OUTPUT_CLASSES.items():
            if first == child:
                counts[name] += 1
    return {"files": files, "countsByClass": counts, "fileCount": len(files)}


def self_test(auth: dict[str, Any]) -> list[dict[str, str]]:
    external_file = Path(os.environ.get("WINDIR", r"C:\Windows")) / "win.ini"
    if not external_file.is_file():
        external_file = Path(sys.executable)
    cases: list[tuple[str, str, Any]] = [
        ("missing_package", "AUTHORIZATION_FIELD_MISSING", lambda x: x.pop("packageId")),
        ("wrong_package", "PACKAGE_ID_MISMATCH", lambda x: x.__setitem__("packageId", "WP-I0-008")),
        ("inside_repository", "OUTPUT_ROOT_NOT_EXTERNAL", lambda x: x.__setitem__("resolvedAbsoluteOutputRoot", str(ROOT / "output"))),
        ("mismatched_run_root", "OUTPUT_ROOT_TEMPLATE_INVALID", lambda x: x.__setitem__("runId", "run-20260809-mismatch")),
        ("mismatched_package_root", "OUTPUT_ROOT_TEMPLATE_INVALID", lambda x: x.__setitem__("resolvedAbsoluteOutputRoot", str(ISOLATED_OUTPUT_BASE / "WP-I0-008" / x["runId"]))),
        ("arbitrary_safe_root", "OUTPUT_ROOT_TEMPLATE_INVALID", lambda x: x.__setitem__("resolvedAbsoluteOutputRoot", r"C:\Temp\unbound-wp7-root")),
        ("duplicate_child", "OUTPUT_CHILD_COLLISION", lambda x: x["outputClasses"].__setitem__("test", "BUILD")),
        ("network_enabled", "UNSAFE_AUTHORIZATION", lambda x: x.__setitem__("networkAuthorized", True)),
        ("command_removed", "COMMAND_SET_INVALID", lambda x: x["commands"].pop()),
        ("existing_file_root", "OUTPUT_ROOT_NOT_DIRECTORY", lambda x: x.__setitem__("resolvedAbsoluteOutputRoot", str(external_file))),
        ("wrong_source_type", "SOURCE_WORKSPACE_INVALID", lambda x: x.__setitem__("sourceWorkspace", None)),
        ("wrong_output_type", "OUTPUT_ROOT_TYPE_INVALID", lambda x: x.__setitem__("resolvedAbsoluteOutputRoot", 0)),
        ("reserved_output_component", "OUTPUT_ROOT_COMPONENT_INVALID", lambda x: x.__setitem__("resolvedAbsoluteOutputRoot", r"C:\Temp\CON\run")),
        ("reserved_superscript_com_component", "OUTPUT_ROOT_COMPONENT_INVALID", lambda x: x.__setitem__("resolvedAbsoluteOutputRoot", "C:\\Temp\\COM¹\\run")),
        ("reserved_superscript_lpt_component", "OUTPUT_ROOT_COMPONENT_INVALID", lambda x: x.__setitem__("resolvedAbsoluteOutputRoot", "C:\\Temp\\LPT².txt\\run")),
        ("reserved_conin_component", "OUTPUT_ROOT_COMPONENT_INVALID", lambda x: x.__setitem__("resolvedAbsoluteOutputRoot", r"C:\Temp\CONIN$\run")),
        ("reserved_conout_component", "OUTPUT_ROOT_COMPONENT_INVALID", lambda x: x.__setitem__("resolvedAbsoluteOutputRoot", r"C:\Temp\CONOUT$\run")),
        ("overlong_output_component", "OUTPUT_ROOT_COMPONENT_INVALID", lambda x: x.__setitem__("resolvedAbsoluteOutputRoot", "C:\\Temp\\" + "x" * 256)),
        ("extended_namespace_repository_alias", "OUTPUT_ROOT_NAMESPACE_INVALID", lambda x: x.__setitem__("resolvedAbsoluteOutputRoot", "\\\\?\\" + str(ROOT / "review-output-never-create"))),
        ("forward_extended_namespace_repository_alias", "OUTPUT_ROOT_NAMESPACE_INVALID", lambda x: x.__setitem__("resolvedAbsoluteOutputRoot", "//?/" + str(ROOT / "review-output-never-create").replace("\\", "/"))),
        ("localhost_unc_repository_alias", "OUTPUT_ROOT_UNC_FORBIDDEN", lambda x: x.__setitem__("resolvedAbsoluteOutputRoot", r"\\localhost\c$\Users\mhyah\Downloads\Code\Lamha\review-output-never-create")),
        ("loopback_unc_repository_alias", "OUTPUT_ROOT_UNC_FORBIDDEN", lambda x: x.__setitem__("resolvedAbsoluteOutputRoot", r"\\127.0.0.1\c$\Users\mhyah\Downloads\Code\Lamha\review-output-never-create")),
        ("alternate_data_stream_output", "OUTPUT_ROOT_COMPONENT_INVALID", lambda x: x.__setitem__("resolvedAbsoluteOutputRoot", r"C:\Temp\wp7:ads")),
        ("trailing_dot_output", "OUTPUT_ROOT_COMPONENT_INVALID", lambda x: x.__setitem__("resolvedAbsoluteOutputRoot", "C:\\Temp\\wp7.")),
        ("noncanonical_separator_output", "OUTPUT_ROOT_NOT_CANONICAL", lambda x: x.__setitem__("resolvedAbsoluteOutputRoot", r"C:\Temp\\wp7")),
        ("invalid_run_id", "RUN_ID_INVALID", lambda x: x.__setitem__("runId", "../escape")),
        ("unexpected_field", "AUTHORIZATION_FIELD_UNEXPECTED", lambda x: x.__setitem__("allowAnything", True)),
        ("duplicate_command", "COMMAND_DUPLICATE", lambda x: x["commands"].append(copy.deepcopy(x["commands"][0]))),
    ]
    rows = []
    for name, expected, mutate in cases:
        candidate = copy.deepcopy(auth)
        mutate(candidate)
        actual = "VALID"
        try:
            validate_authorization(candidate, require_empty_root=False)
        except EvidenceError as error:
            actual = error.code
        rows.append({"name": name, "expected": expected, "actual": actual, "result": "PASS" if actual == expected else "FAIL"})
    artifact_actual = "FORBIDDEN_ARTIFACT" if Path("Codebase/node_modules").name.casefold() in FORBIDDEN_ARTIFACT_NAMES else "ALLOWED"
    rows.append({"name": "generated_dependency_tree", "expected": "FORBIDDEN_ARTIFACT", "actual": artifact_actual, "result": "PASS" if artifact_actual == "FORBIDDEN_ARTIFACT" else "FAIL"})
    sibling_actual = "AUTHORIZED" if allowed_repository_path("graphify/13-implementation/WP-I0-007-evil/file") else "REJECTED"
    rows.append({"name": "package_prefix_sibling", "expected": "REJECTED", "actual": sibling_actual, "result": "PASS" if sibling_actual == "REJECTED" else "FAIL"})
    raw_cases = [
        ("raw_duplicate_key", "AUTHORIZATION_DUPLICATE_KEY", '{"packageId":"WP-I0-007","packageId":"WP-I0-007"}'),
        ("raw_malformed_json", "AUTHORIZATION_JSON_INVALID", '{"packageId":'),
    ]
    for name, expected, raw in raw_cases:
        actual = "VALID"
        try:
            strict_json_text(raw)
        except EvidenceError as error:
            actual = error.code
        rows.append({"name": name, "expected": expected, "actual": actual, "result": "PASS" if actual == expected else "FAIL"})
    raw_path_cases = [
        ("raw_nul_source_path", "sourceWorkspace", "C:\\bad\0", "SOURCE_WORKSPACE_INVALID"),
        ("raw_nul_output_path", "resolvedAbsoluteOutputRoot", "C:\\Temp\\bad\0name", "OUTPUT_ROOT_TYPE_INVALID"),
    ]
    for name, field, malformed, expected in raw_path_cases:
        candidate = copy.deepcopy(auth)
        candidate[field] = malformed
        actual = "VALID"
        try:
            validate_authorization(strict_json_text(json.dumps(candidate)), require_empty_root=False)
        except EvidenceError as error:
            actual = error.code
        rows.append({"name": name, "expected": expected, "actual": actual, "result": "PASS" if actual == expected else "FAIL"})
    floating_version = copy.deepcopy(auth)
    floating_version["schemaVersion"] = 1.0
    actual = "VALID"
    try:
        validate_authorization(strict_json_text(json.dumps(floating_version)), require_empty_root=False)
    except EvidenceError as error:
        actual = error.code
    rows.append({"name": "raw_floating_schema_version", "expected": "AUTHORIZATION_VERSION_INVALID", "actual": actual, "result": "PASS" if actual == "AUTHORIZATION_VERSION_INVALID" else "FAIL"})
    return rows


def write_evidence(auth: dict[str, Any], started: str, ended: str, before: dict[str, Any], after: dict[str, Any],
                   before_status: list[str], after_status: list[str], protected: dict[str, Any],
                   attempts: list[dict[str, Any]], coverage: dict[str, Any], scanner: dict[str, Any],
                   output_inventory: dict[str, Any], cleanup: dict[str, Any], negatives: list[dict[str, str]]) -> None:
    failures = []
    if before["result"] != "PASS" or after["result"] != "PASS": failures.append("Codebase baseline mismatch")
    if before_status or after_status: failures.append("unauthorized Git change")
    if protected["result"] != "PASS": failures.append("protected repository content changed")
    if coverage["result"] != "PASS": failures.append("surface oracle mismatch")
    if scanner["result"] != "PASS": failures.append("artifact scanner fixture failed")
    if not cleanup["succeeded"]: failures.append("external run root/template-parent cleanup failed")
    if any(item["result"] != "PASS" for item in negatives): failures.append("negative fixture failed")
    if len(attempts) != len(auth["commands"]): failures.append("attempt coverage mismatch")
    if not any(item["executed"] and item["kind"] == "build" for item in attempts): failures.append("no build attempt executed")
    if not any(item["executed"] and item["kind"] == "test" for item in attempts): failures.append("no test attempt executed")
    status = "PASS" if not failures else "FAIL"
    counts = {state: sum(item["status"] == state for item in attempts) for state in ("SUCCESS", "FAILURE", "BLOCKED")}
    report = {
        "packageId": PACKAGE_ID, "requirementId": REQUIREMENT_ID, "runId": auth["runId"],
        "collectionWindowUtc": {"start": started, "end": ended},
        "authorization": auth, "attempts": attempts, "attemptCounts": counts,
        "surfaceOracle": coverage, "scannerFixture": scanner,
        "externalOutputInventoryBeforeCleanup": output_inventory,
        "cleanup": cleanup, "negativeFixtures": negatives,
        "recoveredIncidents": [
            {"runId": "authoring", "code": "UNAUTHORIZED_AUTHORING_CACHE", "status": "RECOVERED", "evidence": "authoring-incident.md"},
            {"runId": "run-20260809-001", "code": "WINDOWS_COMMAND_LAUNCHER_DEFECT", "status": "SUPERSEDED", "evidence": "authoring-incident.md"},
            {"runId": "run-20260809-002", "code": "ISOLATION_VIOLATION", "status": "RECOVERED_AND_REJECTED", "evidence": "authoring-incident.md"},
        ],
        "preservation": {"codebaseBefore": before, "codebaseAfter": after, "protectedRepository": protected, "unauthorizedGitStatusBefore": before_status, "unauthorizedGitStatusAfter": after_status},
        "status": status, "failures": failures,
    }
    exit_clauses = [
        {"clause": "One separately authorized external run root contains every writable output class", "evidence": f"Authorization names {auth['runId']}, the canonical external root, all six output classes, and {len(auth['commands'])} commands; network and repository copies are forbidden.", "result": "PASS"},
        {"clause": "Every source-derived baseline build/test surface is faithfully represented or receives an exact pre-execution blocker", "evidence": f"The independent package/mise source oracle and manual platform list report missing={len(coverage['missing'])}, unexpected={len(coverage['unexpected'])}, mismatched={len(coverage['mismatched'])}; {len(attempts)} attempts record {counts['SUCCESS']} successes, {counts['FAILURE']} executed failures, and {counts['BLOCKED']} typed blockers without substituting source commands.", "result": coverage["result"]},
        {"clause": "The corrected run and recorded recovery leave all protected repository content unchanged and remove the disposable root", "evidence": f"Run-002 is rejected as an ISOLATION_VIOLATION. Current run {auth['runId']} has Codebase {before['result']}/{after['result']} across {after['currentFiles']} files, protected repository result {protected['result']} across {protected['afterFileCount']} files, empty unauthorized Git status, scanner fixture {scanner['result']}, and cleanupSucceeded={cleanup['succeeded']}.", "result": "PASS" if after["result"] == "PASS" and protected["result"] == "PASS" and not after_status and scanner["result"] == "PASS" and cleanup["succeeded"] else "FAIL"},
        {"clause": "Invalid authorizations fail with typed errors and no partial execution", "evidence": f"{sum(item['result'] == 'PASS' for item in negatives)}/{len(negatives)} pure negative fixtures returned their expected typed errors, including an existing file-valued root and raw duplicate/malformed JSON.", "result": "PASS" if all(item["result"] == "PASS" for item in negatives) else "FAIL"},
    ]
    summary = {
        "packageId": PACKAGE_ID, "runId": auth["runId"], "outputRoot": auth["resolvedAbsoluteOutputRoot"], "status": status, "failures": failures,
        "checks": {"authorization": "PASS", "attemptCoverage": coverage["result"], "focused": status, "negative": "PASS" if all(item["result"] == "PASS" for item in negatives) and scanner["result"] == "PASS" else "FAIL", "regression": "PASS" if after["result"] == "PASS" and protected["result"] == "PASS" else "FAIL", "artifactScan": "PASS" if not after_status and scanner["result"] == "PASS" and cleanup["succeeded"] else "FAIL", "evidenceConsistency": "PENDING", "exitGate": "PASS" if all(item["result"] == "PASS" for item in exit_clauses) else "FAIL"},
        "counts": {"plannedAttempts": len(auth["commands"]), **counts, "externalFilesBeforeCleanup": output_inventory["fileCount"], "recoveredIncidents": 3},
        "exitGateClauses": exit_clauses,
    }
    provenance = {
        "packageId": PACKAGE_ID, "runId": auth["runId"], "outputRoot": auth["resolvedAbsoluteOutputRoot"], "startingSha": auth["startSha"],
        "selection": {"rule": "sole explicit authorized package remained READY", "readySet": ["WP-I0-007","WP-I0-008","WP-I0-009","WP-I0-010","WP-I0-011","WP-I1-001","WP-I2-001","WP-I2-002","WP-I10-003","WP-I15-006"]},
        "prerequisites": [{"packageId": item, "status": "COMPLETE", "exitGate": "PASS"} for item in PREREQUISITES],
        "operationalAuthority": {"packageId": ISOLATION_AUTHORITY, "status": "COMPLETE", "exitGate": "PASS", "role": "build-output isolation decision; not a DAG prerequisite"},
        "authorizedWrites": ["graphify/13-implementation/WP-I0-007/**", "existing Graphify certification artifacts", auth["resolvedAbsoluteOutputRoot"] + "/** (disposable, removed)"],
    }
    artifact = {
        "packageId": PACKAGE_ID, "runId": auth["runId"], "outputRoot": auth["resolvedAbsoluteOutputRoot"], "unauthorizedGitStatusBefore": before_status, "unauthorizedGitStatusAfter": after_status,
        "codebaseBefore": before, "codebaseAfter": after,
        "protectedRepository": protected, "scannerFixture": scanner,
        "externalOutput": {"root": auth["resolvedAbsoluteOutputRoot"], "inventoryBeforeCleanup": output_inventory, **cleanup},
        "recoveredIncidentEvidence": "graphify/13-implementation/WP-I0-007/authoring-incident.md",
        "result": "PASS" if after["result"] == "PASS" and protected["result"] == "PASS" and scanner["result"] == "PASS" and not after_status and cleanup["succeeded"] else "FAIL",
    }
    write_json(PACKAGE_DIR / "baseline-attempts.json", report)
    write_json(PACKAGE_DIR / "verification-report.json", report)
    write_json(PACKAGE_DIR / "package-summary.json", summary)
    write_json(PACKAGE_DIR / "provenance-report.json", provenance)
    write_json(PACKAGE_DIR / "artifact-scan.json", artifact)
    lines = ["# WP-I0-007 baseline build and test attempts", "", f"- Status: **{status}**", f"- Run: `{auth['runId']}`", f"- External run: `{auth['resolvedAbsoluteOutputRoot']}` (removed after inventory)", f"- Results: {counts['SUCCESS']} successes, {counts['FAILURE']} executed failures, {counts['BLOCKED']} pre-execution blockers.", "", "| ID | Source | Source command | Executed | Status | Exit | Blocker |", "|---|---|---|---:|---|---:|---|"]
    for item in attempts:
        lines.append(f"| {item['id']} | {item['sourcePath']} | `{item['sourceCommand'].replace('|', '&#124;')}` | {str(item['executed']).lower()} | {item['status']} | {item['exitCode'] if item['exitCode'] is not None else ''} | {item['blocker'] or ''} |")
    write_text(PACKAGE_DIR / "baseline-attempts.md", "\n".join(lines))
    evidence = ["# WP-I0-007 completion evidence", "", f"- Package: {PACKAGE_ID} — Baseline build and test attempts", f"- Requirement: `{REQUIREMENT_ID}`", f"- Starting SHA: `{auth['startSha']}`", f"- Current run: `{auth['runId']}`", f"- Attempt coverage: {len(attempts)}/{len(auth['commands'])}", f"- Exact outcomes: {counts['SUCCESS']} successes, {counts['FAILURE']} executed failures, {counts['BLOCKED']} blockers.", f"- Disposable root: `{auth['resolvedAbsoluteOutputRoot']}`; inventory recorded and root removed.", f"- Recovery: `authoring-incident.md` rejects the pre-run cache, run-001 launcher defect, and run-002 isolation violation; {auth['runId']} begins from the restored 3,697-file baseline.", "", "## Exit gate", ""]
    evidence.extend(f"- **{item['result']}** — {item['clause']}: {item['evidence']}" for item in exit_clauses)
    write_text(PACKAGE_DIR / "completion-evidence.md", "\n".join(evidence))
    json_paths = ["baseline-attempts.json", "verification-report.json", "package-summary.json", "provenance-report.json", "artifact-scan.json"]
    mismatches = []
    for name in json_paths:
        value = strict_json(PACKAGE_DIR / name)
        if value.get("packageId") != PACKAGE_ID or value.get("runId") != auth["runId"]:
            mismatches.append(name)
    for name in ("baseline-attempts.md", "completion-evidence.md"):
        text = (PACKAGE_DIR / name).read_text(encoding="utf-8")
        if auth["runId"] not in text or auth["resolvedAbsoluteOutputRoot"] not in text:
            mismatches.append(name)
    consistency = {"packageId": PACKAGE_ID, "runId": auth["runId"], "checkedFiles": json_paths + ["baseline-attempts.md", "completion-evidence.md"], "mismatches": mismatches, "result": "PASS" if not mismatches else "FAIL"}
    write_json(PACKAGE_DIR / "evidence-consistency.json", consistency)
    summary["checks"]["evidenceConsistency"] = consistency["result"]
    if mismatches:
        summary["status"] = "FAIL"
        summary["failures"].append("evidence run consistency mismatch")
        summary["checks"]["exitGate"] = "FAIL"
    write_json(PACKAGE_DIR / "package-summary.json", summary)


def execute() -> int:
    started = utc_now()
    auth = strict_json(AUTHORIZATION)
    output = validate_authorization(auth)
    if git("rev-parse", "HEAD").stdout.strip() != auth["startSha"]:
        raise EvidenceError("START_SHA_MISMATCH", "startSha", "HEAD changed before execution")
    for prerequisite in (*PREREQUISITES, ISOLATION_AUTHORITY):
        summary = strict_json(GRAPHIFY / "13-implementation" / prerequisite / "package-summary.json")
        if summary.get("status") != "PASS" or summary.get("failures"):
            raise EvidenceError("PREREQUISITE_NOT_COMPLETE", prerequisite, "prerequisite is not PASS")
    isolation = strict_json(GRAPHIFY / "13-implementation" / ISOLATION_AUTHORITY / "build-output-isolation-decision.json")
    future = isolation.get("futureWorkspace", {})
    if future.get("separatePackageAuthorizationRequired") is not True or future.get("outputClassPaths") != OUTPUT_CLASSES:
        raise EvidenceError("ISOLATION_AUTHORITY_INVALID", ISOLATION_AUTHORITY, "isolation decision does not match required boundary")
    before_status = unauthorized_git_status()
    before = compare_codebase()
    protected_before = protected_snapshot()
    if before_status or before["result"] != "PASS":
        raise EvidenceError("BASELINE_NOT_CLEAN", "repository", "source baseline is not clean")
    template_parents = [output.parent, ISOLATED_OUTPUT_BASE]
    template_parents_created = {str(path): not path.exists() for path in template_parents}
    attempts: list[dict[str, Any]] = []
    output_inventory: dict[str, Any] = {"files": [], "countsByClass": {}, "fileCount": 0}
    scanner = {"result": "NOT_RUN"}
    def remove_readonly(function: Any, path: str, _error: Any) -> None:
        os.chmod(path, stat.S_IWRITE)
        function(path)

    def cleanup_output_tree() -> dict[str, Any]:
        result: dict[str, Any] = {"attempted": True, "succeeded": False, "rootAbsentAfterCleanup": False, "templateParentsCreated": template_parents_created, "templateParentCleanupErrors": [], "createdTemplateParentsAbsentAfterCleanup": False}
        if output.exists():
            try:
                shutil.rmtree(output, onerror=remove_readonly)
            except OSError as error:
                result["templateParentCleanupErrors"].append({"path": str(output), "error": str(error)})
        for parent in template_parents:
            if template_parents_created[str(parent)] and parent.exists():
                try:
                    parent.rmdir()
                except OSError as error:
                    result["templateParentCleanupErrors"].append({"path": str(parent), "error": str(error)})
        result["rootAbsentAfterCleanup"] = not output.exists()
        result["createdTemplateParentsAbsentAfterCleanup"] = all(not path.exists() for path in template_parents if template_parents_created[str(path)])
        result["succeeded"] = result["rootAbsentAfterCleanup"] and result["createdTemplateParentsAbsentAfterCleanup"] and not result["templateParentCleanupErrors"]
        return result

    setup_actual = "VALID"
    try:
        output.mkdir(parents=True, exist_ok=False)
        (output / OUTPUT_CLASSES["build"]).mkdir()
        raise EvidenceError("INJECTED_OUTPUT_SETUP_FAILURE", "output", "fixture failure after first output child")
    except EvidenceError as error:
        setup_actual = error.code
    except (OSError, RuntimeError, ValueError) as error:
        setup_actual = "OUTPUT_SETUP_FAILED"
    finally:
        setup_fixture_cleanup = cleanup_output_tree()
    setup_fixture = {"name": "mid_setup_failure_recovery", "expected": "INJECTED_OUTPUT_SETUP_FAILURE_AND_CLEAN", "actual": f"{setup_actual}_AND_{'CLEAN' if setup_fixture_cleanup['succeeded'] else 'DIRTY'}", "result": "PASS" if setup_actual == "INJECTED_OUTPUT_SETUP_FAILURE" and setup_fixture_cleanup["succeeded"] else "FAIL", "cleanup": setup_fixture_cleanup}
    if setup_fixture["result"] != "PASS":
        raise EvidenceError("SETUP_RECOVERY_FIXTURE_FAILED", "output", setup_fixture["actual"])

    cleanup: dict[str, Any] = {"attempted": False, "succeeded": False}
    execution_error: EvidenceError | None = None
    try:
        try:
            output.mkdir(parents=True, exist_ok=False)
            for child in OUTPUT_CLASSES.values():
                (output / child).mkdir()
        except (OSError, RuntimeError, ValueError) as error:
            raise EvidenceError("OUTPUT_SETUP_FAILED", "resolvedAbsoluteOutputRoot", str(error)) from error
        env = isolated_env(output)
        scanner = scanner_fixture(output, auth)
        plan = build_plan(output)
        for spec in plan:
            attempts.append(execute_attempt(spec, output, env))
        output_inventory = inventory_output(output)
    except EvidenceError as error:
        execution_error = error
    except Exception as error:
        execution_error = EvidenceError("BASELINE_EXECUTION_FAILED", "execution", str(error))
    finally:
        cleanup = cleanup_output_tree()
    if not cleanup["succeeded"]:
        raise EvidenceError("OUTPUT_CLEANUP_FAILED", "resolvedAbsoluteOutputRoot", json.dumps(cleanup["templateParentCleanupErrors"]))
    if execution_error is not None:
        raise execution_error
    after = compare_codebase()
    protected_after = protected_snapshot()
    protected = compare_protected(protected_before, protected_after)
    after_status = unauthorized_git_status()
    negatives = self_test(auth)
    negatives.append(setup_fixture)
    negatives.append({"name": "nested_ignored_and_reparse_scanner", "expected": "PASS", "actual": scanner["result"], "result": "PASS" if scanner["result"] == "PASS" else "FAIL"})
    source_oracle = independent_surface_oracle()
    plan_index = {item.id: (item.source_path, item.source_command, item.declared, item.cwd, item.kind, item.isolation_proven, item.blocker) for item in build_plan(output)}
    expected_ids = set(source_oracle)
    missing = sorted(expected_ids - plan_index.keys())
    unexpected = sorted(plan_index.keys() - expected_ids)
    mismatched = sorted(key for key, value in source_oracle.items() if plan_index.get(key) != value)
    node_count = sum(key.startswith("node-") for key in source_oracle)
    mise_override_ids = {"ml-unit-test", "mobile-unit-test", "mobile-android-build", "docker-prod-build", "docker-dev-update-build", "docker-dev-scale-build", "docker-prod-scale-build", "docker-e2e-update-build"}
    mise_count = sum(key.startswith("mise-") for key in source_oracle) + sum(key in mise_override_ids for key in source_oracle)
    coverage = {"nodeManifestSurfaceCount": node_count, "miseManifestSurfaceCount": mise_count, "mandatorySurfaceCount": len(source_oracle) - node_count - mise_count, "expectedIds": sorted(expected_ids), "missing": missing, "unexpected": unexpected, "mismatched": mismatched, "result": "PASS" if not (missing or unexpected or mismatched) else "FAIL"}
    ended = utc_now()
    write_evidence(auth, started, ended, before, after, before_status, after_status, protected, attempts, coverage, scanner, output_inventory, cleanup, negatives)
    summary = strict_json(PACKAGE_DIR / "package-summary.json")
    print(json.dumps({"packageId": PACKAGE_ID, "status": summary["status"], "counts": summary["counts"], "failures": summary["failures"]}, indent=2))
    return 0 if summary["status"] == "PASS" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    try:
        auth = strict_json(AUTHORIZATION)
        root = validate_authorization(auth)
        if args.self_test:
            rows = self_test(auth)
            print(json.dumps(rows, indent=2))
            return 0 if all(row["result"] == "PASS" for row in rows) else 1
        if args.validate_only:
            print(json.dumps({"status": "VALID", "packageId": PACKAGE_ID, "outputRoot": str(root)}, indent=2))
            return 0
        return execute()
    except EvidenceError as error:
        print(json.dumps({"status": "INVALID", "code": error.code, "field": error.field, "message": str(error)}, indent=2), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
