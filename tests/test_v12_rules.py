"""CBP 1.2.0 rules: fixtures, false-positive guards, waivers, baselines."""
from __future__ import annotations

import json
import subprocess
from datetime import date
from pathlib import Path

import pytest

from cbp import cli, v12_rules as v12


def _write(root: Path, relative: str, text: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _run(root: Path, rule: str, **kwargs):
    results, expired = v12.run_rules(root, only={rule}, **kwargs)
    assert len(results) == 1
    return results[0], expired


def _git_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=root, check=True)


def test_ci_001_passes_when_the_root_runs(tmp_path: Path) -> None:
    _write(tmp_path, "tests/test_a.py", "def test_a(): pass\n")
    _write(tmp_path, ".github/workflows/ci.yml", "jobs:\n  t:\n    steps:\n      - run: |\n          pytest -q tests\n")
    assert _run(tmp_path, "CBP-CI-001")[0].status == "PASS"


def test_ci_001_fails_when_the_root_is_missing(tmp_path: Path) -> None:
    _write(tmp_path, "tests/test_a.py", "def test_a(): pass\n")
    _write(tmp_path, "quality/tests/test_b.py", "def test_b(): pass\n")
    _write(tmp_path, ".github/workflows/ci.yml", "jobs:\n  t:\n    steps:\n      - run: |\n          pytest -q tests\n")
    result = _run(tmp_path, "CBP-CI-001")[0]
    assert result.status == "FAIL"
    assert any("quality/tests" in item for item in result.findings)


def test_ci_001_ignores_a_path_in_a_comment(tmp_path: Path) -> None:
    _write(tmp_path, "tests/test_a.py", "def test_a(): pass\n")
    _write(tmp_path, ".github/workflows/ci.yml", "jobs:\n  t:\n    steps:\n      - run: |\n          # pytest tests\n          echo ok\n")
    assert _run(tmp_path, "CBP-CI-001")[0].status == "FAIL"


def test_ver_001_passes_when_sources_agree(tmp_path: Path) -> None:
    _write(tmp_path, "VERSION", "1.2.0\n")
    _write(tmp_path, "pyproject.toml", '[project]\nversion = "1.2.0"\n')
    _write(tmp_path, "cbp.json", '{"release_version": "1.2.0"}')
    _write(tmp_path, "CHANGELOG.md", "## 1.2.0 — today\n\n## 1.1.0 — older\n")
    assert _run(tmp_path, "CBP-VER-001")[0].status == "PASS"


def test_ver_001_fails_on_a_mismatch(tmp_path: Path) -> None:
    _write(tmp_path, "VERSION", "1.2.0\n")
    _write(tmp_path, "pyproject.toml", '[project]\nversion = "1.2.0"\n')
    _write(tmp_path, "CHANGELOG.md", "## 1.2.0\n")
    _write(tmp_path, "cbp.json", '{"release_version": "1.1.0"}')
    result = _run(tmp_path, "CBP-VER-001")[0]
    assert result.status == "FAIL"
    assert any("cbp.json" in item for item in result.findings)


def test_ver_001_ignores_older_changelog_headings(tmp_path: Path) -> None:
    _write(tmp_path, "VERSION", "1.2.0\n")
    _write(tmp_path, "CHANGELOG.md", "## 1.2.0\n\n## 0.1.0\n")
    assert _run(tmp_path, "CBP-VER-001")[0].status == "PASS"


QA_TABLE = """| Check | Status |
| --- | --- |
| a | PASS |
| b | PASS |
| c | SKIP |

Total: 3
Coverage: 82%
"""


def test_qa_001_passes_consistent_counts(tmp_path: Path) -> None:
    _write(tmp_path, "FINAL_QA_REPORT.md", QA_TABLE)
    assert _run(tmp_path, "CBP-QA-001")[0].status == "PASS"


