"""Synthetic offline tests for local candidate journal; no external APIs."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from adp_context.checkpoint_store import append, load, resume_gate, StoreError, exclusive_lock, entry_digest
from adp_context.engine import canonical
from adp_context.github_evidence import observe, Target

BASE='b166f4a4ab5dbda8b52489cb7a730090443714d7'
HEAD='3e140bc2f08ee3dd42f4b2110330f71f7e83f57e'
REPO='Pochun2/GOV-TRUSTED-ISSUER'
NOW='2026-11-04T03:00:10Z'
START='2026-11-04T03:00:00Z'

def cp():
    return {'schema':'adp-context-v1','project_id':'test','task_id':'T1','repository':REPO,
            'baseline_sha':BASE,'head_sha':HEAD,'policy_ref':'PINNED-PROPOSED',
            'status':'READY_FOR_REVIEW','completed_steps':['offline tests'],
            'pending_steps':['human review'], 'blockers':[],
            'evidence_refs':[{'locator':'evidence.json','sha256':'a'*64,'claim_level':'EVIDENCED'}],
            'decision_refs':[], 'non_negotiables':['NO ACCOUNT/ORDER','T+1 PAUSED_MANUAL'],
            'last_verified_at_utc':None,'next_action':'independent review',
            'context_sources':[{'locator':'src.txt','sha256':'b'*64,'claim_level':'REPORTED'}]}

def observation():
    d={'schema':'adp-github-observation-v1','source_mode':'GITHUB_API_READ_OBSERVED_NOT_ATTESTED',
       'repository':REPO,'pr_number':10,'main_sha':BASE,'head_sha':HEAD,'pr_base_sha':BASE,
       'pr_state':'DRAFT','policy_ruleset_id':26423889,'required_check_contexts':['x'],
       'ci_state':'SUCCESS','required_check_count':1,'required_success_count':1,
       'required_failed_or_pending':[],'observed_at_utc':START}
    d['observation_sha256']=hashlib.sha256(canonical(d)).hexdigest()
    return d

class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p=Path(self.tmp.name)/'history.jsonl'
        self.c=cp()

    def write(self, id='e1', t=START, expected=None, checkpoint=None):
        return append(self.p,checkpoint or self.c,event_id=id,at_utc=t,expected_last_sha256=expected)

    def first(self):return self.write()
    def test_first_and_reload(self):
        a=self.first(); self.assertEqual(a['sequence'],1)
        self.assertEqual(load(self.p)[0]['entry_sha256'],a['entry_sha256'])
        self.assertIn('NOT_PUBLISHED',a['state'])
    def test_two_append_chain(self):
        first=self.first(); a=self.write('e2','2026-11-04T03:00:01Z',first['entry_sha256'])
        self.assertEqual(a['sequence'],2)
        self.assertEqual(load(self.p)[1]['prev_sha256'],first['entry_sha256'])
    def test_cas_required(self):
        self.first()
        with self.assertRaises(StoreError):self.write('e2','2026-11-04T03:00:01Z')
    def test_cas_stale(self):
        self.first()
        with self.assertRaises(StoreError):self.write('e2','2026-11-04T03:00:01Z','f'*64)
    def test_replay_id(self):
        first=self.first()
        with self.assertRaises(StoreError):self.write('e1','2026-11-04T03:00:01Z',first['entry_sha256'])
    def test_multiple_writes_count(self):
        tail=self.first()['entry_sha256']
        for i in range(2,9):tail=self.write(f'e{i}',f'2026-11-04T03:00:{i:02d}Z',tail)['entry_sha256']
        self.assertEqual(len(load(self.p)),8)
    def test_time_regression(self):
        tail=self.first()['entry_sha256']
        with self.assertRaises(StoreError):self.write('e2','2026-11-04T02:00:00Z',tail)
    def test_bad_time(self):
        with self.assertRaises(StoreError):self.write(t='2026-11-04 03:00:00')
    def test_token_invalid(self):
        with self.assertRaises(StoreError):self.write(id='bad token')
    def test_invalid_cp(self):
        self.c['status']='AUTHORISED'
        with self.assertRaises(ValueError):self.write()
    def test_task_identity_drift(self):
        tail=self.first()['entry_sha256'];self.c['task_id']='OTHER'
        with self.assertRaises(StoreError):self.write('e2','2026-11-04T03:00:01Z',tail)
    def test_policy_drift(self):
        tail=self.first()['entry_sha256'];self.c['policy_ref']='DIFFERENT'
        with self.assertRaises(StoreError):self.write('e2','2026-11-04T03:00:01Z',tail)
    def test_checkpoint_updated_nonidentity(self):
        tail=self.first()['entry_sha256'];self.c['next_action']='different review'
        self.write('e2','2026-11-04T03:00:01Z',tail)
        self.assertEqual(load(self.p)[-1]['checkpoint']['next_action'],'different review')
    def test_missing_journal(self):
        with self.assertRaises(StoreError):load(self.p)
    def test_empty_journal(self):
        self.p.write_bytes(b'')
        with self.assertRaises(StoreError):load(self.p)
    def test_truncated_journal(self):
        self.first();self.p.write_bytes(self.p.read_bytes()[:-1])
        with self.assertRaises(StoreError):load(self.p)
    def test_corrupt_entry(self):
        self.first();self.p.write_bytes(self.p.read_bytes().replace(b'READY_FOR_REVIEW',b'BLOCKED'))
        with self.assertRaises(StoreError):load(self.p)
    def test_tamper_middle_entry(self):
        tail=self.first()['entry_sha256'];self.write('e2','2026-11-04T03:00:01Z',tail)
        # Deliberately corrupt a prior entry without updating its hash.
        raw=self.p.read_bytes(); self.p.write_bytes(raw.replace(b'"event_id":"e1"',b'"event_id":"xx"'))
        with self.assertRaises(StoreError):load(self.p)
    def test_duplicate_json_keys(self):
        self.first();raw=self.p.read_bytes().replace(b'"schema":',b'"schema":"duplicate","schema":',1)
        self.p.write_bytes(raw)
        with self.assertRaises(StoreError):load(self.p)
    def test_duplicate_event_in_history(self):
        tail=self.first()['entry_sha256']; self.write('e2','2026-11-04T03:00:01Z',tail)
        rows=load(self.p)
        rows[1]['event_id']='e1';rows[1]['entry_sha256']=entry_digest(rows[1]);self.p.write_bytes(b''.join(canonical(x) for x in rows))
        with self.assertRaises(StoreError):load(self.p)
    def test_manual_lock_is_not_stolen(self):
        with exclusive_lock(self.p):
            with self.assertRaises(StoreError):self.first()
        self.first()
    def test_stale_lock_blocks(self):
        lock=Path(str(self.p)+'.lock');lock.mkdir()
        with self.assertRaises(StoreError):self.first()
        lock.rmdir()
    def test_path_symlink_rejected_when_supported(self):
        target=Path(self.tmp.name)/'target';target.write_text('data')
        try:self.p.symlink_to(target)
        except (OSError,NotImplementedError):self.skipTest('symlink unsupported')
        with self.assertRaises(StoreError):self.first()
    def test_reopen_on_new_worker(self):
        self.first();self.assertEqual(load(str(self.p))[0]['checkpoint']['task_id'],'T1')
    def test_resume_consistent_still_not_authorized(self):
        self.first();v=resume_gate(self.p,observation(),expected_policy_ruleset_id=26423889,now_utc=NOW)
        self.assertEqual(v['state'],'REVIEW_REQUIRED_NOT_AUTHORIZED')
    def test_resume_stale_blocks(self):
        self.first();v=resume_gate(self.p,observation(),expected_policy_ruleset_id=26423889,now_utc='2026-11-04T04:00:00Z')
        self.assertEqual(v['state'],'BLOCKED_RECONCILIATION')
        self.assertIn('OBSERVATION_STALE_OR_FUTURE',v['reasons'])
    def test_resume_main_drift_blocks(self):
        self.first();o=observation();o['main_sha']='c'*40
        o['observation_sha256']=hashlib.sha256(canonical({k:v for k,v in o.items() if k!='observation_sha256'})).hexdigest()
        v=resume_gate(self.p,o,expected_policy_ruleset_id=26423889,now_utc=NOW)
        self.assertIn('BASELINE_DRIFT',v['reasons'])
    def test_resume_head_drift_blocks(self):
        self.first();o=observation();o['head_sha']='c'*40
        o['observation_sha256']=hashlib.sha256(canonical({k:v for k,v in o.items() if k!='observation_sha256'})).hexdigest()
        v=resume_gate(self.p,o,expected_policy_ruleset_id=26423889,now_utc=NOW)
        self.assertIn('HEAD_DRIFT',v['reasons'])
    def test_resume_wrong_ruleset_blocks(self):
        self.first();v=resume_gate(self.p,observation(),expected_policy_ruleset_id=12345,now_utc=NOW)
        self.assertIn('RULESET_ID_MISMATCH',v['reasons'])
    def test_resume_blockers_block(self):
        self.c['blockers']=['Gate A blocked'];self.first();v=resume_gate(self.p,observation(),expected_policy_ruleset_id=26423889,now_utc=NOW)
        self.assertEqual(v['state'],'BLOCKED_RECONCILIATION')
    def test_resume_no_ci_blocks(self):
        self.first();o=observation();o['ci_state']='INCOMPLETE'
        o['observation_sha256']=hashlib.sha256(canonical({k:v for k,v in o.items() if k!='observation_sha256'})).hexdigest()
        v=resume_gate(self.p,o,expected_policy_ruleset_id=26423889,now_utc=NOW)
        self.assertIn('REQUIRED_CI_NOT_SUCCESS',v['reasons'])
    def test_resume_modified_digest_blocks(self):
        self.first();o=observation();o['head_sha']='f'*40
        with self.assertRaises(ValueError):resume_gate(self.p,o,expected_policy_ruleset_id=26423889,now_utc=NOW)
    def test_no_network_no_write(self):
        with patch('urllib.request.urlopen',side_effect=AssertionError('network forbidden')):
            self.first();self.assertEqual(len(load(self.p)),1)
    def test_fail_second_writer_not_append(self):
        tail=self.first()['entry_sha256'];p=Path(str(self.p)+'.lock');p.mkdir()
        with self.assertRaises(StoreError):self.write('e2','2026-11-04T03:00:01Z',tail)
        p.rmdir();self.assertEqual(len(load(self.p)),1)
    def test_checkpoint_integrity_after_reopen(self):
        self.first();self.assertEqual(load(self.p)[0]['checkpoint'],cp())

if __name__=='__main__':unittest.main()
