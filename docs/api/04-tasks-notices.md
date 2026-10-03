# 个人待办、通知提取与通知事务

> 对照日期：2026-09-30。本模块共 24 个 HTTP 方法与路径组合；以当前后端注册路由和 Web 调用为依据。

> 2026-10-03 补充：任务响应按真实记录返回 `source/external_id/course_id/source_url/last_synced_at`。计划待办的 `source=learning_plan`，`external_id=<plan_id>:<item_id>`；执行响应直接提供 `execution_task_id`，前端用它完成任务或关联专注会话，详见[计划接口闭环](../world-model-backend.md#前端完整调用顺序)。

[文档导航](README.md) · [接入与流程](integration.md) · [字段字典](schemas.md) · [OpenAPI](openapi.json)

## 接口索引

| 方法 | 完整路径 | 用途 |
| --- | --- | --- |
| GET | `/api/v1/notices` | 校园通知列表 —— 聚合 notices 表和 announcements 表的通知 |
| POST | `/api/v1/notices/extract` | 提取notice |
| POST | `/api/v1/notices/extract-multi` | 多任务抽取 — 自动识别通知中是否包含多个独立任务 |
| POST | `/api/v1/notices/check-duplicate` | 检测当前通知是否可能与最近已存在的通知重复 |
| POST | `/api/v1/notices/ingest` | 接收端侧校园通知并同步到所有客户端可见的通知、待办数据源 |
| POST | `/api/v1/notices/ingest-batch` | 接收noticebatch |
| POST | `/api/v1/notices/manual` | 手动提交通知文本,持久化为服务端 notice_id(§8.3) |
| GET | `/api/v1/notification-sources` | 列出来源 |
| PATCH | `/api/v1/notification-sources/{source_id}` | 修改来源 |
| POST | `/api/v1/notices/{notice_id}/workflow` | 创建通知事务 |
| GET | `/api/v1/notice-workflows/{workflow_id}` | 读取通知事务 |
| POST | `/api/v1/notice-workflows/{workflow_id}/reanalyze` | 重新分析通知事务 |
| POST | `/api/v1/notice-workflow-actions/{action_id}/decision` | 决定事务动作 |
| POST | `/api/v1/notice-workflow-actions/{action_id}/execute` | 执行事务动作 |
| GET | `/api/v1/tasks` | 列出当前用户的个人待办 |
| POST | `/api/v1/tasks` | 创建个人待办 |
| POST | `/api/v1/tasks/import/analyze` | 把学习计划或课程材料转换为可编辑的个人待办草稿 |
| POST | `/api/v1/tasks/import/commit` | 批量保存确认后的草稿；同名任务保留原状态，不覆盖学习进度 |
| GET | `/api/v1/tasks/{task_id}` | 获取个人待办详情。跨用户访问返回 404(不泄露存在性) |
| PATCH | `/api/v1/tasks/{task_id}` | 更新个人待办字段(不允许通过此接口修改 status) |
| POST | `/api/v1/tasks/{task_id}/complete` | 标记任务为已完成(pending → completed) |
| POST | `/api/v1/tasks/{task_id}/restore` | 恢复任务为 pending(completed/deleted → pending) |
| DELETE | `/api/v1/tasks/{task_id}` | 软删除任务(任意状态 → deleted) |
| POST | `/api/v1/tasks/rank-importance` | 批量评定任务重要程度(AI 优先 + 规则降级) |

## 接口契约

### `GET /api/v1/notices`

用途：校园通知列表 —— 聚合 notices 表和 announcements 表的通知。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/notices.py](../../backend/app/api/routes/notices.py)，`list_notices`。

Web 封装：`getNotices`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