def test_qa_001_fails_on_a_count_mismatch(tmp_path: Path) -> None:
    _write(tmp_path, "FINAL_QA_REPORT.md", QA_TABLE.replace("Total: 3", "Total: 4"))
    result = _run(tmp_path, "CBP-QA-001")[0]
    assert result.status == "FAIL"
    assert any("declared total" in item for item in result.findings)


def test_qa_001_fails_when_covered_zero_contradicts_coverage(tmp_path: Path) -> None:
    _write(tmp_path, "FINAL_QA_REPORT.md", QA_TABLE + "\nCovered: 0\n")
    result = _run(tmp_path, "CBP-QA-001")[0]
    assert result.status == "FAIL"
    assert any("Covered: 0" in item for item in result.findings)


def test_debt_001_passes_with_evidence(tmp_path: Path) -> None:
    _write(tmp_path, "docs/DEBT.md", "FIXED: tools/x.py\nNOT_FIXED: 3 remaining\n")
    assert _run(tmp_path, "CBP-DEBT-001")[0].status == "PASS"


def test_debt_001_fails_without_evidence(tmp_path: Path) -> None:
    _write(tmp_path, "docs/DEBT.md", "FIXED\n")
    result = _run(tmp_path, "CBP-DEBT-001")[0]
    assert result.status == "FAIL"
    assert any("without file or number" in item for item in result.findings)


def test_debt_001_ignores_lowercase_prose(tmp_path: Path) -> None:
    _write(tmp_path, "docs/DEBT.md", "The bug is fixed now.\n")
    assert _run(tmp_path, "CBP-DEBT-001")[0].status == "PASS"


def test_sign_001_passes_when_the_script_exists(tmp_path: Path) -> None:
    _write(tmp_path, "tools/sign.ps1", "Write-Host ok\n")
    _write(tmp_path, ".github/workflows/release-sign.yml", "jobs:\n  s:\n    steps:\n      - run: |\n          pwsh tools/sign.ps1\n")
    assert _run(tmp_path, "CBP-SIGN-001")[0].status == "PASS"


def test_sign_001_fails_when_the_script_is_missing(tmp_path: Path) -> None:
    _write(tmp_path, ".github/workflows/release-sign.yml", "jobs:\n  s:\n    steps:\n      - run: |\n          pwsh tools/sign.ps1\n")
    result = _run(tmp_path, "CBP-SIGN-001")[0]
    assert result.status == "FAIL"
    assert any("tools/sign.ps1" in item for item in result.findings)


def test_sign_001_ignores_a_path_in_a_comment(tmp_path: Path) -> None:
    _write(tmp_path, ".github/workflows/release-sign.yml", "jobs:\n  s:\n    steps:\n      - run: |\n          # pwsh tools/sign.ps1\n          echo ok\n")
    assert _run(tmp_path, "CBP-SIGN-001")[0].status == "PASS"


def _pe(signed: bool) -> bytes:
    data = bytearray(b"\0" * 0x120)
    data[0:2] = b"MZ"
    data[0x3C:0x40] = (0x80).to_bytes(4, "little")
    data[0x80:0x84] = b"PE\0\0"
    data[0x98:0x9A] = (0x10B).to_bytes(2, "little")
    entry = 0x98 + 96 + 4 * 8
    data[entry:entry + 4] = (0x120 if signed else 0).to_bytes(4, "little")
    data[entry + 4:entry + 8] = (4 if signed else 0).to_bytes(4, "little")
    return bytes(data)


def test_bin_001_passes_without_installers(tmp_path: Path) -> None:
    _write(tmp_path, "README.md", "no exe\n")
    assert _run(tmp_path, "CBP-BIN-001")[0].status == "PASS"


def test_bin_001_fails_on_an_unsigned_installer(tmp_path: Path) -> None:
    (tmp_path / "installer.exe").write_bytes(_pe(signed=False))
    result = _run(tmp_path, "CBP-BIN-001")[0]
    assert result.status == "WARN"
    assert any("no Authenticode signature" in item for item in result.findings)


