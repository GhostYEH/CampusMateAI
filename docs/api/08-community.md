# 校园社区与内容管理

> 对照日期：2026-10-04。本模块共 14 个 HTTP 方法与路径组合；以当前后端注册路由和 Web 调用为依据。

[文档导航](README.md) · [接入与流程](integration.md) · [字段字典](schemas.md) · [OpenAPI](openapi.json)

## 学校隔离与举报反馈

社区仅提供普通用户接口。帖子、评论、互动和举报按当前用户的 `university_id` 限定范围，未选学校返回 409 `UNIVERSITY_REQUIRED`，他校帖子返回 404 `NOT_FOUND`；历史账号同样遵守此规则。

所有 `/api/v1/admin/community/*` 管理接口已移除并返回 404，包括帖子隐藏、全校/全局列表和举报处理。用户仍可举报，记录保持 `pending`；当前产品没有在线审核入口，客户端不得展示管理员审核承诺。

Web 与 HarmonyOS 已同步调整举报提示；Android 和微信小程序仍使用原普通用户请求。请求结构不变；移动端编译与真机流程未验证。

## 接口索引

| 方法 | 完整路径 | 用途 |
| --- | --- | --- |
| GET | `/api/v1/community/posts/categories` | 列出categories |
| GET | `/api/v1/community/posts` | 列出帖子 |
| POST | `/api/v1/community/posts` | 创建帖子 |
| GET | `/api/v1/community/posts/{post_id}` | 读取帖子 |
| PUT | `/api/v1/community/posts/{post_id}` | 更新帖子 |
| DELETE | `/api/v1/community/posts/{post_id}` | 删除帖子 |
| POST | `/api/v1/community/upload-image` | 上传图片 |
| GET | `/api/v1/community/posts/{post_id}/comments` | 列出评论 |
| POST | `/api/v1/community/posts/{post_id}/comments` | 创建评论 |
| POST | `/api/v1/community/posts/{post_id}/like` | 点赞 |
| DELETE | `/api/v1/community/posts/{post_id}/like` | 取消点赞 |
| POST | `/api/v1/community/posts/{post_id}/favorite` | 收藏 |
| DELETE | `/api/v1/community/posts/{post_id}/favorite` | 取消收藏 |
| POST | `/api/v1/community/reports` | 举报 |

## 接口契约

### `GET /api/v1/community/posts/categories`

用途：列出categories。

鉴权：公开或使用专用凭据（扫码 browser token / 可信设备 cookie 等见参数与流程）。

实现：[backend/app/api/routes/community.py](../../backend/app/api/routes/community.py)，`list_categories`。

Web 封装：`getCommunityCategories`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

