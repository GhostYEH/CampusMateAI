# OpenMAIC Fusion 05 Materials, Media, and Agents Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` (recommended) or `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付材料处理、检索、导入导出、生成模式、Web 搜索、TTS、ASR、多智能体和 Provider 设置。

**Architecture:** 文件和外部网络操作在 Node 服务执行；FastAPI 负责授权；Web 只展示任务状态和受控下载。Provider 通过接口注入，测试使用契约替身。

**Tech Stack:** TypeScript、Fastify、Vitest、对象存储接口、FastAPI、pytest、React 18、Node test runner。

**Spec:** `docs/superpowers/specs/2026-09-18-openmaic-campus-fusion-design.md`

## Global Constraints

- 必须先完成计划 03—04；材料、job 和资产都绑定 user/course/stage。
- 文件类型、大小、解压比例、路径和外部 URL 必须由服务端校验。
- Provider 密钥永不回传，Web 搜索必须保留来源和检索时间。
- 默认测试不连接真实 Provider、搜索、TTS 或 ASR 服务。

---

### Task 1: 材料上传、解析、检索和 UI

**Files:**
- Create: `openmaic-service/src/domain/material.ts`
- Create: `openmaic-service/src/services/materialService.ts`
- Create: `openmaic-service/src/services/searchService.ts`
- Create: `openmaic-service/src/routes/materials.ts`
- Test: `openmaic-service/tests/materials.test.ts`
- Test: `backend/tests/test_openmaic_fusion_materials.py`
- Modify: `backend/app/api/routes/openmaic_fusion.py`
- Modify: `backend/app/services/openmaic/fusion_client.py`
- Create: `webreact/src/features/openmaic/materials/MaterialsPanel.jsx`
- Test: `webreact/tests/openmaic-materials.test.mjs`
- Modify: `webreact/src/features/openmaic/workbench/WorkbenchShell.jsx`
- Modify: `webreact/src/data/api.js`

**Interfaces:**
- Consumes: authorized StageBinding and object storage abstraction。
- Produces: `createMaterial(stageId,file) -> MaterialJob`；`searchMaterials(stageId,query) -> MaterialHit[]`；public upload/status/search routes；`MaterialsPanel({stageId})`。

- [ ] **Step 1: Write the failing tests**

```ts
it("rejects an oversized file before object storage", async () => {
  await expect(service.createMaterial(owner, file({ size: limits.maxBytes + 1 }))).rejects.toMatchObject({ statusCode: 413 });
  expect(storage.put).not.toHaveBeenCalled();
});
```

```python
def test_assignment_attachment_requires_course_access(client):
    response = upload_material(client, stage_id="s1", attachment_id="other-course")
    assert response.status_code == 403
```

