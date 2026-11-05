"""ADP C1-U3: strict, pure task-completion decision, NOT a GitHub write permit.

Untrusted Issue data and observation documents are never executable policy.
External, separately shipped controller must verify observations against GitHub.
"""
from __future__ import annotations
import json
import re

SHA40=re.compile(r'[0-9a-f]{40}\Z')
SHA64=re.compile(r'[0-9a-f]{64}\Z')
ISSUE_SCHEMA='adp-c1-issue-v1'
LABEL='adp-agent-ready'

class CompletionError(ValueError):pass

def require(ok,code):
    if not ok:raise CompletionError(code)

def parse_pairs(pairs):
    obj={}
    for key,val in pairs:
        require(key not in obj,'DUPLICATE_ISSUE_BODY_KEY')
        obj[key]=val
    return obj

def decision(issue, proof, expected):
    """Return CLOSE_ELIGIBLE or ALREADY_CLOSED_VERIFIED, fail closed otherwise.

    The external controller supplies verified `proof` and its own sealed `expected`.
    This function alone cannot attest remote GitHub facts or authorize a write.
    """
    require(type(expected) is dict and set(expected)=={
        'repo','number','title','task_id','spec_sha256','baseline_sha',
        'output_path','source_sha256','pr_number','pr_head_sha',
        'pr_merge_sha','regression_merge_sha','check_app_id'},'EXPECTED_SCHEMA_DRIFT')
    for x in ('baseline_sha','pr_head_sha','pr_merge_sha','regression_merge_sha'):
        require(type(expected[x]) is str and SHA40.fullmatch(expected[x]),'EXPECTED_SHA_INVALID')
    for x in ('spec_sha256','source_sha256'):
        require(type(expected[x]) is str and SHA64.fullmatch(expected[x]),'EXPECTED_DIGEST_INVALID')
    require(type(expected['number']) is int and expected['number']>0 and
            type(expected['pr_number']) is int and expected['pr_number']>0 and
            type(expected['check_app_id']) is int and expected['check_app_id']>0,
            'EXPECTED_ID_INVALID')
    require(type(issue) is dict and type(proof) is dict,'ISSUE_OR_PROOF_INVALID')
    require(type(issue.get('number')) is int and issue['number']==expected['number'] and
            issue.get('title')==expected['title'] and issue.get('state') in ('open','closed'),
            'ISSUE_ID_TITLE_OR_STATE_DRIFT')
    labels=issue.get('labels')
    require(type(labels) is list and len(labels)<=30,'ISSUE_LABEL_INVALID')
    labelnames=[v if type(v) is str else v.get('name') if type(v) is dict else None for v in labels]
    require(labelnames.count(LABEL)==1,'ISSUE_READY_LABEL_DRIFT')
    raw=issue.get('body')
    require(type(raw) is str and 0<len(raw.encode('utf-8'))<=6000,'ISSUE_BODY_INVALID')
    try:task=json.loads(raw,object_pairs_hook=parse_pairs)
    except (ValueError,UnicodeError) as e:raise CompletionError('ISSUE_BODY_NOT_JSON') from e
    require(type(task) is dict and set(task)=={
        'schema','task_id','repository','baseline_sha','kind','output_path','spec_sha256'},
        'ISSUE_TASK_SCHEMA_DRIFT')
    require(task=={'schema':ISSUE_SCHEMA,'task_id':expected['task_id'],
                  'repository':expected['repo'],'baseline_sha':expected['baseline_sha'],
                  'kind':'PURE_PYTHON_ONE_FILE','output_path':expected['output_path'],
                  'spec_sha256':expected['spec_sha256']},'ISSUE_TASK_VALUE_DRIFT')
    require(set(proof)=={'repository','source_path','source_sha256','original_pr_number',
                        'original_pr_head_sha','original_pr_merge_sha','regression_merge_sha',
                        'main_sha','ruleset_enforcement','strict_ci','required_app_id',
                        'checks_complete'},'PROOF_SCHEMA_DRIFT')
    require(proof['repository']==expected['repo'] and
            proof['source_path']==expected['output_path'] and
            proof['source_sha256']==expected['source_sha256'] and
            type(proof['original_pr_number']) is int and proof['original_pr_number']==expected['pr_number'] and
            proof['original_pr_head_sha']==expected['pr_head_sha'] and
            proof['original_pr_merge_sha']==expected['pr_merge_sha'] and
            proof['regression_merge_sha']==expected['regression_merge_sha'] and
            proof['main_sha']==expected['regression_merge_sha'] and
            proof['ruleset_enforcement']=='active' and proof['strict_ci'] is True and
            type(proof['required_app_id']) is int and proof['required_app_id']==expected['check_app_id'] and
            proof['checks_complete'] is True,'COMPLETION_PROOF_UNVERIFIED')
    return {'issue_number':expected['number'],'task_id':expected['task_id'],
            'state':'CLOSE_ELIGIBLE' if issue['state']=='open' else 'ALREADY_CLOSED_VERIFIED',
            'authorization':'NONE','attestation':'NOT_ATTESTED'}
