# OpenMAIC Fusion 07 Persistence and Acceptance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` (recommended) or `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Use `verification-before-completion` before any completion claim.

**Goal:** 替换临时 repository，补齐健康、可观测、安全和端到端验收，并逐项关闭能力矩阵。

**Architecture:** OpenMAIC 使用独立 PostgreSQL schema 和对象存储；受管启动脚本按依赖顺序拉起；验收从浏览器到 FastAPI、Node 和契约 Provider 全链路运行。

**Tech Stack:** PostgreSQL、TypeScript migrations、Fastify、Vitest、FastAPI、pytest、React、Playwright。

**Spec:** `docs/superpowers/specs/2026-09-18-openmaic-campus-fusion-design.md`

## Global Constraints

- 必须先完成计划 01—06；不得改变已冻结公开契约。
- OpenMAIC 数据放在独立 PostgreSQL schema，不修改 CampusMate 数据库结构。
- 启动文件使用仓库相对路径，不写本机盘符、用户名或局域网地址。
- 只有具备自动化或明确人工证据的能力才能标记 `verified`。

---

### Task 1: PostgreSQL 与对象存储持久化

**Files:**
- Create: `openmaic-service/src/db/migrations/001_openmaic_fusion.ts`
- Create: `openmaic-service/src/repositories/postgresBindingRepository.ts`
- Create: `openmaic-service/src/repositories/postgresSessionRepository.ts`
- Create: `openmaic-service/src/repositories/postgresStageRepository.ts`
- Create: `openmaic-service/src/repositories/postgresJobRepository.ts`
- Create: `openmaic-service/src/storage/objectStorage.ts`
- Test: `openmaic-service/tests/persistence.integration.test.ts`
- Modify: `openmaic-service/src/server.ts`

**Interfaces:**
- Consumes: repository interfaces from plans 02—05。
- Produces: PostgreSQL implementations for binding/session/event/stage/command/job/provider config and `ObjectStorage` with `put/get/delete/signedDownload`。

- [ ] **Step 1: Write the failing test**

