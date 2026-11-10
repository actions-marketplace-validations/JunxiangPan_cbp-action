# Quality gate self-protection

`GATES.sha256` is the SHA256 manifest for CBP's own gate scripts and release
workflows. It is intentionally outside the frozen `quality-manifest` schema:
this is a sidecar protecting the verifier, not a new manifest field.

Covered paths:

- `src/cbp/*_gate.py`
- `src/cbp/body_hash.py`, `src/cbp/v12_rules.py`, `src/cbp/report_schema.py`
- `.github/workflows/ci.yml`, `.github/workflows/release.yml`, `.github/workflows/rc.yml`
- `tools/verify_gate_manifest.py`

`python tools/verify_gate_manifest.py quality/GATES.sha256` runs in CI and in
the release preflight. A changed file fails with exit 3. Regenerate the
manifest only in a reviewed commit that also explains why the gate changed.

Branch protection / required checks are external GitHub configuration, not
enforced by this manifest.
