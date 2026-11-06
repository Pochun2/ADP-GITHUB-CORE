from __future__ import annotations
import copy, unittest
from adp_context.c1_u34_queue_3 import validate_queue_3 as check
class ContractTests(unittest.TestCase):
 def test_ok(self):self.assertEqual(check([A()],L())['state'],'ACCOUNTED')
 def test_subset(self):self.assertEqual(check([A()],L())['total_tokens_nonduplicated'],140)
 def test_unknown_bill(self):self.assertEqual(check([A()],L())['actual_billed_usd'],'UNKNOWN_NOT_IN_CLI_TELEMETRY')
 def test_no_mutation(self):a=[A()];b=L();old=copy.deepcopy((a,b));check(a,b);self.assertEqual((a,b),old)
 def test_wrong_model(self):a=A();a['model']='fake';self.assertRaises(ValueError,check,[a],L())
 def test_bool_tokens(self):a=A();a['input_tokens']=True;self.assertRaises(ValueError,check,[a],L())
 def test_cache_exceeds(self):a=A();a['cached_input_tokens']=200;self.assertRaises(ValueError,check,[a],L())
 def test_reasoning_exceeds(self):a=A();a['reasoning_tokens']=100;self.assertRaises(ValueError,check,[a],L())
 def test_credit_cap(self):b=L();b['max_credits_micro']=499;self.assertRaises(ValueError,check,[A()],b)
 def test_token_cap(self):b=L();b['max_tokens']=139;self.assertRaises(ValueError,check,[A()],b)
 def test_empty_calls(self):self.assertRaises(ValueError,check,[],L())
 def test_too_many_calls(self):self.assertRaises(ValueError,check,[A()]*9,L())

def A():return {'model':'gpt-6.1-sol','input_tokens':100,'cached_input_tokens':20,'output_tokens':40,'reasoning_tokens':10,'credits_micro':500}
def L():return {'model':'gpt-6.1-sol','max_tokens':500,'max_credits_micro':2000}
