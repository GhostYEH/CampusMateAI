# CampusMate AI 后端 API 概览

> 版本: v1 · 统一前缀 `/api/v1` · 默认端口 `8000`
>
> 本文件是后端所有接口的简洁索引,详细字段、错误码与 SSE 事件格式以
> [`backend/app/schemas/`](../backend/app/schemas/) 中的 Pydantic 模型与
> [`backend/openapi.json`](../backend/openapi.json) 为准。
>
> Flutter 客户端实现位于 [`lib/data/services/api/`](../lib/data/services/api/),
> 字段命名通过 `snake_case_adapter.dart` 自动转换为 Dart `camelCase`。

---

## 通用约定

### Base URL

```
http://{host}:{port}/api/v1
```

- 本机调试: `http://localhost:8000/api/v1`
- Android 模拟器: `http://10.0.2.2:8000/api/v1`
- 真机(同 Wi-Fi): `http://192.168.x.x:8000/api/v1`

### 鉴权

- 学生助手接口(健康检查 / 通知抽取 / 知识库 / AI 导员匿名访问)**不强制 JWT**,默认共享同一知识库。
- 多角色协同接口(课程 / 班级 / 通知 / 任务 / 提交 / 工作台 / AI 导员上下文)**必须**携带 `Authorization: Bearer <access_token>`。
- SSE / EventSource 因浏览器不支持自定义 header,可在 query 中传 `?access_token=<token>`。

### 时间格式

ISO 8601 带时区,如 `2026-09-30T23:59:59+08:00`。后端不会静默丢失时区。

### 字符编码

UTF-8,SSE 中 JSON `ensure_ascii=False`。

### 请求体

- `POST` 接口统一 `application/json`
- 文件上传使用 `multipart/form-data`

### 响应体

- 成功: 直接返回业务 JSON,无外层包裹
- 失败: 统一错误结构 `{"code": "...", "message": "...", "details": null}`
- 列表: 统一分页结构 `{"items": [], "total": 0, "page": 1, "page_size": 20, "has_more": false}`

---

## 1. 健康检查 Health

| Method | Path | 鉴权 | 说明 |
|--------|------|------|------|
| GET | `/health` | 匿名 | 返回运行状态、知识库统计、LLM 可用性、版本号 |

关键字段: `status` / `mode`(`llm` / `rules_only` / `retrieval_only`) / `knowledge_base_initialized` / `document_count` / `chunk_count` / `llm_available` / `fallback_enabled` / `version`

---

## 2. 通知结构化抽取 Notices

| Method | Path | 鉴权 | 说明 |
|--------|------|------|------|
| POST | `/notices/extract` | 匿名 | 抽取通知原文中的标题/截止时间/材料/地点/面向对象 |

**请求体**: `{"content": "...", "published_at": "...", "source_name": "..."}`

**响应字段**:

| 字段 | 说明 |
|------|------|
| `title` / `task` | 通知标题与任务名 |
| `target_students` | 面向对象(如"2024级本科生") |
| `deadline` | ISO 8601 截止时间 |
| `materials[]` | 材料列表(`{id, name, required}`) |
| `submission_method` / `location` | 提交方式 / 办理地点 |
| `importance` | `urgent` / `important` / `normal` / `unknown` |
| `confidence` | 抽取置信度 0~1(仅结构化抽取置信度,不代表内容真实性) |
| `needs_confirmation` | 是否需人工确认(年份缺失/对象不明等) |
| `warnings[]` | 需确认的原因列表(温和提示) |
| `extractor_mode` | `llm` / `rules`(降级模式) |

**抽取规则**: LLM 优先,失败/超时自动降级到规则模式(正则 + 周表达 + 20+ 材料关键词 + 缺年份推断)。永不编造通知中不存在的材料。

---

## 3. 知识库 Knowledge

| Method | Path | 鉴权 | 说明 |
|--------|------|------|------|
| POST | `/knowledge/documents` | 匿名 | 上传文档(`multipart/form-data`,支持 `.md .txt .pdf .docx`) |
| GET | `/knowledge/documents` | 匿名 | 文档列表 |
| DELETE | `/knowledge/documents/{document_id}` | 匿名 | 删除文档(同步删除 chunks) |
| POST | `/knowledge/rebuild` | 匿名 | 重建 BM25 索引 |
| GET | `/knowledge/status` | 匿名 | 知识库状态 |

