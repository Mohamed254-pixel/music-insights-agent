"""Run known-answer evaluations in a disposable synthetic database.

Default: replay recorded plans (tool/SQL/evidence evaluation, no model request).
--live: also evaluate real natural-language routing using OPENAI_API_KEY/MODEL.
"""

import argparse
import os
from pathlib import Path
import unittest
from datetime import date

import psycopg
from dotenv import load_dotenv

from src.agent.cli import ROOT, render
from src.agent.contracts import AgentError
from src.agent.planner import OpenAIPlanner
from src.agent.tools import AnalyticsTools
from tests.agent_support import AgentSandbox, cases
from evals.checks import check_plan, check_evidence


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Send the synthetic questions to OpenAI; incurs provider usage.")
    parser.add_argument("--repeat", type=int, choices=range(1, 4), default=1,
                        help="Run every case 1–3 times; live mode makes a new model request each time.")
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    args = parser.parse_args(argv)
    load_dotenv(args.env_file, override=False)
    if not os.getenv("TEST_DATABASE_URL"):
        print("Set TEST_DATABASE_URL to a disposable PostgreSQL administrator with CREATEDB and CREATEROLE.")
        return 1
    test = unittest.TestCase()
    passed = 0
    fixtures = cases()
    total = len(fixtures) * args.repeat
    try:
        planner = OpenAIPlanner(os.getenv("OPENAI_API_KEY"), os.getenv("OPENAI_MODEL")) if args.live else None
        with AgentSandbox(os.environ["TEST_DATABASE_URL"]) as sandbox:
            tools = AnalyticsTools(sandbox.agent_url, sandbox.role)
            for iteration in range(args.repeat):
                for case in fixtures:
                    label = case["id"] + (f" [{iteration + 1}/{args.repeat}]" if args.repeat > 1 else "")
                    try:
                        if planner:
                            name, arguments = planner.plan(case["question"], today=date(2026, 10, 22))
                            check_plan(test, case, name, arguments)
                        else:
                            name, arguments = case["tool"], case["arguments"]
                        result = tools.run(name, arguments)
                        check_evidence(test, case, result)
                        if name != "clarify":
                            test.assertIn("Missing-date limitation", render(result))
                        passed += 1
                        print(label + ": PASS")
                    except AssertionError:
                        print(label + ": FAIL (routing or evidence mismatch; no private output logged)")
                    except AgentError:
                        print(label + ": FAIL (model response or availability; no private output logged)")
    except (psycopg.Error, AgentError):
        print("Evaluation setup failed. Check configuration and disposable-database permissions.")
        return 1
    print(f"{passed}/{total} cases passed; mode={'live LLM routing' if args.live else 'recorded plans, no LLM requests'}.")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
