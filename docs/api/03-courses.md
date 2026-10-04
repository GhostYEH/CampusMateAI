# 课程、班级、公告、作业与提交

> 对照日期：2026-10-04。本模块共 27 个 HTTP 方法与路径组合；以当前后端注册路由和 Web 调用为依据。

[文档导航](README.md) · [接入与流程](integration.md) · [字段字典](schemas.md) · [OpenAPI](openapi.json)

## 接口索引

| 方法 | 完整路径 | 用途 |
| --- | --- | --- |
| GET | `/api/v1/courses` | 列出课程 |
| GET | `/api/v1/courses/{course_id}` | 读取课程 |
| GET | `/api/v1/classes` | 列出classes |
| GET | `/api/v1/classes/{class_id}` | 读取班级 |
| POST | `/api/v1/classes/{class_id}/join` | 加入班级 |
| GET | `/api/v1/classes/{class_id}/members` | 列出班级成员 |
| GET | `/api/v1/classes/{class_id}/announcements` | 列出公告 |
| GET | `/api/v1/announcements/{announcement_id}` | 读取公告 |
| POST | `/api/v1/announcements/{announcement_id}/read` | 标记公告已读 |
| GET | `/api/v1/classes/{class_id}/assignments` | 列出作业 |
| GET | `/api/v1/student/assignments` | 列出学生作业 |
| GET | `/api/v1/assignments/{assignment_id}` | 读取作业 |
| GET | `/api/v1/assignments/{assignment_id}/attachments` | 列出任务的所有附件 |
| GET | `/api/v1/assignments/{assignment_id}/attachments/{attachment_id}` | 下载任务附件 |
| GET | `/api/v1/assignments/{assignment_id}/my-submission` | 读取我的作业提交 |
| POST | `/api/v1/assignments/{assignment_id}/submissions` | 创建提交 |
| GET | `/api/v1/submissions/{submission_id}` | 读取提交 |
| PATCH | `/api/v1/submissions/{submission_id}` | 更新提交 |
| POST | `/api/v1/submissions/{submission_id}/submit` | 提交提交 |
| POST | `/api/v1/submissions/{submission_id}/attachments` | 上传附件 |
| GET | `/api/v1/submissions/{submission_id}/attachments/{attachment_id}` | 下载提交附件 |
| GET | `/api/v1/courses/{course_id}/content-summary` | 读取课程内容概况 |
| GET | `/api/v1/courses/{course_id}/content` | 列出内容 |
| GET | `/api/v1/courses/{course_id}/knowledge-graph` | 课程知识图谱：课程级统计 + 知识点清单 |
| POST | `/api/v1/courses/{course_id}/sync` | 同步课程内容 |
| GET | `/api/v1/courses/{course_id}/resources/{item_id}/open` | 打开课程资源 |
| GET | `/api/v1/courses/{course_id}/resources/{item_id}/download` | 下载课程资源 |

## 接口契约

### `GET /api/v1/courses`

用途：列出课程。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/courses.py](../../backend/app/api/routes/courses.py)，`list_courses`。

Web 封装：`getCourses`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| query | `query` | string / null | 否 | — | 按名称/代码/描述模糊搜索 |
| query | `status` | string / null | 否 | string约束: pattern="^(draft\|active\|archived)$" | — |
| query | `page` | integer | 否 | default=1; minimum=1 | — |
| query | `page_size` | integer | 否 | default=20; minimum=1; maximum=100 | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [Page](schemas.md#schema-page)；items 元素为 [CourseOut](schemas.md#schema-courseout) |
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

### `GET /api/v1/courses/{course_id}`

用途：读取课程。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/courses.py](../../backend/app/api/routes/courses.py)，`get_course`。

