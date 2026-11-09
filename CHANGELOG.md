# Changelog

## 1.2.2 — 2026-11-09

CBP follows CONTRACT v1.7.1 RC2 (`contract/v1.7.1` at `6835789`, NOT FROZEN).

- `schema_version` stays the string `"1"`.
- `artifact_repository` is an object: `repository`, `run_id`, `artifact_name`.
  CBP's own release manifest points at the `cbp-rc` artifact of the RC run;
  external package manifests use the target repository/run/artifact.
- `ci_commit_sha` is required and must be 40 lowercase hex; `ci_run_id`,
  `generated_at` and `generated_by` are accepted optional fields.
- `gate_status` accepts `NOT_UPLOADED`, which is not PASS and not in the skip
  ratio.
- The canonical body hash is unchanged; the body emits
  `<!-- CBP-BODY-BASE-END -->` and the hash covers the bytes before it.
  CBP-BODY-001 stays blocking.
- RC2 schema fixtures: a real v1.2.2 manifest passes; the real v1.2.0 and
  v1.2.1 manifests fail as legacy string-repository fixtures.
- v1.2.1 is not moved and its Release body is not edited; CBE is notified to
  upgrade to the v1.2.2 manifest shape.

## 1.2.1 — 2026-11-09

- Single canonical release-body hash (`body_hash_bytes`: UTF-8, BOM stripped,
  LF, exactly one trailing newline). Generators, remint, verifier and
  CBP-BODY-001 all call it.
- `tools/remint_manifest.py --release-body` recomputes `release_body_hash` from
  the exact body that will be uploaded; a missing body exits 2 and writes
  nothing; a body different from CI is never silently preserved.
- `release.yml` generates the body, remints the manifest from it, re-verifies,
  and publishes that same body in one job (no cross-job body hash).
- New blocking rule CBP-BODY-001 (13 rules total): fails when the manifest body
  hash does not match the actual body; it fails on the v1.2.0 fixture and
  passes on v1.2.1.
- `docs/1.2.0/ERRATA.md` records the v1.2.0 body-hash mismatch and the stale
  docs pointer. The v1.2.0 tag, PyPI 1.2.0 and Release body are not modified.
- Documentation/schema/SHA pin fixes: 1.2.0 CHANGELOG entry is final; README
  drops stale roadmap/VM wording; `schemas/manifest.schema.json` now validates
  CONTRACT v1.7 manifests; tag pins remain rejected with the documented reason
  and the full-40-hex alternative.

## 1.2.0 — 2026-11-09

- `body_hash_scope: "base"` in the quality manifest. Only `base` is supported;
  `full` or any unknown value is an input error (exit 2), and
  `--parse-report --require-body-scope` rejects a manifest that omits it.
  `release_body_hash` covers the generated body, not later ERRATA addenda.
- `artifact_repository` is recorded from `--artifact-repository`,
  `artifact_repository` in `cbp.json`, or `GITHUB_REPOSITORY`, and omitted when
  empty. `--expected-repository` rejects a cross-repository artifact (exit 2).
- cbc-event 0.1.x emitter: local `events.jsonl` + `head.json`, hash chain
  (genesis = 64 zeroes), HMAC-SHA256, rate limit, disabled by default, dropped
  events counted. CLI: `--cbc-event-dir`, `--cbc-event-max`,
  `--cbc-event-hmac-env`.
- Twelve detection rules with `--v12`:
  - blocking: CBP-CI-001 test roots, CBP-VER-001 version sync, CBP-QA-001 QA
    counts, CBP-DEBT-001 debt evidence, CBP-SIGN-001 sign tools, CBP-WT-001
    worktree cleanliness **and conflict markers in tracked files**;
  - warning + baseline: CBP-BIN-001 Authenticode, CBP-DOC-001 doc references,
    CBP-CLAIM-001 capability claims, CBP-COV-001 coverage hard gate,
    CBP-PROOF-001 proof tier, CBP-SLOP-001 docstring templates.
- Waivers and baselines require `rule`, `path`, `reason` and `expires`; an
  expired entry is not applied and is reported. Blocking failures exit 3;
  warning-only failures exit 0 with a visible WARN (blocking in 1.2.1);
  malformed entries exit 2.
- `--v12-report` writes a machine-readable rule report; `--v12-only` selects
  rules; `--waivers` and `--v12-baseline` load the entry files.
- `cbp manifest` generates a CONTRACT §5 quality manifest for an external
  subject package (`--package-id`, `--producer-id`, `--gate-report`,
  `--artifact`, `--release-body`, `--body-hash-scope base`, `--evidence`).
  Missing inputs or a digest mismatch are exit 2 and write nothing; a FAIL gate
  report stays FAIL. CBC `validate_cbp` accepts the real CBC manifest and CBM's
  B3 field check accepts the real CBM-scoped manifest (B2 not claimed).
