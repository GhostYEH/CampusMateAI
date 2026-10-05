# 学习通、教务连接与兼容接口

> 对照日期：2026-10-04。本模块共 32 个 HTTP 方法与路径组合；以当前后端注册路由和 Web 调用为依据。

[文档导航](README.md) · [接入与流程](integration.md) · [字段字典](schemas.md) · [OpenAPI](openapi.json)

## 学习通状态错误与缓存

`GET /api/v1/chaoxing/status` 的正常 HTTP/网络不可达仍返回 `status="unavailable"`，结果去重缓存 30 秒。意外服务端程序错误进入统一 500 `INTERNAL_ERROR` 信封，不把错误缓存为不可达，也不覆盖最近已知的登录态；可通过 `X-Request-ID` 定位。成功响应及过期登录态协议不变，客户端应区分 HTTP 错误和成功响应中的 status。Web、Android、HarmonyOS、微信小程序的状态接入源码已核对，本次运行验证仅覆盖后端与 Web 调用对照，移动端未进行原生构建或真机验收。

## 接口索引

| 方法 | 完整路径 | 用途 |
| --- | --- | --- |
| POST | `/api/v1/chaoxing/login` | 登录学习通 |
| GET | `/api/v1/chaoxing/status` | 读取学习通状态 |
| POST | `/api/v1/chaoxing/sync` | 同步学习通 |
| POST | `/api/v1/chaoxing/disconnect` | 断开连接学习通 |
| GET | `/api/v1/academic/providers` | [deprecated] 委托 EduConnector.detect |
| GET | `/api/v1/academic/status` | [deprecated] 委托 EduConnector.get_binding |
| POST | `/api/v1/academic/bind` | [deprecated] 委托 EduConnector.bind |
| DELETE | `/api/v1/academic/binding` | [deprecated] 委托 EduConnector.unbind |
| GET | `/api/v1/edu/detect` | 探测学校教务厂商与系统类型（不编造 URL） |
| GET | `/api/v1/edu/config/{university_id}` | 获取学校教务系统配置 |
| GET | `/api/v1/edu/binding` | 获取当前用户教务绑定（不含凭证） |
| POST | `/api/v1/edu/bind` | [deprecated] 兼容旧版一次性绑定接口 |
| DELETE | `/api/v1/edu/binding` | 解绑教务账号 |
| POST | `/api/v1/edu/sync/profile` | 同步profile |
| POST | `/api/v1/edu/sync/schedule` | 同步课表 |
| POST | `/api/v1/edu/sync/grade` | 同步成绩 |
| POST | `/api/v1/edu/sync/exam` | 同步考试 |
| GET | `/api/v1/edu/sync/records` | 列出同步记录 |
| GET | `/api/v1/edu/schedule/semesters` | 列出已同步课表的所有学期 |
| GET | `/api/v1/edu/schedule/items` | 读取已持久化的课表条目 |
| GET | `/api/v1/edu/grade/semesters` | 列出已同步成绩的所有学期 |
| GET | `/api/v1/edu/grade/items` | 读取已持久化的成绩条目 |
| GET | `/api/v1/edu/exam/semesters` | 列出已同步考试安排的所有学期 |
| GET | `/api/v1/edu/exam/items` | 读取已持久化的考试安排，补考通过 exam_type 区分 |
| GET | `/api/v1/edu/systems/{university_id}` | 列出学校的所有教务系统（1:N） |
| POST | `/api/v1/edu/connections` | 创建教务连接（返回 connection_id + 初始状态） |
| GET | `/api/v1/edu/connections/{connection_id}` | 读取教务连接 |
| POST | `/api/v1/edu/connections/{connection_id}/pre-login` | 预登录：获取验证码图片等预登录数据 |
| POST | `/api/v1/edu/connections/{connection_id}/continue` | 推进连接状态 |
| POST | `/api/v1/edu/connections/from-url` | 从教务系统 URL 创建连接（便捷流程） |
| POST | `/api/v1/edu/discovery/probe` | 探测教务系统 URL（不需要 university_id） |
| POST | `/api/v1/edu/discovery/submit-url` | 用户手动提交教务系统 URL |

## 接口契约

### `POST /api/v1/chaoxing/login`

用途：登录学习通。

鉴权：Bearer access token；角色 student。

实现：[backend/app/api/routes/chaoxing.py](../../backend/app/api/routes/chaoxing.py)，`login_chaoxing`。

Web 封装：`loginChaoxing`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

