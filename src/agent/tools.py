"""Fixed parameterized queries, a restricted login, and one read-only snapshot."""

import psycopg
from psycopg.rows import dict_row

from .contracts import AgentError, validate_call

ROLE = "music_insights_agent"
VIEW = "agent_analytics.listening_events"
FILTER = """(%(device)s::text IS NULL OR device_type = %(device)s)
 AND (%(start_date)s::date IS NULL OR listening_date >= %(start_date)s::date)
 AND (%(end_date)s::date IS NULL OR listening_date < %(end_date)s::date)"""
METRICS = """COUNT(*) AS listening_events,
 ROUND(COALESCE(SUM(listening_duration_ms), 0) / 3600000.0, 2) AS listening_hours,
 COUNT(DISTINCT (song_name, album_name)) AS unique_tracks,
 COUNT(*) FILTER (WHERE is_skipped) AS skipped_events,
 ROUND(COUNT(*) FILTER (WHERE is_skipped) * 100.0 / NULLIF(COUNT(*), 0), 2) AS skip_rate_percent"""
BASE = f"FROM {VIEW} WHERE {FILTER}"
# Dynamic selection below chooses only complete, developer-owned SQL constants.
TOP = {
    "hours": f"SELECT song_name, album_name, {METRICS} {BASE} GROUP BY song_name, album_name ORDER BY SUM(listening_duration_ms) DESC, song_name, album_name LIMIT %(fetch_limit)s",
    "events": f"SELECT song_name, album_name, {METRICS} {BASE} GROUP BY song_name, album_name ORDER BY COUNT(*) DESC, song_name, album_name LIMIT %(fetch_limit)s",
}
MONTHLY = f"""SELECT DATE_TRUNC('month', listening_date)::date AS listening_month,
 {METRICS} {BASE} AND listening_date IS NOT NULL
 GROUP BY 1 ORDER BY 1 DESC LIMIT %(fetch_limit)s"""
DEVICES = f"SELECT device_type, {METRICS} {BASE} GROUP BY device_type ORDER BY SUM(listening_duration_ms) DESC, device_type LIMIT %(fetch_limit)s"
OVERALL = f"SELECT {METRICS} {BASE}"
COVERAGE = f"""SELECT COUNT(*) AS all_time_events,
 COUNT(*) FILTER (WHERE listening_date IS NULL) AS undated_events,
 MIN(listening_date) AS earliest_date, MAX(listening_date) AS latest_date
 FROM {VIEW} WHERE (%(device)s::text IS NULL OR device_type = %(device)s)"""


def check_role(connection, expected_role=ROLE, *, require_direct_login=True):
    """Fail closed if someone accidentally supplies the ETL/admin connection."""
    identity = connection.execute("""SELECT current_user AS name,
      session_user = current_user AS direct_login, rolcanlogin, rolsuper, rolcreatedb,
      rolcreaterole, rolreplication, rolbypassrls, rolinherit
      FROM pg_catalog.pg_roles WHERE rolname = current_user""").fetchone()
    if (identity["name"] != expected_role or not identity["rolcanlogin"]
            or (require_direct_login and not identity["direct_login"])
            or any(identity[k] for k in ("rolsuper", "rolcreatedb", "rolcreaterole",
                                        "rolreplication", "rolbypassrls", "rolinherit"))):
        raise AgentError("Use the dedicated agent login, never the ETL or administrator login.")
    if connection.execute("SELECT 1 FROM pg_catalog.pg_auth_members WHERE member = (SELECT oid FROM pg_catalog.pg_roles WHERE rolname=current_user)").fetchone():
        raise AgentError("The agent login must not belong to other roles.")
    unsafe = connection.execute("""SELECT 1 FROM pg_catalog.pg_class c
      JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
      WHERE n.nspname NOT LIKE 'pg_%' AND n.nspname <> 'information_schema'
      AND c.relkind IN ('r','p','v','m','f') AND (
        c.relowner = (SELECT oid FROM pg_catalog.pg_roles WHERE rolname=current_user)
        OR pg_catalog.has_table_privilege(c.oid,'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
        OR pg_catalog.has_any_column_privilege(c.oid,'INSERT,UPDATE,REFERENCES')
        OR ((n.nspname <> 'agent_analytics' OR c.relname <> 'listening_events')
            AND pg_catalog.has_any_column_privilege(c.oid,'SELECT')))
      LIMIT 1""").fetchone()
    database_create = connection.execute("SELECT pg_catalog.has_database_privilege(current_database(), 'CREATE') AS allowed").fetchone()["allowed"]
    if unsafe or database_create or connection.execute("""SELECT 1 FROM pg_catalog.pg_namespace
      WHERE nspname NOT LIKE 'pg_%' AND nspname <> 'information_schema'
      AND pg_catalog.has_schema_privilege(oid,'CREATE') LIMIT 1""").fetchone():
        raise AgentError("The agent login has privileges beyond the approved reporting view.")
    if not connection.execute("SELECT pg_catalog.has_table_privilege(%s,'SELECT') AS allowed", (VIEW,)).fetchone()["allowed"]:
        raise AgentError("The agent login lacks SELECT on the approved reporting view.")


class AnalyticsTools:
    def __init__(self, database_url, expected_role=ROLE):
        if not database_url:
            raise AgentError("Set AGENT_DATABASE_URL to the dedicated read-only login.")
        self.database_url = database_url
        self.expected_role = expected_role

    def run(self, name, arguments):
        args = validate_call(name, arguments)
        if name == "clarify":
            return {"tool": name, "reason": args["reason"]}
        parameters = {**args, "fetch_limit": args["limit"] + 1}
        query = {"top_tracks": TOP.get(args.get("rank_by")),
                 "monthly_listening": MONTHLY, "device_usage": DEVICES,
                 "skip_rates": {"overall": OVERALL, "device": DEVICES, "month": MONTHLY}.get(args.get("group_by"))}[name]
        try:
            with psycopg.connect(self.database_url, connect_timeout=5,
                                 row_factory=dict_row, autocommit=True) as connection:
                # No model-controlled text reaches session setup or SQL construction.
                connection.execute("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY")
                try:
                    connection.execute("SET LOCAL statement_timeout = '3000ms'")
                    connection.execute("SET LOCAL lock_timeout = '1000ms'")
                    connection.execute("SET LOCAL search_path = pg_catalog, agent_analytics")
                    check_role(connection, self.expected_role)
                    coverage = connection.execute(COVERAGE, parameters).fetchone()
                    totals = connection.execute(OVERALL, parameters).fetchone()
                    rows = connection.execute(query, parameters).fetchmany(args["limit"] + 1)
                finally:
                    connection.execute("ROLLBACK")
        except psycopg.Error:
            raise AgentError("The read-only database query failed. Check agent provisioning, connection settings, and database availability.") from None
        monthly = name == "monthly_listening" or (name == "skip_rates" and args.get("group_by") == "month")
        return {"tool": name, "filters": args, "scope_totals": totals,
                "date_coverage": coverage, "dated_rows_only": monthly,
                "truncated": len(rows) > args["limit"], "rows": rows[:args["limit"]]}
