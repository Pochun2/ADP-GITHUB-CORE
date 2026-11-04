"""Deterministic, offline, fail-closed context checkpoint and resume preview.

Every input is untrusted, including summaries, test results, and GitHub-shaped JSON.
No credentials, network, GitHub writes, approval, trading, or issuance capability.
"""
from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path
from typing import Any

SCHEMA = 'adp-context-v1'
SHA = re.compile(r'[0-9a-f]{40}\Z')
DIGEST = re.compile(r'[0-9a-f]{64}\Z')
ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}\Z')
REPO = re.compile(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z')
STATES = {'PAUSED','IN_PROGRESS','BLOCKED','READY_FOR_REVIEW','DONE_REPORTED'}
LEVELS = {'EVIDENCED','REPORTED','INFERRED','UNKNOWN'}
MANDATORY = {'schema','project_id','task_id','repository','baseline_sha','head_sha','policy_ref',
             'status','completed_steps','pending_steps','blockers','evidence_refs','decision_refs',
             'non_negotiables','last_verified_at_utc','next_action','context_sources'}
SECRET = re.compile(r'(?i)(?:gh[pousr]_[a-z0-9]{10,}|github_pat_[a-z0-9_]{10,}|sk-[a-z0-9_-]{12,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|(?:(?:password|token|secret|private_key|api_key)\s*[:=]\s*[^\s,;]+))')
MAX_BYTES = 96_000

class ContextError(ValueError):
    pass

def fail(reason: str):
    raise ContextError(reason)

def _string(v: Any, limit=4000) -> bool:
    return type(v) is str and 0 < len(v) <= limit and v.strip() == v and '\x00' not in v and not SECRET.search(v)

def _list(v: Any, limit=64) -> bool:
    return type(v) is list and 0 <= len(v) <= limit and all(_string(x, 1500) for x in v) and len(v)==len(set(v))

def _ref(v: Any) -> bool:
    # Ref is an immutable or verifiable locator, not a claim of authenticity.
    if type(v) is not dict or set(v) != {'locator','sha256','claim_level'}:
        return False
    return (_string(v['locator'],300) and not v['locator'].startswith(('/', '\\'))
            and '..' not in v['locator'].split('/') and '\\' not in v['locator']
            and bool(DIGEST.fullmatch(v['sha256'])) and v['claim_level'] in LEVELS)

def validate_checkpoint(v: Any) -> dict:
    if type(v) is not dict or set(v) != MANDATORY:
        fail('CHECKPOINT_FIELDS')
    if v['schema'] != SCHEMA or not ID.fullmatch(str(v['project_id'])) or not ID.fullmatch(str(v['task_id'])):
        fail('CHECKPOINT_ID')
    if not REPO.fullmatch(str(v['repository'])):
        fail('CHECKPOINT_REPOSITORY')
    for key in ('baseline_sha','head_sha'):
        if type(v[key]) is not str or not SHA.fullmatch(v[key]):
            fail('CHECKPOINT_SHA')
    if not _string(v['policy_ref'],300) or v['status'] not in STATES:
        fail('CHECKPOINT_POLICY_OR_STATUS')
    for key in ('completed_steps','pending_steps','blockers','non_negotiables'):
        if not _list(v[key]):
            fail('CHECKPOINT_LIST_' + key.upper())
    if not v['pending_steps'] and v['status'] not in {'DONE_REPORTED','READY_FOR_REVIEW'}:
        fail('CHECKPOINT_PENDING_EMPTY')
    if set(v['completed_steps']) & set(v['pending_steps']):
        fail('CHECKPOINT_STEP_CONFLICT')
    if not _string(v['next_action'],1000):
        fail('CHECKPOINT_NEXT_ACTION')
    if v['last_verified_at_utc'] is not None:
        # No wall clock in offline resolver, only syntax check; source freshness requires live caller.
        if type(v['last_verified_at_utc']) is not str or not re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?Z',v['last_verified_at_utc']):
            fail('CHECKPOINT_TIME')
    for key in ('evidence_refs','decision_refs','context_sources'):
        a=v[key]
        if type(a) is not list or len(a)>64 or any(not _ref(x) for x in a):
            fail('CHECKPOINT_REFS_' + key.upper())
        if len({x['locator'] for x in a})!=len(a):
            fail('DUPLICATE_REFERENCE')
    if not v['context_sources']:
        fail('MISSING_CONTEXT_SOURCES')
    return v

def canonical(v: Any) -> bytes:
    return (json.dumps(v, sort_keys=True, ensure_ascii=False, separators=(',',':'))+'\n').encode('utf-8')

def load_json(path: str|Path) -> dict:
    p=Path(path)
    if p.is_symlink() or not p.is_file() or p.stat().st_size>MAX_BYTES:
        fail('INVALID_FILE')
    try:
        raw=p.read_bytes()
        # reject duplicate keys, including nested fields
        def pairs(x):
            o={}
            for k,val in x:
                if k in o: fail('DUPLICATE_JSON_KEY')
                o[k]=val
            return o
        obj=json.loads(raw.decode('utf-8'),object_pairs_hook=pairs)
    except (UnicodeError,ValueError, OSError):
        fail('INVALID_JSON')
    if SECRET.search(raw.decode('utf-8')):
        fail('SECRET_IN_FILE')
    return obj

def verify_local_sources(cp:dict, root: str|Path) -> dict:
    """Checks file bytes against pinned hashes; proves consistency, NOT source authority.

    Only references in context_sources are permitted for this local check. Do not
    use this to validate remote GitHub evidence, live decisions or approvals.
    """
    validate_checkpoint(cp)
    base=Path(root).resolve(strict=True)
    if not base.is_dir(): fail('SOURCE_ROOT_NOT_DIRECTORY')
    for ref in cp['context_sources']:
        rel=ref['locator']
        p=base/rel
        try:
            if p.is_symlink() or not p.is_file() or p.stat().st_size>MAX_BYTES:
                fail('SOURCE_UNAVAILABLE')
            resolved=p.resolve(strict=True)
            if not resolved.is_relative_to(base): fail('SOURCE_OUTSIDE_ROOT')
            raw=p.read_bytes()
        except (OSError, ValueError):
            fail('SOURCE_UNAVAILABLE')
        if hashlib.sha256(raw).hexdigest()!=ref['sha256']:
            fail('SOURCE_DIGEST_MISMATCH')
    return {'state':'LOCAL_SOURCE_HASHES_MATCH_NOT_AUTHENTICATED', 'checked':len(cp['context_sources'])}

def checkpoint_digest(v: dict) -> str:
    validate_checkpoint(v)
    return hashlib.sha256(canonical(v)).hexdigest()

def validate_decisions(items: Any) -> list:
    if type(items) is not list or len(items)>100:
        fail('DECISION_INDEX_INVALID')
    ids=set()
    for e in items:
        if type(e) is not dict or set(e)!={'id','status','supersedes','reason','source'}:
            fail('DECISION_FIELDS')
        if not ID.fullmatch(str(e['id'])) or e['id'] in ids:
            fail('DECISION_ID')
        ids.add(e['id'])
        if e['status'] not in {'PROPOSED','APPROVED','SUPERSEDED','REJECTED'} or not _string(e['reason'],1500) or not _ref(e['source']):
            fail('DECISION_STATUS_OR_SOURCE')
        if e['supersedes'] is not None and (not ID.fullmatch(str(e['supersedes'])) or e['supersedes']==e['id']):
            fail('DECISION_SUPERSEDES')
    for e in items:
        if e['supersedes'] is not None and e['supersedes'] not in ids:
            fail('MISSING_SUPERSEDED_DECISION')
        if e['status']=='APPROVED' and e['source']['claim_level']!='EVIDENCED':
            fail('APPROVAL_WITHOUT_EVIDENCE')
    for e in items:
        if e['status']=='APPROVED' and e['supersedes']:
            prior=next(x for x in items if x['id']==e['supersedes'])
            if prior['status']!='SUPERSEDED':
                fail('DECISION_CONFLICT')
    # cycle detection
    edges={e['id']:e['supersedes'] for e in items}
    for key in edges:
        seen=set()
        p=key
        while p:
            if p in seen: fail('DECISION_CYCLE')
            seen.add(p);p=edges[p]
    return items

def validate_remote_snapshot(v: Any) -> dict:
    """Caller-supplied mock observation ONLY. Never labeled authenticated."""
    required={'repository','main_sha','head_sha','pr_state','ci_state','policy_ref','source_mode'}
    if type(v) is not dict or set(v)!=required or v['source_mode']!='UNTRUSTED_OFFLINE_FIXTURE':
        fail('REMOTE_NOT_OFFLINE_FIXTURE')
    if not REPO.fullmatch(str(v['repository'])) or any(type(v[k]) is not str or not SHA.fullmatch(v[k]) for k in ('main_sha','head_sha')):
        fail('REMOTE_INVALID_SHA')
    if v['pr_state'] not in {'OPEN','DRAFT','MERGED','CLOSED','UNKNOWN'} or v['ci_state'] not in {'SUCCESS','FAILURE','PENDING','UNKNOWN'} or not _string(v['policy_ref'],300):
        fail('REMOTE_INVALID_STATUS')
    return v

def resume_preview(cp:dict,remote:dict,decisions:list) ->dict:
    """Fail closed on drift/claims; never issues authorization to act."""
    validate_checkpoint(cp); validate_remote_snapshot(remote); validate_decisions(decisions)
    reasons=[]
    if cp['repository']!=remote['repository']: reasons.append('REPOSITORY_MISMATCH')
    if cp['baseline_sha']!=remote['main_sha']: reasons.append('BASELINE_DRIFT')
    if cp['head_sha']!=remote['head_sha']: reasons.append('HEAD_DRIFT')
    if cp['policy_ref']!=remote['policy_ref']: reasons.append('POLICY_DRIFT')
    if cp['blockers']: reasons.append('UNRESOLVED_BLOCKERS')
    if cp['status'] in {'BLOCKED','DONE_REPORTED'}: reasons.append('STATE_NOT_RESUMABLE')
    if cp['status']=='READY_FOR_REVIEW' and remote['ci_state']!='SUCCESS': reasons.append('CI_NOT_SUCCESS')
    if cp['status']=='READY_FOR_REVIEW' and remote['pr_state'] not in {'OPEN','DRAFT'}: reasons.append('PR_STATUS_MISMATCH')
    missing=[x['locator'] for x in cp['decision_refs'] if x['locator'] not in {y['source']['locator'] for y in decisions}]
    if missing: reasons.append('DECISION_SOURCE_MISSING')
    if any(x['source']['claim_level']!='EVIDENCED' for x in decisions if x['status']=='APPROVED'):
        reasons.append('UNVERIFIED_DECISION')
    if not cp['evidence_refs']: reasons.append('NO_EVIDENCE_REFS')
    if any(x['claim_level']!='EVIDENCED' for x in cp['evidence_refs']): reasons.append('NON_AUTHORITATIVE_EVIDENCE')
    return {'state':'BLOCKED_RECONCILIATION' if reasons else 'READY_FOR_HUMAN_OR_EXTERNAL_POLICY_REVIEW',
            'reasons':sorted(set(reasons)), 'checkpoint_sha256':checkpoint_digest(cp),
            'next_action':cp['next_action'] if not reasons else 'Reconcile authoritative remote state and policy before any write',
            'note':'OFFLINE_UNTRUSTED_FIXTURE_NO_AUTHORIZATION_NO_GITHUB_WRITE_NO_ISSUER_GATE_A_BLOCKED'}

def retrieve(cp:dict,terms:list[str],limit:int=8)->list[dict]:
    validate_checkpoint(cp)
    if type(terms) is not list or not terms or len(terms)>16 or any(not _string(s,100) for s in terms):
        fail('SEARCH_TERMS_INVALID')
    if type(limit) is not int or not 1<=limit<=16:fail('SEARCH_LIMIT')
    scored=[]
    for r in cp['context_sources']+cp['decision_refs']+cp['evidence_refs']:
        label=r['locator'].lower()
        score=sum(1 for term in terms if term.lower() in label)
        if score:scored.append((score,r))
    scored.sort(key=lambda x:(-x[0],x[1]['locator']))
    seen=set();out=[]
    for _,ref in scored:
        if ref['locator'] not in seen:
            out.append(ref);seen.add(ref['locator'])
        if len(out)==limit: break
    return out

def compact(cp:dict,decisions:list)->str:
    """Lossless for essential fields, deterministic index rather than probabilistic summary."""
    validate_checkpoint(cp);validate_decisions(decisions)
    def ls(a):return '\n'.join('- '+x for x in a)
    d='\n'.join(f"- {x['id']} [{x['status']}] {x['reason']} ({x['source']['locator']})" for x in sorted(decisions,key=lambda x:x['id'])) or '- none'
    refs='\n'.join(f"- {x['locator']} [{x['claim_level']}] sha256={x['sha256']}" for x in cp['context_sources'])
    return (f"# ADP CONTEXT CAPSULE (UNVERIFIED INDEX, NOT APPROVAL)\n\n"
      f"Project: {cp['project_id']} | Task: {cp['task_id']} | State: {cp['status']}\n"
      f"Repo: {cp['repository']}\nBase SHA: {cp['baseline_sha']}\nHead SHA: {cp['head_sha']}\n"
      f"Policy: {cp['policy_ref']}\nCheckpoint digest: {checkpoint_digest(cp)}\n"
      f"Last verified (CLAIM ONLY): {cp['last_verified_at_utc'] or 'UNKNOWN'}\n\n"
      f"## NON-NEGOTIABLES\n{ls(cp['non_negotiables'])}\n\n"
      f"## Completed (UNVERIFIED CLAIMS)\n{ls(cp['completed_steps'])}\n\n"
      f"## Pending\n{ls(cp['pending_steps'])}\n\n## Blockers\n{ls(cp['blockers'])}\n\n"
      f"## Decisions\n{d}\n\n## Source index\n{refs}\n\n"
      f"## Next action\n{cp['next_action']}\n\n"
      f"STOP: check live GitHub and protected policy before acting. No Gate promotion, issuer, account or order authority.\n")
