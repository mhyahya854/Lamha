# Open decisions

**Blocking product decisions: none.**

Phase 1 selections now recorded: target root module structure, `lamha-index.sqlite3` and internal index names, `schemaVersion`/initial `1.0.0` and domain schema keys, AI task keys, the recommendation of length-prefixed child standard input/output after comparison with named pipes, Unix-domain sockets, and Tauri sidecar-managed communication, removal slicing, and proof ownership. These are traced design decisions, not current implementation claims. Phase 10 must validate the recommended transport with mechanism-specific lifecycle, cancellation, access-control, and packaging proof; a traced equivalent alternative remains allowed. Normal implementation-level choices inside those boundaries must be logged here if a genuine ambiguity would alter behavior or safety.

## Implementation-ready addendum

Binding product decisions remain zero. Time-boxed engineering spikes and their proof requirements are listed in `graphify/11-implementation-ready-plan/20-OPEN-DECISIONS.md`; they do not authorize product or safety drift.
