# Process and service map

| Process/boundary | Entrypoints | Responsibility |
|---|---|---|
| Browser | web/src/routes/+layout.svelte; web/src/routes/(user)/+layout.svelte | SvelteKit layouts and route tree |
| API | server/src/main.ts; server/src/app.module.ts; server/src/controllers/ | NestJS HTTP/WebSocket application |
| Microservices/jobs | server/src/workers/; server/src/repositories/job.repository.ts | BullMQ workers backed by Redis |
| ML | machine-learning/immich_ml/__main__.py; machine-learning/immich_ml/main.py | Gunicorn/Uvicorn FastAPI inference service |
| Mobile | mobile/lib/main.dart; mobile/lib/ | Flutter client, sync, backup, generated API |
| Deployment | docker/; docker-compose.yml; deployment/ | Container and cloud/server deployment |

All processes above are current evidence. The target retains one desktop process plus a supervised local AI child process; no current process is silently treated as target architecture.
