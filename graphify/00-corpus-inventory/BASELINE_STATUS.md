# Baseline status

Captured at `2026-07-29T01:49:07.3363573+03:00`, before this run's Master Plan repair, repository mapping, Graphify execution, or Ponytail audit.

## Resolved roots

- Project root: `C:\Users\mhyah\Downloads\Code\Lamha`
- Codebase root: `C:\Users\mhyah\Downloads\Code\Lamha\Codebase`
- Planning and evidence root: `C:\Users\mhyah\Downloads\Code\Lamha\graphify`

## Git state

- Project Git root: unavailable; the project root is not a Git worktree.
- Codebase Git root: unavailable; `Codebase/` is an unpacked source snapshot without `.git` metadata.
- Branch: unavailable.
- `git status --short`: unavailable because no Git worktree exists.
- Staged, modified, untracked, and ignored classifications: unavailable because no Git index or repository metadata exists. No file is assumed clean merely because Git cannot classify it.
- Submodule status: unavailable through Git. The source snapshot contains `.gitmodules` declaring `e2e/test-assets` from `https://github.com/immich-app/test-assets`; the path is treated as ordinary snapshot content because repository metadata is absent.

## Filesystem links

- Recursive reparse-point scan of the project root found no symbolic links, junctions, or other reparse points.
- Machine-readable scan result: `Graphify/00-corpus-inventory/REPARSE_POINTS_BASELINE.csv` (zero records).

## Immutable content baseline

- Baseline file count: **3,697** regular files under `Codebase/`.
- Baseline byte count: **117,435,356** bytes.
- Per-file evidence: `Graphify/00-corpus-inventory/CODEBASE_SHA256_BASELINE.csv` (the on-disk directory is named `graphify`; Windows path matching is case-insensitive).
- Manifest columns: repository-relative path, byte length, and SHA-256 content digest.
- Baseline manifest SHA-256: `1859D2B7A946CD1D5EF2193CF5D322F933C853CF09DBD212A8390163AA1F4D88`.
- End-of-run proof method: generate a separate final manifest from `Codebase/`, compare path/length/SHA-256 tuples against the baseline, and retain both the comparison and final manifest under `Graphify/00-corpus-inventory/`.

## Safety conclusions

- Existing snapshot content is user-owned and must not be reset, cleaned, stashed, overwritten, renamed, or deleted.
- No command that may generate build, test, cache, package, migration, formatting, or dependency-install output will run in `Codebase/`.
- All permitted writes in this run are limited to the three authoritative Master Plans and planning/evidence output under `Graphify/`.

## Baseline validity

- Blank relative paths: **0**.
- Duplicate relative paths: **0**.
- The first recorded path is `.devcontainer/devcontainer.json`.
- Phase 0 and end-of-run comparisons must be generated independently; prior-run comparison files are not accepted as proof for this run.

## Phase 0 integrity gate

- Independently hashed current file count: **3,697**.
- Added, removed, content-changed, or length-changed paths: **0**.
- Phase 0 manifest: `Graphify/00-corpus-inventory/CODEBASE_SHA256_PHASE0.csv`.
- Difference report: `Graphify/00-corpus-inventory/PHASE0_INTEGRITY_DIFFERENCES.csv` (header only; zero difference records).
- Phase 0 manifest SHA-256: `1859D2B7A946CD1D5EF2193CF5D322F933C853CF09DBD212A8390163AA1F4D88`, identical to the baseline manifest hash.
- Result: **PASS — CODEBASE UNCHANGED**.
