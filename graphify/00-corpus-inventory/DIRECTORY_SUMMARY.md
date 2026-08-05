# Directory summary

The snapshot contains **3,697** regular files. Exact path, byte size, category, and graph policy are recorded in `FILE_CLASSIFICATION.csv`; exact top-level totals are recorded in `DIRECTORY_COUNTS.csv`.

| Top-level area | Files | Bytes | Inventory role |
|---|---:|---:|---|
| `mobile/` | 1,607 | 73,880,442 | Flutter/Dart mobile application, native Android/iOS bridges, assets, tests, and generated Dart API client |
| `web/` | 736 | 7,966,698 | Svelte/SvelteKit frontend routes, components, stores/utilities, configuration, and tests |
| `server/` | 646 | 3,768,709 | NestJS controllers/services/repositories/workers, SQL schema/queries, media/storage/jobs, and tests |
| `docs/` | 297 | 15,764,398 | Docusaurus product, architecture, install, developer, and workflow documentation plus assets |
| `e2e/` | 86 | 672,864 | Vitest/Playwright end-to-end infrastructure, Docker orchestration, fixtures, and helpers |
| `i18n/` | 79 | 9,765,682 | Translation source JSON and formatting configuration |
| `packages/` | 51 | 327,828 | CLI, generated TypeScript SDK, plugin SDK/core, and e2e auth server workspaces |
| `machine-learning/` | 50 | 818,066 | Python FastAPI/Gunicorn/Uvicorn ML service, ONNX/InsightFace/CLIP/OCR logic, tests, and container setup |
| `.github/` | 34 | 113,140 | 23 workflow files plus repository templates/configuration |
| `deployment/` | 20 | 14,500 | OpenTofu/Terragrunt deployment configuration |
| `readme_i18n/` | 18 | 108,398 | Upstream translated README files |
| `design/` | 14 | 2,424,974 | Immich logos/screenshots and one excluded OS metadata file |
| `open-api/` | 12 | 754,359 | Generated OpenAPI specification plus Dart generator templates and patches |
| `docker/` | 10 | 20,237 | Development, production, rootless, and default Compose configurations |
| `.devcontainer/` | 7 | 10,093 | Server/mobile development-container configuration and startup scripts |
| Other roots/files | 30 | 1,105,590 | Root manifests/locks/legal files, `.vscode/`, `fastlane/`, and `misc/` |

## Source-layout observations

- `server/src/` has `bin`, `commands`, `controllers`, `cores`, `dtos`, `emails`, `maintenance`, `middleware`, `queries`, `repositories`, `schema`, `services`, `utils`, and `workers` boundaries.
- `web/src/routes/` has `(user)`, `admin`, `auth`, `link`, and `maintenance` route groups.
- `mobile/lib/` has domain, infrastructure, repositories, services, presentation/pages/widgets, providers, platform, routing, and utility layers.
- `server/src/queries/` contains 34 checked-in SQL query files.
- No `node_modules`, `dist`, `build`, `.svelte-kit`, coverage, package-store, Dart-tool, Python bytecode, pytest, mypy, or Ruff cache directories were present.

