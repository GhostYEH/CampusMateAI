"""CampusMate-LM 的唯一业务接线点：影子观测 + 只读金丝雀展示。

存在的理由
----------
`ModelShadowRunner` 与 `LearnerControlService.canary_gate` 此前都只有测试调用方，
没有真实业务入口：能力被注册了却从不被生产流量触发，金丝雀门禁只能"查询"，
候选结果无法进入任何生产响应。本模块补上这两条接线，且**不新建任何平行模型系统**：
它复用同一个 `ModelCapabilityRegistry`、同一个 `ModelShadowRunner` 实例
（同一套熔断器/并发闸门/采样器），只是在正确的业务点上调用它们。

两条路径的语义边界
------------------
* **影子观测**（`observe_plan_summary`）：候选输出只写 `model_shadow_runs/results`，
  调用方拿到 `None`。它不参与、也不影响任何正式状态、计划、任务或决策。
* **金丝雀展示**（`candidate_annotation`）：先过 7 项门禁，只有门禁全过才调用候选模型；
  结果以**只读、可识别、可降级、可追溯**的字段附加在一个真实生产响应上。

回退保证
--------
门禁未通过、模型未配置、采样未命中、熔断打开、超时、非法 JSON、策略违规
——全部路径都返回 `available=False` + 稳定 `reason`，生产响应继续使用确定性结果。
这里不存在"候选失败就报错"的分支：任何异常都被收敛成降级注解。

数据最小化
----------
送进候选模型的只有受控结构化特征（能力码、条目类型、时长桶、数据质量、证据计数、
解释码枚举）。不送源码、答案、课程正文、任务标题、用户自由文本、内部 id 或凭据。
日志只记录 capability / request_id / 异常类型，不记录模型原文或异常消息。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..core.logging import logger
from ..models.model_capability import ModelCapabilityRequest, ModelCapabilityResult

CAPABILITY_NAME = "learning_summary_v1"
CAPABILITY_VERSION = "v1"

# 只读金丝雀允许的能力白名单（与 LearnerControlService.canary_gate 保持一致）。
READ_ONLY_CANARY_CAPABILITIES = frozenset({CAPABILITY_NAME, "read_only_tool_routing_v1"})

# 数据质量 -> 置信度分桶。与 `schemas/learner_state.py` 的"质量->置信度"映射同源，
# 这里只做分桶，不引入第二套置信度定义。
_CONFIDENCE_BUCKET_BY_QUALITY = {
    "verified": "HIGH",
    "partial": "MEDIUM",
    "stale": "LOW",
    "unavailable": "NONE",
}
_ALLOWED_QUALITY = tuple(_CONFIDENCE_BUCKET_BY_QUALITY)
_MAX_CODES = 20
_MAX_EVIDENCE = 10000
_MAX_MINUTES = 1440


def _deadline_bucket(window_end: str | None, now: datetime) -> str:
    """把计划窗口结束时间压成一个有限枚举，避免把具体时刻送进模型。"""
    if not window_end:
        return "NONE"
    try:
        end = datetime.fromisoformat(str(window_end).replace("Z", "+00:00"))
    except ValueError:
        return "NONE"
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    delta_days = (end - now).total_seconds() / 86400.0
    if delta_days < 0:
        return "OVERDUE"
    if delta_days < 1:
        return "TODAY"
    if delta_days <= 7:
        return "THIS_WEEK"
    return "LATER"


def _top_item(plan: Any) -> Any | None:
    """确定性选出"最值得解释"的条目：优先级最高，同分按 item_id 稳定排序。"""
    items = list(getattr(plan, "items", None) or [])
    if not items:
        return None
    return sorted(
        items,
        key=lambda item: (-float(getattr(item, "priority_score", 0.0) or 0.0), str(getattr(item, "item_id", ""))),
    )[0]


class ModelAssistService:
    """候选模型的业务接线服务；只读、可降级、绝不写业务表。"""

    def __init__(
        self,
        *,
        registry: Any,
        runner: Any,
        control_service: Any,
        settings: Any = None,
    ) -> None:
        self._registry = registry
        self._runner = runner
        self._control = control_service
        self._settings = settings

    # ------------------------------------------------------------ 输入构造

    def build_summary_request(self, *, user_id: str, plan: Any, summary: dict[str, Any]) -> ModelCapabilityRequest | None:
        """从**确定性**计划与摘要派生出受控结构化输入；无法派生时返回 None。

        返回 None 不是错误：调用方据此把注解降级为不可用，生产响应不受影响。
        """
        top = _top_item(plan)
        if top is None:
            return None
        run = getattr(plan, "run", None)
        quality = getattr(run, "core_quality", None)
        if quality not in _ALLOWED_QUALITY:
            quality = "unavailable"

        codes = set()
        for item in getattr(plan, "items", None) or []:
            for code in getattr(item, "explanation_codes", None) or []:
                codes.add(str(code))
        # 计划级 warning code 也是"这条计划为什么长这样"的真实证据，一并作为可依据的解释码。
        for code in summary.get("warning_codes") or []:
            codes.add(str(code))
        explanation_codes = sorted(codes)[:_MAX_CODES]

        evidence_count = 0
        for item in getattr(plan, "items", None) or []:
            evidence_count += len(getattr(item, "evidence", None) or [])

        try:
            payload = {
                "plan_id": str(plan.plan_id),
                "warning_codes": [str(code) for code in (summary.get("warning_codes") or [])][:_MAX_CODES],
                "explanation_codes": explanation_codes,
                "item_type": str(getattr(top, "item_type", "") or "REVIEW_AND_REFLECT"),
                "estimated_minutes": max(1, min(_MAX_MINUTES, int(getattr(top, "estimated_minutes", 0) or 0) or 1)),
                "data_quality": quality,
                "evidence_count": max(0, min(_MAX_EVIDENCE, evidence_count)),
                "deadline_bucket": _deadline_bucket(getattr(run, "window_end", None), datetime.now(timezone.utc)),
                "state_band": str(summary.get("stage") or "")[:64] or None,
                "confidence_bucket": _CONFIDENCE_BUCKET_BY_QUALITY[quality],
            }
        except (TypeError, ValueError, AttributeError):
            return None

        digest = self._registry.digest(payload)[:16]
        return ModelCapabilityRequest(
            capability_name=CAPABILITY_NAME,
            capability_version=CAPABILITY_VERSION,
            subject_user_id=user_id,
            input_payload=payload,
            # 同一个计划 + 同一份输入 = 同一条影子记录，重复查看不会让影子表膨胀。
            request_id=f"plan-summary:{plan.plan_id}:{digest}"[:128],
            id_mode=True,
        )

    # ------------------------------------------------------------ 影子观测

    async def observe_plan_summary(self, *, user_id: str, plan: Any, summary: dict[str, Any]) -> None:
        """把一次真实生产输入送进影子评测；结果只落影子表，永不回传。"""
        request = self.build_summary_request(user_id=user_id, plan=plan, summary=summary)
        if request is None:
            return
        try:
            await self._runner.run(request)
        except Exception:  # noqa: BLE001 - 影子观测永远不能影响业务请求
            logger.warning(
                "model_shadow_observation_failed capability={} request_id={} exception_type={}",
                CAPABILITY_NAME, request.request_id, "observation_error",
            )

    # ------------------------------------------------------------ 金丝雀展示

    async def candidate_annotation(self, *, user_id: str, plan: Any, summary: dict[str, Any]) -> dict[str, Any]:
        """门禁通过的只读候选注解；任何不满足条件的情形都返回可降级的不可用注解。"""
        request = self.build_summary_request(user_id=user_id, plan=plan, summary=summary)
        if request is None:
            return self._unavailable("no_eligible_feature_input")

        gate = self._control.canary_gate(capability_name=CAPABILITY_NAME, user_id=user_id)
        if not gate.get("allowed"):
            return self._unavailable(str(gate.get("reason") or "canary_gate_rejected"))

        try:
            result = await self._runner.run(request, sample_rate=self._canary_sample_rate())
        except Exception:  # noqa: BLE001 - 候选调用失败必须回退到确定性结果
            logger.warning(
                "model_canary_invocation_failed capability={} request_id={} exception_type={}",
                CAPABILITY_NAME, request.request_id, "invocation_error",
            )
            return self._unavailable("candidate_invocation_failed")

        if result.inference_source != "REAL_MODEL" or result.used_fallback:
            # 超时 / 非法 JSON / 策略违规 / 熔断 / 采样未命中：生产响应继续用确定性结果。
            return self._unavailable(
                str(result.failure_code or "candidate_result_unavailable"),
                capability_version=result.capability_version,
                model_key=result.model_key,
                model_version=result.model_version,
                prompt_version=result.prompt_version,
                input_digest=result.input_digest,
                shadow_run_id=result.shadow_run_id,
                used_fallback=True,
            )

        return self._available(result)

    def _canary_sample_rate(self) -> float:
        settings = self._settings
        rate = getattr(settings, "campusmate_lm_canary_sample_rate", 1.0)
        try:
            return max(0.0, min(1.0, float(rate)))
        except (TypeError, ValueError):
            return 0.0

    def _available(self, result: ModelCapabilityResult) -> dict[str, Any]:
        payload = result.output_payload or {}
        return {
            "available": True,
            "capability_name": result.capability_name,
            "capability_version": result.capability_version,
            "reason": None,
            "inference_source": result.inference_source,
            "model_key": result.model_key,
            "model_version": result.model_version,
            "prompt_version": result.prompt_version,
            "input_digest": result.input_digest,
            "shadow_run_id": result.shadow_run_id,
            "used_fallback": False,
            "claim_codes": [str(code) for code in (payload.get("claim_codes") or [])],
            "summary": payload.get("summary"),
            "read_only": True,
            "affects_production": False,
        }

    def _unavailable(
        self,
        reason: str,
        *,
        capability_version: str = CAPABILITY_VERSION,
        model_key: str | None = None,
        model_version: str | None = None,
        prompt_version: str | None = None,
        input_digest: str | None = None,
        shadow_run_id: str | None = None,
        used_fallback: bool = False,
    ) -> dict[str, Any]:
        return {
            "available": False,
            "capability_name": CAPABILITY_NAME,
            "capability_version": capability_version,
            "reason": reason,
            "inference_source": "DETERMINISTIC_FALLBACK",
            "model_key": model_key,
            "model_version": model_version,
            "prompt_version": prompt_version,
            "input_digest": input_digest,
            "shadow_run_id": shadow_run_id,
            "used_fallback": used_fallback,
            "claim_codes": [],
            "summary": None,
            "read_only": True,
            "affects_production": False,
        }


__all__ = ["ModelAssistService", "CAPABILITY_NAME", "READ_ONLY_CANARY_CAPABILITIES"]
