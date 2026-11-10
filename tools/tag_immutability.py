"""Detect moved/deleted release tags against a pinned snapshot (opt-in)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def diff(expected: dict[str, str], actual: dict[str, str]) -> list[str]:
    problems: list[str] = []
    for tag, commit in sorted(expected.items()):
        if tag not in actual:
            problems.append(f"{tag}: missing")
        elif actual[tag] != commit:
            problems.append(f"{tag}: moved {commit} -> {actual[tag]}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="check-tag-immutability")
    parser.add_argument("--expected", required=True)
    parser.add_argument("--actual", required=True)
    args = parser.parse_args(argv)
    try:
        expected = json.loads(Path(args.expected).read_text(encoding="utf-8"))
        actual = json.loads(Path(args.actual).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"TAG_CHECK_FAIL reason={exc}", file=sys.stderr)
        return 2
    problems = diff(expected, actual)
    if problems:
        print("TAG_MOVED", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 3
    print(f"TAG_IMMUTABLE_OK tags={len(expected)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
