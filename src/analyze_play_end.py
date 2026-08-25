from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_FILE = PROJECT_ROOT / "data" / "raw" / "Apple Music Play Activity.csv"
CHUNK_SIZE = 10_000

COLUMNS = [
    "Event Type",
    "Event ID",
    "Play Duration Milliseconds",
    "Media Duration In Milliseconds",
    "End Reason Type",
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
    play_end = chunk.loc[chunk["Event Type"] == "PLAY_END"].copy()
    play_end_chunks.append(play_end)
    print(f"Processed chunk {chunk_number}")

data = pd.concat(play_end_chunks, ignore_index=True)

data["play_ms"] = pd.to_numeric(
    data["Play Duration Milliseconds"],
    errors="coerce",
)

data["media_ms"] = pd.to_numeric(
    data["Media Duration In Milliseconds"],
    errors="coerce",
)

data["play_seconds"] = data["play_ms"] / 1000

valid_media = data["media_ms"] > 0

data.loc[valid_media, "completion_percent"] = (
    data.loc[valid_media, "play_ms"]
    / data.loc[valid_media, "media_ms"]
    * 100
)

duration_groups = {
    "Missing duration": data["play_ms"].isna(),
    "Negative duration": data["play_ms"] < 0,
    "Zero duration": data["play_ms"] == 0,
    "Under 10 seconds": (data["play_ms"] > 0)
    & (data["play_ms"] < 10_000),
    "10 to 29 seconds": (data["play_ms"] >= 10_000)
    & (data["play_ms"] < 30_000),
    "30 to 59 seconds": (data["play_ms"] >= 30_000)
    & (data["play_ms"] < 60_000),
    "60 seconds or longer": data["play_ms"] >= 60_000,
}

print("\nPLAY_END duration distribution")

for label, condition in duration_groups.items():
    count = int(condition.sum())
    percentage = round(count / len(data) * 100, 2)
    print(f"- {label}: {count:,} ({percentage}%)")

longer_than_media = (
    valid_media
    & (data["play_ms"] > data["media_ms"])
).sum()

print(
    f"\nPlay duration longer than media duration: "
    f"{longer_than_media:,}"
)

reason_summary = (
    data.groupby("End Reason Type", dropna=False)
    .agg(
        events=("Event ID", "size"),
        zero_duration=("play_ms", lambda values: (values == 0).sum()),
        under_30_seconds=(
            "play_ms",
            lambda values: (
                (values > 0) & (values < 30_000)
            ).sum(),
        ),
        median_play_seconds=("play_seconds", "median"),
        median_completion_percent=("completion_percent", "median"),
    )
    .sort_values("events", ascending=False)
)

reason_summary["median_play_seconds"] = (
    reason_summary["median_play_seconds"].round(2)
)

reason_summary["median_completion_percent"] = (
    reason_summary["median_completion_percent"].round(2)
)

print("\nPLAY_END reasons and duration behavior")
print(reason_summary.head(10).to_string())