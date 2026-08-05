# SUPERSEDED — DO NOT EXECUTE

This historical package is provenance only. The sole active authority is `../12-semantic-implementation-plan/`, and implementation begins at I0. Do not follow any Phase-2-first instruction below.

# Lamha implementation-ready planning package (historical)

## Authority and purpose

This directory is the **binding Phase 1 execution addendum** to the three existing Master Plans. It is not a fourth Master Plan and does not replace product intent. It converts the existing product specification and repository map into implementation contracts concrete enough for Codex or a human team to execute without inventing product behaviour.

Authority order during implementation:

1. The three files in `graphify/Master Plan/` for product intent, invariants, retained/deleted behaviour, and governance.
2. This directory for implementation sequencing, schemas, IPC, security, tests, release budgets, and exact engineering decisions.
3. `REQUIREMENTS_EXECUTION.csv` for executable requirement-to-phase assignment.
4. Existing Graphify maps for current-code evidence and legacy dependency discovery.
5. Actual source code and tests for implementation details that do not contradict 1–4.

When a lower source conflicts with a higher source, stop only the affected work item, record the conflict in `20-OPEN-DECISIONS.md`, and continue independent work.

## Corrected status

The previous package proved **mapping completeness**, not implementation readiness. This addendum closes the missing planning layers and corrects the generated phase-assignment defect. Original requirement rows: **2083**. Rows whose primary execution phase changed: **1228**. Every phase from 0 through 16 now has an explicit outcome, backlog, proof contract, and release role.

## Start here

1. Read `01-PLANNING-GAP-AUDIT.md`.
2. Read `02-DECISION-REGISTER.md` and `03-RELEASE-SCOPE.md`.
3. Execute phases from `04-WORK-BREAKDOWN-STRUCTURE.md`.
4. Use `REQUIREMENTS_EXECUTION.csv`, not the old `ImplementationPhase` column, for execution order.
5. Use `17-CODEX-EXECUTION-PROMPT.md` to begin a controlled Codex run.

## Definition of “100% planned”

“100% planned” means every known requirement has a destination, dependency, implementation phase, data authority, interface contract, failure behaviour, test proof, and release gate. It does **not** mean implementation is complete, unknown implementation discoveries are impossible, or the unexecuted legacy baseline already passes.
