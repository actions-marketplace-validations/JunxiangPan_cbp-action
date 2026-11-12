# CBP 1.5.0 — opt-in quality / AI evidence gates

All three gates are opt-in. Default 1.4.0 behavior is unchanged.

## target-mutation

```bash
python -m cbp.cli --root . --target-mutation \
  --mutation-command "python tests/mutation/run_mutations.py" \
  --target-mutation-report mutation-report.json \
  --mutation-threshold 0.95 \
  --changed-code-score 0.90
```

- `--mutation-command` is split with `shlex` and executed **without a shell**.
- `--target-mutation-report` must be JSON with `score` (or `mutation_score`) and
  `changed_code_score`.
- `--mutation-report-sha256` or `<report>.sha256` verifies the report hash.
- Failure exits 3, including in the strict profile.

## test-quality

```bash
python -m cbp.cli --root . --test-quality \
  --test-paths tests --test-language python \
  --test-baseline tests/test-baseline.json
```

Detects tests with no assertion, `assert True`, skip without a reason, and
(deleted tests) names missing from the baseline. `--test-language generic`
supports JS/TS/Java-style `test(...)`/`it(...)` files.

## ai-evidence

```bash
python -m cbp.cli --root . --ai-evidence \
  --ai-evidence-file ai-evidence.json \
  --ai-coverage-json coverage.json \
  --ai-mutation-report mutation-report.json
```

Claim/evidence JSON:

```json
{"claims": [{
  "id": "c1", "claim": "...", "subjective": false,
  "metrics": {"coverage": 90.0, "mutation_score": 1.0},
  "evidence": [{"file": "src/x.py", "line": 12,
                "command": "pytest tests/test_x.py", "sha256": "<64 hex>"}]
}]}
```

- Every evidence entry needs an existing file, valid line, non-empty command
  and matching file SHA256.
- Claimed `coverage` / `mutation_score` contradicting the supplied reports FAIL.
- No evidence and subjective conclusions are **ADVISORY**;
  forged/contradictory evidence is **FAIL** (exit 3).

## Independence

CBP does not import `cbe` and does not require CBE to be installed. The three
gates use only the CBP package and local files. They are not a runtime security
boundary and do not replace CBE policy.
