# CBP 1.3.0 threat model

CBP is a **release-evidence gate**, not a runtime defense boundary. It reduces
the chance that a release is published with stale or mismatched evidence; it
does not make a compromised build or a malicious maintainer safe.

## Protects against

- A release whose tag, CI run, RC run, body and manifest disagree.
- A manifest that does not bind the actual artifact bytes or the canonical body.
- Stale coverage/docs/binary/claims evidence that no longer matches the tree.
- A moved or deleted release tag, when a pinned snapshot is checked.
- A dependency lock that is unpinned, unhashed or silently edited after approval.
- A GitHub Action pinned to a mutable tag/branch.
- Accidental edits to CBP's own gate scripts or workflows (SHA256 manifest).
- An unsigned provenance sidecar being mistaken for a signed one.

## Does not protect against

- A compromised GitHub account, organization admin, or workflow write access.
- A malicious or poisoned self-hosted runner/kernel; runner trust is external.
- A build that is internally malicious but produces matching evidence.
- A test suite that is itself wrong or weakened in the same commit.
- Branch-protection or required-check bypass at the hosting layer.
- Runtime exploitation of the project being released.
- CBE/CBS/CBM/CBC internals; those components have their own gates.

## Bypass preconditions

- Write access to `main`, workflows, or the tag namespace.
- Disabling branch protection/required checks.
- Replacing the gate manifest and the gate code in the same trusted commit.
- Self-hosted runner compromise or credential exfiltration.
- A signing identity compromise (when signing is enabled).
- A contract change made without updating the frozen tests (which is why the
  contract tests pin the schema and constants).

## Self-hosted runners

CBP does not trust a self-hosted runner by default. If one is used:

- use an ephemeral runner per job, never a persistent workspace with secrets;
- do not expose repository write tokens to untrusted jobs;
- treat `/tmp`, caches and checked-out workspaces as attacker-controlled;
- require the same SHA-pinned actions and lockfile checks on that runner;
- prefer GitHub-hosted runners for release jobs.

The `tests/test_hostile_corpus.py`, `tests/test_gate_selfprotect.py` and the
Windows matrix cover input/path/tamper cases, but runner isolation remains an
**external configuration** responsibility.

## Boundary with CBE / CBS

- CBP produces/verifies release evidence for CBP and external package
  manifests. It does not execute CBE's policy engine or CBS's orchestration.
- CBE/CBS/CBM/CBC are not modified by CBP releases.
- A CBP PASS is evidence for the release gate; it is not a statement that the
  running system is secure.

## External configuration (not enforced by code)

- GitHub branch protection and required status checks.
- Tag protection rules and environment approval for PyPI.
- Organization-level action allowlists and runner groups.
- Secret scanning/push protection.

These must be configured and audited outside CBP; the repository documents them
but cannot prove their state from a checkout.
