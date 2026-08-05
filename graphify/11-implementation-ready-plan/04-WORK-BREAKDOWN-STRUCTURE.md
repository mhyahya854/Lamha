# Work breakdown structure

## Critical path

`0 → 1 → 3 → 4 → 5 → 6/7 → 8 → 9 → 10 → 11 → 12 → 13 → 14 → 15 → 16`

Phase 2 may run after Phase 0 and before/alongside Phase 3, but legal identity must be stable before external packaging. Phases 6 and 7 may overlap only after Phase 5 and the Phase 4 authority model are stable.

## Phase contracts

| Phase | Objective | Required artifacts | Exit condition |
|---:|---|---|---|
| 0 — Repository Proof & Corpus Inventory | Create immutable repository baseline; verify archive integrity; record package/version mismatch; establish disposable build workspace. | Git repository; baseline tag; hash manifest; toolchain report; baseline build/test report or cited blocker. | No code mutation before provenance and rollback exist. |
| 1 — Graphify Mapping & Master-Plan Traceability | Adopt this execution addendum; validate every requirement overlay; establish ADR and proof ledgers. | Execution CSV; decision register; risk/test/release contracts. | No BLOCKED requirement without owner and unblock condition. |
| 2 — Rebranding Foundation | Rebrand visible and package identity while preserving AGPL and third-party attribution. | Lamha names/icons/about/legal notices; compatibility aliases where required. | No removed attribution; UI and package metadata agree. |
| 3 — Tauri Desktop Shell | Create Tauri 2 shell and convert retained Svelte routes to static-client operation. | Cargo/Tauri manifests; capabilities; bootstrap; command registry; local settings/root picker. | No Node/server/database/listener needed to open the app. |
| 4 — Local Data Foundation | Implement local authority, schemas, scanner/watcher, authorized roots, SQLite index, and transaction foundation. | Rust domain modules; JSON Schema validation; DDL/migrations; journal/recovery; scan fixtures. | Delete SQLite and rebuild; crash/disk-full/path-escape tests pass. |
| 5 — Asset API Replacement | Replace asset REST paths and ship the first usable offline library. | Asset commands; gallery/timeline/viewer; local collections/search; inspector; Review shell. | No legacy server call in completed screens; real local data only. |
| 6 — Manage Later & Events | Implement Manage Later and event organization. | Event records; builder; merge/link/split; name normalization; reversible move plans. | Manage Later scan is non-mutating; no automatic event creation. |
| 7 — Faces, People & Groups | Implement faces, people, groups, aliases, and temporal memberships. | Face task slice; cluster curation; person/group records; effective dates. | Corrections are scoped; history is preserved. |
| 8 — Tags, Relationships, Smart Views & Attribution | Implement tags, relationship graph semantics, smart views, and attribution roles. | Multi-edge records; projections; nine views; tag review; photographer/camera owner/importer. | Every derived view explains provenance; roles remain distinct. |
| 9 — Mind Maps | Implement global and scoped map workspace. | Graph store/index; folder/event map; relationship map; drafts; simulation/materialization UX. | Drafts persist without filesystem writes; materialization is reversible. |
| 10 — Local AI Completeness | Complete local AI and intelligence features. | Worker executable; framed protocol; model registry; OCR/search/duplicates/location/content tasks; scheduler. | No network listener; cancellation/retry/invalidation/suppression tests pass. |
| 11 — Metadata Mutation, Editing & Privacy | Implement metadata mutation, editing, privacy, and batch operations. | Authority-aware editor; edit recipes; derivatives; privacy export; snapshots; batch transaction plans. | Originals are never silently overwritten; recovery proof passes. |
| 12 — External Drives & Filesystem Resilience | Implement external-drive identity, overlays, reconciliation, and cross-drive recovery. | Drive registry; reconnect; detached mode; pending overlays; relink; platform path adapters. | Disconnect/crash/read-only/symlink/junction tests do not orphan bundles. |
| 13 — Backup, Trash & Rebuild | Implement backup, Trash, restore, and deterministic rebuild. | Backup manifests; root trash; restore collision handling; full index/AI cache rebuild. | Fresh install + records/media can rebuild essential state. |
| 14 — Performance, Accessibility & Desktop UX | Meet performance, accessibility, and desktop interaction budgets. | Profiling reports; virtualization; job controls; keyboard/screen-reader audits. | Versioned budgets and WCAG-oriented acceptance checks pass. |
| 15 — Integration, Parity & Cross-Platform Packaging | Integrate and package on all platforms; finish legal and parity proof. | Windows/macOS/Linux artifacts; SBOM; notices; model/codec inventory; clean-machine reports. | No separate runtime/server; legal and parity sign-off recorded. |
| 16 — Final Cleanup & Release Reverification | Remove obsolete stack and reverify the final repository and packages. | Server/Postgres/Redis/Docker/mobile/generated-client removal; final graph; absence scan; release manifest. | Final packages pass all gates and obsolete runtime/source paths are absent. |

## Atomic work-item rule

Every implementation work item must contain: requirement IDs, legacy evidence, target files, schema/IPC impact, dependency list, failure modes, focused tests, regression tests, rollback, and removal eligibility. A phase is not a single giant prompt; Codex must execute bounded work packages and commit after each green gate.

## Phase completion evidence

Each phase creates `graphify/10-completion-tracker/phase-XX/` containing scope, changed files, requirements completed, commands run, test results, known limitations, risks changed, removal actions, rollback tag, and reviewer sign-off.
