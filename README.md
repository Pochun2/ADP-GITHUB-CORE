# ADP-GITHUB-CORE — protected portable context engine

Repository `Pochun2/ADP-GITHUB-CORE` implements A1–A4 GitHub context continuity, hash-chained candidate Journals, fail-closed observation contracts, and an offline canonical publication verifier. A1–A3-GH entered protected `main` via PR #1 (`1e72b3282436872ee1adc707b5daae176dcdc3d4`); A4 via PR #2 (`024b04ac8216125ba6258556f68d2587fcc6875a`).

## Governance

`docs/ADP-GOV-AUTOMATION-001.md`: no third-party Approve for routine ADP changes; protected PR, strict Required CI (`adp-context-suite`, GitHub Actions App `15368`), external fixed-content controller and Squash Merge. Do not weaken Ruleset `26509773`. Governance changes in this repo never authorize changes to other GOV repositories.

## Run offline tests

`python -B -m unittest discover -s tests -v`

The CTX-A4-PUBLISH proposal increases the test count to **201**, with 24 additional negative/positive publication integrity tests and an offline validator invoked by the Required CI workflow. `source` integrity and GitHub observation are **not Issuer attestation**.

Verify the first public-task candidate locally from the repository root:

`python -B -m adp_context.canonical_publication --repo-root . --repository Pochun2/ADP-GITHUB-CORE --baseline-sha 024b04ac8216125ba6258556f68d2587fcc6875a`

The committed `candidate.json` remains labeled an untrusted candidate. A separate protected-branch, fixed-SHA readback can establish versioned publication of those bytes, not automatic recovery authorization. See `docs/ADP-CANONICAL-PUBLICATION-001.md`.

**Security:** No Trusted Issuer key or independent certificate deployed; Gate A BLOCKED_UNVERIFIED, T+1 PAUSED_MANUAL, NO ACCOUNT/ORDER. Cross-Agent recovery remains untested.
