# CBP 1.2.0 — Rule Matrix and Delivery Plan

Status: **IN PROGRESS** — RC only. No PyPI or GitHub Release until human audit.

## Baseline (1.1.0, frozen)

| Item | Value |
| --- | --- |
| Tag | `v1.1.0` → `f98acf3ed15498b6f16d1a397a5d0f1fe2843fa9` |
| CI | run `42508979653` (success) |
| Action E2E | run `42509274614` (15/15 payload + consumer-parity) |
| Release | run `42509354867` (verify-artifact / publish / clean-verify all success) |
| PyPI | run `42509434236` (success) |
| Consumer parity | run `42509541259` → `CONSUMER_VIEW_OK wheel=466c2b4d… version=v1.1.0` |
| wheel | `cbp_action-1.1.0-py3-none-any.whl` `466c2b4deadb988b9af879e2522fb2f4fdf63821b996851682428e9e87263595` |
| sdist | `cbp_action-1.1.0.tar.gz` `b0aea78736c4d83e5d1bf1f57bc72d23f7a17ec02673aadae7f72edb29540822` |

Branch for this work: `1.2.0-dev`. The `v1.1.0` tag and assets are never moved.

## Scope

1. `body_hash_scope: "base"` in the quality manifest, CLI, and validation.
2. `artifact_repository` in the manifest, CLI, and cross-repository validation.
3. cbc-event 0.1.x JSONL emission (config, token/HMAC, rate limit, default off).
4. Twelve rules (CBP-CI-001 … CBP-SLOP-001).
5. Real-repository E2E (read-only) over CBS/CBE/CBM/CBC tips.
6. RC artifacts + audit package. **No publish.**

## Non-negotiables

- No invented PASS. A blocking rule failure is exit 3.
- No silent skip. Every SKIP is visible, counted, and in the ratio.
- Do not edit CBS/CBE/CBM/CBC. Read-only E2E only.
- Publishing PyPI/GitHub Release waits for human approval.
- Rule false positives are fixed in the fixture or implementation, never by deleting the test.

## Waiver and baseline policy

Every waiver is an object with all four fields:

```json
{"rule": "CBP-CI-001", "path": "quality/tests", "reason": "runs via a separate workflow", "expires": "2026-12-31"}
```

- A waiver applies to one rule and one exact path (or `*` only for documented global exceptions).
- A missing reason, a missing expiry, or an expired expiry is a FAIL, never a silent skip.
- Warning rules may start on a baseline (`baseline/v1.2.0.json`). Every baseline entry carries `expires`; an expired baseline entry fails.
- Waivers and baselines are counted and printed by `--v12-report`.

## Rule matrix

Severity: **B** = blocking (1.2.0), **W** = warning + baseline (1.2.0), blocking in 1.2.1.

| ID | Rule | Sev | Failure condition | Fixtures (pass / fail / false-positive guard) | Status |
| --- | --- | --- | --- | --- | --- |
| CBP-CI-001 | `TEST_ROOTS_IN_CI` | B | a test root is never executed by any CI workflow | `ci_all_roots` / `ci_missing_root` / `root_in_comments` | implemented |
| CBP-VER-001 | `VERSION_SYNC` | B | VERSION, pyproject, config and CHANGELOG disagree | `versions_synced` / `version_mismatch` / `changelog_old_entries` | implemented |
| CBP-QA-001 | `QA_COUNTS_CONSISTENT` | B | declared counts ≠ row statuses; `Covered: 0` contradicts coverage disclosure | `qa_consistent` / `qa_count_mismatch` / `qa_covered_zero_with_coverage` | implemented |
| CBP-DEBT-001 | `DEBT_EVIDENCE` | B | FIXED / NOT_FIXED entry has no file or number | `debt_with_evidence` / `debt_without_evidence` / `debt_word_in_prose` | implemented |
| CBP-SIGN-001 | `SIGN_TOOLS_IN_TAG` | B | sign workflow references a script absent from the tag tree | `sign_tools_present` / `sign_tool_missing` / `script_in_comment` | implemented |
| CBP-WT-001 | `WORKTREE_CLEAN_AFTER_GATES` | B | tracked files changed by a gate run, or a tracked file contains a conflict marker (`<<<<<<<`, `>>>>>>>`, `|||||||`, or `=======` inside a conflict) | `wt_clean` / `wt_dirty` / `untracked_only`; `wt_conflict_marker` / `wt_end_marker` / `wt_separator_only` / `wt_untracked_marker` | implemented |
| CBP-BIN-001 | `BINARY_AUTHENTICODE` | W | installer exe unsigned and no waiver | `exe_signed` / `exe_unsigned` / `no_exe` | implemented |
| CBP-DOC-001 | `DOC_REFERENCES_EXIST` | W | doc references a missing test/file path | `doc_refs_ok` / `doc_ref_missing` / `example_path` | implemented |
| CBP-CLAIM-001 | `CAPABILITY_CLAIMS` | W | enforce/isolation claim without implementation or `audit-only` marker | `claim_backed` / `claim_unbacked` / `quoted_claim` | implemented |
| CBP-COV-001 | `COVERAGE_HARD` | W | coverage threshold downgraded to warning/0 | `cov_hard` / `cov_downgraded` / `cov_other_gate` | implemented |
| CBP-PROOF-001 | `PROOF_HIGH_TIER` | W | proof lacks SCM/ACL/service-account markers and no waiver | `proof_high` / `proof_low` / `proof_other_format` | implemented |
| CBP-SLOP-001 | `DOCSTRING_SLOP` | W | template docstrings above the configured threshold | `slop_below` / `slop_above` / `slop_quoted` | implemented |

