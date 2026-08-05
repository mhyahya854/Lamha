# Graph Report — Lamha Phase 1

## Invocation and boundary

- Installed Graphify: **0.9.17** (`uv tool graphifyy`).
- Refresh invocations from `graphify/`: `graphify extract <absolute Codebase> --mode deep --code-only --out <OS temp> --no-cluster --force --timing` and the same command with `../Codebase`.
- Both refresh detector/AST cache and raw-output roots resolved to unique OS temporary directories; canonical evidence resolves under `graphify/`; nothing resolved under `Codebase/`.
- No semantic backend/model/key was selected. The local AST pass detected 2,922 code files and explicitly skipped 261 documents plus 336 images; 170 additional files were unclassified by Graphify. The canonical inventory adds file nodes and curated classifications/dispositions for every one of 3,697 corpus files.
- Both fresh CLI runs produced 34,281 nodes / 69,753 edges but collapsed path-qualified external-file identities to basenames. The byte-identical snapshot's preserved raw graph has 34,595 nodes / 70,890 edges and strictly more import evidence, so the smaller refresh was not accepted. `GRAPHIFY_REFRESH_VALIDATION.md` records the full comparison.
- Internal Graphify `build_from_json(..., directed=True)` over the preserved path-qualified raw graph produced 65,397 directed deduplicated edges before curation.
- Semantic token cost: **0 input / 0 output tokens; estimated cost $0.00**.

## Canonical graph

- Nodes: **40959**
- Directed edges: **94180**
- Corpus file-node coverage: **3697/3697**
- Requirement nodes: **2083**
- Feature nodes: **24**
- Self-loops: **0**
- Dangling endpoints: **0**

## Node kinds

| Kind | Count |
|---|---|
| code | 33975 |
| file | 3697 |
| requirement | 2083 |
| concept | 392 |
| endpoint | 245 |
| dependency | 234 |
| type_reference | 91 |
| planned_component | 68 |
| external_reference | 48 |
| rationale | 46 |
| feature | 24 |
| bash_entrypoint | 18 |
| area | 17 |
| bash_function | 13 |
| removal | 8 |

## Relations

| Relation | Count |
|---|---|
| defines | 19210 |
| references | 12404 |
| imports | 10518 |
| imports_from | 6148 |
| current_evidence | 6092 |
| contains | 5399 |
| planned_for | 5031 |
| contains_file | 3697 |
| current_test | 3590 |
| calls | 3339 |
| method | 3171 |
| covers_requirement | 2436 |
| inherits | 2144 |
| requires | 2083 |
| implemented_by | 1369 |
| indirect_call | 1210 |
| current_analogue | 1106 |
| implements | 691 |
| mixes_in | 566 |
| calls_client | 556 |
| renders_component | 386 |
| invokes_repository | 352 |
| includes_dependency | 318 |
| reads_writes_database_model | 296 |
| invokes_controller | 245 |
| calls_endpoint | 245 |
| invokes_service | 240 |
| constructs_type | 200 |
| uses | 152 |
| case_of | 144 |
| configures | 144 |
| verified_by | 135 |
| covers_symbol | 135 |
| extends | 98 |
| uses_store | 74 |
| migrates_to | 72 |
| re_exports | 52 |
| rationale_for | 46 |
| blocked_by_retained_caller | 23 |
| exports | 18 |
| dynamic_import | 12 |
| uses_media_processor | 9 |
| navigates | 6 |
| starts_process | 6 |
| invokes_ml_model | 4 |
| enables_subsystem | 3 |
| derives_from_api | 2 |
| invokes_worker | 2 |
| cites | 1 |

## Confidence

| Evidence class | Count |
|---|---|
| EXTRACTED | 84819 |
| INFERRED | 9361 |

## Limitations

- Code symbols/structural edges are local Graphify AST evidence. Curated file, feature, requirement, target, test, and removal edges cite inventory, plans, or exact current sources.
- 128 supported code/config files emitted zero AST symbols; explicit whole-file nodes preserve their coverage.
- Canonical integrity cleanup removed one blank-ID node, three empty-target edges, and 84 isolated external/type tokens with no source-backed relationship; 108 isolated source-backed extracted nodes were attached to their verified canonical file nodes.
- The canonical node-link export is a `MultiDiGraph`: **803** additional same-endpoint relation variants are intentionally preserved. A standard NetworkX node-link round trip preserves all **40959 nodes / 94180 edges**; a simple `DiGraph` would collapse those variants.
- Documents/images were not sent to an external semantic service without authorization. Markdown is exhaustively classified; all other files have file nodes/categories/dispositions. This limits free-form semantic concept extraction but not file/requirement/target traceability.
- Inferred target edges guide implementation and never authorize deletion. Deletion-critical current dependencies require source verification and proof gates.
