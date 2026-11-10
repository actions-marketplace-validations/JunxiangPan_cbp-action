# CBP 1.3.0 — provenance sidecar

Status: **BLOCKED_NO_SIGNING_IDENTITY**. No signing credential (OIDC keyless or
a private key) is available in this environment, so no signature was produced.

## Delivered

- `schemas/provenance.schema.json` — SLSA/in-toto-shaped statement.
- `src/cbp/provenance.py` — build + offline verify.
- `tools/provenance.py create|verify`.
- `tests/test_provenance.py` — unsigned is blocked; artifact/manifest tamper is
  detected; CLI exits 4, never 0, for an unsigned sidecar.

The sidecar is `provenance.json`; `provenance.sig` is an explicit status object,
not a fabricated signature:

```json
{"status": "BLOCKED_NO_SIGNING_IDENTITY", "algorithm": null, "signature": null}
```

## Offline verification

```bash
python tools/provenance.py verify \
  --provenance provenance/provenance.json \
  --manifest quality-manifest.json \
  --artifact dist/cbp_action-1.3.0-py3-none-any.whl \
  --artifact dist/cbp_action-1.3.0.tar.gz
```

The verifier never uses the network. It recomputes subject hashes, compares the
manifest hash and `artifact_hashes`, and reports `BLOCKED_NO_SIGNING_IDENTITY`
rather than PASS when unsigned.

## To unblock

A human must provide an OIDC identity (GitHub Actions `id-token: write` plus a
sigstore/cosign keyless flow) or a signing key, then re-run creation and
verification. Do not synthesize a signature or downgrade the verifier to PASS.
