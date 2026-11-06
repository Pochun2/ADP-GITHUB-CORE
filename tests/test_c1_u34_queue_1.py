from __future__ import annotations
import copy, unittest
from adp_context.c1_u34_queue_1 import validate_queue_1 as check
class ContractTests(unittest.TestCase):
 def test_ok(self):self.assertEqual(check(M(),I()),{'state':'READY','task_id':'C1-U34-QUEUE-1','issue_number':7})
 def test_no_mutation(self):a=M();b=I(); x=copy.deepcopy((a,b));check(a,b);self.assertEqual((a,b),x)
 def test_bad_task(self):a=M();a['task_id']='bad';self.assertRaises(ValueError,check,a,I())
 def test_wrong_repo(self):a=M();a['repository']='Wrong/Repo';self.assertRaises(ValueError,check,a,I())
 def test_bad_sha(self):a=M();a['baseline_sha']='A'*40;self.assertRaises(ValueError,check,a,I())
 def test_bad_spec(self):a=M();a['spec_sha256']='A'*64;self.assertRaises(ValueError,check,a,I())
 def test_bad_path(self):a=M();a['source_path']='../x.py';self.assertRaises(ValueError,check,a,I())
 def test_extra_manifest(self):a=M();a['extra']=0;self.assertRaises(ValueError,check,a,I())
 def test_wrong_title(self):b=I();b['title']='wrong';self.assertRaises(ValueError,check,M(),b)
 def test_duplicate_label(self):b=I();b['labels']=['adp-agent-ready']*2;self.assertRaises(ValueError,check,M(),b)
 def test_tampered_body(self):b=I();b['body']['baseline_sha']='c'*40;self.assertRaises(ValueError,check,M(),b)
 def test_boolean_id(self):b=I();b['number']=True;self.assertRaises(ValueError,check,M(),b)

def M():
 return {'task_id':'C1-U34-QUEUE-1','repository':'Pochun2/ADP-GITHUB-CORE','baseline_sha':'a'*40,'source_path':'adp_context/c1_u34_queue_1.py','spec_sha256':'b'*64}
def I():
 a=M();return {'number':7,'title':'[ADP-C1] '+a['task_id'],'state':'open','labels':['adp-agent-ready'],
  'body':{'schema':'adp-c1-issue-v1','task_id':a['task_id'],'repository':a['repository'],
  'baseline_sha':a['baseline_sha'],'kind':'PURE_PYTHON_ONE_FILE','output_path':a['source_path'],'spec_sha256':a['spec_sha256']}}