**DocumentSummary 字段**: `document_id` / `title` / `source_department` / `source_type` / `original_filename` / `content_hash` / `published_at` / `updated_at` / `effective_from` / `effective_to` / `version` / `applicable_students` / `is_official` / `is_expired`(基于 `effective_to` 自动计算) / `file_size` / `file_ext` / `imported_at`

**安全限制**: 单文件 ≤ 10 MB(`MAX_UPLOAD_MB`),文件名经 `sanitize_filename` 防路径穿越,空文件/重复内容(基于 SHA256)拒绝,扩展名白名单(`ALLOWED_EXTENSIONS`)。

**检索优先级**: 未过期 > 过期(+0.15) · 官方 > 非官方(+0.10) · 新鲜度 bonus(30 天内满额 +0.05,30~365 天线性衰减) · BM25 主体分(标题/小节加权 ×2) · 校园术语同义词对称扩展 · 短查询回退 · 多路召回。

---

## 4. AI 导员 Counselor

| Method | Path | 鉴权 | 说明 |
|--------|------|------|------|
| POST | `/counselor/chat` | 匿名或 JWT | RAG 问答,支持 SSE 流式与非流式 |

**请求体**: `{"message": "...", "conversation_id": "...", "recent_tasks": [], "stream": true, "course_id"?, "class_id"?, "assignment_id"?, "announcement_id"?}`

携带 `course_id` / `class_id` / `assignment_id` / `announcement_id` 任一字段时必须携带有效 access token,后端真实校验访问权限,草稿对学生不可见。

**响应 / `done` 事件**(`ChatFinalMeta`):

| 字段 | 说明 |
|------|------|
| `answer` | 完整回答 |
| `sources[]` | 引用来源(`{document_id, title, section, source_department, published_at, version, applicable_students, excerpt, relevance_score, is_official, is_expired}`) |
| `confidence` | 综合置信度 0~1 |
| `evidence_level` | `high` / `medium` / `low` / `none` |
| `needs_human_confirmation` | 是否建议人工复核 |
| `suggested_actions[]` | 建议操作(`{id, label, type, payload}`,type ∈ `navigate`/`prefillQuestion`/`createTask`/`none`) |
| `conversation_id` | 会话 ID |
| `mode` | `llm` / `retrieval_summary` / `no_knowledge` |
| `warnings[]` | 警告(冲突/降级等) |

**SSE 事件序列**: `sources`(一次) → `chunk`(多次,`{text, mode}`) → `done`(一次,完整 `ChatFinalMeta`) → 异常时 `error`(`{code, message}`)。

**回答规则(强制)**: 基于知识库 · 不编造 · 无依据返回"建议咨询辅导员"且 `sources=[]` · 冲突时展示两份来源并提示最新官方资料 · 过期资料降权但保留 `is_expired=true` 标记 · LLM 不可用启用检索摘要模式(`mode=retrieval_summary`) · 恶意 Prompt 通过系统消息约束不绕过。

---

## 5. 认证 Auth

| Method | Path | 鉴权 | 说明 |
|--------|------|------|------|
| POST | `/auth/login` | 匿名 | 用户名 + 密码登录,返回 `TokenPair` |
| POST | `/auth/refresh` | 匿名 | 用 refresh token 换发新 token 对(旧 token 撤销) |
| POST | `/auth/logout` | JWT | 撤销当前 refresh token |
| GET | `/auth/me` | JWT | 当前登录用户信息(`UserPublic`) |
| POST | `/auth/admin/users` | admin | 管理员创建用户(无演示专用通道) |

**TokenPair**: `access_token`(默认 30 分钟) / `refresh_token`(默认 14 天,数据库仅存 SHA-256 哈希) / `token_type=Bearer` / `expires_in`

**UserPublic**: `id` / `username` / `role`(`student` / `teacher` / `admin`) / `display_name` / `student_number` / `teacher_number` / `college` / `major` / `grade` / `avatar_url` / `is_active`

**安全**: 登录失败统一返回 `401 INVALID_CREDENTIALS`,不泄露用户名是否存在 · 密码 PBKDF2-HMAC-SHA256(100k 迭代 + 16 字节 salt) · 不记录密码或 token 明文。

---

## 6. 课程 Courses

