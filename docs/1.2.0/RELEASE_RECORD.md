# CBP 1.2.0 — release record

Status: **RELEASED** on 2026-11-09. GitHub Release and PyPI both use the same
audited RC bytes. No cbp-dist or local `dist/` artifact was published.

## Identity

| Item | Value |
| --- | --- |
| Tag | `v1.2.0` → `5ebd0eb52844e2a7b51f6990fb30d1d5005098a9` |
| `main` | `5ebd0eb52844e2a7b51f6990fb30d1d5005098a9` |
| RC run | `42605114400` (`cbp-rc`) |
| Release CI (manifest) | `42605522395` (push `main` at `5ebd0eb`) |
| Release workflow | `42606027527` — preflight / verify-artifact / publish / clean-verify all success |
| PyPI workflow | `42606298206` — success |
| Consumer parity | `42606464772` — success, `CONSUMER_VIEW_OK version=v1.2.0` |

## Artifacts

| Artifact | SHA256 |
| --- | --- |
| wheel | `188639bb47e5a8940defbdb5ba3c4270ae89ad68503d283b611cb2a00497da2e` |
| sdist | `08392b2af6b3ff29dc21cfe5db0f23d628307ccac06b9035639f32da6343defd` |
| `quality-manifest.json` | `4b310cf3b752a8be09431f9475198219c9d7eeecb7548dd7db79b6750d89ac05` |
| `RELEASE_ASSETS.sha256` | `b48ff6aef77483ea349a2b39f8daff4e3a55e66715a42be8ae54cad523bce066` |

The GitHub Release assets and the PyPI files have the same wheel/sdist digests.
`gh attestation verify` returns 0 for both.

## Reminted manifest

The release manifest is the CI manifest reminted from the RC bytes:

```text
ci_run_id=42605522395 ci_commit_sha=5ebd0eb...
artifact_hashes:
  cbp_action-1.2.0-py3-none-any.whl = 188639bb...
  cbp_action-1.2.0.tar.gz           = 08392b2a...
gate_status=PASS body_hash_scope=base
```

`artifact_hashes` match the published assets; `evidence_sha256` is the
recomputed self-hash. No cbp-dist hash appears in the release manifest.

## Release body

`QUALITY_COUNTS: 9/9`. The published body is generated from the audited RC wheel.

## Links

- GitHub Release: https://github.com/JunxiangPan/cbp-action/releases/tag/v1.2.0
- PyPI: https://pypi.org/project/cbp-action/1.2.0/
- Release run: https://github.com/JunxiangPan/cbp-action/actions/runs/42606027527
- PyPI run: https://github.com/JunxiangPan/cbp-action/actions/runs/42606298206

## Boundaries

- CBS/CBE/CBM/CBC were not modified.
- CBM's target `encoding FAIL` remains a CBM finding; B2 is still not claimed.
- Old tag `163f138` and earlier RC artifacts are superseded.
