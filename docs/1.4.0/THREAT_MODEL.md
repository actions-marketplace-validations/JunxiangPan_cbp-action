# CBP 1.4.0 — strict threat model and trust boundary

## Protects against

- A release whose evidence is unsigned or whose signature does not verify.
- A gate script/workflow changed without updating the protected manifest.
- A mutation/hostile/fuzz suite that silently stops catching known mutants.
- A mutable tag or action pin used to substitute different bytes.
- An unlocked/unhashed dependency installation.
- A Windows-path regression that is not exercised on windows-latest.
- A missing or malformed SBOM in the strict evidence bundle.
- A provenance sidecar that claims SIGNED but whose cosign bundle fails.

## Trusted

- The checked-out repository at the reviewed commit.
- GitHub Actions OIDC issuer (`https://token.actions.githubusercontent.com`)
  and the Sigstore Fulcio/Rekor trust root used by cosign.
- The `cbp-gate` workflow/job and the required-check configuration.
- The human owner who approves release and the expected tag map.

## Untrusted

- Workflow inputs, artifact names, checkout refs, release bodies and any file
  supplied by a contributor.
- Self-hosted runners and their caches; strict mode does not make a poisoned
  runner safe.
- Network responses; cosign verification must fail closed.
- The mutable tag namespace unless the tag ruleset is enforced.

## Not protected

- Runtime exploitation of the released software.
- A compromised GitHub account, organization admin, or branch-protection
  bypass.
- A compromised Sigstore trust root or a stolen signing identity.
- A malicious change that also updates every trusted evidence file in one
  reviewed commit.
- CBE/CBS/CBM/CBC internals; those are separate components with their own
  boundaries.

## CBE/CBS boundary

CBP strict is an evidence gate for CBP-produced manifests/assets. CBE owns its
own report policy; CBS owns orchestration. A CBP strict PASS is not a CBE PASS
and not a CBS security proof. CBE must be reviewed against the signed CBP
version separately.

## Bypass preconditions

- Write access to `main`, workflows, or the tag namespace.
- Disabling branch/tag protection or required checks.
- Compromising the OIDC identity or Sigstore trust root.
- A self-hosted-runner compromise.
- A human approving an unsigned/incorrect release despite FAIL.