| Method | Path | 鉴权 | 说明 |
|--------|------|------|------|
| GET | `/courses` | JWT | 课程列表(分页,支持 `query` / `status` 过滤) |
| POST | `/courses` | teacher / admin | 创建课程(`teacher_id` 自动设为当前用户) |
| GET | `/courses/{course_id}` | JWT(RBAC) | 课程详情 |
| PATCH | `/courses/{course_id}` | teacher(本人) / admin | 更新课程 |

**CourseOut**: `id` / `name` / `code` / `semester` / `description` / `teacher_id` / `teacher_name` / `status`(`draft` / `active` / `archived`) / `created_at` / `updated_at`

**权限**: 学生只看已加入班级所属课程 · 教师只看自己负责的课程 · 管理员看全部。

---

## 7. 班级 Classes

| Method | Path | 鉴权 | 说明 |
|--------|------|------|------|
| GET | `/classes` | JWT | 班级列表(支持 `course_id` 过滤) |
| POST | `/courses/{course_id}/classes` | teacher(本人) / admin | 创建班级(教师自动加入为 `teaching_assistant`) |
| GET / PATCH | `/classes/{class_id}` | JWT(RBAC) | 详情 / 更新 |
| POST | `/classes/{class_id}/join` | student / admin | 学生凭邀请码加入(邀请码须与 `class_id` 匹配) |
| POST | `/classes/{class_id}/reset-invite-code` | teacher / admin | 重置邀请码 |
| GET | `/classes/{class_id}/members` | JWT(RBAC) | 班级成员(分页 + `query` / `member_role` 过滤) |
| DELETE | `/classes/{class_id}/members/{user_id}` | teacher / admin | 移除成员(`status=removed`) |

**ClassOut**: `id` / `course_id` / `name` / `class_code` / `invite_code`(6 位,全局唯一) / `description` / `capacity` / `created_at` / `updated_at`

**ClassMemberOut**: `user_id` / `username` / `display_name` / `student_number` / `teacher_number` / `college` / `major` / `grade` / `avatar_url` / `role` / `enrollment_id` / `member_role`(`student` / `teaching_assistant`) / `status` / `joined_at`

---

## 8. 通知 Announcements

| Method | Path | 鉴权 | 说明 |
|--------|------|------|------|
| GET | `/classes/{class_id}/announcements` | JWT(RBAC) | 通知列表(学生强制 `status=published`) |
| POST | `/classes/{class_id}/announcements` | teacher / admin | 创建通知(默认 `draft`) |
| GET / PATCH | `/announcements/{announcement_id}` | JWT(RBAC) | 详情 / 更新 |
| POST | `/announcements/{announcement_id}/publish` | 作者 / admin | 发布(draft → published) |
| POST | `/announcements/{announcement_id}/read` | student | 标记已读(幂等) |
| GET | `/announcements/{announcement_id}/read-status` | teacher / admin | 已读统计 |

**AnnouncementOut**: `id` / `class_group_id` / `author_id` / `author_name` / `title` / `content` / `require_read` / `status`(`draft` / `published` / `archived`) / `published_at` / `created_at` / `updated_at` / `has_read`(学生视角 bool,教师/admin 为 null)

**ReadStatusOut**: `announcement_id` / `total_recipients` / `read_count` / `unread_count` / `receipts[]`(`{user_id, username, display_name, student_number, read_at}`)

---

## 9. 任务 Assignments

| Method | Path | 鉴权 | 说明 |
|--------|------|------|------|
| GET | `/classes/{class_id}/assignments` | JWT(RBAC) | 任务列表(学生强制 `status=published`) |
| POST | `/classes/{class_id}/assignments` | teacher / admin | 创建任务(默认 `draft`) |
| GET / PATCH | `/assignments/{assignment_id}` | JWT(RBAC) | 详情 / 更新 |
| POST | `/assignments/{assignment_id}/publish` | 作者 / admin | 发布任务 |
| POST | `/assignments/{assignment_id}/close` | 作者 / admin | 关闭任务(不再接受新提交) |
| GET | `/assignments/{assignment_id}/stats` | teacher / admin | 任务统计(单条聚合 SQL) |
| GET | `/assignments/{assignment_id}/student-status` | teacher / admin | 学生状态列表(分页 + `submission_status` / `read_status` / `query` 过滤) |

**AssignmentOut**: `id` / `class_group_id` / `author_id` / `author_name` / `title` / `description` / `deadline` / `submission_types[]` / `max_score` / `allow_resubmit` / `status`(`draft` / `published` / `closed` / `archived`) / `published_at` / `created_at` / `updated_at`

