"""OpenMAIC 学习工作台浏览器验收入口：拉起隔离的三服务，跑真实浏览器检查，最后回收。

用法（从仓库根目录）：

    backend/.venv/Scripts/python.exe webreact/tests/e2e/run_openmaic_workbench_e2e.py

和 `run_openmaic_courses_e2e.py` 同构（同样的隔离措施、同样的端口探测、同样在任何
结果下回收进程与端口），只是把浏览器检查换成 `openmaic_workbench_browser.py` 的
"前端视觉对齐 + 响应式互斥单面板"验收。做到这一步的原因是工作台上一次的 P1 缺陷
（窄屏 rail 固定 60px、课堂无条件渲染）在单测里全绿，只有真实浏览器量几何才看得见。
"""

from __future__ import annotations

import os
import secrets
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

# 复用 courses E2E 里已经验证过的三服务编排：同一套隔离、同一套回收。
from run_openmaic_courses_e2e import (  # noqa: E402
    BACKEND,
    SERVICE,
    WEBREACT,
    ServiceControl,
    _popen,
    dump_logs,
    find_free_port,
    provision_databases,
    resolve_node,
    resolve_python,
    stop_process_tree,
    wait_for,
    wait_for_port_release,
)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(errors="replace")
    node = resolve_node()
    python = resolve_python()
    tmp_root = Path(tempfile.mkdtemp(prefix="campusmate-openmaic-workbench-e2e-"))
    print(f"隔离临时目录：{tmp_root}")

    backend_db, service_db = provision_databases(tmp_root)
    secret = secrets.token_urlsafe(36)

    service_port = find_free_port(4210)
    backend_port = find_free_port(8021)
    web_port = find_free_port(5194)

    base_env = {**os.environ, "NO_PROXY": "127.0.0.1,localhost", "no_proxy": "127.0.0.1,localhost"}

    service = ServiceControl(
        [node, "--experimental-strip-types", "src/main.ts"],
        SERVICE,
        {
            **base_env,
            "OPENMAIC_HOST": "127.0.0.1",
            "OPENMAIC_PORT": str(service_port),
            "OPENMAIC_DATABASE_URL": str(service_db),
            "OPENMAIC_INTERNAL_SECRET": secret,
        },
        service_port,
        tmp_root / "openmaic-service.log",
    )
    logs = {
        "openmaic-service": tmp_root / "openmaic-service.log",
        "FastAPI": tmp_root / "fastapi.log",
        "Vite": tmp_root / "vite.log",
    }
    backend = None
    vite = None
    exit_code = 0
    try:
        print(f"启动 openmaic-service :{service_port}")
        service.start()
        print(f"启动 FastAPI          :{backend_port}")
        backend = _popen(
            [python, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
             "--port", str(backend_port), "--log-level", "warning"],
            cwd=BACKEND,
            env={
                **base_env,
                "DATABASE_URL": f"sqlite:///{backend_db.as_posix()}",
                "OPENMAIC_FUSION_ENABLED": "true",
                "OPENMAIC_SERVICE_URL": f"http://127.0.0.1:{service_port}",
                "OPENMAIC_INTERNAL_SECRET": secret,
                "OPENMAIC_SERVICE_TIMEOUT_SECONDS": "5",
                "OPENMAIC_ENABLED": "false",
                "LOG_LEVEL": "WARNING",
            },
            log_file=logs["FastAPI"],
        )
        wait_for(f"http://127.0.0.1:{backend_port}/api/v1/health", label="FastAPI")

        print(f"启动 Vite             :{web_port}")
        vite = _popen(
            [node, str(WEBREACT / "node_modules" / "vite" / "bin" / "vite.js"),
             "--port", str(web_port), "--strictPort", "--host", "127.0.0.1"],
            cwd=WEBREACT,
            env={**base_env, "VITE_BACKEND_PORT": str(backend_port)},
            log_file=logs["Vite"],
        )
        wait_for(f"http://127.0.0.1:{web_port}/", label="Vite")

        base_url = f"http://127.0.0.1:{web_port}"
        print(f"三服务就绪，浏览器验收目标：{base_url}\n")

        os.environ["WEB_BASE_URL"] = base_url
        # 截图落在本次运行的临时目录里，随 finally 的 rmtree 一起消失——仓库里不留
        # 任何产物，也就不需要靠 .gitignore 去掩盖。
        os.environ["E2E_SHOTS_DIR"] = str(tmp_root / "shots")
        import openmaic_workbench_browser  # noqa: E402  （必须在 WEB_BASE_URL 之后导入）

        result = openmaic_workbench_browser.run_checks(service)
        print("\n===== 工作台浏览器验收报告 =====")
        for line in result["report"]:
            print(f"  · {line}")
        if result["shots"]:
            print("  · 截图：" + "、".join(Path(p).name for p in result["shots"]))
        print("\nALL OPENMAIC WORKBENCH E2E CHECKS PASSED")
    except Exception as exc:  # noqa: BLE001 - 入口脚本要把失败原因完整打出来
        print(f"\nE2E 失败：{type(exc).__name__}: {exc}", file=sys.stderr)
        dump_logs(logs)
        exit_code = 1
    finally:
        stop_process_tree(vite)
        stop_process_tree(backend)
        service.stop()
        for port, label in ((web_port, "Vite"), (backend_port, "FastAPI"), (service_port, "openmaic-service")):
            if wait_for_port_release(port, timeout=5):
                print(f"{label} 已回收，端口 {port} 已释放")
            else:
                print(f"错误：{label} 退出后端口 {port} 仍被占用", file=sys.stderr)
                exit_code = 1
        shutil.rmtree(tmp_root, ignore_errors=True)

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
