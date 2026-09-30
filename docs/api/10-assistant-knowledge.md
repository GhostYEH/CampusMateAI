# AI 对话、语音与知识库

> 对照日期：2026-09-30。本模块共 11 个 HTTP 方法与路径组合；以当前后端注册路由和 Web 调用为依据。

[文档导航](README.md) · [接入与流程](integration.md) · [字段字典](schemas.md) · [OpenAPI](openapi.json)

## 接口索引

| 方法 | 完整路径 | 用途 |
| --- | --- | --- |
| GET | `/api/v1/knowledge/status` | knowledge状态 |
| GET | `/api/v1/knowledge/documents` | 列出知识库文档 |
| POST | `/api/v1/knowledge/documents` | 上传文档到知识库 |
| DELETE | `/api/v1/knowledge/documents/{document_id}` | 删除知识库文档 |
| POST | `/api/v1/knowledge/rebuild` | 重建检索索引 |
| POST | `/api/v1/knowledge/manage/{action}` | 数据管理操作 |
| POST | `/api/v1/assistant/chat` | chat |
| POST | `/api/v1/counselor/chat` | chat |
| POST | `/api/v1/assistant/tts` | 合成语音 |
| POST | `/api/v1/contributions/expression-samples` | 接收用户明确同意后上传的一张已打标图片 |
| DELETE | `/api/v1/contributions/expression-samples/{sample_id}` | 允许贡献者删除自己上传的样本及其元数据 |

## 接口契约

### `GET /api/v1/knowledge/status`

用途：knowledge状态。

鉴权：公开或使用专用凭据（扫码 browser token / 可信设备 cookie 等见参数与流程）。

