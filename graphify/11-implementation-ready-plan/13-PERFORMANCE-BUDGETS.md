# Performance budgets v1.0

These are release targets, not measured claims. Phase 14 may amend them only with recorded hardware, method, user impact, and product-owner approval.

## Reference hardware

- **H1 Minimum:** 4 physical CPU cores / 8 threads, 16 GB RAM, integrated graphics, SATA/NVMe SSD.
- **H2 Recommended:** 8 cores / 16 threads, 32 GB RAM, supported mid-range GPU, NVMe SSD.
- **H3 Large-library:** 12+ cores, 32–64 GB RAM, supported GPU, NVMe SSD.

## Interactive budgets

| Operation | 10k H1 | 50k H2 | 100k H3 |
|---|---:|---:|---:|
| Warm app-to-interactive | ≤ 3 s | ≤ 5 s | ≤ 8 s |
| Cold app-to-interactive | ≤ 8 s | ≤ 12 s | ≤ 20 s |
| Timeline initial visible page | ≤ 1.0 s | ≤ 1.5 s | ≤ 2.0 s |
| Metadata/filter search p95 | ≤ 250 ms | ≤ 400 ms | ≤ 600 ms |
| OCR text search p95 after indexing | ≤ 400 ms | ≤ 700 ms | ≤ 1.0 s |
| Viewer navigation to cached preview p95 | ≤ 250 ms | ≤ 300 ms | ≤ 400 ms |
| Mind-map scoped view (≤2k visible nodes) | ≤ 1.5 s | ≤ 2.0 s | ≤ 3.0 s |
| UI input response during background jobs p95 | ≤ 100 ms | ≤ 100 ms | ≤ 150 ms |

## Resource budgets

- UI never loads the full asset list; all major lists are virtualized and paginated.
- Idle CPU after stabilization: ≤ 1% average over 60 seconds on H2, excluding active watchers with incoming changes.
- Memory after opening a 100k library and browsing for 10 minutes: target ≤ 2.5 GB on H3, with no unbounded growth across repeated route/viewer cycles.
- Background jobs are pauseable/cancellable where specified and use bounded queues.
- Initial scan and AI throughput are reported rather than universally fixed, but progress must remain honest, resumable, and must not violate interaction/memory budgets.
- Any regression over 15% from the latest accepted baseline requires investigation; over 25% blocks release unless explicitly waived with user-impact evidence.
