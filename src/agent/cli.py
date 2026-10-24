"""Terminal Q&A: python -m src.agent.cli --question 'What are my top tracks?'"""

import argparse
import json
import os
from datetime import date
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv

from .contracts import AgentError
from .planner import OpenAIPlanner
from .tools import AnalyticsTools

ROOT = Path(__file__).resolve().parents[2]


def json_value(value):
    if isinstance(value, (Decimal, date)):
        return str(value)
    raise TypeError("Unsupported result type")


def render(result):
    """Deterministic numerical evidence; no model-written claims or terminal escapes."""
    if result["tool"] == "clarify":
        return {"unsupported": "This agent supports top tracks, monthly listening, device usage, and skip rates only. Ask one supported question; SQL execution and data changes are unavailable.",
                "ambiguous": "Please specify one supported metric, period, and any device filter.",
                "dates": "Please specify a calendar month or an explicit start and end date."}[result["reason"]]
    coverage = result["date_coverage"]
    args = result["filters"]
    lines = ["Verified database evidence (tool and interpreted filters shown below).",
             json.dumps(result, default=json_value, ensure_ascii=True, indent=2)]
    if not result["scope_totals"]["listening_events"]:
        lines.append("No eligible events match these filters. This is not proof of no listening outside the imported dataset.")
    if result["dated_rows_only"]:
        lines.append("Monthly rows use dated events only; missing months are not filled with zeros. Rows are latest-first.")
    if args["start_date"]:
        lines.append("Date window uses local dates: inclusive start, exclusive end. Undated events are excluded; their dates cannot be assigned to this window.")
    else:
        lines.append("All-time totals include undated events; monthly rows exclude them.")
    lines.append(f"Missing-date limitation: {coverage['undated_events']:,} of {coverage['all_time_events']:,} eligible events in the selected device's all-time scope have no date. No missing dates are inferred.")
    if result["truncated"]:
        lines.append(f"Results limited to {args['limit']} groups. Ties at the boundary are broken deterministically; scope totals are not limited.")
    if result["tool"] == "top_tracks":
        lines.append("Track identity is normalized song + album; repeat playback events count again. Rankings use the requested hours or event counts.")
    lines.append("Hours use capped durations. Skip rate is skipped events / eligible events, not an average of percentages. These data cannot explain personal motives.")
    return "\n\n".join(lines)


def answer(question, planner, tools):
    name, arguments = planner.plan(question)
    return render(tools.run(name, arguments))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--question", help="One question; omit for a terminal prompt without persistent history.")
    args = parser.parse_args(argv)
    load_dotenv(args.env_file, override=False)
    try:
        planner = OpenAIPlanner(os.getenv("OPENAI_API_KEY"), os.getenv("OPENAI_MODEL"))
        tools = AnalyticsTools(os.getenv("AGENT_DATABASE_URL"))
        if args.question is not None:
            print(answer(args.question, planner, tools))
            return 0
        print("Music Insights — read-only terminal. Questions go to OpenAI; query results stay local. Type /quit to exit.")
        while True:
            try:
                question = input("Ask> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return 0
            if question == "/quit":
                return 0
            if not question:
                continue
            try:
                print(answer(question, planner, tools))
            except AgentError as error:
                print(str(error))
    except AgentError as error:
        print(str(error))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
