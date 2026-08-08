# WP-I0-004 mixed-version manifest investigation

Read-only investigation of `Codebase/` manifests. No manifest was modified, no dependency installed, no build executed.

- Declarations captured: **121** across package manifests, lockfiles, generated-client manifests, and toolchain manifests.
- Comparison fixtures: **10** (verdicts: node-runtime-alignment=MIXED, node-engine-range-compatibility=ALIGNED, pnpm-manager-alignment=ALIGNED, python-toolchain-alignment=MIXED, flutter-version-alignment=MIXED, dart-sdk-constraint-diversity=MIXED, workspace-package-version-diversity=RECORD_ONLY, generated-client-version-record=RECORD_ONLY, lockfile-tool-version-record=RECORD_ONLY, mise-pin-lock-consistency=MIXED).

## Mixed-version findings

### node-runtime-alignment (toolchain)

distinct concrete Node versions declared: ['24.1.0', '24.15.0']

- `Codebase/.nvmrc` — `node` = `24.15.0` (concrete)
- `Codebase/mise.toml` — `node` = `24.15.0` (concrete)
- `Codebase/packages/cli/Dockerfile` — `FROM node:24.1.0-alpine3.20 (stage core)` = `node:24.1.0-alpine3.20@sha256:8fe019e0d57dbdce5f5c27c0b63d2775cf34b00e3755a7dea969802d7e0c2b25` (concrete_digest_pinned)
- `Codebase/packages/e2e-auth-server/Dockerfile` — `FROM node:24.1.0-alpine3.20` = `node:24.1.0-alpine3.20@sha256:8fe019e0d57dbdce5f5c27c0b63d2775cf34b00e3755a7dea969802d7e0c2b25` (concrete_digest_pinned)

### python-toolchain-alignment (toolchain)

distinct Python minor lines declared across toolchain manifests: ['3.11', '3.13'] (machine-learning/.python-version=3.13 vs machine-learning/mise.toml python=3.11; Docker base images split between python:3.11-bookworm and python:3.13-slim-trixie; requires-python range results per minor line: [{'source': 'Codebase/machine-learning/pyproject.toml', 'range': '>=3.11,<4.0', 'results': {'3.11': True, '3.13': True}}, {'source': 'Codebase/machine-learning/uv.lock', 'range': '>=3.11, <4.0', 'results': {'3.11': True, '3.13': True}}])

- `Codebase/machine-learning/mise.toml` — `python` = `3.11` (concrete)
- `Codebase/machine-learning/mise.lock` — `python` = `3.11.15` (concrete)
- `Codebase/machine-learning/.python-version` — `python` = `3.13` (concrete)
- `Codebase/machine-learning/pyproject.toml` — `requires-python` = `>=3.11,<4.0` (range)
- `Codebase/machine-learning/uv.lock` — `requires-python` = `>=3.11, <4.0` (range)
- `Codebase/machine-learning/Dockerfile` — `FROM python:3.11-bookworm (stage builder-cpu)` = `python:3.11-bookworm@sha256:970c99f886b839fc8829289040c1845dadaf2cae46b37acc7710333158ec29b4` (concrete_digest_pinned)
- `Codebase/machine-learning/Dockerfile` — `FROM python:3.13-slim-trixie (stage builder-openvino)` = `python:3.13-slim-trixie@sha256:d168b8d9eb761f4d3fe305ebd04aeb7e7f2de0297cec5fb2f8f6403244621664` (concrete_digest_pinned)
- `Codebase/machine-learning/Dockerfile` — `FROM python:3.11-slim-bookworm (stage prod-cpu)` = `python:3.11-slim-bookworm@sha256:9c6f90801e6b68e772b7c0ca74260cbf7af9f320acec894e26fccdaccfbe3b47` (concrete_digest_pinned)

### flutter-version-alignment (package)

distinct Flutter versions declared: ['3.41.9-stable', '3.44.0'] — sources: ['Codebase/mise.lock=3.41.9-stable', 'Codebase/mise.lock=3.44.0', 'Codebase/mise.toml=3.44.0', 'Codebase/mobile/pubspec.lock=3.44.0', 'Codebase/mobile/pubspec.yaml=3.44.0']

- `Codebase/mise.toml` — `aqua:flutter/flutter` = `3.44.0` (concrete)
- `Codebase/mise.lock` — `aqua:flutter/flutter` = `3.44.0` (concrete)
- `Codebase/mise.lock` — `flutter` = `3.41.9-stable` (concrete)
- `Codebase/mobile/pubspec.yaml` — `environment.flutter` = `3.44.0` (concrete)
- `Codebase/mobile/pubspec.lock` — `sdks.dart` = `>=3.12.0 <4.0.0` (range)
- `Codebase/mobile/pubspec.lock` — `sdks.flutter` = `3.44.0` (concrete)

### dart-sdk-constraint-diversity (package)

