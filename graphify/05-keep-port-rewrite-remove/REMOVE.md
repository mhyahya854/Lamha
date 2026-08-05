# Remove

| Capability | Reason/scope | Phase | Target |
|---|---|---|---|
| Authentication and users | Current multi-user/auth/session architecture; target desktop has one local operator and no account requirement. | Phase 3 | src-tauri/src/settings/local_operator.rs; web/src/routes/+layout.svelte |
| Sharing and mobile backup | Current server sharing and phone backup paths; remote/multi-user behavior is out of target scope while local export/backup is replaced. | Phase 15 | src-tauri/src/backup/; src-tauri/src/commands/export.rs |
| Administration | Current server administration, queues, users, and maintenance; retained device settings move to local desktop settings. | Phase 15 | web/src/routes/settings/; src-tauri/src/settings/ |

Removal happens only after replacement-before-removal gates; no removal occurred during planning.
