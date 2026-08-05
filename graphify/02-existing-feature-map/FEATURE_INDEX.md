# Existing and target feature index

A feature is counted once at the capability-cluster level; symbols and files remain separately countable in the graph.

| Graph node | Feature | Current anchors | Tests | Decision | Phase | Target |
|---|---|---|---|---|---|---|
| `feature::gallery-timeline` | Gallery and timeline | 28 | 16 | PORT | Phase 5 | web/src/lib/components/timeline/; src-tauri/src/commands/assets.rs |
| `feature::asset-viewer` | Asset viewer | 103 | 14 | PORT | Phase 5 | web/src/lib/components/asset-viewer/; src-tauri/src/commands/assets.rs |
| `feature::metadata` | Metadata | 10 | 7 | REWRITE | Phase 11 | src-tauri/src/metadata/; src-tauri/src/assets/sidecars.rs |
| `feature::people-faces` | People and faces | 22 | 7 | REWRITE | Phase 7 | src-tauri/src/people/; src-tauri/src/groups/ |
| `feature::search-ocr` | Search and OCR | 12 | 8 | REWRITE | Phase 10 | src-tauri/src/index/search.rs; src-tauri/src/commands/search.rs |
| `feature::tags` | Tags | 9 | 4 | REWRITE | Phase 8 | src-tauri/src/tags/; src-tauri/src/commands/tags.rs |
| `feature::albums-favorites` | Albums and favorites | 24 | 13 | PORT | Phase 5 | src-tauri/src/albums/; src-tauri/src/commands/albums.rs |
| `feature::memories` | Memories | 8 | 5 | PORT | Phase 5 | src-tauri/src/commands/memories.rs; src-tauri/src/index/memories.rs |
| `feature::map-location` | Map and location | 9 | 1 | REWRITE | Phase 5 | src-tauri/src/maps/; src-tauri/src/commands/maps.rs |
| `feature::duplicates` | Duplicates | 9 | 3 | REWRITE | Phase 10 | src-tauri/src/duplicates/; src-tauri/src/commands/duplicates.rs |
| `feature::editing` | Editing | 7 | 4 | REWRITE | Phase 11 | src-tauri/src/assets/edits.rs; src-tauri/src/commands/editing.rs |
| `feature::libraries-storage` | Libraries and storage | 16 | 6 | REWRITE | Phase 4 | src-tauri/src/library/; src-tauri/src/commands/library.rs |
| `feature::jobs-notifications` | Jobs and notifications | 16 | 6 | REPLACE | Phase 10 | src-tauri/src/jobs/; src-tauri/src/commands/jobs.rs |
| `feature::auth-users` | Authentication and users | 37 | 17 | REMOVE | Phase 3 | src-tauri/src/settings/local_operator.rs; web/src/routes/+layout.svelte |
| `feature::sharing-mobile-backup` | Sharing and mobile backup | 677 | 7 | REMOVE | Phase 15 | src-tauri/src/backup/; src-tauri/src/commands/export.rs |
| `feature::administration` | Administration | 73 | 9 | REMOVE | Phase 15 | web/src/routes/settings/; src-tauri/src/settings/ |
| `feature::settings` | Settings | 26 | 5 | REWRITE | Phase 4 | src-tauri/src/settings/; src-tauri/src/commands/settings.rs |
| `feature::local-ai-worker` | Local AI worker | 27 | 0 | TEMPORARILY RETAIN | Phase 10 | ai-worker/; src-tauri/src/ai/ |
| `feature::events-organization` | Events and organization | 2 | 1 | REWRITE | Phase 6 | src-tauri/src/events/; src-tauri/src/assets/move_asset.rs |
| `feature::review-centre` | Review Centre | 3 | 0 | REWRITE | Phase 5 | src-tauri/src/review/; src-tauri/src/commands/review.rs |
| `feature::desktop-shell` | Desktop shell | 12 | 1 | REWRITE | Phase 3 | src-tauri/Cargo.toml; src-tauri/tauri.conf.json |
| `feature::data-authority` | Local data authority | 190 | 0 | REWRITE | Phase 4 | src-tauri/src/schema/; src-tauri/src/index/ |
| `feature::legal-rebranding` | Legal and rebranding | 49 | 1 | KEEP UNCHANGED | Phase 2 | package.json; web/src/app.html |
| `feature::planning-governance` | Planning and verification governance | 0 | 0 | KEEP UNCHANGED | Phase 1 | Graphify/ |

Feature clusters: **24**. Every cluster has current evidence or a confirmed-absence/target mapping.