学习通错误属于第三方账号连接状态，不能因第三方 401 清除 CampusMate 登录态；同步返回分区状态及警告，见 [响应补充](response-contracts.md#sync)。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：`application/json`，必填；[ChaoxingLoginRequest](schemas.md#schema-chaoxingloginrequest)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `username` | string | 是 | — | 登录用户名 |
| `password` | string | 是 | — | 登录密码，仅请求使用 |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "username": "<username>",
  "password": "<password>"
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | 动态响应；见下方补充与 response-contracts.md |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

实际响应补充：动态对象、透传、文件和流式返回不能由默认 OpenAPI 完整表达；业务字段说明在 [响应补充](response-contracts.md)。下面列出实现中的返回构造式，变量代表运行时值，并非 JSON 示例。

```python
{'status': 'success'}
```

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 401 | HTTPException | f'Chaoxing login failed: {msg}' |
| 403 | HTTPException | 'reauth_required / verification_required' |

### `GET /api/v1/chaoxing/status`

用途：读取学习通状态。

鉴权：Bearer access token；角色 student。

实现：[backend/app/api/routes/chaoxing.py](../../backend/app/api/routes/chaoxing.py)，`get_chaoxing_status`。

Web 封装：`getChaoxingStatus`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

学习通错误属于第三方账号连接状态，不能因第三方 401 清除 CampusMate 登录态；同步返回分区状态及警告，见 [响应补充](response-contracts.md#sync)。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [ChaoxingSyncStatus](schemas.md#schema-chaoxingsyncstatus) |
| 503 | application/json | `code: CHAOXING_CREDENTIALS_UNAVAILABLE`；已有连接信息无法解密或损坏，保留已同步数据，重新登录学习通或解除连接后重绑；等待和自动重试无法修复 |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `last_synced_at` | string / null | 否 | — | — |
| `source` | string / null | 否 | — | 来源 |
| `courses` | integer | 否 | default=0 | — |
| `teachers` | integer | 否 | default=0 | — |
| `pending_assignments` | integer | 否 | default=0 | — |
| `notices` | integer | 否 | default=0 | — |
| `warnings` | array<string> | 否 | — | 警告列表；成功也需展示降级或缺失数据 |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `POST /api/v1/chaoxing/sync`

用途：同步学习通。

鉴权：Bearer access token；角色 student。

实现：[backend/app/api/routes/chaoxing.py](../../backend/app/api/routes/chaoxing.py)，`sync_chaoxing`。

Web 封装：`syncChaoxing`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

学习通错误属于第三方账号连接状态，不能因第三方 401 清除 CampusMate 登录态；同步返回分区状态及警告，见 [响应补充](response-contracts.md#sync)。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | 动态响应；见下方补充与 response-contracts.md |

实际响应补充：动态对象、透传、文件和流式返回不能由默认 OpenAPI 完整表达；业务字段说明在 [响应补充](response-contracts.md)。下面列出实现中的返回构造式，变量代表运行时值，并非 JSON 示例。

```python
await _perform_sync_chaoxing(user, container)
```

```python
{'status': 'sync completed', 'notice_sync': 'available' if notice_sync_available else 'unavailable', 'source': 'chaoxing_live', 'complete': all((section['status'] == 'complete' for section in sections.values())), 'warnings': warnings, 'stats': stats, 'sections': sections}
```

```python
container.notice_extraction.extract_bounded(content, source_name=course['name'], published_at=published_at)
```

自动同步使用有界规则提取，不调用外部 LLM。空文本、超过 5000 字及其他提取失败会保留通知原文，继续处理后续通知，但 `sections.notices` 不会标记为 `complete`，并在警告与错误码中说明处理失败；后续同步可在原通知上重试生成待办。

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 409 | HTTPException | 'sync_in_progress' |
| 503 | CHAOXING_CREDENTIALS_UNAVAILABLE | 连接信息无法读取，请重新连接学习通；不应自动反复重试 |
| 401 | HTTPException | 'Chaoxing credentials not found' |
| 401 | HTTPException | 'reauth_required' |
| 403 | HTTPException | 'verification_required' |
| 502 | HTTPException | f'Sync failed: {error_msg}' |
| 依业务分支 | _fetch_http_exception | error |

### `POST /api/v1/chaoxing/disconnect`

用途：断开连接学习通。

鉴权：Bearer access token；角色 student。

实现：[backend/app/api/routes/chaoxing.py](../../backend/app/api/routes/chaoxing.py)，`disconnect_chaoxing`。

Web 封装：`disconnectChaoxing`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

学习通错误属于第三方账号连接状态，不能因第三方 401 清除 CampusMate 登录态；同步返回分区状态及警告，见 [响应补充](response-contracts.md#sync)。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | 动态响应；见下方补充与 response-contracts.md |

实际响应补充：动态对象、透传、文件和流式返回不能由默认 OpenAPI 完整表达；业务字段说明在 [响应补充](response-contracts.md)。下面列出实现中的返回构造式，变量代表运行时值，并非 JSON 示例。

```python
{'status': 'disconnected'}
```

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/academic/providers`

用途：[deprecated] 委托 EduConnector.detect。

鉴权：Bearer access token；角色 student。

实现：[backend/app/api/routes/academic.py](../../backend/app/api/routes/academic.py)，`providers`。

Web 封装：`getAcademicProviders`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

[deprecated] 委托 EduConnector.detect。

兼容接口，建议新前端使用 `/edu/*`。POST /academic/bind 始终返回 ACADEMIC_UNSUPPORTED（409），并未完成绑定。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | 动态响应；见下方补充与 response-contracts.md |

实际响应补充：动态对象、透传、文件和流式返回不能由默认 OpenAPI 完整表达；业务字段说明在 [响应补充](response-contracts.md)。下面列出实现中的返回构造式，变量代表运行时值，并非 JSON 示例。

```python
{'items': [{'university_id': university.id, 'provider': detect.provider, 'status': 'available' if supported else 'unsupported', 'supports': ['courses', 'schedule', 'grades', 'exams'] if supported else []}], '_deprecated': 'Use GET /api/v1/edu/detect instead'}
```

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 409 | UNIVERSITY_REQUIRED | 请先选择你的大学 |

### `GET /api/v1/academic/status`

用途：[deprecated] 委托 EduConnector.get_binding。

鉴权：Bearer access token；角色 student。

实现：[backend/app/api/routes/academic.py](../../backend/app/api/routes/academic.py)，`status`。

Web 封装：`getAcademicStatus`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

[deprecated] 委托 EduConnector.get_binding。

兼容接口，建议新前端使用 `/edu/*`。POST /academic/bind 始终返回 ACADEMIC_UNSUPPORTED（409），并未完成绑定。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | 动态响应；见下方补充与 response-contracts.md |

实际响应补充：动态对象、透传、文件和流式返回不能由默认 OpenAPI 完整表达；业务字段说明在 [响应补充](response-contracts.md)。下面列出实现中的返回构造式，变量代表运行时值，并非 JSON 示例。

```python
{'status': binding.connection_status, 'provider': binding.provider, 'last_synced_at': binding.last_synced_at, 'external_student_id': binding.external_student_id, '_deprecated': 'Use GET /api/v1/edu/binding instead'}
```

```python
{'status': 'unsupported' if not detect.detected else 'unbound', 'provider': detect.provider, 'last_synced_at': None, 'external_student_id': None, '_deprecated': 'Use GET /api/v1/edu/binding instead'}
```

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 409 | UNIVERSITY_REQUIRED | 请先选择你的大学 |

### `POST /api/v1/academic/bind`

用途：[deprecated] 委托 EduConnector.bind。

鉴权：Bearer access token；角色 student。

实现：[backend/app/api/routes/academic.py](../../backend/app/api/routes/academic.py)，`bind`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

[deprecated] 委托 EduConnector.bind。

兼容接口，建议新前端使用 `/edu/*`。POST /academic/bind 始终返回 ACADEMIC_UNSUPPORTED（409），并未完成绑定。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：`application/json`，必填；[AcademicBindRequest](schemas.md#schema-academicbindrequest)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `username` | string | 是 | minLength=1; maxLength=128 | 登录用户名 |
| `password` | string (password) | 是 | format="password"; writeOnly=true | 登录密码，仅请求使用 |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "username": "<username>",
  "password": "<password>"
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | 动态响应；见下方补充与 response-contracts.md |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

实际响应补充：动态对象、透传、文件和流式返回不能由默认 OpenAPI 完整表达；业务字段说明在 [响应补充](response-contracts.md)。下面列出实现中的返回构造式，变量代表运行时值，并非 JSON 示例。

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 409 | ACADEMIC_UNSUPPORTED | 当前学校暂未支持自动教务同步 |

### `DELETE /api/v1/academic/binding`

用途：[deprecated] 委托 EduConnector.unbind。

鉴权：Bearer access token；角色 student。

实现：[backend/app/api/routes/academic.py](../../backend/app/api/routes/academic.py)，`disconnect`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

[deprecated] 委托 EduConnector.unbind。

兼容接口，建议新前端使用 `/edu/*`。POST /academic/bind 始终返回 ACADEMIC_UNSUPPORTED（409），并未完成绑定。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | 动态响应；见下方补充与 response-contracts.md |

实际响应补充：动态对象、透传、文件和流式返回不能由默认 OpenAPI 完整表达；业务字段说明在 [响应补充](response-contracts.md)。下面列出实现中的返回构造式，变量代表运行时值，并非 JSON 示例。

```python
{'ok': True, '_deprecated': 'Use DELETE /api/v1/edu/binding instead'}
```

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/edu/detect`

用途：探测学校教务厂商与系统类型（不编造 URL）。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/edu.py](../../backend/app/api/routes/edu.py)，`detect_university`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

探测学校教务厂商与系统类型（不编造 URL）。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| query | `university_id` | string | 是 | minLength=1; maxLength=128 | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [EduDetectResult](schemas.md#schema-edudetectresult) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `university_id` | string | 是 | — | — |
| `provider` | string | 是 | — | — |
| `system_type` | string | 是 | — | — |
| `detected` | boolean | 是 | — | — |
| `confidence` | number | 否 | default=0.0 | — |
| `evidence` | array<object> | 否 | — | — |
| `detection_source` | string | 否 | default="UNKNOWN" | — |
| `reason` | string / null | 否 | — | 原因 |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/edu/config/{university_id}`

用途：获取学校教务系统配置。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/edu.py](../../backend/app/api/routes/edu.py)，`get_config`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

获取学校教务系统配置。

若不存在，自动创建默认配置（所有 URL=null, url_status=not_discovered）。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `university_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [EduSystemConfigOut](schemas.md#schema-edusystemconfigout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `university_id` | string | 是 | — | — |
| `provider` | string | 是 | — | — |
| `system_type` | string | 是 | — | — |
| `academic_system_url` | string / null | 否 | — | — |
| `academic_system_url_status` | string | 是 | — | — |
| `undergrad_system_url` | string / null | 否 | — | — |
| `undergrad_system_url_status` | string | 是 | — | — |
| `postgrad_system_url` | string / null | 否 | — | — |
| `postgrad_system_url_status` | string | 是 | — | — |
| `sso_url` | string / null | 否 | — | — |
| `sso_url_status` | string | 是 | — | — |
| `cas_url` | string / null | 否 | — | — |
| `cas_url_status` | string | 是 | — | — |
| `webvpn_url` | string / null | 否 | — | — |
| `webvpn_url_status` | string | 是 | — | — |
| `login_method` | string | 是 | — | — |
| `captcha_type` | string | 是 | — | — |
| `requires_campus_network` | boolean / null | 否 | — | — |
| `supported_features` | array<string> | 否 | — | — |
| `school_code` | string / null | 否 | — | 学校代码 |
| `notes` | string / null | 否 | — | — |
| `data_source` | string | 是 | — | — |
| `created_at` | string | 是 | — | 创建时间 |
| `updated_at` | string | 是 | — | 最近更新时间 |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/edu/binding`

用途：获取当前用户教务绑定（不含凭证）。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/edu.py](../../backend/app/api/routes/edu.py)，`get_binding`。

Web 封装：`getEduBinding`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

获取当前用户教务绑定（不含凭证）。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [EduBindingOut](schemas.md#schema-edubindingout) / null |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `POST /api/v1/edu/bind`

用途：[deprecated] 兼容旧版一次性绑定接口。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/edu.py](../../backend/app/api/routes/edu.py)，`bind`。

Web 封装：`bindEdu`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

[deprecated] 兼容旧版一次性绑定接口。

新客户端应使用 EduConnection：创建连接后调用 continue，认证成功再生成 EduBinding。
本兼容端点仍委托同一个 EduConnector/Session/Binding 存储链路，并通过响应头提示迁移。

需要先选择大学（PUT /profile/university）。
username/password 仅用于一次认证，不会明文存储。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：`application/json`，必填；[EduBindRequest](schemas.md#schema-edubindrequest)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `username` | string | 是 | minLength=1; maxLength=128 | 登录用户名 |
| `password` | string (password) | 是 | format="password"; writeOnly=true | 登录密码，仅请求使用 |
| `system_type` | string | 否 | default="undergrad" | undergrad / postgrad |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "username": "<username>",
  "password": "<password>"
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [EduBindingOut](schemas.md#schema-edubindingout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `user_id` | string | 是 | — | 所属用户标识 |
| `edu_system_id` | string / null | 否 | — | — |
| `university_id` | string | 是 | — | — |
| `provider` | string | 是 | — | — |
| `supported_features` | array<string> | 否 | — | — |
| `system_type` | string | 是 | — | — |
| `external_student_id` | string / null | 否 | — | — |
| `external_student_name` | string / null | 否 | — | — |
| `connection_status` | string | 是 | — | — |
| `session_type` | string / null | 否 | — | — |
| `last_authenticated_at` | string / null | 否 | — | — |
| `session_expires_at` | string / null | 否 | — | — |
| `last_synced_at` | string / null | 否 | — | — |
| `last_sync_status` | string / null | 否 | — | — |
| `last_error` | string / null | 否 | — | — |
| `created_at` | string | 是 | — | 创建时间 |
| `updated_at` | string | 是 | — | 最近更新时间 |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 409 | UNIVERSITY_REQUIRED | 请先选择你的大学 |
| 401 | 'EDU_LOGIN_FAILED' | 服务器内部错误 |
| 503 | 'EDU_ADAPTER_UNAVAILABLE' | 服务器内部错误 |

### `DELETE /api/v1/edu/binding`

用途：解绑教务账号。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/edu.py](../../backend/app/api/routes/edu.py)，`unbind`。

Web 封装：`unbindEdu`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

解绑教务账号。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | 动态响应；见下方补充与 response-contracts.md |

实际响应补充：动态对象、透传、文件和流式返回不能由默认 OpenAPI 完整表达；业务字段说明在 [响应补充](response-contracts.md)。下面列出实现中的返回构造式，变量代表运行时值，并非 JSON 示例。

```python
{'ok': True}
```

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `POST /api/v1/edu/sync/profile`

用途：同步profile。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/edu.py](../../backend/app/api/routes/edu.py)，`sync_profile`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [EduSyncResult](schemas.md#schema-edusyncresult) |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `sync_type` | string | 是 | — | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `items_count` | integer | 否 | default=0 | — |
| `error_message` | string / null | 否 | — | — |
| `profile` | [EduProfile](schemas.md#schema-eduprofile) / null | 否 | — | — |
| `schedule` | [EduSchedule](schemas.md#schema-eduschedule) / null | 否 | — | — |
| `grade` | [EduGrade](schemas.md#schema-edugrade) / null | 否 | — | — |
| `exam` | [EduExam](schemas.md#schema-eduexam) / null | 否 | — | — |
| `inserted` | integer | 否 | default=0 | — |
| `updated` | integer | 否 | default=0 | — |
| `unchanged` | integer | 否 | default=0 | — |
| `removed` | integer | 否 | default=0 | — |
| `failed` | integer | 否 | default=0 | — |
| `sync_batch_id` | string / null | 否 | — | — |
| `semester` | string / null | 否 | — | — |
| `persisted` | boolean | 否 | default=false | — |
| `stage` | string / null | 否 | — | — |
| `previous_schedule_preserved` | boolean / null | 否 | — | — |
| `requires_user_action` | string / null | 否 | — | — |
| `protocol_source` | string / null | 否 | — | — |

未绑定教务账号时**不返回 404**：接口仍是 HTTP 200，`status="failed"`、`error_message="未绑定教务账号"`，其余字段为默认值。客户端必须检查业务 `status`，不能只看 HTTP 状态码。

```json
{
  "sync_type": "profile",
  "status": "failed",
  "items_count": 0,
  "error_message": "未绑定教务账号",
  "inserted": 0,
  "updated": 0,
  "unchanged": 0,
  "removed": 0,
  "failed": 0,
  "persisted": false
}
```

契约未变更：这里刻意保持 HTTP 200 + `status=failed`，**没有**为匹配错误字典改成 404；客户端不能只按 HTTP 状态码判断成功。四个 sync 接口的实际调用方为 Web（`syncEdu`）、Android（`ApiService` 的 `edu/sync/*`）、HarmonyOS（`ApiClient` 的 `eduSync`）和微信小程序（`repository.ts`），本轮仅核对了源码调用点与既有 `status` 分支，未做四端运行时验收。

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `POST /api/v1/edu/sync/schedule`

用途：同步课表。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/edu.py](../../backend/app/api/routes/edu.py)，`sync_schedule`。

Web 封装：`syncEdu`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| query | `semester` | string / null | 否 | string约束: maxLength=64 | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [EduSyncResult](schemas.md#schema-edusyncresult) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `sync_type` | string | 是 | — | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `items_count` | integer | 否 | default=0 | — |
| `error_message` | string / null | 否 | — | — |
| `profile` | [EduProfile](schemas.md#schema-eduprofile) / null | 否 | — | — |
| `schedule` | [EduSchedule](schemas.md#schema-eduschedule) / null | 否 | — | — |
| `grade` | [EduGrade](schemas.md#schema-edugrade) / null | 否 | — | — |
| `exam` | [EduExam](schemas.md#schema-eduexam) / null | 否 | — | — |
| `inserted` | integer | 否 | default=0 | — |
| `updated` | integer | 否 | default=0 | — |
| `unchanged` | integer | 否 | default=0 | — |
| `removed` | integer | 否 | default=0 | — |
| `failed` | integer | 否 | default=0 | — |
| `sync_batch_id` | string / null | 否 | — | — |
| `semester` | string / null | 否 | — | — |
| `persisted` | boolean | 否 | default=false | — |
| `stage` | string / null | 否 | — | — |
| `previous_schedule_preserved` | boolean / null | 否 | — | — |
| `requires_user_action` | string / null | 否 | — | — |
| `protocol_source` | string / null | 否 | — | — |

未绑定教务账号时**不返回 404**：接口仍是 HTTP 200，`status="failed"`、`error_message="未绑定教务账号"`，其余字段为默认值。客户端必须检查业务 `status`，不能只看 HTTP 状态码。

```json
{
  "sync_type": "schedule",
  "status": "failed",
  "items_count": 0,
  "error_message": "未绑定教务账号",
  "inserted": 0,
  "updated": 0,
  "unchanged": 0,
  "removed": 0,
  "failed": 0,
  "persisted": false
}
```

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `POST /api/v1/edu/sync/grade`

用途：同步成绩。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/edu.py](../../backend/app/api/routes/edu.py)，`sync_grade`。

Web 封装：`syncEdu`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| query | `semester` | string / null | 否 | string约束: maxLength=64 | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [EduSyncResult](schemas.md#schema-edusyncresult) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `sync_type` | string | 是 | — | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `items_count` | integer | 否 | default=0 | — |
| `error_message` | string / null | 否 | — | — |
| `profile` | [EduProfile](schemas.md#schema-eduprofile) / null | 否 | — | — |
| `schedule` | [EduSchedule](schemas.md#schema-eduschedule) / null | 否 | — | — |
| `grade` | [EduGrade](schemas.md#schema-edugrade) / null | 否 | — | — |
| `exam` | [EduExam](schemas.md#schema-eduexam) / null | 否 | — | — |
| `inserted` | integer | 否 | default=0 | — |
| `updated` | integer | 否 | default=0 | — |
| `unchanged` | integer | 否 | default=0 | — |
| `removed` | integer | 否 | default=0 | — |
| `failed` | integer | 否 | default=0 | — |
| `sync_batch_id` | string / null | 否 | — | — |
| `semester` | string / null | 否 | — | — |
| `persisted` | boolean | 否 | default=false | — |
| `stage` | string / null | 否 | — | — |
| `previous_schedule_preserved` | boolean / null | 否 | — | — |
| `requires_user_action` | string / null | 否 | — | — |
| `protocol_source` | string / null | 否 | — | — |

未绑定教务账号时**不返回 404**：接口仍是 HTTP 200，`status="failed"`、`error_message="未绑定教务账号"`，其余字段为默认值。客户端必须检查业务 `status`，不能只看 HTTP 状态码。

```json
{
  "sync_type": "grade",
  "status": "failed",
  "items_count": 0,
  "error_message": "未绑定教务账号",
  "inserted": 0,
  "updated": 0,
  "unchanged": 0,
  "removed": 0,
  "failed": 0,
  "persisted": false
}
```

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `POST /api/v1/edu/sync/exam`

用途：同步考试。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/edu.py](../../backend/app/api/routes/edu.py)，`sync_exam`。

Web 封装：`syncEdu`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| query | `semester` | string / null | 否 | string约束: maxLength=64 | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [EduSyncResult](schemas.md#schema-edusyncresult) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `sync_type` | string | 是 | — | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `items_count` | integer | 否 | default=0 | — |
| `error_message` | string / null | 否 | — | — |
| `profile` | [EduProfile](schemas.md#schema-eduprofile) / null | 否 | — | — |
| `schedule` | [EduSchedule](schemas.md#schema-eduschedule) / null | 否 | — | — |
| `grade` | [EduGrade](schemas.md#schema-edugrade) / null | 否 | — | — |
| `exam` | [EduExam](schemas.md#schema-eduexam) / null | 否 | — | — |
| `inserted` | integer | 否 | default=0 | — |
| `updated` | integer | 否 | default=0 | — |
| `unchanged` | integer | 否 | default=0 | — |
| `removed` | integer | 否 | default=0 | — |
| `failed` | integer | 否 | default=0 | — |
| `sync_batch_id` | string / null | 否 | — | — |
| `semester` | string / null | 否 | — | — |
| `persisted` | boolean | 否 | default=false | — |
| `stage` | string / null | 否 | — | — |
| `previous_schedule_preserved` | boolean / null | 否 | — | — |
| `requires_user_action` | string / null | 否 | — | — |
| `protocol_source` | string / null | 否 | — | — |

未绑定教务账号时**不返回 404**：接口仍是 HTTP 200，`status="failed"`、`error_message="未绑定教务账号"`，其余字段为默认值。客户端必须检查业务 `status`，不能只看 HTTP 状态码。

```json
{
  "sync_type": "exam",
  "status": "failed",
  "items_count": 0,
  "error_message": "未绑定教务账号",
  "inserted": 0,
  "updated": 0,
  "unchanged": 0,
  "removed": 0,
  "failed": 0,
  "persisted": false
}
```

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/edu/sync/records`

用途：列出同步记录。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/edu.py](../../backend/app/api/routes/edu.py)，`list_sync_records`。

Web 封装：`getEduSyncRecords`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| query | `limit` | integer | 否 | default=20; minimum=1; maximum=100 | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | array<[EduSyncRecordOut](schemas.md#schema-edusyncrecordout)> |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/edu/schedule/semesters`

用途：列出已同步课表的所有学期。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/edu.py](../../backend/app/api/routes/edu.py)，`list_schedule_semesters`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

列出已同步课表的所有学期。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | array<string> |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/edu/schedule/items`

用途：读取已持久化的课表条目。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/edu.py](../../backend/app/api/routes/edu.py)，`list_schedule_items`。

Web 封装：`getScheduleItems`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

读取已持久化的课表条目。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| query | `semester` | string / null | 否 | — | — |
| query | `include_stale` | boolean | 否 | default=false | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | 动态响应；见下方补充与 response-contracts.md |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

实际响应补充：动态对象、透传、文件和流式返回不能由默认 OpenAPI 完整表达；业务字段说明在 [响应补充](response-contracts.md)。下面列出实现中的返回构造式，变量代表运行时值，并非 JSON 示例。

```python
{'semester': semester, 'items_count': len(items), 'items': [{'id': it.id, 'semester': it.semester, 'course_code': it.course_code, 'course_name': it.course_name, 'teacher': it.teacher, 'teachers': it.teachers, 'location': it.location, 'campus': it.campus, 'building': it.building, 'classroom': it.classroom, 'weekday': it.weekday, 'start_section': it.start_section, 'end_section': it.end_section, 'start_time': it.start_time, 'end_time': it.end_time, 'weeks': it.weeks, 'week_text': it.week_text, 'credit': it.credit, 'course_nature': it.course_nature, 'course_category': it.course_category, 'course_type': it.course_type, 'teaching_class': it.teaching_class, 'class_name': it.class_name, 'college': it.college, 'department': it.department, 'assessment_method': it.assessment_method, 'exam_type': it.exam_type, 'total_hours': it.total_hours, 'theory_hours': it.theory_hours, 'practice_hours': it.practice_hours, 'language': it.language, 'note': it.note, 'semester_id': it.semester_id, 'extra_info': it.extra_info, 'is_stale': it.is_stale, 'last_seen_at': it.last_seen_at} for it in items]}
```

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/edu/grade/semesters`

用途：列出已同步成绩的所有学期。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/edu.py](../../backend/app/api/routes/edu.py)，`list_grade_semesters`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

列出已同步成绩的所有学期。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | array<string> |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/edu/grade/items`

用途：读取已持久化的成绩条目。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/edu.py](../../backend/app/api/routes/edu.py)，`list_grade_items`。

Web 封装：`getGradeItems`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

读取已持久化的成绩条目。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| query | `semester` | string / null | 否 | — | — |
| query | `include_stale` | boolean | 否 | default=false | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | 动态响应；见下方补充与 response-contracts.md |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

实际响应补充：动态对象、透传、文件和流式返回不能由默认 OpenAPI 完整表达；业务字段说明在 [响应补充](response-contracts.md)。下面列出实现中的返回构造式，变量代表运行时值，并非 JSON 示例。

```python
{'semester': semester, 'items_count': len(items), 'items': [{'id': it.id, 'semester': it.semester, 'course_code': it.course_code, 'course_name': it.course_name, 'credit': it.credit, 'score': it.score, 'grade_point': it.grade_point, 'category': it.category, 'status': it.status, 'is_stale': it.is_stale, 'last_seen_at': it.last_seen_at} for it in items]}
```

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/edu/exam/semesters`

用途：列出已同步考试安排的所有学期。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/edu.py](../../backend/app/api/routes/edu.py)，`list_exam_semesters`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

列出已同步考试安排的所有学期。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | array<string> |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/edu/exam/items`

用途：读取已持久化的考试安排，补考通过 exam_type 区分。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/edu.py](../../backend/app/api/routes/edu.py)，`list_exam_items`。

Web 封装：`getExamItems`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

读取已持久化的考试安排，补考通过 exam_type 区分。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| query | `semester` | string / null | 否 | — | — |
| query | `include_stale` | boolean | 否 | default=false | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | 动态响应；见下方补充与 response-contracts.md |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

实际响应补充：动态对象、透传、文件和流式返回不能由默认 OpenAPI 完整表达；业务字段说明在 [响应补充](response-contracts.md)。下面列出实现中的返回构造式，变量代表运行时值，并非 JSON 示例。

```python
{'semester': semester, 'items_count': len(items), 'items': [{'id': item.id, 'semester': item.semester, 'course_code': item.course_code, 'course_name': item.course_name, 'exam_type': item.exam_type, 'location': item.location, 'seat': item.seat, 'starts_at': item.starts_at, 'ends_at': item.ends_at, 'notes': item.notes, 'is_stale': item.is_stale, 'last_seen_at': item.last_seen_at} for item in items]}
```

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/edu/systems/{university_id}`

用途：列出学校的所有教务系统（1:N）。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/edu.py](../../backend/app/api/routes/edu.py)，`list_systems`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

列出学校的所有教务系统（1:N）。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `university_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | array<[EduSystemOut](schemas.md#schema-edusystemout)> |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `POST /api/v1/edu/connections`

用途：创建教务连接（返回 connection_id + 初始状态）。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/edu.py](../../backend/app/api/routes/edu.py)，`create_connection`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

创建教务连接（返回 connection_id + 初始状态）。

不默认上传账号密码。后续通过 /connections/{id}/continue 推进状态。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：`application/json`，必填；[EduConnectionCreate](schemas.md#schema-educonnectioncreate)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `edu_system_id` | string | 是 | minLength=1; maxLength=128 | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "edu_system_id": "<edu_system_id>"
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [EduConnectionOut](schemas.md#schema-educonnectionout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `user_id` | string | 是 | — | 所属用户标识 |
| `edu_system_id` | string | 是 | — | — |
| `university_id` | string | 是 | — | — |
| `state` | string | 是 | — | — |
| `provider` | string | 是 | — | — |
| `login_execution_mode` | string | 是 | — | — |
| `portal_url` | string / null | 否 | — | — |
| `allowed_origins` | array<string> | 否 | maxItems=8 | — |
| `external_student_id` | string / null | 否 | — | — |
| `external_student_name` | string / null | 否 | — | — |
| `error_code` | string / null | 否 | — | 失败码，可空 |
| `error_message` | string / null | 否 | — | — |
| `created_at` | string | 是 | — | 创建时间 |
| `updated_at` | string | 是 | — | 最近更新时间 |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | 'EDU_SYSTEM_NOT_FOUND' | 服务器内部错误 |
| 409 | UNIVERSITY_REQUIRED | 请先选择你的大学 |
| 403 | FORBIDDEN | 无权访问该资源。 |

### `GET /api/v1/edu/connections/{connection_id}`

用途：读取教务连接。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/edu.py](../../backend/app/api/routes/edu.py)，`get_connection`。

Web 封装：`getEduConnection`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `connection_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [EduConnectionOut](schemas.md#schema-educonnectionout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `user_id` | string | 是 | — | 所属用户标识 |
| `edu_system_id` | string | 是 | — | — |
| `university_id` | string | 是 | — | — |
| `state` | string | 是 | — | — |
| `provider` | string | 是 | — | — |
| `login_execution_mode` | string | 是 | — | — |
| `portal_url` | string / null | 否 | — | — |
| `allowed_origins` | array<string> | 否 | maxItems=8 | — |
| `external_student_id` | string / null | 否 | — | — |
| `external_student_name` | string / null | 否 | — | — |
| `error_code` | string / null | 否 | — | 失败码，可空 |
| `error_message` | string / null | 否 | — | — |
| `created_at` | string | 是 | — | 创建时间 |
| `updated_at` | string | 是 | — | 最近更新时间 |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | 'EDU_CONNECTION_NOT_FOUND' | 服务器内部错误 |
| 403 | FORBIDDEN | 无权访问该资源。 |

### `POST /api/v1/edu/connections/{connection_id}/pre-login`

用途：预登录：获取验证码图片等预登录数据。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/edu.py](../../backend/app/api/routes/edu.py)，`pre_login`。

Web 封装：`preLoginEdu`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

预登录：获取验证码图片等预登录数据。

流程：
1. 后端 GET 教务登录页，提取验证码图片
2. 返回 pre_login_token + captcha_image_base64
3. 客户端展示验证码图片，用户输入验证码
4. 客户端调用 /continue(action=SUBMIT_WITH_CAPTCHA, pre_login_token, username, password, captcha)

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `connection_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [EduPreLoginResult](schemas.md#schema-edupreloginresult) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `pre_login_token` | string | 是 | — | — |
| `verification_session_id` | string / null | 否 | — | — |
| `captcha_required` | boolean | 是 | — | — |
| `captcha_type` | string | 否 | default="none" | — |
| `challenge_type` | string | 否 | default="none" | — |
| `captcha_image_base64` | string / null | 否 | — | — |
| `captcha_mime_type` | string / null | 否 | — | — |
| `captcha_image_url` | string / null | 否 | — | — |
| `expires_at` | string | 是 | — | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | 'EDU_CONNECTION_NOT_FOUND' | 服务器内部错误 |
| 403 | FORBIDDEN | 无权访问该资源。 |

### `POST /api/v1/edu/connections/{connection_id}/continue`

用途：推进连接状态。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/edu.py](../../backend/app/api/routes/edu.py)，`continue_connection`。

Web 封装：`continueEduConnection`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

推进连接状态。

支持两种路径：
- server_credentials: username + password
- client_webview: action=CLIENT_WEBVIEW_COMPLETE + cookies + current_url + user_agent
- action=POLL: 轮询当前状态
- action=CANCEL: 取消连接
- action=SUBMIT_WITH_CAPTCHA: 携带验证码提交登录（需配合 pre_login_token + captcha）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `connection_id` | string | 是 | — | — |

请求体：`application/json`，必填；[EduConnectionContinue](schemas.md#schema-educonnectioncontinue)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `username` | string / null | 否 | — | 登录用户名 |
| `password` | string (password) / null | 否 | string约束: format="password"; writeOnly=true | 登录密码，仅请求使用 |
| `captcha` | string / null | 否 | — | — |
| `sms_code` | string / null | 否 | — | — |
| `mfa_code` | string / null | 否 | — | — |
| `action` | string / null | 否 | — | — |
| `cookies` | map<string, string> / null | 否 | object约束: additionalProperties={"type": "string"} | — |
| `cookie_jar` | array<[EduCookie](schemas.md#schema-educookie)> | 否 | maxItems=64 | — |
| `current_url` | string / null | 否 | — | — |
| `user_agent` | string / null | 否 | string约束: maxLength=512 | — |
| `pre_login_token` | string / null | 否 | — | — |
| `verification_session_id` | string / null | 否 | — | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [EduConnectionOut](schemas.md#schema-educonnectionout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `user_id` | string | 是 | — | 所属用户标识 |
| `edu_system_id` | string | 是 | — | — |
| `university_id` | string | 是 | — | — |
| `state` | string | 是 | — | — |
| `provider` | string | 是 | — | — |
| `login_execution_mode` | string | 是 | — | — |
| `portal_url` | string / null | 否 | — | — |
| `allowed_origins` | array<string> | 否 | maxItems=8 | — |
| `external_student_id` | string / null | 否 | — | — |
| `external_student_name` | string / null | 否 | — | — |
| `error_code` | string / null | 否 | — | 失败码，可空 |
| `error_message` | string / null | 否 | — | — |
| `created_at` | string | 是 | — | 创建时间 |
| `updated_at` | string | 是 | — | 最近更新时间 |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | 'EDU_CONNECTION_NOT_FOUND' | 服务器内部错误 |
| 403 | FORBIDDEN | 无权访问该资源。 |

### `POST /api/v1/edu/connections/from-url`

用途：从教务系统 URL 创建连接（便捷流程）。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/edu.py](../../backend/app/api/routes/edu.py)，`create_connection_from_url`。

Web 封装：`createEduConnection`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

从教务系统 URL 创建连接（便捷流程）。

1. probe URL 检测 provider
2. ensure_default_system 创建/复用 edu_system
3. create_connection
返回 connection（初始 state=idle），客户端再调 /continue 推进。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：`application/json`，必填；[EduConnectionFromUrlRequest](schemas.md#schema-educonnectionfromurlrequest)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `portal_url` | string | 是 | minLength=1; maxLength=512 | — |
| `university_id` | string / null | 否 | — | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "portal_url": "<portal_url>"
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [EduConnectionOut](schemas.md#schema-educonnectionout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `user_id` | string | 是 | — | 所属用户标识 |
| `edu_system_id` | string | 是 | — | — |
| `university_id` | string | 是 | — | — |
| `state` | string | 是 | — | — |
| `provider` | string | 是 | — | — |
| `login_execution_mode` | string | 是 | — | — |
| `portal_url` | string / null | 否 | — | — |
| `allowed_origins` | array<string> | 否 | maxItems=8 | — |
| `external_student_id` | string / null | 否 | — | — |
| `external_student_name` | string / null | 否 | — | — |
| `error_code` | string / null | 否 | — | 失败码，可空 |
| `error_message` | string / null | 否 | — | — |
| `created_at` | string | 是 | — | 创建时间 |
| `updated_at` | string | 是 | — | 最近更新时间 |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 409 | UNIVERSITY_REQUIRED | 请先选择你的大学 |
| 403 | FORBIDDEN | 无权访问该资源。 |

### `POST /api/v1/edu/discovery/probe`

用途：探测教务系统 URL（不需要 university_id）。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/edu.py](../../backend/app/api/routes/edu.py)，`discovery_probe`。

Web 封装：`probeEduPortal`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

探测教务系统 URL（不需要 university_id）。

只检测 provider/可达性/建议登录模式，不持久化任何数据。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：`application/json`，必填；[EduProbeRequest](schemas.md#schema-eduproberequest)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `portal_url` | string | 是 | minLength=1; maxLength=512 | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "portal_url": "<portal_url>"
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [EduProbeResult](schemas.md#schema-eduproberesult) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `portal_url` | string | 是 | — | — |
| `provider` | string | 否 | default="unknown" | — |
| `provider_confidence` | number | 否 | default=0.0 | — |
| `reachable` | boolean | 否 | default=false | — |
| `http_status` | integer / null | 否 | — | — |
| `final_url` | string / null | 否 | — | — |
| `title` | string / null | 否 | — | 标题 |
| `is_edu_page` | boolean | 否 | default=false | — |
| `suggested_login_mode` | string | 否 | default="backend_http" | — |
| `challenge_type` | string | 否 | default="none" | — |
| `evidence` | array<object> | 否 | — | — |
| `error` | string / null | 否 | — | — |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `POST /api/v1/edu/discovery/submit-url`

用途：用户手动提交教务系统 URL。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/edu.py](../../backend/app/api/routes/edu.py)，`discovery_submit_url`。

Web 封装：当前无封装；按本节后端契约调用。

用户手动提交教务系统 URL。

检测 Provider → 尝试 HTTP 连接 → 保存为 USER_SUBMITTED 候选。
不自动升级 VERIFIED，仅标 CANDIDATE（或 VERIFIED_LIVE 若检测到强信号）。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：`application/json`，必填；[EduDiscoverySubmitUrlRequest](schemas.md#schema-edudiscoverysubmiturlrequest)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `university_id` | string | 是 | — | — |
| `candidate_url` | string | 是 | minLength=1; maxLength=512 | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "university_id": "<university_id>",
  "candidate_url": "<candidate_url>"
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [EduDiscoverySubmitUrlResult](schemas.md#schema-edudiscoverysubmiturlresult) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `school_code` | string / null | 否 | — | 学校代码 |
| `school_name` | string / null | 否 | — | — |
| `candidate_url` | string | 是 | — | — |
| `provider` | string | 否 | default="UNKNOWN" | — |
| `provider_confidence` | number | 否 | default=0.0 | — |
| `reachable` | boolean | 否 | default=false | — |
| `http_status` | integer / null | 否 | — | — |
| `final_url` | string / null | 否 | — | — |
| `title` | string / null | 否 | — | 标题 |
| `is_edu_page` | boolean | 否 | default=false | — |
| `evidence` | array<object> | 否 | — | — |
| `verification_status` | string | 否 | default="CANDIDATE" | — |
| `saved` | boolean | 否 | default=false | — |
| `error` | string / null | 否 | — | — |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。


## 学校 HTTP 请求安全边界

学校 URL 在首次请求及每个重定向处校验。建立 TCP 连接时再次解析并校验全部 DNS 地址，实际连接固定为此次校验通过的 IP；保留原域名的 HTTP Host、TLS SNI 和证书检查，不能通过二次 DNS 解析切换到私网。任一 DNS 地址为 loopback、链路本地、保留地址或默认禁止的私网地址时拒绝连接；解析无有效地址以网络错误处理。已建立的连接池按原 Origin 复用，备用合法 IP 使用同一有界连接超时预算。学校客户端不使用进程的 HTTP(S) 代理变量。

现有仅非生产环境的 `EDU_ALLOW_INSECURE_SSL` 开关仍按原契约控制 TLS 兼容回退，不放松 IP 检查。Web、Android、HarmonyOS、微信小程序请求格式不变，无需端侧适配此连接层修复。
