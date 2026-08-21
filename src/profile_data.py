from collections import Counter
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_FILE = PROJECT_ROOT / "data" / "raw" / "Apple Music Play Activity.csv"
OUTPUT_FILE = PROJECT_ROOT / "data" / "processed" / "column_profile.csv"
CHUNK_SIZE = 10_000


if not INPUT_FILE.exists():
    raise FileNotFoundError(f"File not found: {INPUT_FILE}")

columns = pd.read_csv(INPUT_FILE, nrows=0).columns
null_counts = pd.Series(0, index=columns, dtype="int64")
event_counts = Counter()
seen_event_ids = set()

total_rows = 0
duplicate_event_ids = 0
minimum_timestamp = None
maximum_timestamp = None

for chunk_number, chunk in enumerate(
    pd.read_csv(INPUT_FILE, chunksize=CHUNK_SIZE, low_memory=False),
    start=1,
):
    total_rows += len(chunk)
    null_counts += chunk.isna().sum()

    event_counts.update(
        chunk["Event Type"].fillna("MISSING").astype(str).value_counts().to_dict()
    )

    for event_id in chunk["Event ID"].dropna().astype(str):
        if event_id in seen_event_ids:
            duplicate_event_ids += 1
        else:
            seen_event_ids.add(event_id)

    timestamps = pd.to_datetime(
        chunk["Event Timestamp"],
        errors="coerce",
        utc=True,
        format="mixed",
    ).dropna()

    if not timestamps.empty:
        chunk_minimum = timestamps.min()
        chunk_maximum = timestamps.max()

        minimum_timestamp = (
            chunk_minimum
            if minimum_timestamp is None
            else min(minimum_timestamp, chunk_minimum)
        )
        maximum_timestamp = (
            chunk_maximum
            if maximum_timestamp is None
            else max(maximum_timestamp, chunk_maximum)
        )

    print(f"Processed chunk {chunk_number}: {total_rows:,} rows")

profile = pd.DataFrame(
    {
        "column": columns,
        "missing_count": null_counts.values,
        "non_missing_count": total_rows - null_counts.values,
        "missing_percent": (null_counts.values / total_rows * 100).round(4),
        "all_missing": null_counts.values == total_rows,
    }
).sort_values("missing_percent", ascending=False)

OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
profile.to_csv(OUTPUT_FILE, index=False)

print("\nDataset summary")
print(f"Rows: {total_rows:,}")
print(f"Columns: {len(columns)}")
print(f"Duplicate Event IDs: {duplicate_event_ids:,}")
print(f"Date range: {minimum_timestamp} to {maximum_timestamp}")

print("\nEvent types")
for event_type, count in event_counts.most_common():
    print(f"- {event_type}: {count:,}")

print(f"\nColumn profile saved to: {OUTPUT_FILE}")