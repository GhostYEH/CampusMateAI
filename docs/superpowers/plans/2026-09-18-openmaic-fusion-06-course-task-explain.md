# OpenMAIC Fusion 06 Course and Assignment Explanation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` (recommended) or `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 OpenMAIC 入口融合到课程详情和作业详情，以授权、脱敏、可预览的流程讲解作业内容。

**Architecture:** FastAPI 从现有 repository 建立 ExplainPlan，用户确认后才向 Node 创建运行；Web 不自行拼接或上传隐藏课程数据。

**Tech Stack:** FastAPI、Pydantic、pytest、React 18、Node test runner、OpenMAIC session/stage API。

**Spec:** `docs/superpowers/specs/2026-09-18-openmaic-campus-fusion-design.md`

## Global Constraints

- 必须先完成计划 03—05，并复用现有 course/assignment repository。
- 讲解前必须展示计划；执行时必须二次授权并校验 plan 未过期、未篡改。
- 只转发已授权且已脱敏的内容，不发送作业答案编辑器草稿。
- 现有课程页签、作业查看、保存和提交功能不得回归。

---

### Task 1: 作业讲解计划与脱敏

**Files:**
- Create: `backend/app/services/openmaic/assignment_explanation.py`
- Test: `backend/tests/test_openmaic_assignment_explanation.py`
- Modify: `backend/app/schemas/openmaic_fusion.py`
- Modify: `backend/app/api/routes/openmaic_fusion.py`
- Modify: `backend/app/services/openmaic/redaction.py`

**Interfaces:**
- Consumes: existing course, assignment, attachment repositories and redaction helpers。
- Produces: `build_explain_plan(user,course_id,assignment_id) -> ExplainPlan`；GET explain/plan route；plan includes `planId,summary,includedSources,excludedSources,redactionCount,expiresAt`。

- [ ] **Step 1: Write the failing test**

```python
async def test_plan_redacts_secrets_and_excludes_unauthorized_attachment(service):
    plan = await service.build_explain_plan(user("u1"), "c1", "a1")
    assert "token-raw" not in plan.model_dump_json()
    assert plan.redaction_count == 1
    assert [item.reason for item in plan.excluded_sources] == ["not_authorized"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_openmaic_assignment_explanation.py -q`
Expected: FAIL because `assignment_explanation` is missing.

- [ ] **Step 3: Write minimal implementation**

```python
async def build_explain_plan(self, user, course_id, assignment_id):
    await self.access.require_course(user.id, course_id)
    assignment = await self.assignments.require_in_course(assignment_id, course_id)
    sources = await self.sources.authorized_for(user.id, assignment)
    safe_sources, count = self.redactor.redact_sources(sources)
    return self.sign_plan(user.id, course_id, assignment, safe_sources, count, ttl_seconds=300)
```

Return object keys and display names only; cover cross-course IDs, read-only remote assignments, missing files, PII and token patterns.

- [ ] **Step 4: Run test to verify it passes**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_openmaic_assignment_explanation.py backend/tests/test_openmaic_phase2_context.py -q`
Expected: all tests pass and GET plan does not call a model or create a session.

- [ ] **Step 5: Commit**

```powershell
git add backend/app backend/tests/test_openmaic_assignment_explanation.py
git commit -m "feat: plan safe assignment explanations"
```

### Task 2: 执行讲解并连接工作台

**Files:**
- Test: `backend/tests/test_openmaic_assignment_explain_dispatch.py`
- Modify: `backend/app/services/openmaic/assignment_explanation.py`
- Modify: `backend/app/api/routes/openmaic_fusion.py`
- Modify: `backend/app/services/openmaic/fusion_client.py`
- Test: `openmaic-service/tests/assignmentExplanation.test.ts`
- Modify: `openmaic-service/src/services/runService.ts`

**Interfaces:**
- Consumes: signed ExplainPlan, StageBinding and session/run APIs。
- Produces: POST explain route accepting `{planId,mode,focus,requestId}` and returning `{sessionId,stageId,runId}`；Node `startAssignmentExplanation`。

- [ ] **Step 1: Write the failing tests**

```python
def test_expired_plan_is_not_dispatched(client):
    response = client.post(explain_url, json={"planId": expired_plan, "mode": "standard", "focus": "steps", "requestId": "r1"}, headers=auth_headers())
    assert response.status_code == 409
