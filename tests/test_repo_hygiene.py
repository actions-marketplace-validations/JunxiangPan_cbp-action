"""The repository must ship source only; build artifacts live in CI."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

requires_git = pytest.mark.skipif(
    shutil.which("git") is None or not (ROOT / ".git").exists(),
    reason="git checkout required",
)


def _tracked(pattern: str) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", pattern],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


@requires_git
def test_repo_tracks_no_build_artifacts() -> None:
    assert _tracked("dist/*") == [], "dist/ must stay untracked; the build-artifact job is the only producer"
    assert _tracked("*.whl") == [], "a wheel must never be committed"
    assert _tracked("*.tar.gz") == [], "an sdist must never be committed"


def test_action_installs_only_a_released_attested_wheel() -> None:
    action = (ROOT / "action.yml").read_text(encoding="utf-8")
    assert "gh release download" in action, "the action must fetch the wheel from a release"
    assert "gh attestation verify" in action, "the action must verify provenance before installing"
    assert "dist/cbp_action-" not in action, "the action must not install a wheel committed to the repo"


def test_consumer_parity_job_asserts_installed_equals_released() -> None:
    workflow = (ROOT / ".github" / "workflows" / "e2e-payload.yml").read_text(encoding="utf-8")
    assert "consumer-parity" in workflow
    assert "CONSUMER_VIEW_OK" in workflow
    assert "CONSUMER_VIEW_FAILED" in workflow
