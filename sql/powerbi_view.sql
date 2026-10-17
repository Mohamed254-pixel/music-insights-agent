-- One row per analytics-eligible event. No location, account, or device IDs.
-- Keep undated events: all-time KPIs must not silently drop them.
CREATE OR REPLACE VIEW analytics.powerbi_listening_events AS
SELECT
    event_id,
    event_timestamp_local::DATE AS listening_date,
    DATE_TRUNC('month', event_timestamp_local)::DATE AS listening_month,
    TO_CHAR(event_timestamp_local, 'YYYY-MM') AS month_label,
    (
        EXTRACT(YEAR FROM event_timestamp_local)::INTEGER * 100
        + EXTRACT(MONTH FROM event_timestamp_local)::INTEGER
    ) AS month_sort,
    COALESCE(NULLIF(BTRIM(song_name), ''), 'Unknown Track') AS song_name,
    COALESCE(NULLIF(BTRIM(album_name), ''), 'Unknown Album') AS album_name,
    COALESCE(NULLIF(BTRIM(song_name), ''), 'Unknown Track')
        || ' — ' ||
    COALESCE(NULLIF(BTRIM(album_name), ''), 'Unknown Album') AS track_label,
    -- Encode both fields before hashing to avoid delimiter collisions.
    MD5(JSONB_BUILD_ARRAY(
        COALESCE(NULLIF(BTRIM(song_name), ''), 'Unknown Track'),
        COALESCE(NULLIF(BTRIM(album_name), ''), 'Unknown Album')
    )::TEXT) AS track_key,
    COALESCE(NULLIF(BTRIM(device_type), ''), 'Unknown Device') AS device_type,
    analytics_listening_duration_ms AS listening_duration_ms,
    is_skipped,
    is_natural_end,
    completion_percent,
    (event_timestamp_local IS NOT NULL) AS has_listening_date
FROM analytics.valid_listening_events;
