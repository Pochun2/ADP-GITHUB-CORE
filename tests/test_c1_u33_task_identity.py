"""Permanent regression: C1-U3.3 Issue/task dedupe contract, independently authored."""
import unittest
from adp_context.c1_u33_task_identity import validate_task_identity as check

A={'task_id':'C1-FOO_1','issue_number':25,'baseline_sha':'a'*40}
class TaskIdentityTests(unittest.TestCase):
    def bad(self,task=A,seen=None):
        with self.assertRaises(ValueError):check(task,[] if seen is None else seen)
    def test_new_task(self):self.assertEqual(check(A,[]),{'state':'UNSEEN','task_id':'C1-FOO_1','issue_number':25})
    def test_other_history(self):self.assertEqual(check(A,[dict(A,task_id='C1-BAR',issue_number=24)])['state'],'UNSEEN')
    def test_no_mutation(self):
        s=[dict(A,task_id='C1-BAR',issue_number=24)];old=repr(s);check(A,s);self.assertEqual(repr(s),old)
    def test_duplicate_task(self):self.bad(seen=[dict(A,issue_number=1)])
    def test_duplicate_issue(self):self.bad(seen=[dict(A,task_id='C1-DIFFERENT')])
    def test_issue_bool(self):self.bad(dict(A,issue_number=True))
    def test_issue_negative(self):self.bad(dict(A,issue_number=-4))
    def test_invalid_sha_case(self):self.bad(dict(A,baseline_sha='A'*40))
    def test_invalid_sha_length(self):self.bad(dict(A,baseline_sha='a'*39))
    def test_invalid_id(self):self.bad(dict(A,task_id='bad'))
    def test_extra_key(self):self.bad(dict(A,extra=1))
    def test_large_history(self):self.bad(seen=[dict(A,task_id='C1-BAR',issue_number=24)]*129)
