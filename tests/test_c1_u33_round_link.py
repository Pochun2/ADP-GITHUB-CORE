"""Permanent regression: C1-U3.3 baseline linkage and replay rejection."""
import unittest
from adp_context.c1_u33_round_link import validate_round_link as check

A={'baseline_sha':'a'*40,'merge_sha':'b'*40,'issue_number':11}
B={'baseline_sha':'b'*40,'merge_sha':'c'*40,'issue_number':12}
class RoundLinkTests(unittest.TestCase):
    def bad(self,a=A,b=B):
        with self.assertRaises(ValueError):check(a,b)
    def test_valid_chain(self):self.assertEqual(check(A,B),{'state':'LINKED','from_sha':'b'*40,'to_sha':'c'*40,'issue_pair':[11,12]})
    def test_alternate_valid(self):self.assertEqual(check(dict(A,issue_number=1),dict(B,issue_number=2))['state'],'LINKED')
    def test_no_mutation(self):
        old=(dict(A),dict(B));check(A,B);self.assertEqual((A,B),old)
    def test_wrong_baseline(self):self.bad(b=dict(B,baseline_sha='0'*40))
    def test_repeated_issue(self):self.bad(b=dict(B,issue_number=11))
    def test_boolean_issue(self):self.bad(b=dict(B,issue_number=True))
    def test_empty_previous(self):self.bad(a={})
    def test_missing_field(self):self.bad(b={'baseline_sha':'b'*40,'merge_sha':'c'*40})
    def test_extra_field(self):self.bad(a=dict(A,unexpected=1))
    def test_uppercase_sha(self):self.bad(a=dict(A,merge_sha='B'*40))
    def test_replay_merge(self):self.bad(b=dict(B,merge_sha='b'*40))
    def test_reverse_chain(self):self.bad(b=dict(B,merge_sha='a'*40))
