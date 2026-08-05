# Map and location

Offline-capable coordinate browsing and reviewed local location metadata.

## Current verified evidence

| Current path/line | Symbol | Evidence | Graph node | Action |
|---|---|---|---|---|
| `Codebase/web/src/lib/components/album-page/AlbumMap.svelte:L1-L1` | `lib/components/album-page/AlbumMap.svelte` | EXTRACTED | `ext_codebase_web_src_lib_components_album_page_albummap_svelte` | REWRITE |
| `Codebase/web/src/lib/components/shared-components/map/types.ts:L1-L1` | `SelectionBBox` | EXTRACTED | `c_users_mhyah_downloads_code_lamha_codebase_web_src_lib_components_shared_components_map_types_selectionbbox` | REWRITE |
| `Codebase/web/src/lib/components/shared-components/map/Map.svelte:L1-L1` | `lib/components/shared-components/map/Map.svelte` | EXTRACTED | `ext_codebase_web_src_lib_components_shared_components_map_map_svelte` | REWRITE |
| `Codebase/web/src/routes/(user)/map/[[photos=photos]]/[[assetId=id]]/+page.ts:L1-L1` | `map/[[photos=photos]]/[[assetId=id]]/+page.ts` | EXTRACTED | `ext_codebase_web_src_routes_user_map_photos_photos_assetid_id_page_ts` | REWRITE |
| `Codebase/web/src/routes/(user)/map/[[photos=photos]]/[[assetId=id]]/+page.svelte:L1-L1` | `map/[[photos=photos]]/[[assetId=id]]/+page.svelte` | EXTRACTED | `ext_codebase_web_src_routes_user_map_photos_photos_assetid_id_page_svelte` | REWRITE |
| `Codebase/web/src/routes/(user)/map/[[photos=photos]]/[[assetId=id]]/MapTimelinePanel.svelte:L1-L1` | `MapTimelinePanel.svelte` | EXTRACTED | `ext_codebase_web_src_routes_user_map_photos_photos_assetid_id_maptimelinepanel_svelte` | REWRITE |
| `Codebase/server/src/services/map.service.ts:L1-L1` | `map.service.ts` | EXTRACTED | `ext_codebase_server_src_services_map_service_ts` | REWRITE |
| `Codebase/server/src/controllers/map.controller.ts:L1-L1` | `map.controller.ts` | EXTRACTED | `ext_codebase_server_src_controllers_map_controller_ts` | REWRITE |
| `Codebase/server/src/repositories/map.repository.ts:L1-L1` | `map.repository.ts` | EXTRACTED | `ext_codebase_server_src_repositories_map_repository_ts` | REWRITE |

## Current dependency boundary

- Complete pattern-matched production file set: **9**.
- Complete pattern-matched existing test file set: **1**.
- The table shows ten navigation anchors; all matched files and their calls/imports remain in the directed graph and symbol ledger. Deletion-critical edges require source verification and do not rely on inference alone.

## Target decision

- Classification: **REWRITE**.
- Assigned implementation phase: **Phase 5 — Asset API replacement**.
- Target modules: `src-tauri/src/maps/`, `src-tauri/src/commands/maps.rs`, `web/src/lib/components/map/`.
- Proof: focused behavior tests, affected regression tests, desktop build/launch when applicable, and requirement-linked evidence before any current subsystem is removed.
