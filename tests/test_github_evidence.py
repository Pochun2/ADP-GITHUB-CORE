"""Synthetic response suite. Never contacts GitHub or uses credentials."""
import copy
import hashlib
import json
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from adp_context.github_evidence import (
    AnonymousGitHubREST, EvidenceError, Target, observe, reconcile_checkpoint, _json_object,
)
from adp_context.engine import canonical

BASE = 'b166f4a4ab5dbda8b52489cb7a730090443714d7'
HEAD = '3e140bc2f08ee3dd42f4b2110330f71f7e83f57e'
REPO = 'Pochun2/GOV-TRUSTED-ISSUER'
ROOT = '/repos/' + REPO
NAMES = ['issuer-snapshot-offline','issuer-api-evidence-offline','issuer-live-api-contract-offline',
         'issuer-pair-observer-offline','issuer-trust-boundary-offline','issuer-app-boundary-offline',
         'issuer-transaction-offline','issuer-reconciliation-offline']
TARGET = Target(REPO,10,26423889)
TS = '2026-11-04T03:00:00Z'


def fixture():
    return {
        ROOT:{'full_name':REPO,'private':False,'default_branch':'main'},
        ROOT+'/branches/main':{'commit':{'sha':BASE}},
        ROOT+'/pulls/10':{'number':10,'state':'open','draft':True,'merged':False,
                          'head':{'sha':HEAD},'base':{'sha':BASE,'ref':'main','repo':{'full_name':REPO}}},
        ROOT+'/rulesets/26423889':{'id':26423889,'enforcement':'active','rules':[
            {'type':'deletion'}, {'type':'non_fast_forward'},
            {'type':'required_status_checks','parameters':{'strict_required_status_checks_policy':True,
             'required_status_checks':[{'context':n,'integration_id':15368} for n in NAMES]}}]},
        ROOT+'/commits/'+HEAD+'/check-runs?per_page=100':{'total_count':len(NAMES)+1,
             'check_runs':[{'id':i+1,'name':n,'head_sha':HEAD,'app':{'id':15368},
                            'status':'completed','conclusion':'success'} for i,n in enumerate(NAMES+['issuer-auth-lifecycle-offline'])]}
    }

class MockSource:
    def __init__(self,data=None):self.data=data or fixture();self.paths=[]
    def get(self,endpoint):
        self.paths.append(endpoint)
        return copy.deepcopy(self.data[endpoint])


def checkpoint():
    return {'schema':'adp-context-v1','project_id':'ctx-demo','task_id':'CTX-A2',
            'repository':REPO,'baseline_sha':BASE,'head_sha':HEAD,
            'policy_ref':'EXTERNAL-POLICY-UNVERIFIED','status':'READY_FOR_REVIEW',
            'completed_steps':['offline tests'],'pending_steps':['external review'],
            'blockers':[],
            'evidence_refs':[{'locator':'evidence.json','sha256':'a'*64,'claim_level':'EVIDENCED'}],
            'decision_refs':[],'non_negotiables':['NO ACCOUNT/ORDER','T+1 PAUSED_MANUAL'],
            'last_verified_at_utc':None,'next_action':'verify policy',
            'context_sources':[{'locator':'source.txt','sha256':'b'*64,'claim_level':'REPORTED'}]}

