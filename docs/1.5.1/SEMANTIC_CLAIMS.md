# Semantic-claims gate (opt-in)

`--semantic-claims` validates claim/evidence pairs before any optional semantic
backend runs.

## Modes

- `program` (default): deterministic checks only.
- `local`: optional local backend, chosen explicitly.
- `cloud`: optional cloud backend, requires `--semantic-cloud-consent` and
  receives only redacted payloads (emails, IPs, secrets, paths and commands are
  masked). local and cloud are mutually exclusive.

Program validation **always runs first**. If program validation fails or needs
review, no local/cloud backend is called. No evidence is `REVIEW` by default or
`FAIL` with `--semantic-no-evidence fail`; subjective conclusions are
`ADVISORY`; forged evidence/contradictions are `FAIL` (exit 3).

This gate does not replace the mutation or test-quality gates and does not
import CBF or CBE. It is opt-in and does not change default CBP 1.5.0 behavior.

```bash
cbp --root . --semantic-claims --semantic-claims-file semantic-claims.json
cbp --root . --semantic-claims --semantic-mode local --semantic-backend-command "<cmd>"
cbp --root . --semantic-claims --semantic-mode cloud --semantic-cloud-consent   --semantic-backend-command "<cmd>"
```
