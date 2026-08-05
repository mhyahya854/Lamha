# Local AI worker map

| Boundary | Phase 1 recommendation or alternative | Evidence/risk/proof obligation |
|---|---|---|
| Recommendation | Length-prefixed UTF-8 JSON messages over child standard input/output | Cross-platform non-network stream already coupled to worker spawn/supervision; prove framing, backpressure, size limits, cancellation, and stderr separation |
| Alternative: named pipes | Viable non-network option, strongest fit on Windows | Prove per-user access control, stale-endpoint cleanup, reconnect behavior, packaging, and macOS/Linux equivalent strategy |
| Alternative: Unix-domain sockets | Viable non-network option on macOS/Linux and modern Windows with platform caveats | Prove path/ACL handling, stale socket cleanup, Windows support floor, reconnect behavior, and packaging |
| Alternative: Tauri sidecar communication | Valid process packaging/supervision wrapper; underlying byte transport must still be defined | Prove sidecar API capabilities, streaming/progress/cancellation behavior, stderr isolation, and all-platform packaging |
| Media access | Rust passes authorized canonical local paths and task parameters | No upload; worker read scope is per request |
| Lifecycle | Rust spawn/supervise/restart/terminate; stderr captured to app logs | No daemon/listener; unrelated clients cannot connect |
| Concurrency | Request UUID + bounded scheduler + progress events | Hardware-aware CPU/GPU/hybrid limits |
| Cancellation | Typed cancel message; escalation to process restart after timeout | Idempotent task state and safe retry |
| Authority | Typed candidates/results return to Rust | Worker never writes authoritative JSON/XMP/SQLite decisions |
| Security | No TCP/UDP bind, HTTP, WebSocket, cloud, telemetry, or arbitrary client | Listener/process/packaging tests on Windows/macOS/Linux |

Existing HTTP endpoint evidence: `Codebase/machine-learning/immich_ml/main.py:L152-L166`; existing process evidence: `Codebase/machine-learning/immich_ml/__main__.py:L34-L43`; existing server client evidence: `Codebase/server/src/repositories/machine-learning.repository.ts`. Target ownership is `src-tauri/src/ai/` with thin command consumers under `src-tauri/src/commands/`. Standard input/output is recommended because it is the smallest cross-platform non-network mechanism that naturally shares the required child-process lifecycle; it is not a Master Plan-mandated exclusive transport. Phase 10 must validate the recommendation against the alternatives and may change it only through a traced decision update with equivalent security, lifecycle, streaming, cancellation, and packaging proof.
