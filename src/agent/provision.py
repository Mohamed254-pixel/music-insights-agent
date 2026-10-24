"""Admin-only provisioning. Runtime never loads ADMIN_DATABASE_URL or passwords."""

import argparse
import os
import re
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg import sql
from psycopg.rows import dict_row

from .contracts import AgentError
from .tools import ROLE, check_role

ROOT = Path(__file__).resolve().parents[2]


def provision(admin_url, password, role=ROLE):
    if not admin_url or not password or len(password) < 24:
        raise AgentError("Set ADMIN_DATABASE_URL and a random AGENT_DB_PASSWORD of at least 24 characters.")
    if not re.fullmatch(r"music_insights_agent(?:_test_[a-f0-9]+)?", role):
        raise AgentError("Unapproved agent role name.")
    with psycopg.connect(admin_url, row_factory=dict_row) as connection:
        connection.execute((ROOT / "sql/agent_views.sql").read_text())
        exists = connection.execute("SELECT 1 FROM pg_catalog.pg_roles WHERE rolname=%s", (role,)).fetchone()
        if exists:
            # Idempotent password rotation only after checking the existing role.
            with connection.transaction():
                connection.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(role)))
                # check_role requires a direct login; inspect its flags/memberships separately below.
                flags = connection.execute("SELECT rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls,rolinherit FROM pg_catalog.pg_roles WHERE rolname=current_user").fetchone()
                members = connection.execute("SELECT 1 FROM pg_catalog.pg_auth_members WHERE member=(SELECT oid FROM pg_catalog.pg_roles WHERE rolname=current_user)").fetchone()
                if any(flags.values()) or members:
                    raise AgentError("Existing agent role has unexpected elevated attributes or memberships; provisioning stopped.")
                connection.execute("RESET ROLE")
            connection.execute(sql.SQL("ALTER ROLE {} PASSWORD {}").format(sql.Identifier(role), sql.Literal(password)))
        else:
            connection.execute(sql.SQL("CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 3 PASSWORD {}").format(sql.Identifier(role), sql.Literal(password)))
        database = connection.info.dbname
        connection.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(database), sql.Identifier(role)))
        connection.execute(sql.SQL("GRANT USAGE ON SCHEMA agent_analytics TO {}").format(sql.Identifier(role)))
        connection.execute(sql.SQL("GRANT SELECT ON agent_analytics.listening_events TO {}").format(sql.Identifier(role)))
        for setting, value in (("default_transaction_read_only", "on"),
                               ("statement_timeout", "3s"), ("lock_timeout", "1s"),
                               ("idle_in_transaction_session_timeout", "5s")):
            connection.execute(sql.SQL("ALTER ROLE {} IN DATABASE {} SET {} = {}").format(
                sql.Identifier(role), sql.Identifier(database), sql.Identifier(setting), sql.Literal(value)))
        connection.execute(sql.SQL("ALTER ROLE {} IN DATABASE {} SET search_path = pg_catalog, agent_analytics").format(sql.Identifier(role), sql.Identifier(database)))
        connection.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(role)))
        check_role(connection, role, require_direct_login=False)
        connection.execute("RESET ROLE")
    return role


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    args = parser.parse_args(argv)
    load_dotenv(args.env_file, override=False)
    try:
        provision(os.getenv("ADMIN_DATABASE_URL"), os.getenv("AGENT_DB_PASSWORD"))
    except (psycopg.Error, AgentError):
        print("Provisioning failed. Check administrator access, prerequisites, role attributes, and the required environment variables. No credentials are printed.")
        return 1
    print("Agent view and SELECT-only view grants configured. Set AGENT_DATABASE_URL for the dedicated login; do not use the administrator URL at runtime.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
