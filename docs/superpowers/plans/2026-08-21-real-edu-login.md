# 真实教务登录与课表导入 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 Android 提供无验证码直登、遇人工验证自动 WebView、并可确认真实课表已持久化的教务连接链路。

**Architecture:** 后端正方 Adapter 读取登录页并执行 CSRF/RSA 表单登录，显式返回 `NeedUserAction`，Connector 将其变为 `waiting_user_login` 而非 mock fallback。Android 消费稳定状态：仅人工验证时自动导航到现有 WebView，并在同步后重新读取持久化课表确认导入。

**Tech Stack:** FastAPI、Pydantic、httpx、pytest、Kotlin、Jetpack Compose、Retrofit、JUnit/Robolectric。

**Spec:** `docs/superpowers/specs/2026-08-21-real-edu-login-design.md`

## Global Constraints

- MockEduAdapter 仅允许由测试显式选择；真实用户连接不得回退 mock。
- 不自动绕过、识别或填写图片验证码、滑块、短信验证码或 MFA。
- 密码、Cookie、CSRF token、公钥原始响应和真实课程不得写入测试夹具、日志、错误消息或 Git。
- Android 构建必须使用 `F:\demo1\android\.tools\jdk21-full\jdk-21.0.12+8`；SDK 使用 `H:\Dev\androidSDK`。
- 正方真实目标为河南财经政法大学 JWGL2，站点 URL 只作为受审查的学校配置使用。

---

### Task 1: 正方 JWGL2 直登与人工验证判定

**Files:**
- Modify: `backend/app/services/edu/adapters/zhengfang_http.py`
- Modify: `backend/app/services/edu/adapters/zhengfang.py`
- Test: `backend/tests/test_zhengfang_adapter.py`

**Interfaces:**
- Consumes: `ZhengfangHttpClient`, `SchoolConfig`, `NeedUserAction`。
- Produces: `ZhengfangAdapter.login(username, password, config) -> dict`；人工验证时抛 `NeedUserAction(action, detail, captcha_url)`。

- [ ] **Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_jwgl2_login_response_requiring_captcha_raises_user_action(monkeypatch):
    with pytest.raises(NeedUserAction) as error:
        await ZhengfangAdapter().login(username="fixture", password="password", config={"base_url": "https://jwxt.example.edu"})
    assert error.value.action == "NEED_CAPTCHA"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `F:\demo1\backend\venv\Scripts\python.exe -m pytest tests/test_zhengfang_adapter.py -q`

Expected: FAIL because the adapter posts plaintext fields and does not map login response to `NeedUserAction`.

- [ ] **Step 3: Write minimal implementation**

```python
page = await client.get(school.effective_login_url, referer=school.base_url)
csrf_token = extract_hidden_value(page.text, "csrftoken")
key = await client.get("/jwglxt/xtgl/login_getPublicKey.html")
response = await client.post(school.effective_login_url, data=encrypted_login_form(username, password, csrf_token, key.text), referer=school.effective_login_url)
if login_response_requires_user_action(response.text):
    raise NeedUserAction("NEED_CAPTCHA", captcha_url=school.effective_login_url)
```

Add compact parsing and RSA helpers. Do not log response text or submitted values. Map image, slider, SMS and MFA signals to existing action strings.

- [ ] **Step 4: Run test to verify it passes**

