# Libraries and storage

Library roots, scanning, storage, watchers, linked folders, external drives, and path sandboxing.

## Current verified evidence

| Current path/line | Symbol | Evidence | Graph node | Action |
|---|---|---|---|---|
| `Codebase/web/src/routes/admin/library-management/[id]/+page.ts:L1-L1` | `library-management/[id]/+page.ts` | EXTRACTED | `ext_codebase_web_src_routes_admin_library_management_id_page_ts` | REWRITE |
| `Codebase/web/src/routes/admin/library-management/[id]/+layout.ts:L1-L1` | `library-management/[id]/+layout.ts` | EXTRACTED | `ext_codebase_web_src_routes_admin_library_management_id_layout_ts` | REWRITE |
| `Codebase/web/src/routes/admin/library-management/(list)/+layout.ts:L1-L1` | `library-management/(list)/+layout.ts` | EXTRACTED | `ext_codebase_web_src_routes_admin_library_management_list_layout_ts` | REWRITE |
| `Codebase/web/src/routes/admin/library-management/[id]/+page.svelte:L1-L1` | `library-management/[id]/+page.svelte` | EXTRACTED | `ext_codebase_web_src_routes_admin_library_management_id_page_svelte` | REWRITE |
| `Codebase/web/src/routes/admin/library-management/[id]/edit/+page.ts:L1-L1` | `library-management/[id]/edit/+page.ts` | EXTRACTED | `ext_codebase_web_src_routes_admin_library_management_id_edit_page_ts` | REWRITE |
| `Codebase/web/src/routes/admin/library-management/(list)/+page.svelte:L1-L1` | `library-management/(list)/+page.svelte` | EXTRACTED | `ext_codebase_web_src_routes_admin_library_management_list_page_svelte` | REWRITE |
| `Codebase/web/src/routes/admin/library-management/(list)/new/+page.ts:L1-L1` | `library-management/(list)/new/+page.ts` | EXTRACTED | `ext_codebase_web_src_routes_admin_library_management_list_new_page_ts` | REWRITE |
| `Codebase/web/src/routes/admin/library-management/[id]/+layout.svelte:L1-L1` | `library-management/[id]/+layout.svelte` | EXTRACTED | `ext_codebase_web_src_routes_admin_library_management_id_layout_svelte` | REWRITE |
| `Codebase/web/src/routes/admin/library-management/(list)/+layout.svelte:L1-L1` | `library-management/(list)/+layout.svelte` | EXTRACTED | `ext_codebase_web_src_routes_admin_library_management_list_layout_svelte` | REWRITE |
| `Codebase/web/src/routes/admin/library-management/[id]/edit/+page.svelte:L1-L1` | `library-management/[id]/edit/+page.svelte` | EXTRACTED | `ext_codebase_web_src_routes_admin_library_management_id_edit_page_svelte` | REWRITE |

## Current dependency boundary

- Complete pattern-matched production file set: **16**.
- Complete pattern-matched existing test file set: **6**.
- The table shows ten navigation anchors; all matched files and their calls/imports remain in the directed graph and symbol ledger. Deletion-critical edges require source verification and do not rely on inference alone.

## Target decision

- Classification: **REWRITE**.
- Assigned implementation phase: **Phase 4 — Local data foundation**.
- Target modules: `src-tauri/src/library/`, `src-tauri/src/commands/library.rs`, `src-tauri/src/transactions/`.
- Proof: focused behavior tests, affected regression tests, desktop build/launch when applicable, and requirement-linked evidence before any current subsystem is removed.
