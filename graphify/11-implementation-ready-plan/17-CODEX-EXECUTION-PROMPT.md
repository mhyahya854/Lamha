# SUPERSEDED — DO NOT EXECUTE

Use `../12-semantic-implementation-plan/14-handoff/CODEX-BOUNDED-EXECUTION-PROMPT.md`. Implementation begins at I0, one work package at a time.

# Codex execution prompt (historical)

Use the following prompt at the start of implementation:

> You are implementing Lamha from the received repository snapshot. Read all three files under `graphify/Master Plan/` to EOF, then read every file under `graphify/11-implementation-ready-plan/` to EOF. The Master Plans control product intent; the implementation-ready plan controls engineering detail and execution order. Use `REQUIREMENTS_EXECUTION.csv` rather than the old `ImplementationPhase` field.
>
> Begin with Phase 0 only. Do not modify application code until you have initialized an immutable Git baseline, recorded archive hashes and provenance, investigated the mixed 2.7.5/3.0.0 manifest state, documented the empty test-assets submodule, and executed or explicitly classified the legacy baseline in a disposable workspace. Create a Phase 0 report and stop only if a genuine blocker prevents independent work.
>
> For each work package: list requirement IDs and exact files; state the authority/schema/IPC impact; implement no placeholders; add focused and regression tests; run applicable safety/security gates; update Graphify traceability and phase evidence; commit the coherent green change. Never delete a legacy slice before its replacement, caller migration, parity proof, rollback point, and absence scan pass.
>
> If an ambiguity materially changes behaviour, data safety, privacy, or architecture, add it to `20-OPEN-DECISIONS.md` with cited sources and continue unrelated tasks. Do not ask the user to write code or finish the implementation. Do not substitute mock production data, a server, HTTP, cloud service, or simplified schema.
>
> The first implementation action is to produce the exact Phase 0 execution checklist and repository-provenance report. Do not start Phase 2 rebranding until Phase 0 and Phase 1 Entry Gates are green.
