# SQLite index map

Phase 1 now selects exact target names; the Master Plans correctly avoid locking them before this mapping.

| Concept | Selected Phase 1 name/design | Rule |
|---|---|---|
| Filename | `lamha-index.sqlite3` in the OS application-data directory | Selected after confirming no current desktop DB or naming constraint |
| Schema/versioning | `schema_migrations` with monotonic integer migration IDs | Implementation framework may use Rust migration tooling; destructive downgrade is forbidden |
| Asset index | `asset_index` keyed by stable asset UUID and normalized path/hash fields | Derived from filesystem + authoritative records |
| Search/OCR/embedding | `search_index`, `ocr_index`, `embedding_index` | Derived/rebuildable; vectors may be external cache files referenced by UUID |
| Faces/review/jobs | `face_index`, `review_queue`, `job_state` | Working/derived state; approved decisions/history also persist in JSON |
| Integrity | foreign keys, uniqueness, checks, WAL, transactional migrations | Corruption triggers quarantine/backup and rebuild; never silent data loss |

SQLite is never the sole authority for approved metadata, saved user decisions, operation history, suppression/rejection history, or unresolved overlays. Deleting the database on a test copy must permit deterministic rebuild.
