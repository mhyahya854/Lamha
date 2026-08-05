# Tauri command map

Command families are semantic contracts; final Rust function identifiers may follow implementation conventions while preserving these stable mapped operations.

| Contract family | Consumer | Target file | Authority | Phase |
|---|---|---|---|---|
| assets.list/get | gallery/viewer | src-tauri/src/commands/assets.rs | read-only index/filesystem DTO | 5 |
| library.scan/watch/roots | library settings | src-tauri/src/commands/library.rs | authorized paths + scanner/watcher | 4 |
| events.create/merge/link/split | event organizer | src-tauri/src/commands/events.rs | validated reversible transaction | 6 |
| metadata.inspect/update/privacy | detail/editor | src-tauri/src/commands/metadata.rs | domain authority + XMP mirror | 11 |
| people/groups/relationships | people/maps | src-tauri/src/commands/people.rs | stable IDs/effective-dated edges | 7 |
| tags.review/approve | tags/review | src-tauri/src/commands/tags.rs | candidate → approved record | 8 |
| search.query/ocr | search | src-tauri/src/commands/search.rs | SQLite + worker tasks | 10 |
| transactions.simulate/commit/recover | mind maps/operations | src-tauri/src/commands/transactions.rs | durable manifest coordinator | 4 |
| review.list/approve/reject/reopen | Review Centre | src-tauri/src/commands/review.rs | history/provenance-preserving state | 5 |
| backup/trash/restore/rebuild | maintenance | src-tauri/src/commands/maintenance.rs | complete bundle + verified rebuild | 13 |
