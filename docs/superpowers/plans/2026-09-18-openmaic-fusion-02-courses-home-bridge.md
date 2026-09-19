# OpenMAIC Fusion 02 Courses Home and Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` (recommended) or `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用融合首页替换现有 `/courses` 展示，把 OpenMAIC 首页主区与 CampusMate“我的课程”右栏连接到真实课程和 Stage。

**Architecture:** Web 只使用现有 React 18、路由、主题和 API client。FastAPI 验证课程权限并幂等创建 binding；Node 服务生成不可由浏览器指定的 stageId。

**Tech Stack:** React 18、CSS、Node test runner、FastAPI、pytest、Fastify、Vitest。

**Spec:** `docs/superpowers/specs/2026-09-18-openmaic-campus-fusion-design.md`

## Global Constraints

- 必须先完成计划 01；所有公开请求经过 FastAPI。
- `/courses` 仍是唯一课程首页，不新增第二导航、第二登录或 iframe。
- OpenMAIC 主功能布局保持上游结构，只适配 CampusMate theme tokens 和响应式断点。
- 课程数据只来自现有 `getCourses()`；stageId 只由服务端生成。

---

### Task 1: 固定首页和 binding 契约

**Files:**
- Test: `backend/tests/test_openmaic_fusion_home.py`
- Modify: `backend/app/schemas/openmaic_fusion.py`
- Modify: `backend/app/api/routes/openmaic_fusion.py`
- Modify: `backend/app/services/openmaic/fusion_client.py`
- Create: `openmaic-service/src/routes/home.ts`
- Create: `openmaic-service/src/routes/bindings.ts`
- Create: `openmaic-service/src/routes/projects.ts`
- Test: `openmaic-service/tests/homeBindings.test.ts`

**Interfaces:**
- Consumes: plan 01 的内部断言和 `createServer`。
- Produces: fusion home、project search、folder POST/PATCH/DELETE、course binding public routes；Node `getOrCreateBinding(userId, courseId): Promise<StageBinding>`。

- [ ] **Step 1: Write the failing tests**

```python
def test_binding_rejects_a_course_the_user_cannot_access(client):
    response = client.post("/api/v1/courses/other/openmaic/binding", headers=auth_headers())
    assert response.status_code == 403
```

```ts
it("returns one server-generated stage per user and course", async () => {
  const first = await repo.getOrCreateBinding("u1", "c1");
  const second = await repo.getOrCreateBinding("u1", "c1");
  expect(second.stageId).toBe(first.stageId);
});

it("does not delete a non-empty folder", async () => {
  await expect(projects.deleteFolder("u1", "folder-1")).rejects.toMatchObject({ statusCode: 409 });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_openmaic_fusion_home.py -q`
Run: `Set-Location openmaic-service; npx vitest run tests/homeBindings.test.ts`
Expected: missing routes and repository cause failures.

- [ ] **Step 3: Write minimal implementation**

```ts
export async function getOrCreateBinding(userId: string, courseId: string) {
  const current = await bindings.find(userId, courseId);
  return current ?? bindings.insert({ userId, courseId, stageId: randomUUID() });
}
```

```python
@router.post("/courses/{course_id}/openmaic/binding")
async def bind_course(course_id: str, user=Depends(current_user)):
    await require_course_access(user.id, course_id)
    return ok(await fusion_client.get_or_create_binding(user.id, course_id))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_openmaic_fusion_home.py -q`
Run: `Set-Location openmaic-service; npx vitest run tests/homeBindings.test.ts`
Expected: tests pass for empty home, existing binding, unauthorized course and downstream timeout.

- [ ] **Step 5: Commit**

```powershell
git add backend/app backend/tests/test_openmaic_fusion_home.py openmaic-service
git commit -m "feat: bridge courses to OpenMAIC stages"
```

### Task 2: 重构 `/courses` 页面壳

**Files:**
- Create: `webreact/src/pages/OpenMaicCoursesPage.jsx`
- Create: `webreact/src/features/openmaic/home/OpenMaicHome.jsx`
- Create: `webreact/src/features/openmaic/home/CourseRail.jsx`
- Create: `webreact/src/features/openmaic/home/openMaicHomeModel.js`
- Create: `webreact/src/features/openmaic/openmaic.css`
- Test: `webreact/tests/openmaic-courses-home.test.mjs`
- Modify: `webreact/src/App.jsx`
- Modify: `webreact/src/data/api.js`
- Modify: `webreact/src/styles.css`
- Modify: `webreact/src/pages/ParityPages.jsx`

