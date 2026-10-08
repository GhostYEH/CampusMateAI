# 桌面陪伴设备

本模块为未来桌面硬件提供独立设备身份。设备凭据与用户 access token、浏览器 trusted-device cookie、二维码 Web 登录态相互隔离。二维码绑定借鉴现有扫码登录的随机凭据、短时状态机和原子确认模式，但使用独立 URI 与表结构。

设备只能上传结构化、聚合后的观察信号。接口不接收原始帧、图片、人脸裁剪、音频或其 URL/Base64。设备凭据只代表一台已绑定设备，不能调用普通用户接口。

桌面设备 bearer 通过本模块专用语音入口接入现有中继，不能调用原用户 JWT 实时语音接口。设备播放器与数字人属于后续设备端开发；测试提供方只验证协议，不证明真实服务或硬件效果。

## 绑定流程

1. 设备调用 `POST /api/v1/devices/bindings`，收到 `binding_id`、`qr_payload` 和独立的 `poll_token`。二维码仅包含一次性 `bind_token`；`poll_token` 不放入二维码。
2. 用户在已登录的 CampusMateAI 客户端扫描二维码，并调用 `POST /api/v1/devices/bindings/{binding_id}/confirm`，请求体传入 `bind_token`。用户身份只从当前 access token 读取。
3. 设备使用 `X-Device-Poll-Token` 轮询 `GET /api/v1/devices/bindings/{binding_id}/result`。确认后，服务器在绑定过期前幂等返回同一设备凭据，便于设备恢复丢失的响应。轮询 token 仅短时有效；设备 bearer 凭据服务端只存哈希，并在设备撤销时立即失效。
4. 用户可通过 `GET /api/v1/devices` 查看设备，通过 `DELETE /api/v1/devices/{device_id}` 撤销本人设备。

绑定二维码示例：`campusmate://device/bind?v=1&sid=bind_...&token=<一次性绑定凭据>`。设备应只在确认成功后安全保存设备 bearer 凭据；日志不得输出任何绑定或设备凭据。

## 接口索引

| 方法 | 路径 | 身份 | 说明 |
| --- | --- | --- | --- |
| POST | `/api/v1/devices/bindings` | 匿名，限流 | 创建设备绑定二维码和轮询凭据 |
| POST | `/api/v1/devices/bindings/{binding_id}/confirm` | 用户 access token | 确认绑定，必须校验二维码 bind token |
| GET | `/api/v1/devices/bindings/{binding_id}/result` | `X-Device-Poll-Token` | 轮询绑定结果并领取设备凭据 |
| GET | `/api/v1/devices` | 用户 access token | 列出本人桌面设备 |
| DELETE | `/api/v1/devices/{device_id}` | 用户 access token | 撤销本人设备凭据 |
| POST | `/api/v1/devices/me/focus-sessions/{focus_id}/voice-sessions` | 设备 bearer + Idempotency-Key | 创建本设备实时语音会话 |
| DELETE | `/api/v1/devices/me/voice-sessions/{voice_id}` | 设备 bearer | 停止本设备实时语音会话 |
| POST | `/api/v1/devices/me/heartbeat` | 设备 bearer | 上报客户端、网络、存储、温度和能力状态 |
| GET | `/api/v1/devices/me/config` | 设备 bearer | 读取版本化设备协议配置和账号偏好 |
| POST | `/api/v1/devices/me/focus-sessions` | 设备 bearer + `Idempotency-Key` | 为设备所属账号创建专注会话 |
| POST | `/api/v1/devices/me/focus-sessions/{session_id}/pause` | 设备 bearer + `Idempotency-Key` | 暂停本设备创建的专注会话 |
| POST | `/api/v1/devices/me/focus-sessions/{session_id}/resume` | 设备 bearer + `Idempotency-Key` | 恢复本设备创建的专注会话 |
| POST | `/api/v1/devices/me/focus-sessions/{session_id}/finish` | 设备 bearer + `Idempotency-Key` | 结束本设备创建的专注会话并可写入聚合摘要 |
| POST | `/api/v1/devices/me/events:batch` | 设备 bearer | 幂等批量上传结构化端侧事件 |

