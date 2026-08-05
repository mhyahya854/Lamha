# Port

| Capability | Reason/scope | Phase | Target |
|---|---|---|---|
| Gallery and timeline | Virtualized chronological browsing, selection, filters, and local-first asset loading. | Phase 5 | web/src/lib/components/timeline/; src-tauri/src/commands/assets.rs; src-tauri/src/index/ |
| Asset viewer | Photo/video viewing, detail panels, navigation, media playback, and retained viewer actions. | Phase 5 | web/src/lib/components/asset-viewer/; src-tauri/src/commands/assets.rs; src-tauri/src/assets/ |
| Albums and favorites | Virtual albums, membership, covers, favorites, and local asset collections. | Phase 5 | src-tauri/src/albums/; src-tauri/src/commands/albums.rs; web/src/lib/components/album-page/ |
| Memories | Date-based memory presentation backed by local asset queries. | Phase 5 | src-tauri/src/commands/memories.rs; src-tauri/src/index/memories.rs; web/src/routes/(user)/memory/ |

Implementation has not started; this is the approved planning disposition.
