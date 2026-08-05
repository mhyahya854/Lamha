# Immich snapshot and upstream strategy

## Provenance problem

The received source is a non-Git snapshot. Root/web/ML manifests report `2.7.5`, while server/mobile report `3.0.0` variants. Therefore no implementation may assume a clean official release boundary or rely on unavailable commit history.

## Required Phase 0 actions

- Hash and preserve the received archive.
- Identify the closest upstream release/commit for each major manifest using file comparison in a separate research workspace.
- Record local modifications or mixed-version files without replacing the received baseline.
- Populate the empty declared `e2e/test-assets` submodule path or mark affected tests unavailable with provenance.
- Run licence/provenance checks before distributing Lamha.

## Ongoing upstream policy

Before the desktop cutover, selectively study upstream bug/security fixes. After Phase 4 establishes Lamha authority, do not merge upstream wholesale. Cherry-pick or manually port only changes that affect retained UI/media parsing/security behaviour, with requirement mapping and regression tests. Server/mobile/multi-user features are reference evidence, not a continuing architectural base.

## End state

Lamha owns its architecture, schemas, commands, tests, and release process. Immich-derived code remains attributed, but final source should not carry ceremonial dead subsystems merely to ease hypothetical future merges.
