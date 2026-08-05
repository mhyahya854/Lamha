# SQLite authority

`001_initial.sql` is executable DDL. `entity-authority.csv` identifies which tables are authoritative transaction state and which are rebuildable indexes. SQLite must never become the only durable copy of user knowledge designated as file-authoritative.