Every rule ships: positive fixture, negative fixture, false-positive guard fixture, JSON finding with rule id + path, exit-code assertion, and waiver test.

## Exit codes

| Situation | Exit |
| --- | --- |
| all rules pass (or only waived/baselined) | 0 |
| blocking rule fails | 3 |
| warning rule fails (no baseline) | 0, visible WARN (1.2.1 blocks) |
| missing/invalid config, malformed waiver, unsupported `body_hash_scope` | 2 |
| skip ratio above threshold | 4 |

## Delivery checklist

- [x] Step 0: baseline, branch, this file
- [x] Step 1: `body_hash_scope`, `artifact_repository`, cbc-event emitter
- [x] Step 2: rules 1–6 with fixtures and tests
- [x] Step 3: rules 7–12 with warning baseline and expiry
- [x] Step 4: read-only E2E matrix across CBS/CBE/CBM/CBC + consumer parity (docs/1.2.0/E2E_MATRIX.md)
- [x] Step 5: 1.2.0 RC wheel/sdist + attestation, CHANGELOG/README/UPGRADING, no publish
- [x] Step 6: audit package (docs/1.2.0/AUDIT_PACKAGE.md), stopped for human audit

## Step 1 implementation notes

`body_hash_scope`

- `tools/dogfood_manifest.py` writes `body_hash_scope: "base"`; only `base` is accepted by `report_schema.BODY_HASH_SCOPES`.
- `--body-hash-scope full` (or any other value) is an input error: exit 2.
- `--parse-report --require-body-scope` rejects a manifest that omits the field (exit 2). Without the flag, a 1.1.0-era manifest without the field still parses.
- `release_body_hash` covers the generated body only; the base scope means "the body as generated", not later ERRATA addenda.

`artifact_repository`

- Recorded in the manifest from `--artifact-repository`, `artifact_repository` in `cbp.json`, or `GITHUB_REPOSITORY`.
- Empty values are omitted from the manifest (not written as an empty string).
- `--parse-report --expected-repository owner/repo` rejects a manifest whose `artifact_repository` differs: exit 2, `cross-repository artifact`.

cbc-event 0.1.x

- Disabled by default. Enable with `--cbc-event-dir PATH` (or `cbc_event.enabled` + `dir` in `cbp.json`, or `CBP_CBC_EVENT_DIR`).
- Writes `events.jsonl` + `head.json`; genesis `sha256:`+64 zeroes; `event_hash = sha256(prev_hash + "\n" + canonical_json(event without event_hash))`.
- Events emitted: `cbp.run.start`, one `cbp.gate.result` per gate, `cbp.run.end`.
- `--cbc-event-max N` caps the run; dropped events are counted and printed as `CBC_EVENT ... dropped=N` (never silent).
- `--cbc-event-hmac-env NAME` reads an HMAC-SHA256 key from the environment and writes `hmac_sha256` on every event. No token is written to the log.

## CBP-WT-001 conflict-marker extension (post-RC request)

Tracked files are read through `git ls-files -z`; binary files and files larger
than 2 MB are skipped. A committed start/end/base marker fails the rule even when
the worktree is clean. A bare `=======` (for example an RST heading underline) is
only treated as a conflict separator when it appears between a start and an end
marker. Untracked files are ignored.

The scan exposed a Windows decoding defect: `text=True` decodes with the locale
codec (GBK), and `git ls-files -z` can contain non-UTF-8 bytes, which left
`stdout` as `None`. `_git` now decodes explicitly as UTF-8 with replacement and
always returns a string.

## External-package manifest (field capability, not a rule)

`cbp manifest` adds `package_id`/`producer_id` as command inputs and writes the
same CONTRACT §5 fields that `dogfood_manifest` writes for CBP itself:
`artifact_hashes`, `release_body_hash`, `evidence_sha256`, `body_hash_scope`,
gate counts and gates. It does not add a thirteenth rule and does not change the
twelve-rule exit-code model.

Real E2E: CBC `validate_cbp` PASS on a generated `package_id: "cbc"` manifest
built from a target-scoped gate report (`package_id=cbc`, `producer_id=cbp`,
`version=v0.1.0`). CBM `load_report` PASS with `package_id: "cbm"` and B3 fields
complete, but the real CBM gate report is FAIL (invalid UTF-8 in a tracked
stdout capture) and the manifest preserves FAIL. B2 remains open. Details:
`docs/1.2.0/EXTERNAL_MANIFEST.md` and `docs/1.2.0/E2E_MATRIX.md`.

## Gate provenance

`cbp manifest` requires the gate report's `package_id`, `producer_id` and
`version` to equal its own arguments. A CBP-self report (package_id `cbp`,
version `v0.0.0`) is rejected with exit 2 before any file is written. The gate
report is generated by running the gates on the target root with
`--package-id/--producer-id/--version`; it is not copied or relabelled.