- Real-repository E2E (read-only) and consumer parity are recorded in
  `docs/1.2.0/E2E_MATRIX.md`; the 12-rule delivery matrix is
  `docs/1.2.0/RULE_MATRIX.md`.

## 1.1.0 — 2026-11-09

- `report_schema.py`: the six CONTRACT §3 gate statuses, the §1 exit-code table
  (0/2/3/4), bare-64-hex hash validation, and quality-manifest v1.7 field
  validation. `producer_id` is emitted as `cbp`; `schema_version` stays `"1"`
  (D1: adding a field is not a structural break).
- `report_parser.py`: structured-JSON-only parser for CBE reports, CBP manifests,
  and CBP gate reports. Missing/invalid fields, unsupported `schema_version`, a
  `sha256:` prefix, and an inconsistent skip ratio are input errors (exit 2). An
  exit 3 without a valid `gate_status` is an input error, per CONTRACT §1.
- CLI exit codes are now 0/2/3/4. `package_type: "cbp"` turns claims, binary,
  encoding, docs, and custom into forced gates: a forced SKIPPED gate sets
  `blocking_skip` and exits 3. More than 20% skipped exits 4. `audit`/`warn`
  still exit 0 but print `contract_exit_code` and `publishable=false`.
- New CLI flags: `--report-json` (writes a parseable gate report), `--parse-report`
  (validation only), `--observed-exit-code` (F1 exit-code consistency),
  `--rules-path` / `--rules-sha256` (CBE rule pack; missing or unparseable is
  exit 2), and `--release-assets` (explicit asset inventory for
  `--verify-release`).
- Quality manifest now carries the CONTRACT v1.7 fields (`schema_version`,
  `package_id`, `producer_id`, `version`, `gate_status`,
  `applicable_gate_count`, `skip_count`, `skip_ratio`, `blocking_skip`,
  `gates[]`, `artifact_hashes`, `release_body_hash`, `evidence_sha256`) plus the
  §4 CI binding (`ci_run_id`, `ci_commit_sha`). `claims` and
  `verify_manifest_artifact` read the gate array.
- `--require-gate-pass`: publish fails unless the manifest is `PASS`, has no
  blocking skip, and its skip ratio is at most 20%.
- `SKIPPED_INFRA`: GitHub API timeouts / HTTP 5xx during `--verify-release` exit
  3 with `GATE_STATUS=SKIPPED_INFRA`; the release body generator can render a
  dedicated Infrastructure failures section.
- Encoding allowlist: exact per-path BOM exemptions with a required reason and
  visible counts (`allowlisted=N`, `allowlist_unused=N`). Wildcards, absolute
  paths, duplicates, and stale entries are rejected.
- `--jobs` executes in parallel again instead of being silently ignored.
- The `ai-audit` job no longer ends with an unconditional `exit 0`: a crashing
  gate or a missing SARIF file fails the job, while audit findings stay visible.
- Config gains `package_type` and `encoding_allowlist`; this repository declares
  `"package_type": "cbp"`.
- New `cbp errata` command: prefixes a body with the machine-readable `ERRATUM:`
  token (F4), preserves the original bytes, reports any trailing ERRATUM section
  as human-readable only, and prints a unified diff. It never edits GitHub.

## 1.0.9 — 2026-11-08

- The repository tracks no wheel, sdist, or `WHEEL_SHA256`; the `build-artifact`
  job is the only build step and a CI job rejects tracked build artifacts.
- `action.yml` no longer installs a wheel from the repository. It downloads the
  wheel from the release it was pinned to (`cbp-version`), compares its SHA256
  with the release asset digest, verifies Sigstore provenance with
  `gh attestation verify`, and only then installs it. The verified digest and
  path are exposed as the `wheel-sha256` and `wheel-path` outputs.
- `e2e-payload` gains a `consumer-parity` job asserting that the wheel the action
  installed equals the release asset digest and verifies against its attestation.
- `CONTRIBUTING.md` records two rules: verification features need a consumer-view
  E2E assertion, and the repository never tracks build artifacts.
- Release verification compares the live body with the body artifact produced by
  the publishing run, so a post-release body edit is still detected without
  moving the tag.
- The release body generator no longer claims a byte-identical double build, a
  Python 3.10 skip, or unfilled AI gate counts.

## 1.0.8 — 2026-11-08

- Build-once release pipeline: wheel is built once and shared as `cbp-dist`.
- dogfood, dogfood-verify, release, and clean-verify consume the same artifact.
- Python 3.10 is explicitly SKIPPED when setup-python download is unavailable.
- AI audit results are visible in CI; ai-test self-check catches CBP-TEST-001.
- Publish hard gate requires a green CI run whose commit matches the tag.

