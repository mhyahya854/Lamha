# Filesystem safety tests

Required matrix: authorized/unauthorized roots; symlink/junction/reparse escapes and cycles; case/Unicode/reserved/length collisions; disk full; permission/read-only; disconnect/reconnect; crash at every transaction stage; same/cross-drive move; companion bundles; missing/detached/corrupt/future sidecars; Pending Overlay reconciliation; Trash/restore/permanent delete; incomplete operations; hash/UUID conflicts; SQLite loss. Every test runs on disposable copies.
