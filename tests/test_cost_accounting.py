from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('cost_accounting',ROOT/'adp_context'/'cost_accounting.py')
ca=importlib.util.module_from_spec(spec);spec.loader.exec_module(ca)
RATE=ROOT/'config'/'ADP-COST-RATECARD-20261105.json'
MODEL='gpt-6.1-sol'

def event(k,usage=None):
    obj={'type':k}
    if usage is not None:obj['usage']=usage
    return json.dumps(obj,separators=(',',':'))+'\n'

def valid_stream(input=1000,cached=300,output=100,reason=30,write=0):
    return (event('thread.started')+event('turn.started')+
            event('turn.completed',{'input_tokens':input,'cached_input_tokens':cached,
                                    'output_tokens':output,'reasoning_output_tokens':reason,
                                    'cache_write_input_tokens':write})).encode()

class RatecardTests(unittest.TestCase):
    def test_ratecard(self):self.assertIn(MODEL,ca.load_ratecard(RATE)['models'])
    def test_rate_source(self):self.assertIn('pricing',ca.load_ratecard(RATE)['pricing_source']['api_prices'])
    def test_exact_cost(self):
        count=ca.parse_invocation(valid_stream())['tokens']
        credits,usd=ca.estimate(count,ca.load_ratecard(RATE)['models'][MODEL])
        self.assertEqual(credits,'0.060750')
        self.assertEqual(usd,'0.002430')
    def test_rounding(self):
        count=ca.parse_invocation(valid_stream(input=1,cached=0,output=1,reason=0))['tokens']
        self.assertEqual(ca.estimate(count,ca.load_ratecard(RATE)['models'][MODEL]),('0.000300','0.000012'))
    def test_bad_price(self):
        with tempfile.TemporaryDirectory() as d:
            data=ca.load_ratecard(RATE);data['models'][MODEL]['credits_per_million']['output']=-1
            p=Path(d)/'bad.json';p.write_text(json.dumps(data))
            with self.assertRaises(ca.CostError):ca.load_ratecard(p)
    def test_duplicate_rate_key(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bad.json';p.write_text('{"schema":1,"schema":2}')
            with self.assertRaises(ca.CostError):ca.load_ratecard(p)
    def test_unknown_currency(self):
        with tempfile.TemporaryDirectory() as d:
            data=ca.load_ratecard(RATE);data['currency']='TWD'
            p=Path(d)/'bad.json';p.write_text(json.dumps(data))
            with self.assertRaises(ca.CostError):ca.load_ratecard(p)

class StreamTests(unittest.TestCase):
    def parse(self,raw):return ca.parse_invocation(raw)
    def test_valid(self):self.assertTrue(self.parse(valid_stream())['complete'])
    def test_reasoning_subset(self):
        e=self.parse(valid_stream());self.assertEqual(e['tokens']['output_tokens'],100)
    def test_cached_subset(self):self.assertEqual(self.parse(valid_stream())['tokens']['cached_input_tokens'],300)
    def test_cache_write(self):self.assertEqual(self.parse(valid_stream(write=60))['tokens']['cache_write_input_tokens'],60)
    def test_missing_turn(self):
        with self.assertRaises(ca.CostError):self.parse(event('thread.started').encode())
    def test_missing_thread(self):
        with self.assertRaises(ca.CostError):self.parse((event('turn.started')+event('turn.completed',{})).encode())
    def test_missing_usage(self):
        with self.assertRaises(ca.CostError):self.parse((event('thread.started')+event('turn.started')+event('turn.completed')).encode())
    def test_negative_input(self):
        with self.assertRaises(ca.CostError):self.parse(valid_stream(input=-1))
    def test_boolean_input(self):
        raw=valid_stream().decode().replace('"input_tokens":1000','"input_tokens":true')
        with self.assertRaises(ca.CostError):self.parse(raw.encode())
    def test_cache_exceeds_input(self):
        with self.assertRaises(ca.CostError):self.parse(valid_stream(input=10,cached=11))
    def test_write_overlap(self):
        with self.assertRaises(ca.CostError):self.parse(valid_stream(input=100,cached=80,write=21))
    def test_reason_exceeds_output(self):
        with self.assertRaises(ca.CostError):self.parse(valid_stream(output=20,reason=21))
    def test_zero_usage_unverified(self):
        with self.assertRaises(ca.CostError):self.parse(valid_stream(input=0,cached=0,output=0,reason=0))
    def test_duplicate_completed(self):
        with self.assertRaises(ca.CostError):self.parse(valid_stream()+event('turn.completed',{'input_tokens':1,'cached_input_tokens':0,'output_tokens':1}).encode())
    def test_conflicting_turn_result(self):
        with self.assertRaises(ca.CostError):self.parse(valid_stream()+event('turn.failed',{}).encode())
    def test_incomplete(self):
        obj=self.parse((event('thread.started')+event('turn.started')).encode());self.assertFalse(obj['complete'])
    def test_failed(self):
        obj=self.parse((event('thread.started')+event('turn.started')+event('turn.failed',{})).encode());self.assertTrue(obj['stream_failed'])
    def test_duplicate_json_key(self):
        with self.assertRaises(ca.CostError):self.parse(b'{"type":"thread.started","type":"turn.started"}\n')
    def test_multiple_turn_starts(self):
        with self.assertRaises(ca.CostError):self.parse(valid_stream()+event('turn.started').encode())

class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.manifest=self.root/'invocations.json'
    def write(self,calls=None,files=None,billing='CHATGPT_LOGIN'):
        calls=calls if calls is not None else [{'id':'AUTHOR_1','filename':'AUTHOR_ATTEMPT_1_LOCAL_ONLY.jsonl','model':MODEL}]
        self.manifest.write_text(json.dumps({'schema':ca.MANIFEST,'run_id':'C1TEST20261105',
                  'billing_mode':billing,'invocations':calls}),'utf-8')
        for name,content in (files if files is not None else {'AUTHOR_ATTEMPT_1_LOCAL_ONLY.jsonl':valid_stream()}).items():
            (self.root/name).write_bytes(content)
    def summary(self):return ca.summarize(self.root,self.manifest,RATE)
    def test_complete(self):
        self.write();x=self.summary();self.assertEqual(x['status'],'ACCOUNTING_COMPLETE')
    def test_total_nodup(self):
        self.write();x=self.summary();self.assertEqual((x['total_tokens_no_double_count'],x['output_tokens']), (1100,100))
    def test_credit_equivalent(self):
        self.write();self.assertEqual(self.summary()['codex_credit_equivalent_estimated'],'0.060750')
    def test_billing_not_actual(self):
        self.write();self.assertIn('UNKNOWN',self.summary()['actual_billed_usd'])
    def test_pricing_sha(self):
        self.write();self.assertEqual(len(self.summary()['pricing_ratecard_sha256']),64)
    def test_safe_no_path(self):
        self.write();s=ca.safe_lines(self.summary());self.assertNotIn(self.tmp.name,s)
    def test_safe_fields(self):
        self.write();s=ca.safe_lines(self.summary());self.assertIn('TOKENS_CACHED_INPUT=300',s)
    def test_incomplete_safe_is_marked_partial(self):
        self.write(files={})
        report=ca.safe_lines(self.summary())
        self.assertIn('COST_REPORT_GATE=BLOCKED_USAGE_UNVERIFIED',report)
        self.assertIn('TOKENS_TOTAL_NON_DUPLICATED=PARTIAL_0',report)
    def test_missing_call_fails_gate(self):
        self.write(files={});self.assertEqual(self.summary()['status'],'ACCOUNTING_UNVERIFIED')
    def test_incomplete_call_fails_gate(self):
        self.write(files={'AUTHOR_ATTEMPT_1_LOCAL_ONLY.jsonl':(event('thread.started')+event('turn.started')).encode()});self.assertEqual(self.summary()['status'],'ACCOUNTING_UNVERIFIED')
    def test_unknown_model(self):
        self.write(calls=[{'id':'AUTHOR_1','filename':'AUTHOR_ATTEMPT_1_LOCAL_ONLY.jsonl','model':'unsupported-model'}]);
        with self.assertRaises(ca.CostError):self.summary()
    def test_unregistered_retry(self):
        self.write();(self.root/'AUTHOR_ATTEMPT_2_LOCAL_ONLY.jsonl').write_bytes(valid_stream())
        with self.assertRaises(ca.CostError):self.summary()
    def test_retry_counted(self):
        calls=[{'id':'AUTHOR_1','filename':'AUTHOR_ATTEMPT_1_LOCAL_ONLY.jsonl','model':MODEL},
               {'id':'AUTHOR_2','filename':'AUTHOR_ATTEMPT_2_LOCAL_ONLY.jsonl','model':MODEL}]
        self.write(calls=calls,files={c['filename']:valid_stream() for c in calls})
        self.assertEqual(self.summary()['total_tokens_no_double_count'],2200)
    def test_recovery_counted(self):
        calls=[{'id':'AUTHOR_1','filename':'AUTHOR_ATTEMPT_1_LOCAL_ONLY.jsonl','model':MODEL},
               {'id':'RECOVER','filename':'RECOVER_LOCAL_ONLY.jsonl','model':MODEL}]
        self.write(calls=calls,files={c['filename']:valid_stream() for c in calls})
        self.assertEqual(self.summary()['invocations_measured'],2)
    def test_duplicate_manifest_path(self):
        call={'id':'AUTHOR_1','filename':'AUTHOR_ATTEMPT_1_LOCAL_ONLY.jsonl','model':MODEL}
        self.write(calls=[call,call]);
        with self.assertRaises(ca.CostError):self.summary()
    def test_manifest_path_escape(self):
        self.write(calls=[{'id':'AUTHOR_1','filename':'../x_LOCAL_ONLY.jsonl','model':MODEL}]);
        with self.assertRaises(ca.CostError):self.summary()
    def test_manifest_billing_other(self):
        self.write(billing='API_KEY');
        with self.assertRaises(ca.CostError):self.summary()
    def test_symlink_events(self):
        self.write();source=self.root/'AUTHOR_ATTEMPT_1_LOCAL_ONLY.jsonl';source.unlink()
        tgt=self.root/'data';tgt.write_bytes(valid_stream())
        try:source.symlink_to(tgt)
        except (OSError,NotImplementedError):self.skipTest('symlink privilege unavailable')
        with self.assertRaises(ca.CostError):self.summary()
    def test_cache_write_api_not_complete(self):
        self.write(files={'AUTHOR_ATTEMPT_1_LOCAL_ONLY.jsonl':valid_stream(write=50)})
        self.assertFalse(self.summary()['api_usd_equivalent_complete'])
    def test_output_including_reasoning(self):
        self.write();x=self.summary();self.assertEqual(x['total_tokens_no_double_count'],x['input_tokens']+x['output_tokens'])
    def test_manifest_zero_calls(self):
        self.write(calls=[],files={});
        with self.assertRaises(ca.CostError):self.summary()

if __name__=='__main__':unittest.main()
