"""Permanent GitHub CI regression for PR #6 Codex-authored pure Python lineage verifier."""
import copy
import unittest
from adp_context.c1_commit_lineage import validate_lineage

BASE='a'*40

def rec(sequence=1,base=BASE,merge=None,candidate=None):
    return {'sequence':sequence,'base_sha':base,
            'merge_sha':merge if merge is not None else 'b'*40,
            'candidate_sha256':candidate if candidate is not None else 'c'*64}

class LineagePermanentRegressionTests(unittest.TestCase):
    def bad(self,records,base=BASE):
        with self.assertRaises(ValueError):validate_lineage(records,base)
    def test_one_valid(self):
        result=validate_lineage([rec()],BASE)
        self.assertEqual(result,{'state':'VALID','steps':1,'final_sha':'b'*40,'final_candidate_sha256':'c'*64})
    def test_two_valid(self):
        arr=[rec(),rec(sequence=2,base='b'*40,merge='d'*40,candidate='e'*64)]
        self.assertEqual(validate_lineage(arr,BASE)['final_sha'],'d'*40)
    def test_input_not_modified(self):
        arr=[rec()];before=copy.deepcopy(arr);validate_lineage(arr,BASE);self.assertEqual(arr,before)
    def test_invalid_base(self):self.bad([rec()],base='A'*40)
    def test_empty_list(self):self.bad([])
    def test_not_a_list(self):self.bad(tuple([rec()]))
    def test_over_16(self):self.bad([rec()]*17)
    def test_missing_key(self):
        x=rec();x.pop('candidate_sha256');self.bad([x])
    def test_extra_key(self):
        x=rec();x['note']='a';self.bad([x])
    def test_bool_sequence(self):self.bad([rec(sequence=True)])
    def test_skip_sequence(self):self.bad([rec(sequence=2)])
    def test_bad_sha_case(self):self.bad([rec(merge='B'*40)])
    def test_bad_candidate(self):self.bad([rec(candidate='x'*64)])
    def test_chain_mismatch(self):
        self.bad([rec(),rec(sequence=2,base='f'*40,merge='d'*40,candidate='e'*64)])
    def test_same_merge_base(self):self.bad([rec(merge=BASE)])
    def test_repeated_merge(self):self.bad([rec(),rec(sequence=2,base='b'*40,merge='b'*40,candidate='e'*64)])
    def test_repeated_candidate(self):
        self.bad([rec(),rec(sequence=2,base='b'*40,merge='d'*40,candidate='c'*64)])
    def test_wrong_record_type(self):self.bad(['not-a-record'])
    def test_candidate_integer(self):self.bad([rec(candidate=1)])
    def test_same_baseline_wrong_start(self):self.bad([rec(base='e'*40)])

if __name__=='__main__':unittest.main()
