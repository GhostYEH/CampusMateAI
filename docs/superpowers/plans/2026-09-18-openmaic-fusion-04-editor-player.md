# OpenMAIC Fusion 04 Editor, Player, and Whiteboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` (recommended) or `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 迁移 Stage 编辑、场景元素、时间轴、播放与白板能力，让编辑器和播放器共享同一文档契约。

**Architecture:** Node 拥有 StageDocument、revision、命令幂等和 PlaybackManifest；FastAPI 代理并授权；React 18 通过命令 API 编辑。

**Tech Stack:** TypeScript、Fastify、Vitest、FastAPI、pytest、React 18、Canvas/SVG、Node test runner。

**Spec:** `docs/superpowers/specs/2026-09-18-openmaic-campus-fusion-design.md`

## Global Constraints

- 必须先完成计划 03；StageDocument、EditCommand、PlaybackManifest 字段以设计文档为准。
- 同 commandId 必须幂等；baseRevision 冲突返回 409，客户端不得静默覆盖。
- text、image、code、chart、interaction 元素使用受限联合类型，禁止任意脚本和 HTML。
- 不引入 Next 路由、server component 或第二份 React。

---

### Task 1: Stage 命令与授权网关

**Files:**
- Create: `openmaic-service/src/domain/stage.ts`
- Create: `openmaic-service/src/services/stageCommandService.ts`
- Create: `openmaic-service/src/repositories/stageRepository.ts`
- Create: `openmaic-service/src/routes/stages.ts`
- Test: `openmaic-service/tests/stageCommands.test.ts`
- Test: `backend/tests/test_openmaic_fusion_stages.py`
- Modify: `backend/app/api/routes/openmaic_fusion.py`
- Modify: `backend/app/schemas/openmaic_fusion.py`
- Modify: `backend/app/services/openmaic/fusion_client.py`

**Interfaces:**
- Consumes: StageBinding, AssertionClaims and session authorization。
- Produces: Node `getStage`、`applyCommand`、`getPlayback`；public stage GET/commands/playback routes。

- [ ] **Step 1: Write the failing tests**

```ts
it("rejects a stale base revision without mutation", async () => {
  await service.applyCommand("s1", owner, { commandId: "a", baseRevision: 0, kind: "document.rename", payload: { title: "One" } });
  await expect(service.applyCommand("s1", owner, { commandId: "b", baseRevision: 0, kind: "document.rename", payload: { title: "Two" } })).rejects.toMatchObject({ statusCode: 409, revision: 1 });
});
```

```python
def test_stage_of_another_user_is_hidden(client):
    response = client.get("/api/v1/openmaic/stages/other", headers=auth_headers())
    assert response.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `Set-Location openmaic-service; npx vitest run tests/stageCommands.test.ts`
Run: `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_openmaic_fusion_stages.py -q`
Expected: missing service and routes fail.

- [ ] **Step 3: Write minimal implementation**

```ts
export async function applyCommand(stageId: string, principal: Principal, command: EditCommand) {
  return stages.transaction(stageId, async (document) => {
    assertOwner(document, principal);
    const replay = document.commandResults[command.commandId];
    if (replay) return replay;
    if (document.revision !== command.baseRevision) throw new RevisionConflict(document.revision);
    return executeValidatedCommand(document, command);
  });
}
```

```python
@router.post("/openmaic/stages/{stage_id}/commands")
async def stage_command(stage_id: str, command: EditCommandIn, user=Depends(current_user)):
    binding = await require_owned_stage(user.id, stage_id)
    return ok(await fusion_client.apply_command(binding, command))
```

Implement all eight command kinds and manifest generation; map Node 409 to public 409 with current revision.

- [ ] **Step 4: Run tests to verify they pass**

Run: `Set-Location openmaic-service; npx vitest run tests/stageCommands.test.ts; npx tsc --noEmit`
Run from repository root: `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_openmaic_fusion_stages.py -q`
Expected: commands, idempotency, ownership, schema validation and manifest tests pass.

- [ ] **Step 5: Commit**

```powershell
git add openmaic-service backend/app backend/tests/test_openmaic_fusion_stages.py
git commit -m "feat: add authorized versioned stage editing"
```

### Task 2: 迁移编辑器与场景元素

**Files:**
- Create: `webreact/src/features/openmaic/editor/StageEditor.jsx`
- Create: `webreact/src/features/openmaic/editor/SceneList.jsx`
- Create: `webreact/src/features/openmaic/editor/StageCanvas.jsx`
- Create: `webreact/src/features/openmaic/editor/InspectorPanel.jsx`
- Create: `webreact/src/features/openmaic/editor/Timeline.jsx`
- Create: `webreact/src/features/openmaic/editor/OutlineEditor.jsx`
- Create: `webreact/src/features/openmaic/editor/EditWithAiPanel.jsx`
- Create: `webreact/src/features/openmaic/editor/useStageEditor.js`
- Create: `webreact/src/features/openmaic/editor/renderers.jsx`
- Test: `webreact/tests/openmaic-editor.test.mjs`
- Modify: `webreact/src/features/openmaic/workbench/WorkbenchShell.jsx`
- Modify: `webreact/src/data/api.js`

**Interfaces:**
- Consumes: Task 1 stage GET and command API。
- Produces: `useStageEditor(stageId) -> {document,selection,dispatch,undo,redo,conflict,refresh}`；outline reorder/type edit；validated AI patch preview/history；safe text/formula/table/image/media/code/chart/interaction renderers。

- [ ] **Step 1: Write the failing test**

```js
test("a 409 pauses commands until the document is refreshed", async () => {
  const result = await simulateEditorCommand({ serverRevision: 4, localRevision: 3 });
  assert.equal(result.conflict.currentRevision, 4);
  assert.equal(result.pendingCommands, 0);
  assert.equal(result.autoRetried, false);
});

