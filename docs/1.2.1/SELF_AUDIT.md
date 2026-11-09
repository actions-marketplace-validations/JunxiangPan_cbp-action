# CBP 1.2.1 — self-audit

Status: **PASS — released**. This audit was produced from the same candidate that
was tagged and published.

## Candidate and runs

| Item | Value |
| --- | --- |
| Candidate / tag | `19e44f79ce5a0737d3522bb2bc6dbafa0835aab0` (`v1.2.1`) |
| RC run | `42612084193` (`cbp-rc`) |
| Release CI (push `main`) | `42612217101` |
| E2E run | `42612606203` |
| Release workflow | `42612756724` — all four jobs success |
| PyPI workflow | `42612997685` — success |
| Consumer parity | `42613115587` — success |

## Tests and rules

- **441 passed** (43 warnings). `422+` requirement met.
- CBP-BODY-001 is blocking; the rule set is **13** (7 blocking + 6 warning).
- v1.2.0 fixture: **FAIL** — manifest `1fa44c14139c…bb80`, actual canonical
  body `4798acf332ce…2ef` (raw LF `4709f6a5c4c5…ed3`).
- v1.2.1 fixture: **PASS**; CRLF / extra trailing-newline guard: **PASS**.
- Real CONTRACT v1.7 manifest validates against
  `schemas/manifest.schema.json`.
- Full-40-hex action pins pass; tag pins are rejected with the documented
  reason and alternative.

## Canonical body hash

`cbp.body_hash.canonical_body_hash` is the only implementation:

- decode UTF-8, drop a leading BOM;
- CRLF and lone CR → LF;
- strip trailing newlines, append exactly one LF for non-empty bodies;
- SHA-256 the resulting UTF-8 bytes.

Dogfood, `package_manifest`, remint, `verify_release` and CBP-BODY-001 all call
it. Tests cover no-newline / one / many / CRLF / BOM variants.

## Artifacts

| Artifact | SHA256 |
| --- | --- |
| wheel | `b30b78e876b1c13be4472e7a6e477f8e45466947da9ac306184cfa55427b1718` |
| sdist | `08103c217a6eb19d4393f4ebee03a0d0ded25f0ca16d900e1f7f5271f5a95f59` |
| reminted manifest | `2fa04a6cbaee0d6e90b4af163e3a0fbc5c3c0ed242d079264eb89a825f60b48e` |
| final Release body (canonical) | `561c4767b5ce89d4151760666f9866f2cc0948aa938cc98b981282d242d28fbe` |

Manifest facts: `package_id=cbp`, `producer_id=cbp`, `version=v1.2.1`,
`gate_status=PASS`, `body_hash_scope=base`,
`ci_run_id=42612217101`, `ci_commit_sha=19e44f7…`.
`artifact_hashes` equal the wheel/sdist above; `evidence_sha256` is recomputed
and self-validates.

## Five-way consistency

- tag commit `19e44f7` = RC head = CI head.
- CI manifest is reminted from the exact RC bytes and the exact body; the
  Release body fetched from the GitHub API has canonical hash `561c4767…`,
  equal to `manifest.release_body_hash`.
- Release assets equal the RC wheel/sdist; PyPI digests equal the Release
  assets; `gh attestation verify` returns 0 for both.

## Note on file placement

The exact artifact hashes only exist after the RC build, so this audit and
`docs/1.2.1/RELEASE_RECORD.md` were committed immediately after the tag rather
than inside it. The tag itself contains the code, the v1.2.0 ERRATA and the
schema/README/CHANGELOG fixes. No artifact or claim depends on a post-tag file.
