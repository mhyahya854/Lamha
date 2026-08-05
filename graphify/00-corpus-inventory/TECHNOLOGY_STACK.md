# Technology stack

All versions below come from checked-in manifests and lock/tool configuration. No package installation or runtime command was executed.

| Area | Verified technology/version evidence |
|---|---|
| Snapshot identity | Root package `immich-monorepo` version `2.7.5`; server and mobile manifests report `3.0.0` variants, so the unpacked snapshot contains version-skewed workspace metadata that Phase 1 must preserve as evidence |
| Monorepo/tooling | Mise experimental monorepo; pnpm workspace; pnpm `10.33.4`; Node `24.15.0`; TypeScript `^6.0.0` |
| Frontend | Svelte `5.55.8`; SvelteKit `^2.56.1`; Vite `^8.0.0`; static adapter `^3.0.8`; Tailwind CSS `^4.2.4`; Vitest `^4.0.0`; Socket.IO client `~4.8.0` |
| Backend | NestJS `^11.0.4`; Express `^5.1.0`; TypeScript; Kysely `0.28.17`; PostgreSQL clients `pg` and `postgres`; Socket.IO/WebSockets; Zod; Vitest |
| Jobs/cache | BullMQ `^5.51.0`, `@nestjs/bullmq`, `ioredis ^5.8.2`, Socket.IO Redis adapter |
| Database | PostgreSQL server model with checked-in schema and 34 SQL repository-query files; Kysely/Postgres adapters; mobile also uses Drift for its own local data |
| Machine learning | Python `3.11`; uv `0.8.15`; FastAPI, Gunicorn, Uvicorn, Pydantic, ONNX Runtime variants, InsightFace, OpenCV, Pillow, tokenizers, CLIP and OCR implementations |
| Media/metadata | Sharp `^0.34.5`; `exiftool-vendored ^35.20.0`; `fluent-ffmpeg`; configured Jellyfin FFmpeg `7.1.3-6`; ThumbHash and panorama/video viewers |
| Mobile | Flutter `3.44.0`; Dart SDK `>=3.12.0 <4.0.0`; Riverpod, Drift, background downloader, native Android Kotlin/Java and iOS Swift/Objective-C platform code |
| API generation | Server OpenAPI synchronization; `oazapfts 7.5.0` TypeScript client generation; OpenAPI Generator Dart client with templates/patches |
| Tests | Vitest, Playwright, Supertest, Testcontainers, Pytest, Flutter test/integration_test; 335 executable test source files by suffix/directory rule plus broader e2e/fixture/config evidence |
| Documentation | Docusaurus `~3.10.0`, MDX, React `^19.0.0` |
| Deployment | Docker/Compose, devcontainers, OpenTofu `1.11.6`, Terragrunt `1.0.3`, GitHub Actions |
| Target-desktop prerequisites | No `Cargo.toml` or Cargo lockfile was found in the Phase 0 inventory. This is inventory evidence only; Phase 1 performs the confirmed-absence search for Tauri/Rust implementation. |

## Package managers and locked toolchains

- pnpm with `pnpm-lock.yaml` and workspace manifests
- uv with `machine-learning/uv.lock`
- Flutter/Dart pub with mobile and UI-package lockfiles
- Gradle for Android and Swift Package/Xcode metadata for iOS
- Mise tool locks/configuration across root, web, server, ML, mobile, e2e, docs, CLI, plugins, deployment, and GitHub automation

