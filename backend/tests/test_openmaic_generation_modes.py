"""阶段 2 —— 9 种学生生成意图、受控 requirement 模板与自适应选择。

覆盖：
- 9 个规范意图 + 3 个旧值归一化（explore/practice/project），不破坏旧客户端；
- 每个意图产生**不同**的、以"学生学习任务"表达的受控模板；
- 模板不要求 OpenMAIC 输出不存在的 scene type，并显式声明最终组合由生成器决定；
- 学生输入（目标/困惑/时长/难度/更多练习）进入模板；
- adaptive 是确定性、可解释、可测试的，且 3D 不可用时不会推荐 visualization3d。

本文件全部为纯函数级测试，不触碰网络。
"""
from __future__ import annotations

import pytest

from app.services.openmaic.requirement_builder import (
    CANONICAL_MODES,
    LEGACY_MODE_ALIASES,
    AdaptiveSignals,
    StudentBrief,
    build_input_payload,
    build_requirement,
    choose_adaptive_mode,
    mode_label,
    normalize_mode,
    validate_mode,
)

# 教师备课语气词：学生侧模板里不允许出现
TEACHER_TONE_WORDS = ("备课", "教案", "授课计划", "学员", "教师工作台", "教学大纲编写")


# ===== A. 意图集合与旧值归一化 =====


def test_canonical_modes_are_the_nine_student_intents():
    assert CANONICAL_MODES == (
        "adaptive",
        "explain",
        "quiz",
        "simulation",
        "visualization",
        "mindmap",
        "coding",
        "pbl",
        "review",
    )


def test_legacy_mode_names_normalize_to_canonical_intents():
    assert LEGACY_MODE_ALIASES == {
        "explore": "simulation",
        "practice": "quiz",
        "project": "pbl",
    }
    assert normalize_mode("explore") == "simulation"
    assert normalize_mode("practice") == "quiz"
    assert normalize_mode("project") == "pbl"
    # 旧名必须仍然被接受（不能破坏已有客户端）
    assert validate_mode("practice") == "quiz"
    assert validate_mode("explore") == "simulation"
    assert validate_mode("project") == "pbl"


def test_normalize_mode_is_case_and_whitespace_insensitive():
    assert normalize_mode("  QUIZ ") == "quiz"
    assert normalize_mode("Review") == "review"
    assert normalize_mode("") == "adaptive"
    assert normalize_mode(None) == "adaptive"


def test_unknown_mode_is_rejected():
    for bogus in ("bogus-mode", "3d", "whiteboard", "tts", "discussion", "mind-map"):
        with pytest.raises(ValueError):
            normalize_mode(bogus)


def test_every_canonical_mode_has_a_label():
    for mode in CANONICAL_MODES:
        assert mode_label(mode)


# ===== B. requirement 模板 =====


def test_each_canonical_mode_produces_a_distinct_requirement():
    seen = {}
    for mode in CANONICAL_MODES:
        req = build_requirement(course_context="[课程] 高等数学", mode=mode)
        assert req not in seen.values(), f"{mode} 的模板与 {seen} 中某个重复"
        seen[mode] = req


def test_requirement_is_a_student_learning_task_not_teacher_prep():
    for mode in CANONICAL_MODES:
        req = build_requirement(course_context="[课程] 高等数学", mode=mode)
        for word in TEACHER_TONE_WORDS:
            assert word not in req, f"{mode} 模板出现教师语气词: {word}"
        assert "学生" in req


def test_requirement_states_final_composition_is_decided_by_generator():
    for mode in CANONICAL_MODES:
        req = build_requirement(course_context="[课程] 高等数学", mode=mode)
        assert "不保证包含某一种特定形式" in req, f"{mode} 缺少『不保证』声明"


def test_requirement_does_not_ask_for_nonexistent_scene_types():
    """OpenMAIC 的场景类型只有 slide/quiz/interactive/pbl。

    模板不得把 3D/思维导图/编程 之类说成"场景类型"，只能作为交互组件的意图表达。
    """
    forbidden = ("scene type", "场景类型为", "生成一个 slide 场景")
    for mode in CANONICAL_MODES:
        req = build_requirement(course_context="[课程] 高等数学", mode=mode)
        for token in forbidden:
            assert token not in req


