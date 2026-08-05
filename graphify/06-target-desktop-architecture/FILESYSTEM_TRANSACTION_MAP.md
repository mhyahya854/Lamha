# Filesystem transaction map

| Stage | Binding operation |
|---|---|
| Prepare | Generate transaction UUID; enumerate bundle operations; validate identities, capacity, permissions, collisions, and authorized paths |
| Durable intent | fsync coordinator manifest in OS app data and mirrors on each affected writable root |
| Stage | Copy/write temp files in target filesystem; preserve sources; hash/validate media and sidecars |
| Commit | Atomic rename where supported; update authoritative records; fsync directories; mark all manifests COMMITTED |
| Cleanup | Remove source only after target verification; retain operation history and rollback evidence |
| Recover | On startup reconcile manifests by UUID, never SQLite alone; preserve ambiguous copies and create Review item |
| Cross-drive/read-only | Controlled copy or Pending Overlay; never claim a failed write reached the root |

The media, asset JSON, and XMP form one steady-state bundle. Trash, restore, rename, move, and permanent delete operate on the complete bundle; companion bundles remain independent assets linked by stable IDs.
