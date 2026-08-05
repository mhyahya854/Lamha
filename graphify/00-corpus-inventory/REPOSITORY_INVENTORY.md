# Repository inventory

## Inventory result

- Snapshot files: **3,697**
- Meaningful mapped/file-node files: **3,252**
- Structural/deep-map files: **3,072**
- Binary/design asset file nodes: **180**
- Explicit generated/OS-metadata exclusions: **445**
- Markdown/MDX files classified: **123**
- Executable test source files by suffix/directory rule: **335**
- Broader test/e2e/fixture/config-associated files: **421**
- SQL repository-query files: **34**
- GitHub Actions workflow files: **23**
- Reparse points: **0**
- Checked-in build/cache directories: **0**

Exact inventories:

- `FILE_CLASSIFICATION.csv` — every file, category, size, graph policy, and reason
- `CATEGORY_COUNTS.csv` — totals by curated category
- `DIRECTORY_COUNTS.csv` — top-level counts and bytes
- `EXTENSION_COUNTS.csv` — extension counts and bytes
- `MARKDOWN_CLASSIFICATION.csv` — every Markdown/MDX disposition
- `CODEBASE_SHA256_BASELINE.csv` — immutable content baseline

## Curated categories

| Category | Files | Graph treatment |
|---|---:|---|
| Mobile source/config | 928 | Map |
| Frontend source/config | 654 | Map |
| Server source/config | 459 | Map |
| Generated artifacts | 444 | Explicit deep-extraction exclusion; lineage/consumers mapped |
| Tests/e2e/fixtures/config | 421 | Map |
| Documentation | 331 | Map and classify |
| Binary/design assets | 180 | File node and dependency references |
| I18n | 79 | Map |
| Machine learning | 46 | Map |
| Workspace packages | 45 | Map |
| Deployment/container/devcontainer | 37 | Map |
| CI/CD | 33 | Map |
| Root configuration | 16 | Map |
| OpenAPI generator source/templates | 11 | Map |
| Project support | 6 | Map |
| Legal/governance | 6 | Map |
| OS metadata | 1 | Explicit exclusion |

## Current Immich structure

- Frontend: Svelte/SvelteKit route groups for authenticated user workflows, admin, auth, links, and maintenance; reusable gallery/viewer/people/search/map/album/memory/tag/settings components; generated TypeScript SDK consumption; Socket.IO client use.
- Backend: NestJS controllers, DTOs, middleware, services, repositories, schema, 34 SQL query modules, workers, maintenance/bin commands, email rendering, and server tests.
- Database/cache/queues: PostgreSQL clients and SQL/Kysely repositories; Redis/ioredis; BullMQ; Socket.IO Redis adapter; migrations/schema tasks.
- Machine learning: Python FastAPI HTTP application launched with Gunicorn/Uvicorn; facial recognition, CLIP text/vision, OCR detection/recognition, model cache/session backends, ONNX runtime variants, and one primary Python test module.
- Mobile: Flutter application with server authentication/backup/sync/network dependencies, generated Dart OpenAPI client, local Drift data, Android/iOS platform bridges, UI assets, and tests.
- Generated clients: server-generated OpenAPI specification feeds TypeScript and Dart client generation; both client families are deletion/migration blockers until every consumer is mapped.
- Media processing: Sharp, vendored ExifTool, FFmpeg integration/configured binary, thumbnail/hash/panorama/video paths in web/server/mobile.
- Deployment: Dockerfiles, four root Docker Compose variants, e2e Compose, devcontainers, Terraform/OpenTofu/Terragrunt, GitHub Actions, and packaging/release metadata.
- Legal: root AGPL license, CLI copy, contribution/code-of-conduct/security/ownership files, plus dependency/model/codec/font obligations to be resolved in Phase 1.

## Discovered commands

Every command below is **DISCOVERED BUT NOT EXECUTED DURING READ-ONLY MAPPING**. Install/build/test/check/lint/format commands may create caches, generated files, lock changes, build output, coverage, test output, or dependency stores under `Codebase/`. Migration, schema-reset, Docker, formatter-fix, code-generation, clean, publish, and deploy commands also change source/external state and are forbidden in this run.

### Root and workspace

