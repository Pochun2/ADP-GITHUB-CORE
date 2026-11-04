# CTX-A4 — Protected canonical checkpoint read contract (offline phase)

## Explicit trust claim

This is **not** canonical publication. The GitHub `main` branch of Pochun2/ADP-GITHUB-CORE remains README-only at the pinned observed baseline when this stage was authored. PR #1 is DRAFT and is not merged. No canonical checkpoint exists on protected main.

The new pure verifier `adp_context/canonical_checkpoint.py`:

1. Reads a committed A3-GH candidate from `.adp/checkpoints/<project>/<task>/candidate.json` and `journal.jsonl`.
2. Verifies the complete Journal hash chain, original project/task/policy identity, candidate digest, committed path and checkpoint baseline.
3. Examines separately obtained GitHub-reported metadata for repo, commit, main ancestry, active ruleset, no bypass actors, mandatory `adp-context-suite` result and GitHub Actions app ID 15368.
4. Reports either `BLOCKED_CANONICAL_RECONCILIATION` or `PROTECTED_COMMIT_REPORTED_REVIEW_REQUIRED_NOT_AUTHORIZED`.
5. **Never** grants resume, trust certification, merge, deployment, issuer keys, trading, account or order operations.

### Limitations

- Input observation is **not cryptographic proof** and may be forged by a caller. The first phase therefore only reports evidence requiring independent review.
- A Git commit ID pins bytes, but does not prove that a protected main branch contains those bytes or that branch protection was enforced at time of publication.
- Canonical publication requires: independently approved PR; protected-main merge; readback via fixed Git SHA; independently checked main ancestry and Ruleset; checkpoint snapshot reconstruction; crash/retry/competing agents; fresh-host round trip.
- The GitHub Actions App (15368) is not the independent Trusted Issuer.
- Public repository: **only synthetic test checkpoint**. Do not upload personal context, proprietary data, accounts, prices, credentials, private paths or full conversation history.
- Gate A `BLOCKED/UNVERIFIED`, Trusted Issuer `NOT_DEPLOYED`, YuantaMC `T+1=PAUSED_MANUAL`, `NO ACCOUNT/ORDER` persist.

## Acceptance

`A4_OFFLINE_CONTRACT_PASS` after local full test suite + GitHub independent read-only preflight. `CTX-A4_CANONICAL_CHECKPOINT` remains PENDING until protected-main publication and cold recovery are demonstrated.
