# ADP Core bootstrap governance (updated 2026-11-04)

1. The protected Public repository is `Pochun2/ADP-GITHUB-CORE`. No credentials or personal context may be stored on Public branches.
2. Verified history: PR #1 Squash Merge `1e72b3282436872ee1adc707b5daae176dcdc3d4`; PR #2 Squash Merge `024b04ac8216125ba6258556f68d2587fcc6875a`.
3. `main` has active Ruleset `26509773` enforcing PR-only changes, no deletion/force push, strict required `adp-context-suite` from GitHub Actions App `15368`, required human approvals `0` and no bypass.
4. Owner's `ADP-GOV-AUTOMATION-001 v1.0` decision permits separate fixed-hash merge controller to automatically Squash Merge after new-Head CI and policy verification; old blanket third-party review requirement no longer applies to ADP routine work. The decision is specific to ADP, not other governance repos.
5. High-risk workflow and policy-file changes must be fixed-content allowlisted by a separately packaged controller; Candidate PR content is not allowed to weaken that controller, Ruleset or Issuer controls.
6. A1–A4 modules were validated as offline contracts. Canonical protected publication is a separate task, not implied by CI or A4 source code presence.
7. Canonical public Journal contains task metadata only; it never grants autonomous resume, external attestation, Gate A or account/order permissions.
8. Trusted Issuer remains NOT_DEPLOYED. Gate A remains BLOCKED_UNVERIFIED; YuantaMC T+1 PAUSED_MANUAL; NO ACCOUNT_ORDER.
