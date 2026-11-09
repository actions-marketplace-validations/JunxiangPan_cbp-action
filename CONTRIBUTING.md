# Contributing

## Rules

- Tests must exercise real behavior. Do not add a test that only asserts a
  constant that the test itself set.
- Coverage must not decrease. If a line is untestable, document why and add the
  smallest possible testable exception.
- Do not use `# pragma: no cover` to hide logic. Do not exempt a whole module.
- Do not add a gate that fails closed only when a magic string is present;
  recompute the evidence.
- Keep runtime dependencies at zero unless a gate truly requires a library.
- Every public function or class needs a docstring and accurate parameter names.

## Consumer-view assertions (mandatory for verification features)

A verification feature is not done when the mechanism exists. It is done when an
end-to-end test proves that what the consumer receives *is* what was verified.
Testing that a function returns `True` on a fixture is not enough: the test must
assert that the bytes the consumer runs are the bytes that were proved.

Every change to a verification feature must ship an E2E assertion of that shape.
`e2e-payload` holds the canonical example: the composite action installs a wheel
and the `consumer-parity` job asserts that the installed wheel's SHA256 equals the
release asset digest and passes `gh attestation verify`.

Four releases shipped a verification mechanism that no consumer-view assertion
covered:

| Version | Claimed | Actual | Missing assertion |
|---|---|---|---|
| v0.1.3 | coverage signature | no key, forgeable | "signature is unforgeable" E2E |
| v1.0.2 | wheel hash | nobody read the file | "the hash is read" E2E |
| v1.0.3 | asset inventory check | nobody generated the inventory | "missing inventory must FAIL" E2E |
| v1.0.8 | `sha256sum -c` + OIDC | it checked the same tree it ran from | "executed == attested" E2E |

If that assertion had existed three weeks ago, none of the first three would have
shipped.

## No build artifacts in the repository

The repository must not track a wheel, an sdist, `WHEEL_SHA256`, or
`coverage.json`. The `cbp-dist` artifact produced by the `build-artifact` job is
the only build output: every other job downloads it, and the composite action
downloads the released, attested wheel at runtime. `git ls-files dist` must be
empty, and a test enforces it. Local builds go to the gitignored `dist/`;
`coverage.json` embeds the commit fingerprint, so it is regenerated locally and
in CI instead of being committed.

## Local checks

```bash
python -m pip install -e ".[test]"
python -m build --wheel --sdist --outdir dist
python -m coverage run --branch -m pytest -q tests
python -m coverage json -o coverage.json
python tools/stamp_coverage.py --root . --coverage coverage.json
python tools/dogfood_manifest.py --root=. --coverage-json=coverage.json --output=quality-manifest.json --notes-template=docs/RELEASE_NOTES.md --notes-output=docs/RELEASE_NOTES.generated.md
python -m cbp.cli --root . --mode enforce
```

## Pull requests

Describe the failure mode the change prevents. Include the test that would fail
without the change and the command output showing it now passes.

## Versioning and compatibility

Versioning is part of the review, not a release-time afterthought.

- Every minor release must be backward compatible.
- New gates, rules, inputs, and config fields are opt-in or safe by default.
- Legacy config fields must be auto-mapped in memory and emit a warning.
- A deprecated field remains usable for at least two minor releases.
- A major release needs a migration guide and a maintained previous major line.

See [`UPGRADING.md`](UPGRADING.md) and [`ROADMAP.md`](ROADMAP.md). A pull request
that removes a legacy field without this process is rejected.

## CB governance checks

CBP is the calibrator, not an exception. Every CBP change must pass the eight
gates:

```bash
python -m pip install -e ".[test]"
python -m build --wheel --sdist --outdir dist
python -m coverage run --branch -m pytest -q tests
python -m coverage json -o coverage.json
python tools/stamp_coverage.py --root . --coverage coverage.json
python tools/dogfood_manifest.py --root=. --coverage-json=coverage.json --output=quality-manifest.json --notes-template=docs/RELEASE_NOTES.md --notes-output=docs/RELEASE_NOTES.generated.md
python -m cbp.cli --root . --mode enforce
python tools/audit_rule_sources.py --root .
```

New gate types or rule categories must update the registry and the schema.

## Problem reflection mechanism

When any CB component (CBS, CBR, CBM, CBC, or CBP) discovers a new failure class,
the fix pull request must contain three parts:

1. the business-code fix;
2. the CBP detection rule;
3. a negative test that constructs a violating sample and asserts CBP blocks it,
   plus a positive test that constructs a compliant sample and asserts CBP allows
   it.

Register both tests by full pytest node ID in `rules/registry.json`. CI collects
each node and executes it; a missing or failing node blocks the merge. A rule
without a negative test and a positive test is not mergeable.

Record the source in `RULES-CHANGELOG.md`: component, PR, issue, rule ID, and both
node IDs. If CBP cannot detect the issue, or should not, the pull request must
state the reason and a human must approve the exception.

`rules/registry.json` is append-only for rule IDs. An existing rule may be marked
`deprecated`, never deleted. Source fields may only be corrected for a documented
typo recorded in `RULES-CHANGELOG.md`.