```ts
it("restores a stage and event cursor after server restart", async () => {
  const first = await fixtureServer(databaseUrl);
  await first.seedStageAndEvent({ stageId: "s1", revision: 3, sequence: 9 });
  await first.close();
  const second = await fixtureServer(databaseUrl);
  expect(await second.stages.get("s1")).toMatchObject({ revision: 3 });
  expect(await second.sessions.listEvents("session-1", 8)).toHaveLength(1);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `Set-Location openmaic-service; npx vitest run tests/persistence.integration.test.ts`
Expected: FAIL because PostgreSQL repositories do not exist.

- [ ] **Step 3: Write minimal implementation**

```ts
export class PostgresStageRepository implements StageRepository {
  async transaction<T>(stageId: string, work: (doc: StageDocument) => Promise<T>) {
    return this.db.transaction(async (tx) => {
      const row = await tx.one("select document from openmaic.stage where id=$1 for update", [stageId]);
      return work(parseStage(row.document));
    });
  }
}
```

Create idempotent migration tables and constraints, make command revision/event writes atomic, wire repositories by configuration, and keep memory repositories for unit tests.

- [ ] **Step 4: Run test to verify it passes**

Run: `Set-Location openmaic-service; npx vitest run tests/persistence.integration.test.ts; npx tsc --noEmit`
Expected: migration, repeated migration, restart, uniqueness, concurrency and object compensation tests pass.

- [ ] **Step 5: Commit**

```powershell
git add openmaic-service
git commit -m "feat: persist OpenMAIC fusion state"
```

### Task 2: 健康、启动与可观测

**Files:**
- Create: `openmaic-service/src/observability/logger.ts`
- Test: `openmaic-service/tests/observability.test.ts`
- Create: `start_openmaic.bat`
- Create: `start_all.bat`
- Modify: `openmaic-service/src/routes/health.ts`
- Modify: `openmaic-render-service/src/server.ts`
- Modify: `openmaic-service/.env.example`
- Modify: `backend/.env.example`
- Modify: `README.md`

**Interfaces:**
- Consumes: database/objectStorage/provider/render-service health and repository root paths。
- Produces: structured `createLogger(redactionRules)`；dependency readiness；repo-relative managed startup commands。

- [ ] **Step 1: Write the failing test**

```ts
it("redacts credentials and keeps correlation fields", () => {
  const line = captureLog({ request_id: "r1", user_id: "u1", authorization: "Bearer secret", material: "private body" });
  expect(line).toContain('"request_id":"r1"');
  expect(line).not.toContain("secret");
  expect(line).not.toContain("private body");
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `Set-Location openmaic-service; npx vitest run tests/observability.test.ts`
Expected: FAIL because the redacting logger is missing.

- [ ] **Step 3: Write minimal implementation**

```ts
export const loggerOptions = {
  redact: ["req.headers.authorization", "assertion", "providerKey", "material"],
  serializers: { req: (req: RequestContext) => pick(req, ["request_id", "user_id", "course_id", "stage_id", "session_id"]) }
};
```

Add live/ready dependency details, graceful shutdown, `start_openmaic.bat` based on `%~dp0`, `start_all.bat` in database/object storage → render service → OpenMAIC service → FastAPI → Web order, and matching README commands.

- [ ] **Step 4: Run test to verify it passes**

Run: `Set-Location openmaic-service; npx vitest run tests/observability.test.ts; npm test; npx tsc --noEmit; npm run build`
Expected: all commands pass; manual local start shows degraded then ready status as dependencies change.

- [ ] **Step 5: Commit**

```powershell
git add openmaic-service start_openmaic.bat start_all.bat backend/.env.example README.md
git commit -m "ops: manage OpenMAIC fusion runtime"
```

### Task 3: 安全与回归门禁

**Files:**
- Test: `backend/tests/test_openmaic_fusion_security.py`
- Test: `openmaic-service/tests/security.test.ts`
- Test: `openmaic-render-service/tests/security.test.ts`
- Test: `webreact/tests/openmaic-security-boundary.test.mjs`
- Modify: `backend/app/services/openmaic/service_assertion.py`
- Modify: `backend/app/services/openmaic/redaction.py`
- Modify: `backend/app/services/openmaic/fusion_client.py`
- Modify: `openmaic-service/src/auth/serviceAssertion.ts`
- Modify: `openmaic-service/src/services/importService.ts`
- Modify: `openmaic-service/src/services/speechService.ts`
- Modify: `webreact/src/features/openmaic/editor/renderers.jsx`
- Modify: `webreact/src/App.jsx`

**Interfaces:**
- Consumes: complete public/internal surface from plans 01—06。
- Produces: permanent regression coverage for authorization, assertions, files, URLs, HTML, secrets and browser runtime boundaries。

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.parametrize("case", ["cross_user", "cross_course", "expired_assertion", "missing_scope", "replayed_jti"])
def test_security_boundary_rejects_case(case, security_client):
    assert security_client.attempt(case).status_code in {401, 403, 404}
```

```ts
it.each(["loopback", "private-ip", "dns-rebind"])("blocks %s audio URLs", async (fixtureName) => {
  await expect(fetchAudio(urlFixture(fixtureName))).rejects.toMatchObject({ code: "unsafe_url" });
});
```

```js
test("browser boundary has one React and no whole-app iframe", () => {
  assert.equal(reactMajorVersions(packageGraph), 1);
  assert.doesNotMatch(openMaicSources, /<iframe[^>]+src=.*openmaic/i);
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_openmaic_fusion_security.py -q`
Run: `Set-Location openmaic-service; npx vitest run tests/security.test.ts`
Run from repository root: `Set-Location openmaic-render-service; npx vitest run tests/security.test.ts`
Run from repository root: `Set-Location webreact; node --test tests/openmaic-security-boundary.test.mjs`
Expected: at least one assertion fails, demonstrating the uncovered boundary before the fix.

- [ ] **Step 3: Write minimal implementation**

For each failure, patch the narrow guard selected by the assertion. Example URL guard:

```ts
const addresses = await resolver.lookup(hostname, { all: true });
if (addresses.some(({ address }) => isPrivateOrLoopback(address))) throw new SecurityError("unsafe_url");
```

Do not weaken expected status codes or remove fixtures. Add the exact production path to the task commit only after its test fails.

- [ ] **Step 4: Run test to verify it passes**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_openmaic_fusion_security.py backend/tests/test_openmaic_*.py -q`
Run: `Set-Location openmaic-service; npx vitest run tests/security.test.ts`
Run from repository root: `Set-Location openmaic-render-service; npx vitest run tests/security.test.ts`
Run from repository root: `Set-Location webreact; node --test tests/openmaic-security-boundary.test.mjs`
Expected: all security and existing OpenMAIC backend tests pass.

- [ ] **Step 5: Commit**

```powershell
git add backend/tests/test_openmaic_fusion_security.py openmaic-service/tests/security.test.ts openmaic-render-service/tests/security.test.ts webreact/tests/openmaic-security-boundary.test.mjs
git add backend/app/services/openmaic/service_assertion.py backend/app/services/openmaic/redaction.py backend/app/services/openmaic/fusion_client.py
git add openmaic-service/src/auth/serviceAssertion.ts openmaic-service/src/services/importService.ts openmaic-service/src/services/speechService.ts
git add webreact/src/features/openmaic/editor/renderers.jsx webreact/src/App.jsx
git commit -m "fix: enforce OpenMAIC fusion boundaries"
```

### Task 4: E2E、能力矩阵与发布候选

**Files:**
- Create: `webreact/tests/e2e/openmaic_fusion_golden_path.py`
- Create: `webreact/tests/e2e/openmaic_fusion_failure_modes.py`
- Create: `webreact/tests/e2e/_seed_openmaic_fusion.py`
- Modify: `docs/superpowers/specs/2026-09-18-openmaic-campus-fusion-design.md`

**Interfaces:**
- Consumes: full local stack and contract provider。
- Produces: deterministic seed/cleanup, golden-path and failure-mode E2E, and the single authoritative verified capability matrix。

- [ ] **Step 1: Write the failing test**

```python
def test_course_question_to_assignment_explanation(page, seeded_course):
    page.goto("/courses")
    page.get_by_role("complementary", name="我的课程").get_by_text(seeded_course.name).click()
    page.get_by_placeholder("输入你想了解的内容").fill("解释第一章")
    page.get_by_role("button", name="发送").click()
    expect(page.get_by_text("生成完成")).to_be_visible()
    page.goto(seeded_course.assignment_url)
    page.get_by_role("button", name="开始讲解").click()
    expect(page.get_by_role("button", name="播放讲解")).to_be_visible()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `backend\.venv\Scripts\python.exe webreact/tests/e2e/openmaic_fusion_golden_path.py`
Expected: FAIL until deterministic seed and all workflow selectors are wired.

- [ ] **Step 3: Write minimal implementation**

```python
@contextmanager
def seeded_openmaic_course(api):
    fixture = api.create_fixture(provider="contract", include_assignment=True)
    try:
        yield fixture
    finally:
        api.delete_fixture(fixture.id)
```

Cover course ask, stream, refresh, outline/edit-with-AI/playback actions, quiz/PBL learner state, all interactive widgets, upload/parsing, every import/export format including MP4, media/voice generation, async jobs, locales/themes, assignment explain, dependency outage and revoked permission. Map each of the 89 matrix rows to a named test or recorded manual check; change only evidenced rows to `verified`.

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
backend\.venv\Scripts\python.exe webreact/tests/e2e/openmaic_fusion_golden_path.py
backend\.venv\Scripts\python.exe webreact/tests/e2e/openmaic_fusion_failure_modes.py
backend\.venv\Scripts\python.exe -m pytest backend/tests/test_openmaic_*.py -q
Set-Location openmaic-service; npm test; npx tsc --noEmit; npm run build
Set-Location ..\openmaic-render-service; npm test; npx tsc --noEmit; npm run build
Set-Location ..\webreact; node --test tests/openmaic-*.test.mjs; npm run build
```

Expected: every command exits 0; no screenshot, upload, local database or log artifact is tracked.

- [ ] **Step 5: Commit**

```powershell
git add webreact/tests/e2e/openmaic_fusion_golden_path.py webreact/tests/e2e/openmaic_fusion_failure_modes.py webreact/tests/e2e/_seed_openmaic_fusion.py docs/superpowers/specs/2026-09-18-openmaic-campus-fusion-design.md
git commit -m "test: verify complete OpenMAIC fusion"
```
