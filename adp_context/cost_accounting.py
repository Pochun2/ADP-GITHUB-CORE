"""ADP-COST-GOV-001: strict Codex exec --json token & cost evidence.

Read-only, local-only; no billing API, no authentication and no GitHub writes.
For ChatGPT sign-in, API-equivalent USD is NOT an invoice or actual charge.
Each invocation is a NEW --ephemeral, single-turn `codex exec --json` stream.
"""
from __future__ import annotations

import argparse
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
from pathlib import Path
import re

SCHEMA = 'adp-cost-report-v1'
MANIFEST = 'adp-codex-invocations-v1'
HEX40 = re.compile(r'[0-9a-f]{40}\Z')
IDENT = re.compile(r'[A-Z][A-Z0-9_]{0,63}\Z')
FILE = re.compile(r'[A-Z][A-Z0-9_]{0,63}_LOCAL_ONLY\.jsonl\Z')
MAX_BYTES = 16_000_000
COUNTERS = ('input_tokens','cached_input_tokens','cache_write_input_tokens',
            'output_tokens','reasoning_output_tokens')

class CostError(ValueError):
    pass

def guard(test, code):
    if not test:
        raise CostError(code)

def nonneg(value):
    return type(value) is int and 0 <= value <= 2**53-1

def strict_json(raw):
    def pairs(items):
        value={}
        for k,v in items:
            guard(k not in value,'DUPLICATE_JSON_KEY')
            value[k]=v
        return value
    try:
        return json.loads(raw,object_pairs_hook=pairs)
    except (ValueError,UnicodeError) as exc:
        raise CostError('INVALID_JSON') from exc

def read_local(path, root, limit=MAX_BYTES):
    p=Path(path)
    guard(p.parent==root and p.name == p.name and not p.is_symlink() and p.is_file(),
          'LOCAL_SOURCE_PATH_UNSAFE')
    guard(0 < p.stat().st_size <= limit,'LOCAL_SOURCE_SIZE_INVALID')
    return p.read_bytes()

def parse_invocation(raw):
    """Accept ONE ephemeral turn. Never add a resumed cumulative total."""
    guard(type(raw) is bytes and len(raw)<=MAX_BYTES,'EVENT_BYTES_INVALID')
    events=[]
    for line in raw.splitlines():
        if not line.strip():continue
        guard(len(line)<2_000_000,'EVENT_LINE_OVERSIZE')
        event=strict_json(line.decode('utf-8'))
        guard(type(event) is dict and type(event.get('type')) is str,'EVENT_TYPE_INVALID')
        events.append(event)
    guard(events,'EVENTS_EMPTY')
    kinds=[e['type'] for e in events]
    guard(kinds.count('thread.started')==1 and kinds.count('turn.started')==1,
          'EPHEMERAL_ONE_TURN_REQUIRED')
    guard(kinds.count('turn.completed')<=1,'DUPLICATE_OR_CUMULATIVE_TURN_USAGE')
    guard(kinds.count('turn.failed')<=1,'DUPLICATE_FAILURE')
    guard(not ('turn.completed' in kinds and 'turn.failed' in kinds),'CONFLICTING_TURN_RESULT')
    completed=next((e for e in events if e['type']=='turn.completed'),None)
    counts={x:0 for x in COUNTERS}
    if completed is not None:
        v=completed.get('usage')
        guard(type(v) is dict and all(x in v for x in ('input_tokens','cached_input_tokens','output_tokens')),
              'TOKEN_USAGE_MISSING')
        counts={x:v.get(x,0) for x in COUNTERS}
        guard(all(nonneg(x) for x in counts.values()),'TOKEN_USAGE_INVALID')
        guard(counts['input_tokens']>=counts['cached_input_tokens']+counts['cache_write_input_tokens'],
              'CACHED_OR_WRITE_INPUT_OVERLAP')
        guard(counts['reasoning_output_tokens']<=counts['output_tokens'],
              'REASONING_OUTPUT_DOUBLE_COUNT')
        guard(counts['input_tokens']+counts['output_tokens']>0,'EMPTY_USAGE_UNVERIFIED')
    return {
        'complete':completed is not None,
        'stream_failed': 'turn.failed' in kinds or 'error' in kinds,
        'source_sha256':hashlib.sha256(raw).hexdigest(),
        'tokens':counts,
    }

def load_ratecard(path):
    p=Path(path)
    guard(p.is_file() and not p.is_symlink() and p.stat().st_size<32_000,'RATECARD_UNSAFE')
    rate=strict_json(p.read_text('utf-8'))
    guard(type(rate) is dict and rate.get('schema')=='adp-cost-ratecard-v1' and
          rate.get('currency')=='USD' and rate.get('denominator')==1_000_000,
          'RATECARD_SCHEMA_INVALID')
    guard(type(rate.get('models')) is dict,'RATECARD_MODELS_MISSING')
    for name,fields in rate['models'].items():
        guard(re.fullmatch(r'[a-z0-9_.-]{4,70}',name) is not None,'RATECARD_MODEL_INVALID')
        for currency in ('credits_per_million','api_usd_per_million'):
            v=fields.get(currency)
            guard(type(v) is dict and set(v)=={'uncached_input','cached_input','output'},'RATECARD_FIELD_INVALID')
            for t in v.values():
                guard(type(t) is str and bool(re.fullmatch(r'[0-9]{1,5}(\.[0-9]{1,6})?',t)),
                      'RATECARD_PRICE_INVALID')
    return rate

