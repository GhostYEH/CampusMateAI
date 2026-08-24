# 教务系统应用内验证代理 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 以河南财经政法大学正方 JWGLXT 为真实金样，完成图片验证码前端化、三端应用内复杂验证、安全会话恢复和真实教务数据同步。

**Architecture:** 后端 Verification Broker 统一生成并验证图片或交互挑战；图片挑战返回原始字节，普通 Web 的复杂挑战使用隔离短时浏览器，Android/Harmony 使用内嵌 WebView。登录成功后的完整 Cookie Jar 由加密会话存储持有，客户端只操作连接状态。

**Tech Stack:** FastAPI, Pydantic, SQLite, httpx, cryptography, pytest, Vue 3/Vite, WebSocket, Kotlin/Compose/WebView, ArkTS/ArkWeb.

**Spec:** `docs/superpowers/specs/2026-08-24-edu-verification-broker-design.md`

## Global Constraints

- 构建、测试和运行 Android/Harmony 命令使用项目捆绑 JDK 21.0.12+8。
- 真实教务账号密码不得写入源码、测试、配置、文档、数据库或日志。
- 不自动识别图片验证码，不自动求解或绕过滑块、短信和 MFA。
- 学校 URL 与数据端点必须有真实页面或登录后网络证据，不得猜测。
- 保留工作区现有用户改动，只修改本计划涉及文件。
- 每个切片先写失败测试，确认红灯后做最小实现并运行相关测试。

---

### Task 1: 保留验证码原始字节

**Files:**
- Modify: `backend/app/services/edu/adapters/zhengfang_http.py`
- Modify: `backend/app/services/edu/adapters/zhengfang.py`
- Test: `backend/tests/test_zhengfang_adapter.py`

**Interfaces:** `HttpResponse.content: bytes`；`prepare_login` 返回 `captcha_image_base64` 与 `captcha_mime_type`。

- [ ] 写入二进制 PNG 经 HTTP 包装和 Base64 后逐字节一致的失败测试。
- [ ] 运行定向测试并确认当前文本重编码实现失败。
- [ ] 为 `HttpResponse` 增加原始内容和安全 Content-Type 读取。
- [ ] 使用原始字节生成 Base64，并限制图片类型与大小。
- [ ] 运行正方适配器测试。

### Task 2: 建立显式挑战分流和令牌所有权

**Files:**
- Modify: `backend/app/services/edu/session.py`
- Modify: `backend/app/services/edu/connector.py`
- Modify: `backend/app/schemas/edu.py`
- Modify: `backend/app/api/routes/edu.py`
- Test: `backend/tests/test_edu_connector.py`
- Test: `backend/tests/test_edu_security.py`

**Interfaces:** `challenge_type`、`captcha_mime_type`、`verification_session_id`；令牌绑定 user/connection 并单次消费。

- [ ] 写入图片验证码仍选择 backend challenge、跨连接令牌拒绝、过期和重放失败测试。
- [ ] 运行测试确认红灯。
- [ ] 将图片与交互挑战分类从 `suggested_login_mode` 中拆开。
- [ ] 验证预登录会话 user_id、connection_id，提交后原子消费。
- [ ] 扩展兼容 API 契约并保持旧客户端可用。
- [ ] 运行连接器与安全测试。

### Task 3: 河南财经政法大学正方金样配置

**Files:**
- Modify: `backend/app/services/edu/adapters/zhengfang_strategy.py`
- Modify: `backend/app/services/edu/adapters/zhengfang.py`
- Modify: `backend/app/services/edu/provider_detector.py`
- Test: `backend/tests/fixtures/edu/`（只保存脱敏公开响应）
- Test: `backend/tests/test_zhengfang_adapter.py`

**Interfaces:** 显式 login/captcha/public-key 路径和允许 origin；数据端点只在真实证据确认后加入。

- [ ] 保存脱敏公开登录页与脚本协议 fixture。
- [ ] 写入 HUEL 字段、验证码路径和公钥路径解析失败测试。
- [ ] 增加学校配置并运行测试。
- [ ] 使用短时输入执行一次预登录和最小错误登录，确认验证码协议。
- [ ] 使用真实登录会话确认认证探测和数据端点；立即清理临时输入。
- [ ] 为确认的课表、成绩、考试协议增加脱敏 fixture 测试。

### Task 4: 完整 Cookie Jar 和客户端兼容

