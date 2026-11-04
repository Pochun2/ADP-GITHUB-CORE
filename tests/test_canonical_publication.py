"""Non-credentialed fail-closed publication integrity tests."""
import json
import unittest
from copy import deepcopy
from adp_context.canonical_publication import (
    BASELINE_SHA, REPOSITORY, PROJECT, TASK, PublicationError,
    canonical, digest, validate_candidate_bytes, checkpoint_paths,
    validate_identity,
)


def fixture():
    cp={
        'repository': REPOSITORY,'project_id':PROJECT,'task_id':TASK,
        'baseline_sha':BASELINE_SHA,'head_sha':BASELINE_SHA,
        'policy_ref':'ADP-GOV-AUTOMATION-001-v1.0','status':'BLOCKED',
        'blockers':['GATE_A_BLOCKED_UNVERIFIED','TRUSTED_ISSUER_NOT_DEPLOYED','CROSS_AGENT_RECOVERY_NOT_TESTED'],
        'non_negotiables':['NO_ACCOUNT_ORDER','T_PLUS_ONE_PAUSED_MANUAL'],
    }
    entry={'schema':'adp-context-journal-v1','sequence':1,
           'event_id':'CTX_A4_PUBLISH_GENESIS','at_utc':'2026-11-04T08:45:00Z',
           'prev_sha256':'0'*64,'checkpoint':cp,'checkpoint_sha256':digest(canonical(cp))}
    entry['entry_sha256']=digest(canonical(entry))
    jr=canonical(entry)
    _,jpath=checkpoint_paths(PROJECT,TASK)
    c={'schema':'adp-github-checkpoint-candidate-v1',
       'state':'CANDIDATE_NOT_GITHUB_PUBLISHED_NOT_ATTESTED',
       'repository':REPOSITORY,'baseline_sha':BASELINE_SHA,
       'project_id':PROJECT,'task_id':TASK,'journal_path':jpath,
       'journal_sha256':digest(jr),'journal_tip_sha256':entry['entry_sha256'],
       'checkpoint_sha256':entry['checkpoint_sha256'],'sequence':1,
       'note':'NO_RESUME_NO_GATE_PROMOTION_NO_ISSUER_NO_ORDER'}
    c['candidate_sha256']=digest(canonical(c))
    return c,entry


def encoded(c,e):
    e=deepcopy(e);e['checkpoint_sha256']=digest(canonical(e['checkpoint']))
    e['entry_sha256']=digest(canonical({k:v for k,v in e.items() if k!='entry_sha256'}))
    journal=canonical(e)
    c=deepcopy(c)
    c['journal_sha256']=digest(journal)
    c['journal_tip_sha256']=e['entry_sha256']
    c['checkpoint_sha256']=e['checkpoint_sha256']
    c['candidate_sha256']=digest(canonical({k:v for k,v in c.items() if k!='candidate_sha256'}))
    return canonical(c),journal


class CanonicalPublicationContracts(unittest.TestCase):
    def setUp(self):
        self.c,self.e=fixture()
    def check(self):
        b,j=encoded(self.c,self.e)
        return validate_candidate_bytes(b,j,REPOSITORY,PROJECT,TASK,BASELINE_SHA)
    def test_01_valid_candidate(self):
        self.assertEqual(self.check()['repository'],REPOSITORY)
    def test_02_digest_is_deterministic(self):
        self.assertEqual(self.check(),self.check())
    def test_03_wrong_repository(self):
        self.c['repository']='Other/core'
        with self.assertRaises(PublicationError):self.check()
    def test_04_wrong_baseline(self):
        self.c['baseline_sha']='0'*40
        with self.assertRaises(PublicationError):self.check()
    def test_05_wrong_project(self):
        self.c['project_id']='other'
        with self.assertRaises(PublicationError):self.check()
    def test_06_extra_candidate_field(self):
        self.c['grant_resume']=True
        with self.assertRaises(PublicationError):self.check()
    def test_07_journal_path_traversal(self):
        self.c['journal_path']='../../private'
        with self.assertRaises(PublicationError):self.check()
    def test_08_claimed_published(self):
        self.c['state']='PUBLISHED'
        with self.assertRaises(PublicationError):self.check()
    def test_09_wrong_security_note(self):
        self.c['note']='MAY_ORDER'
        with self.assertRaises(PublicationError):self.check()
    def test_10_no_gate_a_blocker(self):
        self.e['checkpoint']['blockers'].remove('GATE_A_BLOCKED_UNVERIFIED')
        with self.assertRaises(PublicationError):self.check()
    def test_11_missing_trade_guard(self):
        self.e['checkpoint']['non_negotiables'].remove('NO_ACCOUNT_ORDER')
        with self.assertRaises(PublicationError):self.check()
    def test_12_wrong_policy(self):
        self.e['checkpoint']['policy_ref']='UNAPPROVED'
        with self.assertRaises(PublicationError):self.check()
    def test_13_status_promotion(self):
        self.e['checkpoint']['status']='DONE_REPORTED'
        with self.assertRaises(PublicationError):self.check()
    def test_14_duplicate_json_key(self):
        b,j=encoded(self.c,self.e)
        b=b'{"schema":"x","schema":"y"}\n'
        with self.assertRaises(PublicationError):validate_candidate_bytes(b,j,REPOSITORY,PROJECT,TASK,BASELINE_SHA)
    def test_15_modified_raw_journal(self):
        b,j=encoded(self.c,self.e)
        with self.assertRaises(PublicationError):validate_candidate_bytes(b,j+b' ',REPOSITORY,PROJECT,TASK,BASELINE_SHA)
    def test_16_wrong_event_id(self):
        self.e['event_id']='FAKE_PAST_EVENT'
        with self.assertRaises(PublicationError):self.check()
    def test_17_genesis_replay(self):
        b,j=encoded(self.c,self.e)
        with self.assertRaises(PublicationError):validate_candidate_bytes(b,j+j,REPOSITORY,PROJECT,TASK,BASELINE_SHA)
    def test_18_secret_token(self):
        self.e['checkpoint']['next_action']='secret=not_allowed_value'
        with self.assertRaises(PublicationError):self.check()
    def test_19_windows_user_path(self):
        self.e['checkpoint']['next_action']='C:\\Users\\private\\file'
        with self.assertRaises(PublicationError):self.check()
    def test_20_invalid_caller_identity(self):
        with self.assertRaises(PublicationError):validate_identity(REPOSITORY,PROJECT,TASK,'f'*40)
    def test_21_manifest_tamper(self):
        b,j=encoded(self.c,self.e)
        o=json.loads(b);o['candidate_sha256']='f'*64
        with self.assertRaises(PublicationError):validate_candidate_bytes(canonical(o),j,REPOSITORY,PROJECT,TASK,BASELINE_SHA)
    def test_22_entry_digest_tamper(self):
        b,j=encoded(self.c,self.e)
        e=json.loads(j);e['entry_sha256']='f'*64
        with self.assertRaises(PublicationError):validate_candidate_bytes(b,canonical(e),REPOSITORY,PROJECT,TASK,BASELINE_SHA)
    def test_23_no_string_boolean_sequence(self):
        self.c['sequence']=True
        with self.assertRaises(PublicationError):self.check()
    def test_24_oversized_manifest(self):
        b,j=encoded(self.c,self.e)
        with self.assertRaises(PublicationError):validate_candidate_bytes(b+b' '*(12_001),j,REPOSITORY,PROJECT,TASK,BASELINE_SHA)

if __name__=='__main__':unittest.main()
