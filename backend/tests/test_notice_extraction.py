"""通知抽取测试 — 覆盖 15+ 条真实通知与边界情况。"""
from __future__ import annotations

import pytest

# ===== 正常通知 — 各类场景 =====

SCHOLARSHIP_NOTICE = (
    "通知：请2024级信息工程学院本科生于7月30日前，"
    "登录学生事务系统提交奖学金申请表，附个人陈述和成绩单，"
    "逾期不予受理。来源：信息工程学院学生工作办公室。"
)

COMPREHENSIVE_EVALUATION_NOTICE = (
    "关于开展2024-2025学年综合测评工作的通知：请各班级于9月15日前汇总"
    "综合测评材料，包括成绩单、思想品德评议表、社会实践证明、"
    "创新创业材料等，纸质版交学院办公室，电子版发送至教务办公室邮箱。"
)

PRACTICE_NOTICE = (
    "请2024级学生于7月30日前填写实践申请表，并将申请表和证明材料提交至学院办公室。"
)

COURSE_ADD_DROP_NOTICE = (
    "选课通知：通识选修课补退选在每学期第8周开放，通过教务系统操作，"
    "每门课容量有限先到先得，截止时间为第8周周五17:00。"
)

EXAM_ARRANGEMENT_NOTICE = (
    "考试安排：本学期期末考试将于6月15日开始，请2023级和2024级同学携带"
    "学生证和身份证提前15分钟到达指定考场，具体座位号见教务系统。"
)

MATERIAL_SUBMISSION_NOTICE = (
    "材料提交通知：请2022级毕业生于5月20日前提交毕业论文开题报告、"
    "指导教师推荐意见表、开题论证记录表至学院教务办公室，"
    "电子版上传到论文管理系统。"
)

ACTIVITY_REGISTRATION_NOTICE = (
    "活动报名：第十届校园文化艺术节报名正式启动，请各班级同学于4月10日前"
    "在校园活动平台完成报名，可参加歌唱、舞蹈、戏剧、朗诵等项目，"
    "每场限 50 人。"
)

DORM_NOTICE = (
    "宿舍事务通知：请各宿舍楼栋同学于本周五前完成宿舍安全自查，"
    "重点检查用电安全与消防通道畅通，宿管员将逐间核查。"
)


# ===== 边界情况 =====

MISSING_YEAR_NOTICE = (
    "请2024级同学于7月30日前提交实习鉴定表至辅导员办公室。"
    # 没有"年"，只有月日
)

MISSING_DEADLINE_NOTICE = (
    "关于做好本学期学生工作的提醒：请同学们认真参加各类实践活动，"
    "积极参与综合测评，并主动联系辅导员了解奖学金申请条件。"
)

MULTIPLE_MATERIALS_NOTICE = (
    "奖学金申请材料清单：请准备申请表、个人陈述、成绩单、"
    "获奖证书复印件、家庭经济情况说明、推荐信等材料，"
    "提交至学生事务中心，截止时间为 9 月 30 日。"
)

MULTIPLE_AUDIENCE_NOTICE = (
    "通知：请2022级、2023级、2024级全体本科生分别于5月10日、5月15日、5月20日"
    "前到所在学院办公室领取学生证注册章，逾期未领取者需到教务处补办。"
)

NON_NOTICE_TEXT = "今天天气真好，我们一起去吃饭吧。"

EMPTY_TEXT = ""

LONG_TEXT = "请同学于7月30日前提交申请表。" + "测试" * 3000  # 超过 5000 字


# ===== 测试用例 =====


def test_extract_scholarship(app_client):
    resp = app_client.post("/api/v1/notices/extract", json={"content": SCHOLARSHIP_NOTICE})
    assert resp.status_code == 200
    body = resp.json()
    assert body["source_text"] == SCHOLARSHIP_NOTICE
    assert "奖学金" in body["task"] or "奖学金" in body["title"]
    assert body["target_students"] is not None  # 2024级
    assert body["deadline"] is not None
    assert any("申请表" in m["name"] for m in body["materials"])
    assert body["importance"] in ("urgent", "important")  # 含"逾期不予受理"
    assert body["extractor_mode"] in ("rules", "llm")
    assert 0.0 <= body["confidence"] <= 1.0


def test_extract_practice(app_client):
    resp = app_client.post("/api/v1/notices/extract", json={"content": PRACTICE_NOTICE})
    assert resp.status_code == 200
    body = resp.json()
    assert "实践" in body["task"]
    assert body["target_students"] is not None
    assert body["deadline"] is not None
    material_names = [m["name"] for m in body["materials"]]
    assert "申请表" in material_names
    assert "证明材料" in material_names
    assert body["location"] is not None  # 学院办公室


