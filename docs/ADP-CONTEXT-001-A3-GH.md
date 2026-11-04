# CTX-A3-GH: Candidate GitHub Checkpoint Publisher v0.4

**Scope:** GitHub-native versioned PR candidate, fail-closed default. Not trusted publication or independent attestation.

## Inputs
- An A3 local JSONL journal verified through the entire SHA256 chain.
- Separately pinned repository and `origin/main` 40-char SHA.
- Unique, **non-existing** local output directory outside the target repo.

## Operations
1. `python -B -m adp_context.github_checkpoint stage --journal J --repository OWNER/REPO --main-sha SHA --output STAGING` creates exactly two new versionable files: `.adp/checkpoints/PROJECT/TASK/journal.jsonl` and `.adp/checkpoints/PROJECT/TASK/candidate.json`.
2. `python -B -m adp_context.github_checkpoint check --root STAGING --repository OWNER/REPO --main-sha SHA` checks manifest and A3 chain.
3. `tools/Publish-CheckpointDraftPR.ps1` takes `-ContextEngineRoot` pointing to the previously verified A1–A3-GH directory and runs locally with the selected GitHub identity. **Without `-Apply` it performs preflight only**. With `-Apply`, it creates a new branch and Draft PR; never auto-merges or bypasses Rulesets.
4. Remote PR CI and independent human/policy review are separate. Remote `main` change results in BLOCKED, not rebase or auto-retry.

## Threat model and limitations
- SHA256 integrity alone cannot prove trustworthy origin or history immutability. The publisher must be independently protected from PR-submitted code and its credentials.
- A `git push` branch and PR creation are two external side effects, **not an atomic transaction**. If either fails, stop; inspect GitHub state and reconcile manually before retry. No branch overwrite, no force-push.
- `git push` only proves acceptance on a candidate branch. Protected `main` remains unchanged until independent approval. No resume or authorization promotion, no issuance, no trading.
- A3 local directory lock is not a cross-host lease. Cross-host concurrency and GitHub-backed durable canonical state require a later stage: protected merge + independent remote readback + event ownership.
- `candidate.json` describes claims, not evidence. Compaction and CI status must not be embedded as authority.
- GitHub API queries may be rate-limited and privilege-dependent; no token is bundled.
- This package does not grant author GitHub administration rights or place secrets in CI.

## Definition of done
Offline: tests, digest verification, staging, safe preflight. Live: human-authorized Draft PR and protected checks (NOT performed by this offline package). Canonical GitHub checkpoint proof after protected merge remains NOT IMPLEMENTED.
