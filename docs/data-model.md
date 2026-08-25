# Clean Listening Event Data Model

## Dataset Grain

One row represents one unique Apple Music `PLAY_END` event.

`PLAY_START` and `LYRIC_DISPLAY` events are not included in the main cleaned dataset.

## Main Output

The cleaned dataset will be saved as:

`data/processed/listening_events.parquet`

## Main Columns

| Column | Purpose |
|---|---|
| event_id | Unique event identifier |
| event_timestamp_utc | Main event time in UTC |
| event_start_timestamp_utc | Playback start time |
| event_end_timestamp_utc | Playback end time |
| utc_offset_seconds | Offset used to calculate local time |
| event_timestamp_local | Event time in the listener’s local timezone |
| song_name | Song title |
| album_name | Album title |
| media_type | Type of media |
| device_type | Device used |
| client_platform | Operating platform |
| source_type | How playback started |
| end_reason | Why playback ended |
| media_duration_ms | Full song length |
| original_play_duration_ms | Original Apple duration value |
| listening_duration_ms | Cleaned listening duration |
| completion_percent | Percentage of the song played |
| is_natural_end | Song reached its natural ending |
| is_skipped | User explicitly skipped forward or backward |
| is_listening_event | Row counts toward listening analytics |
| duration_quality | Valid, missing, negative, or unusual duration |
| duration_exceeds_media | Listening duration is longer than song length |

## Cleaning Rules

1. Keep only `PLAY_END` rows.
2. Require a unique Event ID.
3. Keep the first record if a duplicate Event ID appears.
4. Log all removed duplicates.
5. Use timestamp difference as the main listening duration.
6. Set duration to null when timestamps are missing and the original duration is negative.
7. Keep `SCRUB_END` rows for auditing but do not count them as listening events.
8. Do not automatically delete durations longer than the song length.
9. Flag unusual durations for review.
10. Keep the original duration fields for auditing.

## Analytics Rules

A row counts as a listening event when:

- End reason is not `SCRUB_END`
- Cleaned listening duration is greater than zero

A row is marked as skipped when the end reason is:

- `TRACK_SKIPPED_FORWARDS`
- `TRACK_SKIPPED_BACKWARDS`

A row is marked as a natural completion when the end reason is:

- `NATURAL_END_OF_TRACK`

Completion percentage is calculated as:

`listening duration / media duration × 100`

The reporting version of completion percentage will be capped at 100%, while the original value is kept for auditing.

## Privacy Rules

The cleaned dataset will remove private fields such as:

- Apple ID
- IP address
- City, region, latitude, and longitude
- Device identifiers
- Subscription user IDs
- House ID
- Network information
- Other personal account identifiers

## Data Quality

Rows will be preserved when possible and marked with quality flags. Unknown values will remain null instead of being replaced with made-up values.