"""Exact action checks with explicit, semantically equivalent alternatives."""

from copy import deepcopy

from tests.agent_support import assert_subset


def check_plan(test, case, name, arguments):
    test.assertEqual(name, case["tool"], "wrong approved action")
    accepted = case.get("accepted_arguments", [case["arguments"]])
    test.assertIn(arguments, accepted, "wrong filters or clarification reason")


def check_evidence(test, case, result):
    expected = deepcopy(case["expected"])
    if "accepted_arguments" in case and case["tool"] == "clarify":
        # Refusal synonyms can differ; analytical results always match the
        # fixture exactly, even with an equivalent overall-total row limit.
        test.assertEqual(case["tool"], "clarify")
        test.assertIn({"reason": result["reason"]}, case["accepted_arguments"])
        expected["reason"] = result["reason"]
    assert_subset(test, expected, result)
