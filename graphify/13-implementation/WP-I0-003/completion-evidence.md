# WP-I0-003 completion evidence

- Package: WP-I0-003 — Existing repository SHA-256 manifest
- Collection ran: 2026-08-08T14:42:09+00:00 → 2026-08-08T14:42:37+00:00
- Manifest entries computed: **3697** (path, byte size, SHA-256), all re-hashed and verified: **3697/3697 entries verify**.
- Outside-Graphify additions/removals/modifications/renames: **zero** (SHA-256 baseline and Git-blob baseline comparisons).
- This package created **no** archive, backup, repository copy/duplicate tree, application mutation, or Git mutation — the manifest records path/size/digest facts only.
- All generated evidence resolves inside `graphify/13-implementation/WP-I0-003/` and was written through `graphify/tools/write_guard.py`.

## Requirements

- `CAN-MISSION-I0-003`: the SHA-256 manifest for existing repository files was calculated (`sha256-manifest.csv`, 3697 entries) and verified (`verification-report.json`: every entry re-hashed with path/size/digest equality; two independent passes byte-identical) without creating an archive, backup, or duplicate repository tree.

## Exit gate

- **PASS** — Every manifest entry verifies: All 3697 manifest entries were re-hashed from the current working tree and verified for path existence, byte size, and SHA-256 digest equality with zero failures; two independent hashing passes produced byte-identical manifests; both planning baselines report zero added/removed/modified/renamed paths.
- **PASS** — No archive, backup, copy, or repository mutation exists: Zero paths were added outside Graphify relative to both planning baselines; this package's evidence files match no archive/backup/copy/build/test/cache/package-manager/generated-code pattern (a manifest records path/size/digest facts and never copies file contents); Git metadata is unchanged across the run; every Git command is read-only under the static allowlist with GIT_OPTIONAL_LOCKS=0.
