# Gallery and timeline

Virtualized chronological browsing, selection, filters, and local-first asset loading.

## Current verified evidence

| Current path/line | Symbol | Evidence | Graph node | Action |
|---|---|---|---|---|
| `Codebase/web/src/lib/components/timeline/Month.svelte:L1-L1` | `lib/components/timeline/Month.svelte` | EXTRACTED | `ext_codebase_web_src_lib_components_timeline_month_svelte` | PORT |
| `Codebase/web/src/lib/components/timeline/Scrubber.svelte:L1-L1` | `lib/components/timeline/Scrubber.svelte` | EXTRACTED | `ext_codebase_web_src_lib_components_timeline_scrubber_svelte` | PORT |
| `Codebase/web/src/lib/components/timeline/Timeline.svelte:L1-L1` | `lib/components/timeline/Timeline.svelte` | EXTRACTED | `ext_codebase_web_src_lib_components_timeline_timeline_svelte` | PORT |
| `Codebase/web/src/lib/components/timeline/AssetLayout.svelte:L1-L1` | `lib/components/timeline/AssetLayout.svelte` | EXTRACTED | `ext_codebase_web_src_lib_components_timeline_assetlayout_svelte` | PORT |
| `Codebase/web/src/routes/(user)/photos/[[assetId=id]]/+page.ts:L1-L1` | `photos/[[assetId=id]]/+page.ts` | EXTRACTED | `ext_codebase_web_src_routes_user_photos_assetid_id_page_ts` | PORT |
| `Codebase/web/src/lib/components/timeline/actions/TagAction.svelte:L1-L1` | `lib/components/timeline/actions/TagAction.svelte` | EXTRACTED | `ext_codebase_web_src_lib_components_timeline_actions_tagaction_svelte` | PORT |
| `Codebase/web/src/lib/components/timeline/actions/focus-actions.ts:L1-L1` | `focus-actions.ts` | EXTRACTED | `ext_codebase_web_src_lib_components_timeline_actions_focus_actions_ts` | PORT |
| `Codebase/web/src/routes/(user)/photos/[[assetId=id]]/+page.svelte:L1-L1` | `photos/[[assetId=id]]/+page.svelte` | EXTRACTED | `ext_codebase_web_src_routes_user_photos_assetid_id_page_svelte` | PORT |
| `Codebase/web/src/lib/components/timeline/TimelineAssetViewer.svelte:L1-L1` | `lib/components/timeline/TimelineAssetViewer.svelte` | EXTRACTED | `ext_codebase_web_src_lib_components_timeline_timelineassetviewer_svelte` | PORT |
| `Codebase/web/src/lib/components/timeline/actions/StackAction.svelte:L1-L1` | `lib/components/timeline/actions/StackAction.svelte` | EXTRACTED | `ext_codebase_web_src_lib_components_timeline_actions_stackaction_svelte` | PORT |

## Current dependency boundary

- Complete pattern-matched production file set: **28**.
- Complete pattern-matched existing test file set: **16**.
- The table shows ten navigation anchors; all matched files and their calls/imports remain in the directed graph and symbol ledger. Deletion-critical edges require source verification and do not rely on inference alone.

## Target decision

- Classification: **PORT**.
- Assigned implementation phase: **Phase 5 — Asset API replacement**.
- Target modules: `web/src/lib/components/timeline/`, `src-tauri/src/commands/assets.rs`, `src-tauri/src/index/`.
- Proof: focused behavior tests, affected regression tests, desktop build/launch when applicable, and requirement-linked evidence before any current subsystem is removed.
