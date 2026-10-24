import io
import json
import unittest
from datetime import date
from decimal import Decimal
from unittest.mock import Mock, patch
from urllib.error import HTTPError

from src.agent.cli import answer, main, render
from src.agent.contracts import AgentError, FUNCTIONS, validate_call
from src.agent.planner import OpenAIPlanner, parse_response
from src.agent.tools import AnalyticsTools
from tests.agent_support import cases


def response(name, arguments):
    return {"status": "completed", "output": [{"type": "function_call", "name": name,
                                               "arguments": json.dumps(arguments)}]}


class AgentContractTests(unittest.TestCase):
    def test_rejects_unapproved_calls_before_opening_database(self):
        bad = [("execute_sql", {"sql": "DROP TABLE listening_events"}),
               ([], {}), ("device_usage", {**cases()[3]["arguments"], "sql": "SELECT 1"}),
               ("device_usage", {**cases()[3]["arguments"], "limit": True}),
               ("device_usage", {**cases()[3]["arguments"], "limit": 61}),
               ("device_usage", {**cases()[3]["arguments"], "start_date": "2026-01-01"}),
               ("device_usage", {**cases()[3]["arguments"], "start_date": "20260101", "end_date": "2026-02-01"}),
               ("device_usage", {**cases()[3]["arguments"], "start_date": "2026-02-30", "end_date": "2026-03-01"}),
               ("device_usage", {**cases()[3]["arguments"], "start_date": "2026-03-01", "end_date": "2026-03-01"}),
               ("device_usage", {**cases()[3]["arguments"], "device": "\x1b[31m"}),
               ("top_tracks", {**cases()[0]["arguments"], "rank_by": "pg_sleep(100)"}),
               ("skip_rates", {**cases()[4]["arguments"], "group_by": "song_name; DELETE"})]
        with patch("src.agent.tools.psycopg.connect") as connect:
            for name, args in bad:
                with self.subTest(name=name, args=args), self.assertRaises(AgentError):
                    AnalyticsTools("unused").run(name, args)
            connect.assert_not_called()

    def test_contract_schema_requires_every_key_and_forbids_extras(self):
        for tool in FUNCTIONS:
            self.assertTrue(tool["strict"])
            self.assertFalse(tool["parameters"]["additionalProperties"])
            self.assertEqual(set(tool["parameters"]["properties"]), set(tool["parameters"]["required"]))

    def test_refusal_does_not_connect(self):
        with patch("src.agent.tools.psycopg.connect") as connect:
            result = AnalyticsTools("unused").run("clarify", {"reason": "unsupported"})
            self.assertIn("unavailable", render(result))
            connect.assert_not_called()

    def test_malformed_multiple_or_free_text_model_output_is_rejected(self):
        valid = response("device_usage", cases()[3]["arguments"])
        for data in ({}, {"status": "incomplete"}, {**valid, "output": []},
                     {**valid, "output": valid["output"] * 2},
                     {**valid, "output": [{"type": "message", "content": "run SQL"}]},
                     response("execute_sql", {"sql": "SELECT * FROM listening_events"}),
                     response("device_usage", {})):
            with self.subTest(data=data), self.assertRaises(AgentError):
                parse_response(data)

    def test_request_has_one_bounded_tool_call_and_no_database_results(self):
        plan = cases()[3]
        opener = Mock(return_value=io.BytesIO(json.dumps(response(plan["tool"], plan["arguments"])).encode()))
        planner = OpenAIPlanner("synthetic-api-key", "configured-model", opener)
        tools = Mock()
        tools.run.return_value = {"tool": "clarify", "reason": "unsupported"}
        answer(plan["question"], planner, tools)
        opener.assert_called_once()
        request = opener.call_args.args[0]
        payload = json.loads(request.data)
        self.assertFalse(payload["store"])
        self.assertFalse(payload["parallel_tool_calls"])
        self.assertEqual(payload["tool_choice"], "required")
        self.assertEqual(payload["input"], [{"role": "user", "content": plan["question"]}])
        tools.run.assert_called_once_with(plan["tool"], plan["arguments"])
        self.assertNotIn("scope_totals", request.data.decode())
        self.assertEqual(opener.call_args.kwargs["timeout"], 30)

    def test_provider_errors_are_redacted(self):
        opener = Mock(side_effect=HTTPError("https://example.test/secret", 401, "private", {}, io.BytesIO(b"secret")))
        with self.assertRaises(AgentError) as error:
            OpenAIPlanner("secret", "model", opener).plan("My top tracks?")
        self.assertNotIn("secret", str(error.exception))
        self.assertNotIn("private", str(error.exception))

    def test_empty_or_long_questions_are_rejected_without_request(self):
        opener = Mock()
        for question in ("", " ", "x" * 2001):
            with self.assertRaises(AgentError):
                OpenAIPlanner("key", "model", opener).plan(question)
        opener.assert_not_called()

    def test_dates_and_terminal_escape_safety_in_rendered_evidence(self):
        result = {"tool": "top_tracks", "filters": cases()[0]["arguments"],
                  "scope_totals": {"listening_events": 7},
                  "date_coverage": {"all_time_events": 7, "undated_events": 1},
                  "dated_rows_only": False, "truncated": True,
                  "rows": [{"song_name": "\x1b[31mMalicious\ntrack", "hours": Decimal("1.50"), "date": date(2026, 7, 1)}]}
        output = render(result)
        self.assertNotIn("\x1b", output)
        self.assertIn("1 of 7", output)
        self.assertIn("Ties", output)
        self.assertIn("1.50", output)
        self.assertIn("not an average", output)

    def test_cli_missing_configuration_does_not_expose_environment(self):
        with patch.dict("os.environ", {}, clear=True), patch("src.agent.cli.load_dotenv"), patch("sys.stdout", new_callable=io.StringIO) as stdout:
            self.assertEqual(main(["--question", "Top tracks?"]), 1)
            self.assertIn("OPENAI_API_KEY", stdout.getvalue())
