# CBP 1.2.0 — RC audit package

Status: **STOPPED FOR HUMAN AUDIT**. Nothing was published to PyPI or as a
GitHub Release. Merging the draft PR, tagging, and publishing are owner actions.

## Candidate identity

| Item | Value |
| --- | --- |
| Branch | `1.2.0-dev` |
| RC commit | `163f138` (remints the CI manifest from RC hashes) |
| Draft PR | https://github.com/JunxiangPan/cbp-action/pull/1 |
| PR CI | run `42603730509` — success |
| Release CI (manifest) | run `42604400520` — success |
| Action E2E | run `42603730815` — success (15/15 payload + consumer parity) |
| RC build + attest | run `42603720434` — success |
| wheel | `cbp_action-1.2.0-py3-none-any.whl`<br>`bdddc74f828de7ae1beae3b484ece5ddb2986620585985b0f24c9b6897701e16` |
| sdist | `cbp_action-1.2.0.tar.gz`<br>`3cee5cd8309533d3b809cdadeea7dd73cf2fc32dda268f9b912c0dfe751335b1` |
| Attestation | `gh attestation verify` exit 0 for both; subject digest equals the local hash; repository `JunxiangPan/cbp-action` |
| PyPI | `https://pypi.org/pypi/cbp-action/1.2.0/json` → **404** |
| GitHub Release | `v1.2.0` → **not found** |
| v1.2.0 tag | exists at `8431712`; approved to delete/recreate at `163f138` |

Post-RC history: `9ee52fb` added conflict markers to CBP-WT-001, `bb8d4d6`
fixed temp-file hygiene, `855fed7` added the external-package manifest
generator, `72252b4` fixed target-scoped gate provenance, and `163f138` fixes
the release path, preflight short-SHA handling, and manifest remint: `release.yml` publishes the audited `cbp-rc` bundle, not
`cbp-dist`, and verifies expected hashes plus tag/RC/CI commit equality. Earlier candidates `5da8b87`, `9ee52fb`, `bb8d4d6`, `855fed7`, `72252b4`,
`d3ec73e` and `8431712` are superseded.

The RC workflow builds and attests only; it never uploads to a package index or
creates a release (`attest-build-provenance` + artifact upload).

## Test evidence

- Local: **421 passed**, 43 warnings.
- CI coverage: `security_core=91.64%/90.00%`, `cbp=90.56%/80.00%`.
- `docs/1.2.0/E2E_MATRIX.md`: 5 repositories × 12 rules, read-only, plus the
  requested CBS `contract/v1.7.1` E2E (exit 3, three committed conflict
  markers in `.github/workflows/vm-proof.yml:15/16/18`).

## External-package manifest (post-RC request)

`cbp manifest` writes a CONTRACT §5 manifest for a subject package using a
target-scoped gate report plus that package's artifacts and body. The gate
report is produced on the target root with
`--package-id/--producer-id/--version`; a CBP-self report is rejected.

| Target | Gate report | Generated manifest | Target-side check |
| --- | --- | --- | --- |
| CBC `11943f14` | `213e8243…` (`cbc`/`cbp`/`v0.1.0`, PASS) | `01438d31067f05508454c81af068efc61c9797034c778746b94d77e3de63bac0` | `validate_cbp` → PASS |
| CBM `8acb628` | `ac4d243b…` (`cbm`/`cbp`/`v0.1.0`, **FAIL**) | `967f15ccd8f222518ceb3c613ffda8d4f2ed04cfede958485f0bd79531e410cb` | `load_report` → PASS; B3 fields complete; `FAIL` preserved |

CBC manifests `f897bc90…` (historical) and `5f952d9b…` (earlier R01–R19)
precede the current `01438d31…`; `EXTERNAL_MANIFEST.md` records the same
history. CBM's real gate finding is `encoding: FAIL` on
`audit/v1.2.0-rc/b5-probe-declared.stdout.txt` (invalid UTF-8). It is not
rewritten to PASS. CBC R02–R19: 18/18 assertions (17 executed; R16 skipped on
Windows); R01 NOT RUN (no upload). CBM B3 is field-level complete; **B2 is not
claimed**. Evidence: `docs/1.2.0/evidence/`.

## Twelve rules — fixtures, tests, exit codes

