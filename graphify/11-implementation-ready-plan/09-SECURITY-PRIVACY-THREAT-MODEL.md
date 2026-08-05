# Security and privacy threat model

## Assets to protect

Original media, embedded metadata, sidecars/domain records, relationship/face knowledge, location data, AI outputs/models, backups, operation journals, root authorization, and signing/update integrity.

## Trust boundaries

1. Svelte webview ↔ Tauri IPC.
2. Rust core ↔ user-selected filesystem roots.
3. Rust core ↔ SQLite/cache.
4. Rust core ↔ AI child process.
5. Packaged application ↔ bundled tools/models/codecs.
6. Lamha ↔ optional user-initiated external export/open actions.

## Threats and required controls

| Threat | Control | Proof |
|---|---|---|
| Webview invokes excessive local authority | Minimal capabilities; scoped custom commands; no generic shell/fs write access. | Capability snapshot and negative IPC tests. |
| Path traversal or symlink/junction escape | Canonicalization, authorized-root token, component checks, platform reparse handling. | Escape corpus on all platforms. |
| Malicious/corrupt sidecar | Size limits, JSON Schema, depth limits, tolerant read, quarantined bytes, no code execution. | Fuzz/property tests and corrupt fixtures. |
| AI worker becomes a local service | Child-only framed streams; no bind/listener; per-request path access; terminate on protocol violation. | Port scan/process tests and malformed-frame tests. |
| Worker writes authoritative data | Read-only media access where possible; results returned to Rust; no record/DB paths supplied. | Sandbox/permission and write-attempt tests. |
| Untrusted media exploits decoder/tool | Pinned binaries, process isolation, resource/time limits, update/legal inventory. | Malformed-media corpus and dependency scanning. |
| Metadata privacy leaks through export | Privacy export defaults to a new output and explicit field checklist. | Golden-file metadata inspection. |
| Backup exposes sensitive graph/face data | Clear destination warning; optional encryption is post-1.0 unless implemented with a separate ADR. | Backup manifest and restore tests. |
| Multiple instances corrupt a root | Root mutation lease and stale-lock recovery. | Concurrent-instance integration tests. |
| Supply-chain or package tampering | Lockfiles, checksums, SBOM, signed release manifest, reproducible-input inventory. | CI artifact verification. |
| Accidental outbound traffic | Network-deny tests; no telemetry/update/tile/model calls by default. | Clean-machine traffic capture. |

## Logging

Logs are local, structured, rotating, and privacy-minimized. Do not log face embeddings, full OCR text, relationship notes, precise paths unless diagnostics mode is explicitly enabled, or media bytes. Diagnostics export previews exactly what will be included.
