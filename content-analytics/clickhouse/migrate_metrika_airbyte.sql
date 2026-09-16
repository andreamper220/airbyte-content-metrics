-- Airbyte 2.x ClickHouse destination requires its own metadata columns.
-- Drop legacy hand-made table so the next sync can recreate raw_metrika_sessions.

DROP TABLE IF EXISTS analytics.raw_metrika_sessions;
