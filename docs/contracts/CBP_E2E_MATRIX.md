# CBP E2E matrix (CBP-01..CBP-15) — DRAFT FOR REVIEW

Status: **APPROVED 2026-11-08 — Phase 0 implemented; not yet frozen upstream.**
Derived from: CONTRACT v1.7 (§1, §4, §5, §8), pinned at `4a437df`
(sha256 `a561f19e0a8e4dba92af82400b5696da18e000ba5362571cb0b40243b9a3afca`),
plus the decided v1.7.1 amendments (HEAD §11 + CBE patch: F2 blocking set,
bare 64-hex hashes, §5.1 `producer_id`).

Freeze target: `public-release/docs/v1.7.1/CBP_E2E_MATRIX.md`. That repository is
read-only from CBP; this file is the CBP-side draft for the CBS thread to freeze.

Not to be confused with `.github/workflows/e2e-payload.yml`: that is an
**action-injection** matrix (hostile inputs into the composite action), not a
CBP gate matrix. The two must not share IDs or CI jobs.

## Rules for every case

- The runner consumes structured JSON only. A case fails if the assertion needs
  to grep stdout, logs, or the step summary.
- Exit codes and `gate_status` follow CONTRACT §1 exactly. A report that exits
  `3` without a valid `gate_status` is an input error: exit `2`.
- `skip_ratio` is computed over `applicable_gate_count` only. `SKIPPED_INFRA`
  is never in the denominator and always blocks publish.
- `0.20` exactly passes; `0.21` exits `4`. When `blocking_skip` is true, exit
  `3` wins over `4`.
- Every case asserts `schema_version`, `package_id`, `producer_id`, `version`,
  `gate_status`, `applicable_gate_count`, `skip_count`, `skip_ratio`,
  `blocking_skip`, `gates[]`, `artifact_hashes`, `release_body_hash`,
  `evidence_sha256` are present and typed.
- Namespace rule (§6): CBP output may carry only `CBP-*` rule IDs.

## Matrix

| ID | Scenario | Input / fixture | exit | gate_status | skip_ratio | blocking_skip | Key assertion | CBE anchor |
|---|---|---|---|---|---|---|---|---|
| CBP-01 | CLI contract | `--help`, `--version`, unknown flag, missing required option | 0 / 0 / 2 / 2 | PASS / PASS / FAIL / FAIL | 0.0 | false | no traceback; JSON error carries the offending flag; unknown flag never silently ignored | CBE-01 |
| CBP-02 | Missing input path | three variants: no asset manifest, no release body, no wheel | 2 | FAIL | 0.0 | false | error names the missing input; no partial PASS; §8 explicitly makes these exit 2, not 3 | CBE-01/03 |
| CBP-03 | Gate FAIL | coverage below floor, other gates PASS | 3 | FAIL | 0.0 | false | `gates[]` marks coverage FAIL with reason; publish blocked | CBE-04 |
| CBP-04 | SKIP above threshold | applicable 5, skipped 2 (0.4); boundary applicable 5, skipped 1 (0.20) | 4 / 0 | FAIL / PASS | 0.4 / 0.2 | false | `skip_ratio` exact; 0.20 passes; 0.21 exits 4 | CBE-08 |
| CBP-05 | Forced gate SKIP | claims, binary, encoding, docs, custom each unconfigured (five sub-cases) | 3 | FAIL | denominator excludes the forced gate | **true** | gate listed as SKIPPED with reason but result is exit 3; never 0; exit 3 wins over 4 | CBE-08 |
| CBP-06 | Consume an external report | valid CBE v1.7.1 report; malformed report (missing `producer_id`, bad JSON) | 0 / 2 | PASS / FAIL | 0.0 | false | valid report contributes findings without crash; malformed report is an input error, never a silent pass | CBE-06 |
| CBP-07 | Infrastructure failure | provider/report fetch timeout; runner 504 simulation | 3 | SKIPPED_INFRA | excluded | false | `SKIPPED_INFRA` is not counted, is not PASS, blocks publish, and appears in its own Release body section | CBE-06 (timeout) |
| CBP-08 | Asset inventory mismatch | three variants: published asset missing from inventory, extra entry, wrong hash | 3 | FAIL | 0.0 | false | manifest lists every published asset except itself; verifier allows the manifest but does not self-hash it | — |
| CBP-09 | Incomplete build artifact | artifact without `RELEASE_ASSETS.sha256`; artifact without `RELEASE_BODY.md` | 2 | FAIL | 0.0 | false | §8 makes a missing asset manifest / release body an input error (2), not a gate failure (3) | — |
| CBP-10 | Publish precondition | tag commit ≠ `manifest.ci_commit_sha`; main CI red | 2 | PRECONDITION_FAIL | 0.0 | false | publish unreachable; no `always()`; no fallback to another run or tag | ORCH-01/05 |
| CBP-11 | Manifest schema_version | missing; non-numeric; unknown future value; `"1"` legacy read; `"2"` current | 2 / 2 / 2 / 0 / 0 | FAIL / FAIL / FAIL / PASS / PASS | 0.0 | false | legacy `"1"` is projected to the v2 model, unknown versions are rejected, never coerced | CBE-03 |
| CBP-12 | Malformed `gates[]` | dict instead of array; entry without `status`; status outside `PASS/FAIL/SKIPPED`; extra property | 2 | FAIL | 0.0 | false | error names the JSON path; no partial manifest accepted | CBE-03 |
| CBP-13 | Hash representation | `artifact_hashes` missing; `sha256:` prefix; uppercase; short hex | 2 | FAIL | 0.0 | false | every sub-case is an input/format error; prefixed value is **not** silently stripped; bare 64 lowercase hex only | CBE-03 |
| CBP-14 | Namespace passthrough | external SARIF carrying `CBE-*` / `CBG-*`; unmapped native rule id | 3 | FAIL | 0.0 | false | CBP SARIF carries only `CBP-*`; unmapped IDs fail instead of being emitted | CBE-07 |
| CBP-15 | Self-bootstrap | previous stable CBP (v1.0.9) in a venv, run against the current built artifact plus a v1-compatible manifest projection | 0 | PASS | 0.0 | false | any 2/3/4 from the previous stable is an E2E failure; new rules stay audit-only until the next version | CBE-11 |

