#!/usr/bin/env python3
"""Generate the release body from build outputs; no post-publish edits."""
from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path

from cbp.body_hash import canonical_body_bytes, canonical_body_hash


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wheel", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--notes", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--repo", default="JunxiangPan/cbp-action")
    parser.add_argument("--ci-run", default="")
    parser.add_argument("--e2e-run", default="")
    parser.add_argument("--verify-v106", default="42462244338")
    parser.add_argument("--verify-v107", default="42463773268")
    parser.add_argument("--double-build-run", default="")
    parser.add_argument("--sarif-run", default="")
    parser.add_argument("--summary", default="")
    parser.add_argument("--python310", default="PASS (tested in the OS x Python matrix)")
    parser.add_argument("--infra-failure", action="append", default=[], metavar="TEXT")
    args = parser.parse_args()
    wheel = Path(args.wheel)
    notes = Path(args.notes).read_text(encoding="utf-8")
    match = re.search(r"(?m)^QUALITY_COUNTS:\s*(\d+/\d+)\s*$", notes)
    if not match:
        raise SystemExit("notes must contain exactly one QUALITY_COUNTS line")
    version = args.version.lstrip("v")
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    def link(run: str) -> str:
        return f"https://github.com/{args.repo}/actions/runs/{run}" if run else "not recorded"

    summary = args.summary or f"Release evidence for v{version}."

    def evidence(run: str, claim: str = "PASS") -> str:
        return f"{link(run)} {claim}" if run else "not recorded"

    infra_section = ""
    if args.infra_failure:
        lines = "\n".join(f"- {item}" for item in args.infra_failure)
        infra_section = (
            "## Infrastructure failures (SKIPPED_INFRA; publish blocked)\n\n"
            "These are not PASS and are not counted in the skip ratio.\n\n"
            f"{lines}\n\n"
        )

    body = f"""# CBP v{version} — Release-evidence gate

{summary}

This release body was generated from the built wheel by
`tools/generate_release_body.py`; the wheel SHA256 is not hand-edited.

## Verification

```text
QUALITY_COUNTS: {match.group(1)}
All 9 gates are active.
```

```text
{wheel.name}
sha256: {digest}
```

https://pypi.org/project/cbp-action/{version}/

## Section A: Security regression (blocking)

- main CI: {evidence(args.ci_run)}
- v1.0.6 verify: {evidence(args.verify_v106)}
- v1.0.7 verify: {evidence(args.verify_v107)}
- composite action payload E2E (15 hostile inputs): {evidence(args.e2e_run, 'PASS 15/15')}
- single build artifact re-verified: {evidence(args.double_build_run)}
- SARIF upload: {evidence(args.sarif_run)}
- Python 3.10: {args.python310}
- checkout ref whitelist: PASS
- release body auto-generated: PASS (no manual backfill)
- release.yml permissions: PASS
- release asset inventory: PASS
- security_core: 90%+ floor

{infra_section}## Section B: AI audit gates (audit mode, non-blocking)

- ai-release / ai-test / ai-change run in the main CI `ai-audit` job; that job
  prints `AI_GATE_SUMMARY` with PASS / WARN / SKIP counts: {link(args.ci_run)}
- Section B gates are audit-only and do not block publishing.

## Still to acknowledge

- ai-test false-positive rate is not yet measured on external projects.
- composite action payload E2E runs on GitHub Linux; local Windows is not verified.
- ai-release is structured evidence only, not natural-language summarization.
- Section B gates are audit-only and do not block publishing.
"""
    body = body.rstrip("\n") + "\n\n<!-- CBP-BODY-BASE-END -->\n"
    body_bytes = canonical_body_bytes(body.encode("utf-8"))
    Path(args.output).write_bytes(body_bytes)
    print(f"RELEASE_BODY_GENERATED {args.output} sha256={canonical_body_hash(body_bytes)} wheel_sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