```js
test("failed parsing remains retryable", () => {
  assert.deepEqual(materialActions({ status: "failed" }), ["retry", "remove"]);
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `Set-Location openmaic-service; npx vitest run tests/materials.test.ts`
Run from repository root: `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_openmaic_fusion_materials.py -q`
Run: `Set-Location webreact; node --test tests/openmaic-materials.test.mjs`
Expected: all fail because material services and UI are missing.

- [ ] **Step 3: Write minimal implementation**

```ts
export async function createMaterial(principal: Principal, input: UploadInput) {
  assertAllowedMime(input.mimeType);
  assertWithinLimit(input.size, config.maxUploadBytes);
  const key = objectKey(principal.userId, principal.courseId, randomUUID());
  await storage.put(key, input.stream);
  return jobs.enqueue({ kind: "material.parse", stageId: input.stageId, key });
}
```

Implement queued/running/completed/failed states, deterministic parser fixtures, cited hits, FastAPI authorization, and an accessible panel with upload progress, source hits and retry/remove controls.

- [ ] **Step 4: Run tests to verify they pass**

Run: `Set-Location openmaic-service; npx vitest run tests/materials.test.ts`
Run from repository root: `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_openmaic_fusion_materials.py -q`
Run: `Set-Location webreact; node --test tests/openmaic-materials.test.mjs; npm run build`
Expected: tests and build pass.

- [ ] **Step 5: Commit**

```powershell
git add openmaic-service backend/app backend/tests/test_openmaic_fusion_materials.py webreact/src webreact/tests/openmaic-materials.test.mjs
git commit -m "feat: add authorized OpenMAIC materials"
```

### Task 2: 导入、导出和传输 UI

**Files:**
- Create: `openmaic-service/src/services/importService.ts`
- Create: `openmaic-service/src/services/exportService.ts`
- Create: `openmaic-service/src/routes/transfers.ts`
- Test: `openmaic-service/tests/transfers.test.ts`
- Create: `openmaic-render-service/package.json`
- Create: `openmaic-render-service/src/server.ts`
- Test: `openmaic-render-service/tests/renderJob.test.ts`
- Test: `backend/tests/test_openmaic_fusion_transfers.py`
- Modify: `backend/app/api/routes/openmaic_fusion.py`
- Create: `webreact/src/features/openmaic/materials/TransferPanel.jsx`
- Test: `webreact/tests/openmaic-transfer.test.mjs`
- Modify: `webreact/src/data/api.js`

**Interfaces:**
- Consumes: StageDocument, command service, object storage and job repository。
- Produces: PPTX and classroom/skill package imports；PPTX、PDF/image、self-contained HTML、classroom ZIP、script MD/DOCX and MP4 exports；`TransferPanel({stageId,capabilities})`；internal `POST /internal/render-jobs`。

- [ ] **Step 1: Write the failing test**

```ts
it("rejects a project package containing zip slip", async () => {
  await expect(importer.projectPackage(fixture("zip-slip.zip"))).rejects.toMatchObject({ code: "unsafe_archive_path" });
});

it("creates one authenticated render job without accepting browser auth", async () => {
  const response = await renderer.inject({ method: "POST", url: "/internal/render-jobs", headers: renderAssertion(), payload: manifest });
  expect(response.statusCode).toBe(202);
  expect((await renderer.inject({ method: "POST", url: "/internal/render-jobs", headers: { authorization: "Bearer campus-user" }, payload: manifest })).statusCode).toBe(401);
});
```

```python
def test_export_download_is_bound_to_the_requesting_user(client):
    response = client.get("/api/v1/openmaic/exports/job-u2/download", headers=auth_headers("u1"))
    assert response.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `Set-Location openmaic-service; npx vitest run tests/transfers.test.ts`
Run: `Set-Location openmaic-render-service; npx vitest run tests/renderJob.test.ts`
Run: `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_openmaic_fusion_transfers.py -q`
Run: `Set-Location webreact; node --test tests/openmaic-transfer.test.mjs`
Expected: missing converter, routes and panel fail.

- [ ] **Step 3: Write minimal implementation**

```ts
export function safeArchivePath(entry: string) {
  const normalized = posix.normalize(entry);
  if (normalized.startsWith("../") || posix.isAbsolute(normalized)) throw new TransferError("unsafe_archive_path");
  return normalized;
}
```

Port the pinned upstream PPTX/classroom-package importers and every audited exporter behind restricted workers. Validate manifest/version/decompression ratio, inline offline assets for HTML/ZIP, run Chromium/FFmpeg only in `openmaic-render-service`, issue user-bound short download URLs, and expose job progress/cancel/download in TransferPanel.

- [ ] **Step 4: Run tests to verify they pass**

Run: `Set-Location openmaic-service; npx vitest run tests/transfers.test.ts; npx tsc --noEmit; npm run build`
Run: `Set-Location openmaic-render-service; npx vitest run tests/renderJob.test.ts; npx tsc --noEmit; npm run build`
Run from repository root: `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_openmaic_fusion_transfers.py -q`
Run: `Set-Location webreact; node --test tests/openmaic-transfer.test.mjs; npm run build`
Expected: PPTX and package imports, seven export families, MP4 authentication/cancellation, archive security, offline asset inlining, package round-trip and UI cleanup pass.

