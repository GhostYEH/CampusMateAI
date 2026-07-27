"""任务拆解服务 — 将一个学习目标拆解为结构化步骤。

设计要点:
1. 输入: task_id(个人待办 PersonalTask ID) 或自由文本 goal,可同时提供。
   - task_id 解析成功且属于当前用户 → 使用其 title/description/deadline/materials
     /submission_method/source_text 作为上下文。
   - task_id 解析失败或不属于当前用户 → 以 goal 为准,记录 warning。
   - 严格区分: task_id 只解析个人待办,不接受教师 Assignment ID。
     未来若需要拆解教师作业,应增加独立 assignment_id 字段。
2. 输出: 结构化步骤列表,每步含 step_number/title/description/estimated_minutes/
   dependencies/completion_criteria。
3. 校园政策相关步骤(申请/截止/材料/办理/学时/奖学金/实践等关键词)必须依赖知识库。
   普通学习步骤可由 LLM 生成(若可用)。
4. 无 LLM 时启用规则化降级拆解,响应中 mode 标注为 rule_fallback。
5. LLM 生成失败/解析失败也降级为 rule_fallback,并记录 warning。
6. 不输出心理诊断相关内容。

模式标注:
- llm: LLM 可用且成功生成
- rule_fallback: 无 LLM 或 LLM 失败,使用规则模板

科学边界:
- 拆解步骤只涉及"可观察的学习/事务动作",不包含情绪判断或心理状态推断。
- 政策步骤严格引用知识库,不编造截止时间/地点/材料。
"""
from __future__ import annotations

import json
import re
from typing import Any, List, Optional, Tuple

from ..core.config import Settings
from ..core.exceptions import ValidationFailed
from ..core.logging import logger
from ..models.multi_role import UserRow
from ..repositories.personal_task_repository import PersonalTaskRepository
from ..schemas.study import (
    TaskBreakdownRequest,
    TaskBreakdownResponse,
    TaskBreakdownStep,
)
from .llm.base import LLMClient, LLMError, LLMTimeoutError
from .retrieval_service import RetrievalService


# ===== 政策关键词(用于判断是否需要检索知识库) =====
# 命中任一关键词的步骤被视为政策相关步骤,必须依赖知识库
POLICY_KEYWORDS: Tuple[str, ...] = (
    "申请",
    "截止",
    "截止时间",
    "办理",
    "材料",
    "证明",
    "学时",
    "奖学金",
    "助学金",
    "贷款",
    "补办",
    "注册",
    "报到",
    "选课",
    "退课",
    "请假",
    "休学",
    "复学",
    "转专业",
    "保研",
    "考研",
    "推免",
    "实习",
    "实践",
    "社会实践",
    "综合测评",
    "综测",
    "学分",
    "选课",
    "补考",
    "重修",
    "毕业",
    "学位",
    "论文",
    "答辩",
    "校园卡",
    "宿舍",
    "住宿",
    "学籍",
    "档案",
    "户口",
    "体检",
    "保险",
)

# 学习类目标关键词(用于规则化拆解判断)
STUDY_KEYWORDS: Tuple[str, ...] = (
    "复习",
    "预习",
    "学习",
    "做作业",
    "完成作业",
    "刷题",
    "练习",
    "阅读",
    "看",
    "整理",
    "背诵",
    "记忆",
    "理解",
    "掌握",
    "总结",
    "写",
    "编程",
    "编码",
    "实现",
    "调试",
    "测试",
    "论文",
    "报告",
    "实验",
    "项目",
    "课程",
)


def _contains_any(text: str, keywords: Tuple[str, ...]) -> bool:
    if not text:
        return False
    return any(kw in text for kw in keywords)


def _detect_policy_intent(goal: str) -> bool:
    """判断目标是否涉及校园政策(需要知识库支撑)。"""
    return _contains_any(goal, POLICY_KEYWORDS)


def _detect_study_intent(goal: str) -> bool:
    """判断目标是否为普通学习任务。"""
    return _contains_any(goal, STUDY_KEYWORDS)


