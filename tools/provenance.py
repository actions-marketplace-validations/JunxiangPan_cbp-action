"""Create or verify the opt-in provenance sidecar (offline)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from cbp import provenance


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cbp provenance")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create")
    create.add_argument("--manifest", required=True)
    create.add_argument("--artifact", action="append", required=True)
    create.add_argument("--output-dir", default="provenance")
    create.add_argument("--repository", required=True)
    create.add_argument("--run-id", required=True)
    create.add_argument("--tag", required=True)
    create.add_argument("--commit", required=True)
    create.add_argument("--generated-at", default="1970-01-01T00:00:00Z")
    create.add_argument("--keyless", action="store_true")
    verify = sub.add_parser("verify")
    verify.add_argument("--provenance", required=True)
    verify.add_argument("--manifest", required=True)
    verify.add_argument("--artifact", action="append", required=True)
    verify.add_argument("--bundle-dir", default="")
    verify.add_argument("--identity-regexp", default="")
    verify.add_argument("--oidc-issuer", default="https://token.actions.githubusercontent.com")
    args = parser.parse_args(argv)

    if args.command == "create":
        statement = provenance.write(
            Path(args.manifest), [Path(item) for item in args.artifact],
            Path(args.output_dir), repository=args.repository, run_id=args.run_id,
            tag=args.tag, commit=args.commit, generated_at=args.generated_at,
            signed=args.keyless,
        )
        print(json.dumps({"status": statement["signature_status"],
                          "output": str(Path(args.output_dir) / "provenance.json")}))
        return 0
    result = provenance.verify(
        Path(args.provenance), Path(args.manifest), [Path(item) for item in args.artifact],
        bundle_dir=Path(args.bundle_dir) if args.bundle_dir else None,
        identity_regexp=args.identity_regexp, oidc_issuer=args.oidc_issuer,
    )
    print(json.dumps(result, ensure_ascii=False))
    if result["status"] == "SIGNED":
        return 0
    if result["status"] == provenance.BLOCKED:
        return 4
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
