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
placeholder
<!-- CBC-EVIDENCE-END -->
