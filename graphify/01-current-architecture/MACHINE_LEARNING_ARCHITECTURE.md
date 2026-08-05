# Machine-learning architecture

Current ML is a Python 3.11 FastAPI application (`immich_ml/main.py:152`) launched through Gunicorn/Uvicorn (`immich_ml/__main__.py:34-43`). `predict` is an HTTP upload/form endpoint at `immich_ml/main.py:166`; server access is mediated by `server/src/repositories/machine-learning.repository.ts`. Models cover facial recognition, CLIP vision/text, OCR, and cache/session providers.

| Current path/line | Symbol | Evidence | Graph node | Action |
|---|---|---|---|---|
| `Codebase/server/src/services/smart-info.service.ts:L1-L1` | `smart-info.service.ts` | EXTRACTED | `ext_codebase_server_src_services_smart_info_service_ts` | TEMPORARILY RETAIN |
| `Codebase/server/src/repositories/machine-learning.repository.ts:L1-L1` | `machine-learning.repository.ts` | EXTRACTED | `ext_codebase_server_src_repositories_machine_learning_repository_ts` | TEMPORARILY RETAIN |
| `Codebase/machine-learning/immich_ml/main.py:L1-L1` | `main.py` | EXTRACTED | `c_users_mhyah_downloads_code_lamha_codebase_machine_learning_immich_ml_main_py_c_users_mhyah_downloads_code_lamha_codebase_machine_learning_immich_ml_main_py_f74538` | TEMPORARILY RETAIN |
| `Codebase/machine-learning/immich_ml/config.py:L1-L1` | `config.py` | EXTRACTED | `ext_codebase_machine_learning_immich_ml_config_py` | TEMPORARILY RETAIN |
| `Codebase/machine-learning/immich_ml/schemas.py:L1-L1` | `immich_ml/schemas.py` | EXTRACTED | `ext_codebase_machine_learning_immich_ml_schemas_py` | TEMPORARILY RETAIN |
| `Codebase/machine-learning/immich_ml/__init__.py:L1-L1` | `immich_ml/__init__.py` | EXTRACTED | `ext_codebase_machine_learning_immich_ml_init_py` | TEMPORARILY RETAIN |
| `Codebase/machine-learning/immich_ml/__main__.py:L1-L1` | `__main__.py` | EXTRACTED | `c_users_mhyah_downloads_code_lamha_codebase_machine_learning_immich_ml_main_py_c_users_mhyah_downloads_code_lamha_codebase_machine_learning_immich_ml_main_py_65ccdc` | TEMPORARILY RETAIN |
| `Codebase/machine-learning/immich_ml/log_conf.json:L1-L21` | `log_conf.json` | EXTRACTED | `file::616dfcab6887acc1db53` | TEMPORARILY RETAIN |
| `Codebase/machine-learning/immich_ml/models/base.py:L1-L1` | `base.py` | EXTRACTED | `ext_codebase_machine_learning_immich_ml_models_base_py` | TEMPORARILY RETAIN |
| `Codebase/machine-learning/immich_ml/models/cache.py:L1-L1` | `cache.py` | EXTRACTED | `ext_codebase_machine_learning_immich_ml_models_cache_py` | TEMPORARILY RETAIN |

Target: retain/adapt proven model logic behind a bundled supervised child process. Phase 1 recommends length-prefixed typed messages over child standard input/output because the desktop process already owns worker launch/supervision and the stream is available on Windows, macOS, and Linux without a listener. Named pipes, Unix-domain sockets, and Tauri sidecar-managed communication remain documented alternatives; they require mechanism-specific lifecycle, access-control, packaging, and cancellation proof before replacing the recommendation. Every candidate uses authorized local paths rather than uploaded media bytes, explicit request IDs, progress, cancellation, restart, timeout semantics, and no TCP/UDP listener or HTTP/WebSocket service.