```

```ts
it("preserves assignment citations in stage output", async () => {
  const run = await service.startAssignmentExplanation(fixturePlan());
  expect(run.commands.flatMap((item) => item.payload.sources)).toContainEqual(expect.objectContaining({ sourceId: "assignment:a1" }));
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_openmaic_assignment_explain_dispatch.py -q`
Run: `Set-Location openmaic-service; npx vitest run tests/assignmentExplanation.test.ts`
Expected: missing dispatch and run mode fail.

- [ ] **Step 3: Write minimal implementation**

```python
async def dispatch(self, user, plan_id, mode, focus, request_id):
    plan = self.verify_plan(plan_id, user.id)
    await self.access.recheck(user.id, plan.course_id, plan.assignment_id)
    binding = await self.fusion.get_or_create_binding(user.id, plan.course_id)
    return await self.fusion.start_explanation(binding, plan, mode, focus, request_id)
```

Node maps the signed safe sources into a dedicated run, emits citations, and writes generated content only through Stage commands.

- [ ] **Step 4: Run tests to verify they pass**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_openmaic_assignment_explain_dispatch.py -q`
Run: `Set-Location openmaic-service; npx vitest run tests/assignmentExplanation.test.ts`
Expected: expiry, tampering, revoked access, requestId idempotency, citations and downstream failure tests pass.

- [ ] **Step 5: Commit**

```powershell
git add backend/app backend/tests/test_openmaic_assignment_explain_dispatch.py openmaic-service
git commit -m "feat: dispatch assignment explanations"
```

### Task 3: 融合课程与作业页面

**Files:**
- Create: `webreact/src/features/openmaic/course/OpenMaicCourseEntry.jsx`
- Create: `webreact/src/features/openmaic/assignment/AssignmentExplainPanel.jsx`
- Test: `webreact/tests/openmaic-course-entry.test.mjs`
- Test: `webreact/tests/openmaic-assignment-explain.test.mjs`
- Modify: `webreact/src/pages/CourseDetailPage.jsx`
- Modify: `webreact/src/pages/TaskDetailPage.jsx`
- Modify: `webreact/src/data/api.js`

**Interfaces:**
- Consumes: plan/status/execute/session APIs。
- Produces: course mentoring entry；`AssignmentExplainPanel({courseId,assignmentId})` with unavailable/planning/ready/running/completed/failed states。

- [ ] **Step 1: Write the failing test**

```js
test("assignment explanation requires a visible plan confirmation", async () => {
  const state = await loadExplainPanel({ assignmentId: "a1" });
  assert.equal(state.status, "ready");
  assert.equal(state.executeCalls, 0);
  assert.deepEqual(state.actions, ["开始讲解"]);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `Set-Location webreact; node --test tests/openmaic-course-entry.test.mjs tests/openmaic-assignment-explain.test.mjs`
Expected: missing entry and panel fail.

- [ ] **Step 3: Write minimal implementation**

```jsx
export function AssignmentExplainPanel({ courseId, assignmentId }) {
  const flow = useAssignmentExplain({ courseId, assignmentId });
  if (flow.status === "ready") return <ExplainPlanCard plan={flow.plan} onConfirm={flow.execute} />;
  if (flow.status === "completed") return <ExplainActions onContinue={flow.continueChat} onEdit={flow.openEditor} onPlay={flow.play} />;
  return <ExplainStatus state={flow} />;
}
```

Place course entry in the existing mentoring tab and explanation beside assignment information without changing submission state. Handle 403, 409 re-plan and 503 inline.

- [ ] **Step 4: Run test to verify it passes**

Run: `Set-Location webreact; node --test tests/openmaic-course-entry.test.mjs tests/openmaic-assignment-explain.test.mjs; npm run build`
Expected: existing tab/submission assertions, plan confirmation and continuation actions pass.

- [ ] **Step 5: Commit**

```powershell
git add webreact/src webreact/tests/openmaic-course-entry.test.mjs webreact/tests/openmaic-assignment-explain.test.mjs
git commit -m "feat: explain assignments with OpenMAIC"
```
