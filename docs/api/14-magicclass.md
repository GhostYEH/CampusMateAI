# 课程互动课堂、受管工作台与学习空间入口

> 对照日期：2026-09-30。本模块共 54 个 HTTP 方法与路径组合；以当前后端注册路由和 Web 调用为依据。

[文档导航](README.md) · [接入与流程](integration.md) · [字段字典](schemas.md) · [OpenAPI](openapi.json)

## 接口索引

| 方法 | 完整路径 | 用途 |
| --- | --- | --- |
| GET | `/api/v1/courses/{course_id}/interactive-classroom/status` | 读取状态 |
| GET | `/api/v1/courses/{course_id}/interactive-classroom/plan` | 生成**之前**给学生看的信息：课程、可选资料、推荐形态与理由 |
| POST | `/api/v1/courses/{course_id}/interactive-classroom/generate` | 生成课堂 |
| GET | `/api/v1/courses/{course_id}/interactive-classroom/jobs/{session_id}` | 读取进度 |
| GET | `/api/v1/courses/{course_id}/interactive-classroom/{session_id}/composition` | 回读这节课**真实**包含的内容（幻灯片/测验/交互/项目式学习 + widget 分布） |
| GET | `/api/v1/courses/{course_id}/interactive-classroom` | 列出课堂 |
| POST | `/api/v1/courses/{course_id}/interactive-classroom/{session_id}/retry` | 重新生成一节课堂 |
| GET | `/api/v1/magicclass/fusion/status` | 受管课堂服务状态 |
| GET | `/api/v1/magicclass/fusion/recent` | 当前用户**所有可见课程**的最近学习内容（一次请求替代按课程轮询） |
| GET | `/api/v1/courses/{course_id}/workspaces` | 列出工作台 |
| POST | `/api/v1/courses/{course_id}/workspaces` | 创建工作台 |
| GET | `/api/v1/courses/{course_id}/workspaces/{workspace_id}` | 读取工作台 |
| PATCH | `/api/v1/courses/{course_id}/workspaces/{workspace_id}` | 更新工作台 |
| DELETE | `/api/v1/courses/{course_id}/workspaces/{workspace_id}` | 删除工作台 |
| GET | `/api/v1/courses/{course_id}/workspaces/{workspace_id}/stages` | 列出舞台 |
| POST | `/api/v1/courses/{course_id}/workspaces/{workspace_id}/stages` | 创建舞台 |
| GET | `/api/v1/courses/{course_id}/workspaces/{workspace_id}/stages/{stage_id}` | 读取舞台 |
| PUT | `/api/v1/courses/{course_id}/workspaces/{workspace_id}/stages/{stage_id}` | 替换舞台 |
| DELETE | `/api/v1/courses/{course_id}/workspaces/{workspace_id}/stages/{stage_id}` | 删除舞台 |
| GET | `/api/v1/courses/{course_id}/folders` | 列出文件夹 |
| POST | `/api/v1/courses/{course_id}/folders` | 创建文件夹 |
| GET | `/api/v1/courses/{course_id}/folders/{folder_id}` | 读取文件夹 |
| PATCH | `/api/v1/courses/{course_id}/folders/{folder_id}` | 更新文件夹 |
| DELETE | `/api/v1/courses/{course_id}/folders/{folder_id}` | 删除文件夹 |
| GET | `/api/v1/courses/{course_id}/search` | 搜索课程内容 |
| POST | `/api/v1/courses/{course_id}/workspaces/{workspace_id}/stages/{stage_id}/commands` | 应用舞台编辑命令 |
| GET | `/api/v1/courses/{course_id}/workspaces/{workspace_id}/stages/{stage_id}/outline` | 读取舞台目录 |
| GET | `/api/v1/courses/{course_id}/workspaces/{workspace_id}/stages/{stage_id}/playback` | 读取舞台播放计划 |
| GET | `/api/v1/courses/{course_id}/workspaces/{workspace_id}/stages/{stage_id}/scenes/{scene_id}` | 读取舞台场景 |
| GET | `/api/v1/courses/{course_id}/materials` | 列出资料 |
| POST | `/api/v1/courses/{course_id}/materials` | 上传资料 |
| POST | `/api/v1/courses/{course_id}/materials/resolve` | 处理资料 |
| GET | `/api/v1/courses/{course_id}/materials/{material_id}` | 读取资料 |
| DELETE | `/api/v1/courses/{course_id}/materials/{material_id}` | 删除资料 |
| GET | `/api/v1/courses/{course_id}/workspaces/{workspace_id}/stages/{stage_id}/export` | 导出舞台 |
| GET | `/api/v1/courses/{course_id}/workspaces/{workspace_id}/stages/{stage_id}/export/{format}` | 导出舞台指定格式 |
| POST | `/api/v1/courses/{course_id}/workspaces/{workspace_id}/stages/{stage_id}/export/video` | 导出舞台视频 |
| POST | `/api/v1/courses/{course_id}/workspaces/{workspace_id}/import` | 导入舞台 |
| POST | `/api/v1/courses/{course_id}/workspaces/{workspace_id}/import/pptx` | 导入PPTX舞台 |
| POST | `/api/v1/courses/{course_id}/workspaces/{workspace_id}/generate` | 生成舞台 |
| POST | `/api/v1/courses/{course_id}/home-generate` | 生成home |
| GET | `/api/v1/courses/{course_id}/jobs/{job_id}` | 读取任务 |
| GET | `/api/v1/courses/{course_id}/artifacts/{artifact_id}` | 读取产物 |
| POST | `/api/v1/courses/{course_id}/jobs/{job_id}/cancel` | 取消任务 |
| POST | `/api/v1/courses/{course_id}/jobs/{job_id}/retry` | 重试任务 |
| POST | `/api/v1/courses/{course_id}/tts` | 合成语音 |
| GET | `/api/v1/courses/{course_id}/workspaces/{workspace_id}/stages/{stage_id}/scenes/{scene_id}/narration` | 读取场景讲解 |
| POST | `/api/v1/courses/{course_id}/workspaces/{workspace_id}/stages/{stage_id}/scenes/{scene_id}/narration` | 合成场景讲解 |
| GET | `/api/v1/courses/{course_id}/workspaces/{workspace_id}/stages/{stage_id}/scenes/{scene_id}/quiz-attempt` | 读取测验作答 |
| POST | `/api/v1/courses/{course_id}/workspaces/{workspace_id}/stages/{stage_id}/scenes/{scene_id}/quiz-attempt` | 保存测验作答 |
| POST | `/api/v1/courses/{course_id}/discussion` | 运行圆桌讨论 |
| GET | `/api/v1/magicclass/fusion/providers` | 提供方状态 |
| GET | `/api/v1/courses/{course_id}/magicclass-context` | 这门课已同步的知识点、章节与可用资料（脱敏，只含标题） |
| GET | `/api/v1/magicclass/learning-space/status` | 独立学习空间状态 |

## 接口契约

### `GET /api/v1/courses/{course_id}/interactive-classroom/status`

用途：读取状态。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/magicclass_classroom.py](../../backend/app/api/routes/magicclass_classroom.py)，`get_status`。

Web 封装：`getInteractiveClassroomStatus`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `course_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [MagicClassStatusOut](schemas.md#schema-magicclassstatusout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `enabled` | boolean | 是 | — | 是否启用 |
| `configured` | boolean | 否 | default=false | — |
| `available` | boolean | 否 | default=false | 当前能力是否可用 |
| `incompatible` | boolean | 否 | default=false | — |
| `degraded` | boolean | 否 | default=false | — |
| `compatibility` | string | 否 | default="unknown" | — |
| `compatibility_reason` | string / null | 否 | — | — |
| `service` | string | 否 | default="magicclass" | — |
| `version` | string | 否 | default="" | — |
| `version_source` | string | 否 | default="unknown" | — |
| `version_out_of_range` | boolean | 否 | default=false | — |
| `capabilities` | map<string, boolean> | 否 | additionalProperties={"type": "boolean"} | — |
| `unavailable_capabilities` | array<string> | 否 | — | — |
| `unavailable` | boolean | 否 | default=false | — |
| `embed_origin` | string / null | 否 | — | — |
| `browser_embed_available` | boolean | 否 | default=false | — |
| `browser_embed_reason` | string / null | 否 | — | — |
| `external_3d_available` | boolean | 否 | default=true | — |
| `poll_interval_ms` | integer | 否 | default=5000 | — |
| `poll_max_seconds` | integer | 否 | default=1800 | — |
| `checked_at` | string | 否 | default="" | — |
| `reason` | string / null | 否 | — | 原因 |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/courses/{course_id}/interactive-classroom/plan`

用途：生成**之前**给学生看的信息：课程、可选资料、推荐形态与理由。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/magicclass_classroom.py](../../backend/app/api/routes/magicclass_classroom.py)，`get_plan`。

Web 封装：`getInteractiveClassroomPlan`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

生成**之前**给学生看的信息：课程、可选资料、推荐形态与理由。

