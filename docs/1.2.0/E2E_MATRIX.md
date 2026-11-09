# CBP 1.2.0 — Real-repository E2E matrix

Status: **RC evidence, awaiting human re-audit.** No repository outside
`cbp-action-release` was modified. Target repositories were fetched at the
requested commits into temporary read-only copies.

## Method

```bash
python -m cbp.cli --root <repo> --v12 --v12-report <report>.json
```

Read-only: the rule engine reads files, runs `git status` (no index writes) and
parses YAML/Python text. Reports are written outside the scanned repositories.
Windows paths are passed in native form because `git -C` does not accept MSYS
`/d/...` paths.

| Repository | Tip | How |
| --- | --- | --- |
| CBP (`1.2.0-dev`) | this branch | working tree |
| CBS | `dcd96732b58b6991fdddf80f17ece52585c63da9` | temp clone |
| CBE | `9a1f5f2891eeb06682107d3a82bf8b2ef5746955` | temp clone |
| CBM | `8acb62856b5008b11a072e0e2f6af7df348b1a49` | temp clone |
| CBC | `11943f14f8bc5907b17338f576d9fee493e798d7` | temp clone |

## Matrix

`P` = PASS, `W(n)` = WARN with n findings, `F(n)` = FAIL with n findings.

| Rule | CBP | CBS | CBE | CBM | CBC |
| --- | --- | --- | --- | --- | --- |
| CBP-CI-001 TEST_ROOTS_IN_CI | P | P | P | **P** | P |
| CBP-VER-001 VERSION_SYNC | P | P | P | P | P |
| CBP-QA-001 QA_COUNTS_CONSISTENT | P | P | P | P | P |
| CBP-DEBT-001 DEBT_EVIDENCE | P | P | P | P | P |
| CBP-SIGN-001 SIGN_TOOLS_IN_TAG | P | P | P | P | P |
| CBP-WT-001 WORKTREE_CLEAN_AFTER_GATES | P | P | P | P | P |
| CBP-BIN-001 BINARY_AUTHENTICODE | P | W(1) | P | P | P |
| CBP-DOC-001 DOC_REFERENCES_EXIST | P | W(32) | P | W(11) | P |
| CBP-CLAIM-001 CAPABILITY_CLAIMS | P | P | P | P | P |
| CBP-COV-001 COVERAGE_HARD | P | P | P | P | P |
| CBP-PROOF-001 PROOF_HIGH_TIER | P | P | P | P | P |
| CBP-SLOP-001 DOCSTRING_SLOP | P | P | P | P | P |
| **Exit** | 0 | 0 | 0 | 0 | 0 |

**No blocking rule failed on any current tip.** CBM CI-001 moved from F(1) to
PASS after CBM added its CI test job. The only findings are warnings.

## Warnings

Warning rules do not block in 1.2.0 (they will in 1.2.1); they are recorded so a
baseline can be reviewed.

| Repository | Rule | Count | Classification |
| --- | --- | ---: | --- |
| CBS | CBP-BIN-001 | 1 | true positive: `START-INSTALLER.exe` has no Authenticode blob |
| CBS | CBP-DOC-001 | 32 | true positive: documentation drift (old status docs, removed tests, runtime-only paths) |
| CBM | CBP-DOC-001 | 11 | true positive: README references `cbm-evidence/*` runtime paths that are not in the tree |

No warning is a false positive after the implementation fixes listed below.

## Gate provenance (external manifest)

The CBC/CBM gate reports are no longer CBP-self reports. They are produced by
running the gates on the target root with explicit identity:

```bash
python -m cbp.cli --root <target> --mode audit --report-json <report>.json \
  --package-id <cbc|cbm> --producer-id cbp --version v0.1.0
```

| Target | Gate report sha256 | package_id / producer_id / version | Result |
| --- | --- | --- | --- |
| CBC `11943f14` | `213e824392879ce539c6664725d5cd919b7f1d471de8d91b9f75d2557279e78b` | `cbc` / `cbp` / `v0.1.0` | PASS |
| CBM `8acb628` | `ac4d243b94a13a2aa591ba96890fdd4d2f4984c30e6e199c15b9ccaf102be7d3` | `cbm` / `cbp` / `v0.1.0` | **FAIL** |

The two reports are byte-different. CBM's real gate finding is:

```text
encoding: FAIL audit/v1.2.0-rc/b5-probe-declared.stdout.txt:
  invalid UTF-8: 'utf-8' codec can't decode byte 0xcb in position 35
```

This is a true CBM finding at its current tip, not a CBP self-report and not a
rule false positive. The CBM manifest preserves `gate_status: FAIL`; it is not
rewritten to PASS.

