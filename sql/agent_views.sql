-- Additive agent surface: no changes to ETL or Power BI definitions.
-- The view owner resolves underlying permissions; the agent gets no base access.
CREATE SCHEMA IF NOT EXISTS agent_analytics;
REVOKE ALL ON SCHEMA agent_analytics FROM PUBLIC;
CREATE OR REPLACE VIEW agent_analytics.listening_events
WITH (security_barrier = true) AS
SELECT listening_date, song_name, album_name, device_type,
       listening_duration_ms, is_skipped
FROM analytics.powerbi_listening_events;
REVOKE ALL ON agent_analytics.listening_events FROM PUBLIC;
