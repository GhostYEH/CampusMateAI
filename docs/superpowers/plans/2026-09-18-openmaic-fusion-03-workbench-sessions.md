# OpenMAIC Fusion 03 Workbench and Sessions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` (recommended) or `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付与课程绑定的工作台、持久会话、消息运行、SSE 恢复、取消和重试。

**Architecture:** 浏览器只连接 FastAPI；FastAPI 校验 session 所属用户和课程后代理 Node；Node 维护 session、run 和有序事件 repository。

**Tech Stack:** React 18、streaming fetch、FastAPI StreamingResponse、Fastify、Vitest、pytest、Node test runner。

**Spec:** `docs/superpowers/specs/2026-09-18-openmaic-campus-fusion-design.md`

## Global Constraints

- 必须先完成计划 01—02，并复用 StageBinding。
- SSE 支持 `Last-Event-ID`，sequence 对同一 session 单调递增。
- 浏览器断开只关闭代理流，不隐式取消服务端运行。
- 自动化测试只用确定性 contract provider。

---

### Task 1: 会话与运行领域模型

**Files:**
- Create: `openmaic-service/src/domain/session.ts`
- Create: `openmaic-service/src/repositories/sessionRepository.ts`
- Create: `openmaic-service/src/services/runService.ts`
- Create: `openmaic-service/src/routes/sessions.ts`
- Test: `openmaic-service/tests/sessions.test.ts`

**Interfaces:**
- Consumes: `StageBinding` and verified `AssertionClaims` from prior plans。
- Produces: `createSession(userId,courseId,stageId,mode)`、`appendMessage(sessionId,{commandId,content,sceneKind})`、`listEvents(sessionId,afterSequence)`、`cancelRun(sessionId)`、`retryRun(sessionId,failedRunId)`。

- [ ] **Step 1: Write the failing test**

```ts
it("deduplicates a message command and preserves event order", async () => {
  const session = await service.createSession("u1", "c1", "s1", "standard");
  const message = { commandId: "cmd-1", content: "hello", sceneKind: "auto" };
  const first = await service.appendMessage(session.id, message);
  const second = await service.appendMessage(session.id, message);
  expect(second.runId).toBe(first.runId);
  expect((await service.listEvents(session.id, 0)).map((e) => e.sequence)).toEqual([1, 2]);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `Set-Location openmaic-service; npx vitest run tests/sessions.test.ts`
Expected: FAIL because `runService` does not exist.

- [ ] **Step 3: Write minimal implementation**

```ts
export async function appendMessage(sessionId: string, message: SessionMessageRequest) {
  const prior = await repo.findRunByCommand(sessionId, message.commandId);
  if (prior) return prior;
  return repo.transaction(async (tx) => {
    const run = await tx.createRun(sessionId, message);
    await tx.appendEvent(sessionId, "tool.started", { runId: run.id });
    return run;
  });
}
```

Implement ownership checks, contract-provider deltas, terminal states, cancel propagation and retry from the failed input snapshot.

- [ ] **Step 4: Run test to verify it passes**

Run: `Set-Location openmaic-service; npx vitest run tests/sessions.test.ts; npx tsc --noEmit`
Expected: tests pass for isolation, ordering, idempotency, cancel and retry.

- [ ] **Step 5: Commit**

```powershell
git add openmaic-service/src openmaic-service/tests/sessions.test.ts
git commit -m "feat: model OpenMAIC sessions and runs"
```

### Task 2: FastAPI 会话网关与 SSE

**Files:**
- Test: `backend/tests/test_openmaic_fusion_sessions.py`
- Modify: `backend/app/api/routes/openmaic_fusion.py`
- Modify: `backend/app/schemas/openmaic_fusion.py`
- Modify: `backend/app/services/openmaic/fusion_client.py`

**Interfaces:**
- Consumes: Task 1 session routes and `issue_service_assertion`。
- Produces: design-specified sessions/messages/events/cancel/retry public routes；`stream_events(session_id,last_event_id) -> AsyncIterator[bytes]`。

- [ ] **Step 1: Write the failing test**

```python
def test_sse_resumes_after_last_event_id(client):
    response = client.get("/api/v1/openmaic/sessions/s1/events", headers={**auth_headers(), "Last-Event-ID": "7"})
    assert response.status_code == 200
    assert "id: 8\nevent: message.delta\n" in response.text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_openmaic_fusion_sessions.py -q`
Expected: FAIL with 404 for the missing events route.

- [ ] **Step 3: Write minimal implementation**

```python
@router.get("/openmaic/sessions/{session_id}/events")
async def events(session_id: str, request: Request, user=Depends(current_user)):
    session = await require_owned_session(user.id, session_id)
    after = int(request.headers.get("Last-Event-ID", "0"))
    return StreamingResponse(fusion_client.stream_events(session, after), media_type="text/event-stream")
