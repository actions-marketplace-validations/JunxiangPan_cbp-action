# CBP 1.2.0 release runbook

Status: **NOT EXECUTED**. Release requires explicit human approval. No tag, no
PyPI upload, no GitHub Release, and no PR merge has been performed.

## Authoritative RC artifact

Only the `cbp-rc` bundle from the audit RC run may be released. The CI
`cbp-dist` bundle is **not** a release input; it is used only for the
quality-manifest.

| Item | Value |
| --- | --- |
| Candidate commit | `163f138` |
| RC run | https://github.com/JunxiangPan/cbp-action/actions/runs/42603720434 |
| CI run (manifest) | https://github.com/JunxiangPan/cbp-action/actions/runs/42604400520 |
| e2e run | https://github.com/JunxiangPan/cbp-action/actions/runs/42603730815 |
| Artifact | `cbp-rc` |
| wheel | `cbp_action-1.2.0-py3-none-any.whl` — `bdddc74f828de7ae1beae3b484ece5ddb2986620585985b0f24c9b6897701e16` |
| sdist | `cbp_action-1.2.0.tar.gz` — `3cee5cd8309533d3b809cdadeea7dd73cf2fc32dda268f9b912c0dfe751335b1` |
| `RC_ASSETS.sha256` | `fdeeab8283847dfcdc1f5f592fc49a394696ee2702ed23dfe0857d14f9370603` |

The tag, RC run head and CI run head must all be candidate `163f138`. Any
mismatch is exit 3 and no Release is created.

## Preflight (no Release, no PyPI)

The tag does not exist yet, so pass `--tag-commit`; the tool resolves the
abbreviated SHA and compares it with the RC/CI heads.

```bash
python tools/release_preflight.py \
  --rc-run-id 42603720434 \
  --ci-run-id 42604400520 \
  --tag v1.2.0 \
  --tag-commit 163f138 \
  --expected-wheel-sha256 bdddc74f828de7ae1beae3b484ece5ddb2986620585985b0f24c9b6897701e16 \
  --expected-sdist-sha256 3cee5cd8309533d3b809cdadeea7dd73cf2fc32dda268f9b912c0dfe751335b1 \
  --e2e-run-id 42603730815 \
  --repository JunxiangPan/cbp-action
```

Actual output on 2026-11-09:

```text
PREFLIGHT_OK tag=v1.2.0 ci_run=42604400520 rc_run=42603720434 commit=163f138 wheel=bdddc74f828de7ae1beae3b484ece5ddb2986620585985b0f24c9b6897701e16 sdist=3cee5cd8309533d3b809cdadeea7dd73cf2fc32dda268f9b912c0dfe751335b1
```

Raw copy: `docs/1.2.0/evidence/preflight.txt` (exit code 0).

Failure handling:

- `TAG_NOT_FOUND` / `rev-parse` failure: confirm `--tag-commit 163f138`; do not
  create a tag just to make preflight pass.
- hash mismatch: stop. Do not edit the expected hash to make it pass.
- RC/CI commit mismatch: stop. Do not tag.
- quality-manifest missing: stop and inspect CI run `42604400520`.

## HUMAN ONLY — release commands (not executed)

```bash
# v1.2.0 currently points at 8431712, which has no Release and no reminted
# manifest. The human approved deleting and recreating it at 163f138.
git tag -d v1.2.0
git push origin :refs/tags/v1.2.0

git checkout main
git merge --ff-only 163f138
git push origin main

git tag -a v1.2.0 163f138 -m "CBP v1.2.0"
git push origin v1.2.0

gh workflow run release.yml \
  --repo JunxiangPan/cbp-action \
  --ref v1.2.0 \
  -f rc_run_id=42603720434 \
  -f ci_run_id=42604400520 \
  -f release_tag=v1.2.0 \
  -f e2e_run_id=42603730815 \
  -f expected_wheel_sha256=bdddc74f828de7ae1beae3b484ece5ddb2986620585985b0f24c9b6897701e16 \
  -f expected_sdist_sha256=3cee5cd8309533d3b809cdadeea7dd73cf2fc32dda268f9b912c0dfe751335b1
```

`release.yml` downloads `cbp-rc`, verifies both hashes and `RC_ASSETS.sha256`,
requires `tag == RC head == CI head`, and then **remints** the CI manifest:
`artifact_hashes` are replaced with the RC wheel/sdist digests while the gate
report, body hash and commit fields are preserved; `evidence_sha256` is
recomputed. The reminted manifest is verified again and `--check-only` asserts
it equals the RC hashes. Only then does it verify the RC attestations, generate
the body from the RC wheel, and create the Release from `rc/*`. Any mismatch
exits 3 before `gh release create`. PyPI publishes the Release assets.

### Merge-commit alternative (not recommended)

If a GitHub merge commit is used, its SHA differs from `163f138`. The RC run
`42603720434` can no longer be used. You must run CI and RC again on the merge
commit, re-attest, re-run preflight, and have the result re-audited. Do not tag a
merge commit and reuse an older RC run.

## Forbidden artifacts

Do not upload, tag, or attest these:

```text
local dist wheel  3fdd809ac0eb6b53ccfffd5029febfc29a27e5b8ca2f9108951b4aeaec26cf9b
local dist sdist  c866d9a5d74aaf15b783aee61ea6c074370b8faf6e5987c313344b3f20534b88
```

### Superseded RC artifacts

| Wheel | Sdist | Status |
| --- | --- | --- |
| `9807d02c…` | `7da76e16…` | superseded by manifest remint |
| `dafc9662…` | `e58524e7…` | superseded by the preflight short-SHA fix |
| `ee365cdd…` | `870b5286…` | superseded by the release-path fix |
| `9469a8e9…` | `98b8916c…` | superseded |
| `589ab147…` | `4415f229…` | superseded |
| `40b0f5f8…` | `e30fa831…` | early RC |
| `06f8c3d3…` | `49592d6b…` | early RC |

## Release steps (do not execute now)

1. Human re-audit of `SELF_AUDIT.md`, `AUDIT_PACKAGE.md`, `RULE_MATRIX.md`,
   `E2E_MATRIX.md`, `EXTERNAL_MANIFEST.md`, the evidence bundle, and this
   runbook.
2. Explicit human approval to release.
3. Run the HUMAN ONLY Fast-forward sequence above so the tag commit is
   `163f138`.
4. Run the preflight command; require `PREFLIGHT_OK`.
5. Dispatch `release.yml` with the exact inputs above.
6. Verify the Release assets equal `bdddc74f…` / `3cee5cd8…`, the manifest `artifact_hashes` match them, PyPI digests match
   the Release assets, and both `gh attestation verify` calls pass.
7. Consumer order: upgrade CBM and CBC consumers first (they need
   `body_hash_scope: "base"`), then CBE/CBP producers, then the CBS
   orchestrator. Do not emit 1.2.0 manifests before consumers can parse them.

## Approval

Release still requires explicit human approval. This runbook is documentation
only; none of the steps above has been executed.
