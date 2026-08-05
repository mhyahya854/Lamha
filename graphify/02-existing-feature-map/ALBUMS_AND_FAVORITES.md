# Albums and favorites

Virtual albums, membership, covers, favorites, and local asset collections.

## Current verified evidence

| Current path/line | Symbol | Evidence | Graph node | Action |
|---|---|---|---|---|
| `Codebase/web/src/routes/(user)/albums/+page.ts:L1-L1` | `albums/+page.ts` | EXTRACTED | `ext_codebase_web_src_routes_user_albums_page_ts` | PORT |
| `Codebase/web/src/routes/(user)/albums/+page.svelte:L1-L1` | `albums/+page.svelte` | EXTRACTED | `ext_codebase_web_src_routes_user_albums_page_svelte` | PORT |
| `Codebase/web/src/lib/components/album-page/AlbumMap.svelte:L1-L1` | `lib/components/album-page/AlbumMap.svelte` | EXTRACTED | `ext_codebase_web_src_lib_components_album_page_albummap_svelte` | PORT |
| `Codebase/web/src/lib/components/album-page/AlbumCard.svelte:L1-L1` | `lib/components/album-page/AlbumCard.svelte` | EXTRACTED | `ext_codebase_web_src_lib_components_album_page_albumcard_svelte` | PORT |
| `Codebase/web/src/routes/(user)/albums/AlbumsControls.svelte:L1-L1` | `AlbumsControls.svelte` | EXTRACTED | `ext_codebase_web_src_routes_user_albums_albumscontrols_svelte` | PORT |
| `Codebase/web/src/lib/components/album-page/AlbumCover.svelte:L1-L1` | `lib/components/album-page/AlbumCover.svelte` | EXTRACTED | `ext_codebase_web_src_lib_components_album_page_albumcover_svelte` | PORT |
| `Codebase/web/src/lib/components/album-page/AlbumsList.svelte:L1-L1` | `lib/components/album-page/AlbumsList.svelte` | EXTRACTED | `ext_codebase_web_src_lib_components_album_page_albumslist_svelte` | PORT |
| `Codebase/web/src/lib/components/album-page/AlbumViewer.svelte:L1-L1` | `lib/components/album-page/AlbumViewer.svelte` | EXTRACTED | `ext_codebase_web_src_lib_components_album_page_albumviewer_svelte` | PORT |
| `Codebase/web/src/lib/components/album-page/AlbumsTable.svelte:L1-L1` | `lib/components/album-page/AlbumsTable.svelte` | EXTRACTED | `ext_codebase_web_src_lib_components_album_page_albumstable_svelte` | PORT |
| `Codebase/web/src/lib/components/album-page/AlbumSummary.svelte:L1-L1` | `./AlbumSummary.svelte` | EXTRACTED | `ext_codebase_web_src_lib_components_album_page_albumsummary_svelte` | PORT |

## Current dependency boundary

- Complete pattern-matched production file set: **24**.
- Complete pattern-matched existing test file set: **13**.
- The table shows ten navigation anchors; all matched files and their calls/imports remain in the directed graph and symbol ledger. Deletion-critical edges require source verification and do not rely on inference alone.

## Target decision

- Classification: **PORT**.
- Assigned implementation phase: **Phase 5 — Asset API replacement**.
- Target modules: `src-tauri/src/albums/`, `src-tauri/src/commands/albums.rs`, `web/src/lib/components/album-page/`.
- Proof: focused behavior tests, affected regression tests, desktop build/launch when applicable, and requirement-linked evidence before any current subsystem is removed.
