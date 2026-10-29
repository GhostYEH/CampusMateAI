# AI 对话、语音与知识库

> 对照日期：2026-10-24。本模块共 8 个 HTTP 方法与路径组合；以当前后端注册路由和 Web 调用为依据。

[文档导航](README.md) · [接入与流程](integration.md) · [字段字典](schemas.md) · [OpenAPI](openapi.json)

## 聊天输入与匿名额度

`POST /api/v1/counselor/chat` 与 `POST /api/v1/assistant/chat` 共用 `ChatRequest` 和匿名额度。`message` 必填，长度 1–20000 字符；可空的 `conversation_id`、`course_id`、`class_id`、`assignment_id`、`announcement_id` 最多 128 字符；`recent_tasks` 最多 100 项，每项 `id` 长度 1–128。最多五个通过归属检查的待办进入聊天上下文。超限在模型调用前返回 422 `VALIDATION_FAILED`；不截断用户问题。

没有有效登录身份的请求按来源地址在当前进程内限流：每 60 秒最多 10 次，两条别名路径共享计数，成功和失败尝试均计数。超限在 SSE 建立前返回普通 HTTP 429 `RATE_LIMITED`，附 `Retry-After` 秒数，结构见 [认证限流](01-auth.md)。有有效身份的请求不占匿名额度，仍须满足输入约束。反向代理应正确配置受信地址识别，多进程额度各自独立。

```json
{"message":"帮我安排今天的复习","conversation_id":"conversation_example","recent_tasks":[{"id":"task_example"}],"stream":false}
```

Web、Android、HarmonyOS、微信小程序的聊天调用已核对：普通短问题和现有 ID 不需迁移；超长问题或上下文需缩减后重发，429 应等待后重试。Web 现有 fetch/Axios 能识别非成功响应；专门的字数限制与重试倒计时尚未做端侧适配，各移动端本次未编译或真机验证。SSE 已开始后的 error 事件及既有 LLM 降级响应保持原协议。

## 接口索引

