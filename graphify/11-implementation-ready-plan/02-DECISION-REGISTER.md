# Locked architecture decision register

| ADR | Decision | Status | Change condition |
|---|---|---|---|
| ADR-001 | Lamha is a single-user, local-first desktop app; no account or server is required. | LOCKED | Product owner changes core identity. |
| ADR-002 | Tauri 2 hosts a static Svelte client; no Node/SvelteKit server process ships. | LOCKED | Equivalent desktop architecture proves smaller attack surface and full parity. |
| ADR-003 | Rust is the sole authority for filesystem, schemas, index mutation, transaction recovery, and AI supervision. | LOCKED | No downgrade of authority separation. |
| ADR-004 | Filesystem + versioned transparent records are durable authority; SQLite is rebuildable/working state. | LOCKED | Requires migration proof and explicit product approval. |
| ADR-005 | Every managed media item has a stable UUID; filename and path are attributes, never identity. | LOCKED | Never. |
| ADR-006 | Exactly one physical original media copy exists per managed asset; virtual views never duplicate media. | LOCKED | Never. |
| ADR-007 | AI is a supervised child process using framed non-network IPC; it cannot write authoritative records. | LOCKED | Equivalent mechanism passes the same security, lifecycle, streaming, cancellation, and packaging gates. |
| ADR-008 | JSON records use `schemaVersion` with SemVer; initial version is `1.0.0`; unsupported future records are preserved read-only. | LOCKED | Schema ADR with migration and backward-compatibility proof. |
| ADR-009 | SQLite file is `lamha-index.sqlite3` in OS app-data; migrations are monotonic and downgrade is unsupported. | LOCKED | Schema ADR plus rebuild proof. |
| ADR-010 | All destructive or structural filesystem actions use durable prepare/stage/commit/recover transactions. | LOCKED | Never weaken crash recovery. |
| ADR-011 | Review decisions preserve provenance and suppression identity; routine reruns cannot resurrect equivalent rejected candidates. | LOCKED | Product owner changes review semantics. |
| ADR-012 | Event/folder map has global and scoped views over the same graph; Draft/Safe mode never touches the filesystem. | LOCKED | Product owner changes map behaviour. |
| ADR-013 | Relationship records are multi-edge, effective-dated, certainty-bearing, and history-preserving. | LOCKED | Never collapse to a single enum. |
| ADR-014 | Windows, macOS, and Linux are release platforms; platform-specific implementation is allowed behind one semantic contract. | LOCKED | Product scope change. |
| ADR-015 | No telemetry, auto-update check, remote tile fetch, cloud model call, or outbound request is enabled by default. | LOCKED | Separate opt-in ADR with disclosure, data-flow, failure, and privacy proof. |
| ADR-016 | The original snapshot becomes an immutable Git baseline before Phase 2. | LOCKED | Never implement on an unversioned working tree. |
| ADR-017 | Old generated requirement phase assignments are evidence-only; `REQUIREMENTS_EXECUTION.csv` controls execution. | LOCKED | Regenerate and semantically validate all mappings. |
| ADR-018 | The first public-quality release is not “Phase 3 shell”; it is Release R1 after Phase 5 with a safe local library and viewer. | LOCKED | Release strategy ADR. |

## Decision hygiene

A decision may be revised only by adding an ADR amendment that states the old decision, new decision, reason, affected requirements/files/schemas/tests, migration path, rollback path, and proof equivalence. Silent architectural drift is prohibited.
