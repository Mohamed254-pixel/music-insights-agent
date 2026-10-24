# Milestone 5: read-only terminal analytics agent

Implemented October 22, 2026. The SQL tools, role restrictions, local answer
renderer, simulated Responses API adapter, and synthetic evaluation cases have
been tested. A live OpenAI request has **not** been verified: no API key/model
is configured. This is not a completed live-model accuracy evaluation.

## How it works

1. A single question and static tool descriptions go to the OpenAI Responses API.
2. The model selects exactly one approved function and typed filters, or asks for
   clarification through a fixed reason code. Free-text model answers are rejected.
3. Independent Python validation rejects unknown tools/keys, invalid dates,
   unsupported grouping/ranking values, and result limits outside 1–60.
4. Fixed SQL templates bind all filter values with Psycopg parameters. Neither
   SQL text, identifiers, connection settings, nor expressions come from the model.
5. A dedicated login reads `agent_analytics.listening_events` in a repeatable-read,
   read-only transaction. Application setup overrides session defaults and applies
   a 3-second statement timeout and 1-second lock timeout. Connections time out
   after 5 seconds; model HTTP requests time out after 30 seconds.
6. A deterministic local renderer returns interpreted filters, supporting rows,
   aggregate totals, coverage, truncation, and limitations. There is no second
   model request containing results, and no generated numerical narrative.

The LLM interprets the question; it does not see or summarize query results.
Inspect the printed filters before relying on an answer. Parameter validation
prevents arbitrary SQL even if model instructions are ignored. It cannot prove
that the model understood an ambiguous question correctly.

## Approved tools

| Tool | Scope |
| --- | --- |
| `top_tracks` | Song + album pairs ranked by unrounded capped listening duration or playback event count |
| `monthly_listening` | Latest-first calendar-month groups; dated events only |
| `device_usage` | Devices ranked by unrounded capped duration |
| `skip_rates` | Count-weighted skips overall or grouped by month/device |
| `clarify` | Fixed clarification/refusal message; no database connection |

Every analytics tool accepts an exact device label or null, both date boundaries
or neither, and a limit from 1–60. Dates use the export's local date, with an
inclusive start and exclusive end. Top-track ties use song/album as deterministic
secondary ordering; this agent returns at most the requested limit, unlike the
Power BI rank measure that includes ties. Monthly results return existing groups
only; missing months are not filled with zeroes. Truncated responses say so.

The monthly tool's `scope_totals` includes undated events when no dates were
requested, while its monthly rows always exclude them. Each answer explains
this distinction. Date-bounded queries exclude undated events, and their true
dates cannot be assigned to the requested window. The coverage numbers describe
the selected device's all-time eligible events, not an inferred date window.

Artist analytics, arbitrary track/album filters, causal explanations, multiple
operations per question, arbitrary SQL, data changes, and web UI are unsupported.

## Database permissions

`sql/agent_views.sql` adds a separate security-barrier reporting view that projects
only dates, normalized song/album/device labels, capped duration, and skip flag
from the existing Power BI view. It exposes no Event ID, account/location fields,
source paths, or ETL audit records. Existing ETL and Power BI SQL is unchanged.

The administrator-only provisioner creates `music_insights_agent` with LOGIN,
NOINHERIT, NOSUPERUSER, NOCREATEDB, NOCREATEROLE, NOREPLICATION, NOBYPASSRLS,
and a connection limit of 3. It grants CONNECT, schema USAGE, and SELECT on the
single reporting view; no base-table grants or future-table grants are added.
Defaults set read-only transactions, a restricted search path, and timeouts.
Existing roles with unexpected elevation, membership, write access, schema/database
creation rights, or other application-table read access fail the permission audit.
Provisioning is transactional and can rotate the agent password on a later run.

Runtime repeats the effective privilege audit, rejects owner/admin connections,
and never falls back to `DATABASE_URL`. It uses only `AGENT_DATABASE_URL`.
PostgreSQL's global PUBLIC permissions are not revoked from the cluster; this
avoids changing other applications' privileges. This role is not a sandbox for
arbitrary SQL: built-in catalog/function and inherited PUBLIC privileges still
exist. The fixed tool surface and application read-only transaction are required
parts of the security boundary. Administrators must not grant this role extra
privileges. Use a dedicated database for this project.

## Setup

Install the existing requirements; the agent adds no third-party dependencies:

```bash
python -m pip install -r requirements-dev.txt
```

Keep `.env` ignored and private. Preserve existing settings; copy needed fields
from `.env.example` instead of overwriting an existing `.env`.

Start the existing project database, then apply the existing schema, analytics,
and Power BI view if not already installed. They are prerequisites, not steps to
rerun or reload listening data unnecessarily:

```bash
docker start music-insights-postgres
```

For a new installation, set `ADMIN_DATABASE_URL` to an administrator for the
project database and `AGENT_DB_PASSWORD` to a newly generated random password of
at least 24 characters, through environment variables or local `.env`. Use the
provisioner once:

