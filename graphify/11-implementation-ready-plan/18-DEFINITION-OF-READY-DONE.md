# Definition of Ready and Definition of Done

## Work item is Ready when

- Requirement IDs and Master Plan clauses are cited.
- Current files/callers/tests are identified or confirmed absent.
- Target module, schema, command, UI, and authority impact are known.
- Dependencies and preceding phase gates are green.
- Failure modes, rollback, fixtures, focused tests, and regression scope are named.
- No unresolved product decision is being guessed.

## Work item is Done when

- Production behaviour is complete with no stub/TODO/mock success path.
- Focused, integration, regression, safety/security, and platform tests applicable to the change pass.
- UI uses real Tauri/local data and handles loading/empty/error/offline/read-only/conflict states.
- Authoritative records and migrations preserve unknown/future/corrupt data safely.
- Traceability, risk, decision, schema/IPC docs, and phase evidence are updated.
- Rollback is possible and a coherent commit exists.
- Any eligible legacy removal has caller/import/config/test/runtime/package absence proof.

## Phase is Done when

Every assigned work item is Done, release gates pass, performance/security/legal deltas are recorded, no P0 risk is accepted silently, and the phase report links exact test artifacts and commit hashes.

## Planning is complete when

Every known requirement is represented in `REQUIREMENTS_EXECUTION.csv`; every phase has work, artifacts, dependencies, tests, risks, and exit gates; exact schemas/IPC/state models exist; open product decisions are zero; and all remaining uncertainty is an implementation proof with a named owner and failure path.
