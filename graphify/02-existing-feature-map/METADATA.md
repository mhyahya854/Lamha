# Metadata

Metadata inspection, authority, EXIF/XMP handling, privacy, and reversible mutation.

## Current verified evidence

| Current path/line | Symbol | Evidence | Graph node | Action |
|---|---|---|---|---|
| `Codebase/web/src/lib/components/asset-viewer/DetailPanel.svelte:L1-L1` | `DetailPanel.svelte` | EXTRACTED | `ext_codebase_web_src_lib_components_asset_viewer_detailpanel_svelte` | REWRITE |
| `Codebase/web/src/lib/components/asset-viewer/DetailPanelDate.svelte:L1-L1` | `lib/components/asset-viewer/DetailPanelDate.svelte` | EXTRACTED | `ext_codebase_web_src_lib_components_asset_viewer_detailpaneldate_svelte` | REWRITE |
| `Codebase/web/src/lib/components/asset-viewer/DetailPanelTags.svelte:L1-L1` | `lib/components/asset-viewer/DetailPanelTags.svelte` | EXTRACTED | `ext_codebase_web_src_lib_components_asset_viewer_detailpaneltags_svelte` | REWRITE |
| `Codebase/web/src/lib/components/asset-viewer/DetailPanelPeople.svelte:L1-L1` | `lib/components/asset-viewer/DetailPanelPeople.svelte` | EXTRACTED | `ext_codebase_web_src_lib_components_asset_viewer_detailpanelpeople_svelte` | REWRITE |
| `Codebase/web/src/lib/components/asset-viewer/DetailPanelLocation.svelte:L1-L1` | `lib/components/asset-viewer/DetailPanelLocation.svelte` | EXTRACTED | `ext_codebase_web_src_lib_components_asset_viewer_detailpanellocation_svelte` | REWRITE |
| `Codebase/web/src/lib/components/asset-viewer/DetailPanelStarRating.svelte:L1-L1` | `lib/components/asset-viewer/DetailPanelStarRating.svelte` | EXTRACTED | `ext_codebase_web_src_lib_components_asset_viewer_detailpanelstarrating_svelte` | REWRITE |
| `Codebase/web/src/lib/components/asset-viewer/DetailPanelDescription.svelte:L1-L1` | `lib/components/asset-viewer/DetailPanelDescription.svelte` | EXTRACTED | `ext_codebase_web_src_lib_components_asset_viewer_detailpaneldescription_svelte` | REWRITE |
| `Codebase/server/src/services/metadata.service.ts:L1-L1` | `metadata.service.ts` | EXTRACTED | `ext_codebase_server_src_services_metadata_service_ts` | REWRITE |
| `Codebase/server/src/controllers/asset.controller.ts:L1-L1` | `asset.controller.ts` | EXTRACTED | `ext_codebase_server_src_controllers_asset_controller_ts` | REWRITE |
| `Codebase/server/src/repositories/metadata.repository.ts:L1-L1` | `metadata.repository.ts` | EXTRACTED | `ext_codebase_server_src_repositories_metadata_repository_ts` | REWRITE |

## Current dependency boundary

- Complete pattern-matched production file set: **10**.
- Complete pattern-matched existing test file set: **7**.
- The table shows ten navigation anchors; all matched files and their calls/imports remain in the directed graph and symbol ledger. Deletion-critical edges require source verification and do not rely on inference alone.

## Target decision

- Classification: **REWRITE**.
- Assigned implementation phase: **Phase 11 — Metadata mutation, editing, and privacy**.
- Target modules: `src-tauri/src/metadata/`, `src-tauri/src/assets/sidecars.rs`, `src-tauri/src/commands/metadata.rs`.
- Proof: focused behavior tests, affected regression tests, desktop build/launch when applicable, and requirement-linked evidence before any current subsystem is removed.
