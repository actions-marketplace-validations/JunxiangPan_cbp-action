"""Generate a CONTRACT v1.7 quality manifest for an external target package.

CBP's own dogfood generator hard-codes ``PACKAGE_ID = "cbp"``. This module turns
a real gate report plus real target artifacts/body into a manifest whose
``package_id`` is the *subject* (cbc, cbm, ...) and whose ``producer_id`` is the
component that ran the gates (cbp).

Only ``body_hash_scope: "base"`` is supported. For a CBC body the base is the
bytes before ``<!-- CBC-EVIDENCE-BEGIN -->``; for other targets the whole body
is the base. Nothing is written unless every input and hash check passes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from . import report_schema

BASE_MARKER = b"<!-- CBC-EVIDENCE-BEGIN -->"
IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
HASH_RE = re.compile(r"^[0-9a-f]{64}$")


class ManifestError(ValueError):
    """A missing or inconsistent input (CLI exit 2)."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return sha256_bytes(payload.encode("utf-8"))


def base_body(data: bytes) -> bytes:
    """Return the base body: the part CBC hashes, before its evidence appendix."""
    return data.split(BASE_MARKER, 1)[0]


def normalize_version(value: str) -> str:
    text = str(value).strip()
    if text.startswith(("v", "V")):
        text = text[1:]
    if not re.fullmatch(r"\d+\.\d+\.\d+", text):
        raise ManifestError(f"version must look like X.Y.Z, got {value!r}")
    return "v" + text


def _identifier(value: str, label: str) -> str:
    if not isinstance(value, str) or not IDENTIFIER_RE.fullmatch(value.strip()):
        raise ManifestError(f"{label} must be a simple identifier, got {value!r}")
    return value.strip()


