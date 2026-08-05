# Sharing and mobile backup

Current server sharing and phone backup paths; remote/multi-user behavior is out of target scope while local export/backup is replaced.

## Current verified evidence

| Current path/line | Symbol | Evidence | Graph node | Action |
|---|---|---|---|---|
| `Codebase/web/src/routes/(user)/share/[key]/+error.svelte:L1-L1` | `[key]/+error.svelte` | EXTRACTED | `ext_codebase_web_src_routes_user_share_key_error_svelte` | REMOVE |
| `Codebase/web/src/routes/(user)/shared-links/(list)/+page.ts:L1-L1` | `(list)/+page.ts` | EXTRACTED | `ext_codebase_web_src_routes_user_shared_links_list_page_ts` | REMOVE |
| `Codebase/web/src/routes/(user)/shared-links/(list)/+layout.ts:L1-L1` | `shared-links/(list)/+layout.ts` | EXTRACTED | `ext_codebase_web_src_routes_user_shared_links_list_layout_ts` | REMOVE |
| `Codebase/web/src/routes/(user)/shared-links/(list)/+page.svelte:L1-L1` | `shared-links/(list)/+page.svelte` | EXTRACTED | `ext_codebase_web_src_routes_user_shared_links_list_page_svelte` | REMOVE |
| `Codebase/web/src/routes/(user)/shared-links/(list)/+layout.svelte:L1-L1` | `shared-links/(list)/+layout.svelte` | EXTRACTED | `ext_codebase_web_src_routes_user_shared_links_list_layout_svelte` | REMOVE |
| `Codebase/web/src/routes/(user)/shared-links/(list)/[id]/+layout.ts:L1-L1` | `(list)/[id]/+layout.ts` | EXTRACTED | `ext_codebase_web_src_routes_user_shared_links_list_id_layout_ts` | REMOVE |
| `Codebase/web/src/routes/(user)/shared-links/(list)/ShareCover.svelte:L1-L1` | `./ShareCover.svelte` | EXTRACTED | `ext_codebase_web_src_routes_user_shared_links_list_sharecover_svelte` | REMOVE |
| `Codebase/web/src/routes/(user)/shared-links/(list)/[id]/edit/+page.ts:L1-L1` | `(list)/[id]/edit/+page.ts` | EXTRACTED | `ext_codebase_web_src_routes_user_shared_links_list_id_edit_page_ts` | REMOVE |
| `Codebase/web/src/routes/(user)/shared-links/(list)/SharedLinkCard.svelte:L1-L1` | `SharedLinkCard.svelte` | EXTRACTED | `ext_codebase_web_src_routes_user_shared_links_list_sharedlinkcard_svelte` | REMOVE |
| `Codebase/web/src/routes/(user)/shared-links/(list)/[id]/edit/+page.svelte:L1-L1` | `(list)/[id]/edit/+page.svelte` | EXTRACTED | `ext_codebase_web_src_routes_user_shared_links_list_id_edit_page_svelte` | REMOVE |

## Current dependency boundary

- Complete pattern-matched production file set: **677**.
- Complete pattern-matched existing test file set: **7**.
- The table shows ten navigation anchors; all matched files and their calls/imports remain in the directed graph and symbol ledger. Deletion-critical edges require source verification and do not rely on inference alone.

## Target decision

- Classification: **REMOVE**.
- Assigned implementation phase: **Phase 15 — Full integration, parity, and cross-platform packaging**.
- Target modules: `src-tauri/src/backup/`, `src-tauri/src/commands/export.rs`.
- Proof: focused behavior tests, affected regression tests, desktop build/launch when applicable, and requirement-linked evidence before any current subsystem is removed.