distinct Dart SDK constraints across pubspec manifests: ['Codebase/mobile/openapi/pubspec.yaml=>=2.12.0 <4.0.0', 'Codebase/mobile/packages/ui/pubspec.yaml=>=3.12.0 <4.0.0', 'Codebase/mobile/pubspec.lock=>=3.12.0 <4.0.0', 'Codebase/mobile/pubspec.yaml=>=3.12.0 <4.0.0']

- `Codebase/mobile/openapi/pubspec.yaml` — `environment.sdk` = `>=2.12.0 <4.0.0` (range)
- `Codebase/mobile/packages/ui/pubspec.yaml` — `environment.sdk` = `>=3.12.0 <4.0.0` (range)
- `Codebase/mobile/pubspec.yaml` — `environment.sdk` = `>=3.12.0 <4.0.0` (range)
- `Codebase/mobile/pubspec.lock` — `sdks.dart` = `>=3.12.0 <4.0.0` (range)

### mise-pin-lock-consistency (lockfile)

mise pin/lock drift in 1 tool(s): ['wrangler pin=4.91.0 lock=4.66.0 (Codebase/docs/)']

- `Codebase/deployment/mise.toml+mise.lock` — `opentofu` = `{'pin': '1.11.6', 'lock': '1.11.6'}` (derived_pair)
- `Codebase/deployment/mise.toml+mise.lock` — `terragrunt` = `{'pin': '1.0.3', 'lock': '1.0.3'}` (derived_pair)
- `Codebase/docs/mise.toml+mise.lock` — `wrangler` = `{'pin': '4.91.0', 'lock': '4.66.0'}` (derived_pair)
- `Codebase/machine-learning/mise.toml+mise.lock` — `python` = `{'pin': '3.11', 'lock': '3.11.15'}` (derived_pair)
- `Codebase/machine-learning/mise.toml+mise.lock` — `uv` = `{'pin': '0.8.15', 'lock': '0.8.15'}` (derived_pair)
- `Codebase/mise.toml+mise.lock` — `aqua:flutter/flutter` = `{'pin': '3.44.0', 'lock': '3.44.0'}` (derived_pair)
- `Codebase/mise.toml+mise.lock` — `github:CQLabs/homebrew-dcm` = `{'pin': '1.37.0', 'lock': '1.37.0'}` (derived_pair)
- `Codebase/mise.toml+mise.lock` — `github:extism/cli` = `{'pin': '1.6.3', 'lock': '1.6.3'}` (derived_pair)
- `Codebase/mise.toml+mise.lock` — `github:extism/js-pdk` = `{'pin': '1.6.0', 'lock': '1.6.0'}` (derived_pair)
- `Codebase/mise.toml+mise.lock` — `github:jellyfin/jellyfin-ffmpeg` = `{'pin': '7.1.3-6', 'lock': '7.1.3-6'}` (derived_pair)
- `Codebase/mise.toml+mise.lock` — `github:webassembly/binaryen` = `{'pin': 'version_124', 'lock': 'version_124'}` (derived_pair)
- `Codebase/mise.toml+mise.lock` — `java` = `{'pin': '21.0.2', 'lock': '21.0.2'}` (derived_pair)
- `Codebase/mise.toml+mise.lock` — `node` = `{'pin': '24.15.0', 'lock': '24.15.0'}` (derived_pair)
- `Codebase/mise.toml+mise.lock` — `npm:oazapfts` = `{'pin': '7.5.0', 'lock': '7.5.0'}` (derived_pair)
- `Codebase/mise.toml+mise.lock` — `opentofu` = `{'pin': '1.11.6', 'lock': '1.11.6'}` (derived_pair)
- `Codebase/mise.toml+mise.lock` — `pnpm` = `{'pin': '10.33.4', 'lock': '10.33.4'}` (derived_pair)
- `Codebase/mise.toml+mise.lock` — `terragrunt` = `{'pin': '1.0.3', 'lock': '1.0.3'}` (derived_pair)

## Aligned fixtures

- **node-engine-range-compatibility**: every declared engines.node range admits the pinned toolchain Node
- **pnpm-manager-alignment**: single concrete pnpm version family ['10.33.4']; lockfileVersion ['9.0'] is the pnpm-9/10 lock format; the declared engines.pnpm range >=10.0.0 admits the pinned version: True

## Record-only fixtures

- **workspace-package-version-diversity**: workspace package identities/versions recorded verbatim across 10 package.json files; distinct declared versions ['0.0.0', '0.1.0', '1.0.0', '2.7.5', '3.0.0'] — notably server/package.json is version 3.0.0 while the monorepo root is 2.7.5
- **generated-client-version-record**: two distinct generator ecosystems are pinned: openapi-generator 7.8.0 produces the mobile/openapi client and oazapfts produces the web/sdk fetch client; both pins are recorded verbatim with their owning manifests
- **lockfile-tool-version-record**: lock-resolved tool versions recorded verbatim from mise.lock files; machine-learning/mise.lock resolves the python=3.11 pin
