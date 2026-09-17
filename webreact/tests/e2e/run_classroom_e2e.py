"""互动课堂浏览器 E2E 入口：启动 Vite，执行检查并在任何结果下回收服务。"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from run_study_e2e import find_free_port, start_vite, stop_process_tree, wait_for_vite


HERE = Path(__file__).resolve().parent
CHECK = HERE / "interactive-classroom-browser.py"
BASE_PORT = int(os.environ.get("CLASSROOM_E2E_PORT", "5184"))


def main() -> int:
    port = find_free_port(BASE_PORT)
    print(f"启动 Vite dev 服务，端口 {port}")
    try:
        process = start_vite(port)
    except RuntimeError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2

    try:
        wait_for_vite(port)
        print(f"Vite 已就绪：http://127.0.0.1:{port}/")
        env = {**os.environ, "WEB_BASE_URL": f"http://127.0.0.1:{port}"}
        return subprocess.run([sys.executable, str(CHECK)], env=env).returncode
    except RuntimeError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2
    finally:
        stop_process_tree(process)


if __name__ == "__main__":
    raise SystemExit(main())