**Files:**
- Modify: `backend/app/services/edu/adapters/zhengfang_http.py`
- Modify: `backend/app/services/edu/adapters/zhengfang.py`
- Modify: `backend/app/schemas/edu.py`
- Modify: `android/app/src/main/java/com/example/campusai/data/remote/ApiService.kt`
- Modify: `android/app/src/main/java/com/example/campusai/ui/screens/profile/EduLoginScreen.kt`
- Modify: `harmony/entry/src/main/ets/data/ApiClient.ets`
- Modify: `harmony/entry/src/main/ets/features/edu/EduLoginPage.ets`
- Test: backend/Android/Harmony 对应测试

**Interfaces:** 结构化 Cookie DTO，兼容旧 `dict`；实际 User-Agent 参与后端会话。

- [ ] 写同名跨域 Cookie 不丢失的后端失败测试。
- [ ] 实现结构化 Cookie Jar 和兼容转换。
- [ ] Android/Harmony 增加 origin 限制、资源释放与账号切换清理。
- [ ] 增加客户端纯逻辑测试并运行相关构建。

### Task 5: 加密可恢复教务会话

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/database/sqlite_db.py`
- Create: `backend/app/services/edu/encrypted_session_store.py`
- Modify: `backend/app/services/container.py`
- Test: `backend/tests/test_edu_security.py`
- Test: `backend/tests/test_edu_connector.py`

**Interfaces:** `EduSessionStore` 保持不变；生产使用 AES-GCM 密文存储，测试可显式选择内存实现。

- [ ] 写重启恢复、密文不含 Cookie、篡改拒绝和生产缺密钥失败测试。
- [ ] 增加数据库表和配置校验。
- [ ] 实现版本化加密存储与过期清理。
- [ ] 接入容器并运行后端测试。

### Task 6: 普通浏览器交互验证运行时

**Files:**
- Create: `backend/app/services/edu/interactive_browser.py`
- Create: `backend/app/api/routes/edu_interactive.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/core/config.py`
- Test: `backend/tests/test_edu_interactive_browser.py`

**Interfaces:** 创建、状态、帧、输入、完成、取消 API；运行时缺失时明确返回 unavailable。

- [ ] 写 owner/origin/TTL/并发/输入范围失败测试。
- [ ] 实现默认关闭且 fail-closed 的会话管理器。
- [ ] 接入可选浏览器运行时、帧限速和安全输入分发。
- [ ] 登录成功后将浏览器 Cookie Jar 交给连接器。
- [ ] 运行交互运行时与安全测试。

### Task 7: Web 全屏验证工作区

**Files:**
- Create: `web/src/features/edu/verificationSession.js`
- Create: `web/src/components/edu/EduInteractiveVerification.vue`
- Modify: `web/src/services/studentApi.js`
- Modify: `web/src/views/student/StudentAcademicView.vue`
- Test: `web/src/features/edu/verificationSession.test.js`
- Modify: `web/package.json`

**Interfaces:** 图片 challenge 继续使用表单；interactive challenge 在同页全屏面板操作。

- [ ] 写状态转换、输入限速、取消和敏感数据不持久化测试。
- [ ] 实现 API/帧/输入控制器。
- [ ] 实现全屏验证面板、超时、重连、取消和无运行时说明。
- [ ] 接入现有连接状态机并运行 Web 测试与构建。

### Task 8: 三端数据同步闭环

**Files:**
- Modify: `backend/app/services/edu/adapters/zhengfang.py`
- Modify: `android/app/src/main/java/com/example/campusai/ui/screens/profile/EduViewModel.kt`
- Modify: `harmony/entry/src/main/ets/features/profile/EduSystemPage.ets`
- Modify: `web/src/views/student/StudentAcademicView.vue`
- Test: backend/Android/Harmony/Web 对应测试

**Interfaces:** 正方能力声明只包含已确认功能；连接后同步 profile/schedule/grade/exam 并显示每项结果。

- [ ] 写能力声明与三端同步状态失败测试。
- [ ] 接入已确认的同步类型和持久化读取。
- [ ] 对部分失败提供可重试结果，不把整体伪装为成功。
- [ ] 运行三端测试和构建。

### Task 9: 最终验证与安全复核

**Files:**
- Modify: `docs/superpowers/plans/2026-08-24-edu-verification-broker.md`（勾选证据）

- [ ] 后端执行全量 pytest 并记录通过数量。
- [ ] Web 执行全量测试和生产构建。
- [ ] 使用捆绑 JDK 验证 Android 单测和 Debug 编译。
- [ ] 若可用，执行 Harmony hvigor 测试与构建；否则明确记录环境阻塞。
- [ ] 对真实 HUEL 账号执行最少次数登录、验证码和数据同步验收。
- [ ] 搜索源码、日志和 Git diff，确认没有真实账号、密码、Cookie 或验证码残留。
- [ ] 复核 SSRF、会话重放、日志脱敏、限流和资源销毁。