## 绑定与设备管理

### `POST /api/v1/devices/bindings`

匿名创建，按请求来源地址限流为 3 次/分钟。请求不接受用户 ID。绑定在 5 分钟后过期。

请求体：

```json
{
  "device_name": "书桌助手",
  "platform": "android",
  "hardware_model": "RK3588S",
  "app_version": "0.1.0"
}
```

`platform` 为 `android` 或 `linux`；`hardware_model`、`app_version` 可省略。成功返回 201：

```json
{
  "binding_id": "bind_0123456789abcdef",
  "qr_payload": "campusmate://device/bind?v=1&sid=bind_0123456789abcdef&token=<redacted>",
  "poll_token": "<仅设备持有的短时凭据>",
  "status": "PENDING",
  "expires_at": "2026-10-08T04:05:00Z",
  "poll_interval_seconds": 2
}
```

服务器只保存 bind token 与 poll token 的 SHA-256 哈希。

### `POST /api/v1/devices/bindings/{binding_id}/confirm`

需要已登录学生账号。用户必须扫描对应二维码，确认当前设备与账号关联。请求体为 `{"bind_token":"<二维码中的一次性凭据>"}`。缺少凭据、凭据不匹配、过期或绑定已经由其他账号确认时，返回 401 `DEVICE_BINDING_INVALID`。同一账号重复确认仍返回 204。

### `GET /api/v1/devices/bindings/{binding_id}/result`

使用 `X-Device-Poll-Token` 请求头，不要把轮询凭据放在 URL。未确认时返回 `PENDING`；确认后返回 200：

```json
{
  "binding_id": "bind_0123456789abcdef",
  "status": "CONFIRMED",
  "expires_at": "2026-10-08T04:05:00Z",
  "device_id": "desk_0123456789abcdef",
  "device_credential": "dvc_<高熵设备 bearer 凭据>"
}
```

同一有效 poll token 在绑定过期前可恢复同一个设备凭据；凭据按绑定 ID 与 poll token 作域分离派生，服务器仅保存凭据哈希。已过期时返回 `EXPIRED`，已撤销时返回 `REVOKED`，这两种状态不含凭据。错误 poll token 返回 401 `DEVICE_BINDING_INVALID`。

### `GET /api/v1/devices` 与 `DELETE /api/v1/devices/{device_id}`

两者均需用户 access token，且只访问当前账号数据。列表成功返回 `{"items":[{"device_id":"desk_...","device_name":"书桌助手","platform":"android","hardware_model":"RK3588S","app_version":"0.1.0","status":"ACTIVE","created_at":"...","bound_at":"...","last_heartbeat_at":null}]}`。删除成功返回 204，并将凭据立即撤销；不存在或不属于当前账号返回 404 `DEVICE_NOT_FOUND`。撤销不能通过再次轮询恢复凭据。

## 设备认证与运行接口

除绑定轮询外，设备 API 使用 `Authorization: Bearer <device_credential>`。缺失、无效或已撤销凭据返回 401 `DEVICE_BINDING_INVALID`。设备身份解析为已绑定账号和设备记录；不得将设备 bearer 传给普通用户 API。

### 心跳：`POST /api/v1/devices/me/heartbeat`

设备每次上报当前软件和硬件状态，不传身份字段：

```json
{
  "app_version": "0.1.0",
  "os_version": "Android 14",
  "network_state": "online",
  "temperature_c": 48.5,
  "free_storage_mb": 24000,
  "capabilities": {"camera": true, "microphone": true, "speaker": true, "display": true},
  "model_versions": {"behavior": "behavior-v34", "expression": "expression-v1"}
}
```

`network_state` 为 `online`、`offline` 或 `limited`。能力白名单为 `camera`、`microphone`、`speaker`、`display`、`behavior_model`、`expression_model`；模型版本白名单为 `behavior`、`expression`、`presence`。成功返回 `{"accepted":true,"received_at":"..."}`。心跳不写入音视频或自由文本诊断内容。

