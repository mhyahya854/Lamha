# Generator defect audit

Review date: 2026-08-01

Scope: `build_semantic_plan.py` and every active generated family under `12-semantic-implementation-plan/`.

This is a defect record, not a readiness declaration. The prior generator is not an acceptable canonical source.

## Confirmed generator defects

| Defect | Generator path | Affected generated family | Evidence before repair | Required correction |
|---|---|---|---|---|
| Keyword-based classification | `classify()` | `02-requirements/*`, all downstream mappings and packets | Classification is selected by substring tests over requirement text, heading, and inherited capability. | Store each final classification in an explicit reviewed requirement registry. Builder must not classify text. |
| Inherited/coarse capability mapping | `normalize_requirements()` | Requirement registry, phase maps, packages | `TargetCapability` is copied from the legacy traceability table, including media obligations labelled `Desktop shell`. | Store a reviewed canonical capability per canonical item, retaining the legacy capability only as provenance. |
| Keyword/default phase allocation | `semantic_phase()`, `CAPABILITY_DEFAULT`, `CAPABILITY_PHASES` | Phase registry, packages, reports, packets | Assignment is made by ordered substring rules and a capability default. `CAN-FAIL-01` and `CAN-LAM-ASSET-004` consequently landed in I2. | Store one reviewed primary phase and the distinct verification/removal/release responsibilities in an explicit mapping table. |
| Keyword-score work-package allocation | `build_work_packages()` | Work-package registry, packets, dependency graph | Requirements are scored against package keyword sets. | Store explicit requirement-to-package membership. Builder must only join explicit IDs. |
| Numerical/source-section slicing | `build_work_packages()` | 59 of 172 work packages | Packages over an internal capacity are divided and named `source-boundary slice N`. | Replace every slice with an architecture-owned package or merge it into a cohesive package. No capacity split is permitted. |
| Generic acceptance-criterion normalization | `normalize_statement()` | 632 canonical statements | Statements use `must demonstrably satisfy: X`, including nouns such as `GPS`, `Tags`, `Reject`, and `Renamed`. | Rewrite criteria to include precondition, behavior, observable result, and failure behavior where applicable. |
| Generic DTO generation | `command_schema()` | 116 request and 116 response schemas | 64 request schemas and 94 response schemas contain undefined nested objects or arrays of anonymous objects. | Use command-specific properties and closed shared definitions; every open extension point must be enumerated and justified. |
| Generic event/worker payloads | `write_shared_contracts()` | Operation-event and AI worker schemas | Event payload, worker input, candidate, and fingerprint shapes contain open or incomplete objects. | Replace with discriminated, closed variants and shared exact definitions. |
| Generic record-schema generation | `RECORD_FIELDS`, `property_schema()`, `write_record_schemas()` | 35 authoritative and 2 derived record schemas | Records are identity shells; several core collections use `object` or `array<object>`, and record envelopes allow all unknown fields. | Author explicit product schemas with a constrained extension container, provenance, privacy, authority, revisions, and concrete nested records. |
| Predetermined audit conclusions | `write_reports()` | `13-reports/manual-semantic-audit.md` | Three samples per capability/phase are generated and every section is pre-filled as correct. | Rename generated sampling honestly and create a separate reviewer-authored findings ledger containing decisions and corrections. |
| Mechanical dependency construction | `build_work_packages()` | Work-package DAG and packets | Dependencies include phase anchors and neighboring packages rather than only technical prerequisites. | Store typed, justified dependency edges explicitly and reject numerical adjacency rationales. |
| Incorrect component blockers | `write_components()` fuzzy `wp()` lookup | Component manifest | Examples: Svelte/SvelteKit -> I15; FFmpeg -> I5; image thumbnails -> I15; face recognition -> I15. | Store decision, blocker, and required-before package IDs explicitly and validate their phase/technical relevance. |
| Hard-coded expected counts | validator level 8 | Validator results | Passing depends on expected numerical ranges/counts produced by the same generator. | Validate completeness from explicit registries and referential/semantic invariants, never target counts. |
| Self-confirming validation | generated validator and reports | All readiness reports | Generated claims are compared with other generated claims and samples are selected by the allocation logic itself. | Add independent source-row reconciliation, forbidden-pattern checks, nested schema traversal, semantic boundary checks, DAG rules, audit-authenticity checks, and adversarial fixtures. |
| Unsafe output primitive | `write_text()` and `write_csv()` | Every generated file | Output paths were formed by concatenating `OUT / rel` without resolved-root or reparse-point enforcement. | Route every write through one resolved descendant guard that rejects symlink/junction traversal and test an outside destination adversarially. |

## Generator-path and output-family trace

| Input or function | Direct outputs | Downstream consumers |
|---|---|---|
| `04-master-plan-traceability/REQUIREMENTS.csv` | Normalized items and source dispositions | Mapping, packages, reports, packets |
| `classify()`, `normalize_statement()` | `02-requirements/canonical-registry.*` | Phase and package allocation, prompt content |
| `semantic_phase()` | `03-phases/*`, remapping audit | Work packages, packets, validation |
| `WP_CATALOG`, `build_work_packages()` | `04-work-packages/*` | DAG, components, commands, packets, handoff |
| `command_schema()`, shared-contract writers | `05-contracts/*` | Contract report, package packets |
| `RECORD_FIELDS`, `write_record_schemas()` | `06-schemas/*` | SQLite traceability, package packets |
| `SQL_DDL`, `write_sqlite()` | `07-sqlite/*` | Schema report and rebuild claims |
| test/risk writers | `08-testing/*`, `09-risks/*` | Phase/work-package packets |
| fuzzy component resolver | `10-component-manifest/*` | Component gates and reports |
| packet writers and `plan_cli.py` | `11-model-packets/*`, package packets | Implementation handoff |
| validator writer | `12-validators/*` | Readiness declaration |
| report writers | `13-reports/*` | Human handoff |
| handoff writer | `14-handoff/*` | First implementation invocation |

## Repair invariant

The replacement builder may format and join reviewed inputs, but it may not infer requirement meaning, capability, phase, package membership, dependency edges, component blockers, command flags, or schema shapes. Missing reviewed decisions are fatal. Forbidden legacy generator symbols and output phrases are validator failures.
