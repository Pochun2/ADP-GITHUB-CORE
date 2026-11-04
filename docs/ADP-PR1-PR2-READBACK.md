# ADP-GITHUB-CORE protected-main evidence index

**Observation:** 2026-11-04, through GitHub API GET and the local Windows SAFE reports (the latter are user-provided claims, not Issuer signatures). This document summarizes publicly observable GitHub facts, not an immutable third-party attestation.

| Item | Observed |
|---|---|
| Repository | `Pochun2/ADP-GITHUB-CORE` (Public) |
| PR #1 | `MERGED` to `main`; merge commit `1e72b3282436872ee1adc707b5daae176dcdc3d4` |
| PR #2 | `MERGED` to `main`; merge commit `024b04ac8216125ba6258556f68d2587fcc6875a` |
| PR #2 Head | `cf6c1f6592f13707e9be2928003716e4dc154448` |
| PR #2 source and merged Git Tree | `002f4f2b9da5c9af453ae4f0c7f21116c6659b19` |
| PR #2 changed files | Exactly five CTX-A4 files |
| PR #2 new Head CI | Six completed successful GitHub Actions checks, App ID `15368` |
| Ruleset | `26509773`, active; strict required `adp-context-suite`; review count `0` |

Public links: https://github.com/Pochun2/ADP-GITHUB-CORE/pull/1 and https://github.com/Pochun2/ADP-GITHUB-CORE/pull/2 .

**Limitations:** The statements must be checked again when publishing a new checkpoint because main and policy may change. GitHub API consistency cannot prove external issuer authenticity, and passed CI does not authorize cross-agent resumption or trading.
