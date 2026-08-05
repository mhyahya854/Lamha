# Authentication and users

Current multi-user/auth/session architecture; target desktop has one local operator and no account requirement.

## Current verified evidence

| Current path/line | Symbol | Evidence | Graph node | Action |
|---|---|---|---|---|
| `Codebase/web/src/routes/auth/login/+page.ts:L1-L1` | `login/+page.ts` | EXTRACTED | `ext_codebase_web_src_routes_auth_login_page_ts` | REMOVE |
| `Codebase/web/src/routes/auth/register/+page.ts:L1-L1` | `register/+page.ts` | EXTRACTED | `ext_codebase_web_src_routes_auth_register_page_ts` | REMOVE |
| `Codebase/web/src/routes/auth/login/+page.svelte:L1-L1` | `login/+page.svelte` | EXTRACTED | `ext_codebase_web_src_routes_auth_login_page_svelte` | REMOVE |
| `Codebase/web/src/routes/auth/logout/+page.svelte:L1-L1` | `logout/+page.svelte` | EXTRACTED | `ext_codebase_web_src_routes_auth_logout_page_svelte` | REMOVE |
| `Codebase/web/src/routes/auth/onboarding/+page.ts:L1-L1` | `onboarding/+page.ts` | EXTRACTED | `ext_codebase_web_src_routes_auth_onboarding_page_ts` | REMOVE |
| `Codebase/web/src/routes/auth/pin-prompt/+page.ts:L1-L1` | `pin-prompt/+page.ts` | EXTRACTED | `ext_codebase_web_src_routes_auth_pin_prompt_page_ts` | REMOVE |
| `Codebase/web/src/routes/admin/users/[id]/+page.ts:L1-L1` | `users/[id]/+page.ts` | EXTRACTED | `ext_codebase_web_src_routes_admin_users_id_page_ts` | REMOVE |
| `Codebase/web/src/routes/auth/register/+page.svelte:L1-L1` | `register/+page.svelte` | EXTRACTED | `ext_codebase_web_src_routes_auth_register_page_svelte` | REMOVE |
| `Codebase/web/src/routes/admin/users/[id]/+layout.ts:L1-L1` | `users/[id]/+layout.ts` | EXTRACTED | `ext_codebase_web_src_routes_admin_users_id_layout_ts` | REMOVE |
| `Codebase/web/src/routes/auth/onboarding/+page.svelte:L1-L1` | `onboarding/+page.svelte` | EXTRACTED | `ext_codebase_web_src_routes_auth_onboarding_page_svelte` | REMOVE |

## Current dependency boundary

- Complete pattern-matched production file set: **37**.
- Complete pattern-matched existing test file set: **17**.
- The table shows ten navigation anchors; all matched files and their calls/imports remain in the directed graph and symbol ledger. Deletion-critical edges require source verification and do not rely on inference alone.

## Target decision

- Classification: **REMOVE**.
- Assigned implementation phase: **Phase 3 — Tauri desktop shell**.
- Target modules: `src-tauri/src/settings/local_operator.rs`, `web/src/routes/+layout.svelte`.
- Proof: focused behavior tests, affected regression tests, desktop build/launch when applicable, and requirement-linked evidence before any current subsystem is removed.
