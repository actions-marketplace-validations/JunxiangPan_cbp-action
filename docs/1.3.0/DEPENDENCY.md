# CBP 1.3.0 dependency-side controls

- Every GitHub Action in CBP workflows is pinned to a full 40-character commit
  SHA; `@v4`/`@main` is rejected by `artifact_integrity.action_pin_findings`.
- `requirements.lock` (or equivalent) must be fully pinned and hashed, and the
  installer must use `--require-hashes`. `CBP-DEP-001` checks both.
- An adjacent `requirements.lock.sha256` (opt-in) detects a lock change after
  approval. The same pattern protects `coverage_allowlist.json`.
- `tools/tag_immutability.py` compares a pinned tag→commit map with the actual
  map and reports moved/missing tags; the expected map must be supplied by the
  release owner.
- Dependency review remains an external review step; CBP can only check the
  recorded lock/installer/pins.
- Self-hosted runners are treated as untrusted by default; see
  `docs/1.3.0/THREAT_MODEL.md` for the contamination assumptions.
