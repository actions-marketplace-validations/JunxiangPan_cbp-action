# CBP 1.3.2 — keyless signing

CBP 1.3.2 is **SIGNED via GitHub OIDC keyless cosign/sigstore**. No long-lived
private key is used.

## Signed files

For each of these on the `v1.3.2` Release:

- `cbp_action-1.3.2-py3-none-any.whl`
- `cbp_action-1.3.2.tar.gz`
- `quality-manifest.json`
- `provenance/provenance.json`

the Release carries:

- `<file>.bundle` — Sigstore bundle (certificate + signature + transparency proof)
- `<file>.sig` — detached signature
- `<file>.pem` — signing certificate

Wheel and sdist also have `attestation.json` / `attestation-sdist.json`
(SLSA provenance predicate), produced with `cosign attest-blob`.

## Verify online

```bash
IDENTITY="https://github.com/JunxiangPan/cbp-action/.github/workflows/release.yml@refs/tags/v1.3.2"
ISSUER="https://token.actions.githubusercontent.com"

cosign verify-blob --bundle cbp_action-1.3.2-py3-none-any.whl.bundle \
  --certificate-identity "$IDENTITY" --certificate-oidc-issuer "$ISSUER" \
  cbp_action-1.3.2-py3-none-any.whl

cosign verify-blob-attestation --bundle attestation.json --type slsaprovenance \
  --certificate-identity "$IDENTITY" --certificate-oidc-issuer "$ISSUER" \
  cbp_action-1.3.2-py3-none-any.whl

python tools/provenance.py verify \
  --provenance provenance/provenance.json \
  --manifest quality-manifest.json \
  --artifact cbp_action-1.3.2-py3-none-any.whl \
  --artifact cbp_action-1.3.2.tar.gz \
  --bundle-dir . --identity-regexp "$IDENTITY" --oidc-issuer "$ISSUER"
```

The verifier recomputes the manifest/artifact hashes and calls
`cosign verify-blob` for every file; it does not trust the JSON status alone.

## Offline

The `.bundle` files contain the signature, certificate and transparency proof.
Use `cosign verify-blob --bundle ... --trusted-root <sigstore-root.json>` if a
local trusted root is available. Without a cached trust root cosign may need to
fetch the Sigstore TUF root; that is a network requirement, not a signature
failure.

## Failure policy

If GitHub OIDC is unavailable, the signing workflow fails; no Release is created
and no PyPI upload occurs. The workflow does not generate a self-signed key or
any substitute signature. A failed signature is never published as signed.

v1.3.1 remains unsigned; its tag and assets are unchanged.
