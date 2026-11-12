# CBF 0.1.0rc1 subject manifest (CBP)

CBP's manifest validator now accepts PEP 440 prereleases; `0.1.0rc1` is no
longer rejected or renamed to a fake stable `0.1.0`.

- CBF artifact: `cbf-0.1.0rc1-py3-none-any.whl`
- artifact SHA256: `3c8faa174fdfa5a6fcd69157f566dde7ac2b11bbd4d164b2ecb7badbe8190060`
- CBF release notes: `cbf/docs/RELEASE_NOTES_0.1.0rc1.md`
- generated manifest: [cbf-0.1.0rc1-subject-manifest.json](cbf-0.1.0rc1-subject-manifest.json)
- manifest SHA256: `ce12e2801a72f95cd5c57c46e3e10e8300414e43e1373fdd9f7ed9c1ee13a7ca`
- version in manifest: `v0.1.0rc1`

The gate report is a CBP-shaped view of the four actual checks in CBF's
`release/RELEASE_EVIDENCE.json` (`scan-all`, `git-staged`, `release-artifacts`,
`verify-evidence`). CBF artifacts were **not modified**; the generated manifest
and gate report live in CBP's docs.

Command:

```bash
cbp manifest --package-id cbf --producer-id cbf --version 0.1.0rc1 \
  --gate-report .tmp-cbf-manifest/gate-report.json \
  --artifact /path/to/cbf-0.1.0rc1-py3-none-any.whl \
  --artifact-sha256 cbf-0.1.0rc1-py3-none-any.whl=3c8faa... \
  --release-body /path/to/RELEASE_NOTES_0.1.0rc1.md \
  --body-hash-scope base \
  --out cbf-0.1.0rc1-subject-manifest.json
```
