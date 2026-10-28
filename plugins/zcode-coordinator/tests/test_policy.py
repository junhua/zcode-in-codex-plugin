import datetime as dt
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/'skills/zcode/scripts/policy.py'
spec=importlib.util.spec_from_file_location('peak_policy_test',SCRIPT);p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
def local(text):return dt.datetime.fromisoformat(text+'+08:00')

class PolicyTest(unittest.TestCase):
    def test_daily_exact_boundaries_and_buffer(self):
        for date in ['2026-01-01','2026-10-31','2026-11-01']:
            for clock,excluded in [('13:59:59',False),('14:00:00',True),('17:59:59',True),('18:00:00',False)]:
                moment=local(date+'T'+clock)
                self.assertEqual(p.window(moment)['excluded'],excluded)
                if clock!='18:00:00':
                    with self.assertRaises(p.PolicyError) as caught:p.admit(1,moment)
                    self.assertEqual(caught.exception.detail['next_allowed'],local(date+'T18:00:00').isoformat())
                else:self.assertFalse(p.admit(1,moment)['excluded'])
    def test_timezone_conversion_dst_independent(self):
        for offset in [-5,-4,0,8,13]:
            for date in ['2026-01-01','2026-07-01']:
                moment=local(date+'T14:00:00').astimezone(dt.timezone(dt.timedelta(hours=offset)))
                self.assertTrue(p.window(moment)['excluded'])
                self.assertEqual(p.window(moment)['timezone'],'UTC+08:00')
    def test_budget_deadline_and_equality(self):
        self.assertFalse(p.admit(58,local('2026-01-01T13:58:00'))['excluded'])
        with self.assertRaises(p.PolicyError):p.admit(60,local('2026-01-01T13:58:00'))
        with self.assertRaises(p.PolicyError):p.window(dt.datetime(2026,1,1))
        self.assertTrue(p.boundary_due(local('2026-01-01T13:59:00').isoformat(),local('2026-01-01T14:00:00')))
    def test_active_guard_rechecks_current_day_after_clock_rewind(self):
        planned=local('2026-01-02T13:59:00').isoformat()
        self.assertTrue(p.boundary_due(planned,local('2026-01-01T13:59:00')))
        self.assertFalse(p.boundary_due(planned,local('2026-01-01T18:00:00')))
    def test_routes_are_explicit_cost_heuristics(self):
        cases=[('mechanical','simple','normal','GLM-5.3-Flash','low'),('routine','bounded','normal','GLM-5.3-Flash','high'),('ui-state','hard','normal','GLM-5.3-Flash','max'),('capability','simple','normal','GLM-5.3','low'),('debugging','bounded','normal','GLM-5.3','high'),('architecture','hard','data-loss','GLM-5.3','max'),('routine','bounded','cross-service','GLM-5.3','high')]
        for kind,complexity,risk,model,effort in cases:
            r=p.route(kind,complexity,risk);self.assertEqual((r['model_id'],r['effort']),(model,effort));self.assertIn('heuristic',r['basis'])
        self.assertTrue(p.route('routine','bounded','security')['independent_review_required'])
        with self.assertRaises(p.PolicyError):p.route('visual','hard','normal')
    def test_unknown_or_mismatched_effective_routes_fail(self):
        desired={'providerId':'account:fixture','modelId':'GLM-5.3-Flash','options':{'reasoningLevel':'low'}}
        snapshot={'settings':{'model':{'current':desired},'thoughtLevel':{'current':'low'},'mode':{'current':'plan'}}}
        self.assertEqual(p.verify_snapshot(snapshot,desired,'plan')['effort'],'low')
        with self.assertRaises(p.PolicyError):p.verify_snapshot(snapshot,desired,'edit')
        for bad in [{},{'settings':{}},{'settings':{'model':{'current':{'providerId':'unknown'}}}}]:
            with self.assertRaises(p.PolicyError):p.verify_snapshot(bad,desired,'plan')

if __name__=='__main__':unittest.main()