def estimate(counts, rate):
    uncached=counts['input_tokens']-counts['cached_input_tokens']
    def calc(prices):
        cost=(Decimal(uncached)*Decimal(prices['uncached_input']) +
              Decimal(counts['cached_input_tokens'])*Decimal(prices['cached_input']) +
              Decimal(counts['output_tokens'])*Decimal(prices['output'])) / Decimal(1_000_000)
        return str(cost.quantize(Decimal('0.000001'),rounding=ROUND_HALF_UP))
    # API cache write has additional cache tier/duration charges not captured here.
    return calc(rate['credits_per_million']),calc(rate['api_usd_per_million'])

def summarize(run_root, manifest_path, ratecard_path):
    root=Path(run_root).resolve(strict=True)
    guard(root.is_dir() and not Path(run_root).is_symlink(),'RUN_ROOT_UNSAFE')
    manifest_path=Path(manifest_path)
    guard(manifest_path.parent.resolve()==root,'MANIFEST_OUTSIDE_RUN_ROOT')
    manifest=strict_json(read_local(manifest_path,root,100_000).decode('utf-8'))
    guard(type(manifest) is dict and set(manifest)=={'schema','run_id','billing_mode','invocations'} and
          manifest['schema']==MANIFEST,'MANIFEST_SCHEMA_INVALID')
    guard(type(manifest['run_id']) is str and IDENT.fullmatch(manifest['run_id']) is not None,
          'RUN_ID_INVALID')
    guard(manifest['billing_mode']=='CHATGPT_LOGIN','UNKNOWN_BILLING_MODE')
    calls=manifest['invocations']
    guard(type(calls) is list and 1<=len(calls)<=32,'INVOCATION_COUNT_INVALID')
    ratecard=load_ratecard(ratecard_path)
    names=set()
    totals={x:0 for x in COUNTERS}
    runs=[]; complete=True; api_estimate_ok=True
    total_credits=Decimal('0'); total_usd=Decimal('0')
    for call in calls:
        guard(type(call) is dict and set(call)=={'id','filename','model'},'INVOCATION_SCHEMA_INVALID')
        name=call['filename']; label=call['id']; model=call['model']
        guard(type(name) is str and FILE.fullmatch(name) is not None and
              type(label) is str and IDENT.fullmatch(label) is not None and
              name not in names,'INVOCATION_NAME_UNSAFE_OR_DUPLICATE')
        guard(type(model) is str and model in ratecard['models'],'MODEL_RATE_NOT_PINNED')
        names.add(name)
        path=root/name
        if not path.exists():
            complete=False
            runs.append({'id':label,'model':model,'usage_status':'MISSING','event_sha256':None})
            continue
        item=parse_invocation(read_local(path,root))
        complete=complete and item['complete'] and not item['stream_failed']
        for x in COUNTERS:
            totals[x]+=item['tokens'][x]
        credits,usd=estimate(item['tokens'],ratecard['models'][model])
        if not item['complete']:credits=usd=None
        else:
            total_credits+=Decimal(credits)
            total_usd+=Decimal(usd)
        if item['tokens']['cache_write_input_tokens']>0:api_estimate_ok=False
        runs.append({'id':label,'model':model,'usage_status':
            ('COMPLETE' if item['complete'] and not item['stream_failed'] else 'UNVERIFIED'),
            'event_sha256':item['source_sha256'], 'tokens':item['tokens'],
            'credits_estimated':credits,'api_usd_equivalent_base_estimated':usd})
    existing={x.name for x in root.glob('*_LOCAL_ONLY.jsonl') if x.is_file() or x.is_symlink()}
    guard(existing.issubset(names),'UNREGISTERED_CODEX_INVOCATION_LOGS')
    return {'schema':SCHEMA,'run_id':manifest['run_id'],
        'status':'ACCOUNTING_COMPLETE' if complete else 'ACCOUNTING_UNVERIFIED',
        'invocations_expected':len(calls),'invocations_measured':sum(x['usage_status']=='COMPLETE' for x in runs),
        'model_set':sorted({x['model'] for x in runs}),
        'billing_mode':'CHATGPT_LOGIN',
        'input_tokens':totals['input_tokens'],
        'cached_input_tokens':totals['cached_input_tokens'],
        'cache_write_input_tokens':totals['cache_write_input_tokens'],
        'uncached_input_tokens':totals['input_tokens']-totals['cached_input_tokens'],
        'output_tokens':totals['output_tokens'],
        'reasoning_output_tokens_included_in_output':totals['reasoning_output_tokens'],
        'total_tokens_no_double_count':totals['input_tokens']+totals['output_tokens'],
        'codex_credit_equivalent_estimated':str(total_credits.quantize(Decimal('0.000001'))),
        'api_usd_equivalent_base_estimated':str(total_usd.quantize(Decimal('0.000001'))),
        'api_usd_equivalent_complete':api_estimate_ok and complete,
        'actual_billed_usd':'UNKNOWN_NOT_IN_CLI_TELEMETRY',
        'actual_codex_credits_deducted':'UNKNOWN_NOT_IN_CLI_TELEMETRY',
        'pricing_ratecard_sha256':hashlib.sha256(Path(ratecard_path).read_bytes()).hexdigest(),
        'pricing_as_of':ratecard['as_of_utc'],
        'pricing_source':ratecard['pricing_source'],
        'aggregation':'ONE_EPHEMERAL_TURN_PER_INVOCATION; OUTPUT_INCLUDES_REASONING; INPUT_INCLUDES_CACHED',
        'items':runs}

