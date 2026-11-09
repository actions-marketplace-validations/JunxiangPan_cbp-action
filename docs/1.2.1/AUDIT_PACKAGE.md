# CBP 1.2.1 — audit package

Candidate: `19e44f79ce5a0737d3522bb2bc6dbafa0835aab0` (`v1.2.1`).
Status: **released**; v1.2.0 untouched.

## Artifacts

| Item | Value |
| --- | --- |
| wheel | `b30b78e876b1c13be4472e7a6e477f8e45466947da9ac306184cfa55427b1718` |
| sdist | `08103c217a6eb19d4393f4ebee03a0d0ded25f0ca16d900e1f7f5271f5a95f59` |
| manifest | `2fa04a6cbaee0d6e90b4af163e3a0fbc5c3c0ed242d079264eb89a825f60b48e` |
| body (canonical) | `561c4767b5ce89d4151760666f9866f2cc0948aa938cc98b981282d242d28fbe` |
| tag | `19e44f79ce5a0737d3522bb2bc6dbafa0835aab0` |
| RC / CI | `42612084193` / `42612217101` |
| release / PyPI / e2e | `42612756724` / `42612997685` / `42613115587` |

## Evidence

- 441 tests; 13 rules (7 blocking + 6 warning); CBP-BODY-001 fail on the
  v1.2.0 fixture and pass on v1.2.1.
- Canonical body hash is the single implementation in `src/cbp/body_hash.py`;
  remint rejects a missing body with exit 2 and never keeps the old hash.
- `release.yml` generates the body, remints the manifest from it, verifies the
  manifest and asserts `--release-body`/`--check-only` in the same job.
- `schemas/manifest.schema.json` validates a real CONTRACT v1.7 manifest.
- Tag/main consistency: `19e44f7`; tag is not moved.
- `docs/1.2.0/ERRATA.md` records the v1.2.0 body-binding defect.

## Known limitation

`docs/1.2.1/SELF_AUDIT.md` and `RELEASE_RECORD.md` were committed after the tag
because their hashes only exist after the RC build. They are on `main`
immediately after `19e44f7`; the tag carries the code and the v1.2.0 ERRATA.
