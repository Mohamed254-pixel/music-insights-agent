"""Real PostgreSQL tests, isolated in a newly created disposable database.

Set TEST_DATABASE_URL to a PostgreSQL account with CREATEDB permission.
Optionally set MUSIC_SOURCE_CSV to verify a private export end to end.
"""

import os
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

from src import clean_listening_events as cleaner
from src import load_postgres as loader
from tests.helpers import event, raw_events

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(
    os.getenv("TEST_DATABASE_URL"), "Set TEST_DATABASE_URL to run real PostgreSQL tests"
)
class PostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.admin_url = os.environ["TEST_DATABASE_URL"]
        cls.database = "music_test_" + uuid.uuid4().hex
        cls.database_url = make_conninfo(cls.admin_url, dbname=cls.database)
        with psycopg.connect(cls.admin_url, autocommit=True) as connection:
            connection.execute(
                sql.SQL("CREATE DATABASE {}").format(sql.Identifier(cls.database))
            )
        cls.addClassCleanup(cls.drop_database)
        with psycopg.connect(cls.database_url) as connection:
            connection.execute((ROOT / "sql/schema.sql").read_text())
            connection.execute((ROOT / "sql/analytics_views.sql").read_text())

    @classmethod
    def drop_database(cls):
        with psycopg.connect(cls.admin_url, autocommit=True) as connection:
            connection.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(
                    sql.Identifier(cls.database)
                )
            )

    def setUp(self):
        with psycopg.connect(self.database_url) as connection:
            connection.execute("TRUNCATE listening_events, etl_runs RESTART IDENTITY")
        self.enterContext(patch.dict(os.environ, {"DATABASE_URL": self.database_url}))

    def query(self, query):
        with psycopg.connect(self.database_url) as connection:
            return connection.execute(query).fetchall()

    def test_rerun_is_unchanged_and_changed_rows_update_with_audit(self):
        data = cleaner.clean_chunk(raw_events(event("one"), event("two")))
        data = data.loc[:, loader.DATABASE_COLUMNS]
        first = loader.load_into_postgres(data)
        self.assertEqual((first["inserted_rows"], first["updated_rows"]), (2, 0))
        timestamps = self.query(
            "SELECT event_id, loaded_at FROM listening_events ORDER BY event_id"
        )
        second = loader.load_into_postgres(data)
        self.assertEqual(
            (second["inserted_rows"], second["updated_rows"], second["unchanged_rows"]),
            (0, 0, 2),
        )
        self.assertEqual(
            self.query(
                "SELECT event_id, loaded_at FROM listening_events ORDER BY event_id"
            ),
            timestamps,
        )
        data.loc[0, "song_name"] = "Updated Synthetic Track"
        third = loader.load_into_postgres(data)
        self.assertEqual(
            (third["inserted_rows"], third["updated_rows"], third["unchanged_rows"]),
            (0, 1, 1),
        )
        self.assertEqual(
            self.query("SELECT song_name FROM listening_events WHERE event_id = 'one'"),
            [("Updated Synthetic Track",)],
        )
        self.assertEqual(
            self.query(
                "SELECT source_rows, inserted_rows, updated_rows FROM etl_runs ORDER BY run_id"
            ),
            [(2, 2, 0), (2, 0, 0), (2, 0, 1)],
        )
        self.assertEqual(
            self.query(
                "SELECT COUNT(*), COUNT(DISTINCT event_id) FROM listening_events"
            ),
            [(2, 2)],
        )

    def test_failed_load_rolls_back_rows_and_audit(self):
        data = cleaner.clean_chunk(raw_events(event("one"), event("two"))).loc[
            :, loader.DATABASE_COLUMNS
        ]
        data.loc[1, "completion_percent"] = 101
        with self.assertRaises(psycopg.errors.CheckViolation):
            loader.load_into_postgres(data)
        self.assertEqual(self.query("SELECT COUNT(*) FROM listening_events"), [(0,)])
        self.assertEqual(self.query("SELECT COUNT(*) FROM etl_runs"), [(0,)])

    def test_analytics_filter_scrubs_and_cap_durations(self):
        data = cleaner.clean_chunk(
            raw_events(
                event("overlong", **{"Media Duration In Milliseconds": 30000}),
                event("skip", **{"End Reason Type": "TRACK_SKIPPED_FORWARDS"}),
                event("scrub", **{"End Reason Type": "SCRUB_END"}),
                event("missing", **{"Event End Timestamp": None}),
                event("unknown", **{"End Reason Type": None}),
            )
        ).loc[:, loader.DATABASE_COLUMNS]
        loader.load_into_postgres(data)
        self.assertEqual(
            self.query(
                "SELECT event_id, analytics_listening_duration_ms FROM analytics.valid_listening_events ORDER BY event_id"
            ),
            [("overlong", 30000), ("skip", 60000)],
        )
        self.assertEqual(
            self.query(
                "SELECT listening_duration_ms FROM listening_events WHERE event_id = 'overlong'"
            ),
            [(60000,)],
        )
        from decimal import Decimal

        expected = [(2, Decimal("1.50"), Decimal("50.00"))]
        self.assertEqual(
            self.query(
                "SELECT listening_events, listening_minutes, skip_rate_percent FROM analytics.monthly_listening"
            ),
            expected,
        )
        self.assertEqual(
            self.query(
                "SELECT listening_events, listening_minutes, skip_rate_percent FROM analytics.track_summary"
            ),
            expected,
        )
        self.assertEqual(
            self.query(
                "SELECT listening_events, listening_minutes, skip_rate_percent FROM analytics.device_summary"
            ),
            expected,
        )
        # The reporting script must also execute successfully on the loaded data.
        with psycopg.connect(self.database_url) as connection:
            connection.execute((ROOT / "sql/data_quality_checks.sql").read_text())

    @unittest.skipUnless(
        os.getenv("MUSIC_SOURCE_CSV"),
        "Set MUSIC_SOURCE_CSV for private-data verification",
    )
    def test_private_export_end_to_end(self):
        source = Path(os.environ["MUSIC_SOURCE_CSV"]).resolve()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "listening_events.parquet"
            with patch.multiple(
                cleaner, INPUT_FILE=source, OUTPUT_FILE=output
            ), patch.object(loader, "INPUT_FILE", output):
                cleaner.main()
                data = loader.read_and_validate_data()
                self.assertGreater(len(data), 0)
                first = loader.load_into_postgres(data)
                second = loader.load_into_postgres(data)
            self.assertEqual(first["inserted_rows"], len(data))
            self.assertEqual(
                (
                    second["inserted_rows"],
                    second["updated_rows"],
                    second["unchanged_rows"],
                ),
                (0, 0, len(data)),
            )
            self.assertEqual(
                self.query(
                    "SELECT COUNT(*), COUNT(DISTINCT event_id) FROM listening_events"
                ),
                [(len(data), len(data))],
            )
            self.assertEqual(
                self.query(
                    "SELECT COUNT(*) FROM listening_events WHERE event_id IS NULL OR BTRIM(event_id) = '' OR event_type <> 'PLAY_END' OR listening_duration_ms < 0 OR completion_percent NOT BETWEEN 0 AND 100"
                ),
                [(0,)],
            )
            valid = data.loc[
                data.is_listening_event & data.listening_duration_ms.gt(0)
            ].copy()
            capped = valid.listening_duration_ms.where(
                ~valid.media_duration_ms.gt(0),
                valid.listening_duration_ms.clip(upper=valid.media_duration_ms),
            )
            actual = self.query(
                "SELECT COUNT(*), SUM(analytics_listening_duration_ms) FROM analytics.valid_listening_events"
            )[0]
            self.assertEqual(actual, (len(valid), int(capped.sum())))
            self.assertEqual(
                self.query(
                    "SELECT SUM(listening_events) FROM analytics.monthly_listening"
                )[0][0],
                int(valid.event_timestamp_local.notna().sum()),
            )
            for view in ("track_summary", "device_summary"):
                self.assertEqual(
                    self.query(f"SELECT SUM(listening_events) FROM analytics.{view}")[
                        0
                    ][0],
                    len(valid),
                )
            with psycopg.connect(self.database_url) as connection:
                cursor = connection.execute(
                    (ROOT / "sql/data_quality_checks.sql").read_text()
                )
                while cursor.nextset():
                    pass
            print(
                f"Verified private export: {len(data):,} unique events; {len(valid):,} analytics events; repeat load unchanged; SQL totals match Pandas."
            )
