"""学习通课程知识图谱接入 —— 解析 / 落库 / 事件 / 世界模型投影。

新版泛雅(fanya V3)的"课程图谱"页发布课程知识点体系与掌握率。这是**外部数据源观测**
(课程/学校发布的知识点 + 平台统计)，与被删除的 C 语言学习系统自造知识点推断无关，
因此命名一律避开 knowledge_components / knowledge_mastery_estimate 等旧术语。

下面用的 HTML 片段按真实页面结构裁剪并**脱敏**(不含姓名、课程 ID、账号)。
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.database.sqlite_db import Database
from app.repositories.chaoxing_repository import ChaoxingRepository
from app.repositories.course_content_repository import CourseContentRepository
from app.repositories.learner_event_repository import LearnerEventRepository
from app.repositories.learner_state_repository import LearnerStateRepository
from app.services.chaoxing.ChaoxingClient import ChaoxingParser
from app.services.chaoxing.course_content_sync import ChaoxingCourseContentSyncService
from app.services.learner_event_service import LearnerEventService
from app.services.learner_state_service import LearnerStateProjectionService

# 真实页面的结构: 课程级统计用固定 id(含平台自身的拼写错误 knowldegeCount)，
# 知识点用 firstLevel-<kpId>，标签在 cb_<tagId> 下拉里。
GRAPH_HTML = """
<div class="zheaderBox zheaderBg1">
  <p class="zname">知识点总数：</p><h2 class="znumber1" id="knowldegeCount">21</h2>
</div>
<div class="zheaderBox zheaderBg2">
  <p class="zname">平均掌握率：</p>
  <h2 class="znumber1"><span id="ownGraspWeightRate">87.5</span><small>%</small></h2>
  <p class="znumber2">班级平均掌握率：<span id="graspWeightRate">69</span><i>%</i></p>
</div>
<div class="zheaderBox zheaderBg3">
  <p class="zname">平均完成率：</p>
  <h2 class="znumber1"><span id="ownCompleteWeightRate">100</span><small>%</small></h2>
  <p class="znumber2">班级平均完成率：<span id="completeWeightRate">97</span><i>%</i></p>
</div>
<ul class="xrc__list">
  <li class="xrc__list__item single" id="firstLevel-166601061">格林公式</li>
  <li class="xrc__list__item single" id="firstLevel-193660305">连续、偏可导、可微的关系</li>
  <li class="xrc__list__item single" id="firstLevel-193663160">高阶偏导数计算</li>