```

Map downstream events to exact `id/event/data` lines; use scopes `session:read`, `session:write`, `run:control`; map cross-user IDs to 404.

- [ ] **Step 4: Run test to verify it passes**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_openmaic_fusion_sessions.py backend/tests/test_openmaic_student_integration.py -q`
Expected: all tests pass, including disconnect cleanup and downstream errors.

- [ ] **Step 5: Commit**

```powershell
git add backend/app backend/tests/test_openmaic_fusion_sessions.py
git commit -m "feat: proxy OpenMAIC session streams"
```

### Task 3: 融合工作台 UI

**Files:**
- Create: `webreact/src/pages/OpenMaicWorkbenchPage.jsx`
- Create: `webreact/src/features/openmaic/workbench/WorkbenchShell.jsx`
- Create: `webreact/src/features/openmaic/workbench/SessionSidebar.jsx`
- Create: `webreact/src/features/openmaic/workbench/ConversationPanel.jsx`
- Create: `webreact/src/features/openmaic/workbench/useFusionSession.js`
- Test: `webreact/tests/openmaic-workbench.test.mjs`
- Test: `webreact/tests/openmaic-stream.test.mjs`
- Modify: `webreact/src/App.jsx`
- Modify: `webreact/src/data/api.js`
- Modify: `webreact/src/features/openmaic/openmaic.css`

**Interfaces:**
- Consumes: Task 2 public routes and plan 02 navigation state。
- Produces: `/courses/:courseId/openmaic`；`useFusionSession({courseId,stageId}) -> {sessions,activeSession,messages,runStatus,send,cancel,retry,reconnect}`。

- [ ] **Step 1: Write the failing test**

```js
test("stream resumes and ignores duplicate events", async () => {
  const state = reduceEvents([], [{ id: "8", type: "message.delta", data: { text: "A" } }, { id: "8", type: "message.delta", data: { text: "A" } }]);
  assert.equal(state.text, "A");
  assert.equal(state.lastEventId, "8");
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `Set-Location webreact; node --test tests/openmaic-workbench.test.mjs tests/openmaic-stream.test.mjs`
Expected: FAIL because workbench and stream reducer are missing.

- [ ] **Step 3: Write minimal implementation**

```js
export function reduceEvents(state, events) {
  return events.reduce((next, event) => next.seen.has(event.id) ? next : applyEvent(next, event), createStreamState(state));
}

export function useFusionSession({ courseId, stageId }) {
  const [state, dispatch] = useReducer(sessionReducer, initialSessionState);
  useEffect(() => connectFusionStream({ courseId, stageId, dispatch }), [courseId, stageId]);
  return bindSessionActions(state, dispatch);
}
```

Build the upstream-compatible session/stage/material/tool layout, consume initial prompt once, restore from server on refresh, and expose accessible cancel/retry/reconnect controls.

- [ ] **Step 4: Run test to verify it passes**

Run: `Set-Location webreact; node --test tests/openmaic-workbench.test.mjs tests/openmaic-stream.test.mjs; npm run build`
Expected: tests and Vite build pass.

- [ ] **Step 5: Commit**

```powershell
git add webreact/src webreact/tests/openmaic-workbench.test.mjs webreact/tests/openmaic-stream.test.mjs
git commit -m "feat: add course-aware OpenMAIC workbench"
```
