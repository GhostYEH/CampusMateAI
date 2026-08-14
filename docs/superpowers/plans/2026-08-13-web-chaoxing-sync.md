# Web 学习通连接与多端同步 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让学生从 Web 通知整理页或个人中心连接学习通，将课程、作业与通知按 CampusMate 账号持久化到后端，并在各端读取同一份数据。

**Architecture:** 保留 FastAPI 现有学习通端点与 SQLite 模型，把已有孤立教师页面重构为学生单页连接流程。Web 通知页改为消费后端已经聚合校内公告和用户通知的 `/notices` 接口，后端补齐连接状态语义和用户隔离回归测试。

**Tech Stack:** Vue 3、Vue Router、Axios、Node.js test runner、FastAPI、Pydantic v2、SQLite、pytest

## Global Constraints

- 不修改 `android/` 和 `harmony/` 下任何文件。
- 保留工作区已有未提交改动，只做可审查的增量编辑。
- 学习通密码不得写入 localStorage、Pinia 或数据库；仅后端加密持久化远端 Cookie。
- 所有学习通凭证、课程、作业、通知查询和写入必须以当前 JWT `user.id` 为隔离边界。
- 解除连接只删除当前用户凭证，保留已经同步的数据。
- 浏览器不实现微信、QQ 或其他应用的系统通知监听。
- 视觉沿用现有学生 Web 设计系统，不新增依赖或图片资产。

---

## File Structure

- `backend/app/api/routes/chaoxing.py`：统一学习通连接状态语义、用户统计和解除连接行为。
- `backend/app/api/routes/courses.py`：继续允许学生读取自己拥有的学习通导入课程。
- `backend/app/api/routes/notices.py`：继续聚合当前用户的统一通知与校内公告，并返回可区分通知类型的字段。
- `backend/app/schemas/notice.py`：为通知列表项增加 `kind` 与 `source_url`，让 Web 避免把学习通通知当作校内公告标记已读。
- `backend/tests/test_chaoxing.py`：验证凭证、状态统计、隔离、解除连接和历史数据保留。
- `backend/tests/test_notices.py`：验证学习通通知只对所属用户可见且带统一通知类型。
- `web/src/services/chaoxing.js`：学生 Web 学习通 API 封装。
- `web/src/services/studentApi.js`：增加统一通知列表读取函数。
- `web/src/views/student/StudentChaoxingView.vue`：学生学习通单页状态机和完整交互。
- `web/src/views/student/StudentNotificationsView.vue`：使用 `/notices` 聚合数据并添加学习通入口。
- `web/src/views/student/StudentProfileView.vue`：增加学习通快捷入口。
- `web/src/router.js`：注册学生路由并兼容重定向旧教师 URL。
- `web/tests/chaoxing-sync-regression.test.mjs`：路由、入口、接口和通知类型回归测试。
- `docs/reviews/2026-08-13-harmony-android-chaoxing-parity.md`：只读记录鸿蒙与 Android 流程差异。

---

### Task 1: 固化后端用户隔离与状态语义

**Files:**
- Modify: `backend/app/api/routes/chaoxing.py`
- Modify: `backend/app/schemas/chaoxing.py`
- Test: `backend/tests/test_chaoxing.py`

**Interfaces:**
- Consumes: `current_user -> UserRow`、`ChaoxingRepository.get_credentials(user_id)`、SQLite 中的 `courses`、`personal_tasks`、`notices`。
- Produces: `GET /chaoxing/status -> ChaoxingSyncStatus`；`POST /chaoxing/disconnect -> {"status": "disconnected"}`，二者只作用于当前用户。

- [ ] **Step 1: 写状态统计和解除连接的失败测试**

在 `backend/tests/test_chaoxing.py` 中增加测试，分别插入两个用户的学习通课程、待办和通知，并断言当前用户只看到自己的统计；解除 user1 后，user2 凭证仍存在且 user1 已同步数据仍保留：

```python
@pytest.mark.asyncio
async def test_chaoxing_status_counts_only_current_user(db, monkeypatch):
    # 两个用户使用相同远端 ID，数据库记录必须独立。
    # mock 远端状态验证为 HTTP 200。
    status = await get_chaoxing_status(user=user1, container=container)
    assert status.courses == 1
    assert status.pending_assignments == 1
    assert status.notices == 1

@pytest.mark.asyncio
async def test_disconnect_removes_only_credentials_and_preserves_synced_data(db):
    result = await disconnect_chaoxing(user=user1, container=container)
    assert result == {"status": "disconnected"}
    assert repo.get_credentials("user1") is None
    assert repo.get_credentials("user2") == {"cookie": "B"}
    assert count_rows(db, "courses", "teacher_id", "user1") == 1
    assert count_rows(db, "personal_tasks", "user_id", "user1") == 1
    assert count_rows(db, "notices", "user_id", "user1") == 1
```

