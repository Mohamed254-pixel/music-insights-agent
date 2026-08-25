from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_FILE = PROJECT_ROOT / "data" / "raw" / "Apple Music Play Activity.csv"
CHUNK_SIZE = 10_000

COLUMNS = [
    "Event Type",
    "Event ID",
    "Song Name",
    "Album Name",
    "Play Duration Milliseconds",
    "Media Duration In Milliseconds",
    "End Reason Type",
    "Event Start Timestamp",
    "Event End Timestamp",
]

stats = defaultdict(Counter)
event_ids = defaultdict(set)
end_reasons = defaultdict(Counter)


def percentage(value, total):
    if total == 0:
        return 0
    return round(value / total * 100, 2)


for chunk_number, chunk in enumerate(
    pd.read_csv(
        INPUT_FILE,
        usecols=COLUMNS,
        chunksize=CHUNK_SIZE,
        low_memory=False,
    ),
    start=1,
):
    chunk["Event Type"] = chunk["Event Type"].fillna("MISSING")

    for event_type, group in chunk.groupby("Event Type"):
        row_count = len(group)
        current = stats[event_type]

        current["rows"] += row_count
        current["song_name"] += group["Song Name"].notna().sum()
        current["album_name"] += group["Album Name"].notna().sum()
        current["play_duration"] += group[
            "Play Duration Milliseconds"
        ].notna().sum()
        current["media_duration"] += group[
            "Media Duration In Milliseconds"
        ].notna().sum()
        current["end_reason"] += group["End Reason Type"].notna().sum()
        current["start_timestamp"] += group[
            "Event Start Timestamp"
        ].notna().sum()
        current["end_timestamp"] += group[
            "Event End Timestamp"
        ].notna().sum()

        play_duration = pd.to_numeric(
            group["Play Duration Milliseconds"],
            errors="coerce",
        )

        current["positive_play_duration"] += play_duration.gt(0).sum()
        current["total_play_milliseconds"] += play_duration.sum()

        event_ids[event_type].update(
            group["Event ID"].dropna().astype(str)
        )

        end_reasons[event_type].update(
            group["End Reason Type"]
            .dropna()
            .astype(str)
            .value_counts()
            .to_dict()
        )

    print(f"Processed chunk {chunk_number}")


print("\nEvent type comparison")

for event_type, current in sorted(
    stats.items(),
    key=lambda item: item[1]["rows"],
    reverse=True,
):
    rows = current["rows"]

    print(f"\n{event_type}: {rows:,} rows")
    print(
        f"- Song name available: "
        f"{percentage(current['song_name'], rows)}%"
    )
    print(
        f"- Album name available: "
        f"{percentage(current['album_name'], rows)}%"
    )
    print(
        f"- Play duration available: "
        f"{percentage(current['play_duration'], rows)}%"
    )
    print(
        f"- Positive play duration: "
        f"{percentage(current['positive_play_duration'], rows)}%"
    )
    print(
        f"- Media duration available: "
        f"{percentage(current['media_duration'], rows)}%"
    )
    print(
        f"- End reason available: "
        f"{percentage(current['end_reason'], rows)}%"
    )
    print(
        f"- Start timestamp available: "
        f"{percentage(current['start_timestamp'], rows)}%"
    )
    print(
        f"- End timestamp available: "
        f"{percentage(current['end_timestamp'], rows)}%"
    )
    print(f"- Unique Event IDs: {len(event_ids[event_type]):,}")


shared_ids = event_ids["PLAY_START"] & event_ids["PLAY_END"]

print(
    f"\nEvent IDs shared by PLAY_START and PLAY_END: "
    f"{len(shared_ids):,}"
)

print("\nTop PLAY_END reasons")

for reason, count in end_reasons["PLAY_END"].most_common(10):
    print(f"- {reason}: {count:,}")