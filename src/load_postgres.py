import os
from datetime import datetime
from pathlib import Path

import pandas as pd
import psycopg
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]

INPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "listening_events.parquet"
)

load_dotenv(PROJECT_ROOT / ".env")

DATABASE_COLUMNS = (
    "event_id",
    "event_type",
    "event_timestamp_utc",
    "event_start_timestamp_utc",
    "event_end_timestamp_utc",
    "utc_offset_seconds",
    "event_timestamp_local",
    "song_name",
    "album_name",
    "media_type",
    "device_type",
    "client_platform",
    "source_type",
    "offline",
    "repeat_play",
    "shuffle_play",
    "end_reason",
    "media_duration_ms",
    "original_play_duration_ms",
    "listening_duration_ms",
    "duration_exceeds_media",
    "duration_quality",
    "completion_percent",
    "is_natural_end",
    "is_skipped",
    "is_listening_event",
)

INTEGER_COLUMNS = {
    "utc_offset_seconds",
    "media_duration_ms",
    "original_play_duration_ms",
    "listening_duration_ms",
}

BOOLEAN_COLUMNS = {
    "offline",
    "duration_exceeds_media",
    "is_natural_end",
    "is_skipped",
    "is_listening_event",
}

TIMESTAMP_COLUMNS = {
    "event_timestamp_utc",
    "event_start_timestamp_utc",
    "event_end_timestamp_utc",
    "event_timestamp_local",
}

COLUMN_LIST = ", ".join(DATABASE_COLUMNS)

COPY_SQL = f"""
    COPY staging_listening_events (
        {COLUMN_LIST}
    )
    FROM STDIN
"""

UPDATE_COLUMNS = tuple(
    column
    for column in DATABASE_COLUMNS
    if column != "event_id"
)

UPDATE_ASSIGNMENTS = ",\n        ".join(
    f"{column} = EXCLUDED.{column}"
    for column in UPDATE_COLUMNS
)

CHANGE_CHECK = "\n        OR ".join(
    (
        f"target.{column} "
        f"IS DISTINCT FROM EXCLUDED.{column}"
    )
    for column in UPDATE_COLUMNS
)

UPSERT_SQL = f"""
    INSERT INTO listening_events AS target (
        {COLUMN_LIST}
    )
    SELECT
        {COLUMN_LIST}
    FROM staging_listening_events
    WHERE TRUE

    ON CONFLICT (event_id)
    DO UPDATE SET
        {UPDATE_ASSIGNMENTS},
        loaded_at = CURRENT_TIMESTAMP

    WHERE
        {CHANGE_CHECK}
"""


def read_and_validate_data():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Parquet file not found: {INPUT_FILE}"
        )

    data = pd.read_parquet(INPUT_FILE)

    missing_columns = (
        set(DATABASE_COLUMNS) - set(data.columns)
    )

    if missing_columns:
        missing = ", ".join(sorted(missing_columns))

        raise ValueError(
            f"Required columns are missing: {missing}"
        )

    data = data.loc[:, list(DATABASE_COLUMNS)].copy()

    missing_event_ids = int(
        (
            data["event_id"].isna()
            | data["event_id"].astype("string").str.strip().eq("")
        ).sum()
    )

    duplicate_event_ids = int(
        data["event_id"].duplicated().sum()
    )

    invalid_event_types = int(
        data["event_type"].fillna("").ne("PLAY_END").sum()
    )

    print("Pre-load validation")
    print(f"- Rows: {len(data):,}")
    print(f"- Database columns: {len(data.columns)}")
    print(f"- Missing Event IDs: {missing_event_ids:,}")
    print(f"- Duplicate Event IDs: {duplicate_event_ids:,}")
    print(f"- Invalid event types: {invalid_event_types:,}")

    if missing_event_ids:
        raise ValueError(
            "The dataset contains missing Event IDs."
        )

    if duplicate_event_ids:
        raise ValueError(
            "The dataset contains duplicate Event IDs."
        )

    if invalid_event_types:
        raise ValueError(
            "The dataset contains rows that are not PLAY_END."
        )

    return data


def normalize_value(column, value):
    if value is None or pd.isna(value):
        return None

    if column in INTEGER_COLUMNS:
        return int(value)

    if column in BOOLEAN_COLUMNS:
        return bool(value)

    if column in TIMESTAMP_COLUMNS:
        if isinstance(value, pd.Timestamp):
            return value.to_pydatetime()

        if isinstance(value, datetime):
            return value

    if hasattr(value, "item"):
        return value.item()

    return value


def create_database_rows(data):
    for values in data.itertuples(
        index=False,
        name=None,
    ):
        yield tuple(
            normalize_value(column, value)
            for column, value in zip(
                DATABASE_COLUMNS,
                values,
            )
        )


def load_into_postgres(data):
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise ValueError(
            "DATABASE_URL was not found in .env."
        )

    with (
        psycopg.connect(database_url) as connection,
        connection.cursor() as cursor,
    ):
        cursor.execute(
            """
            CREATE TEMP TABLE staging_listening_events
            (LIKE listening_events INCLUDING DEFAULTS)
            ON COMMIT DROP
            """
        )

        copied_rows = 0

        with cursor.copy(COPY_SQL) as copy:
            for row in create_database_rows(data):
                copy.write_row(row)
                copied_rows += 1

                if copied_rows % 25_000 == 0:
                    print(
                        f"Copied {copied_rows:,} rows"
                    )

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM staging_listening_events
            """
        )

        staged_rows = cursor.fetchone()[0]

        if staged_rows != len(data):
            raise ValueError(
                "The staging row count does not "
                "match the source row count."
            )

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM staging_listening_events AS staging

            INNER JOIN listening_events AS target
                USING (event_id)
            """
        )

        existing_rows = cursor.fetchone()[0]
        inserted_rows = staged_rows - existing_rows

        cursor.execute(UPSERT_SQL)

        affected_rows = cursor.rowcount
        updated_rows = affected_rows - inserted_rows

        if updated_rows < 0:
            raise ValueError(
                "The UPSERT row counts are inconsistent."
            )

        unchanged_rows = (
            staged_rows
            - inserted_rows
            - updated_rows
        )

        cursor.execute(
            """
            INSERT INTO etl_runs (
                source_file,
                source_rows,
                inserted_rows,
                updated_rows
            )
            VALUES (%s, %s, %s, %s)
            """,
            (
                INPUT_FILE.name,
                staged_rows,
                inserted_rows,
                updated_rows,
            ),
        )

    return {
        "source_rows": staged_rows,
        "copied_rows": copied_rows,
        "inserted_rows": inserted_rows,
        "updated_rows": updated_rows,
        "unchanged_rows": unchanged_rows,
    }


def main():
    data = read_and_validate_data()
    results = load_into_postgres(data)

    print("\nPostgreSQL load complete")
    print(
        f"- Source rows: "
        f"{results['source_rows']:,}"
    )
    print(
        f"- Copied to staging: "
        f"{results['copied_rows']:,}"
    )
    print(
        f"- Inserted rows: "
        f"{results['inserted_rows']:,}"
    )
    print(
        f"- Updated rows: "
        f"{results['updated_rows']:,}"
    )
    print(
        f"- Unchanged rows: "
        f"{results['unchanged_rows']:,}"
    )


if __name__ == "__main__":
    main()