test("AI edits require a validated patch preview", () => {
  const preview = previewAiPatch(stageFixture(), [{ op: "replace", path: "/title", value: "New" }]);
  assert.equal(preview.valid, true);
  assert.equal(preview.applied, false);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `Set-Location webreact; node --test tests/openmaic-editor.test.mjs`
Expected: FAIL because editor model is missing.

- [ ] **Step 3: Write minimal implementation**

```js
async function dispatch(command) {
  try {
    const result = await api.applyOpenMaicCommand(stageId, { ...command, commandId: crypto.randomUUID(), baseRevision: document.revision });
    setDocument(result.document);
    pushUndo(result);
  } catch (error) {
    if (error.response?.status === 409) setConflict({ currentRevision: error.response.data.currentRevision });
    else throw error;
  }
}
```

Port the upstream outline editor, canvas, scene list, inspector, timeline and Edit with AI history into React 18. Implement keyboard-accessible selection, drag/resize/rotate/multi-select, scene add/delete/duplicate/reorder, safe renderers, validated patch confirmation and confirmed undo/redo only.

- [ ] **Step 4: Run test to verify it passes**

Run: `Set-Location webreact; node --test tests/openmaic-editor.test.mjs; npm run build`
Expected: editor tests and build pass; source scan finds no unsafe HTML execution.

- [ ] **Step 5: Commit**

```powershell
git add webreact/src webreact/tests/openmaic-editor.test.mjs
git commit -m "feat: port OpenMAIC stage editor"
```

### Task 3: 播放器与白板

**Files:**
- Create: `webreact/src/features/openmaic/player/StagePlayer.jsx`
- Create: `webreact/src/features/openmaic/player/usePlaybackClock.js`
- Create: `webreact/src/features/openmaic/player/ActionEngine.js`
- Create: `webreact/src/features/openmaic/whiteboard/Whiteboard.jsx`
- Test: `webreact/tests/openmaic-player-whiteboard.test.mjs`
- Modify: `webreact/src/features/openmaic/workbench/WorkbenchShell.jsx`

**Interfaces:**
- Consumes: Task 1 PlaybackManifest and Task 2 renderers/dispatch。
- Produces: `usePlaybackClock({durationMs,onFrame}) -> {timeMs,playing,play,pause,seek,setRate}`；ActionEngine executes narration/spotlight/laser/whiteboard/effect actions；whiteboard strokes dispatch `element.update`。

- [ ] **Step 1: Write the failing test**

```js
test("playback clamps time and cleans the animation frame", () => {
  const clock = createPlaybackClock({ durationMs: 1000, now: fakeNow, raf, cancelRaf });
  clock.seek(1400);
  assert.equal(clock.snapshot().timeMs, 1000);
  clock.dispose();
  assert.equal(cancelRaf.calls.length, 1);
});

test("spotlight and laser actions clear at their end time", () => {
  const frames = runActions([{ type: "spotlight", startMs: 10, endMs: 20, targetId: "el-1" }], [10, 21]);
  assert.deepEqual(frames.map((frame) => frame.spotlight), ["el-1", null]);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `Set-Location webreact; node --test tests/openmaic-player-whiteboard.test.mjs`
Expected: FAIL because playback clock is missing.

- [ ] **Step 3: Write minimal implementation**

```js
const seek = (value) => setTimeMs(Math.max(0, Math.min(durationMs, value)));
const dispose = () => { if (frameRef.current) cancelAnimationFrame(frameRef.current); audioRef.current?.pause(); };
useEffect(() => dispose, []);
```

Render only PlaybackManifest, reuse safe element renderers, implement play/pause/seek/rate/scene jump, execute narration/spotlight/laser/whiteboard/effect actions deterministically, and serialize bounded whiteboard strokes including shapes/formulas/code through editor dispatch.

- [ ] **Step 4: Run test to verify it passes**

Run: `Set-Location webreact; node --test tests/openmaic-player-whiteboard.test.mjs tests/openmaic-editor.test.mjs; npm run build`
Expected: player, whiteboard, reduced-motion and cleanup tests pass.

- [ ] **Step 5: Commit**

```powershell
git add webreact/src/features/openmaic webreact/tests/openmaic-player-whiteboard.test.mjs
git commit -m "feat: add OpenMAIC playback and whiteboard"
```
