# Local AI worker, model, and packaging plan

## Process model

Rust launches one supervised worker per app instance, negotiates protocol version, receives capabilities/model inventory, and sends bounded tasks. The worker has no listening port and exits when the parent closes. A crash marks in-flight tasks retryable; it never marks results approved.

## Framed protocol

Each frame is: 4-byte unsigned big-endian payload length followed by UTF-8 JSON. Maximum control frame size is 16 MiB; large outputs use bounded chunks or files in an app-controlled cache directory referenced by opaque task IDs. Standard error is logs only and never protocol data.

Messages: `hello`, `helloAck`, `taskStart`, `taskProgress`, `taskResult`, `taskError`, `taskCancel`, `taskCancelled`, `ping`, `pong`, `shutdown`. Every task carries request/task UUID, task kind, model ID/version, source fingerprint, configuration fingerprint, authorized input paths, and output constraints.

## Task registry

`face-detect`, `face-embed`, `face-cluster-candidate`, `ocr`, `image-embed`, `semantic-query`, `exact-hash`, `perceptual-duplicate`, `burst-candidate`, `content-tag-candidate`, `location-candidate`, `thumbnail/preview-assist` where retained logic requires it.

## Model registry

Each model entry records stable ID, version, task kinds, source, checksum, licence, input/output contract, minimum RAM/VRAM, supported providers, and redistribution status. The build must fail if a bundled model lacks a checksum or licence record.

## Hardware modes

- `automatic`: benchmark and choose safe provider/concurrency.
- `cpu`: universal fallback.
- `gpu`: only when a validated provider is available.
- `hybrid`: explicit task/provider split.

A benchmark result is device-local and versioned by app, model, provider, and configuration. OOM, thermal, or repeated provider failures downgrade safely and create a diagnostic warning.

## Packaging decision

Package the Python worker into a platform/architecture-specific executable or self-contained directory and declare it as a Tauri sidecar. The implementation may choose PyInstaller, Nuitka, or another reproducible packager only after a spike proves startup, model loading, antivirus/signing compatibility, cancellation, crash handling, and clean-machine operation on all target platforms. No user-installed Python is permitted.

## AI authority and review

Raw model results are candidates. Rust validates shape/ranges, stores task provenance, and creates Review items for consequential interpretation. Approved decisions persist in transparent records. Equivalent rejected/suppressed candidates remain suppressed until explicit reopen or a material source/model/configuration/candidate/evidence change.
