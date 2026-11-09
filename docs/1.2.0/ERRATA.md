# CBP v1.2.0 — ERRATA

Status: **ERRATUM**, fixed in v1.2.1. The v1.2.0 tag, PyPI files and GitHub
Release body are deliberately not modified.

## 1. `release_body_hash` does not bind the published body

- v1.2.0 manifest `quality-manifest.json` records
  `release_body_hash = 1fa44c14139c747601663e2971a8fcade6554f3d9dd404bba5716ba19bd0bb80`.
- The published Release body is 1953 bytes and ends with two newlines. Its raw
  LF hash is
  `4709f6a5c4c56a416117c1f9070d023b028a2a98a7f98106b0e3688f253baed3`;
  after the v1.2.1 canonical normalization (exactly one trailing newline) it is
  `4798acf332ce8a4ea0093cba7755d57132a3e9e81c4d5c0ec9974fd719e802ef`.
- None of the three values match. The manifest did not bind the actual body.

The v1.2.1 fix uses one canonical body hash in every producer, remint,
verifier and CBP-BODY-001. It does not rewrite history.

## 2. Tag documentation points at the previous candidate

Files under `docs/1.2.0/` on tag `v1.2.0` still reference candidate `163f138`
and wheel `bdddc74f…`; the published tag is `5ebd0eb` with wheel `188639bb…`.
The published artifacts are correct; the documentation on the tag is stale.
v1.2.1 pins every document to its own candidate and hashes.

## 3. Other stale statements

- `CHANGELOG.md` said `1.2.0 — RC (not released)` although v1.2.0 was released.
- `README.md` still mentioned the v1.1.0 VM roadmap.
- `schemas/manifest.schema.json` required the old `counts` object and could not
  validate a real v1.7 manifest.

All three are fixed in v1.2.1.

## What is NOT changed

- Tag `v1.2.0` is not moved.
- PyPI `1.2.0` is not deleted.
- The v1.2.0 GitHub Release body is not edited (editing it would change its
  hash and make the binding worse).

The v1.2.1 release notes reference this ERRATUM.