def test_requirement_includes_all_student_inputs():
    brief = StudentBrief(
        learning_objective="搞懂导数定义",
        current_difficulty="看不懂极限的 ε-δ 语言",
        desired_duration_minutes=25,
        difficulty_level="beginner",
        wants_more_practice=True,
    )
    req = build_requirement(
        course_context="[课程] 高等数学", mode="explain", brief=brief
    )
    assert "搞懂导数定义" in req
    assert "看不懂极限的 ε-δ 语言" in req
    assert "25" in req
    assert "入门" in req
    assert "更多练习" in req


def test_requirement_defaults_to_no_student_brief_without_crashing():
    req = build_requirement(course_context="[课程] 高等数学", mode="adaptive")
    assert req
    assert "不保证包含某一种特定形式" in req


def test_difficulty_level_values_are_mapped_to_readable_labels():
    for raw, label in (("beginner", "入门"), ("standard", "标准"), ("advanced", "进阶")):
        req = build_requirement(
            course_context="c", mode="quiz", brief=StudentBrief(difficulty_level=raw)
        )
        assert label in req


def test_unknown_difficulty_level_is_ignored_not_echoed():
    req = build_requirement(
        course_context="c", mode="quiz", brief=StudentBrief(difficulty_level="hacker")
    )
    assert "hacker" not in req


def test_requirement_marks_3d_unavailable_when_switch_is_off():
    off = build_requirement(
        course_context="c", mode="visualization", external_3d_available=False
    )
    assert "3D" in off
    assert "不可用" in off
    on = build_requirement(
        course_context="c", mode="visualization", external_3d_available=True
    )
    assert "不可用" not in on


def test_requirement_states_which_optional_capabilities_are_off():
    req = build_requirement(
        course_context="c",
        mode="explain",
        enable_web_search=False,
        enable_image=False,
        enable_video=False,
        enable_tts=False,
    )
    assert "不启用" in req
    assert "不要假装调用" in req


def test_requirement_instructs_not_to_treat_output_as_official():
    req = build_requirement(course_context="c", mode="explain")
    assert "不得把生成内容当作学校官方规定或考试事实" in req


def test_requirement_keeps_legacy_assertions():
    """保持既有测试依赖的两句话（历史契约）。"""
    req = build_requirement(
        course_context="[课程] 高等数学", mode="explain", learning_objective="掌握导数定义"
    )
    assert "概念讲解与逐步推导" in req
    assert "掌握导数定义" in req
    assert "不要套用固定学科模板" in req


def test_build_input_payload_only_sends_contract_supported_fields():
    payload = build_input_payload(
        requirement="req", capabilities={"webSearch": True, "tts": False}, pdf_text="ctx"
    )
    assert set(payload) == {
        "requirement",
        "pdfContent",
        "enableWebSearch",
        "enableImageGeneration",
        "enableVideoGeneration",
        "enableTTS",
        "agentMode",
    }
    assert payload["pdfContent"] == {"text": "ctx", "images": []}
    assert payload["agentMode"] == "generate"
    assert payload["enableWebSearch"] is True
    assert payload["enableTTS"] is False


# ===== C. adaptive 决策 =====


def test_adaptive_picks_review_when_exam_soon_and_weak_points():
    mode, reason = choose_adaptive_mode(
        AdaptiveSignals(
            weak_points=(("极限的ε-δ定义", 32.0),),
            upcoming_exam_days=9,
            upcoming_exam_title="期中考试",
            has_chapters=True,
        )
    )
    assert mode == "review"
    assert "考试" in reason
    assert "极限的ε-δ定义" in reason


def test_adaptive_ignores_far_away_exam():
    mode, _ = choose_adaptive_mode(
        AdaptiveSignals(
            weak_points=(("极限", 20.0),),
            upcoming_exam_days=45,
            has_interactive_material=True,
        )
    )
    assert mode != "review"


def test_adaptive_picks_simulation_when_weak_points_and_interactive_material():
    mode, reason = choose_adaptive_mode(
        AdaptiveSignals(weak_points=(("矩阵", 40.0),), has_interactive_material=True)
    )
    assert mode == "simulation"
    assert "矩阵" in reason


def test_adaptive_picks_quiz_when_weak_points_without_interactive_material():
    mode, reason = choose_adaptive_mode(
        AdaptiveSignals(weak_points=(("矩阵", 40.0),), has_interactive_material=False)
    )
    assert mode == "quiz"
    assert reason


