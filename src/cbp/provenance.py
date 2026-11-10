"""SLSA-shaped, opt-in release provenance sidecar and offline verifier.

No signing identity is available in this environment. The sidecar is therefore
emitted as UNSIGNED and the verifier reports BLOCKED_NO_SIGNING_IDENTITY; it
never fabricates a signature or a PASS.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

STATEMENT_TYPE = "https://in-toto.io/Statement/v1"
PREDICATE_TYPE = "https://slsa.dev/provenance/v1"
BLOCKED = "BLOCKED_NO_SIGNING_IDENTITY"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(manifest_path: Path, artifacts: list[Path], *, repository: str, run_id: str,
          tag: str, commit: str, generated_at: str,
          signature_status: str = BLOCKED) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    subjects = [{"name": path.name, "digest": {"sha256": _sha(path)}} for path in artifacts]
    return {
        "_type": STATEMENT_TYPE,
        "subject": subjects,
        "predicateType": PREDICATE_TYPE,
        "predicate": {
            "buildDefinition": {
                "buildType": "https://github.com/JunxiangPan/cbp-action/rc@v1",
                "externalParameters": {
                    "repository": repository,
                    "run_id": str(run_id),
                    "tag": tag,
                    "commit": commit,
                },
                "resolvedDependencies": [
                    {"uri": f"pkg:github/{repository}@{commit}", "digest": {"sha1": commit}}
                ],
            },
            "runDetails": {
                "builder": {"id": "https://github.com/JunxiangPan/cbp-action"},
                "metadata": {"invocationId": str(run_id), "startedOn": generated_at},
            },
        },
        "manifest_sha256": _sha(manifest_path),
        "manifest_artifact_hashes": manifest.get("artifact_hashes", {}),
        "signature_status": signature_status,
    }


def write(manifest_path: Path, artifacts: list[Path], output_dir: Path, signed: bool = False, **kwargs: str) -> dict[str, Any]:
    statement = build(manifest_path, artifacts, signature_status="SIGNED" if signed else BLOCKED, **kwargs)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "provenance.json").write_text(
        json.dumps(statement, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output_dir / "predicate.json").write_text(
        json.dumps(statement["predicate"], ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "provenance.sig").write_text(
        json.dumps({"status": statement["signature_status"], "algorithm": "cosign-keyless" if signed else None, "signature": None}, indent=2) + "\n",
        encoding="utf-8",
    )
    return statement


def cosign_verify(path: Path, bundle: Path, identity_regexp: str, issuer: str) -> tuple[bool, str]:
    """Verify one blob with cosign; never trust the JSON status alone."""
    import subprocess
    result = subprocess.run(
        ["cosign", "verify-blob", "--bundle", str(bundle),
         "--certificate-identity-regexp", identity_regexp,
         "--certificate-oidc-issuer", issuer, str(path)],
        capture_output=True, text=True, check=False,
    )
    return result.returncode == 0, (result.stderr or result.stdout).strip()


def verify(provenance_path: Path, manifest_path: Path, artifacts: list[Path], *, bundle_dir: Path | None = None,
           identity_regexp: str = "", oidc_issuer: str = "https://token.actions.githubusercontent.com") -> dict[str, Any]:
    problems: list[str] = []
    try:
        statement = json.loads(provenance_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {"status": "FAIL", "problems": [f"provenance unreadable: {exc}"], "signature": BLOCKED}
    if statement.get("_type") != STATEMENT_TYPE or statement.get("predicateType") != PREDICATE_TYPE:
        problems.append("provenance type/predicateType mismatch")
    subjects = {item.get("name"): item.get("digest", {}).get("sha256") for item in statement.get("subject", [])}
    for path in artifacts:
        if subjects.get(path.name) != _sha(path):
            problems.append(f"{path.name}: subject digest mismatch")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if statement.get("manifest_sha256") != _sha(manifest_path):
        problems.append("manifest_sha256 mismatch")
    if statement.get("manifest_artifact_hashes") != manifest.get("artifact_hashes"):
        problems.append("manifest artifact_hashes mismatch")
    signature = statement.get("signature_status")
    if signature != "SIGNED":
        return {
            "status": BLOCKED,
            "problems": problems,
            "signature": signature,
        }
    if bundle_dir is None:
        problems.append("bundle_dir required to verify a signed provenance sidecar")
        return {"status": "FAIL", "problems": problems, "signature": signature}
    if not identity_regexp:
        problems.append("identity_regexp required to verify keyless signatures")
    for path in [provenance_path, manifest_path, *artifacts]:
        bundle = bundle_dir / (path.name + ".bundle")
        if not bundle.is_file():
            problems.append(f"{bundle.name}: bundle missing")
            continue
        passed, detail = cosign_verify(path, bundle, identity_regexp, oidc_issuer)
        if not passed:
            problems.append(f"{path.name}: cosign verify failed: {detail}")
    return {"status": "FAIL" if problems else "SIGNED", "problems": problems, "signature": signature}
