from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_FILE = PROJECT_ROOT / "data" / "raw" / "Apple Music Play Activity.csv"
OUTPUT_FILE = (
    PROJECT_ROOT / "data" / "processed" / "listening_events.parquet"
)
CHUNK_SIZE = 10_000

SOURCE_COLUMNS = [
    "Event ID",
    "Event Type",
    "Event Timestamp",
    "Event Start Timestamp",
    "Event End Timestamp",
    "UTC Offset In Seconds",
    "Song Name",
    "Album Name",
    "Media Type",
    "Device Type",
    "Client Platform",
    "Source Type",
    "End Reason Type",
    "Media Duration In Milliseconds",
    "Play Duration Milliseconds",
    "Offline",
    "Repeat Play",
    "Shuffle Play",
]

COLUMN_NAMES = {
    "Event ID": "event_id",
    "Event Type": "event_type",
    "Event Timestamp": "event_timestamp_utc",
    "Event Start Timestamp": "event_start_timestamp_utc",
    "Event End Timestamp": "event_end_timestamp_utc",
    "UTC Offset In Seconds": "utc_offset_seconds",
    "Song Name": "song_name",
    "Album Name": "album_name",
    "Media Type": "media_type",
    "Device Type": "device_type",
    "Client Platform": "client_platform",
    "Source Type": "source_type",
    "End Reason Type": "end_reason",
    "Media Duration In Milliseconds": "media_duration_ms",
    "Play Duration Milliseconds": "original_play_duration_ms",
    "Offline": "offline",
    "Repeat Play": "repeat_play",
    "Shuffle Play": "shuffle_play",
}


def clean_chunk(chunk):
    cleaned = chunk.loc[chunk["Event Type"] == "PLAY_END"].copy()
    cleaned = cleaned.rename(columns=COLUMN_NAMES)

    text_columns = [
        "event_id",
        "song_name",
        "album_name",
        "media_type",
        "device_type",
        "client_platform",
        "source_type",
        "end_reason",
    ]

    for column in text_columns:
        cleaned[column] = cleaned[column].astype("string").str.strip()

    timestamp_columns = [
        "event_timestamp_utc",
        "event_start_timestamp_utc",
        "event_end_timestamp_utc",
    ]

    for column in timestamp_columns:
        cleaned[column] = pd.to_datetime(
            cleaned[column],
            errors="coerce",
            utc=True,
            format="mixed",
        )

    numeric_columns = [
        "utc_offset_seconds",
        "media_duration_ms",
        "original_play_duration_ms",
    ]

    for column in numeric_columns:
        cleaned[column] = pd.to_numeric(
            cleaned[column],
            errors="coerce",
        )

    timestamp_duration = (
        cleaned["event_end_timestamp_utc"]
        - cleaned["event_start_timestamp_utc"]
    ).dt.total_seconds() * 1000

    cleaned["listening_duration_ms"] = timestamp_duration.where(
        timestamp_duration >= 0
    )

    cleaned["event_timestamp_local"] = (
        cleaned["event_timestamp_utc"]
        + pd.to_timedelta(
            cleaned["utc_offset_seconds"],
            unit="s",
        )
    ).dt.tz_localize(None)

    cleaned["duration_exceeds_media"] = (
        cleaned["listening_duration_ms"].notna()
        & cleaned["media_duration_ms"].gt(0)
        & cleaned["listening_duration_ms"].gt(
            cleaned["media_duration_ms"]
        )
    )

    cleaned["duration_quality"] = "valid"

    cleaned.loc[
        cleaned["listening_duration_ms"].isna(),
        "duration_quality",
    ] = "missing_or_invalid_timestamp"

    cleaned.loc[
        cleaned["listening_duration_ms"].isna()
        & cleaned["original_play_duration_ms"].lt(0),
        "duration_quality",
    ] = "negative_original_and_missing_timestamp"

    cleaned.loc[
        cleaned["duration_exceeds_media"],
        "duration_quality",
    ] = "exceeds_media"

    cleaned["completion_percent"] = float("nan")

    valid_completion = (
        cleaned["listening_duration_ms"].notna()
        & cleaned["media_duration_ms"].gt(0)
    )

    cleaned.loc[
        valid_completion,
        "completion_percent",
    ] = (
        cleaned.loc[valid_completion, "listening_duration_ms"]
        / cleaned.loc[valid_completion, "media_duration_ms"]
        * 100
    ).clip(lower=0, upper=100)

    cleaned["completion_percent"] = (
        cleaned["completion_percent"].round(2)
    )

    cleaned["is_natural_end"] = (
        cleaned["end_reason"] == "NATURAL_END_OF_TRACK"
    )

    cleaned["is_skipped"] = cleaned["end_reason"].isin(
        [
            "TRACK_SKIPPED_FORWARDS",
            "TRACK_SKIPPED_BACKWARDS",
        ]
    )

    cleaned["is_listening_event"] = (
        cleaned["end_reason"].ne("SCRUB_END")
        & cleaned["listening_duration_ms"].gt(0)
    )

    return cleaned


def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"File not found: {INPUT_FILE}")

    cleaned_chunks = []
    seen_event_ids = set()

    raw_rows = 0
    play_end_rows = 0
    duplicate_rows = 0
    missing_id_rows = 0

    for chunk_number, chunk in enumerate(
        pd.read_csv(
            INPUT_FILE,
            usecols=SOURCE_COLUMNS,
            chunksize=CHUNK_SIZE,
            low_memory=False,
        ),
        start=1,
    ):
        raw_rows += len(chunk)

        cleaned = clean_chunk(chunk)
        play_end_rows += len(cleaned)

        missing_id = (
            cleaned["event_id"].isna()
            | cleaned["event_id"].eq("")
        )

        missing_id_rows += int(missing_id.sum())
        cleaned = cleaned.loc[~missing_id].copy()

        duplicate_id = (
            cleaned["event_id"].duplicated(keep="first")
            | cleaned["event_id"].isin(seen_event_ids)
        )

        duplicate_rows += int(duplicate_id.sum())
        cleaned = cleaned.loc[~duplicate_id].copy()

        seen_event_ids.update(cleaned["event_id"].tolist())
        cleaned_chunks.append(cleaned)

        print(
            f"Processed chunk {chunk_number}: "
            f"{raw_rows:,} raw rows"
        )

    listening_events = pd.concat(
        cleaned_chunks,
        ignore_index=True,
    )

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    listening_events.to_parquet(
        OUTPUT_FILE,
        index=False,
    )

    print("\nETL summary")
    print(f"- Raw rows read: {raw_rows:,}")
    print(f"- PLAY_END rows found: {play_end_rows:,}")
    print(f"- Missing Event IDs removed: {missing_id_rows:,}")
    print(f"- Duplicate Event IDs removed: {duplicate_rows:,}")
    print(f"- Cleaned rows written: {len(listening_events):,}")
    print(
        f"- Listening events: "
        f"{listening_events['is_listening_event'].sum():,}"
    )
    print(
        f"- Invalid durations: "
        f"{listening_events['listening_duration_ms'].isna().sum():,}"
    )
    print(f"- Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()