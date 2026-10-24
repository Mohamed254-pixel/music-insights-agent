"""Run known-answer evaluations in a disposable synthetic database.

Default: replay recorded plans (tool/SQL/evidence evaluation, no model request).
--live: also evaluate real natural-language routing using OPENAI_API_KEY/MODEL.
"""

import argparse
import os
import unittest
from datetime import date

import psycopg
from dotenv import load_dotenv

from src.agent.cli import ROOT, render
from src.agent.contracts import AgentError
from src.agent.planner import OpenAIPlanner
from src.agent.tools import AnalyticsTools
from tests.agent_support import AgentSandbox, assert_subset, cases


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Send the synthetic questions to OpenAI; incurs provider usage.")
    args = parser.parse_args(argv)
    load_dotenv(ROOT / ".env", override=False)
    if not os.getenv("TEST_DATABASE_URL"):
        print("Set TEST_DATABASE_URL to a disposable PostgreSQL administrator with CREATEDB and CREATEROLE.")
        return 1
    test = unittest.TestCase()
    passed = 0
    try:
        planner = OpenAIPlanner(os.getenv("OPENAI_API_KEY"), os.getenv("OPENAI_MODEL")) if args.live else None
        with AgentSandbox(os.environ["TEST_DATABASE_URL"]) as sandbox:
            tools = AnalyticsTools(sandbox.agent_url, sandbox.role)
            for case in cases():
                try:
                    if planner:
                        name, arguments = planner.plan(case["question"], today=date(2026, 10, 22))
                        test.assertEqual(name, case["tool"])
                        test.assertEqual(arguments, case["arguments"])
                    else:
                        name, arguments = case["tool"], case["arguments"]
                    result = tools.run(name, arguments)
                    assert_subset(test, case["expected"], result)
                    if name != "clarify":
                        test.assertIn("Missing-date limitation", render(result))
                    passed += 1
                    print(case["id"] + ": PASS")
                except (AgentError, AssertionError):
                    print(case["id"] + ": FAIL (routing, evidence, or availability; no private output logged)")
    except (psycopg.Error, AgentError):
        print("Evaluation setup failed. Check configuration and disposable-database permissions.")
        return 1
    print(f"{passed}/{len(cases())} cases passed; mode={'live LLM routing' if args.live else 'recorded plans, no LLM requests'}.")
    return 0 if passed == len(cases()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
