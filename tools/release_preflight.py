"""Preflight a CBP release without creating a Release or uploading to PyPI.

The release artifact is the attested ``cbp-rc`` bundle, not the CI ``cbp-dist``
bundle. The quality manifest still comes from the CI run. The tag commit, the
RC run head and the CI run head must all be the same commit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HASH_RE = re.compile(r"^[0-9a-f]{64}$")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.remint_manifest import RemintError, remint  # noqa: E402


class PreflightError(RuntimeError):
    """A release precondition failed (exit 3)."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _one(directory: Path, pattern: str, label: str) -> Path:
    matches = sorted(directory.glob(pattern))
    if len(matches) != 1:
        raise PreflightError(f"expected exactly one {label} in {directory}, found {len(matches)}")
    return matches[0]


def _full_commit(value: str) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", f"{value}^{{commit}}"],
        capture_output=True, text=True, check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else value.strip()


def _same_commit(left: str, right: str) -> bool:
    left_full = _full_commit(left)
    right_full = _full_commit(right)
    if left_full == right_full:
        return True
    return (
        len(left_full) >= 7 and len(right_full) >= 7
        and (left_full.startswith(right_full) or right_full.startswith(left_full))
    )


def _check_hash(path: Path, expected: str, label: str) -> None:
    if not HASH_RE.fullmatch(expected):
        raise PreflightError(f"{label} expected hash is not 64 lowercase hex: {expected!r}")
    actual = _sha256(path)
    if actual != expected:
        raise PreflightError(f"{label} hash mismatch: expected {expected}, got {actual}")


def _check_rc_assets(rc_dir: Path, wheel: Path, sdist: Path) -> None:
    path = rc_dir / "RC_ASSETS.sha256"
    if not path.is_file():
        raise PreflightError("rc/RC_ASSETS.sha256 is missing")
    declared: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) != 2 or not HASH_RE.fullmatch(parts[0].lower()):
            raise PreflightError(f"malformed RC_ASSETS line: {line!r}")
        name = parts[1].lstrip("*")
        name = name.rsplit("/", 1)[-1]
        declared[name] = parts[0].lower()
    for artifact in (wheel, sdist):
        if artifact.name not in declared:
            raise PreflightError(f"RC_ASSETS.sha256 does not list {artifact.name}")
        if declared[artifact.name] != _sha256(artifact):
            raise PreflightError(f"RC_ASSETS.sha256 hash mismatch for {artifact.name}")


def _check_manifest(artifact_dir: Path, wheel: Path, sdist: Path, release_body: bytes | None, repository: str, rc_run_id: str) -> None:
    manifest = artifact_dir / "quality-manifest.json"
    digest = artifact_dir / "quality-manifest.json.sha256"
    if not manifest.is_file() or not digest.is_file():
        raise PreflightError("artifact/quality-manifest.json or .sha256 is missing")
    data = json.loads(manifest.read_text(encoding="utf-8"))
    for field in ("schema_version", "package_id", "producer_id", "version",
                  "gate_status", "gates", "artifact_hashes", "release_body_hash",
                  "evidence_sha256", "body_hash_scope"):
        if field not in data:
            raise PreflightError(f"quality-manifest is missing {field}")
    expected = digest.read_text(encoding="utf-8").split()[0].lower()
    if expected != _sha256(manifest):
        raise PreflightError("quality-manifest.json.sha256 does not match the manifest")
    if repository and rc_run_id:
        data["artifact_repository"] = {
            "repository": repository,
            "run_id": rc_run_id,
            "artifact_name": "cbp-rc",
        }
    try:
        remint(data, [wheel, sdist], release_body)
    except RemintError as exc:
        raise PreflightError(f"manifest cannot be reminted from the RC artifacts: {exc}") from exc


def _check_body(rc_dir: Path, wheel: Path, notes: Path, tag: str, ci_run: str, e2e_run: str) -> bytes:
    if not notes.is_file():
        raise PreflightError(f"release notes missing: {notes}")
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "RELEASE_BODY.md"
        command = [
            sys.executable, str(ROOT / "tools" / "generate_release_body.py"),
            "--wheel", str(wheel), "--version", tag, "--notes", str(notes),
            "--output", str(output), "--ci-run", ci_run,
            "--double-build-run", ci_run, "--sarif-run", ci_run,
        ]
        if e2e_run:
            command += ["--e2e-run", e2e_run]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode != 0 or not output.is_file() or output.stat().st_size == 0:
            raise PreflightError(
                "release body generation failed: "
                + (result.stderr.strip() or result.stdout.strip() or "no output")
            )
        return output.read_bytes()


