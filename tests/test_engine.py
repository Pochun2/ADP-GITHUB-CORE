import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from adp_context.engine import (ContextError,validate_checkpoint,validate_decisions,
    checkpoint_digest,canonical,compact,retrieve,validate_remote_snapshot,resume_preview,load_json,verify_local_sources)

S='a'*40;H='b'*40;D='c'*64
R=lambda loc,level='EVIDENCED':{'locator':loc,'sha256':D,'claim_level':level}

def fixture():
    return {'schema':'adp-context-v1','project_id':'ymc-r73','task_id':'ADP-001',
    'repository':'sample/ymc','baseline_sha':S,'head_sha':H,'policy_ref':'protected:version1',
    'status':'PAUSED','completed_steps':['Read spec'],'pending_steps':['Run tests'],
    'blockers':['GATE_A_BLOCKED'],'evidence_refs':[R('proof/a')],
    'decision_refs':[R('adr/1')], 'non_negotiables':['NO ACCOUNT/ORDER','T+1 PAUSED_MANUAL'],
    'last_verified_at_utc':None,'next_action':'Read live GitHub state','context_sources':[R('docs/contract'),R('docs/api')]}

def decisions():return [{'id':'ADR-1','status':'APPROVED','supersedes':None,'reason':'Use GitHub','source':R('adr/1')}]

def remote():return {'repository':'sample/ymc','main_sha':S,'head_sha':H,
 'pr_state':'DRAFT','ci_state':'SUCCESS','policy_ref':'protected:version1','source_mode':'UNTRUSTED_OFFLINE_FIXTURE'}