- [ ] **Step 2: 运行定向测试并确认按预期失败**

Run: `backend\.venv\Scripts\python.exe -m pytest tests/test_chaoxing.py -k "status_counts_only_current_user or disconnect_removes_only_credentials" -v`

Expected: 新测试因缺失导入、状态语义或测试所需行为失败；不能因语法或 fixture 错误失败。

- [ ] **Step 3: 实现最小后端修正**

确保状态验证中认证失效返回 `expired`，远端网络/5xx 返回 `unavailable`；统计 SQL 必须带 `user.id`。解除连接只调用：

```python
container.chaoxing_repository.delete_credentials(user.id)
return {"status": "disconnected"}
```

不得删除 `courses`、`personal_tasks` 或 `notices`。

- [ ] **Step 4: 运行后端学习通测试**

Run: `backend\.venv\Scripts\python.exe -m pytest tests/test_chaoxing.py tests/test_chaoxing_notices.py -v`

Expected: PASS，且没有新增 warning 或真实外网请求。

- [ ] **Step 5: 提交后端状态语义**

```powershell
git add -- backend/app/api/routes/chaoxing.py backend/app/schemas/chaoxing.py backend/tests/test_chaoxing.py
git commit -m "test: lock chaoxing account isolation"
```

---

### Task 2: 统一通知 API 暴露学习通通知类型

**Files:**
- Modify: `backend/app/schemas/notice.py`
- Modify: `backend/app/api/routes/notices.py`
- Test: `backend/tests/test_notices.py`

**Interfaces:**
- Consumes: `NoticeRepository.list_notices(user.id)` 与当前用户可见校内班级公告。
- Produces: `GET /notices` 的每个 item 含 `kind: "unified" | "announcement"`、`unread`、`source_url`，且只返回当前用户可见数据。

- [ ] **Step 1: 写学习通通知隔离的失败测试**

在 `backend/tests/test_notices.py` 增加：

```python
def test_list_notices_exposes_only_current_users_chaoxing_notice(db):
    notice_repo.create_or_update_notice(
        user_id="user1", source="chaoxing", external_id="same",
        title="用户一通知", source_url="https://example.test/1"
    )
    notice_repo.create_or_update_notice(
        user_id="user2", source="chaoxing", external_id="same",
        title="用户二通知", source_url="https://example.test/2"
    )
    result = list_notices(user=user1, container=container)
    assert [item.title for item in result.items] == ["用户一通知"]
    assert result.items[0].kind == "unified"
    assert result.items[0].source_url == "https://example.test/1"
```

- [ ] **Step 2: 运行测试并确认因新字段缺失而失败**

Run: `backend\.venv\Scripts\python.exe -m pytest tests/test_notices.py -k current_users_chaoxing_notice -v`

Expected: FAIL，指出 `NoticeOut` 没有 `kind` 或 `source_url`。

- [ ] **Step 3: 扩展通知输出模型和映射**

在 `NoticeOut` 中新增：

```python
kind: str = Field("announcement", pattern="^(announcement|unified)$")
source_url: Optional[str] = None
```

统一通知映射为 `kind="unified"`、`source_url=n.source_url`；校内公告映射为 `kind="announcement"`。保持现有用户过滤、倒序排序和分页。

- [ ] **Step 4: 运行通知与学习通后端测试**

Run: `backend\.venv\Scripts\python.exe -m pytest tests/test_notices.py tests/test_chaoxing.py tests/test_chaoxing_notices.py -v`

Expected: PASS。

- [ ] **Step 5: 提交通知契约**

```powershell
git add -- backend/app/schemas/notice.py backend/app/api/routes/notices.py backend/tests/test_notices.py
git commit -m "feat: expose synced notices to web"
```

---

### Task 3: 建立学生 Web 学习通页面、路由与入口