class ObservationTests(unittest.TestCase):
    def setUp(self):self.data=fixture();self.src=MockSource(self.data)
    def collect(self):return observe(self.src,TARGET,observed_at_utc=TS)
    def test_success_not_attestation(self):
        v=self.collect();self.assertEqual(v['ci_state'],'SUCCESS');self.assertEqual(v['required_success_count'],8)
        self.assertEqual(v['pr_state'],'DRAFT');self.assertIn('NOT_ATTESTED',v['source_mode'])
        self.assertEqual(len(self.src.paths),5)
        self.assertEqual(v['required_check_count'],8)
    def test_determinism(self):self.assertEqual(self.collect(),self.collect())
    def test_no_token_or_secrets(self):
        s=json.dumps(self.collect()).lower()
        for key in ('token','password','private_key','authorization','jwt'):
            self.assertNotIn(key,s)
    def test_bad_repo(self):
        self.data[ROOT]['full_name']='someone/other'
        with self.assertRaises(EvidenceError):self.collect()
    def test_private_repo_denied(self):
        self.data[ROOT]['private']=True
        with self.assertRaises(EvidenceError):self.collect()
    def test_wrong_main(self):
        self.data[ROOT+'/branches/main']['commit']['sha']='no'
        with self.assertRaises(EvidenceError):self.collect()
    def test_pr_number(self):
        self.data[ROOT+'/pulls/10']['number']=9
        with self.assertRaises(EvidenceError):self.collect()
    def test_pr_repo(self):
        self.data[ROOT+'/pulls/10']['base']['repo']['full_name']='bad/repo'
        with self.assertRaises(EvidenceError):self.collect()
    def test_pr_base_drift(self):
        self.data[ROOT+'/pulls/10']['base']['sha']='f'*40
        with self.assertRaises(EvidenceError):self.collect()
    def test_closed_draft(self):
        self.data[ROOT+'/pulls/10'].update(state='closed',draft=True)
        with self.assertRaises(EvidenceError):self.collect()
    def test_inactive_rules(self):
        self.data[ROOT+'/rulesets/26423889']['enforcement']='disabled'
        with self.assertRaises(EvidenceError):self.collect()
    def test_missing_rule(self):
        self.data[ROOT+'/rulesets/26423889']['rules']=[]
        with self.assertRaises(EvidenceError):self.collect()
    def test_missing_strict(self):
        self.data[ROOT+'/rulesets/26423889']['rules'][-1]['parameters']['strict_required_status_checks_policy']=False
        with self.assertRaises(EvidenceError):self.collect()
    def test_untrusted_integration(self):
        self.data[ROOT+'/rulesets/26423889']['rules'][-1]['parameters']['required_status_checks'][0]['integration_id']=5475837
        with self.assertRaises(EvidenceError):self.collect()
    def test_duplicate_required(self):
        a=self.data[ROOT+'/rulesets/26423889']['rules'][-1]['parameters']['required_status_checks']
        a.append(a[0])
        with self.assertRaises(EvidenceError):self.collect()
    def test_missing_check(self):
        self.data[ROOT+'/commits/'+HEAD+'/check-runs?per_page=100']['check_runs'].pop(0)
        self.data[ROOT+'/commits/'+HEAD+'/check-runs?per_page=100']['total_count']-=1
        with self.assertRaises(EvidenceError):self.collect()
    def test_partial_page(self):
        self.data[ROOT+'/commits/'+HEAD+'/check-runs?per_page=100']['total_count']=99
        with self.assertRaises(EvidenceError):self.collect()
    def test_duplicate_check_id(self):
        self.data[ROOT+'/commits/'+HEAD+'/check-runs?per_page=100']['check_runs'][1]['id']=1
        with self.assertRaises(EvidenceError):self.collect()
    def test_duplicate_context(self):
        runs=self.data[ROOT+'/commits/'+HEAD+'/check-runs?per_page=100']['check_runs']
        runs[8]['name']=runs[0]['name']
        with self.assertRaises(EvidenceError):self.collect()
    def test_wrong_check_sha(self):
        self.data[ROOT+'/commits/'+HEAD+'/check-runs?per_page=100']['check_runs'][0]['head_sha']='a'*40
        with self.assertRaises(EvidenceError):self.collect()
    def test_pending_check(self):
        c=self.data[ROOT+'/commits/'+HEAD+'/check-runs?per_page=100']['check_runs'][0]
        c.update(status='in_progress',conclusion=None)
        self.assertEqual(self.collect()['ci_state'],'INCOMPLETE')
    def test_failed_check(self):
        self.data[ROOT+'/commits/'+HEAD+'/check-runs?per_page=100']['check_runs'][0]['conclusion']='failure'
        self.assertEqual(self.collect()['required_failed_or_pending'],[NAMES[0]])
    def test_reject_wrong_target(self):
        for args in [(REPO,True,1),(REPO,1,0),('wrong',1,1)]:
            with self.subTest(args=args),self.assertRaises(EvidenceError):Target(*args)
    def test_remote_exception_redacted(self):
        class Broken:
            def get(self,x):raise RuntimeError('ghp_SECRET_MUST_NOT_LEAK')
        with self.assertRaisesRegex(EvidenceError,'REMOTE_UNAVAILABLE'):observe(Broken(),TARGET)
    def test_json_duplicate_key(self):
        with self.assertRaises(EvidenceError):_json_object(b'{"a":1,"a":2}')
    def test_json_too_large(self):
        with self.assertRaises(EvidenceError):_json_object(b' '*1_048_577)
    def test_endpoint_reject_post_or_traversal(self):
        for path in ('/users','/repos/o/r/../x','/repos/o/r?token=abc', '/repos/o/r/actions/secrets'):
            with self.subTest(path=path),self.assertRaises(EvidenceError):AnonymousGitHubREST().get(path)

