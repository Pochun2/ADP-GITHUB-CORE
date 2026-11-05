"""Permanent CI regression for PR #9 independently authored Token Budget module."""
import copy
import unittest
from adp_context.c1_token_budget import validate_token_budget as run


def usage(i=6,c=3,o=2):
    return {'input_tokens':i,'cached_input_tokens':c,'output_tokens':o}

class TokenBudgetPermanentRegression(unittest.TestCase):
    def bad(self,x,cap=20):
        with self.assertRaises(ValueError):run(x,cap)
    def test_under_cap(self):self.assertEqual(run(usage(),9),{'total_tokens':8,'within_budget':True})
    def test_equal_cap(self):self.assertTrue(run(usage(),8)['within_budget'])
    def test_over_cap(self):self.assertFalse(run(usage(),7)['within_budget'])
    def test_zero(self):self.assertEqual(run(usage(0,0,0),0),{'total_tokens':0,'within_budget':True})
    def test_cached_not_added(self):self.assertEqual(run(usage(100,90,10),110)['total_tokens'],110)
    def test_reasoning_extra_forbidden(self):self.bad({**usage(),'reasoning_output_tokens':2})
    def test_input_immutable(self):
        x=usage();copyx=copy.deepcopy(x);run(x,2);self.assertEqual(x,copyx)
    def test_input_tuple(self):self.bad(tuple(usage().values()))
    def test_input_none(self):self.bad(None)
    def test_input_subclass(self):
        class Custom(dict):pass
        self.bad(Custom(usage()))
    def test_missing_input(self):
        x=usage();del x['input_tokens'];self.bad(x)
    def test_missing_cached(self):
        x=usage();del x['cached_input_tokens'];self.bad(x)
    def test_missing_output(self):
        x=usage();del x['output_tokens'];self.bad(x)
    def test_extra_key(self):self.bad({**usage(),'cost':1})
    def test_negative_input(self):self.bad(usage(-1,0,2))
    def test_negative_cached(self):self.bad(usage(6,-1,2))
    def test_negative_output(self):self.bad(usage(6,3,-2))
    def test_cached_exceeds_input(self):self.bad(usage(6,7,2))
    def test_boolean_input(self):self.bad(usage(True,0,0))
    def test_boolean_cached(self):self.bad(usage(1,True,0))
    def test_boolean_output(self):self.bad(usage(1,0,False))
    def test_float_input(self):self.bad(usage(1.0,0,0))
    def test_string_input(self):self.bad(usage('1',0,0))
    def test_none_output(self):self.bad(usage(1,0,None))
    def test_bool_cap(self):self.bad(usage(),True)
    def test_float_cap(self):self.bad(usage(),8.0)
    def test_negative_cap(self):self.bad(usage(),-1)
    def test_string_cap(self):self.bad(usage(),'8')
    def test_max_int_exact(self):
        n=2**53-1;self.assertTrue(run(usage(n,n,1),n+1)['within_budget'])
    def test_exceeds_budget_not_exception(self):
        self.assertEqual(run(usage(9,2,3),0),{'total_tokens':12,'within_budget':False})

if __name__=='__main__':unittest.main()