## 1.0.3 — 2026-11-08

- `action.yml` verifies `dist/WHEEL_SHA256` before installing the wheel.
- Release workflow publishes notes automatically and no longer uploads `WHEEL_SHA256` as an asset.
- `verify_release_assets` rejects extra, missing, or hash-mismatched release assets.
- `security_core` coverage threshold restored to 90.0; measured 90.02.
- README version progression corrected; PyPI install link added.
- VM chaos evidence marked as v1.1.0 roadmap.

## 1.0.2 — 2026-11-08

- Claims gate verifies release version, wheel SHA256, and PyPI link.
- E2E test rejects a release body with the wrong version.
- Coverage ratchet restored to v1.0.0 historical floor.
- Checks API check runs and annotations implemented.

## 1.0.1 — 2026-11-08

- `cbp policy test` CLI entry wired and covered by E2E.
- `_configured` honors packs-only configurations.
- Configuration-only packs trigger custom gate.
- CEL findings report the matching file path.
- Benchmark platform differences documented.

## 1.0.0 — 2026-11-08

- First stable release.
- Nine gates, CEL policy layer, rule packs, SARIF, AST taint, and external report aggregation.
- PyPI trusted publishing via GitHub OIDC.

## 0.1.8 — 2026-11-07

- Added ambiguous Windows-backslash path detection in .py/.ps1 files.
- Made required_artifacts mandatory whenever package_zip is configured.
- Documented that administrator/VM chaos tests are not proven by CI.
- Kept lcov/cobertura, Action SHA pinning, and ReDoS work deferred to P1/P2.

## 0.1.5 — 2026-11-07

- Added a built-in PowerShell AST syntax gate inside the custom gate.
- Added required-pattern support for CBP custom rules.
- Rejects malformed .ps1 files before deployment.
- Added required-artifact ZIP integrity, naked-subprocess, and Python PYTHONPATH checks.
- Fixed CBS journal status binding by rejecting the invalid warning status.

## 0.1.4 — 2026-11-07

- Added source-hash binding for coverage evidence; `touch` no longer bypasses freshness.
- Added baseline generation and inline suppression for existing findings.
- Fixed dead `enable_custom` / `enable_upgrade` switches and unknown-key fail-open.
- Added `gates_ran` and zero-gate FAIL semantics.
- Reduced comment false positives and made PowerShell 7 the supported runtime.

## 0.1.3 — 2026-11-07

- Removed `shell=True` from the upgrade gate; scripts are parsed with `shlex.split` and shell metacharacters are rejected.
- Rejected upgrade-script execution on `pull_request` and `pull_request_target` events.
- Added GitHub OIDC build provenance with `actions/attest-build-provenance`.
- Bumped the configuration schema to `0.1.3`; old `0.1.x` configs migrate in memory.

## 0.1.2 — 2026-11-06

- Added checked-in `docs/RELEASE_BODY.md`, validated by the claims gate and used by `gh release create`.
- Added SARIF 2.1.0 output via `--sarif-output`.
- Added the eighth `custom` gate for config-driven regex/literal rules (warn by default).
- Added optional `coverage.json.sha256` sidecar verification.
- Release body is included in the documentation hash manifest.

## 0.1.1 — 2026-11-06

- Added a strict UTF-8 no-BOM encoding gate (tracked text files only).
- Release claims now validate prose gate counts, not only `QUALITY_COUNTS`.
- Generated release notes use the actual gate count dynamically.
- Action path inputs are optional and fail closed only when their gate is enabled.
- `security_core` coverage now measures the actual gate modules.
- Documented checksum + run-id pinning instead of cryptographic-signature wording.
- CBP is distributed through GitHub Actions/Releases only; PyPI publication is not used.

## 0.1.0 — 2026-11-06

Initial standalone release candidate.

CBP was created after a release process trusted a green report that was not
backed by reproducible evidence: counts did not reconcile, a signing gate
matched a text marker, and blocked checks still allowed a package to ship.

This release turns those lessons into reusable gates:

- coverage with an explicit allowlist and real threshold
- pinned dependencies with hashes and `--require-hashes`
- public docstring, argument, generic-boilerplate, and slop-comment checks
- manifest-bound documentation history
- binary build/SBOM provenance and binary hash checks
- release-note claims reconciled against machine data
- `audit` and `enforce` modes
- GitHub Action and local CLI entry points
- Linux and Windows self-tests
### Scope

v0.1.5 is a P0/VM-guard release. P1/P2 items are deferred to v0.1.8.
