# Frontend architecture

The SvelteKit route tree contains authenticated user, admin, auth, link, and maintenance groups. Shared components live under `web/src/lib/components`; data access imports the generated `@immich/sdk`; Socket.IO supplies server events. The static adapter is present, but current route/load/auth assumptions remain server-coupled.

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

Target rule: preserve verified UI behavior where economical, remove account/server administration surfaces, and replace SDK calls with typed Tauri commands. No Node/SvelteKit server runtime is part of the desktop launch path.
