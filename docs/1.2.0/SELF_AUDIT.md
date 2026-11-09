# CBP 1.2.0 — self-audit (release-path fix)

Status: **PASS for re-audit, no publish**. Code candidate `5ebd0eb`, branch
`1.2.0-dev`, PR #1 open. Each item cites the command, file or hash used.

## [1] Candidate identity / repository state — PASS

| Check | Evidence |
| --- | --- |
| Code candidate | `git rev-parse HEAD` → `5ebd0eb` |
| Branch | `1.2.0-dev` |
| PR #1 | `gh pr view 1` → `OPEN`, head `5ebd0eb` |
| CI | run `42605121408` — success |
| Action E2E | run `42605121445` — success |
| v1.2.0 tag | recreated at `5ebd0eb` (old `163f138` deleted; no Release attached) |
| PyPI 1.2.0 | `https://pypi.org/pypi/cbp-action/1.2.0/json` → **404** |
| GitHub Release | `gh release view v1.2.0` → not found |
| v1.1.0 untouched | `git rev-parse 'v1.1.0^{}'` → `f98acf3ed15498b6f16d1a397a5d0f1fe2843fa9` |

## [2] Tests / CI — PASS

- `python -m pytest -q tests` → **421 passed**, 43 warnings.
- Coverage: `python -m coverage run --branch --source=src/cbp,tools -m pytest -q tests`
  then `python -m coverage json` → `security_core=91.64%/90.00%`,
  `cbp=90.56%/80.00%`.
- PR CI run `42605121408`: all jobs success. Release CI run `42605522395`
  (push main at `5ebd0eb`): success. E2E `42605121445`: success
  (15/15 payload + consumer parity).

## [3] Build artifacts / attestation — PASS

| Artifact | SHA256 |
| --- | --- |
| wheel | `188639bb47e5a8940defbdb5ba3c4270ae89ad68503d283b611cb2a00497da2e` |
| sdist | `08392b2af6b3ff29dc21cfe5db0f23d628307ccac06b9035639f32da6343defd` |
| `RC_ASSETS.sha256` | `84041286984161db060e43b8ecf45e0462f1a7ba8a95c777546c8830483dc7c5` |

- Source: RC run `42605114400`, artifact `cbp-rc`.
- `gh attestation verify <wheel>` → exit 0; `gh attestation verify <sdist>` →
  exit 0; subject digests equal the table.
- Local `dist/` is **not** the audit artifact: wheel
  `3fdd809ac0eb6b53ccfffd5029febfc29a27e5b8ca2f9108951b4aeaec26cf9b`, sdist
  `c866d9a5d74aaf15b783aee61ea6c074370b8faf6e5987c313344b3f20534b88`. The
  runbook forbids publishing them.

## [4] Thirteen rules — PASS

- `python -m cbp.cli --root . --v12` → 12 PASS, `blocking_failed=false`.
- 6 blocking: CI-001, VER-001, QA-001, DEBT-001, SIGN-001, WT-001.
- 6 warning: BIN-001, DOC-001, CLAIM-001, COV-001, PROOF-001, SLOP-001.
- Current tips: CBS `dcd96732`, CBE `9a1f5f28`, CBM `8acb628`, CBC `11943f14`.
  CBM CI-001 PASS; no blocking failure on any tip. Matrix in
  `docs/1.2.0/E2E_MATRIX.md`.

## [5] External manifest structure — PASS

| Target | Manifest | Validation |
| --- | --- | --- |
| CBC `11943f14` | `01438d31067f05508454c81af068efc61c9797034c778746b94d77e3de63bac0` | `validate_cbp` → PASS; cbc/cbp/v0.1.0; base; 2 artifacts |
| CBM `8acb628` | `967f15ccd8f222518ceb3c613ffda8d4f2ed04cfede958485f0bd79531e410cb` | `load_report` → PASS; B3 fields present; `gate_status FAIL` preserved |

CBM B3 fields: `body_hash_scope=base`, `release_body_hash`,
`artifact_hashes=2`, `evidence_sha256`. **B2 not claimed** (no real CBE report
with `package_id: "cbm"`). The external-manifest generator code is unchanged
since the CBC/CBM validation; the release-path fix does not touch it.

## [6] Gate provenance — PASS

