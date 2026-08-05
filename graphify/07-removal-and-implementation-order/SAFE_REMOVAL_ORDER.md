# Safe removal order

| Subsystem/slice | Earliest safe phase | Prerequisite | Absence proof |
|---|---|---|---|
| Auth/user/session server paths | 3 | Local desktop launch/settings no longer depend on login | Phase 16 residual auth scan |
| Asset/timeline REST slices | 5 | Tauri asset commands + UI migration + parity | Generated SDK call absence for migrated slice |
| Storage/event server slices | 6 | Rust transactions/events + focused safety proof | Server caller scan |
| Person/face server slices | 7 | Local people/faces + worker contract | Face correction parity |
| Tag/relationship attribution slices | 8 | Local schemas/projection + nine-view proof | No server dependency for feature |
| ML HTTP listener/client | 10 | Supervised bundled worker + selected non-network IPC/process/listener tests | No FastAPI/Gunicorn/Uvicorn runtime path |
| Redis/BullMQ | 10 | Durable local scheduler + migrated handlers | No imports/env/dependencies/listeners |
| Metadata/editing server slices | 11 | Rust sidecar/XMP/edit/transaction proof | No retained caller |
| PostgreSQL remaining paths | 13 | SQLite-loss rebuild + all repository migrations | No pg/schema/query/migration dependency |
| Mobile/sharing/admin | 15 | Retained behavior parity and clean packages | Remove when safe; Phase 16 catches residues |
| Docker/deployment/generated clients | 15 | Desktop build/test/package paths replace them | Phase 16 repository-wide eradication |

A subsystem is removed as soon as all prerequisites pass in its assigned phase; it is not kept alive until Phase 16 for ceremony.
