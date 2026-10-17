"""Export a private, event-level snapshot for Power BI's web authoring flow."""

import argparse
import csv
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Friendly names match the PBIP semantic model and the web-model instructions.
EXPORT_COLUMNS = {
    "event_id": "Event ID",
    "listening_date": "Listening Date",
    "listening_month": "Listening Month",
    "month_label": "Month",
    "month_sort": "Month Sort",
    "song_name": "Track Name",
    "album_name": "Album",
    "track_label": "Track",
    "track_key": "Track Key",
    "device_type": "Device",
    "listening_duration_ms": "Listening Duration ms",
    "is_skipped": "Is Skipped",
    "is_natural_end": "Is Natural End",
    "completion_percent": "Completion Percent",
    "has_listening_date": "Has Listening Date",
}


def export_data(database_url, output):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    count = 0
    try:
        with psycopg.connect(database_url) as connection:
            connection.execute("SET TRANSACTION READ ONLY")
            with connection.cursor(name="powerbi_export") as cursor:
                cursor.execute(
                    "SELECT "
                    + ", ".join(EXPORT_COLUMNS)
                    + " FROM analytics.powerbi_listening_events ORDER BY event_id"
                )
                with temporary.open("w", encoding="utf-8-sig", newline="") as handle:
                    writer = csv.writer(handle)
                    writer.writerow(EXPORT_COLUMNS.values())
                    for row in cursor:
                        writer.writerow(row)
                        count += 1
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "data/processed/Listening Events.csv",
    )
    args = parser.parse_args()
    load_dotenv(PROJECT_ROOT / ".env")
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        parser.error("Set DATABASE_URL or create the local .env file.")
    count = export_data(database_url, args.output)
    print(f"Exported {count:,} events to {args.output}")
    print("Private snapshot: keep this file out of Git and public sharing.")


if __name__ == "__main__":
    main()
