# Music Insights Agent

An end-to-end music analytics system that transforms private Apple Music listening history into cleaned data, a PostgreSQL analytics database, and verified SQL insights.

The data layer includes the Python ETL pipeline, Dockerized PostgreSQL,
a duplicate-safe loader, data-quality checks, and analytics views.

The three-page Power BI web report is saved and has passed SQL, filter, and
screenshot checks. A separate native Desktop project is prepared; its Windows
refresh check remains pending.

Milestone 5 adds a terminal agent with approved read-only SQL tools, a restricted
database login, and tested local evidence rendering. The expanded 24-case live
evaluation passed twice (48/48 checks) on October 26, 2026. Eight real-data
questions and an end-to-end terminal command passed independent SQL checks on
October 24, 2026.

## Project Goal

This project combines data engineering, business intelligence, and agentic AI to analyze music-listening behavior.

The completed data layer can answer questions such as:

- How did my listening change each month?
- Which tracks received the most listening time?
- How did my skip rate change?
- Which devices account for most of my listening?
- How do repeat and shuffle settings affect listening behavior?

The terminal agent supports top tracks, monthly listening, device usage, and skip rates through approved parameterized tools. Other questions require additional tools and evaluation.

## Architecture

```mermaid
flowchart TD
    A["Apple Music Export"] --> B["Python and Pandas ETL"]
    B --> C["Cleaned Parquet Data"]
    C --> D["PostgreSQL in Docker"]
    D --> E["SQL Analytics Views"]
    E --> F["Power BI Web Dashboard"]
    E --> G["Read-Only Terminal Agent"]
    G --> H["Natural-Language Insights"]
```

## Current Data Results

The source Apple Music Play Activity export contains:

- 278,231 raw activity records
- 145 source columns
- Playback timestamps
- Song and album information
- Listening-duration fields
- Completion and skip information
- Device and playback-source data

The cleaned PostgreSQL dataset contains:

- 172,899 unique `PLAY_END` events
- 160,417 events that qualify for listening analytics
- 26 selected analytics columns
- Zero missing Event IDs
- Zero duplicate Event IDs
- Data from July 2023 through August 2026

Duration-quality results:

- 164,311 valid durations, or 95.03%
- 5,972 missing durations caused mainly by negative scrub activity
- 2,616 durations longer than the source media duration

## Data Engineering Decisions

### Listening-event grain

One database row represents one unique Apple Music `PLAY_END` event.

`PLAY_START` and `LYRIC_DISPLAY` events are excluded from the main listening table because they do not represent completed playback sessions.

### Primary key

`event_id` is the primary key because it uniquely identifies an Apple Music playback event.

The loader uses this key to prevent duplicates and safely process newer Apple Music exports.

### Duration handling

The pipeline uses the difference between the event start and end timestamps as the cleaned listening duration, rounded to whole milliseconds to match database storage without floating-point truncation.

Rows with missing or unusual durations remain in the main table for auditing. The analytics view caps durations that exceed the media duration instead of deleting the original record.

### Staging and UPSERT loading

The PostgreSQL loader:

1. Validates the Parquet file.
2. Checks required columns and Event IDs.
3. Copies rows into a temporary staging table.
4. Compares staging rows with existing database rows.
5. Inserts new events.
6. Updates changed events.
7. Leaves identical events unchanged.
8. Records the result in `etl_runs`.

This makes the pipeline safe to rerun.

## Technology Stack

- Python
- Pandas
- PyArrow and Parquet
- PostgreSQL 17
- SQL
- Docker and Docker Compose
- Psycopg
- Power BI
- Git and GitHub

## Repository Structure

