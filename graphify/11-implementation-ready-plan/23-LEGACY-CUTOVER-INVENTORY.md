# Legacy frontend and runtime cutover inventory

## Verified current facts

- `web/svelte.config.js` already uses `@sveltejs/adapter-static` with `fallback: 'index.html'`.
- There are no `+page.server.ts` or `+layout.server.ts` files under `web/src/routes` in this snapshot.
- The web source contains approximately 315 non-test files matching SDK/API/auth coupling patterns and three files with direct `fetch(` calls.
- `socket.io-client` is a production dependency.
- Static configuration injects Immich/FUTO commercial hosts through `PUBLIC_IMMICH_BUY_HOST` and `PUBLIC_IMMICH_PAY_HOST` defaults.
- Root/web/ML versions are `2.7.5`; server/mobile manifests use `3.0.0` variants.

## Consequence

The frontend migration is not a rewrite from SSR to static. The static build foundation already exists. The critical work is a consumer-by-consumer replacement of generated SDK/REST/socket/auth/server-admin assumptions with typed Tauri commands and local state, followed by removal of unused server-era routes, stores, dependencies, environment variables, and outbound defaults.

## Phase 3/5 required ledgers

1. Retained route/component → current SDK calls → target command(s) → real-data integration test.
2. Removed route/component → removal requirement → caller/import/navigation cleanup → absence test.
3. Shared store/service → server assumptions → replacement owner → migration phase.
4. External URL/dependency → keep/remove/opt-in decision → privacy/legal test.
5. Socket event → local Tauri event/background-job equivalent → ordering/reconnect test.
