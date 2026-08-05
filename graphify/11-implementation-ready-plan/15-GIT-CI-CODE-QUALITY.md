# Git, CI, code quality, and release workflow

## Repository bootstrap

1. Initialize Git around the exact received snapshot.
2. Commit without modification as `immich-snapshot-import` and tag `baseline/received-archive` with hash manifest.
3. Commit Graphify evidence and this planning addendum separately.
4. Record the absence of original Git history and the package-version mismatch in `PROVENANCE.md`.
5. Never rewrite baseline tags.

## Branch and commit policy

Use short-lived phase/work-package branches. Commit one coherent, tested change with requirement IDs in the message. No phase-long mega-commit. Merge only after the work-item gate passes and Graphify/traceability updates accompany code.

## Required CI jobs

- Formatting, lint, type checking, Rust clippy, tests, schema validation, SQL migration checks.
- Static-client build and forbidden server/HTTP dependency scan.
- Rust/Tauri command contract and TypeScript DTO drift check.
- Worker protocol tests and no-listener scan.
- Unit/integration/E2E matrix on Windows, macOS, Linux.
- Dependency vulnerability, licence, secret, and SBOM generation.
- Package build, signature/notarization checks where credentials are available, and clean-machine smoke tests.
- Data-safety failure-injection suite on protected disposable fixtures.
- Final obsolete-stack and outbound-network absence scan.

## Review rules

Data authority, transaction, schema/migration, security capability, deletion, AI authority, and legal changes require an independent review pass. Generated code is never accepted without reading the generator contract and checking produced diffs.

## Release artifacts

Binaries/installers, source archive, SBOM, third-party notices, model/component manifest, checksums, signed release manifest, migration compatibility report, test summary, known limitations, and rollback instructions.
