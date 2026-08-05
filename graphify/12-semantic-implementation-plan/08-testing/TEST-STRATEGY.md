# Test strategy

Each work package supplies focused success, boundary, invalid-input, authorization, concurrency/revision, cancellation, I/O-failure, rollback, and recovery checks as applicable. Contract schemas are meta-validated; SQLite DDL executes in memory; dependency and reference integrity are checked globally. Twelve adversarial fixtures prove the validator rejects every final-blocker defect class.
