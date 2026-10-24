"""Disposable database/role for synthetic security tests and evaluations."""

import json
import secrets
import uuid
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

from src.agent.provision import provision

ROOT = Path(__file__).resolve().parents[1]


class AgentSandbox:
    def __init__(self, admin_url):
        self.admin_url = admin_url
        self.database = "music_agent_test_" + uuid.uuid4().hex
        self.role = "music_insights_agent_test_" + uuid.uuid4().hex

    def __enter__(self):
        with psycopg.connect(self.admin_url, autocommit=True) as connection:
            connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(self.database)))
        try:
            self.owner_url = make_conninfo(self.admin_url, dbname=self.database)
            with psycopg.connect(self.owner_url) as connection:
                for name in ("sql/schema.sql", "sql/analytics_views.sql", "sql/powerbi_view.sql", "evals/agent_fixture.sql"):
                    connection.execute((ROOT / name).read_text())
            password = secrets.token_urlsafe(32)
            provision(self.owner_url, password, self.role)
            self.agent_url = make_conninfo(self.owner_url, user=self.role, password=password)
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def __exit__(self, *args):
        with psycopg.connect(self.admin_url, autocommit=True) as connection:
            connection.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(self.database)))
            connection.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(self.role)))


def cases():
    return json.loads((ROOT / "evals/agent_cases.json").read_text())


def assert_subset(test, expected, actual):
    """Hand-calculated fixture values; dicts specify selected evidence fields."""
    if isinstance(expected, dict):
        for key, value in expected.items():
            test.assertIn(key, actual)
            assert_subset(test, value, actual[key])
    elif isinstance(expected, list):
        test.assertEqual(len(expected), len(actual))
        for left, right in zip(expected, actual):
            assert_subset(test, left, right)
    elif expected is None or isinstance(expected, (int, bool)):
        test.assertEqual(expected, actual)
    else:
        test.assertEqual(expected, str(actual))
