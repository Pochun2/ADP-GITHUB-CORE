"""CTX-A3-GH isolated staging tests; never create GitHub PRs."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from adp_context.checkpoint_store import append
from adp_context.github_checkpoint import (CandidateError, verify_journal_candidate,
    validate_candidate, stage, check_stage)

BASE='b166f4a4ab5dbda8b52489cb7a730090443714d7'
HEAD='3e140bc2f08ee3dd42f4b2110330f71f7e83f57e'
REPO='Pochun2/GOV-TRUSTED-ISSUER'
NOW='2026-11-04T03:00:00Z'

def sample():
    return {'schema':'adp-context-v1','project_id':'demo','task_id':'CTX-001','repository':REPO,
            'baseline_sha':BASE,'head_sha':HEAD,'policy_ref':'PINNED-PROPOSED',
            'status':'READY_FOR_REVIEW','completed_steps':['offline tests'],
            'pending_steps':['review'], 'blockers':[],
            'evidence_refs':[{'locator':'evidence.json','sha256':'a'*64,'claim_level':'EVIDENCED'}],
            'decision_refs':[], 'non_negotiables':['NO ACCOUNT/ORDER','T+1 PAUSED_MANUAL'],
            'last_verified_at_utc':None,'next_action':'review',
            'context_sources':[{'locator':'src.txt','sha256':'b'*64,'claim_level':'REPORTED'}]}

class GHCheckpointTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.journal=self.root/'local.jsonl'
        append(self.journal,sample(),event_id='A1',at_utc=NOW)
        self.stagepath=self.root/'stage'
    def proposal(self):
        return verify_journal_candidate(self.journal,repository=REPO,expected_main_sha=BASE)
    def staged(self):
        return stage(self.journal,repository=REPO,expected_main_sha=BASE,output_root=self.stagepath)
    def test_manifest_identity(self):
        d,_=self.proposal();self.assertEqual(d['repository'],REPO)
    def test_manifest_baseline(self):
        d,_=self.proposal();self.assertEqual(d['baseline_sha'],BASE)
    def test_manifest_state_no_grant(self):
        d,_=self.proposal();self.assertIn('NOT_ATTESTED',d['state'])
    def test_manifest_deterministic(self):
        self.assertEqual(self.proposal(),self.proposal())
    def test_manifest_path(self):
        d,_=self.proposal();self.assertEqual(d['journal_path'],'.adp/checkpoints/demo/CTX-001/journal.jsonl')
    def test_staged(self):
        result=self.staged();self.assertIn('NOT_PUBLISHED',result['state'])
    def test_stage_readback(self):
        self.staged();self.assertEqual(check_stage(self.stagepath,repository=REPO,expected_main_sha=BASE)['sequence'],1)
    def test_stage_double_refused(self):
        self.staged()
        with self.assertRaises(CandidateError):self.staged()
    def test_stage_existing_empty_refused(self):
        self.stagepath.mkdir()
        with self.assertRaises(CandidateError):self.staged()
    def test_repo_mismatch(self):
        with self.assertRaises(CandidateError):verify_journal_candidate(self.journal,repository='Other/Repo',expected_main_sha=BASE)
    def test_baseline_drift(self):
        with self.assertRaises(CandidateError):verify_journal_candidate(self.journal,repository=REPO,expected_main_sha='f'*40)
    def test_bad_main(self):
        with self.assertRaises(CandidateError):verify_journal_candidate(self.journal,repository=REPO,expected_main_sha='bad')
    def test_bad_repo(self):
        with self.assertRaises(CandidateError):verify_journal_candidate(self.journal,repository='../a',expected_main_sha=BASE)
    def test_tampered_journal(self):
        self.journal.write_bytes(self.journal.read_bytes().replace(b'READY_FOR_REVIEW',b'BLOCKED'))
        with self.assertRaises(CandidateError):self.proposal()
    def test_truncated_journal(self):
        self.journal.write_bytes(self.journal.read_bytes()[:-1])
        with self.assertRaises(CandidateError):self.proposal()
    def test_manifest_tamper(self):
        self.staged();m=self.stagepath/'candidate.json'
        data=json.loads(m.read_text());data['state']='APPROVED';m.write_text(json.dumps(data))
        with self.assertRaises(CandidateError):check_stage(self.stagepath,repository=REPO,expected_main_sha=BASE)
    def test_journal_tamper(self):
        self.staged();j=self.stagepath/'.adp/checkpoints/demo/CTX-001/journal.jsonl'
        j.write_bytes(j.read_bytes().replace(b'READY_FOR_REVIEW',b'BLOCKED'))
        with self.assertRaises(CandidateError):check_stage(self.stagepath,repository=REPO,expected_main_sha=BASE)
    def test_manifest_duplicate_keys(self):
        self.staged();m=self.stagepath/'candidate.json';raw=m.read_text();m.write_text(raw[:-1]+',"schema":"oops"}')
        with self.assertRaises(CandidateError):check_stage(self.stagepath,repository=REPO,expected_main_sha=BASE)
    def test_missing_manifest(self):
        self.staged();(self.stagepath/'candidate.json').unlink()
        with self.assertRaises(CandidateError):check_stage(self.stagepath,repository=REPO,expected_main_sha=BASE)
    def test_stage_wrong_repo(self):
        self.staged()
        with self.assertRaises(CandidateError):check_stage(self.stagepath,repository='Elsewhere/Repo',expected_main_sha=BASE)
    def test_stage_wrong_base(self):
        self.staged()
        with self.assertRaises(CandidateError):check_stage(self.stagepath,repository=REPO,expected_main_sha='f'*40)
    def test_manifest_digest_tamper(self):
        d,raw=self.proposal();d['candidate_sha256']='f'*64
        with self.assertRaises(CandidateError):validate_candidate(d,raw,repository=REPO,expected_main_sha=BASE)
    def test_wrong_bytes(self):
        d,raw=self.proposal()
        with self.assertRaises(CandidateError):validate_candidate(d,raw+b' ',repository=REPO,expected_main_sha=BASE)
    def test_invalid_sequence_type(self):
        d,raw=self.proposal();d['sequence']=True
        with self.assertRaises(CandidateError):validate_candidate(d,raw,repository=REPO,expected_main_sha=BASE)
    def test_extra_fields(self):
        d,raw=self.proposal();d['token']='SECRET'
        with self.assertRaises(CandidateError):validate_candidate(d,raw,repository=REPO,expected_main_sha=BASE)
    def test_missing_journal(self):
        self.journal.unlink()
        with self.assertRaises(CandidateError):self.proposal()
    def test_two_events(self):
        from adp_context.checkpoint_store import load
        tail=load(self.journal)[-1]['entry_sha256']
        append(self.journal,sample(),event_id='A2',at_utc='2026-11-04T03:00:01Z',expected_last_sha256=tail)
        d,_=self.proposal();self.assertEqual(d['sequence'],2)
    def test_symlink_journal_rejected(self):
        link=self.root/'alias.jsonl'
        try:link.symlink_to(self.journal)
        except (OSError,NotImplementedError):self.skipTest('symlink unsupported')
        with self.assertRaises(CandidateError):verify_journal_candidate(link,repository=REPO,expected_main_sha=BASE)
    def test_staged_file_symlink_rejected(self):
        self.staged();j=self.stagepath/'.adp/checkpoints/demo/CTX-001/journal.jsonl'
        backup=self.root/'original';j.rename(backup)
        try:j.symlink_to(backup)
        except (OSError,NotImplementedError):self.skipTest('symlink unsupported')
        with self.assertRaises(CandidateError):check_stage(self.stagepath,repository=REPO,expected_main_sha=BASE)

if __name__=='__main__':unittest.main()
