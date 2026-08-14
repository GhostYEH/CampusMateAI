# 学习通课程内容完整同步 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 同步学习通课程扩展信息、章节与只读内容元数据，并在 Web、Android、HarmonyOS 三端提供统一课程详情和安全的按需下载。

**Architecture:** 后端使用统一 `course_content_items` 模型保存不同类型的远程内容，以 `course_sync_sections` 表达每个栏目的完整性，以 `course_resource_cache` 管理按需下载缓存。三端只消费本地课程 API；学习通 Cookie、原始下载签名和跨域请求全部留在后端。

**Tech Stack:** FastAPI、SQLite、httpx、pytest、Vue 3/Vite、Kotlin/Jetpack Compose、ArkTS/ArkUI。

## Global Constraints

- 所有学习通功能只读，不代替用户提交、考试、签到、评论或上报学习进度。
- 不生成模拟课程内容；真实空列表、不可用和失败必须区分。
- 文件下载仅接受本地内容项 ID，并校验用户、课程、允许域名、重定向和大小限制。
- Web、Android、HarmonyOS 使用相同字段语义并沿用现有视觉组件。
- 保留工作区中既有用户改动，不修改与本功能无关的文件。

---

### Task 1: 持久化模型与仓库

**Files:**
- Modify: `backend/app/database/sqlite_db.py`
- Modify: `backend/app/models/multi_role.py`
- Modify: `backend/app/repositories/multi_role_repository.py`
- Test: `backend/tests/test_chaoxing_course_content.py`

**Interfaces:**
- Produces: `CourseContentItemRow`、`CourseSyncSectionRow`、`CourseContentRepository`，以及课程远程上下文字段。

- [ ] 写入失败测试：迁移后表与索引存在；不同用户的相同远程 ID 不冲突；重复 upsert 更新而不新增。
- [ ] 运行 `python -m pytest tests/test_chaoxing_course_content.py -q`，确认因模型缺失失败。
- [ ] 新增三张表、课程扩展列、行模型和仓库的 upsert/list/summary/section-status/cache 方法。
- [ ] 重跑测试，确认通过。

### Task 2: 学习通解析器与真实栏目探测

**Files:**
- Modify: `backend/app/services/chaoxing/ChaoxingClient.py`
- Test: `backend/tests/test_chaoxing_course_content.py`

**Interfaces:**
- Consumes: `course_id`、`clazz_id`、`cpi`。
- Produces: `get_course_chapters(context)`、`get_chapter_resources(context, chapter)`、`get_course_exams(context)`、`get_course_discussions(context)`、`get_course_materials(context)`，返回 `{status, items, error}`。

- [ ] 用脱敏的真实响应结构添加课程扩展字段、章节树和卡片资源解析失败测试。
- [ ] 运行目标测试，确认解析字段或方法缺失导致失败。
- [ ] 实现纯解析函数及只读请求方法，不调用任何进度上报或写操作接口。
- [ ] 对已绑定账号进行小规模只读探测，将不可用栏目返回 `unavailable`，结构变化返回 `failed`。
- [ ] 重跑目标测试和现有 `test_chaoxing.py`。

### Task 3: 同步服务与完整性状态

**Files:**
- Create: `backend/app/services/chaoxing/course_content_sync.py`
- Modify: `backend/app/services/container.py`
- Modify: `backend/app/api/routes/chaoxing.py`
- Test: `backend/tests/test_chaoxing_course_content.py`

**Interfaces:**
- Produces: `ChaoxingCourseContentSyncService.sync_course(user_id, course_id)` 和 `sync_all(user_id)`，返回逐栏目统计。

- [ ] 添加失败测试：单栏目失败保留旧数据、完整栏目将消失项标记 stale、重复同步幂等、用户隔离。
- [ ] 运行目标测试并确认按预期失败。
- [ ] 实现逐栏目独立事务、有限并发、状态写入和全局同步接线。
- [ ] 重跑测试并确认通过。

### Task 4: 课程内容 API 与下载代理缓存

**Files:**
- Create: `backend/app/schemas/course_content.py`
- Create: `backend/app/api/routes/course_content.py`
- Create: `backend/app/services/chaoxing/resource_proxy.py`
- Modify: `backend/app/api/router.py`
- Modify: `backend/app/core/config.py`
- Test: `backend/tests/test_chaoxing_course_content_api.py`

