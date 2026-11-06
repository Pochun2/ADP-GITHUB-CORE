from __future__ import annotations
import copy, unittest
from adp_context.c1_u34_queue_2 import validate_queue_2 as check
class ContractTests(unittest.TestCase):
 def test_ok(self):self.assertEqual(check(A(),B())['state'],'LINKED')
 def test_link_from(self):self.assertEqual(check(A(),B())['from_sha'],'b'*40)
 def test_pair(self):self.assertEqual(check(A(),B())['pr_pair'],[12,13])
 def test_no_mutation(self):a=A();b=B();old=copy.deepcopy((a,b));check(a,b);self.assertEqual((a,b),old)
 def test_bad_ci(self):a=A();a['ci_names']=[];self.assertRaises(ValueError,check,a,B())
 def test_duplicate_ci(self):a=A();a['ci_names']=a['ci_names'][:5]+[a['ci_names'][0]];self.assertRaises(ValueError,check,a,B())
 def test_wrong_base(self):b=B();b['base_sha']='e'*40;self.assertRaises(ValueError,check,A(),b)
 def test_repeat_issue(self):b=B();b['issue_number']=11;self.assertRaises(ValueError,check,A(),b)
 def test_repeat_pr(self):b=B();b['pr_number']=12;self.assertRaises(ValueError,check,A(),b)
 def test_reversed_merge(self):b=B();b['merge_sha']='a'*40;self.assertRaises(ValueError,check,A(),b)
 def test_boolean_id(self):a=A();a['issue_number']=True;self.assertRaises(ValueError,check,a,B())
 def test_extra_field(self):b=B();b['unsafe']='x';self.assertRaises(ValueError,check,A(),b)

CI=['adp-context-suite','adp-context-offline','adp-context-canonical-offline','adp-context-checkpoint-offline','adp-context-github-observation-offline','adp-context-github-publisher-offline']
def A():return {'base_sha':'a'*40,'merge_sha':'b'*40,'issue_number':11,'pr_number':12,'ci_names':list(CI)}
def B():return {'base_sha':'b'*40,'merge_sha':'c'*40,'issue_number':12,'pr_number':13,'ci_names':list(CI)}
