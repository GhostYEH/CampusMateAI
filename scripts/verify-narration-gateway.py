"""经 FastAPI 网关的讲解链路验证（浏览器实际走的那条路）。

与 `verify-narration-e2e.py` 的区别：那个脚本直连受管服务，验证的是服务端本身；
这个脚本走 `/api/v1/...` + 真实登录令牌，验证的是**浏览器 → FastAPI 网关 →
受管服务**这一段，包括课程权限校验和断言签发。这是学生真正点击时经过的路径。
"""

from __future__ import annotations

import base64
import json
import secrets
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

BASE = "http://127.0.0.1:8000/api/v1"
failures: list[str] = []

#: 演示班级：学生自注册后无权建课（这是正确行为），所以加入一个已有班级来取得
#: 课程访问权。这两项来自演示数据，不是硬编码的本机路径。
DEMO_CLASS = ("crs_620a86b9e8104310", "cls_163e90622c544dcf")
DEMO_INVITE = "453EYHKL"


def request(method, path, *, token=None, body=None, key=None):
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        headers["Content-Type"] = "application/json"
    if key:
        headers["Idempotency-Key"] = key
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, headers=headers, method=method, data=data)
    try:
        with urllib.request.urlopen(req, timeout=180) as response:
            raw = response.read()
            try:
                return response.status, json.loads(raw.decode())
            except Exception:
                return response.status, {"_raw": raw}
    except urllib.error.HTTPError as error:
        raw = error.read().decode()
        try:
            return error.code, json.loads(raw)
        except Exception:
            return error.code, {"raw": raw[:300]}


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"{'PASS' if ok else 'FAIL'}  {label}{(' — ' + detail) if detail else ''}")
    if not ok:
        failures.append(label)


