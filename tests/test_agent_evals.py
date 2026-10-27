"""Regression checks for evaluation policy and refused-question execution paths."""

import io
import json
import unittest
from copy import deepcopy
from unittest.mock import Mock, patch

from evals.checks import check_plan, check_evidence
from src.agent.cli import answer
from src.agent.contracts import validate_call
from src.agent.planner import OpenAIPlanner
from src.agent.tools import AnalyticsTools
from tests.agent_support import cases


class EvaluationPolicyTests(unittest.TestCase):
    def test_case_ids_are_unique_and_all_recorded_plans_obey_contracts(self):
        fixtures = cases()
        self.assertEqual(len({case['id'] for case in fixtures}), len(fixtures))
        for case in fixtures:
            with self.subTest(case=case['id']):
                validate_call(case['tool'], case['arguments'])
                check_plan(self, case, case['tool'], case['arguments'])
                for arguments in case.get('accepted_arguments', []):
                    validate_call(case['tool'], arguments)
                    check_plan(self, case, case['tool'], arguments)

    def test_ambiguous_and_unsafe_questions_render_without_database_access(self):
        for case in cases():
            if case['tool'] != 'clarify':
                continue
            with self.subTest(case=case['id']), patch('src.agent.tools.psycopg.connect') as connect:
                response = {'status': 'completed', 'output': [
                    {'type': 'function_call', 'name': 'clarify',
                     'arguments': json.dumps(case['arguments'])}]}
                opener = Mock(return_value=io.BytesIO(json.dumps(response).encode()))
                planner = OpenAIPlanner('synthetic-key', 'test-model', opener)
                text = answer(case['question'], planner, AnalyticsTools('unused'))
                self.assertTrue(text)
                connect.assert_not_called()

    def test_clarification_synonyms_never_allow_a_database_action(self):
        case = next(c for c in cases() if c['id'] == 'ambiguous_recent')
        for reason in ('dates', 'ambiguous'):
            check_plan(self, case, 'clarify', {'reason': reason})
            check_evidence(self, case, {'tool': 'clarify', 'reason': reason})
        with self.assertRaises(AssertionError):
            check_plan(self, case, 'device_usage', cases()[3]['arguments'])
        with self.assertRaises(AssertionError):
            check_plan(self, case, 'clarify', {'reason': 'dates', 'sql': 'SELECT 1'})
        with self.assertRaises(AssertionError):
            check_evidence(self, case, {'tool': 'clarify', 'reason': 'unsupported'})

    def test_equivalent_reason_check_does_not_mutate_expected_fixture(self):
        case = next(c for c in cases() if c['id'] == 'multiple_questions')
        before = deepcopy(case)
        check_evidence(self, case, {'tool': 'clarify', 'reason': 'unsupported'})
        self.assertEqual(case, before)

    def test_wrong_dates_device_rank_or_evidence_cannot_pass(self):
        for case_id, key, wrong in [('combined_filters', 'device', 'MACINTOSH'),
                                    ('combined_filters', 'end_date', '2026-08-31'),
                                    ('top_hours', 'rank_by', 'events')]:
            case = next(c for c in cases() if c['id'] == case_id)
            with self.subTest(case=case_id), self.assertRaises(AssertionError):
                check_plan(self, case, case['tool'], {**case['arguments'], key: wrong})
        case = next(c for c in cases() if c['id'] == 'weighted_skip')
        with self.assertRaises(AssertionError):
            check_evidence(self, case, {'rows': [{'listening_events': 7, 'skipped_events': 3,
                                                'skip_rate_percent': '44.44'}],
                                       'date_coverage': {'all_time_events': 7, 'undated_events': 1}})

    def test_equivalent_overall_limits_do_not_allow_wrong_scope(self):
        case = next(c for c in cases() if c['id'] == 'weighted_skip')
        check_plan(self, case, 'skip_rates', {**case['arguments'], 'limit': 1})
        for changes in ({'device': 'IPHONE'}, {'group_by': 'device'}, {'limit': 61}):
            with self.subTest(changes=changes), self.assertRaises(AssertionError):
                check_plan(self, case, 'skip_rates', {**case['arguments'], **changes})

    def test_repeats_use_new_model_requests_and_stop_wrong_plans_before_tools(self):
        from contextlib import redirect_stdout
        from types import SimpleNamespace
        from evals.run_agent import main
        case = next(c for c in cases() if c['id'] == 'unsupported')
        with patch.dict('os.environ', {'TEST_DATABASE_URL': 'unused', 'OPENAI_API_KEY': 'test-key', 'OPENAI_MODEL': 'test-model'}), \
             patch('evals.run_agent.load_dotenv'), \
             patch('evals.run_agent.cases', return_value=[case]), \
             patch('evals.run_agent.AgentSandbox') as sandbox, \
             patch('evals.run_agent.OpenAIPlanner') as planner, \
             patch('evals.run_agent.AnalyticsTools') as tools:
            sandbox.return_value.__enter__.return_value = SimpleNamespace(agent_url='unused', role='unused')
            planner.return_value.plan.side_effect = [('clarify', {'reason': 'unsupported'}),
                                                     ('clarify', {'reason': 'dates'})]
            tools.return_value.run.return_value = {'tool': 'clarify', 'reason': 'unsupported'}
            output = io.StringIO()
            with redirect_stdout(output):
                code = main(['--live', '--repeat', '2'])
            self.assertEqual(code, 1)
            self.assertEqual(planner.return_value.plan.call_count, 2)
            tools.return_value.run.assert_called_once_with('clarify', {'reason': 'unsupported'})
            self.assertIn('1/2 cases passed', output.getvalue())
            planner.return_value.plan.side_effect = [('clarify', {'reason': 'unsupported'})] * 2
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(['--live', '--repeat', '2']), 0)

    def test_provider_failure_is_not_counted_as_successful_refusal(self):
        from contextlib import redirect_stdout
        from types import SimpleNamespace
        from evals.run_agent import main
        from src.agent.contracts import AgentError
        case = next(c for c in cases() if c['id'] == 'unsupported')
        with patch.dict('os.environ', {'TEST_DATABASE_URL': 'unused', 'OPENAI_API_KEY': 'test-key', 'OPENAI_MODEL': 'test-model'}), \
             patch('evals.run_agent.load_dotenv'), \
             patch('evals.run_agent.cases', return_value=[case]), \
             patch('evals.run_agent.AgentSandbox') as sandbox, \
             patch('evals.run_agent.OpenAIPlanner') as planner, \
             patch('evals.run_agent.AnalyticsTools') as tools:
            sandbox.return_value.__enter__.return_value = SimpleNamespace(agent_url='unused', role='unused')
            planner.return_value.plan.side_effect = AgentError('Provider unavailable')
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(['--live']), 1)
            tools.return_value.run.assert_not_called()
            self.assertIn('0/1 cases passed', output.getvalue())