Web 封装：`getCourse`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）；`getCourseDetail`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `course_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [CourseOut](schemas.md#schema-courseout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `name` | string | 是 | — | 名称 |
| `code` | string / null | 否 | — | — |
| `semester` | string / null | 否 | — | — |
| `description` | string / null | 否 | — | 说明 |
| `teacher_id` | string / null | 否 | — | — |
| `teacher_name` | string / null | 否 | — | — |
| `provider` | string / null | 否 | — | — |
| `external_id` | string / null | 否 | — | — |
| `source_url` | string / null | 否 | — | 来源链接 |
| `last_synced_at` | string / null | 否 | — | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `created_at` | string | 是 | — | 创建时间 |
| `updated_at` | string | 是 | — | 最近更新时间 |
| `owner_user_id` | string / null | 否 | — | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | COURSE_NOT_FOUND | 课程不存在。 |
| 403 | FORBIDDEN | '你未加入此课程下的任何班级' |

### `GET /api/v1/classes`

用途：列出classes。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/classes.py](../../backend/app/api/routes/classes.py)，`list_classes`。

Web 封装：当前无封装；按本节后端契约调用。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| query | `course_id` | string / null | 否 | — | — |
| query | `page` | integer | 否 | default=1; minimum=1 | — |
| query | `page_size` | integer | 否 | default=20; minimum=1; maximum=100 | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [Page](schemas.md#schema-page)；items 元素为 [ClassOut](schemas.md#schema-classout) |
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

### `GET /api/v1/classes/{class_id}`

用途：读取班级。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/classes.py](../../backend/app/api/routes/classes.py)，`get_class`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `class_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [ClassOut](schemas.md#schema-classout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `course_id` | string | 是 | — | 关联课程标识 |
| `name` | string | 是 | — | 名称 |
| `class_code` | string / null | 否 | — | — |
| `invite_code` | string | 是 | — | — |
| `description` | string / null | 否 | — | 说明 |
| `capacity` | integer / null | 否 | — | — |
| `created_at` | string | 是 | — | 创建时间 |
| `updated_at` | string | 是 | — | 最近更新时间 |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | CLASS_GROUP_NOT_FOUND | 班级不存在。 |
| 403 | FORBIDDEN | '你未加入此班级' |

### `POST /api/v1/classes/{class_id}/join`

用途：加入班级。

鉴权：Bearer access token；角色 student。

实现：[backend/app/api/routes/classes.py](../../backend/app/api/routes/classes.py)，`join_class`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `class_id` | string | 是 | — | — |

请求体：`application/json`，必填；[ClassJoinRequest](schemas.md#schema-classjoinrequest)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `invite_code` | string | 是 | minLength=1; maxLength=32 | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{
  "invite_code": "<invite_code>"
}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [ClassOut](schemas.md#schema-classout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `course_id` | string | 是 | — | 关联课程标识 |
| `name` | string | 是 | — | 名称 |
| `class_code` | string / null | 否 | — | — |
| `invite_code` | string | 是 | — | — |
| `description` | string / null | 否 | — | 说明 |
| `capacity` | integer / null | 否 | — | — |
| `created_at` | string | 是 | — | 创建时间 |
| `updated_at` | string | 是 | — | 最近更新时间 |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | CLASS_GROUP_NOT_FOUND | 班级不存在。 |
| 404 | INVALID_INVITE_CODE | 邀请码无效或班级不存在。 |
| 409 | ALREADY_ENROLLED | 该学生已加入此班级。 |
| 409 | CLASS_GROUP_FULL | 班级已满员。 |

### `GET /api/v1/classes/{class_id}/members`

用途：列出班级成员。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/classes.py](../../backend/app/api/routes/classes.py)，`list_members`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `class_id` | string | 是 | — | — |
| query | `query` | string / null | 否 | — | — |
| query | `member_role` | string / null | 否 | string约束: pattern="^(student\|teaching_assistant)$" | — |
| query | `page` | integer | 否 | default=1; minimum=1 | — |
| query | `page_size` | integer | 否 | default=100; minimum=1; maximum=500 | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [Page](schemas.md#schema-page)；items 元素为 [ClassMemberOut](schemas.md#schema-classmemberout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `items` | array<any> | 否 | — | 列表条目 |
| `total` | integer | 否 | default=0 | 总数 |
| `page` | integer | 否 | default=1 | 当前页，从 1 开始 |
| `page_size` | integer | 否 | default=20 | 每页数量 |
| `has_more` | boolean | 否 | default=false | 是否还有下一页 |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | CLASS_GROUP_NOT_FOUND | 班级不存在。 |
| 403 | FORBIDDEN | '你未加入此班级' |

### `GET /api/v1/classes/{class_id}/announcements`

用途：列出公告。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/announcements.py](../../backend/app/api/routes/announcements.py)，`list_announcements`。

Web 封装：`getCourseDetail`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `class_id` | string | 是 | — | — |
| query | `status` | string / null | 否 | string约束: pattern="^(draft\|published\|archived)$" | — |
| query | `page` | integer | 否 | default=1; minimum=1 | — |
| query | `page_size` | integer | 否 | default=20; minimum=1; maximum=100 | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [Page](schemas.md#schema-page)；items 元素为 [AnnouncementOut](schemas.md#schema-announcementout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `items` | array<any> | 否 | — | 列表条目 |
| `total` | integer | 否 | default=0 | 总数 |
| `page` | integer | 否 | default=1 | 当前页，从 1 开始 |
| `page_size` | integer | 否 | default=20 | 每页数量 |
| `has_more` | boolean | 否 | default=false | 是否还有下一页 |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | CLASS_GROUP_NOT_FOUND | 班级不存在。 |

### `GET /api/v1/announcements/{announcement_id}`

用途：读取公告。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/announcements.py](../../backend/app/api/routes/announcements.py)，`get_announcement`。

Web 封装：`getAnnouncement`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `announcement_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [AnnouncementOut](schemas.md#schema-announcementout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `class_group_id` | string | 是 | — | — |
| `author_id` | string | 是 | — | — |
| `author_name` | string / null | 否 | — | — |
| `title` | string | 是 | — | 标题 |
| `content` | string | 是 | — | 正文或业务内容，嵌套结构按类型 |
| `require_read` | boolean | 是 | — | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `published_at` | string / null | 否 | — | — |
| `created_at` | string | 是 | — | 创建时间 |
| `updated_at` | string | 是 | — | 最近更新时间 |
| `has_read` | boolean / null | 否 | — | 当前用户是否已读 |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | ANNOUNCEMENT_NOT_FOUND | 通知不存在。 |
| 404 | CLASS_GROUP_NOT_FOUND | 班级不存在。 |

### `POST /api/v1/announcements/{announcement_id}/read`

用途：标记公告已读。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/announcements.py](../../backend/app/api/routes/announcements.py)，`mark_announcement_read`。

Web 封装：`markAnnouncementRead`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `announcement_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | 动态响应；见下方补充与 response-contracts.md |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

实际响应补充：动态对象、透传、文件和流式返回不能由默认 OpenAPI 完整表达；业务字段说明在 [响应补充](response-contracts.md)。下面列出实现中的返回构造式，变量代表运行时值，并非 JSON 示例。

```python
{'ok': True, 'first_time': first_time}
```

```python
{'ok': True, 'message': '无需标记已读'}
```

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | ANNOUNCEMENT_NOT_FOUND | 通知不存在。 |
| 404 | CLASS_GROUP_NOT_FOUND | 班级不存在。 |

### `GET /api/v1/classes/{class_id}/assignments`

用途：列出作业。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/assignments.py](../../backend/app/api/routes/assignments.py)，`list_assignments`。

