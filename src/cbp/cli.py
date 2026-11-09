"""Standalone CBP CLI."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import platform
import re
import sys
from pathlib import Path

from . import baseline, binary_gate, suppression, cbc_event, claims_gate, comment_gate, coverage_gate, custom_rules, dependency_gate, docs_gate, encoding_gate, errata, report_parser, report_schema, sarif, upgrade_gate, verify_release
from .config import SCHEMA_VERSION, load_config


def _init(argv: list[str]) -> int:  # pragma: no cover - exercised via subprocess CLI
    """Generate a minimal cbp.json with a schema version."""
    import argparse

    parser = argparse.ArgumentParser(prog="cbp init")
    parser.add_argument("--root", default=".")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    path = root / "cbp.json"
    if path.exists() and not args.force:
        print(f"INIT_REFUSED {path} exists; pass --force")
        return 1
    import json

    path.write_text(json.dumps({"schema_version": SCHEMA_VERSION, "enable_claims": True}, indent=2) + chr(10), encoding="utf-8")
    print(f"INIT_OK {path}")
    return 0


def _errata(argv: list[str]) -> int:
    """Generate and validate an ERRATUM-prefixed body; never edits GitHub."""
    parser = argparse.ArgumentParser(prog="cbp errata")
    parser.add_argument("--body", required=True)
    parser.add_argument("--output", default="")
    parser.add_argument("--reason", default="")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--diff", action="store_true")
    args = parser.parse_args(argv)
    path = Path(args.body)
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            original = handle.read()
    except FileNotFoundError:
        print(json.dumps({"gate_status": "FAIL", "exit_code": 2, "error": f"body missing: {path}"}, ensure_ascii=False))
        return report_schema.EXIT_INPUT
    except OSError as exc:
        print(json.dumps({"gate_status": "FAIL", "exit_code": 2, "error": f"body unreadable: {path}: {exc}"}, ensure_ascii=False))
        return report_schema.EXIT_INPUT
    if args.check:
        if errata.is_errata(original):
            print("ERRATUM_OK")
            return report_schema.EXIT_PASS
        print("ERRATUM_MISSING body does not start with ERRATUM:")
        return report_schema.EXIT_GATE
    corrected = errata.apply_errata(original, args.reason)
    if corrected == original:
        print("ERRATUM_ALREADY_PRESENT")
    if args.diff or not args.output:
        print(errata.unified_diff(original, corrected), end="")
    if args.output:
        with Path(args.output).open("w", encoding="utf-8", newline="") as handle:
            handle.write(corrected)
        print(f"ERRATUM_WRITTEN {args.output}")
    trailing = errata.trailing_errata_count(corrected)
    if trailing:
        print(f"TRAILING_ERRATUM_SECTIONS={trailing} (human-readable only; F4 reads the prefix)")
    if not errata.is_errata(corrected):
        print("ERRATUM_INVALID corrected body is not machine-readable")
        return report_schema.EXIT_INPUT
    print(f"ERRATUM_OK chars={len(corrected)}")
    return report_schema.EXIT_PASS


def _configured(name: str, cfg) -> bool:
    """Return whether a gate has enough configuration to run meaningfully."""
    if name == "encoding":
        return True
    if name == "coverage":
        return bool(getattr(cfg, "coverage_json", "") or getattr(cfg, "coverage_groups", ()))
    if name == "dependency":
        return bool(getattr(cfg, "dependency_lock", "") or getattr(cfg, "install_command", ""))
    if name == "comments":
        return bool(getattr(cfg, "comment_files", ()))
    if name == "docs":
        return bool(getattr(cfg, "docs_manifest", ""))
    if name == "claims":
        return bool(getattr(cfg, "claims_manifest", None) or getattr(cfg, "claims_notes", None))
    if name == "custom":
        return bool(getattr(cfg, "custom_rules", ()) or getattr(cfg, "packs", ()))
    if name == "upgrade":
        return bool(getattr(cfg, "upgrade_script", "") or getattr(cfg, "upgrade_fixtures", ()))
    if name == "binary":
        return bool(getattr(cfg, "binary_artifacts", ""))
    return True


def _policy_test(argv: list[str]) -> int:
    """Run a CEL policy fixture file from the CLI."""
    parser = argparse.ArgumentParser(prog="cbp policy test")
    parser.add_argument("fixtures")
    args = parser.parse_args(argv)
    from .policy_test import run_fixture

    passed, failures = run_fixture(Path(args.fixtures))
    for failure in failures:
        print("POLICY_FAIL " + failure)
    print("POLICY_TEST=" + ("PASS" if passed else "FAIL"))
    return 0 if passed else 1


def _changed_files(root: Path, ref: str) -> set[str]:
    """Return repository-relative paths changed since a git ref."""
    import subprocess

    try:
        completed = subprocess.run(
            ["git", "-C", str(root), "diff", "--name-only", ref],
            capture_output=True, text=True, timeout=20, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return set()
    return {line.strip().replace("\\", "/") for line in completed.stdout.splitlines() if line.strip()}


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - exercised via subprocess CLI
    """Run enabled CBP gates and return a process exit code."""
    if argv is None:
        argv = __import__("sys").argv[1:]
    if argv and argv[0] == "init":
        return _init(argv[1:])
    if argv and argv[0] == "errata":
        return _errata(argv[1:])
    if argv and argv[:2] == ["policy", "test"]:
        return _policy_test(argv[2:])
    if argv and argv[0] == "manifest":
        from . import package_manifest
        return package_manifest.main(argv[1:])
    parser = argparse.ArgumentParser(prog="cbp")
    parser.add_argument("--root", default=".")
    parser.add_argument("--config", default="")
    parser.add_argument("--mode", choices=("audit", "warn", "enforce"), default="enforce")
    parser.add_argument("--coverage-threshold", type=float, default=None)
    parser.add_argument("--policy-coverage-threshold", type=float, default=None)
    parser.add_argument("--coverage-json", default="")
    parser.add_argument("--coverage-allowlist", default="")
    parser.add_argument("--coverage-signature", default="")
    parser.add_argument("--require-coverage-signature", type=lambda x: x.lower() == "true", default=None)
    parser.add_argument("--dependency-lock", default="")
    parser.add_argument("--install-command", default="")
    parser.add_argument("--installer-core", dest="install_command", default=argparse.SUPPRESS)
    parser.add_argument("--docs-manifest", default="")
    parser.add_argument("--binary-artifacts", default="")
    parser.add_argument("--package-zip", default="")
    parser.add_argument("--claims-manifest", default="")
    parser.add_argument("--claims-notes", default="")
    parser.add_argument("--release-body", default="")
    parser.add_argument("--release-assets", default="")
    parser.add_argument("--rules-path", default="")
    parser.add_argument("--rules-sha256", default="")
    parser.add_argument("--manifest", default="")
    parser.add_argument("--sarif-output", default="")
    parser.add_argument("--report-json", default="")
    parser.add_argument("--package-id", default="")
    parser.add_argument("--producer-id", default="")
    parser.add_argument("--version", default="")
    parser.add_argument("--parse-report", default="")
    parser.add_argument("--observed-exit-code", type=int, default=None)
    parser.add_argument("--baseline", default="")
    parser.add_argument("--generate-baseline", default="")
    parser.add_argument("--verify-release", default="")
    parser.add_argument("--repository", default="")
    parser.add_argument("--enable-coverage", type=lambda x: x.lower() == "true", default=None)
    parser.add_argument("--enable-encoding", type=lambda x: x.lower() == "true", default=None)
    parser.add_argument("--enable-dependency", type=lambda x: x.lower() == "true", default=None)
    parser.add_argument("--enable-comments", type=lambda x: x.lower() == "true", default=None)
    parser.add_argument("--enable-docs", type=lambda x: x.lower() == "true", default=None)
    parser.add_argument("--enable-binary", type=lambda x: x.lower() == "true", default=None)
    parser.add_argument("--enable-claims", type=lambda x: x.lower() == "true", default=None)
    parser.add_argument("--enable-custom", type=lambda x: x.lower() == "true", default=None)
    parser.add_argument("--enable-upgrade", type=lambda x: x.lower() == "true", default=None)
    parser.add_argument("--diff", default="")
    parser.add_argument("--gate", choices=("ai-release", "ai-test", "ai-change"), default="")
    parser.add_argument("--tag", default="")
    parser.add_argument("--test-path", default="")
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--github-annotations", action="store_true")
    parser.add_argument("--artifact-repository", default="")
    parser.add_argument("--body-hash-scope", default="")
    parser.add_argument("--require-body-scope", action="store_true")
    parser.add_argument("--expected-repository", default="")
    parser.add_argument("--cbc-event-dir", default="")
    parser.add_argument("--cbc-event-max", type=int, default=1000)
    parser.add_argument("--cbc-event-hmac-env", default="")
    parser.add_argument("--v12", action="store_true")
    parser.add_argument("--v12-report", default="")
    parser.add_argument("--v12-only", default="")
    parser.add_argument("--waivers", default="")
    parser.add_argument("--v12-baseline", default="")
    args = parser.parse_args(argv)
    if args.body_hash_scope and args.body_hash_scope not in report_schema.BODY_HASH_SCOPES:
        print(json.dumps({
            "gate_status": "FAIL",
            "exit_code": report_schema.EXIT_INPUT,
            "error": "unsupported body_hash_scope "
            + repr(args.body_hash_scope)
            + "; supported: "
            + ", ".join(report_schema.BODY_HASH_SCOPES),
        }, ensure_ascii=False))
        return report_schema.EXIT_INPUT
    if args.parse_report:
        try:
            parsed = report_parser.parse_report(
                Path(args.parse_report),
                observed_exit_code=args.observed_exit_code,
                require_body_scope=args.require_body_scope,
                expected_repository=args.expected_repository,
            )
        except report_parser.ReportError as exc:
            print(json.dumps(
                {"gate_status": "FAIL", "exit_code": report_schema.EXIT_INPUT, "error": str(exc)},
                ensure_ascii=False,
            ))
            return report_schema.EXIT_INPUT
        print(json.dumps(parsed.to_dict(), indent=2, ensure_ascii=False))
        return report_schema.EXIT_PASS
    if args.gate:
        from . import ai_gates
        result = ai_gates.run(args.gate, Path(args.root), args.tag, args.baseline, args.test_path, args.release_body)
        print(result.line())
        for finding in result.findings:
            print(finding)
        for skipped in result.skipped:
            print(f"SKIP {skipped}")
        if args.sarif_output:
            Path(args.sarif_output).write_text(json.dumps(ai_gates.sarif(result), indent=2) + chr(10), encoding="utf-8")
        return report_schema.EXIT_GATE if args.mode == "enforce" and result.status == "FAIL" else 0
    if args.verify_release:
        repository = args.repository or os.environ.get("GITHUB_REPOSITORY", "")
        if not repository:
            print("VERIFY_RELEASE_FAILED: --repository or GITHUB_REPOSITORY is required")
            return report_schema.EXIT_INPUT
        body = Path(args.release_body) if args.release_body else Path(args.root) / "docs" / "RELEASE_BODY.md"
        try:
            ok, detail = verify_release.verify(repository, args.verify_release, body, verify_release.token_from_env())
        except report_schema.InfraError as exc:
            print(f"GATE_STATUS=SKIPPED_INFRA {exc}")
            return report_schema.EXIT_GATE
        print(("RELEASE_BODY_OK " if ok else "") + detail)
        if not ok:
            return report_schema.EXIT_GATE
        asset_manifest = (
            Path(args.release_assets)
            if args.release_assets
            else Path(args.root) / "dist" / "RELEASE_ASSETS.sha256"
        )
        if not asset_manifest.is_file():
            print("FAIL: RELEASE_ASSETS.sha256 missing; asset verification cannot run", file=sys.stderr)
            return report_schema.EXIT_INPUT
        from .verify_release_assets import verify_from_manifest
        assets_ok, assets_detail = verify_from_manifest(
            asset_manifest, repository, args.verify_release, verify_release.token_from_env()
        )
        print(assets_detail)
        if not assets_ok:
            return report_schema.EXIT_GATE
        return report_schema.EXIT_PASS
    config_path = Path(args.config) if args.config else Path(args.root) / "cbp.json"
    if not args.config and not config_path.is_file():
        config_path = Path(args.root) / ".cbp" / "config.json"
    overrides = {}
    if args.coverage_threshold is not None:
        overrides["coverage_threshold"] = args.coverage_threshold
    if args.policy_coverage_threshold is not None:
        overrides["policy_threshold"] = args.policy_coverage_threshold
    for key, value in {
        "coverage_json": args.coverage_json, "coverage_allowlist": args.coverage_allowlist, "coverage_signature": args.coverage_signature,
        "dependency_lock": args.dependency_lock, "install_command": args.install_command,
        "docs_manifest": args.docs_manifest, "binary_artifacts": args.binary_artifacts,
        "package_zip": args.package_zip, "claims_manifest": args.claims_manifest,
        "claims_notes": args.claims_notes, "release_body": args.release_body, "baseline": args.baseline,
    }.items():
        if value:
            overrides[key] = value
    if args.manifest:
        overrides["claims_manifest"] = args.manifest
    for key in ("enable_coverage", "require_coverage_signature", "enable_encoding", "enable_dependency", "enable_comments", "enable_docs", "enable_binary", "enable_claims", "enable_custom", "enable_upgrade"):
        value = getattr(args, key)
        if value is not None:
            overrides[key] = value
    if args.v12:
        from . import v12_rules
        only = {item.strip() for item in args.v12_only.split(",") if item.strip()} if args.v12_only else None
        try:
            results, expired = v12_rules.run_rules(
                Path(args.root),
                only=only,
                waivers_path=args.waivers or None,
                baseline_path=args.v12_baseline or None,
            )
        except v12_rules.RuleConfigError as exc:
            print(json.dumps({
                "gate_status": "FAIL",
                "exit_code": report_schema.EXIT_INPUT,
                "error": str(exc),
            }, ensure_ascii=False))
            return report_schema.EXIT_INPUT
        payload = v12_rules.report(results, expired)
        for result in results:
            suffix = ""
            if result.waived:
                suffix += f" waived={len(result.waived)}"
            if result.baselined:
                suffix += f" baselined={len(result.baselined)}"
            print(f"{result.rule_id} {result.name}: {result.status}{suffix}")
            for finding in result.findings:
                print(f"  {finding}")
        if expired:
            print(f"V12_EXPIRED_ENTRIES={len(expired)}")
            for item in expired:
                print(f"  EXPIRED {item}")
        if args.v12_report:
            Path(args.v12_report).write_text(
                json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
        blocking = bool(payload["summary"]["blocking_failed"])
        warning = bool(payload["summary"]["warning_failed"])
        print(
            f"CBP_V12_RESULT={'FAIL' if blocking else ('WARN' if warning else 'PASS')} "
            f"rules={len(results)} blocking_failed={str(blocking).lower()} "
            f"warning_failed={str(warning).lower()}"
        )
        return report_schema.EXIT_GATE if blocking else report_schema.EXIT_PASS
    try:
        cfg = load_config(Path(args.root), config_path, overrides)
    except (OSError, ValueError, RuntimeError) as exc:
        print(json.dumps({"gate_status": "FAIL", "exit_code": report_schema.EXIT_INPUT, "error": str(exc)}, ensure_ascii=False))
        return report_schema.EXIT_INPUT
    if args.rules_sha256 and not args.rules_path:
        print(json.dumps({
            "gate_status": "FAIL",
            "exit_code": report_schema.EXIT_INPUT,
            "error": "--rules-sha256 requires --rules-path",
        }, ensure_ascii=False))
        return report_schema.EXIT_INPUT
    if args.rules_path:
        from . import packs
        try:
            pack = packs.load_pack(Path(args.rules_path), args.rules_sha256)
        except (OSError, ValueError, packs.PackError) as exc:
            print(json.dumps({
                "gate_status": "FAIL",
                "exit_code": report_schema.EXIT_INPUT,
                "error": f"rules pack unreadable: {args.rules_path}: {exc}",
            }, ensure_ascii=False))
            return report_schema.EXIT_INPUT
        cfg.custom_rules = tuple(getattr(cfg, "custom_rules", ()) or ()) + tuple(pack["rules"])
        cfg.enable_custom = True
    artifact_repository = args.artifact_repository or os.environ.get("GITHUB_REPOSITORY", "")
    cbc_config = getattr(cfg, "cbc_event", {}) or {}
    if not isinstance(cbc_config, dict):
        print(json.dumps({"gate_status": "FAIL", "exit_code": report_schema.EXIT_INPUT, "error": "cbc_event must be an object"}, ensure_ascii=False))
        return report_schema.EXIT_INPUT
    event_dir = (
        args.cbc_event_dir
        or str(cbc_config.get("dir", "") or "")
        or os.environ.get("CBP_CBC_EVENT_DIR", "")
    )
    event_enabled = bool(event_dir) and bool(
        args.cbc_event_dir
        or cbc_config.get("enabled", False)
        or os.environ.get("CBP_CBC_EVENT_DIR")
    )
    event_max = args.cbc_event_max if args.cbc_event_max != 1000 else int(cbc_config.get("max_events", 1000))
    hmac_env = args.cbc_event_hmac_env or str(cbc_config.get("hmac_key_env", "") or "")
    hmac_key = os.environ.get(hmac_env, "") if hmac_env else ""
    try:
        cbp_version = importlib.metadata.version("cbp-action")
    except importlib.metadata.PackageNotFoundError:
        cbp_version = str(getattr(cfg, "release_version", "") or "0")
    emitter = cbc_event.EventEmitter(
        event_dir,
        source={"kind": "tool", "name": "cbp", "version": cbp_version, "instance": platform.node() or "cbp"},
        enabled=event_enabled,
        max_events=event_max,
        hmac_key=hmac_key,
    )
    emitter.emit("INFO", "cbp.run.start", {
        "root": str(Path(args.root).resolve()),
        "package_type": str(getattr(cfg, "package_type", "") or ""),
        "mode": args.mode,
        "body_hash_scope": args.body_hash_scope or "base",
    })
    runners = {
        "encoding": encoding_gate.run,
        "coverage": coverage_gate.run,
        "dependency": dependency_gate.run,
        "comments": comment_gate.run,
        "docs": docs_gate.run,
        "claims": claims_gate.run,
        "custom": custom_rules.run,
        "upgrade": upgrade_gate.run,
        "binary": binary_gate.run,
    }
    enabled = {
        "encoding": cfg.enable_encoding,
        "coverage": cfg.enable_coverage,
        "dependency": cfg.enable_dependency,
        "comments": cfg.enable_comments,
        "docs": cfg.enable_docs,
        "claims": cfg.enable_claims,
        "custom": cfg.enable_custom,
        "upgrade": cfg.enable_upgrade,
        "binary": cfg.enable_binary,
    }
    package_type = str(getattr(cfg, "package_type", "") or "")
    contract_mode = package_type == report_schema.PACKAGE_ID
    gate_results = []
    entries = []
    executed = 0
    skip_count = 0
    blocking_skip = False
    infra_failure = False
    changed = _changed_files(Path(args.root), args.diff) if args.diff else set()

    def apply_filters(passed: bool, detail: str) -> tuple[bool, str]:
        """Apply inline suppression and changed-file filtering to one gate."""
        filtered = suppression.filter_text(cfg.root, detail)
        if filtered != detail:
            passed = passed or not filtered.strip()
            detail = filtered or "inline-suppressed"
        if args.diff and not passed:
            kept = []
            for line in detail.splitlines():
                match = __import__("re").match(r"^(?P<path>[^:]+):", line)
                if match and match.group("path").replace("\\", "/") not in changed:
                    continue
                kept.append(line)
            if detail and not kept:
                passed = True
                detail = "no findings on changed files"
            else:
                detail = chr(10).join("[NEW] " + line for line in kept)
        return passed, detail

    plan = []
    for name in report_schema.ALL_GATES:
        if not enabled[name]:
            forced = contract_mode and name in report_schema.FORCED_GATES
            reason = "forced gate is disabled" if forced else "disabled"
            plan.append((name, None, reason, forced, False))
        elif not _configured(name, cfg):
            forced = contract_mode and name in report_schema.FORCED_GATES
            reason = "forced gate is not configured" if forced else "not configured"
            plan.append((name, None, reason, forced, not forced))
        else:
            plan.append((name, runners[name], "", False, False))

    def execute(item):
        """Run one configured gate and classify its outcome."""
        name = item[0]
        try:
            passed, detail = runners[name](cfg)
        except report_schema.InfraError as exc:
            return name, "SKIPPED_INFRA", True, "infrastructure: " + str(exc)
        except Exception as exc:  # a crashing gate is a failure, never a pass
            return name, "FAIL", False, f"internal error: {type(exc).__name__}: {exc}"
        passed, detail = apply_filters(passed, detail)
        return name, ("PASS" if passed else "FAIL"), passed, detail

    runnable = [item for item in plan if item[1] is not None]
    if args.jobs > 1 and len(runnable) > 1:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
            outcomes = list(pool.map(execute, runnable))
    else:
        outcomes = [execute(item) for item in runnable]
    outcome_by_name = {name: (status, passed, detail) for name, status, passed, detail in outcomes}

    for name, runner, reason, forced, counts_as_skip in plan:
        if runner is None:
            blocking_skip = blocking_skip or forced
            if counts_as_skip and contract_mode:
                skip_count += 1
            entries.append({"name": name, "status": "SKIPPED", "reason": reason})
            gate_results.append((name, True, "SKIPPED (" + reason + ")"))
            print(f"{name}: SKIPPED ({reason})")
            emitter.emit("WARN", "cbp.gate.result", {"gate": name, "status": "SKIPPED", "reason": reason})
            continue
        executed += 1
        status, passed, detail = outcome_by_name[name]
        if status == "SKIPPED_INFRA":
            infra_failure = True
            entries.append({"name": name, "status": "SKIPPED", "reason": detail})
            gate_results.append((name, True, "SKIPPED_INFRA " + detail))
            print(f"{name}: SKIPPED_INFRA {detail}")
            emitter.emit("CRITICAL", "cbp.gate.result", {"gate": name, "status": "SKIPPED_INFRA", "reason": detail})
            continue
        if status == "FAIL":
            entries.append({"name": name, "status": "FAIL", "reason": (detail.splitlines() or [""])[0][:500]})
            gate_results.append((name, False, detail))
            print(f"{name}: FAIL {detail}")
            emitter.emit("CRITICAL", "cbp.gate.result", {"gate": name, "status": "FAIL", "reason": detail[:500]})
            if args.github_annotations:
                for line in detail.splitlines():
                    match = __import__("re").match(r"^(?P<path>[^:]+):(?P<line>\d+):\s*(?P<message>.+)$", line)
                    if match:
                        print(f"::error file={match.group('path')},line={match.group('line')}::{match.group('message')}")
            continue
        entries.append({"name": name, "status": "PASS", "reason": ""})
        gate_results.append((name, True, detail))
        print(f"{name}: PASS {detail}")
        emitter.emit("INFO", "cbp.gate.result", {"gate": name, "status": "PASS", "reason": ""})
    baseline_path = Path(args.generate_baseline) if args.generate_baseline else Path(args.baseline) if args.baseline else Path(args.root) / "cbp-baseline.json"
    if args.generate_baseline:
        entries_to_write = []
        for gate, passed, detail in gate_results:
            if not passed:
                entries_to_write.extend((gate, line) for line in detail.splitlines() if line.strip())
        baseline.write_entries(baseline_path, entries_to_write)
        print(f"BASELINE_WRITTEN path={baseline_path} entries={len(entries_to_write)}")
        return report_schema.EXIT_PASS
    allowed_baseline = baseline.load(baseline_path)
    if allowed_baseline:
        adjusted = []
        for gate, passed, detail in gate_results:
            kept = [line for line in detail.splitlines() if baseline.fingerprint(gate, line) not in allowed_baseline]
            if not passed and not any(line.strip() for line in kept):
                passed = True
            adjusted.append((gate, passed, chr(10).join(kept) if kept else "baseline-suppressed"))
        gate_results = adjusted
        suppressed = {name: passed for name, passed, _ in adjusted}
        for entry in entries:
            if entry["name"] in suppressed and suppressed[entry["name"]] and entry["status"] == "FAIL":
                entry["status"] = "PASS"
                entry["reason"] = "baseline-suppressed"
    if args.sarif_output:
        try:
            target = Path(args.sarif_output)
            document = sarif.build(gate_results, Path(args.root))
            target.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
        except OSError as exc:
            print(f"sarif: FAIL cannot write {args.sarif_output}: {exc}")
            infra_failure = True
    failed = any(not passed for _, passed, _ in gate_results)
    applicable = (
        len(report_schema.FORCED_GATES)
        + sum(1 for name in report_schema.ADAPTED_GATES if enabled[name])
        if contract_mode
        else executed
    )
    skip_ratio = skip_count / applicable if applicable else 0.0
    if infra_failure:
        gate_status, exit_code = "SKIPPED_INFRA", report_schema.EXIT_GATE
    elif blocking_skip or failed or executed == 0:
        gate_status, exit_code = "FAIL", report_schema.EXIT_GATE
    elif skip_ratio > report_schema.SKIP_RATIO_LIMIT:
        gate_status, exit_code = "FAIL", report_schema.EXIT_SKIP
    else:
        gate_status, exit_code = "PASS", report_schema.EXIT_PASS
    skipped_entries = sum(1 for entry in entries if entry["status"] == "SKIPPED")
    print(
        "CBP_RESULT=" + ("PASS" if gate_status == "PASS" else "FAIL")
        + " gates_ran=" + str(executed) + " skipped=" + str(skipped_entries)
    )
    print(
        f"CBP_GATE_STATUS={gate_status} CBP_EXIT_CODE={exit_code} "
        f"CBP_APPLICABLE={applicable} CBP_SKIP_RATIO={skip_ratio:.6f} "
        f"CBP_BLOCKING_SKIP={'true' if blocking_skip else 'false'}"
    )
    emitter.emit(
        "CRITICAL" if exit_code in (report_schema.EXIT_GATE, report_schema.EXIT_SKIP) else "INFO",
        "cbp.run.end",
        {
            "gate_status": gate_status,
            "exit_code": exit_code,
            "applicable_gate_count": applicable,
            "skip_count": skip_count,
            "skip_ratio": skip_ratio,
            "blocking_skip": blocking_skip,
        },
    )
    if emitter.enabled:
        print(f"CBC_EVENT emitted={emitter.emitted} dropped={emitter.dropped} dir={emitter.event_dir}")
    if args.report_json:
        report_package_id = args.package_id or report_schema.PACKAGE_ID
        report_producer_id = args.producer_id or report_schema.PRODUCER_ID
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", report_package_id):
            print(json.dumps({"gate_status": "FAIL", "exit_code": report_schema.EXIT_INPUT,
                              "error": f"invalid --package-id {report_package_id!r}"}, ensure_ascii=False))
            return report_schema.EXIT_INPUT
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", report_producer_id):
            print(json.dumps({"gate_status": "FAIL", "exit_code": report_schema.EXIT_INPUT,
                              "error": f"invalid --producer-id {report_producer_id!r}"}, ensure_ascii=False))
            return report_schema.EXIT_INPUT
        if args.version:
            raw_version = args.version.lstrip("vV")
            if not re.fullmatch(r"\d+\.\d+\.\d+", raw_version):
                print(json.dumps({"gate_status": "FAIL", "exit_code": report_schema.EXIT_INPUT,
                                  "error": f"invalid --version {args.version!r}"}, ensure_ascii=False))
                return report_schema.EXIT_INPUT
            report_version = "v" + raw_version
        else:
            report_version = "v" + str(getattr(cfg, "release_version", "") or "0.0.0").lstrip("v")
        report = {
            "schema_version": report_schema.MANIFEST_SCHEMA_VERSION,
            "package_id": report_package_id,
            "producer_id": report_producer_id,
            "version": report_version,
            "gate_status": gate_status,
            "exit_code": exit_code,
            "applicable_gate_count": applicable,
            "skip_count": skip_count,
            "skip_ratio": skip_ratio,
            "blocking_skip": blocking_skip,
            "body_hash_scope": args.body_hash_scope or "base",
            "package_type": package_type,
            "gates": entries,
        }
        if artifact_repository:
            report["artifact_repository"] = artifact_repository
        try:
            report_parser.parse_report_data(report, source="--report-json")
        except report_parser.ReportError as exc:
            print(f"REPORT_JSON_INVALID {exc}", file=sys.stderr)
            return report_schema.EXIT_INPUT
        Path(args.report_json).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.mode in {"audit", "warn"}:
        print(f"CBP_MODE={args.mode} contract_exit_code={exit_code} publishable={'true' if gate_status == 'PASS' and exit_code == 0 else 'false'}")
        return report_schema.EXIT_PASS
    return exit_code


if __name__ == "__main__":  # pragma: no cover - module entry point
    raise SystemExit(main())
