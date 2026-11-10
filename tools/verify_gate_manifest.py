"""Verify the SHA256 manifest that protects CBP's own gate scripts/workflows."""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path


def _rows(path: Path) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        if len(parts) != 2 or len(parts[0]) != 64:
            raise ValueError(f"line {line_no}: expected '<64-hex>  <path>'")
        rows.append((parts[0].lower(), parts[1].strip()))
    if not rows:
        raise ValueError("manifest is empty")
    return rows


def verify(manifest: Path, root: Path) -> list[str]:
    problems: list[str] = []
    for expected, relative in _rows(manifest):
        path = (root / relative).resolve()
        try:
            path.relative_to(root.resolve())
        except ValueError:
            problems.append(f"{relative}: path escapes the repository")
            continue
        if not path.is_file():
            problems.append(f"{relative}: missing")
            continue
        actual = hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        if actual != expected:
            problems.append(f"{relative}: hash {actual} != {expected}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="verify-gate-manifest")
    parser.add_argument("manifest", nargs="?", default="quality/GATES.sha256")
    parser.add_argument("--root", default=".")
    args = parser.parse_args(argv)
    try:
        problems = verify(Path(args.manifest), Path(args.root))
    except (OSError, ValueError) as exc:
        print(f"GATE_MANIFEST_FAIL reason={exc}", file=sys.stderr)
        return 2
    if problems:
        print("GATE_MANIFEST_FAIL", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 3
    print(f"GATE_MANIFEST_OK entries={len(_rows(Path(args.manifest)))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