def test_bin_001_passes_with_a_signature_blob(tmp_path: Path) -> None:
    (tmp_path / "installer.exe").write_bytes(_pe(signed=True))
    assert _run(tmp_path, "CBP-BIN-001")[0].status == "PASS"


def test_doc_001_passes_when_the_path_exists(tmp_path: Path) -> None:
    _write(tmp_path, "tools/x.py", "x = 1\n")
    _write(tmp_path, "docs/a.md", "See `tools/x.py`.\n")
    assert _run(tmp_path, "CBP-DOC-001")[0].status == "PASS"


def test_doc_001_fails_on_a_missing_path(tmp_path: Path) -> None:
    _write(tmp_path, "docs/a.md", "See `tools/missing.py`.\n")
    result = _run(tmp_path, "CBP-DOC-001")[0]
    assert result.status == "WARN"
    assert any("tools/missing.py" in item for item in result.findings)


def test_doc_001_ignores_bare_prose_paths(tmp_path: Path) -> None:
    _write(tmp_path, "docs/a.md", "For example src/example.py is a placeholder.\n")
    assert _run(tmp_path, "CBP-DOC-001")[0].status == "PASS"


def test_claim_001_passes_with_evidence(tmp_path: Path) -> None:
    _write(tmp_path, "docs/a.md", "This prevents escalation (tests/test_a.py).\n")
    assert _run(tmp_path, "CBP-CLAIM-001")[0].status == "PASS"


def test_claim_001_fails_without_evidence(tmp_path: Path) -> None:
    _write(tmp_path, "docs/a.md", "This prevents privilege escalation.\n")
    result = _run(tmp_path, "CBP-CLAIM-001")[0]
    assert result.status == "WARN"
    assert any("capability claim" in item for item in result.findings)


def test_claim_001_accepts_an_audit_only_marker(tmp_path: Path) -> None:
    _write(tmp_path, "docs/a.md", "audit-only: isolation is not enforced here.\n")
    assert _run(tmp_path, "CBP-CLAIM-001")[0].status == "PASS"


def test_cov_001_passes_with_a_hard_gate(tmp_path: Path) -> None:
    _write(tmp_path, "pyproject.toml", "[tool.coverage.report]\nfail_under = 90\n")
    _write(tmp_path, ".github/workflows/ci.yml", "jobs:\n  t:\n    steps:\n      - run: |\n          coverage report\n")
    assert _run(tmp_path, "CBP-COV-001")[0].status == "PASS"


def test_cov_001_fails_when_downgraded(tmp_path: Path) -> None:
    _write(tmp_path, "pyproject.toml", "[tool.coverage.report]\nfail_under = 20\n")
    _write(tmp_path, ".github/workflows/ci.yml", "jobs:\n  t:\n    steps:\n      - run: |\n          coverage report\n        continue-on-error: true\n")
    result = _run(tmp_path, "CBP-COV-001")[0]
    assert result.status == "WARN"
    assert any("below 50" in item for item in result.findings)
    assert any("allows failure" in item for item in result.findings)


def test_proof_001_passes_with_all_markers(tmp_path: Path) -> None:
    _write(tmp_path, "FINAL_PROOF.md", "commit abc\nACL applied\nservice account used\n")
    assert _run(tmp_path, "CBP-PROOF-001")[0].status == "PASS"


def test_proof_001_fails_when_a_marker_is_missing(tmp_path: Path) -> None:
    _write(tmp_path, "FINAL_PROOF.md", "commit abc\nservice account used\n")
    result = _run(tmp_path, "CBP-PROOF-001")[0]
    assert result.status == "WARN"
    assert any("acl" in item for item in result.findings)


def test_slop_001_ignores_a_few_template_docstrings(tmp_path: Path) -> None:
    body = "\n".join(f'def f{i}():\n    """Return the result."""\n    return {i}\n' for i in range(3))
    _write(tmp_path, "src/a.py", body)
    assert _run(tmp_path, "CBP-SLOP-001")[0].status == "PASS"


