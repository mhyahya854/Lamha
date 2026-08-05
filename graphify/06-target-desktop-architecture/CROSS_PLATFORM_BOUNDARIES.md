# Cross-platform boundaries

| Boundary | Selected approach | Required proof |
|---|---|---|
| Paths | Rust `Path`/canonicalization; no hard-coded drive/home prefixes | Windows drive/UNC, macOS/Linux roots, Unicode/case/reserved-name tests |
| Permissions/sandbox | Tauri capabilities + Authorized Path Set | escape/symlink/junction/reparse-cycle rejection |
| Watchers | platform watcher abstraction with rescan reconciliation | rename, disconnect, reconnect, overflow tests |
| Atomicity | same-filesystem atomic rename; cross-drive staged copy | crash/disk-full/disconnect failure injection |
| Worker | bundled Python executable/environment + mapped non-network IPC (framed stdio recommended) | mechanism-specific lifecycle/cancel/access-control proof; no installed runtime/listener; signed package test |
| Media tools | bundled/licensed FFmpeg/ExifTool/decoders as selected | architecture/codec/licence/clean-machine matrix |
| Packaging | Tauri Windows/macOS/Linux | launch, signing/notarization paths, clean machine |
