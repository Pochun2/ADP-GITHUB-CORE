"""ADP-CONTEXT-001-A2: bounded GitHub REST read-only observation and drift report.

The caller supplies a read-only GET adapter; the default anonymous HTTPS adapter
uses NO credentials. JSON over public HTTPS is not independent attestation.
Neither positive result nor CI success authorizes a GitHub write, merge or issuance.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Protocol
import json
import re
import urllib.error
import urllib.request

from .engine import validate_checkpoint, canonical

SHA = re.compile(r'[0-9a-f]{40}\Z')
REPO = re.compile(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z')
CHECK = re.compile(r'[A-Za-z0-9_.-]{1,128}\Z')
MAX_BYTES = 1024 * 1024
MAX_CHECKS = 100
DEFAULT_APP = 15368  # GitHub Actions check run integration; not Trusted Issuer.


class EvidenceError(ValueError):
    pass


def reject(reason: str):
    raise EvidenceError(reason)


def _str(v: Any) -> bool:
    return type(v) is str and len(v) > 0


def _positive(v: Any) -> bool:
    return type(v) is int and v > 0


def _sha(v: Any) -> bool:
    return type(v) is str and bool(SHA.fullmatch(v))


def _keys(v, required):
    if type(v) is not dict or not set(required).issubset(v):
        reject('MISSING_OR_INVALID_FIELDS')


def _json_object(data: bytes):
    if type(data) is not bytes or len(data) > MAX_BYTES:
        reject('RESPONSE_TOO_LARGE_OR_INVALID')
    try:
        def no_duplicates(pairs):
            result = {}
            for k, v in pairs:
                if k in result:
                    reject('DUPLICATE_JSON_KEY')
                result[k] = v
            return result
        parsed = json.loads(data.decode('utf-8'), object_pairs_hook=no_duplicates)
    except (UnicodeError, ValueError):
        reject('RESPONSE_JSON_INVALID')
    if type(parsed) is not dict:
        reject('RESPONSE_NOT_OBJECT')
    return parsed


class ReadOnlySource(Protocol):
    def get(self, endpoint: str) -> dict: ...


class AnonymousGitHubREST:
    """Hardcoded GitHub API host, no bearer token, redirects or stateful writes.

    Read-only public repositories only. No token/PAT/private repo support here.
    A GitHub App-authenticated collector must be separate and independently
    reviewed; never pass credentials to model-generated code or this adapter.
    """
    def get(self, endpoint: str) -> dict:
        if type(endpoint) is not str or not endpoint.startswith('/repos/') or '?' in endpoint and not endpoint.endswith('?per_page=100'):
            reject('DISALLOWED_ENDPOINT')
        if any(x in endpoint for x in ('..', '\\', '#', '%', '//')):
            reject('DISALLOWED_ENDPOINT')
        allowed = (
            re.fullmatch(r'/repos/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', endpoint)
            or re.fullmatch(r'/repos/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/branches/main', endpoint)
            or re.fullmatch(r'/repos/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/pulls/[1-9][0-9]*', endpoint)
            or re.fullmatch(r'/repos/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/rulesets/[1-9][0-9]*', endpoint)
            or re.fullmatch(r'/repos/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/commits/[0-9a-f]{40}/check-runs\?per_page=100', endpoint)
        )
        if not allowed:
            reject('DISALLOWED_ENDPOINT')
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None
        opener = urllib.request.build_opener(NoRedirect)
        req = urllib.request.Request('https://api.github.com' + endpoint, headers={
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28',
            'User-Agent': 'ADP-CTX-A2-ReadOnly/0.1',
        }, method='GET')
        try:
            with opener.open(req, timeout=12) as r:
                if r.status != 200:
                    reject('REMOTE_HTTP_FAILURE')
                raw = r.read(MAX_BYTES + 1)
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, TimeoutError):
            reject('REMOTE_UNAVAILABLE')
        return _json_object(raw)


@dataclass(frozen=True)
class Target:
    repository: str
    pr_number: int
    ruleset_id: int
    required_app_id: int = DEFAULT_APP

    def __post_init__(self):
        if (type(self.repository) is not str or not REPO.fullmatch(self.repository)
                or not _positive(self.pr_number) or not _positive(self.ruleset_id)
                or not _positive(self.required_app_id)):
            reject('INVALID_TARGET')


def _remote_get(source: ReadOnlySource, path: str) -> dict:
    try:
        response = source.get(path)
    except EvidenceError:
        raise
    except Exception:
        reject('REMOTE_UNAVAILABLE')
    if type(response) is not dict:
        reject('INVALID_REMOTE_RESPONSE')
    return response


def _verified_checks(data: dict, head: str, required: list[tuple[str, int]]):
    _keys(data, ('total_count', 'check_runs'))
    checks = data['check_runs']
    if (type(data['total_count']) is not int or not 0 <= data['total_count'] <= MAX_CHECKS
            or type(checks) is not list or len(checks) != data['total_count']):
        reject('PAGINATED_OR_INCOMPLETE_CHECK_RUNS')
    names = set()
    ids = set()
    statuses = {}
    for c in checks:
        _keys(c, ('id', 'name', 'head_sha', 'app', 'status', 'conclusion'))
        if (not _positive(c['id']) or c['id'] in ids or not _str(c['name'])
                or type(c['app']) is not dict or not _positive(c['app'].get('id'))
                or not _sha(c['head_sha']) or c['head_sha'] != head):
            reject('INVALID_OR_DUPLICATE_CHECK_RUN')
        ids.add(c['id'])
        pair = (c['name'], c['app']['id'])
        if pair in names:
            reject('AMBIGUOUS_DUPLICATE_CHECK')
        names.add(pair)
        statuses[pair] = (c['status'], c['conclusion'])
    missing = [name for name, app in required if (name,app) not in statuses]
    if missing:
        reject('REQUIRED_CHECK_MISSING')
    failed = [name for name, app in required if statuses[(name,app)] != ('completed', 'success')]
    return {'required_count': len(required), 'observed_count': len(checks),
            'required_success_count': len(required) - len(failed),
            'required_all_success': not bool(failed),
            'required_failed_or_pending': sorted(failed)}


def observe(source: ReadOnlySource, target: Target, *, observed_at_utc: str | None = None) -> dict:
    """Read exact REST resources and return minimal sanitized observation.

    No supplied client response is assumed cryptographically authenticated.
    Caller must separately ensure the source adapter's origin and isolation.
    """
    prefix = '/repos/' + target.repository
    repo = _remote_get(source, prefix)
    _keys(repo, ('full_name', 'private', 'default_branch'))
    if (repo['full_name'] != target.repository or repo['private'] is not False or repo['default_branch'] != 'main'):
        reject('REPOSITORY_IDENTITY_OR_VISIBILITY')
    branch = _remote_get(source, prefix + '/branches/main')
    _keys(branch, ('commit',))
    if type(branch['commit']) is not dict or not _sha(branch['commit'].get('sha')):
        reject('INVALID_MAIN_SHA')
    base = branch['commit']['sha']
    pr = _remote_get(source, prefix + '/pulls/' + str(target.pr_number))
    _keys(pr, ('number', 'state', 'draft', 'merged', 'head', 'base'))
    if (pr['number'] != target.pr_number or type(pr['draft']) is not bool or type(pr['merged']) is not bool
            or pr['state'] not in ('open','closed') or type(pr['head']) is not dict or type(pr['base']) is not dict):
        reject('INVALID_PR')
    head = pr['head'].get('sha')
    if not _sha(head) or not _sha(pr['base'].get('sha')):
        reject('INVALID_PR_SHA')
    base_repo = pr['base'].get('repo')
    if type(base_repo) is not dict or base_repo.get('full_name') != target.repository or pr['base'].get('ref') != 'main':
        reject('PR_BASE_REPOSITORY_MISMATCH')
    if pr['state'] == 'open' and pr['base']['sha'] != base:
        reject('PR_BASE_DRIFT')
    if pr['state'] == 'open' and pr['merged']:
        reject('INVALID_PR_STATE')
    if pr['state'] == 'closed' and pr['draft']:
        reject('INVALID_PR_STATE')
    policy = _remote_get(source, prefix + '/rulesets/' + str(target.ruleset_id))
    _keys(policy, ('id','enforcement','rules'))
    if policy['id'] != target.ruleset_id or policy['enforcement'] != 'active' or type(policy['rules']) is not list:
        reject('RULESET_MISMATCH_OR_INACTIVE')
    required_blocks = [x for x in policy['rules'] if type(x) is dict and x.get('type') == 'required_status_checks']
    if len(required_blocks) != 1:
        reject('REQUIRED_CHECK_RULE_MISSING_OR_DUPLICATED')
    params = required_blocks[0].get('parameters')
    if (type(params) is not dict or params.get('strict_required_status_checks_policy') is not True
            or type(params.get('required_status_checks')) is not list):
        reject('REQUIRED_CHECK_POLICY_INVALID')
    required = []
    for c in params['required_status_checks']:
        if type(c) is not dict or set(c) != {'context','integration_id'} or not CHECK.fullmatch(str(c['context'])):
            reject('INVALID_REQUIRED_CHECK')
        if c['integration_id'] != target.required_app_id or type(c['integration_id']) is not int:
            reject('UNEXPECTED_CHECK_INTEGRATION')
        required.append((c['context'], c['integration_id']))
    if not required or len(required) != len(set(required)):
        reject('DUPLICATE_OR_MISSING_REQUIRED_CHECKS')
    runs = _remote_get(source, prefix + '/commits/' + head + '/check-runs?per_page=100')
    check_info = _verified_checks(runs, head, required)
    if observed_at_utc is None:
        observed_at_utc = datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')
    try:
        timestamp = datetime.fromisoformat(observed_at_utc.replace('Z','+00:00'))
        if not observed_at_utc.endswith('Z') or timestamp.utcoffset().total_seconds() != 0:
            reject('INVALID_OBSERVATION_TIME')
    except (TypeError, ValueError, AttributeError):
        reject('INVALID_OBSERVATION_TIME')
    result = {'schema':'adp-github-observation-v1', 'source_mode':'GITHUB_API_READ_OBSERVED_NOT_ATTESTED',
              'repository':target.repository,'pr_number':target.pr_number,'main_sha':base,
              'head_sha':head,'pr_base_sha':pr['base']['sha'],
              'pr_state':'MERGED' if pr['merged'] else 'DRAFT' if pr['draft'] else pr['state'].upper(),
              'policy_ruleset_id':target.ruleset_id,
              'required_check_contexts':sorted(name for name,_ in required),
              'ci_state':'SUCCESS' if check_info['required_all_success'] else 'INCOMPLETE',
              'required_check_count':check_info['required_count'],
              'required_success_count':check_info['required_success_count'],
              'required_failed_or_pending':check_info['required_failed_or_pending'],
              'observed_at_utc':observed_at_utc}
    result['observation_sha256']=sha256(canonical(result)).hexdigest()
    return result


def reconcile_checkpoint(cp: dict, observation: dict, *, expected_policy_ruleset_id: int,
                         max_age_seconds: int = 300, now_utc: str | None = None) -> dict:
    """Compare checkpoint with previously collected observation; never grant resume.

    Consistency and freshness are NOT proof of the origin of an injected dict.
    """
    validate_checkpoint(cp)
    required = {'schema','source_mode','repository','pr_number','main_sha','head_sha','pr_base_sha',
                'pr_state','policy_ruleset_id','required_check_contexts','ci_state',
                'required_check_count','required_success_count','required_failed_or_pending',
                'observed_at_utc','observation_sha256'}
    if type(observation) is not dict or set(observation) != required:
        reject('OBSERVATION_FIELDS_INVALID')
    if observation['schema'] != 'adp-github-observation-v1' or observation['source_mode'] != 'GITHUB_API_READ_OBSERVED_NOT_ATTESTED':
        reject('OBSERVATION_SCHEMA_INVALID')
    body={k:v for k,v in observation.items() if k!='observation_sha256'}
    if observation['observation_sha256'] != sha256(canonical(body)).hexdigest():
        reject('OBSERVATION_DIGEST_MISMATCH')
    if not _positive(expected_policy_ruleset_id) or type(max_age_seconds) is not int or not 0 < max_age_seconds <= 3600:
        reject('RECONCILIATION_ARGS_INVALID')
    if now_utc is None:
        now_utc = datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')
    try:
        obs_time=datetime.fromisoformat(observation['observed_at_utc'].replace('Z','+00:00'))
        now=datetime.fromisoformat(now_utc.replace('Z','+00:00'))
        if (not observation['observed_at_utc'].endswith('Z') or not now_utc.endswith('Z')
                or obs_time.utcoffset().total_seconds()!=0 or now.utcoffset().total_seconds()!=0):
            reject('INVALID_TIME')
    except (ValueError, TypeError, AttributeError):
        reject('INVALID_TIME')
    reasons=[]
    if not 0 <= (now - obs_time).total_seconds() <= max_age_seconds:
        reasons.append('OBSERVATION_STALE_OR_FUTURE')
    if cp['repository'] != observation['repository']: reasons.append('REPOSITORY_MISMATCH')
    if cp['baseline_sha'] != observation['main_sha']: reasons.append('BASELINE_DRIFT')
    if cp['head_sha'] != observation['head_sha']: reasons.append('HEAD_DRIFT')
    # Existing A1 policy_ref is a separately approved policy ID; do not substitute Ruleset ID by guesswork.
    if observation['policy_ruleset_id'] != expected_policy_ruleset_id:
        reasons.append('RULESET_ID_MISMATCH')
    if observation['ci_state'] != 'SUCCESS':
        reasons.append('REQUIRED_CI_NOT_SUCCESS')
    if observation['pr_state'] not in ('DRAFT', 'OPEN'):
        reasons.append('PR_NOT_OPEN')
    if cp['blockers'] or cp['status'] in ('BLOCKED','DONE_REPORTED'):
        reasons.append('CHECKPOINT_BLOCKED')
    if not cp['evidence_refs'] or any(x['claim_level'] != 'EVIDENCED' for x in cp['evidence_refs']):
        reasons.append('CHECKPOINT_EVIDENCE_NOT_AUTHORITATIVE')
    return {'state':'BLOCKED_RECONCILIATION' if reasons else 'CONSISTENT_OBSERVATION_NOT_AUTHORIZED',
            'reasons':sorted(set(reasons)), 'checkpoint_sha256':sha256(canonical(cp)).hexdigest(),
            'observation_sha256':observation['observation_sha256'],
            'note':'NO_RESUME_AUTHORITY_NO_GITHUB_WRITE_NO_ISSUER_KEY_GATE_A_BLOCKED'}


def main(argv=None):
    import argparse
    p=argparse.ArgumentParser(description='ADP CTX-A2 anonymous public read-only GitHub observation')
    p.add_argument('--self-check',action='store_true')
    p.add_argument('--repository')
    p.add_argument('--pr',type=int)
    p.add_argument('--ruleset',type=int)
    p.add_argument('--checkpoint')
    p.add_argument('--max-age',type=int,default=300)
    args=p.parse_args(argv)
    if args.self_check:
        print(json.dumps({'state':'READ_ONLY_CAPABLE','note':'NO_CREDENTIALS_NO_GITHUB_WRITE_NO_ISSUER_KEY_GATE_A_BLOCKED'},sort_keys=True));return 0
    try:
        if not args.repository or not args.pr or not args.ruleset:
            reject('TARGET_REQUIRED')
        result=observe(AnonymousGitHubREST(),Target(args.repository,args.pr,args.ruleset))
        if args.checkpoint:
            from .engine import load_json
            result=reconcile_checkpoint(load_json(args.checkpoint),result,expected_policy_ruleset_id=args.ruleset,max_age_seconds=args.max_age)
        print(json.dumps(result,sort_keys=True,separators=(',',':')))
        return 2 if result.get('state')=='BLOCKED_RECONCILIATION' else 0
    except (EvidenceError, ValueError, OSError):
        print(json.dumps({'state':'BLOCKED','reason':'REMOTE_OR_VALIDATION_FAILED'},sort_keys=True))
        return 2

if __name__=='__main__':
    raise SystemExit(main())
