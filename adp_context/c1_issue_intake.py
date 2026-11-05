"""Read-only, fail-closed C1 unattended Issue intake contract.

This is policy-gated task *discovery*, not an autonomous scheduler or a merge permit.
The untrusted Issue body is data; never use it to override controller policy.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re

SCHEMA='adp-c1-issue-v1'
REPO='Pochun2/ADP-GITHUB-CORE'
LABEL='adp-agent-ready'
TASK_ID=re.compile(r'C1-[A-Z0-9][A-Z0-9_-]{2,50}\Z')
SHA40=re.compile(r'[0-9a-f]{40}\Z')
SHA64=re.compile(r'[0-9a-f]{64}\Z')
TARGET=re.compile(r'adp_context/[a-z][a-z0-9_]{0,60}\.py\Z')

class IntakeError(ValueError):pass

def need(test, message):
    if not test:raise IntakeError(message)

def parse_pairs(items):
    result={}
    for k,v in items:
        need(k not in result,'DUPLICATE_JSON_KEY')
        result[k]=v
    return result

def validate_issue(issue,baseline):
    """Only return bounded facts. Do not emit raw title, body or user identities."""
    need(type(baseline) is str and SHA40.fullmatch(baseline),'BASELINE_INVALID')
    need(type(issue) is dict,'ISSUE_NOT_OBJECT')
    need(type(issue.get('number')) is int and issue['number']>0,'ISSUE_NUMBER_INVALID')
    need(issue.get('state')=='open' and not issue.get('pull_request'),'ISSUE_NOT_OPEN_TASK')
    labels=issue.get('labels')
    need(type(labels) is list and len(labels)<=30,'ISSUE_LABELS_INVALID')
    names=[]
    for label in labels:
        name=label if type(label) is str else label.get('name') if type(label) is dict else None
        need(type(name) is str,'ISSUE_LABEL_INVALID')
        names.append(name)
    need(names.count(LABEL)==1,'ISSUE_NOT_EXPLICITLY_READY')
    body=issue.get('body')
    need(type(body) is str and 0<len(body.encode('utf-8'))<=6000,'ISSUE_BODY_INVALID')
    try:task=json.loads(body,object_pairs_hook=parse_pairs)
    except (ValueError,UnicodeError) as exc:raise IntakeError('ISSUE_BODY_NOT_STRICT_JSON') from exc
    need(type(task) is dict and set(task)=={'schema','task_id','repository','baseline_sha',
                                          'kind','output_path','spec_sha256'},'ISSUE_TASK_SCHEMA_INVALID')
    need(task['schema']==SCHEMA and task['repository']==REPO and task['baseline_sha']==baseline,
         'ISSUE_SCOPE_OR_BASELINE_INVALID')
    need(task['kind']=='PURE_PYTHON_ONE_FILE','ISSUE_KIND_NOT_APPROVED')
    need(type(task['task_id']) is str and TASK_ID.fullmatch(task['task_id']),
         'ISSUE_TASK_ID_INVALID')
    need(type(task['output_path']) is str and TARGET.fullmatch(task['output_path']) and
         not task['output_path'].startswith('adp_context/c1_issue_intake') and
         not task['output_path'].startswith('adp_context/cost_accounting'),
         'ISSUE_OUTPUT_PATH_UNSAFE')
    need(type(task['spec_sha256']) is str and SHA64.fullmatch(task['spec_sha256']),
         'ISSUE_SPEC_DIGEST_INVALID')
    need(issue.get('title')=='[ADP-C1] '+task['task_id'],'ISSUE_TITLE_MISMATCH')
    return {'issue_number':issue['number'],'task_id':task['task_id'],
            'repository':REPO,'baseline_sha':baseline,'kind':task['kind'],
            'output_path':task['output_path'],'spec_sha256':task['spec_sha256'],
            'authorization':'NONE','state':'READY_FOR_EXTERNAL_BOUNDED_CONTROLLER_REVIEW'}

def select_ready(issues,baseline):
    need(type(issues) is list and len(issues)<=100,'ISSUE_COLLECTION_INVALID')
    eligible=[];seen=set()
    for issue in issues:
        # Ignore unrelated Issues. An explicitly ready Issue with malformed
        # schema is a blocking policy violation, not silently skipped.
        if type(issue) is not dict:
            raise IntakeError('ISSUE_COLLECTION_MEMBER_INVALID')
        labels=issue.get('labels',[])
        if type(labels) is not list:
            raise IntakeError('ISSUE_LABELS_INVALID')
        names=[v if type(v) is str else v.get('name') if type(v) is dict else None
               for v in labels]
        if LABEL not in names:continue
        result=validate_issue(issue,baseline)
        need(result['issue_number'] not in seen and result['task_id'] not in seen,
             'DUPLICATE_READY_ISSUE_OR_TASK')
        seen.update((result['issue_number'],result['task_id']))
        eligible.append(result)
    eligible.sort(key=lambda q:q['issue_number'])
    need(len(eligible)<=1,'AMBIGUOUS_MULTIPLE_READY_ISSUES_FAIL_CLOSED')
    return eligible[0] if eligible else {'state':'NO_APPROVED_READY_TASK','authorization':'NONE'}

def main(argv=None):
    ap=argparse.ArgumentParser()
    ap.add_argument('--self-check',action='store_true')
    ap.add_argument('--issues-fixture')
    ap.add_argument('--baseline-sha')
    a=ap.parse_args(argv)
    if a.self_check:
        print('C1_ISSUE_INTAKE_READONLY_NO_WRITE_NO_SCHEDULER');return 0
    if not a.issues_fixture or not a.baseline_sha:
        print('ISSUE_INTAKE=BLOCKED_MISSING_ARGUMENTS');return 2
    try:
        p=Path(a.issues_fixture)
        need(p.is_file() and not p.is_symlink() and p.stat().st_size<=100_000,
             'ISSUE_FIXTURE_UNSAFE')
        issues=json.loads(p.read_text('utf-8'),object_pairs_hook=parse_pairs)
        print(json.dumps(select_ready(issues,a.baseline_sha),sort_keys=True))
        return 0
    except (IntakeError,OSError,ValueError) as exc:
        print('ISSUE_INTAKE=BLOCKED_'+str(exc)[:100]);return 2

if __name__=='__main__':raise SystemExit(main())