### 配置：`GET /api/v1/devices/me/config`

配置使用 `protocol_version=1` 与 `config_version=desktop-v1`。`local_behavior_inference` / `local_expression_inference` 只有设备最近一次心跳同时声明对应 `capabilities` 为 true 且上报对应模型版本后才为 true；未报告时返回 false。`supports_ota=false`，`hardware_acceleration_status=unverified`，不承诺 OTA、NPU 或具体开发板加速已经实现或验收。

账号偏好复用学习状态中的用户偏好，不建立设备专属副本：返回 `timezone`、`daily_capacity_minutes`、`quiet_hours_start`、`quiet_hours_end`、`preferences_configured`、`preferences_version` 和 `preferences_updated_at`。未设置时使用明确默认值 `Asia/Shanghai`、240 分钟、无安静时段，并标记 `preferences_configured=false`。客户端应按偏好版本检测变更。

Android 设备的成功响应示例（偏好尚未配置）：

```json
{
  "protocol_version": 1,
  "config_version": "desktop-v1",
  "vision_enabled": true,
  "behavior_sample_interval_ms": 500,
  "expression_enabled": true,
  "supports_session_control": true,
  "supports_structured_event_upload": true,
  "supports_ota": false,
  "local_behavior_inference": true,
  "local_expression_inference": true,
  "hardware_acceleration_status": "unverified",
  "preferences_configured": false,
  "preferences_version": 0,
  "timezone": "Asia/Shanghai",
  "daily_capacity_minutes": 240,
  "quiet_hours_start": null,
  "quiet_hours_end": null,
  "preferences_updated_at": null,
  "updated_at": "2026-10-08T04:00:00Z"
}
```

### 专注会话

设备创建会话成功返回 201，空请求体或可选的计划时长、目标：

```json
{"planned_duration_seconds":1500,"goal":"复习线性代数"}
```

四个会话操作都必须带 `Idempotency-Key` 请求头（1–128 字符）。同一设备重试相同 key 和相同操作内容时返回第一次的同一响应；同 key 携带不同操作或请求体返回 409 `DEVICE_COMMAND_ID_CONFLICT`。创建、状态迁移、设备与会话关联、命令回执及结束学习事件在同一事务中提交；响应丢失后可安全重试。服务端以设备绑定账号作为 owner，创建 `mode=focus`、`experience_mode=SMART_GUARD` 的会话，并记录由本设备创建。暂停、恢复、结束和事件上传只接受本设备创建的会话；即使同账号的手机会话也不能由桌面设备操作或上传事件。越权访问统一返回 404。状态冲突返回 409 `INVALID_TRANSITION`。结束请求允许为空，也可带既有 `StudyBehaviorSummary` 聚合字段；`duration_seconds`、结束时间和休息累计均由现有学习会话仓库按服务端时间计算，设备不能提交或覆盖这些值。成功结束会话会在同一事务按现有策略写入 canonical 学习事件；写入失败时会话结束与命令回执一并回滚。结束不会自动生成用户自述。

成功响应只包含会话状态：

```json
{
  "id": "stdy_0123456789abcdef",
  "mode": "focus",
  "started_at": "2026-10-08T04:00:00Z",
  "paused_at": null,
  "ended_at": null,
  "planned_duration_seconds": 1500,
  "duration_seconds": 0,
  "pause_seconds": 0,
  "status": "active"
}
```

## 结构化事件批量上传

### `POST /api/v1/devices/me/events:batch`

每批 1–100 项；批次全有或全无。每项必须提供本设备创建的 `focus` 学习会话 ID，服务器忽略任何客户端 device/user 身份声明（schema 禁止额外字段）。`occurred_at` 必须带时区；最多容忍未来 5 分钟。事件不得早于会话开始；未结束会话只接受 `active`/`paused`，已完成会话允许补传最近 7 天内、发生时间不晚于会话结束 5 分钟的事件。其他会话状态、他人或同账号其他设备会话、过期事件和错误时间返回 404 或 422。

单项格式：

