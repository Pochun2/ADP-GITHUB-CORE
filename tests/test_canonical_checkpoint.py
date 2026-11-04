import json
import errno
import tempfile
import unittest
from pathlib import Path

from adp_context.canonical_checkpoint import CanonicalError, assess_snapshot, read_candidate, SCHEMA
from adp_context.checkpoint_store import append
from adp_context.github_checkpoint import verify_journal_candidate

REPO='Pochun2/ADP-GITHUB-CORE'
BASE='a'*40
COMMIT='b'*40

class CanonicalCheckpointTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.cp=json.loads((Path(__file__).parent.parent/'examples'/'sample.checkpoint.json').read_text())
        self.cp['repository']=REPO
        self.cp['baseline_sha']=BASE
        self.cp['project_id']='project-one'
        self.cp['task_id']='CTX-A4'
        self.cp['status']='BLOCKED'
        self.base=self.root/'.adp/checkpoints/project-one/CTX-A4'
        self.base.mkdir(parents=True)
        append(self.base/'journal.jsonl',self.cp,event_id='start',at_utc='2026-11-04T00:00:00Z')
        self.c,self.raw=verify_journal_candidate(self.base/'journal.jsonl',repository=REPO,expected_main_sha=BASE)
        (self.base/'candidate.json').write_text(json.dumps(self.c))
        self.obs=dict(schema=SCHEMA,repository=REPO,commit_sha=COMMIT,main_sha=COMMIT,
            main_ancestor_confirmed=True,ruleset_id=26509773,ruleset_name='ADP-MAIN-PROTECTION',
            ruleset_enforcement='active',required_check='adp-context-suite',
            required_check_conclusion='success',required_check_app_id=15368,
            bypass_actor_count=0,candidate_path_present=True,journal_path_present=True,
            source_kind='INDEPENDENT_GITHUB_READ_REPORTED')
    def load(self):
        return read_candidate(self.root,repository=REPO,baseline_sha=BASE,project_id='project-one',task_id='CTX-A4')
    def test_valid_candidate(self):self.assertEqual(self.load(),self.c)
    def test_protected_snapshot_is_not_authorization(self):
        self.assertEqual(assess_snapshot(self.load(),repository=REPO,commit_sha=COMMIT,observation=self.obs)['state'], 'PROTECTED_COMMIT_REPORTED_REVIEW_REQUIRED_NOT_AUTHORIZED')
    def test_observation_digest_deterministic(self):
        a=assess_snapshot(self.load(),repository=REPO,commit_sha=COMMIT,observation=self.obs)
        b=assess_snapshot(self.load(),repository=REPO,commit_sha=COMMIT,observation=self.obs)
        self.assertEqual(a,b)
    def test_missing_candidate(self):
        (self.base/'candidate.json').unlink()
        with self.assertRaises(CanonicalError):self.load()
    def test_missing_journal(self):
        (self.base/'journal.jsonl').unlink()
        with self.assertRaises(CanonicalError):self.load()
    def test_candidate_tamper(self):
        p=self.base/'candidate.json';p.write_text(p.read_text().replace('candidate_sha256','wrong_sha'))
        with self.assertRaises(CanonicalError):self.load()
    def test_journal_tamper(self):
        p=self.base/'journal.jsonl';p.write_bytes(p.read_bytes().replace(b'project-one',b'project-two'))
        with self.assertRaises(CanonicalError):self.load()
    def test_duplicate_manifest_key(self):
        p=self.base/'candidate.json';p.write_text('{"schema":"x","schema":"y"}')
        with self.assertRaises(CanonicalError):self.load()
    def test_bad_repo(self):
        with self.assertRaises(CanonicalError):read_candidate(self.root,repository='not-repo',baseline_sha=BASE,project_id='project-one',task_id='CTX-A4')
    def test_wrong_repo(self):
        with self.assertRaises(CanonicalError):read_candidate(self.root,repository='Other/Core',baseline_sha=BASE,project_id='project-one',task_id='CTX-A4')
    def test_wrong_base(self):
        with self.assertRaises(CanonicalError):read_candidate(self.root,repository=REPO,baseline_sha='c'*40,project_id='project-one',task_id='CTX-A4')
    def test_wrong_task(self):
        with self.assertRaises(CanonicalError):read_candidate(self.root,repository=REPO,baseline_sha=BASE,project_id='project-one',task_id='OTHER')
    def test_symlink_journal(self):
        (self.base/'journal.jsonl').unlink()
        try:
            (self.base/'journal.jsonl').symlink_to(self.root/'outside')
        except OSError as exc:
            # Windows may deny symlink creation without Developer Mode / SeCreateSymbolicLinkPrivilege.
            # Only an explicit environment limitation is skipped; other OS errors remain failures.
            if getattr(exc, 'winerror', None) == 1314 or exc.errno in (errno.EPERM, errno.EACCES, errno.ENOTSUP):
                self.skipTest('symlink creation unsupported or permission denied in this environment')
            raise
        with self.assertRaises(CanonicalError):
            self.load()
    def test_bad_commit(self):
        with self.assertRaises(CanonicalError):assess_snapshot(self.c,repository=REPO,commit_sha='invalid',observation=self.obs)
    def test_injected_source(self):
        self.obs['source_kind']='FIXTURE'
        with self.assertRaises(CanonicalError):assess_snapshot(self.c,repository=REPO,commit_sha=COMMIT,observation=self.obs)
    def test_wrong_schema(self):
        self.obs['schema']='unknown'
        with self.assertRaises(CanonicalError):assess_snapshot(self.c,repository=REPO,commit_sha=COMMIT,observation=self.obs)
    def test_observation_wrong_repo(self):
        self.obs['repository']='Other/Core'
        with self.assertRaises(CanonicalError):assess_snapshot(self.c,repository=REPO,commit_sha=COMMIT,observation=self.obs)
    def test_commit_drift(self):
        self.obs['commit_sha']='c'*40
        with self.assertRaises(CanonicalError):assess_snapshot(self.c,repository=REPO,commit_sha=COMMIT,observation=self.obs)
    def test_extra_observation_fields(self):
        self.obs['override']='approve'
        with self.assertRaises(CanonicalError):assess_snapshot(self.c,repository=REPO,commit_sha=COMMIT,observation=self.obs)
    def test_missing_observation_field(self):
        del self.obs['schema']
        with self.assertRaises(CanonicalError):assess_snapshot(self.c,repository=REPO,commit_sha=COMMIT,observation=self.obs)
    def test_unmerged_commit(self):
        self.obs['main_ancestor_confirmed']=False
        a=assess_snapshot(self.c,repository=REPO,commit_sha=COMMIT,observation=self.obs)
        self.assertIn('NOT_IN_PROTECTED_MAIN_HISTORY',a['blockers'])
    def test_inactive_ruleset(self):
        self.obs['ruleset_enforcement']='disabled'
        self.assertIn('PROTECTION_NOT_ACTIVE',assess_snapshot(self.c,repository=REPO,commit_sha=COMMIT,observation=self.obs)['blockers'])
    def test_wrong_ruleset(self):
        self.obs['ruleset_name']='fake'
        self.assertIn('PROTECTION_NOT_ACTIVE',assess_snapshot(self.c,repository=REPO,commit_sha=COMMIT,observation=self.obs)['blockers'])
    def test_bypass(self):
        self.obs['bypass_actor_count']=1
        self.assertIn('BYPASS_ACTORS_PRESENT',assess_snapshot(self.c,repository=REPO,commit_sha=COMMIT,observation=self.obs)['blockers'])
    def test_required_ci_failed(self):
        self.obs['required_check_conclusion']='failure'
        self.assertIn('REQUIRED_CHECK_NOT_VERIFIED',assess_snapshot(self.c,repository=REPO,commit_sha=COMMIT,observation=self.obs)['blockers'])
    def test_wrong_ci_app(self):
        self.obs['required_check_app_id']=999
        self.assertIn('REQUIRED_CHECK_NOT_VERIFIED',assess_snapshot(self.c,repository=REPO,commit_sha=COMMIT,observation=self.obs)['blockers'])
    def test_wrong_ci_context(self):
        self.obs['required_check']='weak-test'
        self.assertIn('REQUIRED_CHECK_NOT_VERIFIED',assess_snapshot(self.c,repository=REPO,commit_sha=COMMIT,observation=self.obs)['blockers'])
    def test_candidate_remote_missing(self):
        self.obs['candidate_path_present']=False
        self.assertIn('REMOTE_PATHS_MISSING',assess_snapshot(self.c,repository=REPO,commit_sha=COMMIT,observation=self.obs)['blockers'])
    def test_journal_remote_missing(self):
        self.obs['journal_path_present']=False
        self.assertIn('REMOTE_PATHS_MISSING',assess_snapshot(self.c,repository=REPO,commit_sha=COMMIT,observation=self.obs)['blockers'])
    def test_string_bool_reject(self):
        self.obs['main_ancestor_confirmed']='true'
        with self.assertRaises(CanonicalError):assess_snapshot(self.c,repository=REPO,commit_sha=COMMIT,observation=self.obs)
    def test_invalid_bypass_count(self):
        self.obs['bypass_actor_count']=-1
        with self.assertRaises(CanonicalError):assess_snapshot(self.c,repository=REPO,commit_sha=COMMIT,observation=self.obs)
    def test_invalid_check_app_id(self):
        self.obs['required_check_app_id']='15368'
        with self.assertRaises(CanonicalError):assess_snapshot(self.c,repository=REPO,commit_sha=COMMIT,observation=self.obs)
    def test_no_bypass_default_hardcoded(self):
        result=assess_snapshot(self.c,repository=REPO,commit_sha=COMMIT,observation=self.obs)
        self.assertIn('NO_RESUME',result['note'])

if __name__=='__main__':unittest.main()
