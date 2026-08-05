# Server architecture

The server is a NestJS/Express application with controllers, services, repositories, DTOs, schema, SQL query modules, middleware, workers, and maintenance commands. The endpoint parser found **245** decorated HTTP operations; exact controller-to-service rows are in `03-dependency-graphs/API_TO_SERVICE_MAP.md`. PostgreSQL, Redis/BullMQ, WebSocket, filesystem/media, and ML HTTP boundaries make the server load-bearing until Phase 3–15 caller migrations pass.

Key anchors: `Codebase/server/src/main.ts`, `Codebase/server/src/app.module.ts`, `Codebase/server/src/controllers/`, `Codebase/server/src/services/`, `Codebase/server/src/repositories/`, `Codebase/server/src/queries/`, and `Codebase/server/src/workers/`.

Disposition: **TEMPORARILY RETAIN**, then remove each safe subsystem in its assigned phase; Phase 16 is residual eradication and reverification, not an artificial holding phase.
