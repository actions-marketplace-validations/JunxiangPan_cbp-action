# CBP 1.4.0 — strict profile usage

`--profile strict` is opt-in. The default command path is unchanged.

```bash
python -m cbp.cli \
  --root . \
  --profile strict \
  --manifest quality-manifest.json \
  --provenance provenance.json \
  --bundle-dir . \
  --strict-artifact cbp_action-1.4.0-py3-none-any.whl \
  --strict-artifact cbp_action-1.4.0.tar.gz \
  --identity-regexp 'https://github.com/JunxiangPan/cbp-action/.github/workflows/release.yml@refs/tags/v1.4.0' \
  --oidc-issuer https://token.actions.githubusercontent.com \
  --strict-report strict-profile.json
```

## Checks

| Check | Evidence |
|---|---|
| `gates_sha256` | `quality/GATES.sha256` verifies |
| `mutation` | mutation report recall >= 95% |
| `hostile_corpus` | >= 50 cases, all expected FAIL |
| `fuzz` | 200 deterministic hostile inputs rejected |
| `action_pins` | every action pinned to a full 40-hex SHA |
| `lockfile` | pinned/hashed lock + `--require-hashes` installer |
| `tag_immutability` | expected map equals actual tag commits |
| `windows` | CI declares `windows-latest` |
| `sbom` | CycloneDX SBOM with components |
| `provenance` | cosign-verified SIGNED provenance + artifact hashes |

## Result

`strict-profile.json` is written next to the root. Exit codes:

- `0` — all strict checks PASS;
- `3` — at least one evidence check failed;
- `2` — required strict arguments are missing (for example no
  `--identity-regexp`).

A missing signing identity or a cosign failure is a FAIL, not a PASS. Strict
mode never writes to the frozen quality-manifest.
