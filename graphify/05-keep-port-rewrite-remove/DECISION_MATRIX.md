# Keep/port/rewrite/replace/remove decision matrix

| Capability | Decision | Phase | Target | Basis |
|---|---|---|---|---|
| Gallery and timeline | PORT | Phase 5 | web/src/lib/components/timeline/; src-tauri/src/commands/assets.rs; src-tauri/src/index/ | Source/test/dependency mapped |
| Asset viewer | PORT | Phase 5 | web/src/lib/components/asset-viewer/; src-tauri/src/commands/assets.rs; src-tauri/src/assets/ | Source/test/dependency mapped |
| Metadata | REWRITE | Phase 11 | src-tauri/src/metadata/; src-tauri/src/assets/sidecars.rs; src-tauri/src/commands/metadata.rs | Source/test/dependency mapped |
| People and faces | REWRITE | Phase 7 | src-tauri/src/people/; src-tauri/src/groups/; src-tauri/src/relationships/; ai-worker/faces/ | Source/test/dependency mapped |
| Search and OCR | REWRITE | Phase 10 | src-tauri/src/index/search.rs; src-tauri/src/commands/search.rs; ai-worker/search/; ai-worker/ocr/ | Source/test/dependency mapped |
| Tags | REWRITE | Phase 8 | src-tauri/src/tags/; src-tauri/src/commands/tags.rs; web/src/lib/components/tags/ | Source/test/dependency mapped |
| Albums and favorites | PORT | Phase 5 | src-tauri/src/albums/; src-tauri/src/commands/albums.rs; web/src/lib/components/album-page/ | Source/test/dependency mapped |
| Memories | PORT | Phase 5 | src-tauri/src/commands/memories.rs; src-tauri/src/index/memories.rs; web/src/routes/(user)/memory/ | Source/test/dependency mapped |
| Map and location | REWRITE | Phase 5 | src-tauri/src/maps/; src-tauri/src/commands/maps.rs; web/src/lib/components/map/ | Source/test/dependency mapped |
| Duplicates | REWRITE | Phase 10 | src-tauri/src/duplicates/; src-tauri/src/commands/duplicates.rs; ai-worker/duplicates/ | Source/test/dependency mapped |
| Editing | REWRITE | Phase 11 | src-tauri/src/assets/edits.rs; src-tauri/src/commands/editing.rs; web/src/lib/components/editing/ | Source/test/dependency mapped |
| Libraries and storage | REWRITE | Phase 4 | src-tauri/src/library/; src-tauri/src/commands/library.rs; src-tauri/src/transactions/ | Source/test/dependency mapped |
| Jobs and notifications | REPLACE | Phase 10 | src-tauri/src/jobs/; src-tauri/src/commands/jobs.rs; src-tauri/src/notifications/ | Source/test/dependency mapped |
| Authentication and users | REMOVE | Phase 3 | src-tauri/src/settings/local_operator.rs; web/src/routes/+layout.svelte | Source/test/dependency mapped |
| Sharing and mobile backup | REMOVE | Phase 15 | src-tauri/src/backup/; src-tauri/src/commands/export.rs | Source/test/dependency mapped |
| Administration | REMOVE | Phase 15 | web/src/routes/settings/; src-tauri/src/settings/ | Source/test/dependency mapped |
| Settings | REWRITE | Phase 4 | src-tauri/src/settings/; src-tauri/src/commands/settings.rs; web/src/routes/(user)/user-settings/ | Source/test/dependency mapped |
| Local AI worker | TEMPORARILY RETAIN | Phase 10 | ai-worker/; src-tauri/src/ai/; src-tauri/src/commands/ai.rs | Source/test/dependency mapped |
| Events and organization | REWRITE | Phase 6 | src-tauri/src/events/; src-tauri/src/assets/move_asset.rs; src-tauri/src/commands/events.rs | Source/test/dependency mapped |
| Review Centre | REWRITE | Phase 5 | src-tauri/src/review/; src-tauri/src/commands/review.rs; web/src/routes/(user)/review/ | Source/test/dependency mapped |
| Desktop shell | REWRITE | Phase 3 | src-tauri/Cargo.toml; src-tauri/tauri.conf.json; src-tauri/src/app.rs; src-tauri/capabilities/default.json | Source/test/dependency mapped |
| Local data authority | REWRITE | Phase 4 | src-tauri/src/schema/; src-tauri/src/index/; src-tauri/src/transactions/; src-tauri/src/trash/ | Source/test/dependency mapped |
| Legal and rebranding | KEEP UNCHANGED | Phase 2 | package.json; web/src/app.html; web/src/lib/components/ServerAboutItem.svelte; THIRD_PARTY_NOTICES.md | Source/test/dependency mapped |
| Planning and verification governance | KEEP UNCHANGED | Phase 1 | Graphify/ | Source/test/dependency mapped |

Ponytail classifications are reconciled one-for-one in `PONYTAIL_RECONCILIATION.md`; they preserve retained behavior and cannot bypass removal prerequisites.