Web 封装：`getCourseDetail`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `class_id` | string | 是 | — | — |
| query | `status` | string / null | 否 | string约束: pattern="^(draft\|published\|closed\|archived)$" | — |
| query | `page` | integer | 否 | default=1; minimum=1 | — |
| query | `page_size` | integer | 否 | default=20; minimum=1; maximum=100 | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [Page](schemas.md#schema-page)；items 元素为 [AssignmentOut](schemas.md#schema-assignmentout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `items` | array<any> | 否 | — | 列表条目 |
| `total` | integer | 否 | default=0 | 总数 |
| `page` | integer | 否 | default=1 | 当前页，从 1 开始 |
| `page_size` | integer | 否 | default=20 | 每页数量 |
| `has_more` | boolean | 否 | default=false | 是否还有下一页 |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | CLASS_GROUP_NOT_FOUND | 班级不存在。 |

### `GET /api/v1/student/assignments`

用途：列出学生作业。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/assignments.py](../../backend/app/api/routes/assignments.py)，`list_student_assignments`。

Web 封装：`getAssignments`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| query | `status` | string / null | 否 | string约束: pattern="^(pending\|submitted\|overdue\|graded)$" | — |
| query | `search` | string / null | 否 | string约束: maxLength=200 | — |
| query | `sort_by` | string | 否 | default="deadline"; pattern="^(deadline\|created_at\|title)$" | — |
| query | `sort_desc` | boolean | 否 | default=false | — |
| query | `page` | integer | 否 | default=1; minimum=1 | — |
| query | `page_size` | integer | 否 | default=20; minimum=1; maximum=100 | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [Page](schemas.md#schema-page)；items 元素为 [AssignmentOut](schemas.md#schema-assignmentout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `items` | array<any> | 否 | — | 列表条目 |
| `total` | integer | 否 | default=0 | 总数 |
| `page` | integer | 否 | default=1 | 当前页，从 1 开始 |
| `page_size` | integer | 否 | default=20 | 每页数量 |
| `has_more` | boolean | 否 | default=false | 是否还有下一页 |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 403 | FORBIDDEN | '仅学生可访问学生任务列表' |

### `GET /api/v1/assignments/{assignment_id}`

用途：读取作业。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/assignments.py](../../backend/app/api/routes/assignments.py)，`get_assignment`。

