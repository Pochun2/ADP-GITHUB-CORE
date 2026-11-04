# ADP-GOV-AUTOMATION-001 v1.0 — ADP-GITHUB-CORE automation control

**Policy decision date:** 2026-11-04 (Asia/Taipei). **Scope:** `Pochun2/ADP-GITHUB-CORE` daily software development and canonical *metadata* publication. This note records the owner's stated decision; it is not a cryptographic governance signature, and it does not amend any other repository's rules.

## Enforced normal workflow

- No third-party human review requirement for ordinary ADP development. GitHub required review count is 0.
- GitHub `main` remains protected by active Ruleset `26509773`, PR-only changes, non-fast-forward and deletion protection, required `adp-context-suite` check from GitHub Actions app `15368`, with **strict** required checks. Never disable protection, grant bypass or force push to make a change pass.
- A separately packaged, fixed-hash local merge/publish controller performs a fresh GitHub identity and Ruleset readback, exact-base and Head SHA checks, PR changed-file allowlist and blob/tree checks, and new-Head CI verification before authorizing Squash Merge. Candidate code, candidate PR changes and the PR's own CI cannot modify the controller's independently distributed policy.
- Workflow or policy-file changes require an explicit fixed-content allowlist in that external controller, a conservative offline test, and success on the actual new PR Head SHA. This does **not** create an independent Trusted Issuer or authorize self-upgrading policy gates.
- The controller must fail closed on ambiguity, credential failures, SHA drift, CI mismatch, unauthorized file changes, or policy changes. No credential bundles or private keys are stored in this public repository.

## Canonical checkpoint boundary

A hash-chained public Journal and `candidate.json` are **reported task state and versioned bytes**, not automatic resumption permits. Once merged via protected `main` and verified at an immutable Git commit, the checkpoint may be described as `PUBLISHED_PROTECTED_MAIN_READBACK_NOT_ATTESTED`. It is not signed by an external Trusted Issuer and must not elevate itself to `APPROVED`, `RESUMABLE`, `GATE_A_PASS`, or `TRADING_ENABLED`.

A real (rather than synthetic fixture) Journal may start at a new task session using independently read PR/CI/Ruleset observations; past events reconstructed from GitHub may be summarized as **reported history**, not retroactively authored operational logs. Public metadata only; personal context, conversation transcripts, broker prices, account/order payloads, credentials, private absolute paths and raw Windows logs are forbidden.

## Explicitly unchanged

- `GOV-GITHUB`, `GOV-PROTECTED-VALIDATOR` and `GOV-TRUSTED-ISSUER` are **not** re-governed by this ADP decision.
- Trusted Issuer: `NOT_DEPLOYED`. Gate A: `BLOCKED_UNVERIFIED`.
- YuantaMC T+1: `PAUSED_MANUAL`. `NO_ACCOUNT_ORDER` remains mandatory.
- Cross-Agent cold recovery, distributed lease ownership, crash recovery and two-repository migration remain separate acceptance milestones.
