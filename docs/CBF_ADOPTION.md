# CBF adoption — CBP

Status: **PENDING_CBF_0.1.0**

- surfaces: `git` / `api` / `local-ai`
- planned gate: `cbf gate --surface git`
- planned CI job: `cbf-privacy-gate`
- evidence format: `cbf-evidence/v1`

CBP has **not** integrated CBF. There is **no CBF PASS**, and CBP does not
claim CBF compatibility. CBF is an independent project; CBP does not import it
and does not require it to be installed for normal development.

## Phase 0 (current)

- Adoption documented here.
- The `cbf-privacy-gate` CI job name is reserved in this document only; no
  workflow file is added in Phase 0.
- Existing CI does not fake a CBF result and does not use `continue-on-error`
  or `if: false` to bypass it.
- No GitHub Release, PyPI upload, or git push is claimed to have CBF evidence.

## Phase 1 (after CBF 0.1.0rc1)

- Add `cbf.policy.json` pinned to the CBF policy version/hash.
- Wire `cbf-privacy-gate` into the release path and add the local pre-push
  `cbf gate --surface git`.
- Block GitHub Release / PyPI on CBF failure; record `cbf-evidence/v1`.

## Boundary: CBF is not a CBP replacement

- CBF is a **pre-release privacy gate**. In Phase 1 it runs before tag,
  GitHub Release and PyPI upload (`cbf gate --surface git`).
- `cbf-evidence/v1` is an **optional sidecar only**. It is not written into the
  frozen quality-manifest and does not add or remove manifest fields.
- CBP does **not import CBF** and does not make it a runtime/install dependency.
- CBF does **not replace** CBP's own coverage, dependency, docs, binary or
  claims gates. Both CBF and those CBP gates must pass; one cannot waive the
  other.
- Phase 0 has no active CBF gate, no policy pin and no CBF PASS.
