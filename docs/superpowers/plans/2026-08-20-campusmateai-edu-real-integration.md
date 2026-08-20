# CampusMateAI 教务系统真实接入专项 Implementation Plan

> **For agentic workers:** 按增量任务执行；每个任务先写回归测试并确认 RED，再做最小实现、确认 GREEN，然后提交独立 commit。

**Goal:** 在不扩展无关功能的前提下，把 EduConnection → Adapter → EduBinding → 同步链路修到可开始第一所正方 Golden School 真实联调的状态。

**Architecture:** EduSystem 只保存管理员/可信发现确认的公共配置；用户输入的未验证 URL 只属于自己的 EduConnection，并可作为 Discovery Candidate。连接状态机在创建时进入对应的等待状态，第一次真实凭据或 Cookie 提交就执行认证；认证成功后持久化完整 AdapterConfig，所有 Provider 操作复用同一配置和严格会话探针。

**Tech Stack:** FastAPI、SQLAlchemy、Pydantic、httpx、pytest；Android Kotlin/Gradle；HarmonyOS TypeScript；Web/WX TypeScript。

**Spec:** 用户提供的“教务系统真实接入专项核查 + 修复”要求（当前会话附件 `pasted-text.txt`）。

## Global Constraints

- 先找到代码、调用链和测试，再按 `CONFIRMED`、`PARTIALLY_CONFIRMED`、`NOT_PRESENT`、`ALREADY_FIXED` 判定；未确认的问题不得修改。
- 普通用户不可读取、推进、取消其他用户的 EduConnection，也不可覆盖公共 EduSystem 或连接到其他 university。
- backend_http 禁止后端访问校内网；client_webview 可用于校内网登录，但 Cookie 必须经真实登录探针验证。
- 不保存明文密码、真实 Cookie、真实账号或真实 Session；不绕过验证码/MFA；不为测试或生产失败降级 Mock。
- 不实现 Qiangzhi/Qingguo 全部功能，不做无关 UI 重构，不编造学校 URL。
- 任何“通过/完成”结论都必须有当前命令的退出码和测试输出作证。

---

### Task 1: 当前实现与跨端契约审计

**Files:**
- Inspect: `backend/app/services/edu/`, `backend/app/api/routes/edu.py`, `backend/app/models/edu.py`, `backend/app/schemas/edu.py`, `backend/app/repositories/edu_repository.py`, `backend/app/repositories/edu_data_repository.py`
- Inspect: `backend/tests/test_edu_connector.py`, `backend/tests/test_zhengfang_adapter.py`
- Inspect: `android/`, `harmony/`, `web/`, `wx/` 中 EduRepository、EduViewModel、EduSystem、EduLogin、studentApi、academic 页面和 DTO
- Create: `docs/superpowers/plans/2026-08-20-campusmateai-edu-real-integration.md`

**Interfaces:**
- Produces: 一份按 P0/P1 编号的证据表、调用链、测试缺口和最小修改文件清单；后续任务只修 `CONFIRMED` 或 `PARTIALLY_CONFIRMED` 项。

- [ ] Step 1: 搜索所有 connection endpoint、状态转换、provider config 构造、主动 HTTP 请求、跨端字段和现有测试。
- [ ] Step 2: 读取实现及调用方上下文，确认每条外部审查结论是否真实存在。
- [ ] Step 3: 运行当前专项测试，记录基线失败与环境问题。
- [ ] Step 4: 更新审计报告草稿，明确 `NOT_PRESENT`/`ALREADY_FIXED` 项不改代码。

### Task 2: EduConnection 首次认证与归属隔离

**Files:**
- Modify: `backend/app/services/edu/connector.py` 或实际 `EduConnectorService` 所在文件
- Modify: `backend/app/api/routes/edu.py`
- Test: `backend/tests/test_edu_connector.py` 或按现有结构新增专项测试

**Interfaces:**
- Consumes: `login_execution_mode`、当前用户身份、`EduConnection` 状态。
- Produces: 创建 `backend_http` 后为 `auth_required`、创建 `client_webview` 后为 `waiting_user_login`；第一次 credential/cookie continue 执行认证；所有 GET/POLL/CONTINUE/CANCEL 先校验 owner。

- [ ] Step 1: 写测试覆盖 create → `auth_required`、第一次 credential continue、create → `waiting_user_login`、第一次 cookie continue、POLL/CANCEL/auth_failed/unsupported、跨用户 GET/continue。
- [ ] Step 2: 运行专项测试确认新行为在当前实现上 RED。
- [ ] Step 3: 最小修改状态机和 endpoint 归属校验，保留已有错误语义与非教务代码。
- [ ] Step 4: 运行专项测试及相关回归测试确认 GREEN。
- [ ] Step 5: 检查 diff 中不存在凭据/Cookie 日志。

### Task 3: URL 临时目标、university 隔离与 Discovery 文件健壮性

**Files:**
- Modify: `backend/app/services/edu/connector.py`、`backend/app/api/routes/edu.py`、实际 Discovery service/repository/model/schema 文件
- Modify: `backend/app/models/edu.py` / migration（仅在现有结构确实需要时）
- Test: Discovery/edu route 现有测试或新增 `backend/tests/test_edu_discovery.py`

**Interfaces:**
- Consumes: 已验证 EduSystem、用户输入 `portal_url`、当前用户 `university_id`、candidate loader。
- Produces: 已验证系统可复用；未验证 URL 只写连接级目标/candidate，不 upsert 公共 EduSystem；普通用户不能指定其他大学；候选文件不存在/空白返回空集合，损坏 JSON 明确报错且不覆盖。

