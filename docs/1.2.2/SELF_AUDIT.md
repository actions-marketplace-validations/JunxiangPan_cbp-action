# CBP 1.2.2 — self-audit

Status: **PASS — released** against CONTRACT v1.7.1 RC2 (`contract/v1.7.1` at
`6835789`, NOT FROZEN).

## Candidate and runs

| Item | Value |
| --- | --- |
| Candidate / tag | `d4bfefbd5f66c6bbdb74549b37f1f187fcb61924` (`v1.2.2`) |
| RC run | `42617444192` (`cbp-rc`) |
| Release CI | `42617560868` (push `main`) |
| E2E | `42617990302` |
| Release workflow | `42618135714` — all four jobs success |
| PyPI workflow | `42618389970` |
| Consumer parity | `42618563357` — `CONSUMER_VIEW_OK version=v1.2.2` |

## RC2 conformance

- `schema_version` is the string `"1"`.
- `artifact_repository` is the object
  `{repository: JunxiangPan/cbp-action, run_id: 42617444192, artifact_name: cbp-rc}`.
- `ci_commit_sha` = `d4bfefbd5f66c6bbdb74549b37f1f187fcb61924` (40 lowercase hex).
- `gate_status=PASS`; `NOT_UPLOADED` is accepted by the schema and is not PASS.
- `body_hash_scope=base`.
- Real v1.2.2 manifest passes `schemas/manifest.schema.json` (RC2 schema).
- Real v1.2.0 and v1.2.1 manifests are negative fixtures and **fail** the RC2
  schema because `artifact_repository` is a string.

## Body binding

The generator emits `<!-- CBP-BODY-BASE-END -->`; `release_body_hash` covers the
canonical bytes before it. CBP-BODY-001 remains blocking.

- Final body canonical hash: `21fbc2bbd36c67261573d784bfcdba73cedf98543f70e42ba85ed20cb50049cd`.
- The GitHub Release body fetched after publication hashes to the same value.
- CBP-BODY-001: v1.2.0 fixture **FAIL**, v1.2.2 fixture **PASS**.

## Tests

**444 passed**. Schema tests: RC2 manifest accepted; v1.2.0 and v1.2.1 real
manifests rejected. `test_remint_manifest` covers body recompute, missing body
exit 2, and artifact hash preservation.

## Artifacts

| Artifact | SHA256 |
| --- | --- |
| wheel | `2b73b4a4c387e4eb0700a339235249d62accfbe0a14c505188c53c484df7d046` |
| sdist | `91974398ea0bc850633919e287f546d48b53f08d0ca57befce3a4a091de092d5` |
| manifest | `228594d07d7a9906280e7b5ff12fa0b1bf70b22ffff4b3d25983a4bcc072a2c6` |
| body | `21fbc2bbd36c67261573d784bfcdba73cedf98543f70e42ba85ed20cb50049cd` |
