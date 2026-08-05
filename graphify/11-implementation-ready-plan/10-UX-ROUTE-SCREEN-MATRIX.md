# UX, navigation, and screen-to-command matrix

## Primary navigation

`Timeline`, `Folders`, `Events`, `People`, `Relationships`, `Mind Maps`, `Albums`, `Favorites`, `Memories`, `Map`, `Search`, `Review`, `Manage Later`, `Trash`, `Settings`.

## Route contract

The final static client may retain SvelteKit route syntax, but every route must be client-loadable from the packaged fallback and must not depend on `+page.server`, server hooks, cookies, sessions, or REST fetches.

| Screen | Core commands | Mandatory states |
|---|---|---|
| First launch/root setup | roots choose/validate/add; app status | No root, invalid path, read-only, offline, permission denied. |
| Timeline/gallery | assets page; thumbnail request; selection summary | Empty, scanning, partial results, offline assets, corrupt sidecar, unsupported preview. |
| Viewer/inspector | asset get/open; metadata inspect; companions | Missing original, read-only, future schema, conflict, video/RAW fallback. |
| Folders | roots/list folders; assets page | Linked vs managed, offline, unauthorized, watcher reconciliation. |
| Manage Later | scan plan/status; event planning | No mutation before confirmation; resumable review. |
| Events | event CRUD; merge/link/split simulations | Collision, unknown date, midnight span, mixed/linked folder. |
| People/groups | people/face/group commands | Unknown, hidden, merge conflict, historical membership. |
| Relationships | edges/history/projection | Multiple simultaneous edges, certainty, custom type, effective dates. |
| Mind Maps | global/scoped load; draft save; simulate/materialize | Draft, ready, materialized, linked, read-only, offline, conflict, failed operation. |
| Search | structured/text/OCR/semantic | Indexing, model unavailable, stale results, no match. |
| Review | list/get/decision/bulk | Pending, deferred, suppressed, stale, conflict, reconsidered. |
| Editing/privacy | recipe; metadata proposal; export | Non-destructive preview, original protection, output collision. |
| Backup/Trash/Rebuild | maintenance plans/runs/status | Destination offline/full, verification failure, restore collision, cancellable rebuild. |
| Settings/diagnostics | settings; models; roots; diagnostics | Local-only disclosure, component licences, storage/cache controls. |

## Accessibility contract

All functionality is keyboard reachable; focus order and restoration are deterministic; dialogs trap focus; icon-only controls have accessible names; state is not conveyed only by color; progress and errors are announced; graph canvases provide list/tree alternatives and keyboard node operations; reduced motion is respected.

## Global vs scoped mind maps

The global view shows all user-visible event/folder nodes and their logical edges. A scoped view filters the same canonical graph to a selected root, folder, event, branch, person context, or saved focus. Scoped edits update the same draft graph; they do not create a second inconsistent map. The UI must always display current scope and provide `Show in global map`.
