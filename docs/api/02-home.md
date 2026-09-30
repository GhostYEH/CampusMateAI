# 首页、今日待办、横幅与壁纸

> 对照日期：2026-09-30。本模块共 13 个 HTTP 方法与路径组合；以当前后端注册路由和 Web 调用为依据。

[文档导航](README.md) · [接入与流程](integration.md) · [字段字典](schemas.md) · [OpenAPI](openapi.json)

## 接口索引

| 方法 | 完整路径 | 用途 |
| --- | --- | --- |
| GET | `/api/v1/health` | 返回服务健康状态 |
| GET | `/api/v1/home-banners` | 列出首页横幅 |
| GET | `/api/v1/admin/home-banners` | 管理员列出首页横幅 |
| POST | `/api/v1/admin/home-banners` | 创建首页横幅 |
| PUT | `/api/v1/admin/home-banners/{banner_id}` | 更新首页横幅 |
| POST | `/api/v1/admin/home-banners/{banner_id}/publish` | 发布首页横幅 |
| POST | `/api/v1/admin/home-banners/{banner_id}/archive` | 归档首页横幅 |
| DELETE | `/api/v1/admin/home-banners/{banner_id}` | 删除首页横幅 |
| POST | `/api/v1/admin/home-banners/images` | 上传首页横幅图片 |
| GET | `/api/v1/dashboard/student` | 学生首页数据 |
| GET | `/api/v1/agenda/today` | 按 Asia/Shanghai 自然日聚合当前用户的今日待办 |
| GET | `/api/v1/wallpaper/bing-daily` | 代理 UAPI 必应每日壁纸的 image/json/redirect 三种响应格式 |
| GET | `/api/v1/wallpaper/bing-daily/history` | 代理 UAPI 必应壁纸历史列表，支持按日期精确查询 |

## 接口契约

### `GET /api/v1/health`

用途：返回服务健康状态。

鉴权：公开或使用专用凭据（扫码 browser token / 可信设备 cookie 等见参数与流程）。

实现：[backend/app/api/routes/health.py](../../backend/app/api/routes/health.py)，`health`。

Web 封装：`studyCheckinsSupported`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）；`probeBackend`（[webreact/src/data/http/authEndpoints.js](../../webreact/src/data/http/authEndpoints.js)）

返回服务健康状态。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | 动态响应；见下方补充与 response-contracts.md |

实际响应补充：动态对象、透传、文件和流式返回不能由默认 OpenAPI 完整表达；业务字段说明在 [响应补充](response-contracts.md)。下面列出实现中的返回构造式，变量代表运行时值，并非 JSON 示例。

```python
{'status': 'ok', 'mode': 'real_backend', 'env': s.app_env, 'version': s.app_version, 'knowledge_base_initialized': container.retrieval.is_ready, 'document_count': container.document_repository.count_documents(), 'chunk_count': container.retrieval.chunk_count, 'llm_provider': s.llm_provider, 'llm_available': bool(container.llm and s.llm_available), 'fallback_enabled': s.enable_fallback_mode, 'retrieval_method': 'bm25', 'study_checkins_supported': True}
```

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/home-banners`

用途：列出首页横幅。

鉴权：公开或使用专用凭据（扫码 browser token / 可信设备 cookie 等见参数与流程）。

实现：[backend/app/api/routes/home_banners.py](../../backend/app/api/routes/home_banners.py)，`list_home_banners`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [HomeBannerFeed](schemas.md#schema-homebannerfeed) |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `items` | array<[HomeBannerOut](schemas.md#schema-homebannerout)> | 是 | — | 列表条目 |
| `updated_at` | string / null | 否 | — | 最近更新时间 |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/admin/home-banners`

用途：管理员列出首页横幅。

鉴权：Bearer access token；角色 admin。