```json
{
  "event_id": "01J9DEVICEEVENT000000000001",
  "session_id": "stdy_0123456789abcdef",
  "event_type": "behavior_stable",
  "occurred_at": "2026-10-08T04:01:12Z",
  "model_version": "behavior-v34",
  "payload": {"label":"READ","confidence":0.88,"duration_seconds":20}
}
```

目前允许三种 payload：

| `event_type` | 字段 |
| --- | --- |
| `behavior_stable` | `label`: READ / WRITE / PHONE_INTERACTION / NO_VISIBLE_STUDY / COMPUTER；`confidence` 0–1；`duration_seconds` 0–86400 |
| `presence_changed` | `state`: PRESENT / OBSERVING / ABSENT；`confidence` 0–1 |
| `expression_stable` | `label`: ANGRY / DISGUST / FEAR / HAPPY / NEUTRAL / SAD / SURPRISE / UNKNOWN / NO_FACE；`confidence` 0–1 |

Payload 为严格类型的白名单聚合结果，不接受图片、帧、人脸裁剪、视频、音频、Base64、URL 或自由文本。接收成功返回：

```json
{"accepted_event_ids":["01J9DEVICEEVENT000000000001"],"duplicate_event_ids":[]}
```

幂等键为 `(device_id,event_id)`。相同事件内容重放返回 `duplicate_event_ids`；相同 ID 携带不同内容时返回 409 `DEVICE_EVENT_ID_CONFLICT`，整批回滚。校验/存储任一事件失败时不提交批次中其他新事件。

## 错误处理与验收边界

| HTTP | 错误码 | 客户端处理 |
| --- | --- | --- |
| 401 | `DEVICE_BINDING_INVALID` | 停止设备请求，提示重新绑定；不得退化成普通用户登录 |
| 404 | `DEVICE_NOT_FOUND` / `STUDY_SESSION_NOT_FOUND` | 刷新本人资源；不要枚举其他账号设备或会话 |
| 409 | `INVALID_TRANSITION` / `DEVICE_COMMAND_ID_CONFLICT` / `DEVICE_EVENT_ID_CONFLICT` | 会话状态冲突由用户处理；命令冲突更换 key 前先核对原请求；事件冲突保留本地队列并报告 ID 内容不一致 |
| 422 | 请求校验错误 | 丢弃或修正违反 schema/时间范围的事件，不上传原始媒体作为回退 |
| 429 | 限流 | 遵循 `Retry-After`（若返回），退避重试 |

软件测试可覆盖绑定状态机、owner 隔离、凭据撤销、幂等重放/冲突回滚、专注会话状态和事件时间边界。UVC/CameraX 兼容、摄像头与 USB 音频并发、设备温升/NPU、实体麦克风静音键与摄像头滑盖、整机长时运行和网络抓包须在实际硬件上验收。


## 设备专用实时语音

### `POST /api/v1/devices/me/focus-sessions/{focus_id}/voice-sessions`

设备 bearer 鉴权，focus_id 必须属于本设备且为 active/paused 专注会话；不存在、他设备或已结束返回404。Idempotency-Key 为必填1–128字符请求头，无请求体。201返回 `{"session_id":"focus_voice_...","websocket_path":"devices/me/voice-sessions/focus_voice_.../ws"}`，路径相对 `/api/v1/`。响应不含上游密钥。每设备最多一个未过期语音连接；同focus和同键重放返回原记录，不同键/会话返回409 DEVICE_VOICE_ACTIVE。未配置语音提供方返回503，不能用假回答降级为成功。

### `DELETE /api/v1/devices/me/voice-sessions/{voice_id}`

设备 bearer 鉴权，无请求体。200返回 `{"session_id":"focus_voice_...","stopped":true}`；不属于该设备或已结束返回404，应按已结束处理。停止后已建立连接会在最多一次检查周期后关闭。

### WebSocket `/api/v1/devices/me/voice-sessions/{voice_id}/ws`