def test_extract_comprehensive_evaluation(app_client):
    resp = app_client.post(
        "/api/v1/notices/extract", json={"content": COMPREHENSIVE_EVALUATION_NOTICE}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "综合测评" in body["task"]
    assert body["deadline"] is not None
    # 多个材料
    assert len(body["materials"]) >= 3
    assert body["importance"] == "important"  # 含"汇总"


def test_extract_course_add_drop(app_client):
    resp = app_client.post("/api/v1/notices/extract", json={"content": COURSE_ADD_DROP_NOTICE})
    assert resp.status_code == 200
    body = resp.json()
    assert "选课" in body["task"] or "补退选" in body["task"]
    assert body["deadline"] is not None


def test_extract_exam_arrangement(app_client):
    resp = app_client.post(
        "/api/v1/notices/extract", json={"content": EXAM_ARRANGEMENT_NOTICE}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["task"]  # 应有任务名
    # 多个面向对象
    assert body["target_students"] is not None or body["needs_confirmation"]


def test_extract_material_submission(app_client):
    resp = app_client.post(
        "/api/v1/notices/extract", json={"content": MATERIAL_SUBMISSION_NOTICE}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["materials"]) >= 2  # 多个材料
    assert body["submission_method"] is not None
    assert body["deadline"] is not None


def test_extract_activity_registration(app_client):
    resp = app_client.post(
        "/api/v1/notices/extract", json={"content": ACTIVITY_REGISTRATION_NOTICE}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "活动" in body["task"] or "报名" in body["task"]


def test_extract_dorm_affairs(app_client):
    resp = app_client.post("/api/v1/notices/extract", json={"content": DORM_NOTICE})
    assert resp.status_code == 200
    body = resp.json()
    assert body["task"]


def test_extract_missing_year_marks_confirmation(app_client):
    """年份缺失时必须标记 needs_confirmation 并给出 warnings。"""
    resp = app_client.post(
        "/api/v1/notices/extract", json={"content": MISSING_YEAR_NOTICE}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["deadline"] is not None
    assert body["needs_confirmation"] is True
    assert any("年份" in w for w in body["warnings"])


def test_extract_missing_deadline_marks_confirmation(app_client):
    """无截止时间时必须标记 needs_confirmation。"""
    resp = app_client.post(
        "/api/v1/notices/extract", json={"content": MISSING_DEADLINE_NOTICE}
    )
    assert resp.status_code == 200
    body = resp.json()
    # 没有任何"前""截止""截至"
    assert body["needs_confirmation"] is True
    assert any("截止" in w for w in body["warnings"])


def test_extract_multiple_materials(app_client):
    resp = app_client.post(
        "/api/v1/notices/extract", json={"content": MULTIPLE_MATERIALS_NOTICE}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["materials"]) >= 4  # 多种材料


def test_extract_multiple_audience(app_client):
    resp = app_client.post(
        "/api/v1/notices/extract", json={"content": MULTIPLE_AUDIENCE_NOTICE}
    )
    assert resp.status_code == 200
    body = resp.json()
    # 多年级通知，target_students 应非空或需要确认
    assert body["target_students"] is not None or body["needs_confirmation"]


def test_extract_non_notice_text(app_client):
    """非通知文本应被拒绝或标记。"""
    resp = app_client.post("/api/v1/notices/extract", json={"content": NON_NOTICE_TEXT})
    # 应返回 422 NoticeUnparseable
    assert resp.status_code == 422
    body = resp.json()
    assert body["code"] == "NOTICE_UNPARSEABLE"


def test_extract_empty_text(app_client):
    """空文本应返回 400。"""
    resp = app_client.post("/api/v1/notices/extract", json={"content": EMPTY_TEXT})
    assert resp.status_code == 400
    body = resp.json()
    assert body["code"] == "NOTICE_EMPTY"


def test_extract_too_long_text(app_client):
    """超长文本应返回 400。"""
    resp = app_client.post("/api/v1/notices/extract", json={"content": LONG_TEXT})
    assert resp.status_code == 400
    body = resp.json()
    assert body["code"] == "NOTICE_TOO_LONG"


def test_extract_with_source_name_and_published_at(app_client):
    """携带 source_name / published_at 的请求。"""
    resp = app_client.post(
        "/api/v1/notices/extract",
        json={
            "content": PRACTICE_NOTICE,
            "source_name": "信息工程学院通知",
            "published_at": "2026-07-20T09:00:00+08:00",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["source_name"] == "信息工程学院通知"


def test_extract_does_not_invent_materials(app_client):
    """规则模式不得编造通知中不存在的材料。"""
    content = "请同学本周五前到办公室领取学生证。"
    resp = app_client.post("/api/v1/notices/extract", json={"content": content})
    assert resp.status_code == 200
    body = resp.json()
    # 该通知无材料，materials 应为空
    assert body["materials"] == []


# ===== 回归测试：本轮修复的边界场景 =====


def test_extract_materials_with_location_and_dedup(app_client):
    """case1: 多材料 + 地点 + 去重。

    回归 normalize_text 破坏 markdown 的副作用导致材料漏提取，
    以及长名称(社会实践申请表)被短名称(申请表)覆盖的问题。
    """
    content = (
        "请2024级计算机科学与技术专业学生于7月30日前填写社会实践申请表，"
        "并将申请表、实践计划书和指导教师确认表提交至信息楼305办公室。"
    )
    resp = app_client.post("/api/v1/notices/extract", json={"content": content})
    assert resp.status_code == 200
    body = resp.json()
    # 至少 3 个材料(申请表、实践计划书、指导教师确认表)
    assert len(body["materials"]) >= 3
    material_names = [m["name"] for m in body["materials"]]
    assert "实践计划书" in material_names
    assert "指导教师确认表" in material_names
    # 地点应被正确提取
    assert "信息楼305办公室" in (body["location"] or "")
    # 缺年份需确认
    assert body["needs_confirmation"] is True


def test_extract_deadline_not_confused_with_start_time(app_client):
    """case9: '报名开始时间' 不应被误识别为截止时间。

    回归 _NON_DEADLINE_CONTEXTS 缺少 '开始时间' 导致
    把开始日期当截止日期返回的问题。
    """
    content = (
        "关于2026年秋季学期选课的通知。"
        "报名开始时间：2026年9月1日。"
        "报名截止时间：2026年9月10日。"
        "请同学们在截止时间前完成选课。"
    )
    resp = app_client.post("/api/v1/notices/extract", json={"content": content})
    assert resp.status_code == 200
    body = resp.json()
    deadline = body["deadline"]
    assert deadline is not None
    # 截止时间必须是 9 月 10 日，不是 9 月 1 日
    assert "2026-09-10" in deadline
    assert "2026-09-01" not in deadline


def test_extract_deadline_not_confused_with_start_date_keyword(app_client):
    """case10: '申报起始时间' 不应被误识别为截止时间。

    回归 _NON_DEADLINE_CONTEXTS 缺少 '起始时间' 导致
    把起始日期当截止日期返回的问题。
    """
    content = (
        "关于开展2026年大学生创新创业训练计划项目申报的通知。"
        "申报起始时间：2026年3月1日。"
        "项目截止时间：2026年4月15日。"
        "请有意申报的同学在截止时间前提交材料。"
    )
    resp = app_client.post("/api/v1/notices/extract", json={"content": content})
    assert resp.status_code == 200
    body = resp.json()
    deadline = body["deadline"]
    assert deadline is not None
    # 截止时间必须是 4 月 15 日，不是 3 月 1 日
    assert "2026-04-15" in deadline
    assert "2026-03-01" not in deadline


def test_extract_deadline_with_chinese_colon(app_client):
    """截止时间：日期(中文冒号) 应被正确匹配。

    回归 deadline 正则不支持中文冒号 '：' 导致
    '截止时间：2026年9月10日' 不被 deadline_full 匹配的问题。
    """
    content = "通知：报名截止时间：2026年9月10日。请同学按时完成。"
    resp = app_client.post("/api/v1/notices/extract", json={"content": content})
    assert resp.status_code == 200
    body = resp.json()
    assert body["deadline"] is not None
    assert "2026-09-10" in body["deadline"]


def test_extract_class_monitor_audience(app_client):
    """case2: '各班班长' 应正确识别为面向对象，并提示需转发确认。"""
    content = "各班班长请于2026年8月3日18:00前将综合测评汇总表上传至学生工作平台。"
    resp = app_client.post("/api/v1/notices/extract", json={"content": content})
    assert resp.status_code == 200
    body = resp.json()
    # 面向对象应包含"各班班长"，不应被截断为"各班班"
    assert "各班班长" in (body["target_students"] or "")
    # 综合测评汇总表应被识别为材料
    material_names = [m["name"] for m in body["materials"]]
    assert any("综合测评汇总表" in n for n in material_names)
    # 面向班长需提示转发
    assert body["needs_confirmation"] is True
    assert any("班长" in w or "负责人" in w for w in body["warnings"])


def test_extract_relative_date_marks_confirmation(app_client):
    """case3: '本周五' 相对时间必须标记 needs_confirmation=True。"""
    content = "软件工程1班和软件工程2班学生请在本周五前完成问卷。"
    resp = app_client.post("/api/v1/notices/extract", json={"content": content})
    assert resp.status_code == 200
    body = resp.json()
    assert body["deadline"] is not None
    assert body["needs_confirmation"] is True
    assert any("本周五" in w or "相对" in w for w in body["warnings"])


def test_extract_meeting_time_not_treated_as_deadline(app_client):
    """case8: '会议时间' 不应被误识别为截止时间。

    回归 _NON_DEADLINE_CONTEXTS 缺少 '会议时间' 的问题。
    """
    content = (
        "关于举办2026年暑期社会实践动员会的通知。"
        "请各学院于2026年7月15日前将参会名单报送至校团委，"
        "会议时间为2026年7月20日下午2点，地点为行政楼301会议室。"
    )
    resp = app_client.post("/api/v1/notices/extract", json={"content": content})
    assert resp.status_code == 200
    body = resp.json()
    deadline = body["deadline"]
    assert deadline is not None
    # 截止时间应为 7 月 15 日(名单报送)，不是 7 月 20 日(会议时间)
    assert "2026-07-15" in deadline
    assert "2026-07-20" not in deadline
    # 地点应被提取
    assert "行政楼301会议室" in (body["location"] or "")
