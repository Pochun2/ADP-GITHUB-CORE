# CTX-A4-PUBLISH v1.0 — protected metadata publication plan

**Task:** `ADP-GITHUB-CORE / CTX-A4-PUBLISH`.

This PR proposes the first **real-task-originated** checkpoint for ADP itself: a new, single-entry A3 JSONL Journal assembled during the 2026-11-04 publication task from currently observed public GitHub PR and Ruleset evidence. It is *not* a fabricated reproduction of logs from earlier runs. Historical PR merges are marked as observed/reported history and linked by immutable merge SHAs. The snapshot records unresolved blockers explicitly.

The committed public files are `.adp/checkpoints/ADP-GITHUB-CORE/CTX-A4-PUBLISH/journal.jsonl` and `candidate.json`, accompanied by this validator, new tests and policy/evidence descriptions. No private user context is stored. The `candidate.json` state intentionally remains `CANDIDATE_NOT_GITHUB_PUBLISHED_NOT_ATTESTED` after merge: it is an immutable **description of the candidate at authoring time**, not a publication-attestation token. Remote publication status is an *external observation* bound to the resulting protected main commit.

## Required gates

1. Independent fixed-hash controller validates repo identity, exact `main` baseline (`024b04ac8216125ba6258556f68d2587fcc6875a`), PR #1/#2 true merge SHAs, protected Ruleset `26509773`, zero required reviews and strict required check App `15368`.
2. Run all existing 177 contract tests plus the new 24 tests (201 total), verify A3 Journal/Candidate and A4 canonical read contract; allow only explicitly pinned source/document/workflow/checkpoint files.
3. Push a new feature branch *without force*, create a normal Ready PR, wait for all six GitHub Actions checks on that exact new PR Head. Failure, timeout or changed SHA terminates with no merge.
4. An independently packaged merge controller re-verifies Ruleset, main lease, exact source diffs, CI app identity and expected Head SHA, then requests Squash Merge.
5. Independently read back the new `main` Git commit SHA and source Git Tree equivalence, and the committed Journal/Manifest bytes at the fixed immutable commit. A new disposable clone rechecks the snapshot. Log the real merged SHA only after these succeed.

## Trust boundary and follow-on

Successful publication qualifies only `PUBLISHED_PROTECTED_MAIN_READBACK_NOT_ATTESTED` for *byte-level versioned task state*. External Trusted Issuer signature/attestation, Gate A approval and autonomous Cross-Agent recovery remain absent. The new Journal is explicitly `BLOCKED`, with Gate A/Issuer/Cross-Agent blockers. YuantaMC T+1 is paused and all Account/Order operations remain disabled.

Next task: independently recover fixed-SHA public context from a separate Agent/session and host, test CAS/Lease conflicts, policy drift, stale evidence, crash/replay and failure response; only then may CTX-A5 be assessed. No automatic trading or privileged operation is coupled to this publication.
