import os
import secrets
import unittest
from decimal import Decimal
from unittest.mock import patch

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from src.agent.cli import answer, render
from src.agent.contracts import AgentError
from src.agent.tools import AnalyticsTools, check_role
from src.agent.provision import provision
from tests.agent_support import AgentSandbox, assert_subset, cases


@unittest.skipUnless(os.getenv("TEST_DATABASE_URL"), "Set TEST_DATABASE_URL for agent integration tests")
class AgentPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sandbox = AgentSandbox(os.environ["TEST_DATABASE_URL"])
        cls.sandbox.__enter__()
        cls.addClassCleanup(cls.sandbox.__exit__, None, None, None)
        cls.tools = AnalyticsTools(cls.sandbox.agent_url, cls.sandbox.role)

    def test_synthetic_evaluation_cases_and_local_answers(self):
        for case in cases():
            with self.subTest(case=case["id"]):
                result = self.tools.run(case["tool"], case["arguments"])
                assert_subset(self, case["expected"], result)
                class RecordedPlanner:
                    def plan(self, question):
                        return case["tool"], case["arguments"]
                output = answer(case["question"], RecordedPlanner(), self.tools)
                if case["tool"] != "clarify":
                    self.assertIn("Missing-date limitation", output)
                    self.assertIn("scope_totals", output)
                if case["id"] == "empty":
                    self.assertIn("No eligible events", output)
                if case["id"] == "monthly":
                    self.assertIn("Undated events are excluded", output)

    def test_sql_injection_device_is_a_literal_not_sql(self):
        args = {**cases()[3]["arguments"], "device": "IPHONE'; DROP TABLE public.listening_events; --"}
        result = self.tools.run("device_usage", args)
        self.assertEqual(result["rows"], [])
        with psycopg.connect(self.sandbox.owner_url) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM listening_events").fetchone()[0], 8)

    def test_login_is_restricted_and_default_session_is_read_only(self):
        with psycopg.connect(self.sandbox.agent_url, row_factory=dict_row) as connection:
            check_role(connection, self.sandbox.role)
            self.assertEqual(connection.execute("SHOW transaction_read_only").fetchone()["transaction_read_only"], "on")
            self.assertEqual(connection.execute("SHOW statement_timeout").fetchone()["statement_timeout"], "3s")
            self.assertEqual(connection.execute("SELECT COUNT(*) AS n FROM agent_analytics.listening_events").fetchone()["n"], 7)

    def test_base_tables_other_views_and_mutations_denied(self):
        attempts = ["SELECT * FROM public.listening_events", "SELECT * FROM public.etl_runs",
                    "SELECT * FROM analytics.powerbi_listening_events", "SELECT * FROM analytics.valid_listening_events",
                    "INSERT INTO public.listening_events (event_id) VALUES ('bad')",
                    "UPDATE agent_analytics.listening_events SET is_skipped=false", "DELETE FROM agent_analytics.listening_events",
                    "TRUNCATE public.listening_events", "CREATE TABLE public.bad (n int)",
                    "DROP VIEW agent_analytics.listening_events", "ALTER TABLE public.listening_events ADD COLUMN bad int",
                    "CREATE ROLE bad_agent_role", "GRANT SELECT ON public.listening_events TO PUBLIC"]
        for query in attempts:
            with self.subTest(query=query), psycopg.connect(self.sandbox.agent_url, autocommit=True) as connection:
                # Check ACLs independently of the protective read-only default.
                connection.execute("SET default_transaction_read_only=off")
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    connection.execute(query)

    def test_runtime_refuses_admin_connection(self):
        with self.assertRaises(AgentError):
            AnalyticsTools(self.sandbox.owner_url, self.sandbox.role).run("device_usage", cases()[3]["arguments"])

    def test_runtime_overrides_session_timeouts_and_read_write_defaults(self):
        from psycopg.conninfo import make_conninfo
        configured = make_conninfo(self.sandbox.agent_url,
                                  options="-c default_transaction_read_only=off -c statement_timeout=0")
        result = AnalyticsTools(configured, self.sandbox.role).run("skip_rates", cases()[4]["arguments"])
        self.assertEqual(result["rows"][0]["skip_rate_percent"], Decimal("42.86"))

    def test_excessive_select_grant_is_detected(self):
        with psycopg.connect(self.sandbox.owner_url) as connection:
            connection.execute(sql.SQL("GRANT SELECT ON public.listening_events TO {}").format(sql.Identifier(self.sandbox.role)))
        try:
            with self.assertRaises(AgentError):
                self.tools.run("device_usage", cases()[3]["arguments"])
        finally:
            with psycopg.connect(self.sandbox.owner_url) as connection:
                connection.execute(sql.SQL("REVOKE SELECT ON public.listening_events FROM {}").format(sql.Identifier(self.sandbox.role)))

    def test_evidence_totals_match_independent_sql(self):
        result = self.tools.run("skip_rates", cases()[4]["arguments"])
        with psycopg.connect(self.sandbox.owner_url) as connection:
            count, duration, skipped = connection.execute("""SELECT COUNT(*), SUM(LEAST(listening_duration_ms,media_duration_ms)), COUNT(*) FILTER (WHERE is_skipped)
              FROM public.listening_events WHERE is_listening_event AND listening_duration_ms>0""").fetchone()
        self.assertEqual(result["scope_totals"]["listening_events"], count)
        self.assertEqual(result["scope_totals"]["listening_hours"], duration / Decimal(3600000))
        self.assertEqual(result["scope_totals"]["skipped_events"], skipped)
        self.assertEqual(result["date_coverage"]["undated_events"], 1)

    def test_provisioning_is_idempotent_and_rotates_password_safely(self):
        from psycopg.conninfo import make_conninfo
        with AgentSandbox(os.environ["TEST_DATABASE_URL"]) as sandbox:
            password = secrets.token_urlsafe(32)
            provision(sandbox.owner_url, password, sandbox.role)
            provision(sandbox.owner_url, password, sandbox.role)
            updated = make_conninfo(sandbox.agent_url, password=password)
            result = AnalyticsTools(updated, sandbox.role).run("skip_rates", cases()[4]["arguments"])
            self.assertEqual(result["scope_totals"]["listening_events"], 7)

    def test_memberships_are_rejected(self):
        with psycopg.connect(self.sandbox.owner_url) as connection:
            connection.execute(sql.SQL("GRANT pg_read_all_data TO {}").format(sql.Identifier(self.sandbox.role)))
        try:
            with self.assertRaises(AgentError):
                self.tools.run("device_usage", cases()[3]["arguments"])
        finally:
            with psycopg.connect(self.sandbox.owner_url) as connection:
                connection.execute(sql.SQL("REVOKE pg_read_all_data FROM {}").format(sql.Identifier(self.sandbox.role)))