**Interfaces:**
- Consumes: `getCourses()`、`getOpenMaicFusionHome()`、`getOpenMaicFusionStatus()`。
- Produces: `CourseRail({courses, selectedCourseId, onSelect, onAsk})`；`OpenMaicCoursesPage` 作为 `/courses` lazy route。

- [ ] **Step 1: Write the failing test**

```js
test("courses route uses the fused page and keeps one browser shell", () => {
  assert.match(appSource, /OpenMaicCoursesPage/);
  assert.match(pageSource, /aria-label="我的课程"/);
  assert.doesNotMatch(pageSource, /<iframe|登录 OpenMAIC/);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `Set-Location webreact; node --test tests/openmaic-courses-home.test.mjs`
Expected: FAIL because `/courses` still imports `CoursesParityPage`.

- [ ] **Step 3: Write minimal implementation**

```jsx
export function CourseRail({ courses, selectedCourseId, onSelect, onAsk }) {
  return <aside aria-label="我的课程">{courses.map((course) =>
    <button key={course.id} aria-current={course.id === selectedCourseId} onClick={() => onSelect(course.id)}>
      <span>{course.name}</span><span onClick={(event) => { event.stopPropagation(); onAsk(course.id); }}>询问</span>
    </button>)}</aside>;
}
```

Implement `OpenMaicCoursesPage` with desktop main/rail layout, project search, recent projects, folder create/rename/delete, a narrow-screen course drawer, loading/error/empty states, reduced-motion CSS, and deletion of only the old `CoursesParityPage` card grid.

- [ ] **Step 4: Run test to verify it passes**

Run: `Set-Location webreact; node --test tests/openmaic-courses-home.test.mjs; npm run build`
Expected: test and Vite build pass.

- [ ] **Step 5: Commit**

```powershell
git add webreact/src webreact/tests/openmaic-courses-home.test.mjs
git commit -m "feat: fuse OpenMAIC home into courses"
```

### Task 3: 打通课程快捷提问

**Files:**
- Create: `webreact/src/features/openmaic/home/useCourseAsk.js`
- Test: `webreact/tests/openmaic-course-ask.test.mjs`
- Modify: `webreact/src/features/openmaic/home/OpenMaicHome.jsx`
- Modify: `webreact/src/features/openmaic/home/CourseRail.jsx`
- Modify: `webreact/src/data/api.js`

**Interfaces:**
- Consumes: `createOpenMaicBinding(courseId)` and React Router `navigate`。
- Produces: `useCourseAsk(): {ask(courseId,prompt,mode),busy,error}`；导航到 `/courses/{courseId}/openmaic?stage={stageId}`，prompt 只放 navigation state。

- [ ] **Step 1: Write the failing test**

```js
test("binding completes before workbench navigation", async () => {
  const actions = await runCourseAsk({ courseId: "c1", prompt: "解释第一章", binding: async () => ({ stageId: "s1" }) });
  assert.deepEqual(actions, ["bind:c1", "navigate:/courses/c1/openmaic?stage=s1"]);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `Set-Location webreact; node --test tests/openmaic-course-ask.test.mjs`
Expected: FAIL because `useCourseAsk` is missing.

- [ ] **Step 3: Write minimal implementation**

```js
const ask = async (courseId, prompt, mode = "standard") => {
  if (!courseId || !prompt.trim()) throw new Error("请选择课程并输入问题");
  const binding = await api.createOpenMaicBinding(courseId);
  navigate(`/courses/${courseId}/openmaic?stage=${encodeURIComponent(binding.stageId)}`, { state: { prompt, mode } });
};
```

Add a single-flight guard and render 403/503 errors inline without placing prompt, assertion or materials in the URL.

- [ ] **Step 4: Run test to verify it passes**

Run: `Set-Location webreact; node --test tests/openmaic-course-ask.test.mjs tests/openmaic-courses-home.test.mjs; npm run build`
Expected: all commands pass.

- [ ] **Step 5: Commit**

```powershell
git add webreact/src/features/openmaic webreact/src/data/api.js webreact/tests/openmaic-course-ask.test.mjs
git commit -m "feat: start OpenMAIC from a course question"
```
