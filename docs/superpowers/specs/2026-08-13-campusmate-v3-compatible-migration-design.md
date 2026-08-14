# CampusMateAI V3 Compatible Migration Design

## Product outcome

CampusMateAI 从“校园办事 + 学习 Demo”迁移为“大学身份 + 学业数据 + 校园社区 + AI 学习伴侣”。正式系统角色只有 student/admin；Android 是首要验收端，HarmonyOS 与 Web 共享同一 Backend 与数据模型。

## Chosen approach

采用兼容式纵向切片。每个切片先增加 Backend 模型、migration、API 和测试，再切换 Android，然后追平 HarmonyOS/Web，最后移除旧路由和死代码。这样既保护当前大量未提交工作，也避免先删除接口造成三端同时崩溃。

没有采用一次性 schema/UI 重写，因为当前仓库包含稳定的通知、RAG、学习陪伴、CameraX 和学习通同步；大爆炸会让回归来源不可追踪。也不采用 Android-only 快速版，因为 University scope、社区权限和教务凭证安全必须从 Backend 契约开始统一。

## Architecture

### University tenancy

`University` 是大学元数据与能力状态的唯一来源，`users.university_id` 可为空。ForumPost、ForumComment、LostFound、CampusActivity 等公共校园数据必须带 university_id。学生请求的 scope 从鉴权用户派生，不接受客户端任意覆盖；管理员接口可显式传 university_id。

### Community domain

Community 使用独立的 post/comment/like/favorite/report 表。帖子支持 published/hidden/deleted/under_review，评论最多两层展示。匿名帖子仍保存真实 author_id，仅序列化时隐藏身份。轻量限流、长度/URL/重复内容检查先于可选 AI moderation；管理员执行 hide/moderate/ban，普通用户不能控制治理逻辑。

### Academic domain

`AcademicProvider` 定义 authenticate、refresh_session、fetch_profile、fetch_courses、fetch_schedule、fetch_grades、fetch_exams。University 指定 provider key；没有真实可测 adapter 的学校返回 unsupported。`AcademicBinding` 独立于 User，响应中绝不包含密码或 credential_ref。客户端只提交一次性凭证，移动端/Web 不持久化密码。

### Client structure

三个端都遵循“我的大学 → 搜索 → 选择 → 确认”，并实现 Loading/Success/Empty/Error。Android 底部导航升级为首页/课程/社区/AI助手/我的，待办移动为首页和课程快捷入口；若现有导航回归风险超出阶段预算，则社区先作为首页一级入口并在 parity matrix 标记 PARTIAL。

Web 学生端移除办事大厅和教师端，加入课表、社区、大学与教务连接；Admin 增加大学管理、社区治理和举报管理。视觉继续使用现有白/浅灰蓝/淡紫、圆角、校园插画与柔和卡片，不另造设计系统。

## Data migration

SQLite migration 必须幂等并保留现有数据。新增表用 `CREATE TABLE IF NOT EXISTS`，新增列先检查 `PRAGMA table_info`。旧用户保持 nullable university_id；demo seed 绑定 Demo University。高风险教师/审批历史列本轮不 DROP，但运行时撤下相关路由。

## Error and privacy behavior

- 未选择大学：社区/失物/活动返回可识别的 university_required 错误，客户端显示选择入口。
- 未支持教务：展示“当前学校暂未支持自动教务同步”，不返回假课程。
- 认证过期/MFA/验证码：返回 expired、mfa_required、verification_required 或 unsupported，不绕过学校安全机制。
- 账户删除：撤销 binding/session/token；社区内容采用匿名化作者策略，个人失物内容删除。
- AI 仅使用当前大学的公开帖子摘要，不记录用户大学、学院、专业、年级的 prompt 明文日志。

## Testing

Backend 以 University isolation、ownership、admin moderation、binding ownership、no-password-response 和 migration idempotency 为核心。Android repository 测试覆盖大学、社区、教务和课表。每个 phase 运行相应单测、构建和 `git diff --stat`；最终运行 Backend pytest/compileall、Android JDK17 test/compile/assemble、Harmony 真 build 与 Web build。

## Scope decomposition

实施分为七个可独立验证的子计划：旧方向清理、University Core、Community、LostFound scope、Academic Integration、三端 parity、全量验证与文档。每个子计划完成后才能删除它替代的旧运行时能力。
