"""ADP canonical publication byte-integrity contracts (v1.0).

A protected main SHA may establish that particular bytes were published. It is
not an Issuer signature and NEVER grants resume, secrets, trading or Gate A.
This module has no GitHub write or credential functionality.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

REPOSITORY = 'Pochun2/ADP-GITHUB-CORE'
PROJECT = 'ADP-GITHUB-CORE'
TASK = 'CTX-A4-PUBLISH'
BASELINE_SHA = '024b04ac8216125ba6258556f68d2587fcc6875a'
SCHEMA = 'adp-github-checkpoint-candidate-v1'
HEX40 = re.compile(r'[0-9a-f]{40}\Z')
HEX64 = re.compile(r'[0-9a-f]{64}\Z')
TOKEN = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}\Z')
MAX_CANDIDATE = 12_000
MAX_JOURNAL = 5_000_000
EXPECTED_STATE = 'CANDIDATE_NOT_GITHUB_PUBLISHED_NOT_ATTESTED'
REQUIRED_BLOCKERS = {'GATE_A_BLOCKED_UNVERIFIED','TRUSTED_ISSUER_NOT_DEPLOYED','CROSS_AGENT_RECOVERY_NOT_TESTED'}
PRIVATE_PATTERN = re.compile(r'(?i)(?:github_pat_[A-Za-z0-9_]{10,}|gh[pousr]_[A-Za-z0-9]{10,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|(?:password|secret|token|access_token|private_key|api_key)\s*[:=]\s*[^\s,;]+|[A-Z]:\\Users\\)')

class PublicationError(ValueError):
    pass

def reject(code):
    raise PublicationError(code)

def canonical(obj):
    return (json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False) + '\n').encode('utf-8')

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def unique_pairs(pairs):
    result={}
    for key,value in pairs:
        if key in result:
            reject('DUPLICATE_JSON_KEY')
        result[key]=value
    return result

def parse_object(raw, max_size):
    if type(raw) is not bytes or not raw or len(raw) > max_size:
        reject('OBJECT_SIZE_INVALID')
    try:
        obj=json.loads(raw.decode('utf-8'), object_pairs_hook=unique_pairs)
    except (UnicodeError, json.JSONDecodeError):
        reject('OBJECT_JSON_INVALID')
    if type(obj) is not dict:
        reject('OBJECT_NOT_DICT')
    return obj

def validate_identity(repository, project, task, baseline):
    if (repository != REPOSITORY or project != PROJECT or task != TASK or
        type(baseline) is not str or not HEX40.fullmatch(baseline) or
        baseline != BASELINE_SHA):
        reject('SCOPE_OR_BASELINE_DRIFT')

def checkpoint_paths(project, task):
    if not all(type(x) is str and TOKEN.fullmatch(x) for x in (project,task)):
        reject('IDENTIFIER_UNSAFE')
    return (f'.adp/checkpoints/{project}/{task}/candidate.json',
            f'.adp/checkpoints/{project}/{task}/journal.jsonl')

def validate_candidate_bytes(candidate_bytes, journal_bytes, repository, project, task, baseline):
    """Validate all digests and public-boundary metadata; not an attestation."""
    validate_identity(repository,project,task,baseline)
    c=parse_object(candidate_bytes,MAX_CANDIDATE)
    expected={'schema','state','repository','baseline_sha','project_id','task_id',
              'journal_path','journal_sha256','journal_tip_sha256','checkpoint_sha256',
              'sequence','note','candidate_sha256'}
    if set(c)!=expected or c['schema']!=SCHEMA or c['state']!=EXPECTED_STATE:
        reject('CANDIDATE_SCHEMA_INVALID')
    if (c['repository'],c['project_id'],c['task_id'],c['baseline_sha'])!=(repository,project,task,baseline):
        reject('CANDIDATE_SCOPE_MISMATCH')
    _,jpath=checkpoint_paths(project,task)
    if c['journal_path']!=jpath:
        reject('CANDIDATE_JOURNAL_PATH_MISMATCH')
    if type(c['sequence']) is not int or c['sequence']!=1:
        reject('SEQUENCE_NOT_SINGLE_GENESIS')
    if type(journal_bytes) is not bytes or not journal_bytes or len(journal_bytes)>MAX_JOURNAL or not journal_bytes.endswith(b'\n'):
        reject('JOURNAL_INVALID_BYTES')
    for key in ('journal_sha256','journal_tip_sha256','checkpoint_sha256','candidate_sha256'):
        if type(c[key]) is not str or not HEX64.fullmatch(c[key]):
            reject('CANDIDATE_SHA_FORMAT')
    if digest(journal_bytes)!=c['journal_sha256']:
        reject('JOURNAL_DIGEST_MISMATCH')
    if digest(canonical({k:v for k,v in c.items() if k!='candidate_sha256'}))!=c['candidate_sha256']:
        reject('MANIFEST_DIGEST_MISMATCH')
    if c['note']!='NO_RESUME_NO_GATE_PROMOTION_NO_ISSUER_NO_ORDER':
        reject('AUTHORIZATION_BOUNDARY_DRIFT')
    entries=journal_bytes.splitlines()
    if len(entries)!=1:
        reject('EXPECTED_GENESIS_EVENT_ONLY')
    e=parse_object(entries[0],100_000)
    if set(e)!={'schema','sequence','event_id','at_utc','prev_sha256','checkpoint','checkpoint_sha256','entry_sha256'}:
        reject('JOURNAL_ENTRY_FIELDS_INVALID')
    if e['schema']!='adp-context-journal-v1' or type(e['sequence']) is not int or e['sequence']!=1:
        reject('JOURNAL_ENTRY_SEQUENCE_INVALID')
    if e['prev_sha256']!='0'*64 or e['event_id']!='CTX_A4_PUBLISH_GENESIS':
        reject('JOURNAL_GENESIS_MISMATCH')
    cp=e['checkpoint']
    def walk_strings(v):
        if isinstance(v,str): yield v
        elif isinstance(v,list):
            for item in v: yield from walk_strings(item)
        elif isinstance(v,dict):
            for key,value in v.items():
                yield key
                yield from walk_strings(value)
    if any(PRIVATE_PATTERN.search(v) for v in walk_strings(cp)):
        reject('SENSITIVE_CHECKPOINT_CONTENT')
    if type(cp) is not dict or (cp.get('repository'),cp.get('project_id'),cp.get('task_id'),cp.get('baseline_sha'))!=(repository,project,task,baseline):
        reject('CHECKPOINT_SCOPE_MISMATCH')
    if cp.get('head_sha')!=baseline or cp.get('policy_ref')!='ADP-GOV-AUTOMATION-001-v1.0':
        reject('CHECKPOINT_SOURCE_OR_POLICY_DRIFT')
    if cp.get('status')!='BLOCKED' or not REQUIRED_BLOCKERS.issubset(set(cp.get('blockers',[]))):
        reject('CHECKPOINT_AUTHORIZATION_BOUNDARY_DRIFT')
    if digest(canonical(cp))!=c['checkpoint_sha256'] or e['checkpoint_sha256']!=c['checkpoint_sha256']:
        reject('CHECKPOINT_DIGEST_MISMATCH')
    if digest(canonical({k:v for k,v in e.items() if k!='entry_sha256'}))!=c['journal_tip_sha256'] or e['entry_sha256']!=c['journal_tip_sha256']:
        reject('JOURNAL_TIP_DIGEST_MISMATCH')
    if cp.get('non_negotiables') is None or 'NO_ACCOUNT_ORDER' not in cp['non_negotiables'] or 'T_PLUS_ONE_PAUSED_MANUAL' not in cp['non_negotiables']:
        reject('TRADING_GUARDRAILS_MISSING')
    return c

def read_and_verify(root, repository=REPOSITORY, project=PROJECT, task=TASK, baseline=BASELINE_SHA):
    validate_identity(repository,project,task,baseline)
    root=Path(root)
    if root.is_symlink() or not root.is_dir():
        reject('ROOT_UNTRUSTED')
    candidate_rel,journal_rel=checkpoint_paths(project,task)
    for prefix in (root/'.adp',root/'.adp'/'checkpoints',root/'.adp'/'checkpoints'/project,root/'.adp'/'checkpoints'/project/task):
        if prefix.is_symlink() or not prefix.is_dir():
            reject('UNSAFE_DIRECTORY')
    cpath=root/candidate_rel
    jpath=root/journal_rel
    for p in (cpath,jpath):
        if p.is_symlink() or not p.is_file():
            reject('MISSING_OR_SYMLINK_FILE')
    c=validate_candidate_bytes(cpath.read_bytes(),jpath.read_bytes(),repository,project,task,baseline)
    # Demand the existing independent offline contracts also agree.
    from .canonical_checkpoint import read_candidate
    from .engine import verify_local_sources
    obj=read_candidate(root,repository=repository,baseline_sha=baseline,project_id=project,task_id=task)
    if obj!=c:
        reject('A4_CANDIDATE_MISMATCH')
    from .checkpoint_store import load
    entry=load(jpath)[-1]
    verify_local_sources(entry['checkpoint'],root)
    return {'state':'CANDIDATE_BYTES_VALID_NOT_REMOTE_ATTESTATION',
            'checkpoint_sha256':c['checkpoint_sha256'],
            'journal_tip_sha256':c['journal_tip_sha256'],
            'candidate_sha256':c['candidate_sha256'],
            'baseline_sha':baseline,'note':'NO_RESUME_NO_ISSUER_NO_TRADING'}

def main(argv=None):
    p=argparse.ArgumentParser(description='Strict offline canonical-publication integrity validator')
    p.add_argument('--self-check',action='store_true')
    p.add_argument('--repo-root',default='.')
    p.add_argument('--repository',default=REPOSITORY)
    p.add_argument('--baseline-sha',default=BASELINE_SHA)
    args=p.parse_args(argv)
    try:
        if args.self_check:
            print(json.dumps({'state':'OFFLINE_NO_WRITE_NO_RESUME_NO_ISSUER_NO_ORDER'},sort_keys=True));return 0
        out=read_and_verify(args.repo_root,repository=args.repository,baseline=args.baseline_sha)
        print(json.dumps(out,sort_keys=True));return 0
    except (PublicationError,ValueError,OSError) as e:
        print(json.dumps({'state':'BLOCKED_CANONICAL_PUBLICATION','reason':str(e)[:100]},sort_keys=True));return 2

if __name__=='__main__':
    raise SystemExit(main())
