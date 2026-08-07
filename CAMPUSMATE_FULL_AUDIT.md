# CampusMateAI 全面代码体检报告

## 1. 项目总体情况
CampusMateAI 是一个包含多端（Android, Web, 微信小程序）和 Python FastAPI 后端的 monorepo 项目。目前代码库正处于从“多角色 LMS 平台”向“面向大学生个人使用的 AI 校园助手”转型的阶段。

## 2. 当前真实架构
*   **Backend**: FastAPI + SQLite + Pydantic，负责提供 API，并集成了大模型进行通知解析（RAG 和实体抽取）。
*   **Android**: Kotlin + Jetpack Compose，作为核心的学生端，包含了通知、待办、课程、专注学习（集成 LiteRT 本地面部表情识别）等模块。
*   **Web**: Vue 3 + Vite，目前主要包含了大量的管理员和教师功能页面。
*   **WeChat MiniProgram**: 微信小程序，作为一个轻量级的入口，包含了首页、课程、待办、导员等基本功能。

## 3. 当前产品定位与代码实际定位的偏差
*   **目标定位**: 纯粹面向学生的 AI 个人校园助手，聚合多方数据，提供日程管理和学习辅助。
*   **代码现状**: 仍残留大量传统 LMS（学习管理系统）的影子。存在清晰的 `admin`、`teacher` 角色定义，后端的 `classes`、`submissions` 路由，以及前端复杂的管理后台逻辑。

## 4. 教师端/LMS遗留功能
**A. 应彻底删除的教师/LMS功能**
*   `backend/app/api/routes/admin_*.py`: 所有的管理员专属路由。
*   `backend/app/api/routes/classes.py`: 班级管理功能，个人助手不需要管理教学班。
*   `backend/app/api/routes/submissions.py`: 作业提交和批改逻辑，个人助手只关心作业的“待办”状态，不负责提交批改闭环。
*   `backend/app/schemas/admin.py`, `backend/app/schemas/multi_role.py` 中的管理员和教师角色定义。
*   `web/src/views/admin/` 下的所有 Vue 页面：这些纯粹是系统后台。
*   `android/app/src/main/java/com/example/campusai/ui/screens/admin/AdminSystemScreen.kt`: Android 端的管理员界面。
*   `android/app/src/main/java/com/example/campusai/ui/screens/profile/TeachersViewModel.kt`: 获取教师列表的功能。

**B. 应保留但改变含义的功能**
*   **Course (课程)**: `backend/app/api/routes/courses.py`。从“学校排课系统中的课程实体”转变为“学生个人课表中的一项”。
*   **Assignment (作业)**: 从“教师发布的作业要求”转变为“学生个人的学习任务（来源于学习通同步等）”。
*   **Announcement (通知)**: 建议与现有的 `Notice` 体系合并，统一作为“从各渠道收集到的通知信息”。

**C. 删除依赖问题**
*   **数据库初始化 (`demo_seeder.py`)**: 目前的测试数据严重依赖创建 admin 和 teacher 账号，并由他们发布课程和通知。删除后，需重写 seeder，改为直接为学生生成模拟的同步数据。
*   **用户模型 (`User.kt`, `multi_role.py`)**: 如果移除 role 字段，所有依赖 `if (user.role == 'student')` 的权限校验代码都会报错，需要进行一次全局清理。

## 5. Android 学生端体检
*   **主要 Screen 梳理**:
    *   首页: `AppShell` 包含 Bottom Navigation。
    *   通知: 存在。
    *   待办: 存在 (`PersonalTask` 体系)。
    *   课程: 存在。
    *   学习/专注: `FocusScreen` (功能较完善，集成了本地 AI)。
    *   AI 导员: `Counselor` 聊天界面。
    *   我的: `AccountScreen`, `SettingsScreen`。
    *   *需清理*: `AdminSystemScreen`, `UsersScreen` 等管理后台入口。
*   **Navigation**: `AppNavHost.kt` 中仍有进入管理和教师页面的 route。
*   **登录体系**: `ApiService` 和 ViewModel 中尚未简化，后端 API 仍基于多角色返回不同的 Dashboard 数据。

