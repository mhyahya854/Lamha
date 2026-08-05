# Risk register

| ID | Risk | Severity | Mitigation/proof | Owner phase |
|---|---|---|---|---|
| R-01 | Data loss during bundle mutation | P0 | transaction protocol + failure injection + backups | 4 |
| R-02 | Authority divergence among filesystem/JSON/XMP/SQLite/overlay | P0 | directional authority + conflict review + rebuild | 4 |
| R-03 | Premature server/Postgres/Redis/Docker removal | P0 | replacement/caller migration/proof gates | Each removal |
| R-04 | AI worker exposes network or writes authority | P0 | supervised child, mapped non-network IPC, sandbox, mechanism-specific lifecycle/access-control, listener/write tests | 10 |
| R-05 | Cross-platform path/permission mismatch | P0 | native APIs and platform matrix | 12 |
| R-06 | Feature parity loss in UI/API migration | P1 | requirement/test matrix and sliced removals | 5 |
| R-07 | Schema migration/future-version/corruption loss | P0 | formal schemas, backups, unknown-field preservation | 4 |
| R-08 | Licence/attribution/model/codec omission | P0 | inventory, notices, legal sign-off | 15 |
| R-09 | Large-library performance collapse | P1 | 10k/50k/100k measured budgets | 14 |
| R-10 | Generated-client or launch-path residue | P1 | consumer graph + Phase 16 absence scan | 16 |

Ponytail reconciliation confirms R-03/R-06/R-09/R-10 as the over-engineering and residue risks: one-for-one server layering, broker/runtime carry-over, premature code generation/multi-crate architecture, and obsolete deployment/client remnants.

## Expanded binding register

The ten-row summary above is retained as a headline view. The binding trigger/impact/prevention/detection/recovery/test/owner/status register is `graphify/11-implementation-ready-plan/19-RISK-REGISTER-EXPANDED.md`.