def validate(
    rc_dir: Path,
    artifact_dir: Path,
    *,
    tag: str,
    expected_wheel_sha256: str,
    expected_sdist_sha256: str,
    tag_commit: str,
    rc_head: str,
    ci_head: str,
    ci_run: str = "",
    e2e_run: str = "",
    repository: str = "",
    rc_run: str = "",
) -> dict[str, str]:
    """Validate already-downloaded inputs; return the resolved artifact paths."""
    if not _same_commit(tag_commit, rc_head):
        raise PreflightError(f"tag {tag} is {tag_commit}, RC run head is {rc_head}")
    if not _same_commit(tag_commit, ci_head):
        raise PreflightError(f"tag {tag} is {tag_commit}, CI run head is {ci_head}")
    if not rc_dir.is_dir():
        raise PreflightError(f"rc directory missing: {rc_dir}")
    if not artifact_dir.is_dir():
        raise PreflightError(f"artifact directory missing: {artifact_dir}")
    wheel = _one(rc_dir, "*.whl", "wheel")
    sdist = _one(rc_dir, "*.tar.gz", "sdist")
    _check_hash(wheel, expected_wheel_sha256.lower(), "wheel")
    _check_hash(sdist, expected_sdist_sha256.lower(), "sdist")
    _check_rc_assets(rc_dir, wheel, sdist)
    notes = artifact_dir / "docs" / "RELEASE_NOTES.generated.md"
    body = _check_body(rc_dir, wheel, notes, tag, ci_run, e2e_run)
    _check_manifest(artifact_dir, wheel, sdist, body, repository, rc_run)
    return {"wheel": str(wheel), "sdist": str(sdist)}


def _run_head(run_id: str, repository: str) -> str:
    result = subprocess.run(
        ["gh", "api", f"repos/{repository}/actions/runs/{run_id}", "--jq", ".head_sha"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        raise PreflightError(f"cannot read run {run_id}: {result.stderr.strip()}")
    return result.stdout.strip()


def _run_conclusion(run_id: str, repository: str) -> str:
    result = subprocess.run(
        ["gh", "api", f"repos/{repository}/actions/runs/{run_id}", "--jq", ".conclusion"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        raise PreflightError(f"cannot read run {run_id}: {result.stderr.strip()}")
    return result.stdout.strip()


def _download(run_id: str, name: str, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["gh", "run", "download", run_id, "-n", name, "-D", str(destination)],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        raise PreflightError(f"download {name} from run {run_id} failed: {result.stderr.strip()}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="release-preflight")
    parser.add_argument("--rc-run-id", required=True)
    parser.add_argument("--ci-run-id", required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--expected-wheel-sha256", required=True)
    parser.add_argument("--expected-sdist-sha256", required=True)
    parser.add_argument("--e2e-run-id", default="")
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--rc-dir", default="")
    parser.add_argument("--artifact-dir", default="")
    parser.add_argument("--tag-commit", default="")
    parser.add_argument("--rc-head", default="")
    parser.add_argument("--ci-head", default="")
    parser.add_argument("--skip-body", action="store_true")
    args = parser.parse_args(argv)

    try:
        if not re.fullmatch(r"v\d+\.\d+\.\d+", args.tag):
            raise PreflightError(f"invalid tag: {args.tag}")
        if not args.repository:
            raise PreflightError("--repository or GITHUB_REPOSITORY is required")
        tag_commit = args.tag_commit or subprocess.run(
            ["git", "rev-parse", f"refs/tags/{args.tag}^{{commit}}"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        rc_head = args.rc_head or _run_head(args.rc_run_id, args.repository)
        ci_head = args.ci_head or _run_head(args.ci_run_id, args.repository)
        if not args.rc_dir or not args.artifact_dir:
            if _run_conclusion(args.rc_run_id, args.repository) != "success":
                raise PreflightError(f"RC run {args.rc_run_id} did not succeed")
            if _run_conclusion(args.ci_run_id, args.repository) != "success":
                raise PreflightError(f"CI run {args.ci_run_id} did not succeed")
        rc_dir = Path(args.rc_dir) if args.rc_dir else Path("rc")
        artifact_dir = Path(args.artifact_dir) if args.artifact_dir else Path("artifact")
        if not args.rc_dir:
            _download(args.rc_run_id, "cbp-rc", rc_dir)
        if not args.artifact_dir:
            _download(args.ci_run_id, f"quality-manifest-{args.ci_run_id}", artifact_dir)
        if args.skip_body:
            # Only the metadata checks; the body generator is covered by release.yml.
            wheel = _one(rc_dir, "*.whl", "wheel")
            sdist = _one(rc_dir, "*.tar.gz", "sdist")
            _check_hash(wheel, args.expected_wheel_sha256.lower(), "wheel")
            _check_hash(sdist, args.expected_sdist_sha256.lower(), "sdist")
            _check_rc_assets(rc_dir, wheel, sdist)
            _check_manifest(artifact_dir, wheel, sdist, None, args.repository, args.rc_run)
            if not _same_commit(tag_commit, rc_head) or not _same_commit(tag_commit, ci_head):
                raise PreflightError("tag / RC / CI commits disagree")
        else:
            validate(
                rc_dir, artifact_dir,
                tag=args.tag,
                expected_wheel_sha256=args.expected_wheel_sha256,
                expected_sdist_sha256=args.expected_sdist_sha256,
                tag_commit=tag_commit, rc_head=rc_head, ci_head=ci_head,
                ci_run=args.ci_run_id, e2e_run=args.e2e_run_id,
            )
    except (PreflightError, OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"PREFLIGHT_FAIL reason={exc}", file=sys.stderr)
        return 3
    print(
        f"PREFLIGHT_OK tag={args.tag} ci_run={args.ci_run_id} rc_run={args.rc_run_id} "
        f"commit={tag_commit} wheel={args.expected_wheel_sha256.lower()} "
        f"sdist={args.expected_sdist_sha256.lower()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
