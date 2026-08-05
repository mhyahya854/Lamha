# Tauri IPC contract

## Contract principles

- Commands are typed request/response operations. Long work returns an operation/task ID and reports progress through typed events.
- Every mutating command accepts `requestId`, expected record revisions where applicable, and a `dryRun`/simulation path for structural filesystem work.
- The webview never receives arbitrary filesystem authority. It sends stable IDs and user-selected root tokens; Rust resolves canonical paths.
- Errors are machine-readable and never represented as a successful empty response.

## Standard envelope

```text
Request:  { requestId, commandVersion, payload }
Success:  { requestId, result, warnings[], affectedRevisions{} }
Failure:  { requestId, error: { code, message, retryable, details, reviewItemId? } }
Progress: { operationId, stage, completed, total?, message?, cancellable }
```

## Error taxonomy

`INVALID_ARGUMENT`, `NOT_FOUND`, `REVISION_CONFLICT`, `ROOT_NOT_AUTHORIZED`, `PATH_ESCAPE`, `READ_ONLY`, `ROOT_OFFLINE`, `COLLISION`, `INSUFFICIENT_SPACE`, `UNSUPPORTED_FORMAT`, `FUTURE_SCHEMA`, `CORRUPT_RECORD`, `TRANSACTION_IN_DOUBT`, `WORKER_UNAVAILABLE`, `TASK_CANCELLED`, `MODEL_UNAVAILABLE`, `LEGAL_COMPONENT_MISSING`, `INTERNAL`.

## Command families

| Family | Required operations |
|---|---|
| `app` | bootstrap/status, diagnostics export, local settings get/update, graceful shutdown readiness. |
| `roots` | choose/add/remove/list, validate, reconnect, access-mode change, rescan. |
| `assets` | page/get/locate/open, selection summaries, metadata/companions, thumbnail request, hash verify. |
| `scan` | plan/start/pause/resume/cancel/status; watcher reconcile. |
| `events` | create/update, plan merge/link/split/normalize, commit operation, undo eligibility. |
| `people` | clusters/person CRUD, merge/split/hide, face correction, group and membership operations. |
| `relationships` | edge CRUD, effective-date change, certainty/note update, projection preview, history. |
| `tags` | namespaces, candidates, approve/reject/suppress, bulk assignment. |
| `maps` | global graph load, scoped graph load, draft create/save, simulate, materialize, recover. |
| `search` | structured query, text/OCR, semantic query, pagination and cancellation. |
| `review` | list/filter/get, approve/reject/defer/suppress/reopen, bulk action with per-item result. |
| `ai` | hardware assessment, model inventory, task plan/start/pause/resume/cancel/retry/invalidate. |
| `metadata` | inspect sources, propose update, apply reviewed update, privacy export, snapshot/restore. |
| `editing` | recipe get/update, derivative/export plan, render, reset. |
| `maintenance` | backup plan/run/verify, trash/restore/permanent-delete plan, rebuild plan/run/status. |
| `operations` | simulate/get/list/recover/rollback where valid; export diagnostics. |

## Compatibility

`commandVersion` starts at `1`. Additive fields are tolerated. Breaking payload changes require a new version and a temporary adapter until all UI consumers migrate. Rust integration tests and generated TypeScript types must derive from one canonical DTO source or be checked for drift in CI.