实现：[backend/app/api/routes/home_banners.py](../../backend/app/api/routes/home_banners.py)，`admin_list_home_banners`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [HomeBannerFeed](schemas.md#schema-homebannerfeed) |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `items` | array<[HomeBannerOut](schemas.md#schema-homebannerout)> | 是 | — | 列表条目 |
| `updated_at` | string / null | 否 | — | 最近更新时间 |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `POST /api/v1/admin/home-banners`

用途：创建首页横幅。

鉴权：Bearer access token；角色 admin。

实现：[backend/app/api/routes/home_banners.py](../../backend/app/api/routes/home_banners.py)，`create_home_banner`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：`application/json`，必填；[HomeBannerWrite](schemas.md#schema-homebannerwrite)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `eyebrow` | string | 是 | minLength=1; maxLength=60 | — |
| `title` | string | 是 | minLength=1; maxLength=80 | 标题 |
| `subtitle` | string | 是 | minLength=1; maxLength=160 | — |
| `cta_label` | string | 是 | minLength=1; maxLength=30 | — |
| `image_url` | string | 是 | minLength=1; maxLength=500 | — |
| `action_key` | enum ["CPM_ASSISTANT", "CHAOXING", "EDU_SYSTEM", "TASKS", "COMMUNITY"] | 是 | — | — |
| `theme_key` | enum ["INDIGO", "CYAN", "VIOLET", "ORANGE", "GREEN"] | 是 | — | — |
| `sort_order` | integer | 否 | default=0; minimum=-10000.0; maximum=10000.0 | — |
| `starts_at` | string (date-time) / null | 否 | string约束: format="date-time" | — |
| `ends_at` | string (date-time) / null | 否 | string约束: format="date-time" | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "eyebrow": "<eyebrow>",
  "title": "<title>",
  "subtitle": "<subtitle>",
  "cta_label": "<cta_label>",
  "image_url": "<image_url>",
  "action_key": "CPM_ASSISTANT",
  "theme_key": "INDIGO"
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 201 | application/json | [HomeBannerOut](schemas.md#schema-homebannerout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

201 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `eyebrow` | string | 是 | — | — |
| `title` | string | 是 | — | 标题 |
| `subtitle` | string | 是 | — | — |
| `cta_label` | string | 是 | — | — |
| `image_url` | string | 是 | — | — |
| `action_key` | enum ["CPM_ASSISTANT", "CHAOXING", "EDU_SYSTEM", "TASKS", "COMMUNITY"] | 是 | — | — |
| `theme_key` | enum ["INDIGO", "CYAN", "VIOLET", "ORANGE", "GREEN"] | 是 | — | — |
| `sort_order` | integer | 是 | — | — |
| `status` | enum ["DRAFT", "PUBLISHED", "ARCHIVED"] | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `starts_at` | string / null | 否 | — | — |
| `ends_at` | string / null | 否 | — | — |
| `created_at` | string | 是 | — | 创建时间 |
| `updated_at` | string | 是 | — | 最近更新时间 |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `PUT /api/v1/admin/home-banners/{banner_id}`

用途：更新首页横幅。

鉴权：Bearer access token；角色 admin。

实现：[backend/app/api/routes/home_banners.py](../../backend/app/api/routes/home_banners.py)，`update_home_banner`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `banner_id` | string | 是 | — | — |

请求体：`application/json`，必填；[HomeBannerWrite](schemas.md#schema-homebannerwrite)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `eyebrow` | string | 是 | minLength=1; maxLength=60 | — |
| `title` | string | 是 | minLength=1; maxLength=80 | 标题 |
| `subtitle` | string | 是 | minLength=1; maxLength=160 | — |
| `cta_label` | string | 是 | minLength=1; maxLength=30 | — |
| `image_url` | string | 是 | minLength=1; maxLength=500 | — |
| `action_key` | enum ["CPM_ASSISTANT", "CHAOXING", "EDU_SYSTEM", "TASKS", "COMMUNITY"] | 是 | — | — |
| `theme_key` | enum ["INDIGO", "CYAN", "VIOLET", "ORANGE", "GREEN"] | 是 | — | — |
| `sort_order` | integer | 否 | default=0; minimum=-10000.0; maximum=10000.0 | — |
| `starts_at` | string (date-time) / null | 否 | string约束: format="date-time" | — |
| `ends_at` | string (date-time) / null | 否 | string约束: format="date-time" | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "eyebrow": "<eyebrow>",
  "title": "<title>",
  "subtitle": "<subtitle>",
  "cta_label": "<cta_label>",
  "image_url": "<image_url>",
  "action_key": "CPM_ASSISTANT",
  "theme_key": "INDIGO"
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [HomeBannerOut](schemas.md#schema-homebannerout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `eyebrow` | string | 是 | — | — |
| `title` | string | 是 | — | 标题 |
| `subtitle` | string | 是 | — | — |
| `cta_label` | string | 是 | — | — |
| `image_url` | string | 是 | — | — |
| `action_key` | enum ["CPM_ASSISTANT", "CHAOXING", "EDU_SYSTEM", "TASKS", "COMMUNITY"] | 是 | — | — |
| `theme_key` | enum ["INDIGO", "CYAN", "VIOLET", "ORANGE", "GREEN"] | 是 | — | — |
| `sort_order` | integer | 是 | — | — |
| `status` | enum ["DRAFT", "PUBLISHED", "ARCHIVED"] | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `starts_at` | string / null | 否 | — | — |
| `ends_at` | string / null | 否 | — | — |
| `created_at` | string | 是 | — | 创建时间 |
| `updated_at` | string | 是 | — | 最近更新时间 |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | HOME_BANNER_NOT_FOUND | Home banner not found |

### `POST /api/v1/admin/home-banners/{banner_id}/publish`

用途：发布首页横幅。

鉴权：Bearer access token；角色 admin。

实现：[backend/app/api/routes/home_banners.py](../../backend/app/api/routes/home_banners.py)，`publish_home_banner`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `banner_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [HomeBannerOut](schemas.md#schema-homebannerout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `eyebrow` | string | 是 | — | — |
| `title` | string | 是 | — | 标题 |
| `subtitle` | string | 是 | — | — |
| `cta_label` | string | 是 | — | — |
| `image_url` | string | 是 | — | — |
| `action_key` | enum ["CPM_ASSISTANT", "CHAOXING", "EDU_SYSTEM", "TASKS", "COMMUNITY"] | 是 | — | — |
| `theme_key` | enum ["INDIGO", "CYAN", "VIOLET", "ORANGE", "GREEN"] | 是 | — | — |
| `sort_order` | integer | 是 | — | — |
| `status` | enum ["DRAFT", "PUBLISHED", "ARCHIVED"] | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `starts_at` | string / null | 否 | — | — |
| `ends_at` | string / null | 否 | — | — |
| `created_at` | string | 是 | — | 创建时间 |
| `updated_at` | string | 是 | — | 最近更新时间 |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | HOME_BANNER_NOT_FOUND | Home banner not found |

### `POST /api/v1/admin/home-banners/{banner_id}/archive`

用途：归档首页横幅。

鉴权：Bearer access token；角色 admin。

实现：[backend/app/api/routes/home_banners.py](../../backend/app/api/routes/home_banners.py)，`archive_home_banner`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `banner_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [HomeBannerOut](schemas.md#schema-homebannerout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `eyebrow` | string | 是 | — | — |
| `title` | string | 是 | — | 标题 |
| `subtitle` | string | 是 | — | — |
| `cta_label` | string | 是 | — | — |
| `image_url` | string | 是 | — | — |
| `action_key` | enum ["CPM_ASSISTANT", "CHAOXING", "EDU_SYSTEM", "TASKS", "COMMUNITY"] | 是 | — | — |
| `theme_key` | enum ["INDIGO", "CYAN", "VIOLET", "ORANGE", "GREEN"] | 是 | — | — |
| `sort_order` | integer | 是 | — | — |
| `status` | enum ["DRAFT", "PUBLISHED", "ARCHIVED"] | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `starts_at` | string / null | 否 | — | — |
| `ends_at` | string / null | 否 | — | — |
| `created_at` | string | 是 | — | 创建时间 |
| `updated_at` | string | 是 | — | 最近更新时间 |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | HOME_BANNER_NOT_FOUND | Home banner not found |

### `DELETE /api/v1/admin/home-banners/{banner_id}`

用途：删除首页横幅。

鉴权：Bearer access token；角色 admin。

实现：[backend/app/api/routes/home_banners.py](../../backend/app/api/routes/home_banners.py)，`delete_home_banner`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `banner_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 204 | 无声明 | Successful Response |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

实际响应补充：动态对象、透传、文件和流式返回不能由默认 OpenAPI 完整表达；业务字段说明在 [响应补充](response-contracts.md)。下面列出实现中的返回构造式，变量代表运行时值，并非 JSON 示例。

```python
Response(status_code=status.HTTP_204_NO_CONTENT)
```

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | HOME_BANNER_NOT_FOUND | Home banner not found |

### `POST /api/v1/admin/home-banners/images`

用途：上传首页横幅图片。

鉴权：Bearer access token；角色 admin。

实现：[backend/app/api/routes/home_banners.py](../../backend/app/api/routes/home_banners.py)，`upload_home_banner_image`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：`multipart/form-data`，必填；[Body_upload_home_banner_image_api_v1_admin_home_banners_images_post](schemas.md#schema-body_upload_home_banner_image_api_v1_admin_home_banners_images_post)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `image` | string (binary) | 是 | format="binary" | — |

上传使用 FormData；字段名按上表；浏览器由运行时生成 multipart boundary。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 201 | application/json | [HomeBannerImageOut](schemas.md#schema-homebannerimageout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

201 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `image_url` | string | 是 | — | — |
| `filename` | string | 是 | — | 文件名 |
| `size` | integer | 是 | — | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 415 | 'BANNER_IMAGE_TYPE_INVALID' | '仅支持 JPG、PNG、WebP 图片' |
| 413 | 'BANNER_IMAGE_TOO_LARGE' | 'Banner 图片不能超过 8 MB' |

### `GET /api/v1/dashboard/student`

用途：学生首页数据。

鉴权：Bearer access token；角色 student。

实现：[backend/app/api/routes/dashboards.py](../../backend/app/api/routes/dashboards.py)，`student_dashboard`。

Web 封装：`getDashboard`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

Return the authenticated student's home-page summary.

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [StudentDashboard](schemas.md#schema-studentdashboard) |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `enrolled_course_count` | integer | 是 | — | — |
| `unread_announcement_count` | integer | 是 | — | — |
| `pending_assignment_count` | integer | 是 | — | — |
| `overdue_assignment_count` | integer | 是 | — | — |
| `due_soon_assignments` | array<object> | 否 | — | — |
| `recent_announcements` | array<object> | 否 | — | — |
| `pending_personal_task_count` | integer | 否 | default=0 | — |
| `overdue_personal_task_count` | integer | 否 | default=0 | — |
| `due_soon_personal_tasks` | array<object> | 否 | — | — |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/agenda/today`

用途：按 Asia/Shanghai 自然日聚合当前用户的今日待办。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/agenda.py](../../backend/app/api/routes/agenda.py)，`get_today_agenda`。

Web 封装：`getTodayAgenda`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

按 Asia/Shanghai 自然日聚合当前用户的今日待办。

聚合范围: 已逾期但仍未完成的学习通作业、今天截止的学习通作业、今天进行或
今天截止的学习通考试、今天上课的课程(仅在确实有课表数据时)、今天截止或今天
新建的个人待办、学习陪伴与 AI 拆解产生的今日任务。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [TodayAgendaOut](schemas.md#schema-todayagendaout) |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `date` | string | 是 | — | — |
| `timezone` | string | 否 | default="Asia/Shanghai" | — |
| `generated_at` | string | 是 | — | — |
| `last_chaoxing_synced_at` | string / null | 否 | — | — |
| `stale` | boolean | 否 | default=false | — |
| `summary` | [AgendaSummaryOut](schemas.md#schema-agendasummaryout) | 否 | — | — |
| `sources` | [AgendaSourcesOut](schemas.md#schema-agendasourcesout) | 否 | — | — |
| `items` | array<[AgendaItemOut](schemas.md#schema-agendaitemout)> | 否 | — | 列表条目 |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/wallpaper/bing-daily`

用途：代理 UAPI 必应每日壁纸的 image/json/redirect 三种响应格式。

鉴权：公开或使用专用凭据（扫码 browser token / 可信设备 cookie 等见参数与流程）。

实现：[backend/app/api/routes/bing_daily_wallpaper.py](../../backend/app/api/routes/bing_daily_wallpaper.py)，`get_bing_daily_wallpaper`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

代理 UAPI 必应每日壁纸的 image/json/redirect 三种响应格式。

format=image 是图片，format=json 是元数据，format=redirect 是重定向；响应内容与历史列表见 [响应补充](response-contracts.md#wallpaper)。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| query | `date` | string / null | 否 | — | — |
| query | `random` | boolean | 否 | default=false | — |
| query | `resolution` | string | 否 | default="4k" | — |
| query | `format` | string | 否 | default="image" | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | image/* / application/json / 重定向 | 由 format 决定；元数据至少有 image_url |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

实际响应补充：动态对象、透传、文件和流式返回不能由默认 OpenAPI 完整表达；业务字段说明在 [响应补充](response-contracts.md)。下面列出实现中的返回构造式，变量代表运行时值，并非 JSON 示例。

```python
_error_response(502, 'UAPI_INVALID_RESPONSE', '必应壁纸服务未返回有效跳转地址')
```

```python
RedirectResponse(url=location, status_code=upstream.status_code)
```

```python
_upstream_error(upstream)
```

```python
JSONResponse(content=payload, status_code=upstream.status_code)
```

```python
Response(content=upstream.content, status_code=upstream.status_code, media_type=content_type)
```

```python
_error_response(504, 'UAPI_TIMEOUT', '必应壁纸服务请求超时，请稍后重试')
```

```python
_error_response(502, 'UAPI_NETWORK_ERROR', '必应壁纸服务暂时不可达，请稍后重试')
```

```python
_error_response(502, 'UAPI_INVALID_RESPONSE', '必应壁纸服务未返回图片地址')
```

```python
_error_response(502, 'UAPI_INVALID_RESPONSE', '必应壁纸服务返回的数据缺少 image_url')
```

```python
_error_response(502, 'UAPI_INVALID_RESPONSE', '必应壁纸服务未返回有效图片')
```

```python
_error_response(502, 'UAPI_INVALID_RESPONSE', '必应壁纸服务返回了无法解析的数据')
```

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 400 | 'UAPI_BAD_REQUEST' | 'random 不能和 date 同时使用' |
| 400 | 'UAPI_BAD_REQUEST' | 'format 只能传 image、json 或 redirect' |
| 503 | 'UAPI_KEY_INVALID' | 'UAPI Key 格式无效，应以 uapi- 开头' |
| 400 | 'UAPI_BAD_REQUEST' | 'date 格式必须是 YYYY-MM-DD' |
| 400 | 'UAPI_BAD_REQUEST' | 'date 格式必须是有效的 YYYY-MM-DD 日期' |
| 400 | 'UAPI_BAD_REQUEST' | 'resolution 只能传 4k 或 1080' |

### `GET /api/v1/wallpaper/bing-daily/history`

用途：代理 UAPI 必应壁纸历史列表，支持按日期精确查询。

鉴权：公开或使用专用凭据（扫码 browser token / 可信设备 cookie 等见参数与流程）。

实现：[backend/app/api/routes/bing_daily_wallpaper.py](../../backend/app/api/routes/bing_daily_wallpaper.py)，`get_bing_daily_wallpaper_history`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

代理 UAPI 必应壁纸历史列表，支持按日期精确查询。

format=image 是图片，format=json 是元数据，format=redirect 是重定向；响应内容与历史列表见 [响应补充](response-contracts.md#wallpaper)。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| query | `date` | string / null | 否 | — | — |
| query | `resolution` | string | 否 | default="4k" | — |
| query | `page` | integer | 否 | default=1 | — |
| query | `page_size` | integer | 否 | default=30 | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | 动态响应；见下方补充与 response-contracts.md |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

实际响应补充：动态对象、透传、文件和流式返回不能由默认 OpenAPI 完整表达；业务字段说明在 [响应补充](response-contracts.md)。下面列出实现中的返回构造式，变量代表运行时值，并非 JSON 示例。

```python
JSONResponse(content=payload, status_code=upstream.status_code)
```

```python
_upstream_error(upstream)
```

```python
_error_response(502, 'UAPI_INVALID_RESPONSE', '必应壁纸历史服务返回的数据结构无效')
```

```python
_error_response(504, 'UAPI_TIMEOUT', '必应壁纸历史服务请求超时，请稍后重试')
```

```python
_error_response(502, 'UAPI_NETWORK_ERROR', '必应壁纸历史服务暂时不可达，请稍后重试')
```

```python
_error_response(502, 'UAPI_INVALID_RESPONSE', '必应壁纸历史服务返回了无法解析的数据')
```

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 400 | 'UAPI_BAD_REQUEST' | 'page 必须是正整数' |
| 400 | 'UAPI_BAD_REQUEST' | 'page_size 必须是 1 到 100 之间的正整数' |
| 400 | 'UAPI_BAD_REQUEST' | 'date 格式必须是 YYYY-MM-DD' |
| 400 | 'UAPI_BAD_REQUEST' | 'date 格式必须是有效的 YYYY-MM-DD 日期' |
| 400 | 'UAPI_BAD_REQUEST' | 'resolution 只能传 4k 或 1080' |
| 503 | 'UAPI_KEY_INVALID' | 'UAPI Key 格式无效，应以 uapi- 开头' |
