# 课程互动课堂、受管工作台与学习空间入口

> 对照日期：2026-10-05。本模块共 68 个 HTTP 方法与路径组合；以当前后端注册路由和 Web 调用为依据。

[文档导航](README.md) · [接入与流程](integration.md) · [字段字典](schemas.md) · [OpenAPI](openapi.json)

## 测验并发保存与冲突

`GET` / `POST /api/v1/courses/{course_id}/workspaces/{workspace_id}/stages/{stage_id}/scenes/{scene_id}/quiz-attempt` 继续要求已登录且有课程访问权限。POST 对已有作答的课堂归属及 `draft → submitted → reviewed` 阶段进行校验；原子读写覆盖重试 ID 分配，并发重试不会相互覆盖。

状态回退或试图把已有作答移到另一课堂时返回 HTTP 409 `QUIZ_ATTEMPT_CONFLICT`，使用统一错误信封；原 `{detail: ...}` 冲突响应已替换。客户端应回读 GET 获取当前作答，不能把 409 当作成功保存。

```json
{"code":"QUIZ_ATTEMPT_CONFLICT","message":"测验状态不能回退或更改所属课堂","details":null,"request_id":"req_example"}
```

成功响应、`start_new_attempt` 和根作答 ID 规则保持兼容。Web 保存封装使用通用 HTTP 错误流程，源码已核对，无需修改成功字段；专门的冲突提示尚未验证，Android、HarmonyOS、微信小程序没有在本次运行测验流程或原生构建。

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
| GET | `/api/v1/magicclass/learning-space/identity` | 当前账号 UID 与显示名 |
| GET | `/api/v1/magicclass/learning-space/students/{uid}` | 按 UID 校验邀请对象（仅 UID、显示名） |
| GET | `/api/v1/magicclass/learning-space/rooms` | 已加入的共同课堂 |
| POST | `/api/v1/magicclass/learning-space/rooms` | 上传完整课件并创建共同课堂 |
| GET | `/api/v1/magicclass/learning-space/invitations` | 待接受的邀请 |
| POST | `/api/v1/magicclass/learning-space/rooms/{room_id}/invitations` | 发起人按 UID 邀请同学 |
| POST | `/api/v1/magicclass/learning-space/invitations/{room_id}/accept` | 接受邀请 |
| POST | `/api/v1/magicclass/learning-space/invitations/{room_id}/decline` | 拒绝邀请 |
| GET | `/api/v1/magicclass/learning-space/rooms/{room_id}` | 成员、课程及共享页码 |
| GET | `/api/v1/magicclass/learning-space/rooms/{room_id}/archive` | 成员下载同一份课件 |
| PATCH | `/api/v1/magicclass/learning-space/rooms/{room_id}/cursor` | 发起人更新共享页码 |
| GET | `/api/v1/magicclass/learning-space/rooms/{room_id}/messages` | 按消息 ID 增量读取交流记录 |
| POST | `/api/v1/magicclass/learning-space/rooms/{room_id}/messages` | 发送文字消息 |
| POST | `/api/v1/magicclass/learning-space/rooms/{room_id}/leave` | 离开课堂；发起人操作时结束课堂 |

共同课堂接口均要求 Bearer 登录。UID 复用账号已有的唯一 `id`，注册、登录和个人信息响应同步提供 `uid` 字段。创建课堂用 multipart 的 `title`、`stage_id`、`file` 上传 `.maic.zip`（最多 64 MB）；邀请用 `{ "uid": "usr_…" }`。未接受邀请的用户不能读取课件、成员或消息。翻页用 `{ "scene_index": 0 }`；消息用 `{ "content": "一起讨论", "client_id": "客户端生成的唯一 ID" }`，同一成员在同一课堂重复提交同一个 `client_id` 不会重复写入。消息读取接受 `after`（默认 0），每次最多返回 100 条，按服务端 ID 升序排列。每位发起人最多保留 20 个活动课堂，每个课堂最多 8 位已加入或待接受的成员。

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
| 409 | application/json | `QUIZ_ATTEMPT_CONFLICT`；测验状态回退或课堂归属冲突，回读当前作答后再决定操作 |
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

<a id="learning-rooms"></a>
## 共同课堂协议与接入

以下 14 个接口属于 CampusMate 后端，统一使用 Bearer access token；路径不能改为 iframe 独立 Origin 的 /api。实现为 [learning_rooms.py](../../backend/app/api/routes/learning_rooms.py) 与 [LearningRoomRepository](../../backend/app/repositories/learning_room_repository.py)，Web 封装见 [learningRoomApi.js](../../webreact/src/data/learningRoomApi.js)。

