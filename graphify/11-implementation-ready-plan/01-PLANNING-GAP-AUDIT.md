# Planning gap audit

## Executive finding

The original Graphify package is exceptionally strong as a repository inventory and requirement-evidence map, but its statement `PLANNING COMPLETE — READY FOR IMPLEMENTATION` was premature. The validator checked graph structure, file coverage, required document presence, and non-mutation. It did not validate semantic correctness of every execution assignment or the existence of complete implementation contracts.

## Confirmed defects repaired by this addendum

1. **Phase-assignment corruption.** The generated execution matrix assigned Phase 9 Mind Map requirements to Phases 4/5/7, Phase 12 external-drive work mainly to Phase 4, Phase 14 work to unrelated phases, and Phase 16 cleanup across unrelated phases. The addendum creates a deterministic execution overlay and keeps original evidence fields intact.
2. **No exact command contract.** Command families existed, but request/response DTOs, errors, progress events, pagination, cancellation, idempotency, and compatibility rules did not.
3. **No implementable schema set.** The plan named sidecar concepts but did not provide exact JSON Schema documents or an exact SQLite DDL/index contract.
4. **No complete UX route matrix.** Retained screens were named but routes, empty/error/offline/read-only states, and command dependencies were not fully locked.
5. **No threat model.** Security statements existed, but assets, trust boundaries, threats, mitigations, and verification cases were not organized into a release gate.
6. **No fixed release slices.** Seventeen phases existed, but there was no user-usable release ladder, dependency-critical path, or phase-by-phase atomic backlog.
7. **Performance gate missing.** The Master Plan required Phase 1 budgets, but only measurement categories were provided. This addendum supplies versioned initial budgets and reference hardware classes.
8. **Baseline not executed.** Existing builds/tests remain discovered-but-not-executed. The plan now treats this as an implementation Entry Gate, not a passing baseline.
9. **Risk register too shallow.** Ten broad rows did not meet the Master Plan requirement for trigger, impact, prevention, detection, recovery, test, owner, and status. The expanded register supplies these fields.
10. **No upstream/fork policy.** The snapshot has no Git metadata and mixed package versions (`2.7.5` and `3.0.0`). The plan now requires provenance, repository initialization, immutable baseline tag, and selective upstream adoption rules before code changes.
11. **No exact release/CI strategy.** Clean builds, test layers, artifact signing, reproducibility, dependency scanning, schema compatibility, and absence scans were not placed into one executable pipeline.
12. **No explicit change-control rule for planning detail.** Exact implementation decisions are now ADR-locked and may change only with equivalent proof and updated traceability.

## What remains intentionally unproved until implementation

- The legacy snapshot builds and tests successfully on the target toolchain.
- Chosen Rust crates, model files, codecs, and packaging binaries pass legal and clean-machine checks.
- Performance budgets are achievable.
- Every retained Immich UI component can be reused economically after server coupling is removed.
- The selected Python-worker packaging method behaves consistently on all target operating systems.

These are not planning gaps anymore: each is an explicit Entry/Exit Gate with an owner, artifact, and failure path.