- [ ] Step 1: 写 URL 污染、university mismatch、空/空白/合法/损坏 candidate 文件测试。
- [ ] Step 2: 运行测试确认 RED。
- [ ] Step 3: 实现连接级临时 URL 或等价字段，固定 university 来源并修复 loader。
- [ ] Step 4: 运行测试确认 GREEN，并验证已验证 EduSystem 复用路径。

### Task 4: SSRF 统一防护

**Files:**
- Modify: 实际 SSRF URL validator、`probe_portal`、`discovery_service`、`ZhengfangHttpClient` 及所有后端主动访问学校 URL 的调用点
- Test: SSRF 所在测试文件或新增 `backend/tests/test_edu_ssrf.py`

**Interfaces:**
- Consumes: URL、DNS resolver、httpx response redirect。
- Produces: 每个实际请求前检查解析后的 IPv4/IPv6；redirect 目标重新检查；内网/loopback/link-local/multicast 等拒绝；校内网仍仅允许 client_webview 路径。

- [ ] Step 1: 写 IP、DNS→私网、redirect→loopback、合法公网和校内网模式测试。
- [ ] Step 2: 运行测试确认 RED。
- [ ] Step 3: 集中实现可注入 resolver/transport 的 validator，并关闭不受控自动跟随或逐跳校验。
- [ ] Step 4: 运行 SSRF 与全量 Edu 测试确认 GREEN。

### Task 5: Zhengfang 会话验证、完整配置与能力语义

**Files:**
- Modify: `backend/app/services/edu/adapters/zhengfang*`、`backend/app/services/edu/*config*`、`EduSession` 持久化位置、能力声明位置
- Test: `backend/tests/test_zhengfang_adapter.py`、脱敏 fixture 目录 `backend/tests/fixtures/edu/zhengfang/`

**Interfaces:**
- Consumes: 完整 EduSystem 配置、Cookie、profile/schedule/grade/exam response。
- Produces: `login_with_cookies` 只在 authenticated_probe 证明学生会话时成功；Session 可恢复完整 AdapterConfig；Profile HTML/JSON、JWGL2/JW2005 schedule/grade 按 fixture 解析；Exam 无 parser 时返回明确 unsupported；Qiangzhi/Qingguo 能力如实声明。

- [ ] Step 1: 为登录页 200、认证错误、有效 probe、网络异常、配置字段保留、现有 parser 和 exam unsupported 写测试。
- [ ] Step 2: 运行测试确认 RED。
- [ ] Step 3: 实现统一 `build_adapter_config(system)`、严格 probe 和 session config 持久化；只实现 fixture 有证据的解析。
- [ ] Step 4: 运行 Zhengfang 专项测试确认 GREEN，并检查 fixture 无真实身份信息。

### Task 6: 跨端契约、登录模式与旧接口兼容

**Files:**
- Modify: `backend/app/schemas/edu.py`、OpenAPI 相关 model（若需要）
- Modify: `android/`、`harmony/`、`web/`、`wx/` 的 Edu DTO/repository/academic 登录链路
- Modify: `backend/app/api/routes/edu.py` 旧 `/edu/bind` 兼容层（仅在审计确认双轨）
- Test: 跨端静态 contract test 或现有端测试

**Interfaces:**
- Consumes: Backend OpenAPI contract。
- Produces: 所有端使用同一 `connection_status`/约定字段和 `backend_http | client_webview | unsupported`；旧 bind 不再维护独立认证逻辑；若跨设备 handoff 现有基础设施不足，则只提供安全接口/模型并明确未完成，不伪装支持。

- [ ] Step 1: 写 DTO/枚举 contract test，覆盖 Backend、Android、Harmony、Web、WX 关键字段。
- [ ] Step 2: 运行测试确认 RED。
- [ ] Step 3: 对齐真实字段，修正 UI capability 展示；把旧 bind 接到新 Connection Service 或标记 deprecated。
- [ ] Step 4: 运行契约及相关端测试；不扩大为无关 UI 重构。

### Task 7: 端到端验证与交付报告

**Files:**
- Modify: `docs/` 中本专项审计/交付报告（如仓库已有对应文件则沿用）
- Inspect: Backend、Web、Android、Harmony、WX 的实际构建/测试入口

**Interfaces:**
- Produces: Audit Result 表、Changed Files、Architecture Changes、每条测试命令的 passed/failed/skipped、剩余风险，区分代码支持/fixture 覆盖/真实学校验证。

- [ ] Step 1: 运行 `backend` 专项测试，再运行全量 `pytest`。
- [ ] Step 2: 运行 Web lint/test/build；Android 绑定项目 JDK 21 后执行现有 test/lint/compile；Harmony/WX 执行仓库中可运行的检查。
- [ ] Step 3: 检查 git diff、敏感信息、无关模块变更和未提交文件。
- [ ] Step 4: 仅基于命令输出和代码证据写最终报告，明确未能执行的命令及原因。

---

## Self-review checklist

- P0-1 状态机与首次认证：Task 2。
- P0 归属隔离：Task 2。
- P0 公共 EduSystem 污染与 university 越权：Task 3。
- P0 candidate loader：Task 3。
- P0 SSRF DNS/redirect/校内网边界：Task 4。
- P1 Zhengfang cookie/config/session/parser/exam/capabilities：Task 5。
- P1 Harmony/Web/WX/Android contract 与旧 bind：Task 6。
- Golden School 脱敏 fixture：Task 5。
- 跨设备 handoff：Task 6 仅按现有基础设施最小实现，不把 TODO 写成完成。
- 全端验证与报告：Task 7。