class TaskBreakdownService:
    """任务拆解服务。"""

    def __init__(
        self,
        *,
        personal_task_repo: PersonalTaskRepository,
        retrieval: RetrievalService,
        llm: Optional[LLMClient],
        settings: Settings,
    ) -> None:
        self._personal_task_repo = personal_task_repo
        self._retrieval = retrieval
        self._llm = llm
        self._settings = settings

    # ===== 公共入口 =====

    def breakdown(
        self,
        req: TaskBreakdownRequest,
        *,
        user: UserRow,
    ) -> TaskBreakdownResponse:
        """主入口: 解析任务/目标 → 检索政策知识 → 生成步骤 → 标注 mode。

        Args:
            req: 拆解请求(task_id 或 goal)。
            user: 当前登录用户(用于权限校验与上下文)。

        Raises:
            ValidationFailed: task_id 与 goal 同时为空。
        """
        if not req.task_id and not req.goal:
            raise ValidationFailed("task_id 与 goal 不能同时为空")

        warnings: List[str] = []
        related_task_title: Optional[str] = None
        related_task_id: Optional[str] = None
        goal_text = req.goal or ""

        # 1. 解析 task_id(只解析 PersonalTask,不接受 Assignment ID)
        if req.task_id:
            task_ctx, task_warn = self._resolve_task(req.task_id, user=user)
            if task_ctx is not None:
                related_task_id = req.task_id
                related_task_title = task_ctx["title"]
                # 若用户未提供 goal,使用任务标题作为 goal
                if not goal_text:
                    goal_text = task_ctx["title"]
                # 任务上下文增强:描述/材料/提交方式/原文
                ctx_parts: List[str] = []
                if task_ctx["description"]:
                    ctx_parts.append(f"任务说明: {task_ctx['description']}")
                if task_ctx.get("materials"):
                    ctx_parts.append(
                        f"所需材料: {', '.join(task_ctx['materials'])}"
                    )
                if task_ctx.get("submission_method"):
                    ctx_parts.append(
                        f"提交方式: {task_ctx['submission_method']}"
                    )
                if task_ctx.get("deadline"):
                    ctx_parts.append(f"截止时间: {task_ctx['deadline']}")
                if task_ctx.get("source_text"):
                    # 原文截断,避免上下文过长
                    src = task_ctx["source_text"][:400]
                    ctx_parts.append(f"通知原文(节选): {src}")
                if ctx_parts:
                    goal_text = f"{goal_text}\n" + "\n".join(ctx_parts)
            else:
                warnings.extend(task_warn)
                if not goal_text:
                    # task_id 解析失败且无 goal
                    raise ValidationFailed(
                        "无法解析指定的任务 ID,且未提供 goal"
                    )

        goal_text = goal_text.strip()
        if not goal_text:
            raise ValidationFailed("goal 不能为空")

        # 2. 检索政策相关资料(若涉及政策)
        policy_kb = self._retrieve_policy_knowledge(goal_text, warnings=warnings)

        # 3. 生成步骤(LLM 优先,失败降级规则)
        steps: List[TaskBreakdownStep]
        mode: str
        if self._llm is not None and self._llm.available:
            try:
                steps, llm_warn = self._build_llm_steps(
                    goal_text, policy_kb=policy_kb, user=user
                )
                mode = "llm"
                warnings.extend(llm_warn)
            except (LLMError, LLMTimeoutError) as e:
                logger.warning(
                    "task_breakdown.llm_failed fallback=rule error=%s", e
                )
                warnings.append(
                    f"LLM 调用失败({type(e).__name__}),已降级为规则拆解"
                )
                steps = self._build_rule_steps(
                    goal_text, policy_kb=policy_kb
                )
                mode = "rule_fallback"
        else:
            warnings.append("未配置 LLM 或 LLM 不可用,使用规则拆解")
            steps = self._build_rule_steps(goal_text, policy_kb=policy_kb)
            mode = "rule_fallback"

        # 4. 后处理: 步骤编号、依赖去重、政策步骤标注来源
        steps = self._normalize_steps(steps)

        return TaskBreakdownResponse(
            mode=mode,
            steps=steps,
            goal=goal_text,
            related_task_id=related_task_id,
            related_task_title=related_task_title,
            warnings=warnings,
        )

    # ===== 任务解析 =====

    def _resolve_task(
        self,
        task_id: str,
        *,
        user: UserRow,
    ) -> Tuple[Optional[dict], List[str]]:
        """解析个人待办 ID,返回任务上下文或 None。

        严格区分实体类型:
        - task_id 只解析 PersonalTask(用户私人待办),不接受教师 Assignment ID。
        - PersonalTaskRepository.get_task 已强制按 user_id 过滤,跨用户访问返回 None。
        - 已软删除的任务(status='deleted')视为不可用,记录 warning。
        - 教师 Assignment ID 在 personal_tasks 表中查不到,自然返回 None + warning。

        返回的上下文字段(供拆解使用):
        - title
        - description
        - deadline
        - materials (List[str])
        - submission_method
        - source_text (原通知文本,可追溯)
        """
        warnings: List[str] = []
        task = self._personal_task_repo.get_task(task_id, user_id=user.id)
        if task is None:
            warnings.append(f"任务 {task_id} 不存在或不属于当前用户,改用 goal 拆解")
            return None, warnings
        if task.status == "deleted":
            warnings.append(f"任务 {task_id} 已删除,改用 goal 拆解")
            return None, warnings
        # 解析 materials(JSON 字符串 → list)
        materials: List[str] = []
        if task.materials:
            try:
                parsed = json.loads(task.materials)
                if isinstance(parsed, list):
                    materials = [str(x) for x in parsed]
            except (ValueError, TypeError):
                pass
        return (
            {
                "title": task.title or "",
                "description": task.description or "",
                "deadline": task.deadline,
                "materials": materials,
                "submission_method": task.submission_method,
                "source_text": task.source_text,
            },
            warnings,
        )

    # ===== 知识库检索 =====

    def _retrieve_policy_knowledge(
        self,
        goal: str,
        *,
        warnings: List[str],
    ) -> List[dict]:
        """检索与目标相关的政策资料,用于支撑政策步骤。

        返回 [{title, section, content, document_id}, ...] 列表。
        若目标不涉及政策关键词,返回空列表。
        若知识库为空或检索失败,记录 warning 并返回空列表。
        """
        if not _detect_policy_intent(goal):
            return []
        if not self._retrieval.is_ready:
            warnings.append(
                "目标涉及校园政策但知识库未就绪,政策步骤可能缺少权威依据"
            )
            return []
        try:
            results = self._retrieval.search(goal, k=5)
        except Exception as e:  # noqa: BLE001
            warnings.append(
                f"知识库检索失败({type(e).__name__}),政策步骤可能缺少权威依据"
            )
            return []
        kb_items: List[dict] = []
        for rc in results:
            doc = rc.document
            if doc is None:
                continue
            kb_items.append(
                {
                    "document_id": doc.document_id,
                    "title": doc.title,
                    "section": rc.chunk.section,
                    "content": rc.chunk.content,
                }
            )
        if not kb_items:
            warnings.append(
                "目标涉及校园政策但知识库未匹配到资料,政策步骤将以提示性建议为主"
            )
        return kb_items

    # ===== LLM 拆解 =====

    def _build_llm_steps(
        self,
        goal: str,
        *,
        policy_kb: List[dict],
        user: UserRow,
    ) -> Tuple[List[TaskBreakdownStep], List[str]]:
        """调用 LLM 生成结构化拆解步骤。

        策略:
        - 政策关键词步骤必须依赖知识库,LLM 仅做"整理"而非"编造"。
        - 普通学习步骤可由 LLM 自由生成。
        - 严格输出 JSON,失败则抛 LLMError(由调用方降级)。
        """
        warnings: List[str] = []
        kb_context = self._format_kb_context(policy_kb)
        has_policy = bool(policy_kb) or _detect_policy_intent(goal)

        system_prompt = (
            "你是 CampusMate AI 学习陪伴助手,负责将一个学习目标拆解为可执行的步骤。\n"
            "严格规则:\n"
            "1. 步骤必须可观察、可执行,避免模糊描述。\n"
            "2. 涉及校园政策(申请/截止/材料/办理/学时/奖学金/实践/综合测评等)的步骤,"
            "只能基于提供的'参考资料'整理,不得编造截止时间、地点、材料、金额。\n"
            "3. 若资料不足,政策步骤的 description 中明确写'建议咨询辅导员或相关负责老师',"
            "completion_criteria 写'已向辅导员或相关部门确认具体要求'。\n"
            "4. 普通学习步骤可自由生成,但 estimated_minutes 必须在 5~120 之间。\n"
            "5. 不输出任何心理诊断、情绪判断或健康相关结论。\n"
            "6. 严格输出 JSON 数组,每个元素包含字段: "
            "step_number, title, description, estimated_minutes, dependencies, "
            "completion_criteria, is_policy_step, knowledge_source。\n"
            "7. dependencies 是 step_number 列表(必须先完成的步骤)。\n"
            "8. knowledge_source 仅在 is_policy_step=true 时填写资料标题,否则为 null。\n"
            "9. 步骤数 3~8 个,按执行顺序排列。\n"
        )
        user_prompt = (
            f"学习目标:\n{goal}\n\n"
            f"参考资料(政策步骤必须基于此):\n{kb_context or '(无相关政策资料)'}\n\n"
            f"学生身份: {user.role}\n"
            f"请输出 JSON 数组。"
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        # 同步调用(LLMClient.chat 是 async,但在路由层我们用 sync 包装)
        import asyncio

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        response = loop.run_until_complete(
            self._llm.chat(  # type: ignore[union-attr]
                messages,
                temperature=0.3,
                max_tokens=1500,
                timeout=20.0,
            )
        )
        content = response.content.strip()
        steps_raw = self._parse_llm_json(content)
        if not steps_raw:
            warnings.append("LLM 输出无法解析为 JSON,降级为规则拆解")
            raise LLMError("LLM 输出无法解析为 JSON")
        steps: List[TaskBreakdownStep] = []
        for item in steps_raw:
            try:
                step = self._parse_step_item(item, has_policy=has_policy)
                steps.append(step)
            except (KeyError, ValueError, TypeError) as e:
                warnings.append(
                    f"LLM 输出第 {len(steps) + 1} 步格式不完整({e}),已跳过"
                )
                continue
        if not steps:
            warnings.append("LLM 未输出有效步骤,降级为规则拆解")
            raise LLMError("LLM 未输出有效步骤")
        return steps, warnings

    def _parse_llm_json(self, content: str) -> List[dict]:
        """从 LLM 输出中解析 JSON 数组,容错处理代码围栏与多余文本。"""
        if not content:
            return []
        # 去除 ```json ... ``` 围栏
        text = content.strip()
        if text.startswith("```"):
            # 去掉首行 ```json 或 ```
            lines = text.split("\n")
            lines = lines[1:]  # 去掉首行
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        # 尝试直接解析
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return parsed
            if isinstance(parsed, dict) and "steps" in parsed:
                steps = parsed["steps"]
                if isinstance(steps, list):
                    return steps
        except json.JSONDecodeError:
            pass
        # 兜底: 用正则提取第一个 JSON 数组
        match = re.search(r"\[\s*\{.*\}\s*\]", text, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(0))
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                pass
        return []

    def _parse_step_item(self, item: Any, *, has_policy: bool) -> TaskBreakdownStep:
        """把单个 LLM 输出的 dict 解析为 TaskBreakdownStep。"""
        if not isinstance(item, dict):
            raise TypeError("step must be a dict")
        step_number = int(item["step_number"])
        title = str(item["title"]).strip()
        description = str(item["description"]).strip()
        estimated = int(item.get("estimated_minutes", 30))
        # 钳制
        estimated = max(5, min(120, estimated))
        deps_raw = item.get("dependencies", [])
        if not isinstance(deps_raw, list):
            deps_raw = []
        deps = [int(d) for d in deps_raw if isinstance(d, (int, float)) or str(d).isdigit()]
        completion = str(item.get("completion_criteria", "")).strip()
        if not completion:
            completion = f"完成《{title}》相关动作"
        is_policy = bool(item.get("is_policy_step", False))
        knowledge_source = item.get("knowledge_source")
        if knowledge_source is not None:
            knowledge_source = str(knowledge_source).strip() or None
        # 政策步骤但没有知识来源 → 标记 warning(由调用方处理)
        return TaskBreakdownStep(
            step_number=step_number,
            title=title,
            description=description,
            estimated_minutes=estimated,
            dependencies=deps,
            completion_criteria=completion,
            is_policy_step=is_policy,
            knowledge_source=knowledge_source,
        )

    def _format_kb_context(self, kb: List[dict]) -> str:
        if not kb:
            return ""
        lines: List[str] = []
        for i, item in enumerate(kb, start=1):
            section = item.get("section") or "正文"
            lines.append(
                f"[资料 {i}] 标题: {item['title']}\n"
                f"  小节: {section}\n"
                f"  内容: {item['content'][:600]}"
            )
        return "\n".join(lines)

    # ===== 规则化降级拆解 =====

    def _build_rule_steps(
        self,
        goal: str,
        *,
        policy_kb: List[dict],
    ) -> List[TaskBreakdownStep]:
        """无 LLM 或 LLM 失败时的规则化拆解。

        生成模板步骤(理解目标 → 准备资源 → 执行 → 自测 → 整理),
        并在涉及政策时追加"咨询辅导员/查阅官方资料"步骤。
        """
        is_policy = _detect_policy_intent(goal) or bool(policy_kb)
        is_study = _detect_study_intent(goal) or not is_policy

        steps: List[TaskBreakdownStep] = []
        # 1. 理解目标
        steps.append(
            TaskBreakdownStep(
                step_number=1,
                title="明确目标与范围",
                description=(
                    f"用一句话写下本次目标: {goal[:80]}。"
                    "明确产出物(笔记/代码/报告/答案)与完成标准。"
                ),
                estimated_minutes=10,
                dependencies=[],
                completion_criteria="已写下目标与产出物描述,并能口头复述完成标准",
                is_policy_step=False,
                knowledge_source=None,
            )
        )
        # 2. 准备资源
        if is_study:
            steps.append(
                TaskBreakdownStep(
                    step_number=2,
                    title="准备学习资源",
                    description=(
                        "整理需要的教材、课件、笔记工具或代码环境,"
                        "确认网络/账号/软件就绪。"
                    ),
                    estimated_minutes=15,
                    dependencies=[1],
                    completion_criteria="所需资源已打开或下载,可立即开始学习",
                    is_policy_step=False,
                    knowledge_source=None,
                )
            )
        # 3. 政策查阅(若涉及)
        if is_policy:
            policy_desc = (
                "本目标涉及校园政策相关事项。"
            )
            if policy_kb:
                titles = "、".join(f"《{k['title']}》" for k in policy_kb[:3])
                policy_desc += f"已检索到资料: {titles}。请优先阅读上述资料中与本目标相关的小节。"
                knowledge_source = titles
                completion = "已阅读检索到的资料相关小节,记录关键截止时间/地点/材料"
            else:
                policy_desc += (
                    "知识库未匹配到相关资料,建议咨询辅导员或相关负责老师,"
                    "或查阅学校官方通知渠道(教务系统/学院公众号)。"
                )
                knowledge_source = None
                completion = "已向辅导员或相关部门确认本事项的具体要求"
            steps.append(
                TaskBreakdownStep(
                    step_number=len(steps) + 1,
                    title="查阅政策资料 / 咨询辅导员",
                    description=policy_desc,
                    estimated_minutes=20,
                    dependencies=[1],
                    completion_criteria=completion,
                    is_policy_step=True,
                    knowledge_source=knowledge_source,
                )
            )
        # 4. 主执行步骤
        if is_study:
            steps.append(
                TaskBreakdownStep(
                    step_number=len(steps) + 1,
                    title="分块执行核心任务",
                    description=(
                        "将核心任务拆成 2~3 个 25~40 分钟的小块,"
                        "每块专注单一子任务,完成一块后短暂休息。"
                    ),
                    estimated_minutes=80,
                    dependencies=[2] if is_study else [1],
                    completion_criteria="所有子任务块均已完成,产出物可见",
                    is_policy_step=False,
                    knowledge_source=None,
                )
            )
        # 5. 自测 / 检查
        steps.append(
            TaskBreakdownStep(
                step_number=len(steps) + 1,
                title="自测与查漏补缺",
                description=(
                    "用 2~3 个问题自测目标达成度,"
                    "或对照完成标准逐项检查产出物。"
                ),
                estimated_minutes=15,
                dependencies=[len(steps)],
                completion_criteria="能回答自测问题或所有检查项均已勾选",
                is_policy_step=False,
                knowledge_source=None,
            )
        )
        # 6. 整理产出
        steps.append(
            TaskBreakdownStep(
                step_number=len(steps) + 1,
                title="整理产出与归档",
                description=(
                    "把笔记/代码/报告/截图归档到对应课程或事项目录,"
                    "记录本次未完成的疑问(供下次或咨询时使用)。"
                ),
                estimated_minutes=10,
                dependencies=[len(steps)],
                completion_criteria="产出物已归档,疑问清单已记录",
                is_policy_step=False,
                knowledge_source=None,
            )
        )
        return steps

    # ===== 后处理 =====

    def _normalize_steps(
        self, steps: List[TaskBreakdownStep]
    ) -> List[TaskBreakdownStep]:
        """重新编号(1..n)、依赖去重、依赖编号合法性过滤。"""
        if not steps:
            return steps
        # 按原 step_number 排序(若乱序)
        sorted_steps = sorted(steps, key=lambda s: s.step_number)
        # 旧编号 → 新编号映射
        old_to_new: dict = {}
        for new_idx, step in enumerate(sorted_steps, start=1):
            old_to_new[step.step_number] = new_idx
        # 重建
        result: List[TaskBreakdownStep] = []
        for new_idx, step in enumerate(sorted_steps, start=1):
            # 依赖映射 + 去重 + 仅保留指向更早步骤的依赖
            new_deps: List[int] = []
            seen: set = set()
            for old_dep in step.dependencies:
                new_dep = old_to_new.get(old_dep)
                if new_dep is None or new_dep >= new_idx:
                    continue  # 丢弃指向自身/后续/不存在步骤的依赖
                if new_dep in seen:
                    continue
                seen.add(new_dep)
                new_deps.append(new_dep)
            result.append(
                step.model_copy(
                    update={
                        "step_number": new_idx,
                        "dependencies": new_deps,
                    }
                )
            )
        return result


__all__ = ["TaskBreakdownService", "POLICY_KEYWORDS"]
