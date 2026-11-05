# ADP-COST-GOV-001 v1.0 — Token usage and cost reporting (2026-11-05)

**Owner-approved additive ADP rule.** Scope: `Pochun2/ADP-GITHUB-CORE` and its external C1/Codex controllers. This rule is subordinate to the already protected GitHub PR/Strict CI/zero-review rules and grants no new operational authority.

## Mandatory run-close evidence — success and failure

1. Every automated run **MUST** produce a SAFE execution report with a **cost section**, including failures, retries, cold-recovery sessions, and subsequent Codex invocations. Report `input_tokens`, `cached_input_tokens`, `uncached_input_tokens`, `output_tokens` (including reasoning), `reasoning_output_tokens` (a subset, not an addition), and `total_tokens = input + output`.
2. Each Codex model invocation MUST be registered **before execution** in a local, append-preserved invocation manifest. Use a new `--ephemeral` thread and capture raw `codex exec --json` output locally. The parser must match each invocation to exactly one completed turn. Reused event files, missing usage events, unsupported models, contradictory or invalid numbers MUST result in `COST_REPORT_GATE=BLOCKED_USAGE_UNVERIFIED`; never estimate a missing Token count as zero.
3. Every run report MUST include **Codex credit-equivalent estimate**, **API USD-equivalent estimate**, a pinned `model`, pricing date/source, ratecard SHA256, and `ACTUAL_BILLED_USD=UNKNOWN_NOT_IN_CLI_TELEMETRY` (unless independent billing evidence becomes available). The dollar equivalent is a **comparison metric, not the user's bill**; ChatGPT sign-in is governed by plan allowances and credits rather than API token prices.
4. Costs MUST aggregate **all invocation attempts** (including bounded repair attempts and fresh-agent read-only recovery), not just accepted output. Incomplete/crashed turns MUST be marked as unverified even when some completed-turn Tokens are available.
5. The **minimal sufficient cost management evidence** for an automated run is complete measured Token telemetry plus pinned, reproducible credit and currency equivalent estimates with actual-charge uncertainty disclosed. No additional PostgreSQL ledger, FX tracking, second host or third-party reviewer is required merely to satisfy this rule.
6. The external controller may authorize a protected merge only after complete cost telemetry from the pre-merge model invocations. **Final run-close** after all post-merge invocations must again pass the cost report gate. If a post-merge recovery fails, preserve the actual merge SHA and `MERGED_RECOVERY_PENDING`; do not claim full C1 PASS or attempt to merge again.
7. Keep raw prompts, JSONL events, account usage, model completion text, checkout paths and identity details **local-only**. Public GitHub may contain policy and code but no raw per-user telemetry; the clipboard contains only redacted aggregate statistics.

## Pricing and exactness

- Official Codex/ChatGPT credit schedule: https://learn.chatgpt.com/docs/pricing
- Official API-equivalent USD reference (Standard, short-context): https://developers.openai.com/api/docs/pricing
- The local ratecard pins a model and vintage, not a live invoice. The prices can change; update through protected PR and an independent controller. Do not silently fall back to a different model.
- Cache-write duration/tier is not evident in JSONL event usage. If `cache_write_input_tokens > 0`, the API USD field is only a **base equivalent**, flagged `COST_API_USD_ESTIMATE_COMPLETE=FALSE`; it is not a complete API billing estimate.
- Codex API USD equivalent and ChatGPT credits are **distinct measures**. They must not be added together or represented as two actual charges.

## Security invariants

This policy does **not** change Ruleset `26509773`, required `adp-context-suite` App `15368`, zero third-party human Approve, Gate A (`BLOCKED_UNVERIFIED`), Trusted Issuer (`NOT_DEPLOYED`), YuantaMC T+1 (`PAUSED_MANUAL`), or `NO_ACCOUNT_ORDER`.

Implementation: `adp_context/cost_accounting.py`, pinned `config/ADP-COST-RATECARD-20261105.json`, permanent tests. Integrate the external cost gate into the next C1 continuous controller before it gains unattended execution privileges.