Run: `F:\demo1\backend\venv\Scripts\python.exe -m pytest tests/test_zhengfang_adapter.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

Run: `git add backend/app/services/edu/adapters/zhengfang_http.py backend/app/services/edu/adapters/zhengfang.py backend/tests/test_zhengfang_adapter.py && git commit -m "feat: support direct Zhengfang login and captcha handoff"`

### Task 2: Connector 真实状态与 mock 隔离

**Files:**
- Modify: `backend/app/services/edu/connector.py`
- Test: `backend/tests/test_edu_connector.py`

**Interfaces:**
- Consumes: `NeedUserAction`, `EduConnectionContinue`。
- Produces: `waiting_user_login` 加安全的 `NEED_CAPTCHA|NEED_SLIDER|NEED_SMS|NEED_MFA` 错误码；未知/未实现 provider 返回 `unsupported`。

- [ ] **Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_credentials_need_captcha_transitions_to_webview(monkeypatch):
    monkeypatch.setattr(ZhengfangAdapter, "login", raise_need_captcha)
    result = await connector.continue_connection(connection_id=connection.id, username="fixture", password="password")
    assert result == CONN_WAITING_USER_LOGIN
    assert repo.get_connection(connection.id).error_code == "NEED_CAPTCHA"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `F:\demo1\backend\venv\Scripts\python.exe -m pytest tests/test_edu_connector.py -q`

Expected: FAIL because `NeedUserAction` is not caught and development mode selects mock for unknown providers.

- [ ] **Step 3: Write minimal implementation**

```python
except NeedUserAction as action:
    self._edu_repo.update_connection_state(connection_id, state=CONN_WAITING_USER_LOGIN, error_code=action.action, error_message=human_message(action.action))
    return CONN_WAITING_USER_LOGIN
```

Apply the same mapping to cookie verification. Only explicit test fixtures may select `provider="mock"`; URL discovery must never create a mock binding.

- [ ] **Step 4: Run test to verify it passes**

Run: `F:\demo1\backend\venv\Scripts\python.exe -m pytest tests/test_edu_connector.py tests/test_zhengfang_adapter.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

Run: `git add backend/app/services/edu/connector.py backend/tests/test_edu_connector.py && git commit -m "fix: preserve real edu login state without mock fallback"`

### Task 3: 黄金学校配置与导入契约

**Files:**
- Modify: `backend/app/services/edu/registry.py`
- Modify: `backend/app/services/edu/adapters/zhengfang_strategy.py`
- Modify: `backend/tests/test_edu_connector.py`
- Modify: `backend/tests/test_edu_data_repository.py`

**Interfaces:**
- Consumes: verified university/system metadata.
- Produces: `zhengfang` / `jwgl2` / `backend_http` configuration; a schedule result is successful only when persisted with nonzero items.

- [ ] **Step 1: Write the failing test**

```python
def test_schedule_sync_without_persisted_items_is_failed(monkeypatch):
    result = asyncio.run(connector.sync_schedule(user_id))
    assert result.status == "failed"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `F:\demo1\backend\venv\Scripts\python.exe -m pytest tests/test_edu_connector.py tests/test_edu_data_repository.py -q`

Expected: FAIL because success does not yet enforce a persisted non-empty schedule.

- [ ] **Step 3: Write minimal implementation**

```python
HUEL_ZHENGFANG = {"provider": "zhengfang", "provider_version": "jwgl2", "base_url": "https://xk.huel.edu.cn", "login_execution_mode": "backend_http", "verification_status": "VERIFIED_LIVE", "is_mock": False}
```

Keep school endpoint overrides and semester payloads restricted to verified protocol evidence. Return failed schedule sync when fetched data cannot be persisted.

- [ ] **Step 4: Run test to verify it passes**

Run: `F:\demo1\backend\venv\Scripts\python.exe -m pytest tests/test_edu_connector.py tests/test_edu_data_repository.py tests/test_zhengfang_adapter.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

Run: `git add backend/app/services/edu/registry.py backend/app/services/edu/adapters/zhengfang_strategy.py backend/tests/test_edu_connector.py backend/tests/test_edu_data_repository.py && git commit -m "feat: verify HUEL Zhengfang schedule import"`

### Task 4: Android 自动 WebView 分流和课表确认

**Files:**
- Modify: `android/app/src/main/java/com/example/campusai/data/remote/ApiService.kt`
- Modify: `android/app/src/main/java/com/example/campusai/data/repository/EduRepository.kt`
- Modify: `android/app/src/main/java/com/example/campusai/ui/screens/profile/EduViewModel.kt`
- Modify: `android/app/src/main/java/com/example/campusai/ui/screens/profile/EduSystemScreen.kt`
- Modify: `android/app/src/main/java/com/example/campusai/ui/screens/profile/EduLoginScreen.kt`
- Create: `android/app/src/test/java/com/example/campusai/ui/screens/profile/EduConnectionFlowTest.kt`