## 6. 微信通知自动接入完整调用链
*   **完成度**: ⚠️ **部分实现 (约 40%)**
*   **调用链铁证追踪**:
    *   ✅ **服务注册**: `WeChatNoticeListenerService.kt` 继承了 `NotificationListenerService`，且 `AndroidManifest.xml` 中配置了 `BIND_NOTIFICATION_LISTENER_SERVICE`。
    *   ✅ **获取文本**: 在 `onNotificationPosted` 中成功获取了 `android.title` (群名) 和 `android.text` (消息内容)。
    *   ✅ **过滤逻辑**: 过滤了 `com.tencent.mm` 包名，且实现了基于 `appRepository.getMonitoredGroupChats()` 的白名单群聊过滤。
    *   ✅ **去重机制**: 实现了基于 SHA-256 和 5分钟有效期的简单内存去重 (`isDuplicate` 方法)。
    *   ❌ **断链点 (🐛 Bug / 未实现)**: `WeChatNoticeListenerService.kt` 的第 55 行调用了 `appRepository.ingestNotice(...)`。
        ```kotlin
        // AppRepository.kt (行 803)
        suspend fun ingestNotice(content: String, sourceName: String, publishedAt: String) {
            if (!_backendOnline.value || _mockMode.value) return // <-- 如果是 mock 模式直接返回了！
            try {
                ApiClient.api.ingestNotice(...)
            } catch (e: Exception) {
                println("Failed to ingest notice: ${e.message}") // <-- 异常被吞掉了，用户界面无感知
            }
        }
        ```
    *   **结论**: 虽然 Android 端的监听逻辑基本写完了，但由于默认处于 `mockMode`，导致上传逻辑被直接 `return` 拦截。即使非 Mock 模式，由于网络异常被吞，整个闭环非常脆弱。

## 7. 学习通接入完整调用链
*   **完成度**: ❌ **未实现 (仅有接口壳子, 0%)**
*   **调用链铁证追踪**:
    *   **接口存在**: 后端 `backend/app/api/routes/chaoxing.py` 定义了 `/api/v1/chaoxing/login` 和 `/api/v1/chaoxing/sync`。
    *   **假登录**: 查看 `ChaoxingClient.py` 第 13 行：
        ```python
        async def login(self, username: str, password: str) -> bool:
            # ...
            # 根本没有处理验证码、cookie 持久化，也没有真实请求学习通的 passport
            # 只是简单发了个 get，然后检查 status_code == 200
            return response.status_code == 200 and "status" in response.json() and response.json()["status"] == True
        ```
    *   **假数据同步**: 查看 `ChaoxingClient.py` 第 35 行 `get_courses`，它请求的是一个固定的、带时间戳的死链接 (`http://mooc2-ans.chaoxing.com/visit/courses/list?v=1652629452722...`)，没有任何真正的认证机制，且提取逻辑只写了注释 `# 从链接中提取 course_id 和 class_id`，并没有真正实现。
    *   **结论**: 学习通的同步完全是**未完成的 Demo**，无法抓取任何真实数据。

## 8. 通知 → AI → 待办闭环
*   **完成度**: ✅ **核心逻辑已实现 (约 80%)**
*   **调用链追踪**:
    *   后端 `notice_extraction_service.py` 中有 `extract_tasks_from_notice` 方法，调用了 LLM 客户端，并有明确的 Prompt 指导大模型提取 `tasks` 和 `deadline`。
    *   当 `POST /api/v1/notices` 创建通知时（如果从其他地方调用的前提下），可以选择触发解析，并写入 `PersonalTask`。
    *   Android 端有对应的 `PersonalTasks` 页面显示结果。
    *   *扣分项*：前端缺乏主动提交通知的入口（微信自动导入未闭环，手动输入未见明显入口）。

## 9. 课程与作业数据模型
*   **当前模型**: 存在严重的重叠。有 `Notice` 也有 `Announcement`，有 `PersonalTask` 也有 `Assignment`，还有 `Submission`。这正是 LMS 遗留造成的。
*   **新架构建议**:
    *   `User`: (无需 Role，均为学生)
    *   `Course`: 学生自己的课程表。
    *   `Source`: 数据来源（如：学习通、微信群、手动）。
    *   `Notice`: 统一的消息实体（绑定 Source）。
    *   `PersonalTask`: 统一的待办实体（可关联 Course 或 Notice）。

## 10. AI 导员
*   **完成度**: ✅ **逻辑完整 (约 90%)**
*   **调用链追踪**: `rag_service.py` 实现了非常严格和优秀的 RAG 逻辑。
    *   它**能够**读取用户的 `recent_tasks`（从 `PersonalTaskRepository` 获取）作为上下文。
    *   它有完善的 Prompt 限制大模型不编造学校规定。
    *   支持流式输出和降级策略。

## 11. 学习/专注模块
*   **完成度**: ✅ **功能真实且闭环 (约 90%)**
*   **分析**: `FocusScreen.kt` 和 `ExpressionSessionManager.kt` 表明，这是一个完全本地运行的（基于 CameraX 和 LiteRT）真实功能。它可以识别面部表情，统计专注时间，并生成摘要传给 AI 导员进行分析。这是完全符合“学生个人助手”定位的优质功能。

## 12. Web
*   **定位**: 目前 Web 端的路由 (`router.js`) 显示它是一个**大杂烩**。既有学生的视图，也有完整的 Admin 后台。
*   **建议**: 降级为单纯的后台管理工具（用于管理系统全局设置或配置），或者直接废弃，因为核心交互在 Android 端。

