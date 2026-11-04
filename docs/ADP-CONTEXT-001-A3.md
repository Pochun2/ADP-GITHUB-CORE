# ADP-CONTEXT-001-A3 — Offline Durable Candidate Checkpoint / Resume (v0.3)

## Scope and provenance

This increment extends verified A1 (41 tests) + A2 (39 tests) with an A3 local candidate journal (35 tests). No modification of A1/A2 files; import four new files. The test suite is synthetic and offline. No user credentials, external writes, privileged GitHub App access, issuer deployment, or trading permissions.

### What it actually does

- Validates A1 checkpoint shape and hashes the canonical checkpoint bytes.
- Appends a JSONL history to a **trusted operator-controlled local directory**; initial creation uses `xb`, subsequent writes append + `fsync`.
- Each entry pins sequence, UTC timestamp, event ID, previous entry SHA256, checkpoint SHA256 and a canonical entry hash.
- Every append replays the entire journal and requires the caller's exact previous entry SHA256 (CAS). Duplicate event IDs, stale CAS, clock regression, task/repository/policy mutation, malformed/truncated journals fail closed.
- Exclusive `.lock` directory coordinates writers **on one trusted filesystem**. Stale lock is never auto-stolen. A human must inspect before releasing it.
- `resume_gate(...)` replays the journal and invokes A2 `reconcile_checkpoint` against a **caller-supplied** A2 observation. A positive comparison returns `REVIEW_REQUIRED_NOT_AUTHORIZED`; an inconsistency returns `BLOCKED_RECONCILIATION`.

### Deliberate limitations / threat boundary

1. **This is NOT yet GitHub persisted state.** The local JSONL file can be copied to another host, but must not be treated as the GitHub canonical source, trust anchor, independent evidence, or cross-host durable locking.
2. A SHA256 chain detects accidental or unsophisticated in-place changes, **not malicious rewriting of the entire chain**. A remote protected Git commit / separately pinned signed root is needed for rollback and root-integrity protection.
3. The `.lock` directory is a single-filesystem advisory mutual exclusion convention; it is not a distributed lease, not a reliable NFS lock, and not process-crash recovery. Suspicious or stale locks block.
4. Operating-system `fsync` does not guarantee durable storage across every hardware or filesystem failure. Truncated or unparseable state blocks and requires manual reconciliation.
5. A2 observation JSON may be a fixture or injected by an untrusted caller: even an observation digest and successful required CI do not authenticate its origin. A trusted remote collector, freshness, and independent policy still must be verified.
6. The append API never changes GitHub state. `resume_gate` grants **no** GitHub/PR/Issuer authorization and does not claim to recover real work execution side effects.
7. Do not store private keys, tokens, broker credentials or sensitive prices in checkpoint fields. Keep operator-controlled local directories separated from public PR runners.

### Example — offline only

```python
from adp_context.checkpoint_store import append,load,resume_gate
# checkpoint: A1-validated dictionary, retrieved by trusted caller.
# Only in an operator-controlled directory, not on an untrusted PR filesystem.
first=append('checkpoint.jsonl',checkpoint,event_id='task-001',
             at_utc='2026-11-04T03:00:00Z')
second=append('checkpoint.jsonl',updated_checkpoint,event_id='task-002',
              at_utc='2026-11-04T03:00:01Z',
              expected_last_sha256=first['entry_sha256'])
# read and validate the full chain before any resume preview
entries=load('checkpoint.jsonl')
# `resume_gate` takes previously collected A2 observation; no real writes.
preview=resume_gate('checkpoint.jsonl',observation,
                    expected_policy_ruleset_id=26423889,
                    now_utc='2026-11-04T03:00:02Z')
```

### Formal future gate CTX-A3-GH

To claim GitHub-canonical checkpoint persistence requires a *separate* change that: (a) writes on an approved protected ref via non-agent publisher, (b) pins parent commit and policy/manifest hashes with compare-and-swap, (c) persists append-only journals in independent trust domain, (d) can cold-load from a new host with fresh independent A2 read, (e) simulates publisher timeout, CAS conflicts, lease expiry, malicious writer, crash, and rollback. Until all pass, state stays `LOCAL_CANDIDATE_PERSISTED_NOT_PUBLISHED`.

**Project gates remain:** `Gate A=BLOCKED/UNVERIFIED`, `Trusted Issuer=NOT_DEPLOYED`, `YuantaMC T+1=PAUSED_MANUAL`, `NO ACCOUNT/ORDER`.