这个接口不产生任何外部任务、不产生费用；学生确认后才调用 generate。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `course_id` | string | 是 | — | — |
| query | `mode` | string | 否 | default="adaptive" | 生成意图 |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [MagicClassPlanOut](schemas.md#schema-magicclassplanout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `course_id` | string | 是 | — | 关联课程标识 |
| `course_name` | string | 是 | — | — |
| `mode` | string | 是 | — | — |
| `mode_label` | string | 是 | — | — |
| `requested_mode` | string | 是 | — | — |
| `adaptive_reason` | string / null | 否 | — | — |
| `intent_note` | string | 否 | default="内容形态只是生成意图，最终包含哪些形式由生成器根据课程内容决定。" | — |
| `materials` | array<[MagicClassMaterialOut](schemas.md#schema-magicclassmaterialout)> | 否 | — | — |
| `selected_material_ids` | array<string> | 否 | — | — |
| `context_sources` | map<string, string> | 否 | additionalProperties={"type": "string"} | — |
| `context_updated_at` | map<string, string> | 否 | additionalProperties={"type": "string"} | — |
| `context_truncated` | boolean | 否 | default=false | — |
| `context_warnings` | array<string> | 否 | — | — |
| `capabilities` | map<string, boolean> | 否 | additionalProperties={"type": "boolean"} | — |
| `external_3d_available` | boolean | 否 | default=true | — |
| `can_generate` | boolean | 否 | default=false | — |
| `reason` | string / null | 否 | — | 原因 |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `POST /api/v1/courses/{course_id}/interactive-classroom/generate`

用途：生成课堂。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/magicclass_classroom.py](../../backend/app/api/routes/magicclass_classroom.py)，`generate_classroom`。

Web 封装：`generateInteractiveClassroom`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `course_id` | string | 是 | — | — |

请求体：`application/json`，必填；[MagicClassGenerateRequest](schemas.md#schema-magicclassgeneraterequest)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `mode` | string | 否 | default="adaptive" | 生成意图：adaptive/explain/quiz/simulation/visualization/mindmap/coding/pbl/review |
| `learning_objective` | string / null | 否 | string约束: maxLength=500 | 学生明确选择的学习目标(可选) |
| `current_difficulty` | string / null | 否 | string约束: maxLength=500 | 学生当前卡在哪里(可选) |
| `desired_duration_minutes` | integer / null | 否 | integer约束: minimum=5.0; maximum=180.0 | 期望学习时长(分钟，可选) |
| `difficulty_level` | string / null | 否 | — | 难度：beginner/standard/advanced(可选) |
| `wants_more_practice` | boolean | 否 | default=false | 是否需要更多练习 |
| `selected_material_ids` | array<string> | 否 | maxItems=20 | 希望使用的课程资料 ID 列表 |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 202 | application/json | [MagicClassGenerateOut](schemas.md#schema-magicclassgenerateout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

202 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `accepted` | boolean | 否 | default=true | — |
| `session` | [MagicClassSessionOut](schemas.md#schema-magicclasssessionout) | 是 | — | — |
| `poll_interval_ms` | integer | 否 | default=5000 | — |
| `mode` | string | 是 | — | — |
| `requested_mode` | string / null | 否 | — | — |
| `adaptive_reason` | string / null | 否 | — | — |
| `materials` | array<[MagicClassMaterialOut](schemas.md#schema-magicclassmaterialout)> | 否 | — | — |
| `request_source` | string / null | 否 | — | — |
| `request_source_note` | string / null | 否 | — | — |
| `materials_unresolved` | array<string> | 否 | — | — |
| `materials_warning` | string / null | 否 | — | — |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/courses/{course_id}/interactive-classroom/jobs/{session_id}`

用途：读取进度。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/magicclass_classroom.py](../../backend/app/api/routes/magicclass_classroom.py)，`get_progress`。

Web 封装：`getInteractiveClassroomJob`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `course_id` | string | 是 | — | — |
| path | `session_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [MagicClassSessionOut](schemas.md#schema-magicclasssessionout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `session_id` | string | 是 | — | — |
| `course_id` | string | 是 | — | 关联课程标识 |
| `mode` | string | 是 | — | — |
| `requested_mode` | string / null | 否 | — | — |
| `adaptive_reason` | string / null | 否 | — | — |
| `job_id` | string / null | 否 | — | 任务标识 |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `step` | string | 是 | — | — |
| `progress` | integer | 否 | default=0 | 进度；对象或数值范围按字段类型 |
| `message` | string | 否 | default="" | — |
| `error` | string / null | 否 | — | — |
| `classroom_id` | string / null | 否 | — | — |
| `url` | string / null | 否 | — | — |
| `url_unavailable_reason` | string / null | 否 | — | — |
| `scenes_count` | integer / null | 否 | — | — |
| `terminal` | boolean | 否 | default=false | — |
| `retryable` | boolean | 否 | default=false | — |
| `partial` | boolean | 否 | default=false | — |
| `error_code` | string / null | 否 | — | 失败码，可空 |
| `created_at` | string | 否 | default="" | 创建时间 |
| `updated_at` | string | 否 | default="" | 最近更新时间 |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | NOT_FOUND | '课堂生成任务不存在' |

### `GET /api/v1/courses/{course_id}/interactive-classroom/{session_id}/composition`

用途：回读这节课**真实**包含的内容（幻灯片/测验/交互/项目式学习 + widget 分布）。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/magicclass_classroom.py](../../backend/app/api/routes/magicclass_classroom.py)，`get_composition`。

Web 封装：`getInteractiveClassroomComposition`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

回读这节课**真实**包含的内容（幻灯片/测验/交互/项目式学习 + widget 分布）。

只读、按需调用（不在历史列表里批量拉取上游）。请求 mode 只是意图，
这里返回的才是实际产出，UI 必须用这份数据向学生说明"已生成内容包含……"。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `course_id` | string | 是 | — | — |
| path | `session_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [MagicClassCompositionOut](schemas.md#schema-magicclasscompositionout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `classroom_id` | string | 是 | — | — |
| `scene_total` | integer | 否 | default=0 | — |
| `scenes` | array<[MagicClassSceneCountOut](schemas.md#schema-magicclassscenecountout)> | 否 | — | — |
| `widget_types` | array<[MagicClassWidgetCountOut](schemas.md#schema-magicclasswidgetcountout)> | 否 | — | — |
| `has_whiteboard` | boolean | 否 | default=false | — |
| `has_tts` | boolean | 否 | default=false | — |
| `has_multi_agent` | boolean | 否 | default=false | — |
| `has_unknown_scene_type` | boolean | 否 | default=false | — |
| `has_unknown_widget_type` | boolean | 否 | default=false | — |
| `requires_external_3d` | boolean | 否 | default=false | — |
| `external_3d_available` | boolean | 否 | default=true | — |
| `degraded` | boolean | 否 | default=false | — |
| `read_at` | string | 否 | default="" | — |
| `error` | string / null | 否 | — | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | NOT_FOUND | '课堂生成任务不存在' |

### `GET /api/v1/courses/{course_id}/interactive-classroom`

用途：列出课堂。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/magicclass_classroom.py](../../backend/app/api/routes/magicclass_classroom.py)，`list_classrooms`。

Web 封装：`listInteractiveClassrooms`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `course_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [MagicClassClassroomsOut](schemas.md#schema-magicclassclassroomsout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `enabled` | boolean | 是 | — | 是否启用 |
| `items` | array<[MagicClassClassroomOut](schemas.md#schema-magicclassclassroomout)> | 否 | — | 列表条目 |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `POST /api/v1/courses/{course_id}/interactive-classroom/{session_id}/retry`

用途：重新生成一节课堂。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/magicclass_classroom.py](../../backend/app/api/routes/magicclass_classroom.py)，`retry_session`。

Web 封装：`retryInteractiveClassroom`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

重新生成一节课堂。

magic class **没有**原生 retry：这里始终是"以原任务的学生输入重新提交一个新任务"。

- 个性化以原任务的 `request_snapshot` 为**权威**，绝不因为客户端没传就丢掉；
- 旧任务没有快照时，接受经过校验的请求体；
- 两者都没有时走明确记录、有测试覆盖的兼容降级（只沿用原形态）；
- 课程权限、资料授权、用户身份一律重新校验；
- 绝不篡改旧 session。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `course_id` | string | 是 | — | — |
| path | `session_id` | string | 是 | — | — |

请求体：`application/json`，可省略；[MagicClassGenerateRequest](schemas.md#schema-magicclassgeneraterequest) / null。


请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 202 | application/json | [MagicClassGenerateOut](schemas.md#schema-magicclassgenerateout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

202 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `accepted` | boolean | 否 | default=true | — |
| `session` | [MagicClassSessionOut](schemas.md#schema-magicclasssessionout) | 是 | — | — |
| `poll_interval_ms` | integer | 否 | default=5000 | — |
| `mode` | string | 是 | — | — |
| `requested_mode` | string / null | 否 | — | — |
| `adaptive_reason` | string / null | 否 | — | — |
| `materials` | array<[MagicClassMaterialOut](schemas.md#schema-magicclassmaterialout)> | 否 | — | — |
| `request_source` | string / null | 否 | — | — |
| `request_source_note` | string / null | 否 | — | — |
| `materials_unresolved` | array<string> | 否 | — | — |
| `materials_warning` | string / null | 否 | — | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | NOT_FOUND | '课堂生成任务不存在' |

### `GET /api/v1/magicclass/fusion/status`

用途：受管课堂服务状态。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/magicclass_fusion.py](../../backend/app/api/routes/magicclass_fusion.py)，`fusion_status`。

Web 封装：`getMagicClassFusionStatus`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [FusionStatus](schemas.md#schema-fusionstatus) |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `enabled` | boolean | 是 | — | 是否启用 |
| `available` | boolean | 是 | — | 当前能力是否可用 |
| `state` | [FusionState](schemas.md#schema-fusionstate) | 是 | — | — |
| `capabilities` | array<string> | 否 | — | — |
| `reason` | string | 是 | — | 原因 |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/magicclass/fusion/recent`

用途：当前用户**所有可见课程**的最近学习内容（一次请求替代按课程轮询）。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/magicclass_fusion.py](../../backend/app/api/routes/magicclass_fusion.py)，`fusion_recent`。

Web 封装：`getMagicClassRecent`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

当前用户**所有可见课程**的最近学习内容（一次请求替代按课程轮询）。

课程可见性走与课程详情/互动课堂完全相同的策略（`can_view_course`），
因此这里不会出现别的用户的记录，也不会出现该用户已失去访问权的课程。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| query | `limit` | integer | 否 | default=20; minimum=1; maximum=50 | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [FusionRecentOut](schemas.md#schema-fusionrecentout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `items` | array<[FusionRecentItem](schemas.md#schema-fusionrecentitem)> | 否 | — | 列表条目 |
| `limit` | integer | 是 | — | 本次读取上限 |
| `has_more` | boolean | 否 | default=false | 是否还有下一页 |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/courses/{course_id}/workspaces`

用途：列出工作台。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/magicclass_workspaces.py](../../backend/app/api/routes/magicclass_workspaces.py)，`list_workspaces`。

Web 封装：`listMagicClassWorkspaces`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `course_id` | string | 是 | — | — |
| query | `limit` | integer | 否 | default=20; minimum=1; maximum=50 | — |
| query | `cursor` | string / null | 否 | string约束: maxLength=512 | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [WorkspaceListOut](schemas.md#schema-workspacelistout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `items` | array<[WorkspaceOut](schemas.md#schema-workspaceout)> | 否 | — | 列表条目 |
| `next_cursor` | string / null | 否 | — | 下一页游标，为空表示没有后续页 |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 503 | MAGICCLASS_FUSION_UNAVAILABLE | '受管 magic class 服务未启用' |

### `POST /api/v1/courses/{course_id}/workspaces`

用途：创建工作台。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/magicclass_workspaces.py](../../backend/app/api/routes/magicclass_workspaces.py)，`create_workspace`。

Web 封装：`createMagicClassWorkspace`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `course_id` | string | 是 | — | — |
| header | `Idempotency-Key` | string / null | 否 | — | — |

请求体：`application/json`，必填；[WorkspaceCreateIn](schemas.md#schema-workspacecreatein)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `name` | string | 是 | minLength=1; maxLength=120 | 名称 |
| `description` | string | 否 | default=""; maxLength=4000 | 说明 |
| `folder_id` | string / null | 否 | string约束: minLength=1; maxLength=120 | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "name": "<name>"
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 201 | application/json | [WorkspaceOut](schemas.md#schema-workspaceout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

201 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `course_id` | string | 是 | — | 关联课程标识 |
| `name` | string | 是 | — | 名称 |
| `description` | string | 否 | default="" | 说明 |
| `folder_id` | string / null | 否 | — | — |
| `revision` | integer | 是 | — | 当前版本号，条件写入回传 If-Match |
| `created_at` | string | 否 | default="" | 创建时间 |
| `updated_at` | string | 否 | default="" | 最近更新时间 |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 503 | MAGICCLASS_FUSION_UNAVAILABLE | '受管 magic class 服务未启用' |
| 400 | MAGICCLASS_INVALID_REQUEST | '创建请求必须携带 Idempotency-Key' |
| 400 | MAGICCLASS_INVALID_REQUEST | 'Idempotency-Key 过长' |

### `GET /api/v1/courses/{course_id}/workspaces/{workspace_id}`

用途：读取工作台。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/magicclass_workspaces.py](../../backend/app/api/routes/magicclass_workspaces.py)，`get_workspace`。

Web 封装：`getMagicClassWorkspace`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `course_id` | string | 是 | — | — |
| path | `workspace_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [WorkspaceOut](schemas.md#schema-workspaceout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `course_id` | string | 是 | — | 关联课程标识 |
| `name` | string | 是 | — | 名称 |
| `description` | string | 否 | default="" | 说明 |
| `folder_id` | string / null | 否 | — | — |
| `revision` | integer | 是 | — | 当前版本号，条件写入回传 If-Match |
| `created_at` | string | 否 | default="" | 创建时间 |
| `updated_at` | string | 否 | default="" | 最近更新时间 |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 503 | MAGICCLASS_FUSION_UNAVAILABLE | '受管 magic class 服务未启用' |

### `PATCH /api/v1/courses/{course_id}/workspaces/{workspace_id}`

用途：更新工作台。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/magicclass_workspaces.py](../../backend/app/api/routes/magicclass_workspaces.py)，`update_workspace`。

Web 封装：`updateMagicClassWorkspace`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `course_id` | string | 是 | — | — |
| path | `workspace_id` | string | 是 | — | — |
| header | `If-Match` | string / null | 否 | — | — |

请求体：`application/json`，必填；[WorkspaceUpdateIn](schemas.md#schema-workspaceupdatein)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `name` | string / null | 否 | string约束: minLength=1; maxLength=120 | 名称 |
| `description` | string / null | 否 | string约束: maxLength=4000 | 说明 |
| `folder_id` | string / null | 否 | string约束: minLength=1; maxLength=120 | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [WorkspaceOut](schemas.md#schema-workspaceout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `course_id` | string | 是 | — | 关联课程标识 |
| `name` | string | 是 | — | 名称 |
| `description` | string | 否 | default="" | 说明 |
| `folder_id` | string / null | 否 | — | — |
| `revision` | integer | 是 | — | 当前版本号，条件写入回传 If-Match |
| `created_at` | string | 否 | default="" | 创建时间 |
| `updated_at` | string | 否 | default="" | 最近更新时间 |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 400 | MAGICCLASS_INVALID_REQUEST | '没有需要更新的字段' |
| 503 | MAGICCLASS_FUSION_UNAVAILABLE | '受管 magic class 服务未启用' |
| 400 | MAGICCLASS_INVALID_REQUEST | '写入请求必须携带 If-Match（当前 revision）' |
| 400 | MAGICCLASS_INVALID_REQUEST | 'If-Match 不接受 *，请传回你读到的 revision' |
| 400 | MAGICCLASS_INVALID_REQUEST | 'If-Match 必须是正整数 revision' |

### `DELETE /api/v1/courses/{course_id}/workspaces/{workspace_id}`

用途：删除工作台。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/magicclass_workspaces.py](../../backend/app/api/routes/magicclass_workspaces.py)，`delete_workspace`。

Web 封装：`deleteMagicClassWorkspace`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `course_id` | string | 是 | — | — |
| path | `workspace_id` | string | 是 | — | — |
| header | `If-Match` | string / null | 否 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | 动态响应；见下方补充与 response-contracts.md |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 503 | MAGICCLASS_FUSION_UNAVAILABLE | '受管 magic class 服务未启用' |
| 400 | MAGICCLASS_INVALID_REQUEST | '写入请求必须携带 If-Match（当前 revision）' |
| 400 | MAGICCLASS_INVALID_REQUEST | 'If-Match 不接受 *，请传回你读到的 revision' |
| 400 | MAGICCLASS_INVALID_REQUEST | 'If-Match 必须是正整数 revision' |

### `GET /api/v1/courses/{course_id}/workspaces/{workspace_id}/stages`

用途：列出舞台。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/magicclass_workspaces.py](../../backend/app/api/routes/magicclass_workspaces.py)，`list_stages`。

Web 封装：`listMagicClassStages`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `course_id` | string | 是 | — | — |
| path | `workspace_id` | string | 是 | — | — |
| query | `limit` | integer | 否 | default=20; minimum=1; maximum=50 | — |
| query | `cursor` | string / null | 否 | string约束: maxLength=512 | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [StageListOut](schemas.md#schema-stagelistout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `items` | array<[StageSummaryOut](schemas.md#schema-stagesummaryout)> | 否 | — | 列表条目 |
| `next_cursor` | string / null | 否 | — | 下一页游标，为空表示没有后续页 |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 503 | MAGICCLASS_FUSION_UNAVAILABLE | '受管 magic class 服务未启用' |

### `POST /api/v1/courses/{course_id}/workspaces/{workspace_id}/stages`

用途：创建舞台。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/magicclass_workspaces.py](../../backend/app/api/routes/magicclass_workspaces.py)，`create_stage`。

Web 封装：`createMagicClassStage`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `course_id` | string | 是 | — | — |
| path | `workspace_id` | string | 是 | — | — |
| header | `Idempotency-Key` | string / null | 否 | — | — |

请求体：`application/json`，必填；[StageCreateIn](schemas.md#schema-stagecreatein)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `title` | string | 是 | minLength=1; maxLength=200 | 标题 |
| `document` | object / null | 否 | — | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "title": "<title>"
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 201 | application/json | [StageOut](schemas.md#schema-stageout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

201 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `workspace_id` | string | 是 | — | 工作台标识 |
| `course_id` | string | 是 | — | 关联课程标识 |
| `title` | string | 是 | — | 标题 |
| `revision` | integer | 是 | — | 当前版本号，条件写入回传 If-Match |
| `dsl_version` | string | 否 | default="" | — |
| `created_at` | string | 否 | default="" | 创建时间 |
| `updated_at` | string | 否 | default="" | 最近更新时间 |
| `document` | object | 否 | — | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 503 | MAGICCLASS_FUSION_UNAVAILABLE | '受管 magic class 服务未启用' |
| 400 | MAGICCLASS_INVALID_REQUEST | '创建请求必须携带 Idempotency-Key' |
| 400 | MAGICCLASS_INVALID_REQUEST | 'Idempotency-Key 过长' |

### `GET /api/v1/courses/{course_id}/workspaces/{workspace_id}/stages/{stage_id}`

用途：读取舞台。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/magicclass_workspaces.py](../../backend/app/api/routes/magicclass_workspaces.py)，`get_stage`。

Web 封装：`getMagicClassStage`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `course_id` | string | 是 | — | — |
| path | `workspace_id` | string | 是 | — | — |
| path | `stage_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [StageOut](schemas.md#schema-stageout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `workspace_id` | string | 是 | — | 工作台标识 |
| `course_id` | string | 是 | — | 关联课程标识 |
| `title` | string | 是 | — | 标题 |
| `revision` | integer | 是 | — | 当前版本号，条件写入回传 If-Match |
| `dsl_version` | string | 否 | default="" | — |
| `created_at` | string | 否 | default="" | 创建时间 |
| `updated_at` | string | 否 | default="" | 最近更新时间 |
| `document` | object | 否 | — | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 503 | MAGICCLASS_FUSION_UNAVAILABLE | '受管 magic class 服务未启用' |

### `PUT /api/v1/courses/{course_id}/workspaces/{workspace_id}/stages/{stage_id}`

用途：替换舞台。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/magicclass_workspaces.py](../../backend/app/api/routes/magicclass_workspaces.py)，`replace_stage`。

Web 封装：`replaceMagicClassStage`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `course_id` | string | 是 | — | — |
| path | `workspace_id` | string | 是 | — | — |
| path | `stage_id` | string | 是 | — | — |
| header | `If-Match` | string / null | 否 | — | — |

请求体：`application/json`，必填；[StageReplaceIn](schemas.md#schema-stagereplacein)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `document` | object | 是 | — | — |
| `title` | string / null | 否 | string约束: minLength=1; maxLength=200 | 标题 |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "document": {}
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [StageOut](schemas.md#schema-stageout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `workspace_id` | string | 是 | — | 工作台标识 |
| `course_id` | string | 是 | — | 关联课程标识 |
| `title` | string | 是 | — | 标题 |
| `revision` | integer | 是 | — | 当前版本号，条件写入回传 If-Match |
| `dsl_version` | string | 否 | default="" | — |
| `created_at` | string | 否 | default="" | 创建时间 |
| `updated_at` | string | 否 | default="" | 最近更新时间 |
| `document` | object | 否 | — | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 503 | MAGICCLASS_FUSION_UNAVAILABLE | '受管 magic class 服务未启用' |
| 400 | MAGICCLASS_INVALID_REQUEST | '写入请求必须携带 If-Match（当前 revision）' |
| 400 | MAGICCLASS_INVALID_REQUEST | 'If-Match 不接受 *，请传回你读到的 revision' |
| 400 | MAGICCLASS_INVALID_REQUEST | 'If-Match 必须是正整数 revision' |

### `DELETE /api/v1/courses/{course_id}/workspaces/{workspace_id}/stages/{stage_id}`

用途：删除舞台。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/magicclass_workspaces.py](../../backend/app/api/routes/magicclass_workspaces.py)，`delete_stage`。

Web 封装：当前无封装；按本节后端契约调用。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `course_id` | string | 是 | — | — |
| path | `workspace_id` | string | 是 | — | — |
| path | `stage_id` | string | 是 | — | — |
| header | `If-Match` | string / null | 否 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | 动态响应；见下方补充与 response-contracts.md |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 503 | MAGICCLASS_FUSION_UNAVAILABLE | '受管 magic class 服务未启用' |
| 400 | MAGICCLASS_INVALID_REQUEST | '写入请求必须携带 If-Match（当前 revision）' |
| 400 | MAGICCLASS_INVALID_REQUEST | 'If-Match 不接受 *，请传回你读到的 revision' |
| 400 | MAGICCLASS_INVALID_REQUEST | 'If-Match 必须是正整数 revision' |

### `GET /api/v1/courses/{course_id}/folders`

用途：列出文件夹。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/magicclass_discovery.py](../../backend/app/api/routes/magicclass_discovery.py)，`list_folders`。

Web 封装：`listMagicClassFolders`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `course_id` | string | 是 | — | — |
| query | `limit` | integer | 否 | default=20; minimum=1; maximum=50 | — |
| query | `cursor` | string / null | 否 | string约束: maxLength=512 | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [FolderListOut](schemas.md#schema-folderlistout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `items` | array<[FolderOut](schemas.md#schema-folderout)> | 否 | — | 列表条目 |
| `next_cursor` | string / null | 否 | — | 下一页游标，为空表示没有后续页 |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 503 | MAGICCLASS_FUSION_UNAVAILABLE | '受管 magic class 服务未启用' |

### `POST /api/v1/courses/{course_id}/folders`

用途：创建文件夹。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/magicclass_discovery.py](../../backend/app/api/routes/magicclass_discovery.py)，`create_folder`。

Web 封装：`createMagicClassFolder`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `course_id` | string | 是 | — | — |
| header | `Idempotency-Key` | string / null | 否 | — | — |

请求体：`application/json`，必填；[FolderCreateIn](schemas.md#schema-foldercreatein)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `name` | string | 是 | minLength=1; maxLength=120 | 名称 |
| `parent_id` | string / null | 否 | string约束: minLength=1; maxLength=120 | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "name": "<name>"
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 201 | application/json | [FolderOut](schemas.md#schema-folderout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

201 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `course_id` | string | 是 | — | 关联课程标识 |
| `parent_id` | string / null | 否 | — | — |
| `name` | string | 是 | — | 名称 |
| `revision` | integer | 是 | — | 当前版本号，条件写入回传 If-Match |
| `created_at` | string | 否 | default="" | 创建时间 |
| `updated_at` | string | 否 | default="" | 最近更新时间 |
| `workspace_count` | integer / null | 否 | — | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 503 | MAGICCLASS_FUSION_UNAVAILABLE | '受管 magic class 服务未启用' |
| 400 | MAGICCLASS_INVALID_REQUEST | '创建请求必须携带 Idempotency-Key' |
| 400 | MAGICCLASS_INVALID_REQUEST | 'Idempotency-Key 过长' |

### `GET /api/v1/courses/{course_id}/folders/{folder_id}`

用途：读取文件夹。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/magicclass_discovery.py](../../backend/app/api/routes/magicclass_discovery.py)，`get_folder`。

Web 封装：当前无封装；按本节后端契约调用。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `course_id` | string | 是 | — | — |
| path | `folder_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [FolderOut](schemas.md#schema-folderout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `course_id` | string | 是 | — | 关联课程标识 |
| `parent_id` | string / null | 否 | — | — |
| `name` | string | 是 | — | 名称 |
| `revision` | integer | 是 | — | 当前版本号，条件写入回传 If-Match |
| `created_at` | string | 否 | default="" | 创建时间 |
| `updated_at` | string | 否 | default="" | 最近更新时间 |
| `workspace_count` | integer / null | 否 | — | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 503 | MAGICCLASS_FUSION_UNAVAILABLE | '受管 magic class 服务未启用' |

### `PATCH /api/v1/courses/{course_id}/folders/{folder_id}`

用途：更新文件夹。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/magicclass_discovery.py](../../backend/app/api/routes/magicclass_discovery.py)，`update_folder`。

Web 封装：`updateMagicClassFolder`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `course_id` | string | 是 | — | — |
| path | `folder_id` | string | 是 | — | — |
| header | `If-Match` | string / null | 否 | — | — |

请求体：`application/json`，必填；[FolderUpdateIn](schemas.md#schema-folderupdatein)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `name` | string / null | 否 | string约束: minLength=1; maxLength=120 | 名称 |
| `parent_id` | string / null | 否 | string约束: minLength=1; maxLength=120 | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [FolderOut](schemas.md#schema-folderout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `course_id` | string | 是 | — | 关联课程标识 |
| `parent_id` | string / null | 否 | — | — |
| `name` | string | 是 | — | 名称 |
| `revision` | integer | 是 | — | 当前版本号，条件写入回传 If-Match |
| `created_at` | string | 否 | default="" | 创建时间 |
| `updated_at` | string | 否 | default="" | 最近更新时间 |
| `workspace_count` | integer / null | 否 | — | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 400 | MAGICCLASS_INVALID_REQUEST | '没有需要更新的字段' |
| 503 | MAGICCLASS_FUSION_UNAVAILABLE | '受管 magic class 服务未启用' |
| 400 | MAGICCLASS_INVALID_REQUEST | '写入请求必须携带 If-Match（当前 revision）' |
| 400 | MAGICCLASS_INVALID_REQUEST | 'If-Match 不接受 *，请传回你读到的 revision' |
| 400 | MAGICCLASS_INVALID_REQUEST | 'If-Match 必须是正整数 revision' |

### `DELETE /api/v1/courses/{course_id}/folders/{folder_id}`

用途：删除文件夹。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/magicclass_discovery.py](../../backend/app/api/routes/magicclass_discovery.py)，`delete_folder`。

Web 封装：`deleteMagicClassFolder`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `course_id` | string | 是 | — | — |
| path | `folder_id` | string | 是 | — | — |
| header | `If-Match` | string / null | 否 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | 动态响应；见下方补充与 response-contracts.md |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 503 | MAGICCLASS_FUSION_UNAVAILABLE | '受管 magic class 服务未启用' |
| 400 | MAGICCLASS_INVALID_REQUEST | '写入请求必须携带 If-Match（当前 revision）' |
| 400 | MAGICCLASS_INVALID_REQUEST | 'If-Match 不接受 *，请传回你读到的 revision' |
| 400 | MAGICCLASS_INVALID_REQUEST | 'If-Match 必须是正整数 revision' |

### `GET /api/v1/courses/{course_id}/search`

用途：搜索课程内容。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/magicclass_discovery.py](../../backend/app/api/routes/magicclass_discovery.py)，`search_course_content`。

Web 封装：`searchMagicClassContent`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `course_id` | string | 是 | — | — |
| query | `q` | string / null | 否 | string约束: maxLength=400 | — |
| query | `limit` | integer | 否 | default=20; minimum=1; maximum=50 | — |
| query | `cursor` | string / null | 否 | string约束: maxLength=512 | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [SearchListOut](schemas.md#schema-searchlistout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `items` | array<[SearchHitOut](schemas.md#schema-searchhitout)> | 否 | — | 列表条目 |
| `next_cursor` | string / null | 否 | — | 下一页游标，为空表示没有后续页 |
| `query` | string | 是 | — | 查询内容 |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 503 | MAGICCLASS_FUSION_UNAVAILABLE | '受管 magic class 服务未启用' |
| 400 | MAGICCLASS_INVALID_REQUEST | '搜索关键词不能为空' |
| 400 | MAGICCLASS_INVALID_REQUEST | f'搜索关键词不能超过 {MAX_QUERY_LENGTH} 个字符' |

### `POST /api/v1/courses/{course_id}/workspaces/{workspace_id}/stages/{stage_id}/commands`

用途：应用舞台编辑命令。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/magicclass_editor.py](../../backend/app/api/routes/magicclass_editor.py)，`apply_stage_commands`。

Web 封装：`applyMagicClassStageCommands`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

编辑 commands 必须同时带 If-Match 与 Idempotency-Key。头字段在 OpenAPI 可选，但业务校验强制要求。详见 [接入流程](integration.md#magicclass)。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `course_id` | string | 是 | — | — |
| path | `workspace_id` | string | 是 | — | — |
| path | `stage_id` | string | 是 | — | — |
| header | `If-Match` | string / null | 否 | — | — |
| header | `Idempotency-Key` | string / null | 否 | — | — |

请求体：`application/json`，必填；[StageCommandsIn](schemas.md#schema-stagecommandsin)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `commands` | array<object> | 是 | minItems=1; maxItems=50 | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "commands": [
    {}
  ]
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [StageCommandResultOut](schemas.md#schema-stagecommandresultout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `workspace_id` | string | 是 | — | 工作台标识 |
| `course_id` | string | 是 | — | 关联课程标识 |
| `title` | string | 是 | — | 标题 |
| `revision` | integer | 是 | — | 当前版本号，条件写入回传 If-Match |
| `dsl_version` | string | 否 | default="" | — |
| `created_at` | string | 否 | default="" | 创建时间 |
| `updated_at` | string | 否 | default="" | 最近更新时间 |
| `document` | object | 否 | — | — |
| `applied_commands` | integer | 否 | default=0 | — |
| `migrated` | boolean | 否 | default=false | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 400 | MAGICCLASS_INVALID_REQUEST | '至少需要一条命令' |
| 400 | MAGICCLASS_INVALID_REQUEST | f'一次最多提交 {MAX_COMMANDS_PER_REQUEST} 条命令' |
| 503 | MAGICCLASS_FUSION_UNAVAILABLE | '受管 magic class 服务未启用' |
| 400 | MAGICCLASS_INVALID_REQUEST | '编辑请求必须携带 If-Match（当前 revision）' |
| 400 | MAGICCLASS_INVALID_REQUEST | 'If-Match 不接受 *，请传回你读到的 revision' |
| 400 | MAGICCLASS_INVALID_REQUEST | 'If-Match 必须是正整数 revision' |
| 400 | MAGICCLASS_INVALID_REQUEST | '编辑请求必须携带 Idempotency-Key' |
| 400 | MAGICCLASS_INVALID_REQUEST | 'Idempotency-Key 过长' |

### `GET /api/v1/courses/{course_id}/workspaces/{workspace_id}/stages/{stage_id}/outline`

用途：读取舞台目录。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/magicclass_editor.py](../../backend/app/api/routes/magicclass_editor.py)，`get_stage_outline`。

Web 封装：`getMagicClassStageOutline`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

编辑 commands 必须同时带 If-Match 与 Idempotency-Key。头字段在 OpenAPI 可选，但业务校验强制要求。详见 [接入流程](integration.md#magicclass)。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `course_id` | string | 是 | — | — |
| path | `workspace_id` | string | 是 | — | — |
| path | `stage_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [StageOutlineOut](schemas.md#schema-stageoutlineout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `stage_id` | string | 是 | — | 舞台标识 |
| `workspace_id` | string | 是 | — | 工作台标识 |
| `title` | string | 是 | — | 标题 |
| `revision` | integer | 是 | — | 当前版本号，条件写入回传 If-Match |
| `dsl_version` | string | 否 | default="" | — |
| `scenes` | array<[SceneOutlineOut](schemas.md#schema-sceneoutlineout)> | 否 | — | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 503 | MAGICCLASS_FUSION_UNAVAILABLE | '受管 magic class 服务未启用' |

### `GET /api/v1/courses/{course_id}/workspaces/{workspace_id}/stages/{stage_id}/playback`

用途：读取舞台播放计划。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/magicclass_editor.py](../../backend/app/api/routes/magicclass_editor.py)，`get_stage_playback`。

Web 封装：`getMagicClassStagePlayback`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

Playback plan. `scene_id` carries the resume position from the URL.

编辑 commands 必须同时带 If-Match 与 Idempotency-Key。头字段在 OpenAPI 可选，但业务校验强制要求。详见 [接入流程](integration.md#magicclass)。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `course_id` | string | 是 | — | — |
| path | `workspace_id` | string | 是 | — | — |
| path | `stage_id` | string | 是 | — | — |
| query | `scene_id` | string / null | 否 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [StagePlaybackOut](schemas.md#schema-stageplaybackout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `stage_id` | string | 是 | — | 舞台标识 |
| `workspace_id` | string | 是 | — | 工作台标识 |
| `title` | string | 是 | — | 标题 |
| `revision` | integer | 是 | — | 当前版本号，条件写入回传 If-Match |
| `dsl_version` | string | 否 | default="" | — |
| `start_index` | integer | 否 | default=0 | — |
| `scenes` | array<[ScenePlaybackOut](schemas.md#schema-sceneplaybackout)> | 否 | — | — |
| `degraded` | array<object> | 否 | — | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 503 | MAGICCLASS_FUSION_UNAVAILABLE | '受管 magic class 服务未启用' |

### `GET /api/v1/courses/{course_id}/workspaces/{workspace_id}/stages/{stage_id}/scenes/{scene_id}`

用途：读取舞台场景。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/magicclass_editor.py](../../backend/app/api/routes/magicclass_editor.py)，`get_stage_scene`。

Web 封装：`getMagicClassStageScene`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

编辑 commands 必须同时带 If-Match 与 Idempotency-Key。头字段在 OpenAPI 可选，但业务校验强制要求。详见 [接入流程](integration.md#magicclass)。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `course_id` | string | 是 | — | — |
| path | `workspace_id` | string | 是 | — | — |
| path | `stage_id` | string | 是 | — | — |
| path | `scene_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | 动态响应；见下方补充与 response-contracts.md |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 503 | MAGICCLASS_FUSION_UNAVAILABLE | '受管 magic class 服务未启用' |

### `GET /api/v1/courses/{course_id}/materials`

用途：列出资料。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/magicclass_materials.py](../../backend/app/api/routes/magicclass_materials.py)，`list_materials`。

Web 封装：`listMagicClassMaterials`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `course_id` | string | 是 | — | — |
| query | `limit` | integer | 否 | default=20; minimum=1; maximum=50 | — |
| query | `cursor` | string / null | 否 | string约束: maxLength=512 | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [MaterialListOut](schemas.md#schema-materiallistout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `items` | array<[MaterialOut](schemas.md#schema-materialout)> | 否 | — | 列表条目 |
| `next_cursor` | string / null | 否 | — | 下一页游标，为空表示没有后续页 |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 503 | MAGICCLASS_FUSION_UNAVAILABLE | '受管 magic class 服务未启用' |

### `POST /api/v1/courses/{course_id}/materials`

用途：上传资料。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/magicclass_materials.py](../../backend/app/api/routes/magicclass_materials.py)，`upload_material`。

Web 封装：`uploadMagicClassMaterial`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `course_id` | string | 是 | — | — |
| header | `Idempotency-Key` | string / null | 否 | — | — |

请求体：`multipart/form-data`，必填；[Body_upload_material_api_v1_courses__course_id__materials_post](schemas.md#schema-body_upload_material_api_v1_courses__course_id__materials_post)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `file` | string (binary) | 是 | format="binary" | — |

上传使用 FormData；字段名按上表；浏览器由运行时生成 multipart boundary。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 201 | application/json | [MaterialOut](schemas.md#schema-materialout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

201 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `course_id` | string | 是 | — | 关联课程标识 |
| `filename` | string | 是 | — | 文件名 |
| `media_type` | string | 否 | default="application/octet-stream" | — |
| `byte_size` | integer | 否 | default=0 | 字节大小 |
| `sha256` | string | 否 | default="" | 内容 SHA256 |
| `extraction_status` | string | 否 | default="unsupported" | — |
| `text_chars` | integer | 否 | default=0 | — |
| `revision` | integer | 否 | default=1 | 当前版本号，条件写入回传 If-Match |
| `created_at` | string / null | 否 | — | 创建时间 |
| `updated_at` | string / null | 否 | — | 最近更新时间 |
| `deduplicated` | boolean | 否 | default=false | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 503 | MAGICCLASS_FUSION_UNAVAILABLE | '受管 magic class 服务未启用' |
| 400 | MAGICCLASS_INVALID_REQUEST | '上传请求必须携带 Idempotency-Key' |
| 400 | MAGICCLASS_INVALID_REQUEST | 'Idempotency-Key 过长' |

### `POST /api/v1/courses/{course_id}/materials/resolve`

用途：处理资料。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/magicclass_materials.py](../../backend/app/api/routes/magicclass_materials.py)，`resolve_materials`。

Web 封装：`resolveMagicClassMaterials`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `course_id` | string | 是 | — | — |

请求体：`application/json`，必填；[MaterialResolveIn](schemas.md#schema-materialresolvein)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `material_ids` | array<string> | 否 | maxItems=50 | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [MaterialResolveOut](schemas.md#schema-materialresolveout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `resolved` | array<[MaterialReferenceOut](schemas.md#schema-materialreferenceout)> | 否 | — | — |
| `unresolved` | array<string> | 否 | — | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 400 | MAGICCLASS_INVALID_REQUEST | 'material_ids 只能包含非空字符串' |
| 400 | MAGICCLASS_INVALID_REQUEST | f'material_ids 最多 {MAX_REFERENCE_COUNT} 项' |
| 503 | MAGICCLASS_FUSION_UNAVAILABLE | '受管 magic class 服务未启用' |

### `GET /api/v1/courses/{course_id}/materials/{material_id}`

用途：读取资料。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/magicclass_materials.py](../../backend/app/api/routes/magicclass_materials.py)，`get_material`。

Web 封装：`getMagicClassMaterial`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

The one material route that returns the extracted text.

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `course_id` | string | 是 | — | — |
| path | `material_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [MaterialDetailOut](schemas.md#schema-materialdetailout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `course_id` | string | 是 | — | 关联课程标识 |
| `filename` | string | 是 | — | 文件名 |
| `media_type` | string | 否 | default="application/octet-stream" | — |
| `byte_size` | integer | 否 | default=0 | 字节大小 |
| `sha256` | string | 否 | default="" | 内容 SHA256 |
| `extraction_status` | string | 否 | default="unsupported" | — |
| `text_chars` | integer | 否 | default=0 | — |
| `revision` | integer | 否 | default=1 | 当前版本号，条件写入回传 If-Match |
| `created_at` | string / null | 否 | — | 创建时间 |
| `updated_at` | string / null | 否 | — | 最近更新时间 |
| `deduplicated` | boolean | 否 | default=false | — |
| `text` | string | 否 | default="" | 文本 |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 503 | MAGICCLASS_FUSION_UNAVAILABLE | '受管 magic class 服务未启用' |

### `DELETE /api/v1/courses/{course_id}/materials/{material_id}`

用途：删除资料。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/magicclass_materials.py](../../backend/app/api/routes/magicclass_materials.py)，`delete_material`。

Web 封装：`deleteMagicClassMaterial`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `course_id` | string | 是 | — | — |
| path | `material_id` | string | 是 | — | — |
| header | `If-Match` | string / null | 否 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | 动态响应；见下方补充与 response-contracts.md |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 503 | MAGICCLASS_FUSION_UNAVAILABLE | '受管 magic class 服务未启用' |
| 400 | MAGICCLASS_INVALID_REQUEST | '写入请求必须携带 If-Match（当前 revision）' |
| 400 | MAGICCLASS_INVALID_REQUEST | 'If-Match 不接受 *，请传回你读到的 revision' |
| 400 | MAGICCLASS_INVALID_REQUEST | 'If-Match 必须是正整数 revision' |

### `GET /api/v1/courses/{course_id}/workspaces/{workspace_id}/stages/{stage_id}/export`

用途：导出舞台。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/magicclass_archive.py](../../backend/app/api/routes/magicclass_archive.py)，`export_stage`。

Web 封装：`exportMagicClassStage`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `course_id` | string | 是 | — | — |
| path | `workspace_id` | string | 是 | — | — |
| path | `stage_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/zip | .maic.zip 文件及 X-Archive-* 头 |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

实际响应补充：动态对象、透传、文件和流式返回不能由默认 OpenAPI 完整表达；业务字段说明在 [响应补充](response-contracts.md)。下面列出实现中的返回构造式，变量代表运行时值，并非 JSON 示例。

```python
Response(content=archive, media_type='application/zip', headers={'Content-Disposition': content_disposition(filename), 'Cache-Control': 'no-store', 'X-Archive-Sha256': str(payload.get('sha256') or ''), 'X-Archive-Format-Version': str(payload.get('format_version') or '')})
```

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 503 | MAGICCLASS_FUSION_UNAVAILABLE | '受管服务未返回可用档案' |
| 503 | MAGICCLASS_FUSION_UNAVAILABLE | '受管服务返回的档案无法解码' |
| 503 | MAGICCLASS_FUSION_UNAVAILABLE | '受管 magic class 服务未启用' |

### `GET /api/v1/courses/{course_id}/workspaces/{workspace_id}/stages/{stage_id}/export/{format}`

用途：导出舞台指定格式。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/magicclass_archive.py](../../backend/app/api/routes/magicclass_archive.py)，`export_stage_format`。

Web 封装：`exportMagicClassStageFormat`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `course_id` | string | 是 | — | — |
| path | `workspace_id` | string | 是 | — | — |
| path | `stage_id` | string | 是 | — | — |
| path | `format` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | 对应导出文件媒体类型 | Markdown / DOCX / PPTX 二进制文件 |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

实际响应补充：动态对象、透传、文件和流式返回不能由默认 OpenAPI 完整表达；业务字段说明在 [响应补充](response-contracts.md)。下面列出实现中的返回构造式，变量代表运行时值，并非 JSON 示例。

```python
Response(content=content, media_type=media_type, headers={'Content-Disposition': content_disposition(filename), 'Cache-Control': 'no-store', 'X-Archive-Sha256': str(payload.get('sha256') or '')})
```

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 400 | MAGICCLASS_INVALID_REQUEST | '暂不支持该导出格式' |
| 503 | MAGICCLASS_FUSION_UNAVAILABLE | '受管服务未返回可用导出文件' |
| 503 | MAGICCLASS_FUSION_UNAVAILABLE | '受管服务返回了不匹配的文件类型' |
| 503 | MAGICCLASS_FUSION_UNAVAILABLE | '受管服务返回的文件无法解码' |
| 503 | MAGICCLASS_FUSION_UNAVAILABLE | '受管 magic class 服务未启用' |

### `POST /api/v1/courses/{course_id}/workspaces/{workspace_id}/stages/{stage_id}/export/video`

用途：导出舞台视频。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/magicclass_archive.py](../../backend/app/api/routes/magicclass_archive.py)，`export_stage_video`。

Web 封装：`enqueueMagicClassStageVideo`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `course_id` | string | 是 | — | — |
| path | `workspace_id` | string | 是 | — | — |
| path | `stage_id` | string | 是 | — | — |
| header | `Idempotency-Key` | string / null | 否 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 202 | application/json | 动态响应；见下方补充与 response-contracts.md |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

实际响应补充：动态对象、透传、文件和流式返回不能由默认 OpenAPI 完整表达；业务字段说明在 [响应补充](response-contracts.md)。下面列出实现中的返回构造式，变量代表运行时值，并非 JSON 示例。

```python
payload
```

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 503 | MAGICCLASS_FUSION_UNAVAILABLE | '受管服务未返回视频导出任务' |
| 503 | MAGICCLASS_FUSION_UNAVAILABLE | '受管 magic class 服务未启用' |
| 400 | MAGICCLASS_INVALID_REQUEST | '导入请求必须携带 Idempotency-Key' |
| 400 | MAGICCLASS_INVALID_REQUEST | 'Idempotency-Key 过长' |

### `POST /api/v1/courses/{course_id}/workspaces/{workspace_id}/import`

用途：导入舞台。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/magicclass_archive.py](../../backend/app/api/routes/magicclass_archive.py)，`import_stage`。

Web 封装：`importMagicClassStage`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `course_id` | string | 是 | — | — |
| path | `workspace_id` | string | 是 | — | — |
| header | `Idempotency-Key` | string / null | 否 | — | — |

请求体：`multipart/form-data`，必填；[Body_import_stage_api_v1_courses__course_id__workspaces__workspace_id__import_post](schemas.md#schema-body_import_stage_api_v1_courses__course_id__workspaces__workspace_id__import_post)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `file` | string (binary) | 是 | format="binary" | — |

上传使用 FormData；字段名按上表；浏览器由运行时生成 multipart boundary。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 201 | application/json | [StageOut](schemas.md#schema-stageout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

201 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `workspace_id` | string | 是 | — | 工作台标识 |
| `course_id` | string | 是 | — | 关联课程标识 |
| `title` | string | 是 | — | 标题 |
| `revision` | integer | 是 | — | 当前版本号，条件写入回传 If-Match |
| `dsl_version` | string | 否 | default="" | — |
| `created_at` | string | 否 | default="" | 创建时间 |
| `updated_at` | string | 否 | default="" | 最近更新时间 |
| `document` | object | 否 | — | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 400 | MAGICCLASS_INVALID_REQUEST | f'档案不能超过 {MAX_ARCHIVE_BYTES} 字节' |
| 400 | MAGICCLASS_INVALID_REQUEST | '档案为空' |
| 503 | MAGICCLASS_FUSION_UNAVAILABLE | '受管服务未返回导入结果' |
| 503 | MAGICCLASS_FUSION_UNAVAILABLE | '受管 magic class 服务未启用' |
| 400 | MAGICCLASS_INVALID_REQUEST | '导入请求必须携带 Idempotency-Key' |
| 400 | MAGICCLASS_INVALID_REQUEST | 'Idempotency-Key 过长' |

### `POST /api/v1/courses/{course_id}/workspaces/{workspace_id}/import/pptx`

用途：导入PPTX舞台。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/magicclass_archive.py](../../backend/app/api/routes/magicclass_archive.py)，`import_pptx_stage`。

Web 封装：`importMagicClassPptx`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `course_id` | string | 是 | — | — |
| path | `workspace_id` | string | 是 | — | — |
| header | `Idempotency-Key` | string / null | 否 | — | — |

请求体：`multipart/form-data`，必填；[Body_import_pptx_stage_api_v1_courses__course_id__workspaces__workspace_id__import_pptx_post](schemas.md#schema-body_import_pptx_stage_api_v1_courses__course_id__workspaces__workspace_id__import_pptx_post)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `file` | string (binary) | 是 | format="binary" | — |

上传使用 FormData；字段名按上表；浏览器由运行时生成 multipart boundary。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 201 | application/json | [StageOut](schemas.md#schema-stageout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

201 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `workspace_id` | string | 是 | — | 工作台标识 |
| `course_id` | string | 是 | — | 关联课程标识 |
| `title` | string | 是 | — | 标题 |
| `revision` | integer | 是 | — | 当前版本号，条件写入回传 If-Match |
| `dsl_version` | string | 否 | default="" | — |
| `created_at` | string | 否 | default="" | 创建时间 |
| `updated_at` | string | 否 | default="" | 最近更新时间 |
| `document` | object | 否 | — | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 400 | MAGICCLASS_INVALID_REQUEST | f'PPTX 不能超过 {MAX_PPTX_BYTES} 字节' |
| 400 | MAGICCLASS_INVALID_REQUEST | 'PPTX 文件为空' |
| 503 | MAGICCLASS_FUSION_UNAVAILABLE | '受管服务未返回导入结果' |
| 503 | MAGICCLASS_FUSION_UNAVAILABLE | '受管 magic class 服务未启用' |
| 400 | MAGICCLASS_INVALID_REQUEST | '导入请求必须携带 Idempotency-Key' |
| 400 | MAGICCLASS_INVALID_REQUEST | 'Idempotency-Key 过长' |

### `POST /api/v1/courses/{course_id}/workspaces/{workspace_id}/generate`

用途：生成舞台。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/magicclass_generation.py](../../backend/app/api/routes/magicclass_generation.py)，`generate_stage`。

Web 封装：`generateMagicClassStage`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `course_id` | string | 是 | — | — |
| path | `workspace_id` | string | 是 | — | — |
| header | `Idempotency-Key` | string / null | 否 | — | — |

请求体：`application/json`，必填；[GenerationIn](schemas.md#schema-generationin)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `mode` | string | 是 | minLength=1; maxLength=80 | — |
| `prompt` | string | 是 | minLength=1; maxLength=2000 | — |
| `role_mode` | string | 否 | default="preset"; pattern="^(preset\|auto)$" | — |
| `selected_role_ids` | array<string> | 否 | maxItems=7 | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "mode": "<mode>",
  "prompt": "<prompt>"
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 201 | application/json | 动态响应；见下方补充与 response-contracts.md |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 503 | MAGICCLASS_FUSION_UNAVAILABLE | '课程生成模型当前不可用' |
| 503 | MAGICCLASS_FUSION_UNAVAILABLE | '受管 magic class 服务未启用' |
| 400 | MAGICCLASS_INVALID_REQUEST | '生成请求必须携带有效的 Idempotency-Key' |

### `POST /api/v1/courses/{course_id}/home-generate`

用途：生成home。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/magicclass_generation.py](../../backend/app/api/routes/magicclass_generation.py)，`generate_home`。

Web 封装：`generateMagicClassHome`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

Resolve one course homepage submission into one workspace/job pair.

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `course_id` | string | 是 | — | — |
| header | `Idempotency-Key` | string / null | 否 | — | — |

请求体：`application/json`，必填；[HomeGenerationIn](schemas.md#schema-homegenerationin)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `mode` | string | 否 | default="slide"; minLength=1; maxLength=80 | — |
| `prompt` | string | 是 | minLength=1; maxLength=750 | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "prompt": "<prompt>"
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 201 | application/json | 动态响应；见下方补充与 response-contracts.md |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 503 | MAGICCLASS_FUSION_UNAVAILABLE | '课程生成模型当前不可用' |
| 503 | MAGICCLASS_FUSION_UNAVAILABLE | '受管服务未返回工作台标识' |
| 503 | MAGICCLASS_FUSION_UNAVAILABLE | '受管 magic class 服务未启用' |
| 400 | MAGICCLASS_INVALID_REQUEST | '生成请求必须携带有效的 Idempotency-Key' |

### `GET /api/v1/courses/{course_id}/jobs/{job_id}`

用途：读取任务。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/magicclass_generation.py](../../backend/app/api/routes/magicclass_generation.py)，`get_job`。

Web 封装：`getMagicClassJob`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `course_id` | string | 是 | — | — |
| path | `job_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | 动态响应；见下方补充与 response-contracts.md |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 503 | MAGICCLASS_FUSION_UNAVAILABLE | '受管 magic class 服务未启用' |

### `GET /api/v1/courses/{course_id}/artifacts/{artifact_id}`

用途：读取产物。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/magicclass_generation.py](../../backend/app/api/routes/magicclass_generation.py)，`get_artifact`。

Web 封装：`getMagicClassArtifact`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `course_id` | string | 是 | — | — |
| path | `artifact_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | 实际产物媒体类型 | 文件及 X-Artifact-Sha256 头 |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

实际响应补充：动态对象、透传、文件和流式返回不能由默认 OpenAPI 完整表达；业务字段说明在 [响应补充](response-contracts.md)。下面列出实现中的返回构造式，变量代表运行时值，并非 JSON 示例。

```python
Response(content=content, media_type=media_type, headers={'Content-Disposition': content_disposition(filename, ascii_fallback=ascii_fallback, fallback=fallback), 'Cache-Control': 'no-store', 'X-Artifact-Sha256': str(payload.get('sha256') or '')})
```

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 503 | MAGICCLASS_FUSION_UNAVAILABLE | '受管服务未返回可用产物' |
| 503 | MAGICCLASS_FUSION_UNAVAILABLE | '受管服务返回了不受支持的产物类型' |
| 503 | MAGICCLASS_FUSION_UNAVAILABLE | '受管服务返回的产物无法解码' |
| 503 | MAGICCLASS_FUSION_UNAVAILABLE | '受管 magic class 服务未启用' |

### `POST /api/v1/courses/{course_id}/jobs/{job_id}/cancel`

用途：取消任务。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/magicclass_generation.py](../../backend/app/api/routes/magicclass_generation.py)，`cancel_job`。

Web 封装：`cancelMagicClassJob`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `course_id` | string | 是 | — | — |
| path | `job_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | 动态响应；见下方补充与 response-contracts.md |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 503 | MAGICCLASS_FUSION_UNAVAILABLE | '受管 magic class 服务未启用' |

### `POST /api/v1/courses/{course_id}/jobs/{job_id}/retry`

用途：重试任务。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/magicclass_generation.py](../../backend/app/api/routes/magicclass_generation.py)，`retry_job`。

Web 封装：`retryMagicClassJob`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `course_id` | string | 是 | — | — |
| path | `job_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | 动态响应；见下方补充与 response-contracts.md |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 503 | MAGICCLASS_FUSION_UNAVAILABLE | '受管 magic class 服务未启用' |

### `POST /api/v1/courses/{course_id}/tts`

用途：合成语音。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/magicclass_tts.py](../../backend/app/api/routes/magicclass_tts.py)，`synthesize_speech`。

Web 封装：`synthesizeMagicClassTts`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `course_id` | string | 是 | — | — |
| header | `Idempotency-Key` | string / null | 否 | — | — |

请求体：`application/json`，必填；[TtsIn](schemas.md#schema-ttsin)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `text` | string | 是 | minLength=1; maxLength=20000 | 文本 |
| `instruction` | string / null | 否 | string约束: minLength=1; maxLength=2000 | — |
| `voice` | string / null | 否 | string约束: minLength=1; maxLength=80 | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "text": "<text>"
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 202 | application/json | 动态响应；见下方补充与 response-contracts.md |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 503 | MAGICCLASS_FUSION_UNAVAILABLE | '受管 magic class 服务未启用' |
| 400 | MAGICCLASS_INVALID_REQUEST | '语音合成请求必须携带有效的 Idempotency-Key' |

### `GET /api/v1/courses/{course_id}/workspaces/{workspace_id}/stages/{stage_id}/scenes/{scene_id}/narration`

用途：读取场景讲解。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/magicclass_narration.py](../../backend/app/api/routes/magicclass_narration.py)，`get_scene_narration`。

Web 封装：`getMagicClassSceneNarration`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

Report whether this scene already has narration, and which job owns it.

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `course_id` | string | 是 | — | — |
| path | `workspace_id` | string | 是 | — | — |
| path | `stage_id` | string | 是 | — | — |
| path | `scene_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | 动态响应；见下方补充与 response-contracts.md |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 503 | MAGICCLASS_FUSION_UNAVAILABLE | '受管 magic class 服务未启用' |

### `POST /api/v1/courses/{course_id}/workspaces/{workspace_id}/stages/{stage_id}/scenes/{scene_id}/narration`

用途：合成场景讲解。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/magicclass_narration.py](../../backend/app/api/routes/magicclass_narration.py)，`synthesize_scene_narration`。

Web 封装：`synthesizeMagicClassSceneNarration`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

Enqueue narration for one scene; the audio arrives as an artifact.

Answers 202 with a job reference because synthesis is queued, not inline.
Repeated calls for the same scene reuse the existing job rather than paying
for a second synthesis.

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `course_id` | string | 是 | — | — |
| path | `workspace_id` | string | 是 | — | — |
| path | `stage_id` | string | 是 | — | — |
| path | `scene_id` | string | 是 | — | — |
| header | `Idempotency-Key` | string / null | 否 | — | — |

请求体：`application/json`，必填；[NarrationIn](schemas.md#schema-narrationin)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `scene_id` | string | 是 | minLength=1; maxLength=192 | 场景标识 |
| `stage_id` | string | 是 | minLength=1; maxLength=192 | 舞台标识 |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "scene_id": "<scene_id>",
  "stage_id": "<stage_id>"
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 202 | application/json | 动态响应；见下方补充与 response-contracts.md |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 400 | MAGICCLASS_INVALID_REQUEST | '请求体中的场景标识与路径不一致' |
| 503 | MAGICCLASS_FUSION_UNAVAILABLE | '受管 magic class 服务未启用' |
| 400 | MAGICCLASS_INVALID_REQUEST | '讲解生成请求必须携带有效的 Idempotency-Key' |

### `GET /api/v1/courses/{course_id}/workspaces/{workspace_id}/stages/{stage_id}/scenes/{scene_id}/quiz-attempt`

用途：读取测验作答。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/magicclass_quiz.py](../../backend/app/api/routes/magicclass_quiz.py)，`get_quiz_attempt`。

Web 封装：`getMagicClassQuizAttempt`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `course_id` | string | 是 | — | — |
| path | `workspace_id` | string | 是 | — | — |
| path | `stage_id` | string | 是 | — | — |
| path | `scene_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [QuizAttemptStateOut](schemas.md#schema-quizattemptstateout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `attempt_id` | string | 是 | — | — |
| `state` | object / null | 否 | — | — |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `POST /api/v1/courses/{course_id}/workspaces/{workspace_id}/stages/{stage_id}/scenes/{scene_id}/quiz-attempt`

用途：保存测验作答。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/magicclass_quiz.py](../../backend/app/api/routes/magicclass_quiz.py)，`save_quiz_attempt`。

Web 封装：`saveMagicClassQuizAttempt`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `course_id` | string | 是 | — | — |
| path | `workspace_id` | string | 是 | — | — |
| path | `stage_id` | string | 是 | — | — |
| path | `scene_id` | string | 是 | — | — |

请求体：`application/json`，必填；[QuizAttemptIn](schemas.md#schema-quizattemptin)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `attempt_id` | string | 是 | minLength=1; maxLength=128 | — |
| `phase` | enum ["draft", "submitted", "reviewed"] | 是 | — | — |
| `answers` | map<string, string / array<string>> | 否 | additionalProperties={"anyOf": [{"type": "string"}, {"items": {"type": "string"}, "type": "array"}]} | — |
| `results` | array<object> | 否 | — | — |
| `start_new_attempt` | boolean | 否 | default=false | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "attempt_id": "<attempt_id>",
  "phase": "draft"
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [QuizAttemptStateOut](schemas.md#schema-quizattemptstateout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `attempt_id` | string | 是 | — | — |
| `state` | object / null | 否 | — | — |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `POST /api/v1/courses/{course_id}/discussion`

用途：运行圆桌讨论。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/magicclass_discussion.py](../../backend/app/api/routes/magicclass_discussion.py)，`run_discussion`。

Web 封装：`runMagicClassDiscussion`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `course_id` | string | 是 | — | — |
| header | `Idempotency-Key` | string / null | 否 | — | — |

请求体：`application/json`，必填；[DiscussionIn](schemas.md#schema-discussionin)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `prompt` | string | 是 | minLength=1; maxLength=4000 | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "prompt": "<prompt>"
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 202 | application/json | 动态响应；见下方补充与 response-contracts.md |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 503 | MAGICCLASS_FUSION_UNAVAILABLE | '受管 magic class 服务未启用' |
| 400 | MAGICCLASS_INVALID_REQUEST | '圆桌讨论请求必须携带有效的 Idempotency-Key' |

### `GET /api/v1/magicclass/fusion/providers`

用途：提供方状态。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/magicclass_provider.py](../../backend/app/api/routes/magicclass_provider.py)，`provider_status`。

Web 封装：`getMagicClassProviderStatus`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | 动态响应；见下方补充与 response-contracts.md |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/courses/{course_id}/magicclass-context`

用途：这门课已同步的知识点、章节与可用资料（脱敏，只含标题）。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/magicclass_course_context.py](../../backend/app/api/routes/magicclass_course_context.py)，`get_course_context`。

Web 封装：`getMagicClassCourseContext`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

这门课已同步的知识点、章节与可用资料（脱敏，只含标题）。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `course_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [CourseContextOut](schemas.md#schema-coursecontextout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `course_id` | string | 是 | — | 关联课程标识 |
| `name` | string | 是 | — | 名称 |
| `code` | string | 否 | default="" | — |
| `semester` | string | 否 | default="" | — |
| `description` | string | 否 | default="" | 说明 |
| `knowledge_points` | array<[CourseKnowledgePointOut](schemas.md#schema-courseknowledgepointout)> | 否 | — | — |
| `chapters` | array<string> | 否 | — | — |
| `materials` | array<map<string, string>> | 否 | — | — |
| `sources` | map<string, string> | 否 | additionalProperties={"type": "string"} | — |
| `warnings` | array<string> | 否 | — | 警告列表；成功也需展示降级或缺失数据 |
| `synced` | boolean | 否 | default=false | — |
| `updated_at` | string | 否 | default="" | 最近更新时间 |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/magicclass/learning-space/status`

用途：独立学习空间状态。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/magicclass_learning_space.py](../../backend/app/api/routes/magicclass_learning_space.py)，`learning_space_status`。

Web 封装：`getLearningSpaceStatus`（[webreact/src/data/learningSpaceApi.js](../../webreact/src/data/learningSpaceApi.js)）

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [MagicClassStatusOut](schemas.md#schema-magicclassstatusout) |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `enabled` | boolean | 是 | — | 是否启用 |
| `configured` | boolean | 否 | default=false | — |
| `available` | boolean | 否 | default=false | 当前能力是否可用 |
| `incompatible` | boolean | 否 | default=false | — |
| `degraded` | boolean | 否 | default=false | — |
| `compatibility` | string | 否 | default="unknown" | — |
| `compatibility_reason` | string / null | 否 | — | — |
| `service` | string | 否 | default="magicclass" | — |
| `version` | string | 否 | default="" | — |
| `version_source` | string | 否 | default="unknown" | — |
| `version_out_of_range` | boolean | 否 | default=false | — |
| `capabilities` | map<string, boolean> | 否 | additionalProperties={"type": "boolean"} | — |
| `unavailable_capabilities` | array<string> | 否 | — | — |
| `unavailable` | boolean | 否 | default=false | — |
| `embed_origin` | string / null | 否 | — | — |
| `browser_embed_available` | boolean | 否 | default=false | — |
| `browser_embed_reason` | string / null | 否 | — | — |
| `external_3d_available` | boolean | 否 | default=true | — |
| `poll_interval_ms` | integer | 否 | default=5000 | — |
| `poll_max_seconds` | integer | 否 | default=1800 | — |
| `checked_at` | string | 否 | default="" | — |
| `reason` | string / null | 否 | — | 原因 |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。
