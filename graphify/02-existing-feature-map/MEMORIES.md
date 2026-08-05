# Memories

Date-based memory presentation backed by local asset queries.

## Current verified evidence

| Current path/line | Symbol | Evidence | Graph node | Action |
|---|---|---|---|---|
| `Codebase/web/src/routes/(user)/memory/[[photos=photos]]/[[assetId=id]]/+page.ts:L1-L1` | `memory/[[photos=photos]]/[[assetId=id]]/+page.ts` | EXTRACTED | `ext_codebase_web_src_routes_user_memory_photos_photos_assetid_id_page_ts` | PORT |
| `Codebase/web/src/routes/(user)/memory/[[photos=photos]]/[[assetId=id]]/+page.svelte:L1-L1` | `memory/[[photos=photos]]/[[assetId=id]]/+page.svelte` | EXTRACTED | `ext_codebase_web_src_routes_user_memory_photos_photos_assetid_id_page_svelte` | PORT |
| `Codebase/web/src/routes/(user)/memory/[[photos=photos]]/[[assetId=id]]/MemoryViewer.svelte:L1-L1` | `MemoryViewer.svelte` | EXTRACTED | `ext_codebase_web_src_routes_user_memory_photos_photos_assetid_id_memoryviewer_svelte` | PORT |
| `Codebase/web/src/routes/(user)/memory/[[photos=photos]]/[[assetId=id]]/MemoryPhotoViewer.svelte:L32-L32` | `addEventListener()` | EXTRACTED | `c_users_mhyah_downloads_code_lamha_codebase_web_src_routes_user_memory_photos_photos_assetid_id_memoryphotoviewer_addeventlistener` | PORT |
| `Codebase/web/src/routes/(user)/memory/[[photos=photos]]/[[assetId=id]]/MemoryVideoViewer.svelte:L1-L1` | `./MemoryVideoViewer.svelte` | EXTRACTED | `ext_codebase_web_src_routes_user_memory_photos_photos_assetid_id_memoryvideoviewer_svelte` | PORT |
| `Codebase/server/src/services/memory.service.ts:L1-L1` | `memory.service.ts` | EXTRACTED | `ext_codebase_server_src_services_memory_service_ts` | PORT |
| `Codebase/server/src/controllers/memory.controller.ts:L1-L1` | `memory.controller.ts` | EXTRACTED | `ext_codebase_server_src_controllers_memory_controller_ts` | PORT |
| `Codebase/server/src/repositories/memory.repository.ts:L1-L1` | `memory.repository.ts` | EXTRACTED | `ext_codebase_server_src_repositories_memory_repository_ts` | PORT |

## Current dependency boundary

- Complete pattern-matched production file set: **8**.
- Complete pattern-matched existing test file set: **5**.
- The table shows ten navigation anchors; all matched files and their calls/imports remain in the directed graph and symbol ledger. Deletion-critical edges require source verification and do not rely on inference alone.

## Target decision

- Classification: **PORT**.
- Assigned implementation phase: **Phase 5 — Asset API replacement**.
- Target modules: `src-tauri/src/commands/memories.rs`, `src-tauri/src/index/memories.rs`, `web/src/routes/(user)/memory/`.
- Proof: focused behavior tests, affected regression tests, desktop build/launch when applicable, and requirement-linked evidence before any current subsystem is removed.