## 13. 微信小程序
*   **定位**: 从 `app.json` 来看，它是一个轻量级的学生端（包含课程、待办、导员）。
*   **建议**: 保留作为查询入口，功能上不需要像 Android 那么重（例如不需要专注模式的本地 AI 推理）。

## 14. API 前后端一致性
通过对比 `Android ApiService.kt` 与后端 `FastAPI routes`，发现严重的割裂现象：
*   **Android 端未使用的后端接口**：后端定义了大量的路由，例如 `admin_*.py`（管理员功能）、`classes.py`（班级管理）、`submissions.py`（作业批改），但 Android 端的 `ApiService.kt` 中**完全没有**调用这些接口。这再次印证了这些是 Web 端遗留的教师/管理功能。
*   **参数不一致的接口**：无明显参数不一致（Android 端主要调用了 `/notices`、`/tasks`、`/courses`、`/counselor/chat` 等，均能匹配上后端的定义）。
*   **总结**：后端接口比前端（Android）需求多出了一大截（约有 70 个路由，而 Android 只请求了 27 个）。多出来的部分应当在后续转型中全部废弃。

## 15. 数据库和数据模型
*   使用 SQLite，模型设计仍包含 LMS 遗迹。未发现明显的明文密码存储（使用了 `bcrypt` 哈希），但 `config.py` 中可能存在硬编码的默认密钥。

## 16. 隐私与安全问题
*   `backend/app/core/config.py` 中发现硬编码的 `SECRET_KEY = "super-secret-key-..."`，存在安全隐患。
*   微信通知监听由于尚未上传服务器，目前没有隐私泄露，但未来实现时需要极高的隐私保护策略。

## 17. Mock/TODO/死代码/重复代码
*   最大的 Mock 就是整个**学习通**的接入模块 (`ChaoxingClient.py`)。

## 18. 构建与测试情况
*   **Web**: 运行 `npm run build` 成功。
*   **Backend**: 运行 `pytest` 失败，出现 `ModuleNotFoundError: No module named 'app'` 错误，说明测试环境配置或 Python 路径设置有问题（`PYTHONPATH` 缺失）。
*   **Android**: 运行 `./gradlew assembleDebug` 失败，原因是 `JAVA_HOME` 配置不正确（指向了不存在的 JDK 26 目录）。

## 19. 各模块真实完成度评分
*   **Android 学生端**: 80% (界面完善，但包含冗余后台入口)
*   **微信通知自动导入**: 40% (仅有本地拦截，未上传后端解析)
*   **学习通同步**: 0% (纯 Mock 数据)
*   **通知系统**: 80% (后端逻辑好，前端接入弱)
*   **个人待办**: 85% (`PersonalTask` 逻辑清晰)
*   **课程系统**: 60% (受旧 LMS 逻辑干扰)
*   **AI 导员**: 95% (RAG 和上下文限制做得很好)
*   **专注学习**: 95% (本地 AI 识别已闭环)
*   **Web**: 50% (定位不清，冗余太多)
*   **后端**: 70% (核心逻辑好，但遗留路由太多)

## 20. P0/P1/P2/P3 问题列表
*   **P0 (必须立刻解决)**: 补全微信通知拦截后向后端发送的逻辑，打通自动导入闭环。
*   **P1 (核心功能问题)**: 学习通真实接口的调研与替换，移除现有的 Mock 代码。
*   **P2 (架构优化)**: 彻底清理后端和数据库中的 `admin`, `teacher`, `class`, `submission` 相关遗留代码和表结构。
*   **P3 (体验优化)**: 清理 Android 和 Web 端的无效导航入口。

## 21. 建议的新架构
*   前端：Android (核心) + 微信小程序 (轻量)。
*   后端：专注处理“数据同步 (Sync)”、“AI 提取 (Extract)”、“个人查询 (Query)”。
*   数据流：统一将外部数据转化为 `Notice` 或 `PersonalTask`。

## 22. 建议删除的文件/模块清单
*   `backend/app/api/routes/admin_*.py`
*   `backend/app/api/routes/classes.py`
*   `backend/app/api/routes/submissions.py`
*   `web/src/views/admin/` 目录下的所有文件

## 23. 建议保留并重构的文件/模块清单
*   `backend/app/api/routes/chaoxing.py` (需要重写真实业务)
*   `android/app/src/main/java/com/example/campusai/service/WeChatNotificationListener.kt` (需要添加网络请求)

## 24. 下一阶段开发顺序
1.  **清理战场**: 删除所有 P2 级别提到的 LMS 遗留代码。
2.  **打通核心闭环**: 完善 Android 微信通知上传功能。
3.  **攻坚痛点**: 研发真实的学习通数据抓取逻辑。