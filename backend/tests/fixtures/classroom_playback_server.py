"""启动脱敏经典课堂联调服务器。

用途：真实 magic class 上游不可用时，让 Android/iOS 通过真实 HTTP 访问本仓库
的播放、媒体、经典 quiz-attempt 契约。数据来自 `test_magicclass_playback.py`
的合成课堂。开场包含 PNG、两段不同音高的 WAV 测试音和项目已有的 MP4。

启动（在 backend 目录）：
    .venv_check\\Scripts\\python.exe tests\\fixtures\\classroom_playback_server.py --port 8000

然后使用 demo 学生账号登录，按脚本打印的 course_id / session_id 请求。
这不是生产服务，也不代表真实生成课堂；仅用于双端联调和契约回归。
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

import uvicorn

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(BACKEND_DIR / "tests") not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR / "tests"))

import test_magicclass_playback as fixture  # noqa: E402
from app.api.routes.magicclass_playback import SELF_COURSE_ID  # noqa: E402


def _playable_fixture() -> tuple[dict, dict[str, tuple[str, bytes]]]:
    classroom = fixture._classroom_document()
    slide = next(scene for scene in classroom["scenes"] if scene["id"] == "sc_slide")
    bounds = {
        "img_1": (80, 100, 240, 160),
        "vid_1": (400, 100, 530, 360),
        "aud_1": (80, 320, 240, 80),
    }
    for element in slide["content"]["canvas"]["elements"]:
        if element["id"] in bounds:
            left, top, width, height = bounds[element["id"]]
            element.update(left=left, top=top, width=width, height=height)

    media_root = f"/api/classroom-media/{classroom['id']}"
    first_clip = f"{media_root}/audio/tts_s1_a1.wav"
    second_clip = f"{media_root}/audio/tts_s1_followup.wav"
    slide["actions"][0]["text"] = "第一段讲解测试音（低音）"
    slide["actions"].insert(
        1,
        {
            "id": "a_followup",
            "type": "speech",
            "text": "第二段讲解测试音（高音）",
            "audioUrl": second_clip,
        },
    )

    video_path = BACKEND_DIR.parent / "android/app/src/main/res/raw/login_campus.mp4"
    media = fixture._media_payloads()
    media[f"{media_root}/media/vid_1.mp4"] = ("video/mp4", video_path.read_bytes())
    media[first_clip] = ("audio/wav", fixture._valid_wav(frequency=392, frame_count=8000))
    media[second_clip] = ("audio/wav", fixture._valid_wav(frequency=659, frame_count=8000))
    return classroom, media


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    classroom, media = _playable_fixture()
    handler = fixture._default_handler([], classroom=classroom, media=media)
    ctx = fixture._setup_routes(Path(tempfile.mkdtemp()), handler)
    fixture._save_session(
        ctx.store,
        user_id=ctx.user_id,
        course_id=ctx.course_id,
        session_id="sess_fixture_course",
        classroom_id="cls_demo",
    )
    fixture._save_session(
        ctx.store,
        user_id=ctx.user_id,
        course_id=SELF_COURSE_ID,
        session_id="sess_fixture_self",
        classroom_id="cls_demo",
    )
    # 用于验证“不属于本人”的拒绝：这个会话属于另一个账号。
    fixture._save_session(
        ctx.store,
        user_id="fixture-other-user",
        course_id=ctx.course_id,
        session_id="sess_fixture_foreign",
        classroom_id="cls_demo",
    )

    info = {
        "source": "synthetic-sanitized-fixture",
        "login": {"username": "student_demo", "password": "Demo123456"},
        "course_id": ctx.course_id,
        "course_session_id": "sess_fixture_course",
        "self_session_id": "sess_fixture_self",
        "foreign_session_id": "sess_fixture_foreign",
        "quiz_scene_id": "sc_quiz",
        "sandbox_scene_id": "sc_int",
        "compat_scene_id": "sc_pbl",
        "media": {
            "image": "media/img_1.png",
            "narration": "audio/tts_s1_a1.wav",
            "narration_followup": "audio/tts_s1_followup.wav",
            "video": "media/vid_1.mp4",
        },
        "listen": f"http://{args.host}:{args.port}",
    }
    print(json.dumps(info, ensure_ascii=False, indent=2), flush=True)
    uvicorn.run(ctx.client.app, host=args.host, port=args.port, log_level="warning", lifespan="off")


if __name__ == "__main__":
    main()
