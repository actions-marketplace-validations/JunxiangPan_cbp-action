# CBP 1.3.0 AI audit (shadow mode)

The AI gates (`ai-release`, `ai-test`, `ai-change`) remain **shadow mode**.
They do not block publishing and they do not guarantee safety.

## Backtest

`tests/ai/incidents.json` contains 10 known cases: 6 incidents and 4 clean
cases. The detector flags 5 incidents and 1 clean case.

| Metric | Value |
|---|---|
| TP / FP / FN / TN | 5 / 1 / 1 / 3 |
| Precision | 5/6 = 83.3% |
| Recall | 5/6 = 83.3% |
| Blocking | **false** |

`tools/ai_backtest.py tests/ai/incidents.json` reproduces the numbers. The
false positive is a legacy fixture that the rule intentionally flags; it is not
counted as a release failure. The false negative is an unsigned sidecar being
shipped, which is handled by the provenance verifier as
`BLOCKED_NO_SIGNING_IDENTITY`, not by an AI claim.

## Claim boundary

A green AI audit means "the structured evidence matches the rules we encoded".
It does not mean "AI has guaranteed the release is safe". No natural-language
summary is used as a release gate.