握手要求 `Authorization: Bearer <设备凭据>` 请求头，不支持 query 中长期凭据。输入为16kHz/单声道/16bit PCM二进制，输出为24kHz/单声道/16bit PCM二进制；文本帧的取消及提交命令、转写/回答/状态事件与现有[实时语音协议](response-contracts.md#voice)相同。握手无权/过期/重复连接以1008拒绝。设备撤销、账号停用、专注会话结束、显式停止语音时，服务端每帧及约一秒周期重新校验并关闭连接；音频仅在连接中转发，不写入事件表。

未连接会话五分钟过期，单连接最多四小时。本功能及创建幂等记录为进程内短时状态：重启或连接退出后失效，须重新创建；部署必须把创建/连接路由至同一后端进程。客户端断线后重新创建，不能把此幂等描述为持久化队列。配置的 supports_realtime_voice 只表明服务设置可用，不代表已完成真实提供方、麦克风/扬声器或数字人验证。


### `DELETE /api/v1/devices/{device_id}`

本人学生 JWT，device_id 路径参数，无请求体。204空响应，撤销立即使凭据失效；不存在、非本人或已撤销返回404 DEVICE_NOT_FOUND。不得调用该接口撤销登录浏览器可信设备。

### `POST /api/v1/devices/me/heartbeat`

设备 bearer；请求 DeviceHeartbeat。app_version 必填1–64字符；network_state 必填 online/offline/limited。可选 os_version（最多64字符）、temperature_c（-20..120）、free_storage_mb（0..2000000）、capabilities（camera/microphone/speaker/display/behavior_model/expression_model 对应 boolean）、model_versions（behavior/expression/presence 对应1–128字符版本）。禁止额外键。200 DeviceHeartbeatOut：accepted=true和received_at（服务端UTC）；401凭据失效、422非法字段。

### `GET /api/v1/devices/me/config`

设备 bearer，无参数/请求体。200 DeviceConfigOut。protocol_version=1/config_version=desktop-v1；能力来自设备心跳自报，未上报不声称模型可用；硬件加速unverified、OTA=false。supports_realtime_voice反映语音配置是否可用。daily_capacity_minutes/quiet_hours/timezone和preferences_version/updated_at取本人真实偏好，未配置preferences_configured=false。updated_at是读取时服务器UTC，并非偏好修改时间。免打扰配置由后续设备应用执行，本轮不提供提醒投递服务。

### `POST /api/v1/devices/me/focus-sessions`

设备 bearer及必填 Idempotency-Key（1–128字符）。请求 DeviceFocusSessionCreate：planned_duration_seconds可空，非空300..14400；goal可空，非空最多500字符且不能纯空白。201 DeviceFocusSessionActionOut，字段 id/mode/started_at/paused_at/ended_at/planned_duration_seconds/duration_seconds/pause_seconds/status；mode固定focus。新会话仅关联本设备。原键原请求重放原响应，不重复创建；同键不同action/body返回409 DEVICE_COMMAND_ID_CONFLICT。

### `POST /api/v1/devices/me/focus-sessions/{session_id}/pause`

设备 bearer及必填 Idempotency-Key，无请求体。仅本设备创建会话；active变paused，200 DeviceFocusSessionActionOut。不存在或非本设备404；状态不允许409 INVALID_TRANSITION。重试原key返回原操作响应，不再次计暂停时间。

### `POST /api/v1/devices/me/focus-sessions/{session_id}/resume`

设备 bearer及必填 Idempotency-Key，无请求体。仅本设备创建会话；paused变active，200 DeviceFocusSessionActionOut，服务器维护pause_seconds。归属错误404，状态不允许409；原key重放原响应。

### `POST /api/v1/devices/me/focus-sessions/{session_id}/finish`

设备 bearer及必填 Idempotency-Key。请求 DeviceFocusSessionFinish：可选behavior_summary，白名单StudyBehaviorSummary聚合字段，禁止原始视觉媒体；可用空对象。200 DeviceFocusSessionActionOut。会话时长由服务器计算，不能由设备事件改写。完成会话、生成 canonical learner event及持久化命令回执在同一事务，失败全部回滚，客户端保留原key重试。数据源已暂停时按既有模型策略跳过派生事件，业务会话正常完成。不存在/非本设备404，非法字段422，同键不同内容409。
