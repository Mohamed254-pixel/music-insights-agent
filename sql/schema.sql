CREATE TABLE IF NOT EXISTS listening_events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL
        CHECK (event_type = 'PLAY_END'),

    event_timestamp_utc TIMESTAMPTZ,
    event_start_timestamp_utc TIMESTAMPTZ,
    event_end_timestamp_utc TIMESTAMPTZ,
    utc_offset_seconds INTEGER,
    event_timestamp_local TIMESTAMP,

    song_name TEXT,
    album_name TEXT,
    media_type TEXT,
    device_type TEXT,
    client_platform TEXT,
    source_type TEXT,

    offline BOOLEAN,
    repeat_play TEXT,
    shuffle_play TEXT,

    end_reason TEXT,
    media_duration_ms BIGINT,
    original_play_duration_ms BIGINT,
    listening_duration_ms BIGINT,

    duration_exceeds_media BOOLEAN NOT NULL,
    duration_quality TEXT NOT NULL,

    completion_percent NUMERIC(6, 2)
        CHECK (
            completion_percent IS NULL
            OR completion_percent BETWEEN 0 AND 100
        ),

    is_natural_end BOOLEAN NOT NULL,
    is_skipped BOOLEAN NOT NULL,
    is_listening_event BOOLEAN NOT NULL,

    loaded_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE listening_events
    ADD COLUMN IF NOT EXISTS offline BOOLEAN,
    ADD COLUMN IF NOT EXISTS repeat_play TEXT,
    ADD COLUMN IF NOT EXISTS shuffle_play TEXT;


CREATE INDEX IF NOT EXISTS idx_listening_events_timestamp
    ON listening_events (event_timestamp_utc);

CREATE INDEX IF NOT EXISTS idx_listening_events_local_timestamp
    ON listening_events (event_timestamp_local);

CREATE INDEX IF NOT EXISTS idx_listening_events_song_album
    ON listening_events (song_name, album_name);

CREATE INDEX IF NOT EXISTS idx_listening_events_end_reason
    ON listening_events (end_reason);

CREATE INDEX IF NOT EXISTS idx_listening_events_device
    ON listening_events (device_type);

CREATE INDEX IF NOT EXISTS idx_listening_events_valid_analytics
    ON listening_events (event_timestamp_utc)
    WHERE is_listening_event;


CREATE TABLE IF NOT EXISTS etl_runs (
    run_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_file TEXT NOT NULL,
    source_rows INTEGER NOT NULL,
    inserted_rows INTEGER NOT NULL,
    updated_rows INTEGER NOT NULL,
    completed_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP
);