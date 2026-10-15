import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from src.clean_listening_events import clean_chunk
from src import load_postgres as loader
from tests.helpers import event, raw_events


class LoaderValidationTests(unittest.TestCase):
    def validate(self, data):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.parquet"
            data.to_parquet(path, index=False)
            with patch.object(loader, "INPUT_FILE", path):
                return loader.read_and_validate_data()

    def test_valid_data_has_database_column_order(self):
        data = clean_chunk(raw_events(event()))
        self.assertEqual(tuple(self.validate(data).columns), loader.DATABASE_COLUMNS)

    def test_missing_required_column_is_rejected(self):
        data = clean_chunk(raw_events(event())).drop(columns="song_name")
        with self.assertRaisesRegex(
            ValueError, "Required columns are missing: song_name"
        ):
            self.validate(data)

    def test_null_empty_and_whitespace_ids_are_rejected(self):
        for event_id in (None, "", "   "):
            with self.subTest(event_id=event_id):
                data = clean_chunk(raw_events(event()))
                data["event_id"] = event_id
                with self.assertRaisesRegex(ValueError, "missing Event IDs"):
                    self.validate(data)

    def test_duplicate_ids_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate Event IDs"):
            self.validate(clean_chunk(raw_events(event(), event())))

    def test_wrong_and_null_event_types_are_rejected(self):
        for event_type in ("PLAY_START", None):
            with self.subTest(event_type=event_type):
                data = clean_chunk(raw_events(event()))
                data["event_type"] = event_type
                with self.assertRaisesRegex(ValueError, "not PLAY_END"):
                    self.validate(data)

    def test_normalization_preserves_nulls_and_python_types(self):
        self.assertIsNone(loader.normalize_value("listening_duration_ms", float("nan")))
        self.assertIsNone(loader.normalize_value("event_timestamp_utc", pd.NaT))
        self.assertEqual(
            loader.normalize_value("listening_duration_ms", 60000.0), 60000
        )
        self.assertIs(loader.normalize_value("offline", False), False)
        timestamp = pd.Timestamp("2026-08-01", tz="UTC")
        self.assertEqual(
            loader.normalize_value("event_timestamp_utc", timestamp),
            timestamp.to_pydatetime(),
        )
