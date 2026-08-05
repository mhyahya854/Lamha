# Filesystem transaction and recovery specification

## Transaction states

`PLANNED → PREPARED → STAGING → READY_TO_COMMIT → COMMITTING → COMMITTED → CLEANED`

Failure branches: `CANCELLED`, `ROLLED_BACK`, `RECOVERY_REQUIRED`, `CONFLICT`, `FAILED_SAFE`. No state transition erases prior history.

## Required journal fields

Operation UUID, schema version, operation kind, created/updated time, initiating app version, source and target roots, expected asset/record revisions, ordered steps, preconditions, estimated bytes, backups, hashes, current state, completed steps, rollback steps, warnings, errors, and recovery decision.

## Protocol

1. **Plan:** Resolve stable IDs, canonical paths, companions and sidecars; compute exact operations and user-visible consequences.
2. **Validate:** Authorized roots, path containment, symlink/junction/reparse safety, collisions, read-only/offline state, free space, expected revisions, and format constraints.
3. **Persist intent:** Write and fsync coordinator journal in OS app-data and mirrors on every affected writable root.
4. **Stage:** Create target-side temporary files/directories; copy or write; preserve source; hash and validate.
5. **Commit:** Atomic rename on the same filesystem. For cross-filesystem moves, verify complete target bundles before source removal. Commit authoritative records and fsync parent directories.
6. **Finalize:** Mark all journals committed, update the derived index, then clean temporary data and eligible source copies.
7. **Recover:** At startup, reconcile journals by UUID and on-disk evidence. Ambiguity preserves both copies and creates a Review item.

## Concurrency and locking

- Per-asset and per-event logical locks prevent overlapping structural operations.
- A root-scoped mutation lease prevents two Lamha instances from mutating the same root.
- Read-only browsing may continue during safe stages; UI shows affected items as in-operation.
- All operations are idempotent by operation UUID and step ID.

## Mandatory failure injection

Process kill at every state, disk full during copy and sidecar replacement, unplugged external drive, permission loss, destination collision, hash mismatch, corrupted journal, stale lock, duplicate startup recovery, read-only filesystem, Unicode/reserved names, symlink/junction escape, and companion member missing.
