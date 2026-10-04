# 认证、账号与扫码登录

> 对照日期：2026-09-30。本模块共 17 个 HTTP 方法与路径组合；以当前后端注册路由和 Web 调用为依据。

[文档导航](README.md) · [接入与流程](integration.md) · [字段字典](schemas.md) · [OpenAPI](openapi.json)

## 登录与注册限流

`POST /api/v1/auth/login` 每个来源地址每 60 秒最多 20 次，`POST /api/v1/auth/register` 每 60 秒最多 5 次，成功和失败尝试均计数。限流发生在密码校验和写库前；超限返回 HTTP 429、`RATE_LIMITED`、`Retry-After` 秒数及统一错误信封。来源取服务器识别的连接地址，不自行信任客户端提交的转发头。计数在当前后端进程中维护，重启清空；多进程的额度各自独立。

```json
{"code":"RATE_LIMITED","message":"请求过于频繁，请稍后重试。","details":{"retry_after_seconds":45},"request_id":"req_example"}
```

客户端应按 `Retry-After` 等待后再允许重试，不将 429 当作密码错误或注销凭据。Web、Android、HarmonyOS、微信小程序的登录调用已核对，通用错误流程可处理失败；专门的倒计时提示尚未适配，各移动端本次未编译或真机验证。无需修改成功响应字段。

## 接口索引

| 方法 | 完整路径 | 用途 |
| --- | --- | --- |
| POST | `/api/v1/auth/login` | 登录 |
| POST | `/api/v1/auth/register` | 公开注册接口(无需鉴权) |
| POST | `/api/v1/auth/refresh` | 用 refresh token 换发新的 access token + refresh token |
| POST | `/api/v1/auth/logout` | 撤销当前 refresh token(若有)，并撤销当前浏览器的可信设备凭据 |
| GET | `/api/v1/auth/me` | 当前用户资料 |
| POST | `/api/v1/auth/admin/users` | 管理员创建用户接口(仅 admin 角色) |
| GET | `/api/v1/auth/admin/users` | 管理员列出用户 |
| PATCH | `/api/v1/auth/admin/users/{user_id}` | 管理员更新用户 |
| POST | `/api/v1/auth/qr/create` | Web 创建 QR Login Session(无需鉴权) |
| POST | `/api/v1/auth/qr/scan` | 手机扫码(需登录)。绑定当前手机用户到 session |
| POST | `/api/v1/auth/qr/confirm` | 手机确认登录 Web(需登录) |
| POST | `/api/v1/auth/qr/cancel` | 手机取消登录(需登录) |
| GET | `/api/v1/auth/qr/{session_id}/status` | Web 用 browser_token 查询状态 |
| POST | `/api/v1/auth/qr/exchange` | Web 用 browser_token 兑换登录态(无需鉴权) |
| POST | `/api/v1/auth/trusted-device/auto-login` | 浏览器用可信设备 Cookie 自动登录 |
| GET | `/api/v1/auth/trusted-devices` | 列出当前用户的可信设备 |
| POST | `/api/v1/auth/trusted-device/revoke` | 撤销可信设备 |

## 接口契约

### `POST /api/v1/auth/login`

用途：登录。

鉴权：公开或使用专用凭据（扫码 browser token / 可信设备 cookie 等见参数与流程）。

实现：[backend/app/api/routes/auth.py](../../backend/app/api/routes/auth.py)，`login`。

