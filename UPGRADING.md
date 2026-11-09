# Upgrading CBP

## 1.1.0 → 1.2.0 (RC)

1.2.0 is additive for readers but the manifest grows two fields:

- `body_hash_scope: "base"` — required by CBM/CBC consumers; `full` is not
  supported (exit 2).
- `artifact_repository` — recorded when configured; cross-repository artifacts
  are rejected by `--expected-repository`.

Compatibility is one-way: 1.2.0 parses 1.1.0 manifests, but a pinned 1.1.0
consumer rejects a 1.2.0 manifest with
`unexpected key(s) artifact_repository, body_hash_scope`. Upgrade every consumer
(CBS/CBE/CBM) before a producer emits 1.2.0 manifests. CBM and CBC need
`body_hash_scope` for their real E2E, so they must move first.

New commands are opt-in:

```bash
python -m cbp.cli --root . --v12 --v12-report v12-report.json
python -m cbp.cli --root . --v12 --waivers waivers.json --v12-baseline baseline.json
```

`--v12` does not run the normal gates; it evaluates only the twelve rules.
Blocking-rule failures exit 3; warning-only failures exit 0 with a visible WARN
until 1.2.1.

cbc-event emission stays off unless `--cbc-event-dir` (or `cbc_event.enabled`
with a `dir` in `cbp.json`) is provided.

CBP is infrastructure. A version bump must never be a forced migration for
existing CI.

## Semantic version promise

### Minor releases: `0.1.x -> 0.1.y`

Minor releases are additive and safe:

- no breaking configuration changes;
- new gates, rules, inputs, and fields are opt-in or have safe defaults;
- old `cbp.json` files are read as-is or migrated in memory;
- legacy fields emit a warning, not an error;
- an old workflow only changes `@v0.1.x` to `@v0.1.y`.

### Major releases: `1.x -> 2.0`

A major version is only for a genuinely incompatible architecture change.
It must include:

- a written migration guide;
- a configuration converter when the mapping is mechanical;
- a maintained previous major line for users who cannot move immediately;
- a deliberate opt-in point, never an automatic forced upgrade.

## v0.1.6 compatibility matrix

| Version | Configuration | Action input | CLI | Result |
|---|---|---|---|---|
| v0.1.0 | `installer_core`, `broker_files` | `installer-core` | `--installer-core` | auto-mapped / alias accepted |
| v0.1.1 | `install-command`, `target_files` | `install-command` | `--install-command` | accepted |
| v0.1.6 | adds `schema_version`, `custom_rules`, `evidence_readers`, `release_body`, `coverage_signature` | all optional | all optional | accepted |

Old configurations without `schema_version` are assumed to be `0.1.0` and
migrated in memory. The actual file is not rewritten unless the user chooses to
commit the update.

Legacy aliases are kept through at least v0.2.x:

```text
installer_core -> install_command
broker_files   -> target_files
measured_files -> target_files
installer-core (Action input and CLI) -> install-command
```

## Deprecation window

A deprecated configuration item must remain usable for at least two minor
releases:

```text
v0.1.x: documentation + DeprecationWarning, behavior unchanged
v0.2.x: behavior unchanged, mandatory warning
v0.3.x or later: removal allowed only after a migration guide exists
```

A deprecated item is never the only way to express a required behavior.

## How to upgrade safely

```bash
# 1. keep the old workflow as a branch/tag
git switch -c upgrade-cbp-0.1.6

# 2. change only the action version
#    uses: owner/cbp-action@v0.1.1
# -> uses: owner/cbp-action@v0.1.6

# 3. run the old config unchanged
python -m cbp.cli --root . --mode enforce

# 4. optionally add schema_version and new opt-in rules
```

If CBP prints `CBP_CONFIG_WARN`, the old configuration still ran. Commit the
suggested field names only after reviewing the output.

## Rollback

Revert the action version to the previous minor. CBP does not rewrite the
checked-in configuration during migration, so rollback is a version change, not
a data recovery operation.

## Upgrade gate

Projects can configure an upgrade script, old configuration fixtures, and a
previous/current JSON Schema comparison. The gate runs in CI and fails closed:

```json
{
  "upgrade_script": "pytest tests/test_upgrade.py",
  "upgrade_fixtures": ["tests/fixtures/v0.1.0_config.json"],
  "previous_schema": "schemas/config.v0.1.1.schema.json",
  "current_schema": "schemas/config.schema.json",
  "allow_breaking_changes": false
}
```

A schema regression requires explicit `allow_breaking_changes: true`.