Web 封装：`getAssignment`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `assignment_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [AssignmentOut](schemas.md#schema-assignmentout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `class_group_id` | string | 是 | — | — |
| `course_id` | string / null | 否 | — | 关联课程标识 |
| `author_id` | string | 是 | — | — |
| `author_name` | string / null | 否 | — | — |
| `title` | string | 是 | — | 标题 |
| `description` | string / null | 否 | — | 说明 |
| `deadline` | string / null | 否 | — | 截止时间 |
| `submission_types` | array<string> | 否 | — | — |
| `max_score` | number / null | 否 | — | — |
| `allow_resubmit` | boolean | 是 | — | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `published_at` | string / null | 否 | — | — |
| `created_at` | string | 是 | — | 创建时间 |
| `updated_at` | string | 是 | — | 最近更新时间 |
| `submission_status` | string / null | 否 | — | 当前用户的提交状态 |
| `attachments` | array<[AssignmentAttachmentOut](schemas.md#schema-assignmentattachmentout)> | 否 | — | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | ASSIGNMENT_NOT_FOUND | 任务不存在。 |
| 404 | CLASS_GROUP_NOT_FOUND | 班级不存在。 |

### `GET /api/v1/assignments/{assignment_id}/attachments`

用途：列出任务的所有附件。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/assignments.py](../../backend/app/api/routes/assignments.py)，`list_assignment_attachments`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

列出任务的所有附件。

权限:
- 学生: 只能看到自己所在班级已发布任务的附件

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `assignment_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | array<[AssignmentAttachmentOut](schemas.md#schema-assignmentattachmentout)> |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | ASSIGNMENT_NOT_FOUND | 任务不存在。 |
| 404 | CLASS_GROUP_NOT_FOUND | 班级不存在。 |

### `GET /api/v1/assignments/{assignment_id}/attachments/{attachment_id}`

用途：下载任务附件。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/assignments.py](../../backend/app/api/routes/assignments.py)，`download_assignment_attachment`。

Web 封装：`downloadAssignmentAttachment`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

下载任务附件。