**AssignmentStatsOut**: `total_students` / `submitted` / `not_submitted` / `draft` / `late` / `graded` / `pending_grading` / `avg_score`(无评分时 null)

**StudentStatusItem**: `student_id` / `student_name` / `student_number` / `submission_id` / `submission_status`(`not_submitted` / `draft` / `submitted` / `resubmitted` / `late`) / `submitted_at` / `is_late` / `score` / `teacher_comment` / `read_status` / `read_at`

---

## 10. 提交 Submissions

| Method | Path | 鉴权 | 说明 |
|--------|------|------|------|
| GET | `/assignments/{assignment_id}/submissions` | teacher / admin | 提交列表(分页 + `status` 过滤,列表 `attachments` 恒为空数组) |
| POST | `/assignments/{assignment_id}/submissions` | student | 创建提交(`submit=false` 存草稿,`true` 直接提交) |
| GET / PATCH | `/submissions/{submission_id}` | JWT(RBAC) | 详情(含附件) / 学生更新文本 |
| POST | `/submissions/{submission_id}/submit` | student | 正式提交(草稿→submitted / 已交→resubmitted / 逾期→late) |
| POST | `/submissions/{submission_id}/attachments` | student(本人) | 上传附件(`multipart/form-data`) |
| GET | `/submissions/{submission_id}/attachments/{attachment_id}` | JWT(RBAC) | 下载附件(`FileResponse`,二进制流) |
| POST | `/submissions/{submission_id}/grade` | teacher(本班级) / admin | 教师评分 |

**SubmissionOut**: `id` / `assignment_id` / `student_id` / `student_name` / `student_number` / `college` / `major` / `grade` / `text_content` / `status` / `submitted_at` / `updated_at` / `score` / `teacher_comment` / `attachments[]`

**AttachmentOut**: `id` / `submission_id` / `original_filename` / `stored_filename` / `mime_type` / `size_bytes` / `created_at`

**附件安全**: 扩展名白名单 `txt md pdf doc docx xls xlsx ppt pptx png jpg jpeg gif zip py cpp java c` · 单文件 ≤ 10 MB · 文件名 `sanitize_filename` 防路径穿越 · 存储路径二次校验 `is_path_traversal` · 下载接口 `submission_id` 与 `attachment_id` 必须匹配。

---

## 11. 工作台 Dashboard

| Method | Path | 鉴权 | 说明 |
|--------|------|------|------|
| GET | `/dashboard/teacher` | teacher / admin | 教师工作台(admin 返回空摘要) |
| GET | `/dashboard/student` | student / admin | 学生工作台(admin 返回空摘要) |

**TeacherDashboard**: `course_count` / `class_count` / `student_count` / `active_assignment_count` / `pending_submission_count` / `unread_announcement_count` / `overdue_student_count` / `recent_assignments[]` / `recent_activity[]`(预留扩展,当前为空)

**StudentDashboard**: `enrolled_course_count` / `unread_announcement_count` / `pending_assignment_count` / `overdue_assignment_count` / `due_soon_assignments[]` / `recent_announcements[]`

全部聚合 SQL,无 N+1。一次返回所有摘要,前端无需连续请求十几个接口。

---

## RBAC 权限矩阵(简表)

| 资源 / 操作 | student | teacher | admin |
|------|------|------|------|
| 创建课程 / 班级 | ❌ | ✅(自己课程) | ✅ |
| 加入班级(凭邀请码) | ✅ | ❌(教师自动加入) | ✅ |
| 创建 / 发布通知 / 任务 | ❌ | ✅(自己班级) | ✅ |
| 标记通知已读 | ✅(自己) | — | — |
| 创建 / 修改 / 提交提交 | ✅(自己,只能自己) | ❌ | ❌ |
| 评分 / 评论 | ❌ | ✅(自己班级) | ✅ |
| 任务统计 / 学生状态 / 已读统计 | ❌ | ✅(自己班级) | ✅ |
| 教师工作台 | ❌ | ✅ | ✅(空摘要) |
| 学生工作台 | ✅ | ❌ | ✅(空摘要) |
| AI 导员上下文融合 | ✅(已加入班级) | ✅(自己课程) | ✅ |