- CBC gate report `213e8243…`: `package_id=cbc`, `producer_id=cbp`,
  `version=v0.1.0`, PASS.
- CBM gate report `ac4d243b…`: `package_id=cbm`, `producer_id=cbp`,
  `version=v0.1.0`, **FAIL** (`encoding`: invalid UTF-8 in
  `audit/v1.2.0-rc/b5-probe-declared.stdout.txt`).
- The reports are byte-different; the manifests' `gates[]` equal the target
  reports' gates.
- `cbp manifest` with CBC gate + `--package-id cbm` → exit 2, no file.
- `cbp manifest` with `v0.0.0` gate + `--version v0.1.0` → exit 2.
- Tests: `test_gate_report_package_id_must_match_the_target`,
  `test_gate_report_version_must_match_the_target`,
  `test_manifest_gates_come_from_the_gate_report`,
  `test_gate_report_generator_records_target_identity`.

## [7] E2E / docs / release hygiene — PASS

- `E2E_MATRIX.md`: current tips and CBM CI-001 PASS; no blocking failures.
- CBC manifests recorded: `f897bc90…`, `5f952d9b…`, `01438d31…`.
- CBP-DOC-001: CBP v12 PASS; the two problematic references were changed to
  CBE/CBS names, and `.tmp-*` is ignored in every rule walk.
- `RELEASE_RUNBOOK.md` exists and forbids `cbp-dist` and local `dist/`.
- `git ls-files` has no `.tmp*`, `pytest-current` or `__pycache__`.
- No GitHub Release, no PyPI upload; the `v1.2.0` tag was deleted from `163f138` and recreated at `5ebd0eb`; PR #1 open and unmerged.

## [8] Release artifact provenance — PASS

- `release.yml` inputs include `rc_run_id`, `ci_run_id`, `release_tag`,
  `e2e_run_id`, `expected_wheel_sha256`, `expected_sdist_sha256`.
- `publish` downloads `gh run download "$RC_RUN_ID" -n cbp-rc -D rc` and
  `quality-manifest-$CI_RUN_ID`; it does **not** download or publish `cbp-dist`.
- It checks wheel `bdddc74f…` and sdist `3cee5cd8…` against the expected inputs,
  checks `rc/RC_ASSETS.sha256`, then remints the CI manifest from the RC hashes
  (preserving gate/body/commit, recomputing `evidence_sha256`), re-verifies it,
  and asserts `--check-only`; it verifies both RC attestations and uses
  `rc/*.whl` / `rc/*.tar.gz` in `gh release create`.
- `tools/release_preflight.py` runs the same checks without creating a Release:
  correct inputs → 0 / `PREFLIGHT_OK`; wrong wheel or sdist hash → 3; tag/RC/CI
  commit mismatch → 3.
- Tests: `test_release_preflight.py` (5), `test_release_workflow.py` (5),
  `test_remint_manifest.py` (5).
- Actual read-only preflight on 2026-11-09 (exit 0):

```text
PREFLIGHT_OK tag=v1.2.0 ci_run=42605522395 rc_run=42605114400 commit=5ebd0eb wheel=188639bb47e5a8940defbdb5ba3c4270ae89ad68503d283b611cb2a00497da2e sdist=08392b2af6b3ff29dc21cfe5db0f23d628307ccac06b9035639f32da6343defd
```

Raw: `docs/1.2.0/evidence/preflight.txt`.

## [9] Tag / merge / run consistency — PASS

- The Fast-forward path is documented and is the only supported path for this
  RC: delete the stale `v1.2.0` tag, `merge --ff-only 5ebd0eb`, re-tag
  `v1.2.0` at `5ebd0eb`; then
  `tag_commit == rc_run.head_sha == ci_run.head_sha == 5ebd0eb`; the actual
  preflight above printed `commit=5ebd0eb`.
- `release.yml` and the preflight reject any disagreement with exit 3.
- The runbook explicitly forbids tagging a GitHub merge commit and reusing RC
  run `42605114400`; a merge commit would require new CI, new RC, new
  attestation, and a new audit.

## Verdict

All nine items pass for re-audit. The only non-PASS gate result in the train is
CBM's real `encoding FAIL`; it is preserved and must be fixed by CBM, not
waived. Release is approved; this document is the final pre-release self-audit.
