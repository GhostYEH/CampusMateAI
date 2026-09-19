"""Schemas for the managed OpenMAIC fusion boundary."""

from __future__ import annotations

from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class FusionState(str, Enum):
    """受管服务的单一状态判据（客户端只需 switch 这一个字段）。

    - ``disabled``：融合开关关闭，网关**不会**尝试调用受管服务。
    - ``unavailable``：开关开启，但受管服务不可达/未配置/拒绝我们的断言。
    - ``degraded``：受管服务在线，但自身依赖（数据库等）未就绪。
    - ``ready``：受管服务与依赖都就绪，``capabilities`` 可信。
    """

    DISABLED = "disabled"
    UNAVAILABLE = "unavailable"
    DEGRADED = "degraded"
    READY = "ready"


class FusionStatus(BaseModel):
    """网关对受管 OpenMAIC 服务的公开状态。

    ``state`` 是唯一判据；``enabled`` / ``available`` 保留为便捷布尔量，
    供只关心"能不能用"的旧客户端使用。``capabilities`` 只在 ``state=ready``
    时非空 —— 依赖没就绪时不得声称任何能力可用。
    """

    enabled: bool
    available: bool
    state: FusionState
    capabilities: List[str] = Field(default_factory=list)
    reason: str


class FusionRecentItem(BaseModel):
    """一条"最近学习内容"，已按服务端权限过滤。

    ``href`` 是 **CampusMate 站内**深链（不是 OpenMAIC 地址），学生点击后
    回到课程详情的智能辅导栏目；``classroom_url`` 才是可选的外部课堂地址，
    且仅在公开 Origin 已配置时才下发。
    """

    kind: Literal["classroom"]
    id: str
    course_id: str
    course_name: str
    title: str
    mode: Optional[str] = None
    status: str
    scenes_count: Optional[int] = None
    href: str
    classroom_url: Optional[str] = None
    classroom_url_unavailable_reason: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""


class FusionRecentOut(BaseModel):
    items: List[FusionRecentItem] = Field(default_factory=list)
    limit: int
    has_more: bool = False


# ===== workspace / stage =====


class WorkspaceOut(BaseModel):
    """一个学习工作台。

    `revision` 是并发控制的唯一凭据：客户端读到的值必须原样回传，否则写入被拒。
    `course_id` 由服务端回填，客户端**不能**在请求体里指定归属。
    `folder_id` 为 `None` 表示未归档（等同于没有文件夹功能之前的行为）。
    """

    id: str
    course_id: str
    name: str
    description: str = ""
    folder_id: Optional[str] = None
    revision: int
    created_at: str = ""
    updated_at: str = ""


class WorkspaceListOut(BaseModel):
    items: List[WorkspaceOut] = Field(default_factory=list)
    # 不透明游标；只在归属过滤内收窄，客户端不需要理解其内容。
    next_cursor: Optional[str] = None


class StageSummaryOut(BaseModel):
    """列表里的 stage。**不含 document**：列表是导航面，打开时才取全文。"""

    id: str
    workspace_id: str
    course_id: str
    title: str
    revision: int
    dsl_version: str = ""
    created_at: str = ""
    updated_at: str = ""


class StageOut(StageSummaryOut):
    """单个 stage，带完整 DSL 文档。"""

    document: dict = Field(default_factory=dict)


class StageListOut(BaseModel):
    items: List[StageSummaryOut] = Field(default_factory=list)
    next_cursor: Optional[str] = None


class WorkspaceCreateIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: str = Field("", max_length=4000)
    # 省略表示不归档；显式 null 与省略在服务端同义。
    folder_id: Optional[str] = Field(None, min_length=1, max_length=120)


class WorkspaceUpdateIn(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    description: Optional[str] = Field(None, max_length=4000)
    # 只有显式提供时才改变归档位置；`model_fields_set` 用来区分"未传"与"传了 null"。
    folder_id: Optional[str] = Field(None, min_length=1, max_length=120)


class StageCreateIn(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    # 省略表示"一个只有标题的空 stage"；提供时必须能通过 DSL 写入路径。
    document: Optional[dict] = None


class StageReplaceIn(BaseModel):
    document: dict
    title: Optional[str] = Field(None, min_length=1, max_length=200)


# ===== folders / search =====


class FolderOut(BaseModel):
    """一个用户可见的文件夹。

    与 workspace 一样，`revision` 是并发控制的唯一凭据；`parent_id` 为 `None`
    表示位于根层。`workspace_count` 只统计调用者自己、仍然存活的工作台。
    """

    id: str
    course_id: str
    parent_id: Optional[str] = None
    name: str
    revision: int
    created_at: str = ""
    updated_at: str = ""
    workspace_count: Optional[int] = None


class FolderListOut(BaseModel):
    items: List[FolderOut] = Field(default_factory=list)
    next_cursor: Optional[str] = None


class FolderCreateIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    parent_id: Optional[str] = Field(None, min_length=1, max_length=120)


class FolderUpdateIn(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    # 显式 null 表示"移动到根层"，与"未提供该字段"不同。
    parent_id: Optional[str] = Field(None, min_length=1, max_length=120)


class SearchHitOut(BaseModel):
    """一条搜索命中。

    `path` 是 CampusMate 站内深链，服务端生成，客户端不得自行拼接。
    """

    kind: Literal["workspace", "stage"]
    workspace_id: str
    stage_id: Optional[str] = None
    title: str
    snippet: str = ""
    folder_id: Optional[str] = None
    updated_at: str = ""
    path: str


class SearchListOut(BaseModel):
    items: List[SearchHitOut] = Field(default_factory=list)
    next_cursor: Optional[str] = None
    query: str


# ===== editor =====


class StageCommandsIn(BaseModel):
    """编辑器提交的**命令列表**，不是整份文档。

    整份 PUT 会让没看到并发修改的作者静默回退别人的改动；命令列表由服务端
    作用在它刚读到的行上。上限与服务端的 `maxCommandsPerRequest` 保持一致，
    这样超限在网关就得到 400，而不是变成一次昂贵的内部调用。
    """

    commands: List[dict] = Field(..., min_length=1, max_length=50)


class SceneOutlineOut(BaseModel):
    """场景目录项：**不含场景正文**（列表是导航面）。"""

    id: str
    type: str
    title: str
    order: int
    actions: int = 0
    updated_at: Optional[int] = None


class StageOutlineOut(BaseModel):
    stage_id: str
    workspace_id: str
    title: str
    revision: int
    dsl_version: str = ""
    scenes: List[SceneOutlineOut] = Field(default_factory=list)


class StageCommandResultOut(StageOut):
    """命令应用后的 stage，附带本次实际应用了多少条命令。"""

    applied_commands: int = 0
    migrated: bool = False


__all__ = [
    "FusionState",
    "FusionStatus",
    "FusionRecentItem",
    "FusionRecentOut",
    "WorkspaceOut",
    "WorkspaceListOut",
    "StageSummaryOut",
    "StageOut",
    "StageListOut",
    "WorkspaceCreateIn",
    "WorkspaceUpdateIn",
    "StageCreateIn",
    "StageReplaceIn",
    "FolderOut",
    "FolderListOut",
    "FolderCreateIn",
    "FolderUpdateIn",
    "SearchHitOut",
    "SearchListOut",
    "StageCommandsIn",
    "SceneOutlineOut",
    "StageOutlineOut",
    "StageCommandResultOut",
]
