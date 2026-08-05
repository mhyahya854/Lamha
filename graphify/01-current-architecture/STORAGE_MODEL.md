# Current storage model

| Store | Current evidence | Authority/disposition |
|---|---|---|
| Primary media | Server storage service/repository and filesystem | Authoritative media bytes; target single-media authority |
| PostgreSQL | server/src/schema; repositories; queries | Current authoritative application database; remove after local replacements |
| Redis/BullMQ | server/src/repositories/job.repository.ts; config.repository.ts | Current queues/cache; replace with local scheduler/state |
| Machine-learning model cache | machine-learning/immich_ml/models/cache.py | Derived, rebuildable local artifacts |
| Mobile Drift/SQLite | mobile/lib/infrastructure/entities | Mobile-only current local cache; not a desktop implementation |
| Target sidecars | CONFIRMED ABSENCE in Codebase | Future transparent authority mapped in Phase 4 |
| Target embedded SQLite | CONFIRMED ABSENCE for desktop | Future derived index/working-state store mapped in Phase 4 |

Confirmed-absence scope: all 3,697 inventoried files, Graphify nodes/edges, filename searches for Cargo/Tauri/Rust/desktop SQLite/sidecar/overlay concepts, and bottom-up directory review. Only Flutter's mobile SQLite packages were found; they do not satisfy the target desktop store.
