# Generated, vendor, binary, cache, and sensitive-file policy

## Counted graph policy

| Policy | Files | Treatment |
|---|---:|---|
| Deep/structural map | 3,072 | Source, tests, documentation, configuration, legal, CI, deployment, API-source, and support files |
| File-node/reference map | 180 | Binary/design/UI/font assets: represented by path and dependency references; no unsupported semantic content is fabricated |
| Explicit deep-extraction exclusions | 445 | 444 generated artifacts plus one OS metadata file; source/generator and consumer relationships remain mapped |
| Total snapshot | 3,697 | Every file has one row in `FILE_CLASSIFICATION.csv` |
| Meaningful mapped/file-node corpus | 3,252 | 3,072 mapped files plus 180 file-node assets |

## Generated artifacts

The 444 generated artifacts are:

- 405 files under `mobile/openapi/`, the generated Dart API client and its package metadata/readme
- 37 generated Dart files outside that directory with `.g.dart`, `.gr.dart`, or `.drift.dart` suffixes
- `packages/sdk/src/fetch-client.ts`, the generated TypeScript API client
- `open-api/immich-openapi-specs.json`, produced by the checked-in server OpenAPI synchronization task

Deep semantic duplication is excluded because generator sources, templates, API specification lineage, build tasks, and generated-client consumers are mapped separately. Generated clients remain deletion-critical dependency clusters: Phase 1 records derives-from, imports/consumers, build references, and safe-removal blockers.

## Binary and design assets

The 180 asset-classified files include images, icons, fonts, SVG/design resources, storyboards, and diagrams after test/generated precedence. They receive file nodes and importer/build/package references. Content interpretation is excluded unless a specific requirement depends on the asset’s visual/legal semantics.

## Vendor state

- No `node_modules`, Python virtual environment, package cache, or vendored dependency source tree is present.
- Pinned Git dependencies appear in the mobile manifest; they are external dependency declarations, not checked-in vendor source.
- `e2e/test-assets` is declared as a Git submodule but contains no files in this snapshot. The declaration remains mapped; no absent test assets are fabricated.
- Fonts, model/tool dependencies, codecs, and bundled binaries require Phase 1 licensing traceability even when represented only by manifests/assets.

## OS/build/cache exclusions

- `design/.DS_Store` is the single OS metadata exclusion.
- No build/cache directories were present at baseline.
- Build, test, formatter, coverage, generator, migration, and package commands are not executed in `Codebase/` because they may create such directories or modify checked-in artifacts.

## Markdown classification

All 123 Markdown/MDX files are classified in `MARKDOWN_CLASSIFICATION.csv`: 85 upstream product/architecture/install documents, 18 translated READMEs, 15 package/subsystem READMEs, 3 legal/governance documents, 1 repository workflow document, and 1 generated-client README. All are retained/classified during planning; none is deletion-eligible merely by extension.

## Sensitive paths

Two `.env` files exist in the snapshot. Their contents are not reproduced in planning output. Graphify must apply its sensitive-file skip behaviour while the curated inventory still records their paths and configuration role.