**Files:**
- Create: `web/src/services/chaoxing.js`
- Create: `web/src/views/student/StudentChaoxingView.vue`
- Modify: `web/src/router.js`
- Modify: `web/src/views/student/StudentNotificationsView.vue`
- Modify: `web/src/views/student/StudentProfileView.vue`
- Test: `web/tests/chaoxing-sync-regression.test.mjs`

**Interfaces:**
- Consumes: `GET /chaoxing/status`、`POST /chaoxing/login`、`POST /chaoxing/sync`、`POST /chaoxing/disconnect`。
- Produces: 学生路由 `/profile/chaoxing`；旧 `/teacher/chaoxing*` 重定向；通知页与个人中心入口。

- [ ] **Step 1: 写 Web 路由、入口和 API 契约失败测试**

创建 `web/tests/chaoxing-sync-regression.test.mjs`，使用 Vite SSR 加载 router 并读取源码：

```javascript
test("registers student chaoxing route and redirects legacy teacher URLs", async () => {
  const router = await loadRouter();
  assert.equal(router.resolve("/profile/chaoxing").matched.at(-1).components.default.__name, "StudentChaoxingView");
  assert.equal(router.resolve("/teacher/chaoxing").redirectedFrom?.fullPath, "/teacher/chaoxing");
});

test("links chaoxing from notifications and profile", async () => {
  assert.match(await read("src/views/student/StudentNotificationsView.vue"), /\/profile\/chaoxing/);
  assert.match(await read("src/views/student/StudentProfileView.vue"), /学习通同步/);
});

test("student chaoxing page uses all four backend operations", async () => {
  const source = await read("src/views/student/StudentChaoxingView.vue");
  for (const name of ["getChaoxingStatus", "loginChaoxing", "syncChaoxing", "disconnectChaoxing"]) {
    assert.match(source, new RegExp(name));
  }
});
```

- [ ] **Step 2: 运行 Web 测试并确认失败**

Run: `node --test tests/chaoxing-sync-regression.test.mjs`

Workdir: `web`

Expected: FAIL，因为学生页面、学生路由和入口尚不存在。

- [ ] **Step 3: 新建学生学习通 API 封装**

`web/src/services/chaoxing.js` 导出：

```javascript
export const getChaoxingStatus = async () => (await client.get("/chaoxing/status")).data;
export const loginChaoxing = async (username, password) => (
  await client.post("/chaoxing/login", { username, password }, { timeout: 30000 })
).data;
export const syncChaoxing = async () => (
  await client.post("/chaoxing/sync", {}, { timeout: 120000 })
).data;
export const disconnectChaoxing = async () => (
  await client.post("/chaoxing/disconnect")
).data;
```

- [ ] **Step 4: 实现学生单页状态机**

`StudentChaoxingView.vue` 使用 `status = ref("checking")`，进入时请求状态；`offline` 和 `expired` 内嵌登录表单；`online` 展示统计并支持同步、解除；`unavailable` 保留最近确认状态并允许重试。登录结束必须执行：

```javascript
password.value = "";
await checkStatus();
```

所有异常通过一个 `errorDetail(error)` 解析 FastAPI `detail`，验证码、重新认证和网络不可用分别显示中文可操作提示。

- [ ] **Step 5: 注册路由并添加双入口**

在学生 children 中注册：

```javascript
{ path: "profile/chaoxing", name: "student-chaoxing", component: StudentChaoxingView, meta: { roles: ["student"] } }
```

将旧教师子树改为顶层兼容重定向：

```javascript
{ path: "/teacher/chaoxing", redirect: "/profile/chaoxing" },
{ path: "/teacher/chaoxing/login", redirect: "/profile/chaoxing" },
```

通知页页头按钮与个人中心 `quickTools` 都指向 `/profile/chaoxing`。

- [ ] **Step 6: 运行 Web 回归测试与构建**

Run: `node --test tests/*.test.mjs`

Run: `npm run build`

Workdir: `web`

Expected: 全部 PASS；Vite 构建无编译错误。

- [ ] **Step 7: 提交学生 Web 连接流程**

```powershell
git add -- web/src/services/chaoxing.js web/src/views/student/StudentChaoxingView.vue web/src/router.js web/src/views/student/StudentNotificationsView.vue web/src/views/student/StudentProfileView.vue web/tests/chaoxing-sync-regression.test.mjs
git commit -m "feat: add web chaoxing connection flow"
```

---

### Task 4: 让 Web 通知页消费后端统一通知

**Files:**
- Modify: `web/src/services/studentApi.js`
- Modify: `web/src/views/student/StudentNotificationsView.vue`
- Test: `web/tests/chaoxing-sync-regression.test.mjs`