Web 封装：`login`（[webreact/src/data/http/authEndpoints.js](../../webreact/src/data/http/authEndpoints.js)）

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：`application/json`，必填；[LoginRequest](schemas.md#schema-loginrequest)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `username` | string | 是 | minLength=1; maxLength=64 | 登录用户名 |
| `password` | string | 是 | minLength=1; maxLength=128 | 登录密码，仅请求使用 |

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
| 200 | application/json | [TokenPair](schemas.md#schema-tokenpair) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `access_token` | string | 是 | — | 业务访问令牌 |
| `refresh_token` | string | 是 | — | 换发令牌；不是业务访问凭据 |
| `token_type` | string | 否 | default="Bearer" | 令牌类型 |
| `expires_in` | integer | 是 | — | access token 有效期(秒) |
| `expires_at` | string | 是 | — | access token 到期时间(ISO 8601) |
| `user` | [UserPublic](schemas.md#schema-userpublic) | 是 | — | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 401 | INVALID_CREDENTIALS | 用户名或密码错误。 |

### `POST /api/v1/auth/register`

用途：公开注册接口(无需鉴权)。

鉴权：公开或使用专用凭据（扫码 browser token / 可信设备 cookie 等见参数与流程）。

实现：[backend/app/api/routes/auth.py](../../backend/app/api/routes/auth.py)，`register`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

公开注册接口(无需鉴权)。

限制:
- 仅允许注册 student 角色;admin 必须由管理员通过 /auth/admin/users 创建。
- 注册成功后用户仍需走 /auth/login 登录获取 token(注册不自动登录)。
- 用户名/学号唯一性校验同 admin_create_user。

安全:
- 密码以 PBKDF2-HMAC-SHA256 哈希存储,不返回密码或哈希。
- 返回 UserPublic(不含 password_hash)。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：`application/json`，必填；[RegisterRequest](schemas.md#schema-registerrequest)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `username` | string | 是 | minLength=3; maxLength=64; pattern="^[a-zA-Z0-9_]+$" | 登录用户名 |
| `password` | string | 是 | minLength=8; maxLength=128 | 登录密码，仅请求使用 |
| `role` | string | 否 | default="student"; pattern="^(student)$" | — |
| `display_name` | string / null | 否 | string约束: maxLength=128 | — |
| `student_number` | string / null | 否 | string约束: maxLength=32 | — |
| `teacher_number` | string / null | 否 | string约束: maxLength=32 | 已废弃,仅为兼容旧数据保留 |
| `college` | string / null | 否 | string约束: maxLength=64 | — |
| `major` | string / null | 否 | string约束: maxLength=64 | — |
| `grade` | string / null | 否 | string约束: maxLength=32 | — |

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
| 201 | application/json | [UserPublic](schemas.md#schema-userpublic) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

201 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `username` | string | 是 | — | 登录用户名 |
| `role` | string | 是 | — | — |
| `name` | string | 否 | default="" | 名称 |
| `display_name` | string / null | 否 | — | — |
| `student_number` | string / null | 否 | — | — |
| `teacher_number` | string / null | 否 | — | — |
| `college` | string / null | 否 | — | — |
| `major` | string / null | 否 | — | — |
| `grade` | string / null | 否 | — | — |
| `avatar_url` | string / null | 否 | — | — |
| `university_id` | string / null | 否 | — | — |
| `university_name` | string / null | 否 | — | — |
| `is_active` | boolean | 否 | default=true | — |
| `created_at` | string | 否 | default="" | 创建时间 |
| `updated_at` | string | 否 | default="" | 最近更新时间 |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 422 | VALIDATION_FAILED | '学生角色不应携带 teacher_number' |
| 409 | USERNAME_EXISTS | 用户名已被占用。 |
| 409 | STUDENT_NUMBER_EXISTS | 学号已被占用。 |

### `POST /api/v1/auth/refresh`

用途：用 refresh token 换发新的 access token + refresh token。

鉴权：公开或使用专用凭据（扫码 browser token / 可信设备 cookie 等见参数与流程）。

实现：[backend/app/api/routes/auth.py](../../backend/app/api/routes/auth.py)，`refresh`。

Web 封装：`refreshAccessToken`（[webreact/src/data/http/client.js](../../webreact/src/data/http/client.js)）

用 refresh token 换发新的 access token + refresh token。

旧 refresh token 在换发后被撤销(防止重放)。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：`application/json`，必填；[RefreshRequest](schemas.md#schema-refreshrequest)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `refresh_token` | string | 是 | minLength=1 | 换发令牌；不是业务访问凭据 |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "refresh_token": "<refresh_token>"
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [TokenPair](schemas.md#schema-tokenpair) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `access_token` | string | 是 | — | 业务访问令牌 |
| `refresh_token` | string | 是 | — | 换发令牌；不是业务访问凭据 |
| `token_type` | string | 否 | default="Bearer" | 令牌类型 |
| `expires_in` | integer | 是 | — | access token 有效期(秒) |
| `expires_at` | string | 是 | — | access token 到期时间(ISO 8601) |
| `user` | [UserPublic](schemas.md#schema-userpublic) | 是 | — | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 401 | UNAUTHORIZED | 'token 类型错误,期望 refresh token' |
| 401 | UNAUTHORIZED | 'refresh token 已失效或不存在' |
| 401 | UNAUTHORIZED | 'refresh token 已过期' |
| 401 | UNAUTHORIZED | '用户不存在或已停用' |
| 401 | UNAUTHORIZED | f'refresh token 无效: {e}' |

### `POST /api/v1/auth/logout`

用途：撤销当前 refresh token(若有)，并撤销当前浏览器的可信设备凭据。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/auth.py](../../backend/app/api/routes/auth.py)，`logout`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

撤销当前 refresh token(若有)，并撤销当前浏览器的可信设备凭据。

可信设备凭据由 HttpOnly cookie 携带；默认名 campus_trusted_device，可由配置覆盖，Path=/api/v1/auth。使用 credentials/include 或 Axios withCredentials；JavaScript 不读取 cookie 值。具体清除和撤销流程见 [认证接入](integration.md#auth)。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：`application/json`，必填；[LogoutRequest](schemas.md#schema-logoutrequest)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `refresh_token` | string / null | 否 | — | 换发令牌；不是业务访问凭据 |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | 动态响应；见下方补充与 response-contracts.md |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

实际响应补充：动态对象、透传、文件和流式返回不能由默认 OpenAPI 完整表达；业务字段说明在 [响应补充](response-contracts.md)。下面列出实现中的返回构造式，变量代表运行时值，并非 JSON 示例。

```python
{'ok': True, 'message': '已退出登录'}
```

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/auth/me`

用途：当前用户资料。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/auth.py](../../backend/app/api/routes/auth.py)，`me`。

Web 封装：`getProfile`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）；`login`（[webreact/src/data/http/authEndpoints.js](../../webreact/src/data/http/authEndpoints.js)）

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [AuthMeResponse](schemas.md#schema-authmeresponse) |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `user` | [UserPublic](schemas.md#schema-userpublic) | 是 | — | — |
| `access_token` | string / null | 否 | — | 业务访问令牌 |
| `expires_in` | integer / null | 否 | — | — |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `POST /api/v1/auth/admin/users`

用途：管理员创建用户接口(仅 admin 角色)。

鉴权：Bearer access token；角色 admin。

实现：[backend/app/api/routes/auth.py](../../backend/app/api/routes/auth.py)，`admin_create_user`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

管理员创建用户接口(仅 admin 角色)。

用于在真实数据库中创建学生/管理员验收账号,执行完整真实业务流程,
无任何"演示专用通道"或绕过认证的特殊账号。

权限校验:
- 仅 admin 角色可调用(require_role("admin"))
- 用户名/学号唯一性校验
- role 与 student_number 一致性校验

安全:
- 密码以 PBKDF2-HMAC-SHA256 哈希存储,不返回密码或哈希
- 返回 UserPublic(不含 password_hash)

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：`application/json`，必填；[UserCreate](schemas.md#schema-usercreate)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `username` | string | 是 | minLength=3; maxLength=64; pattern="^[a-zA-Z0-9_]+$" | 登录用户名 |
| `password` | string | 是 | minLength=8; maxLength=128 | 登录密码，仅请求使用 |
| `role` | string | 是 | pattern="^(student\|admin)$" | — |
| `display_name` | string / null | 否 | string约束: maxLength=128 | — |
| `student_number` | string / null | 否 | string约束: maxLength=32 | — |
| `teacher_number` | string / null | 否 | string约束: maxLength=32 | 已废弃,仅为兼容旧数据保留 |
| `college` | string / null | 否 | string约束: maxLength=64 | — |
| `major` | string / null | 否 | string约束: maxLength=64 | — |
| `grade` | string / null | 否 | string约束: maxLength=32 | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "username": "<username>",
  "password": "<password>",
  "role": "<role>"
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 201 | application/json | [UserPublic](schemas.md#schema-userpublic) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

201 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `username` | string | 是 | — | 登录用户名 |
| `role` | string | 是 | — | — |
| `name` | string | 否 | default="" | 名称 |
| `display_name` | string / null | 否 | — | — |
| `student_number` | string / null | 否 | — | — |
| `teacher_number` | string / null | 否 | — | — |
| `college` | string / null | 否 | — | — |
| `major` | string / null | 否 | — | — |
| `grade` | string / null | 否 | — | — |
| `avatar_url` | string / null | 否 | — | — |
| `university_id` | string / null | 否 | — | — |
| `university_name` | string / null | 否 | — | — |
| `is_active` | boolean | 否 | default=true | — |
| `created_at` | string | 否 | default="" | 创建时间 |
| `updated_at` | string | 否 | default="" | 最近更新时间 |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 422 | VALIDATION_FAILED | '管理员角色不应携带学号或工号' |
| 422 | VALIDATION_FAILED | '学生角色不应携带 teacher_number' |
| 409 | USERNAME_EXISTS | 用户名已被占用。 |
| 409 | STUDENT_NUMBER_EXISTS | 学号已被占用。 |

### `GET /api/v1/auth/admin/users`

用途：管理员列出用户。

鉴权：Bearer access token；角色 admin。

实现：[backend/app/api/routes/auth.py](../../backend/app/api/routes/auth.py)，`admin_list_users`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| query | `role` | string / null | 否 | string约束: pattern="^(student\|admin)$" | — |
| query | `is_active` | boolean / null | 否 | — | — |
| query | `query` | string / null | 否 | string约束: maxLength=128 | — |
| query | `page` | integer | 否 | default=1; minimum=1 | — |
| query | `page_size` | integer | 否 | default=20; minimum=1; maximum=100 | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [Page](schemas.md#schema-page)；items 元素为 [UserPublic](schemas.md#schema-userpublic) |
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

### `PATCH /api/v1/auth/admin/users/{user_id}`

用途：管理员更新用户。

鉴权：Bearer access token；角色 admin。

实现：[backend/app/api/routes/auth.py](../../backend/app/api/routes/auth.py)，`admin_update_user`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `user_id` | string | 是 | — | — |

请求体：`application/json`，必填；[UserAdminUpdate](schemas.md#schema-useradminupdate)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `display_name` | string / null | 否 | string约束: minLength=1; maxLength=128 | — |
| `role` | string / null | 否 | string约束: pattern="^(student\|admin)$" | — |
| `college` | string / null | 否 | string约束: maxLength=64 | — |
| `major` | string / null | 否 | string约束: maxLength=64 | — |
| `grade` | string / null | 否 | string约束: maxLength=32 | — |
| `is_active` | boolean / null | 否 | — | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [UserPublic](schemas.md#schema-userpublic) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `username` | string | 是 | — | 登录用户名 |
| `role` | string | 是 | — | — |
| `name` | string | 否 | default="" | 名称 |
| `display_name` | string / null | 否 | — | — |
| `student_number` | string / null | 否 | — | — |
| `teacher_number` | string / null | 否 | — | — |
| `college` | string / null | 否 | — | — |
| `major` | string / null | 否 | — | — |
| `grade` | string / null | 否 | — | — |
| `avatar_url` | string / null | 否 | — | — |
| `university_id` | string / null | 否 | — | — |
| `university_name` | string / null | 否 | — | — |
| `is_active` | boolean | 否 | default=true | — |
| `created_at` | string | 否 | default="" | 创建时间 |
| `updated_at` | string | 否 | default="" | 最近更新时间 |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | USER_NOT_FOUND | 用户不存在。 |
| 422 | VALIDATION_FAILED | '不能停用当前登录的管理员账号' |
| 422 | VALIDATION_FAILED | '不能修改当前登录账号的管理员角色' |

### `POST /api/v1/auth/qr/create`

用途：Web 创建 QR Login Session(无需鉴权)。

鉴权：公开或使用专用凭据（扫码 browser token / 可信设备 cookie 等见参数与流程）。

实现：[backend/app/api/routes/qr_auth.py](../../backend/app/api/routes/qr_auth.py)，`qr_create`。

Web 封装：`qrCreate`（[webreact/src/data/http/authEndpoints.js](../../webreact/src/data/http/authEndpoints.js)）

Web 创建 QR Login Session(无需鉴权)。

可选 User-Agent 由浏览器自动发送；服务端据此生成浏览器与操作系统信息，供扫码确认页展示。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：`application/json`，必填；[QrCreateRequest](schemas.md#schema-qrcreaterequest)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `device_id` | string / null | 否 | string约束: maxLength=128 | 浏览器生成的设备标识 |
| `browser_name` | string / null | 否 | string约束: maxLength=64 | — |
| `os_name` | string / null | 否 | string约束: maxLength=64 | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [QrCreateResponse](schemas.md#schema-qrcreateresponse) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `session_id` | string | 是 | — | — |
| `qr_payload` | string | 是 | — | 二维码内容字符串 |
| `browser_token` | string | 是 | — | 浏览器兑换凭据，不写入二维码 |
| `status` | string | 否 | default="PENDING" | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `expires_at` | string | 是 | — | — |
| `expires_in` | integer | 是 | — | 剩余有效期(秒) |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 429 | QR_RATE_LIMITED | 创建二维码过于频繁，请稍后再试。 |

### `POST /api/v1/auth/qr/scan`

用途：手机扫码(需登录)。绑定当前手机用户到 session。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/qr_auth.py](../../backend/app/api/routes/qr_auth.py)，`qr_scan`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

手机扫码(需登录)。绑定当前手机用户到 session。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：`application/json`，必填；[QrScanRequest](schemas.md#schema-qrscanrequest)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `session_id` | string | 是 | minLength=16; maxLength=64 | — |
| `scan_token` | string | 是 | minLength=32; maxLength=128 | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "session_id": "<session_id>",
  "scan_token": "<scan_token>"
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [QrScanResponse](schemas.md#schema-qrscanresponse) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `session_id` | string | 是 | — | — |
| `browser_name` | string / null | 否 | — | — |
| `os_name` | string / null | 否 | — | — |
| `device_label` | string / null | 否 | — | — |
| `expires_at` | string | 是 | — | — |
| `status` | string | 否 | default="SCANNED" | 业务状态，合法取值和操作前置条件见枚举及流程 |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 400 | QR_INVALID | '二维码不存在。' |
| 400 | QR_INVALID | 'scan token 不匹配。' |
| 410 | QR_EXPIRED | 二维码已过期。 |
| 409 | QR_CANCELLED | 二维码已取消。 |
| 409 | QR_ALREADY_SCANNED | '二维码已确认，不能重复扫描。' |
| 409 | QR_ALREADY_SCANNED | 二维码已被扫描。 |
| 409 | QR_ALREADY_SCANNED | '二维码已被其他账号扫描。' |

### `POST /api/v1/auth/qr/confirm`

用途：手机确认登录 Web(需登录)。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/qr_auth.py](../../backend/app/api/routes/qr_auth.py)，`qr_confirm`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

手机确认登录 Web(需登录)。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：`application/json`，必填；[QrConfirmRequest](schemas.md#schema-qrconfirmrequest)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `session_id` | string | 是 | minLength=16; maxLength=64 | — |
| `scan_token` | string | 是 | minLength=32; maxLength=128 | — |
| `trust_device` | boolean | 否 | default=false | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "session_id": "<session_id>",
  "scan_token": "<scan_token>"
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [QrConfirmResponse](schemas.md#schema-qrconfirmresponse) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `session_id` | string | 是 | — | — |
| `status` | string | 否 | default="CONFIRMED" | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `trust_device` | boolean | 是 | — | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 400 | QR_INVALID | '二维码不存在。' |
| 400 | QR_INVALID | 'scan token 不匹配。' |
| 410 | QR_EXPIRED | 二维码已过期。 |
| 409 | QR_CANCELLED | 二维码已取消。 |
| 409 | QR_ALREADY_CONSUMED | 二维码已使用，不能重复兑换。 |
| 400 | QR_INVALID | '二维码尚未扫描。' |
| 403 | QR_USER_MISMATCH | 确认用户与扫描用户不一致。 |
| 400 | QR_INVALID | '状态迁移失败，二维码可能已被其他操作修改。' |

### `POST /api/v1/auth/qr/cancel`

用途：手机取消登录(需登录)。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/qr_auth.py](../../backend/app/api/routes/qr_auth.py)，`qr_cancel`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

手机取消登录(需登录)。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：`application/json`，必填；[QrCancelRequest](schemas.md#schema-qrcancelrequest)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `session_id` | string | 是 | minLength=16; maxLength=64 | — |
| `scan_token` | string | 是 | minLength=32; maxLength=128 | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "session_id": "<session_id>",
  "scan_token": "<scan_token>"
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | 动态响应；见下方补充与 response-contracts.md |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

实际响应补充：动态对象、透传、文件和流式返回不能由默认 OpenAPI 完整表达；业务字段说明在 [响应补充](response-contracts.md)。下面列出实现中的返回构造式，变量代表运行时值，并非 JSON 示例。

```python
{'ok': True, 'status': 'CANCELLED'}
```

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 400 | QR_INVALID | '二维码不存在。' |
| 400 | QR_INVALID | 'scan token 不匹配。' |
| 400 | QR_INVALID | '当前状态不允许取消。' |
| 409 | QR_ALREADY_CONFIRMED | '二维码已确认，不能取消。' |
| 409 | QR_ALREADY_CONSUMED | 二维码已使用，不能重复兑换。 |

### `GET /api/v1/auth/qr/{session_id}/status`

用途：Web 用 browser_token 查询状态。

鉴权：公开或使用专用凭据（扫码 browser token / 可信设备 cookie 等见参数与流程）。

实现：[backend/app/api/routes/qr_auth.py](../../backend/app/api/routes/qr_auth.py)，`qr_status`。

Web 封装：`qrStatus`（[webreact/src/data/http/authEndpoints.js](../../webreact/src/data/http/authEndpoints.js)）

Web 用 browser_token 查询状态。

browser_token 通过 Authorization: Bearer 或 X-Browser-Token 头传递。
不让仅知道 session_id 的人能查询状态。

业务必需专用凭据：请求头 **X-Browser-Token: <创建二维码返回的 browser_token>**；也兼容 Authorization: Bearer <browser_token>。此处 Bearer 值是扫码浏览器凭据。不能使用普通 access_token 或 scan_token 代替；缺少或错误凭据返回 401。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `session_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [QrStatusResponse](schemas.md#schema-qrstatusresponse) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `session_id` | string | 是 | — | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `expires_at` | string | 是 | — | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 401 | QR_BROWSER_TOKEN_INVALID | '缺少 browser_token。' |
| 400 | QR_INVALID | '二维码不存在。' |
| 401 | QR_BROWSER_TOKEN_INVALID | 浏览器凭据无效。 |

### `POST /api/v1/auth/qr/exchange`

用途：Web 用 browser_token 兑换登录态(无需鉴权)。

鉴权：公开或使用专用凭据（扫码 browser token / 可信设备 cookie 等见参数与流程）。

实现：[backend/app/api/routes/qr_auth.py](../../backend/app/api/routes/qr_auth.py)，`qr_exchange`。

Web 封装：`qrExchange`（[webreact/src/data/http/authEndpoints.js](../../webreact/src/data/http/authEndpoints.js)）

Web 用 browser_token 兑换登录态(无需鉴权)。

原子性地 CONFIRMED -> CONSUMED，然后复用 _issue_tokens 签发正常 TokenPair。
若 trust_device=true，同时建立可信设备。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：`application/json`，必填；[QrExchangeRequest](schemas.md#schema-qrexchangerequest)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `session_id` | string | 是 | minLength=16; maxLength=64 | — |
| `browser_token` | string | 是 | minLength=32; maxLength=128 | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "session_id": "<session_id>",
  "browser_token": "<browser_token>"
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [TokenPair](schemas.md#schema-tokenpair) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `access_token` | string | 是 | — | 业务访问令牌 |
| `refresh_token` | string | 是 | — | 换发令牌；不是业务访问凭据 |
| `token_type` | string | 否 | default="Bearer" | 令牌类型 |
| `expires_in` | integer | 是 | — | access token 有效期(秒) |
| `expires_at` | string | 是 | — | access token 到期时间(ISO 8601) |
| `user` | [UserPublic](schemas.md#schema-userpublic) | 是 | — | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 400 | QR_INVALID | '二维码不存在。' |
| 401 | QR_BROWSER_TOKEN_INVALID | 浏览器凭据无效。 |
| 409 | QR_CANCELLED | 二维码已取消。 |
| 409 | QR_NOT_CONFIRMED | 二维码尚未确认，不能兑换。 |
| 410 | QR_EXPIRED | 二维码已过期。 |
| 409 | QR_ALREADY_CONSUMED | 二维码已使用，不能重复兑换。 |
| 400 | QR_INVALID | f'二维码状态异常: {session.status}' |
| 400 | QR_INVALID | '兑换失败，二维码状态可能已变更。' |
| 401 | UNAUTHORIZED | '用户不存在或已停用' |

### `POST /api/v1/auth/trusted-device/auto-login`

用途：浏览器用可信设备 Cookie 自动登录。

鉴权：公开或使用专用凭据（扫码 browser token / 可信设备 cookie 等见参数与流程）。

实现：[backend/app/api/routes/qr_auth.py](../../backend/app/api/routes/qr_auth.py)，`trusted_device_auto_login`。

Web 封装：`trustedDeviceAutoLogin`（[webreact/src/data/http/authEndpoints.js](../../webreact/src/data/http/authEndpoints.js)）

浏览器用可信设备 Cookie 自动登录。

可信设备凭据由 HttpOnly cookie 携带；默认名 campus_trusted_device，可由配置覆盖，Path=/api/v1/auth。使用 credentials/include 或 Axios withCredentials；JavaScript 不读取 cookie 值。具体清除和撤销流程见 [认证接入](integration.md#auth)。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：`application/json`，必填；[TrustedDeviceAutoLoginRequest](schemas.md#schema-trusteddeviceautologinrequest)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `device_id` | string / null | 否 | string约束: maxLength=128 | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [TokenPair](schemas.md#schema-tokenpair) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `access_token` | string | 是 | — | 业务访问令牌 |
| `refresh_token` | string | 是 | — | 换发令牌；不是业务访问凭据 |
| `token_type` | string | 否 | default="Bearer" | 令牌类型 |
| `expires_in` | integer | 是 | — | access token 有效期(秒) |
| `expires_at` | string | 是 | — | access token 到期时间(ISO 8601) |
| `user` | [UserPublic](schemas.md#schema-userpublic) | 是 | — | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 401 | TRUSTED_DEVICE_INVALID | '缺少可信设备凭据。' |
| 401 | TRUSTED_DEVICE_INVALID | 可信设备凭据无效。 |
| 401 | TRUSTED_DEVICE_REVOKED | 可信设备已被撤销。 |
| 401 | TRUSTED_DEVICE_EXPIRED | 可信设备凭据已过期。 |
| 401 | UNAUTHORIZED | '用户不存在或已停用' |

### `GET /api/v1/auth/trusted-devices`

用途：列出当前用户的可信设备。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/qr_auth.py](../../backend/app/api/routes/qr_auth.py)，`list_trusted_devices`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

列出当前用户的可信设备。

可信设备凭据由 HttpOnly cookie 携带；默认名 campus_trusted_device，可由配置覆盖，Path=/api/v1/auth。使用 credentials/include 或 Axios withCredentials；JavaScript 不读取 cookie 值。具体清除和撤销流程见 [认证接入](integration.md#auth)。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [TrustedDeviceListResponse](schemas.md#schema-trusteddevicelistresponse) |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `devices` | array<[TrustedDeviceListItem](schemas.md#schema-trusteddevicelistitem)> | 否 | — | — |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `POST /api/v1/auth/trusted-device/revoke`

用途：撤销可信设备。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/qr_auth.py](../../backend/app/api/routes/qr_auth.py)，`revoke_trusted_device`。

Web 封装：`revokeTrustedDevice`（[webreact/src/data/http/authEndpoints.js](../../webreact/src/data/http/authEndpoints.js)）

撤销可信设备。

若 req.device_id 为空，撤销当前 Cookie 对应的设备（即退出登录时撤销本浏览器）。

可信设备凭据由 HttpOnly cookie 携带；默认名 campus_trusted_device，可由配置覆盖，Path=/api/v1/auth。使用 credentials/include 或 Axios withCredentials；JavaScript 不读取 cookie 值。具体清除和撤销流程见 [认证接入](integration.md#auth)。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：`application/json`，必填；[TrustedDeviceRevokeRequest](schemas.md#schema-trusteddevicerevokerequest)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `device_id` | string / null | 否 | string约束: maxLength=128 | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | 动态响应；见下方补充与 response-contracts.md |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

实际响应补充：动态对象、透传、文件和流式返回不能由默认 OpenAPI 完整表达；业务字段说明在 [响应补充](response-contracts.md)。下面列出实现中的返回构造式，变量代表运行时值，并非 JSON 示例。

```python
{'ok': True, 'message': '已撤销设备'}
```

```python
{'ok': True, 'message': '已撤销当前设备'}
```

```python
{'ok': True, 'message': '无当前设备凭据'}
```

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。