def load_gate_report(path: Path) -> dict[str, Any]:
    """Read and validate the subject package's real gate report."""
    if not path.is_file():
        raise ManifestError(f"gate report missing: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ManifestError(f"gate report unreadable: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ManifestError("gate report must be a JSON object")
    package_id = data.get("package_id")
    producer_id = data.get("producer_id")
    version = data.get("version")
    if not isinstance(package_id, str) or not package_id.strip():
        raise ManifestError("gate report is missing package_id")
    if not isinstance(producer_id, str) or not producer_id.strip():
        raise ManifestError("gate report is missing producer_id")
    if not isinstance(version, str) or not version.strip():
        raise ManifestError("gate report is missing version")
    try:
        report_version = normalize_version(version)
    except ManifestError as exc:
        raise ManifestError(f"gate report version is invalid: {version!r}") from exc
    gates = data.get("gates")
    if not isinstance(gates, list) or not gates:
        raise ManifestError("gate report must contain a non-empty gates array")
    normalized: list[dict[str, str]] = []
    for index, gate in enumerate(gates, 1):
        if not isinstance(gate, dict):
            raise ManifestError(f"gates[{index}] must be an object")
        name = gate.get("name")
        status = gate.get("status")
        reason = gate.get("reason", "")
        if not isinstance(name, str) or not name.strip():
            raise ManifestError(f"gates[{index}].name is required")
        if status not in {"PASS", "FAIL", "SKIPPED"}:
            raise ManifestError(f"gates[{index}].status must be PASS, FAIL or SKIPPED")
        if not isinstance(reason, str):
            raise ManifestError(f"gates[{index}].reason must be a string")
        if status == "SKIPPED" and not reason.strip():
            raise ManifestError(f"gates[{index}] is SKIPPED without a reason")
        normalized.append({"name": name.strip(), "status": status, "reason": reason})
    status = data.get("gate_status")
    if status not in {"PASS", "FAIL", "SKIPPED_INFRA", "PRECONDITION_FAIL"}:
        raise ManifestError(f"gate_status is invalid: {status!r}")
    applicable = data.get("applicable_gate_count", len(normalized))
    skip_count = data.get("skip_count", sum(1 for gate in normalized if gate["status"] == "SKIPPED"))
    if not isinstance(applicable, int) or applicable < 0:
        raise ManifestError("applicable_gate_count must be a non-negative integer")
    if not isinstance(skip_count, int) or skip_count < 0:
        raise ManifestError("skip_count must be a non-negative integer")
    ratio = data.get("skip_ratio", (skip_count / applicable) if applicable else 0.0)
    if not isinstance(ratio, (int, float)) or ratio < 0 or ratio > 1:
        raise ManifestError("skip_ratio must be between 0 and 1")
    expected = (skip_count / applicable) if applicable else 0.0
    if abs(float(ratio) - expected) > 1e-9:
        raise ManifestError(f"skip_ratio {ratio} does not equal skip_count/applicable {expected}")
    blocking = data.get("blocking_skip", False)
    if not isinstance(blocking, bool):
        raise ManifestError("blocking_skip must be a boolean")
    return {
        "package_id": package_id.strip(),
        "producer_id": producer_id.strip(),
        "version": report_version,
        "gate_status": status,
        "applicable_gate_count": applicable,
        "skip_count": skip_count,
        "skip_ratio": float(ratio),
        "blocking_skip": blocking,
        "gates": normalized,
    }


def _artifact_hashes(
    artifacts: list[str],
    expected: dict[str, str],
) -> dict[str, str]:
    if not artifacts:
        raise ManifestError("at least one --artifact is required")
    hashes: dict[str, str] = {}
    for item in artifacts:
        path = Path(item)
        if not path.is_file():
            raise ManifestError(f"artifact missing: {path}")
        name = path.name
        if name in hashes:
            raise ManifestError(f"duplicate artifact basename: {name}")
        digest = sha256_bytes(path.read_bytes())
        if name in expected and expected[name] != digest:
            raise ManifestError(
                f"artifact hash mismatch for {name}: expected {expected[name]}, got {digest}"
            )
        hashes[name] = digest
    return hashes


def build_manifest(
    *,
    package_id: str,
    producer_id: str,
    version: str,
    gate_report: Path,
    artifacts: list[str],
    release_body: Path,
    body_hash_scope: str,
    evidence: list[str] | None = None,
    artifact_sha256: dict[str, str] | None = None,
    artifact_repository: str = "",
    out: Path | None = None,
) -> dict[str, Any]:
    """Build the manifest and (optionally) write it atomically."""
    package_id = _identifier(package_id, "package_id")
    producer_id = _identifier(producer_id, "producer_id")
    if body_hash_scope != "base":
        raise ManifestError(
            "unsupported body_hash_scope "
            + repr(body_hash_scope)
            + "; supported: base"
        )
    normalized_version = normalize_version(version)
    report = load_gate_report(gate_report)
    if report["package_id"] != package_id:
        raise ManifestError(
            f"gate report package_id mismatch: {report['package_id']!r} != {package_id!r}"
        )
    if report["producer_id"] != producer_id:
        raise ManifestError(
            f"gate report producer_id mismatch: {report['producer_id']!r} != {producer_id!r}"
        )
    if report["version"] != normalized_version:
        raise ManifestError(
            f"gate report version mismatch: {report['version']!r} != {normalized_version!r}"
        )
    if not release_body.is_file():
        raise ManifestError(f"release body missing: {release_body}")
    body_data = release_body.read_bytes()
    body_digest = sha256_bytes(base_body(body_data))
    hashes = _artifact_hashes(list(artifacts), dict(artifact_sha256 or {}))
    evidence_hashes = []
    for item in evidence or []:
        path = Path(item)
        if not path.is_file():
            raise ManifestError(f"evidence missing: {path}")
        evidence_hashes.append({"name": path.name, "sha256": sha256_bytes(path.read_bytes())})
    evidence_hashes.sort(key=lambda entry: (entry["name"], entry["sha256"]))

    manifest: dict[str, Any] = {
        "schema_version": report_schema.MANIFEST_SCHEMA_VERSION,
        "package_id": package_id,
        "producer_id": producer_id,
        "version": normalized_version,
        "gate_status": report["gate_status"],
        "applicable_gate_count": report["applicable_gate_count"],
        "skip_count": report["skip_count"],
        "skip_ratio": report["skip_ratio"],
        "blocking_skip": report["blocking_skip"],
        "gates": report["gates"],
        "artifact_hashes": hashes,
        "release_body_hash": body_digest,
        "body_hash_scope": body_hash_scope,
    }
    if artifact_repository:
        manifest["artifact_repository"] = artifact_repository
    unsigned = {key: value for key, value in manifest.items() if key != "evidence_sha256"}
    if evidence_hashes:
        manifest["evidence_sha256"] = canonical_sha256(
            {"manifest": unsigned, "evidence": evidence_hashes}
        )
    else:
        manifest["evidence_sha256"] = canonical_sha256(unsigned)
    problems = report_schema.validate_manifest(manifest, require_body_scope=True)
    if problems:
        raise ManifestError("generated manifest is invalid: " + "; ".join(problems))
    if out is not None:
        _write_atomic(Path(out), manifest)
    return manifest


def _write_atomic(path: Path, manifest: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cbp manifest")
    parser.add_argument("--root", default=".")
    parser.add_argument("--package-id", required=True)
    parser.add_argument("--producer-id", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--gate-report", required=True)
    parser.add_argument("--artifact", action="append", default=[])
    parser.add_argument("--artifact-sha256", action="append", default=[],
                        help="NAME=HEX expected artifact digest (repeatable)")
    parser.add_argument("--release-body", required=True)
    parser.add_argument("--body-hash-scope", default="")
    parser.add_argument("--evidence", action="append", default=[])
    parser.add_argument("--artifact-repository", default="")
    parser.add_argument("--out", default="quality-manifest.json")
    args = parser.parse_args(argv)

    expected: dict[str, str] = {}
    for item in args.artifact_sha256:
        name, separator, digest = item.partition("=")
        if not separator or not name or not HASH_RE.fullmatch(digest.lower()):
            print(json.dumps({"gate_status": "FAIL", "exit_code": report_schema.EXIT_INPUT,
                              "error": f"invalid --artifact-sha256 {item!r}; expected NAME=HEX"},
                             ensure_ascii=False))
            return report_schema.EXIT_INPUT
        expected[name] = digest.lower()

    try:
        manifest = build_manifest(
            package_id=args.package_id,
            producer_id=args.producer_id,
            version=args.version,
            gate_report=Path(args.gate_report),
            artifacts=args.artifact,
            release_body=Path(args.release_body),
            body_hash_scope=args.body_hash_scope,
            evidence=args.evidence,
            artifact_sha256=expected,
            artifact_repository=args.artifact_repository,
            out=Path(args.out),
        )
    except ManifestError as exc:
        print(json.dumps({"gate_status": "FAIL", "exit_code": report_schema.EXIT_INPUT,
                          "error": str(exc)}, ensure_ascii=False))
        return report_schema.EXIT_INPUT
    digest = sha256_bytes(Path(args.out).read_bytes())
    print(f"MANIFEST_WRITTEN path={args.out} sha256={digest} "
          f"package_id={manifest['package_id']} producer_id={manifest['producer_id']} "
          f"gate_status={manifest['gate_status']}")
    return report_schema.EXIT_PASS