- [ ] **Step 5: Commit**

```powershell
git add openmaic-service openmaic-render-service backend/app backend/tests/test_openmaic_fusion_transfers.py webreact/src webreact/tests/openmaic-transfer.test.mjs
git commit -m "feat: port OpenMAIC transfer workflows"
```

### Task 3: 生成模式、Web 搜索和多智能体

**Files:**
- Create: `openmaic-service/src/providers/provider.ts`
- Create: `openmaic-service/src/providers/contractProvider.ts`
- Create: `openmaic-service/src/tools/webSearch.ts`
- Create: `openmaic-service/src/agents/orchestrator.ts`
- Create: `openmaic-service/src/services/outlineService.ts`
- Create: `openmaic-service/src/services/learnerRuntimeService.ts`
- Create: `openmaic-service/src/services/mediaGenerationService.ts`
- Test: `openmaic-service/tests/generationAgents.test.ts`
- Modify: `openmaic-service/src/services/runService.ts`
- Create: `webreact/src/features/openmaic/workbench/SceneKindPicker.jsx`
- Test: `webreact/tests/openmaic-scene-kinds.test.mjs`
- Modify: `webreact/src/features/openmaic/workbench/ConversationPanel.jsx`

**Interfaces:**
- Consumes: FusionSession, FusionEvent and Stage command service。
- Produces: `Provider.generate(request,signal): AsyncIterable<ProviderEvent>`；scene kinds `slide|quiz|interactive|pbl`；interactive widgets `visualization-3d|simulation|game|mind-map|online-code|procedural-skill`；`orchestrate(run,signal)`；learner quiz/PBL runtime；image/video asset generation；`SceneKindPicker`。

- [ ] **Step 1: Write the failing test**

```ts
it.each(["slide", "quiz", "interactive", "pbl"])("turns %s output into stage commands", async (mode) => {
  const result = await orchestrator.run({ mode, prompt: "fixture", provider: contractProvider });
  expect(result.commands.length).toBeGreaterThan(0);
  expect(result.events.at(-1)?.type).toBe("message.completed");
});

test("scene picker exposes every supported kind", () => {
  assert.deepEqual(sceneKindOptions.map((item) => item.value), ["auto", "slide", "quiz", "interactive", "pbl"]);
});

it.each(["visualization-3d", "simulation", "game", "mind-map", "online-code", "procedural-skill"])("persists %s learner state", async (widget) => {
  const runtime = await learnerRuntime.open({ stageId: "s1", sceneId: "scene-1", widget });
  await runtime.append({ type: "learner.progress", data: { value: 1 } });
  expect(await learnerRuntime.resume(runtime.id)).toMatchObject({ lastSequence: 1 });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `Set-Location openmaic-service; npx vitest run tests/generationAgents.test.ts`
Run from repository root: `Set-Location webreact; node --test tests/openmaic-scene-kinds.test.mjs`
Expected: FAIL because provider, orchestrator and picker are missing.

- [ ] **Step 3: Write minimal implementation**

```ts
export interface Provider {
  generate(request: GenerationRequest, signal: AbortSignal): AsyncIterable<ProviderEvent>;
}

