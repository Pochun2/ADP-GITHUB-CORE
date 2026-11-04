# ADP-CONTEXT-001 v0.1 | 2026-11-04

**Status: OFFLINE_PROTOTYPE; NOT_DEPLOYED; NOT_APPROVED AS EXTERNAL TRUST ROOT.**

## Purpose
Durable, portable context from GitHub and locally hash-pinned inputs, not model weights or chat transcripts. This package is cross-project by contract; it holds no YuantaMC API logic. It intentionally does NOT use remote GitHub credentials or call GitHub APIs. Its `remote` argument is explicitly a **synthetic, untrusted fixture** and cannot authorize work or certify GitHub state.

## Reuse of historical work
Incorporates concepts from `YMC-CONTINUITY-001_PROPOSED.md` (2026-10-22): authority hierarchy, Capsule, decision ADRs, evidence strength, known unknowns and fail-closed conflicts. Earlier document was PROPOSED and is **not** deemed approved by this package.

## Contract
- `adp-context-v1` checkpoint with repository, baseline/head immutable SHAs, policy reference, status, completed/pending/blockers, decisions, evidence, source digests, UTC verified-at claim, next action, non-negotiables.
- `validate_checkpoint` rejects extra fields, invalid hashes, duplicated refs/steps, sensitive strings and impossible status labels.
- `validate_decisions` requires explicit supersession chain; an approved decision must have an evidence-designated source reference (but this is still only untrusted metadata).
- `verify_local_sources`: sha256 of locally available context source bytes. This only proves byte consistency, never author/authenticity.
- `compact`: deterministic, complete critical fields, claims clearly labeled; no probabilistic LLM compression.
- `retrieve`: deterministic lexical file-locator search over pinned reference index; NOT full-text/RAG yet.
- `resume_preview`: compares a checkpoint with synthetic GitHub-shaped observation. Rejects drift, unresolved blockers, mismatched policy and missing or untrusted evidence references. A positive result is **READY_FOR_HUMAN_OR_EXTERNAL_POLICY_REVIEW**, NOT permission to resume.

## Required next integration (not implemented)
1. GitHub read-only collector, explicit pagination and freshness validation against live APIs.
2. Protected policy pin and remote evidence origin verification outside the candidate PR.
3. Append-only task checkpoint journal with idempotent workflow run IDs and concurrency lease/recovery.
4. Optional, bounded LLM semantic compaction / on-demand retrieval with source coverage tests.
5. Cross-Agent cold-start acceptance: independent workers / two repos / forced interruption and replay.
6. GitHub PR-based governance, Windows 3.13 regression and hosted CI; no automated privileged merge or issuance until independently authorized.

## Security invariants
- Gate A = BLOCKED/UNVERIFIED; Trusted Issuer = NOT_DEPLOYED.
- YuantaMC T+1 = PAUSED_MANUAL; NO ACCOUNT / NO ORDER.
- Never publish real tokens, passwords, PFX/private keys, broker prices, raw identifiers or raw logs.
- `context_sources` SHA is an index to bytes, not a trust signature; source pin should originate outside candidate PR.
- The CLI never writes to GitHub, never mints tokens, never changes Ruleset and never certifies an acceptance gate.

## Example execution
```
python -B -m unittest discover -s tests -p test_engine.py -v
python -B -m adp_context self-check
python -B -m adp_context validate --checkpoint examples/sample.checkpoint.json
python -B -m adp_context capsule --checkpoint examples/sample.checkpoint.json --decisions examples/sample.decisions.json
python -B -m adp_context resume --checkpoint examples/sample.checkpoint.json --decisions examples/sample.decisions.json --remote examples/sample.remote.fixture.json
```

The synthetic `resume` command intentionally exits 2 / BLOCKED in example because Gate A is blocked.
