# Search and OCR

Text/semantic search, filters, OCR extraction, and local result ranking.

## Current verified evidence

| Current path/line | Symbol | Evidence | Graph node | Action |
|---|---|---|---|---|
| `Codebase/web/src/routes/(user)/search/[[photos=photos]]/[[assetId=id]]/+page.ts:L1-L1` | `search/[[photos=photos]]/[[assetId=id]]/+page.ts` | EXTRACTED | `ext_codebase_web_src_routes_user_search_photos_photos_assetid_id_page_ts` | REWRITE |
| `Codebase/web/src/routes/(user)/search/[[photos=photos]]/[[assetId=id]]/+page.svelte:L1-L1` | `search/[[photos=photos]]/[[assetId=id]]/+page.svelte` | EXTRACTED | `ext_codebase_web_src_routes_user_search_photos_photos_assetid_id_page_svelte` | REWRITE |
| `Codebase/server/src/services/ocr.service.ts:L1-L1` | `ocr.service.ts` | EXTRACTED | `ext_codebase_server_src_services_ocr_service_ts` | REWRITE |
| `Codebase/server/src/services/search.service.ts:L1-L1` | `search.service.ts` | EXTRACTED | `ext_codebase_server_src_services_search_service_ts` | REWRITE |
| `Codebase/server/src/repositories/ocr.repository.ts:L1-L1` | `ocr.repository.ts` | EXTRACTED | `ext_codebase_server_src_repositories_ocr_repository_ts` | REWRITE |
| `Codebase/server/src/controllers/search.controller.ts:L1-L1` | `search.controller.ts` | EXTRACTED | `ext_codebase_server_src_controllers_search_controller_ts` | REWRITE |
| `Codebase/server/src/repositories/search.repository.ts:L1-L1` | `search.repository.ts` | EXTRACTED | `ext_codebase_server_src_repositories_search_repository_ts` | REWRITE |
| `Codebase/machine-learning/immich_ml/models/clip/visual.py:L1-L1` | `visual.py` | EXTRACTED | `ext_codebase_machine_learning_immich_ml_models_clip_visual_py` | REWRITE |
| `Codebase/machine-learning/immich_ml/models/ocr/schemas.py:L1-L1` | `ocr/schemas.py` | EXTRACTED | `ext_codebase_machine_learning_immich_ml_models_ocr_schemas_py` | REWRITE |
| `Codebase/machine-learning/immich_ml/models/clip/textual.py:L1-L1` | `textual.py` | EXTRACTED | `ext_codebase_machine_learning_immich_ml_models_clip_textual_py` | REWRITE |

## Current dependency boundary

- Complete pattern-matched production file set: **12**.
- Complete pattern-matched existing test file set: **8**.
- The table shows ten navigation anchors; all matched files and their calls/imports remain in the directed graph and symbol ledger. Deletion-critical edges require source verification and do not rely on inference alone.

## Target decision

- Classification: **REWRITE**.
- Assigned implementation phase: **Phase 10 — Local AI completeness**.
- Target modules: `src-tauri/src/index/search.rs`, `src-tauri/src/commands/search.rs`, `ai-worker/search/`, `ai-worker/ocr/`.
- Proof: focused behavior tests, affected regression tests, desktop build/launch when applicable, and requirement-linked evidence before any current subsystem is removed.
