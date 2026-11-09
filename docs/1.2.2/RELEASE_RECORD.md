# CBP 1.2.2 — release record

Status: **RELEASED** on 2026-11-09 for CONTRACT v1.7.1 RC2. v1.2.1 is not moved
and its Release body was not edited.

## Identity

| Item | Value |
| --- | --- |
| Tag | `v1.2.2` → `d4bfefbd5f66c6bbdb74549b37f1f187fcb61924` |
| RC run | `42617444192` |
| Release CI | `42617560868` |
| Release workflow | `42618135714` — preflight / verify-artifact / publish / clean-verify success |
| PyPI | `42618389970` |
| Consumer parity | `42618563357` |

## Artifacts

| Artifact | SHA256 |
| --- | --- |
| wheel | `2b73b4a4c387e4eb0700a339235249d62accfbe0a14c505188c53c484df7d046` |
| sdist | `91974398ea0bc850633919e287f546d48b53f08d0ca57befce3a4a091de092d5` |
| manifest | `228594d07d7a9906280e7b5ff12fa0b1bf70b22ffff4b3d25983a4bcc072a2c6` |
| body (canonical) | `21fbc2bbd36c67261573d784bfcdba73cedf98543f70e42ba85ed20cb50049cd` |

Release assets and PyPI digests match the RC. `gh attestation verify` returns 0
for both files.

## Manifest

```json
{
  "schema_version": "1",
  "artifact_repository": {
    "repository": "JunxiangPan/cbp-action",
    "run_id": "42617444192",
    "artifact_name": "cbp-rc"
  },
  "ci_commit_sha": "d4bfefbd5f66c6bbdb74549b37f1f187fcb61924",
  "body_hash_scope": "base",
  "gate_status": "PASS"
}
```

The real manifest passes the RC2 schema; v1.2.0/v1.2.1 manifests fail as legacy.

## Links

- Release: https://github.com/JunxiangPan/cbp-action/releases/tag/v1.2.2
- PyPI: https://pypi.org/project/cbp-action/1.2.2/
- CBE notification: https://github.com/JunxiangPan/cbe/issues/1

## Boundaries

- `v1.2.1` tag remains `19e44f7`; its Release body is unchanged.
- `v1.2.0` tag remains `5ebd0eb`; its tag/PyPI/Release body are untouched.
- No cbp-dist or local `dist/` artifact was published.
- CBE was notified, not modified.
