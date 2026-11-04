"""CTX-A3-GH: GitHub PR candidate from a verified A3 journal.

This module cannot write GitHub, grant resume, issue checks or merge PRs.
GitHub-branch publication is performed only by a separate operator-invoked script.
"""
from __future__ import annotations

from hashlib import sha256
import argparse
import json
from pathlib import Path
import re

from .engine import canonical, validate_checkpoint
from .checkpoint_store import load, StoreError

SCHEMA = 'adp-github-checkpoint-candidate-v1'
REPO = re.compile(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z')
SHA = re.compile(r'[0-9a-f]{40}\Z')
ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}\Z')
HEX64 = re.compile(r'[0-9a-f]{64}\Z')
MAX_JOURNAL = 5_000_000

class CandidateError(ValueError):
    pass

def reject(code):
    raise CandidateError(code)

def _id(value):
    return type(value) is str and bool(ID.fullmatch(value)) and value not in ('.','..')

def verify_journal_candidate(path, *, repository, expected_main_sha):
    """Produce immutable content-addressed proposal, not a trusted proof.

    Caller supplies separately pinned main SHA; it is NOT inferred from journal.
    The publisher must re-fetch remote main at time of push and before merge.
    """
    if type(repository) is not str or not REPO.fullmatch(repository):
        reject('INVALID_REPOSITORY')
    if type(expected_main_sha) is not str or not SHA.fullmatch(expected_main_sha):
        reject('INVALID_PINNED_MAIN')
    p = Path(path)
    if p.is_symlink() or not p.is_file() or p.stat().st_size > MAX_JOURNAL:
        reject('UNTRUSTED_JOURNAL')
    try:
        before = p.read_bytes()
        events = load(p)
        after = p.read_bytes()
    except (StoreError, OSError, ValueError):
        reject('INVALID_JOURNAL')
    if before != after or not before.endswith(b'\n'):
        reject('JOURNAL_CHANGED_DURING_READ')
    # No untrusted paths, references or identity can broaden repository scope.
    cp = events[-1]['checkpoint']
    validate_checkpoint(cp)
    if cp['repository'] != repository:
        reject('REPOSITORY_MISMATCH')
    if cp['baseline_sha'] != expected_main_sha:
        reject('BASELINE_DRIFT')
    project, task = cp['project_id'], cp['task_id']
    if not _id(project) or not _id(task):
        reject('INVALID_TASK_ID')
    relative = f'.adp/checkpoints/{project}/{task}/journal.jsonl'
    manifest = {
        'schema': SCHEMA,
        'state': 'CANDIDATE_NOT_GITHUB_PUBLISHED_NOT_ATTESTED',
        'repository': repository,
        'baseline_sha': expected_main_sha,
        'project_id': project,
        'task_id': task,
        'journal_path': relative,
        'journal_sha256': sha256(before).hexdigest(),
        'journal_tip_sha256': events[-1]['entry_sha256'],
        'checkpoint_sha256': events[-1]['checkpoint_sha256'],
        'sequence': len(events),
        'note': 'NO_RESUME_NO_GATE_PROMOTION_NO_ISSUER_NO_ORDER',
    }
    manifest['candidate_sha256'] = sha256(canonical(manifest)).hexdigest()
    return manifest, before

def validate_candidate(candidate, journal_bytes, *, repository, expected_main_sha):
    if type(candidate) is not dict or set(candidate) != {
        'schema','state','repository','baseline_sha','project_id','task_id',
        'journal_path','journal_sha256','journal_tip_sha256','checkpoint_sha256',
        'sequence','note','candidate_sha256'}:
        reject('CANDIDATE_FIELDS')
    if candidate['schema'] != SCHEMA or candidate['state'] != 'CANDIDATE_NOT_GITHUB_PUBLISHED_NOT_ATTESTED':
        reject('CANDIDATE_STATUS')
    if candidate['repository'] != repository or candidate['baseline_sha'] != expected_main_sha:
        reject('CANDIDATE_SCOPE_DRIFT')
    if not _id(candidate['project_id']) or not _id(candidate['task_id']):
        reject('CANDIDATE_ID')
    if candidate['journal_path'] != f".adp/checkpoints/{candidate['project_id']}/{candidate['task_id']}/journal.jsonl":
        reject('CANDIDATE_PATH')
    if type(journal_bytes) is not bytes or not journal_bytes or len(journal_bytes) > MAX_JOURNAL:
        reject('INVALID_JOURNAL_BYTES')
    if candidate['journal_sha256'] != sha256(journal_bytes).hexdigest():
        reject('CANDIDATE_JOURNAL_MISMATCH')
    if type(candidate['sequence']) is not int or candidate['sequence'] < 1:
        reject('CANDIDATE_SEQUENCE')
    for key in ('journal_sha256','journal_tip_sha256','checkpoint_sha256','candidate_sha256'):
        if type(candidate[key]) is not str or not HEX64.fullmatch(candidate[key]):
            reject('CANDIDATE_HASH')
    body = {k:v for k,v in candidate.items() if k != 'candidate_sha256'}
    if sha256(canonical(body)).hexdigest() != candidate['candidate_sha256']:
        reject('CANDIDATE_DIGEST')
    return True

