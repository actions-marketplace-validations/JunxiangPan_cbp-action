"""release.yml must publish the audited cbp-rc bundle, not cbp-dist."""
from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"


def _data() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def test_release_inputs_include_rc_and_expected_hashes() -> None:
    inputs = _data()[True]["workflow_dispatch"]["inputs"]
    for name in ("rc_run_id", "ci_run_id", "release_tag", "e2e_run_id",
                 "expected_wheel_sha256", "expected_sdist_sha256"):
        assert name in inputs, name


def test_publish_downloads_cbp_rc_and_uses_it() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert 'gh run download "$RC_RUN_ID" -n cbp-rc -D rc' in text
    assert "gh release create \"$RELEASE_TAG\" rc/*.whl rc/*.tar.gz" in text
    assert "cbp-dist" not in text


def test_preflight_job_runs_the_tool() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "tools/release_preflight.py" in text
    assert "PREFLIGHT" not in text  # the tool prints the result, not the workflow
    jobs = _data()["jobs"]
    assert "preflight" in jobs
    assert "publish" in jobs and "preflight" in jobs["publish"]["needs"]


def test_publish_remints_and_checks_the_manifest() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "tools/remint_manifest.py" in text
    assert "--release-body rc/RELEASE_BODY.md" in text
    assert "--artifact-repository" in text
    assert "--artifact-name cbp-rc" in text
    assert "Assert manifest artifact and body hashes equal" in text
    assert "Verify manifest binds the published body" in text
    assert "CBP-BODY-001" in text
    assert text.index("Generate the release body that will be published") < text.index("Remint the manifest from the RC hashes")


def test_ai_gate_sees_the_release_asset_manifest() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "cp rc/RELEASE_ASSETS.sha256 dist/RELEASE_ASSETS.sha256" in text


def test_clean_verify_downloads_rc_artifact() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert 'gh run download "$RC_RUN_ID" -n cbp-rc -D dist-verify' in text
    assert "(cd dist-verify && sed 's#  dist/#  #' RC_ASSETS.sha256 | sha256sum -c -)" in text
