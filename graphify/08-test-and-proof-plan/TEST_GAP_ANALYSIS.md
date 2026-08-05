# Test gap analysis

| Gap | Current status | Owner | Required proof |
|---|---|---|---|
| Tauri command/UI wiring | No current Tauri/Rust | Phases 3–14 | typed command integration + desktop launch |
| SQLite loss/rebuild | No target desktop store | Phases 4/13 | delete DB on test copy; rebuild from filesystem/JSON |
| JSON schemas/migrations/future/corrupt | No target sidecars | Phase 4 | schema fixtures, unknown-field preservation, backups |
| Filesystem transaction failure injection | Current server semantics do not prove target | Phases 4/6/11/12/13 | disk full, crash, disconnect, collision, read-only |
| Non-network AI worker | Current ML is HTTP | Phase 10 | no listener + lifecycle/cancel/retry/security |
| Relationship multi-edge/projection | Confirmed absent | Phase 8 | history/certainty/custom type/nine views |
| Cross-platform packages | No desktop package | Phase 15 | clean Windows/macOS/Linux launch |
| Removal absence | Nothing removed yet | Each removal + Phase 16 | source/import/dependency/config/runtime/installer/UI scan |

Ponytail-added proof needs are included: generated-client absence, broker/server/listener absence, per-screen real-data Tauri wiring, architecture simplicity review, and preservation of current parity scenarios.
