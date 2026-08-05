# Removal blockers

| Subsystem | Load-bearing consumers | Replacement window | Safe-removal rule |
|---|---|---|---|
| NestJS/Express server | All web/mobile/SDK HTTP consumers; media/storage/business services | Phases 3–15 | Remove by assigned subsystem after local replacement; Phase 16 residual scan |
| PostgreSQL/schema/queries | Repositories, migrations, e2e fixtures, backup/maintenance | Phases 4–15 | Remove after SQLite/JSON rebuild and behavior parity |
| Redis/BullMQ | Job repository, workers, events, WebSocket adapter | Phases 10–15 | Remove after durable local scheduler proof |
| Python HTTP service | Machine-learning repository and deployment | Phase 10 | Replace listener with a supervised bundled worker using the Phase 1-recommended non-network IPC after mechanism-specific proof |
| Generated SDKs/OpenAPI | Web, mobile, CLI, e2e | Phases 5–16 | Remove after every generated-client consumer migrates |
| Mobile | Backup/sync/platform UI and generated Dart client | Phases 5–15 | Port retained local behaviors, then remove |
| Docker/deployment | Development, e2e, server packaging, docs | Phases 3–16 | Desktop launch first; final clean-machine proof |
| Auth/users/sharing/admin | Routes, controllers, services, DTOs, tests | Phases 3–16 | Local settings/export/backup replacement, then remove |

Ponytail evidence: `graphify-out/ponytail/PONYTAIL_AUDIT.md`; every finding is resolved in `05-keep-port-rewrite-remove/PONYTAIL_RECONCILIATION.md`.

No deletion is authorized by this document. Each subsystem requires source-verified caller migration, focused/regression/build/desktop-launch proof, rollback/baseline evidence, Graphify/Ponytail agreement, and recorded absence proof.
