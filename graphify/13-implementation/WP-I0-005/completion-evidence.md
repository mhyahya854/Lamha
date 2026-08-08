# WP-I0-005 completion evidence

- Package: WP-I0-005 — Toolchain inventory
- Collection: 2026-08-08T23:28:23+00:00 → 2026-08-08T23:28:32+00:00
- `CAN-MISSION-I0-006`: 189 available manifest paths, 73 unavailable referenced manifest paths, 744 version declarations, and 42 host probes across all six required categories.
- Unavailable/ambiguous records: 236, each explicitly `REVIEW_REQUIRED`.
- Preservation: manifest fingerprint `54974a809e9b641dcfa12c692617232c7b9d82b3926d46f1d321e715f5c39377` unchanged; outside-Graphify Git status clean before/after; no forbidden command or artifact.
- Contracts/commands/schemas/SQLite/UI: none owned; authoritative contract review records zero IPC commands and zero missing references.

## Exit gate

- **PASS** — Every discoverable toolchain manifest path and version is recorded in the six required categories: Recorded 189 available manifest files and 744 version declarations; a separately derived 189-path oracle plus source-derived reference resolution recorded 73 unavailable mandatory manifests as REVIEW_REQUIRED; supplemental 31-path/78-declaration fixtures have zero omissions.
- **PASS** — Every unavailable or ambiguous version is explicitly REVIEW_REQUIRED: Derived 11 current repository ambiguities, probed 42 baseline/repository-declared tools, recorded 2 unmapped declared tools and 73 unavailable referenced manifests, removed 23 superseded predecessor rows, classified all 12 floating/dynamic compose-image cases as references, and produced 236 explicit REVIEW_REQUIRED entries with zero unreported unavailable items.
- **PASS** — Inspection is local-only, typed on failure, and preserves authoritative state: All 5 negative fixtures rejected; measured manifest fingerprint and outside-Graphify Git state were identical pre/post; no network/install/build/product-test command ran.
