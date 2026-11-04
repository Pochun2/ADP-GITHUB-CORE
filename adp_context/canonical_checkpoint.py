"""CTX-A4 protected-commit checkpoint verifier.

This verifier cannot publish, approve, merge, issue attestations, or authorize
execution. An input observation is *reported evidence*, never an authorization.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import json
import re

from .checkpoint_store import load, StoreError
from .engine import canonical
from .github_checkpoint import validate_candidate, verify_journal_candidate, CandidateError

HEX40 = re.compile(r'[0-9a-f]{40}\Z')
HEX64 = re.compile(r'[0-9a-f]{64}\Z')
REPO = re.compile(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z')
RULESET_NAME = 'ADP-MAIN-PROTECTION'
CHECK_NAME = 'adp-context-suite'
SCHEMA = 'adp-canonical-read-observation-v1'

class CanonicalError(ValueError):
    pass

def refuse(code):
    raise CanonicalError(code)

def unique_pairs(pairs):
    d={}
    for k,v in pairs:
        if k in d: refuse('DUPLICATE_JSON_KEY')
        d[k]=v
    return d

def read_candidate(root, *, repository, baseline_sha, project_id, task_id):
    """Fully verify a previously committed A3-GH candidate, not a publication."""
    if type(repository) is not str or not REPO.fullmatch(repository): refuse('REPOSITORY_INVALID')
    if type(baseline_sha) is not str or not HEX40.fullmatch(baseline_sha): refuse('BASE_SHA_INVALID')
    if not all(type(x) is str and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}',x) for x in (project_id,task_id)):
        refuse('TASK_ID_INVALID')
    root=Path(root)
    if root.is_symlink() or not root.is_dir(): refuse('ROOT_UNTRUSTED')
    base=root/'.adp'/'checkpoints'/project_id/task_id
    m=base/'candidate.json'
    j=base/'journal.jsonl'
    if any(p.is_symlink() for p in [base,m,j]) or not m.is_file() or not j.is_file():
        refuse('CANONICAL_FILES_MISSING')
    if m.stat().st_size > 12000 or j.stat().st_size > 5_000_000: refuse('OVERSIZED_FILE')
    try:
        raw=j.read_bytes()
        obj=json.loads(m.read_text('utf-8'),object_pairs_hook=unique_pairs)
        if type(obj) is not dict: refuse('INVALID_CANDIDATE')
        validate_candidate(obj,raw,repository=repository,expected_main_sha=baseline_sha)
        expected,verified=verify_journal_candidate(j,repository=repository,expected_main_sha=baseline_sha)
    except (UnicodeError, OSError, StoreError, CandidateError, ValueError, json.JSONDecodeError) as e:
        if isinstance(e,CanonicalError): raise
        refuse('INTEGRITY_VALIDATION_FAILED')
    if obj != expected or verified != raw: refuse('MANIFEST_CHAIN_MISMATCH')
    if obj['project_id'] != project_id or obj['task_id'] != task_id:
        refuse('TASK_MISMATCH')
    return obj

def assess_snapshot(candidate, *, repository, commit_sha, observation):
    """Conservative classification using separately collected, non-authoritative metadata.

    A protected-branch observation is necessary, not sufficient. Even a positive
    assessment cannot grant resume, approve a PR, or establish independent trust.
    """
    if type(commit_sha) is not str or not HEX40.fullmatch(commit_sha): refuse('COMMIT_INVALID')
    if type(observation) is not dict or set(observation) != {
        'schema','repository','commit_sha','main_sha','main_ancestor_confirmed',
        'ruleset_id','ruleset_name','ruleset_enforcement','required_check',
        'required_check_conclusion','required_check_app_id','bypass_actor_count',
        'candidate_path_present','journal_path_present','source_kind'}:
        refuse('OBSERVATION_FIELDS_INVALID')
    if observation['schema'] != SCHEMA: refuse('OBSERVATION_SCHEMA_INVALID')
    if observation['source_kind'] != 'INDEPENDENT_GITHUB_READ_REPORTED':
        refuse('OBSERVATION_UNTRUSTED_SOURCE')
    if observation['repository'] != repository or candidate['repository'] != repository:
        refuse('REPOSITORY_DRIFT')
    if observation['commit_sha'] != commit_sha: refuse('COMMIT_DRIFT')
    if type(observation['main_sha']) is not str or not HEX40.fullmatch(observation['main_sha']):
        refuse('MAIN_SHA_INVALID')
    if type(observation['ruleset_id']) is not int or observation['ruleset_id'] <= 0:
        refuse('RULESET_ID_INVALID')
    if type(observation['required_check_app_id']) is not int or observation['required_check_app_id'] <= 0:
        refuse('CHECK_APP_INVALID')
    for k in ('main_ancestor_confirmed','candidate_path_present','journal_path_present'):
        if type(observation[k]) is not bool: refuse('INVALID_BOOLEAN')
    if type(observation['bypass_actor_count']) is not int or observation['bypass_actor_count'] < 0:
        refuse('BYPASS_COUNT_INVALID')
    if not all(type(candidate.get(k)) is str and HEX64.fullmatch(candidate[k]) for k in ('candidate_sha256','journal_sha256','journal_tip_sha256')):
        refuse('CANDIDATE_HASH_INVALID')
    blockers=[]
    if not observation['main_ancestor_confirmed']: blockers.append('NOT_IN_PROTECTED_MAIN_HISTORY')
    if observation['ruleset_enforcement'] != 'active' or observation['ruleset_name'] != RULESET_NAME:
        blockers.append('PROTECTION_NOT_ACTIVE')
    if observation['bypass_actor_count'] != 0: blockers.append('BYPASS_ACTORS_PRESENT')
    if observation['required_check'] != CHECK_NAME or observation['required_check_conclusion'] != 'success' or observation['required_check_app_id'] != 15368:
        blockers.append('REQUIRED_CHECK_NOT_VERIFIED')
    if not observation['candidate_path_present'] or not observation['journal_path_present']:
        blockers.append('REMOTE_PATHS_MISSING')
    return {
        'state': 'BLOCKED_CANONICAL_RECONCILIATION' if blockers else 'PROTECTED_COMMIT_REPORTED_REVIEW_REQUIRED_NOT_AUTHORIZED',
        'blockers': blockers,
        'commit_sha': commit_sha,
        'checkpoint_sha256': candidate['checkpoint_sha256'],
        'journal_tip_sha256': candidate['journal_tip_sha256'],
        'observation_sha256': sha256(canonical(observation)).hexdigest(),
        'note':'OBSERVATION_IS_NOT_ATTESTATION_NO_RESUME_NO_ISSUER_NO_ACCOUNT_ORDER',
    }

def main(argv=None):
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument('--self-check',action='store_true')
    a=p.parse_args(argv)
    if a.self_check:
        print(json.dumps({'state':'OFFLINE_ONLY','note':'NO_GITHUB_WRITE_NO_MERGE_NO_RESUME_NO_ISSUER_GATE_A_BLOCKED'},sort_keys=True))
        return 0
    return 2

if __name__=='__main__':
    raise SystemExit(main())
