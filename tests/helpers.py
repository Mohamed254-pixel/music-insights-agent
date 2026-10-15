"""Synthetic Apple Music events; no private listening history is stored here."""

import pandas as pd

from src.clean_listening_events import SOURCE_COLUMNS


def event(event_id="event-1", **changes):
    row = dict.fromkeys(SOURCE_COLUMNS)
    row.update(
        {
            "Event ID": event_id,
            "Event Type": "PLAY_END",
            "Event Timestamp": "2026-08-01T00:00:00Z",
            "Event Start Timestamp": "2026-08-01T00:00:00Z",
            "Event End Timestamp": "2026-08-01T00:01:00Z",
            "UTC Offset In Seconds": -25200,
            "Song Name": "Synthetic Track",
            "Album Name": "Synthetic Album",
            "Media Type": "AUDIO",
            "Device Type": "Test Device",
            "Client Platform": "Test Platform",
            "Source Type": "LIBRARY",
            "End Reason Type": "NATURAL_END_OF_TRACK",
            "Media Duration In Milliseconds": 120000,
            "Play Duration Milliseconds": 60000,
            "Offline": False,
            "Repeat Play": "OFF",
            "Shuffle Play": "OFF",
        }
    )
    row.update(changes)
    return row


def raw_events(*rows):
    return pd.DataFrame(rows, columns=SOURCE_COLUMNS)
