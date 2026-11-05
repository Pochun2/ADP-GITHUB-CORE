# ADP C1-U3 — Post-merge task completion and permanent regression

Issue: `#8` (`C1-U22-TOKEN-BUDGET`). Prior Codex-authored source was merged through PR #9 on protected `main` at `783697370a8a2a38951a4da9e09ec600a618ff45`.

This change adds **permanent offline Token Budget regression tests**, a **pure decision contract** for Issue completion and negative-path tests, and updates the strict GitHub CI test-count guard. It does not redeploy an Agent, change pricing, modify the prior Journal, enable a scheduler, or grant any merge/Issue write authority to repository code.

The separately distributed external U3 publisher must independently verify: original PR #9 merge/tree, source SHA256 `d6f210c102cb1bebea59da21d10226f1f2d7706dbe6b1bba07824f450617a2a5`, live Issue #8 body and label, Ruleset `26509773`, exact CI App `15368`, strict CI checks on the new PR head, exact five-file scope and protected Squash Merge. **Only after** the protected main readback of all five files can it close Issue #8. If a process stops after merge but before closing the Issue, the next invocation must read GitHub's actual state and reconcile without a second merge. If the Issue is already closed with unchanged verified history, there must be no second PATCH.

Public Checkpoints remain `NOT_ATTESTED` and never act as bearer authorization; prior candidate Journals are deliberately not retroactively upgraded. This is a single-run, owner-invoked controller; no unattended schedule. No Trusted Issuer or Gate A elevation. YuantaMC `T+1=PAUSED_MANUAL` and `NO_ACCOUNT_ORDER` remain enforced. Zero Codex invocations in this deterministic regression-publication operation; report zero model Tokens/cost for this operation only.
