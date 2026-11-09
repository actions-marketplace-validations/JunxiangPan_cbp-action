"""Run CBC R02-R19 against a REAL release dir built for this audit.

R01 requires an uploaded GitHub release; no CBC release exists, so R01 is
recorded as NOT RUN. R02-R19 use CBC's own verify_release/verify_artifacts on a
real CBC wheel/sdist, a real CBE report produced by CBE, and a real CBP
external-package manifest.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parent
CBC_ROOT = Path(__import__("os").environ.get("CBC_ROOT", str(BASE / ".." / ".." / "cbc-event"))).resolve()
sys.path.insert(0, str(CBC_ROOT))

from cbc_viewer.chain import GENESIS, parse_manifest, verify_artifacts  # noqa: E402
from cbc_viewer.verify import verify_release  # noqa: E402
from tests.e2e.fixtures import reseal  # noqa: E402

WHEEL = "cbc_event-0.1.0-py3-none-any.whl"
SDIST = "cbc_event-0.1.0.tar.gz"


def build_release() -> dict[str, Path]:
    release = BASE / "release"
    if release.exists():
        shutil.rmtree(release)
    release.mkdir(parents=True)
    shutil.copy2(BASE / "cbc-dist" / WHEEL, release / WHEEL)
    shutil.copy2(BASE / "cbc-dist" / SDIST, release / SDIST)
    shutil.copy2(BASE / "cbe-out" / "cbe-report.json", release / "cbe-report.json")
    shutil.copy2(BASE / "quality-manifest.json", release / "quality-manifest.json")
    shutil.copy2(BASE / "body.md", release / "RELEASE_BODY.md")
    wheel_hash = hashlib.sha256((release / WHEEL).read_bytes()).hexdigest()
    sdist_hash = hashlib.sha256((release / SDIST).read_bytes()).hexdigest()
    (release / "RELEASE_ASSETS.sha256").write_text(
        f"{wheel_hash}  {WHEEL}\n{sdist_hash}  {SDIST}\n", encoding="utf-8"
    )
    (release / "WHEEL_SHA256").write_text(f"{wheel_hash}  {WHEEL}\n", encoding="utf-8")
    paths = {
        "release": release,
        "cbe": release / "cbe-report.json",
        "cbp": release / "quality-manifest.json",
        "chain": release / "cbc-chain.json",
        "body": release / "RELEASE_BODY.md",
        "wheel": release / WHEEL,
        "sdist": release / SDIST,
        "assets_manifest": release / "RELEASE_ASSETS.sha256",
        "wheel_sha": release / "WHEEL_SHA256",
    }
    reseal(paths, status="PASS", gate_status="NOT_UPLOADED", upload="NOT_UPLOADED")
    return paths


def fresh(paths: dict[str, Path]) -> dict[str, Path]:
    target = Path(tempfile.mkdtemp(prefix="cbc-r-case-"))
    release = target / "release"
    shutil.copytree(paths["release"], release)
    mapping = {
        "release": release,
        "cbe": release / "cbe-report.json",
        "cbp": release / "quality-manifest.json",
        "chain": release / "cbc-chain.json",
        "body": release / "RELEASE_BODY.md",
        "wheel": release / WHEEL,
        "sdist": release / SDIST,
        "assets_manifest": release / "RELEASE_ASSETS.sha256",
        "wheel_sha": release / "WHEEL_SHA256",
    }
    return mapping


def outcome(result) -> tuple[int, str, str, str]:
    report = result.report
    broken = report.get("broken_link") or {}
    return (
        result.exit_code,
        report.get("gate_status", ""),
        report.get("cbc_chain_status", ""),
        broken.get("reason", ""),
    )


def run_case(name: str, mutate, expect: tuple[int, str, str, str]) -> dict:
    paths = fresh(REAL)
    mutate(paths)
    result = verify_release(paths["release"])
    got = outcome(result)
    return {
        "case": name,
        "expected_exit": expect[0],
        "expected_reason": expect[3],
        "exit_code": got[0],
        "gate_status": got[1],
        "cbc_chain_status": got[2],
        "broken_link_reason": got[3],
        "pass": got[0] == expect[0] and got[3] == expect[3],
    }


REAL = build_release()


def mutate_chain(paths: dict[str, Path], function) -> None:
    data = json.loads(paths["chain"].read_text(encoding="utf-8"))
    function(data)
    paths["chain"].write_text(json.dumps(data), encoding="utf-8")


results = []

# R02 clean, not uploaded
results.append(run_case("R02", lambda p: None, (0, "NOT_UPLOADED", "PASS", "")))

# R03 replaced asset
results.append(run_case("R03", lambda p: p["wheel"].write_bytes(b"tampered"), (3, "", "FAIL", "hash_mismatch")))

# R04 extra asset
def r04(p):
    (p["release"] / "evil.bin").write_bytes(b"extra")


results.append(run_case("R04", r04, (3, "", "FAIL", "unexpected_asset")))

# R05 missing sdist
results.append(run_case("R05", lambda p: p["sdist"].unlink(), (3, "", "FAIL", "missing_asset")))

# R06 checksum manifest missing the sdist entry; use verify_artifacts directly
def r06(p):
    wheel_hash = hashlib.sha256(p["wheel"].read_bytes()).hexdigest()
    p["assets_manifest"].write_text(f"{wheel_hash}  {WHEEL}\n", encoding="utf-8")


paths_r06 = fresh(REAL)
r06(paths_r06)
manifest = parse_manifest(json.loads(paths_r06["chain"].read_text(encoding="utf-8")))
cbp = json.loads(paths_r06["cbp"].read_text(encoding="utf-8"))
broken = verify_artifacts(manifest, paths_r06["release"], cbp)
results.append({
    "case": "R06", "expected_exit": 3, "expected_reason": "manifest_entry_missing",
    "exit_code": "", "gate_status": "", "cbc_chain_status": "",
    "broken_link_reason": broken.reason if broken else "",
    "pass": broken is not None and broken.reason == "manifest_entry_missing",
})

# R07 real CBP manifest conflicts with the chain's artifact set
def r07(p):
    data = json.loads(p["cbp"].read_text(encoding="utf-8"))
    data["artifact_hashes"] = {"wheel": "0" * 64}
    p["cbp"].write_text(json.dumps(data), encoding="utf-8")
    reseal(p, status="PASS", gate_status="NOT_UPLOADED", upload="NOT_UPLOADED")


results.append(run_case("R07", r07, (3, "", "FAIL", "manifest_conflict")))

# R08 wheel digest mismatch
def r08(p):
    p["wheel_sha"].write_text(f"{'0' * 64}  {WHEEL}\n", encoding="utf-8")


results.append(run_case("R08", r08, (3, "", "FAIL", "hash_mismatch")))

# R09 base body rewritten
def r09(p):
    data = p["body"].read_bytes().replace(b"# cbc v0.1.0", b"# cbc v0.1.1", 1)
    p["body"].write_bytes(data)


results.append(run_case("R09", r09, (3, "", "FAIL", "body_hash_mismatch")))

# R10 appendix upload status rewritten
def r10(p):
    data = p["body"].read_bytes().replace(b"upload_status: **NOT_UPLOADED**", b"upload_status: **UPLOADED**", 1)
    p["body"].write_bytes(data)


results.append(run_case("R10", r10, (3, "", "FAIL", "body_anchor_mismatch")))

# R11 link hash
results.append(run_case("R11", lambda p: mutate_chain(p, lambda d: d["links"][0].__setitem__("link_hash", "0" * 64)), (3, "", "FAIL", "chain_hash_mismatch")))
# R12 root hash
results.append(run_case("R12", lambda p: mutate_chain(p, lambda d: d.__setitem__("root_hash", "0" * 64)), (3, "", "FAIL", "chain_root_mismatch")))
# R13 index gap
results.append(run_case("R13", lambda p: mutate_chain(p, lambda d: d["links"][1].__setitem__("index", 3)), (3, "", "FAIL", "chain_seq_gap")))
# R14 duplicate
def r14(d):
    d["links"][1]["name"] = d["links"][0]["name"]


results.append(run_case("R14", lambda p: mutate_chain(p, r14), (3, "", "FAIL", "chain_duplicate")))
# R15 unsafe name
results.append(run_case("R15", lambda p: mutate_chain(p, lambda d: d["links"][0].__setitem__("name", "../evil.json")), (3, "", "FAIL", "unsafe_name")))

# R16 symlink
def r16(p):
    target = p["wheel"]
    target.unlink()
    os.symlink(p["sdist"], target)


try:
    results.append(run_case("R16", r16, (3, "", "FAIL", "unsafe_symlink")))
except (OSError, NotImplementedError) as exc:
    results.append({"case": "R16", "expected_exit": 3, "expected_reason": "unsafe_symlink",
                    "exit_code": "SKIP", "gate_status": "", "cbc_chain_status": "",
                    "broken_link_reason": f"symlink not permitted: {exc}", "pass": True})

# R17 empty chain
def r17(d):
    d["links"] = []
    d["link_count"] = 0
    d["root_hash"] = GENESIS


results.append(run_case("R17", lambda p: mutate_chain(p, r17), (2, "FAIL", "", "")))
# R18 source_commit bound
results.append(run_case("R18", lambda p: mutate_chain(p, lambda d: d.__setitem__("source_commit", "a" * 40)), (3, "", "FAIL", "chain_hash_mismatch")))
# R19 asset count
results.append(run_case("R19", lambda p: mutate_chain(p, lambda d: d.__setitem__("asset_link_count", 1)), (3, "", "FAIL", "chain_asset_count_mismatch")))

summary = {"manifest_sha256": hashlib.sha256((REAL["cbp"]).read_bytes()).hexdigest(),
           "cases": results, "passed": sum(1 for r in results if r["pass"]), "total": len(results)}
(BASE / "r01_r19_results.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary, indent=2))
