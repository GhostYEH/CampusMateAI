# 学校、个人文件与收藏

> 对照日期：2026-09-30。本模块共 11 个 HTTP 方法与路径组合；以当前后端注册路由和 Web 调用为依据。

[文档导航](README.md) · [接入与流程](integration.md) · [字段字典](schemas.md) · [OpenAPI](openapi.json)

## 接口索引

| 方法 | 完整路径 | 用途 |
| --- | --- | --- |
| GET | `/api/v1/personal-hub/files` | 列出文件 |
| POST | `/api/v1/personal-hub/files` | 创建文件 |
| PATCH | `/api/v1/personal-hub/files/{file_id}` | 更新文件 |
| POST | `/api/v1/personal-hub/files/{file_id}/favorite` | 设置文件收藏状态(同步移除/加入收藏夹由客户端维护) |
| DELETE | `/api/v1/personal-hub/files/{file_id}` | 删除文件 |
| GET | `/api/v1/personal-hub/favorites` | 列出收藏 |
| POST | `/api/v1/personal-hub/favorites` | 添加收藏 |
| DELETE | `/api/v1/personal-hub/favorites/{favorite_id}` | 移除收藏 |
| GET | `/api/v1/universities` | 列出universities |
| GET | `/api/v1/universities/{university_id}` | 读取大学 |
| PUT | `/api/v1/profile/university` | 更新个人学校选择 |

## 接口契约

### `GET /api/v1/personal-hub/files`

