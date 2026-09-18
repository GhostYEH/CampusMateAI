# OpenMAIC Fusion 01 Source, Service, and Auth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` (recommended) or `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立可追溯源码基线、仓库内受管 Node 服务、FastAPI 状态代理和短期内部断言。

**Architecture:** 正式源码只从固定 upstream commit 提取。`openmaic-service/` 是无公开 UI 的服务端；FastAPI 是唯一公开入口并用 HMAC 断言调用内部服务。

**Tech Stack:** PowerShell、Node.js 22.19+、TypeScript、Fastify、Vitest、FastAPI、Pydantic、pytest。

**Spec:** `docs/superpowers/specs/2026-09-18-openmaic-campus-fusion-design.md`

## Global Constraints

- 正式来源固定为 `THU-MAIC/OpenMAIC` tag `v1.0.3`、commit `e693e11a81644f84c258df73dbda378643520a62`。
- 本地参考副本不是可发布来源或运行时依赖。
- Node.js 最低版本为 22.19；浏览器继续只使用 `webreact/` 的 React 18。
- 不新增第二登录、公开 OpenMAIC 站点、整站 iframe 或 CampusMate 数据库迁移。
- 密钥只通过环境变量或 secret provider 注入，任何日志和响应都不得包含密钥。

---

### Task 1: 固定源码与许可证审计

**Files:**
- Create: `scripts/openmaic-source-audit.ps1`
- Test: `scripts/tests/openmaic-source-audit.test.mjs`
- Create: `third_party/openmaic/UPSTREAM.json`
- Create: `third_party/openmaic/LICENSE`
- Create: `third_party/openmaic/NOTICE.md`
- Create: `third_party/openmaic/source-manifest.sha256`
- Create: `third_party/openmaic/capability-inventory.json`

**Interfaces:**
- Consumes: 环境变量 `OPENMAIC_AUDIT_SOURCE` 指向官方固定 commit checkout。
- Produces: `openmaic-source-audit.ps1 -Source string -Output string -ExpectedCommit string`；`UPSTREAM.json` 含 `repository`、`tag`、`commit`、`auditedAt`、`files`；capability inventory 枚举产品 routes、pages、components、packages、skills 和 render-service entries。

- [ ] **Step 1: Write the failing test**

```js
test("rejects a source without the pinned commit", () => {
  const result = spawnSync("pwsh", ["-File", script, "-Source", fixture, "-Output", out, "-ExpectedCommit", pinned]);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr.toString(), /commit/i);
});

test("inventories every product surface before migration", () => {
  const inventory = JSON.parse(readFileSync(join(out, "capability-inventory.json"), "utf8"));
  assert.ok(inventory.routes.length > 0);
  assert.ok(inventory.packages.length > 0);
  assert.equal(inventory.unclassified.length, 0);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test scripts/tests/openmaic-source-audit.test.mjs`
Expected: FAIL because `scripts/openmaic-source-audit.ps1` does not exist.

- [ ] **Step 3: Write minimal implementation**

```powershell
param([string]$Source, [string]$Output, [string]$ExpectedCommit)
$metadata = Get-Content -Raw (Join-Path $Source 'UPSTREAM.json') | ConvertFrom-Json
if ($metadata.commit -ne $ExpectedCommit) { throw 'OpenMAIC commit does not match the pinned source' }
if (-not (Test-Path (Join-Path $Source 'LICENSE'))) { throw 'OpenMAIC LICENSE is missing' }
```

