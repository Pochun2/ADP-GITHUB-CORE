# ADP C1-U1 — Minimal issue intake (development, not deployed)

C1 deterministic 2-round PR E2E and one bounded Codex-authored E2E are successful. The next stage is **bounded Issue selection and unattended-loop readiness**, not PostgreSQL or dual-host coordination.

`adp_context/c1_issue_intake.py` enforces untrusted Issue JSON data, exact `adp-agent-ready` label, repository, protected baseline SHA, an agreed one-file pure-Python task kind, exact task identifier and independent task-spec digest. Multiple eligible Issues are an ambiguity and fail closed. The selector returns only a **read-only candidate** without merge or Agent authority.

The public repository does **not** include an unattended scheduler, privileged controller, model credentials, task dispatch, automated requeue, or service account. Do not interpret `READY_FOR_EXTERNAL_BOUNDED_CONTROLLER_REVIEW` as authority for GitHub writes.

Next development steps: (1) prove issue-to-Agent prompt contract in a separate fixed-content control process; (2) register every Codex invocation in a local cost manifest before executing; (3) run independent code acceptance and required CI, then protected merge; (4) cold-read the new protected checkpoint; (5) require final token/cost SAFE report even on a partial failure; (6) test crash replay and issue deduplication before enabling a schedule.

Source code and tests are security boundaries, not cryptographic attestations.

Permanent regression: `tests/test_c1_commit_lineage.py` adds 20 tests for PR #6 Codex-authored source. Total C1-U1 new tests: 91; required GitHub suite count: 292.
