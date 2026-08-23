from __future__ import annotations

import argparse
from pathlib import Path

from .audit import audit_sources, load_source_specs
from .constants import DEFAULT_SEED
from .manifest import build_manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="behavior-recognition",
        description="CampusMateAI behavior recognition pipeline",
    )
    subparsers = parser.add_subparsers(dest="command")
    audit = subparsers.add_parser("audit", help="audit configured YOLO sources")
    audit.add_argument("--sources", type=Path, required=True)
    audit.add_argument("--output", type=Path, required=True)
    manifest = subparsers.add_parser("manifest", help="build leakage-controlled manifests")
    manifest.add_argument("--sources", type=Path, required=True)
    manifest.add_argument("--output", type=Path, required=True)
    manifest.add_argument("--seed", type=int, default=DEFAULT_SEED)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "audit":
        report = audit_sources(load_source_specs(args.sources), args.output)
        print(f"audit complete: blocking_errors={report['blocking_errors']}")
        return 1 if report["blocking_errors"] else 0
    if args.command == "manifest":
        specs = load_source_specs(args.sources)
        audit_path = args.output / "audit.json"
        report = audit_sources(specs, audit_path)
        if report["blocking_errors"]:
            print(f"manifest blocked: blocking_errors={report['blocking_errors']}")
            return 1
        manifests = build_manifest(specs, args.output, args.seed)
        counts = {split: len(records) for split, records in manifests.items()}
        print(f"manifest complete: {counts}")
        return 0
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