class ReconcileTests(unittest.TestCase):
    def setUp(self):self.obs=observe(MockSource(),TARGET,observed_at_utc=TS);self.cp=checkpoint()
    def run_check(self):return reconcile_checkpoint(self.cp,self.obs,expected_policy_ruleset_id=26423889,now_utc=TS)
    def test_consistent_never_authorizes(self):
        v=self.run_check();self.assertEqual(v['state'],'CONSISTENT_OBSERVATION_NOT_AUTHORIZED')
    def test_cp_drift(self):
        self.cp['baseline_sha']='a'*40
        self.assertIn('BASELINE_DRIFT',self.run_check()['reasons'])
    def test_head_drift(self):
        self.cp['head_sha']='b'*40
        self.assertIn('HEAD_DRIFT',self.run_check()['reasons'])
    def test_blockers(self):
        self.cp['blockers']=['Gate A blocked']
        self.assertEqual(self.run_check()['state'],'BLOCKED_RECONCILIATION')
    def test_ci_incomplete(self):
        body={k:v for k,v in self.obs.items() if k!='observation_sha256'}
        body.update(ci_state='INCOMPLETE')
        self.obs=body|{'observation_sha256':hashlib.sha256(canonical(body)).hexdigest()}
        self.assertIn('REQUIRED_CI_NOT_SUCCESS',self.run_check()['reasons'])
    def test_policy_id_drift(self):
        v=reconcile_checkpoint(self.cp,self.obs,expected_policy_ruleset_id=123,now_utc=TS)
        self.assertIn('RULESET_ID_MISMATCH',v['reasons'])
    def test_stale(self):
        v=reconcile_checkpoint(self.cp,self.obs,expected_policy_ruleset_id=26423889,now_utc='2026-11-04T03:06:00Z')
        self.assertIn('OBSERVATION_STALE_OR_FUTURE',v['reasons'])
    def test_future(self):
        v=reconcile_checkpoint(self.cp,self.obs,expected_policy_ruleset_id=26423889,now_utc='2026-11-04T02:59:59Z')
        self.assertIn('OBSERVATION_STALE_OR_FUTURE',v['reasons'])
    def test_changed_digest(self):
        self.obs['head_sha']='c'*40
        with self.assertRaises(EvidenceError):self.run_check()
    def test_no_evidence(self):
        self.cp['evidence_refs']=[]
        self.assertIn('CHECKPOINT_EVIDENCE_NOT_AUTHORITATIVE',self.run_check()['reasons'])
    def test_completed_not_resumable(self):
        self.cp['status']='DONE_REPORTED';self.cp['pending_steps']=[]
        self.assertIn('CHECKPOINT_BLOCKED',self.run_check()['reasons'])
    def test_no_policy_side_effects(self):
        old=copy.deepcopy(self.cp),copy.deepcopy(self.obs)
        self.run_check();self.assertEqual(old,(self.cp,self.obs))

if __name__=='__main__': unittest.main()
