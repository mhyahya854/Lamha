# Duplicates

Exact/similar duplicate candidates and user-reviewed burst grouping.

## Current verified evidence

| Current path/line | Symbol | Evidence | Graph node | Action |
|---|---|---|---|---|
| `Codebase/web/src/routes/(user)/utilities/duplicates/[[photos=photos]]/[[assetId=id]]/+page.ts:L1-L1` | `duplicates/[[photos=photos]]/[[assetId=id]]/+page.ts` | EXTRACTED | `ext_codebase_web_src_routes_user_utilities_duplicates_photos_photos_assetid_id_page_ts` | REWRITE |
| `Codebase/web/src/routes/(user)/utilities/duplicates/[[photos=photos]]/[[assetId=id]]/+page.svelte:L1-L1` | `duplicates/[[photos=photos]]/[[assetId=id]]/+page.svelte` | EXTRACTED | `ext_codebase_web_src_routes_user_utilities_duplicates_photos_photos_assetid_id_page_svelte` | REWRITE |
| `Codebase/web/src/routes/(user)/utilities/duplicates/[[photos=photos]]/[[assetId=id]]/InfoRow.svelte:L1-L1` | `InfoRow.svelte` | EXTRACTED | `ext_codebase_web_src_routes_user_utilities_duplicates_photos_photos_assetid_id_inforow_svelte` | REWRITE |
| `Codebase/web/src/routes/(user)/utilities/duplicates/[[photos=photos]]/[[assetId=id]]/LinkToDocs.svelte:L1-L1` | `LinkToDocs.svelte` | EXTRACTED | `ext_codebase_web_src_routes_user_utilities_duplicates_photos_photos_assetid_id_linktodocs_svelte` | REWRITE |
| `Codebase/web/src/routes/(user)/utilities/duplicates/[[photos=photos]]/[[assetId=id]]/DuplicateAsset.svelte:L1-L1` | `./DuplicateAsset.svelte` | EXTRACTED | `ext_codebase_web_src_routes_user_utilities_duplicates_photos_photos_assetid_id_duplicateasset_svelte` | REWRITE |
| `Codebase/web/src/routes/(user)/utilities/duplicates/[[photos=photos]]/[[assetId=id]]/DuplicatesCompareControl.svelte:L1-L1` | `DuplicatesCompareControl.svelte` | EXTRACTED | `ext_codebase_web_src_routes_user_utilities_duplicates_photos_photos_assetid_id_duplicatescomparecontrol_svelte` | REWRITE |
| `Codebase/server/src/services/duplicate.service.ts:L1-L1` | `duplicate.service.ts` | EXTRACTED | `ext_codebase_server_src_services_duplicate_service_ts` | REWRITE |
| `Codebase/server/src/controllers/duplicate.controller.ts:L1-L1` | `duplicate.controller.ts` | EXTRACTED | `ext_codebase_server_src_controllers_duplicate_controller_ts` | REWRITE |
| `Codebase/server/src/repositories/duplicate.repository.ts:L1-L1` | `duplicate.repository.ts` | EXTRACTED | `ext_codebase_server_src_repositories_duplicate_repository_ts` | REWRITE |

## Current dependency boundary

- Complete pattern-matched production file set: **9**.
- Complete pattern-matched existing test file set: **3**.
- The table shows ten navigation anchors; all matched files and their calls/imports remain in the directed graph and symbol ledger. Deletion-critical edges require source verification and do not rely on inference alone.

## Target decision

- Classification: **REWRITE**.
- Assigned implementation phase: **Phase 10 — Local AI completeness**.
- Target modules: `src-tauri/src/duplicates/`, `src-tauri/src/commands/duplicates.rs`, `ai-worker/duplicates/`.
- Proof: focused behavior tests, affected regression tests, desktop build/launch when applicable, and requirement-linked evidence before any current subsystem is removed.
