# CampusMate AI 后端 API 契约

> 版本: v1 · 统一前缀 `/api/v1` · 默认端口 `8000`
>
> 本文件与 [`backend/app/schemas/`](../backend/app/schemas/) 中的 Pydantic 模型保持一致;
> 字段含义、枚举值、错误码、SSE 事件格式均以本文为准。
>
> Flutter 客户端实现在 [`lib/data/services/api/`](../lib/data/services/api/) 中,
> JSON 字段名与本文一一对应。

---

## 目录

- [通用约定](#通用约定)
- [1. 健康检查 Health](#1-健康检查-health)
- [2. 通知结构化抽取 Notices](#2-通知结构化抽取-notices)
- [3. 知识库 Knowledge](#3-知识库-knowledge)
- [4. AI 导员 Counselor](#4-ai-导员-counselor)
- [错误码](#错误码)
- [SSE 事件格式](#sse-事件格式)
- [枚举对照表](#枚举对照表)
- [数据模型对照表](#数据模型对照表)

---

## 通用约定

### Base URL

```
http://{host}:{port}/api/v1
```

- 本机调试: `http://localhost:8000/api/v1`
- Android 模拟器: `http://10.0.2.2:8000/api/v1`
- 真机(同 Wi-Fi): `http://192.168.x.x:8000/api/v1`

### 时间格式

所有时间字段使用 **ISO 8601 带时区**,例如 `2026-07-30T23:59:00+08:00`。
后端不会静默丢失时区;客户端反序列化时使用本地时区显示。

### 字符编码

UTF-8。所有中文文本不做转义,SSE 中 JSON `ensure_ascii=False`。

### 鉴权

本轮**不实现** JWT。所有接口匿名可访问,默认共享同一知识库。
预留扩展:`Authorization: Bearer <token>`(后续接入)。

### 请求体

- `POST` 接口统一使用 `application/json`
- 文档上传使用 `multipart/form-data`

### 响应体

成功: 直接返回业务 JSON,无外层包裹。
失败: 统一错误结构(见 [错误码](#错误码))。

---

## 1. 健康检查 Health

### `GET /api/v1/health`

返回服务状态、运行模式、知识库与 LLM 可用性。

**响应 200**

```json
{
  "status": "ok",
  "mode": "rules_only",
  "knowledge_base_initialized": true,
  "document_count": 5,
  "chunk_count": 42,
  "llm_available": false,
  "fallback_enabled": true,
  "version": "0.2.0",
  "checked_at": "2026-07-25T10:00:00+08:00"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `status` | string | `ok` / `degraded` / `error` |
| `mode` | string | `llm` / `rules_only` / `retrieval_only` |
| `knowledge_base_initialized` | bool | 是否已导入至少 1 份文档 |
| `document_count` | int | 已索引文档数 |
| `chunk_count` | int | 分块总数 |
| `llm_available` | bool | LLM Provider 是否可用 |
| `fallback_enabled` | bool | 是否启用降级(检索摘要)模式 |
| `version` | string | 后端版本号(来自 `APP_VERSION`) |
| `checked_at` | datetime | 检查时间(ISO 8601) |

> Flutter 客户端用 `BackendStatus` 模型映射,`mode=llm` 显示"知识库 + LLM",
> `mode=rules_only` 显示"检索摘要模式"。

---

## 2. 通知结构化抽取 Notices

### `POST /api/v1/notices/extract`

抽取校园通知原文中的结构化字段。LLM 优先,失败自动降级规则抽取。

**请求体**

```json
{
  "content": "请2024级学生于7月30日前填写实践申请表,并将申请表和证明材料提交至学院办公室。",
  "published_at": "2026-07-20T09:00:00+08:00",
  "source_name": "信息工程学院通知"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `content` | string | 是 | 通知原文(1~5000 字) |
| `published_at` | datetime | 否 | 通知发布时间(用于缺少年份时推断) |
| `source_name` | string | 否 | 来源单位/系统名称 |

**响应 200**

```json
{
  "title": "提交实践申请",
  "task": "提交实践申请",
  "target_students": "2024级",
  "deadline": "2026-07-30T23:59:00+08:00",
  "materials": [
    {"id": "m_1", "name": "申请表", "required": true},
    {"id": "m_2", "name": "证明材料", "required": true}
  ],
  "submission_method": "提交纸质版",
  "location": "学院办公室",
  "source_name": "信息工程学院通知",
  "source_text": "请2024级学生于7月30日前填写实践申请表...",
  "importance": "important",
  "confidence": 0.82,
  "needs_confirmation": false,
  "warnings": [],
  "extracted_at": "2026-07-25T10:00:00+08:00",
  "extractor_mode": "rules"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `title` | string | 通知标题(可与 `task` 相同) |
| `task` | string | 任务名(对齐 Flutter `taskName`) |
| `target_students` | string\|null | 面向对象(如"2024级本科生") |
| `deadline` | datetime\|null | 截止时间 |
| `materials` | MaterialItem[] | 材料列表 |
| `submission_method` | string\|null | 提交方式 |
| `location` | string\|null | 办理地点 |
| `source_name` | string\|null | 来源单位 |
| `source_text` | string | 原文(便于人工复核) |
| `importance` | string | `urgent`\|`important`\|`normal`\|`unknown` |
| `confidence` | float | 抽取置信度 0~1(仅表示结构化抽取置信度,不代表内容真实性) |
| `needs_confirmation` | bool | 是否需要人工确认(年份缺失/对象不明等) |
| `warnings` | string[] | 需要确认的原因列表(温和提示,非错误) |
| `extracted_at` | datetime | 抽取完成时间 |
| `extractor_mode` | string | `llm` / `rules`(客户端可据此显示徽章) |

**MaterialItem**

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string | 材料 ID(便于客户端引用) |
| `name` | string | 材料名称 |
| `required` | bool | 是否必需(默认 true) |

### 抽取规则

1. **LLM 模式**(`LLM_PROVIDER=openai_compatible` 且 API Key 配置):
   - LLM 输出结构化 JSON,Pydantic 校验
   - 失败/超时自动降级到规则模式

2. **规则模式**(默认,无 LLM 也能用):
   - 正则匹配: `2026年7月30日前` / `7月30日前` / `截止时间为...` / `截至...`
   - 周表达: `第8周周五17:00` / `本周五` / `下周一`
   - 提交方式: `提交至` / `交到` / `上传到` / `通过...提交`
   - 面向对象: `2024级本科生` / `XX学院学生` / `XX专业` / `XX班`
   - 地点: `行政楼XX办公室` / `学院办公室` / `学生事务中心`
   - 材料: 申请表 / 证明材料 / 成绩单 / 开题报告 / 创新创业材料 等 20+ 关键词
   - 缺少年份时基于 `published_at` 或当前时间推断

3. **不确定情况**(`needs_confirmation=true`):
   - 缺少年份
   - 面向对象不明确
   - 提交方式不明确
   - `warnings` 字段列出原因

4. **永不编造**: 不擅自补充通知原文中不存在的材料或任务。

---

## 3. 知识库 Knowledge

### `POST /api/v1/knowledge/documents`

上传并导入知识库文档。

**请求**(`multipart/form-data`)

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `file` | File | 是 | 文件(支持 `.md .txt .pdf .docx`) |
| `title` | string | 否 | 文档标题(留空则从内容/文件名推断) |
| `source_department` | string | 否 | 来源部门 |
| `source_type` | string | 否 | 来源类型 |
| `published_at` | datetime | 否 | 发布时间 |
| `updated_at` | datetime | 否 | 更新时间 |
| `effective_from` | datetime | 否 | 生效起始 |
| `effective_to` | datetime | 否 | 生效截止(过期判定依据) |
| `version` | string | 否 | 版本号 |
| `applicable_students` | string | 否 | 适用对象 |
| `is_official` | bool | 否 | 是否官方资料(默认 false) |

**响应 201** — 返回 `DocumentSummary`(见下)。

**安全限制**

- 文件大小: ≤ 10 MB(可在 `MAX_UPLOAD_MB` 调整)
- 文件类型: `.md .txt .pdf .docx`(可在 `ALLOWED_EXTENSIONS` 调整)
- 文件名: `sanitize_filename` 处理,拒绝路径穿越(`../`、绝对路径等)
- 空文件: 拒绝
- 重复内容: 基于内容哈希去重,返回 `DOCUMENT_ALREADY_EXISTS`(409)

---

### `GET /api/v1/knowledge/documents`

返回已导入文档列表。

**响应 200** — `DocumentSummary[]`

```json
[
  {
    "document_id": "doc_1",
    "title": "社会实践申请指南",
    "source_department": "校团委",
    "source_type": "md",
    "original_filename": "01_social_practice_guide.md",
    "content_hash": "sha256_abc...",
    "published_at": "2026-07-01T00:00:00+08:00",
    "updated_at": "2026-07-10T00:00:00+08:00",
    "effective_from": null,
    "effective_to": null,
    "version": "v1.2",
    "applicable_students": "2024级本科生",
    "is_official": true,
    "is_expired": false,
    "file_size": 4096,
    "file_ext": "md",
    "imported_at": "2026-07-15T10:00:00+08:00"
  }
]
```

**DocumentSummary 字段**

| 字段 | 类型 | 说明 |
|------|------|------|
| `document_id` | string | 文档 ID |
| `title` | string | 标题 |
| `source_department` | string\|null | 来源部门 |
| `source_type` | string\|null | 来源类型 |
| `original_filename` | string\|null | 原始文件名 |
| `content_hash` | string | SHA256 内容哈希 |
| `published_at` | datetime\|null | 发布时间 |
| `updated_at` | datetime\|null | 更新时间 |
| `effective_from` | datetime\|null | 生效起始 |
| `effective_to` | datetime\|null | 生效截止 |
| `version` | string\|null | 版本 |
| `applicable_students` | string\|null | 适用对象 |
| `is_official` | bool | 是否官方 |
| `is_expired` | bool | 是否过期(基于 `effective_to` 判定) |
| `file_size` | int\|null | 文件大小(字节) |
| `file_ext` | string\|null | 扩展名 |
| `imported_at` | datetime | 导入时间 |

---

### `DELETE /api/v1/knowledge/documents/{document_id}`

删除文档并同步更新索引。

**路径参数**

| 字段 | 类型 | 说明 |
|------|------|------|
| `document_id` | string | 文档 ID |

**响应 200**

```json
{"success": true, "document_id": "doc_1"}
```

---

### `POST /api/v1/knowledge/rebuild`

重建知识库索引(从已导入文档重新分块、索引)。

**响应 200**

```json
{
  "success": true,
  "document_count": 5,
  "chunk_count": 42,
  "message": "索引重建完成"
}
```

---

### `GET /api/v1/knowledge/status`

返回知识库状态。

**响应 200**

```json
{
  "document_count": 5,
  "chunk_count": 42,
  "last_updated": "2026-07-15T10:00:00+08:00",
  "index_status": "ready",
  "retrieval_method": "bm25",
  "is_available": true,
  "knowledge_base_path": "./data/knowledge_base"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `document_count` | int | 文档数 |
| `chunk_count` | int | 分块数 |
| `last_updated` | datetime\|null | 最近更新时间 |
| `index_status` | string | `ready` / `empty` / `error` |
| `retrieval_method` | string | `bm25` / `vector` / `hybrid`(当前固定 `bm25`) |
| `is_available` | bool | 是否可用于回答 |
| `knowledge_base_path` | string | 知识库根目录 |

### 检索优先级

文档与分块的元数据用于优先级排序:

1. 未过期 > 过期
2. 官方 > 非官方
3. 更新时间新 > 旧
4. BM25 相关度作为辅助

过期文档不会默认作为最高优先级证据,但仍可在 `sources` 中显示(标注 `is_expired=true`)。

---

## 4. AI 导员 Counselor

### `POST /api/v1/counselor/chat`

基于校园知识库的 RAG 问答。支持 SSE 流式与非流式。

**请求体**

```json
{
  "message": "实践学分怎样申请?",
  "conversation_id": "conv_123",
  "recent_tasks": [],
  "stream": true
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `message` | string | 是 | 用户问题(非空) |
| `conversation_id` | string | 否 | 会话 ID(留空则后端生成) |
| `recent_tasks` | object[] | 否 | 最近待办(用于个性化提示) |
| `stream` | bool | 否 | 是否流式(默认 true) |

#### 非流式响应

`stream=false` 时,返回 `ChatFinalMeta`:

```json
{
  "answer": "根据《社会实践申请指南》,申请表需在 7 月 30 日前提交至学院办公室。",
  "sources": [...],
  "confidence": 0.85,
  "evidence_level": "high",
  "needs_human_confirmation": false,
  "suggested_actions": [...],
  "conversation_id": "conv_123",
  "mode": "llm",
  "warnings": []
}
```

#### 流式响应 (SSE)

`stream=true` 时,返回 `text/event-stream`,事件序列见 [SSE 事件格式](#sse-事件格式)。

**ChatFinalMeta 字段**

| 字段 | 类型 | 说明 |
|------|------|------|
| `answer` | string | 完整回答 |
| `sources` | ChatSource[] | 引用来源列表 |
| `confidence` | float | 综合置信度 0~1 |
| `evidence_level` | string | `high`\|`medium`\|`low`\|`none` |
| `needs_human_confirmation` | bool | 是否建议人工复核 |
| `suggested_actions` | SuggestedAction[] | 建议操作 |
| `conversation_id` | string | 会话 ID |
| `mode` | string | `llm` / `retrieval_summary` / `no_knowledge` |
| `warnings` | string[] | 警告(冲突/降级等) |

**ChatSource 字段**

| 字段 | 类型 | 说明 |
|------|------|------|
| `document_id` | string | 文档 ID |
| `title` | string | 文档标题 |
| `section` | string\|null | 小节 |
| `source_department` | string\|null | 来源部门 |
| `published_at` | datetime\|null | 发布时间 |
| `version` | string\|null | 版本 |
| `applicable_students` | string\|null | 适用对象 |
| `excerpt` | string | 引用片段(已截断) |
| `relevance_score` | float | 相关度 0~1 |
| `is_official` | bool | 是否官方 |
| `is_expired` | bool | 是否过期 |

**SuggestedAction 字段**

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string | 操作 ID |
| `label` | string | 显示文本 |
| `type` | string | `navigate`\|`prefillQuestion`\|`createTask`\|`none` |
| `payload` | string\|null | 跳转路径/预填问题/任务数据 |

### 回答规则(强制)

1. **基于知识库**: 回答只能以检索到的校园资料为主要依据。
2. **不编造**: 不允许把模型自身知识伪装为学校规定。
3. **无依据**: 检索证据不足时返回:
   ```
   当前知识库无法确认这一事项。建议咨询辅导员或相关负责老师。
   ```
   且 `sources=[]`, `needs_human_confirmation=true`,不生成看似确定的流程/日期/地点/材料。
4. **冲突处理**: 检索到相互冲突的资料时:
   - 明确指出存在冲突
   - 展示两个来源
   - 优先提示最新官方资料
   - 建议人工复核
5. **过期资料**: 降权处理,标注 `is_expired=true`,不作为最高优先级证据。
6. **降级模式**: LLM 不可用时启用检索摘要模式:
   - 返回检索到的关键段落
   - 使用模板整理为简洁回答
   - 标注 `mode=retrieval_summary`
   - 仍然保留来源
   - 不直接返回错误页
7. **恶意 Prompt 防御**: 系统消息强制约束"只能基于知识库回答",`recent_tasks` 等用户字段
   不会被解释为指令。

---

## 错误码

所有错误响应统一结构:

```json
{
  "code": "KNOWLEDGE_BASE_EMPTY",
  "message": "当前知识库中没有可用于回答该问题的资料。",
  "details": null
}
```

| HTTP | code | 触发场景 |
|------|------|----------|
| 400 | `NOTICE_EMPTY` | 通知文本为空 |
| 400 | `NOTICE_TOO_LONG` | 通知文本 > 5000 字 |
| 400 | `EMPTY_QUESTION` | 用户问题为空 |
| 400 | `FILE_NAME_UNSAFE` | 文件名包含路径穿越字符 |
| 413 | `FILE_TOO_LARGE` | 文件 > 10 MB |
| 415 | `FILE_TYPE_NOT_ALLOWED` | 文件类型不在允许列表 |
| 404 | `DOCUMENT_NOT_FOUND` | 文档 ID 不存在 |
| 404 | `NOT_FOUND` | 路由不存在 |
| 405 | `METHOD_NOT_ALLOWED` | HTTP 方法不允许 |
| 409 | `DOCUMENT_ALREADY_EXISTS` | 内容哈希重复 |
| 422 | `NOTICE_UNPARSEABLE` | 文本无法识别为通知 |
| 422 | `VALIDATION_FAILED` | Pydantic 校验失败 |
| 500 | `INTERNAL_ERROR` | 未捕获异常(不暴露堆栈) |

> 注意: `KNOWLEDGE_BASE_EMPTY`(HTTP 200) 和 `LLM_UNAVAILABLE`(HTTP 200) **不是错误**,
> 而是业务上的"无资料"/"降级"状态,通过响应体 `mode` / `evidence_level` 表达。

---

## SSE 事件格式

`Content-Type: text/event-stream`

每个事件由 `event:` 和 `data:` 两行组成,以 `\n\n` 结尾:

```
event: sources
data: {"sources": [...]}

event: chunk
data: {"text": "增量内容", "mode": "llm"}

event: done
data: {完整 ChatFinalMeta}

```

### 事件类型

#### `sources` (一次性,先于所有 chunk)

```json
{
  "sources": [
    {
      "document_id": "doc_1",
      "title": "社会实践申请指南",
      "section": "申请流程",
      "source_department": "校团委",
      "published_at": "2026-07-01T00:00:00+08:00",
      "version": "v1.2",
      "applicable_students": "2024级本科生",
      "excerpt": "申请表需在 7 月 30 日前提交至学院办公室",
      "relevance_score": 0.85,
      "is_official": true,
      "is_expired": false
    }
  ]
}
```

#### `chunk` (多次,逐字/逐段增量)

```json
{"text": "根据", "mode": "llm"}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `text` | string | 本次增量文本 |
| `mode` | string | `llm` / `retrieval_summary` / `no_knowledge` |

客户端应将所有 `chunk.text` 拼接得到完整 `answer`。
每个 chunk 触发 `onChunk(text)` 回调,同时建议触发 `onTyping()` 反馈。

#### `done` (一次,最后)

```json
{
  "answer": "根据《社会实践申请指南》,申请表需在 7 月 30 日前提交。",
  "sources": [...],
  "confidence": 0.85,
  "evidence_level": "high",
  "needs_human_confirmation": false,
  "suggested_actions": [...],
  "conversation_id": "conv_123",
  "mode": "llm",
  "warnings": []
}
```

客户端收到 `done` 后:
- 调用 `onActions(actions)` 反馈建议操作
- 关闭流式光标
- 启用"重新生成"按钮

#### `error` (异常时,流末尾)

```json
{"code": "RAG_ERROR", "message": "生成失败"}
```

客户端应展示"生成失败,请重试",不清空已生成内容。

### Flutter 客户端处理

参考 [`lib/data/services/api/api_counselor_chat_service.dart`](../lib/data/services/api/api_counselor_chat_service.dart):
- 使用 `dio.post` + `ResponseType.stream` 接收 SSE
- 按行解析 `event:` / `data:` 前缀
- 通过 `onSources` / `onChunk` / `onActions` / `onTyping` 回调向上传递
- 网络中断时保留已生成内容,触发 `onError`

---

## 枚举对照表

### `importance`

| 后端 | Flutter `NoticeImportance` |
|------|-----------------------------|
| `urgent` | `urgent` |
| `important` | `important` |
| `normal` | `normal` |
| `unknown` | `unknown` |

### `evidence_level`

| 值 | 含义 |
|----|------|
| `high` | 多份官方资料直接命中 |
| `medium` | 部分命中或非官方资料 |
| `low` | 仅弱相关命中 |
| `none` | 无任何资料(触发人工兜底) |

### `mode`(counselor)

| 值 | 含义 |
|----|------|
| `llm` | LLM 基于知识库生成 |
| `retrieval_summary` | LLM 不可用,检索摘要模式 |
| `no_knowledge` | 知识库为空 |
| `error` | 生成失败 |

### `extractor_mode`(notices)

| 值 | 含义 |
|----|------|
| `llm` | LLM 结构化抽取 |
| `rules` | 规则抽取(降级或默认) |

### `suggested_action.type`

| 值 | 客户端行为 |
|----|------------|
| `navigate` | 跳转到 `payload` 路径(如 `/notifications/extract`) |
| `prefillQuestion` | 在导员输入框预填 `payload` |
| `createTask` | 跳转到任务创建,预填 `payload` |
| `none` | 仅显示,不触发操作 |

---

## 数据模型对照表

### 通知抽取

| 后端 Pydantic | Flutter Dart |
|---------------|--------------|
| `NoticeExtractRequest` | (无,直接构造 JSON) |
| `NoticeExtractResponse` | `ExtractedNotice` |
| `MaterialItem` | `TaskMaterial` |

### 知识库

| 后端 Pydantic | Flutter Dart |
|---------------|--------------|
| `DocumentMetadata` | (上传时构造 `FormData`) |
| `DocumentSummary` | `KnowledgeSource`(部分字段) |
| `KnowledgeStatus` | `BackendStatus` |

### 聊天

| 后端 Pydantic | Flutter Dart |
|---------------|--------------|
| `ChatRequest` | (无,直接构造 JSON) |
| `ChatSource` | `KnowledgeSource` |
| `SuggestedAction` | `SuggestedAction` |
| `ChatFinalMeta` | `CounselorAnswer`(部分字段) |

### 时间与版本兼容

- 新增字段尽量提供默认值,避免旧客户端反序列化失败
- `extractor_mode` / `warnings` / `evidence_level` / `mode` 均为新增字段,
  旧版本 Flutter 客户端忽略不影响功能
- 后端在响应中始终带 `version`(health 接口),客户端可据此判断兼容性
