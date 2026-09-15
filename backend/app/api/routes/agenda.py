"""统一"今日待办"路由 — /api/v1/agenda。

全站唯一事实源: 首页今日任务区、学习陪伴右侧今日待办、任务总览"今天"分组、
全局待办角标都读这里，避免三个页面各自组合 assignments/tasks/dashboard 后口径不一。

只读且不触网: 本接口不发起任何学习通请求，因此页面加载不会隐式触发耗时抓取。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ...models.multi_role import UserRow
from ...schemas.agenda import TodayAgendaOut
from ...services.agenda_service import TodayAgendaService
from ...services.container import ServiceContainer, get_container
from ..deps import current_user

router = APIRouter(prefix="/agenda", tags=["agenda"])


def _container() -> ServiceContainer:
    return get_container()


@router.get("/today", response_model=TodayAgendaOut)
def get_today_agenda(
    user: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(_container),
) -> TodayAgendaOut:
    """按 Asia/Shanghai 自然日聚合当前用户的今日待办。

    聚合范围: 已逾期但仍未完成的学习通作业、今天截止的学习通作业、今天进行或
    今天截止的学习通考试、今天上课的课程(仅在确实有课表数据时)、今天截止或今天
    新建的个人待办、学习陪伴与 AI 拆解产生的今日任务。
    """
    payload = TodayAgendaService(container).build(user_id=user.id)
    return TodayAgendaOut(**payload)


__all__ = ["router"]