用途：列出文件。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/personal_hub.py](../../backend/app/api/routes/personal_hub.py)，`list_files`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | array<[PersonalFileOut](schemas.md#schema-personalfileout)> |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `POST /api/v1/personal-hub/files`

用途：创建文件。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/personal_hub.py](../../backend/app/api/routes/personal_hub.py)，`create_file`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：`application/json`，必填；[PersonalFileCreate](schemas.md#schema-personalfilecreate)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `name` | string | 是 | minLength=1; maxLength=256 | 名称 |
| `category` | string / null | 否 | string约束: maxLength=64 | — |
| `source` | string / null | 否 | string约束: maxLength=128 | 来源 |
| `size_label` | string / null | 否 | string约束: maxLength=32 | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "name": "<name>"
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 201 | application/json | [PersonalFileOut](schemas.md#schema-personalfileout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

201 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `name` | string | 是 | — | 名称 |
| `category` | string / null | 否 | — | — |
| `size_label` | string / null | 否 | — | — |
| `updated_at` | string / null | 否 | — | 最近更新时间 |
| `source` | string / null | 否 | — | 来源 |
| `is_favorite` | boolean | 否 | default=false | — |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `PATCH /api/v1/personal-hub/files/{file_id}`

用途：更新文件。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/personal_hub.py](../../backend/app/api/routes/personal_hub.py)，`update_file`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `file_id` | string | 是 | — | — |

请求体：`application/json`，必填；[PersonalFileUpdate](schemas.md#schema-personalfileupdate)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `name` | string / null | 否 | string约束: minLength=1; maxLength=256 | 名称 |
| `category` | string / null | 否 | string约束: maxLength=64 | — |
| `source` | string / null | 否 | string约束: maxLength=128 | 来源 |
| `size_label` | string / null | 否 | string约束: maxLength=32 | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [PersonalFileOut](schemas.md#schema-personalfileout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `name` | string | 是 | — | 名称 |
| `category` | string / null | 否 | — | — |
| `size_label` | string / null | 否 | — | — |
| `updated_at` | string / null | 否 | — | 最近更新时间 |
| `source` | string / null | 否 | — | 来源 |
| `is_favorite` | boolean | 否 | default=false | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | NOT_FOUND | '文件不存在' |

### `POST /api/v1/personal-hub/files/{file_id}/favorite`

用途：设置文件收藏状态(同步移除/加入收藏夹由客户端维护)。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/personal_hub.py](../../backend/app/api/routes/personal_hub.py)，`toggle_file_favorite`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

设置文件收藏状态(同步移除/加入收藏夹由客户端维护)。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `file_id` | string | 是 | — | — |

请求体：`application/json`，必填；[FileFavoriteToggle](schemas.md#schema-filefavoritetoggle)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `favorite` | boolean | 是 | — | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "favorite": false
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [PersonalFileOut](schemas.md#schema-personalfileout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `name` | string | 是 | — | 名称 |
| `category` | string / null | 否 | — | — |
| `size_label` | string / null | 否 | — | — |
| `updated_at` | string / null | 否 | — | 最近更新时间 |
| `source` | string / null | 否 | — | 来源 |
| `is_favorite` | boolean | 否 | default=false | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | NOT_FOUND | '文件不存在' |

### `DELETE /api/v1/personal-hub/files/{file_id}`

用途：删除文件。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/personal_hub.py](../../backend/app/api/routes/personal_hub.py)，`delete_file`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `file_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | 动态响应；见下方补充与 response-contracts.md |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

实际响应补充：动态对象、透传、文件和流式返回不能由默认 OpenAPI 完整表达；业务字段说明在 [响应补充](response-contracts.md)。下面列出实现中的返回构造式，变量代表运行时值，并非 JSON 示例。

```python
{'ok': True}
```

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | NOT_FOUND | '文件不存在' |

### `GET /api/v1/personal-hub/favorites`

用途：列出收藏。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/personal_hub.py](../../backend/app/api/routes/personal_hub.py)，`list_favorites`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | array<[FavoriteOut](schemas.md#schema-favoriteout)> |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `POST /api/v1/personal-hub/favorites`

用途：添加收藏。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/personal_hub.py](../../backend/app/api/routes/personal_hub.py)，`add_favorite`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：`application/json`，必填；[FavoriteCreate](schemas.md#schema-favoritecreate)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | minLength=1; maxLength=128 | 当前资源标识 |
| `title` | string | 是 | minLength=1; maxLength=256 | 标题 |
| `type` | string / null | 否 | string约束: maxLength=32 | — |
| `subtitle` | string / null | 否 | string约束: maxLength=256 | — |
| `saved_at` | string / null | 否 | — | — |
| `source_route` | string / null | 否 | string约束: maxLength=64 | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "id": "<id>",
  "title": "<title>"
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 201 | application/json | [FavoriteOut](schemas.md#schema-favoriteout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

201 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `title` | string | 是 | — | 标题 |
| `type` | string / null | 否 | — | — |
| `subtitle` | string / null | 否 | — | — |
| `saved_at` | string / null | 否 | — | — |
| `source_route` | string / null | 否 | — | — |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `DELETE /api/v1/personal-hub/favorites/{favorite_id}`

用途：移除收藏。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/personal_hub.py](../../backend/app/api/routes/personal_hub.py)，`remove_favorite`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `favorite_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | 动态响应；见下方补充与 response-contracts.md |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

实际响应补充：动态对象、透传、文件和流式返回不能由默认 OpenAPI 完整表达；业务字段说明在 [响应补充](response-contracts.md)。下面列出实现中的返回构造式，变量代表运行时值，并非 JSON 示例。

```python
{'ok': True}
```

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | NOT_FOUND | '收藏不存在' |

### `GET /api/v1/universities`

用途：列出universities。

鉴权：公开或使用专用凭据（扫码 browser token / 可信设备 cookie 等见参数与流程）。

实现：[backend/app/api/routes/universities.py](../../backend/app/api/routes/universities.py)，`list_universities`。

Web 封装：`getUniversities`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| query | `q` | string / null | 否 | string约束: minLength=1; maxLength=128 | — |
| query | `province` | string / null | 否 | string约束: minLength=1; maxLength=128 | — |
| query | `city` | string / null | 否 | string约束: minLength=1; maxLength=128 | — |
| query | `level` | string / null | 否 | string约束: minLength=1; maxLength=32 | 办学层次：本科/专科 |
| query | `page` | integer | 否 | default=1; minimum=1 | — |
| query | `page_size` | integer | 否 | default=20; minimum=1; maximum=100 | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [UniversityPage](schemas.md#schema-universitypage) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `items` | array<[UniversityOut](schemas.md#schema-universityout)> | 是 | — | 列表条目 |
| `page` | integer | 是 | — | 当前页，从 1 开始 |
| `page_size` | integer | 是 | — | 每页数量 |
| `total` | integer | 是 | — | 总数 |

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/universities/{university_id}`

用途：读取大学。

鉴权：公开或使用专用凭据（扫码 browser token / 可信设备 cookie 等见参数与流程）。

实现：[backend/app/api/routes/universities.py](../../backend/app/api/routes/universities.py)，`get_university`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `university_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [UniversityOut](schemas.md#schema-universityout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `name` | string | 是 | — | 名称 |
| `short_name` | string / null | 否 | — | — |
| `province` | string / null | 否 | — | — |
| `city` | string / null | 否 | — | — |
| `country` | string | 是 | — | — |
| `level` | string / null | 否 | — | — |
| `logo_url` | string / null | 否 | — | — |
| `official_domain` | string / null | 否 | — | — |
| `official_website` | string / null | 否 | — | — |
| `academic_system_type` | string | 是 | — | — |
| `academic_system_url` | string / null | 否 | — | — |
| `academic_provider` | string | 是 | — | — |
| `forum_enabled` | boolean | 是 | — | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `is_demo` | boolean | 是 | — | — |
| `created_at` | string | 是 | — | 创建时间 |
| `updated_at` | string | 是 | — | 最近更新时间 |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | UNIVERSITY_NOT_FOUND | University not found |

### `PUT /api/v1/profile/university`

用途：更新个人学校选择。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/universities.py](../../backend/app/api/routes/universities.py)，`update_profile_university`。

Web 封装：`selectUniversity`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：`application/json`，必填；[ProfileUniversityUpdate](schemas.md#schema-profileuniversityupdate)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `university_id` | string / null | 是 | string约束: minLength=1; maxLength=128 | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "university_id": "<university_id>"
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [ProfileUniversityOut](schemas.md#schema-profileuniversityout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `university_id` | string / null | 否 | — | — |
| `university` | [UniversityOut](schemas.md#schema-universityout) / null | 否 | — | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | UNIVERSITY_NOT_FOUND | University not found |