def test_slop_001_fails_above_the_threshold(tmp_path: Path) -> None:
    body = "\n".join(f'def f{i}():\n    """Return the result."""\n    return {i}\n' for i in range(4))
    _write(tmp_path, "src/a.py", body)
    result = _run(tmp_path, "CBP-SLOP-001")[0]
    assert result.status == "WARN"
    assert len(result.findings) == 4


def test_waiver_must_match_the_exact_path(tmp_path: Path) -> None:
    _write(tmp_path, "tests/test_a.py", "def test_a(): pass\n")
    _write(tmp_path, ".github/workflows/ci.yml", "jobs:\n  t:\n    steps:\n      - run: |\n          echo ok\n")
    waiver = tmp_path / "waivers.json"
    waiver.write_text(json.dumps({"waivers": [
        {"rule": "CBP-CI-001", "path": "quality/tests", "reason": "other", "expires": "2099-01-01"}
    ]}), encoding="utf-8")
    result, _ = _run(tmp_path, "CBP-CI-001", waivers_path=waiver)
    assert result.status == "FAIL"


def test_a_matching_waiver_suppresses_the_finding(tmp_path: Path) -> None:
    _write(tmp_path, "tests/test_a.py", "def test_a(): pass\n")
    _write(tmp_path, ".github/workflows/ci.yml", "jobs:\n  t:\n    steps:\n      - run: |\n          echo ok\n")
    waiver = tmp_path / "waivers.json"
    waiver.write_text(json.dumps({"waivers": [
        {"rule": "CBP-CI-001", "path": "tests", "reason": "runs elsewhere", "expires": "2099-01-01"}
    ]}), encoding="utf-8")
    result, _ = _run(tmp_path, "CBP-CI-001", waivers_path=waiver)
    assert result.status == "PASS"
    assert result.waived


def test_an_expired_waiver_is_not_applied(tmp_path: Path) -> None:
    _write(tmp_path, "tests/test_a.py", "def test_a(): pass\n")
    _write(tmp_path, ".github/workflows/ci.yml", "jobs:\n  t:\n    steps:\n      - run: |\n          echo ok\n")
    waiver = tmp_path / "waivers.json"
    waiver.write_text(json.dumps({"waivers": [
        {"rule": "CBP-CI-001", "path": "tests", "reason": "old", "expires": "2020-01-01"}
    ]}), encoding="utf-8")
    result, expired = _run(tmp_path, "CBP-CI-001", waivers_path=waiver)
    assert result.status == "FAIL"
    assert expired


def test_malformed_waiver_is_an_input_error(tmp_path: Path) -> None:
    waiver = tmp_path / "waivers.json"
    waiver.write_text(json.dumps({"waivers": [{"rule": "CBP-CI-001", "path": "tests"}]}), encoding="utf-8")
    with pytest.raises(v12.RuleConfigError, match="reason"):
        v12.run_rules(tmp_path, only={"CBP-CI-001"}, waivers_path=waiver)


def test_warning_baseline_suppresses_until_expiry(tmp_path: Path) -> None:
    _write(tmp_path, "docs/a.md", "See `tools/missing.py`.\n")
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps({"baseline": [
        {"rule": "CBP-DOC-001", "path": "docs/a.md", "reason": "known", "expires": "2099-01-01"}
    ]}), encoding="utf-8")
    result, _ = _run(tmp_path, "CBP-DOC-001", baseline_path=baseline)
    assert result.status == "PASS"
    assert result.baselined


def test_expired_baseline_does_not_suppress(tmp_path: Path) -> None:
    _write(tmp_path, "docs/a.md", "See `tools/missing.py`.\n")
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps({"baseline": [
        {"rule": "CBP-DOC-001", "path": "docs/a.md", "reason": "old", "expires": "2020-01-01"}
    ]}), encoding="utf-8")
    result, expired = _run(tmp_path, "CBP-DOC-001", baseline_path=baseline)
    assert result.status == "WARN"
    assert expired


