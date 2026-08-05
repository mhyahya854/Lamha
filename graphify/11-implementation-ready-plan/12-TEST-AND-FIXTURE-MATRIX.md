# Test strategy and fixture matrix

## Test layers

1. Rust unit/property tests for schemas, IDs, paths, authority, state machines, and transactions.
2. SQLite migration/rebuild tests against golden databases and authoritative-record fixtures.
3. Worker protocol/model-adapter tests with real small models plus deterministic fake adapters used only in tests.
4. Tauri command integration tests with temporary roots and real filesystem operations.
5. Svelte component tests with typed command fakes and contract fixtures.
6. Desktop end-to-end tests against packaged/dev Tauri builds and real local fixtures.
7. Cross-platform clean-machine, failure-injection, performance, security, and absence tests.

## Required fixture libraries

| Fixture | Contents |
|---|---|
| `tiny-clean` | JPEG, PNG, WebP, GIF, MP4/MOV, dates, GPS, orientation, Unicode names. |
| `companions` | Live Photo pairs, Motion Photo, RAW+JPEG, missing member, duplicate filenames. |
| `metadata-conflicts` | EXIF/XMP/JSON disagreements, future schema, unknown fields, corrupt/truncated files. |
| `events` | Unknown dates, midnight-spanning event, merge/link/split, nested folders, collisions. |
| `people-relationships` | Face corrections, merged/split people, nested groups, temporal membership, multi-edge relationships. |
| `external-drive` | Stable/changed drive identity, offline roots, read-only, reconnect, external rename/move. |
| `transactions` | Prepared/staged/committing journals, partial copies, hash mismatch, disk-full simulations. |
| `privacy` | Rich EXIF/IPTC/XMP/QuickTime metadata with expected clean-export golden files. |
| `malformed-media` | Truncated/hostile files within legal redistribution constraints. |
| `scale-10k/50k/100k` | Generated metadata and thumbnails plus representative real-media subset. |

## Phase gate rule

A work item is complete only when focused tests pass, affected retained legacy scenarios are represented, applicable security/data-safety tests pass, and the requirement tracker names the exact test. “Build passes” alone is never completion.

## Baseline Entry Gate

Before Phase 2, run the legacy snapshot in a disposable copy with outputs outside the immutable baseline. Record all build/test commands, toolchain versions, failures, missing submodule assets, and package-version mismatch. A failing legacy test does not block Lamha forever, but it must be classified as pre-existing, repaired, replaced by an equivalent Lamha proof, or formally retired with rationale.
