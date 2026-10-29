#!/usr/bin/env python3
"""Run iOS checks against a fresh, explicitly located disposable backend database."""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ui", action="store_true", help="also run native UI tests")
    parser.add_argument("--device", help="installed simulator UDID (required for --ui)")
    parser.add_argument("--derived-data", type=Path, help="reuse an external Xcode build cache between devices")
    args = parser.parse_args()
    if args.ui and not args.device:
        parser.error("--ui requires --device from xcrun simctl list devices available")
    repo = Path(__file__).resolve().parents[2]
    # Preserve the virtualenv entry point; resolving its symlink bypasses the venv.
    python = Path(os.environ.get("CAMPUS_BACKEND_PYTHON", repo / "backend/.venv/bin/python")).absolute()
    if not python.is_file():
        parser.error("Backend environment unavailable; set CAMPUS_BACKEND_PYTHON to the existing backend interpreter")
    # Refuse to reuse even a test-configured server: its DB location cannot be proven remotely.
    with socket.socket() as probe:
        try:
            probe.bind(("127.0.0.1", 18927))
        except OSError:
            parser.error("Port 18927 is occupied. Stop the previous validation server before running this command")
    scratch = Path(tempfile.mkdtemp(prefix="campusmate-ios-validation-"))
    print(f"Disposable validation directory: {scratch}", flush=True)
    env = dict(os.environ)
    env.update({
        "APP_ENV": "test", "DATABASE_URL": f"sqlite:///{scratch / 'validation.sqlite'}",
        "KNOWLEDGE_BASE_PATH": str(scratch / "knowledge"),
        "COMMUNITY_IMAGE_PATH": str(scratch / "community_images"),
        "EXPRESSION_CONTRIBUTION_PATH": str(scratch / "contributions"),
        "CHAOXING_CACHE_PATH": str(scratch / "chaoxing_cache"),
        "AUTO_SEED_DEMO_USERS": "false", "AGENT_ALLOW_MOCK_PROVIDERS": "false",
        "LLM_PROVIDER": "none", "CAMPUS_RUN_LOCAL_INTEGRATION": "1",
    })
    backend = None
    try:
        with (scratch / "backend.log").open("w") as output:
            backend = subprocess.Popen([
                str(python), "-m", "uvicorn", "app.main:app", "--app-dir", str(repo / "backend"),
                "--host", "127.0.0.1", "--port", "18927",
            ], cwd=scratch, env=env, stdout=output, stderr=subprocess.STDOUT)
            for _ in range(120):
                if backend.poll() is not None:
                    raise RuntimeError("Disposable backend exited; inspect backend.log")
                try:
                    with urllib.request.urlopen("http://127.0.0.1:18927/api/v1/health", timeout=1) as response:
                        if json.load(response).get("env") == "test":
                            break
                except (OSError, ValueError):
                    pass
                time.sleep(0.5)
            else:
                raise RuntimeError("Disposable backend did not become ready")
            if not (scratch / "validation.sqlite").is_file():
                raise RuntimeError("Expected disposable database does not exist; validation aborted")
            commands = [["swift", "test", "--package-path", str(repo / "ios/Packages/CampusCore"), "--scratch-path", str(scratch / "CoreBuild")]]
            if args.ui:
                commands.append([
                    "xcodebuild", "-project", str(repo / "ios/CampusMate.xcodeproj"), "-scheme", "CampusMate",
                    "-configuration", "Debug", "-destination", f"platform=iOS Simulator,id={args.device}",
                    "-derivedDataPath", str(args.derived_data.absolute() if args.derived_data else scratch / "DerivedData"), "-resultBundlePath", str(scratch / "NativeUI.xcresult"),
                    "-parallel-testing-enabled", "NO", "test",
                ])
            for index, command in enumerate(commands):
                log = scratch / f"check-{index + 1}.log"
                with log.open("w") as check_output:
                    subprocess.run(command, cwd=repo, env=env, stdout=check_output, stderr=subprocess.STDOUT, check=True)
                print("\n".join(log.read_text().splitlines()[-12:]), flush=True)
            print("Checks passed. Logs and simulator results remain in the disposable validation directory.")
    finally:
        if backend and backend.poll() is None:
            backend.terminate()
            try:
                backend.wait(timeout=15)
            except subprocess.TimeoutExpired:
                backend.kill(); backend.wait()


if __name__ == "__main__":
    main()