未声明响应模型的社区接口字段见 [实际响应补充](response-contracts.md#community)。点赞、收藏、删除返回帖子对象，不能统一当作 `{ok:true}`。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | 动态响应；见下方补充与 response-contracts.md |

实际响应补充：动态对象、透传、文件和流式返回不能由默认 OpenAPI 完整表达；业务字段说明在 [响应补充](response-contracts.md)。下面列出实现中的返回构造式，变量代表运行时值，并非 JSON 示例。

```python
{'items': CATEGORY_META}
```

异常：公共鉴权 / 校验错误及依赖服务错误，见 [接入约定](integration.md#errors)。

### `GET /api/v1/community/posts`

用途：列出帖子。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/community.py](../../backend/app/api/routes/community.py)，`list_posts`。

Web 封装：`getCommunityPosts`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

未声明响应模型的社区接口字段见 [实际响应补充](response-contracts.md#community)。点赞、收藏、删除返回帖子对象，不能统一当作 `{ok:true}`。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| query | `q` | string / null | 否 | string约束: maxLength=200 | — |
| query | `category` | string / null | 否 | string约束: maxLength=32 | — |
| query | `sort` | string | 否 | default="time"; pattern="^(time\|hot)$" | — |
| query | `page` | integer | 否 | default=1; minimum=1 | — |
| query | `page_size` | integer | 否 | default=20; minimum=1; maximum=100 | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | 动态响应；见下方补充与 response-contracts.md |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

实际响应补充：动态对象、透传、文件和流式返回不能由默认 OpenAPI 完整表达；业务字段说明在 [响应补充](response-contracts.md)。下面列出实现中的返回构造式，变量代表运行时值，并非 JSON 示例。

```python
{'items': [_post_out(row, c, user.id) for row in rows], 'page': page, 'page_size': page_size, 'total': total}
```

```python
{**row, 'images': images, 'extra': extra, 'is_anonymous': anonymous, 'author_id': None if anonymous else row['author_id'], 'author_name': '校园同学' if anonymous else author.display_name or author.username if author else '已注销用户', 'liked': liked, 'favorited': favorited, 'is_owner': is_owner}
```

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 409 | UNIVERSITY_REQUIRED | 请先选择你的大学 |

### `POST /api/v1/community/posts`

用途：创建帖子。

鉴权：Bearer access token；角色 student。

实现：[backend/app/api/routes/community.py](../../backend/app/api/routes/community.py)，`create_post`。

Web 封装：`createCommunityPost`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

未声明响应模型的社区接口字段见 [实际响应补充](response-contracts.md#community)。点赞、收藏、删除返回帖子对象，不能统一当作 `{ok:true}`。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：`application/json`，必填；[PostCreate](schemas.md#schema-postcreate)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `title` | string | 是 | minLength=1; maxLength=120 | 标题 |
| `content` | string | 是 | minLength=1; maxLength=10000 | 正文或业务内容，嵌套结构按类型 |
| `category` | string | 否 | default="campus"; pattern="^(campus\|study\|life\|secondhand\|question\|activity\|experience\|recruit\|errand\|other)$" | — |
| `images` | array<string> | 否 | maxItems=9 | — |
| `is_anonymous` | boolean | 否 | default=false | — |
| `extra` | object / null | 否 | — | — |

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
| 201 | application/json | 动态响应；见下方补充与 response-contracts.md |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

实际响应补充：动态对象、透传、文件和流式返回不能由默认 OpenAPI 完整表达；业务字段说明在 [响应补充](response-contracts.md)。下面列出实现中的返回构造式，变量代表运行时值，并非 JSON 示例。

```python
_post_out(row, c, user.id)
```

```python
{**row, 'images': images, 'extra': extra, 'is_anonymous': anonymous, 'author_id': None if anonymous else row['author_id'], 'author_name': '校园同学' if anonymous else author.display_name or author.username if author else '已注销用户', 'liked': liked, 'favorited': favorited, 'is_owner': is_owner}
```

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 409 | UNIVERSITY_REQUIRED | 请先选择你的大学 |

### `GET /api/v1/community/posts/{post_id}`

用途：读取帖子。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/community.py](../../backend/app/api/routes/community.py)，`get_post`。

Web 封装：`getCommunityPost`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

未声明响应模型的社区接口字段见 [实际响应补充](response-contracts.md#community)。点赞、收藏、删除返回帖子对象，不能统一当作 `{ok:true}`。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `post_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | 动态响应；见下方补充与 response-contracts.md |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

实际响应补充：动态对象、透传、文件和流式返回不能由默认 OpenAPI 完整表达；业务字段说明在 [响应补充](response-contracts.md)。下面列出实现中的返回构造式，变量代表运行时值，并非 JSON 示例。

```python
_post_out(post, c, user.id)
```

```python
{**row, 'images': images, 'extra': extra, 'is_anonymous': anonymous, 'author_id': None if anonymous else row['author_id'], 'author_name': '校园同学' if anonymous else author.display_name or author.username if author else '已注销用户', 'liked': liked, 'favorited': favorited, 'is_owner': is_owner}
```

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | NOT_FOUND | '帖子不存在' |
| 409 | UNIVERSITY_REQUIRED | 请先选择你的大学 |

### `PUT /api/v1/community/posts/{post_id}`

用途：更新帖子。

鉴权：Bearer access token；角色 student。

实现：[backend/app/api/routes/community.py](../../backend/app/api/routes/community.py)，`update_post`。

Web 封装：`updateCommunityPost`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

未声明响应模型的社区接口字段见 [实际响应补充](response-contracts.md#community)。点赞、收藏、删除返回帖子对象，不能统一当作 `{ok:true}`。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `post_id` | string | 是 | — | — |

请求体：`application/json`，必填；[PostUpdate](schemas.md#schema-postupdate)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `title` | string / null | 否 | string约束: minLength=1; maxLength=120 | 标题 |
| `content` | string / null | 否 | string约束: minLength=1; maxLength=10000 | 正文或业务内容，嵌套结构按类型 |
| `category` | string / null | 否 | string约束: pattern="^(campus\|study\|life\|secondhand\|question\|activity\|experience\|recruit\|errand\|other)$" | — |
| `images` | array<string> / null | 否 | array约束: maxItems=9 | — |
| `is_anonymous` | boolean / null | 否 | — | — |
| `extra` | object / null | 否 | — | — |

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
_post_out(row or post, c, user.id)
```

```python
{**row, 'images': images, 'extra': extra, 'is_anonymous': anonymous, 'author_id': None if anonymous else row['author_id'], 'author_name': '校园同学' if anonymous else author.display_name or author.username if author else '已注销用户', 'liked': liked, 'favorited': favorited, 'is_owner': is_owner}
```

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 403 | FORBIDDEN | '只能编辑自己的帖子' |
| 404 | NOT_FOUND | '帖子不存在' |
| 409 | UNIVERSITY_REQUIRED | 请先选择你的大学 |

### `DELETE /api/v1/community/posts/{post_id}`

用途：删除帖子。

鉴权：Bearer access token；角色 student。

实现：[backend/app/api/routes/community.py](../../backend/app/api/routes/community.py)，`delete_post`。

Web 封装：`deleteCommunityPost`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

未声明响应模型的社区接口字段见 [实际响应补充](response-contracts.md#community)。点赞、收藏、删除返回帖子对象，不能统一当作 `{ok:true}`。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `post_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | 动态响应；见下方补充与 response-contracts.md |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

实际响应补充：动态对象、透传、文件和流式返回不能由默认 OpenAPI 完整表达；业务字段说明在 [响应补充](response-contracts.md)。下面列出实现中的返回构造式，变量代表运行时值，并非 JSON 示例。

```python
_post_out(c.community_repository.set_post_status(post_id, 'deleted'), c, user.id)
```

```python
{**row, 'images': images, 'extra': extra, 'is_anonymous': anonymous, 'author_id': None if anonymous else row['author_id'], 'author_name': '校园同学' if anonymous else author.display_name or author.username if author else '已注销用户', 'liked': liked, 'favorited': favorited, 'is_owner': is_owner}
```

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 403 | FORBIDDEN | '只能删除自己的帖子' |
| 404 | NOT_FOUND | '帖子不存在' |
| 409 | UNIVERSITY_REQUIRED | 请先选择你的大学 |

### `POST /api/v1/community/upload-image`

用途：上传图片。

鉴权：Bearer access token；角色 student。

实现：[backend/app/api/routes/community.py](../../backend/app/api/routes/community.py)，`upload_image`。

Web 封装：`uploadCommunityImage`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

未声明响应模型的社区接口字段见 [实际响应补充](response-contracts.md#community)。点赞、收藏、删除返回帖子对象，不能统一当作 `{ok:true}`。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：`multipart/form-data`，必填；[Body_upload_image_api_v1_community_upload_image_post](schemas.md#schema-body_upload_image_api_v1_community_upload_image_post)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `image` | string (binary) | 是 | format="binary" | — |

上传使用 FormData；字段名按上表；浏览器由运行时生成 multipart boundary。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [UploadImageResponse](schemas.md#schema-uploadimageresponse) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `url` | string | 是 | — | — |
| `filename` | string | 是 | — | 文件名 |
| `size` | integer | 是 | — | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 415 | 'IMAGE_TYPE_INVALID' | '仅支持 JPG/PNG/WebP/GIF 图片' |
| 413 | 'IMAGE_TOO_LARGE' | f'图片超过 {settings.community_image_max_mb} MB 上限' |

### `GET /api/v1/community/posts/{post_id}/comments`

用途：列出评论。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/community.py](../../backend/app/api/routes/community.py)，`list_comments`。

Web 封装：`getComments`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

未声明响应模型的社区接口字段见 [实际响应补充](response-contracts.md#community)。点赞、收藏、删除返回帖子对象，不能统一当作 `{ok:true}`。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `post_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | 动态响应；见下方补充与 response-contracts.md |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

实际响应补充：动态对象、透传、文件和流式返回不能由默认 OpenAPI 完整表达；业务字段说明在 [响应补充](response-contracts.md)。下面列出实现中的返回构造式，变量代表运行时值，并非 JSON 示例。

```python
{'items': [_comment_out(row, c) for row in rows], 'page': 1, 'page_size': len(rows), 'total': len(rows)}
```

```python
{**row, 'is_anonymous': anonymous, 'author_id': None if anonymous else row['author_id'], 'author_name': '校园同学' if anonymous else author.display_name or author.username if author else '已注销用户'}
```

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | NOT_FOUND | '帖子不存在' |
| 409 | UNIVERSITY_REQUIRED | 请先选择你的大学 |

### `POST /api/v1/community/posts/{post_id}/comments`

用途：创建评论。

鉴权：Bearer access token；角色 student。

实现：[backend/app/api/routes/community.py](../../backend/app/api/routes/community.py)，`create_comment`。

Web 封装：`createComment`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

未声明响应模型的社区接口字段见 [实际响应补充](response-contracts.md#community)。点赞、收藏、删除返回帖子对象，不能统一当作 `{ok:true}`。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `post_id` | string | 是 | — | — |

请求体：`application/json`，必填；[CommentCreate](schemas.md#schema-commentcreate)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `content` | string | 是 | minLength=1; maxLength=2000 | 正文或业务内容，嵌套结构按类型 |
| `parent_comment_id` | string / null | 否 | — | — |
| `is_anonymous` | boolean | 否 | default=false | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "content": "<content>"
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 201 | application/json | 动态响应；见下方补充与 response-contracts.md |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

实际响应补充：动态对象、透传、文件和流式返回不能由默认 OpenAPI 完整表达；业务字段说明在 [响应补充](response-contracts.md)。下面列出实现中的返回构造式，变量代表运行时值，并非 JSON 示例。

```python
_comment_out(row, c)
```

```python
{**row, 'is_anonymous': anonymous, 'author_id': None if anonymous else row['author_id'], 'author_name': '校园同学' if anonymous else author.display_name or author.username if author else '已注销用户'}
```

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | NOT_FOUND | '父评论不存在' |
| 404 | NOT_FOUND | '帖子不存在' |
| 409 | UNIVERSITY_REQUIRED | 请先选择你的大学 |

### `POST /api/v1/community/posts/{post_id}/like`

用途：点赞。

鉴权：Bearer access token；角色 student。

实现：[backend/app/api/routes/community.py](../../backend/app/api/routes/community.py)，`like`。

Web 封装：`likePost`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

未声明响应模型的社区接口字段见 [实际响应补充](response-contracts.md#community)。点赞、收藏、删除返回帖子对象，不能统一当作 `{ok:true}`。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `post_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | 动态响应；见下方补充与 response-contracts.md |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

实际响应补充：动态对象、透传、文件和流式返回不能由默认 OpenAPI 完整表达；业务字段说明在 [响应补充](response-contracts.md)。下面列出实现中的返回构造式，变量代表运行时值，并非 JSON 示例。

```python
_toggle(post_id, user, c, 'forum_likes', 'like_count', True)
```

```python
{**row, 'images': images, 'extra': extra, 'is_anonymous': anonymous, 'author_id': None if anonymous else row['author_id'], 'author_name': '校园同学' if anonymous else author.display_name or author.username if author else '已注销用户', 'liked': liked, 'favorited': favorited, 'is_owner': is_owner}
```

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | NOT_FOUND | '帖子不存在' |
| 409 | UNIVERSITY_REQUIRED | 请先选择你的大学 |

### `DELETE /api/v1/community/posts/{post_id}/like`

用途：取消点赞。

鉴权：Bearer access token；角色 student。

实现：[backend/app/api/routes/community.py](../../backend/app/api/routes/community.py)，`unlike`。

Web 封装：`unlikePost`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

未声明响应模型的社区接口字段见 [实际响应补充](response-contracts.md#community)。点赞、收藏、删除返回帖子对象，不能统一当作 `{ok:true}`。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `post_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | 动态响应；见下方补充与 response-contracts.md |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

实际响应补充：动态对象、透传、文件和流式返回不能由默认 OpenAPI 完整表达；业务字段说明在 [响应补充](response-contracts.md)。下面列出实现中的返回构造式，变量代表运行时值，并非 JSON 示例。

```python
_toggle(post_id, user, c, 'forum_likes', 'like_count', False)
```

```python
{**row, 'images': images, 'extra': extra, 'is_anonymous': anonymous, 'author_id': None if anonymous else row['author_id'], 'author_name': '校园同学' if anonymous else author.display_name or author.username if author else '已注销用户', 'liked': liked, 'favorited': favorited, 'is_owner': is_owner}
```

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | NOT_FOUND | '帖子不存在' |
| 409 | UNIVERSITY_REQUIRED | 请先选择你的大学 |

### `POST /api/v1/community/posts/{post_id}/favorite`

用途：收藏。

鉴权：Bearer access token；角色 student。

实现：[backend/app/api/routes/community.py](../../backend/app/api/routes/community.py)，`favorite`。

Web 封装：`favoritePost`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

未声明响应模型的社区接口字段见 [实际响应补充](response-contracts.md#community)。点赞、收藏、删除返回帖子对象，不能统一当作 `{ok:true}`。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `post_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | 动态响应；见下方补充与 response-contracts.md |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

实际响应补充：动态对象、透传、文件和流式返回不能由默认 OpenAPI 完整表达；业务字段说明在 [响应补充](response-contracts.md)。下面列出实现中的返回构造式，变量代表运行时值，并非 JSON 示例。

```python
_toggle(post_id, user, c, 'forum_favorites', 'favorite_count', True)
```

```python
{**row, 'images': images, 'extra': extra, 'is_anonymous': anonymous, 'author_id': None if anonymous else row['author_id'], 'author_name': '校园同学' if anonymous else author.display_name or author.username if author else '已注销用户', 'liked': liked, 'favorited': favorited, 'is_owner': is_owner}
```

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | NOT_FOUND | '帖子不存在' |
| 409 | UNIVERSITY_REQUIRED | 请先选择你的大学 |

### `DELETE /api/v1/community/posts/{post_id}/favorite`

用途：取消收藏。

鉴权：Bearer access token；角色 student。

实现：[backend/app/api/routes/community.py](../../backend/app/api/routes/community.py)，`unfavorite`。

Web 封装：`unfavoritePost`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

未声明响应模型的社区接口字段见 [实际响应补充](response-contracts.md#community)。点赞、收藏、删除返回帖子对象，不能统一当作 `{ok:true}`。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `post_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | 动态响应；见下方补充与 response-contracts.md |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

实际响应补充：动态对象、透传、文件和流式返回不能由默认 OpenAPI 完整表达；业务字段说明在 [响应补充](response-contracts.md)。下面列出实现中的返回构造式，变量代表运行时值，并非 JSON 示例。

```python
_toggle(post_id, user, c, 'forum_favorites', 'favorite_count', False)
```

```python
{**row, 'images': images, 'extra': extra, 'is_anonymous': anonymous, 'author_id': None if anonymous else row['author_id'], 'author_name': '校园同学' if anonymous else author.display_name or author.username if author else '已注销用户', 'liked': liked, 'favorited': favorited, 'is_owner': is_owner}
```

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | NOT_FOUND | '帖子不存在' |
| 409 | UNIVERSITY_REQUIRED | 请先选择你的大学 |

### `POST /api/v1/community/reports`

用途：举报。

鉴权：Bearer access token；角色 student。

实现：[backend/app/api/routes/community.py](../../backend/app/api/routes/community.py)，`report`。

Web 封装：`reportPost`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

未声明响应模型的社区接口字段见 [实际响应补充](response-contracts.md#community)。点赞、收藏、删除返回帖子对象，不能统一当作 `{ok:true}`。

参数：无 path / query / header 参数；Bearer 头按鉴权说明提供。

请求体：`application/json`，必填；[ReportCreate](schemas.md#schema-reportcreate)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `target_type` | string | 是 | pattern="^(post\|comment)$" | — |
| `target_id` | string | 是 | minLength=1; maxLength=128 | — |
| `reason` | string | 是 | pattern="^(垃圾广告\|辱骂攻击\|色情低俗\|违法违规\|隐私泄露\|诈骗\|其它)$" | 原因 |
| `details` | string / null | 否 | string约束: maxLength=1000 | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "target_type": "<target_type>",
  "target_id": "<target_id>",
  "reason": "<reason>"
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 201 | application/json | 动态响应；见下方补充与 response-contracts.md |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

实际响应补充：动态对象、透传、文件和流式返回不能由默认 OpenAPI 完整表达；业务字段说明在 [响应补充](response-contracts.md)。下面列出实现中的返回构造式，变量代表运行时值，并非 JSON 示例。

```python
c.community_repository.create_report(university_id=university_id, reporter_id=user.id, **req.model_dump())
```

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 409 | UNIVERSITY_REQUIRED | 请先选择你的大学 |
| 404 | NOT_FOUND | '帖子不存在' |