def test_worktree_rule_detects_a_tracked_change(tmp_path: Path) -> None:
    _write(tmp_path, "a.txt", "one\n")
    _git_repo(tmp_path)
    ctx = v12.RuleContext(root=tmp_path, initial_worktree="")
    (tmp_path / "a.txt").write_text("two\n", encoding="utf-8")
    findings = v12.rule_wt_001(ctx)
    assert findings and "a.txt" in findings[0]


def test_worktree_rule_passes_on_a_clean_tree(tmp_path: Path) -> None:
    _write(tmp_path, "a.txt", "one\n")
    _git_repo(tmp_path)
    code, status = v12._git(tmp_path, "status", "--porcelain", "--untracked-files=no")
    assert code == 0
    ctx = v12.RuleContext(root=tmp_path, initial_worktree=status)
    assert v12.rule_wt_001(ctx) == []


def test_worktree_rule_fails_on_a_committed_conflict_marker(tmp_path: Path) -> None:
    _write(tmp_path, "a.py", "<<<<<<< HEAD\nprint(1)\n=======\nprint(2)\n>>>>>>> feature\n")
    _git_repo(tmp_path)
    code, status = v12._git(tmp_path, "status", "--porcelain", "--untracked-files=no")
    ctx = v12.RuleContext(root=tmp_path, initial_worktree=status)
    findings = v12.rule_wt_001(ctx)
    assert findings
    assert any("conflict marker" in item for item in findings)
    assert any("a.py:1" in item for item in findings)


def test_worktree_rule_flags_an_end_marker_without_a_start(tmp_path: Path) -> None:
    _write(tmp_path, "a.py", ">>>>>>> feature\n")
    _git_repo(tmp_path)
    code, status = v12._git(tmp_path, "status", "--porcelain", "--untracked-files=no")
    ctx = v12.RuleContext(root=tmp_path, initial_worktree=status)
    findings = v12.rule_wt_001(ctx)
    assert any("a.py:1" in item and "conflict marker" in item for item in findings)


def test_worktree_rule_accepts_a_separator_without_a_conflict(tmp_path: Path) -> None:
    _write(tmp_path, "doc.rst", "Title\n=======\n\nBody\n")
    _git_repo(tmp_path)
    code, status = v12._git(tmp_path, "status", "--porcelain", "--untracked-files=no")
    ctx = v12.RuleContext(root=tmp_path, initial_worktree=status)
    assert v12.rule_wt_001(ctx) == []


def test_worktree_rule_ignores_untracked_conflict_markers(tmp_path: Path) -> None:
    _write(tmp_path, "a.txt", "clean\n")
    _git_repo(tmp_path)
    _write(tmp_path, "untracked.txt", "<<<<<<< HEAD\n")
    code, status = v12._git(tmp_path, "status", "--porcelain", "--untracked-files=no")
    ctx = v12.RuleContext(root=tmp_path, initial_worktree=status)
    assert v12.rule_wt_001(ctx) == []


def test_cli_v12_exit_codes_and_report(tmp_path: Path) -> None:
    _write(tmp_path, "tests/test_a.py", "def test_a(): pass\n")
    _write(tmp_path, ".github/workflows/ci.yml", "jobs:\n  t:\n    steps:\n      - run: |\n          pytest -q tests\n")
    report = tmp_path / "report.json"
    assert cli.main(["--root", str(tmp_path), "--v12", "--v12-only", "CBP-CI-001", "--v12-report", str(report)]) == 0
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["rules"][0]["id"] == "CBP-CI-001"
    assert payload["summary"]["blocking_failed"] is False


def test_cli_v12_blocks_on_a_blocking_rule(tmp_path: Path) -> None:
    _write(tmp_path, "tests/test_a.py", "def test_a(): pass\n")
    _write(tmp_path, ".github/workflows/ci.yml", "jobs:\n  t:\n    steps:\n      - run: |\n          echo ok\n")
    assert cli.main(["--root", str(tmp_path), "--v12", "--v12-only", "CBP-CI-001"]) == 3