**Interfaces:**
- Consumes: `EduConnectionDto.state`, `EduConnectionDto.error_code`, `EduSyncResult.persisted`, `EduScheduleItemsResponse.items_count`。
- Produces: one-time WebView event only for `waiting_user_login`; `Synced` only after persisted items are re-read.

- [ ] **Step 1: Write the failing test**

```kotlin
@Test fun emptyPersistedScheduleIsReportedAsImportFailure() {
    val result = importVerifier.verify(EduSyncResult(status = "success", persisted = true, items_count = 0), EduScheduleItemsResponse(items_count = 0))
    assertTrue(result is ImportVerification.Failure)
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `F:\demo1\android\gradlew.bat -p F:\demo1\.worktrees\edu-real-login\android :app:testDebugUnitTest`

Expected: FAIL because sync success does not verify persisted items and WebView navigation remains manually button-driven.

- [ ] **Step 3: Write minimal implementation**

```kotlin
val imported = scheduleResult?.status == "success" && scheduleResult.persisted && scheduleResult.items_count > 0 && (repo.listScheduleItems().getOrNull()?.items_count ?: 0) > 0
```

Make Compose consume the one-time event immediately. Do not open a WebView after a successful backend login. Show imported course count or an import failure.

- [ ] **Step 4: Run test to verify it passes**

Run: `F:\demo1\android\gradlew.bat -p F:\demo1\.worktrees\edu-real-login\android :app:testDebugUnitTest`

Expected: PASS.

- [ ] **Step 5: Commit**

Run: `git add android/app/src/main/java/com/example/campusai/data/remote/ApiService.kt android/app/src/main/java/com/example/campusai/data/repository/EduRepository.kt android/app/src/main/java/com/example/campusai/ui/screens/profile/EduViewModel.kt android/app/src/main/java/com/example/campusai/ui/screens/profile/EduSystemScreen.kt android/app/src/main/java/com/example/campusai/ui/screens/profile/EduLoginScreen.kt android/app/src/test/java/com/example/campusai/ui/screens/profile/EduConnectionFlowTest.kt && git commit -m "feat: route edu verification to browser only when required"`

### Task 5: 全链路验证

**Files:**
- Modify: `docs/superpowers/specs/2026-08-21-real-edu-login-design.md`

**Interfaces:**
- Consumes: Tasks 1–4 and a runtime-only authenticated session.
- Produces: fresh regression and real-site verification evidence without credentials.

- [ ] **Step 1: Run backend regression suite**

Run: `F:\demo1\backend\venv\Scripts\python.exe -m pytest tests/test_edu_connector.py tests/test_zhengfang_adapter.py tests/test_edu_data_repository.py -q`

Expected: PASS with no leaked secrets.

- [ ] **Step 2: Run Android unit suite**

Run: `$env:JAVA_HOME='F:\demo1\android\.tools\jdk21-full\jdk-21.0.12+8'; $env:PATH="$env:JAVA_HOME\bin;$env:PATH"; $env:ANDROID_HOME='H:\Dev\androidSDK'; $env:ANDROID_SDK_ROOT='H:\Dev\androidSDK'; & 'F:\demo1\android\gradlew.bat' -p 'F:\demo1\.worktrees\edu-real-login\android' :app:testDebugUnitTest`

Expected: BUILD SUCCESSFUL.

- [ ] **Step 3: Perform real-site verification**

Use runtime-only credentials supplied in the conversation. Make one direct login attempt; if the school requests human verification, complete it only in Android WebView before returning Cookie state. Confirm `zhengfang` provider, non-mock binding, persisted schedule sync, and non-empty `/edu/schedule/items`. Do not record credentials or returned personal/course data.

- [ ] **Step 4: Commit**

Run: `git add docs/superpowers/specs/2026-08-21-real-edu-login-design.md && git commit -m "test: record real edu integration verification"`
