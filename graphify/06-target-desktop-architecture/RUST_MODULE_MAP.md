# Rust module map

| Planned path | Responsibility | First phase |
|---|---|---|
| src-tauri/src/app.rs | bootstrap, state, command registration | 3 |
| src-tauri/src/commands/ | thin typed IPC adapters | 3 |
| src-tauri/src/library/ | roots/scanner/watcher/external drives | 4 |
| src-tauri/src/assets/ | bundle/sidecar/rename/move/edit | 4 |
| src-tauri/src/schema/ | versioned schema validation/migration | 4 |
| src-tauri/src/index/ | SQLite migrations/index/rebuild | 4 |
| src-tauri/src/transactions/ | prepare/commit/rollback/recovery | 4 |
| src-tauri/src/events/ | event identity/organization | 6 |
| src-tauri/src/people/ | people/faces | 7 |
| src-tauri/src/groups/ | nested/effective membership | 7 |
| src-tauri/src/relationships/ | multi-edge certainty/projection | 8 |
| src-tauri/src/review/ | review lifecycle/history | 5 |
| src-tauri/src/ai/ | worker supervision/protocol/task state | 10 |
| src-tauri/src/backup/ | backup/restore | 13 |
| src-tauri/src/trash/ | reversible Trash/permanent delete | 13 |

These paths are target nodes with `Not implemented` status; the confirmed-absence audit found no current Cargo/Tauri/Rust source.
