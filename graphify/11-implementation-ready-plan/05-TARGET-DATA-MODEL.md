# Target data model and authority contract

## Stable identities

All domain objects use lowercase UUID strings. Paths, names, dates, hashes, face embeddings, and model scores are mutable attributes, never identity. Timestamps are RFC 3339 UTC plus optional original timezone/offset evidence.

## Authoritative records

| Record | Location | Authority |
|---|---|---|
| Asset | Adjacent `media.ext.asset.json` | Identity, current path, original filename, hashes, approved metadata, links, attribution, AI task state references. |
| Event | Event folder `event.json` with compatible `event.xmp` mirror | Event identity, name/date, folder state, attendees, asset membership. |
| Person, group, relationship | Root `.app-data/domain/` | Stable knowledge graph, aliases, temporal membership, multi-edge history. |
| Tag, album, saved view | Root `.app-data/domain/` | User-defined and approved virtual organization. |
| Folder-map draft | Root `.app-data/maps/` | Global graph and scoped view state; draft operations. |
| Review history | Root `.app-data/review/` | Candidate identity, provenance, decisions, suppression, reconsideration. |
| Operation journal/history | OS app-data + affected-root mirrors | Crash recovery, commit state, rollback and ambiguity evidence. |
| Settings/root registry | OS app-data | Device-specific paths, capabilities, appearance, AI limits; never copied into media roots unless exported. |
| SQLite | OS app-data `lamha-index.sqlite3` | Derived search/index/cache/working state only. |

## Required common fields

Every authoritative record includes `schemaVersion`, `id`, `createdAt`, `updatedAt`, and `revision`. Mutating writes use optimistic revision checks. Unknown fields are preserved. A future schema version is read-only and copied byte-for-byte during backup/export.

## Conflict order

1. Explicit user-approved record value.
2. Newer explicit Lamha record revision with valid history.
3. Compatible XMP mirror for fields whose direction is declared bidirectional.
4. Embedded EXIF/IPTC/QuickTime evidence.
5. Filesystem facts such as actual path, size, and modification time.
6. AI or heuristic candidate, which has no authority until approved.

Conflicts are preserved as Review items; the application never overwrites a higher-authority value silently.

## Schema files

The exact initial contracts are under `schemas/`. They are planning baselines and must be implemented with generated/handwritten Rust validation tests before the first writer is enabled. Any field change requires a schema version, migration fixture, unknown-field preservation test, and updated IPC DTO.