权限:
- 学生: 只能下载自己所在班级已发布任务的附件

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `assignment_id` | string | 是 | — | — |
| path | `attachment_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | 附件媒体类型 / application/octet-stream | FileResponse，Content-Disposition 指定文件名 |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

实际响应补充：动态对象、透传、文件和流式返回不能由默认 OpenAPI 完整表达；业务字段说明在 [响应补充](response-contracts.md)。下面列出实现中的返回构造式，变量代表运行时值，并非 JSON 示例。

```python
FileResponse(str(storage_path), filename=att.original_filename, media_type=att.mime_type or 'application/octet-stream')
```

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | ASSIGNMENT_NOT_FOUND | 任务不存在。 |
| 404 | CLASS_GROUP_NOT_FOUND | 班级不存在。 |
| 404 | NOT_FOUND | '附件不存在或不属于该任务' |
| 404 | NOT_FOUND | '附件文件已被删除' |

### `GET /api/v1/assignments/{assignment_id}/my-submission`

用途：读取我的作业提交。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/submissions.py](../../backend/app/api/routes/submissions.py)，`get_my_submission`。

Web 封装：`getSubmission`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `assignment_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [SubmissionOut](schemas.md#schema-submissionout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `assignment_id` | string | 是 | — | — |
| `student_id` | string | 是 | — | — |
| `student_name` | string / null | 否 | — | — |
| `student_number` | string / null | 否 | — | — |
| `college` | string / null | 否 | — | — |
| `major` | string / null | 否 | — | — |
| `grade` | string / null | 否 | — | — |
| `text_content` | string / null | 否 | — | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `submitted_at` | string / null | 否 | — | — |
| `updated_at` | string | 是 | — | 最近更新时间 |
| `score` | number / null | 否 | — | — |
| `teacher_comment` | string / null | 否 | — | — |
| `attachments` | array<[AttachmentOut](schemas.md#schema-attachmentout)> | 否 | — | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 403 | FORBIDDEN | '仅学生可查看自己的提交' |
| 404 | SUBMISSION_NOT_FOUND | 提交不存在。 |

### `POST /api/v1/assignments/{assignment_id}/submissions`

用途：创建提交。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/submissions.py](../../backend/app/api/routes/submissions.py)，`create_submission`。

Web 封装：`saveSubmission`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `assignment_id` | string | 是 | — | — |

请求体：`application/json`，必填；[SubmissionCreate](schemas.md#schema-submissioncreate)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `text_content` | string / null | 否 | string约束: maxLength=50000 | — |
| `submit` | boolean | 否 | default=false | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 201 | application/json | [SubmissionOut](schemas.md#schema-submissionout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

201 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `assignment_id` | string | 是 | — | — |
| `student_id` | string | 是 | — | — |
| `student_name` | string / null | 否 | — | — |
| `student_number` | string / null | 否 | — | — |
| `college` | string / null | 否 | — | — |
| `major` | string / null | 否 | — | — |
| `grade` | string / null | 否 | — | — |
| `text_content` | string / null | 否 | — | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `submitted_at` | string / null | 否 | — | — |
| `updated_at` | string | 是 | — | 最近更新时间 |
| `score` | number / null | 否 | — | — |
| `teacher_comment` | string / null | 否 | — | — |
| `attachments` | array<[AttachmentOut](schemas.md#schema-attachmentout)> | 否 | — | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | ASSIGNMENT_NOT_FOUND | 任务不存在。 |
| 403 | FORBIDDEN | '仅学生可创建提交' |
| 409 | ASSIGNMENT_CLOSED | 任务已截止提交。 |

### `GET /api/v1/submissions/{submission_id}`

用途：读取提交。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/submissions.py](../../backend/app/api/routes/submissions.py)，`get_submission`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `submission_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [SubmissionOut](schemas.md#schema-submissionout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `assignment_id` | string | 是 | — | — |
| `student_id` | string | 是 | — | — |
| `student_name` | string / null | 否 | — | — |
| `student_number` | string / null | 否 | — | — |
| `college` | string / null | 否 | — | — |
| `major` | string / null | 否 | — | — |
| `grade` | string / null | 否 | — | — |
| `text_content` | string / null | 否 | — | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `submitted_at` | string / null | 否 | — | — |
| `updated_at` | string | 是 | — | 最近更新时间 |
| `score` | number / null | 否 | — | — |
| `teacher_comment` | string / null | 否 | — | — |
| `attachments` | array<[AttachmentOut](schemas.md#schema-attachmentout)> | 否 | — | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | SUBMISSION_NOT_FOUND | 提交不存在。 |
| 404 | ASSIGNMENT_NOT_FOUND | 任务不存在。 |
| 403 | FORBIDDEN | '不能查看其他学生的提交' |

### `PATCH /api/v1/submissions/{submission_id}`

用途：更新提交。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/submissions.py](../../backend/app/api/routes/submissions.py)，`update_submission`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `submission_id` | string | 是 | — | — |

请求体：`application/json`，必填；[SubmissionUpdate](schemas.md#schema-submissionupdate)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `text_content` | string / null | 否 | string约束: maxLength=50000 | — |

请求结构示例（占位符需替换；业务约束见字段字典与流程）：

```json
{}
```

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [SubmissionOut](schemas.md#schema-submissionout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `assignment_id` | string | 是 | — | — |
| `student_id` | string | 是 | — | — |
| `student_name` | string / null | 否 | — | — |
| `student_number` | string / null | 否 | — | — |
| `college` | string / null | 否 | — | — |
| `major` | string / null | 否 | — | — |
| `grade` | string / null | 否 | — | — |
| `text_content` | string / null | 否 | — | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `submitted_at` | string / null | 否 | — | — |
| `updated_at` | string | 是 | — | 最近更新时间 |
| `score` | number / null | 否 | — | — |
| `teacher_comment` | string / null | 否 | — | — |
| `attachments` | array<[AttachmentOut](schemas.md#schema-attachmentout)> | 否 | — | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | SUBMISSION_NOT_FOUND | 提交不存在。 |
| 404 | ASSIGNMENT_NOT_FOUND | 任务不存在。 |
| 403 | FORBIDDEN | '只能修改自己的提交' |
| 409 | ASSIGNMENT_CLOSED | 任务已截止提交。 |

### `POST /api/v1/submissions/{submission_id}/submit`

用途：提交提交。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/submissions.py](../../backend/app/api/routes/submissions.py)，`submit_submission`。

Web 封装：`submitSubmission`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `submission_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [SubmissionOut](schemas.md#schema-submissionout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `assignment_id` | string | 是 | — | — |
| `student_id` | string | 是 | — | — |
| `student_name` | string / null | 否 | — | — |
| `student_number` | string / null | 否 | — | — |
| `college` | string / null | 否 | — | — |
| `major` | string / null | 否 | — | — |
| `grade` | string / null | 否 | — | — |
| `text_content` | string / null | 否 | — | — |
| `status` | string | 是 | — | 业务状态，合法取值和操作前置条件见枚举及流程 |
| `submitted_at` | string / null | 否 | — | — |
| `updated_at` | string | 是 | — | 最近更新时间 |
| `score` | number / null | 否 | — | — |
| `teacher_comment` | string / null | 否 | — | — |
| `attachments` | array<[AttachmentOut](schemas.md#schema-attachmentout)> | 否 | — | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | SUBMISSION_NOT_FOUND | 提交不存在。 |
| 404 | ASSIGNMENT_NOT_FOUND | 任务不存在。 |
| 403 | FORBIDDEN | '只能提交自己的提交' |
| 409 | RESUBMIT_NOT_ALLOWED | 该任务不允许重新提交。 |
| 409 | ASSIGNMENT_CLOSED | 任务已截止提交。 |

### `POST /api/v1/submissions/{submission_id}/attachments`

用途：上传附件。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/submissions.py](../../backend/app/api/routes/submissions.py)，`upload_attachment`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `submission_id` | string | 是 | — | — |

请求体：`multipart/form-data`，必填；[Body_upload_attachment_api_v1_submissions__submission_id__attachments_post](schemas.md#schema-body_upload_attachment_api_v1_submissions__submission_id__attachments_post)。

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `file` | string (binary) | 是 | format="binary" | — |

上传使用 FormData；字段名按上表；浏览器由运行时生成 multipart boundary。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 201 | application/json | [AttachmentOut](schemas.md#schema-attachmentout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

201 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | string | 是 | — | 当前资源标识 |
| `submission_id` | string | 是 | — | — |
| `original_filename` | string | 是 | — | — |
| `stored_filename` | string | 是 | — | — |
| `mime_type` | string / null | 否 | — | 媒体类型 |
| `size_bytes` | integer / null | 否 | — | — |
| `created_at` | string | 是 | — | 创建时间 |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | SUBMISSION_NOT_FOUND | 提交不存在。 |
| 404 | ASSIGNMENT_NOT_FOUND | 任务不存在。 |
| 415 | ATTACHMENT_TYPE_NOT_ALLOWED | f'不支持的文件类型: .{ext}' |
| 413 | ATTACHMENT_TOO_LARGE | '附件不能超过 10MB' |
| 400 | FILE_NAME_UNSAFE | '文件为空' |
| 400 | FILE_NAME_UNSAFE | '存储路径非法' |
| 403 | FORBIDDEN | '只能给自己的提交上传附件' |
| 409 | ASSIGNMENT_CLOSED | 任务已截止提交。 |
| 400 | FILE_NAME_UNSAFE | str(e) |

### `GET /api/v1/submissions/{submission_id}/attachments/{attachment_id}`

用途：下载提交附件。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/submissions.py](../../backend/app/api/routes/submissions.py)，`download_attachment`。

Web 封装：当前 Web 未找到直接封装；仍属于已注册后端接口。

下载提交附件。

权限:
- 学生: 只能下载自己提交的附件

安全:
- 严格校验 storage_path 位于允许的根目录之下(防路径穿越)
- 文件不存在则返回 404
- submission_id 与 attachment_id 必须匹配

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `submission_id` | string | 是 | — | — |
| path | `attachment_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | 附件媒体类型 / application/octet-stream | FileResponse，Content-Disposition 指定文件名 |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

实际响应补充：动态对象、透传、文件和流式返回不能由默认 OpenAPI 完整表达；业务字段说明在 [响应补充](response-contracts.md)。下面列出实现中的返回构造式，变量代表运行时值，并非 JSON 示例。

```python
FileResponse(str(storage_path), filename=att.original_filename, media_type=att.mime_type or 'application/octet-stream')
```

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | SUBMISSION_NOT_FOUND | 提交不存在。 |
| 404 | ASSIGNMENT_NOT_FOUND | 任务不存在。 |
| 404 | NOT_FOUND | '附件不存在或不属于该提交' |
| 404 | NOT_FOUND | '附件文件已被删除' |
| 403 | FORBIDDEN | '不能下载其他学生的附件' |

### `GET /api/v1/courses/{course_id}/content-summary`

用途：读取课程内容概况。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/course_content.py](../../backend/app/api/routes/course_content.py)，`get_content_summary`。

Web 封装：`getCourseDetail`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `course_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [CourseContentSummaryOut](schemas.md#schema-coursecontentsummaryout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `course_id` | string | 是 | — | 关联课程标识 |
| `provider` | string / null | 否 | — | — |
| `cover_url` | string / null | 否 | — | — |
| `teacher_name` | string / null | 否 | — | — |
| `school_name` | string / null | 否 | — | — |
| `class_name` | string / null | 否 | — | — |
| `student_count` | integer / null | 否 | — | — |
| `starts_at` | string / null | 否 | — | — |
| `ends_at` | string / null | 否 | — | — |
| `last_synced_at` | string / null | 否 | — | — |
| `sections` | array<[CourseSectionStatusOut](schemas.md#schema-coursesectionstatusout)> | 否 | — | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | HTTPException | 'course_not_found' |

### `GET /api/v1/courses/{course_id}/content`

用途：列出内容。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/course_content.py](../../backend/app/api/routes/course_content.py)，`list_content`。

Web 封装：`getCourseDetail`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `course_id` | string | 是 | — | — |
| query | `kind` | string / null | 否 | — | — |
| query | `page` | integer | 否 | default=1; minimum=1 | — |
| query | `page_size` | integer | 否 | default=100; minimum=1; maximum=500 | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [CourseContentPage](schemas.md#schema-coursecontentpage) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `items` | array<[CourseContentItemOut](schemas.md#schema-coursecontentitemout)> | 否 | — | 列表条目 |
| `total` | integer | 是 | — | 总数 |
| `page` | integer | 是 | — | 当前页，从 1 开始 |
| `page_size` | integer | 是 | — | 每页数量 |
| `has_more` | boolean | 是 | — | 是否还有下一页 |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | HTTPException | 'course_not_found' |

### `GET /api/v1/courses/{course_id}/knowledge-graph`

用途：课程知识图谱：课程级统计 + 知识点清单。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/course_content.py](../../backend/app/api/routes/course_content.py)，`get_knowledge_graph`。

Web 封装：`getCourseKnowledgeGraph`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

课程知识图谱：课程级统计 + 知识点清单。

数据来自外部数据源（课程/学校发布的课程图谱页）经 deep 同步落库的观测，
不是本地推断。未同步过时返回 available=False 而不是 404，方便客户端区分
"没有这个课程"和"这个课程还没同步"。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `course_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | [KnowledgeGraphOut](schemas.md#schema-knowledgegraphout) |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

200 响应顶层字段：

| 字段 | 类型 | 必须出现 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `course_id` | string | 是 | — | 关联课程标识 |
| `available` | boolean | 否 | default=false | 当前能力是否可用 |
| `synced_at` | string / null | 否 | — | — |
| `knowledge_point_count` | integer | 否 | default=0 | — |
| `own_mastery_rate` | number / null | 否 | — | — |
| `class_mastery_rate` | number / null | 否 | — | — |
| `mastery_gap_vs_class` | number / null | 否 | — | — |
| `own_completion_rate` | number / null | 否 | — | — |
| `class_completion_rate` | number / null | 否 | — | — |
| `tags` | array<string> | 否 | — | — |
| `points` | array<[KnowledgePointOut](schemas.md#schema-knowledgepointout)> | 否 | — | — |

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | HTTPException | 'course_not_found' |

### `POST /api/v1/courses/{course_id}/sync`

用途：同步课程内容。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/course_content.py](../../backend/app/api/routes/course_content.py)，`sync_course_content`。

Web 封装：`syncCourse`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `course_id` | string | 是 | — | — |
| query | `depth` | string | 否 | default="fast"; pattern="^(fast\|deep\|full)$" | — |
| query | `sections` | string / null | 否 | — | 逗号分隔的 section 白名单，覆盖 depth 推导结果 |
| query | `force_refresh` | boolean | 否 | default=false | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | 动态响应；见下方补充与 response-contracts.md |
| 503 | application/json | `code: CHAOXING_CREDENTIALS_UNAVAILABLE`；连接信息无法读取，保留已同步数据，请重新连接学习通 |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

实际响应补充：动态对象、透传、文件和流式返回不能由默认 OpenAPI 完整表达；业务字段说明在 [响应补充](response-contracts.md)。下面列出实现中的返回构造式，变量代表运行时值，并非 JSON 示例。

```python
await ChaoxingCourseContentSyncService(container).sync_course(user_id=user.id, course_id=course_id, depth=depth, force_refresh=force_refresh, sections=requested)
```

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 503 | CHAOXING_CREDENTIALS_UNAVAILABLE | 已有凭据损坏或无法解密；重新登录或解除连接后重绑，不应自动反复重试 |
| 400 | HTTPException | 'not_chaoxing_course' |
| 400 | HTTPException | str(error) |
| 404 | HTTPException | 'course_not_found' |

兼容性与客户端处理：成功响应和请求参数不变，503 是既有凭据读取失败的显式声明。Web、Android、HarmonyOS 均消费课程同步接口；收到 `CHAOXING_CREDENTIALS_UNAVAILABLE` 时保留已缓存课程，提示用户从学习通连接页重新登录或解除连接后重绑，停止自动反复重试。微信小程序当前没有该接口消费。Web 已通过自动化错误契约验证；Android、HarmonyOS 的原生编译未在本次环境验证。

### `GET /api/v1/courses/{course_id}/resources/{item_id}/open`

用途：打开课程资源。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/course_content.py](../../backend/app/api/routes/course_content.py)，`open_resource`。

Web 封装：`openCourseResource`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `course_id` | string | 是 | — | — |
| path | `item_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | application/json | 动态响应；见下方补充与 response-contracts.md |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |

实际响应补充：动态对象、透传、文件和流式返回不能由默认 OpenAPI 完整表达；业务字段说明在 [响应补充](response-contracts.md)。下面列出实现中的返回构造式，变量代表运行时值，并非 JSON 示例。

```python
{'url': safe_url, 'mode': 'external'}
```

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 404 | HTTPException | 'resource_not_found' |
| 404 | HTTPException | 'resource_url_missing' |
| 400 | HTTPException | error.code |
| 404 | HTTPException | 'course_not_found' |

### `GET /api/v1/courses/{course_id}/resources/{item_id}/download`

用途：下载课程资源。

鉴权：Bearer access token；已登录用户（另有资源归属校验）。

实现：[backend/app/api/routes/course_content.py](../../backend/app/api/routes/course_content.py)，`download_resource`。

Web 封装：`downloadCourseResource`（[webreact/src/data/api.js](../../webreact/src/data/api.js)）

音视频流支持可选 **Range** 请求头并转发上游；返回 **200 / 206**，范围错误可返回 **416**（http_error_416）。Content-Range、Accept-Ranges、Content-Length 等以实际上游结果为准。必须按二进制解析，并携带本站登录态与有效学习通绑定。

参数：

| 位置 | 名称 | 类型 | OpenAPI 必填 | 默认值 / 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| path | `course_id` | string | 是 | — | — |
| path | `item_id` | string | 是 | — | — |

请求体：无。

响应：

| HTTP | Content-Type | 结构 |
| --- | --- | --- |
| 200 | 实际资源媒体类型 | 文件 / 上游二进制流 |
| 503 | application/json | `code: CHAOXING_CREDENTIALS_UNAVAILABLE`；连接信息无法读取，保留已同步数据，请重新连接学习通 |
| 422 | application/json | 运行时为 [统一错误结构](integration.md#errors)（默认 OpenAPI 的 HTTPValidationError 不反映全局处理器） |
| 206 | 实际资源媒体类型 | 文件 / 上游二进制流 |

实际响应补充：动态对象、透传、文件和流式返回不能由默认 OpenAPI 完整表达；业务字段说明在 [响应补充](response-contracts.md)。下面列出实现中的返回构造式，变量代表运行时值，并非 JSON 示例。

```python
FileResponse(path, media_type=mime_type, filename=filename)
```

```python
StreamingResponse(stream_result['stream'], media_type=stream_result['mime_type'], status_code=stream_result['status_code'], headers=headers)
```

路由及同模块辅助函数显式抛出的业务错误（鉴权、服务内部和依赖还可能产生公共错误）：

| HTTP / 分支 | code / 异常 | 原因或 message 表达式 |
| --- | --- | --- |
| 503 | CHAOXING_CREDENTIALS_UNAVAILABLE | 已有凭据损坏或无法解密；重新登录或解除连接后重绑，不应自动反复重试 |
| 404 | HTTPException | 'resource_not_found' |
| 400 | HTTPException | 'resource_not_downloadable' |
| 401 | HTTPException | 'chaoxing_credentials_not_found' |
| status | HTTPException | error.code |
| 404 | HTTPException | 'course_not_found' |

兼容性与客户端处理：成功文件和流式协议不变；503 使用 JSON 统一错误结构，客户端须先检查 HTTP 状态，不能把错误体当作资源文件缓存。Web、Android、HarmonyOS 均消费下载接口，凭据损坏时应保留现有缓存并引导重新连接；微信小程序当前没有该接口消费。Web 自动化测试已验证错误文案，移动端原生编译未在本次环境验证。
