import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from src import clean_listening_events as cleaner
from tests.helpers import event, raw_events


class CleaningTests(unittest.TestCase):
    def test_only_play_end_events_are_kept(self):
        result = cleaner.clean_chunk(
            raw_events(
                event("end"),
                event("start", **{"Event Type": "PLAY_START"}),
                event("lyrics", **{"Event Type": "LYRIC_DISPLAY"}),
            )
        )
        self.assertEqual(result.event_id.tolist(), ["end"])

    def test_timestamp_duration_wins_over_original_and_local_time_uses_offset(self):
        result = cleaner.clean_chunk(
            raw_events(
                event(
                    **{
                        "Play Duration Milliseconds": -5000,
                    }
                )
            )
        ).iloc[0]
        self.assertEqual(result.listening_duration_ms, 60000)
        self.assertEqual(result.original_play_duration_ms, -5000)
        self.assertEqual(result.duration_quality, "valid")
        self.assertEqual(
            result.event_timestamp_local, pd.Timestamp("2026-07-31 17:00:00")
        )
        self.assertEqual(result.completion_percent, 50)
        self.assertTrue(result.is_natural_end)

    def test_millisecond_precision_survives_database_normalization(self):
        from src.load_postgres import normalize_value

        row = cleaner.clean_chunk(
            raw_events(
                event(
                    **{
                        "Event End Timestamp": "2026-08-01T00:00:01.001Z",
                    }
                )
            )
        ).iloc[0]
        self.assertEqual(row.listening_duration_ms, 1001)
        self.assertEqual(
            normalize_value("listening_duration_ms", row.listening_duration_ms), 1001
        )

    def test_invalid_timestamps_remain_null_and_are_excluded(self):
        result = cleaner.clean_chunk(
            raw_events(
                event(
                    "missing",
                    **{"Event End Timestamp": None, "Play Duration Milliseconds": -10}
                ),
                event("invalid", **{"Event End Timestamp": "bad timestamp"}),
                event("negative", **{"Event End Timestamp": "2026-07-31T23:59:00Z"}),
            )
        ).set_index("event_id")
        self.assertTrue(result.listening_duration_ms.isna().all())
        self.assertTrue(result.completion_percent.isna().all())
        self.assertFalse(result.is_listening_event.any())
        self.assertEqual(
            result.loc["missing", "duration_quality"],
            "negative_original_and_missing_timestamp",
        )
        self.assertEqual(
            result.loc["invalid", "duration_quality"], "missing_or_invalid_timestamp"
        )

    def test_overlong_duration_is_preserved_but_completion_is_capped(self):
        row = cleaner.clean_chunk(
            raw_events(
                event(
                    **{
                        "Media Duration In Milliseconds": 30000,
                    }
                )
            )
        ).iloc[0]
        self.assertEqual(row.listening_duration_ms, 60000)
        self.assertTrue(row.duration_exceeds_media)
        self.assertEqual(row.duration_quality, "exceeds_media")
        self.assertEqual(row.completion_percent, 100)

    def test_scrub_zero_and_skip_classification(self):
        result = cleaner.clean_chunk(
            raw_events(
                event("scrub", **{"End Reason Type": "SCRUB_END"}),
                event("zero", **{"Event End Timestamp": "2026-08-01T00:00:00Z"}),
                event("skip", **{"End Reason Type": "TRACK_SKIPPED_FORWARDS"}),
                event("back", **{"End Reason Type": "TRACK_SKIPPED_BACKWARDS"}),
                event(
                    "unknown",
                    **{"End Reason Type": None, "Media Duration In Milliseconds": 0}
                ),
            )
        ).set_index("event_id")
        self.assertFalse(result.loc["scrub", "is_listening_event"])
        self.assertFalse(result.loc["zero", "is_listening_event"])
        self.assertTrue(result.loc["skip", "is_skipped"])
        self.assertTrue(result.loc["back", "is_skipped"])
        self.assertTrue(result.loc["skip", "is_listening_event"])
        self.assertTrue(pd.isna(result.loc["unknown", "completion_percent"]))
        self.assertFalse(result.loc["unknown", "is_natural_end"])
        self.assertFalse(result.loc["unknown", "is_listening_event"])

    def test_csv_to_parquet_removes_missing_and_duplicate_ids_across_chunks(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "events.csv"
            output = Path(directory) / "nested" / "events.parquet"
            raw_events(
                event(" one "),
                event("one"),
                event(None),
                event("   "),
                event("one"),
                event("two"),
            ).to_csv(source, index=False)
            with patch.multiple(
                cleaner, INPUT_FILE=source, OUTPUT_FILE=output, CHUNK_SIZE=2
            ):
                cleaner.main()
            result = pd.read_parquet(output)
            self.assertEqual(result.event_id.tolist(), ["one", "two"])
            self.assertEqual(result.song_name.tolist(), ["Synthetic Track"] * 2)
