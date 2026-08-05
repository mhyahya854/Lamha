# Job and queue architecture

`server/src/repositories/job.repository.ts:1-4` imports BullMQ and queue tokens; it creates workers, controls concurrency, pauses/resumes/drains queues, enqueues jobs, and waits for completion. Redis configuration is assembled in `server/src/repositories/config.repository.ts`; decorated job handlers are distributed across services/workers. The web admin queue/job routes are consumers.

Target: replace Redis/BullMQ with an in-process durable local scheduler whose authoritative/recoverable state is represented in transparent operation/task records and whose derived working state may be indexed in SQLite. Keep retry, cancellation, progress, invalidation, and crash recovery; remove distributed-server semantics.
