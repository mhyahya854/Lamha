# Administration

Current server administration, queues, users, and maintenance; retained device settings move to local desktop settings.

## Current verified evidence

| Current path/line | Symbol | Evidence | Graph node | Action |
|---|---|---|---|---|
| `Codebase/web/src/routes/admin/+page.ts:L1-L1` | `admin/+page.ts` | EXTRACTED | `ext_codebase_web_src_routes_admin_page_ts` | REMOVE |
| `Codebase/web/src/routes/admin/+layout.ts:L1-L1` | `admin/+layout.ts` | EXTRACTED | `ext_codebase_web_src_routes_admin_layout_ts` | REMOVE |
| `Codebase/web/src/routes/admin/+page.svelte:L1-L1` | `admin/+page.svelte` | EXTRACTED | `ext_codebase_web_src_routes_admin_page_svelte` | REMOVE |
| `Codebase/web/src/routes/admin/queues/+page.ts:L1-L1` | `queues/+page.ts` | EXTRACTED | `ext_codebase_web_src_routes_admin_queues_page_ts` | REMOVE |
| `Codebase/web/src/routes/admin/queues/+page.svelte:L1-L1` | `queues/+page.svelte` | EXTRACTED | `ext_codebase_web_src_routes_admin_queues_page_svelte` | REMOVE |
| `Codebase/web/src/routes/admin/users/[id]/+page.ts:L1-L1` | `users/[id]/+page.ts` | EXTRACTED | `ext_codebase_web_src_routes_admin_users_id_page_ts` | REMOVE |
| `Codebase/web/src/routes/admin/jobs-status/+page.ts:L1-L1` | `jobs-status/+page.ts` | EXTRACTED | `ext_codebase_web_src_routes_admin_jobs_status_page_ts` | REMOVE |
| `Codebase/web/src/routes/admin/maintenance/+page.ts:L1-L1` | `admin/maintenance/+page.ts` | EXTRACTED | `ext_codebase_web_src_routes_admin_maintenance_page_ts` | REMOVE |
| `Codebase/web/src/routes/admin/users/[id]/+layout.ts:L1-L1` | `users/[id]/+layout.ts` | EXTRACTED | `ext_codebase_web_src_routes_admin_users_id_layout_ts` | REMOVE |
| `Codebase/web/src/routes/admin/queues/[name]/+page.ts:L1-L1` | `[name]/+page.ts` | EXTRACTED | `ext_codebase_web_src_routes_admin_queues_name_page_ts` | REMOVE |

## Current dependency boundary

- Complete pattern-matched production file set: **73**.
- Complete pattern-matched existing test file set: **9**.
- The table shows ten navigation anchors; all matched files and their calls/imports remain in the directed graph and symbol ledger. Deletion-critical edges require source verification and do not rely on inference alone.

## Target decision

- Classification: **REMOVE**.
- Assigned implementation phase: **Phase 15 — Full integration, parity, and cross-platform packaging**.
- Target modules: `web/src/routes/settings/`, `src-tauri/src/settings/`.
- Proof: focused behavior tests, affected regression tests, desktop build/launch when applicable, and requirement-linked evidence before any current subsystem is removed.
