"""RC2 schema: v1.2.2 accepted; v1.2.0/v1.2.1 legacy manifests fail."""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schemas" / "manifest.schema.json").read_text(encoding="utf-8"))
FIXTURES = ROOT / "tests" / "fixtures" / "manifest"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_schema_accepts_rc2_manifest() -> None:
    jsonschema.validate(_load("v122-rc2.json"), SCHEMA)


def test_schema_accepts_real_v17_manifest() -> None:
    jsonschema.validate(_load("v122-rc2.json"), SCHEMA)


def test_legacy_v120_manifest_fails() -> None:
    legacy = json.loads((ROOT / "tests" / "fixtures" / "body" / "v120-quality-manifest.json").read_text(encoding="utf-8"))
    try:
        jsonschema.validate(legacy, SCHEMA)
    except jsonschema.ValidationError:
        return
    raise AssertionError("v1.2.0 legacy manifest must fail RC2")


def test_legacy_v121_manifest_fails() -> None:
    try:
        jsonschema.validate(_load("v121-real.json"), SCHEMA)
    except jsonschema.ValidationError:
        return
    raise AssertionError("v1.2.1 legacy manifest must fail RC2")