def test_adaptive_picks_explain_when_chapters_and_no_history():
    mode, reason = choose_adaptive_mode(
        AdaptiveSignals(has_chapters=True, used_modes=frozenset())
    )
    assert mode == "explain"
    assert reason


def test_adaptive_rotates_among_unused_intents():
    mode, _ = choose_adaptive_mode(
        AdaptiveSignals(
            has_chapters=True,
            used_modes=frozenset({"explain", "quiz"}),
        )
    )
    assert mode not in {"explain", "quiz"}
    assert mode in CANONICAL_MODES


def test_adaptive_never_picks_visualization_when_3d_unavailable():
    mode, _ = choose_adaptive_mode(
        AdaptiveSignals(
            has_chapters=True,
            used_modes=frozenset({"explain", "quiz", "mindmap", "coding"}),
            external_3d_available=False,
        )
    )
    assert mode != "visualization"
    assert mode in CANONICAL_MODES


def test_adaptive_may_pick_visualization_when_3d_available():
    mode, _ = choose_adaptive_mode(
        AdaptiveSignals(
            has_chapters=True,
            used_modes=frozenset({"explain", "quiz", "mindmap", "coding"}),
            external_3d_available=True,
        )
    )
    assert mode == "visualization"


def test_adaptive_does_not_always_return_the_same_mode():
    """反向验证：喂不同的真实信号必须得到不同的推荐，不能恒定一种。"""
    cases = [
        AdaptiveSignals(
            weak_points=(("A", 10.0),), upcoming_exam_days=5, upcoming_exam_title="期末"
        ),
        AdaptiveSignals(weak_points=(("B", 30.0),), has_interactive_material=True),
        AdaptiveSignals(weak_points=(("C", 30.0),), has_interactive_material=False),
        AdaptiveSignals(has_chapters=True, used_modes=frozenset()),
    ]
    chosen = set()
    for signals in cases:
        mode, reason = choose_adaptive_mode(signals)
        assert reason, "adaptive 必须给出可解释的理由"
        chosen.add(mode)
    assert len(chosen) >= 3, f"adaptive 过于单一: {chosen}"


def test_adaptive_reason_is_non_empty_in_every_branch():
    branches = [
        AdaptiveSignals(weak_points=(("A", 1.0),), upcoming_exam_days=1),
        AdaptiveSignals(weak_points=(("A", 1.0),), has_interactive_material=True),
        AdaptiveSignals(weak_points=(("A", 1.0),)),
        AdaptiveSignals(has_chapters=True),
        AdaptiveSignals(),
    ]
    for signals in branches:
        mode, reason = choose_adaptive_mode(signals)
        assert mode in CANONICAL_MODES
        assert reason.strip()


def test_adaptive_returns_canonical_mode_even_with_no_signals():
    mode, reason = choose_adaptive_mode(AdaptiveSignals())
    assert mode in CANONICAL_MODES
    assert reason


def test_adaptive_uses_observable_unfinished_chapters_when_no_measured_mastery():
    """学习通只提供课程级掌握率，没有逐知识点掌握率。

    因此当没有实测逐点数据时，adaptive 只能用"章节未完成"这种**可观察**事实
    作为薄弱信号，并且措辞必须诚实（不能编造掌握率数字）。
    """
    mode, reason = choose_adaptive_mode(
        AdaptiveSignals(
            weak_areas=("第3章 极限", "第4章 导数"),
            upcoming_exam_days=6,
            upcoming_exam_title="期中考试",
        )
    )
    assert mode == "review"
    assert "第3章 极限" in reason
    assert "章节" in reason
    assert "%" not in reason, "没有实测掌握率时不得在理由里出现百分比"


def test_adaptive_prefers_measured_mastery_over_chapter_proxy():
    mode, reason = choose_adaptive_mode(
        AdaptiveSignals(
            weak_points=(("极限的ε-δ定义", 32.0),),
            weak_areas=("第3章 极限",),
        )
    )
    assert mode == "quiz"
    assert "极限的ε-δ定义" in reason
    assert "章节" not in reason


def test_adaptive_ignores_empty_weak_areas_entries():
    mode, reason = choose_adaptive_mode(
        AdaptiveSignals(weak_areas=("", "   "), has_chapters=True)
    )
    assert mode in CANONICAL_MODES
    assert reason
