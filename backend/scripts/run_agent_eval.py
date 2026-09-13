"""运行 Agent Runtime 评测,用于 CI 门禁与论文指标。

用法(在 backend/ 目录下):
    python scripts/run_agent_eval.py
    python scripts/run_agent_eval.py --level L0
    python scripts/run_agent_eval.py --out data/agent_eval_report.json

退出码:全部通过为 0;存在失败为 1。P0 用例失败同样计为失败,
便于直接在 CI 里当门禁使用。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.services.agent_eval import cases_by_level, format_text, run_cases  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Agent Runtime 评测")
    parser.add_argument("--level", choices=["L0", "L1", "L2"], help="只跑某一层用例")
    parser.add_argument("--out", help="把 JSON 报告写到指定路径")
    args = parser.parse_args(argv)

    cases = None
    if args.level:
        cases = list(cases_by_level(args.level))  # type: ignore[arg-type]
        if not cases:
            print(f"没有 {args.level} 层用例", file=sys.stderr)
            return 1

    report = run_cases(cases)
    print(format_text(report))

    if args.out:
        target = Path(args.out)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\nJSON 报告已写入 {target}")

    return 0 if report.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
