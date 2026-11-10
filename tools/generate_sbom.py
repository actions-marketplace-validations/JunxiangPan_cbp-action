"""Generate a small CycloneDX SBOM for CBP itself (opt-in, offline)."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTION = re.compile(r"uses:\s*([^@\s]+)@([0-9a-f]{40})")


def generate(root: Path = ROOT) -> dict:
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    name_match = re.search(r'(?m)^name\s*=\s*"([^"]+)"', pyproject)
    version_match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', pyproject)
    components = [{
        "type": "application", "name": name_match.group(1) if name_match else "cbp-action",
        "version": version_match.group(1) if version_match else "0",
        "purl": "pkg:pypi/cbp-action",
    }]
    refs = set()
    for workflow in sorted((root / ".github" / "workflows").glob("*.yml")):
        for name, commit in ACTION.findall(workflow.read_text(encoding="utf-8")):
            refs.add((name, commit))
    for name, commit in sorted(refs):
        components.append({
            "type": "library", "name": name, "version": commit,
            "properties": [{"name": "cbp:action-pin", "value": "full-sha"}],
        })
    return {
        "bomFormat": "CycloneDX", "specVersion": "1.5", "version": 1,
        "metadata": {"component": components[0]},
        "components": components[1:],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="generate-sbom")
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", default="")
    args = parser.parse_args(argv)
    data = generate(Path(args.root))
    text = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(text, encoding="utf-8")
        print(f"SBOM_WRITTEN path={args.output} components={len(data['components'])}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
