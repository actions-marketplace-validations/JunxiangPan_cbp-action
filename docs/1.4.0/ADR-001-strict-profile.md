# ADR 001 — opt-in strict evidence profile

Status: **accepted for 1.4.0 development** (not released, not default).

## Context

CBP 1.3.2 already verifies release evidence with the default gate set. Some
consumers need stronger evidence: signed provenance, a protected gate manifest,
mutation/hostile/fuzz evidence, pinned actions, lock integrity, immutable tags,
Windows coverage and an SBOM. Making these mandatory by default would break
existing 1.3.2 users and change the frozen release semantics.

## Decision

Add `--profile strict` as a separate, opt-in execution path. The default CLI
path, quality-manifest schema, exit codes, 20% skip ratio and CBP-BODY-001 are
unchanged. Strict requirements are reported in a sidecar
`strict-profile.json`; no new fields are added to the frozen quality manifest.

Strict mode requires:

1. signed provenance (SIGNED, bundles verified with cosign);
2. `quality/GATES.sha256` verification;
3. mutation evidence with recall >= 95%;
4. at least 50 hostile corpus cases, all expected FAIL;
5. deterministic fuzz guard;
6. full-SHA action pins;
7. lockfile/installer integrity;
8. tag map immutability;
9. Windows CI declaration;
10. CycloneDX SBOM;
11. external provenance verifier with cosign.

## Consequences

- Existing 1.3.2 callers are unaffected.
- Strict errors return exit 3 (evidence failure) or exit 2 (missing arguments);
  the frozen 0/2/3/4 meaning is not changed.
- Strict requires a signing identity and a network/cached Sigstore trust root;
  without them it fails honestly and is not downgraded to PASS.
- The profile is not a runtime security boundary and does not replace human
  review.

## Alternatives rejected

- Making strict the default: breaks 1.3.2 behavior and users without OIDC.
- Adding strict fields to quality-manifest: violates the frozen schema.
- Treating an unsigned sidecar as signed: forbidden; strict returns FAIL/BLOCKED.
