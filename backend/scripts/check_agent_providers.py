from __future__ import annotations

import argparse
import json

from app.core.config import get_settings
from app.services.llm.provider_registry import ProviderRegistry


def main() -> None:
    parser = argparse.ArgumentParser(description="Secret-safe Agent provider configuration check")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = {"providers": ProviderRegistry.from_settings(get_settings()).diagnostic()}
    if args.json:
        print(json.dumps(report, sort_keys=True))
    else:
        for name, configured in report["providers"].items():
            print(f"{name}: {'configured' if configured else 'not configured'}")


if __name__ == "__main__":
    main()