```bash
python -m src.agent.provision
```

It reads the checked-in SQL; no credentials belong in that SQL. It does not
write credential files or print passwords. Set `AGENT_DATABASE_URL` to the same
host/database with user `music_insights_agent` and the new password. Psycopg URL
and libpq connection-string formats are accepted. Percent-encode URL passwords.
Unset `ADMIN_DATABASE_URL` and `AGENT_DB_PASSWORD` in the normal runtime environment.

The local project database has already been provisioned and its runtime DSN is
saved in the ignored workspace `.env` with mode 0600. Docker was stopped after
verification. That credential file is intentionally absent from Git.

Set `OPENAI_API_KEY` and `OPENAI_MODEL` locally. Choose a model available to your
account that supports Responses API strict function tools. No model ID is guessed
or hard-coded. See OpenAI's [function calling documentation](https://developers.openai.com/api/docs/guides/function-calling).

Run the terminal prompt (no persistent chat history):

```bash
python -m src.agent.cli
```

Or ask one question:

```bash
python -m src.agent.cli --question 'What are my top 10 tracks by listening hours, all time?'
python -m src.agent.cli --question 'Show my monthly listening for July through September 2026.'
python -m src.agent.cli --question 'Show my listening by device, all time.'
python -m src.agent.cli --question 'What was my iPhone skip rate in August 2026?'
```

The model is told to resolve relative dates from the machine's current date,
not the latest imported listening date. Prefer explicit dates for reproducible
questions. Inputs containing multiple questions or unavailable filters should
produce a clarification; live model routing has not yet been evaluated.

## Privacy

Only question text and the public static tool contract go to OpenAI. Questions
may themselves contain private names, dates, or preferences, so avoid putting
sensitive information in them. `store=false` is requested; this does not promise
zero provider retention or override your account's data policies. No API keys,
DSNs, database records, query results, schemas, or listening-history files are
sent as model inputs. Errors omit provider bodies and database diagnostics.

Answers stay on the terminal. Database strings are JSON-escaped, including
terminal control characters. The application adds no history files, telemetry,
or answer logs. Terminal recording, scrollback, shell history, and manually
redirected output remain the user's responsibility; the interactive prompt
avoids putting questions in shell command history.

## Verification

October 22, 2026:

- 39 unit/integration/regression tests passed, including the existing private
  CSV → Parquet → PostgreSQL rerun and SQL/Pandas reconciliation test.
- Power BI metadata: 3 pages, 32 visuals, and 41 schema-validated files passed.
- 8/8 synthetic recorded-plan evaluation cases passed. These are tool/evidence
  evaluations, not evidence of real model understanding.
- The restricted production login returned 160,417 eligible events,
  3,472.07 capped hours, 19.35% skips, and 56,679 undated eligible events.
  The original ETL row count was unchanged by provisioning.
- Tested denied base-table and other-view reads, INSERT/UPDATE/DELETE/TRUNCATE,
  schema/table changes, role creation, and grants, independently of the read-only
  default. Tested excessive SELECT grants, administrator credentials, and SQL
  injection in filter values. Application setup handles altered session defaults.
- HTTP adapter tests used simulated API responses; no live LLM call ran.

The integration/evaluation account requires CREATEDB and CREATEROLE on a
**disposable** PostgreSQL 17 instance. CI already uses its isolated postgres
superuser; normal agent credentials must never have these permissions.

```bash
docker run --detach --rm --name music-insights-agent-tests \
  -e POSTGRES_PASSWORD=verification \
  -p 127.0.0.1:55434:5432 postgres:17-alpine
# Wait for accepting connections:
docker exec music-insights-agent-tests pg_isready -U postgres

export TEST_DATABASE_URL=postgresql://postgres:verification@127.0.0.1:55434/postgres
python -m unittest discover -s tests -t . -v
python powerbi/validate_project.py --schemas
python -m evals.run_agent

# Optional live model routing evaluation, using synthetic questions only:
# Configure OPENAI_API_KEY and OPENAI_MODEL first. This incurs provider usage.
python -m evals.run_agent --live

docker stop music-insights-agent-tests
```

The evaluator creates and drops its own uniquely named database and role. Its
fixture SQL and expected numerical results contain synthetic data only. By
default it replays recorded plans. `--live` checks actual question-to-tool/argument
routing against the same explicit expectations before checking SQL evidence.
It prints case IDs and pass/fail summaries, never model bodies or listening rows.
Set `MUSIC_SOURCE_CSV` for the existing optional private-export regression test.

## Next checks

1. Configure the model/key locally and run the live synthetic routing evaluation.
2. Review interpreted filters on representative personal questions, especially
   relative dates and unsupported filters. Expand the evaluation set before
   changing tool capabilities.
3. Keep database refresh explicit. The agent reads the current PostgreSQL snapshot;
   it does not refresh the ETL or the separate Power BI CSV snapshot.
4. Consider a web UI only after live routing quality is verified. No web interface
   is part of this milestone implementation.
