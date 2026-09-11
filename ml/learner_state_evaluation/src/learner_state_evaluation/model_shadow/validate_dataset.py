from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .dataset import load_shadow_dataset


def validate_files(data_path: Path, manifest_path: Path, output_path: Path) -> dict:
    rows = load_shadow_dataset(data_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["records_sha256"] != hashlib.sha256(data_path.read_bytes()).hexdigest() or manifest["sample_count"] != len(rows):
        raise ValueError("dataset manifest digest or count does not match")
    report = {"valid": True, "dataset_version": manifest["dataset_version"], "sample_count": len(rows),
              "capability_counts": manifest["capability_counts"], "split_counts": manifest["split_counts"],
              "sensitive_scan": manifest["sensitive_scan"], "leakage": manifest["leakage"],
              "decision_eligible": manifest["decision_eligible"]}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a synthetic CampusMate-LM shadow dataset")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    validate_files(args.dataset, args.manifest, args.output)


if __name__ == "__main__":
    main()
