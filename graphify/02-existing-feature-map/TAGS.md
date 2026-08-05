# Tags

Tag browsing and assignment with review-first local authority and provenance.

## Current verified evidence

| Current path/line | Symbol | Evidence | Graph node | Action |
|---|---|---|---|---|
| `Codebase/web/src/lib/components/shared-components/TagPill.svelte:L1-L1` | `../components/shared-components/TagPill.svelte` | EXTRACTED | `ext_codebase_web_src_lib_components_shared_components_tagpill_svelte` | REWRITE |
| `Codebase/web/src/lib/components/timeline/actions/TagAction.svelte:L1-L1` | `lib/components/timeline/actions/TagAction.svelte` | EXTRACTED | `ext_codebase_web_src_lib_components_timeline_actions_tagaction_svelte` | REWRITE |
| `Codebase/web/src/lib/components/asset-viewer/DetailPanelTags.svelte:L1-L1` | `lib/components/asset-viewer/DetailPanelTags.svelte` | EXTRACTED | `ext_codebase_web_src_lib_components_asset_viewer_detailpaneltags_svelte` | REWRITE |
| `Codebase/web/src/routes/(user)/tags/[[photos=photos]]/[[assetId=id]]/+page.ts:L1-L1` | `tags/[[photos=photos]]/[[assetId=id]]/+page.ts` | EXTRACTED | `ext_codebase_web_src_routes_user_tags_photos_photos_assetid_id_page_ts` | REWRITE |
| `Codebase/web/src/routes/(user)/tags/[[photos=photos]]/[[assetId=id]]/+page.svelte:L1-L1` | `tags/[[photos=photos]]/[[assetId=id]]/+page.svelte` | EXTRACTED | `ext_codebase_web_src_routes_user_tags_photos_photos_assetid_id_page_svelte` | REWRITE |
| `Codebase/web/src/lib/components/shared-components/search-bar/SearchTagsSection.svelte:L1-L1` | `lib/components/shared-components/search-bar/SearchTagsSection.svelte` | EXTRACTED | `ext_codebase_web_src_lib_components_shared_components_search_bar_searchtagssection_svelte` | REWRITE |
| `Codebase/server/src/services/tag.service.ts:L1-L1` | `src/services/tag.service.ts` | EXTRACTED | `ext_codebase_server_src_services_tag_service_ts` | REWRITE |
| `Codebase/server/src/controllers/tag.controller.ts:L1-L1` | `tag.controller.ts` | EXTRACTED | `ext_codebase_server_src_controllers_tag_controller_ts` | REWRITE |
| `Codebase/server/src/repositories/tag.repository.ts:L1-L1` | `tag.repository.ts` | EXTRACTED | `ext_codebase_server_src_repositories_tag_repository_ts` | REWRITE |

## Current dependency boundary

- Complete pattern-matched production file set: **9**.
- Complete pattern-matched existing test file set: **4**.
- The table shows ten navigation anchors; all matched files and their calls/imports remain in the directed graph and symbol ledger. Deletion-critical edges require source verification and do not rely on inference alone.

## Target decision

- Classification: **REWRITE**.
- Assigned implementation phase: **Phase 8 — Tags, relationships, smart views, and attribution**.
- Target modules: `src-tauri/src/tags/`, `src-tauri/src/commands/tags.rs`, `web/src/lib/components/tags/`.
- Proof: focused behavior tests, affected regression tests, desktop build/launch when applicable, and requirement-linked evidence before any current subsystem is removed.