**Interfaces:**
- Produces: `GET content-summary`、`GET content`、`POST sync`、`GET resources/{item_id}/download`、`GET resources/{item_id}/open`。

- [ ] 添加 API 失败测试，覆盖课程权限、用户隔离、分页、栏目状态与缓存命中。
- [ ] 添加下载安全失败测试，覆盖任意 URL、非允许域名、跨域重定向、超限和缓存损坏。
- [ ] 运行目标测试，确认路由不存在而失败。
- [ ] 实现 schema、路由、流式代理、安全文件名、哈希缓存和稳定错误码。
- [ ] 重跑 API 测试与学习通后端测试。

### Task 5: Web 课程详情

**Files:**
- Modify: `web/src/services/studentApi.js`
- Modify: `web/src/views/student/StudentCourseDetailView.vue`
- Test: `web/tests/chaoxing-course-content.test.mjs`

**Interfaces:**
- Consumes: Task 4 API。
- Produces: 概览、章节、资料、作业、考试、通知、讨论和单课程刷新 UI。

- [ ] 添加失败测试，验证栏目、同步状态和代理下载链接由 API 数据驱动。
- [ ] 运行 `node --test tests/chaoxing-course-content.test.mjs`，确认失败。
- [ ] 沿用现有课程详情样式增加内容中心、展开章节和错误/空状态区分。
- [ ] 运行目标测试和 `npm run build`。

### Task 6: Android 原生课程详情

**Files:**
- Modify: `android/app/src/main/java/com/example/campusai/data/remote/ApiService.kt`
- Modify: `android/app/src/main/java/com/example/campusai/data/repository/AppRepository.kt`
- Modify: `android/app/src/main/java/com/example/campusai/ui/screens/courses/CoursesScreen.kt`
- Modify: `android/app/src/main/java/com/example/campusai/ui/screens/shell/AppShell.kt`
- Create: `android/app/src/main/java/com/example/campusai/ui/screens/courses/CourseDetailScreen.kt`
- Test: `android/app/src/test/java/com/example/campusai/data/remote/ChaoxingCourseContentContractTest.kt`

**Interfaces:**
- Consumes: Task 4 API。
- Produces: 课程列表到详情导航、栏目状态、展开章节、代理下载与学习通跳转。

- [ ] 添加 DTO/状态映射失败测试。
- [ ] 运行 Android 目标测试，确认类型缺失失败。
- [ ] 实现 DTO、仓库方法、详情目的地和 Compose 页面。
- [ ] 运行目标测试与 `:app:compileDebugKotlin`。

### Task 7: HarmonyOS 原生课程详情

**Files:**
- Modify: `harmony/entry/src/main/ets/data/ApiClient.ets`
- Modify: `harmony/entry/src/main/ets/features/courses/CoursesPage.ets`
- Create: `harmony/entry/src/main/ets/features/courses/CourseDetailPage.ets`
- Modify: `harmony/entry/src/main/ets/pages/Index.ets`

**Interfaces:**
- Consumes: Task 4 API。
- Produces: ArkUI 课程详情、栏目状态、折叠章节、下载和学习通 URI 跳转。

- [ ] 先在 ApiClient 增加明确的响应接口类型，并运行现有 HarmonyOS 静态检查确认调用尚缺失。
- [ ] 实现详情页面、路由状态和课程列表入口。
- [ ] 运行项目已有 HarmonyOS 构建或静态检查；若本机 SDK 不可用，记录精确阻塞并完成源码级校验。

### Task 8: 真实账号审计与全量回归

**Files:**
- Modify as required by failures only.

**Interfaces:**
- Verifies: 上游数据、数据库和三端 API 统计一致。

- [ ] 对已绑定账号运行一次只读课程内容同步，输出逐课程与逐栏目统计。
- [ ] 核对上游返回数量、数据库数量和 API 数量。
- [ ] 运行后端学习通测试、Web 构建、Android 编译和 HarmonyOS 可用检查。
- [ ] 运行 `git diff --check` 并检查只包含本功能的预期改动。
