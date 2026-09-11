from __future__ import annotations

import argparse
from pathlib import Path

from .sft import build_sft_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="Build deterministic train/validation SFT JSONL artifacts")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    build_sft_dataset(args.dataset, args.output_dir)


if __name__ == "__main__":
    main()
