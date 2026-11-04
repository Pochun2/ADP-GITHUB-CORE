"""CTX-A3 candidate offline durable journal, exclusive lease, conservative restart.

Local persisted state is NOT canonical GitHub state and never authorizes an
external write. See docs/ADP-CONTEXT-001-A3.md.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import secrets
from datetime import datetime, timezone
from contextlib import contextmanager

from .engine import canonical, checkpoint_digest, validate_checkpoint
from .github_evidence import reconcile_checkpoint

SCHEMA = 'adp-context-journal-v1'
HEX64 = re.compile(r'[0-9a-f]{64}\Z')
TOKEN = re.compile(r'[A-Za-z0-9_.:-]{1,96}\Z')
MAX_JOURNAL = 5_000_000
MAX_ENTRY = 100_000

class StoreError(ValueError):
    pass

def reject(code):
    raise StoreError(code)

def utc(value):
    if type(value) is not str or not value.endswith('Z'):
        reject('INVALID_UTC')
    try:
        d = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        reject('INVALID_UTC')
    if d.utcoffset().total_seconds() != 0:
        reject('INVALID_UTC')
    return d

def entry_digest(e):
    return hashlib.sha256(canonical({k:v for k,v in e.items() if k != 'entry_sha256'})).hexdigest()

def _file(path):
    p = Path(path)
    if p.is_symlink() or not p.is_file() or p.stat().st_size > MAX_JOURNAL:
        reject('JOURNAL_UNAVAILABLE')
    return p

def _pairs(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            reject('DUPLICATE_JSON_KEY')
        out[k] = v
    return out

def load(path):
    """Verify entire append-only chain. Missing/truncated/tampered => reject."""
    p = _file(path)
    raw = p.read_bytes()
    if not raw or not raw.endswith(b'\n'):
        reject('INCOMPLETE_JOURNAL')
    lines = raw.splitlines()
    if len(lines) > 10000:
        reject('JOURNAL_TOO_LONG')
    entries = []
    prev = '0' * 64
    last_time = None
    ids = set()
    try:
        for number, line in enumerate(lines, 1):
            if len(line) > MAX_ENTRY:
                reject('ENTRY_TOO_LARGE')
            e = json.loads(line.decode('utf-8'), object_pairs_hook=_pairs)
            if type(e) is not dict or set(e) != {'schema','sequence','event_id','at_utc','prev_sha256','checkpoint','checkpoint_sha256','entry_sha256'}:
                reject('INVALID_ENTRY_FIELDS')
            if e['schema'] != SCHEMA or type(e['sequence']) is not int or e['sequence'] != number:
                reject('SEQUENCE_MISMATCH')
            if type(e['event_id']) is not str or not TOKEN.fullmatch(e['event_id']) or e['event_id'] in ids:
                reject('EVENT_ID_INVALID_OR_REPLAY')
            ids.add(e['event_id'])
            if e['prev_sha256'] != prev or type(e['prev_sha256']) is not str:
                reject('HASH_CHAIN_BROKEN')
            stamp = utc(e['at_utc'])
            if last_time is not None and stamp < last_time:
                reject('NON_MONOTONIC_TIME')
            last_time = stamp
            if type(e['checkpoint']) is not dict:
                reject('INVALID_CHECKPOINT')
            digest = checkpoint_digest(e['checkpoint'])
            if e['checkpoint_sha256'] != digest or type(e['entry_sha256']) is not str or not HEX64.fullmatch(e['entry_sha256']) or e['entry_sha256'] != entry_digest(e):
                reject('ENTRY_DIGEST_MISMATCH')
            if entries:
                previous = entries[-1]['checkpoint']
                new = e['checkpoint']
                for key in ('project_id','task_id','repository','policy_ref'):
                    if new[key] != previous[key]:
                        reject('TASK_IDENTITY_DRIFT')
            prev = e['entry_sha256']
            entries.append(e)
    except (UnicodeError, json.JSONDecodeError):
        reject('INVALID_JOURNAL_JSON')
    return entries

@contextmanager
def exclusive_lock(journal_path):
    """Atomic mkdir lock; stale locks must be resolved OUTSIDE automation.

    No lock stealing; no trust in wall-clock TTL; removes only own lock.
    """
    p = Path(str(journal_path) + '.lock')
    if p.is_symlink():
        reject('LOCK_UNTRUSTED')
    try:
        p.mkdir(mode=0o700)
    except FileExistsError:
        reject('LOCK_HELD_OR_STALE')
    except OSError:
        reject('LOCK_UNAVAILABLE')
    try:
        yield
    finally:
        try:
            p.rmdir()
        except OSError:
            reject('LOCK_RELEASE_FAILED')

def _append_file(p, e):
    b = canonical(e)
    if len(b) > MAX_ENTRY:
        reject('ENTRY_TOO_LARGE')
    with open(p, 'ab', buffering=0) as f:
        f.write(b)
        os.fsync(f.fileno())

def append(path, checkpoint, *, event_id, at_utc, expected_last_sha256=None):
    """Local candidate state only; no GitHub publication, issuance or approval.

    CAS expected_last_sha256 is REQUIRED for updates; genesis requires None.
    """
    validate_checkpoint(checkpoint)
    if type(event_id) is not str or not TOKEN.fullmatch(event_id):
        reject('EVENT_ID_INVALID')
    utc(at_utc)
    p = Path(path)
    if p.is_symlink() or not p.parent.is_dir() or p.parent.is_symlink():
        reject('UNTRUSTED_JOURNAL_PATH')
    with exclusive_lock(p):
        if p.exists():
            previous = load(p)
            tail = previous[-1]
            if type(expected_last_sha256) is not str or not HEX64.fullmatch(expected_last_sha256) or expected_last_sha256 != tail['entry_sha256']:
                reject('CAS_MISMATCH')
            if any(x['event_id'] == event_id for x in previous):
                reject('EVENT_REPLAY')
            if utc(at_utc) < utc(tail['at_utc']):
                reject('NON_MONOTONIC_TIME')
            old = tail['checkpoint']
            for k in ('project_id','task_id','repository','policy_ref'):
                if checkpoint[k] != old[k]:
                    reject('TASK_IDENTITY_DRIFT')
            sequence = len(previous) + 1
            prior_sha = tail['entry_sha256']
        else:
            if expected_last_sha256 is not None:
                reject('CAS_MISMATCH')
            sequence = 1
            prior_sha = '0' * 64
        e = {'schema':SCHEMA,'sequence':sequence,'event_id':event_id,'at_utc':at_utc,
             'prev_sha256':prior_sha,'checkpoint':checkpoint,
             'checkpoint_sha256':checkpoint_digest(checkpoint)}
        e['entry_sha256'] = entry_digest(e)
        if sequence == 1:
            # exclusive creation is stronger than normal append but crash may
            # leave empty file: fail closed and require manual recovery.
            with open(p, 'xb', buffering=0) as f:
                f.write(canonical(e))
                os.fsync(f.fileno())
        else:
            _append_file(p, e)
        # Local state cannot guarantee durability across power loss/network FS.
        return {'state':'LOCAL_CANDIDATE_PERSISTED_NOT_PUBLISHED',
                'sequence':sequence,'entry_sha256':e['entry_sha256'],
                'note':'LOCAL_ONLY_NOT_GITHUB_AUTHORITY'}

def resume_gate(path, observation, *, expected_policy_ruleset_id, now_utc, max_age_seconds=300):
    """Require replay-checked journal and fresh A2 observation; no grants."""
    entries = load(path)
    cp = entries[-1]['checkpoint']
    result = reconcile_checkpoint(cp, observation,
        expected_policy_ruleset_id=expected_policy_ruleset_id,
        max_age_seconds=max_age_seconds, now_utc=now_utc)
    return {'state': 'BLOCKED_RECONCILIATION' if result['state'] == 'BLOCKED_RECONCILIATION' else 'REVIEW_REQUIRED_NOT_AUTHORIZED',
            'reasons':result['reasons'],'sequence':len(entries),
            'checkpoint_sha256':entries[-1]['checkpoint_sha256'],
            'journal_tip_sha256':entries[-1]['entry_sha256'],
            'observation_sha256':result['observation_sha256'],
            'note':'LOCAL_JOURNAL_AND_GITHUB_OBSERVATION_NOT_AUTHORIZATION'}

def main(argv=None):
    import argparse
    p=argparse.ArgumentParser(description='CTX-A3 local candidate journal: offline and no authorization')
    p.add_argument('--self-check', action='store_true')
    p.add_argument('--verify-journal')
    args=p.parse_args(argv)
    if args.self_check:
        print(json.dumps({'state':'OFFLINE_ONLY','note':'NO_GITHUB_WRITE_NO_AUTONOMOUS_LEASE_STEAL_NO_ISSUER_KEY_GATE_A_BLOCKED'},sort_keys=True))
        return 0
    if not args.verify_journal:
        print(json.dumps({'state':'BLOCKED','reason':'SELF_CHECK_OR_VERIFY_REQUIRED'},sort_keys=True))
        return 2
    try:
        events=load(args.verify_journal)
        print(json.dumps({'state':'LOCAL_CHAIN_VERIFIED_NOT_ATTESTED','sequence':len(events),'journal_tip_sha256':events[-1]['entry_sha256']},sort_keys=True))
        return 0
    except (StoreError, OSError, ValueError):
        print(json.dumps({'state':'BLOCKED','reason':'JOURNAL_VALIDATION_FAILED'},sort_keys=True))
        return 2

if __name__=='__main__':
    raise SystemExit(main())
