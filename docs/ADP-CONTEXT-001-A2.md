# ADP-CONTEXT-001-A2 — GitHub read-only observed evidence

Status: **CANDIDATE / OFFLINE_UNIT_TESTED / NOT DEPLOYED**.

## Scope and truthful limits

The module `adp_context.github_evidence` is an **anonymous, read-only** GitHub REST collector for **public repositories**. It gathers five endpoints: repository, `main` branch, PR, repository Ruleset and exact-head Check Runs. It is reusable for arbitrary GitHub repositories through the `Target` arguments; the module does not embed YuantaMC or any private project credentials.

It verifies repository identity, main SHA, PR base/head/repo, selected active Ruleset, strict required checks with pinned GitHub Actions integration ID, complete Check Run response (<=100), duplicate IDs or contexts and each required check's completion/conclusion. It produces a minimal SHA256-digested observation and compares it to A1 checkpoint's repository, base/head SHA, status, blockers and claimed evidence. It treats `observed_at_utc` as reported local time, not a trusted timestamp.

**Non-claims:** API read does not prove authenticated independent source, official policy provenance, GitHub App authorization, source-code correctness, `Gate A` status, trustworthy `EVIDENCED` labels, or permission to `resume`, merge, attest, issue or trade. Observation digest guarantees only byte-consistency of canonical data, not signatures. `policy_ref` inside A1 is an *external* policy reference and is NOT independently verified by this module. The return state on no-drift is `CONSISTENT_OBSERVATION_NOT_AUTHORIZED`.

## Target deployment

A1 is installed in an isolated folder. Copy only new A2 files into its matching relative paths. Do not replace A1 engine or change its prior tests. Run complete `unittest discover` from the A1 root on Windows Python 3.13. The check is **80 tests** (41 original + 39 new), with 1 Windows symlink skip expected. Do not treat a different count as successful without review.

A2 standalone CLI:

```
py -3.13 -B -m adp_context.github_evidence --self-check
py -3.13 -B -m adp_context.github_evidence --repository Pochun2/GOV-TRUSTED-ISSUER --pr 10 --ruleset 26423889
```

The second command uses public, unauthenticated GitHub REST GET and can fail when GitHub API is unavailable, rate-limited, restricted or the PR/Ruleset changes. No credentials are requested. `--checkpoint PATH` adds A1 checkpoint drift checks; A1 synthetic example MUST block against real PR.

Do not paste raw authenticated responses into an LLM. Never grant elevated permissions to a public PR runner. In A3, persist snapshots only in a separately governed repository, with source verification and revocation/retention rules.

## Limitations and C-CTX next steps

- A2: **anonymous** public REST observation only. Independent trusted source/App identity is not established.
- A3: durable append-only checkpoint history, concurrency/lease, HEAD pinning and crash/restart recovery.
- A4: verifiable source registry/compaction and immutable policy reference mapping.
- A5: real two-agent cold start and two-project portability evidence.

Safety invariant: Gate A remains `BLOCKED / UNVERIFIED`, Trusted Issuer `NOT_DEPLOYED`, YuantaMC `T+1 PAUSED_MANUAL`, no account/order operations.
