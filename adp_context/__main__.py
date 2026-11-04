"""Offline command line demonstration: never grants permission or writes to GitHub."""
import argparse
import json
from pathlib import Path
from .engine import load_json,validate_checkpoint,validate_decisions,checkpoint_digest,compact,resume_preview,retrieve,ContextError

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument('command',choices=['self-check','validate','capsule','resume','retrieve'])
    p.add_argument('--checkpoint')
    p.add_argument('--decisions')
    p.add_argument('--remote')
    p.add_argument('--query')
    a=p.parse_args(argv)
    try:
        if a.command=='self-check':
            print(json.dumps({'state':'OFFLINE_ONLY','note':'NO_NETWORK_NO_GITHUB_WRITE_NO_ISSUER_KEY_GATE_A_BLOCKED'},sort_keys=True));return 0
        if not a.checkpoint: raise ContextError('CHECKPOINT_REQUIRED')
        cp=validate_checkpoint(load_json(a.checkpoint))
        if a.command=='validate':
            print(json.dumps({'state':'VALIDATED_SHAPE_NOT_AUTHENTICATED','digest':checkpoint_digest(cp)},sort_keys=True));return 0
        decisions=validate_decisions(load_json(a.decisions)) if a.decisions else []
        if a.command=='capsule':print(compact(cp,decisions),end='');return 0
        if a.command=='retrieve':print(json.dumps(retrieve(cp,[a.query] if a.query else []),sort_keys=True));return 0
        if a.command=='resume':
            if not a.remote:raise ContextError('REMOTE_FIXTURE_REQUIRED')
            result=resume_preview(cp,load_json(a.remote),decisions)
            print(json.dumps(result,sort_keys=True))
            return 2 if result['state']=='BLOCKED_RECONCILIATION' else 0
    except (ContextError, OSError) as exc:
        print(json.dumps({'state':'BLOCKED','reason':str(exc)},sort_keys=True));return 2

if __name__=='__main__':raise SystemExit(main())