class ContractTests(unittest.TestCase):
 def test_valid(self):self.assertEqual(validate_checkpoint(fixture())['task_id'],'ADP-001')
 def test_digest_determinism(self):
  a=fixture();b=dict(reversed(list(a.items())));self.assertEqual(checkpoint_digest(a),checkpoint_digest(b))
 def test_status_cannot_elevate(self):
  a=fixture();a['status']='GATE_A_PASS';self.assertRaises(ContextError,validate_checkpoint,a)
 def test_missing_key(self):
  a=fixture();del a['policy_ref'];self.assertRaises(ContextError,validate_checkpoint,a)
 def test_extra_key(self):
  a=fixture();a['secret']='x';self.assertRaises(ContextError,validate_checkpoint,a)
 def test_sha(self):
  a=fixture();a['head_sha']='deadbeef';self.assertRaises(ContextError,validate_checkpoint,a)
 def test_repo(self):
  a=fixture();a['repository']='bad';self.assertRaises(ContextError,validate_checkpoint,a)
 def test_secret(self):
  a=fixture();a['next_action']='token=SECRET_VALUE';self.assertRaises(ContextError,validate_checkpoint,a)
 def test_duplicate_steps(self):
  a=fixture();a['completed_steps']=['x','x'];self.assertRaises(ContextError,validate_checkpoint,a)
 def test_step_conflict(self):
  a=fixture();a['pending_steps']=['Read spec'];self.assertRaises(ContextError,validate_checkpoint,a)
 def test_refs_missing(self):
  a=fixture();a['context_sources']=[];self.assertRaises(ContextError,validate_checkpoint,a)
 def test_ref_traversal(self):
  a=fixture();a['context_sources'][0]['locator']='../private';self.assertRaises(ContextError,validate_checkpoint,a)
 def test_bad_digest(self):
  a=fixture();a['context_sources'][0]['sha256']='bad';self.assertRaises(ContextError,validate_checkpoint,a)
 def test_duplicate_ref(self):
  a=fixture();a['context_sources'].append(copy.deepcopy(a['context_sources'][0]));self.assertRaises(ContextError,validate_checkpoint,a)
 def test_decision_valid(self):self.assertEqual(len(validate_decisions(decisions())),1)
 def test_decision_claim(self):
  d=decisions();d[0]['source']['claim_level']='REPORTED';self.assertRaises(ContextError,validate_decisions,d)
 def test_decision_bad_supersede(self):
  d=decisions();d[0]['supersedes']='ADR-9';self.assertRaises(ContextError,validate_decisions,d)
 def test_decision_conflict(self):
  d=decisions();d.append({'id':'ADR-2','status':'APPROVED','supersedes':'ADR-1','reason':'change','source':R('adr/2')});self.assertRaises(ContextError,validate_decisions,d)
 def test_decision_supersede(self):
  d=decisions();d[0]['status']='SUPERSEDED';d.append({'id':'ADR-2','status':'APPROVED','supersedes':'ADR-1','reason':'change','source':R('adr/2')});self.assertEqual(len(validate_decisions(d)),2)
 def test_decision_cycle(self):
  d=[{'id':'A','status':'SUPERSEDED','supersedes':'B','reason':'one','source':R('adr/a')},
     {'id':'B','status':'SUPERSEDED','supersedes':'A','reason':'two','source':R('adr/b')}];self.assertRaises(ContextError,validate_decisions,d)
 def test_resume_blocker(self):self.assertIn('UNRESOLVED_BLOCKERS',resume_preview(fixture(),remote(),decisions())['reasons'])
 def test_resume_drift(self):
  r=remote();r['head_sha']='e'*40;self.assertIn('HEAD_DRIFT',resume_preview(fixture(),r,decisions())['reasons'])
 def test_resume_policy_drift(self):
  r=remote();r['policy_ref']='new-policy';self.assertIn('POLICY_DRIFT',resume_preview(fixture(),r,decisions())['reasons'])
 def test_resume_main_drift(self):
  r=remote();r['main_sha']='e'*40;self.assertIn('BASELINE_DRIFT',resume_preview(fixture(),r,decisions())['reasons'])
 def test_resume_repo_mismatch(self):
  r=remote();r['repository']='someone/else';self.assertIn('REPOSITORY_MISMATCH',resume_preview(fixture(),r,decisions())['reasons'])
 def test_resume_ci_pending(self):
  a=fixture();a['blockers']=['none'];a['status']='READY_FOR_REVIEW';r=remote();r['ci_state']='PENDING';self.assertIn('CI_NOT_SUCCESS',resume_preview(a,r,decisions())['reasons'])
 def test_resume_no_evidence(self):
  a=fixture();a['evidence_refs']=[];self.assertIn('NO_EVIDENCE_REFS',resume_preview(a,remote(),decisions())['reasons'])
 def test_resume_unverified_evidence(self):
  a=fixture();a['evidence_refs']=[R('proof/a','REPORTED')];self.assertIn('NON_AUTHORITATIVE_EVIDENCE',resume_preview(a,remote(),decisions())['reasons'])
 def test_resume_missing_decision(self):
  self.assertIn('DECISION_SOURCE_MISSING',resume_preview(fixture(),remote(),[])['reasons'])
 def test_resume_unblocked_preview_not_approval(self):
  a=fixture();a['blockers']=['none'];a['status']='PAUSED';r=resume_preview(a,remote(),decisions());
  self.assertEqual(r['state'],'BLOCKED_RECONCILIATION') # unresolved blocker label still blocks? no, list nonempty blocks
 def test_resume_preview_positive(self):
  a=fixture();a['blockers']=[] # empty blockers should be permitted, requires list validation adjust
  r=resume_preview(a,remote(),decisions());self.assertEqual(r['state'],'READY_FOR_HUMAN_OR_EXTERNAL_POLICY_REVIEW');self.assertIn('NO_AUTHORIZATION',r['note'])
 def test_remote_source_is_untrusted_fixture(self):
  r=remote();r['source_mode']='LIVE_AUTHENTICATED';self.assertRaises(ContextError,validate_remote_snapshot,r)
 def test_capsule_essential(self):
  s=compact(fixture(),decisions());self.assertIn('NO ACCOUNT/ORDER',s);self.assertIn('GATE_A_BLOCKED',s);self.assertIn('ADR-1',s);self.assertIn(S,s)
 def test_retrieval(self):self.assertEqual(retrieve(fixture(),['api'])[0]['locator'],'docs/api')
 def test_retrieval_deterministic(self):self.assertEqual(retrieve(fixture(),['docs']),retrieve(fixture(),['docs']))
 def test_json_duplicate_key(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'x.json';p.write_text('{"a":1,"a":2}');self.assertRaises(ContextError,load_json,p)
 def test_symlink_rejected(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'file';p.write_text('{}');q=Path(t)/'link';
   try:q.symlink_to(p)
   except (OSError,NotImplementedError):self.skipTest('symlink unsupported')
   self.assertRaises(ContextError,load_json,q)
 def test_local_hash_source(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'proof';p.write_text('hello',encoding='utf-8')
   a=fixture();a['context_sources']=[{'locator':'proof','sha256':hashlib.sha256(b'hello').hexdigest(),'claim_level':'REPORTED'}]
   self.assertEqual(verify_local_sources(a,t)['checked'],1)
 def test_local_hash_tampering(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'proof';p.write_text('changed')
   a=fixture();a['context_sources']=[{'locator':'proof','sha256':D,'claim_level':'REPORTED'}]
   self.assertRaises(ContextError,verify_local_sources,a,t)
 def test_local_missing_source(self):
  with tempfile.TemporaryDirectory() as t:
   self.assertRaises(ContextError,verify_local_sources,fixture(),t)
 def test_cross_project_same_engine(self):
  a=fixture();b=fixture();b['project_id']='other-project';b['repository']='other/repo';
  self.assertEqual(validate_checkpoint(a)['schema'],validate_checkpoint(b)['schema'])

if __name__=='__main__':unittest.main()
