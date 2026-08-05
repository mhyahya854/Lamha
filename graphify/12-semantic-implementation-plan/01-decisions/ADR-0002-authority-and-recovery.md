# ADR-0002: Local authority and recovery

Status: Accepted.

Rust is the privileged local authority. Versioned files hold durable user knowledge; SQLite holds transactional and rebuildable indexes according to `entity-authority.csv`. Destructive operations require plan/commit separation, explicit authorization, journaling, and recovery evidence.
