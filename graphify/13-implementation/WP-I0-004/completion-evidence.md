# WP-I0-004 completion evidence

- Package: WP-I0-004 — Mixed-version manifest investigation
- Collection ran: 2026-08-08T15:23:13+00:00 → 2026-08-08T15:23:14+00:00
- Declarations investigated: **121** across the four manifest families; comparison fixtures: **10**; mixed-version findings recorded: **5**.
- Inspected manifest files unchanged during the run: **54/54 hash-identical**; zero paths added/removed outside Graphify; Git metadata unchanged.
- This package created **no** archive, backup, repository copy/duplicate tree, application mutation, or Git mutation.
- All generated evidence resolves inside `graphify/13-implementation/WP-I0-004/` and was written through `graphify/tools/write_guard.py`.

## Requirements

- `CAN-MISSION-I0-004`: mixed-version package, lockfile, generated-client, and toolchain manifests were investigated (`mixed-version-investigation.json` records every extracted declaration with source/key/kind/value) and mixed-version findings were recorded verbatim: node-runtime-alignment; python-toolchain-alignment; flutter-version-alignment; dart-sdk-constraint-diversity; mise-pin-lock-consistency. No manifest was modified.

## Exit gate

- **PASS** — All four manifest families are investigated and recorded: Captured 121 version declarations: 36 package-manifest, 22 lockfile, 5 generated-client, 58 toolchain declarations, each with source path, key, kind, and raw value in mixed-version-investigation.json.
- **PASS** — Every reviewed comparison fixture produced a typed verdict and mixed-version findings are recorded: 10 comparison fixtures executed with typed verdicts {'node-runtime-alignment': 'MIXED', 'node-engine-range-compatibility': 'ALIGNED', 'pnpm-manager-alignment': 'ALIGNED', 'python-toolchain-alignment': 'MIXED', 'flutter-version-alignment': 'MIXED', 'dart-sdk-constraint-diversity': 'MIXED', 'workspace-package-version-diversity': 'RECORD_ONLY', 'generated-client-version-record': 'RECORD_ONLY', 'lockfile-tool-version-record': 'RECORD_ONLY', 'mise-pin-lock-consistency': 'MIXED'}; mixed-version findings recorded with the exact conflicting declarations: ['node-runtime-alignment', 'python-toolchain-alignment', 'flutter-version-alignment', 'dart-sdk-constraint-diversity', 'mise-pin-lock-consistency'].
- **PASS** — Failures are typed and no unrelated authoritative state changed: 4 invalid-input probes returned typed errors with no partial commit; write-guard escape probes rejected; all 54 inspected manifest files hash-identical before/after; Git metadata unchanged; zero paths added/removed outside Graphify; every Git command read-only with GIT_OPTIONAL_LOCKS=0.
