# ADP Core bootstrap governance

1. Admin/operator must explicitly run `Start-ADPCoreBootstrap.ps1 -Apply` locally. Default is read-only.
2. The remote repository is created with a README-only `main` baseline. It is **not** considered protected before successful active Ruleset creation and readback verification.
3. **Default visibility is Public** for this ADP source-only repository, which is intended to contain no private data. Public visibility does not waive active Ruleset verification. `-Visibility Private` remains an explicit override and may need a paid GitHub plan.
4. Rule for `main`: PR required, strict required status check `adp-context-suite` from GitHub Actions App 15368, no bypass, no force push/delete, zero human reviews (independent policy not yet implemented).
5. All imported context code goes to a feature branch and Draft PR, never directly to `main`. CI must pass before operator-controlled Squash Merge.
6. The 144 tests are offline contracts only; the GitHub Publisher is an operator-invoked candidate path, not a credentialed source of truth or autonomous resume permit.
7. No key/token/price/broker API values in commits, Actions, or SAFE REPORT.
8. Keep Gate A BLOCKED/UNVERIFIED; Trusted Issuer NOT_DEPLOYED; T+1 PAUSED_MANUAL.
