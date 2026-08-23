from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        prog="behavior-recognition",
        description="CampusMateAI behavior recognition pipeline",
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    parser.parse_args(argv)
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
