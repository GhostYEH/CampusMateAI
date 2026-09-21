"""真实链路端到端验证：managed service -> MiMo TTS -> artifact -> 场景归属。

这不是 mock：它用配置里的真实 MiMo 凭据合成音频，验证的正是学生点「生成讲解」
之后会发生的事。用两个不同的场景来验证音频不会串页。
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.services.magicclass.service_assertion import issue_service_assertion  # noqa: E402

BASE = "http://127.0.0.1:4010"
SERVICE_ENV = Path(__file__).resolve().parents[1] / "magicclass-service" / ".env"


def read_secret() -> str:
    for line in SERVICE_ENV.read_text(encoding="utf-8").splitlines():
        if line.startswith("MAGICCLASS_INTERNAL_SECRET="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("no secret")


DB_PATH = Path(__file__).resolve().parents[1] / "magicclass-service" / "data" / "magicclass-service.db"


def read_job_input(job_id: str) -> dict:
    """读回任务入参。

    `input_json` 是服务端内部状态，不在 job 的公开响应里，所以这里直接查库——
    验证的是"实际送去合成的参数"，而不是接口声称的参数。
    """
    import sqlite3

    connection = sqlite3.connect(str(DB_PATH))
    try:
        row = connection.execute("select input_json from jobs where id = ?", (job_id,)).fetchone()
    finally:
        connection.close()
    return json.loads(row[0]) if row and row[0] else {}


SECRET = read_secret()
COURSE = "audit-course"
USER = "audit-user"


def call(method: str, path: str, *, scopes, body=None, key=None, course=None):
    """每次调用铸一枚新断言：断言带 jti 且一次性消费。"""
    # 默认值必须在**调用时**取全局 COURSE。写成 `course=COURSE` 会在导入时求值一次，
    # 之后重新绑定 COURSE 就失效了 —— 那会让第二次运行仍然用旧课程，鉴权直接 403。
    course = COURSE if course is None else course
    token = issue_service_assertion(user_id=USER, course_id=course, scopes=scopes, secret=SECRET)
    headers = {"X-CampusMate-Service-Assertion": token, "Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if key:
        headers["Idempotency-Key"] = key
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(BASE + path, headers=headers, method=method, data=data)
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            return response.status, json.loads(response.read().decode())
    except urllib.error.HTTPError as error:
        raw = error.read().decode()
        try:
            return error.code, json.loads(raw)
        except Exception:
            return error.code, {"raw": raw}


def main() -> int:
    failures: list[str] = []
    # 每次运行都用新的课堂/舞台：讲解是**持久化**的，复用上一次的舞台会让
    # "生成前应当没有音频"这条断言读到上一轮留下的成品。
    run_tag = str(int(time.time()))
    course = f"audit-course-{run_tag}"
    global COURSE
    COURSE = course

    def check(label: str, ok: bool, detail: str = "") -> None:
        print(f"{'PASS' if ok else 'FAIL'}  {label}{(' — ' + detail) if detail else ''}")
        if not ok:
            failures.append(label)

    # 1) 建工作台 + 舞台（两页内容明显不同的幻灯片）
    status, workspace = call("POST", f"/internal/courses/{COURSE}/workspaces",
                             scopes=["workspace:write"], body={"name": "端到端验证"}, key=f"e2e-ws-{run_tag}")
    check("创建课堂工作台", status == 201, f"status={status}")
    workspace_id = workspace["id"]

    document = {
        "dslVersion": "0.3.0",
        "stage": {"id": "stage-e2e", "name": "端到端验证", "createdAt": 1, "updatedAt": 1},
        "scenes": [
            {"id": "scene-alpha", "stageId": "stage-e2e", "title": "牛顿第一定律", "order": 0, "type": "slide",
             "content": {"type": "slide",
                         "slide": {"title": "牛顿第一定律", "bullets": ["物体在不受外力时保持静止或匀速直线运动"]},
                         "canvas": {"title": "牛顿第一定律", "body": "物体在不受外力时保持静止或匀速直线运动"}}},
            {"id": "scene-beta", "stageId": "stage-e2e", "title": "动量守恒", "order": 1, "type": "slide",
             "content": {"type": "slide",
                         "slide": {"title": "动量守恒", "bullets": ["系统不受外力时总动量保持不变"]},
                         "canvas": {"title": "动量守恒", "body": "系统不受外力时总动量保持不变"}}},
        ],
    }
    status, stage = call("POST", f"/internal/courses/{COURSE}/workspaces/{workspace_id}/stages",
                         scopes=["workspace:write"], body={"title": "端到端验证", "document": document}, key=f"e2e-st-{run_tag}")
    check("创建舞台（两页）", status == 201, f"status={status}")
    stage_id = stage["id"]

    def narration(scene_id: str, *, method="GET", key=None):
        return call(method, f"/internal/courses/{COURSE}/workspaces/{workspace_id}/stages/{stage_id}/scenes/{scene_id}/narration",
                    scopes=["tts:write"] if method == "POST" else ["tts:read"],
                    body={"scene_id": scene_id, "stage_id": stage_id} if method == "POST" else None, key=key)

    # 2) 生成前：两页都还没有音频
    status, before = narration("scene-alpha")
    check("生成前 alpha 无音频", status == 200 and before["job"] is None and before["has_script"], json.dumps(before, ensure_ascii=False)[:160])

    # 3) 真实合成 alpha
    status, started = narration("scene-alpha", method="POST", key=f"e2e-n-alpha-{run_tag}")
    check("alpha 入队成功", status == 201, f"status={status} body={json.dumps(started, ensure_ascii=False)[:160]}")
    alpha_job = started["job"]["id"]

    # 4) 重复点击必须复用，不重复计费
    status, again = narration("scene-alpha", method="POST", key=f"e2e-n-alpha2-{run_tag}")
    check("重复点击复用同一任务", again.get("reuse") is True and again["job"]["id"] == alpha_job, json.dumps(again, ensure_ascii=False)[:160])

    # 5) 轮询到完成
    job = None
    deadline = time.time() + 170
    while time.time() < deadline:
        status, job = call("GET", f"/internal/courses/{COURSE}/jobs/{alpha_job}", scopes=["job:read"])
        if job.get("status") in ("completed", "failed"):
            break
        time.sleep(2)
    check("alpha 任务完成", job and job.get("status") == "completed",
          f"status={job and job.get('status')} error={job and job.get('error_code')}")
    check("alpha 任务带场景归属", job and job.get("scene_id") == "scene-alpha", f"scene_id={job and job.get('scene_id')}")

    if not (job and job.get("status") == "completed"):
        print("\n合成未成功，后续断言跳过")
        print(json.dumps(failures, ensure_ascii=False))
        return 1

    # 6) 取音频产物：必须是真 WAV，且文件名指向 alpha
    status, artifact = call("GET", f"/internal/courses/{COURSE}/artifacts/{job['artifact_id']}", scopes=["job:read"])
    import base64
    audio = base64.b64decode(artifact["content_base64"])
    check("产物是 audio/wav", artifact["media_type"] == "audio/wav", artifact["media_type"])
    check("产物是合法 RIFF/WAVE", audio[:4] == b"RIFF" and audio[8:12] == b"WAVE", f"head={audio[:12]!r}")
    check("音频非空且有实际时长", len(audio) > 44, f"bytes={len(audio)}")
    check("文件名指向 alpha", "牛顿第一定律" in artifact["filename"], artifact["filename"])
    print(f"      alpha 音频: {artifact['filename']}  {len(audio)} bytes  sha256={artifact['sha256'][:16]}…")

    # 7) 读回：alpha 有音频，beta 仍然没有（不会串页）
    status, read_alpha = narration("scene-alpha")
    check("读回 alpha 有音频", read_alpha["job"] and read_alpha["job"]["scene_id"] == "scene-alpha",
          json.dumps(read_alpha, ensure_ascii=False)[:200])

    status, read_beta = narration("scene-beta")
    check("beta 不会被 alpha 的音频顶替", read_beta["job"] is None, json.dumps(read_beta, ensure_ascii=False)[:200])

    # 8) 为 beta 生成，验证两页各自独立
    status, beta_started = narration("scene-beta", method="POST", key=f"e2e-n-beta-{run_tag}")
    check("beta 入队成功", status == 201, f"status={status}")
    beta_job = beta_started["job"]["id"]
    check("beta 是独立任务", beta_job != alpha_job)

    deadline = time.time() + 170
    beta = None
    while time.time() < deadline:
        status, beta = call("GET", f"/internal/courses/{COURSE}/jobs/{beta_job}", scopes=["job:read"])
        if beta.get("status") in ("completed", "failed"):
            break
        time.sleep(2)
    check("beta 任务完成", beta and beta.get("status") == "completed", f"status={beta and beta.get('status')}")

    if beta and beta.get("status") == "completed":
        status, beta_artifact = call("GET", f"/internal/courses/{COURSE}/artifacts/{beta['artifact_id']}", scopes=["job:read"])
        beta_audio = base64.b64decode(beta_artifact["content_base64"])
        check("beta 产物文件名指向 beta", "动量守恒" in beta_artifact["filename"], beta_artifact["filename"])
        check("两页音频内容不同", beta_audio != audio, f"alpha={len(audio)}B beta={len(beta_audio)}B")
        check("beta 任务场景归属正确", beta.get("scene_id") == "scene-beta", str(beta.get("scene_id")))
        print(f"      beta  音频: {beta_artifact['filename']}  {len(beta_audio)} bytes")

    # 9) 再次读回：两页各自正确（模拟刷新页面）
    _, final_alpha = narration("scene-alpha")
    _, final_beta = narration("scene-beta")
    check("刷新后 alpha 仍指向自己", final_alpha["job"]["scene_id"] == "scene-alpha" and final_alpha["job"]["artifact_id"] == job["artifact_id"])
    check("刷新后 beta 仍指向自己", final_beta["job"]["scene_id"] == "scene-beta")

    # 10) 讲稿真的来自场景正文（而不是别的东西）
    # `input_json` 不在 job 的公开响应里（它属于服务端内部状态），所以直接读库。
    jobs_input = read_job_input(job["id"])
    print(f"      alpha 讲稿: {jobs_input.get('text', '')}")
    check("alpha 讲稿来自 alpha 正文", "牛顿第一定律" in jobs_input.get("text", "") and "动量守恒" not in jobs_input.get("text", ""))
    check("使用 mimo-v2.5-tts 模型", job.get("mode") == "mimo-v2.5-tts", str(job.get("mode")))
    check("音色来自服务端配置", bool(jobs_input.get("voice")), str(jobs_input.get("voice")))
    check("讲稿带场景归属", jobs_input.get("scene_id") == "scene-alpha", str(jobs_input.get("scene_id")))

    print()
    if failures:
        print(f"[FAIL] {len(failures)} 项失败: {failures}")
        return 1
    print("[OK] 全部端到端断言通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