def main() -> int:
    stamp = int(time.time())
    username = f"narr{stamp}"
    password = "Narration#2026"

    # 注册只建号，不返回令牌（`/auth/register` 是 UserPublic），所以要再登一次。
    status, registered = request("POST", "/auth/register", body={
        "username": username, "password": password, "role": "student",
        "display_name": "讲解验证", "student_number": f"E2E{stamp}",
    })
    check("注册学生账号", status == 201, f"status={status} {json.dumps(registered, ensure_ascii=False)[:200]}")

    # 学生无权建课（正确行为），所以加入一个已有的演示班级来取得课程访问权。
    status, auth = request("POST", "/auth/login", body={"username": username, "password": password})
    token = auth.get("access_token") or auth.get("token")
    check("学生登录并取得令牌", bool(token), f"status={status} {json.dumps(auth, ensure_ascii=False)[:200]}")
    if not token:
        return 1

    course_id, class_id = DEMO_CLASS
    status, joined = request("POST", f"/classes/{class_id}/join", token=token, body={"invite_code": DEMO_INVITE})
    check("加入演示班级", status in (200, 201), f"status={status} {json.dumps(joined, ensure_ascii=False)[:200]}")

    status, visible = request("GET", f"/courses/{course_id}", token=token)
    check("学生可见该课程", status == 200, f"status={status} {json.dumps(visible, ensure_ascii=False)[:160]}")

    # 工作台
    status, workspace = request("POST", f"/courses/{course_id}/workspaces", token=token,
                                body={"name": "讲解验证"}, key=f"gw-ws-{stamp}")
    workspace_id = workspace.get("id")
    check("经网关创建课堂工作台", bool(workspace_id), f"status={status} {json.dumps(workspace, ensure_ascii=False)[:200]}")
    if not workspace_id:
        return 1

    # 舞台：两页内容不同，用来验证音频不串页
    document = {
        "dslVersion": "0.3.0",
        "stage": {"id": "stage-gw", "name": "讲解验证", "createdAt": 1, "updatedAt": 1},
        "scenes": [
            {"id": "scene-a", "stageId": "stage-gw", "title": "光合作用", "order": 0, "type": "slide",
             "content": {"type": "slide",
                         "slide": {"title": "光合作用", "bullets": ["植物把光能转化成化学能"]},
                         "canvas": {"title": "光合作用", "body": "植物把光能转化成化学能"}}},
            {"id": "scene-b", "stageId": "stage-gw", "title": "细胞呼吸", "order": 1, "type": "slide",
             "content": {"type": "slide",
                         "slide": {"title": "细胞呼吸", "bullets": ["细胞分解有机物释放能量"]},
                         "canvas": {"title": "细胞呼吸", "body": "细胞分解有机物释放能量"}}},
        ],
    }
    status, stage = request("POST", f"/courses/{course_id}/workspaces/{workspace_id}/stages", token=token,
                            body={"title": "讲解验证", "document": document}, key=f"gw-st-{stamp}")
    stage_id = stage.get("id")
    check("经网关创建舞台", bool(stage_id), f"status={status} {json.dumps(stage, ensure_ascii=False)[:200]}")
    if not stage_id:
        return 1

    def narration(scene_id, *, post=False, key=None):
        path = f"/courses/{course_id}/workspaces/{workspace_id}/stages/{stage_id}/scenes/{scene_id}/narration"
        if post:
            return request("POST", path, token=token, body={"scene_id": scene_id, "stage_id": stage_id}, key=key)
        return request("GET", path, token=token)

    # 1) 生成前无音频
    status, before = narration("scene-a")
    check("生成前 scene-a 无音频", status == 200 and before.get("job") is None,
          json.dumps(before, ensure_ascii=False)[:200])

    # 2) 经网关生成
    status, started = narration("scene-a", post=True, key=f"gw-n-a-{stamp}")
    check("经网关排队生成讲解", status == 202 and started.get("job"), f"status={status} {json.dumps(started, ensure_ascii=False)[:200]}")
    job = (started.get("job") or {})
    job_id = job.get("id")

    # 3) 重复点击复用
    status, again = narration("scene-a", post=True, key=f"gw-na2-{stamp}")
    check("重复点击经网关仍复用同一任务", again.get("reuse") is True and (again.get("job") or {}).get("id") == job_id,
          json.dumps(again, ensure_ascii=False)[:200])

    # 4) 轮询
    final = None
    deadline = time.time() + 170
    while time.time() < deadline:
        status, final = request("GET", f"/courses/{course_id}/jobs/{job_id}", token=token)
        if final.get("status") in ("completed", "failed"):
            break
        time.sleep(2)
    check("经网关查询任务完成", final and final.get("status") == "completed",
          f"status={final and final.get('status')} err={final and final.get('error_code')}")

    # 5) 取音频产物
    if final and final.get("status") == "completed":
        req = urllib.request.Request(
            f"{BASE}/courses/{course_id}/artifacts/{final['artifact_id']}",
            headers={"Authorization": f"Bearer {token}"},
        )
        with urllib.request.urlopen(req, timeout=60) as response:
            audio = response.read()
            ctype = response.headers.get("content-type")
            disp = response.headers.get("content-disposition", "")
        check("经网关拿到 audio/wav", ctype == "audio/wav", str(ctype))
        check("音频是合法 WAV 且非空", audio[:4] == b"RIFF" and audio[8:12] == b"WAVE" and len(audio) > 44,
              f"{len(audio)} bytes head={audio[:12]!r}")
        check("下载文件名指向 scene-a", "光合作用" in urllib.parse.unquote(disp), disp)
        print(f"      音频 {len(audio)} bytes")

    # 6) 读回：两页各自正确
    _, read_a = narration("scene-a")
    _, read_b = narration("scene-b")
    check("读回 scene-a 指向自己", (read_a.get("job") or {}).get("scene_id") == "scene-a",
          json.dumps(read_a, ensure_ascii=False)[:180])
    check("scene-b 未被 scene-a 的音频顶替", read_b.get("job") is None,
          json.dumps(read_b, ensure_ascii=False)[:180])

    # 7) 权限：别人的课程必须被拒
    other = request("GET", "/courses/not-my-course/workspaces", token=token)
    check("跨课程访问被网关拒绝", other[0] in (403, 404), f"status={other[0]}")

    # 8) 缺 Idempotency-Key 必须被拒（不会打到上游）
    status, no_key = narration("scene-b", post=True)
    check("缺幂等键被拒", status == 400, f"status={status} {json.dumps(no_key, ensure_ascii=False)[:160]}")

    print()
    if failures:
        print(f"[FAIL] {len(failures)} 项失败: {failures}")
        return 1
    print("[OK] 网关链路全部断言通过")
    return 0


if __name__ == "__main__":
    import urllib.parse  # noqa: E402

    raise SystemExit(main())
