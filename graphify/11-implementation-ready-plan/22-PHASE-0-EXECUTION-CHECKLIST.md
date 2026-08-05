# Phase 0 execution checklist

## Immutable provenance

- [ ] Confirm `/Codebase` file count and SHA-256 manifest against the received archive.
- [ ] Initialize Git at the Lamha root without formatting, generating, or installing anything.
- [ ] Commit the exact received snapshot and tag `baseline/received-archive`.
- [ ] Commit Graphify planning as a separate commit and tag `planning/implementation-ready-v1`.
- [ ] Record archive hash, OS, filesystem, timestamps, and absence of original `.git` history.
- [ ] Record root/web/ML `2.7.5` versus server/mobile `3.0.0` manifest mismatch.
- [ ] Record the declared but empty `e2e/test-assets` submodule path.

## Disposable baseline execution

- [ ] Create a second disposable working copy or container; never install/build inside the immutable baseline tree.
- [ ] Install the toolchains pinned by `.nvmrc`, `mise.toml`, lockfiles, Python project, and Flutter configuration.
- [ ] Restore the missing test-assets source if provenance can be verified; otherwise mark affected tests `UNAVAILABLE — MISSING SNAPSHOT INPUT`.
- [ ] Run web format/lint/Svelte/TypeScript checks, unit tests, and build.
- [ ] Run server build/check/unit/medium tests where dependencies are available.
- [ ] Run ML lint/type/test with the supported Python version and lockfile.
- [ ] Run mobile analyze/test only as retained-parity evidence; mobile is not a Lamha target.
- [ ] Run E2E tests only in an isolated environment with all writes outside the baseline.
- [ ] Save exact commands, versions, stdout/stderr, exit codes, durations, and produced artifacts.

## Cutover inventory

- [ ] Confirm static-adapter configuration and fallback route behaviour.
- [ ] Inventory every web import/use of `@immich/sdk`, Socket.IO, auth/session stores, server configuration, upload/share/admin routes, and external URL.
- [ ] Create a route-by-route cutover ledger mapping each retained screen to Tauri commands and each removed screen to its safe deletion phase.
- [ ] Identify closest upstream provenance for mixed snapshot components without altering the baseline.

## Exit gate

Phase 0 is green only when rollback is immutable, baseline execution is classified, unresolved provenance is explicit, and Phase 2/3 work can be performed in version control without losing the received state.
