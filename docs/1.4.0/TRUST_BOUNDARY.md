# CBP 1.4.0 — strict trust boundary and non-goals

## Trust boundary

CBP strict sits between **evidence producers** (build/RC workflows, manifest,
provenance, signatures) and **consumers** (release owner, GitHub Release, PyPI,
CBE review). It verifies that the evidence presented is internally consistent
and cryptographically signed; it does not execute the released artifact.

The boundary includes:

- the repository content at the reviewed commit;
- `quality/GATES.sha256` and its covered gate/workflow files;
- the manifest artifact hashes and canonical body hash;
- the provenance statement and cosign bundles;
- the expected tag map and the tag ruleset;
- the declared Windows matrix and SBOM.

Outside the boundary:

- the GitHub account/admin who can change protection;
- the OIDC issuer and Sigstore trust root;
- a self-hosted runner's kernel, caches and secrets;
- CBE/CBS/CBM/CBC policy and orchestration;
- the runtime behavior of the released package.

## Non-goals

CBP 1.4.0 strict does **not**:

- make the default profile strict;
- claim that unsigned evidence is signed;
- replace human approval or independent review;
- protect against a fully compromised repository/admin;
- guarantee a runtime security boundary;
- modify the frozen quality-manifest schema or exit-code semantics;
- change the 20% skip ratio or CBP-BODY-001;
- publish or tag anything automatically.

## Failure semantics

- Missing strict arguments: exit 2.
- Any strict evidence check fails: exit 3, report written, no PASS claim.
- Unsigned or unverifiable provenance: FAIL (never BLOCKED-as-PASS).
- Default profile failures keep the existing 0/2/3/4 semantics.