def safe_lines(report):
    """Only stable aggregates. Never print prompt contents, file paths or thread IDs."""
    return '\n'.join([
        'COST_GOVERNANCE=ADP-COST-GOV-001-v1.0',
        'TOKEN_ACCOUNTING='+report['status'],
        'CODEX_MODEL='+','.join(report['model_set']),
        'CODEX_CALLS='+str(report['invocations_measured'])+'/'+str(report['invocations_expected']),
        'TOKENS_INPUT_TOTAL='+str(report['input_tokens']),
        'TOKENS_CACHED_INPUT='+str(report['cached_input_tokens']),
        'TOKENS_INPUT_UNCACHED='+str(report['uncached_input_tokens']),
        'TOKENS_CACHE_WRITE='+str(report['cache_write_input_tokens']),
        'TOKENS_OUTPUT_INCLUDING_REASONING='+str(report['output_tokens']),
        'TOKENS_REASONING_SUBSET='+str(report['reasoning_output_tokens_included_in_output']),
        'TOKENS_TOTAL_NON_DUPLICATED='+('PARTIAL_'+str(report['total_tokens_no_double_count']) if report['status']!='ACCOUNTING_COMPLETE' else str(report['total_tokens_no_double_count'])),
        'COST_CODEX_CREDITS_EQUIVALENT_ESTIMATE='+('PARTIAL_'+report['codex_credit_equivalent_estimated'] if report['status']!='ACCOUNTING_COMPLETE' else report['codex_credit_equivalent_estimated']),
        'COST_API_USD_EQUIVALENT_BASE_ESTIMATE='+('PARTIAL_'+report['api_usd_equivalent_base_estimated'] if report['status']!='ACCOUNTING_COMPLETE' else report['api_usd_equivalent_base_estimated']),
        'COST_API_USD_ESTIMATE_COMPLETE='+str(report['api_usd_equivalent_complete']).upper(),
        'ACTUAL_BILLED_USD=UNKNOWN_NOT_IN_CLI_TELEMETRY',
        'ACTUAL_CODEX_CREDITS_DEDUCTED=UNKNOWN_NOT_IN_CLI_TELEMETRY',
        'PRICE_RATECARD_SHA256='+report['pricing_ratecard_sha256'],
        'COST_REPORT_GATE='+('PASS_TELEMETRY_COMPLETE_NOT_ACTUAL_BILL' if report['status']=='ACCOUNTING_COMPLETE' else 'BLOCKED_USAGE_UNVERIFIED'),
    ])+'\n'

def main(argv=None):
    ap=argparse.ArgumentParser()
    ap.add_argument('--self-check',action='store_true')
    ap.add_argument('--run-root')
    ap.add_argument('--manifest')
    ap.add_argument('--ratecard')
    ap.add_argument('--output-json')
    ns=ap.parse_args(argv)
    if ns.self_check:
        print('COST_MODULE_READONLY_NO_BILLING_NO_GITHUB_WRITE')
        return 0
    if not (ns.run_root and ns.manifest and ns.ratecard):
        print('COST_REPORT_GATE=BLOCKED_ARGUMENTS_MISSING');return 2
    try:
        report=summarize(ns.run_root,ns.manifest,ns.ratecard)
        if ns.output_json:
            dest=Path(ns.output_json)
            guard(dest.parent.resolve()==Path(ns.run_root).resolve() and not dest.is_symlink(),
                  'OUTPUT_LOCATION_UNSAFE')
            dest.write_text(json.dumps(report,indent=2,ensure_ascii=False,sort_keys=True)+'\n','utf-8')
        print(safe_lines(report),end='')
        return 0 if report['status']=='ACCOUNTING_COMPLETE' else 2
    except (CostError,OSError) as exc:
        print('COST_REPORT_GATE=BLOCKED_'+str(exc)[:90]);return 2

if __name__=='__main__':
    raise SystemExit(main())
