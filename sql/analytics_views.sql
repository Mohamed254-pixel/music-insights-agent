CREATE SCHEMA IF NOT EXISTS analytics;


CREATE OR REPLACE VIEW
    analytics.valid_listening_events
AS

SELECT
    events.*,

    CASE
        WHEN media_duration_ms > 0
        THEN LEAST(
            listening_duration_ms,
            media_duration_ms
        )

        ELSE listening_duration_ms
    END AS analytics_listening_duration_ms

FROM listening_events AS events

WHERE is_listening_event
  AND listening_duration_ms IS NOT NULL
  AND listening_duration_ms > 0;


CREATE OR REPLACE VIEW
    analytics.monthly_listening
AS

SELECT
    DATE_TRUNC(
        'month',
        event_timestamp_local
    )::DATE AS listening_month,

    COUNT(*) AS listening_events,

    COUNT(
        DISTINCT song_name
    ) AS unique_tracks,

    ROUND(
        SUM(analytics_listening_duration_ms)
        / 60000.0,
        2
    ) AS listening_minutes,

    COUNT(*) FILTER (
        WHERE is_skipped
    ) AS skipped_events,

    ROUND(
        COUNT(*) FILTER (
            WHERE is_skipped
        ) * 100.0
        / NULLIF(COUNT(*), 0),
        2
    ) AS skip_rate_percent,

    COUNT(*) FILTER (
        WHERE is_natural_end
    ) AS natural_end_events,

    ROUND(
        COUNT(*) FILTER (
            WHERE is_natural_end
        ) * 100.0
        / NULLIF(COUNT(*), 0),
        2
    ) AS natural_end_rate_percent

FROM analytics.valid_listening_events

WHERE event_timestamp_local IS NOT NULL

GROUP BY
    DATE_TRUNC(
        'month',
        event_timestamp_local
    )::DATE;


CREATE OR REPLACE VIEW
    analytics.track_summary
AS

SELECT
    COALESCE(
        song_name,
        'Unknown Track'
    ) AS song_name,

    COALESCE(
        album_name,
        'Unknown Album'
    ) AS album_name,

    COUNT(*) AS listening_events,

    ROUND(
        SUM(analytics_listening_duration_ms)
        / 60000.0,
        2
    ) AS listening_minutes,

    ROUND(
        AVG(completion_percent),
        2
    ) AS average_completion_percent,

    COUNT(*) FILTER (
        WHERE is_skipped
    ) AS skipped_events,

    ROUND(
        COUNT(*) FILTER (
            WHERE is_skipped
        ) * 100.0
        / NULLIF(COUNT(*), 0),
        2
    ) AS skip_rate_percent,

    MAX(
        event_timestamp_local
    ) AS last_listened_at

FROM analytics.valid_listening_events

GROUP BY
    COALESCE(
        song_name,
        'Unknown Track'
    ),

    COALESCE(
        album_name,
        'Unknown Album'
    );


CREATE OR REPLACE VIEW
    analytics.device_summary
AS

SELECT
    COALESCE(
        NULLIF(
            BTRIM(device_type),
            ''
        ),
        'Unknown Device'
    ) AS device_type,

    COUNT(*) AS listening_events,

    ROUND(
        SUM(analytics_listening_duration_ms)
        / 60000.0,
        2
    ) AS listening_minutes,

    COUNT(*) FILTER (
        WHERE is_skipped
    ) AS skipped_events,

    ROUND(
        COUNT(*) FILTER (
            WHERE is_skipped
        ) * 100.0
        / NULLIF(COUNT(*), 0),
        2
    ) AS skip_rate_percent,

    MIN(
        event_timestamp_local
    ) AS first_used_at,

    MAX(
        event_timestamp_local
    ) AS last_used_at

FROM analytics.valid_listening_events

GROUP BY
    COALESCE(
        NULLIF(
            BTRIM(device_type),
            ''
        ),
        'Unknown Device'
    );