扩展同一脚本：复制 LICENSE/NOTICE、按相对路径排序生成 SHA-256 清单、生成 capability inventory，并拒绝符号链接逃逸输出目录。每个 inventory 条目必须映射到设计矩阵编号或 `campusmate-equivalent`，未分类条目让脚本失败。

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test scripts/tests/openmaic-source-audit.test.mjs`
Expected: PASS for the valid fixture and non-zero exit for invalid fixtures.

- [ ] **Step 5: Commit**

```powershell
git add scripts/openmaic-source-audit.ps1 scripts/tests/openmaic-source-audit.test.mjs third_party/openmaic
git commit -m "build: pin audited OpenMAIC source"
```

### Task 2: 建立无 UI 的受管服务

**Files:**
- Create: `openmaic-service/package.json`
- Create: `openmaic-service/tsconfig.json`
- Create: `openmaic-service/src/config.ts`
- Create: `openmaic-service/src/server.ts`
- Create: `openmaic-service/src/routes/health.ts`
- Test: `openmaic-service/tests/health.test.ts`
- Create: `openmaic-service/.env.example`

**Interfaces:**
- Consumes: `OPENMAIC_PORT`、`OPENMAIC_DATABASE_URL`、`OPENMAIC_INTERNAL_SECRET`。
- Produces: `createServer(deps: ServiceDependencies): FastifyInstance`；`GET /internal/health/live`；`GET /internal/health/ready`。

- [ ] **Step 1: Write the failing test**

```ts
it("reports dependency failure without exposing a public UI", async () => {
  const app = createServer({ readiness: async () => ({ database: false }) });
  expect((await app.inject({ method: "GET", url: "/internal/health/ready" })).statusCode).toBe(503);
  expect((await app.inject({ method: "GET", url: "/" })).statusCode).toBe(404);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `Set-Location openmaic-service; npx vitest run tests/health.test.ts`
Expected: FAIL because `createServer` is missing.

- [ ] **Step 3: Write minimal implementation**

```ts
export function createServer(deps: ServiceDependencies) {
  const app = Fastify({ logger: false });
  app.get("/internal/health/live", async () => ({ status: "ok" }));
  app.get("/internal/health/ready", async (_, reply) => {
    const state = await deps.readiness();
    return Object.values(state).every(Boolean) ? { status: "ready", dependencies: state } : reply.code(503).send({ status: "degraded", dependencies: state });
  });
  return app;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `Set-Location openmaic-service; npx vitest run tests/health.test.ts; npx tsc --noEmit; npm run build`
Expected: all commands exit 0.

- [ ] **Step 5: Commit**

```powershell
git add openmaic-service
git commit -m "feat: add managed OpenMAIC runtime"
```

### Task 3: 实现内部断言与重放保护

**Files:**
- Create: `backend/app/services/openmaic/service_assertion.py`
- Test: `backend/tests/test_openmaic_service_assertion.py`
- Create: `openmaic-service/src/auth/serviceAssertion.ts`
- Test: `openmaic-service/tests/serviceAssertion.test.ts`
- Modify: `backend/.env.example`
- Modify: `openmaic-service/.env.example`

**Interfaces:**
- Consumes: `user_id: str`、`course_id: str`、`scopes: list[str]`、共享 secret。
- Produces: Python `issue_service_assertion(*, user_id, course_id, scopes, now) -> str`；TypeScript `verifyServiceAssertion(token, expectedCourseId, requiredScopes, now): AssertionClaims`。

- [ ] **Step 1: Write the failing tests**

```python
def test_assertion_is_short_lived():
    token = issue_service_assertion(user_id="u1", course_id="c1", scopes=["stage:read"], now=100)
    claims = decode_for_test(token)
    assert claims["exp"] - claims["iat"] <= 60
```

```ts
it("rejects a replayed jti", () => {
  const token = fixtureToken({ jti: "once" });
  verifyServiceAssertion(token, "c1", ["stage:read"], 100);
  expect(() => verifyServiceAssertion(token, "c1", ["stage:read"], 100)).toThrow(/replay/i);
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_openmaic_service_assertion.py -q`
Run: `Set-Location openmaic-service; npx vitest run tests/serviceAssertion.test.ts`
Expected: both fail because assertion functions are missing.

- [ ] **Step 3: Write minimal implementation**

```python
def issue_service_assertion(*, user_id, course_id, scopes, now):
    claims = {"iss": "campusmate-backend", "aud": "openmaic-service", "sub": user_id,
              "course_id": course_id, "scope": scopes, "iat": now, "exp": now + 60,
              "jti": secrets.token_urlsafe(18)}
    return sign_hs256(claims, settings.openmaic_internal_secret)
```

```ts
export function verifyServiceAssertion(token: string, courseId: string, scopes: string[], now: number) {
  const claims = verifyHs256(token, config.internalSecret);
  assertClaims(claims, courseId, scopes, now);
  replayStore.consume(claims.jti, claims.exp);
  return claims;
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_openmaic_service_assertion.py -q`
Run: `Set-Location openmaic-service; npx vitest run tests/serviceAssertion.test.ts`
Expected: both exit 0 and cover tampering, expiry, course mismatch, missing scope and replay.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/services/openmaic/service_assertion.py backend/tests/test_openmaic_service_assertion.py backend/.env.example openmaic-service
git commit -m "feat: secure internal OpenMAIC calls"
```

### Task 4: 接入状态代理与功能开关

**Files:**
- Create: `backend/app/api/routes/openmaic_fusion.py`
- Create: `backend/app/schemas/openmaic_fusion.py`
- Create: `backend/app/services/openmaic/fusion_client.py`
- Test: `backend/tests/test_openmaic_fusion_status.py`
- Modify: `backend/app/main.py`
- Modify: `backend/.env.example`

**Interfaces:**
- Consumes: Task 2 readiness endpoints and Task 3 `issue_service_assertion`。
- Produces: `GET /api/v1/openmaic/fusion/status -> FusionStatus(enabled, available, capabilities, reason)`。

- [ ] **Step 1: Write the failing test**

```python
def test_disabled_status_does_not_call_node(client, monkeypatch):
    monkeypatch.setenv("OPENMAIC_FUSION_ENABLED", "false")
    response = client.get("/api/v1/openmaic/fusion/status", headers=auth_headers())
    assert response.status_code == 200
    assert response.json()["data"] == {"enabled": False, "available": False, "capabilities": [], "reason": "disabled"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_openmaic_fusion_status.py -q`
Expected: FAIL with 404 for the missing route.

- [ ] **Step 3: Write minimal implementation**

```python
@router.get("/status", response_model=ApiResponse[FusionStatus])
async def fusion_status(user=Depends(current_user), client=Depends(get_fusion_client)):
    if not settings.openmaic_fusion_enabled:
        return ok(FusionStatus(enabled=False, available=False, capabilities=[], reason="disabled"))
    return ok(await client.status(user_id=str(user.id)))
```

Map timeout to `available=false, reason="service_unavailable"`; do not return 500 or leak the internal URL.

- [ ] **Step 4: Run test to verify it passes**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_openmaic_fusion_status.py backend/tests/test_openmaic_classroom.py -q`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/api/routes/openmaic_fusion.py backend/app/schemas/openmaic_fusion.py backend/app/services/openmaic/fusion_client.py backend/app/main.py backend/.env.example backend/tests/test_openmaic_fusion_status.py
git commit -m "feat: expose OpenMAIC fusion readiness"
```