`cbp manifest` rejects a gate report whose `package_id`, `producer_id` or
`version` does not match its own arguments (exit 2, no file written).

## External-package manifest E2E (CBC / CBM)

| Target | Manifest | Target-side validation |
| --- | --- | --- |
| CBC `11943f14` | `01438d31067f05508454c81af068efc61c9797034c778746b94d77e3de63bac0`, `package_id cbc`, `producer_id cbp`, `v0.1.0`, base | `cbc_viewer.reports.validate_cbp` → PASS |
| CBM `8acb628` | `967f15ccd8f222518ceb3c613ffda8d4f2ed04cfede958485f0bd79531e410cb`, `package_id cbm`, `producer_id cbp`, `v0.1.0`, base | `cbm_attach.reports.load_report` → PASS; B3 fields complete; `gate_status FAIL` preserved |

CBC manifests recorded across the audit:

| Manifest | Role |
| --- | --- |
| `f897bc905d4cebfa82cc83f137440cb0a024e0dd060eaa022bca1fb7a3942724` | historical; artifacts not retained |
| `5f952d9bf82413520b87d31a41fba85f49e8242e203f83cc32e6c3d33a5cab20` | earlier R01–R19 run |
| `01438d31067f05508454c81af068efc61c9797034c778746b94d77e3de63bac0` | current R01–R19 run, target-scoped gate report |

CBC R02–R19 on the current inputs: **18/18 assertions matched** (17 executed;
R16 skipped on Windows because symlink creation needs a privilege). R01 requires
an actually uploaded release and is **NOT RUN**; no upload is claimed. Evidence:
`docs/1.2.0/evidence/cbc-r01-r19/`.

CBM B3 is field-level complete (`body_hash_scope`, `release_body_hash`,
`artifact_hashes`, `evidence_sha256`). **B2 is not claimed**: no real CBE report
with `package_id: "cbm"` exists.

## Historical: CBS contract/v1.7.1

Earlier in the audit, `contract/v1.7.1` @ `5d0b100` failed CBP-WT-001 with three
committed conflict markers in `.github/workflows/vm-proof.yml:15/16/18`. That
finding is historical; the current CBS tip passes all twelve rules.

## False positives found and fixed in the implementation

| Symptom | Fix | Fixture |
| --- | --- | --- |
| Inline `run: pytest` ignored | parse both block and inline `run:` | `test_ci_001_passes_when_the_root_runs` |
| Bare `pytest` (no path) did not cover roots | treat a pytest line without any root path as covering all roots | `test_ci_001_ignores_a_path_in_a_comment` |
| `passed`/`PASSED` QA status rejected | accept PASS/PASSED/FAIL/FAILED/SKIP/SKIPPED/WARN/PARTIAL | `test_qa_001_passes_consistent_counts` |
| `examples/…/tests` treated as a project root | ignore examples/fixtures/vendor/third_party | CBP self-run |
| `docs/v1.7/*`, `schemas/v1.7/*` treated as local | external contract namespace | CBE run |
| Planned links flagged | skip lines marked pending/planned/not yet/future/todo | CBE matrix |
| Bare filenames flagged | resolve a bare filename as weak, never fatal | CBP self-run |
| Command names in code spans/fences/headings flagged as claims | strip code, skip headings and CLI usage | CBE run |
| Temporary `.tmp-*` clones scanned by rules | ignore `.tmp-*` in every file walk | CBP self-run |
| Temp files resolved a missing doc reference by suffix | filter ignored paths in the suffix search | CBP self-run |

No test was deleted to make a rule pass.

## Consumer parity

| Reader | Manifest | Result |
| --- | --- | --- |
| 1.1.0 | 1.1.0 | exit 0 |
| 1.2.0 | 1.1.0 | exit 0 (new fields optional) |
| 1.2.0 | 1.2.0 | exit 0 |
| 1.1.0 | 1.2.0 | exit 2 — unexpected `artifact_repository`, `body_hash_scope` |

Upgrade consumers before producers emit 1.2.0 manifests.

## Waivers used

None. No blocking failure needed a waiver, and no warning was waived.

## Reproduction

```bash
python -m cbp.cli --root "D:\path\to\repo" --v12 --v12-report report.json
python -m cbp.cli --root "D:\path\to\repo" --v12 --v12-only CBP-CI-001
python -m cbp.cli --root "D:\path\to\repo" --mode audit --report-json gate.json \
  --package-id cbc --producer-id cbp --version v0.1.0
python -m cbp.cli manifest --package-id cbc --producer-id cbp --version v0.1.0 \
  --gate-report gate.json --artifact a.whl --artifact a.tar.gz \
  --release-body body.md --body-hash-scope base --out quality-manifest.json
```
