# Ponytail audit run log

## Installed mode

- Skill: `ponytail-audit`.
- Installation form: local skill instructions; no executable or version metadata is provided, so no version is invented.
- Read instructions: `ponytail-audit/SKILL.md` and the referenced `ponytail-review/SKILL.md` format/tag contract.
- Mode: whole-repository, one-shot, read-only audit.
- Fix/apply/patch/format/refactor/delete/dependency modes: none exist in the installed audit skill and none were used.
- Cache/temp path: none; the skill performs source inspection and emits this report only.

## Scope and limitations

- Scope inspected: the complete 3,697-file inventory, directed Graphify graph, current server/web/mobile/ML/deployment/generated boundaries, current tests, and target planning maps.
- Ponytail scope is over-engineering and complexity only. It does not author correctness, security, performance, data-loss, legal, or test-gap conclusions; those are covered by separate Graphify audits.
- Ponytail cannot consume Graphify through a dedicated executable interface. Graph nodes/edges and curated counts were used as inspection evidence, then every finding was source-checked in `PONYTAIL_RECONCILIATION.md`.

## Evidence counts

- Non-test server controllers: **39**.
- services extending `BaseService`: **47**.
- non-test repositories: **51**.
- web files importing `@immich/sdk`: **330**.
- auth-route files: **20**.
- admin-route files: **66**.
- shared-link-route files: **10**.
- Current runtime evidence: NestJS/PostgreSQL/Redis/BullMQ dependencies in `server/package.json`; BullMQ construction in `server/src/repositories/job.repository.ts`; Redis construction in `server/src/repositories/app.repository.ts`; FastAPI/File/Form in `machine-learning/immich_ml/main.py`; Gunicorn/Uvicorn launch in `machine-learning/immich_ml/__main__.py`.

## Net estimate method

The audit contract requires a final `net:` estimate. The reported **578,461 lines / 198 dependencies** is a computed gross upper bound for the current target-dead surface, not an immediate deletion authorization and not achieved savings:

- Unique selected paths: `server/`, `mobile/`, `open-api/`, `packages/sdk/`, `deployment/`, `docker/`, root Docker Compose files, and auth/admin/shared-link route trees.
- UTF-8 text files counted: **2,262**.
- Binary files excluded from line counting: **136**.
- Dependency candidates: unique server `dependencies`/`devDependencies`/`optionalDependencies` plus mobile `dependencies`/`dev_dependencies`.
- Replacement code and dependencies are not yet implemented and therefore cannot be subtracted. Every cut remains conditional on Graphify’s replacement-before-removal gates.

## Mutation result

Ponytail changed no source, test, configuration, dependency, or Master Plan file. It wrote only `PONYTAIL_AUDIT.md` and this run log under `Graphify/graphify-out/ponytail/`.
