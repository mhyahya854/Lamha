# Asset viewer

Photo/video viewing, detail panels, navigation, media playback, and retained viewer actions.

## Current verified evidence

| Current path/line | Symbol | Evidence | Graph node | Action |
|---|---|---|---|---|
| `Codebase/web/src/lib/components/asset-viewer/OcrButton.svelte:L1-L1` | `OcrButton.svelte` | EXTRACTED | `ext_codebase_web_src_lib_components_asset_viewer_ocrbutton_svelte` | PORT |
| `Codebase/web/src/routes/(user)/photos/[[assetId=id]]/+page.ts:L1-L1` | `photos/[[assetId=id]]/+page.ts` | EXTRACTED | `ext_codebase_web_src_routes_user_photos_assetid_id_page_ts` | PORT |
| `Codebase/web/src/lib/components/asset-viewer/actions/action.ts:L1-L1` | `action.ts` | EXTRACTED | `ext_codebase_web_src_lib_components_asset_viewer_actions_action_ts` | PORT |
| `Codebase/web/src/lib/components/asset-viewer/AssetViewer.svelte:L121-L121` | `if()` | EXTRACTED | `c_users_mhyah_downloads_code_lamha_codebase_web_src_lib_components_asset_viewer_assetviewer_if` | PORT |
| `Codebase/web/src/lib/components/asset-viewer/DetailPanel.svelte:L1-L1` | `DetailPanel.svelte` | EXTRACTED | `ext_codebase_web_src_lib_components_asset_viewer_detailpanel_svelte` | PORT |
| `Codebase/web/src/lib/components/asset-viewer/PhotoViewer.svelte:L162-L162` | `if()` | EXTRACTED | `c_users_mhyah_downloads_code_lamha_codebase_web_src_lib_components_asset_viewer_photoviewer_if` | PORT |
| `Codebase/web/src/lib/components/asset-viewer/SlideshowBar.svelte:L1-L1` | `SlideshowBar.svelte` | EXTRACTED | `ext_codebase_web_src_lib_components_asset_viewer_slideshowbar_svelte` | PORT |
| `Codebase/web/src/lib/components/asset-viewer/AlbumListItem.svelte:L1-L1` | `../components/asset-viewer/AlbumListItem.svelte` | EXTRACTED | `ext_codebase_web_src_lib_components_asset_viewer_albumlistitem_svelte` | PORT |
| `Codebase/web/src/routes/(user)/photos/[[assetId=id]]/+page.svelte:L1-L1` | `photos/[[assetId=id]]/+page.svelte` | EXTRACTED | `ext_codebase_web_src_routes_user_photos_assetid_id_page_svelte` | PORT |
| `Codebase/web/src/lib/components/asset-viewer/ActivityStatus.svelte:L1-L1` | `./ActivityStatus.svelte` | EXTRACTED | `ext_codebase_web_src_lib_components_asset_viewer_activitystatus_svelte` | PORT |

## Current dependency boundary

- Complete pattern-matched production file set: **103**.
- Complete pattern-matched existing test file set: **14**.
- The table shows ten navigation anchors; all matched files and their calls/imports remain in the directed graph and symbol ledger. Deletion-critical edges require source verification and do not rely on inference alone.

## Target decision

- Classification: **PORT**.
- Assigned implementation phase: **Phase 5 — Asset API replacement**.
- Target modules: `web/src/lib/components/asset-viewer/`, `src-tauri/src/commands/assets.rs`, `src-tauri/src/assets/`.
- Proof: focused behavior tests, affected regression tests, desktop build/launch when applicable, and requirement-linked evidence before any current subsystem is removed.
