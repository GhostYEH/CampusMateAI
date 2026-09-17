"""Web E2E 夹具：把「课程知识图谱」写进 E2E 临时库。

用真实链路，不 mock：脱敏页面 fixture → 真实 ChaoxingParser → 真实 ChaoxingRepository。

单独进程运行（由 course-knowledge-graph-e2e.py 通过 subprocess 拉起），
因为它需要自己的 DATABASE_URL，避免与 uvicorn 进程共享 Database 单例。

用法: python _seed_course_knowledge_graph.py <username> <database_url>
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE = REPO_ROOT / "backend/tests/fixtures/chaoxing/course_knowledge_graph.html"

sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.core.config import Settings  # noqa: E402
from app.services.chaoxing.ChaoxingClient import ChaoxingParser  # noqa: E402
from app.services.container import build_container  # noqa: E402


def main() -> int:
    username = sys.argv[1]
    database_url = sys.argv[2]

    parsed = ChaoxingParser.parse_knowledge_graph(FIXTURE.read_text(encoding="utf-8"))
    points = parsed.get("knowledge_points") or []
    assert len(points) == 21, f"fixture 解析出 {len(points)} 个知识点，期望 21"

    container = build_container(Settings(database_url=database_url, app_env="test"))
    user = container.user_repository.get_user_by_username(username)
    assert user is not None, f"用户 {username} 不存在（AUTO_SEED_DEMO_USERS 是否开启？）"

    course = container.course_repository.create_course(
        name="高等数学（Ⅱ）",
        owner_user_id=user.id,
        provider="chaoxing",
        external_id="11_22",
        remote_teacher_name="演示教师",
        remote_class_name="高数Ⅱ-01班",
        status="active",
    )
    written = container.chaoxing_repository.upsert_knowledge_graph(
        user_id=user.id,
        course_id=course.id,
        external_course_id="11_22",
        graph=parsed,
        points=points,
    )
    print(
        f"seeded course={course.id} graph={written['graph_id']} "
        f"points={written['point_count']} own={written['own_mastery_rate']} "
        f"class={written['class_mastery_rate']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