| Purpose | Evidence-backed command/interface | Mapping disposition |
|---|---|---|
| Root i18n format check | `pnpm format` | Discovered, not executed |
| Root i18n format fix | `pnpm format:fix` | Forbidden write mode |
| Workspace development | `mise //:dev` | Docker Compose; not executed |
| Workspace production | `mise //:prod` | Docker build/run; not executed |
| Workspace e2e | `mise //:e2e` | Docker Compose; not executed |
| TypeScript OpenAPI generation | `mise //:open-api-typescript` | Code generation/install/build; forbidden |
| Dart OpenAPI generation | `mise //:open-api-dart` | Code generation; forbidden |
| Full OpenAPI synchronization | `mise //:open-api` | Installs/builds/generates; forbidden |
| SQL synchronization | `mise //:sql` | Requires built server and writes generated SQL; forbidden |
| Clean | `mise //:clean` | Destructive; forbidden |

### Web

| Purpose | Command |
|---|---|
| Install | `mise //web:install` |
| Build | `mise //web:build` / `pnpm run build` |
| Svelte check | `mise //web:check-svelte` / `pnpm run check:svelte` |
| TypeScript check | `mise //web:check-typescript` / `pnpm run check:typescript` |
| Unit tests | `mise //web:test --run` / `pnpm run test` |
| Coverage | `pnpm run test:cov` |
| Lint | `mise //web:lint` / `pnpm run lint` |
| Format check | `mise //web:format` / `pnpm run format` |
| Fix modes | `lint:fix`, `format:fix` — forbidden |

### Server

| Purpose | Command |
|---|---|
| Install | `mise //server:install` |
| Build | `mise //server:build` / `pnpm run build` |
| Type check | `mise //server:check` / `pnpm run check` |
| Unit tests | `mise //server:test --run` / `pnpm run test` |
| Medium tests | `mise //server:test-medium --run` / `pnpm run test:medium` |
| Coverage | `pnpm run test:cov` |
| Lint | `mise //server:lint` / `pnpm run lint` |
| Format check | `mise //server:format` / `pnpm run format` |
| Migrations | `mise //server:migrations ...` and `pnpm run migrations:*` — forbidden |
| Schema reset/drop | `mise //server:schema-reset` / package scripts — destructive and forbidden |
| OpenAPI sync | `mise //server:sync-open-api` — code generation, forbidden |

### Machine learning

| Purpose | Command |
|---|---|
| Install | `mise //machine-learning:install` / `uv sync --locked` |
| Lint | `mise //machine-learning:lint` |
| Type check | `mise //machine-learning:check` |
| Tests/coverage | `mise //machine-learning:test` |
| Formatter | `mise //machine-learning:format` — may write; not executed |

### Mobile

| Purpose | Command |
|---|---|
| Install | `mise //mobile:install` / `flutter pub get` |
| Analyze | `mise //mobile:analyze` |
| Tests | `mise //mobile:test` / `flutter test` |
| Android release build | `mise //mobile:build:android` |
| Format check | `mise //mobile:format` |
| Dart/build-runner generation | `mise //mobile:codegen:dart` — forbidden |
| Pigeon generation | `mise //mobile:codegen:pigeon` — forbidden |
| Translation/icon/splash generation | corresponding `codegen:*` tasks — forbidden |
| Drift migration generation | `mise //mobile:drift:migration` — forbidden |
| Analyze fixes | `mise //mobile:analyze-fix` — forbidden |

### End-to-end, packages, docs, and deployment

| Area | Commands discovered |
|---|---|
| E2E | `mise //e2e:test`, `mise //e2e:test-web`, package Vitest/Playwright scripts; depends on Docker/install/setup |
| CLI | `mise //packages/cli:build`, `:check`, `:test --run`, `:lint`, `:format`; publish task is external-state-changing and forbidden |
| SDK | `mise //:sdk:build`; generated source consumers must be mapped |
| Docs | `mise //docs:build`, `:start`, `:preview`, `:format`; deploy is external-state-changing and forbidden |
| Deployment | Terragrunt/OpenTofu format/init/run tasks; external/infrastructure mutation and formatting are forbidden |
| GitHub Actions | workflow definitions for tests, static analysis, OpenAPI, SDK, CLI, Docker, mobile, docs, releases, CodeQL, translations, and repository maintenance |

## Phase 0 gate

- Roots resolved: PASS
- Meaningful files inventoried: PASS
- Exclusions justified: PASS
- Existing commands recorded without invention: PASS
- Baseline state preserved: PASS
- `Codebase/` modified: NO
- Graphify extraction begun: NO
- Implementation begun: NO