```text
music-insights-agent/
├── data/
│   ├── raw/                         Private Apple Music files
│   └── processed/                   Private cleaned Parquet files
├── docs/
│   ├── data-model.md
│   └── engineering-decisions.md
├── sql/
│   ├── schema.sql
│   ├── data_quality_checks.sql
│   └── analytics_views.sql
├── src/
│   ├── profile_data.py
│   ├── analyze_event_types.py
│   ├── analyze_play_end.py
│   ├── analyze_duration_fields.py
│   ├── clean_listening_events.py
│   ├── check_database.py
│   └── load_postgres.py
├── .env.example
├── compose.yaml
├── requirements.txt
└── README.md
```

## Run the PostgreSQL Data Layer

### 1. Create and activate a Python environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install the Python packages

```bash
python -m pip install -r requirements.txt
```

### 3. Create the local database configuration

```bash
cp .env.example .env
```

The `.env` file contains local database settings and is ignored by Git.

### 4. Start PostgreSQL

Make sure Docker Desktop is running, then execute:

```bash
docker compose up -d postgres
```

Check the container:

```bash
docker compose ps
```

The container should report a `healthy` status.

### 5. Prepare the private source data

Place the Apple Music Play Activity export at:

```text
data/raw/Apple Music Play Activity.csv
```

Run the cleaning pipeline:

```bash
python src/clean_listening_events.py
```

The cleaned output is written to:

```text
data/processed/listening_events.parquet
```

### 6. Create the PostgreSQL schema

```bash
docker compose exec -T postgres \
  psql -U music_user -d music_insights \
  < sql/schema.sql
```

### 7. Test the Python connection

```bash
python src/check_database.py
```

### 8. Load the cleaned data

```bash
python src/load_postgres.py
```

### 9. Run the data-quality checks

```bash
docker compose exec -T postgres \
  psql -U music_user -d music_insights \
  < sql/data_quality_checks.sql
```

### 10. Create the analytics views

```bash
docker compose exec -T postgres \
  psql -U music_user -d music_insights \
  < sql/analytics_views.sql
```

### 11. Query the analytics layer

Monthly listening:

```bash
docker compose exec postgres \
  psql -U music_user -d music_insights \
  -c "SELECT * FROM analytics.monthly_listening ORDER BY listening_month DESC LIMIT 12;"
```

Top tracks:

```bash
docker compose exec postgres \
  psql -U music_user -d music_insights \
  -c "SELECT * FROM analytics.track_summary ORDER BY listening_minutes DESC LIMIT 10;"
```

Device usage:

```bash
docker compose exec postgres \
  psql -U music_user -d music_insights \
  -c "SELECT * FROM analytics.device_summary ORDER BY listening_minutes DESC;"
```

### 12. Stop PostgreSQL

```bash
docker compose stop postgres
```

The named Docker volume preserves the database when the container stops.

## Analytics Views

The `analytics` schema currently contains:

- `valid_listening_events`: reporting-ready listening events
- `monthly_listening`: monthly listening, track, skip, and completion metrics
- `track_summary`: track-level listening and skip metrics
- `device_summary`: device-level listening and skip metrics

## Milestone 5: Read-Only Terminal Agent

The terminal agent uses an LLM to select one approved tool and its filters.
It never accepts model-generated SQL. The four analytics tools cover top tracks,
monthly listening, device usage, and count-weighted skip rates. The model receives
only the question and static tool descriptions; database results stay local.
A deterministic answer includes numerical evidence, interpreted filters, and
missing-date limitations. No web interface has been built.

A dedicated PostgreSQL login has SELECT on a separate restricted reporting view,
with no base-table grants. Runtime verifies privileges, uses read-only snapshots,
binds parameters, and enforces query timeouts and result limits. Existing ETL
and Power BI project definitions are unchanged.

```bash
# Configure AGENT_DATABASE_URL, OPENAI_API_KEY, and OPENAI_MODEL locally first.
python -m src.agent.cli
```

