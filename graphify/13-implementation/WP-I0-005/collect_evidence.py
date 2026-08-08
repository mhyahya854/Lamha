"""WP-I0-005 read-only repository and host toolchain inventory.

No installs, builds, product tests, network calls, or writes outside this
package evidence directory are permitted.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True

PACKAGE_ID = "WP-I0-005"
PACKAGE_DIR = Path(__file__).resolve().parent
GRAPHIFY = PACKAGE_DIR.parents[1]
LAMHA = GRAPHIFY.parent.resolve(strict=True)
CODEBASE = LAMHA / "Codebase"
PLAN = GRAPHIFY / "12-semantic-implementation-plan"
PACKET = PLAN / "04-work-packages" / "packets" / f"{PACKAGE_ID}.md"
PREREQ_DIR = GRAPHIFY / "13-implementation" / "WP-I0-004"
PREREQ_SUMMARY = PREREQ_DIR / "package-summary.json"
PREREQ_REVIEW = PREREQ_DIR / "adversarial-review.md"
PREREQ_INVESTIGATION = PREREQ_DIR / "mixed-version-investigation.json"
PREREQ_COLLECTOR = PREREQ_DIR / "collect_evidence.py"

sys.path.insert(0, str(GRAPHIFY / "tools"))
from write_guard import guard_write_path  # noqa: E402

GIT_ENV = {**os.environ, "GIT_OPTIONAL_LOCKS": "0", "PYTHONDONTWRITEBYTECODE": "1"}
CATEGORIES = ("node", "package-manager", "rust", "python", "media", "platform")

MANIFEST_NAMES = {
    ".nvmrc", ".npmrc", ".pnpmfile.cjs", ".python-version",
    "package.json", "package-lock.json", "pnpm-lock.yaml", "pnpm-workspace.yaml",
    "yarn.lock", "bun.lock", "bun.lockb", "mise.toml", "mise.lock",
    "Cargo.toml", "Cargo.lock", "rust-toolchain", "rust-toolchain.toml",
    "pyproject.toml", "uv.lock", "Pipfile", "Pipfile.lock", "poetry.lock",
    "pubspec.yaml", "pubspec.lock", "Podfile", "Podfile.lock", "Gemfile",
    "Gemfile.lock", "Package.swift", "Package.resolved", "gradle.properties",
    "libs.versions.toml", "gradle-wrapper.properties", "CMakeLists.txt",
    "project.pbxproj", "devcontainer.json", "openapitools.json", "environment.yml",
    "environment.yaml", "env.yml", "env.yaml",
    ".terraform.lock.hcl", ".metadata", "VERSION", "example.env", ".travis.yml", ".travis.yaml", ".browserslistrc",
    ".dockerignore", ".gitmodules", ".npmignore", ".openapi-generator-ignore",
    ".editorconfig", ".prettierrc", ".prettierignore", ".env",
    "analysis_options.yaml", "build.yaml", "dcm_global.yaml", "devtools_options.yaml",
    "flutter_native_splash.yaml", "Fastfile", "Appfile", "AppFrameworkInfo.plist",
    "Makefile", "makefile",
    "renovate.json",
}

EXPECTED_PATHS = {
    "Codebase/.pnpmfile.cjs",
    "Codebase/web/.npmrc",
    "Codebase/mobile/android/gradle/libs.versions.toml",
    "Codebase/mobile/android/gradle.properties",
    "Codebase/mobile/android/Gemfile.lock",
    "Codebase/mobile/ios/Podfile.lock",
    "Codebase/mobile/ios/Runner.xcodeproj/project.xcworkspace/xcshareddata/swiftpm/Package.resolved",
    "Codebase/mobile/ios/Runner.xcworkspace/xcshareddata/swiftpm/Package.resolved",
    "Codebase/.devcontainer/mobile/container-compose-overrides.yml",
    "Codebase/.devcontainer/server/container-compose-overrides.yml",
    "Codebase/open-api/openapitools.json",
    "Codebase/deployment/modules/cloudflare/docs/.terraform.lock.hcl",
    "Codebase/deployment/modules/cloudflare/docs-release/.terraform.lock.hcl",
    "Codebase/mobile/.metadata",
    "Codebase/mobile/openapi/.openapi-generator/VERSION",
    "Codebase/machine-learning/ann/export/env.yaml",
    "Codebase/docker/example.env",
    "Codebase/mobile/openapi/.travis.yml",
    "Codebase/deployment/modules/cloudflare/docs/config.tf",
    "Codebase/deployment/modules/cloudflare/docs-release/config.tf",
    "Codebase/deployment/modules/cloudflare/docs/terragrunt.hcl",
    "Codebase/deployment/modules/cloudflare/docs-release/terragrunt.hcl",
    "Codebase/deployment/state.hcl",
    "Codebase/docker/hwaccel.ml.yml",
    "Codebase/docker/hwaccel.transcoding.yml",
    "Codebase/open-api/bin/generate-dart-sdk.sh",
    "Codebase/machine-learning/ann/export/download-armnn.sh",
    "Codebase/mobile/ios/ci_scripts/ci_post_clone.sh",
    "Codebase/machine-learning/ann/export/build-converter.sh",
    "Codebase/machine-learning/ann/build.sh",
    "Codebase/renovate.json",
}

EXPECTED_DECLARATIONS = {
    ("Codebase/.github/workflows/build-mobile.yml", "java-version", "17"),
    ("Codebase/.github/workflows/build-mobile.yml", "ruby-version", "3.3"),
    ("Codebase/mobile/android/gradle/libs.versions.toml", "version:agp", "8.11.2"),
    ("Codebase/mobile/android/gradle/libs.versions.toml", "version:kotlin", "2.2.20"),
    ("Codebase/mobile/android/Gemfile.lock", "gem:fastlane", "2.214.0"),
    ("Codebase/mobile/android/Gemfile.lock", "bundler", "2.3.7"),
    ("Codebase/mobile/ios/Podfile.lock", "cocoapods", "1.16.2"),
    ("Codebase/mobile/ios/Runner.xcodeproj/project.xcworkspace/xcshareddata/swiftpm/Package.resolved", "swift-package:grdb.swift", "7.8.0"),
    ("Codebase/mobile/ios/Runner.xcworkspace/xcshareddata/swiftpm/Package.resolved", "swift-package:grdb.swift", "7.9.0"),
    ("Codebase/open-api/openapitools.json", "openapi-generator-cli", "7.8.0"),
    ("Codebase/mobile/openapi/.openapi-generator/VERSION", "openapi-generator-cli", "7.8.0"),
    ("Codebase/deployment/modules/cloudflare/docs/.terraform.lock.hcl", "terraform-provider:registry.opentofu.org/cloudflare/cloudflare", "4.52.7"),
    ("Codebase/deployment/modules/cloudflare/docs-release/.terraform.lock.hcl", "terraform-provider:registry.opentofu.org/cloudflare/cloudflare", "4.52.7"),
    ("Codebase/machine-learning/ann/export/env.yaml", "conda:python", "3.10.13"),
    ("Codebase/machine-learning/ann/export/env.yaml", "conda:pip", "23.3.1"),
    ("Codebase/machine-learning/ann/export/env.yaml", "conda:cuda-runtime", "11.7.1"),
    ("Codebase/machine-learning/ann/export/env.yaml", "conda:pytorch", "1.13.1"),
    ("Codebase/docker/example.env", "env:immich_version", "v2"),
    ("Codebase/mobile/openapi/.travis.yml", "dart-version", "2.12"),
    ("Codebase/deployment/modules/cloudflare/docs/config.tf", "terraform-required-version", "~> 1.7"),
    ("Codebase/deployment/modules/cloudflare/docs/config.tf", "terraform-provider:cloudflare/cloudflare", "4.52.7"),
    ("Codebase/deployment/modules/cloudflare/docs-release/config.tf", "terraform-provider:cloudflare/cloudflare", "4.52.7"),
    ("Codebase/machine-learning/Dockerfile", "docker-env:armnn_version", "v24.05"),
    ("Codebase/machine-learning/Dockerfile", "docker-env:rknn_toolkit_version", "v2.3.0"),
    ("Codebase/machine-learning/Dockerfile", "docker-copy-image:ghcr.io/astral-sh/uv", "ghcr.io/astral-sh/uv:0.8.15@sha256:a5727064a0de127bdb7c9d3c1383f3a9ac307d9f2d8a391edc7896c54289ced0"),
    ("Codebase/machine-learning/Dockerfile", "docker-release:github.com/intel/intel-graphics-compiler", "v2.32.7"),
    ("Codebase/machine-learning/Dockerfile", "docker-package:libcudnn9-cuda-12", "9.10.2.21-1"),
    ("Codebase/machine-learning/Dockerfile", "docker-deb:libigdgmm12", "22.9.0"),
    ("Codebase/server/Dockerfile.dev", "docker-copy-image:ghcr.io/jdx/mise", "ghcr.io/jdx/mise:2026.5.11@sha256:2ba959e4827f845fe0c4cfb4814089e790dc513040ef74f9e14925f446412a51"),
    ("Codebase/server/Dockerfile.dev", "docker-env:flutter_version", "3.35.7"),
    ("Codebase/mobile/packages/ui/pubspec.lock", "sdks.flutter", ">=3.18.0-18.0.pre.54"),
    ("Codebase/mobile/packages/ui/pubspec.lock", "sdks.dart", ">=3.12.0 <4.0.0"),
    ("Codebase/mobile/dcm_global.yaml", "dcm", ">=1.29.0 <=1.37.0"),
    ("Codebase/open-api/bin/generate-dart-sdk.sh", "script:openapi_generator_version", "v7.12.0"),
    ("Codebase/machine-learning/ann/export/download-armnn.sh", "script-release:github.com/arm-software/armnn", "v23.11"),
    ("Codebase/mobile/android/app/CMakeLists.txt", "cmake-minimum-version", "3.12"),
    ("Codebase/mobile/android/app/CMakeLists.txt", "c-language-standard", "17"),
    ("Codebase/e2e/tsconfig.json", "typescript-target", "es2023"),
    ("Codebase/packages/plugin-core/tsconfig.json", "typescript-target", "es2020"),
    ("Codebase/server/tsconfig.json", "typescript-target", "es2022"),
    ("Codebase/server/tsconfig.json", "typescript-lib:es2023", "es2023"),
    ("Codebase/web/tsconfig.json", "typescript-target", "es2022"),
    ("Codebase/web/vite.config.ts", "node-build-target:line-25", "es2022"),
    ("Codebase/web/eslint.config.js", "ecmascript-version:line-93", "2022"),
    ("Codebase/web/eslint.config.js", "ecmascript-version:line-153", "5"),
    ("Codebase/mobile/android/app/build.gradle", "java-source-compatibility", "17"),
    ("Codebase/mobile/android/app/build.gradle", "java-target-compatibility", "17"),
    ("Codebase/mobile/ios/Runner.xcodeproj/project.pbxproj", "gcc_c_language_standard:line-990", "gnu17"),
    ("Codebase/mobile/ios/Runner.xcodeproj/project.pbxproj", "swift-package-minimum:sqlite-data", ">=1.6.1 <2.0.0"),
    ("Codebase/mobile/ios/Runner.xcodeproj/project.pbxproj", "swift-package-minimum:swift-http-structured-headers", ">=1.6.0 <2.0.0"),
    ("Codebase/web/.browserslistrc", "browserslist-query:line-1", "> 0.2% and last 4 major versions"),
    ("Codebase/web/.browserslistrc", "browserslist-query:line-2", "> 0.5%"),
    ("Codebase/pnpm-workspace.yaml", "pnpm-override:canvas", "3.2.3"),
    ("Codebase/pnpm-workspace.yaml", "pnpm-override:sharp", "^0.34.5"),
    ("Codebase/pnpm-workspace.yaml", "pnpm-override:webpackbar", "^7.0.0"),
    ("Codebase/pnpm-workspace.yaml", "pnpm-package-extension:@immich/ui:dependencies:tailwindcss", ">=4.1"),
    ("Codebase/pnpm-workspace.yaml", "pnpm-package-extension:tailwind-variants:dependencies:tailwindcss", ">=4.1"),
    ("Codebase/docs/package.json", "node-config-package:@docusaurus/core", "~3.10.0"),
    ("Codebase/package.json", "node-config-package:prettier-plugin-sort-json", "^4.2.0"),
    ("Codebase/mobile/pubspec.lock", "dart-config-package:flutter_lints", "5.0.0"),
    ("Codebase/machine-learning/ann/export/env.yaml", "conda-pip-vcs:github.com/fyfrey/tinyneuralnetwork", "git+https://github.com/fyfrey/TinyNeuralNetwork.git"),
    ("Codebase/mobile/ios/ci_scripts/ci_post_clone.sh", "script-git:github.com/flutter/flutter", "stable"),
    ("Codebase/mobile/ios/ci_scripts/ci_post_clone.sh", "script-package:brew:cocoapods", "unversioned"),
    ("Codebase/.github/workflows/close-duplicates.yml", "workflow-image:line-38", "ghcr.io/immich-app/mdq:main@sha256:0a8b8867773a0f8368061f47578603f438349f8f1f28b0e16105f481e5c794e0"),
    ("Codebase/.github/workflows/test.yml", "workflow-image:line-714", "ghcr.io/immich-app/postgres:14-vectorchord0.4.3@sha256:dbf18b3ffea4a81434c65b71e20d27203baf903a0275f4341e4c16dfd901fd67"),
    ("Codebase/machine-learning/ann/export/build-converter.sh", "script-tool-source:armnn", "23.11"),
    ("Codebase/machine-learning/ann/export/build-converter.sh", "compiler-language-standard:g++", "c++17"),
    ("Codebase/machine-learning/ann/build.sh", "compiler-language-standard:g++", "c++17"),
    ("Codebase/server/Dockerfile", "docker-tool:corepack", "latest"),
    ("Codebase/server/Dockerfile.dev", "docker-tool:java", "21.x"),
    ("Codebase/server/Dockerfile.dev", "docker-tool:dcm", "unversioned"),
    ("Codebase/machine-learning/Dockerfile", "docker-tool:g++", "unversioned"),
    ("Codebase/machine-learning/Dockerfile", "docker-tool:ccache", "unversioned"),
    ("Codebase/.gitmodules", "git-submodule-url:e2e/test-assets", "https://github.com/immich-app/test-assets"),
    ("Codebase/.gitmodules", "git-submodule-revision:e2e/test-assets", "UNAVAILABLE"),
    ("Codebase/renovate.json", "renovate-extends:line-3", "local>immich-app/.github:renovate-config"),
    ("Codebase/renovate.json", "renovate-package:ruby", "< 3.4"),
    ("Codebase/Makefile", "package-manager-tool:renovate", "unversioned"),
}

EXPECTED_MISSING_REFERENCED_PATHS = {
    "Codebase/mobile/ios/Flutter/Generated.xcconfig",
    "Codebase/mobile/android/local.properties",
    "Codebase/mobile/ios/Flutter/ephemeral/Packages/FlutterGeneratedPluginSwiftPackage/Package.swift",
    "Codebase/web/.svelte-kit/tsconfig.json",
    "Codebase/docs/node_modules/@docusaurus/tsconfig/package.json",
    "Codebase/mobile/.dart_tool/package_config.json",
    "Codebase/docs/node_modules/@docusaurus/core/package.json",
    "Codebase/node_modules/prettier-plugin-sort-json/package.json",
    "Codebase/mobile/ios/Pods/Target Support Files/Pods-ShareExtension/Pods-ShareExtension.debug.xcconfig",
    "Codebase/mobile/ios/Pods/Target Support Files/Pods-ShareExtension/Pods-ShareExtension.release.xcconfig",
    "Codebase/mobile/ios/Pods/Target Support Files/Pods-ShareExtension/Pods-ShareExtension.profile.xcconfig",
    "Codebase/mobile/ios/Pods/Manifest.lock",
    "Codebase/mobile/ios/Pods/Target Support Files/Pods-Runner/Pods-Runner-resources-${CONFIGURATION}-input-files.xcfilelist",
    "Codebase/mobile/ios/Pods/Target Support Files/Pods-Runner/Pods-Runner-resources-${CONFIGURATION}-output-files.xcfilelist",
    "Codebase/mobile/ios/Pods/Target Support Files/Pods-Runner/Pods-Runner-frameworks-${CONFIGURATION}-input-files.xcfilelist",
    "Codebase/mobile/ios/Pods/Target Support Files/Pods-Runner/Pods-Runner-frameworks-${CONFIGURATION}-output-files.xcfilelist",
    "Codebase/mobile/ios/Pods/Target Support Files/Pods-Runner/Pods-Runner-resources.sh",
    "Codebase/mobile/ios/Pods/Target Support Files/Pods-Runner/Pods-Runner-frameworks.sh",
    "Codebase/mobile/ios/${FLUTTER_ROOT}/packages/flutter_tools/bin/xcode_backend.sh",
    "Codebase/mobile/android/${flutterSdkPath}/packages/flutter_tools/gradle",
    "Codebase/${RENOVATE_REMOTE}/immich-app/.github/renovate-config.json",
}

# Maps normalized repository-declared tools to their actual local executable.
PROBE_MAP = {
    "node": ("node", ("--version",), "node"),
    "npm": ("npm", ("--version",), "package-manager"),
    "pnpm": ("pnpm", ("--version",), "package-manager"),
    "corepack": ("corepack", ("--version",), "package-manager"),
    "yarn": ("yarn", ("--version",), "package-manager"),
    "bun": ("bun", ("--version",), "package-manager"),
    "rustc": ("rustc", ("--version",), "rust"),
    "cargo": ("cargo", ("--version",), "rust"),
    "rustup": ("rustup", ("--version",), "rust"),
    "python": ("python", ("--version",), "python"),
    "python3": ("python3", ("--version",), "python"),
    "uv": ("uv", ("--version",), "python"),
    "pip": ("pip", ("--version",), "python"),
    "ffmpeg": ("ffmpeg", ("-version",), "media"),
    "ffprobe": ("ffprobe", ("-version",), "media"),
    "dcm": ("dcm", ("--version",), "media"),
    "mise": ("mise", ("--version",), "platform"),
    "flutter": ("flutter", ("--version",), "platform"),
    "dart": ("dart", ("--version",), "platform"),
    "java": ("java", ("-version",), "platform"),
    "gradle": ("gradle", ("--version",), "platform"),
    "cmake": ("cmake", ("--version",), "platform"),
    "ninja": ("ninja", ("--version",), "platform"),
    "docker": ("docker", ("--version",), "platform"),
    "pod": ("pod", ("--version",), "platform"),
    "git": ("git", ("--version",), "platform"),
    "tofu": ("tofu", ("--version",), "platform"),
    "terragrunt": ("terragrunt", ("--version",), "platform"),
    "wrangler": ("wrangler", ("--version",), "platform"),
    "extism": ("extism", ("--version",), "platform"),
    "binaryen": ("wasm-opt", ("--version",), "platform"),
    "oazapfts": ("oazapfts", ("--version",), "platform"),
    "ruby": ("ruby", ("--version",), "platform"),
    "bundler": ("bundle", ("--version",), "platform"),
    "fastlane": ("fastlane", ("--version",), "platform"),
    "swift": ("swift", ("--version",), "platform"),
    "xcodebuild": ("xcodebuild", ("-version",), "platform"),
    "openapi-generator-cli": ("openapi-generator-cli", ("version",), "platform"),
    "conda": ("conda", ("--version",), "python"),
    "g++": ("g++", ("--version",), "platform"),
    "ccache": ("ccache", ("--version",), "platform"),
    "renovate": ("renovate", ("--version",), "package-manager"),
}

BASE_PROBE_TOOLS = {
    "node", "npm", "pnpm", "corepack", "yarn", "bun",
    "rustc", "cargo", "rustup", "python", "python3", "uv", "pip",
    "ffmpeg", "ffprobe", "dcm", "mise", "flutter", "dart", "java",
    "gradle", "cmake", "ninja", "docker", "pod", "git", "ruby",
    "bundler", "swift", "xcodebuild",
}


class InventoryError(Exception):
    def __init__(self, error_type: str, message: str) -> None:
        super().__init__(message)
        self.error_type = error_type


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> tuple[int, str]:
    data = path.read_bytes()
    return len(data), sha256_bytes(data)


def parse_json_text(text: str, source: str) -> object:
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise InventoryError("InventoryInputError", f"{source}: invalid JSON: {error}") from error


def load_json(path: Path) -> object:
    try:
        return parse_json_text(path.read_text(encoding="utf-8"), str(path))
    except OSError as error:
        raise InventoryError("InventoryInputError", f"{path}: {error}") from error


def write_text(name: str, value: str, written: list[str]) -> None:
    target = guard_write_path(PACKAGE_DIR / name)
    target.resolve(strict=False).relative_to(PACKAGE_DIR)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(value.rstrip() + "\n", encoding="utf-8", newline="\n")
    written.append(target.relative_to(GRAPHIFY).as_posix())


def write_json(name: str, value: object, written: list[str]) -> None:
    write_text(name, json.dumps(value, ensure_ascii=False, indent=2), written)


def load_prerequisite_parser():
    spec = importlib.util.spec_from_file_location("wp_i0_004_collector", PREREQ_COLLECTOR)
    if spec is None or spec.loader is None:
        raise InventoryError("PrerequisiteUnavailable", str(PREREQ_COLLECTOR))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def is_version_bearing_tool_script(rel: str) -> bool:
    path = CODEBASE / rel
    if path.suffix.lower() not in {".sh", ".ps1", ".js", ".mjs", ".cjs"}:
        return False
    text = path.read_text(encoding="utf-8", errors="replace")
    static_assignment = re.search(
        r"^\s*[A-Za-z0-9_]*(?:TOOL|SDK|GENERATOR|ARMNN|RKNN)[A-Za-z0-9_]*VERSION[A-Za-z0-9_]*=['\"]?v?\d+(?:\.\d+)+",
        text, re.M | re.I,
    )
    static_release = re.search(
        r"github\.com/(?:ARM-software/armnn|OpenAPITools/openapi-generator)/(?:releases/download|archive/refs/tags)/v?\d+(?:\.\d+)+",
        text, re.I,
    )
    floating_flutter_clone = re.search(
        r"git\s+clone\s+https://github\.com/flutter/flutter(?:\.git)?\b[^\n]*\s(?:-b|--branch)\s+\S+",
        text, re.I,
    )
    compiler_standard = re.search(r"\b(?:g\+\+|clang\+\+|gcc|clang)(?=\s)[^\n]*-std=(?:c|gnu)\+*\d+", text, re.I)
    versioned_tool_source = re.search(r"\b(?:armnn)-v?\d+(?:\.\d+)+/", text, re.I)
    return bool(static_assignment or static_release or floating_flutter_clone or compiler_standard or versioned_tool_source)


def is_manifest(rel: str) -> bool:
    path = Path(rel)
    name = path.name
    lower = rel.lower().replace("\\", "/")
    return (
        name in MANIFEST_NAMES
        or name.startswith("Dockerfile")
        or name.startswith("requirements") and name.endswith(".txt")
        or name.startswith("build.gradle")
        or name.startswith("settings.gradle")
        or name.endswith(".xcconfig")
        or name.lower().endswith((".tf", ".hcl"))
        or name.lower().startswith("hwaccel.") and name.lower().endswith((".yml", ".yaml"))
        or lower.startswith(".vscode/") or "/.vscode/" in lower
        or re.match(r"^(?:tsconfig(?:\.[^.]+)?\.json|vitest(?:\.[^.]+)?\.config(?:\.[^.]+)?\.[^.]+|(?:eslint|vite|playwright|svelte|babel|tailwind|docusaurus)\.config\.[^.]+)$", name.lower()) is not None
        or lower.startswith(".github/workflows/") and name.lower().endswith((".yml", ".yaml"))
        or re.search(r"(^|/)[^/]*compose[^/]*\.ya?ml$", lower) is not None
        or is_version_bearing_tool_script(rel)
    )


def manifest_paths() -> list[str]:
    return sorted(
        path.relative_to(CODEBASE).as_posix()
        for path in CODEBASE.rglob("*")
        if path.is_file() and is_manifest(path.relative_to(CODEBASE).as_posix())
    )


def independent_manifest_candidates() -> tuple[set[str], dict[str, str], list[dict[str, object]]]:
    """Build a coverage oracle without calling the production classifier.

    The oracle uses broad manifest-name families plus references resolved from
    devcontainer manifests. Exact fixtures remain regression checks, not the
    completeness proof.
    """
    candidates: set[str] = set()
    reasons: dict[str, str] = {}
    referenced: list[dict[str, object]] = []

    def record_reference(
        source: Path, value: str, target: Path, mechanism: str, reference_kind: str = "path",
    ) -> None:
        try:
            target_rel = target.resolve(strict=False).relative_to(CODEBASE.resolve(strict=True)).as_posix()
        except ValueError as error:
            raise InventoryError("ManifestReferenceEscape", f"{source.relative_to(CODEBASE).as_posix()}: {value}") from error
        full = f"Codebase/{target_rel}"
        available = target.is_file()
        referenced.append(
            {
                "source": f"Codebase/{source.relative_to(CODEBASE).as_posix()}",
                "reference": value,
                "resolvedPath": full,
                "mechanism": mechanism,
                "referenceKind": reference_kind,
                "required": True,
                "status": "AVAILABLE" if available else "REVIEW_REQUIRED",
                "reason": None if available else "REFERENCED_MANIFEST_UNAVAILABLE",
            }
        )
        if available:
            candidates.add(full)
            reasons[full] = mechanism

    def package_manifest_target(source: Path, specifier: str) -> Path:
        segments = specifier.split("/")
        package_segments = segments[:2] if specifier.startswith("@") else segments[:1]
        return source.parent.joinpath("node_modules", *package_segments, "package.json")
    exact_names = {
        ".nvmrc", ".npmrc", ".pnpmfile.cjs", ".python-version", ".metadata",
        "package.json", "package-lock.json", "pnpm-lock.yaml", "pnpm-workspace.yaml",
        "yarn.lock", "bun.lock", "bun.lockb", "mise.toml", "mise.lock",
        "cargo.toml", "cargo.lock", "rust-toolchain", "rust-toolchain.toml",
        "pyproject.toml", "uv.lock", "pipfile", "pipfile.lock", "poetry.lock",
        "pubspec.yaml", "pubspec.lock", "podfile", "podfile.lock", "gemfile",
        "gemfile.lock", "package.swift", "package.resolved", "gradle.properties",
        "libs.versions.toml", "gradle-wrapper.properties", "cmakelists.txt",
        "project.pbxproj", "devcontainer.json", "openapitools.json",
        ".terraform.lock.hcl", "example.env", "makefile",
        ".browserslistrc", ".dockerignore", ".gitmodules", ".npmignore",
        ".openapi-generator-ignore", ".editorconfig", ".prettierrc", ".prettierignore", ".env",
        "analysis_options.yaml", "build.yaml",
        "dcm_global.yaml", "devtools_options.yaml", "flutter_native_splash.yaml",
        "fastfile", "appfile", "appframeworkinfo.plist", "renovate.json",
    }
    for path in CODEBASE.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(CODEBASE).as_posix()
        lower = rel.lower()
        name = path.name.lower()
        reason = None
        if name in exact_names:
            reason = "standard-toolchain-manifest-name"
        elif name in {"environment.yml", "environment.yaml", "env.yml", "env.yaml"}:
            text = path.read_text(encoding="utf-8", errors="replace")
            if re.search(r"^channels:\s*$", text, re.M) and re.search(r"^dependencies:\s*$", text, re.M):
                reason = "content-qualified-conda-environment-manifest"
        elif name in {".travis.yml", ".travis.yaml"}:
            text = path.read_text(encoding="utf-8", errors="replace")
            if re.search(r"^language:\s*\S+", text, re.M):
                reason = "content-qualified-travis-toolchain-manifest"
        elif path.name.startswith("Dockerfile"):
            reason = "docker-build-manifest-family"
        elif name.startswith("requirements") and name.endswith(".txt"):
            reason = "python-requirements-family"
        elif name.startswith(("build.gradle", "settings.gradle")):
            reason = "gradle-build-manifest-family"
        elif name.endswith(".xcconfig"):
            reason = "xcode-toolchain-config-family"
        elif name.endswith((".tf", ".hcl")):
            reason = "terraform-terragrunt-manifest-family"
        elif lower.startswith(".github/workflows/") and name.endswith((".yml", ".yaml")):
            reason = "ci-toolchain-workflow-family"
        elif "compose" in name and name.endswith((".yml", ".yaml")):
            reason = "compose-manifest-family"
        elif name.startswith("hwaccel.") and name.endswith((".yml", ".yaml")):
            reason = "media-acceleration-manifest-family"
        elif lower.startswith(".vscode/") or "/.vscode/" in lower:
            reason = "editor-toolchain-config-family"
        elif re.match(r"^(?:tsconfig(?:\.[^.]+)?\.json|vitest(?:\.[^.]+)?\.config(?:\.[^.]+)?\.[^.]+|(?:eslint|vite|playwright|svelte|babel|tailwind|docusaurus)\.config\.[^.]+)$", name):
            reason = "node-build-tool-config-family"
        elif path.suffix.lower() in {".sh", ".ps1", ".js", ".mjs", ".cjs"}:
            text = path.read_text(encoding="utf-8", errors="replace")
            if re.search(
                r"^\s*[A-Za-z0-9_]*(?:TOOL|SDK|GENERATOR|ARMNN|RKNN)[A-Za-z0-9_]*VERSION[A-Za-z0-9_]*=['\"]?v?\d+(?:\.\d+)+",
                text, re.M | re.I,
            ) or re.search(
                r"github\.com/(?:ARM-software/armnn|OpenAPITools/openapi-generator)/(?:releases/download|archive/refs/tags)/v?\d+(?:\.\d+)+",
                text, re.I,
            ):
                reason = "content-qualified-version-bearing-tool-script"
            elif re.search(
                r"git\s+clone\s+https://github\.com/flutter/flutter(?:\.git)?\b[^\n]*\s(?:-b|--branch)\s+\S+",
                text, re.I,
            ):
                reason = "content-qualified-floating-toolchain-clone-script"
            elif re.search(r"\b(?:g\+\+|clang\+\+|gcc|clang)(?=\s)[^\n]*-std=(?:c|gnu)\+*\d+", text, re.I) or re.search(
                r"\b(?:armnn)-v?\d+(?:\.\d+)+/", text, re.I,
            ):
                reason = "content-qualified-compiler-toolchain-script"
        elif name == "version" and "/.openapi-generator/" in lower:
            reason = "openapi-generator-version-manifest"
        if reason:
            full = f"Codebase/{rel}"
            candidates.add(full)
            reasons[full] = reason

    for devcontainer in sorted(CODEBASE.rglob("devcontainer.json")):
        rel = devcontainer.relative_to(CODEBASE).as_posix()
        text = re.sub(r"^\s*//.*$", "", devcontainer.read_text(encoding="utf-8", errors="replace"), flags=re.M)
        data = parse_json_text(text, rel)
        compose_files = data.get("dockerComposeFile", []) if isinstance(data, dict) else []
        if isinstance(compose_files, str):
            compose_files = [compose_files]
        for value in compose_files:
            target = (devcontainer.parent / str(value)).resolve(strict=False)
            record_reference(devcontainer, str(value), target, "referenced-by-devcontainer-dockerComposeFile")

    for renovate in sorted(CODEBASE.rglob("renovate.json")):
        text = renovate.read_text(encoding="utf-8", errors="replace")
        for value in re.findall(r'["\'](local>[^"\']+)["\']', text):
            remote, _, config_name = value.removeprefix("local>").partition(":")
            owner, _, repository_path = remote.partition("/")
            target = CODEBASE / "${RENOVATE_REMOTE}" / owner / repository_path / (config_name or "default")
            if target.suffix.lower() != ".json":
                target = target.with_suffix(".json")
            record_reference(renovate, value, target, "renovate-remote-config", "remote")

    for tsconfig in sorted(CODEBASE.rglob("tsconfig*.json")):
        text = tsconfig.read_text(encoding="utf-8", errors="replace")
        extends = re.search(r'["\']extends["\']\s*:\s*["\']([^"\']+)["\']', text)
        if not extends:
            continue
        value = extends.group(1)
        if value.startswith("."):
            target = (tsconfig.parent / value).resolve(strict=False)
            if target.suffix.lower() != ".json":
                file_candidate = target.with_suffix(".json")
                directory_candidate = target / "tsconfig.json"
                target = file_candidate if file_candidate.is_file() or not directory_candidate.is_file() else directory_candidate
            record_reference(tsconfig, value, target, "tsconfig-extends-relative", "relative")
        else:
            target = package_manifest_target(tsconfig, value)
            record_reference(tsconfig, value, target, "tsconfig-extends-package", "package")

    for compose in sorted(
        path for path in CODEBASE.rglob("*")
        if path.is_file() and "compose" in path.name.lower() and path.suffix.lower() in {".yml", ".yaml"}
    ):
        extends_indent: int | None = None
        for raw_line in compose.read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = raw_line.lstrip()
            if not stripped or stripped.startswith("#"):
                continue
            indent = len(raw_line) - len(stripped)
            if re.fullmatch(r"extends:\s*", stripped):
                extends_indent = indent
                continue
            if extends_indent is not None and indent <= extends_indent:
                extends_indent = None
            if extends_indent is not None and (match := re.fullmatch(r"file:\s*['\"]?([^'\"#]+?)['\"]?\s*", stripped)):
                value = match.group(1).strip()
                record_reference(compose, value, compose.parent / value, "compose-extends-file", "relative")

    for pubspec in sorted(CODEBASE.rglob("pubspec.yaml")):
        section = ""
        dependency = ""
        for raw_line in pubspec.read_text(encoding="utf-8", errors="replace").splitlines():
            if not raw_line.strip() or raw_line.lstrip().startswith("#"):
                continue
            indent = len(raw_line) - len(raw_line.lstrip())
            match = re.match(r"\s*([^:#][^:]*):(?:\s+(.*?))?\s*$", raw_line)
            if not match:
                continue
            key = match.group(1).strip().strip("'\"")
            value = (match.group(2) or "").strip().strip("'\"")
            if indent == 0:
                section, dependency = key, ""
            elif section in {"dependencies", "dev_dependencies", "dependency_overrides"} and indent == 2:
                dependency = key
            elif section in {"dependencies", "dev_dependencies", "dependency_overrides"} and indent == 4 and key == "path" and dependency and value:
                record_reference(pubspec, value, pubspec.parent / value / "pubspec.yaml", "pubspec-local-path-dependency", "relative")

    for analysis_options in sorted(CODEBASE.rglob("analysis_options.yaml")):
        text = analysis_options.read_text(encoding="utf-8", errors="replace")
        for value in re.findall(r"^include:\s*(package:[^\s#]+)", text, re.M):
            record_reference(
                analysis_options, value, analysis_options.parent / ".dart_tool" / "package_config.json",
                "dart-analysis-package-include", "package",
            )

    node_config_pattern = re.compile(
        r"^(?:vitest(?:\.[^.]+)?\.config(?:\.[^.]+)?\.[^.]+|(?:eslint|vite|playwright|svelte|babel|tailwind|docusaurus)\.config\.[^.]+)$",
        re.I,
    )
    for config in sorted(path for path in CODEBASE.rglob("*") if path.is_file() and node_config_pattern.match(path.name)):
        text = config.read_text(encoding="utf-8", errors="replace")
        specifiers = set(re.findall(r"\bfrom\s+['\"]([^'\"]+)['\"]", text))
        specifiers.update(re.findall(r"\bimport\s+['\"]([^'\"]+)['\"]", text))
        specifiers.update(re.findall(r"\brequire(?:\.resolve)?\(\s*['\"]([^'\"]+)['\"]\s*\)", text))
        for value in sorted(specifiers):
            if value.startswith((".", "/", "node:")):
                continue
            record_reference(
                config, value, package_manifest_target(config, value),
                "node-tool-config-package", "package",
            )

    for prettier in sorted(CODEBASE.rglob(".prettierrc")):
        try:
            data = parse_json_text(prettier.read_text(encoding="utf-8", errors="replace"), prettier.relative_to(CODEBASE).as_posix())
        except InventoryError:
            continue
        plugins = data.get("plugins", []) if isinstance(data, dict) else []
        for value in plugins if isinstance(plugins, list) else []:
            if isinstance(value, str) and not value.startswith((".", "/")):
                record_reference(
                    prettier, value, package_manifest_target(prettier, value),
                    "prettier-plugin-package", "package",
                )

    for xcconfig in sorted(CODEBASE.rglob("*.xcconfig")):
        text = xcconfig.read_text(encoding="utf-8", errors="replace")
        for optional, value in re.findall(r'^\s*#include(\?)?\s+["<]([^">]+)[">]', text, re.M):
            if optional:
                continue
            record_reference(xcconfig, value, xcconfig.parent / value, "mandatory-xcconfig-include")

    for podfile in sorted(CODEBASE.rglob("Podfile")):
        text = podfile.read_text(encoding="utf-8", errors="replace")
        if "Generated.xcconfig" in text and "must exist" in text:
            record_reference(
                podfile, "Flutter/Generated.xcconfig", podfile.parent / "Flutter" / "Generated.xcconfig",
                "podfile-required-generated-xcconfig",
            )

    for settings in sorted(CODEBASE.rglob("settings.gradle*")):
        text = settings.read_text(encoding="utf-8", errors="replace")
        values = re.findall(r'new\s+File\(rootProject\.projectDir,\s*["\']([^"\']+)["\']\)', text)
        values.extend(re.findall(r'file\(["\']([^"\']+\.properties)["\']\)\.withInputStream', text))
        for value in sorted(set(values)):
            record_reference(settings, value, settings.parent / value, "gradle-required-local-properties")
        for value in re.findall(r'includeBuild\(\s*["\']([^"\']+)["\']\s*\)', text):
            if "$flutterSdkPath" in value or "${flutterSdkPath}" in value:
                normalized = value.replace("$flutterSdkPath", "${flutterSdkPath}")
                target = settings.parent / normalized
                record_reference(settings, value, target, "gradle-include-build", "variable")

    for project in sorted(CODEBASE.rglob("project.pbxproj")):
        text = project.read_text(encoding="utf-8", errors="replace")
        section = text.partition("/* Begin XCLocalSwiftPackageReference section */")[2].partition(
            "/* End XCLocalSwiftPackageReference section */"
        )[0]
        for value in re.findall(r"relativePath\s*=\s*([^;]+);", section):
            relative = value.strip().strip('"')
            record_reference(
                project, relative, project.parent.parent / relative / "Package.swift",
                "xcode-local-swift-package-reference",
            )
        file_references = {
            identifier: value.strip().strip('"')
            for identifier, value in re.findall(
                r"^\s*([0-9A-F]{24})\s+/\*.*?\*/\s*=\s*\{isa\s*=\s*PBXFileReference;[^\n]*?\bpath\s*=\s*([^;]+);",
                text, re.M,
            )
        }
        for identifier in sorted(set(re.findall(r"\bbaseConfigurationReference\s*=\s*([0-9A-F]{24})\b", text))):
            value = file_references.get(identifier)
            if not value:
                raise InventoryError("ManifestReferenceUnresolved", f"{project.relative_to(CODEBASE).as_posix()}: {identifier}")
            target = project.parent.parent / value
            if value.startswith("Target Support Files/"):
                target = project.parent.parent / "Pods" / value
            record_reference(project, value, target, "xcode-base-configuration-reference", "relative")
        podfile_dir = project.parent.parent
        pods_root = podfile_dir / "Pods"

        def record_pods_reference(value: str, mechanism: str) -> None:
            if value.startswith("${PODS_ROOT}/"):
                target = pods_root / value.removeprefix("${PODS_ROOT}/")
            elif value.startswith("${PODS_PODFILE_DIR_PATH}/"):
                target = podfile_dir / value.removeprefix("${PODS_PODFILE_DIR_PATH}/")
            else:
                return
            kind = "variable" if "${CONFIGURATION}" in value else "relative"
            record_reference(project, value, target, mechanism, kind)

        for block_name in ("inputFileListPaths", "outputFileListPaths", "inputPaths"):
            for block in re.findall(rf"\b{block_name}\s*=\s*\((.*?)\);", text, re.S):
                for value in re.findall(r'"([^"\n]+)"', block):
                    record_pods_reference(value, f"xcode-{block_name}")
        for value in sorted(set(re.findall(r'\$\{PODS_ROOT\}/[^"\\]+?\.sh', text))):
            record_pods_reference(value, "xcode-pods-shell-script")
        flutter_scripts = set(re.findall(r'\$(?:\{FLUTTER_ROOT\}|FLUTTER_ROOT)(/[^"\\]+?\.sh)', text))
        for suffix in sorted(flutter_scripts):
            value = f"${{FLUTTER_ROOT}}{suffix}"
            target = podfile_dir / "${FLUTTER_ROOT}" / suffix.removeprefix("/")
            record_reference(project, value, target, "xcode-flutter-root-shell-script", "variable")
    return candidates, dict(sorted(reasons.items())), referenced


def add_declaration(
    rows: list[dict[str, object]], source: str, key: str, value: object,
    kind: str = "concrete", family: str = "toolchain",
) -> None:
    if value is None or value == "":
        return
    rows.append({"family": family, "source": f"Codebase/{source}", "key": key, "value": value, "kind": kind})


def node_constraint_kind(value: str) -> str:
    """Classify package constraints without pretending wildcards are pins."""
    value = value.strip()
    if value in {"*", "latest", "next"} or value.startswith(("workspace:", "catalog:", "link:", "file:")):
        return "reference"
    if re.search(r"(?:^|\s)(?:[<>]=?|[~^])", value) or "||" in value or " - " in value:
        return "range"
    return "concrete" if re.fullmatch(r"v?\d+(?:\.\d+){1,3}(?:[-+][A-Za-z0-9.-]+)?", value) else "reference"


def node_package_name(specifier: str) -> str:
    segments = specifier.split("/")
    return "/".join(segments[:2] if specifier.startswith("@") else segments[:1])


def nearest_package_json(path: Path) -> Path | None:
    for parent in (path.parent, *path.parents):
        if parent == CODEBASE.parent:
            break
        candidate = parent / "package.json"
        if candidate.is_file():
            return candidate
    return None


def extra_declarations(paths: list[str]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for rel in paths:
        path = CODEBASE / rel
        text = path.read_text(encoding="utf-8", errors="replace")
        name = path.name
        lower = rel.lower()

        if lower.startswith(".github/workflows/"):
            for match in re.finditer(
                r"^(?!\s*#)\s*(java|ruby|node|python|flutter|dart|xcode|pnpm)-version(?:-file)?:\s*['\"]?([^'\"\s#]+)",
                text, re.M | re.I,
            ):
                add_declaration(rows, rel, f"{match.group(1).lower()}-version", match.group(2))
            for action, ref in re.findall(r"^(?!\s*#)\s*-?\s*uses:\s*([^@\s]+)@([^\s#]+)", text, re.M):
                kind = "concrete" if re.fullmatch(r"[0-9a-fA-F]{40,64}", ref) else "reference"
                add_declaration(rows, rel, f"action:{action}", ref, kind)
            yaml_stack: list[tuple[int, str]] = []
            for line, raw_line in enumerate(text.splitlines(), 1):
                if not raw_line.strip() or raw_line.lstrip().startswith("#"):
                    continue
                indent = len(raw_line) - len(raw_line.lstrip())
                match = re.match(r"\s*([^:#][^:]*):(?:\s+(.*?))?\s*$", raw_line)
                if not match:
                    continue
                key = match.group(1).strip()
                value = (match.group(2) or "").strip().strip("'\"")
                while yaml_stack and yaml_stack[-1][0] >= indent:
                    yaml_stack.pop()
                parents = [parent_key for _, parent_key in yaml_stack]
                consumed_image = key == "image" and value and (
                    bool(parents and parents[-1] == "container") or "services" in parents
                )
                yaml_stack.append((indent, key))
                if not consumed_image:
                    continue
                image = value
                final_segment = image.split("@", 1)[0].rsplit("/", 1)[-1]
                tag = final_segment.rsplit(":", 1)[1] if ":" in final_segment else ""
                if "@sha256:" in image:
                    kind = "concrete_digest_pinned"
                elif tag and tag != "latest" and "${" not in image:
                    kind = "concrete"
                else:
                    kind = "reference"
                add_declaration(rows, rel, f"workflow-image:line-{line}", image, kind)

        if name in {".travis.yml", ".travis.yaml"}:
            language = re.search(r"^language:\s*([^\s#]+)", text, re.M)
            if language:
                add_declaration(rows, rel, "travis-language", language.group(1), "observed")
            dart_block = re.search(r"^dart:\s*\n(.*?)(?=^[A-Za-z_][A-Za-z0-9_-]*:\s*)", text, re.M | re.S)
            if dart_block:
                for version in re.findall(r"^\s*-\s*['\"]?([^'\"\s#]+)", dart_block.group(1), re.M):
                    add_declaration(rows, rel, "dart-version", version)

        if name == "libs.versions.toml":
            try:
                versions = tomllib.loads(text).get("versions", {})
            except tomllib.TOMLDecodeError as error:
                raise InventoryError("ManifestParseError", f"{rel}: {error}") from error
            for key, value in sorted(versions.items()):
                add_declaration(rows, rel, f"version:{key}", value)

        if name == "Gemfile.lock":
            for gem, version in re.findall(r"^    ([A-Za-z0-9_.-]+) \(([^),]+)", text, re.M):
                add_declaration(rows, rel, f"gem:{gem.lower()}", version)
            bundled = re.search(r"^BUNDLED WITH\s*\n\s+([^\s]+)", text, re.M)
            if bundled:
                add_declaration(rows, rel, "bundler", bundled.group(1))

        if name == "Podfile.lock":
            pods_block = text.partition("PODS:\n")[2].partition("\nDEPENDENCIES:")[0]
            for pod, version in re.findall(r"^  - ([^\s(/:]+)(?:/[^\s(]+)? \(([^):]+)", pods_block, re.M):
                add_declaration(rows, rel, f"pod:{pod.lower()}", version)
            cocoapods = re.search(r"^COCOAPODS:\s*(\S+)", text, re.M)
            if cocoapods:
                add_declaration(rows, rel, "cocoapods", cocoapods.group(1))

        if name == "pubspec.lock":
            sdk_block = re.search(r"^sdks:\s*\n((?:[ \t]+[^\n]*\n?)*)", text, re.M)
            if sdk_block:
                for sdk, constraint in re.findall(r"^\s+(dart|flutter):\s*['\"]([^'\"]+)['\"]", sdk_block.group(1), re.M):
                    add_declaration(rows, rel, f"sdks.{sdk}", constraint, "range")
            analysis_options = path.parent / "analysis_options.yaml"
            if analysis_options.is_file():
                included_packages = set(re.findall(
                    r"^include:\s*package:([^/\s#]+)/", analysis_options.read_text(encoding="utf-8", errors="replace"), re.M,
                ))
                for package in sorted(included_packages):
                    block = re.search(rf"^  {re.escape(package)}:\s*\n(.*?)(?=^  [^\s][^:]*:\s*$|\Z)", text, re.M | re.S)
                    version = re.search(r'^    version:\s*["\']([^"\']+)["\']', block.group(1), re.M) if block else None
                    if version:
                        add_declaration(rows, rel, f"dart-config-package:{package}", version.group(1))

        if name == "dcm_global.yaml":
            version = re.search(r"^version:\s*['\"]([^'\"]+)['\"]", text, re.M)
            if version:
                add_declaration(rows, rel, "dcm", version.group(1), "range")

        if name == ".browserslistrc":
            for line_number, raw_line in enumerate(text.splitlines(), 1):
                query = raw_line.strip()
                if query and not query.startswith("#"):
                    # Browserslist queries resolve against a changing browser-usage
                    # database, so even percentage-only selectors are references.
                    add_declaration(rows, rel, f"browserslist-query:line-{line_number}", query, "reference")

        if name == "pnpm-workspace.yaml":
            section = ""
            extension = ""
            dependency_group = ""
            for raw_line in text.splitlines():
                if not raw_line.strip() or raw_line.lstrip().startswith("#"):
                    continue
                indent = len(raw_line) - len(raw_line.lstrip())
                match = re.match(r"\s*([^:#][^:]*):(?:\s+(.*?))?\s*$", raw_line)
                if not match:
                    continue
                key = match.group(1).strip().strip("'\"")
                value = (match.group(2) or "").strip().strip("'\"")
                if indent == 0:
                    section, extension, dependency_group = key, "", ""
                elif section == "overrides" and indent == 2 and value:
                    add_declaration(rows, rel, f"pnpm-override:{key.lower()}", value, node_constraint_kind(value))
                elif section == "packageExtensions":
                    if indent == 2:
                        extension, dependency_group = key, ""
                    elif indent == 4:
                        dependency_group = key
                    elif indent == 6 and extension and dependency_group and value:
                        add_declaration(
                            rows, rel,
                            f"pnpm-package-extension:{extension.lower()}:{dependency_group.lower()}:{key.lower()}",
                            value, node_constraint_kind(value),
                        )

        if name == "renovate.json":
            for match in re.finditer(r'["\'](local>[^"\']+)["\']', text):
                line = text.count("\n", 0, match.start()) + 1
                add_declaration(rows, rel, f"renovate-extends:line-{line}", match.group(1), "reference")
            ruby_rule = re.search(
                r'["\']matchPackageNames["\']\s*:\s*\[\s*["\']ruby["\']\s*\].*?'
                r'["\']matchCurrentVersion["\']\s*:\s*["\']([^"\']+)["\']',
                text, re.S,
            )
            if ruby_rule:
                add_declaration(rows, rel, "renovate-package:ruby", ruby_rule.group(1), "range")

        if name.lower() == "makefile" and re.search(r"\bpnpm\s+exec\s+renovate\b", text):
            add_declaration(rows, rel, "package-manager-tool:renovate", "unversioned", "reference")

        if name == "package.json":
            data = parse_json_text(text, rel)
            if isinstance(data, dict):
                declared = {
                    str(package): str(constraint)
                    for section in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies")
                    for package, constraint in ((data.get(section) or {}).items() if isinstance(data.get(section), dict) else [])
                }
                config_pattern = re.compile(
                    r"^(?:vitest(?:\.[^.]+)?\.config(?:\.[^.]+)?\.[^.]+|(?:eslint|vite|playwright|svelte|babel|tailwind|docusaurus)\.config\.[^.]+)$",
                    re.I,
                )
                specifiers: set[str] = set()
                for config in path.parent.rglob("*"):
                    if not config.is_file() or nearest_package_json(config) != path:
                        continue
                    if config_pattern.match(config.name):
                        config_text = config.read_text(encoding="utf-8", errors="replace")
                        specifiers.update(re.findall(r"\bfrom\s+['\"]([^'\"]+)['\"]", config_text))
                        specifiers.update(re.findall(r"\bimport\s+['\"]([^'\"]+)['\"]", config_text))
                        specifiers.update(re.findall(r"\brequire(?:\.resolve)?\(\s*['\"]([^'\"]+)['\"]\s*\)", config_text))
                prettier = path.parent / ".prettierrc"
                if prettier.is_file():
                    prettier_data = parse_json_text(prettier.read_text(encoding="utf-8", errors="replace"), prettier.relative_to(CODEBASE).as_posix())
                    if isinstance(prettier_data, dict) and isinstance(prettier_data.get("plugins"), list):
                        specifiers.update(value for value in prettier_data["plugins"] if isinstance(value, str))
                for specifier in sorted(specifiers):
                    if specifier.startswith((".", "/", "node:")):
                        continue
                    package = node_package_name(specifier)
                    if package in declared:
                        value = declared[package]
                        add_declaration(rows, rel, f"node-config-package:{package}", value, node_constraint_kind(value))

        if re.match(r"^tsconfig(?:\.[^.]+)?\.json$", name.lower()):
            target = re.search(r'["\']target["\']\s*:\s*["\']([^"\']+)["\']', text, re.I)
            if target:
                value = target.group(1).lower()
                add_declaration(rows, rel, "typescript-target", value, "reference" if value == "esnext" else "concrete")
            lib_block = re.search(r'["\']lib["\']\s*:\s*\[(.*?)\]', text, re.I | re.S)
            if lib_block:
                for value in re.findall(r'["\'](es(?:\d+|next)(?:\.[a-z0-9.-]+)?)["\']', lib_block.group(1), re.I):
                    normalized = value.lower()
                    add_declaration(rows, rel, f"typescript-lib:{normalized}", normalized, "reference" if normalized.startswith("esnext") else "concrete")

        if name.lower().startswith("vite.config."):
            for match in re.finditer(r"\btarget\s*:\s*['\"]([^'\"]+)['\"]", text):
                line = text.count("\n", 0, match.start()) + 1
                value = match.group(1).lower()
                add_declaration(rows, rel, f"node-build-target:line-{line}", value, "reference" if value == "esnext" else "concrete")

        if name.lower().startswith("eslint.config."):
            for match in re.finditer(r"\becmaVersion\s*:\s*['\"]?([A-Za-z0-9.]+)", text):
                line = text.count("\n", 0, match.start()) + 1
                value = match.group(1).lower()
                kind = "reference" if value == "latest" else "concrete"
                add_declaration(rows, rel, f"ecmascript-version:line-{line}", value, kind)

        if name == "Package.resolved":
            data = parse_json_text(text, rel)
            if isinstance(data, dict):
                for pin in data.get("pins", []):
                    state = pin.get("state", {}) if isinstance(pin, dict) else {}
                    add_declaration(
                        rows, rel, f"swift-package:{str(pin.get('identity', '')).lower()}",
                        state.get("version") or state.get("revision"),
                    )

        if name == "Package.swift":
            match = re.search(r"swift-tools-version:\s*([^\s]+)", text)
            if match:
                add_declaration(rows, rel, "swift-tools-version", match.group(1))

        if name == "openapitools.json":
            data = parse_json_text(text, rel)
            generator = data.get("generator-cli", {}) if isinstance(data, dict) else {}
            if isinstance(generator, dict):
                add_declaration(rows, rel, "openapi-generator-cli", generator.get("version"))

        if name == "VERSION" and "/.openapi-generator/" in f"/{lower}":
            add_declaration(rows, rel, "openapi-generator-cli", text.strip())

        if name == ".terraform.lock.hcl":
            for provider, block in re.findall(r'provider\s+"([^"]+)"\s*\{(.*?)\n\}', text, re.S):
                version = re.search(r'^\s*version\s*=\s*"([^"]+)"', block, re.M)
                if version:
                    add_declaration(rows, rel, f"terraform-provider:{provider}", version.group(1))

        if name.endswith(".tf"):
            required = re.search(r'^\s*required_version\s*=\s*"([^"]+)"', text, re.M)
            if required:
                add_declaration(rows, rel, "terraform-required-version", required.group(1), "range")
            for block in re.findall(r"\b[A-Za-z0-9_-]+\s*=\s*\{(.*?)\n\s*\}", text, re.S):
                source = re.search(r'^\s*source\s*=\s*"([^"]+)"', block, re.M)
                version = re.search(r'^\s*version\s*=\s*"([^"]+)"', block, re.M)
                if source and version:
                    add_declaration(rows, rel, f"terraform-provider:{source.group(1)}", version.group(1))

        if name == "AppFrameworkInfo.plist":
            minimum = re.search(r"<key>MinimumOSVersion</key>\s*<string>([^<]+)</string>", text)
            if minimum:
                add_declaration(rows, rel, "ios-minimum-os-version", minimum.group(1))

        if name == "CMakeLists.txt":
            minimum = re.search(r"cmake_minimum_required\s*\(\s*VERSION\s+([^\s)]+)", text, re.I)
            standard = re.search(r"set\s*\(\s*CMAKE_C_STANDARD\s+([^\s)]+)", text, re.I)
            if minimum:
                add_declaration(rows, rel, "cmake-minimum-version", minimum.group(1))
            if standard:
                add_declaration(rows, rel, "c-language-standard", standard.group(1))

        if name == ".metadata":
            revision = re.search(r"^\s*revision:\s*([^\s#]+)", text, re.M)
            channel = re.search(r"^\s*channel:\s*([^\s#]+)", text, re.M)
            if revision:
                add_declaration(rows, rel, "flutter-project-revision", revision.group(1))
            if channel:
                add_declaration(rows, rel, "flutter-project-channel", channel.group(1), "observed")

        if name in {"environment.yml", "environment.yaml", "env.yml", "env.yaml"}:
            if re.search(r"^channels:\s*$", text, re.M) and re.search(r"^dependencies:\s*$", text, re.M):
                environment_name = re.search(r"^name:\s*([^\s#]+)", text, re.M)
                if environment_name:
                    add_declaration(rows, rel, "conda", environment_name.group(1), "observed")
                for dependency, version in re.findall(
                    r"^\s*-\s*([A-Za-z0-9_.-]+)=([^=\s#]+)(?:=[^\s#]+)?\s*$", text, re.M,
                ):
                    add_declaration(rows, rel, f"conda:{dependency.lower()}", version)
                pip_block = re.search(r"^\s{2}-\s+pip:\s*\n((?:\s{6}-[^\n]+\n?)*)", text, re.M)
                if pip_block:
                    for requirement in re.findall(r"^\s{6}-\s*([^\s#]+)", pip_block.group(1), re.M):
                        if requirement.startswith("git+"):
                            repository = requirement.removeprefix("git+").split("@", 1)[0].removesuffix(".git")
                            repository_key = re.sub(r"^https?://", "", repository, flags=re.I).lower()
                            ref = requirement.rsplit("@", 1)[1] if "@" in requirement else ""
                            kind = "concrete" if re.fullmatch(r"[0-9a-fA-F]{40,64}|v?\d+(?:\.\d+){1,3}", ref) else "reference"
                            add_declaration(rows, rel, f"conda-pip-vcs:{repository_key}", requirement, kind)
                        else:
                            package = re.match(r"([A-Za-z0-9_.-]+)(.*)", requirement)
                            if package:
                                constraint = package.group(2) or "*"
                                add_declaration(rows, rel, f"conda-pip:{package.group(1).lower()}", constraint, node_constraint_kind(constraint))

        if name == "example.env":
            for key, value in re.findall(r"^(?!\s*#)\s*([A-Za-z0-9_]*VERSION[A-Za-z0-9_]*)=([^\s#]+)", text, re.M):
                kind = "concrete" if re.fullmatch(r"v?\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?", value) else "reference"
                add_declaration(rows, rel, f"env:{key.lower()}", value, kind)

        if name.startswith("Dockerfile"):
            stage_aliases = {
                alias.lower() for alias in re.findall(r"^\s*FROM\s+\S+\s+AS\s+(\S+)", text, re.M | re.I)
            }
            for key, value in re.findall(
                r"^\s*(?:ARG|ENV)\s+([A-Za-z0-9_]*VERSION[A-Za-z0-9_]*)\s*(?:=|\s)\s*['\"]?([^'\"\s\\]+)",
                text, re.M | re.I,
            ):
                kind = "reference" if "${" in value or value.startswith("$") else "concrete"
                add_declaration(rows, rel, f"docker-env:{key.lower()}", value, kind)
            for image in re.findall(r"^\s*COPY\s+[^\n]*?--from=([^\s]+)", text, re.M | re.I):
                if image.lower() in stage_aliases:
                    continue
                image_name = image.split("@", 1)[0]
                final_segment = image_name.rsplit("/", 1)[-1]
                if ":" in final_segment:
                    image_name = image_name.rsplit(":", 1)[0]
                tag = image.split("@", 1)[0].rsplit(":", 1)[-1] if ":" in final_segment else None
                pinned = "@sha256:" in image or bool(tag and tag != "latest" and "${" not in image)
                kind = "concrete_digest_pinned" if "@sha256:" in image else "concrete" if pinned else "reference"
                add_declaration(rows, rel, f"docker-copy-image:{image_name}", image, kind)
            for repository, version in re.findall(
                r"https://(github\.com/[^/\s]+/[^/\s]+)/releases/download/([^/\s\"']+)", text,
            ):
                add_declaration(rows, rel, f"docker-release:{repository.lower()}", version)
            for filename in re.findall(r"https://[^\s\"']+/([^/\s\"']+\.deb)", text):
                package_version = re.match(r"(.+?)[_-](\d+(?:\.\d+){1,4})(?:[+_-])", filename)
                if package_version:
                    add_declaration(
                        rows, rel, f"docker-deb:{package_version.group(1).lower()}", package_version.group(2),
                    )
            for install_block in re.findall(r"apt-get\s+install\b(.*?)(?=&&|$)", text, re.S | re.I):
                for package, version in re.findall(r"\b([A-Za-z0-9.+-]+)=([0-9][A-Za-z0-9.+:~-]*)", install_block):
                    add_declaration(rows, rel, f"docker-package:{package.lower()}", version)
            for package, version in re.findall(r"npm\s+install\s+--global\s+([A-Za-z0-9_.+-]+)@([^\s\\]+)", text, re.I):
                add_declaration(rows, rel, f"docker-tool:{package.lower()}", version, node_constraint_kind(version))
            for install_block in re.findall(r"\bapt(?:-get)?\s+install\b(.*?)(?=&&|$)", text, re.S | re.I):
                clean_block = re.sub(r"#.*", "", install_block)
                for package in re.findall(r"(?:^|\s)([A-Za-z0-9][A-Za-z0-9.+-]*)(?=\s|\\|$)", clean_block):
                    lowered = package.lower()
                    if match := re.fullmatch(r"openjdk-(\d+)-jre-headless", lowered):
                        add_declaration(rows, rel, "docker-tool:java", f"{match.group(1)}.x", "reference")
                    elif lowered in {"dcm", "g++", "ccache"}:
                        add_declaration(rows, rel, f"docker-tool:{lowered}", "unversioned", "reference")

        if path.suffix.lower() in {".sh", ".ps1", ".js", ".mjs", ".cjs"} and is_version_bearing_tool_script(rel):
            for key, value in re.findall(
                r"^\s*([A-Za-z0-9_]*VERSION[A-Za-z0-9_]*)=['\"]?(v?\d+(?:\.\d+)+(?:[-+][A-Za-z0-9.-]+)?)",
                text, re.M | re.I,
            ):
                add_declaration(rows, rel, f"script:{key.lower()}", value)
            for repository, version in re.findall(
                r"https://(github\.com/[^/\s]+/[^/\s]+)/(?:releases/download|archive/refs/tags)/(v?\d+(?:\.\d+)+)",
                text, re.I,
            ):
                add_declaration(rows, rel, f"script-release:{repository.lower()}", version)
            for branch in re.findall(
                r"git\s+clone\s+https://github\.com/flutter/flutter(?:\.git)?\b[^\n]*\s(?:-b|--branch)\s+([^\s]+)",
                text, re.I,
            ):
                value = branch.strip("'\"")
                kind = "concrete" if re.fullmatch(r"[0-9a-fA-F]{40,64}|v?\d+(?:\.\d+){1,3}", value) else "reference"
                add_declaration(rows, rel, "script-git:github.com/flutter/flutter", value, kind)
            for install_line in re.findall(r"^\s*brew\s+install\s+([^#\n]+)", text, re.M):
                for package in re.findall(r"(?:^|\s)([A-Za-z0-9_.+-]+)(?:@([0-9][A-Za-z0-9_.+-]*))?", install_line):
                    name, version = package
                    add_declaration(
                        rows, rel, f"script-package:brew:{name.lower()}", version or "unversioned",
                        "concrete" if version else "reference",
                    )
            for compiler, standard in re.findall(
                r"\b(g\+\+|clang\+\+|gcc|clang)(?=\s)[^\n]*?-std=((?:c|gnu)\+*\d+)", text, re.I,
            ):
                add_declaration(rows, rel, f"compiler-language-standard:{compiler.lower()}", standard.lower())
            for tool, version in re.findall(r"\b(armnn)-v?(\d+(?:\.\d+)+)/", text, re.I):
                add_declaration(rows, rel, f"script-tool-source:{tool.lower()}", version)

        if name == "Podfile":
            match = re.search(r"^platform\s+:ios,\s*['\"]([^'\"]+)", text, re.M)
            if match:
                add_declaration(rows, rel, "ios-deployment-target", match.group(1))

        if name == "project.pbxproj" or name.endswith(".xcconfig"):
            for match in re.finditer(
                r"^\s*(IPHONEOS_DEPLOYMENT_TARGET|MACOSX_DEPLOYMENT_TARGET|SWIFT_VERSION|CLANG_CXX_LANGUAGE_STANDARD|GCC_C_LANGUAGE_STANDARD)\s*=\s*([^;\s]+)",
                text, re.M,
            ):
                key, value = match.group(1).lower(), match.group(2)
                if name == "project.pbxproj":
                    key = f"{key}:line-{text.count(chr(10), 0, match.start()) + 1}"
                add_declaration(rows, rel, key, value)
            if name == "project.pbxproj":
                for owner, package, kind, minimum in re.findall(
                    r'repositoryURL\s*=\s*"https://github\.com/([^/\"]+)/([^/\";]+?)(?:\.git)?";.*?kind\s*=\s*([^;]+);.*?minimumVersion\s*=\s*([^;]+);',
                    text, re.S,
                ):
                    value = minimum.strip()
                    if kind.strip() == "upToNextMajorVersion" and (parsed := numeric_version(value)):
                        value = f">={value} <{parsed[0] + 1}.0.0"
                    add_declaration(rows, rel, f"swift-package-minimum:{package.lower()}", value, "range")

        if name.startswith(("build.gradle", "settings.gradle")):
            for key, value in re.findall(
                r"\b(compileSdk|minSdk|targetSdk|ndkVersion|jvmTarget)\b\s*(?:=\s*)?['\"]?([A-Za-z0-9_.+-]+)",
                text,
            ):
                kind = "concrete" if re.fullmatch(r"\d+(?:\.\d+)*(?:[-+][A-Za-z0-9.-]+)?", value) else "reference"
                add_declaration(rows, rel, key, value, kind)
            for compatibility, version in re.findall(
                r"\b(sourceCompatibility|targetCompatibility)\b\s*(?:=\s*)?JavaVersion\.VERSION_(\d+)", text,
            ):
                add_declaration(rows, rel, f"java-{compatibility.removesuffix('Compatibility').lower()}-compatibility", version)
            for plugin, version in re.findall(r"id\s+['\"]([^'\"]+)['\"]\s+version\s+['\"]([^'\"]+)", text):
                add_declaration(rows, rel, f"gradle-plugin:{plugin}", version)

        if name == "devcontainer.json":
            data = parse_json_text(re.sub(r"//.*", "", text), rel)
            if isinstance(data, dict):
                add_declaration(rows, rel, "devcontainer-image", data.get("image"))
                for feature, value in sorted((data.get("features") or {}).items()):
                    feature_name, separator, feature_version = feature.rpartition(":")
                    if separator and "/" in feature_name:
                        kind = "concrete" if re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?", feature_version) else "reference"
                        add_declaration(rows, rel, f"devcontainer-feature:{feature_name}", feature_version, kind)
                    add_declaration(rows, rel, f"devcontainer-feature-options:{feature}", value, "observed")

        if "compose" in name and name.endswith((".yml", ".yaml")):
            for image in re.findall(r"^\s*image:\s*['\"]?([^'\"\s#]+)", text, re.M):
                tag = image.rsplit(":", 1)[-1] if ":" in image.rsplit("/", 1)[-1] else None
                pinned = "@sha256:" in image or bool(tag and tag != "latest" and "${" not in image)
                kind = "concrete" if pinned else "reference"
                image_name = image.split("@", 1)[0]
                final_segment = image_name.rsplit("/", 1)[-1]
                if ":${" in image_name:
                    image_name = image_name.split(":${", 1)[0]
                elif ":" in final_segment:
                    image_name = image_name.rsplit(":", 1)[0]
                add_declaration(rows, rel, f"compose-image:{image_name}", image, kind)

    return rows


def relevant_declaration(row: dict[str, object]) -> bool:
    key = str(row.get("key", "")).lower()
    source = str(row.get("source", "")).lower()
    return (
        row.get("family") in {"toolchain", "lockfile"}
        or key in {
            "packagemanager", "engines.node", "engines.pnpm", "environment.sdk",
            "environment.flutter", "requires-python", "sdks.dart", "sdks.flutter",
        }
        or source.endswith(".nvmrc")
    )


def superseded_prior_compose_declaration(row: dict[str, object]) -> bool:
    source = str(row.get("source", "")).lower()
    key = str(row.get("key", "")).lower()
    name = Path(source).name
    return "compose" in name and name.endswith((".yml", ".yaml")) and key.startswith("image ")


def internal_docker_stage_declaration(row: dict[str, object]) -> bool:
    source = str(row.get("source", ""))
    key = str(row.get("key", ""))
    value = str(row.get("value", ""))
    if not source.startswith("Codebase/") or not Path(source).name.startswith("Dockerfile") or not key.startswith("FROM "):
        return False
    path = LAMHA / source
    aliases = {
        alias.lower()
        for alias in re.findall(r"^\s*FROM\s+\S+\s+AS\s+(\S+)", path.read_text(encoding="utf-8", errors="replace"), re.M | re.I)
    }
    return value.lower() in aliases


def superseded_prior_declaration(row: dict[str, object]) -> bool:
    """Drop predecessor rows superseded by stricter package semantics."""
    return superseded_prior_compose_declaration(row) or internal_docker_stage_declaration(row)


def deduplicate(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    seen = set()
    result = []
    for row in rows:
        key = (
            row.get("family"), row.get("source"), row.get("key"), row.get("kind"),
            json.dumps(row.get("value"), sort_keys=True, ensure_ascii=False),
        )
        if key not in seen:
            seen.add(key)
            result.append(row)
    return sorted(result, key=lambda row: (str(row["source"]), str(row["key"]), str(row["value"])))


def declaration_categories(row: dict[str, object]) -> list[str]:
    source = str(row.get("source", "")).lower()
    text = " ".join(str(row.get(key, "")) for key in ("source", "key", "value")).lower()
    categories = []
    tests = {
        "node": r"\bnode\b|setup-node|typescript|tsconfig|ecmascript|eslint|vite|browserslist",
        "package-manager": r"package.?manager|\bpnpm\b|\bnpm\b|\byarn\b|\bbun\b|\bpip\b|\bconda\b|\brenovate\b|lockfileversion",
        "rust": r"\brustc?\b|\bcargo\b|rust-toolchain",
        "python": r"\bpython\b|setup-python|pyproject|uv\.lock|\buv\b|\bconda\b|environment\.ya?ml|/env\.ya?ml",
        "media": r"ffmpeg|\bdcm\b|exiftool",
        "platform": r"flutter|\bdart\b|\bjava\b|gradle|android|ios|macos|xcode|swift|pod:|cocoapods|gem:|ruby|docker|compose|cmake|cuda|pytorch|armnn|rknn|opentofu|terraform|terragrunt|wrangler|extism|binaryen|openapi-generator|immich_version",
    }
    for category, pattern in tests.items():
        if re.search(pattern, text):
            categories.append(category)
    if not categories and row.get("family") in {"toolchain", "lockfile"}:
        categories.append("platform")
    if "/mobile/" in source and "platform" not in categories:
        categories.append("platform")
    return sorted(set(categories))


def intrinsic_categories(rel: str) -> set[str]:
    name = Path(rel).name
    lower = rel.lower()
    categories: set[str] = set()
    if name == ".nvmrc":
        categories.add("node")
    if name in {".npmrc", ".npmignore", ".pnpmfile.cjs", "package.json", "package-lock.json", "pnpm-lock.yaml", "pnpm-workspace.yaml", "yarn.lock", "bun.lock", "bun.lockb", "renovate.json"}:
        categories.add("package-manager")
    if name in {"Cargo.toml", "Cargo.lock", "rust-toolchain", "rust-toolchain.toml"}:
        categories.add("rust")
    if name in {"pyproject.toml", "uv.lock", ".python-version", "Pipfile", "Pipfile.lock", "poetry.lock", "environment.yml", "environment.yaml", "env.yml", "env.yaml"} or name.startswith("requirements"):
        categories.add("python")
    if name in {".browserslistrc", ".prettierrc", ".prettierignore"} or re.match(r"^(?:tsconfig(?:\.[^.]+)?\.json|vitest(?:\.[^.]+)?\.config(?:\.[^.]+)?\.[^.]+|(?:eslint|vite|playwright|svelte|babel|tailwind|docusaurus)\.config\.[^.]+)$", name.lower()):
        categories.add("node")
    if name in {
        "pubspec.yaml", "pubspec.lock", "Podfile", "Podfile.lock", "Gemfile", "Gemfile.lock",
        "Package.swift", "Package.resolved", "gradle.properties", "libs.versions.toml",
        "gradle-wrapper.properties", "CMakeLists.txt", "project.pbxproj", "devcontainer.json",
        "openapitools.json", ".terraform.lock.hcl", ".metadata", "VERSION", "example.env",
        ".travis.yml", ".travis.yaml", ".dockerignore", ".gitmodules", ".openapi-generator-ignore",
        ".editorconfig", ".env",
        "analysis_options.yaml", "build.yaml", "dcm_global.yaml", "devtools_options.yaml",
        "flutter_native_splash.yaml", "Fastfile", "Appfile", "AppFrameworkInfo.plist",
        "Makefile", "makefile",
    } or name.startswith(("build.gradle", "settings.gradle", "Dockerfile")) or name.endswith(".xcconfig"):
        categories.add("platform")
    if name.lower().endswith((".tf", ".hcl")):
        categories.add("platform")
    if name.lower().startswith("hwaccel.") and name.lower().endswith((".yml", ".yaml")):
        categories.update({"media", "platform"})
    if lower.startswith(".vscode/") or "/.vscode/" in lower:
        categories.add("platform")
    if lower.startswith(".github/workflows/") or re.search(r"(^|/)[^/]*compose[^/]*\.ya?ml$", lower):
        categories.add("platform")
    return categories


def content_categories(rel: str) -> set[str]:
    """Classify generic manifests (especially mise task files) by their bytes."""
    if Path(rel).name not in {"mise.toml", "mise.lock", "Makefile", "makefile"}:
        return set()
    text = (CODEBASE / rel).read_text(encoding="utf-8", errors="replace").lower()
    categories = set()
    checks = {
        "node": r"\bnode\b",
        "package-manager": r"\bpnpm\b|\bnpm\b|\byarn\b|\bbun\b|\brenovate\b",
        "rust": r"\brustc?\b|\bcargo\b",
        "python": r"\bpython\b|\buv\b|\bpip\b|\bconda\b",
        "media": r"ffmpeg|\bdcm\b|exiftool",
        "platform": r"flutter|\bdart\b|\bjava\b|gradle|docker|compose|cmake|opentofu|terraform|terragrunt|wrangler|extism|binaryen|openapi-generator",
    }
    for category, pattern in checks.items():
        if re.search(pattern, text):
            categories.add(category)
    return categories


def normalized_tool(row: dict[str, object]) -> str | None:
    key = str(row.get("key", "")).lower()
    text = f"{key} {row.get('value', '')}".lower()
    exact = {
        "node": "node", "pnpm": "pnpm", "python": "python", "uv": "uv",
        "aqua:flutter/flutter": "flutter", "flutter": "flutter", "sdks.flutter": "flutter",
        "environment.flutter": "flutter", "sdks.dart": "dart", "environment.sdk": "dart", "dart-version": "dart",
        "java": "java", "gradle": "gradle", "wrangler": "wrangler", "dcm": "dcm",
        "opentofu": "tofu", "terragrunt": "terragrunt", "bundler": "bundler",
        "cocoapods": "pod", "java-version": "java", "ruby-version": "ruby",
        "conda:python": "python", "conda:pip": "pip",
        "conda": "conda",
        "docker-env:flutter_version": "flutter",
        "docker-copy-image:ghcr.io/astral-sh/uv": "uv",
        "docker-copy-image:ghcr.io/jdx/mise": "mise",
        "script:openapi_generator_version": "openapi-generator-cli",
        "docker-env:armnn_version": "armnn",
        "script-release:github.com/arm-software/armnn": "armnn",
        "script-tool-source:armnn": "armnn",
        "compiler-language-standard:g++": "g++",
        "docker-tool:corepack": "corepack",
        "docker-tool:java": "java",
        "docker-tool:dcm": "dcm",
        "docker-tool:g++": "g++",
        "docker-tool:ccache": "ccache",
        "renovate-package:ruby": "ruby",
        "openapi-generator-cli": "openapi-generator-cli",
        "cmake-minimum-version": "cmake",
        "java-source-compatibility": "java", "java-target-compatibility": "java",
    }
    if key in exact:
        return exact[key]
    if key.startswith("renovate-extends:") or key == "package-manager-tool:renovate":
        return "renovate"
    if key == "packagemanager":
        return str(row.get("value", "")).split("@", 1)[0].lower()
    if key == "gem:fastlane":
        return "fastlane"
    mappings = {
        "github:cqlabs/homebrew-dcm": "dcm",
        "github:jellyfin/jellyfin-ffmpeg": "ffmpeg",
        "github:extism/cli": "extism",
        "github:extism/js-pdk": "extism-js-pdk",
        "github:webassembly/binaryen": "binaryen",
        "npm:oazapfts": "oazapfts",
    }
    for prefix, tool in mappings.items():
        if key == prefix:
            return tool
    if key.startswith("from node:") or re.search(r"\bnode:\d", text):
        return "node"
    if key.startswith("from python:") or re.search(r"\bpython:\d", text):
        return "python"
    return None


def comparable_value(tool: str, row: dict[str, object]) -> str | None:
    value = row.get("value")
    kind = str(row.get("kind", ""))
    if not isinstance(value, str) or kind not in {"concrete", "concrete_digest_pinned", "range"}:
        return None
    text = value.strip()
    if tool == "pnpm" and "@" in text:
        text = text.split("@", 1)[1].split("+", 1)[0]
    if text.startswith((">", "<", "=", "^", "~")):
        text = re.sub(r"\s+", "", text)

        def normalize_bound(match: re.Match[str]) -> str:
            parts = match.group(2).split(".")
            while len(parts) > 1 and parts[-1] == "0":
                parts.pop()
            return match.group(1) + ".".join(parts)

        text = re.sub(r"(>=|<=|>|<|=|\^|~)(\d+(?:\.\d+)*)", normalize_bound, text)
        return f"range:{text}"
    if tool in {"node", "python", "uv", "mise"}:
        match = re.search(rf"(?:^|/){tool}:(\d+(?:\.\d+){{0,3}})", text)
        if match:
            return match.group(1)
    if tool == "armnn" and (parsed := numeric_version(text)):
        return ".".join(str(part) for part in parsed)
    return text


def numeric_version(value: str) -> tuple[int, ...] | None:
    match = re.match(r"^v?(\d+(?:\.\d+)*)", value)
    return tuple(int(part) for part in match.group(1).split(".")) if match else None


def range_allows(version: str, constraint: str) -> bool | None:
    candidate = numeric_version(version)
    comparisons = re.findall(r"(>=|<=|>|<|=)(\d+(?:\.\d+)*)", constraint)
    if candidate is None:
        return None
    if not comparisons:
        exact = numeric_version(constraint)
        if exact is None:
            return None
        width = max(len(candidate), len(exact))
        return candidate + (0,) * (width - len(candidate)) == exact + (0,) * (width - len(exact))
    for operator, bound_text in comparisons:
        bound = tuple(int(part) for part in bound_text.split("."))
        width = max(len(candidate), len(bound))
        left = candidate + (0,) * (width - len(candidate))
        right = bound + (0,) * (width - len(bound))
        if operator == ">=" and not left >= right:
            return False
        if operator == ">" and not left > right:
            return False
        if operator == "<=" and not left <= right:
            return False
        if operator == "<" and not left < right:
            return False
        if operator == "=" and not left == right:
            return False
    return True


def npm_caret_interval(constraint: str) -> tuple[tuple[int, int, int], tuple[int, int, int]] | None:
    match = re.fullmatch(r"\^(\d+)(?:\.(\d+))?(?:\.(\d+))?", constraint)
    if not match:
        return None
    specified = [int(part) if part is not None else 0 for part in match.groups()]
    lower = tuple(specified)
    major, minor, patch = lower
    if major:
        upper = (major + 1, 0, 0)
    elif match.group(2) is None:
        upper = (1, 0, 0)
    elif minor:
        upper = (0, minor + 1, 0)
    elif match.group(3) is None:
        upper = (0, 1, 0)
    else:
        upper = (0, 0, patch + 1)
    return lower, upper


def npm_caret_ranges_overlap(constraints: list[str]) -> bool | None:
    intervals = [npm_caret_interval(constraint) for constraint in constraints]
    if not intervals or any(interval is None for interval in intervals):
        return None
    concrete_intervals = [interval for interval in intervals if interval is not None]
    return max(lower for lower, _ in concrete_intervals) < min(upper for _, upper in concrete_intervals)


def derive_ambiguities(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    groups: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        key = str(row.get("key", "")).lower()
        source = str(row.get("source", ""))
        context_scoped = re.match(
            r"^(?:node-config-package:|compiler-language-standard:|typescript-target|typescript-lib:|node-build-target:|ecmascript-version:|"
            r"c-language-standard|java-(?:source|target)-compatibility|"
            r"(?:iphoneos|macosx)_deployment_target|swift_version|"
            r"clang_cxx_language_standard|gcc_c_language_standard)",
            key,
        ) is not None
        tool = None if context_scoped else normalized_tool(row)
        if context_scoped:
            source_path = LAMHA / source
            owner = nearest_package_json(source_path)
            context = owner.parent.relative_to(CODEBASE).as_posix() if owner else str(Path(source).parent)
            group = f"{key}@{context}"
        else:
            group = tool or key
        value = comparable_value(tool or group, row)
        if value:
            groups.setdefault(group, []).append({**row, "comparableValue": value})
    findings = []
    for group, declarations in sorted(groups.items()):
        exact = [row for row in declarations if not str(row["comparableValue"]).startswith("range:")]
        ranges = [row for row in declarations if str(row["comparableValue"]).startswith("range:")]
        exact_versions = sorted({str(row["comparableValue"]) for row in exact})
        range_versions = sorted({str(row["comparableValue"]).removeprefix("range:") for row in ranges})
        incompatible_ranges = [
            row for row in ranges
            if any(range_allows(version, str(row["comparableValue"]).removeprefix("range:")) is False for version in exact_versions)
        ]
        conflicting = []
        if len(exact_versions) > 1 or incompatible_ranges:
            conflicting.extend(exact)
        range_text_conflict = len(range_versions) > 1
        if group.startswith("node-config-package:") and npm_caret_ranges_overlap(range_versions) is True:
            range_text_conflict = False
        if range_text_conflict:
            conflicting.extend(ranges)
        else:
            conflicting.extend(incompatible_ranges)
        if not conflicting:
            continue
        versions = sorted({str(row["comparableValue"]).removeprefix("range:") for row in conflicting})
        if versions:
            categories = sorted({category for row in conflicting for category in row["categories"]}) or ["platform"]
            findings.append(
                {
                    "status": "REVIEW_REQUIRED",
                    "reason": "AMBIGUOUS_REPOSITORY_VERSION",
                    "item": f"repository-version:{group}",
                    "categories": categories,
                    "versions": versions,
                    "sources": sorted({str(row["source"]) for row in conflicting}),
                }
            )
    return findings


def derive_probe_tools(rows: list[dict[str, object]]) -> tuple[set[str], set[str]]:
    declared = {tool for row in rows if (tool := normalized_tool(row))}
    return BASE_PROBE_TOOLS | {tool for tool in declared if tool in PROBE_MAP}, declared - set(PROBE_MAP)


def sanitize_output(value: str) -> str:
    home = str(Path.home())
    return value.replace(home, "%USERPROFILE%").replace(str(LAMHA), "<LAMHA>")[:4000]


def probe_host(tool: str) -> dict[str, object]:
    if tool not in PROBE_MAP:
        raise InventoryError("CommandProbeRejected", f"non-allowlisted probe: {tool}")
    command, args, category = PROBE_MAP[tool]
    executable = shutil.which(command)
    record: dict[str, object] = {
        "category": category,
        "tool": tool,
        "command": " ".join((command, *args)),
        "executable": Path(executable).name if executable else None,
    }
    if executable is None:
        return {**record, "status": "REVIEW_REQUIRED", "reason": "HOST_TOOL_UNAVAILABLE", "exitCode": None, "output": ""}
    try:
        completed = subprocess.run(
            [executable, *args], cwd=CODEBASE, env=GIT_ENV, capture_output=True,
            text=True, errors="replace", timeout=15, check=False,
        )
    except subprocess.TimeoutExpired:
        return {**record, "status": "REVIEW_REQUIRED", "reason": "VERSION_PROBE_TIMEOUT", "exitCode": None, "output": ""}
    output = sanitize_output((completed.stdout + "\n" + completed.stderr).strip())
    if completed.returncode == 0 and output:
        return {**record, "status": "AVAILABLE", "reason": None, "exitCode": completed.returncode, "output": output}
    return {**record, "status": "REVIEW_REQUIRED", "reason": "VERSION_UNAVAILABLE_OR_AMBIGUOUS", "exitCode": completed.returncode, "output": output}


def host_repository_differences(
    rows: list[dict[str, object]], probes: list[dict[str, object]],
) -> list[dict[str, object]]:
    repo: dict[str, set[str]] = {}
    for row in rows:
        if (tool := normalized_tool(row)) and (value := comparable_value(tool, row)):
            if not value.startswith((">", "<", "=", "^", "~")):
                repo.setdefault(tool, set()).add(value)
    findings = []
    for probe in probes:
        tool = str(probe["tool"])
        if probe["status"] != "AVAILABLE" or tool not in repo:
            continue
        match = re.search(r"\d+(?:\.\d+){0,2}(?:[-+][A-Za-z0-9.-]+)?", str(probe["output"]))
        if match and match.group(0) not in repo[tool]:
            findings.append(
                {
                    "status": "REVIEW_REQUIRED",
                    "reason": "HOST_REPOSITORY_VERSION_DIFFERENCE",
                    "item": f"host-version:{tool}",
                    "category": probe["category"],
                    "hostVersion": match.group(0),
                    "repositoryVersions": sorted(repo[tool]),
                }
            )
    return findings


def git_state() -> dict[str, object]:
    queries = {
        "head": ("rev-parse", "HEAD"),
        "originMain": ("rev-parse", "origin/main"),
        "branch": ("branch", "--show-current"),
        "statusOutsideGraphify": ("status", "--porcelain=v1", "--untracked-files=all", "--", ".", ":(exclude)graphify"),
    }
    result = {}
    for name, args in queries.items():
        completed = subprocess.run(
            ["git", "-c", "core.quotePath=false", *args], cwd=LAMHA, env=GIT_ENV,
            capture_output=True, text=True, check=False,
        )
        result[name] = {
            "command": "git " + " ".join(args), "exitCode": completed.returncode,
            "output": completed.stdout, "stderr": completed.stderr, "readOnly": True,
        }
    return result


def inspect_git_submodules() -> tuple[list[dict[str, object]], list[dict[str, object]], list[str]]:
    manifest = CODEBASE / ".gitmodules"
    if not manifest.is_file():
        return [], [], []
    text = manifest.read_text(encoding="utf-8", errors="replace")
    records: list[dict[str, object]] = []
    rows: list[dict[str, object]] = []
    commands: list[str] = []
    for block in re.finditer(r'^\[submodule\s+"([^"]+)"\]\s*\n(.*?)(?=^\[|\Z)', text, re.M | re.S):
        name, body = block.group(1), block.group(2)
        path_match = re.search(r"^\s*path\s*=\s*(\S+)\s*$", body, re.M)
        url_match = re.search(r"^\s*url\s*=\s*(\S+)\s*$", body, re.M)
        if not path_match or not url_match:
            raise InventoryError("ManifestKeyMissing", f".gitmodules: incomplete submodule {name}")
        submodule_path, url = path_match.group(1), url_match.group(1)
        repo_path = f"Codebase/{submodule_path}"
        command = ["git", "ls-files", "--stage", "--", repo_path]
        completed = subprocess.run(command, cwd=LAMHA, env=GIT_ENV, capture_output=True, text=True, check=False)
        commands.append(" ".join(command))
        if completed.returncode != 0:
            raise InventoryError("GitlinkInspectionError", sanitize_output(completed.stderr))
        gitlink = re.search(r"^160000\s+([0-9a-fA-F]{40,64})\s+", completed.stdout, re.M)
        revision = gitlink.group(1).lower() if gitlink else None
        records.append(
            {
                "name": name, "path": repo_path, "url": url, "revision": revision,
                "status": "PINNED" if revision else "REVIEW_REQUIRED",
                "reason": None if revision else "SUBMODULE_REVISION_UNAVAILABLE",
                "inspectionCommand": " ".join(command), "exitCode": completed.returncode,
            }
        )
        add_declaration(rows, ".gitmodules", f"git-submodule-url:{submodule_path}", url, "observed")
        add_declaration(
            rows, ".gitmodules", f"git-submodule-revision:{submodule_path}",
            revision or "UNAVAILABLE", "concrete" if revision else "unavailable",
        )
    return records, rows, commands


def records(paths: list[str], rows: list[dict[str, object]]) -> list[dict[str, object]]:
    source_categories: dict[str, set[str]] = {}
    for row in rows:
        source_categories.setdefault(str(row["source"]), set()).update(row["categories"])
    result = []
    for rel in paths:
        size, digest = sha256_file(CODEBASE / rel)
        categories = intrinsic_categories(rel) | content_categories(rel) | source_categories.get(f"Codebase/{rel}", set())
        result.append({"path": f"Codebase/{rel}", "size": size, "sha256": digest, "categories": sorted(categories)})
    return result


def typed_fixture(name: str, action) -> dict[str, object]:
    try:
        action()
    except (InventoryError, ValueError) as error:
        return {
            "fixture": name, "rejected": True,
            "typedError": error.error_type if isinstance(error, InventoryError) else type(error).__name__,
            "message": str(error),
        }
    return {"fixture": name, "rejected": False, "typedError": None}


def require_expected_path(path: str, actual: set[str]) -> None:
    if path not in actual:
        raise InventoryError("ManifestCoverageError", f"required manifest omitted: {path}")


def main() -> int:
    started = utc_now()
    written: list[str] = []
    failures: list[str] = []

    prerequisite = load_json(PREREQ_SUMMARY)
    review_text = PREREQ_REVIEW.read_text(encoding="utf-8")
    if not isinstance(prerequisite, dict) or prerequisite.get("status") != "PASS":
        failures.append("WP-I0-004 prerequisite summary is not PASS")
    if "Final package status: COMPLETE and GitHub-verified" not in review_text:
        failures.append("WP-I0-004 is not COMPLETE and GitHub-verified")

    git_before = git_state()
    paths = manifest_paths()
    oracle_candidates, oracle_reasons, referenced_manifest_paths = independent_manifest_candidates()
    unavailable_referenced_paths = sorted(
        {str(row["resolvedPath"]) for row in referenced_manifest_paths if row["status"] == "REVIEW_REQUIRED"}
    )
    missing_expected_referenced_paths = sorted(EXPECTED_MISSING_REFERENCED_PATHS - set(unavailable_referenced_paths))
    parser = load_prerequisite_parser()
    prior_rows, extraction_errors, _ = parser.collect_declarations()
    submodule_records, submodule_rows, submodule_git_commands = inspect_git_submodules()
    superseded_prior_compose_rows = [row for row in prior_rows if superseded_prior_compose_declaration(row)]
    internal_docker_stage_rows = [row for row in prior_rows if internal_docker_stage_declaration(row)]
    superseded_prior_rows = [row for row in prior_rows if superseded_prior_declaration(row)]
    rows = deduplicate(
        [row for row in prior_rows if relevant_declaration(row) and not superseded_prior_declaration(row)]
        + extra_declarations(paths) + submodule_rows
    )
    for row in rows:
        row["categories"] = declaration_categories(row)
    records_before = records(paths, rows)
    fingerprint_before = sha256_bytes(json.dumps(records_before, sort_keys=True).encode())

    actual_paths = {row["path"] for row in records_before}
    actual_declarations = {(str(row["source"]), str(row["key"]), str(row["value"])) for row in rows}
    missing_oracle_paths = sorted(oracle_candidates - actual_paths)
    missing_expected_paths = sorted(EXPECTED_PATHS - actual_paths)
    missing_expected_declarations = sorted(EXPECTED_DECLARATIONS - actual_declarations)
    category_paths = {
        category: [row["path"] for row in records_before if category in row["categories"]]
        for category in CATEGORIES
    }
    category_declarations = {
        category: [row for row in rows if category in row["categories"]]
        for category in CATEGORIES
    }

    probe_tools, unmapped_declared_tools = derive_probe_tools(rows)
    host_probes = [probe_host(tool) for tool in sorted(probe_tools)]
    ambiguities = derive_ambiguities(rows)
    review_required: list[dict[str, object]] = []
    manifest_categories_by_path = {
        str(record["path"]): set(str(category) for category in record["categories"])
        for record in records_before
    }

    def reference_categories(reference: dict[str, object]) -> set[str]:
        source = str(reference["source"])
        mechanism = str(reference["mechanism"])
        resolved = str(reference["resolvedPath"])
        categories = set(manifest_categories_by_path.get(source, set()))
        if mechanism in {"node-tool-config-package", "prettier-plugin-package", "tsconfig-extends-package"}:
            categories = {"node", "package-manager"}
        elif mechanism == "tsconfig-extends-relative":
            categories = {"node"}
        elif mechanism == "renovate-remote-config":
            categories = {"package-manager"}
        elif mechanism in {"dart-analysis-package-include", "pubspec-local-path-dependency"}:
            categories = {"package-manager", "platform"}
        elif str(reference.get("referenceKind")) == "package":
            categories.add("package-manager")
        if "/Pods/" in resolved or mechanism in {
            "xcode-local-swift-package-reference", "xcode-base-configuration-reference",
            "xcode-inputFileListPaths", "xcode-outputFileListPaths", "xcode-inputPaths",
            "xcode-pods-shell-script",
        }:
            categories.update({"package-manager", "platform"})
        return categories or {"platform"}

    for category in CATEGORIES:
        if not category_paths[category]:
            review_required.append({"category": category, "status": "REVIEW_REQUIRED", "reason": "NO_REPOSITORY_MANIFEST", "item": category})
        if not category_declarations[category]:
            review_required.append({"category": category, "status": "REVIEW_REQUIRED", "reason": "NO_DISCOVERABLE_REPOSITORY_VERSION", "item": category})
    for missing_path in unavailable_referenced_paths:
        references = [row for row in referenced_manifest_paths if row["resolvedPath"] == missing_path]
        sources = sorted({str(row["source"]) for row in references})
        categories = sorted({category for reference in references for category in reference_categories(reference)})
        for category in categories:
            review_required.append(
                {
                    "category": category,
                    "status": "REVIEW_REQUIRED",
                    "reason": "REFERENCED_MANIFEST_UNAVAILABLE",
                    "item": missing_path,
                    "sources": sources,
                    "applicableCategories": categories,
                }
            )
    unavailable_submodules = [row for row in submodule_records if row["status"] == "REVIEW_REQUIRED"]
    for submodule in unavailable_submodules:
        review_required.append(
            {
                "category": "platform", "status": "REVIEW_REQUIRED",
                "reason": "SUBMODULE_REVISION_UNAVAILABLE",
                "item": f"submodule-revision:{submodule['path']}",
                "source": "Codebase/.gitmodules", "url": submodule["url"],
            }
        )
    unresolved_declarations = []
    for row in rows:
        if row.get("kind") not in {"reference", "unresolved"}:
            continue
        category = (row.get("categories") or ["platform"])[0]
        item = f"declaration:{row['source']}#{row['key']}"
        unresolved_declarations.append((str(category), item))
        review_required.append(
            {
                "category": category,
                "status": "REVIEW_REQUIRED",
                "reason": "VERSION_REFERENCE_UNRESOLVED",
                "item": item,
                "observedValue": row["value"],
            }
        )
    review_required.extend(
        {"category": row["category"], "status": "REVIEW_REQUIRED", "reason": row["reason"], "item": row["tool"]}
        for row in host_probes if row["status"] == "REVIEW_REQUIRED"
    )
    review_required.extend(
        {"category": "platform", "status": "REVIEW_REQUIRED", "reason": "HOST_PROBE_UNMAPPED", "item": tool}
        for tool in sorted(unmapped_declared_tools)
    )
    for finding in ambiguities:
        review_required.append({"category": finding["categories"][0], **finding})
    review_required.extend(host_repository_differences(rows, host_probes))

    floating_image_rows = [
        row for row in rows
        if "compose" in Path(str(row.get("source", ""))).name.lower()
        and (str(row.get("value", "")).endswith(":latest") or "${" in str(row.get("value", "")))
    ]
    misclassified_floating_images = [row for row in floating_image_rows if row.get("kind") != "reference"]
    surviving_superseded_rows = [row for row in rows if superseded_prior_declaration(row)]
    surviving_internal_stage_rows = [row for row in rows if internal_docker_stage_declaration(row)]
    current_review_items = {str(row["item"]) for row in review_required}
    review_categories_by_item: dict[str, set[str]] = {}
    for row in review_required:
        review_categories_by_item.setdefault(str(row["item"]), set()).add(str(row["category"]))
    unreported_referenced_paths = sorted(set(unavailable_referenced_paths) - current_review_items)
    unreported_submodules = sorted(
        str(row["path"]) for row in unavailable_submodules
        if f"submodule-revision:{row['path']}" not in current_review_items
    )
    representative_reference_categories = {
        "Codebase/e2e/node_modules/vitest/package.json": ["node", "package-manager"],
        "Codebase/node_modules/prettier-plugin-sort-json/package.json": ["node", "package-manager"],
        "Codebase/${RENOVATE_REMOTE}/immich-app/.github/renovate-config.json": ["package-manager"],
        "Codebase/mobile/.dart_tool/package_config.json": ["package-manager", "platform"],
        "Codebase/mobile/ios/Pods/Manifest.lock": ["package-manager", "platform"],
    }
    reference_category_mismatches = {
        item: {"expected": expected, "actual": sorted(review_categories_by_item.get(item, set()))}
        for item, expected in representative_reference_categories.items()
        if set(expected) != review_categories_by_item.get(item, set())
    }
    conda_probe = next((row for row in host_probes if row["tool"] == "conda"), None)
    conda_probe_unreported = bool(
        conda_probe and conda_probe["status"] == "REVIEW_REQUIRED" and "conda" not in current_review_items
    )
    dcm_ranges = [
        str(row["value"]) for row in rows if normalized_tool(row) == "dcm" and row.get("kind") == "range"
    ]
    dcm_pins = [
        str(value) for row in rows
        if normalized_tool(row) == "dcm" and row.get("kind") != "range"
        and (value := comparable_value("dcm", row))
    ]
    dcm_incompatible = [
        {"pin": pin, "constraint": constraint}
        for pin in dcm_pins for constraint in dcm_ranges if range_allows(pin, constraint) is False
    ]
    flutter_ranges = [
        str(row["value"]) for row in rows if normalized_tool(row) == "flutter" and row.get("kind") == "range"
    ]
    flutter_pins = [
        str(value) for row in rows
        if normalized_tool(row) == "flutter" and row.get("kind") != "range"
        and (value := comparable_value("flutter", row))
    ]
    flutter_incompatible = [
        {"pin": pin, "constraint": constraint}
        for pin in flutter_pins for constraint in flutter_ranges if range_allows(pin, constraint) is False
    ]
    unreported_floating_images = [
        row for row in floating_image_rows
        if f"declaration:{row['source']}#{row['key']}" not in current_review_items
    ]
    npm_caret_aligned_cases = {
        "dotenv": ["^17", "^17.2.3"],
        "prettier-plugin-sort-json": ["^4.1.1", "^4.2"],
        "typescript-eslint": ["^8.28", "^8.45", "^8.58"],
        "vite-tsconfig-paths": ["^6", "^6.1.1"],
    }
    npm_caret_aligned_results = {
        package: npm_caret_ranges_overlap(constraints)
        for package, constraints in npm_caret_aligned_cases.items()
    }
    npm_caret_disjoint = npm_caret_ranges_overlap(["^3", "^4"])
    typescript_target_rows = [row for row in rows if str(row["key"]) == "typescript-target"]
    typescript_target_contexts = {
        (nearest_package_json(LAMHA / str(row["source"])).parent.relative_to(CODEBASE).as_posix()
         if nearest_package_json(LAMHA / str(row["source"])) else str(Path(str(row["source"])).parent)): str(row["value"])
        for row in typescript_target_rows
    }
    vitest_contexts = {
        (nearest_package_json(LAMHA / str(row["source"])).parent.relative_to(CODEBASE).as_posix()
         if nearest_package_json(LAMHA / str(row["source"])) else str(Path(str(row["source"])).parent)): str(row["value"])
        for row in rows if str(row["key"]) == "node-config-package:vitest"
    }
    false_contextual_target_findings = [
        finding for finding in ambiguities
        if str(finding["item"]).startswith((
            "repository-version:typescript-target", "repository-version:iphoneos_deployment_target",
            "repository-version:clang_cxx_language_standard", "repository-version:gcc_c_language_standard",
            "repository-version:node-config-package:",
        ))
    ]

    coverage_fixtures = {
        "independentManifestOracle": {
            "method": "broad manifest-family scan plus source-derived devcontainer, mandatory xcconfig, Podfile, and Gradle reference resolution; production is_manifest is not called",
            "candidateCount": len(oracle_candidates),
            "candidates": oracle_reasons,
            "referencedManifestPaths": referenced_manifest_paths,
            "unavailableReferencedPaths": unavailable_referenced_paths,
            "missingExpectedUnavailableReferences": missing_expected_referenced_paths,
            "unreportedUnavailableReferences": unreported_referenced_paths,
            "missing": missing_oracle_paths,
            "status": "PASS" if not missing_oracle_paths and not missing_expected_referenced_paths and not unreported_referenced_paths else "FAIL",
        },
        "gitSubmoduleRevisions": {
            "records": submodule_records,
            "unreportedUnavailableRevisions": unreported_submodules,
            "status": "PASS" if submodule_records and not unreported_submodules else "FAIL",
        },
        "unavailableReferenceCategories": {
            "representativeExpected": representative_reference_categories,
            "mismatches": reference_category_mismatches,
            "status": "PASS" if not reference_category_mismatches else "FAIL",
        },
        "expectedManifestPaths": {"missing": missing_expected_paths, "status": "PASS" if not missing_expected_paths else "FAIL"},
        "expectedVersionDeclarations": {"missing": missing_expected_declarations, "status": "PASS" if not missing_expected_declarations else "FAIL"},
        "condaEnvironment": {
            "manifestPath": "Codebase/machine-learning/ann/export/env.yaml",
            "hostProbe": conda_probe,
            "unavailableProbeUnreported": conda_probe_unreported,
            "status": "PASS" if conda_probe and not conda_probe_unreported else "FAIL",
        },
        "dcmRangeCompatibility": {
            "constraints": sorted(set(dcm_ranges)),
            "pins": sorted(set(dcm_pins)),
            "incompatible": dcm_incompatible,
            "status": "PASS" if dcm_ranges and dcm_pins and not dcm_incompatible else "FAIL",
        },
        "flutterRangeCompatibility": {
            "constraints": sorted(set(flutter_ranges)),
            "pins": sorted(set(flutter_pins)),
            "incompatible": flutter_incompatible,
            "verdict": "MIXED" if flutter_incompatible else "ALIGNED",
            "status": "PASS" if flutter_ranges and flutter_pins else "FAIL",
        },
        "npmCaretRangeCompatibility": {
            "alignedCases": npm_caret_aligned_cases,
            "alignedResults": npm_caret_aligned_results,
            "disjointControl": {"constraints": ["^3", "^4"], "overlap": npm_caret_disjoint},
            "status": "PASS" if all(npm_caret_aligned_results.values()) and npm_caret_disjoint is False else "FAIL",
        },
        "contextScopedLanguageTargets": {
            "typescriptTargetsByPackage": dict(sorted(typescript_target_contexts.items())),
            "distinctTypescriptTargets": sorted(set(typescript_target_contexts.values())),
            "vitestConstraintsByPackage": dict(sorted(vitest_contexts.items())),
            "falseRepositoryWideFindings": false_contextual_target_findings,
            "status": "PASS" if len(set(typescript_target_contexts.values())) >= 3 and len(set(vitest_contexts.values())) == 2 and not false_contextual_target_findings else "FAIL",
        },
        "floatingComposeImages": {
            "cases": floating_image_rows,
            "misclassified": misclassified_floating_images,
            "withoutReviewRequired": unreported_floating_images,
            "supersededPredecessorRowsRemoved": len(superseded_prior_compose_rows),
            "survivingSupersededPredecessorRows": surviving_superseded_rows,
            "status": "PASS" if floating_image_rows and not misclassified_floating_images and not unreported_floating_images and not surviving_superseded_rows else "FAIL",
        },
        "internalDockerStageAliases": {
            "predecessorRowsRemoved": internal_docker_stage_rows,
            "survivingRows": surviving_internal_stage_rows,
            "status": "PASS" if internal_docker_stage_rows and not surviving_internal_stage_rows else "FAIL",
        },
        "categoryMembershipFromContent": {
            "deploymentMiseCategories": next(row["categories"] for row in records_before if row["path"] == "Codebase/deployment/mise.toml"),
            "pluginCoreMiseCategories": next(row["categories"] for row in records_before if row["path"] == "Codebase/packages/plugin-core/mise.toml"),
        },
    }
    if coverage_fixtures["categoryMembershipFromContent"]["deploymentMiseCategories"] != ["platform"]:
        failures.append("deployment/mise.toml category assignment is not content-derived platform-only")
    if coverage_fixtures["categoryMembershipFromContent"]["pluginCoreMiseCategories"] != ["package-manager"]:
        failures.append("packages/plugin-core/mise.toml category assignment is not package-manager-only")

    fixtures = [
        typed_fixture("malformed-prerequisite-json", lambda: parse_json_text("{", "probe.json")),
        typed_fixture("non-allowlisted-command", lambda: probe_host("not-declared")),
        typed_fixture("parent-traversal-write", lambda: guard_write_path(PACKAGE_DIR / "../escape.txt")),
        typed_fixture("absolute-write-escape", lambda: guard_write_path(Path(LAMHA.anchor) / "escape.txt")),
        typed_fixture("omitted-manifest-detected", lambda: require_expected_path("Codebase/missing-toolchain.manifest", actual_paths)),
    ]

    records_after = records(paths, rows)
    fingerprint_after = sha256_bytes(json.dumps(records_after, sort_keys=True).encode())
    git_after = git_state()
    outside_before = str(git_before["statusOutsideGraphify"]["output"])
    outside_after = str(git_after["statusOutsideGraphify"]["output"])
    preserved = fingerprint_before == fingerprint_after and not outside_before and not outside_after
    for fixture in fixtures:
        fixture["partialCommit"] = not preserved
        fixture["authoritativeStatePreserved"] = preserved

    if extraction_errors:
        failures.append(f"manifest extraction errors: {extraction_errors}")
    if missing_oracle_paths:
        failures.append(f"independent manifest oracle omissions: {missing_oracle_paths}")
    if missing_expected_referenced_paths:
        failures.append(f"expected missing manifest references were not derived: {missing_expected_referenced_paths}")
    if unreported_referenced_paths:
        failures.append(f"missing referenced manifests lack REVIEW_REQUIRED: {unreported_referenced_paths}")
    if not submodule_records or unreported_submodules:
        failures.append(f"Git submodule revision coverage incomplete: {unreported_submodules}")
    if reference_category_mismatches:
        failures.append(f"unavailable reference categories are incorrect: {reference_category_mismatches}")
    if missing_expected_paths:
        failures.append(f"expected manifest paths omitted: {missing_expected_paths}")
    if missing_expected_declarations:
        failures.append(f"expected version declarations omitted: {missing_expected_declarations}")
    if conda_probe is None:
        failures.append("Conda environment did not derive a host probe")
    if conda_probe_unreported:
        failures.append("unavailable Conda host probe lacks REVIEW_REQUIRED")
    if not dcm_ranges or not dcm_pins:
        failures.append("DCM range/pin compatibility fixture is incomplete")
    if dcm_incompatible:
        failures.append(f"DCM range/pin incompatibility: {dcm_incompatible}")
    if not flutter_ranges or not flutter_pins:
        failures.append("Flutter range/pin compatibility fixture is incomplete")
    if not all(npm_caret_aligned_results.values()) or npm_caret_disjoint is not False:
        failures.append("npm caret range-intersection fixtures are incomplete")
    if len(set(typescript_target_contexts.values())) < 3 or len(set(vitest_contexts.values())) != 2 or false_contextual_target_findings:
        failures.append("package-scoped output or Node config-package diversity was misclassified as repository ambiguity")
    if not floating_image_rows:
        failures.append("floating compose-image fixture set is empty")
    if misclassified_floating_images:
        failures.append(f"floating compose images classified concrete: {misclassified_floating_images}")
    if unreported_floating_images:
        failures.append(f"floating compose images lack REVIEW_REQUIRED: {unreported_floating_images}")
    if surviving_superseded_rows:
        failures.append(f"superseded predecessor compose rows survived: {surviving_superseded_rows}")
    if not internal_docker_stage_rows:
        failures.append("internal Docker stage-alias fixture set is empty")
    if surviving_internal_stage_rows:
        failures.append(f"internal Docker stage aliases survived: {surviving_internal_stage_rows}")
    if not all(row["rejected"] for row in fixtures):
        failures.append("one or more negative fixtures did not reject")
    if not preserved:
        failures.append("authoritative state changed during collection or negative fixtures")
    if any(not category_paths[category] and not any(row["category"] == category for row in review_required) for category in CATEGORIES):
        failures.append("category omitted without REVIEW_REQUIRED classification")

    unavailable_reference_requirements = {
        (category, str(reference["resolvedPath"]))
        for reference in referenced_manifest_paths if reference["status"] == "REVIEW_REQUIRED"
        for category in reference_categories(reference)
    }
    required_review_items = {
        (str(row["category"]), str(row["tool"]))
        for row in host_probes if row["status"] == "REVIEW_REQUIRED"
    } | {("platform", tool) for tool in unmapped_declared_tools} | set(unresolved_declarations) | unavailable_reference_requirements | {
        ("platform", f"submodule-revision:{row['path']}") for row in unavailable_submodules
    }
    actual_review_items = {(str(row["category"]), str(row["item"])) for row in review_required}
    unreported_review_items = sorted(required_review_items - actual_review_items)
    if unreported_review_items:
        failures.append(f"unavailable declared tools lack REVIEW_REQUIRED: {unreported_review_items}")

    categories = {
        category: {
            "manifestPaths": category_paths[category],
            "versionDeclarations": category_declarations[category],
            "hostTools": [row for row in host_probes if row["category"] == category],
            "reviewRequired": [row for row in review_required if row["category"] == category],
            "status": "RECORDED",
        }
        for category in CATEGORIES
    }
    prerequisite_investigation = load_json(PREREQ_INVESTIGATION)
    prerequisite_mixed = prerequisite_investigation.get("mixedVersionFindings", []) if isinstance(prerequisite_investigation, dict) else []

    inventory = {
        "packageId": PACKAGE_ID,
        "objective": "Record Node, package-manager, Rust, Python, media, and platform toolchains without installation or mutation.",
        "host": {
            "system": platform.system(), "release": platform.release(), "version": platform.version(),
            "machine": platform.machine(), "pythonRunningCollector": sys.version.split()[0],
        },
        "categories": categories,
        "manifestRecords": records_before,
        "independentManifestOracle": {
            "candidateCount": len(oracle_candidates),
            "missingPaths": missing_oracle_paths,
            "referencedManifestPaths": referenced_manifest_paths,
            "unavailableReferencedPaths": unavailable_referenced_paths,
        },
        "versionDeclarations": rows,
        "repositoryAmbiguities": ambiguities,
        "mixedVersionFindingsFromPrerequisite": prerequisite_mixed,
        "hostToolProbes": host_probes,
        "unmappedDeclaredTools": sorted(unmapped_declared_tools),
        "gitSubmodules": submodule_records,
        "reviewRequired": review_required,
        "counts": {
            "categories": len(categories), "manifestFiles": len(records_before),
            "versionDeclarations": len(rows), "hostProbes": len(host_probes),
            "availableHostTools": sum(row["status"] == "AVAILABLE" for row in host_probes),
            "repositoryAmbiguities": len(ambiguities), "unavailableReferencedManifests": len(unavailable_referenced_paths),
            "reviewRequired": len(review_required),
        },
        "status": "PASS" if not failures else "FAIL",
    }

    provenance = {
        "packageId": PACKAGE_ID,
        "packetPath": PACKET.relative_to(GRAPHIFY).as_posix(),
        "packetSha256": sha256_bytes(PACKET.read_bytes()),
        "ownedRequirements": ["CAN-MISSION-I0-006"],
        "selection": {
            "rule": "explicit authorization from WP-I0-004, confirmed by deterministic READY sorting",
            "readyPackages": ["WP-I0-005", "WP-I0-006", "WP-I0-008", "WP-I0-009", "WP-I0-010", "WP-I0-011", "WP-I1-001", "WP-I2-002"],
            "explicitAuthorizationRecordPath": PREREQ_REVIEW.relative_to(GRAPHIFY).as_posix(),
            "explicitAuthorizationRecordSha256": sha256_bytes(PREREQ_REVIEW.read_bytes()),
            "startSha": str(git_before["head"]["output"]).strip(),
            "startRemoteSha": str(git_before["originMain"]["output"]).strip(),
        },
        "prerequisite": {
            "packageId": "WP-I0-004", "dependencyType": "REQUIRES_DECISION",
            "summaryPath": PREREQ_SUMMARY.relative_to(GRAPHIFY).as_posix(),
            "summarySha256": sha256_bytes(PREREQ_SUMMARY.read_bytes()),
            "summaryStatus": prerequisite.get("status") if isinstance(prerequisite, dict) else None,
            "reviewPath": PREREQ_REVIEW.relative_to(GRAPHIFY).as_posix(),
            "investigationPath": PREREQ_INVESTIGATION.relative_to(GRAPHIFY).as_posix(),
        },
        "writeBoundary": "graphify/13-implementation/WP-I0-005/** only through graphify/tools/write_guard.py",
        "readOnlyPaths": ["Codebase/**", "graphify/12-semantic-implementation-plan/**", "graphify/13-implementation/WP-I0-004/**", ".git metadata through read-only commands"],
        "prohibitedPaths": ["Codebase/** writes", "later-package implementation/tests/dependencies", "repository copies, archives, backups, builds, caches, generated code"],
    }

    exit_gate = [
        {
            "clause": "Every discoverable toolchain manifest path and version is recorded in the six required categories",
            "evidence": f"Recorded {len(records_before)} available manifest files and {len(rows)} version declarations; a separately derived {len(oracle_candidates)}-path oracle plus source-derived reference resolution recorded {len(unavailable_referenced_paths)} unavailable mandatory manifests as REVIEW_REQUIRED; supplemental {len(EXPECTED_PATHS)}-path/{len(EXPECTED_DECLARATIONS)}-declaration fixtures have zero omissions.",
            "evidenceFiles": ["13-implementation/WP-I0-005/toolchain-inventory.json", "13-implementation/WP-I0-005/verification-report.json"],
            "result": "PASS" if len(categories) == 6 and not reference_category_mismatches and submodule_records and not unreported_submodules and not missing_oracle_paths and not missing_expected_referenced_paths and not unreported_referenced_paths and not missing_expected_paths and not missing_expected_declarations and not extraction_errors else "FAIL",
        },
        {
            "clause": "Every unavailable or ambiguous version is explicitly REVIEW_REQUIRED",
            "evidence": f"Derived {len(ambiguities)} current repository ambiguities, probed {len(host_probes)} baseline/repository-declared tools, recorded {len(unmapped_declared_tools)} unmapped declared tools and {len(unavailable_referenced_paths)} unavailable referenced manifests, removed {len(superseded_prior_rows)} superseded predecessor rows, classified all {len(floating_image_rows)} floating/dynamic compose-image cases as references, and produced {len(review_required)} explicit REVIEW_REQUIRED entries with zero unreported unavailable items.",
            "evidenceFiles": ["13-implementation/WP-I0-005/toolchain-inventory.json"],
            "result": "PASS" if review_required and not reference_category_mismatches and not unreported_submodules and floating_image_rows and not surviving_superseded_rows and not misclassified_floating_images and not unreported_floating_images and not unreported_referenced_paths and not unreported_review_items and all(row["status"] == "REVIEW_REQUIRED" for row in review_required) else "FAIL",
        },
        {
            "clause": "Inspection is local-only, typed on failure, and preserves authoritative state",
            "evidence": f"All {len(fixtures)} negative fixtures rejected; measured manifest fingerprint and outside-Graphify Git state were identical pre/post; no network/install/build/product-test command ran.",
            "evidenceFiles": ["13-implementation/WP-I0-005/verification-report.json", "13-implementation/WP-I0-005/artifact-scan.json"],
            "result": "PASS" if all(row["rejected"] and row["authoritativeStatePreserved"] for row in fixtures) and preserved else "FAIL",
        },
    ]
    if any(row["result"] != "PASS" for row in exit_gate):
        failures.append("one or more exit-gate clauses failed")

    verification = {
        "focused": {
            "wp_i0_005_success": "PASS" if inventory["status"] == "PASS" and len(categories) == 6 else "FAIL",
            "coverageFixtures": coverage_fixtures,
            "unreportedReviewItems": unreported_review_items,
        },
        "negative": {"fixtures": fixtures, "status": "PASS" if all(row["rejected"] and row["authoritativeStatePreserved"] for row in fixtures) else "FAIL"},
        "regression": {
            "prerequisiteSummary": prerequisite.get("status") if isinstance(prerequisite, dict) else None,
            "prerequisiteReviewComplete": "Final package status: COMPLETE and GitHub-verified" in review_text,
            "manifestExtractionErrors": extraction_errors,
            "manifestFingerprintBefore": fingerprint_before,
            "manifestFingerprintAfter": fingerprint_after,
            "outsideGraphifyBefore": outside_before,
            "outsideGraphifyAfter": outside_after,
            "status": "PASS" if not extraction_errors and preserved else "FAIL",
        },
        "commandAudit": {
            "networkCommands": [], "installCommands": [], "buildOrProductTestCommands": [],
            "hostVersionProbes": [row["command"] for row in host_probes],
            "gitCommands": [value["command"] for value in git_before.values()] + submodule_git_commands + [value["command"] for value in git_after.values()],
        },
        "gitState": {"before": git_before, "after": git_after},
        "exitGateClauses": exit_gate,
        "status": "PASS" if not failures else "FAIL",
    }

    write_json("provenance-report.json", provenance, written)
    write_json("toolchain-inventory.json", inventory, written)
    write_json("verification-report.json", verification, written)
    artifact_scan = {
        "scope": "WP-I0-005 evidence plus outside-Graphify Git state and all inventoried manifest hashes",
        "addedOrModifiedOutsideGraphify": [],
        "manifestFingerprintBefore": fingerprint_before,
        "manifestFingerprintAfter": fingerprint_after,
        "archiveBackupCopyBuildCacheInstallOrGeneratedArtifacts": [],
        "status": "PASS" if preserved else "FAIL",
    }
    write_json("artifact-scan.json", artifact_scan, written)

    md = [
        "# WP-I0-005 toolchain inventory", "",
        "Read-only repository and host inspection. No dependency was installed, no build/product test or network command ran, and no `Codebase/` file was modified.", "",
        f"- Available manifest files: **{len(records_before)}**",
        f"- Unavailable referenced manifests: **{len(unavailable_referenced_paths)}** (`REVIEW_REQUIRED`)",
        f"- Version declarations: **{len(rows)}**",
        f"- Host probes: **{len(host_probes)}** ({inventory['counts']['availableHostTools']} available)",
        f"- Derived repository ambiguities: **{len(ambiguities)}**",
        f"- Explicit `REVIEW_REQUIRED` records: **{len(review_required)}**", "", "## Categories", "",
    ]
    for category, value in categories.items():
        md.append(f"- **{category}** — {len(value['manifestPaths'])} manifests, {len(value['versionDeclarations'])} versions, {len(value['hostTools'])} probes, {len(value['reviewRequired'])} review-required")
    md.extend(["", "## Review required", ""])
    for row in review_required:
        md.append(f"- **{row['category']} / {row['item']}** — `{row['reason']}` — `REVIEW_REQUIRED`")
    md.append("")
    write_text("toolchain-inventory.md", "\n".join(md), written)

    completion = [
        f"# {PACKAGE_ID} completion evidence", "", f"- Package: {PACKAGE_ID} — Toolchain inventory",
        f"- Collection: {started} → {utc_now()}",
        f"- `CAN-MISSION-I0-006`: {len(records_before)} available manifest paths, {len(unavailable_referenced_paths)} unavailable referenced manifest paths, {len(rows)} version declarations, and {len(host_probes)} host probes across all six required categories.",
        f"- Unavailable/ambiguous records: {len(review_required)}, each explicitly `REVIEW_REQUIRED`.",
        f"- Preservation: manifest fingerprint `{fingerprint_before}` unchanged; outside-Graphify Git status clean before/after; no forbidden command or artifact.",
        "- Contracts/commands/schemas/SQLite/UI: none owned; authoritative contract review records zero IPC commands and zero missing references.",
        "", "## Exit gate", "",
    ]
    completion.extend(f"- **{row['result']}** — {row['clause']}: {row['evidence']}" for row in exit_gate)
    completion.append("")
    write_text("completion-evidence.md", "\n".join(completion), written)

    summary = {
        "packageId": PACKAGE_ID, "status": "PASS" if not failures else "FAIL", "failures": failures,
        "collectionWindowUtc": {"start": started, "end": utc_now()},
        "checks": {
            "categoryCoverage": "PASS" if len(categories) == 6 else "FAIL",
            "manifestAndVersionInventory": "PASS" if not reference_category_mismatches and submodule_records and not unreported_submodules and not missing_oracle_paths and not missing_expected_referenced_paths and not unreported_referenced_paths and not missing_expected_paths and not missing_expected_declarations and not extraction_errors else "FAIL",
            "reviewRequiredClassification": "PASS" if review_required and not unreported_review_items else "FAIL",
            "focused": verification["focused"]["wp_i0_005_success"],
            "negative": verification["negative"]["status"], "regression": verification["regression"]["status"],
            "artifactScan": artifact_scan["status"],
            "exitGate": "PASS" if all(row["result"] == "PASS" for row in exit_gate) else "FAIL",
        },
        "counts": inventory["counts"],
        "evidenceFiles": sorted(written + ["13-implementation/WP-I0-005/package-summary.json"]),
        "exitGateClauses": exit_gate,
    }
    write_json("package-summary.json", summary, written)
    print(json.dumps({"status": summary["status"], "failures": failures, "counts": inventory["counts"]}, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
