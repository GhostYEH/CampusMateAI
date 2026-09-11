from __future__ import annotations

import argparse
from pathlib import Path

from .dataset import DATASET_VERSION, RANDOM_SEED, write_shadow_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the deterministic synthetic CampusMate-LM shadow dataset")
    parser.add_argument("--version", default=DATASET_VERSION)
    parser.add_argument("--seed", type=int, default=RANDOM_SEED)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parents[3] / "datasets")
    args = parser.parse_args()
    write_shadow_dataset(args.output_dir, seed=args.seed, version=args.version)


if __name__ == "__main__":
    main()
