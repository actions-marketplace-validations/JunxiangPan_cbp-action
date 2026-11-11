# CBP 1.4.0 — non-goals

Strict mode is an **evidence gate**, not a security boundary. It does not:

- make CBP a runtime defense or sandbox;
- prove that a human reviewed the release;
- protect against a compromised GitHub account, repository admin, OIDC
  identity, Sigstore trust root, or self-hosted runner;
- replace CBE policy or CBS orchestration;
- make the default 1.3.2 profile strict;
- add or remove frozen quality-manifest fields;
- change exit codes 0/2/3/4, the 20% skip ratio, or CBP-BODY-001;
- re-sign, move, or republish an old release;
- guarantee SBOM completeness beyond the components CBP can enumerate;
- guarantee Windows behavior beyond the declared windows-latest matrix.

Any claim stronger than the evidence in `strict-profile.json` is out of scope.