**Interfaces:**
- Consumes: `GET /notices?page_size=200` 返回 `{ items: NoticeOut[] }`。
- Produces: `getStudentNotices(params)`；通知页对 `kind="announcement"` 才调用 `markAnnouncementRead`，学习通通知只展开或打开 `source_url`。

- [ ] **Step 1: 写统一通知消费和已读保护失败测试**

追加源码契约测试：

```javascript
test("notifications consume unified notices and guard announcement receipts", async () => {
  const [service, view] = await Promise.all([
    read("src/services/studentApi.js"),
    read("src/views/student/StudentNotificationsView.vue"),
  ]);
  assert.match(service, /getStudentNotices/);
  assert.match(service, /client\.get\("\/notices"/);
  assert.match(view, /item\.kind\s*!==\s*"announcement"/);
});
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `node --test tests/chaoxing-sync-regression.test.mjs`

Workdir: `web`

Expected: FAIL，因为通知页仍逐班级请求公告且没有 `kind` 保护。

- [ ] **Step 3: 增加统一通知服务并替换加载逻辑**

`studentApi.js`：

```javascript
export async function getStudentNotices(params = {}) {
  const { data } = await client.get("/notices", { params: { page_size: 200, ...params } });
  return data;
}
```

通知页 `load()` 改为单次 `getStudentNotices()`，标准化为：

```javascript
notices.value = (data.items || []).map((item) => ({
  ...item,
  has_read: !item.unread,
  published_at: item.time,
}));
```

`toggleNotice` 与 `openNoticeDetail` 仅在 `item.kind === "announcement"` 时写入校内公告已读回执；`kind="unified"` 且有 `source_url` 时使用安全的新窗口打开来源。

- [ ] **Step 4: 运行全部 Web 测试与构建**

Run: `node --test tests/*.test.mjs`

Run: `npm run build`

Workdir: `web`

Expected: 全部 PASS。

- [ ] **Step 5: 提交通知聚合衔接**

```powershell
git add -- web/src/services/studentApi.js web/src/views/student/StudentNotificationsView.vue web/tests/chaoxing-sync-regression.test.mjs
git commit -m "feat: show synced notices on web"
```

---

### Task 5: 全链路验证与只读鸿蒙对照报告

**Files:**
- Create: `docs/reviews/2026-08-13-harmony-android-chaoxing-parity.md`
- Verify only: `android/**`
- Verify only: `harmony/**`

**Interfaces:**
- Consumes: 已实现的 Web/后端功能与当前 Android/鸿蒙源码。
- Produces: 可复查的流程对照和零移动端改动证明。

- [ ] **Step 1: 记录移动端基线状态**

运行并保存输出以便与完成后比较：

```powershell
git status --short -- android harmony
git diff --numstat -- android harmony
```

不要编辑或格式化这些目录。

- [ ] **Step 2: 写只读流程对照报告**

报告明确列出：Android 已有学习通账号登录、状态、手动同步、周期同步、失效恢复、解除连接；鸿蒙已有系统通知订阅、来源识别、通知上传/转待办，但没有学习通账号绑定、状态检查、后端拉取同步和解除连接页面。结论须区分“通知监听一致性”和“学习通绑定流程一致性”。

- [ ] **Step 3: 运行后端定向与完整测试**

Run: `backend\.venv\Scripts\python.exe -m pytest tests/test_chaoxing.py tests/test_chaoxing_notices.py tests/test_notices.py -v`

Run: `backend\.venv\Scripts\python.exe -m pytest -q`

Expected: 全部 PASS；若完整套件有与本次无关的既有失败，记录具体测试和证据，定向测试仍须全绿。

- [ ] **Step 4: 运行 Web 全部测试和生产构建**

Run: `node --test tests/*.test.mjs`

Run: `npm run build`

Workdir: `web`

Expected: 全部 PASS。

- [ ] **Step 5: 验证移动端文件零新增改动**

再次运行：

```powershell
git status --short -- android harmony
git diff --numstat -- android harmony
```

Expected: 与 Step 1 基线一致，没有本次任务新增的 Android/鸿蒙差异。

- [ ] **Step 6: 提交审计报告**

```powershell
git add -- docs/reviews/2026-08-13-harmony-android-chaoxing-parity.md
git commit -m "docs: audit harmony chaoxing parity"
```
