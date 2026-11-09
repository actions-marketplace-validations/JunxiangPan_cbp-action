# External-package quality-manifest generator (1.2.0 field capability)

Status: **RC only, awaiting human re-audit**. This adds fields and two commands,
not a thirteenth rule.

## Gate report provenance

A target manifest must be built from a gate report produced on the target root
with explicit identity:

```bash
python -m cbp.cli --root <target> --mode audit --report-json gate.json \
  --package-id <cbc|cbm> --producer-id cbp --version v0.1.0
```

`--package-id`, `--producer-id` and `--version` are written into the report; the
gates are the real target gates. A CBP-self report (package_id `cbp`, version
`v0.0.0`) cannot be reused.

## Manifest command

```bash
python -m cbp.cli manifest \
  --package-id cbc --producer-id cbp --version v0.1.0 \
  --gate-report gate.json \
  --artifact dist/pkg-0.1.0-py3-none-any.whl \
  --artifact dist/pkg-0.1.0.tar.gz \
  --release-body RELEASE_BODY.md \
  --body-hash-scope base \
  --evidence gate.json \
  --out quality-manifest.json
```

`--artifact` and `--evidence` are repeatable; `--artifact-sha256 NAME=HEX`
checks an expected digest.

## Output

Always includes:

```text
schema_version, package_id, producer_id, version,
gate_status, applicable_gate_count, skip_count, skip_ratio,
blocking_skip, gates[], artifact_hashes, release_body_hash,
evidence_sha256, body_hash_scope
```

`package_id` is the subject under test, `producer_id` is the component that ran
the gates. `gates[]` are copied from the target gate report. `artifact_hashes`
maps each artifact basename to a bare sha256. `release_body_hash` hashes the
**base** body: the bytes before `<!-- CBC-EVIDENCE-BEGIN -->` when that marker is
present, otherwise the whole file.

## Validation and exit codes

| Situation | Exit |
| --- | --- |
| manifest written | 0 |
| missing gate report / artifact / release body / evidence | 2 |
| `body_hash_scope` missing or not `base` | 2 |
| artifact digest mismatch | 2 |
| gate report `package_id` / `producer_id` / `version` mismatch | 2 |
| gate report invalid, or SKIPPED without a reason | 2 |
| gate report `FAIL` | 0, manifest keeps `FAIL` |

Nothing is written on a failure. Identity mismatch is checked before any file
write:

```text
gate report package_id mismatch: 'cbp' != 'cbc'
gate report version mismatch: 'v0.0.0' != 'v0.1.0'
```

## Real E2E — CBC

Target: CBC `11943f14f8bc5907b17338f576d9fee493e798d7` (temp read-only clone;
artifacts built from it). Gate report: real CBP run on CBC with
`--package-id cbc --producer-id cbp --version v0.1.0`,
sha256 `213e824392879ce539c6664725d5cd919b7f1d471de8d91b9f75d2557279e78b`.

Manifest:

```text
sha256    01438d31067f05508454c81af068efc61c9797034c778746b94d77e3de63bac0
package_id cbc, producer_id cbp, version v0.1.0
body_hash_scope base, gate_status PASS
gates[encoding] PASS
```

CBC validation:

```text
from cbc_viewer.reports import validate_cbp
CBC_VALIDATE_CBP=PASS
```

R02–R19 with this manifest on a real release dir: **18/18 assertions matched**
(17 executed; R16 SKIP on Windows because symlink creation needs a privilege).
R01 needs an actual upload and is **NOT RUN**. Evidence:
`docs/1.2.0/evidence/cbc-r01-r19/`.

Earlier manifests are historical: `f897bc90…` (artifacts not retained) and
`5f952d9b…` (earlier R01–R19 run). The current manifest is `01438d31…`.

The CBE report used for the chain comes from a real CBE engine run on the CBC
source with a **minimal advisory pack disclosed in the evidence**. No production
CBE pack lists `cbc`, so this is not a production CBC gate; it is only enough to
exercise CBC's chain.

## Real E2E — CBM (B3 only)

Target: CBM `8acb62856b5008b11a072e0e2f6af7df348b1a49`. Gate report: real CBP
run with `--package-id cbm --producer-id cbp --version v0.1.0`,
sha256 `ac4d243b94a13a2aa591ba96890fdd4d2f4984c30e6e199c15b9ccaf102be7d3`.

The real target gate is **FAIL**:

```text
encoding: FAIL audit/v1.2.0-rc/b5-probe-declared.stdout.txt:
  invalid UTF-8: 'utf-8' codec can't decode byte 0xcb in position 35
```

Manifest `967f15ccd8f222518ceb3c613ffda8d4f2ed04cfede958485f0bd79531e410cb`
keeps `gate_status: FAIL`; it is not rewritten to PASS. CBM validation:

```text
from cbm_attach.reports import load_report
CBM_LOAD=PASS package_id=cbm version=v0.1.0
B3_FIELDS body_hash_scope=base, release_body_hash, artifact_hashes=2, evidence_sha256
```

**B3 is field-level complete. B2 is not claimed**: there is still no real CBE
report with `package_id: "cbm"` + `producer_id`.

## Test coverage

`tests/test_package_manifest.py` (16 tests): subject/producer/version written;
gate report identity mismatch (`package_id`, `version`) is exit 2 with no file;
manifest gates equal the gate report gates; base body excludes the CBC appendix;
missing gate/artifact/body/evidence; missing or `full` scope; digest mismatch;
stable hashes; `FAIL` stays `FAIL`; SKIPPED without a reason rejected; the gate
report generator records target identity and two targets produce different
bytes. Full suite: **421 passed**.
