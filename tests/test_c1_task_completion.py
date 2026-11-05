"""Permanent fail-closed, no-network lifecycle/anti-replay contract tests."""
import copy
import json
import unittest
from adp_context.c1_task_completion import decision,CompletionError

BASE='a'*40
HEAD='b'*40
PRMERGE='c'*40
MERGE='d'*40
SPEC='e'*64
SOURCE='f'*64

def expected():
    return {'repo':'Pochun2/ADP-GITHUB-CORE','number':8,'title':'[ADP-C1] C1-U22-TOKEN-BUDGET',
      'task_id':'C1-U22-TOKEN-BUDGET','spec_sha256':SPEC,'baseline_sha':BASE,
      'output_path':'adp_context/c1_token_budget.py','source_sha256':SOURCE,
      'pr_number':9,'pr_head_sha':HEAD,'pr_merge_sha':PRMERGE,
      'regression_merge_sha':MERGE,'check_app_id':15368}

def issue(state='open'):
    e=expected();body={'schema':'adp-c1-issue-v1','task_id':e['task_id'],
     'repository':e['repo'],'baseline_sha':e['baseline_sha'],
     'kind':'PURE_PYTHON_ONE_FILE','output_path':e['output_path'],
     'spec_sha256':e['spec_sha256']}
    return {'number':8,'state':state,'title':e['title'],'body':json.dumps(body),
     'labels':[{'name':'adp-agent-ready'}]}

def proof():
    e=expected();return {'repository':e['repo'],'source_path':e['output_path'],
      'source_sha256':e['source_sha256'],'original_pr_number':e['pr_number'],
      'original_pr_head_sha':e['pr_head_sha'],'original_pr_merge_sha':e['pr_merge_sha'],
      'regression_merge_sha':e['regression_merge_sha'],'main_sha':e['regression_merge_sha'],
      'ruleset_enforcement':'active','strict_ci':True,'required_app_id':15368,'checks_complete':True}

class TaskCompletionPermanentRegression(unittest.TestCase):
    def bad(self,i=None,p=None,e=None):
        with self.assertRaises(CompletionError):decision(i if i is not None else issue(),p if p is not None else proof(),e if e is not None else expected())
    def test_eligible(self):self.assertEqual(decision(issue(),proof(),expected())['state'],'CLOSE_ELIGIBLE')
    def test_already_closed(self):self.assertEqual(decision(issue('closed'),proof(),expected())['state'],'ALREADY_CLOSED_VERIFIED')
    def test_no_grant(self):self.assertEqual(decision(issue(),proof(),expected())['authorization'],'NONE')
    def test_not_attested(self):self.assertEqual(decision(issue(),proof(),expected())['attestation'],'NOT_ATTESTED')
    def test_input_immutable(self):
        i=issue();p=proof();e=expected();copies=copy.deepcopy([i,p,e]);decision(i,p,e)
        self.assertEqual([i,p,e],copies)
    def test_issue_number_bool(self):
        i=issue();i['number']=True;self.bad(i=i)
    def test_wrong_issue_id(self):
        i=issue();i['number']=9;self.bad(i=i)
    def test_wrong_issue_title(self):
        i=issue();i['title']='changed';self.bad(i=i)
    def test_issue_draft_state(self):
        i=issue('draft');self.bad(i=i)
    def test_issue_missing_label(self):
        i=issue();i['labels']=[];self.bad(i=i)
    def test_issue_duplicate_label(self):
        i=issue();i['labels']=i['labels']*2;self.bad(i=i)
    def test_issue_body_duplicate_json_key(self):
        i=issue();i['body']='{"schema":"a","schema":"b"}';self.bad(i=i)
    def test_issue_body_additional_key(self):
        i=issue();q=json.loads(i['body']);q['extra']=1;i['body']=json.dumps(q);self.bad(i=i)
    def test_issue_kind_other(self):
        i=issue();q=json.loads(i['body']);q['kind']='OTHER';i['body']=json.dumps(q);self.bad(i=i)
    def test_issue_baseline_drift(self):
        i=issue();q=json.loads(i['body']);q['baseline_sha']='f'*40;i['body']=json.dumps(q);self.bad(i=i)
    def test_proof_wrong_source(self):
        p=proof();p['source_sha256']='e'*64;self.bad(p=p)
    def test_proof_wrong_pr(self):
        p=proof();p['original_pr_number']=10;self.bad(p=p)
    def test_proof_bad_pr_head(self):
        p=proof();p['original_pr_head_sha']='a'*40;self.bad(p=p)
    def test_proof_bad_merge(self):
        p=proof();p['original_pr_merge_sha']='a'*40;self.bad(p=p)
    def test_proof_wrong_current_main(self):
        p=proof();p['main_sha']='a'*40;self.bad(p=p)
    def test_proof_strict_check_false(self):
        p=proof();p['strict_ci']=False;self.bad(p=p)
    def test_proof_app_wrong(self):
        p=proof();p['required_app_id']=99;self.bad(p=p)
    def test_proof_ruleset_disabled(self):
        p=proof();p['ruleset_enforcement']='disabled';self.bad(p=p)
    def test_proof_checks_missing(self):
        p=proof();p['checks_complete']=False;self.bad(p=p)
    def test_proof_additional_field(self):
        p=proof();p['extra']='x';self.bad(p=p)
    def test_expected_missing_id(self):
        e=expected();del e['pr_number'];self.bad(e=e)
    def test_expected_invalid_sha(self):
        e=expected();e['regression_merge_sha']='NOT_A_SHA';self.bad(e=e)
    def test_expected_bool_id(self):
        e=expected();e['number']=True;self.bad(e=e)
    def test_proof_bool_app(self):
        p=proof();p['required_app_id']=True;self.bad(p=p)
    def test_no_bool_checks(self):
        p=proof();p['checks_complete']=1;self.bad(p=p)
    def test_non_dict_issue(self):self.bad(i='issue')
    def test_non_dict_proof(self):self.bad(p='proof')
    def test_issue_number_missing(self):
        i=issue();del i['number'];self.bad(i=i)
    def test_body_not_json(self):
        i=issue();i['body']='not_json';self.bad(i=i)

if __name__=='__main__':unittest.main()