**教师可见学生信息边界**: 允许查看 姓名 / 学号 / 学院 / 专业 / 年级 / 所属班级 / 通知已读状态 / 任务提交状态 / 提交时间 / 是否逾期 / 成绩 / 教师评论 / 当前课程完成率。**禁止**访问 学生私人 AI 对话 / 私人待办 / 学习陪伴记录 / 摄像头画面 / 表情识别结果 / 与当前课程无关的信息 / 密码 / token。

后端真实执行 RBAC,客户端 `role` 字段不被信任(来自 JWT)。越权请求返回 `403 FORBIDDEN` 或 `404 *_NOT_FOUND`(不暴露存在性)。

---

## 验收账号(dev/test 环境)

正式 Release 不提供任何"演示账号"或绕过认证的特殊账号。验收账号为**普通用户**,走完整真实业务流程(JWT 登录 / RBAC 校验 / 真实 SQL),不持有任何特殊权限或 Mock 数据开关。

启动时若 `AUTO_SEED_DEMO_USERS=true`(默认关闭;仅 dev/test 显式开启;production 下强制抛 ValidationError)会幂等 seed:

| 角色 | 用户名 | 密码 | 备注 |
|------|--------|------|------|
| 教师 | `teacher_demo` / `teacher_demo2` | `Demo123456` | 信息工程学院 / 外国语学院 |
| 学生 | `student_demo` / `student_demo_01` ~ `student_demo_30` | `Demo123456` | 31 名验收学生 |
| 管理员 | `admin_demo` | `Demo123456` | 管理员(验收) |

所有验收账号 `display_name` 含"(演示)"后缀。验收数据涵盖 3 门课程、4 个班级、6 条通知、8 个任务、若干提交与评分,覆盖已读/未读/已交/未交/逾期等不同状态。**正式生产环境中,验收账号应由管理员通过真实业务流程在数据库中创建。**

---

## 错误码

### 学生助手接口

| HTTP | code | 触发场景 |
|------|------|----------|
| 400 | `NOTICE_EMPTY` / `NOTICE_TOO_LONG` / `FILE_NAME_UNSAFE` / `EMPTY_QUESTION` | 输入校验失败 |
| 404 | `DOCUMENT_NOT_FOUND` / `NOT_FOUND` | 资源不存在 |
| 405 | `METHOD_NOT_ALLOWED` | HTTP 方法不允许 |
| 409 | `DOCUMENT_ALREADY_EXISTS` | 内容哈希重复 |
| 413 | `FILE_TOO_LARGE` | 文件 > 10 MB |
| 415 | `FILE_TYPE_NOT_ALLOWED` | 文件类型不在允许列表 |
| 422 | `NOTICE_UNPARSEABLE` / `VALIDATION_FAILED` | 文本无法识别为通知 / Pydantic 校验失败 |
| 500 | `INTERNAL_ERROR` | 未捕获异常(不暴露堆栈) |

### 多角色接口(新增)

| HTTP | code | 触发场景 |
|------|------|----------|
| 401 | `UNAUTHORIZED` / `INVALID_CREDENTIALS` | 未认证 / 凭证错误(不泄露用户名是否存在) |
| 403 | `FORBIDDEN` | 无权访问该资源 |
| 404 | `USER_NOT_FOUND` / `COURSE_NOT_FOUND` / `CLASS_GROUP_NOT_FOUND` / `ANNOUNCEMENT_NOT_FOUND` / `ASSIGNMENT_NOT_FOUND` / `SUBMISSION_NOT_FOUND` / `INVALID_INVITE_CODE` | 资源不存在(不暴露存在性) |
| 409 | `USERNAME_EXISTS` / `STUDENT_NUMBER_EXISTS` / `TEACHER_NUMBER_EXISTS` / `ALREADY_ENROLLED` / `CLASS_GROUP_FULL` / `ASSIGNMENT_CLOSED` / `RESUBMIT_NOT_ALLOWED` / `INVALID_TRANSITION` | 冲突 / 状态机非法 |
| 413 | `ATTACHMENT_TOO_LARGE` | 附件过大 |
| 415 | `ATTACHMENT_TYPE_NOT_ALLOWED` | 附件类型不被允许 |

> `KNOWLEDGE_BASE_EMPTY`(HTTP 200) 和 `LLM_UNAVAILABLE`(HTTP 200) **不是错误**,而是业务上的"无资料"/"降级"状态,通过响应体 `mode` / `evidence_level` 表达。

---

## 数据模型与数据库

