# CBP 1.2.1 — release record

Status: **RELEASED** on 2026-11-09. GitHub Release and PyPI use the same audited
RC bytes; v1.2.0 is untouched.

## Identity

| Item | Value |
| --- | --- |
| Tag | `v1.2.1` → `19e44f79ce5a0737d3522bb2bc6dbafa0835aab0` |
| RC run | `42612084193` |
| Release CI | `42612217101` (push `main` at `19e44f7`) |
| Release workflow | `42612756724` — preflight / verify-artifact / publish / clean-verify success |
| PyPI workflow | `42612997685` — success |
| Consumer parity | `42613115587` — `CONSUMER_VIEW_OK version=v1.2.1` |

## Artifacts

| Artifact | SHA256 |
| --- | --- |
| wheel | `b30b78e876b1c13be4472e7a6e477f8e45466947da9ac306184cfa55427b1718` |
| sdist | `08103c217a6eb19d4393f4ebee03a0d0ded25f0ca16d900e1f7f5271f5a95f59` |
| `quality-manifest.json` | `2fa04a6cbaee0d6e90b4af163e3a0fbc5c3c0ed242d079264eb89a825f60b48e` |
| final body (canonical) | `561c4767b5ce89d4151760666f9866f2cc0948aa938cc98b981282d242d28fbe` |
| `RELEASE_ASSETS.sha256` | `5ddd73568fad2d3088472d272e07c6f542bf84c33a4f029b27426abf84c0e89f` |

Release asset digest, PyPI digest and RC digest are identical for both files.
`gh attestation verify` returns 0. Release body QUALITY_COUNTS: 9/9.

## Body binding

The v1.2.0 mismatch is recorded in `docs/1.2.0/ERRATA.md`. For v1.2.1 the
release job generated `RELEASE_BODY.md`, reminted the manifest with
`--release-body`, re-verified it, and published that same body. The GitHub API
body hashes to `561c4767…`, equal to the manifest. CBP-BODY-001 passes on the
v1.2.1 fixture and fails on the v1.2.0 fixture.

## Links

- Release: https://github.com/JunxiangPan/cbp-action/releases/tag/v1.2.1
- PyPI: https://pypi.org/project/cbp-action/1.2.1/
- Release run: https://github.com/JunxiangPan/cbp-action/actions/runs/42612756724
- PyPI run: https://github.com/JunxiangPan/cbp-action/actions/runs/42612997685

## Boundaries

- `v1.2.0` tag remains `5ebd0eb`; PyPI `1.2.0` files remain; its Release body
  was not edited.
- No cbp-dist or local `dist/` artifact was published.
- CBS/CBE/CBM/CBC were not modified.
- CBM's own `encoding FAIL` remains a CBM finding.