| 方法 | 完整路径 | 用途 |
| --- | --- | --- |
| GET | `/api/v1/knowledge/status` | knowledge状态 |
| GET | `/api/v1/knowledge/documents` | 列出知识库文档 |
| POST | `/api/v1/assistant/chat` | chat |
| POST | `/api/v1/counselor/chat` | chat |
| POST | `/api/v1/assistant/tts` | 合成语音 |
| POST | `/api/v1/assistant/asr` | 识别语音输入 |
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
| `knowledge_base_type` | string | 是 | — | demo\|user\|hybrid\|empty |
| `demo_document_count` | integer | 否 | default=0 | — |
| `user_document_count` | integer | 否 | default=0 | — |
| `llm_available` | boolean | 否 | default=false | — |
| `qa_mode` | string | 否 | default="no_knowledge" | retrieval_summary\|llm_rag\|no_knowledge |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/knowledge/documents`

用途：列出知识库文档。

鉴权：Bearer access token；已登录用户。

实现：[backend/app/api/routes/knowledge.py](../../backend/app/api/routes/knowledge.py)，`list_documents`。

Web 封装：`getKnowledgeDocuments`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | array<[DocumentSummary](schemas.md#schema-documentsummary)> |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

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
| `message` | string | 是 | minLength=1; maxLength=20000 | 用户问题 |
| `conversation_id` | string / null | 否 | string约束: maxLength=128 | 会话 ID(仅作会话标识) |
| `workspace_id` | string / null | 否 | string约束: minLength=1; maxLength=120 | 原生 magic class workspace 会话归属；必须与 course_id 一起提供并通过服务端归属校验 |
| `recent_tasks` | array<[CounselorRecentTask](schemas.md#schema-counselorrecenttask)> | 否 | maxItems=100 | 最近待办(仅 PersonalTask,id 为必填,其他字段为 hint),后端会通过 PersonalTaskRepository 校验归属,越权/不存在/已删除的条目会被忽略 |
| `stream` | boolean | 否 | default=true | 是否使用 SSE 流式响应 |
| `web_search` | boolean | 否 | default=false | 是否检索公开网页并将结果作为非官方辅助上下文 |
| `attachment` | [CounselorAttachment](schemas.md#schema-counselorattachment) / null | 否 | — | 本轮用户选择的文本附件；作为不可信上下文使用，不得覆盖系统规则 |
| `course_id` | string / null | 否 | string约束: maxLength=128 | 课程 ID(需有权限) |
| `class_id` | string / null | 否 | string约束: maxLength=128 | 班级 ID(需有权限) |
| `assignment_id` | string / null | 否 | string约束: maxLength=128 | 任务 ID(需有权限) |
| `announcement_id` | string / null | 否 | string约束: maxLength=128 | 通知 ID(需有权限) |
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
| 429 | application/json | 匿名额度耗尽，返回 `RATE_LIMITED` 和 `Retry-After`；发生在 SSE 建立前 |

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
| `message` | string | 是 | minLength=1; maxLength=20000 | 用户问题 |
| `conversation_id` | string / null | 否 | string约束: maxLength=128 | 会话 ID(仅作会话标识) |
| `workspace_id` | string / null | 否 | string约束: minLength=1; maxLength=120 | 原生 magic class workspace 会话归属；必须与 course_id 一起提供并通过服务端归属校验 |
| `recent_tasks` | array<[CounselorRecentTask](schemas.md#schema-counselorrecenttask)> | 否 | maxItems=100 | 最近待办(仅 PersonalTask,id 为必填,其他字段为 hint),后端会通过 PersonalTaskRepository 校验归属,越权/不存在/已删除的条目会被忽略 |
| `stream` | boolean | 否 | default=true | 是否使用 SSE 流式响应 |
| `web_search` | boolean | 否 | default=false | 是否检索公开网页并将结果作为非官方辅助上下文 |
| `attachment` | [CounselorAttachment](schemas.md#schema-counselorattachment) / null | 否 | — | 本轮用户选择的文本附件；作为不可信上下文使用，不得覆盖系统规则 |
| `course_id` | string / null | 否 | string约束: maxLength=128 | 课程 ID(需有权限) |
| `class_id` | string / null | 否 | string约束: maxLength=128 | 班级 ID(需有权限) |
| `assignment_id` | string / null | 否 | string约束: maxLength=128 | 任务 ID(需有权限) |
| `announcement_id` | string / null | 否 | string约束: maxLength=128 | 通知 ID(需有权限) |
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
| 429 | application/json | 匿名额度耗尽，返回 `RATE_LIMITED` 和 `Retry-After`；发生在 SSE 建立前 |

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

### `POST /api/v1/assistant/asr`

用途：识别语音输入。

鉴权：Bearer access token；已登录用户。

实现：[backend/app/api/routes/asr.py](../../backend/app/api/routes/asr.py)，`recognize_speech`。

Web 封装：[transcribeSpeech](../../webreact/src/data/api.js)，由 [useVoiceInput](../../webreact/src/hooks/useVoiceInput.js) 调用。

AI 助手对话页"按住说话"的语音输入：客户端录音后转成约定格式上传，服务端用**本地 SenseVoice 模型离线转写**，回填聊天输入框。推理不联网、不调用第三方、不产生费用，音频不落盘。

音频格式约定：**WAV / PCM16LE / 16000Hz / 单声道**，由客户端录制后就地转换。非单声道、非 16 位 PCM、非 WAV 内容返回 422；时长或体积超限返回 413。

空文本语义：`text` 为空字符串**不是错误**，而是约定的"没听清"信号（语音检测未通过、静音、噪声或识别结果只剩标点），客户端应提示用户重说。空文本不能证明录音一定不含语音。

服务端在 `ASR_VAD_MODEL_PATH` 指向的本地文件存在时启用 **Silero VAD**（默认 `data/asr_models/silero_vad.onnx`，通过 `python scripts/download_asr_model.py --with-vad` 获取）；`ASR_VAD_THRESHOLD` 默认 0.4，范围 `(0, 1)`。检测器只判断是否含语音，通过后仍将完整录音交给 SenseVoice，不裁剪轻声起音，不拼接多段文本；不再叠加固定 RMS 或 crest 门限。每次请求重置检测状态，避免上一条录音影响下一条。VAD 不负责降噪，强噪声、背景人声和远距离混响仍可能导致误报或错字。

默认门控由 0.5 调整为 0.4，客户端上传协议与响应不变；服务端改变的是语音检测的放行阈值。0.4 是当前实际试用选择，不代表已证明跨设备或真实远场稳健，依据与局限见[实验记录](../../ml/speech_recognition/README.md)。已有环境或 `.env` 中显式的 `ASR_VAD_THRESHOLD=0.5` 会继续覆盖默认值；要采用新默认，应改为 0.4 或移除该显式配置并重启后端。0.5 仍是有效可配值，但不再作为当前首选默认方案。

可选低幅度复检：`ASR_VAD_RECHECK_ENABLED` 默认 `true`（当前应用默认）。启用且本地 VAD 可用时，仅在首次检测拒绝后计算受限增益；增益大于 1 才对用于分析的增响副本再检测一次，每条录音最多复检一次，沿用 `ASR_VAD_THRESHOLD`。增响副本仅用于 VAD，完整原音和原采样率保留给后续识别流程（包括另行启用的可选增强），不裁剪、不拼接，也不改变 ASR 输入音量。任一次检测通过即可进入后续流程；两次均拒绝或无需增响时返回空 `text`。复检的启用与否不新增请求字段，也不改变响应结构；需要退回单次门控时把 `ASR_VAD_RECHECK_ENABLED` 设为 `false`。

复检参数均为服务端配置，无客户端请求字段：`ASR_VAD_RECHECK_TARGET_RMS` 默认 0.005、范围 `(0, 1)`；`ASR_VAD_RECHECK_MAX_GAIN` 默认 20、范围 `[1, +∞)`；`ASR_VAD_RECHECK_PEAK_LIMIT` 默认 0.95、范围 `(0, 1)`。实际增益取最大增益、目标 RMS / 原音 RMS、峰值上限 / 原音峰值三者的最小值，仅放大且限制峰值；纯静音不复检。数字增益不会提高物理信噪比。默认值来自新独立验证集：24 条未使用中文原句、20 个未使用 ESC-50 fold 5 噪声源、3 个未使用实测 RIR，共 204 条变体；按预先冻结协议（候选、门槛与 3 次重复均在推理前写入）通过全部门槛——总体 CER 12.97%→10.93%，1% 幅度 CER 21.97%→9.75%，空转写 4→0，噪声非空输出保持 1→1，clean/10% 幅度/两档噪声/混响零退化，总体分组 95% CI `[-4.33, -0.41]` 个百分点不触零，P95 中位数 0.495→0.526 秒（+6.4%，在 20% 门槛内）。历史 0.5 阈值 + 0.02/100 宽增益复检仍未通过其自身门槛，保持为已停止采用的对照；本默认只对应受限的 0.005/20 组合，不要把两者混为一谈。说话人不相交无法证明，真实麦克风、远场与浏览器默认降噪仍未验证，详见[验证结果与复现](../../ml/speech_recognition/README.md)。两个检测器按录音重置；复检检测器加载失败仍返回 503 `ASR_UNAVAILABLE`，检测或状态重置失败仍返回 500 `ASR_FAILED`，不增加错误码或暴露内部异常。

VAD 文件缺失或路径留空时，兼容原有能量门控：整段 RMS 低于 `ASR_MIN_RMS`（默认 0.008）或峰值因子 `crest = 最大帧RMS/整段RMS` 低于 `ASR_MIN_CREST`（默认 1.5）返回空文本；短于 `ASR_MIN_DYNAMIC_SECONDS`（默认 0.35 秒）跳过 crest 判据。该回退可能误拒小声、持续语音和留白较多的录音，也可能放过脉冲噪声。已有 VAD 文件损坏或加载失败时返回 503，不静默回退。

配置校验补充：`ASR_VAD_RECHECK_MAX_GAIN` 必须为大于等于 1 的有限数，不接受 NaN 或正负无穷。显式把 `ASR_VAD_RECHECK_ENABLED` 设为 `false` 可回到单次门控；已有环境或 `.env` 中残留的 `ASR_VAD_RECHECK_TARGET_RMS=0.02` / `ASR_VAD_RECHECK_MAX_GAIN=100` 会继续覆盖新默认，要采用受限复检应改为 0.005 与 20，或移除这两项显式配置并重启后端。本接口不因此新增请求字段或改变响应约定。

可选论文增强：`ASR_DENOISE_ENABLED` 默认 `false`，仅服务端配置，无客户端请求字段。显式启用后，原音先通过上述检测，再由本地 GTCRN 增强，并以 `w*原音+(1-w)*增强音` 混合交给 SenseVoice；`w=ASR_DENOISE_OBSERVATION_WEIGHT`，范围 `[0,1]`，默认实验值 0.5。0 为纯增强，1 完全旁路增强且不要求模型。模型默认路径 `ASR_DENOISE_MODEL_PATH=data/asr_models/gtcrn_simple.onnx`，下载命令 `python scripts/download_asr_model.py --with-denoiser`；文件存在不会自动开启。增强可能引入伪影并增加错字，必须用独立标注集验证后再启用；原音 VAD 不重复运行于增强音，不使用 VAD 区间裁剪录音，增强短尾保留原音。显式启用且权重小于 1 时模型缺失/加载失败为 503 `ASR_UNAVAILABLE`，推理失败为 500 `ASR_FAILED`。详见[方法与消融评测](../../backend/README.md#可选增强gtcrn-与-observation-adding)。

Web 下采样到 16kHz 前使用低通滤波抑制混叠；上传前仅拦截空录音、短于 500ms 的误触和电平可用时的全零录音，非零小声和环境噪声交服务端检测。服务端也能将其他有效采样率的单声道 PCM16 WAV 交给 sherpa-onnx 原生重采样；采样率必须大于 0 且不超过 192000Hz，超范围返回 422 `ASR_AUDIO_INVALID`，客户端仍推荐发送约定的 16kHz 格式。WAV 声明的帧数与实际数据不符同样返回 422，不把截断文件当作有效短录音。

模型为可选能力：`sherpa-onnx` 未安装或模型文件缺失时，后端仍正常启动，仅本接口返回 503。模型约 230MB，不随仓库分发，用 [backend/scripts/download_asr_model.py](../../backend/scripts/download_asr_model.py) 获取。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：`multipart/form-data`，必填；[Body_recognize_speech_api_v1_assistant_asr_post](schemas.md#schema-body_recognize_speech_api_v1_assistant_asr_post)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `audio` | string (binary) | 是 | format="binary" | WAV/PCM16LE/16kHz/单声道 音频 |

上传使用 FormData；字段名按上表；浏览器由运行时生成 multipart boundary。

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```text
POST /api/v1/assistant/asr
Authorization: Bearer <access_token>
Content-Type: multipart/form-data; boundary=<boundary>

