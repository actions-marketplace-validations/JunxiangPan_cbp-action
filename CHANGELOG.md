# Changelog

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
