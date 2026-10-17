-- Compare these figures with the report with all slicers cleared.
SELECT
    COUNT(*) AS playback_events,
    ROUND(SUM(listening_duration_ms) / 3600000.0, 2) AS listening_hours,
    COUNT(DISTINCT track_key) AS unique_tracks,
    ROUND(COUNT(*) FILTER (WHERE is_skipped) * 100.0 / NULLIF(COUNT(*), 0), 2)
        AS skip_rate_percent,
    COUNT(*) FILTER (WHERE has_listening_date) AS dated_events,
    COUNT(*) FILTER (WHERE NOT has_listening_date) AS undated_events,
    ROUND(COUNT(*) FILTER (WHERE has_listening_date) * 100.0 / NULLIF(COUNT(*), 0), 2)
        AS date_coverage_percent
FROM analytics.powerbi_listening_events;

-- Charts by month intentionally use dated events only.
SELECT
    listening_month,
    COUNT(*) AS playback_events,
    ROUND(SUM(listening_duration_ms) / 3600000.0, 2) AS listening_hours,
    ROUND(COUNT(*) FILTER (WHERE is_skipped) * 100.0 / NULLIF(COUNT(*), 0), 2)
        AS skip_rate_percent
FROM analytics.powerbi_listening_events
WHERE has_listening_date
GROUP BY listening_month
ORDER BY listening_month;