--<boundary>
Content-Disposition: form-data; name="audio"; filename="speech.wav"
Content-Type: audio/wav

<WAV 二进制：PCM16LE / 16000Hz / 单声道>
--<boundary>--
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [AsrResponse](schemas.md#schema-asrresponse)；`text` 可能为空字符串表示没听清 |
| 413 | application/json | 音频超出体积或时长上限，`ASR_AUDIO_TOO_LARGE` / `ASR_AUDIO_TOO_LONG` |
| 422 | application/json | 音频格式非法或字段缺失，`ASR_AUDIO_INVALID`；运行时为 [统一错误结构](integration.md#errors) |
| 503 | application/json | 本地识别未就绪（依赖或模型缺失），`ASR_UNAVAILABLE` |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `text` | string | 是 | — | 识别文本；空字符串表示没听清 |
| `duration_seconds` | number | 是 | minimum=0.0 | 服务端实际送入识别的音频时长(秒) |

响应示例：

```json
{"text": "开饭时间早上9点至下午5点。", "duration_seconds": 5.592}
```

没听清时：

```json
{"text": "", "duration_seconds": 1.0}
```

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 413 | 'ASR_AUDIO_TOO_LARGE' | f'录音文件不能超过 {settings.asr_max_upload_mb} MB' |
| 413 | 'ASR_AUDIO_TOO_LONG' | f'音频时长不能超过 {max_seconds:g} 秒' |
| 422 | 'ASR_AUDIO_INVALID' | '录音文件为空' |
| 422 | 'ASR_AUDIO_INVALID' | '音频不是有效的 WAV 文件' |
| 422 | 'ASR_AUDIO_INVALID' | '音频必须是单声道' |
| 422 | 'ASR_AUDIO_INVALID' | '音频必须是 16 位 PCM(WAV PCM16LE)' |
| 422 | 'ASR_AUDIO_INVALID' | '音频数据不完整' |
| 422 | 'ASR_AUDIO_INVALID' | '音频采样率无效' |
| 503 | 'ASR_UNAVAILABLE' | '本地语音识别未就绪' |
| 503 | 'ASR_UNAVAILABLE' | '本地语音识别模型缺失' |
| 503 | 'ASR_UNAVAILABLE' | '本地语音检测模型加载失败' |
| 503 | 'ASR_UNAVAILABLE' | '本地语音增强模型缺失' / '本地语音增强模型加载失败' |
| 500 | 'ASR_FAILED' | '语音识别失败，请重试' |

客户端兼容性：路径、请求字段、响应字段和空文本约定均保持兼容，默认阈值调整不要求客户端新增参数。Web 已接入本接口，继续使用现有编码、录音状态与小声上传逻辑；浏览器麦克风实录和真机环境未验证。Android、HarmonyOS、微信小程序尚未发现调用本接口，仍**待适配**；各端须转换上述 WAV 格式并处理空 `text`。本地识别指后端机器离线推理，不代表这些客户端已在设备端运行模型。服务端单次识别串行执行（模型实例加锁），并发请求排队；时延取决于录音长度、CPU、VAD 和冷启动，可通过[评测工具](../../backend/scripts/evaluate_asr.py)单独测量。

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