校园通知列表 —— 聚合 notices 表和 announcements 表的通知。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| query | `unread_only` | boolean | 否 | default=false | 仅返回未读 |
| query | `page` | integer | 否 | default=1; minimum=1 | — |
| query | `page_size` | integer | 否 | default=50; minimum=1; maximum=200 | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [Page](schemas.md#schema-page)；items 为聚合通知条目，见 response-contracts.md#notices |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `items` | array<any> | 否 | — | 列表条目 |
| `total` | integer | 否 | default=0 | 总数 |
| `page` | integer | 否 | default=1 | 当前页，从 1 开始 |
| `page_size` | integer | 否 | default=20 | 每页数量 |
| `has_more` | boolean | 否 | default=false | 是否还有下一页 |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `POST /api/v1/notices/extract`

用途：提取notice。

鉴权：Bearer access token；已登录用户。

实现：[backend/app/api/routes/notices.py](../../backend/app/api/routes/notices.py)，`extract_notice`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：`application/json`，必填；[NoticeExtractRequest](schemas.md#schema-noticeextractrequest)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `content` | string | 是 | — | 校园通知原文 |
| `published_at` | string (date-time) / null | 否 | string约束: format="date-time" | 通知发布时间(ISO 8601，带时区) |
| `source_name` | string / null | 否 | — | 来源单位/系统名称 |
| `allow_multi_task` | boolean | 否 | default=true | 是否允许拆分为多个任务(默认 True,无法可靠拆分时返回单任务) |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "allow_multi_task": true,
  "content": "请2024级学生于7月30日前填写实践申请表,并将申请表和证明材料提交至学院办公室。",
  "published_at": "2026-07-20T09:00:00+08:00",
  "source_name": "信息工程学院通知"
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [NoticeExtractResponse](schemas.md#schema-noticeextractresponse) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `title` | string | 是 | — | 通知标题/任务名(可为空字符串) |
| `task` | string | 是 | — | 任务名(对齐移动端 taskName) |
| `actionable` | boolean | 否 | default=false | 是否是明确需要学生执行的行动型通知(普通公告为 false) |
| `target_students` | string / null | 否 | — | 面向对象 |
| `deadline` | string (date-time) / null | 否 | string约束: format="date-time" | 截止时间(ISO 8601) |
| `materials` | array<[MaterialItem](schemas.md#schema-materialitem)> | 否 | — | — |
| `submission_method` | string / null | 否 | — | 提交方式 |
| `location` | string / null | 否 | — | 办理地点 |
| `source_name` | string / null | 否 | — | 来源单位 |
| `source_text` | string | 是 | — | 通知原文(便于人工复核) |
| `importance` | string | 否 | default="unknown" | 重要程度: urgent\|high\|important\|normal\|low\|unknown |
| `confidence` | number | 是 | minimum=0.0; maximum=1.0 | 抽取置信度 0~1 |
| `needs_confirmation` | boolean | 是 | — | 是否需要人工确认(年份缺失/对象不明等) |
| `warnings` | array<string> | 否 | — | 需要确认的原因列表(温和提示，非错误) |
| `extracted_at` | string (date-time) | 是 | format="date-time" | 抽取完成时间(ISO 8601) |
| `extractor_mode` | string | 是 | — | 抽取器模式: llm\|rules (便于客户端区分) |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `POST /api/v1/notices/extract-multi`

用途：多任务抽取 — 自动识别通知中是否包含多个独立任务。

鉴权：Bearer access token；已登录用户。

实现：[backend/app/api/routes/notices.py](../../backend/app/api/routes/notices.py)，`extract_notice_multi`。

Web 封装：`extractNotice`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

多任务抽取 — 自动识别通知中是否包含多个独立任务。

- 当识别到 >=2 个独立截止/动作时返回多个任务
- 无法可靠拆分时返回单任务,并标注 split_reason
- needs_user_confirmation=true 时建议用户人工确认拆分结果

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：`application/json`，必填；[NoticeExtractRequest](schemas.md#schema-noticeextractrequest)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `content` | string | 是 | — | 校园通知原文 |
| `published_at` | string (date-time) / null | 否 | string约束: format="date-time" | 通知发布时间(ISO 8601，带时区) |
| `source_name` | string / null | 否 | — | 来源单位/系统名称 |
| `allow_multi_task` | boolean | 否 | default=true | 是否允许拆分为多个任务(默认 True,无法可靠拆分时返回单任务) |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "allow_multi_task": true,
  "content": "请2024级学生于7月30日前填写实践申请表,并将申请表和证明材料提交至学院办公室。",
  "published_at": "2026-07-20T09:00:00+08:00",
  "source_name": "信息工程学院通知"
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [MultiNoticeExtractResponse](schemas.md#schema-multinoticeextractresponse) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `tasks` | array<[NoticeExtractResponse](schemas.md#schema-noticeextractresponse)> | 否 | — | 抽取的任务列表(1 个或多个) |
| `split_reason` | string | 否 | default="" | 拆分说明(如'识别到 2 个独立截止时间'或'合并为单任务') |
| `needs_user_confirmation` | boolean | 否 | default=false | 是否建议用户人工确认拆分结果 |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `POST /api/v1/notices/check-duplicate`

用途：检测当前通知是否可能与最近已存在的通知重复。

鉴权：Bearer access token；已登录用户。

实现：[backend/app/api/routes/notices.py](../../backend/app/api/routes/notices.py)，`check_duplicate`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

检测当前通知是否可能与最近已存在的通知重复。

判定依据:
- 原文内容 hash 一致 → 高度可能重复
- 来源 + 截止 + 任务名 一致 → 可能重复
- 任务名 + 截止 一致 → 可能重复
- 文本 Jaccard 相似度 >= 0.85 → 可能重复

发现重复时只提示,不自动覆盖。
服务端无状态:客户端应将本地已保存的通知列表作为 recent_notices 传入。
若 recent_notices 为空,则返回 is_duplicate=false(无对比基准)。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：`application/json`，必填；[DuplicateNoticeCheckRequest](schemas.md#schema-duplicatenoticecheckrequest)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `content` | string | 是 | — | 通知原文 |
| `source_name` | string / null | 否 | — | 来源名称 |
| `task_name` | string / null | 否 | — | 已抽取的任务名(可选) |
| `deadline` | string (date-time) / null | 否 | string约束: format="date-time" | 已抽取的截止时间(可选) |
| `recent_notices` | array<[RecentNoticeItem](schemas.md#schema-recentnoticeitem)> | 否 | — | 客户端本地已保存的通知列表(用于服务端对比) |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "content": "请2024级学生于7月30日前提交实践申请表...",
  "recent_notices": [
    {
      "deadline": "2026-07-30T23:59:00+08:00",
      "notice_id": "task_001",
      "source_name": "信息工程学院通知",
      "source_text": "请2024级学生于7月30日前提交实践申请表...",
      "title": "提交实践申请表"
    }
  ],
  "source_name": "信息工程学院通知",
  "task_name": "提交实践申请表"
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [DuplicateNoticeCheckResponse](schemas.md#schema-duplicatenoticecheckresponse) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `is_duplicate` | boolean | 是 | — | 是否可能重复 |
| `matches` | array<[DuplicateNoticeMatch](schemas.md#schema-duplicatenoticematch)> | 否 | — | — |
| `content_hash` | string | 是 | — | 当前通知的内容哈希(SHA256) |
| `note` | string | 否 | default="仅提示可能重复,不会自动覆盖原待办。请人工确认后决定是否继续保存。" | 说明文案 |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `POST /api/v1/notices/ingest`

用途：接收端侧校园通知并同步到所有客户端可见的通知、待办数据源。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/notices.py](../../backend/app/api/routes/notices.py)，`ingest_notice`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

接收端侧校园通知并同步到所有客户端可见的通知、待办数据源。

原始通知仅在客户端白名单和本地规则通过后才会到达这里。服务端
以原文 hash 作为通知幂等键，使用多任务抽取，并只自动创建明确
actionable 的待办；低置信度结果仍会保留在统一通知列表供确认。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：`application/json`，必填；[NoticeExtractRequest](schemas.md#schema-noticeextractrequest)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `content` | string | 是 | — | 校园通知原文 |
| `published_at` | string (date-time) / null | 否 | string约束: format="date-time" | 通知发布时间(ISO 8601，带时区) |
| `source_name` | string / null | 否 | — | 来源单位/系统名称 |
| `allow_multi_task` | boolean | 否 | default=true | 是否允许拆分为多个任务(默认 True,无法可靠拆分时返回单任务) |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "allow_multi_task": true,
  "content": "请2024级学生于7月30日前填写实践申请表,并将申请表和证明材料提交至学院办公室。",
  "published_at": "2026-07-20T09:00:00+08:00",
  "source_name": "信息工程学院通知"
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [MultiNoticeExtractResponse](schemas.md#schema-multinoticeextractresponse) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `tasks` | array<[NoticeExtractResponse](schemas.md#schema-noticeextractresponse)> | 否 | — | 抽取的任务列表(1 个或多个) |
| `split_reason` | string | 否 | default="" | 拆分说明(如'识别到 2 个独立截止时间'或'合并为单任务') |
| `needs_user_confirmation` | boolean | 否 | default=false | 是否建议用户人工确认拆分结果 |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `POST /api/v1/notices/ingest-batch`

用途：接收noticebatch。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/notices.py](../../backend/app/api/routes/notices.py)，`ingest_notice_batch`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：`application/json`，必填；[NoticeBatchIngestRequest](schemas.md#schema-noticebatchingestrequest)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `items` | array<[NoticeBatchItem](schemas.md#schema-noticebatchitem)> | 是 | minItems=1; maxItems=20 | 列表条目 |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "items": [
    {
      "client_id": "<client_id>",
      "client_fingerprint": "<client_fingerprint>",
      "source_name": "<source_name>",
      "messages": [
        {
          "text": "<text>"
        }
      ]
    }
  ]
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [NoticeBatchIngestResponse](schemas.md#schema-noticebatchingestresponse) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `items` | array<[NoticeBatchItemResult](schemas.md#schema-noticebatchitemresult)> | 否 | — | 列表条目 |
| `stats` | map<string, integer> | 否 | additionalProperties={"type": "integer"} | — |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `POST /api/v1/notices/manual`

用途：手动提交通知文本,持久化为服务端 notice_id(§8.3)。

鉴权：Bearer access token；角色 student（不包含历史 teacher 账号）。

实现：[backend/app/api/routes/notices.py](../../backend/app/api/routes/notices.py)，`create_manual_notice`。

Web 封装：`createManualNotice`（[webreact/src/data/agentApi.js](../../webreact/src/data/agentApi.js)）；`createManualNotice`（[webreact/src/data/agentRuntimeApi.js](../../webreact/src/data/agentRuntimeApi.js)）

手动提交通知文本,持久化为服务端 notice_id(§8.3)。

先把粘贴文本写入 notices 表,返回 notice_id,客户端再调用
POST /notices/{notice_id}/workflow 创建工作流。同内容幂等返回。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| header | `Idempotency-Key` | string / null | 否 | — | — |

请求体：`application/json`，必填；[ManualNoticeIn](schemas.md#schema-manualnoticein)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `title` | string | 是 | minLength=1; maxLength=256 | 标题 |
| `content` | string | 是 | minLength=1; maxLength=5000 | 正文或业务内容，嵌套结构按类型 |
| `source_name` | string / null | 否 | string约束: maxLength=64 | — |
| `idempotency_key` | string / null | 否 | string约束: minLength=1; maxLength=128 | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "title": "<title>",
  "content": "<content>"
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [ManualNoticeOut](schemas.md#schema-manualnoticeout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `notice_id` | string | 是 | minLength=1; maxLength=64 | — |
| `title` | string | 是 | maxLength=256 | 标题 |
| `duplicate` | boolean | 否 | default=false | — |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/notification-sources`

用途：列出来源。

鉴权：Bearer access token；角色 student（不包含历史 teacher 账号）。

实现：[backend/app/api/routes/notice_workflows.py](../../backend/app/api/routes/notice_workflows.py)，`list_sources`。

Web 封装：`getNotificationSources`（[webreact/src/data/agentRuntimeApi.js](../../webreact/src/data/agentRuntimeApi.js)）

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | array<[NotificationSourceOut](schemas.md#schema-notificationsourceout)> |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `PATCH /api/v1/notification-sources/{source_id}`

用途：修改来源。

鉴权：Bearer access token；角色 student（不包含历史 teacher 账号）。

实现：[backend/app/api/routes/notice_workflows.py](../../backend/app/api/routes/notice_workflows.py)，`patch_source`。

Web 封装：`updateNotificationSource`（[webreact/src/data/agentRuntimeApi.js](../../webreact/src/data/agentRuntimeApi.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `source_id` | string | 是 | — | — |

请求体：`application/json`，必填；[NotificationSourcePatchIn](schemas.md#schema-notificationsourcepatchin)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `automation_enabled` | boolean / null | 否 | — | — |
| `display_name` | string / null | 否 | string约束: maxLength=128 | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [NotificationSourceOut](schemas.md#schema-notificationsourceout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `source_id` | string | 是 | minLength=1; maxLength=64 | — |
| `code` | string | 是 | minLength=1; maxLength=64 | — |
| `display_name` | string | 是 | maxLength=128 | — |
| `kind` | string | 是 | maxLength=32 | — |
| `automation_enabled` | boolean | 否 | default=false | — |
| `permission_scope` | string / null | 否 | string约束: maxLength=256 | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | WORKFLOW_NOT_FOUND | '通知来源不存在' |

### `POST /api/v1/notices/{notice_id}/workflow`

用途：创建通知事务。

鉴权：Bearer access token；角色 student（不包含历史 teacher 账号）。

实现：[backend/app/api/routes/notice_workflows.py](../../backend/app/api/routes/notice_workflows.py)，`create_workflow`。

Web 封装：`analyzeNotice`（[webreact/src/data/agentApi.js](../../webreact/src/data/agentApi.js)）；`createNoticeWorkflow`（[webreact/src/data/agentRuntimeApi.js](../../webreact/src/data/agentRuntimeApi.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `notice_id` | string | 是 | — | — |
| header | `Idempotency-Key` | string / null | 否 | — | — |

请求体：`application/json`，必填；[WorkflowCreateIn](schemas.md#schema-workflowcreatein)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `idempotency_key` | string / null | 否 | string约束: minLength=1; maxLength=128 | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [WorkflowOut](schemas.md#schema-workflowout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `workflow_id` | string | 是 | minLength=1; maxLength=64 | — |
| `user_id` | string | 是 | minLength=1; maxLength=64 | 所属用户标识 |
| `notice_id` | string | 是 | minLength=1; maxLength=64 | — |
| `source_id` | string / null | 否 | string约束: maxLength=64 | — |
| `status` | string | 是 | maxLength=24 | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `title` | string / null | 否 | string约束: maxLength=256 | 标题 |
| `deadline` | string / null | 否 | string约束: maxLength=64 | 截止时间 |
| `location` | string / null | 否 | string约束: maxLength=256 | — |
| `audience` | string / null | 否 | string约束: maxLength=256 | — |
| `materials` | array<string> | 否 | — | — |
| `steps` | array<[WorkflowStepOut](schemas.md#schema-workflowstepout)> | 否 | — | — |
| `source_evidence` | array<string> | 否 | — | — |
| `confidence` | number | 是 | minimum=0.0; maximum=1.0 | — |
| `uncertainty` | array<string> | 否 | — | — |
| `error_code` | string / null | 否 | string约束: maxLength=64 | 失败码，可空 |
| `error_message` | string / null | 否 | string约束: maxLength=256 | — |
| `created_at` | string | 是 | minLength=1; maxLength=64 | 创建时间 |
| `updated_at` | string | 是 | minLength=1; maxLength=64 | 最近更新时间 |
| `actions` | array<[WorkflowActionOut](schemas.md#schema-workflowactionout)> | 否 | — | — |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/notice-workflows/{workflow_id}`

用途：读取通知事务。

鉴权：Bearer access token；角色 student（不包含历史 teacher 账号）。

实现：[backend/app/api/routes/notice_workflows.py](../../backend/app/api/routes/notice_workflows.py)，`get_workflow`。

Web 封装：`getNoticeWorkflow`（[webreact/src/data/agentRuntimeApi.js](../../webreact/src/data/agentRuntimeApi.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `workflow_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [WorkflowOut](schemas.md#schema-workflowout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `workflow_id` | string | 是 | minLength=1; maxLength=64 | — |
| `user_id` | string | 是 | minLength=1; maxLength=64 | 所属用户标识 |
| `notice_id` | string | 是 | minLength=1; maxLength=64 | — |
| `source_id` | string / null | 否 | string约束: maxLength=64 | — |
| `status` | string | 是 | maxLength=24 | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `title` | string / null | 否 | string约束: maxLength=256 | 标题 |
| `deadline` | string / null | 否 | string约束: maxLength=64 | 截止时间 |
| `location` | string / null | 否 | string约束: maxLength=256 | — |
| `audience` | string / null | 否 | string约束: maxLength=256 | — |
| `materials` | array<string> | 否 | — | — |
| `steps` | array<[WorkflowStepOut](schemas.md#schema-workflowstepout)> | 否 | — | — |
| `source_evidence` | array<string> | 否 | — | — |
| `confidence` | number | 是 | minimum=0.0; maximum=1.0 | — |
| `uncertainty` | array<string> | 否 | — | — |
| `error_code` | string / null | 否 | string约束: maxLength=64 | 失败码，可空 |
| `error_message` | string / null | 否 | string约束: maxLength=256 | — |
| `created_at` | string | 是 | minLength=1; maxLength=64 | 创建时间 |
| `updated_at` | string | 是 | minLength=1; maxLength=64 | 最近更新时间 |
| `actions` | array<[WorkflowActionOut](schemas.md#schema-workflowactionout)> | 否 | — | — |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `POST /api/v1/notice-workflows/{workflow_id}/reanalyze`

用途：重新分析通知事务。

鉴权：Bearer access token；角色 student（不包含历史 teacher 账号）。

实现：[backend/app/api/routes/notice_workflows.py](../../backend/app/api/routes/notice_workflows.py)，`reanalyze_workflow`。

Web 封装：`reanalyzeNoticeWorkflow`（[webreact/src/data/agentRuntimeApi.js](../../webreact/src/data/agentRuntimeApi.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `workflow_id` | string | 是 | — | — |
| header | `Idempotency-Key` | string / null | 否 | — | — |

请求体：`application/json`，必填；[WorkflowReanalyzeIn](schemas.md#schema-workflowreanalyzein)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `idempotency_key` | string / null | 否 | string约束: minLength=1; maxLength=128 | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [WorkflowOut](schemas.md#schema-workflowout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `workflow_id` | string | 是 | minLength=1; maxLength=64 | — |
| `user_id` | string | 是 | minLength=1; maxLength=64 | 所属用户标识 |
| `notice_id` | string | 是 | minLength=1; maxLength=64 | — |
| `source_id` | string / null | 否 | string约束: maxLength=64 | — |
| `status` | string | 是 | maxLength=24 | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `title` | string / null | 否 | string约束: maxLength=256 | 标题 |
| `deadline` | string / null | 否 | string约束: maxLength=64 | 截止时间 |
| `location` | string / null | 否 | string约束: maxLength=256 | — |
| `audience` | string / null | 否 | string约束: maxLength=256 | — |
| `materials` | array<string> | 否 | — | — |
| `steps` | array<[WorkflowStepOut](schemas.md#schema-workflowstepout)> | 否 | — | — |
| `source_evidence` | array<string> | 否 | — | — |
| `confidence` | number | 是 | minimum=0.0; maximum=1.0 | — |
| `uncertainty` | array<string> | 否 | — | — |
| `error_code` | string / null | 否 | string约束: maxLength=64 | 失败码，可空 |
| `error_message` | string / null | 否 | string约束: maxLength=256 | — |
| `created_at` | string | 是 | minLength=1; maxLength=64 | 创建时间 |
| `updated_at` | string | 是 | minLength=1; maxLength=64 | 最近更新时间 |
| `actions` | array<[WorkflowActionOut](schemas.md#schema-workflowactionout)> | 否 | — | — |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `POST /api/v1/notice-workflow-actions/{action_id}/decision`

用途：决定事务动作。

鉴权：Bearer access token；角色 student（不包含历史 teacher 账号）。

实现：[backend/app/api/routes/notice_workflows.py](../../backend/app/api/routes/notice_workflows.py)，`decide_action`。

Web 封装：`decideNoticeWorkflowAction`（[webreact/src/data/agentRuntimeApi.js](../../webreact/src/data/agentRuntimeApi.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `action_id` | string | 是 | — | — |
| header | `Idempotency-Key` | string / null | 否 | — | — |

请求体：`application/json`，必填；[ActionDecisionIn](schemas.md#schema-actiondecisionin)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `decision` | string | 是 | pattern="^(APPROVED\|REJECTED)$" | 用户决定，严格按枚举大小写 |
| `reason` | string / null | 否 | string约束: maxLength=256 | 原因 |
| `idempotency_key` | string / null | 否 | string约束: minLength=1; maxLength=128 | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "decision": "<decision>"
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [WorkflowActionOut](schemas.md#schema-workflowactionout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `action_id` | string | 是 | minLength=1; maxLength=64 | — |
| `workflow_id` | string | 是 | minLength=1; maxLength=64 | — |
| `action_type` | string | 是 | maxLength=64 | — |
| `title` | string | 是 | maxLength=256 | 标题 |
| `risk_level` | [RiskLevel](schemas.md#schema-risklevel) | 是 | — | — |
| `status` | string | 是 | maxLength=16 | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `external_ref` | string / null | 否 | string约束: maxLength=128 | — |
| `expires_at` | string / null | 否 | string约束: maxLength=64 | — |
| `error_code` | string / null | 否 | string约束: maxLength=64 | 失败码，可空 |
| `error_message` | string / null | 否 | string约束: maxLength=256 | — |
| `created_at` | string | 是 | minLength=1; maxLength=64 | 创建时间 |
| `updated_at` | string | 是 | minLength=1; maxLength=64 | 最近更新时间 |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `POST /api/v1/notice-workflow-actions/{action_id}/execute`

用途：执行事务动作。

鉴权：Bearer access token；角色 student（不包含历史 teacher 账号）。

实现：[backend/app/api/routes/notice_workflows.py](../../backend/app/api/routes/notice_workflows.py)，`execute_action`。

Web 封装：`executeNoticeWorkflowAction`（[webreact/src/data/agentRuntimeApi.js](../../webreact/src/data/agentRuntimeApi.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `action_id` | string | 是 | — | — |
| header | `Idempotency-Key` | string / null | 否 | — | — |

请求体：`application/json`，必填；[ActionExecuteIn](schemas.md#schema-actionexecutein)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `idempotency_key` | string / null | 否 | string约束: minLength=1; maxLength=128 | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [ActionResultOut](schemas.md#schema-actionresultout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `action_id` | string | 是 | minLength=1; maxLength=64 | — |
| `status` | string | 是 | maxLength=16 | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `external_ref` | string / null | 否 | string约束: maxLength=128 | — |
| `result` | object / null | 否 | — | — |
| `error_code` | string / null | 否 | string约束: maxLength=64 | 失败码，可空 |
| `error_message` | string / null | 否 | string约束: maxLength=256 | — |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/tasks`

用途：列出当前用户的个人待办。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/personal_tasks.py](../../backend/app/api/routes/personal_tasks.py)，`list_personal_tasks`。

Web 封装：`getTasks`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

列出当前用户的个人待办。

- 默认不返回 `deleted` 状态(除非 `include_deleted=true` 或显式 `status=deleted`)
- 支持按 status/priority/deadline 筛选

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| query | `status` | string / null | 否 | string约束: pattern="^(pending\|completed\|deleted)$" | — |
| query | `priority` | string / null | 否 | string约束: pattern="^(low\|medium\|high)$" | — |
| query | `deadline_before` | string / null | 否 | — | — |
| query | `deadline_after` | string / null | 否 | — | — |
| query | `include_deleted` | boolean | 否 | default=false | — |
| query | `page` | integer | 否 | default=1; minimum=1 | — |
| query | `page_size` | integer | 否 | default=50; minimum=1; maximum=200 | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [Page](schemas.md#schema-page)；items 元素为 [PersonalTaskOut](schemas.md#schema-personaltaskout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `items` | array<any> | 否 | — | 列表条目 |
| `total` | integer | 否 | default=0 | 总数 |
| `page` | integer | 否 | default=1 | 当前页，从 1 开始 |
| `page_size` | integer | 否 | default=20 | 每页数量 |
| `has_more` | boolean | 否 | default=false | 是否还有下一页 |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `POST /api/v1/tasks`

用途：创建个人待办。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/personal_tasks.py](../../backend/app/api/routes/personal_tasks.py)，`create_personal_task`。

Web 封装：`createTask`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

创建个人待办。

`source_text` 建议保留(用于原文追溯)。`user_id` 由 JWT 注入,客户端不传。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：`application/json`，必填；[PersonalTaskCreate](schemas.md#schema-personaltaskcreate)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `title` | string | 是 | minLength=1; maxLength=256 | 标题 |
| `description` | string / null | 否 | string约束: maxLength=4000 | 说明 |
| `target_students` | string / null | 否 | string约束: maxLength=512 | 通知面向对象(如 '2024级各班') |
| `deadline` | string / null | 否 | — | ISO 8601 截止时间(带时区) |
| `materials` | array<string> / null | 否 | array约束: maxItems=50 | 所需材料名称列表 |
| `submission_method` | string / null | 否 | string约束: maxLength=256 | — |
| `location` | string / null | 否 | string约束: maxLength=256 | — |
| `source_name` | string / null | 否 | string约束: maxLength=256 | 通知来源(如 '教务处') |
| `source_text` | string / null | 否 | string约束: maxLength=10000 | 原通知全文(用于追溯) |
| `source_notice_id` | string / null | 否 | string约束: maxLength=128 | 关联通知 ID(可为空) |
| `priority` | string | 否 | default="medium"; pattern="^(low\|medium\|high)$" | — |
| `importance` | string / null | 否 | default="unknown"; string约束: pattern="^(urgent\|high\|important\|normal\|low\|unknown)$" | AI 评定的重要程度标签(交作业=high,填表=low) |
| `reminder_minutes` | integer / null | 否 | integer约束: minimum=0.0; maximum=43200.0 | 提前提醒分钟数(0 表示按 deadline 精确触发) |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "title": "<title>"
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 201 | application/json | [PersonalTaskOut](schemas.md#schema-personaltaskout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

201 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `user_id` | string | 是 | — | 所属用户标识 |
| `title` | string | 是 | — | 标题 |
| `description` | string / null | 否 | — | 说明 |
| `target_students` | string / null | 否 | — | — |
| `deadline` | string / null | 否 | — | 截止时间 |
| `materials` | array<string> | 否 | — | — |
| `submission_method` | string / null | 否 | — | — |
| `location` | string / null | 否 | — | — |
| `source_name` | string / null | 否 | — | — |
| `source_text` | string / null | 否 | — | — |
| `source_notice_id` | string / null | 否 | — | — |
| `priority` | string | 是 | — | — |
| `importance` | string | 否 | default="unknown" | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `reminder_minutes` | integer / null | 否 | — | — |
| `source` | string / null | 否 | — | 来源 |
| `external_id` | string / null | 否 | — | — |
| `course_id` | string / null | 否 | — | 关联课程标识 |
| `source_url` | string / null | 否 | — | 来源链接 |
| `last_synced_at` | string / null | 否 | — | — |
| `created_at` | string | 是 | — | 创建时间 |
| `updated_at` | string | 是 | — | 最近更新时间 |
| `completed_at` | string / null | 否 | — | — |
| `deleted_at` | string / null | 否 | — | — |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `POST /api/v1/tasks/import/analyze`

用途：把学习计划或课程材料转换为可编辑的个人待办草稿。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/personal_tasks.py](../../backend/app/api/routes/personal_tasks.py)，`analyze_task_import`。

Web 封装：`analyzeTaskImport`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

把学习计划或课程材料转换为可编辑的个人待办草稿。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：`application/json`，必填；[TaskImportAnalyzeRequest](schemas.md#schema-taskimportanalyzerequest)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `content` | string | 是 | minLength=1; maxLength=20000 | 正文或业务内容，嵌套结构按类型 |
| `source_name` | string / null | 否 | string约束: maxLength=256 | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "content": "<content>"
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [TaskImportAnalyzeResponse](schemas.md#schema-taskimportanalyzeresponse) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `mode` | string | 是 | pattern="^(structured_text\|llm\|rules)$" | — |
| `split_reason` | string | 否 | default="" | — |
| `needs_user_confirmation` | boolean | 否 | default=false | — |
| `tasks` | array<[TaskImportDraft](schemas.md#schema-taskimportdraft)> | 否 | — | — |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `POST /api/v1/tasks/import/commit`

用途：批量保存确认后的草稿；同名任务保留原状态，不覆盖学习进度。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/personal_tasks.py](../../backend/app/api/routes/personal_tasks.py)，`commit_task_import`。

Web 封装：`commitTaskImport`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

批量保存确认后的草稿；同名任务保留原状态，不覆盖学习进度。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：`application/json`，必填；[TaskImportCommitRequest](schemas.md#schema-taskimportcommitrequest)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `tasks` | array<[TaskImportCommitItem](schemas.md#schema-taskimportcommititem)> | 是 | minItems=1; maxItems=50 | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "tasks": [
    {
      "title": "<title>"
    }
  ]
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 201 | application/json | [TaskImportCommitResponse](schemas.md#schema-taskimportcommitresponse) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

201 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `created` | array<[PersonalTaskOut](schemas.md#schema-personaltaskout)> | 否 | — | — |
| `skipped_existing` | array<[TaskImportExisting](schemas.md#schema-taskimportexisting)> | 否 | — | — |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/tasks/{task_id}`

用途：获取个人待办详情。跨用户访问返回 404(不泄露存在性)。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/personal_tasks.py](../../backend/app/api/routes/personal_tasks.py)，`get_personal_task`。

Web 封装：`getTask`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

获取个人待办详情。跨用户访问返回 404(不泄露存在性)。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `task_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [PersonalTaskOut](schemas.md#schema-personaltaskout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `user_id` | string | 是 | — | 所属用户标识 |
| `title` | string | 是 | — | 标题 |
| `description` | string / null | 否 | — | 说明 |
| `target_students` | string / null | 否 | — | — |
| `deadline` | string / null | 否 | — | 截止时间 |
| `materials` | array<string> | 否 | — | — |
| `submission_method` | string / null | 否 | — | — |
| `location` | string / null | 否 | — | — |
| `source_name` | string / null | 否 | — | — |
| `source_text` | string / null | 否 | — | — |
| `source_notice_id` | string / null | 否 | — | — |
| `priority` | string | 是 | — | — |
| `importance` | string | 否 | default="unknown" | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `reminder_minutes` | integer / null | 否 | — | — |
| `source` | string / null | 否 | — | 来源 |
| `external_id` | string / null | 否 | — | — |
| `course_id` | string / null | 否 | — | 关联课程标识 |
| `source_url` | string / null | 否 | — | 来源链接 |
| `last_synced_at` | string / null | 否 | — | — |
| `created_at` | string | 是 | — | 创建时间 |
| `updated_at` | string | 是 | — | 最近更新时间 |
| `completed_at` | string / null | 否 | — | — |
| `deleted_at` | string / null | 否 | — | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | PERSONAL_TASK_NOT_FOUND | 个人待办不存在。 |

### `PATCH /api/v1/tasks/{task_id}`

用途：更新个人待办字段(不允许通过此接口修改 status)。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/personal_tasks.py](../../backend/app/api/routes/personal_tasks.py)，`update_personal_task`。

Web 封装：`updateTask`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

更新个人待办字段(不允许通过此接口修改 status)。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `task_id` | string | 是 | — | — |

请求体：`application/json`，必填；[PersonalTaskUpdate](schemas.md#schema-personaltaskupdate)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `title` | string / null | 否 | string约束: minLength=1; maxLength=256 | 标题 |
| `description` | string / null | 否 | string约束: maxLength=4000 | 说明 |
| `target_students` | string / null | 否 | string约束: maxLength=512 | — |
| `deadline` | string / null | 否 | — | 截止时间 |
| `materials` | array<string> / null | 否 | array约束: maxItems=50 | — |
| `submission_method` | string / null | 否 | string约束: maxLength=256 | — |
| `location` | string / null | 否 | string约束: maxLength=256 | — |
| `source_name` | string / null | 否 | string约束: maxLength=256 | — |
| `source_text` | string / null | 否 | string约束: maxLength=10000 | — |
| `source_notice_id` | string / null | 否 | string约束: maxLength=128 | — |
| `priority` | string / null | 否 | string约束: pattern="^(low\|medium\|high)$" | — |
| `importance` | string / null | 否 | string约束: pattern="^(urgent\|high\|important\|normal\|low\|unknown)$" | — |
| `reminder_minutes` | integer / null | 否 | integer约束: minimum=0.0; maximum=43200.0 | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [PersonalTaskOut](schemas.md#schema-personaltaskout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `user_id` | string | 是 | — | 所属用户标识 |
| `title` | string | 是 | — | 标题 |
| `description` | string / null | 否 | — | 说明 |
| `target_students` | string / null | 否 | — | — |
| `deadline` | string / null | 否 | — | 截止时间 |
| `materials` | array<string> | 否 | — | — |
| `submission_method` | string / null | 否 | — | — |
| `location` | string / null | 否 | — | — |
| `source_name` | string / null | 否 | — | — |
| `source_text` | string / null | 否 | — | — |
| `source_notice_id` | string / null | 否 | — | — |
| `priority` | string | 是 | — | — |
| `importance` | string | 否 | default="unknown" | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `reminder_minutes` | integer / null | 否 | — | — |
| `source` | string / null | 否 | — | 来源 |
| `external_id` | string / null | 否 | — | — |
| `course_id` | string / null | 否 | — | 关联课程标识 |
| `source_url` | string / null | 否 | — | 来源链接 |
| `last_synced_at` | string / null | 否 | — | — |
| `created_at` | string | 是 | — | 创建时间 |
| `updated_at` | string | 是 | — | 最近更新时间 |
| `completed_at` | string / null | 否 | — | — |
| `deleted_at` | string / null | 否 | — | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | PERSONAL_TASK_NOT_FOUND | 个人待办不存在。 |
| 409 | PERSONAL_TASK_CONFLICT | '已删除的任务不能修改,请先恢复' |
| 409 | PERSONAL_TASK_CONFLICT | '学习通作业/考试的状态由学习通决定，请到课程详情查看原始任务' |

### `POST /api/v1/tasks/{task_id}/complete`

用途：标记任务为已完成(pending → completed)。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/personal_tasks.py](../../backend/app/api/routes/personal_tasks.py)，`complete_personal_task`。

Web 封装：`completeTask`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

标记任务为已完成(pending → completed)。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `task_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [PersonalTaskOut](schemas.md#schema-personaltaskout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `user_id` | string | 是 | — | 所属用户标识 |
| `title` | string | 是 | — | 标题 |
| `description` | string / null | 否 | — | 说明 |
| `target_students` | string / null | 否 | — | — |
| `deadline` | string / null | 否 | — | 截止时间 |
| `materials` | array<string> | 否 | — | — |
| `submission_method` | string / null | 否 | — | — |
| `location` | string / null | 否 | — | — |
| `source_name` | string / null | 否 | — | — |
| `source_text` | string / null | 否 | — | — |
| `source_notice_id` | string / null | 否 | — | — |
| `priority` | string | 是 | — | — |
| `importance` | string | 否 | default="unknown" | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `reminder_minutes` | integer / null | 否 | — | — |
| `source` | string / null | 否 | — | 来源 |
| `external_id` | string / null | 否 | — | — |
| `course_id` | string / null | 否 | — | 关联课程标识 |
| `source_url` | string / null | 否 | — | 来源链接 |
| `last_synced_at` | string / null | 否 | — | — |
| `created_at` | string | 是 | — | 创建时间 |
| `updated_at` | string | 是 | — | 最近更新时间 |
| `completed_at` | string / null | 否 | — | — |
| `deleted_at` | string / null | 否 | — | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | PERSONAL_TASK_NOT_FOUND | 个人待办不存在。 |
| 409 | PERSONAL_TASK_CONFLICT | '已删除的任务不能完成,请先恢复' |
| 409 | PERSONAL_TASK_CONFLICT | '当前状态不允许完成' |
| 409 | PERSONAL_TASK_CONFLICT | '学习通作业/考试的状态由学习通决定，请到课程详情查看原始任务' |

### `POST /api/v1/tasks/{task_id}/restore`

用途：恢复任务为 pending(completed/deleted → pending)。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/personal_tasks.py](../../backend/app/api/routes/personal_tasks.py)，`restore_personal_task`。

Web 封装：`completeTask`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

恢复任务为 pending(completed/deleted → pending)。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `task_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [PersonalTaskOut](schemas.md#schema-personaltaskout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `user_id` | string | 是 | — | 所属用户标识 |
| `title` | string | 是 | — | 标题 |
| `description` | string / null | 否 | — | 说明 |
| `target_students` | string / null | 否 | — | — |
| `deadline` | string / null | 否 | — | 截止时间 |
| `materials` | array<string> | 否 | — | — |
| `submission_method` | string / null | 否 | — | — |
| `location` | string / null | 否 | — | — |
| `source_name` | string / null | 否 | — | — |
| `source_text` | string / null | 否 | — | — |
| `source_notice_id` | string / null | 否 | — | — |
| `priority` | string | 是 | — | — |
| `importance` | string | 否 | default="unknown" | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `reminder_minutes` | integer / null | 否 | — | — |
| `source` | string / null | 否 | — | 来源 |
| `external_id` | string / null | 否 | — | — |
| `course_id` | string / null | 否 | — | 关联课程标识 |
| `source_url` | string / null | 否 | — | 来源链接 |
| `last_synced_at` | string / null | 否 | — | — |
| `created_at` | string | 是 | — | 创建时间 |
| `updated_at` | string | 是 | — | 最近更新时间 |
| `completed_at` | string / null | 否 | — | — |
| `deleted_at` | string / null | 否 | — | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | PERSONAL_TASK_NOT_FOUND | 个人待办不存在。 |
| 409 | PERSONAL_TASK_CONFLICT | '当前状态不允许恢复' |
| 409 | PERSONAL_TASK_CONFLICT | '学习通作业/考试的状态由学习通决定，请到课程详情查看原始任务' |

### `DELETE /api/v1/tasks/{task_id}`

用途：软删除任务(任意状态 → deleted)。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/personal_tasks.py](../../backend/app/api/routes/personal_tasks.py)，`delete_personal_task`。

Web 封装：`deleteTask`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

软删除任务(任意状态 → deleted)。

物理删除由后续清理任务执行(本轮不实现)。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `task_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [PersonalTaskOut](schemas.md#schema-personaltaskout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `user_id` | string | 是 | — | 所属用户标识 |
| `title` | string | 是 | — | 标题 |
| `description` | string / null | 否 | — | 说明 |
| `target_students` | string / null | 否 | — | — |
| `deadline` | string / null | 否 | — | 截止时间 |
| `materials` | array<string> | 否 | — | — |
| `submission_method` | string / null | 否 | — | — |
| `location` | string / null | 否 | — | — |
| `source_name` | string / null | 否 | — | — |
| `source_text` | string / null | 否 | — | — |
| `source_notice_id` | string / null | 否 | — | — |
| `priority` | string | 是 | — | — |
| `importance` | string | 否 | default="unknown" | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `reminder_minutes` | integer / null | 否 | — | — |
| `source` | string / null | 否 | — | 来源 |
| `external_id` | string / null | 否 | — | — |
| `course_id` | string / null | 否 | — | 关联课程标识 |
| `source_url` | string / null | 否 | — | 来源链接 |
| `last_synced_at` | string / null | 否 | — | — |
| `created_at` | string | 是 | — | 创建时间 |
| `updated_at` | string | 是 | — | 最近更新时间 |
| `completed_at` | string / null | 否 | — | — |
| `deleted_at` | string / null | 否 | — | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | PERSONAL_TASK_NOT_FOUND | 个人待办不存在。 |
| 409 | PERSONAL_TASK_CONFLICT | '当前状态不允许删除' |

### `POST /api/v1/tasks/rank-importance`

用途：批量评定任务重要程度(AI 优先 + 规则降级)。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/personal_tasks.py](../../backend/app/api/routes/personal_tasks.py)，`rank_importance`。

Web 封装：`rankTasks`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

批量评定任务重要程度(AI 优先 + 规则降级)。

- 不传 task_ids 时，评定当前用户所有 pending 任务(最多 50 条)
- 传 task_ids 时，评定指定任务(跨用户或不存在的自动跳过)
- 评定结果写回任务的 importance 字段

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：`application/json`，必填；[ImportanceRankRequest](schemas.md#schema-importancerankrequest)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `task_ids` | array<string> / null | 否 | array约束: maxItems=50 | 指定任务 ID 列表(为空则评定全部 pending 任务) |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [ImportanceRankResponse](schemas.md#schema-importancerankresponse) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `updated` | array<[ImportanceRankItem](schemas.md#schema-importancerankitem)> | 否 | — | — |
| `skipped` | array<string> | 否 | — | 跳过的任务 ID(LLM 不可用或任务不存在) |
| `mode` | string | 是 | — | 本次评定实际使用模式: llm\|rules |
| `total` | integer | 否 | default=0 | 本次评定任务数 |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。
