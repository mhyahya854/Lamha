# Graphify refresh validation

## Refresh boundary

- Installed Graphify: **0.9.17**.
- Source snapshot: `C:\Users\mhyah\Downloads\Code\Lamha\Codebase`.
- Baseline manifest: **3,697 files**, SHA-256 `1859D2B7A946CD1D5EF2193CF5D322F933C853CF09DBD212A8390163AA1F4D88`.
- External semantic backend/model: **none**.
- Refresh mode: deep local AST extraction, code-only, no clustering, forced rescan.
- Output/cache roots: unique OS temporary directories outside `Codebase/`.

## Reproducibility result

Two independent refresh invocations—one with the absolute corpus path and one with `..\Codebase` from the Graphify working directory—both produced:

- **34,281 nodes**
- **69,753 edges**
- **2,922 detected code files**
- **128 supported code/config files with zero emitted AST nodes**

The preserved pre-refresh raw extraction for the byte-identical source snapshot contains:

- **34,595 nodes**
- **70,890 edges**

## Shrink investigation

The refreshed extractor assigned basename-only identities to many external-file nodes. The preserved extraction used repository-path-qualified identities.

- Preserved-only node IDs: **2,834**
- Refresh-only node IDs: **2,520**
- Net node loss from basename collisions: **314**
- `defines` edges: **19,354** in both
- `calls` edges: **3,447** in both
- `contains` edges: **5,397** in both
- `imports_from` edges: **9,497 preserved / 8,482 refreshed**
- `imports` edges: **11,030 preserved / 10,935 refreshed**

The shrink is therefore an extractor identity/import-resolution regression, not a source deletion. Accepting it would collapse distinct same-named files and discard directed dependency evidence.

## Evidence-preserving decision

The refreshed smaller graph was **not** copied over `graph.raw.json`. The preserved higher-fidelity raw extraction remains the directed-build input because:

1. `Codebase/` is byte-identical to its baseline.
2. Both refreshes reproduce the same basename-collision shrink.
3. The preserved graph has path-qualified external-file identities and strictly more import evidence.
4. The canonical augmentation independently adds one verified file node for every inventory path and validates all endpoints.

This decision is not a claim that Graphify 0.9.17 is deterministic across extractor identity strategies. The limitation remains visible and no deletion planning relies on inferred or basename-collapsed edges.