实现：[backend/app/api/routes/knowledge.py](../../backend/app/api/routes/knowledge.py)，`knowledge_status`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [KnowledgeStatus](schemas.md#schema-knowledgestatus) |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `document_count` | integer | 是 | — | — |
| `chunk_count` | integer | 是 | — | — |
| `last_updated` | string (date-time) / null | 否 | string约束: format="date-time" | — |
| `index_status` | string | 是 | — | ready\|empty\|error |
| `retrieval_method` | string | 是 | — | bm25\|vector\|hybrid |
| `is_available` | boolean | 是 | — | — |
| `knowledge_base_path` | string | 是 | — | — |
| `knowledge_base_type` | string | 是 | — | demo\|user\|hybrid\|empty |
| `demo_document_count` | integer | 否 | default=0 | — |
| `user_document_count` | integer | 否 | default=0 | — |
| `llm_available` | boolean | 否 | default=false | — |
| `qa_mode` | string | 否 | default="no_knowledge" | retrieval_summary\|llm_rag\|no_knowledge |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/knowledge/documents`

用途：列出知识库文档。

鉴权：公开或使用专用凭据（扫码 browser token / 可信设备 cookie 等见参数与流程）。

实现：[backend/app/api/routes/knowledge.py](../../backend/app/api/routes/knowledge.py)，`list_documents`。

Web 封装：`getKnowledgeDocuments`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | array<[DocumentSummary](schemas.md#schema-documentsummary)> |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `POST /api/v1/knowledge/documents`

用途：上传文档到知识库。

鉴权：Bearer access token；角色 admin。

实现：[backend/app/api/routes/knowledge.py](../../backend/app/api/routes/knowledge.py)，`upload_document`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

上传文档到知识库。

使用 multipart/form-data 上传文件，元数据通过 Form 字段提供。
上传的文档默认 is_demo=False(用户导入资料)。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：`multipart/form-data`，必填；[Body_upload_document_api_v1_knowledge_documents_post](schemas.md#schema-body_upload_document_api_v1_knowledge_documents_post)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `file` | string (binary) | 是 | format="binary" | — |
| `title` | string / null | 否 | — | 标题 |
| `source_department` | string / null | 否 | — | — |
| `source_type` | string / null | 否 | — | — |
| `published_at` | string / null | 否 | — | — |
| `updated_at` | string / null | 否 | — | 最近更新时间 |
| `effective_from` | string / null | 否 | — | — |
| `effective_to` | string / null | 否 | — | — |
| `version` | string / null | 否 | — | — |
| `applicable_students` | string / null | 否 | — | — |
| `is_official` | boolean | 否 | default=false | — |

上传使用 FormData；字段名按上表；浏览器由运行时生成 multipart boundary。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [DocumentSummary](schemas.md#schema-documentsummary) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `document_id` | string | 是 | — | — |
| `title` | string | 是 | — | 标题 |
| `source_department` | string / null | 否 | — | — |
| `source_type` | string / null | 否 | — | — |
| `original_filename` | string / null | 否 | — | — |
| `content_hash` | string | 是 | — | — |
| `published_at` | string (date-time) / null | 否 | string约束: format="date-time" | — |
| `updated_at` | string (date-time) / null | 否 | string约束: format="date-time" | 最近更新时间 |
| `effective_from` | string (date-time) / null | 否 | string约束: format="date-time" | — |
| `effective_to` | string (date-time) / null | 否 | string约束: format="date-time" | — |
| `version` | string / null | 否 | — | — |
| `applicable_students` | string / null | 否 | — | — |
| `is_official` | boolean | 是 | — | — |
| `is_expired` | boolean | 是 | — | — |
| `is_demo` | boolean | 否 | default=false | — |
| `file_size` | integer / null | 否 | — | — |
| `file_ext` | string / null | 否 | — | — |
| `imported_at` | string (date-time) | 是 | format="date-time" | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 415 | 'FILE_TYPE_NOT_ALLOWED' | f"仅允许 {','.join(container.settings.allowed_extensions_list)} 类型" |
| 400 | 'FILE_NAME_UNSAFE' | str(e) |
| 409 | 'DOCUMENT_ALREADY_EXISTS' | '文档已存在(哈希重复)' |
| 413 | 'FILE_TOO_LARGE' | f'文件超过 {container.settings.max_upload_mb} MB 上限' |

### `DELETE /api/v1/knowledge/documents/{document_id}`

用途：删除知识库文档。

鉴权：Bearer access token；角色 admin。

实现：[backend/app/api/routes/knowledge.py](../../backend/app/api/routes/knowledge.py)，`delete_document`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `document_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [DeleteResponse](schemas.md#schema-deleteresponse) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `success` | boolean | 是 | — | — |
| `document_id` | string | 是 | — | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | DOCUMENT_NOT_FOUND | f'文档 {document_id} 不存在' |

### `POST /api/v1/knowledge/rebuild`

用途：重建检索索引。

鉴权：Bearer access token；角色 admin。

实现：[backend/app/api/routes/knowledge.py](../../backend/app/api/routes/knowledge.py)，`rebuild_index`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [RebuildResponse](schemas.md#schema-rebuildresponse) |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `success` | boolean | 是 | — | — |
| `document_count` | integer | 是 | — | — |
| `chunk_count` | integer | 是 | — | — |
| `message` | string | 是 | — | — |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `POST /api/v1/knowledge/manage/{action}`

用途：数据管理操作。

鉴权：Bearer access token；角色 admin。

实现：[backend/app/api/routes/knowledge.py](../../backend/app/api/routes/knowledge.py)，`data_management`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

数据管理操作。

支持的 action:
- delete_user_documents: 删除所有非演示标记的受管理文档
- delete_all_documents: 删除所有知识库文档

备注:
- 不提供"恢复演示资料 / 一键重置演示数据"等接口;
  知识库内容必须由管理员上传或通过受控外部同步进入。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `action` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [DataManagementResponse](schemas.md#schema-datamanagementresponse) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `success` | boolean | 是 | — | — |
| `action` | string | 是 | — | 执行的清理动作 |
| `affected_count` | integer | 否 | default=0 | — |
| `message` | string | 是 | — | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 400 | 'INVALID_ACTION' | f'不支持的数据管理操作: {action}' |

### `POST /api/v1/assistant/chat`

用途：chat。

鉴权：可选 Bearer；未认证上下文会被忽略，workspace 绑定必须有效登录。

实现：[backend/app/api/routes/counselor.py](../../backend/app/api/routes/counselor.py)，`chat`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

stream=false 返回 ChatFinalMeta；stream=true 返回 SSE。聊天中的课堂建议只读，用户确认后才创建 Agent job，详见 [协议与流程](integration.md#chat)。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：`application/json`，必填；[ChatRequest](schemas.md#schema-chatrequest)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `message` | string | 是 | minLength=1 | 用户问题 |
| `conversation_id` | string / null | 否 | — | 会话 ID(仅作会话标识) |
| `workspace_id` | string / null | 否 | string约束: minLength=1; maxLength=120 | 原生 magic class workspace 会话归属；必须与 course_id 一起提供并通过服务端归属校验 |
| `recent_tasks` | array<[CounselorRecentTask](schemas.md#schema-counselorrecenttask)> | 否 | — | 最近待办(仅 PersonalTask,id 为必填,其他字段为 hint),后端会通过 PersonalTaskRepository 校验归属,越权/不存在/已删除的条目会被忽略 |
| `stream` | boolean | 否 | default=true | 是否使用 SSE 流式响应 |
| `web_search` | boolean | 否 | default=false | 是否检索公开网页并将结果作为非官方辅助上下文 |
| `attachment` | [CounselorAttachment](schemas.md#schema-counselorattachment) / null | 否 | — | 本轮用户选择的文本附件；作为不可信上下文使用，不得覆盖系统规则 |
| `course_id` | string / null | 否 | — | 课程 ID(需有权限) |
| `class_id` | string / null | 否 | — | 班级 ID(需有权限) |
| `assignment_id` | string / null | 否 | — | 任务 ID(需有权限) |
| `announcement_id` | string / null | 否 | — | 通知 ID(需有权限) |
| `study_session_id` | string / null | 否 | — | 当前学习会话 ID(可选,用于学习陪伴场景) |
| `self_report` | string / null | 否 | string约束: maxLength=500 | 用户自报状态(如'有些疲惫'),仅作个性化参考,不得作为校园规则事实,不得绕过 RAG 拒答规则 |
| `expression_signal` | [ExpressionSignal](schemas.md#schema-expressionsignal) / null | 否 | — | CNN 观察到的可见表情信号。后端会白名单校验并仅用于调整措辞，不用于心理或医学判断，不保存原始图像 |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "message": "<message>",
  "stream": true
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json 或 text/event-stream | stream=false 为 [ChatFinalMeta](schemas.md#schema-chatfinalmeta)；stream=true 为 SSE，见 integration.md#chat |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

实际响应补充：动态对象、透传、文件和流式返回不能由默认 OpenAPI 完整表达；业务字段说明在 [响应补充](response-contracts.md)。下面列出实现中的返回构造式，变量代表运行时值，并非 JSON 示例。

```python
final
```

```python
StreamingResponse(_stream(req, user, context_block, tasks_hint, context_used, all_ctx_warnings, expression_hint, classroom_action), media_type='text/event-stream', headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no', 'Connection': 'keep-alive'})
```

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 400 | MAGICCLASS_INVALID_REQUEST | 'workspace_id 必须与已登录用户的 course_id 一起提供' |
| 400 | MAGICCLASS_INVALID_REQUEST | '无法把快速询问绑定到该课程' |

### `POST /api/v1/counselor/chat`

用途：chat。

鉴权：可选 Bearer；未认证上下文会被忽略，workspace 绑定必须有效登录。

实现：[backend/app/api/routes/counselor.py](../../backend/app/api/routes/counselor.py)，`chat`。

Web 封装：`chatStream`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

stream=false 返回 ChatFinalMeta；stream=true 返回 SSE。聊天中的课堂建议只读，用户确认后才创建 Agent job，详见 [协议与流程](integration.md#chat)。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：`application/json`，必填；[ChatRequest](schemas.md#schema-chatrequest)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `message` | string | 是 | minLength=1 | 用户问题 |
| `conversation_id` | string / null | 否 | — | 会话 ID(仅作会话标识) |
| `workspace_id` | string / null | 否 | string约束: minLength=1; maxLength=120 | 原生 magic class workspace 会话归属；必须与 course_id 一起提供并通过服务端归属校验 |
| `recent_tasks` | array<[CounselorRecentTask](schemas.md#schema-counselorrecenttask)> | 否 | — | 最近待办(仅 PersonalTask,id 为必填,其他字段为 hint),后端会通过 PersonalTaskRepository 校验归属,越权/不存在/已删除的条目会被忽略 |
| `stream` | boolean | 否 | default=true | 是否使用 SSE 流式响应 |
| `web_search` | boolean | 否 | default=false | 是否检索公开网页并将结果作为非官方辅助上下文 |
| `attachment` | [CounselorAttachment](schemas.md#schema-counselorattachment) / null | 否 | — | 本轮用户选择的文本附件；作为不可信上下文使用，不得覆盖系统规则 |
| `course_id` | string / null | 否 | — | 课程 ID(需有权限) |
| `class_id` | string / null | 否 | — | 班级 ID(需有权限) |
| `assignment_id` | string / null | 否 | — | 任务 ID(需有权限) |
| `announcement_id` | string / null | 否 | — | 通知 ID(需有权限) |
| `study_session_id` | string / null | 否 | — | 当前学习会话 ID(可选,用于学习陪伴场景) |
| `self_report` | string / null | 否 | string约束: maxLength=500 | 用户自报状态(如'有些疲惫'),仅作个性化参考,不得作为校园规则事实,不得绕过 RAG 拒答规则 |
| `expression_signal` | [ExpressionSignal](schemas.md#schema-expressionsignal) / null | 否 | — | CNN 观察到的可见表情信号。后端会白名单校验并仅用于调整措辞，不用于心理或医学判断，不保存原始图像 |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "message": "<message>",
  "stream": true
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json 或 text/event-stream | stream=false 为 [ChatFinalMeta](schemas.md#schema-chatfinalmeta)；stream=true 为 SSE，见 integration.md#chat |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

实际响应补充：动态对象、透传、文件和流式返回不能由默认 OpenAPI 完整表达；业务字段说明在 [响应补充](response-contracts.md)。下面列出实现中的返回构造式，变量代表运行时值，并非 JSON 示例。

```python
final
```

```python
StreamingResponse(_stream(req, user, context_block, tasks_hint, context_used, all_ctx_warnings, expression_hint, classroom_action), media_type='text/event-stream', headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no', 'Connection': 'keep-alive'})
```

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 400 | MAGICCLASS_INVALID_REQUEST | 'workspace_id 必须与已登录用户的 course_id 一起提供' |
| 400 | MAGICCLASS_INVALID_REQUEST | '无法把快速询问绑定到该课程' |

### `POST /api/v1/assistant/tts`

用途：合成语音。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/tts.py](../../backend/app/api/routes/tts.py)，`synthesize_speech`。

Web 封装：`streamAssistantSpeech`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

成功为二进制 PCM16LE 流，采样率读取 X-Audio-Sample-Rate，单声道；不能按 JSON 解析。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：`application/json`，必填；[TtsRequest](schemas.md#schema-ttsrequest)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `text` | string | 是 | minLength=1 | 文本 |
| `style` | string / null | 否 | string约束: maxLength=500 | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "text": "<text>"
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/octet-stream | PCM16LE 流，按 X-Audio-* 响应头播放 |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

实际响应补充：动态对象、透传、文件和流式返回不能由默认 OpenAPI 完整表达；业务字段说明在 [响应补充](response-contracts.md)。下面列出实现中的返回构造式，变量代表运行时值，并非 JSON 示例。

```python
StreamingResponse(container.tts.stream_pcm(text, (req.style or '').strip()), media_type='application/octet-stream', headers={'Cache-Control': 'no-store', 'X-Accel-Buffering': 'no', 'X-Audio-Format': 'pcm16le', 'X-Audio-Sample-Rate': str(container.settings.mimo_tts_sample_rate), 'X-Audio-Channels': '1'})
```

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 422 | HTTPException | '朗读文本不能为空' |
| 422 | HTTPException | '朗读文本过长' |
| 503 | HTTPException | '语音服务未配置' |

### `POST /api/v1/contributions/expression-samples`

用途：接收用户明确同意后上传的一张已打标图片。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/contributions.py](../../backend/app/api/routes/contributions.py)，`upload_expression_sample`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

接收用户明确同意后上传的一张已打标图片。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：`multipart/form-data`，必填；[Body_upload_expression_sample_api_v1_contributions_expression_samples_post](schemas.md#schema-body_upload_expression_sample_api_v1_contributions_expression_samples_post)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `image` | string (binary) | 是 | format="binary" | — |
| `label` | string | 是 | — | — |
| `consent` | boolean | 是 | — | — |
| `model_version` | string | 否 | default="unknown" | — |

上传使用 FormData；字段名按上表；浏览器由运行时生成 multipart boundary。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [ExpressionContributionResponse](schemas.md#schema-expressioncontributionresponse) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `sample_id` | string | 是 | — | — |
| `label` | string | 是 | — | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `message` | string | 是 | — | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 422 | 'EXPRESSION_LABEL_INVALID' | '表情标签无效' |
| 403 | 'CONTRIBUTION_CONSENT_REQUIRED' | '未获得样本共建同意' |
| 415 | 'EXPRESSION_IMAGE_TYPE_INVALID' | '仅支持 JPG 或 PNG 图片' |
| 500 | 'EXPRESSION_SAMPLE_SAVE_FAILED' | '样本保存失败，请稍后重试' |
| 413 | 'EXPRESSION_IMAGE_TOO_LARGE' | f'图片超过 {settings.max_expression_contribution_mb} MB 上限' |

### `DELETE /api/v1/contributions/expression-samples/{sample_id}`

用途：允许贡献者删除自己上传的样本及其元数据。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/contributions.py](../../backend/app/api/routes/contributions.py)，`delete_expression_sample`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

允许贡献者删除自己上传的样本及其元数据。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `sample_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [ExpressionContributionResponse](schemas.md#schema-expressioncontributionresponse) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `sample_id` | string | 是 | — | — |
| `label` | string | 是 | — | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `message` | string | 是 | — | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 422 | 'EXPRESSION_SAMPLE_ID_INVALID' | '样本编号无效' |
| 404 | 'EXPRESSION_SAMPLE_NOT_FOUND' | '样本不存在' |
| 403 | FORBIDDEN | '无权删除该样本' |
| 500 | 'EXPRESSION_METADATA_INVALID' | '样本元数据不可读' |