实体清单: `users` / `refresh_tokens` / `courses` / `class_groups` / `enrollments` / `announcements` / `announcement_read_receipts` / `assignments` / `submissions` / `submission_attachments` / `documents` / `chunks`(知识库)。

**关键约束**: `users.username` 唯一 · `users.student_number` / `teacher_number` 非空时唯一(部分唯一索引) · `class_groups.invite_code` 全局唯一 · `enrollments` 对 `(class_group_id, user_id)` 唯一 · `announcement_read_receipts` 主键 `(announcement_id, student_id)` · `submissions` 对 `(assignment_id, student_id)` 唯一 · `AssignmentStudentStatus` 不建立独立表(聚合查询生成)。

**数据库迁移**: 不删除或重建现有 `app.db` · 不破坏已有知识库 / 通知抽取 / RAG 表 · 沿用现有 `sqlite_db.py` + `multi_role_repository.py` · 轻量幂等 schema migration(`_migrate()` 在 `_init_schema()` 末尾执行) · 全部 `CREATE TABLE IF NOT EXISTS` / `CREATE INDEX IF NOT EXISTS` · 旧库自动 `ALTER TABLE documents ADD COLUMN is_demo`。

**性能策略**: 所有长列表分页(默认 20,最大 100~500) · 教师统计使用聚合 SQL(`COUNT` / `GROUP BY` / `LEFT JOIN`,无 N+1) · `dashboard` 一次返回所有摘要 · 附件列表不返回文件内容 · 事务批量写入 · SQLite WAL 模式 · 唯一约束 + upsert 防重复。

---

## 字段命名约定

- 后端使用 `snake_case`(如 `class_group_id`、`teacher_id`)
- Flutter 客户端通过 [`snake_case_adapter.dart`](../lib/data/services/api/snake_case_adapter.dart) 自动转换为 Dart 的 `camelCase`
- 时间字段统一为 ISO 8601 字符串

---

## 当前限制

### 已实现

- ✅ JWT access + refresh token 认证 · RBAC(student/teacher/admin)
- ✅ 课程 / 班级 / 通知 / 任务 / 提交 全 CRUD + 状态机
- ✅ 教师工作台 + 学生工作台(聚合 SQL,数字与数据库真实状态一致)
- ✅ 任务统计与学生状态(分页 + 筛选 + 搜索)
- ✅ 附件上传与下载(安全校验 + 路径穿越二次防御)
- ✅ AI 导员上下文融合(权限校验 + 草稿隔离)
- ✅ 数据库迁移(旧库兼容 + 幂等)
- ✅ 验收账号 seeding(幂等,仅 dev/test 显式启用)
- ✅ 13 个正式 Release 强约束测试(证明 production 无法启用 Mock 业务开关)

### 未实现 / 后续扩展

- ❌ 用户注册接口(生产应由管理员通过真实业务流程创建用户)
- ❌ 教师工作台 `recent_activity`(当前为空数组,后续可扩展为评分/发布时间线)
- ❌ 任务提醒推送(由客户端轮询 dashboard 或后续接入 FCM/APNs)
- ❌ 用户头像上传(当前 `avatar_url` 字段预留,无上传接口)
- ❌ PostgreSQL 迁移(当前仍为 SQLite,所有 SQL 已使用标准方言)
- ❌ 任务/通知的跨班级分发(当前按 `class_group_id` 分发)
- ❌ 任务截止时间到期的自动 `closed` 转换(需后端定时任务)
- ❌ SSE 流式通知推送(当前为拉取模式)

---

## 相关文档

- [`backend/README.md`](../backend/README.md) — 后端 README
- [`docs/knowledge_base_guide.md`](./knowledge_base_guide.md) — 知识库使用指南(导入格式 / 冲突处理 / 过期文档)
- [`docs/reminder_guide.md`](./reminder_guide.md) — 本地提醒功能指南(Android 精确提醒)
- [`docs/retrieval_evaluation.md`](./retrieval_evaluation.md) — 检索评测指南
- [`docs/reports/2026-07-26-end-to-end-verification.md`](./reports/2026-07-26-end-to-end-verification.md) — 端到端验证报告
- [`docs/cnn/`](./cnn/) — CNN 训练与 LiteRT 部署文档
- [`backend/app/schemas/`](../backend/app/schemas/) — Pydantic 模型源码
- [`backend/app/api/routes/`](../backend/app/api/routes/) — 路由源码
- [`backend/tests/`](../backend/tests/) — 测试源码
