# CampusMate AI 多角色协同平台 API 契约

> 版本: v1 · 统一前缀 `/api/v1` · 默认端口 `8000`
>
> 本文件覆盖 **教师 / 课程 / 班级 / 学生 / 任务 / 提交** 等多角色协同接口,
> 与 [`api_contract.md`](./api_contract.md)(单学生助手接口)互为补充。
>
> 字段含义、枚举值、错误码均以本文为准,Pydantic 模型对应
> [`backend/app/schemas/multi_role.py`](../backend/app/schemas/multi_role.py)。

---

## 目录

- [通用约定](#通用约定)
- [验收账号(dev/test 环境)](#验收账号devtest-环境)
- [1. 认证 Auth](#1-认证-auth)
- [2. 课程 Courses](#2-课程-courses)
- [3. 班级 Classes](#3-班级-classes)
- [4. 通知 Announcements](#4-通知-announcements)
- [5. 任务 Assignments](#5-任务-assignments)
- [6. 提交 Submissions](#6-提交-submissions)
- [7. 工作台 Dashboard](#7-工作台-dashboard)
- [8. AI 导员上下文融合](#8-ai-导员上下文融合)
- [RBAC 权限矩阵](#rbac-权限矩阵)
- [数据模型](#数据模型)
- [数据库迁移](#数据库迁移)
- [附件安全](#附件安全)
- [性能策略](#性能策略)
- [错误码](#错误码)
- [当前限制](#当前限制)

---

## 通用约定

### Base URL

```
http://{host}:{port}/api/v1
```

### 鉴权

除 `POST /auth/login`、`POST /auth/refresh` 与匿名 `/counselor/chat` 外,
**所有多角色接口都需要 JWT access token**:

```
Authorization: Bearer <access_token>
```

SSE / EventSource 因浏览器不支持自定义 header,可在 query 中传:

```
GET /api/v1/counselor/chat?access_token=<access_token>
```

### 时间格式

ISO 8601 带时区,如 `2026-09-30T23:59:59+08:00`。
所有 `deadline` / `published_at` / `submitted_at` 等字段均为字符串。

### 分页响应

所有列表接口(`GET /courses`、`GET /classes/{id}/announcements` 等)统一返回:

```json
{
  "items": [],
  "total": 0,
  "page": 1,
  "page_size": 20,
  "has_more": false
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `items` | array | 当前页数据 |
| `total` | int | 总条数 |
| `page` | int | 当前页码(从 1 起) |
| `page_size` | int | 每页大小 |
| `has_more` | bool | 是否还有下一页 |

### 错误响应

统一结构(同 [`api_contract.md`](./api_contract.md) 错误格式):

```json
{
  "code": "FORBIDDEN",
  "message": "无权访问该资源。",
  "details": null
}
```

新增错误码见 [错误码](#错误码) 章节。

---

## 验收账号(dev/test 环境)

> 正式 Release 不提供任何"演示账号"或绕过认证的特殊账号。
> 验收账号为**普通用户**,走完整真实业务流程(JWT 登录 / RBAC 校验 / 真实 SQL),
> 不持有任何特殊权限或 Mock 数据开关。

启动时若 `AUTO_SEED_DEMO_USERS=true`(默认关闭;仅 dev/test 显式开启;
**production 下强制抛 ValidationError**),会幂等 seed 以下账号:

| 角色 | 用户名 | 密码 | 备注 |
|------|--------|------|------|
| 教师 | `teacher_demo` | `Demo123456` | 李老师(信息工程学院) |
| 教师 | `teacher_demo2` | `Demo123456` | 王老师(外国语学院) |
| 学生 | `student_demo` | `Demo123456` | 陈同学 |
| 学生 | `student_demo_01` ~ `student_demo_30` | `Demo123456` | 30 名验收学生 |
| 管理员 | `admin_demo` | `Demo123456` | 管理员(验收) |

> 所有验收账号均明确标注"(演示)"后缀,密码统一为 `Demo123456`。
> 验收数据涵盖 3 门课程、4 个班级、6 条通知、8 个任务、若干提交与评分,
> 覆盖已读/未读/已交/未交/逾期等不同状态。
> **验收数据并非真实学校数据**,仅用于 dev/test 验证业务流程。
> 正式生产环境中,验收账号应由管理员通过真实业务流程在数据库中创建。

---

## 1. 认证 Auth

### `POST /api/v1/auth/login`

用户名 + 密码登录,返回 access token + refresh token。

**请求体**

```json
{
  "username": "teacher_demo",
  "password": "Demo123456"
}
```

**响应 200** — `TokenPair`

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "Bearer",
  "expires_in": 1800
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `access_token` | string | JWT access token(默认 30 分钟) |
| `refresh_token` | string | JWT refresh token(默认 14 天) |
| `token_type` | string | 固定 `Bearer` |
| `expires_in` | int | access token 有效期(秒) |

**安全设计**

- 登录失败统一返回 `401 INVALID_CREDENTIALS`,**不泄露用户名是否存在**。
- 密码使用 PBKDF2-HMAC-SHA256(100k 迭代 + 16 字节 salt)。
- 不在日志中记录密码或 token 明文。

**错误**

| HTTP | code | 触发场景 |
|------|------|----------|
| 401 | `INVALID_CREDENTIALS` | 用户名不存在 / 密码错误 / 用户已停用 |
| 422 | `VALIDATION_FAILED` | 字段缺失或格式错误 |

---

### `POST /api/v1/auth/refresh`

用 refresh token 换发新的 access token + refresh token。

**请求体**

```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
}
```

**响应 200** — `TokenPair`(同 login)

**安全设计**

- 旧 refresh token 在换发后被撤销(防止重放)。
- refresh token 在数据库仅存 SHA-256 哈希,不可逆。

**错误**

| HTTP | code | 触发场景 |
|------|------|----------|
| 401 | `UNAUTHORIZED` | refresh token 无效 / 已撤销 / 已过期 / 用户已停用 |

---

### `POST /api/v1/auth/logout`

撤销当前 refresh token(可选)。需要 access token。

**请求体**

```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
}
```

**响应 200**

```json
{
  "ok": true,
  "message": "已退出登录"
}
```

> access token 当前不维护黑名单,因其有效期短(30 分钟)。
> 如需强制下线,可扩展 jti 黑名单。

---

### `GET /api/v1/auth/me`

返回当前登录用户信息。需要 access token。

**响应 200** — `AuthMeResponse`

```json
{
  "user": {
    "id": "u_abc123",
    "username": "teacher_demo",
    "role": "teacher",
    "display_name": "李老师(演示)",
    "student_number": null,
    "teacher_number": "T2024001",
    "college": "信息工程学院",
    "major": "计算机系",
    "grade": null,
    "avatar_url": null,
    "is_active": true,
    "created_at": "2026-07-26T10:00:00+00:00",
    "updated_at": "2026-07-26T10:00:00+00:00"
  },
  "access_token": null,
  "expires_in": null
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `user` | UserPublic | 用户公开信息(不含 `password_hash`) |
| `access_token` | string\|null | 当前 access token(此处恒为 null,仅做扩展位) |
| `expires_in` | int\|null | 剩余有效期(此处恒为 null) |

**UserPublic 字段**

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string | 用户 ID |
| `username` | string | 用户名(唯一) |
| `role` | string | `student` / `teacher` / `admin` |
| `display_name` | string\|null | 显示名 |
| `student_number` | string\|null | 学号(非空时唯一) |
| `teacher_number` | string\|null | 工号(非空时唯一) |
| `college` | string\|null | 学院 |
| `major` | string\|null | 专业 |
| `grade` | string\|null | 年级 |
| `avatar_url` | string\|null | 头像 URL |
| `is_active` | bool | 是否启用 |

---

### `POST /api/v1/auth/admin/users`

管理员创建用户接口(仅 `admin` 角色可调用)。用于在真实数据库中创建教师/学生/管理员账号,
执行完整真实业务流程,无任何"演示专用通道"或绕过认证的特殊账号。

正式 Release 原则: 真实登录 → 真实课程班级 → 真实发布 → 真实学生接收 → 真实提交 → 真实统计。
所有验收账号均通过此接口在真实数据库中创建,执行的仍是完整真实业务流程。

**权限**: 仅 `admin` 角色可调用(`require_role("admin")`)。学生/教师调用返回 403,未认证返回 401。

**请求体** — `UserCreate`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `username` | string | 是 | 3-64 字符,仅字母/数字/下划线 |
| `password` | string | 是 | 8-128 字符(后端 PBKDF2-HMAC-SHA256 哈希后存储,不入日志) |
| `role` | string | 是 | `student` / `teacher` / `admin` |
| `display_name` | string\|null | 否 | 显示名,最长 128 字符 |
| `student_number` | string\|null | 否 | 学号(非空时唯一);仅 `student` 角色可携带 |
| `teacher_number` | string\|null | 否 | 工号(非空时唯一);仅 `teacher` 角色可携带 |
| `college` | string\|null | 否 | 学院 |
| `major` | string\|null | 否 | 专业 |
| `grade` | string\|null | 否 | 年级 |

**一致性校验**:

- `role=student` 时不得携带 `teacher_number`(否则 422 `VALIDATION_FAILED`)
- `role=teacher` 时不得携带 `student_number`(否则 422)
- `role=admin` 时不得携带 `student_number` 或 `teacher_number`(否则 422)

**响应 201** — `UserPublic`(不含 `password_hash`)

```json
{
  "id": "usr_new_001",
  "username": "new_teacher_can_login",
  "role": "teacher",
  "display_name": "新教师(验收)",
  "student_number": null,
  "teacher_number": "T_NEW_001",
  "college": null,
  "major": null,
  "grade": null,
  "avatar_url": null,
  "is_active": true,
  "created_at": "2026-07-26T10:00:00+00:00",
  "updated_at": "2026-07-26T10:00:00+00:00"
}
```

**错误响应**

| HTTP | code | 说明 |
|------|------|------|
| 401 | `UNAUTHORIZED` | 未携带 access token |
| 403 | `FORBIDDEN` | 当前角色非 `admin` |
| 409 | `USERNAME_EXISTS` | 用户名已被占用 |
| 409 | `STUDENT_NUMBER_EXISTS` | 学号已被占用 |
| 409 | `TEACHER_NUMBER_EXISTS` | 工号已被占用 |
| 422 | `VALIDATION_FAILED` | 角色与学号/工号不一致,或字段格式不合法 |

**安全设计**:

- 密码以 PBKDF2-HMAC-SHA256(100k 迭代)哈希存储,响应不返回 `password_hash` 或 `password`
- 创建的账号可立即通过 `POST /api/v1/auth/login` 登录,走完整真实业务流程
- 无任何"演示专用通道"或绕过认证的特殊账号

---

## 2. 课程 Courses

### `GET /api/v1/courses`

列出当前用户可见的课程。

**Query 参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `query` | string | 否 | 按名称/代码/描述模糊搜索 |
| `status` | string | 否 | `draft` / `active` / `archived` |
| `page` | int | 否 | 默认 1 |
| `page_size` | int | 否 | 默认 20,最大 100 |

**权限**

- 学生: 只看自己已加入班级所属的课程。
- 教师: 只看自己负责的课程。
- 管理员: 看全部课程。

**响应 200** — `Page<CourseOut>`

```json
{
  "items": [
    {
      "id": "c_xxx",
      "name": "演示课程-程序设计基础",
      "code": "DEMO-CS101-2024",
      "semester": "2024-2025秋季",
      "description": "Python 入门",
      "teacher_id": "u_xxx",
      "teacher_name": "李老师(演示)",
      "status": "active",
      "created_at": "...",
      "updated_at": "..."
    }
  ],
  "total": 3,
  "page": 1,
  "page_size": 20,
  "has_more": false
}
```

---

### `POST /api/v1/courses`

创建课程。

**请求体** — `CourseCreate`

```json
{
  "name": "数据结构",
  "code": "CS201",
  "semester": "2025-2026春季",
  "description": "数据结构与算法基础",
  "status": "draft"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | string | 是 | 1~128 字符 |
| `code` | string | 否 | ≤ 64 字符 |
| `semester` | string | 否 | ≤ 32 字符 |
| `description` | string | 否 | ≤ 2000 字符 |
| `status` | string | 否 | `draft`(默认) / `active` / `archived` |

**权限**: 仅 `teacher` / `admin`。`teacher_id` 自动设为当前用户。

**响应 201** — `CourseOut`

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string | 课程 ID |
| `name` | string | 名称 |
| `code` | string\|null | 课程代码 |
| `semester` | string\|null | 学期 |
| `description` | string\|null | 描述 |
| `teacher_id` | string | 负责教师 ID |
| `teacher_name` | string\|null | 教师姓名 |
| `status` | string | 课程状态 |
| `created_at` | string | 创建时间 |
| `updated_at` | string | 更新时间 |

---

### `GET /api/v1/courses/{course_id}`

课程详情。

**权限**

- 学生: 必须已加入该课程下的任一班级。
- 教师: 必须为该课程的负责教师。
- 管理员: 任意。

**响应 200** — `CourseOut`

---

### `PATCH /api/v1/courses/{course_id}`

更新课程信息。仅 `teacher_id == 当前用户` 或 `admin` 可调用。

**请求体** — `CourseUpdate`(所有字段可选)

---

## 3. 班级 Classes

### `GET /api/v1/classes`

**Query 参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `course_id` | string | 否 | 按课程筛选 |
| `page` | int | 否 | 默认 1 |
| `page_size` | int | 否 | 默认 20,最大 100 |

**权限**

- 学生: 只看自己已加入的班级。
- 教师: 只看自己课程下的班级。
- 管理员: 全部。

**响应 200** — `Page<ClassOut>`

```json
{
  "items": [
    {
      "id": "cg_xxx",
      "course_id": "c_xxx",
      "name": "演示-计科1班",
      "class_code": "DEMO-MATH101-CLS1",
      "invite_code": "AB3X9K",
      "description": "演示班级-演示-计科1班",
      "capacity": 40,
      "created_at": "...",
      "updated_at": "..."
    }
  ],
  "total": 4,
  "page": 1,
  "page_size": 20,
  "has_more": false
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `invite_code` | string | 6 位随机邀请码,可重置,全局唯一 |

---

### `POST /api/v1/courses/{course_id}/classes`

在指定课程下创建班级。

**请求体** — `ClassCreate`

```json
{
  "name": "2024级计科1班",
  "class_code": "CS2024-1",
  "description": "...",
  "capacity": 50
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | string | 是 | 1~128 字符 |
| `class_code` | string | 否 | ≤ 64 字符 |
| `description` | string | 否 | ≤ 2000 字符 |
| `capacity` | int | 否 | 1~1000 |

**权限**: 必须为该课程的负责教师或管理员。
创建后教师自动加入班级为 `teaching_assistant`。

**响应 201** — `ClassOut`

---

### `GET /api/v1/classes/{class_id}` / `PATCH /api/v1/classes/{class_id}`

详情/更新。PATCH 仅教师/管理员可调用。

---

### `POST /api/v1/classes/{class_id}/join`

学生凭邀请码加入班级。

**请求体** — `ClassJoinRequest`

```json
{
  "invite_code": "AB3X9K"
}
```

**权限**: 仅 `student` / `admin`。

**响应 200** — `ClassOut`

**安全设计**

- 邀请码必须与 URL 中的 `class_id` 匹配,防止通过任意 class_id + 邀请码绕过。
- 已加入返回 `409 ALREADY_ENROLLED`。
- 班级满员返回 `409 CLASS_GROUP_FULL`。
- 曾被移除的学生重新加入会重新激活原 enrollment。

---

### `POST /api/v1/classes/{class_id}/reset-invite-code`

重置邀请码(教师/管理员)。返回新班级对象。

---

### `GET /api/v1/classes/{class_id}/members`

列出班级成员。

**Query 参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `query` | string | 否 | 按姓名/学号/工号模糊搜索 |
| `member_role` | string | 否 | `student` / `teaching_assistant` |
| `page` | int | 否 | 默认 1 |
| `page_size` | int | 否 | 默认 100,最大 500 |

**权限**: 教师/管理员可看全部;学生只能看同班同学。

**响应 200** — `Page<ClassMemberOut>`

```json
{
  "items": [
    {
      "user_id": "u_xxx",
      "username": "student_demo",
      "display_name": "陈同学(演示)",
      "student_number": "S202401001",
      "teacher_number": null,
      "college": "信息工程学院",
      "major": "计算机科学与技术",
      "grade": "2024",
      "avatar_url": null,
      "role": "student",
      "enrollment_id": "e_xxx",
      "member_role": "student",
      "status": "active",
      "joined_at": "..."
    }
  ],
  "total": 31,
  "page": 1,
  "page_size": 100,
  "has_more": false
}
```

---

### `DELETE /api/v1/classes/{class_id}/members/{user_id}`

移除成员(将 status 置为 `removed`)。仅教师/管理员可调用。

**响应 200**

```json
{"ok": true, "message": "成员已移除"}
```

---

## 4. 通知 Announcements

### `GET /api/v1/classes/{class_id}/announcements`

**Query 参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `status` | string | 否 | `draft` / `published` / `archived`(学生强制 `published`) |
| `page` | int | 否 | 默认 1 |
| `page_size` | int | 否 | 默认 20,最大 100 |

**权限**

- 学生: 必须已加入班级;只能看 `published` 通知。
- 教师/管理员: 可看草稿等。

**响应 200** — `Page<AnnouncementOut>`

```json
{
  "items": [
    {
      "id": "ann_xxx",
      "class_group_id": "cg_xxx",
      "author_id": "u_xxx",
      "author_name": "李老师(演示)",
      "title": "开学第一周课程安排",
      "content": "请同学们注意...",
      "require_read": true,
      "status": "published",
      "published_at": "2026-07-26T10:00:00+00:00",
      "created_at": "...",
      "updated_at": "...",
      "has_read": false
    }
  ],
  "total": 6,
  "page": 1,
  "page_size": 20,
  "has_more": false
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `require_read` | bool | 是否必须确认已读 |
| `has_read` | bool\|null | 学生视角是否已读;教师/管理员为 null |

---

### `POST /api/v1/classes/{class_id}/announcements`

创建通知(默认为 `draft`)。仅教师/管理员。

**请求体** — `AnnouncementCreate`

```json
{
  "title": "开学第一周课程安排",
  "content": "...",
  "require_read": true,
  "status": "draft"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `title` | string | 是 | 1~200 字符 |
| `content` | string | 是 | 1~20000 字符 |
| `require_read` | bool | 否 | 默认 false |
| `status` | string | 否 | `draft`(默认) / `published` / `archived` |

**响应 201** — `AnnouncementOut`

---

### `GET /api/v1/announcements/{announcement_id}` / `PATCH /api/v1/announcements/{announcement_id}`

详情/更新。学生不可见草稿。

---

### `POST /api/v1/announcements/{announcement_id}/publish`

发布通知(draft → published)。仅作者或管理员。

**响应 200** — `AnnouncementOut`(status=`published`, `published_at` 已填)

---

### `POST /api/v1/announcements/{announcement_id}/read`

学生标记已读(幂等)。

**权限**: 仅学生,且必须已加入该班级。

**响应 200**

```json
{
  "ok": true,
  "first_time": true
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `first_time` | bool | true=本次为首次标记;false=之前已读 |

> 重复标记不产生重复记录,因 `announcement_read_receipts` 表对 `(announcement_id, student_id)` 有主键约束。

---

### `GET /api/v1/announcements/{announcement_id}/read-status`

通知已读统计。仅教师/管理员可调用(须为本班级负责教师)。

**响应 200** — `ReadStatusOut`

```json
{
  "announcement_id": "ann_xxx",
  "total_recipients": 31,
  "read_count": 18,
  "unread_count": 13,
  "receipts": [
    {
      "user_id": "u_xxx",
      "username": "student_demo",
      "display_name": "陈同学(演示)",
      "student_number": "S202401001",
      "read_at": "2026-07-26T11:00:00+00:00"
    }
  ]
}
```

---

## 5. 任务 Assignments

### `GET /api/v1/classes/{class_id}/assignments`

**Query 参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `status` | string | 否 | `draft` / `published` / `closed` / `archived`(学生强制 `published`) |
| `page` | int | 否 | 默认 1 |
| `page_size` | int | 否 | 默认 20,最大 100 |

**权限**: 同通知列表。学生只看 `published`。

**响应 200** — `Page<AssignmentOut>`

```json
{
  "items": [
    {
      "id": "asg_xxx",
      "class_group_id": "cg_xxx",
      "author_id": "u_xxx",
      "author_name": "李老师(演示)",
      "title": "第一章习题",
      "description": "完成课本 P15-P18 第 1-5 题。",
      "deadline": "2026-09-20T23:59:59+08:00",
      "submission_types": ["text", "file"],
      "max_score": 100.0,
      "allow_resubmit": true,
      "status": "published",
      "published_at": "...",
      "created_at": "...",
      "updated_at": "..."
    }
  ],
  "total": 8,
  "page": 1,
  "page_size": 20,
  "has_more": false
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `deadline` | string\|null | ISO 8601 截止时间 |
| `submission_types` | string[] | 允许的提交类型(如 `["text","file"]`) |
| `max_score` | float\|null | 满分 |
| `allow_resubmit` | bool | 是否允许重新提交 |
| `status` | string | `draft` / `published` / `closed` / `archived` |

---

### `POST /api/v1/classes/{class_id}/assignments`

创建任务。仅教师/管理员。

**请求体** — `AssignmentCreate`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `title` | string | 是 | 1~200 字符 |
| `description` | string | 否 | ≤ 20000 字符 |
| `deadline` | string | 否 | ISO 8601 带时区 |
| `submission_types` | string[] | 否 | ≤ 10 项 |
| `max_score` | float | 否 | 0~1000 |
| `allow_resubmit` | bool | 否 | 默认 true |
| `status` | string | 否 | `draft`(默认) / `published` / `closed` / `archived` |

---

### `GET /api/v1/assignments/{assignment_id}` / `PATCH /api/v1/assignments/{assignment_id}`

详情/更新。学生不可见草稿。

---

### `POST /api/v1/assignments/{assignment_id}/publish`

发布任务(draft → published)。仅作者或管理员。

---

### `POST /api/v1/assignments/{assignment_id}/close`

关闭任务(不再接受新提交)。仅作者或管理员。

---

### `GET /api/v1/assignments/{assignment_id}/stats`

任务统计。仅教师/管理员。

**响应 200** — `AssignmentStatsOut`

```json
{
  "assignment_id": "asg_xxx",
  "total_students": 31,
  "submitted": 18,
  "not_submitted": 13,
  "draft": 4,
  "late": 2,
  "graded": 10,
  "pending_grading": 8,
  "avg_score": 88.5
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `total_students` | int | 班级学生总数 |
| `submitted` | int | 已提交(含 resubmitted/late,不含 draft) |
| `not_submitted` | int | 未提交 |
| `draft` | int | 草稿数 |
| `late` | int | 逾期提交数 |
| `graded` | int | 已评分 |
| `pending_grading` | int | 已提交但未评分 |
| `avg_score` | float\|null | 平均分(无评分时为 null) |

> 全部使用单条聚合 SQL,无 N+1 查询。

---

### `GET /api/v1/assignments/{assignment_id}/student-status`

学生状态列表(教师视角)。仅教师/管理员。

**Query 参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `submission_status` | string | 否 | `not_submitted` / `draft` / `submitted` / `resubmitted` / `late` |
| `read_status` | string | 否 | `read` / `unread`(注: 任务当前 read_status 固定 `not_required`,留作扩展) |
| `query` | string | 否 | 按姓名/学号搜索 |
| `page` | int | 否 | 默认 1 |
| `page_size` | int | 否 | 默认 100,最大 500 |

**响应 200** — `Page<StudentStatusItem>`

```json
{
  "items": [
    {
      "student_id": "u_xxx",
      "student_name": "陈同学(演示)",
      "student_number": "S202401001",
      "submission_id": "sub_xxx",
      "submission_status": "submitted",
      "submitted_at": "2026-09-19T22:00:00+08:00",
      "is_late": false,
      "score": null,
      "teacher_comment": null,
      "read_status": "not_required",
      "read_at": null
    }
  ],
  "total": 31,
  "page": 1,
  "page_size": 100,
  "has_more": false
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `submission_status` | string | `not_submitted` / `draft` / `submitted` / `resubmitted` / `late` |
| `is_late` | bool | 是否逾期提交 |
| `score` | float\|null | 评分 |
| `teacher_comment` | string\|null | 教师评语 |

> 通过 `LEFT JOIN enrollments + LEFT JOIN submissions` 单条聚合查询生成,
> 不保存可实时计算的冗余状态。

---

## 6. 提交 Submissions

### `GET /api/v1/assignments/{assignment_id}/submissions`

提交列表(教师视角)。仅教师/管理员。

**Query 参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `status` | string | 否 | `draft` / `submitted` / `resubmitted` / `late` |
| `page` | int | 否 | 默认 1 |
| `page_size` | int | 否 | 默认 50,最大 200 |

**响应 200** — `Page<SubmissionOut>`

```json
{
  "items": [
    {
      "id": "sub_xxx",
      "assignment_id": "asg_xxx",
      "student_id": "u_xxx",
      "student_name": "陈同学(演示)",
      "student_number": "S202401001",
      "college": "信息工程学院",
      "major": "计算机科学与技术",
      "grade": "2024",
      "text_content": "答案见附件。",
      "status": "submitted",
      "submitted_at": "...",
      "updated_at": "...",
      "score": null,
      "teacher_comment": null,
      "attachments": []
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 50,
  "has_more": false
}
```

> `attachments` 字段在列表接口恒为空数组 `[]`,
> 详情接口(`GET /submissions/{id}`)才会返回完整附件列表(避免列表接口过大)。

---

### `POST /api/v1/assignments/{assignment_id}/submissions`

学生创建提交(草稿或直接提交)。

**请求体** — `SubmissionCreate`

```json
{
  "text_content": "答案见附件。",
  "submit": false
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `text_content` | string | 否 | ≤ 50000 字符 |
| `submit` | bool | 否 | true=直接提交;false=保存草稿(默认 false) |

**权限**: 仅学生。已加入班级才可创建。

**状态计算**

- `submit=false` → `draft`
- `submit=true` 且未过截止 → `submitted`
- `submit=true` 且已过截止 → `late`
- 任务 `closed` 且 `submit=true` → `409 ASSIGNMENT_CLOSED`

**响应 201** — `SubmissionOut`

> 同一学生同一任务只能存在一个当前提交记录(`UNIQUE(assignment_id, student_id)` 约束),
> 重复创建会被 upsert 替换。

---

### `GET /api/v1/submissions/{submission_id}`

提交详情(含附件列表)。

**权限**

- 学生: 只能看自己的提交。
- 教师: 必须为该任务所在班级的负责教师。
- 管理员: 任意。

**响应 200** — `SubmissionOut`(含 `attachments` 数组)

---

### `PATCH /api/v1/submissions/{submission_id}`

学生更新提交文本(保持原状态)。

**权限**: 仅本人。

**错误**

| HTTP | code | 触发场景 |
|------|------|----------|
| 409 | `ASSIGNMENT_CLOSED` | 任务已关闭且不允许重新提交 |

---

### `POST /api/v1/submissions/{submission_id}/submit`

学生正式提交(或将草稿/已交重新提交)。

**权限**: 仅本人。

**状态转换**

- 已过截止 → `late`
- 之前已提交 → `resubmitted`
- 否则 → `submitted`

**错误**

| HTTP | code | 触发场景 |
|------|------|----------|
| 409 | `RESUBMIT_NOT_ALLOWED` | 已提交且 `allow_resubmit=false` |
| 409 | `ASSIGNMENT_CLOSED` | 任务已关闭且 `allow_resubmit=false` |

---

### `POST /api/v1/submissions/{submission_id}/attachments`

上传附件(`multipart/form-data`)。

**请求字段**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `file` | File | 是 | 附件文件 |

**权限**

- 学生: 只能给自己提交上传;任务关闭后不可上传。
- 教师/管理员: 不可上传(避免混淆)。

**附件安全限制**

- 扩展名白名单: `txt md pdf doc docx xls xlsx ppt pptx png jpg jpeg gif zip py cpp java c`
- 文件大小: ≤ 10 MB
- 文件名: 必须通过 `sanitize_filename` 校验,拒绝路径穿越字符(`/` `\` `..` 等)与 shell 元字符
- 空文件: 拒绝
- 存储路径: `./data/submission_attachments/<submission_id>/<uuid>_<safe_name>`,二次校验 `is_path_traversal`

**响应 201** — `AttachmentOut`

```json
{
  "id": "att_xxx",
  "submission_id": "sub_xxx",
  "original_filename": "homework.pdf",
  "stored_filename": "a1b2c3d4e5f67890_homework.pdf",
  "mime_type": "application/pdf",
  "size_bytes": 204800,
  "created_at": "..."
}
```

> 不返回文件内容;下载请使用 `GET /api/v1/submissions/{submission_id}/attachments/{attachment_id}`。

**错误**

| HTTP | code | 触发场景 |
|------|------|----------|
| 400 | `FILE_NAME_UNSAFE` | 文件名包含非法字符 / 空文件 |
| 413 | `ATTACHMENT_TOO_LARGE` | > 10 MB |
| 415 | `ATTACHMENT_TYPE_NOT_ALLOWED` | 扩展名不在白名单 |

---

### `GET /api/v1/submissions/{submission_id}/attachments/{attachment_id}`

下载提交附件(返回文件二进制流,`Content-Type` 与附件 `mime_type` 一致)。

**权限**

- 学生: 只能下载**自己**提交的附件
- 教师/管理员: 只能下载**自己课程下**任一学生的附件(走 `_assert_can_manage_class` 校验)
- 未认证: 返回 401

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| `submission_id` | string | 提交 ID(必须存在) |
| `attachment_id` | string | 附件 ID(必须属于该 submission_id) |

**安全校验**

- `submission_id` 与 `attachment_id` 必须匹配(否则 404 `NOT_FOUND`)
- `storage_path` 必须解析到 `./data/submission_attachments/` 之下(防路径穿越);不通过则 404 `NOT_FOUND`
- 文件不存在于磁盘(已被外部删除): 返回 404 `NOT_FOUND`(避免泄露存在性)

**响应 200** — `FileResponse`

```
Content-Type: application/pdf
Content-Disposition: attachment; filename="homework.pdf"

<binary>
```

**错误**

| HTTP | code | 触发场景 |
|------|------|----------|
| 401 | `UNAUTHORIZED` | 未携带 access token |
| 403 | `FORBIDDEN` | 学生下载他人附件 / 教师非本课程负责教师 |
| 404 | `SUBMISSION_NOT_FOUND` | `submission_id` 不存在 |
| 404 | `NOT_FOUND` | `attachment_id` 不存在或不属于该提交 / 文件已被删除 / 路径非法 |

---

### `POST /api/v1/submissions/{submission_id}/grade`

教师评分。

**请求体** — `SubmissionGrade`

```json
{
  "score": 95.0,
  "teacher_comment": "思路清晰,大部分正确。第 3 题注意符号问题。"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `score` | float | 否 | 0~1000 |
| `teacher_comment` | string | 否 | ≤ 5000 字符 |

**权限**: 教师(须为本班级负责教师)或管理员。

**响应 200** — `SubmissionOut`

---

## 7. 工作台 Dashboard

### `GET /api/v1/dashboard/teacher`

教师工作台。

**权限**: 教师 / 管理员(管理员返回空摘要)。

**响应 200** — `TeacherDashboard`

```json
{
  "course_count": 2,
  "class_count": 3,
  "student_count": 31,
  "active_assignment_count": 5,
  "pending_submission_count": 13,
  "unread_announcement_count": 0,
  "overdue_student_count": 2,
  "recent_assignments": [
    {
      "assignment_id": "asg_xxx",
      "title": "第一章习题",
      "status": "published",
      "deadline": "2026-09-20T23:59:59+08:00",
      "published_at": "...",
      "class_id": "cg_xxx",
      "class_name": "演示-计科1班",
      "course_id": "c_xxx",
      "course_name": "演示课程-高等数学(上)"
    }
  ],
  "recent_activity": []
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `course_count` | int | 教师所辖课程数 |
| `class_count` | int | 教师所辖班级数 |
| `student_count` | int | 教师所辖学生总数 |
| `active_assignment_count` | int | 已发布且未关闭的任务数 |
| `pending_submission_count` | int | 待评分提交数 |
| `unread_announcement_count` | int | 教师未读通知数(教师视角通常 0) |
| `overdue_student_count` | int | 逾期未交学生数 |
| `recent_assignments` | dict[] | 最近 5 个任务(含课程/班级名) |
| `recent_activity` | dict[] | 最近活动(后续扩展,当前为空) |

> 全部聚合 SQL,无 N+1。

---

### `GET /api/v1/dashboard/student`

学生工作台。

**权限**: 学生 / 管理员(管理员返回空摘要)。

**响应 200** — `StudentDashboard`

```json
{
  "enrolled_course_count": 2,
  "unread_announcement_count": 3,
  "pending_assignment_count": 5,
  "overdue_assignment_count": 1,
  "due_soon_assignments": [
    {
      "assignment_id": "asg_xxx",
      "title": "第一章习题",
      "deadline": "2026-09-20T23:59:59+08:00",
      "status": "published",
      "class_id": "cg_xxx",
      "class_name": "演示-计科1班",
      "course_id": "c_xxx",
      "course_name": "演示课程-高等数学(上)",
      "submission_id": null,
      "submission_status": null
    }
  ],
  "recent_announcements": [
    {
      "announcement_id": "ann_xxx",
      "title": "开学第一周课程安排",
      "published_at": "...",
      "require_read": true,
      "class_id": "cg_xxx",
      "class_name": "演示-计科1班",
      "course_id": "c_xxx",
      "course_name": "演示课程-高等数学(上)",
      "read_at": null
    }
  ]
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `enrolled_course_count` | int | 已加入课程数 |
| `unread_announcement_count` | int | 未读通知数 |
| `pending_assignment_count` | int | 待提交任务数 |
| `overdue_assignment_count` | int | 已逾期任务数 |
| `due_soon_assignments` | dict[] | 未来 7 天到期的任务(最多 5 条) |
| `recent_announcements` | dict[] | 最近 5 条已发布通知 |

> 一次返回所有摘要,前端无需连续请求十几个接口。

---

## 8. AI 导员上下文融合

### `POST /api/v1/counselor/chat` — 增强版

在 [`api_contract.md`](./api_contract.md) 已有 schema 基础上,新增 4 个可选上下文字段:

```json
{
  "message": "这个任务要交什么?",
  "conversation_id": "conv_xxx",
  "recent_tasks": [],
  "stream": true,
  "course_id": "c_xxx",
  "class_id": "cg_xxx",
  "assignment_id": "asg_xxx",
  "announcement_id": "ann_xxx"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `course_id` | string | 否 | 课程 ID(须有权限) |
| `class_id` | string | 否 | 班级 ID(须有权限) |
| `assignment_id` | string | 否 | 任务 ID(须有权限) |
| `announcement_id` | string | 否 | 通知 ID(须有权限) |

### 上下文权限校验(后端真实执行)

- **匿名访问**: 仍可调用(仅使用通用知识库),但**不得携带任何上下文字段**;
  携带上下文字段时必须携带有效 access token,否则返回 `403 FORBIDDEN`。
- **学生**: 必须已加入对应班级;只能引用已发布的任务/通知;草稿不可见。
- **教师**: 必须为对应课程的负责教师。
- **管理员**: 任意。

### 上下文注入

后端把当前用户有权限访问的 `course/class/assignment/announcement` 元数据
拼成隐式 prompt 前缀,注入到 RAG 检索源中,客户端不可见。

例如学生问"这个任务要交什么?"时:

1. 优先使用教师发布的任务原文(`assignment.description`、`deadline`、`max_score`)。
2. 其次使用课程资料和学校知识库。
3. 返回来源(`sources` 数组)。
4. **无依据时拒答**,返回"建议咨询辅导员或相关负责老师"。

### 草稿隔离

教师未发布的草稿(draft)任务/通知**不得被学生检索**,
后端在权限校验阶段返回 `404 ASSIGNMENT_NOT_FOUND`(不暴露存在性)。

---

## RBAC 权限矩阵

### 角色

| 角色 | 说明 |
|------|------|
| `student` | 学生 — 只能访问自己加入的班级内容 |
| `teacher` | 教师 — 管理自己负责的课程/班级 |
| `admin` | 管理员 — 管理用户、课程、班级 |

### 资源权限矩阵

| 资源 / 操作 | 学生 | 教师 | 管理员 |
|------|------|------|------|
| 创建课程 | ❌ | ✅(自动成为 teacher_id) | ✅ |
| 查看课程列表 | ✅ 仅已加入课程 | ✅ 仅自己课程 | ✅ 全部 |
| 更新课程 | ❌ | ✅ 仅自己课程 | ✅ |
| 在课程下创建班级 | ❌ | ✅ 仅自己课程 | ✅ |
| 查看班级 | ✅ 仅已加入班级 | ✅ 仅自己课程下 | ✅ 全部 |
| 更新班级 | ❌ | ✅ 仅自己班级 | ✅ |
| 加入班级(凭邀请码) | ✅ | ❌(教师自动加入) | ✅ |
| 重置邀请码 | ❌ | ✅ 仅自己班级 | ✅ |
| 查看班级成员 | ✅ 仅同班同学 | ✅ 自己班级 | ✅ 全部 |
| 移除成员 | ❌ | ✅ 仅自己班级 | ✅ |
| 创建通知/任务 | ❌ | ✅ 仅自己班级 | ✅ |
| 查看通知/任务列表 | ✅ 仅 published | ✅ 含草稿 | ✅ 全部 |
| 发布/关闭通知/任务 | ❌ | ✅ 仅作者本人 | ✅ |
| 标记已读 | ✅ 仅自己 | (教师不需要) | (管理员不需要) |
| 已读统计 / 任务统计 / 学生状态 | ❌ | ✅ 仅自己班级 | ✅ |
| 创建提交 | ✅ 仅自己 | ❌ | ❌ |
| 修改/提交/上传附件 | ✅ 仅自己 | ❌ | ❌ |
| 查看提交详情 | ✅ 仅自己 | ✅ 自己班级 | ✅ 任意 |
| 评分 | ❌ | ✅ 仅自己班级 | ✅ |
| 教师工作台 | ❌ | ✅ | ✅(返回空摘要) |
| 学生工作台 | ✅ | ❌ | ✅(返回空摘要) |
| AI 导员上下文 | ✅ 已加入班级 | ✅ 自己课程 | ✅ 任意 |

### 教师可见的学生信息边界

教师**只能查看**与教学和任务协同直接相关的信息:

| 允许查看 | 禁止查看 |
|------|------|
| 姓名 / 学号 | 学生私人 AI 对话 |
| 学院 / 专业 / 年级 | 私人待办 |
| 所属班级 | 个人学习陪伴记录 |
| 通知已读状态 | 摄像头画面 |
| 任务提交状态 | 表情识别结果 |
| 提交时间 / 是否逾期 | 与当前课程无关的信息 |
| 成绩 / 教师评论 | 密码 / token |
| 当前课程中的完成率 | |

> 已增加权限测试,证明教师无法跨课程读取学生数据(见
> [`test_multi_role_submissions.py::test_counselor_with_other_teacher_course_forbidden`](../backend/tests/test_multi_role_submissions.py))。

### 客户端不得绕过

- 后端**真实执行 RBAC**,不依赖 Flutter 页面隐藏实现权限控制。
- 客户端提交的 `role` 字段**不被信任**(role 来自 JWT,登录时由后端签发)。
- 任何越权请求返回 `403 FORBIDDEN` 或 `404 *_NOT_FOUND`(不暴露存在性)。

---

## 数据模型

### 实体清单

| 实体 | 表名 | 说明 |
|------|------|------|
| User | `users` | 用户(student/teacher/admin) |
| RefreshToken | `refresh_tokens` | refresh token 哈希(可撤销) |
| Course | `courses` | 课程 |
| ClassGroup | `class_groups` | 班级 |
| Enrollment | `enrollments` | 选课记录(student/teaching_assistant) |
| Announcement | `announcements` | 通知 |
| AnnouncementReadReceipt | `announcement_read_receipts` | 已读回执 |
| Assignment | `assignments` | 任务 |
| Submission | `submissions` | 学生提交 |
| SubmissionAttachment | `submission_attachments` | 提交附件 |

### 关键约束

- `users.username` 唯一
- `users.student_number` 非空时唯一(部分唯一索引)
- `users.teacher_number` 非空时唯一(部分唯一索引)
- `class_groups.invite_code` 全局唯一
- `enrollments` 对 `(class_group_id, user_id)` 建唯一约束
- `announcement_read_receipts` 主键为 `(announcement_id, student_id)`
- `submissions` 对 `(assignment_id, student_id)` 建唯一约束
- `AssignmentStudentStatus` **不建立独立表**,通过聚合查询生成

### 索引

所有外键字段与高频查询字段均已建索引:

- `users.username`、`users.student_number`、`users.teacher_number`
- `courses.teacher_id`、`courses.status`
- `class_groups.course_id`
- `enrollments.class_group_id`、`enrollments.user_id`、`enrollments.status`
- `announcements.class_group_id`、`announcements.status`、`announcements.published_at`
- `announcement_read_receipts.announcement_id`、`announcement_read_receipts.student_id`
- `assignments.class_group_id`、`assignments.status`、`assignments.deadline`
- `submissions.assignment_id`、`submissions.student_id`、`submissions.status`
- `submission_attachments.submission_id`
- `refresh_tokens.user_id`、`refresh_tokens.token_hash`

---

## 数据库迁移

### 设计原则

1. **不删除或重建现有 `app.db`** — 验收数据与历史数据共存(dev/test)。
2. **不破坏已有知识库、通知抽取和 RAG 表** — 仅新增多角色表。
3. **沿用现有数据库封装和 Repository 风格** — [`sqlite_db.py`](../backend/app/database/sqlite_db.py) + [`multi_role_repository.py`](../backend/app/repositories/multi_role_repository.py)。
4. **轻量、幂等的 schema migration** — `_migrate()` 函数在 `_init_schema()` 末尾执行。
5. **应用重复启动不重复创建数据或破坏索引** — 全部 `CREATE TABLE IF NOT EXISTS` / `CREATE INDEX IF NOT EXISTS`。
6. **验收账号 seeding 也幂等** — [`demo_seeder.py`](../backend/app/services/demo_seeder.py) 按 (username/code/title) 去重,仅在 dev/test 显式启用。

### 迁移内容

#### 旧库兼容(`documents` 表)

- 检测 `documents` 表是否缺 `is_demo` 列
- 缺则 `ALTER TABLE documents ADD COLUMN is_demo INTEGER DEFAULT 0`
- 旧数据 `is_demo` 默认 0(用户导入资料;`is_demo=1` 仅用于 dev/test 显式导入的测试环境资料)
- 索引 `idx_documents_is_demo` 在迁移后创建(避免旧库无列时报 "no such column")

#### 多角色表

全部使用 `CREATE TABLE IF NOT EXISTS`,首次启动会创建 10 张表 + 全部索引;
重复启动不会破坏已有数据。

### 测试

- [`test_old_database_migration_adds_is_demo_column`](../backend/tests/test_multi_role_submissions.py): 模拟旧库(无 `is_demo` 列)→ 启动 Database → 验证列已补齐、旧数据 `is_demo=0`、多角色表已创建。
- [`test_database_init_idempotent`](../backend/tests/test_multi_role_submissions.py): 多次初始化不破坏数据。

---

## 附件安全

### 文件名校验

`sanitize_filename(name)` 在 [`security.py`](../backend/app/core/security.py):

1. 取 `Path(name).name` 去掉路径部分(`../../etc/passwd` → `passwd`)
2. 拒绝 `..`、`/`、`\` 残留
3. 必须匹配正则 `^[\w\u4e00-\u9fa5\-. ()（）\[\]【】、，]{1,200}$`
4. 含 shell 元字符(如 `;` `&` `|`)直接拒绝,返回 `400 FILE_NAME_UNSAFE`

### 扩展名白名单

```python
_ALLOWED_EXT = {
    "txt", "md", "pdf", "doc", "docx", "xls", "xlsx",
    "ppt", "pptx", "png", "jpg", "jpeg", "gif", "zip",
    "py", "cpp", "java", "c",
}
```

不在白名单的扩展名返回 `415 ATTACHMENT_TYPE_NOT_ALLOWED`。

### 大小限制

- 单文件 ≤ 10 MB(`_MAX_SIZE_BYTES = 10 * 1024 * 1024`)
- 空文件拒绝

### 路径穿越二次防御

存储路径 `./data/submission_attachments/<submission_id>/<uuid>_<safe_name>`,
写入前再次调用 `is_path_traversal(storage_path, base_dir)` 校验绝对路径仍在 `base_dir` 之内。

### 附件列表不返回文件内容

`AttachmentOut` 仅含元数据(`original_filename`、`size_bytes`、`mime_type` 等),
不返回文件内容;附件下载接口后续扩展。

---

## 性能策略

### 目标测试规模

| 维度 | 规模 |
|------|------|
| 课程 | 100 |
| 班级 | 300 |
| 学生/班 | 100 |
| 任务 | 1000 |
| 提交状态 + 已读记录 | 100,000 |

### 优化策略

1. **所有长列表分页** — `page` + `page_size`,默认 20,最大 100~500。
2. **搜索支持 query 参数** — `query`、`status`、`member_role` 等过滤。
3. **教师统计使用聚合 SQL** — `COUNT(*)` / `GROUP BY` / `LEFT JOIN`,不允许逐个学生循环查询。
4. **避免 N+1 查询** — `student-status` / `list_submissions` 通过 `JOIN` 一次取出学生信息。
5. **student-status 支持分页、状态筛选和姓名/学号搜索** — `submission_status` / `read_status` / `query`。
6. **dashboard 接口一次返回必要摘要** — 教师工作台 8 个聚合字段 + recent_assignments,学生工作台 6 个字段 + due_soon + recent_announcements,前端无需连续请求十几个接口。
7. **附件列表不返回文件内容** — `AttachmentOut` 仅元数据。
8. **事务批量写入** — `enroll` / `mark_read` / `upsert_submission` 均在单事务中完成。
9. **SQLite 写操作避免长时间持锁** — 文件模式启用 WAL,短超时 30s;`_release` 及时关闭连接。
10. **重复请求和并发提交不产生重复数据** — `UNIQUE(class_group_id, user_id)` / `UNIQUE(announcement_id, student_id)` / `UNIQUE(assignment_id, student_id)` 约束 + upsert 语义。

### 测试耗时

- 84 个多角色测试约 60 秒完成(含 84 个测试用例 + 验收账号 seeding)。
- 全部 209 个 pytest 测试(含 13 个正式 Release 强约束测试)约 110 秒。
- 检索评测 44 条样例平均 0.12 ms / 条。
- 不虚构线上性能数据。

---

## 错误码

新增错误码(在 [`api_contract.md`](./api_contract.md) 已有基础上):

| HTTP | code | 触发场景 |
|------|------|----------|
| 401 | `UNAUTHORIZED` | 未认证或认证已失效 |
| 401 | `INVALID_CREDENTIALS` | 用户名或密码错误 |
| 403 | `FORBIDDEN` | 无权访问该资源 |
| 404 | `USER_NOT_FOUND` | 用户不存在 |
| 404 | `COURSE_NOT_FOUND` | 课程不存在 |
| 404 | `CLASS_GROUP_NOT_FOUND` | 班级不存在 |
| 404 | `ANNOUNCEMENT_NOT_FOUND` | 通知不存在 |
| 404 | `ASSIGNMENT_NOT_FOUND` | 任务不存在 |
| 404 | `SUBMISSION_NOT_FOUND` | 提交不存在 |
| 404 | `INVALID_INVITE_CODE` | 邀请码无效或班级不存在 |
| 409 | `USERNAME_EXISTS` | 用户名已被占用 |
| 409 | `STUDENT_NUMBER_EXISTS` | 学号已被占用 |
| 409 | `TEACHER_NUMBER_EXISTS` | 工号已被占用 |
| 409 | `ALREADY_ENROLLED` | 该学生已加入此班级 |
| 409 | `CLASS_GROUP_FULL` | 班级已满员 |
| 409 | `ASSIGNMENT_CLOSED` | 任务已截止提交 |
| 409 | `RESUBMIT_NOT_ALLOWED` | 该任务不允许重新提交 |
| 409 | `INVALID_TRANSITION` | 状态转换不被允许(如 draft → closed) |
| 413 | `ATTACHMENT_TOO_LARGE` | 附件过大 |
| 415 | `ATTACHMENT_TYPE_NOT_ALLOWED` | 附件类型不被允许 |

### 安全设计要点

- 登录失败统一返回 `401 INVALID_CREDENTIALS`,**不泄露用户名是否存在**。
- 越权访问资源时,若资源存在性敏感,返回 `404 *_NOT_FOUND` 而非 `403 FORBIDDEN`。
- 不在日志中记录 token 或密码明文。
- 不在错误响应中泄露密码是否正确。

---

## 当前限制

### 已实现

- ✅ JWT access + refresh token 认证
- ✅ RBAC(student/teacher/admin)
- ✅ 课程/班级/通知/任务/提交 全 CRUD + 状态机
- ✅ 教师工作台 + 学生工作台(聚合 SQL,数字与数据库真实状态一致)
- ✅ 任务统计与学生状态(分页 + 筛选 + 搜索)
- ✅ 附件上传(安全校验)
- ✅ AI 导员上下文融合(权限校验 + 草稿隔离)
- ✅ 数据库迁移(旧库兼容 + 幂等)
- ✅ 验收账号 seeding(幂等,仅 dev/test 显式启用)
- ✅ 84 个多角色测试(覆盖所有要求场景)
- ✅ 13 个正式 Release 强约束测试(证明 production 无法启用 Mock 业务开关)

### 未实现 / 后续扩展

- ❌ 用户注册接口(生产应由管理员通过真实业务流程创建用户)
- ❌ 附件下载接口(当前仅上传 + 列表)
- ❌ 教师工作台 `recent_activity`(当前为空数组,后续可扩展为评分/发布时间线)
- ❌ 任务提醒推送(后端不发送推送,由客户端轮询 dashboard 或后续接入 FCM/APNs)
- ❌ 任务同步为个人待办(此为 Flutter 端逻辑,后端已暴露任务数据,客户端可调用
  `/api/v1/assignments/{id}` 拉取后本地创建待办)
- ❌ 用户头像上传(当前 `avatar_url` 字段预留,无上传接口)
- ❌ 管理员运营后台(当前 admin 仅能管理用户/课程/班级,无复杂运营功能)
- ❌ PostgreSQL 迁移(当前仍为 SQLite,所有 SQL 已使用标准方言,迁移成本较低)
- ❌ 任务/通知的"班级范围"分发(当前按 `class_group_id` 分发,跨班级分发需多次创建)
- ❌ 任务截止时间到期的自动 `closed` 转换(需后端定时任务,当前由教师手动关闭)
- ❌ SSE 流式通知推送(当前通知为拉取模式,后续可扩展为 SSE 推送)

---

## 与 Flutter 客户端协作

### Flutter Agent 需要的接口字段

Flutter 客户端在 [`lib/data/services/api/api_multi_role_services.dart`](../lib/data/services/api/api_multi_role_services.dart)
等文件中已实现 API 调用。后端保证以下字段稳定:

- `TokenPair`: `access_token` / `refresh_token` / `token_type` / `expires_in`
- `UserPublic`: `id` / `username` / `role` / `display_name` / `student_number` /
  `teacher_number` / `college` / `major` / `grade` / `avatar_url` / `is_active`
- `Page`: `items` / `total` / `page` / `page_size` / `has_more`
- `CourseOut`: 见 [课程](#2-课程-courses)
- `ClassOut`: 含 `invite_code`
- `AnnouncementOut`: 含 `has_read`(学生视角)
- `AssignmentOut`: 含 `submission_types` / `allow_resubmit`
- `SubmissionOut`: 含 `attachments` 数组
- `AttachmentOut`: 不含文件内容
- `StudentStatusItem`: 教师视角学生状态
- `TeacherDashboard` / `StudentDashboard`: 一次返回全部摘要字段

### 字段命名约定

- 后端使用 `snake_case`(如 `class_group_id`、`teacher_id`)
- Flutter 客户端通过 [`snake_case_adapter.dart`](../lib/data/services/api/snake_case_adapter.dart)
  自动转换为 Dart 的 `camelCase`
- 时间字段统一为 ISO 8601 字符串

### 鉴权流程

1. Flutter 启动时检查本地 `token_storage` 是否有有效 token
2. 无 → 跳转登录页 → `POST /auth/login` → 保存 token
3. 有 → `GET /auth/me` 验证 → 失败则 `POST /auth/refresh`
4. refresh 失败 → 跳转登录页
5. 所有 API 请求通过 [`auth_interceptor.dart`](../lib/data/services/api/auth_interceptor.dart)
   自动附加 `Authorization: Bearer <token>` 头

---

## 与已有 AI 能力的融合

### 通知抽取

教师创建通知或任务时,可调用已有的:

```
POST /api/v1/notices/extract
```

将长通知结构化为:标题、截止时间、材料、地点、多任务拆分建议。
详见 [`api_contract.md`](./api_contract.md) §2。

### AI 导员上下文

`POST /api/v1/counselor/chat` 新增 4 个可选上下文字段,详见
[§8 AI 导员上下文融合](#8-ai-导员上下文融合)。

### 知识库

学校知识库与多角色数据完全解耦,仍通过 `/api/v1/knowledge/*` 接口管理。
AI 导员在引用上下文时,优先级为:

1. 教师发布的任务/通知原文(权限校验后注入)
2. 课程资料(后续扩展:课程关联的知识库文档)
3. 学校知识库(全局共享)

---

## 相关文档

- [`api_contract.md`](./api_contract.md) — 单学生助手接口(健康/通知抽取/知识库/AI 导员)
- [`current_capabilities.md`](./current_capabilities.md) — 当前能力总览
- [`knowledge_base_guide.md`](./knowledge_base_guide.md) — 知识库使用指南
- [`retrieval_evaluation.md`](./retrieval_evaluation.md) — 检索评测说明
- [`backend/README.md`](../backend/README.md) — 后端 README
- [`backend/app/schemas/multi_role.py`](../backend/app/schemas/multi_role.py) — Pydantic 模型源码
- [`backend/app/api/routes/`](../backend/app/api/routes/) — 路由源码
- [`backend/tests/test_multi_role_*.py`](../backend/tests/) — 测试源码
