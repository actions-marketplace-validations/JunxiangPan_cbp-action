"""Remint a CI quality-manifest so its artifact hashes describe the RC bundle.

The CI ``cbp-dist`` build and the audited ``cbp-rc`` build are different bytes.
The manifest still comes from the CI run (gate report, body hash, commit), but
``artifact_hashes`` and ``evidence_sha256`` must be recomputed from the RC
artifacts before anything is published. Every other field is preserved.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cbp import report_schema  # noqa: E402


class RemintError(ValueError):
    """Invalid input or a failed remint (exit 2 or 3)."""


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def remint(manifest: dict[str, Any], artifacts: list[Path]) -> dict[str, Any]:
    """Return a copy with RC artifact hashes and a recomputed evidence hash."""
    if not isinstance(manifest, dict):
        raise RemintError("manifest must be a JSON object")
    if not artifacts:
        raise RemintError("at least one --artifact is required")
    hashes: dict[str, str] = {}
    for path in artifacts:
        if not path.is_file():
            raise RemintError(f"artifact missing: {path}")
        if path.name in hashes:
            raise RemintError(f"duplicate artifact basename: {path.name}")
        hashes[path.name] = sha256_file(path)
    updated = dict(manifest)
    updated["artifact_hashes"] = hashes
    unsigned = {key: value for key, value in updated.items() if key != "evidence_sha256"}
    updated["evidence_sha256"] = canonical_sha256(unsigned)
    problems = report_schema.validate_manifest(updated, require_body_scope=True)
    if problems:
        raise RemintError("reminted manifest is invalid: " + "; ".join(problems))
    return updated


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise RemintError(f"manifest missing: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RemintError(f"manifest unreadable: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise RemintError("manifest must be a JSON object")
    return data


def _write_atomic(path: Path, manifest: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n",
    )
    os.replace(temporary, path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="remint-manifest")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--artifact", action="append", default=[])
    parser.add_argument("--out", default="")
    parser.add_argument("--expect-run-id", default="")
    parser.add_argument("--expect-commit", default="")
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args(argv)
    try:
        manifest = _load(Path(args.manifest))
        if args.expect_run_id and str(manifest.get("ci_run_id", "")) != args.expect_run_id:
            raise RemintError(
                f"ci_run_id mismatch: manifest={manifest.get('ci_run_id')!r} expected={args.expect_run_id!r}"
            )
        if args.expect_commit and str(manifest.get("ci_commit_sha", "")) != args.expect_commit:
            raise RemintError(
                f"ci_commit_sha mismatch: manifest={manifest.get('ci_commit_sha')!r} expected={args.expect_commit!r}"
            )
        artifacts = [Path(item) for item in args.artifact]
        updated = remint(manifest, artifacts)
        if args.check_only:
            if manifest.get("artifact_hashes") != updated["artifact_hashes"]:
                raise RemintError("manifest artifact_hashes do not equal the RC artifact hashes")
            if manifest.get("evidence_sha256") != updated["evidence_sha256"]:
                raise RemintError("manifest evidence_sha256 is not the reminted value")
            print(f"REMIT_OK check-only manifest={args.manifest} artifacts={len(artifacts)}")
            return 0
        output = Path(args.out) if args.out else Path(args.manifest)
        _write_atomic(output, updated)
        print(
            f"REMIT_OK manifest={output} sha256={sha256_file(output)} "
            f"artifacts={len(artifacts)} evidence_sha256={updated['evidence_sha256']}"
        )
        return 0
    except RemintError as exc:
        print(f"REMIT_FAIL reason={exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
