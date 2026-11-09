# CBC R01–R19 evidence (real inputs)

This directory is the audit record for running CBC's release-chain cases against
a **real CBE report**, **real CBC wheel/sdist**, and a **real CBP
external-package manifest**. CBC was not modified.

## Inputs

| Input | Provenance |
| --- | --- |
| CBC source | `cbc-event` HEAD `11943f14`, temp clone |
| CBC artifacts | `cbc_event-0.1.0-py3-none-any.whl` / `.tar.gz`, built from that archive copy |
| CBE report | CBE `9a1f5f28` engine run on the CBC source with the minimal advisory pack in `pack.json` (package_id `cbc`, version/tag `v0.1.0`, gate PASS) |
| Gate report | target-scoped CBP run (`cbc`/`cbp`/`v0.1.0`), sha256 `213e824392879ce539c6664725d5cd919b7f1d471de8d91b9f75d2557279e78b` |
| CBP manifest | `cbp manifest` with the target-scoped report; sha256 `01438d31067f05508454c81af068efc61c9797034c778746b94d77e3de63bac0` |
| Body | assembled from the real CBC CHANGELOG; upload status is `NOT_UPLOADED` because no CBC release exists |
| Chain | CBC `build_manifest` / `reseal`, not hand-written |

The CBE pack is deliberately minimal (one builtin advisory) and is disclosed here
because no production CBE pack lists `cbc` as a package type. The CBE report is a
real CBE execution, but its rule set is not a production CBC gate.

The manifests `f897bc90…` (artifacts not retained) and `5f952d9b…` (earlier
run) are historical; the current manifest is `01438d31…`. All use the same
external-manifest generator.

## Results

`R01` needs an actually uploaded GitHub release. No CBC release exists, so R01 is
**NOT RUN**; it is not reported as PASS.

`R02`–`R19` were executed with the real release directory. 18/18 assertions
matched (17 executed + R16 skipped on Windows because creating a symlink needs a
privilege the runner does not have; CBC's Linux CI executes it).

| Case | Result |
| --- | --- |
| R01 clean uploaded | NOT RUN (no upload) |
| R02 clean not uploaded | exit 0, chain PASS, NOT_UPLOADED |
| R03 replaced asset | exit 3, hash_mismatch |
| R04 extra asset | exit 3, unexpected_asset |
| R05 missing asset | exit 3, missing_asset |
| R06 checksum manifest missing entry | manifest_entry_missing |
| R07 CBP manifest/chain conflict | exit 3, manifest_conflict |
| R08 wheel digest mismatch | exit 3, hash_mismatch |
| R09 base body rewritten | exit 3, body_hash_mismatch |
| R10 appendix rewritten | exit 3, body_anchor_mismatch |
| R11 link hash | exit 3, chain_hash_mismatch |
| R12 root hash | exit 3, chain_root_mismatch |
| R13 index gap | exit 3, chain_seq_gap |
| R14 duplicate link | exit 3, chain_duplicate |
| R15 unsafe name | exit 3, unsafe_name |
| R16 symlink | SKIP on Windows (privilege) |
| R17 empty chain | exit 2, gate FAIL |
| R18 header metadata bound | exit 3, chain_hash_mismatch |
| R19 asset_link_count | exit 3, chain_asset_count_mismatch |

Full machine-readable output: `r01_r19_results.json`. Harness: `run_cases.py`.

## Reproduction

```bash
# from a workspace containing cbc-dist/, cbe-out/, body.md and quality-manifest.json
CBC_ROOT=<cbc clone> python run_cases.py
```

The harness imports CBC's own `verify_release`, `verify_artifacts`,
`build_manifest`, and `reseal`; it does not hand-write chain links and does not
fake an uploaded release.
