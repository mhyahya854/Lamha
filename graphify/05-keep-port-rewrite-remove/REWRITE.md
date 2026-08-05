# Rewrite

| Capability | Reason/scope | Phase | Target |
|---|---|---|---|
| Metadata | Metadata inspection, authority, EXIF/XMP handling, privacy, and reversible mutation. | Phase 11 | src-tauri/src/metadata/; src-tauri/src/assets/sidecars.rs; src-tauri/src/commands/metadata.rs |
| People and faces | Face detection/recognition, identity curation, people views, grouping, merge/split, and history. | Phase 7 | src-tauri/src/people/; src-tauri/src/groups/; src-tauri/src/relationships/; ai-worker/faces/ |
| Search and OCR | Text/semantic search, filters, OCR extraction, and local result ranking. | Phase 10 | src-tauri/src/index/search.rs; src-tauri/src/commands/search.rs; ai-worker/search/; ai-worker/ocr/ |
| Tags | Tag browsing and assignment with review-first local authority and provenance. | Phase 8 | src-tauri/src/tags/; src-tauri/src/commands/tags.rs; web/src/lib/components/tags/ |
| Map and location | Offline-capable coordinate browsing and reviewed local location metadata. | Phase 5 | src-tauri/src/maps/; src-tauri/src/commands/maps.rs; web/src/lib/components/map/ |
| Duplicates | Exact/similar duplicate candidates and user-reviewed burst grouping. | Phase 10 | src-tauri/src/duplicates/; src-tauri/src/commands/duplicates.rs; ai-worker/duplicates/ |
| Editing | Non-destructive edits, derivatives, exports, snapshots, privacy transforms, and restore. | Phase 11 | src-tauri/src/assets/edits.rs; src-tauri/src/commands/editing.rs; web/src/lib/components/editing/ |
| Libraries and storage | Library roots, scanning, storage, watchers, linked folders, external drives, and path sandboxing. | Phase 4 | src-tauri/src/library/; src-tauri/src/commands/library.rs; src-tauri/src/transactions/ |
| Settings | System/user preferences that survive as local desktop, library, AI, privacy, and appearance settings. | Phase 4 | src-tauri/src/settings/; src-tauri/src/commands/settings.rs; web/src/routes/(user)/user-settings/ |
| Events and organization | Manage Later, event folders, merge/link/split, normalized naming, and reversible organization. | Phase 6 | src-tauri/src/events/; src-tauri/src/assets/move_asset.rs; src-tauri/src/commands/events.rs |
| Review Centre | Unified review queues for conflicts, AI candidates, external changes, and approved/rejected history. | Phase 5 | src-tauri/src/review/; src-tauri/src/commands/review.rs; web/src/routes/(user)/review/ |
| Desktop shell | Tauri 2 desktop process, static Svelte client, local commands, permissions, and packaging. | Phase 3 | src-tauri/Cargo.toml; src-tauri/tauri.conf.json; src-tauri/src/app.rs; src-tauri/capabilities/default.json |
| Local data authority | Versioned sidecars, embedded SQLite derived index, operation history, overlays, and rebuild. | Phase 4 | src-tauri/src/schema/; src-tauri/src/index/; src-tauri/src/transactions/; src-tauri/src/trash/ |

Implementation has not started; this is the approved planning disposition.
