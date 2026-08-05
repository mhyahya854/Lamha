# Release proof gates and command registry

| Scope | Evidence-backed command/interface | Planning status |
|---|---|---|
| Web build | `mise //web:build` / `pnpm run build` | Discovered, not executed |
| Web checks | `mise //web:check-svelte`; `mise //web:check-typescript` | Discovered, not executed |
| Web unit | `mise //web:test --run` / `pnpm run test` | Discovered, not executed |
| Server build/check | `mise //server:build`; `mise //server:check` | Discovered, not executed |
| Server tests | `mise //server:test --run`; `mise //server:test-medium --run` | Discovered, not executed |
| ML | `mise //machine-learning:lint`; `:check`; `:test` | Discovered, not executed |
| Mobile | `mise //mobile:analyze`; `mise //mobile:test` | Discovered, not executed |
| E2E | `mise //e2e:test`; `mise //e2e:test-web` | Docker/install dependent; not executed |
| Target Rust/Tauri | Commands absent until Phase 3 manifests exist | Create exact registry in Phase 3 before proof |

Completion requires focused tests, applicable Gates 1–8, affected regression, build, desktop launch, clean package, legal, and traceability proof. Commands that mutate dependencies/generated output/migrations/deployment remain forbidden in Phase 0/1 and were not run.