export async function runAgent(request: GenerationRequest, signal: AbortSignal) {
  for await (const event of provider.generate(request, signal)) await eventSink.append(mapProviderEvent(event));
}
```

Port the pinned upstream two-stage outline pipeline, slide/quiz/interactive/PBL generation, all six interactive widgets, quiz grading, PBL v2 roles/tasks/milestones/evaluation, classroom discussion/debate/free-Q&A, image/video tools and provider-neutral orchestration. Preserve cited Web results, enforce tool timeout/search switch, propagate cancellation, and pass `sceneKind` from the picker into `SessionMessageRequest` while keeping session `mode` as standard/deep.

- [ ] **Step 4: Run test to verify it passes**

Run: `Set-Location openmaic-service; npx vitest run tests/generationAgents.test.ts tests/sessions.test.ts; npx tsc --noEmit`
Run from repository root: `Set-Location webreact; node --test tests/openmaic-scene-kinds.test.mjs; npm run build`
Expected: generation, picker, citations, timeout, rate limit, child failure and cancellation tests pass.

- [ ] **Step 5: Commit**

```powershell
git add openmaic-service/src openmaic-service/tests/generationAgents.test.ts webreact/src/features/openmaic/workbench/SceneKindPicker.jsx webreact/src/features/openmaic/workbench/ConversationPanel.jsx webreact/tests/openmaic-scene-kinds.test.mjs
git commit -m "feat: port OpenMAIC generation agents"
```

### Task 4: TTS、ASR 与 Provider 设置

**Files:**
- Create: `openmaic-service/src/services/speechService.ts`
- Create: `openmaic-service/src/services/voiceProfileService.ts`
- Create: `openmaic-service/src/routes/settings.ts`
- Test: `openmaic-service/tests/speechSettings.test.ts`
- Test: `backend/tests/test_openmaic_fusion_settings.py`
- Modify: `backend/app/api/routes/openmaic_fusion.py`
- Create: `webreact/src/features/openmaic/settings/OpenMaicSettings.jsx`
- Test: `webreact/tests/openmaic-settings-speech.test.mjs`
- Modify: `webreact/src/features/openmaic/workbench/ConversationPanel.jsx`
- Modify: `webreact/src/data/api.js`

**Interfaces:**
- Consumes: object storage, provider secret store and admin authorization。
- Produces: `synthesize(text,voice,speed)`、`transcribe(audio)`、`createVoiceProfile(referenceAudio,consent)`、LLM/image/video/TTS/ASR/search/render capability settings；Web record/speak/voice/settings controls。

- [ ] **Step 1: Write the failing tests**

```ts
it("does not return provider secrets", async () => {
  await settings.save({ provider: "fixture", apiKey: "secret-value" });
  expect(await settings.summary()).toEqual({ provider: "fixture", configured: true });
});

it("requires explicit consent before cloning a voice", async () => {
  await expect(voices.create(referenceAudio(), { consent: false })).rejects.toMatchObject({ statusCode: 422 });
});
```

```python
def test_student_cannot_read_provider_settings(client):
    assert client.get("/api/v1/admin/openmaic/settings", headers=student_headers()).status_code == 403
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `Set-Location openmaic-service; npx vitest run tests/speechSettings.test.ts`
Run from repository root: `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_openmaic_fusion_settings.py -q`
Run from repository root: `Set-Location webreact; node --test tests/openmaic-settings-speech.test.mjs`
Expected: all fail because services and controls are missing.

- [ ] **Step 3: Write minimal implementation**

```ts
export async function settingsSummary() {
  const config = await secretStore.readProvider();
  return { provider: config.provider, configured: Boolean(config.apiKey), model: config.model };
}
```

Implement TTS cache key from text/voice/speed, parallel scene synthesis with cancellation, consent-bound voice profiles, bounded ASR upload, audio URL SSRF/DNS-rebinding protection, provider/model routing for LLM/image/video/TTS/ASR/search/render, capability force-off, admin-only mutation, permission-denied UI and secret-free responses/logs.

- [ ] **Step 4: Run tests to verify they pass**

Run: `Set-Location openmaic-service; npx vitest run tests/speechSettings.test.ts; npx tsc --noEmit; npm run build`
Run from repository root: `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_openmaic_fusion_settings.py -q`
Run: `Set-Location webreact; node --test tests/openmaic-settings-speech.test.mjs; npm run build`
Expected: security, cache, permissions, recording failure and build checks pass.

- [ ] **Step 5: Commit**