The SQL tools, permissions, API adapter simulations, and recorded-plan evaluations
passed testing. **The 24-case live suite passed twice: 48/48 checks on October 26,
2026.** It covers supported questions, ambiguous dates, unsupported requests,
SQL/credential bypass attempts, and excessive limits. Eight real-data questions
and the terminal command also passed independent SQL verification on October 24.
These checks do not guarantee arbitrary-question accuracy. See [setup, security boundaries, evaluation commands, and verified
results](docs/milestone-5-agent.md). The agent cannot establish personal motives
or infer dates for undated playback events.

## Project Status

- [x] GitHub repository created
- [x] Private data protected with `.gitignore`
- [x] Chunked data-profiling pipeline
- [x] Data cleaning and Parquet transformation
- [x] PostgreSQL database running in Docker
- [x] Staging-table and UPSERT loading pipeline
- [x] ETL run auditing
- [x] SQL data-quality checks
- [x] Reusable analytics views
- [x] Power BI web dashboard — three pages saved, SQL/filter checks and screenshot review passed
- [ ] Native Power BI Desktop project refresh verification (Windows)
- [x] Read-only terminal analytics tools, restricted login, and local evidence answers
- [x] Live LLM routing evaluation — 24 cases × 2 runs, 48/48 passed (October 26, 2026)
- [x] Real-data Q&A — 8/8 questions and an end-to-end terminal check passed (October 24, 2026)
- [x] Automated unit and PostgreSQL integration tests

## Power BI Report

The report project includes a listening overview, track explorer, and device/data
coverage page with date and device slicers. See [powerbi/README.md](powerbi/README.md)
for the Mac/browser import workflow, Desktop project, measure definitions, and
SQL reconciliation checks. The private CSV export stays under ignored
`data/processed/`; no credentials or data caches are embedded in the report.

## Verification and Tests

The tests use Python's built-in `unittest`; no extra test packages are required.
Run the cleaning and loader-validation tests after installing `requirements.txt`:

```bash
python -m unittest discover -s tests -t . -v
```

PostgreSQL tests are skipped unless `TEST_DATABASE_URL` is set. They create a
uniquely named temporary database and delete it after the suite, so the supplied
account needs `CREATEDB` and `CREATEROLE` permission for agent tests. Existing
databases and listening data are not modified. To run against a disposable PostgreSQL 17 container:

```bash
docker run --detach --rm --name music-insights-tests \
  -e POSTGRES_PASSWORD=verification \
  -p 127.0.0.1:55432:5432 postgres:17-alpine
# Wait until this reports "accepting connections":
docker exec music-insights-tests pg_isready -U postgres
TEST_DATABASE_URL=postgresql://postgres:verification@127.0.0.1:55432/postgres \
  python -m unittest discover -s tests -t . -v
docker stop music-insights-tests
```

To also verify your private export, set `MUSIC_SOURCE_CSV` to its absolute path
alongside `TEST_DATABASE_URL` when running the suite. This exercises CSV cleaning,
Parquet validation, two database loads, quality reports, and SQL totals checked
against Pandas. Its generated Parquet file and database are temporary; the source
export is only read. Without this variable, the private-export test is skipped.

Coverage includes:

- PLAY_END filtering and duplicate removal within and across chunks
- Missing/blank IDs, missing columns, and invalid event types
- Timestamp durations, invalid durations, completion caps, and local timestamps
- Scrub/skip classification and missing end reasons
- Unchanged reruns, changed-row updates, audit counts, and transaction rollback
- Analytics filtering, duration caps, and monthly/track/device aggregates
- Agent contract validation, restricted-role access, denied writes, injection-safe
  filter binding, local evidence/coverage reporting, and known-answer evaluations

Rows with missing end reasons remain available for auditing, with
`is_natural_end` and `is_listening_event` set to false.

## Privacy

The original Apple Music ZIP archive, CSV files, cleaned Parquet files, and local environment settings are never uploaded to GitHub.

The repository contains only:

- Source code
- SQL scripts
- Documentation
- Dashboard screenshots
- Sanitized sample data when available

## Disclaimer

This is an independent portfolio project and is not affiliated with or endorsed by Apple.