SELECT
    COUNT(*) AS total_rows,

    COUNT(*) FILTER (
        WHERE is_listening_event
    ) AS listening_events,

    COUNT(*) FILTER (
        WHERE is_skipped
    ) AS skipped_events,

    COUNT(*) FILTER (
        WHERE is_natural_end
    ) AS natural_end_events,

    COUNT(*) FILTER (
        WHERE song_name IS NULL
    ) AS missing_song_names,

    COUNT(*) FILTER (
        WHERE listening_duration_ms IS NULL
    ) AS missing_durations

FROM listening_events;


SELECT
    duration_quality,
    COUNT(*) AS event_count,

    ROUND(
        COUNT(*) * 100.0
        / SUM(COUNT(*)) OVER (),
        2
    ) AS percentage

FROM listening_events

GROUP BY duration_quality
ORDER BY event_count DESC;


SELECT
    MIN(event_timestamp_utc) AS earliest_event,
    MAX(event_timestamp_utc) AS latest_event

FROM listening_events;


SELECT
    repeat_play,
    shuffle_play,
    COUNT(*) AS event_count

FROM listening_events

GROUP BY
    repeat_play,
    shuffle_play

ORDER BY event_count DESC;