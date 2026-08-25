from pathlib import Path
import pandas as pd 

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_FILE = PROJECT_ROOT / "data" / "raw" / "Apple Music Play Activity.csv"
CHUNK_SIZE = 10_000

COLUMNS = [
    "Event Type",
    "End Reason Type",
    "Play Duration Milliseconds",
    "Milliseconds Since Play",
    "Media Duration In Milliseconds",
    "Start Position In Milliseconds",
    "End Position In Milliseconds",
    "Event Start Timestamp",
    "Event End Timestamp",
]

play_end_chunks = []

for chunk_number, chunk in enumerate(
    pd.read_csv(
        INPUT_FILE,
        usecols=COLUMNS,
        chunksize=CHUNK_SIZE,
        low_memory=False,
    ),
    start=1,
):
    play_end_chunks.append(
        chunk.loc[chunk["Event Type"] == "PLAY_END"].copy()
    )
    print(f"Processed chunk {chunk_number}")

data = pd.concat(play_end_chunks, ignore_index=True)

numeric_columns = [
    "Play Duration Milliseconds",
    "Milliseconds Since Play",
    "Media Duration In Milliseconds",
    "Start Position In Milliseconds",
    "End Position In Milliseconds",
]

for column in numeric_columns:
    data[column] = pd.to_numeric(data[column], errors="coerce")

data["position_change_ms"] = (
    data["End Position In Milliseconds"]
    - data["Start Position In Milliseconds"]
)

start_time = pd.to_datetime(
    data["Event Start Timestamp"],
    errors="coerce",
    utc=True,
    format="mixed",
)

end_time = pd.to_datetime(
    data["Event End Timestamp"],
    errors="coerce",
    utc=True,
    format="mixed",
)

data["timestamp_duration_ms"] = (
    end_time - start_time
).dt.total_seconds() * 1000

media_duration = data["Media Duration In Milliseconds"]

candidates = {
    "Play Duration": data["Play Duration Milliseconds"],
    "Milliseconds Since Play": data["Milliseconds Since Play"],
    "Position Change": data["position_change_ms"],
    "Timestamp Difference": data["timestamp_duration_ms"],
}

print("\nDuration field comparison")

for name, values in candidates.items():
    available = values.notna()
    negative = (values < 0).sum()
    zero = (values == 0).sum()
    longer_than_media = (
        available
        & media_duration.gt(0)
        & values.gt(media_duration)
    ).sum()

    print(f"\n{name}")
    print(f"- Available: {available.sum():,}")
    print(f"- Missing: {values.isna().sum():,}")
    print(f"- Negative: {negative:,}")
    print(f"- Zero: {zero:,}")
    print(f"- Longer than media: {longer_than_media:,}")
    print(f"- Median seconds: {round(values.median() / 1000, 2)}")

data["negative_play_duration"] = (
    data["Play Duration Milliseconds"] < 0
)

data["missing_timestamp_duration"] = (
    data["timestamp_duration_ms"].isna()
)

reason_summary = (
    data.groupby("End Reason Type", dropna=False)
    .agg(
        events=("Event Type", "size"),
        negative_play_duration=("negative_play_duration", "sum"),
        missing_timestamp_duration=("missing_timestamp_duration", "sum"),
        play_duration=("Play Duration Milliseconds", "median"),
        milliseconds_since_play=("Milliseconds Since Play", "median"),
        position_change=("position_change_ms", "median"),
        timestamp_difference=("timestamp_duration_ms", "median"),
    )
    .sort_values("events", ascending=False)
)

duration_columns = [
    "play_duration",
    "milliseconds_since_play",
    "position_change",
    "timestamp_difference",
]

for column in duration_columns:
    reason_summary[column] = (
        reason_summary[column] / 1000
    ).round(2)

print("\nMedian seconds by end reason")
print(reason_summary.head(10).to_string())