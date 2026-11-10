# CBP 1.3.0 — self-audit (pre-release)

Status: **READY_FOR_HUMAN_APPROVAL**. No tag, GitHub Release, PyPI upload or
move of any old tag was performed.

## Candidate

Code candidate: `32d00cb87d1e7269175a2d9014241fb211d68411` (`1.3.0-dev`).
PR: https://github.com/JunxiangPan/cbp-action/pull/2

## Acceptance results

| Item | Result |
|---|---|
| Tests | **525 passed**, CI run `42807482183` (ubuntu + windows) success |
| Mutation | **12/12 detected, recall 100%** (`docs/1.3.0/MUTATION_REPORT.md`) |
| Hostile corpus | **50/50 rejected** (`docs/1.3.0/HOSTILE_CORPUS.md`) |
| Contract frozen | 6 tests green: schema SHA, required fields, exit codes, status enum, skip 20%, CBP-BODY-001 |
| Gate self-protection | `quality/GATES.sha256` verifies; tamper tests for coverage/claims/workflow all detected |
| Provenance | schema + offline verifier; **BLOCKED_NO_SIGNING_IDENTITY** (no signature fabricated) |
| Windows | **green**: windows-latest py3.10 + py3.12, CI run `42807482183` |
| AI audit | shadow mode, precision 83.3%, recall 83.3%, not blocking |
| SBOM | CycloneDX, 8 components, full-SHA actions |
| Old behavior | v1.2.2 manifest/schema/exit semantics unchanged; v1.2.0/v1.2.1/v1.2.2 tags and assets untouched |

## P0/P1/P2 mapping

- P0: CBP-MUT-01, CBP-ATK-01, CBP-TRUST-01 (partial: unsigned), CBP-SELF-01,
  CBP-CONTRACT-01.
- P1: CBP-DEP-01 (pins/lock/tag-move/threat model), CBP-WIN-01, CBP-AI-01,
  CBP-THREAT-01.
- P2: CBP-SBOM-01 (SBOM + provenance tooling; release attach only after human
  approval).

## BLOCKED / external

- **BLOCKED_NO_SIGNING_IDENTITY**: no OIDC/sigstore or private key available;
  provenance is unsigned and verifier exits 4. Do not treat as PASS.
- Branch protection / required checks are external GitHub configuration
  (`docs/1.3.0/THREAT_MODEL.md`); the repo cannot prove their state.
- Tag force-push detection is a pure snapshot tool; a real release run must
  supply the expected tag map.
- No AI gate was promoted to blocking.
- CBP is not claimed to be a runtime security boundary.

## Release gate

Per the project rule, release needs **explicit human approval**. This audit and
the PR are the input to that decision; nothing has been tagged or published.