</ul>
<li class="xdropdownBox__item"><input type="checkbox" data="1" id="cb_1"><label for="cb_1"><div class="ellips">重点</div></label></li>
<li class="xdropdownBox__item"><input type="checkbox" data="2" id="cb_2"><label for="cb_2"><div class="ellips">难点</div></label></li>
<li class="xdropdownBox__item"><input type="checkbox" data="3" id="cb_3"><label for="cb_3"><div class="ellips">三级</div></label></li>
<li class="xdropdownBox__item"><input type="checkbox" data="4" id="cb_4"><label for="cb_4"><div class="ellips">父子关系</div></label></li>
"""

GRAPH_STATS = {
    "knowledge_point_count": 21,
    "own_mastery_rate": 87.5,
    "class_mastery_rate": 69.0,
    "own_completion_rate": 100.0,
    "class_completion_rate": 97.0,
    "tags": ["重点", "难点"],
}
GRAPH_POINTS = [
    {"external_id": "166601061", "name": "格林公式"},
    {"external_id": "193660305", "name": "连续、偏可导、可微的关系"},
]


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _make_db() -> Database:
    return Database(None)


def _add_user(db: Database, user_id: str = "user1") -> None:
    with db.transaction() as conn:
        conn.execute(
            "INSERT INTO users (id, username, password_hash, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, user_id, "hash", "now", "now"),
        )


def _event_service(db: Database) -> LearnerEventService:
    return LearnerEventService(
        LearnerEventRepository(db),
        personal_task_repository=None,
        course_content_repository=None,
    )


def _projection_service(db: Database) -> LearnerStateProjectionService:
    return LearnerStateProjectionService(
        LearnerStateRepository(db),
        learner_event_repository=LearnerEventRepository(db),
    )


# --------------------------------------------------------------------------
# 1. 解析
# --------------------------------------------------------------------------

def test_parse_knowledge_graph_extracts_stats_points_and_tags():
    parsed = ChaoxingParser.parse_knowledge_graph(GRAPH_HTML)
    assert parsed["knowledge_point_count"] == 21.0
    assert parsed["own_mastery_rate"] == 87.5
    assert parsed["class_mastery_rate"] == 69.0
    assert parsed["own_completion_rate"] == 100.0
    assert parsed["class_completion_rate"] == 97.0
    assert [point["name"] for point in parsed["knowledge_points"]] == [
        "格林公式", "连续、偏可导、可微的关系", "高阶偏导数计算",
    ]
    assert parsed["knowledge_points"][0]["external_id"] == "166601061"
    # 标签下拉里混着层级(三级)与关系类型(父子关系)，必须剔除
    assert parsed["tags"] == ["重点", "难点"]


def test_parse_knowledge_graph_tolerates_missing_or_foreign_page():
    assert ChaoxingParser.parse_knowledge_graph("") == {}
    parsed = ChaoxingParser.parse_knowledge_graph("<html>请先登录</html>")
    assert parsed["knowledge_points"] == []
    assert parsed["tags"] == []
    assert "own_mastery_rate" not in parsed


# --------------------------------------------------------------------------
# 2. 落库
# --------------------------------------------------------------------------

def test_upsert_knowledge_graph_is_idempotent_and_flags_changes():
    db = _make_db()
    _add_user(db)
    repo = ChaoxingRepository(db)
    first = repo.upsert_knowledge_graph(
        user_id="user1", course_id="course_1", external_course_id="11_22",
        graph=GRAPH_STATS, points=GRAPH_POINTS,
    )
    assert first["changed"] is True
    assert first["new_point_count"] == 2

    second = repo.upsert_knowledge_graph(
        user_id="user1", course_id="course_1", external_course_id="11_22",
        graph=GRAPH_STATS, points=GRAPH_POINTS,
    )
    assert second["changed"] is False
    assert second["new_point_count"] == 0

    # 掌握率变化必须被识别出来，否则永远不会投射新事件
    third = repo.upsert_knowledge_graph(
        user_id="user1", course_id="course_1", external_course_id="11_22",
        graph={**GRAPH_STATS, "own_mastery_rate": 90.0}, points=GRAPH_POINTS,
    )
    assert third["changed"] is True

    stored = repo.list_knowledge_graphs(user_id="user1")
    assert len(stored) == 1
    assert stored[0]["own_mastery_rate"] == 90.0
    assert len(repo.list_knowledge_points(user_id="user1")) == 2


def test_knowledge_points_are_isolated_by_user():
    db = _make_db()
    _add_user(db, "user1")
    _add_user(db, "user2")
    repo = ChaoxingRepository(db)
    repo.upsert_knowledge_graph(
        user_id="user1", course_id="course_1", external_course_id="11_22",
        graph=GRAPH_STATS, points=GRAPH_POINTS,
    )
    assert repo.list_knowledge_points(user_id="user2") == []
    assert repo.list_knowledge_graphs(user_id="user2") == []


# --------------------------------------------------------------------------
# 3. 事件
# --------------------------------------------------------------------------

def test_knowledge_graph_sync_projects_event_once():
    db = _make_db()
    _add_user(db)

    class _Container:
        def __init__(self) -> None:
            self.chaoxing_repository = ChaoxingRepository(db)
            self.course_content_repository = CourseContentRepository(db)
            self.learner_event_service = _event_service(db)

    service = ChaoxingCourseContentSyncService(_Container())
    kwargs = dict(
        user_id="user1", course_id="course_1", course_external_id="11_22",
        graph=GRAPH_STATS, points=GRAPH_POINTS,
    )
    service._persist_knowledge_graph(**kwargs)
    events, total = _event_service(db).list_events(user_id="user1", page=1, page_size=10)
    assert total == 1
    assert events[0].event_type == "knowledge_graph_synced"
    assert events[0].payload["knowledge_point_count"] == 21

    # 重复同步同一份图谱不应重复投射
    service._persist_knowledge_graph(**kwargs)
    _, total = _event_service(db).list_events(user_id="user1", page=1, page_size=10)
    assert total == 1


# --------------------------------------------------------------------------
# 4. 世界模型投影
# --------------------------------------------------------------------------

def test_academic_projects_knowledge_mastery_observation():
    db = _make_db()
    _add_user(db)
    ChaoxingRepository(db).upsert_knowledge_graph(
        user_id="user1", course_id="course_1", external_course_id="11_22",
        graph=GRAPH_STATS, points=GRAPH_POINTS,
    )
    result = _projection_service(db).project_academic("user1", as_of=_now())
    observation = next(
        snapshot for snapshot in result.snapshots
        if snapshot.state_type == "knowledge_mastery_observation"
    )
    assert observation.value["knowledge_point_count"] == 2
    assert observation.value["own_mastery_rate"] == 87.5
    assert observation.value["class_mastery_rate"] == 69.0
    # 正数表示领先班级平均
    assert observation.value["mastery_gap_vs_class"] == 18.5
    assert observation.value["own_completion_rate"] == 100.0
    # 平台观测，不能冒充教务权威数据
    assert observation.data_quality == "partial"


def test_knowledge_mastery_observation_is_unavailable_without_graph():
    db = _make_db()
    _add_user(db)
    result = _projection_service(db).project_academic("user1", as_of=_now())
    observation = next(
        snapshot for snapshot in result.snapshots
        if snapshot.state_type == "knowledge_mastery_observation"
    )
    assert observation.value["knowledge_point_count"] == 0
    assert observation.value["own_mastery_rate"] is None
    assert observation.value["mastery_gap_vs_class"] is None
    assert observation.data_quality == "unavailable"
    assert "knowledge_graph_unavailable" in observation.value["warning_codes"]
