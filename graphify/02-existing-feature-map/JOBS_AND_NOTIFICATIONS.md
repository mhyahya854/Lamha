# Jobs and notifications

Background processing state, progress, retry/cancel, and desktop notifications.

## Current verified evidence

| Current path/line | Symbol | Evidence | Graph node | Action |
|---|---|---|---|---|
| `Codebase/web/src/routes/admin/queues/+page.ts:L1-L1` | `queues/+page.ts` | EXTRACTED | `ext_codebase_web_src_routes_admin_queues_page_ts` | REPLACE |
| `Codebase/web/src/routes/admin/queues/+page.svelte:L1-L1` | `queues/+page.svelte` | EXTRACTED | `ext_codebase_web_src_routes_admin_queues_page_svelte` | REPLACE |
| `Codebase/web/src/routes/admin/jobs-status/+page.ts:L1-L1` | `jobs-status/+page.ts` | EXTRACTED | `ext_codebase_web_src_routes_admin_jobs_status_page_ts` | REPLACE |
| `Codebase/web/src/routes/admin/queues/[name]/+page.ts:L1-L1` | `[name]/+page.ts` | EXTRACTED | `ext_codebase_web_src_routes_admin_queues_name_page_ts` | REPLACE |
| `Codebase/web/src/routes/admin/queues/QueueCard.svelte:L1-L1` | `./QueueCard.svelte` | EXTRACTED | `ext_codebase_web_src_routes_admin_queues_queuecard_svelte` | REPLACE |
| `Codebase/web/src/routes/admin/queues/QueuePanel.svelte:L1-L1` | `QueuePanel.svelte` | EXTRACTED | `ext_codebase_web_src_routes_admin_queues_queuepanel_svelte` | REPLACE |
| `Codebase/web/src/routes/admin/queues/[name]/+page.svelte:L1-L1` | `[name]/+page.svelte` | EXTRACTED | `ext_codebase_web_src_routes_admin_queues_name_page_svelte` | REPLACE |
| `Codebase/web/src/routes/admin/queues/QueueCardBadge.svelte:L1-L1` | `QueueCardBadge.svelte` | EXTRACTED | `ext_codebase_web_src_routes_admin_queues_queuecardbadge_svelte` | REPLACE |
| `Codebase/web/src/routes/admin/queues/QueueCardButton.svelte:L1-L1` | `QueueCardButton.svelte` | EXTRACTED | `ext_codebase_web_src_routes_admin_queues_queuecardbutton_svelte` | REPLACE |
| `Codebase/web/src/routes/admin/queues/[name]/QueueGraph.svelte:L1-L1` | `QueueGraph.svelte` | EXTRACTED | `ext_codebase_web_src_routes_admin_queues_name_queuegraph_svelte` | REPLACE |

## Current dependency boundary

- Complete pattern-matched production file set: **16**.
- Complete pattern-matched existing test file set: **6**.
- The table shows ten navigation anchors; all matched files and their calls/imports remain in the directed graph and symbol ledger. Deletion-critical edges require source verification and do not rely on inference alone.

## Target decision

- Classification: **REPLACE**.
- Assigned implementation phase: **Phase 10 — Local AI completeness**.
- Target modules: `src-tauri/src/jobs/`, `src-tauri/src/commands/jobs.rs`, `src-tauri/src/notifications/`.
- Proof: focused behavior tests, affected regression tests, desktop build/launch when applicable, and requirement-linked evidence before any current subsystem is removed.