| ID | Rule | Severity | Fixtures (positive / negative / false-positive guard) | Exit |
| --- | --- | --- | --- | --- |
| CBP-CI-001 | TEST_ROOTS_IN_CI | blocking | `test_ci_001_passes_when_the_root_runs` / `test_ci_001_fails_when_the_root_is_missing` / `test_ci_001_ignores_a_path_in_a_comment` | 3 |
| CBP-VER-001 | VERSION_SYNC | blocking | `test_ver_001_passes_when_sources_agree` / `test_ver_001_fails_on_a_mismatch` / `test_ver_001_ignores_older_changelog_headings` | 3 |
| CBP-QA-001 | QA_COUNTS_CONSISTENT | blocking | `test_qa_001_passes_consistent_counts` / `test_qa_001_fails_on_a_count_mismatch` / `test_qa_001_fails_when_covered_zero_contradicts_coverage` | 3 |
| CBP-DEBT-001 | DEBT_EVIDENCE | blocking | `test_debt_001_passes_with_evidence` / `test_debt_001_fails_without_evidence` / `test_debt_001_ignores_lowercase_prose` | 3 |
| CBP-SIGN-001 | SIGN_TOOLS_IN_TAG | blocking | `test_sign_001_passes_when_the_script_exists` / `test_sign_001_fails_when_the_script_is_missing` / `test_sign_001_ignores_a_path_in_a_comment` | 3 |
| CBP-WT-001 | WORKTREE_CLEAN_AFTER_GATES | blocking | `test_worktree_rule_passes_on_a_clean_tree` / `test_worktree_rule_detects_a_tracked_change` / `test_worktree_rule_fails_on_a_committed_conflict_marker` / `test_worktree_rule_flags_an_end_marker_without_a_start` / `test_worktree_rule_accepts_a_separator_without_a_conflict` / `test_worktree_rule_ignores_untracked_conflict_markers` | 3 |
| CBP-BIN-001 | BINARY_AUTHENTICODE | warning | `test_bin_001_passes_with_a_signature_blob` / `test_bin_001_fails_on_an_unsigned_installer` / `test_bin_001_passes_without_installers` | 0 (1.2.1: 3) |
| CBP-DOC-001 | DOC_REFERENCES_EXIST | warning | `test_doc_001_passes_when_the_path_exists` / `test_doc_001_fails_on_a_missing_path` / `test_doc_001_ignores_bare_prose_paths` | 0 (1.2.1: 3) |
| CBP-CLAIM-001 | CAPABILITY_CLAIMS | warning | `test_claim_001_passes_with_evidence` / `test_claim_001_fails_without_evidence` / `test_claim_001_accepts_an_audit_only_marker` | 0 (1.2.1: 3) |
| CBP-COV-001 | COVERAGE_HARD | warning | `test_cov_001_passes_with_a_hard_gate` / `test_cov_001_fails_when_downgraded` | 0 (1.2.1: 3) |
| CBP-PROOF-001 | PROOF_HIGH_TIER | warning | `test_proof_001_passes_with_all_markers` / `test_proof_001_fails_when_a_marker_is_missing` | 0 (1.2.1: 3) |
| CBP-SLOP-001 | DOCSTRING_SLOP | warning | `test_slop_001_ignores_a_few_template_docstrings` / `test_slop_001_fails_above_the_threshold` | 0 (1.2.1: 3) |

Waiver tests: `test_a_matching_waiver_suppresses_the_finding`,
`test_waiver_must_match_the_exact_path`, `test_an_expired_waiver_is_not_applied`,
`test_malformed_waiver_is_an_input_error`,
`test_warning_baseline_suppresses_until_expiry`,
`test_expired_baseline_does_not_suppress`.

CLI tests: `test_cli_v12_exit_codes_and_report`,
`test_cli_v12_blocks_on_a_blocking_rule`,
`test_cli_rejects_unsupported_body_scope`.

## Waivers and baseline

None are shipped or active for the RC.

- Entry schema: `{"rule", "path", "reason", "expires"}`; all four are required.
- Expired entries are not applied and are printed as `EXPIRED …`.
- Malformed or missing entries are an input error (exit 2).
- A waiver binds one rule to one exact path (or `*` for a documented global
  exception). A path mismatch does not suppress anything.
- Warning baselines use the same schema and the same expiry rule; 1.2.1 will
  turn unbaselined warnings into blocking findings.

## Consumer parity

| Reader | Manifest | Result |
| --- | --- | --- |
| 1.1.0 | 1.1.0 | exit 0 |
| 1.2.0 | 1.1.0 | exit 0 (new fields optional) |
| 1.2.0 | 1.2.0 | exit 0 |
| 1.1.0 | 1.2.0 | exit 2 — `unexpected key(s) artifact_repository, body_hash_scope` |

Upgrade order: consumers before producers. CBM/CBC require `body_hash_scope`
for their real E2E, so they must move to 1.2.0 before the train can pass.

## Unresolved items

1. **Publish approval** — owner decision. No tag, no PyPI upload, no Release.
2. **CBM encoding FAIL** — the target-scoped gate on CBM `8acb628` fails on
   `audit/v1.2.0-rc/b5-probe-declared.stdout.txt` (invalid UTF-8). This is a real
   CBM finding, preserved in the CBM manifest; it is not waived and must be
   fixed by CBM.
3. **Warning baselines** — CBS (BIN 1, DOC 32), CBM (DOC 11). They are warnings
   in 1.2.0; 1.2.1 needs an accepted baseline with expiry before they block.
4. **RC rebuild policy** — the RC workflow ignores docs-only pushes
   (`paths-ignore: docs/**, *.md`). Code commits still rebuild and require
   re-attestation. The candidate for this audit is `163f138` / run
   `42603720434`; earlier candidates are superseded.

## Reproduction

```bash
python -m pytest -q tests
python -m cbp.cli --root . --v12 --v12-report v12-report.json
gh run view 42603720434 --repo JunxiangPan/cbp-action
gh attestation verify cbp_action-1.2.0-py3-none-any.whl --repo JunxiangPan/cbp-action
```

Release path: after the RC hashes are checked, `release.yml` remints the CI
manifest (RC `artifact_hashes`, recomputed `evidence_sha256`, preserved gate /
body / commit fields), re-verifies it, and asserts `--check-only` before
publishing. Preflight performs the same remint.

Preflight (read-only): `PREFLIGHT_OK tag=v1.2.0 ci_run=42604400520
rc_run=42603720434 commit=163f138` — raw output in
`docs/1.2.0/evidence/preflight.txt`.

Self-audit: `docs/1.2.0/SELF_AUDIT.md`. Release steps that must not be executed
without approval: `docs/1.2.0/RELEASE_RUNBOOK.md`.

Stop here. Human re-audit is required before tagging 1.2.0 or publishing.