权限按账号 UID 与课堂成员关系校验，不要求与发起人同校或预先选择学校；历史 teacher/admin 账号按普通学生身份参与。发起人创建后自动成为 accepted 成员；待接受邀请的用户不能读取课堂、课件或消息。每位发起人最多保留 20 个活动课堂；每个课堂的 pending 与 accepted 成员合计最多 8 人，包含发起人。

所有动态成功对象的完整字段、列表顺序和数据类型见[共同课堂响应](response-contracts.md#learning-rooms)。共同错误包括认证失败 401 `UNAUTHORIZED`、请求模型校验失败 422 `VALIDATION_FAILED`，及以下成员/状态错误：

| HTTP | code | 触发条件与处理 |
| --- | --- | --- |
| 404 | LEARNING_ROOM_ERROR | 课堂不存在、不是 accepted 成员，或邀请失效；回到课堂/邀请列表 |
| 403 | LEARNING_ROOM_ERROR | 已接受邀请的成员执行发起人专用操作 |
| 409 | LEARNING_ROOM_ERROR | 活动课堂数或成员数达到上限；已加入后尝试拒绝邀请 |
| 410 | LEARNING_ROOM_ERROR | 成员仍为 accepted，但课堂已结束；停止轮询 |
| 422 | LEARNING_ROOM_ERROR | 邀请自己或场景索引超出课件范围 |

发起人结束课堂会同时清空归档并将所有成员置为 left，因此后续访问通常返回 404；客户端不能只处理 410。其余接口特有错误列在各节，body.request_id 可用于问题追踪。

接入顺序：读取本人 identity → 上传完整课件创建课堂 → 按 UID 校验并邀请同学 → 对方读取 invitations 并接受 → 双方读取课堂与 archive → 发起人更新 cursor、成员轮询 room/messages → 主动 leave。客户端保存自己已读取的最大消息 id 作为 after；满 100 条时继续读取，避免遗漏后续消息。本协议使用 HTTP 轮询，没有 SSE 或 WebSocket。消息重试复用 client_id，新的消息必须使用新的 client_id；创建课堂没有幂等键，重复提交会创建新课堂。

Web 已有上述调用封装；Android、HarmonyOS、微信小程序在本次审查中未接入该共同课堂协议，须按本文独立适配，原生构建与真机流程未验证。

### `GET /api/v1/magicclass/learning-space/identity`

用途：取得本人 UID 与显示名；只要求登录，没有额外参数或请求体。成功返回 200 Identity。

Web 封装：`getLearningIdentity`（[webreact/src/data/learningRoomApi.js](../../webreact/src/data/learningRoomApi.js)）

脱敏响应：`{"uid":"usr_host_example","name":"同学甲"}`。

### `GET /api/v1/magicclass/learning-space/students/{uid}`

用途：校验邀请对象。path 参数 uid 为账号唯一 ID，服务端去除首尾空白；没有请求体。目标必须存在且启用，历史角色按普通学生处理。成功返回 200 Identity，只暴露 UID 和显示名。

Web 封装：`findLearningStudent`（[webreact/src/data/learningRoomApi.js](../../webreact/src/data/learningRoomApi.js)）

例如读取 /students/usr_guest_example，响应 `{"uid":"usr_guest_example","name":"同学乙"}`。目标不存在或停用返回 404 `STUDENT_UID_NOT_FOUND`；本人 UID 返回 422 `INVALID_INVITATION`。该预检不替代邀请时的权限和有效性校验。

### `GET /api/v1/magicclass/learning-space/rooms`

用途：取得本人已加入且活动的课堂。没有 query 参数或请求体，不包含仅收到邀请的课堂。成功返回 200 `{items:RoomSummary[]}`，最多 100 条，按创建时间降序，无分页参数。

Web 封装：`listLearningRooms`（[webreact/src/data/learningRoomApi.js](../../webreact/src/data/learningRoomApi.js)）

脱敏响应：`{"items":[{"id":"room_example","title":"共同复习","host_uid":"usr_host_example","created_at":"2026-10-05T00:00:00+00:00"}]}`。

### `POST /api/v1/magicclass/learning-space/rooms`

用途：上传完整课件并创建课堂。`multipart/form-data` 请求的 title、stage_id、file 均必填，见[创建表单](schemas.md#schema-body-create-room-api-v1-magicclass-learning-space-rooms-post)。title 长度 1–200，stage_id 长度 1–128；服务端去除首尾空白。file 最大 64 MB，文件名与 MIME 不是验证依据。

归档必须包含 JSON manifest.json，其 stage 为对象、scenes 为 1–1000 个对象，且每个场景的 content 为对象。归档最多 10000 个条目，声明的解压后大小合计最多 256 MB，manifest.json 最多 4 MB。客户端应在课件完整生成后上传已有 .maic.zip。

Web 封装：`createLearningRoom`（[webreact/src/data/learningRoomApi.js](../../webreact/src/data/learningRoomApi.js)）

示例表单：title=共同复习、stage_id=stage_example、file=完整课堂.maic.zip 的二进制文件。成功返回 201 RoomRecord，例如：

```json
{"id":"room_example","title":"共同复习","stage_id":"stage_example","host_uid":"usr_host_example","scene_index":0,"scene_count":2,"active":1,"created_at":"2026-10-05T00:00:00+00:00","members":[{"uid":"usr_host_example","name":"同学甲","status":"accepted"}]}
```

上传超限返回 413 `CLASSROOM_ARCHIVE_TOO_LARGE`；无效或解压后过大的归档返回 422 `INVALID_CLASSROOM_ARCHIVE`；全空白 title/stage_id 返回 422 `INTERNAL_ERROR`（现有实现的错误码）；20 个活动课堂上限返回 409 `LEARNING_ROOM_ERROR`。没有 Idempotency-Key 语义，超时后应先回读 rooms 确认，再决定重试。

### `GET /api/v1/magicclass/learning-space/invitations`

用途：读取本人待接受邀请。没有参数或请求体；只列出活动课堂且发起人账号启用的邀请。成功返回 200 `{items:InvitationRecord[]}`，最多 100 条，按更新时间降序，不提供分页参数。

Web 封装：`listLearningInvitations`（[webreact/src/data/learningRoomApi.js](../../webreact/src/data/learningRoomApi.js)）

脱敏响应：`{"items":[{"room_id":"room_example","title":"共同复习","host_uid":"usr_host_example","host_name":"同学甲","updated_at":"2026-10-05T00:00:00+00:00"}]}`。

### `POST /api/v1/magicclass/learning-space/rooms/{room_id}/invitations`

用途：发起人邀请同学。path 参数 room_id 为课堂 ID；JSON body 见 [InvitationIn](schemas.md#schema-invitationin)，例如 `{"uid":"usr_guest_example"}`。uid 必填，长度 1–128，去除首尾空白后不能为空。

Web 封装：`inviteLearningStudent`（[webreact/src/data/learningRoomApi.js](../../webreact/src/data/learningRoomApi.js)）

目标必须存在、启用且不是本人。成功返回 200，例如 `{"uid":"usr_guest_example","status":"pending"}`。重复邀请 pending/accepted 成员返回原状态，不占新名额；declined/left 成员可重新邀请。不存在的目标使用 404 `LEARNING_ROOM_ERROR`，与 students 预检的错误码不同；本人 UID 使用 422 `LEARNING_ROOM_ERROR`。其他权限与 8 人上限见共同错误表。

### `POST /api/v1/magicclass/learning-space/invitations/{room_id}/accept`

用途：本人接受有效邀请。path 参数 room_id 必填，没有请求体；仅本人 pending/accepted 成员关系可操作。成功返回 200 RoomRecord，字段与创建课堂的示例一致。

Web 封装：`acceptLearningInvitation`（[webreact/src/data/learningRoomApi.js](../../webreact/src/data/learningRoomApi.js)）

重复接受已加入的活动课堂可返回同一课堂；拒绝后或发起人结束后再接受返回 404 `LEARNING_ROOM_ERROR`，不能据此进入归档下载流程。

### `POST /api/v1/magicclass/learning-space/invitations/{room_id}/decline`

用途：本人拒绝待接受邀请。path 参数 room_id 必填，没有请求体。成功返回 204，无响应体。

Web 封装：`declineLearningInvitation`（[webreact/src/data/learningRoomApi.js](../../webreact/src/data/learningRoomApi.js)）

邀请不存在、已拒绝或失效返回 404 `LEARNING_ROOM_ERROR`；已经 accepted 时返回 409 `LEARNING_ROOM_ERROR`，须使用 leave。客户端不能将此接口当作可重复成功的删除操作。

### `GET /api/v1/magicclass/learning-space/rooms/{room_id}`

用途：accepted 成员读取活动课堂、共享页码和成员。path 参数 room_id 必填，没有请求体。成功返回 200 RoomRecord，字段与创建示例一致；members 只包含 pending/accepted 成员。

Web 封装：`getLearningRoom`（[webreact/src/data/learningRoomApi.js](../../webreact/src/data/learningRoomApi.js)）

成员可轮询 scene_index 决定是否跟随发起人翻页，pending 邀请不能读取本接口。成员状态与结束错误见共同错误表。

### `GET /api/v1/magicclass/learning-space/rooms/{room_id}/archive`

用途：accepted 成员下载创建时的完整课件。path 参数 room_id 必填，没有请求体。成功为 200 `application/zip` 和 `Cache-Control: no-store`，响应体是二进制归档，未设置 Content-Disposition。

Web 封装：`getLearningArchive`（[webreact/src/data/learningRoomApi.js](../../webreact/src/data/learningRoomApi.js)）

客户端按 Blob/二进制读取 .maic.zip，不可用 JSON 解析；失败时仍按统一 JSON 错误信封处理。无成员权限或已离开通常返回 404 `LEARNING_ROOM_ERROR`。

### `PATCH /api/v1/magicclass/learning-space/rooms/{room_id}/cursor`

用途：发起人更新共享场景索引。path 参数 room_id 必填；JSON body 见 [CursorIn](schemas.md#schema-cursorin)，例如 `{"scene_index":1}`。scene_index 必须是 0 起的非负整数，并小于当前 scene_count。成功返回 204，无响应体；重复写同一索引保持同一值。

Web 封装：`setLearningCursor`（[webreact/src/data/learningRoomApi.js](../../webreact/src/data/learningRoomApi.js)）

普通 accepted 成员返回 403 `LEARNING_ROOM_ERROR`；索引超过课件范围返回 422 `LEARNING_ROOM_ERROR`，模型类型或非负约束不合法则是 422 `VALIDATION_FAILED`。

### `GET /api/v1/magicclass/learning-space/rooms/{room_id}/messages`

用途：accepted 成员增量读取消息。path 参数 room_id 必填；query after 为非负整数，默认 0，仅返回消息 id > after 的记录。成功返回 200 `{items:MessageRecord[]}`，按 id 升序最多 100 条。

Web 封装：`getLearningMessages`（[webreact/src/data/learningRoomApi.js](../../webreact/src/data/learningRoomApi.js)）

脱敏响应：`{"items":[{"id":1,"uid":"usr_guest_example","name":"同学乙","content":"一起看第二页","created_at":"2026-10-05T00:00:00+00:00"}]}`。下一次将 after 设为最大已收 id；客户端按 id 去重。空列表仅表示暂无更新，没有实时通道或总量字段。

### `POST /api/v1/magicclass/learning-space/rooms/{room_id}/messages`

用途：accepted 成员发送文字消息。path 参数 room_id 必填；JSON body 见 [MessageIn](schemas.md#schema-messagein)，例如 `{"content":"一起看第二页","client_id":"msg_example"}`。content 长度 1–2000，去除首尾空白后不能为空；client_id 长度 1–128，不做自动 trim。

Web 封装：`sendLearningMessage`（[webreact/src/data/learningRoomApi.js](../../webreact/src/data/learningRoomApi.js)）

成功返回 201，例如 `{"id":1,"content":"一起看第二页","created_at":"2026-10-05T00:00:00+00:00"}`。同一成员、同一课堂的 client_id 去重；重试用同一 ID 返回原内容，即使新的 content 不同也不会覆盖。新消息使用新 ID。空白或超长正文返回 422 `VALIDATION_FAILED`。

### `POST /api/v1/magicclass/learning-space/rooms/{room_id}/leave`

用途：accepted 成员主动离开。path 参数 room_id 必填，没有请求体。成功返回 204，无响应体。普通成员离开后不能再读取课件或消息，但发起人可重新邀请；发起人离开会结束整个课堂、清空共享归档、将全部成员置为 left。

Web 封装：`leaveLearningRoom`（[webreact/src/data/learningRoomApi.js](../../webreact/src/data/learningRoomApi.js)）

其他成员随后应停止轮询。重复离开通常返回 404 `LEARNING_ROOM_ERROR`；邀请列表与活动课堂列表不再包含已结束课堂。