def stage(journal, *, repository, expected_main_sha, output_root):
    """Write candidate ONLY to a new, local, isolated staging directory.

    Refuses existing output path; no side effects outside the selected root.
    Does not execute git or acquire credentials.
    """
    manifest, raw = verify_journal_candidate(journal, repository=repository, expected_main_sha=expected_main_sha)
    root = Path(output_root)
    if root.exists() or root.is_symlink() or not root.parent.is_dir() or root.parent.is_symlink():
        reject('UNSAFE_OR_EXISTING_OUTPUT')
    root.mkdir(mode=0o700)
    try:
        dest = root / manifest['journal_path']
        dest.parent.mkdir(parents=True)
        dest.write_bytes(raw)
        m = root / 'candidate.json'
        m.write_bytes(canonical(manifest))
        validate_candidate(manifest, dest.read_bytes(), repository=repository, expected_main_sha=expected_main_sha)
        return {'state':'LOCAL_GITHUB_PR_CANDIDATE_STAGED_NOT_PUBLISHED',
                'candidate_sha256':manifest['candidate_sha256'],
                'journal_path':manifest['journal_path'],
                'sequence':manifest['sequence'],
                'note':'LOCAL_STAGING_ONLY_NO_GITHUB_WRITE_NO_ISSUER_GATE_A_BLOCKED'}
    except Exception:
        # Directory is intentionally retained to make partial failure evident.
        raise

def check_stage(root, *, repository, expected_main_sha):
    p=Path(root)
    if not p.is_dir() or p.is_symlink():
        reject('STAGE_UNAVAILABLE')
    manifest_path = p / 'candidate.json'
    if manifest_path.is_symlink() or not manifest_path.is_file() or manifest_path.stat().st_size > 12_000:
        reject('MANIFEST_UNAVAILABLE')
    try:
        # Reject duplicate keys, not merely last-wins parse.
        def unique(pairs):
            d={}
            for k,v in pairs:
                if k in d: reject('DUPLICATE_MANIFEST_KEY')
                d[k]=v
            return d
        c=json.loads(manifest_path.read_text('utf-8'),object_pairs_hook=unique)
        if type(c) is not dict or not _id(c.get('project_id')) or not _id(c.get('task_id')):
            reject('INVALID_MANIFEST')
        path=p / f".adp/checkpoints/{c['project_id']}/{c['task_id']}/journal.jsonl"
        if path.is_symlink() or not path.is_file():
            reject('STAGED_JOURNAL_UNAVAILABLE')
        raw=path.read_bytes()
        validate_candidate(c,raw,repository=repository,expected_main_sha=expected_main_sha)
        # Entire chain, not just digest of bytes.
        check, raw2=verify_journal_candidate(path,repository=repository,expected_main_sha=expected_main_sha)
        if raw != raw2 or c != check:
            reject('STAGE_CHAIN_OR_MANIFEST_MISMATCH')
        return c
    except (OSError,UnicodeError,ValueError,json.JSONDecodeError) as ex:
        if isinstance(ex,CandidateError):raise
        reject('STAGE_VALIDATION_FAILED')

def main(argv=None):
    parser=argparse.ArgumentParser(description='CTX-A3-GH local PR candidate only')
    sub=parser.add_subparsers(dest='cmd')
    sub.add_parser('self-check')
    stagep=sub.add_parser('stage')
    stagep.add_argument('--journal',required=True)
    stagep.add_argument('--repository',required=True)
    stagep.add_argument('--main-sha',required=True)
    stagep.add_argument('--output',required=True)
    check=sub.add_parser('check')
    check.add_argument('--root',required=True)
    check.add_argument('--repository',required=True)
    check.add_argument('--main-sha',required=True)
    args=parser.parse_args(argv)
    try:
        if args.cmd=='self-check':
            result={'state':'OFFLINE_ONLY','note':'NO_GITHUB_WRITE_NO_ISSUER_KEY_NO_AUTO_MERGE_GATE_A_BLOCKED'}
        elif args.cmd=='stage':
            result=stage(args.journal,repository=args.repository,expected_main_sha=args.main_sha,output_root=args.output)
        elif args.cmd=='check':
            c=check_stage(args.root,repository=args.repository,expected_main_sha=args.main_sha)
            result={'state':'LOCAL_CANDIDATE_VERIFIED_NOT_PUBLISHED','candidate_sha256':c['candidate_sha256']}
        else:
            parser.print_help();return 2
        print(json.dumps(result,sort_keys=True));return 0
    except (CandidateError,StoreError,ValueError,OSError):
        print(json.dumps({'state':'BLOCKED','reason':'CANDIDATE_VALIDATION_FAILED'},sort_keys=True));return 2

if __name__=='__main__':
    raise SystemExit(main())
