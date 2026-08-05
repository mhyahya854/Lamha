# Graph Report — Lamha Phase 1

## Invocation and boundary

- Installed Graphify: **0.9.17** (`uv tool graphifyy`).
- Refresh invocations from `graphify/`: `graphify extract <absolute Codebase> --mode deep --code-only --out <OS temp> --no-cluster --force --timing` and the same command with `../Codebase`.
- Both refresh detector/AST cache and raw-output roots resolved to unique OS temporary directories; canonical evidence resolves under `graphify/`; nothing resolved under `Codebase/`.
- No semantic backend/model/key was selected. The local AST pass detected 2,922 code files and explicitly skipped 261 documents plus 336 images; 170 additional files were unclassified by Graphify. The canonical inventory adds file nodes and curated classifications/dispositions for every one of 3,697 corpus files.
- Both fresh CLI runs produced 34,281 nodes / 69,753 edges but collapsed path-qualified external-file identities to basenames. The byte-identical snapshot's preserved raw graph has 34,595 nodes / 70,890 edges and strictly more import evidence, so the smaller refresh was not accepted. `GRAPHIFY_REFRESH_VALIDATION.md` records the full comparison.
- Internal Graphify `build_from_json(..., directed=True)` over the preserved path-qualified raw graph produced 65,397 directed deduplicated edges before curation.
- Semantic token cost: **0 input / 0 output tokens; estimated cost $0.00**.

## Incremental support

`manifest.json` records content hashes for 2,922 detected code files from the unchanged snapshot. Future runs use `graphify update`/incremental extraction only after preserving curated augmentation or rerunning this generator. `graph.raw.json` is the preserved path-qualified raw extraction; `graph.json` is the canonical augmented directed map. A future Graphify version may replace the raw graph only after its refresh passes the no-shrink/path-identity comparison in `GRAPHIFY_REFRESH_VALIDATION.md`.
