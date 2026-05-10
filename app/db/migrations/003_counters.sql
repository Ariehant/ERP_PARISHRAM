-- 003_counters.sql -- atomic counter for receipt numbers and similar.
-- Increment with INSERT ... ON CONFLICT DO UPDATE inside a transaction
-- so two concurrent writers can't allocate the same value.

CREATE TABLE counters (
    name TEXT PRIMARY KEY,
    value INTEGER NOT NULL DEFAULT 0
);
