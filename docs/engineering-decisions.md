# Engineering Decisions and Tradeoffs

## Exact checks for completely missing columns

### Problem

The first profiling version rounded missing percentages to two decimal places. `Source Radio Type` had 278,221 missing values out of 278,231 rows, so it displayed as 100.0% missing even though 10 valid values existed.

### Risk

Using the rounded percentage to remove empty columns could delete a column that still contains valid data.

### Decision

The profiler now records:

- Exact missing count
- Exact non-missing count
- Missing percentage to four decimal places
- An `all_missing` boolean based on exact row counts

Percentages are only used for reporting. Column-removal decisions use the exact `all_missing` value.

### Verification

`Source Radio Type` now reports:

- Missing: 278,221
- Non-missing: 10
- Missing percentage: 99.9964%
- Completely missing: False

## Choosing the listening-event grain

### Problem

The raw file contains PLAY_START, PLAY_END, and LYRIC_DISPLAY rows. Counting every row as a song play would inflate the listening metrics.

### Evidence

- PLAY_END: 172,899 rows with duration and end reason available for 100% of rows
- PLAY_START: 103,200 rows with no positive play duration and no end reason
- LYRIC_DISPLAY: 2,132 lyric interactions
- PLAY_START contains 117 duplicate Event IDs
- PLAY_START and PLAY_END share zero Event IDs

### Decision

One row in the main listening-events dataset will represent one unique PLAY_END event.

PLAY_START and LYRIC_DISPLAY rows will not be included in the main listening fact table. They will remain in the private raw data for auditing.

Zero-duration PLAY_END rows will be kept until their end reasons and duration patterns are investigated.

## Handling unreliable listening durations

### Problem

`Play Duration Milliseconds` cannot always be treated as listening time. The dataset contains 5,972 negative durations and 2,378 durations longer than the song length.

### Investigation

The negative values closely match backward position changes. Every negative play-duration row is also missing a usable timestamp difference.

Of the 5,972 affected rows, 5,519 have the `SCRUB_END` reason, showing that most negative values come from timeline navigation rather than actual negative listening time.

### Decision

The cleaned pipeline will:

- Use the difference between Event End Timestamp and Event Start Timestamp as the main listening duration
- Keep the original duration fields for auditing
- Set listening duration to null when the timestamp difference is unavailable and the original duration is negative
- Add a data-quality flag to these rows
- Keep SCRUB_END records but exclude them from listening-time and play-count analytics
- Keep durations longer than the media length and flag them for review instead of automatically deleting them

Unknown duration will remain null rather than being changed to zero.