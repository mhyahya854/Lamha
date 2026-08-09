# WP-I0-007 baseline build and test attempts

- Status: **PASS**
- Run: `run-20260809-019`
- External run: `C:\Users\mhyah\Downloads\Code\Lamha-isolated-output\WP-I0-007\run-20260809-019` (removed after inventory)
- Results: 1 successes, 2 executed failures, 48 pre-execution blockers.

| ID | Source | Source command | Executed | Status | Exit | Blocker |
|---|---|---|---:|---|---:|---|
| node-docs-build | Codebase/docs/package.json | `pnpm run copy:openapi && docusaurus build` | false | BLOCKED |  | PROJECT_DEPENDENCIES_UNAVAILABLE |
| node-e2e-test | Codebase/e2e/package.json | `vitest --run` | false | BLOCKED |  | PROJECT_DEPENDENCIES_UNAVAILABLE |
| node-e2e-test-maintenance | Codebase/e2e/package.json | `vitest --run --config vitest.maintenance.config.ts` | false | BLOCKED |  | PROJECT_DEPENDENCIES_UNAVAILABLE |
| node-e2e-test-web | Codebase/e2e/package.json | `pnpm exec playwright test --project=web` | false | BLOCKED |  | PROJECT_DEPENDENCIES_UNAVAILABLE |
| node-e2e-test-web-maintenance | Codebase/e2e/package.json | `pnpm exec playwright test --project=maintenance` | false | BLOCKED |  | PROJECT_DEPENDENCIES_UNAVAILABLE |
| node-e2e-test-web-ui | Codebase/e2e/package.json | `pnpm exec playwright test --project=ui` | false | BLOCKED |  | PROJECT_DEPENDENCIES_UNAVAILABLE |
| node-packages-cli-build | Codebase/packages/cli/package.json | `vite build` | false | BLOCKED |  | PROJECT_DEPENDENCIES_UNAVAILABLE |
| node-packages-cli-build-dev | Codebase/packages/cli/package.json | `vite build --sourcemap true` | false | BLOCKED |  | PROJECT_DEPENDENCIES_UNAVAILABLE |
| node-packages-cli-test | Codebase/packages/cli/package.json | `vitest` | false | BLOCKED |  | PROJECT_DEPENDENCIES_UNAVAILABLE |
| node-packages-cli-test-cov | Codebase/packages/cli/package.json | `vitest --coverage` | false | BLOCKED |  | PROJECT_DEPENDENCIES_UNAVAILABLE |
| node-packages-plugin-core-build | Codebase/packages/plugin-core/package.json | `pnpm build:tsc && pnpm build:wasm` | false | BLOCKED |  | PROJECT_DEPENDENCIES_UNAVAILABLE |
| node-packages-plugin-core-build-tsc | Codebase/packages/plugin-core/package.json | `tsc --noEmit && node esbuild.js` | false | BLOCKED |  | PROJECT_DEPENDENCIES_UNAVAILABLE |
| node-packages-plugin-core-build-wasm | Codebase/packages/plugin-core/package.json | `extism-js dist/index.js -i src/index.d.ts -o dist/plugin.wasm` | false | BLOCKED |  | PROJECT_DEPENDENCIES_UNAVAILABLE |
| node-packages-plugin-sdk-build | Codebase/packages/plugin-sdk/package.json | `node esbuild.js && tsc --emitDeclarationOnly && tsc-alias` | false | BLOCKED |  | PROJECT_DEPENDENCIES_UNAVAILABLE |
| node-packages-plugin-sdk-test | Codebase/packages/plugin-sdk/package.json | `echo "Error: no test specified" && exit 1` | false | BLOCKED |  | PROJECT_DEPENDENCIES_UNAVAILABLE |
| node-packages-sdk-build | Codebase/packages/sdk/package.json | `tsc` | false | BLOCKED |  | PROJECT_DEPENDENCIES_UNAVAILABLE |
| node-server-build | Codebase/server/package.json | `nest build` | false | BLOCKED |  | PROJECT_DEPENDENCIES_UNAVAILABLE |
| node-server-test | Codebase/server/package.json | `vitest --config test/vitest.config.mjs` | false | BLOCKED |  | PROJECT_DEPENDENCIES_UNAVAILABLE |
| node-server-test-cov | Codebase/server/package.json | `vitest --config test/vitest.config.mjs --coverage` | false | BLOCKED |  | PROJECT_DEPENDENCIES_UNAVAILABLE |
| node-server-test-medium | Codebase/server/package.json | `vitest --config test/vitest.config.medium.mjs` | false | BLOCKED |  | PROJECT_DEPENDENCIES_UNAVAILABLE |
| node-web-build | Codebase/web/package.json | `vite build` | false | BLOCKED |  | PROJECT_DEPENDENCIES_UNAVAILABLE |
| node-web-build-stats | Codebase/web/package.json | `BUILD_STATS=true vite build` | false | BLOCKED |  | PROJECT_DEPENDENCIES_UNAVAILABLE |
| node-web-test | Codebase/web/package.json | `vitest` | false | BLOCKED |  | PROJECT_DEPENDENCIES_UNAVAILABLE |
| node-web-test-cov | Codebase/web/package.json | `vitest --coverage` | false | BLOCKED |  | PROJECT_DEPENDENCIES_UNAVAILABLE |
| mise-docs-build | Codebase/docs/mise.toml | `jq -c < ../open-api/immich-openapi-specs.json > ./static/openapi.json &#124;&#124; exit 0 && docusaurus build` | false | BLOCKED |  | DECLARED_BUILD_OUTPUT_REDIRECTION_UNPROVEN |
| mise-e2e-build | Codebase/e2e/mise.toml | `docker compose build` | false | BLOCKED |  | CONTAINER_RUNTIME_AND_PROJECT_DEPENDENCIES_UNAVAILABLE |
| mise-e2e-test | Codebase/e2e/mise.toml | `vitest --run` | false | BLOCKED |  | CONTAINER_RUNTIME_AND_PROJECT_DEPENDENCIES_UNAVAILABLE |
| mise-e2e-test-web | Codebase/e2e/mise.toml | `playwright test` | false | BLOCKED |  | CONTAINER_RUNTIME_AND_PROJECT_DEPENDENCIES_UNAVAILABLE |
| ml-unit-test | Codebase/machine-learning/mise.toml | `uv run pytest --cov=immich_ml --cov-report term-missing` | true | FAILURE | 1 | COMMAND_EXIT_NONZERO |
| docker-dev-scale-build | Codebase/mise.toml | `mise run //:dev --build -V --scale immich-server=3` | false | BLOCKED |  | CONTAINER_RUNTIME_VOLUME_AND_NETWORK_UNAVAILABLE |
| docker-dev-update-build | Codebase/mise.toml | `mise run //:dev --build -V` | false | BLOCKED |  | CONTAINER_RUNTIME_VOLUME_AND_NETWORK_UNAVAILABLE |
| docker-e2e-update-build | Codebase/mise.toml | `mise run //:e2e --build -V` | false | BLOCKED |  | CONTAINER_RUNTIME_VOLUME_AND_NETWORK_UNAVAILABLE |
| docker-prod-build | Codebase/mise.toml | `docker compose -f ./docker-compose.prod.yml up --build --remove-orphans` | false | BLOCKED |  | CONTAINER_RUNTIME_VOLUME_AND_NETWORK_UNAVAILABLE |
| docker-prod-scale-build | Codebase/mise.toml | `mise run //:prod --build -V --scale immich-server=3 --scale immich-microservices` | false | BLOCKED |  | CONTAINER_RUNTIME_VOLUME_AND_NETWORK_UNAVAILABLE |
| mobile-android-build | Codebase/mobile/mise.toml | `flutter build appbundle` | false | BLOCKED |  | FLUTTER_OUTPUT_REDIRECTION_UNPROVEN |
| mobile-unit-test | Codebase/mobile/mise.toml | `flutter test` | false | BLOCKED |  | FLUTTER_OUTPUT_REDIRECTION_UNPROVEN |
| mise-packages-cli-build | Codebase/packages/cli/mise.toml | `vite build` | false | BLOCKED |  | DECLARED_BUILD_OUTPUT_REDIRECTION_UNPROVEN |
| mise-packages-cli-test | Codebase/packages/cli/mise.toml | `vitest` | false | BLOCKED |  | TEST_SIDE_EFFECT_REDIRECTION_UNPROVEN |
| mise-packages-plugin-core-build | Codebase/packages/plugin-core/mise.toml | `pnpm --filter @immich/plugin-sdk --filter @immich/plugin-core build` | false | BLOCKED |  | DECLARED_BUILD_OUTPUT_REDIRECTION_UNPROVEN |
| mise-server-build | Codebase/server/mise.toml | `nest build` | false | BLOCKED |  | DECLARED_BUILD_OUTPUT_REDIRECTION_UNPROVEN |
| mise-server-test | Codebase/server/mise.toml | `vitest --config test/vitest.config.mjs` | false | BLOCKED |  | TEST_SIDE_EFFECT_REDIRECTION_UNPROVEN |
| mise-server-test-medium | Codebase/server/mise.toml | `vitest --config test/vitest.config.medium.mjs` | false | BLOCKED |  | TEST_SIDE_EFFECT_REDIRECTION_UNPROVEN |
| mise-web-build | Codebase/web/mise.toml | `pnpm run build` | false | BLOCKED |  | DECLARED_BUILD_OUTPUT_REDIRECTION_UNPROVEN |
| mise-web-build-stats | Codebase/web/mise.toml | `pnpm run build:stats` | false | BLOCKED |  | DECLARED_BUILD_OUTPUT_REDIRECTION_UNPROVEN |
| mise-web-test | Codebase/web/mise.toml | `pnpm run test` | false | BLOCKED |  | TEST_SIDE_EFFECT_REDIRECTION_UNPROVEN |
| ml-bytecode-build | Codebase/machine-learning/pyproject.toml | `Python source bytecode compilation` | true | SUCCESS | 0 |  |
| ml-package-build | Codebase/machine-learning/pyproject.toml | `[build-system] package build` | true | FAILURE | 2 | COMMAND_EXIT_NONZERO |
| mobile-ui-unit-test | Codebase/mobile/packages/ui/test | `flutter test` | false | BLOCKED |  | FLUTTER_OUTPUT_REDIRECTION_UNPROVEN |
| open-api-dart-build | Codebase/mise.toml | `[tasks.open-api-dart] bash ./bin/generate-dart-sdk.sh` | false | BLOCKED |  | GENERATED_SOURCE_REDIRECTION_UNPROVEN |
| ios-build | Codebase/mobile/ios/Runner.xcodeproj/project.pbxproj | `Xcode Runner build` | false | BLOCKED |  | PLATFORM_AND_DERIVED_DATA_REDIRECTION_UNAVAILABLE |
| docker-e2e-test | Codebase/mise.toml | `[tasks.e2e] docker compose -f ./docker-compose.yml up --remove-orphans` | false | BLOCKED |  | CONTAINER_RUNTIME_AND_VOLUME_WRITES_UNAVAILABLE |
