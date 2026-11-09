# cbc v0.1.0 — Release evidence

## Source excerpt (real CBC CHANGELOG)

Unreleased — cbc_viewer 0.1.0

- Added the read-only `cbc_viewer` package and `cbc-viewer` entry point:
  release/event-log hash-chain verification, body rendering, and a GET-only
  GitHub transport.
- Added `cbc-chain.schema.json` and `cbc-report.schema.json`; the first chain
  link is a manifest header binding version/tag/body-hash-scope/source commit.
  `link_count` includes the header/reports/controls/assets; `asset_link_count`
  counts only asset leaves.
- Added the `sealed-v1` body base/appendix rule and F6 NOT_UPLOADED rendering;
  broken chains include `cbc: NOT_UPLOADED`, `broken_link: #<index> <name> — <reason>`,
  and SKIPPED_INFRA materializes a dedicated `

## Honesty boundary

Assembled from CBC 11943f14 for the CBP external-manifest E2E.
Not an official GitHub Release body; upload status is NOT_UPLOADED.

<!-- CBC-EVIDENCE-BEGIN -->
<!-- cbc-evidence {"schema":"cbc-body-anchor/v1","root_hash":"sha256:04010d648d5617610ec0c453fde163b8551a0fa35f6ab6e5eb974e529688f668","link_count":7,"asset_link_count":0,"verified_link_count":7,"appendix_sha256":"sha256:af123af7725a3134df7647db97ea4ad02c4f2535faa1b5d4f834fb037b1aebdb"} -->
## CBC evidence chain

- gate_status: **NOT_UPLOADED**
- cbc_chain_status: **PASS** (file integrity only; this is NOT a release PASS)
- root_hash: `sha256:04010d648d5617610ec0c453fde163b8551a0fa35f6ab6e5eb974e529688f668`
- link_count: 7
- asset_link_count: 0
- broken_link: none
- upload_status: **NOT_UPLOADED**
- upload_blocked_reason: `not_uploaded`
- skip_accounting: CBC is not counted in the CBE/CBP SKIP ratio
<!-- CBC-EVIDENCE-END -->
