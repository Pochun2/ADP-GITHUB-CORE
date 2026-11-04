# CTX-A4 — protected canonical checkpoint read contract

## Historical milestone and immutable facts

A4 offline read contract was merged as ADP PR #2 on 2026-11-04. Verified protected-main merge SHA: `024b04ac8216125ba6258556f68d2587fcc6875a`. Earlier notes about a README-only `main` or unmerged PR #1 are superseded.

`adp_context/canonical_checkpoint.py` reads an A3-GH candidate under `.adp/checkpoints/<project>/<task>/` and checks the hash-chained Journal and a separately supplied GitHub observation. It returns `BLOCKED_CANONICAL_RECONCILIATION` or `PROTECTED_COMMIT_REPORTED_REVIEW_REQUIRED_NOT_AUTHORIZED`. That original naming is a **code-level historical state**, not a requirement for a third-party reviewer under the current ADP-GOV-AUTOMATION-001 policy.

The verifier **cannot publish, approve, merge, issue, attest or authorize resume**. It trusts neither caller-supplied observation JSON nor synthetic fixtures.

## Subsequent canonical publication proposal

`CTX-A4-PUBLISH` is a new, separately controlled GitHub PR and public Journal record. It must pass GitHub strict required CI, zero-review governance, fixed SHA/Policy controller, protected-main readback and independent byte verification. The state of its `candidate.json` remains a candidate claim even after protected publication; only separately collected immutable-main evidence can establish publication.

## Persistent limits

- No independent Trusted Issuer signature or key (`NOT_DEPLOYED`).
- Gate A `BLOCKED_UNVERIFIED`; Cross-Agent recovery `NOT_TESTED` until actual two-agent acceptance.
- Public repository has no private context, credentials, broker quotes, accounts/orders, user paths or raw logs.
- T+1 `PAUSED_MANUAL`, NO ACCOUNT/ORDER.
