# Manual semantic audit

Reviewer: Codex semantic repair session, 2026-08-01

This document records the independent review performed after candidate generation. It is not emitted or rewritten by `build_semantic_plan.py`. The row-level evidence is in `reviewed-semantic-sample-ledger.csv`, `manual-package-review.csv`, `command-flag-review.csv`, `manual-schema-review.csv`, `legacy-package-disposition.csv`, and the component registry.

## Review coverage

- 540 normalized requirement samples across all 32 active canonical capabilities; 20 per capability where at least 20 were available.
- All 154 final packages, including all 19 packages above 20 items and all 25 packages spanning more than two canonical capability labels.
- All 172 legacy packages received an explicit keep/reassign/merge/replace disposition.
- All 65 mutating IPC commands and all 11 destructive commands.
- All 20 authoritative and 3 derived record schemas.
- All 17 unresolved component/version/licence rows.
- All 84 typed dependency edges.

## Findings and corrections

| Finding | Reviewer judgement | Correction made |
|---|---|---|
| 632 active criteria used the phrase `must demonstrably satisfy` around labels or fragments. | Defect | Rewrote fragmentary criteria with an explicit trigger, behavior, observable state, and failure rule; no active generic template remains. |
| Four short prohibitions were grammatical but too terse to expose the tested boundary. | Defect | Expanded photographer/camera-owner separation, cross-drive rename behavior, scoped rescanning, and attendee/visible-person separation into complete testable obligations. |
| 99 rows from the deletion plan were still represented as feature implementation. | Defect | Reclassified them as final-state prohibitions, retained source provenance, and separated I15 removal verification from primary implementation. |
| `CAN-FAIL-01` and `CAN-LAM-ASSET-004` inherited `Desktop shell` and I2 because their source capability was coarse. | Defect | Assigned both to `Media ingestion and derivation`, I4, with explicit membership in the HEIF/RAW/media foundation. |
| HEIF, RAW, video ingestion, companion handling, extraction, previews, scanning, and watchers inherited UI/shell phases in several rows. | Defect | Corrected the reviewed mapping by actual media-pipeline responsibility; no such record remains in I2. Viewer-only behavior remains in I5 and depends on I4 format/runtime foundations. |
| A repository rollback/baseline record drifted into crash recovery because it contained the word `recovery`. | Defect | Made every mission-owned I0 record explicitly I0; mapping no longer derives from words. |
| Agent/governance clauses such as anti-guessing and asking the user for code were treated as application features. | Defect | Removed their primary implementation phases and retained them as global implementation/verification constraints. |
| Synthetic section parents were routed from the phrase `Synthesized from fragmented clauses`. | Defect | Assigned each parent from the reviewed consensus of its linked child criteria, then bound it to the majority child package. |
| Event/folder criteria accumulated in a 76-item `event materialization` package because `folder` was over-broad. | Defect | Reassigned event records, UI blocks, boundaries, Manage Later, merge/split, and materialization to their distinct architectural packages; materialization fell below the mandatory large-package threshold. |
| Tag requirements were captured by attribution/projection packages because the Phase 8 heading named several capabilities. | Defect | Applied the source text and the canonical `Tags` capability before relationship/attribution routes; tag records and tag-candidate packages now own their respective rows. |
| All previous `source-boundary slice` packages encoded capacity/source order rather than architecture. | Defect | Merged/replaced all 59 slices and froze 1,183 explicit requirement-to-package memberships; zero slice names or capacity flags remain. |
| Cross-capability packages initially appeared suspicious. | Mixed | Confirmed only shared boundaries whose contents use one common record/contract/workflow: authoritative record envelope, SQLite projection, Review Centre, duplicate comparison, relationship projection, accessibility, and similar cross-cutting surfaces. Their explicit rationales name the participating capabilities. |
| Dependencies were partly generated from phase/package adjacency. | Defect | Replaced them with 84 explicit typed technical edges; no edge rationale references previous/next/package number or array order. |
| Several component blockers pointed to unrelated I15 packages, and two inference-host decisions were later than an I7 consumer. | Defect | Corrected each decision/blocker/required-before reference. Tauri/Svelte/WebView implementation is I2; SQLite I3; media codecs/extraction/previews I4; face and AI runtime use is I7/I10; all choices needed by earlier consumers are feasibility/licence decisions in I0; signing is I15. |
| 64 request and 94 response schemas contained untyped nested objects; event/worker contracts had additional payload holes. | Defect | Replaced them with exact command-specific schemas and closed shared definitions. One intentional `x-*` scalar extension map remains with an explicit rationale. |
| 26 command flag combinations were inconsistent with planning versus commit, duration, or destructive authority. | Defect | Reclassified them in the explicit v3 command registry and reviewed every mutating/destructive command in the command ledger. |
| The prior 35 authoritative and 2 derived records were skeletal identity shells with anonymous objects. | Defect | Replaced them with 20 materially complete authoritative and 3 derived schemas, including full asset, event, identity, relationship, operation, backup, trash, settings, and edit contracts. |
| The prior automatically generated sample report labelled itself manual and pre-filled every finding as correct. | Defect | Removed it from the active generation path. Generated sampling is labelled generated; this reviewer-authored audit records both confirmations and defects/corrections. |

## Boundary confirmations

- The first implementation package remains `WP-I0-001`; this audit does not claim the application builds or works.
- Pending component versions, licences, and redistribution rights remain pending and block only their explicit decision/required-before packages.
- Packages spanning several capability labels were retained only when the shared architecture is the subject of the package; the labels are recorded rather than hidden.
- No requirement, phase, package, dependency, component, command flag, or schema shape is recalculated by the production builder.