## Resolved decisions (2026-11-08)

**D1 — `schema_version` stays `"1"`.**
CBE already froze `"1"` with `producer_id` required, and a version bump means a
structural break, not an added field. CBP keeps `schema_version: "1"` and emits
`producer_id: "cbp"`; the CBS thread adds `producer_id` to
`quality-manifest.schema.json` when it lands v1.7.1. `CHANGELOG` records
"producer_id added", not "schema_version breaking". A manifest whose
`schema_version` is outside the supported set is an input error (exit 2); this is
implemented and covered by the synthetic old-consumer fixture, not by running an
old CBP binary.

**D2 — missing field is 2, inconsistent value is 3.**
CONTRACT §5 says missing required fields exit `2`, and `artifact_hashes` is a
required schema field, so a missing field is a format error. `3` is reserved for
a present-but-inconsistent inventory (missing/extra/wrong asset, CBP-08). All
four CBP-13 sub-cases are therefore exit `2`.

**D3 — the owner executes the historical body edit.**
`cbp errata` generates and validates the amended body (`ERRATUM:` at the top,
original body and the old trailing section preserved). It does not edit GitHub.
The owner reviews the diff and runs
`gh release edit v1.0.8 --notes-file <corrected>`; CBP then re-runs
`--verify-release v1.0.8` to confirm the machine-readable ERRATUM is recognised.

## Implementation mapping

| Phase | Case(s) | Status |
|---|---|---|
| 0 (contract core) | CBP-01, CBP-02, CBP-03, CBP-11, CBP-12, CBP-13 | **implemented** (`report_schema`, `report_parser`, CLI exit codes) |
| 0.5 (errata) | none (tooling case only) | tool implemented; the v1.0.8 body edit awaits the owner |
| 1 (F3/F5) | CBP-04, CBP-05, CBP-07 | **implemented for force/skip and verify-release infra**; the external-report OSError path and the standalone body section wiring remain |
| 2 (`--rules-path`) | CBP-06, CBP-14 | **implemented** (pack loading, exit 2 on bad input, CBP-only namespace mapping) |
| 3 (F4 / bootstrap) | CBP-10, CBP-15 | CBP-10 (`--require-gate-pass`, tag/CI binding) implemented; CBP-15 self-bootstrap pending |
| 4 (freeze) | all, wired into one `cbp-e2e.yml` workflow | pending — cases are covered across unit/integration tests, not yet as one ID-addressed suite |
| 5 (publish wiring) | CBP-08, CBP-09, CBP-10 | manifest carries artifact hashes and the publish gate requires PASS; asset inventory checks pre-exist |
