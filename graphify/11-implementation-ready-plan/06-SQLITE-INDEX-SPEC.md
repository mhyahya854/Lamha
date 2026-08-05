# SQLite index specification

## Database contract

- File: `lamha-index.sqlite3` in per-user OS application-data.
- Open with foreign keys enabled for every connection, busy timeout, integrity checks, and WAL on local writable storage.
- SQLite is disposable. A user may close Lamha, delete the database, reopen, and deterministically rebuild from roots and authoritative records.
- Database corruption causes quarantine to a timestamped copy, a Review item, and rebuild; never silent replacement.

## Required tables

| Table | Key columns | Purpose |
|---|---|---|
| `schema_migrations` | `id`, `applied_at`, `checksum` | Monotonic migration ledger. |
| `library_root` | `root_id`, canonical path, drive identity, access mode, last seen | Device/root registry cache. |
| `asset_index` | `asset_id`, root/path, media kind, size, hashes, capture time, event ID, status | Main rebuildable asset index. |
| `asset_companion` | two asset IDs, relation type | Live Photo/RAW+JPEG/other companion links. |
| `event_index` | event ID, folder path, dates, materialization state | Fast event browsing. |
| `person_index` / `face_index` | IDs, display fields, asset/region references | People and face lookup. |
| `group_index` / `group_membership_index` | IDs, parent, effective interval | Nested/temporal groups. |
| `relationship_index` | edge ID, endpoints, type, effective interval, certainty | Multi-edge graph queries. |
| `tag_index` / `asset_tag_index` | IDs, namespace, assignment state | Tag and provenance lookup. |
| `album_index` / `album_asset_index` | IDs and memberships | Virtual albums. |
| `review_queue` | review ID, kind, state, fingerprints, priority | Working queue; history also exists in JSON. |
| `job_state` | task ID, asset ID, task kind, state, fingerprints, progress | Restartable AI/background work. |
| `ocr_index` | asset ID, text, language, regions | OCR query source. |
| `search_document` | asset ID, normalized fields | Structured/FTS search. |
| `embedding_index` | asset ID, model ID/version, vector reference | Semantic lookup; vectors may live in versioned cache files. |
| `thumbnail_index` | asset ID, variant, cache path, fingerprint | Rebuildable derivatives. |
| `operation_index` | operation ID, state, timestamps | Fast diagnostics over authoritative journals. |
| `map_node_index` / `map_edge_index` | IDs, graph/scope/state | Mind-map rendering and queries. |

## Index rules

- Unique `(root_id, normalized_path)` and stable `asset_id` constraints.
- Partial indexes for active jobs, pending review, offline roots, and unresolved conflicts.
- FTS table for user-visible text/OCR; semantic vectors are model-version scoped.
- Every derived row stores a source revision/fingerprint so stale rows are detectable.
- No cascade may delete an authoritative domain decision; cascades are limited to rebuildable children.

## Migration and rebuild

Migrations run in a transaction after a backup copy and checksum validation. Unsupported downgrade refuses to open for write. Rebuild scans roots, validates sidecars, reconstructs domain records, then regenerates indexes and caches in resumable batches. Rebuild progress is cancellable and restartable.