```powershell
git add openmaic-service backend/app backend/tests/test_openmaic_fusion_settings.py webreact/src webreact/tests/openmaic-settings-speech.test.mjs
git commit -m "feat: add OpenMAIC speech and provider settings"
```

### Task 5: 异步 Job API、国际化与主题

**Files:**
- Create: `openmaic-service/src/routes/jobs.ts`
- Test: `openmaic-service/tests/jobs.test.ts`
- Test: `backend/tests/test_openmaic_fusion_jobs.py`
- Modify: `backend/app/api/routes/openmaic_fusion.py`
- Modify: `backend/app/services/openmaic/fusion_client.py`
- Create: `webreact/src/features/openmaic/i18n/catalogs.js`
- Create: `webreact/src/features/openmaic/i18n/useOpenMaicLocale.js`
- Test: `webreact/tests/openmaic-i18n-theme.test.mjs`
- Modify: `webreact/src/features/openmaic/openmaic.css`

**Interfaces:**
- Consumes: generation/session service, CampusMate user identity, active locale and theme tokens。
- Produces: public job submit/status/cancel routes for the audited OpenMAIC Skill contract；catalogs for zh-CN/zh-TW/en-US/ja-JP/ko-KR/ru-RU/ar-SA/pt-BR/es-MX/fr-FR/vi-VN/de-DE；light/dark/responsive theme parity。

- [ ] **Step 1: Write the failing tests**

```ts
it("keeps a job bound to its submitting user", async () => {
  const job = await jobs.submit(owner("u1"), requestFixture());
  await expect(jobs.get(owner("u2"), job.id)).rejects.toMatchObject({ statusCode: 404 });
});
```

```js
test("every upstream locale has the required workbench keys", () => {
  for (const locale of supportedLocales) assert.deepEqual(Object.keys(catalogs[locale]).sort(), requiredKeys);
  assert.match(openMaicCss, /prefers-color-scheme|data-theme/);
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `Set-Location openmaic-service; npx vitest run tests/jobs.test.ts`
Run from repository root: `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_openmaic_fusion_jobs.py -q`
Run from repository root: `Set-Location webreact; node --test tests/openmaic-i18n-theme.test.mjs`
Expected: missing job routes and locale catalogs fail.

- [ ] **Step 3: Write minimal implementation**

```ts
export async function submitJob(principal: Principal, request: JobRequest) {
  const binding = await bindings.require(principal.userId, request.courseId);
  return jobs.insert({ ownerId: principal.userId, stageId: binding.stageId, status: "queued", request });
}
```

```js
export function useOpenMaicLocale() {
  const locale = useCampusLocale();
  const catalog = catalogs[locale] ?? catalogs["zh-CN"];
  return (key) => catalog[key] ?? catalogs["en-US"][key] ?? key;
}
```

Match the audited async Skill request/poll/cancel contract, hide cross-user jobs, port all upstream user-facing keys, inherit CampusMate appearance, preserve RTL direction, and test 320/768/1024/1440 widths.

- [ ] **Step 4: Run tests to verify they pass**

Run: `Set-Location openmaic-service; npx vitest run tests/jobs.test.ts; npx tsc --noEmit`
Run from repository root: `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_openmaic_fusion_jobs.py -q`
Run from repository root: `Set-Location webreact; node --test tests/openmaic-i18n-theme.test.mjs; npm run build`
Expected: job ownership/cancel, catalog parity, RTL, dark mode and four viewport contracts pass.

- [ ] **Step 5: Commit**

```powershell
git add openmaic-service/src/routes/jobs.ts openmaic-service/tests/jobs.test.ts backend/app backend/tests/test_openmaic_fusion_jobs.py webreact/src/features/openmaic/i18n webreact/src/features/openmaic/openmaic.css webreact/tests/openmaic-i18n-theme.test.mjs
git commit -m "feat: preserve OpenMAIC jobs and locale parity"
```
