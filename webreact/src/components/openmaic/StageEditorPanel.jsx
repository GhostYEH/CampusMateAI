import React from "react";
import { Button, Panel, SectionHeading } from "../Primitives.jsx";
import { Icon } from "../Icon.jsx";
import * as api from "../../data/api.js";
import StagePlayerPanel from "./StagePlayerPanel.jsx";
import StageCanvasPreview from "../../maic/edit/StageCanvasPreview.jsx";
import {
  MAX_COMMANDS_PER_REQUEST,
  SCENE_TYPE_LABELS,
  SCENE_TYPES,
  createCommandBuffer,
  describeEditorError,
  sceneCreateCommand,
  sceneDeleteCommand,
  sceneDuplicateCommand,
  sceneMoveCommand,
  sceneUpdateCommand,
  slideElementMoveCommand,
  slideElementUpdateCommand,
} from "../../features/openmaic/editorModel.js";

/**
 * Stage 编辑器：场景目录的增删改排序。
 *
 * 关键约束都在这里落地：
 *
 * - 提交的是**命令列表**（`createCommandBuffer`），不是整份文档；
 * - 保存用**一次读取到的 revision**；409 表示手上的副本过期，必须重新读取而不是
 *   原样重放命令；
 * - 切换课程/workspace/stage 后，迟到的响应不得写进新上下文（epoch 守卫）；
 * - 只有服务端真实上报 `editor` 能力时才渲染（由父组件决定），离线时不出现
 *   可点击的编辑入口。
 */
export default function StageEditorPanel({ courseId, workspaceId, stageId, onSaved }) {
  const buffer = React.useRef(createCommandBuffer());
  const epoch = React.useRef(0);
  const idempotencyKey = React.useRef(null);
  const [view, setView] = React.useState(null);
  const [selectedSceneId, setSelectedSceneId] = React.useState("");
  const [loading, setLoading] = React.useState(true);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState("");
  const [notice, setNotice] = React.useState("");
  const [editingScene, setEditingScene] = React.useState(null);
  const [sceneDraft, setSceneDraft] = React.useState("");
  const [sceneLoading, setSceneLoading] = React.useState(false);
  const [addType, setAddType] = React.useState("slide");
  // 正在播放的场景：播放器自己按 scene_id 恢复位置，编辑器只负责记下这一个 id。
  const [playingSceneId, setPlayingSceneId] = React.useState("");

  const scopeKey = `${courseId}:${workspaceId}:${stageId}`;

  const load = React.useCallback(async () => {
    const mine = (epoch.current += 1);
    setLoading(true);
    setError("");
    try {
      // 编辑画布和目录必须来自同一次完整 stage 读取。若把 outline 与 document
      // 分别读取，另一个作者恰好保存时会把 A 版本的目录和 B 版本的画布拼在一起。
      const stagePayload = await api.getOpenMAICStage(courseId, workspaceId, stageId);
      if (mine !== epoch.current) return; // 迟到的响应：切课/切 workspace 后必须丢弃
      const sourceDocument = stagePayload?.document && typeof stagePayload.document === "object"
        ? stagePayload.document
        : {};
      const document = {
        ...sourceDocument,
        stage: sourceDocument.stage || {
          id: stagePayload?.id || stageId,
          name: stagePayload?.title || "未命名内容",
        },
        // `document.scenes` is authoritative. In particular, `actions` is the
        // complete playback/edit timeline, while the outline only exposes an
        // action count for navigation. Never merge that summary back here.
        scenes: Array.isArray(sourceDocument.scenes) ? sourceDocument.scenes : [],
      };
      const outline = {
        stageId: stagePayload?.id || stageId,
        workspaceId: stagePayload?.workspace_id || workspaceId,
        title: stagePayload?.title || document.stage?.name || "未命名内容",
        revision: Number(stagePayload?.revision) || 0,
      };
      buffer.current.setBase(
        document,
        outline.revision,
      );
      idempotencyKey.current = null;
      setSelectedSceneId((current) => document.scenes.some((scene) => scene.id === current)
        ? current
        : (document.scenes[0]?.id || ""));
      setView({ outline, document: buffer.current.preview() });
    } catch (failure) {
      if (mine !== epoch.current) return;
      setError(describeEditorError(failure).message);
      setView(null);
    } finally {
      if (mine === epoch.current) setLoading(false);
    }
  }, [courseId, workspaceId, stageId]);

  React.useEffect(() => {
    buffer.current = createCommandBuffer();
    idempotencyKey.current = null;
    setPlayingSceneId("");
    setEditingScene(null);
    setSceneDraft("");
    setNotice("");
    void load();
    // scopeKey 变化即"换了一份被编辑的内容"：必须重建缓冲，否则会把上一个
    // workspace 的命令提交到这里。
    return () => {
      // Invalidate any read still in flight when the panel unmounts or its
      // course/workspace/stage context changes.
      epoch.current += 1;
    };
  }, [scopeKey, load]);

  const scenes = view?.document?.scenes || [];
  React.useEffect(() => {
    setSelectedSceneId((current) => scenes.some((scene) => scene.id === current)
      ? current
      : (scenes[0]?.id || ""));
  }, [scenes]);

  function run(command) {
    setError("");
    setNotice("");
    try {
      buffer.current.run(command);
      setView((current) => (current ? { ...current, document: buffer.current.preview() } : current));
      return true;
    } catch (failure) {
      // 本地不接受的命令绝不发出去，也就不会出现"界面改了服务端没改"。
      setError(failure.message || "这条编辑无法应用。");
      return false;
    }
  }

  function moveSlideElement(elementId, left, top) {
    if (!selectedScene?.id) return false;
    return run(slideElementMoveCommand(selectedScene.id, elementId, left, top));
  }

  function updateTextElement(elementId, content) {
    if (!selectedScene?.id) return false;
    return run(slideElementUpdateCommand(selectedScene.id, elementId, content));
  }

  async function editScene(sceneId) {
    const mine = epoch.current;
    setSceneLoading(true);
    setError("");
    try {
      // Full stage reads normally make this local. Keep the scene endpoint as
      // a compatibility fallback for older/partial stage responses.
      let scene = view?.document?.scenes?.find((entry) => entry.id === sceneId) || null;
      if (!scene) scene = await api.getOpenMAICStageScene(courseId, workspaceId, stageId, sceneId);
      if (mine !== epoch.current) return;
      setEditingScene(scene);
      setSceneDraft(JSON.stringify({ title: scene.title, content: scene.content }, null, 2));
    } catch (failure) {
      setError(failure?.response?.data?.message || failure?.message || "读取场景内容失败。");
    } finally {
      setSceneLoading(false);
    }
  }

  function saveSceneDraft() {
    let parsed;
    try {
      parsed = JSON.parse(sceneDraft);
    } catch {
      setError("场景内容必须是合法 JSON。");
      return;
    }
    if (!parsed || typeof parsed !== "object" || typeof parsed.title !== "string" || !parsed.content || typeof parsed.content !== "object") {
      setError("场景编辑器需要 title 与 content 字段。");
      return;
    }
    if (parsed.content.type !== editingScene?.type) {
      setError("content.type 必须保持原场景类型不变。");
      return;
    }
    if (run(sceneUpdateCommand(editingScene.id, { title: parsed.title, content: parsed.content }))) {
      setEditingScene(null);
      setSceneDraft("");
      setNotice("场景内容已加入待保存编辑。");
    }
  }

  function undo() {
    buffer.current.undo();
    setView((current) => (current ? { ...current, document: buffer.current.preview() } : current));
  }

  function redo() {
    buffer.current.redo();
    setView((current) => (current ? { ...current, document: buffer.current.preview() } : current));
  }

  function discard() {
    buffer.current.reset();
    void load();
  }

  async function save() {
    if (!buffer.current.isDirty()) return;
    setBusy(true);
    setError("");
    setNotice("");
    idempotencyKey.current = idempotencyKey.current || api.newIdempotencyKey();
    const batches = buffer.current.takeBatches(MAX_COMMANDS_PER_REQUEST);
    try {
      let last = null;
      for (const commands of batches) {
        // 每一批都用**当前** revision：服务端每成功一次就 +1，用旧的会立刻 409。
        last = await api.applyOpenMAICStageCommands(courseId, workspaceId, stageId, {
          commands,
          revision: buffer.current.revision,
          idempotencyKey: idempotencyKey.current,
        });
        buffer.current.setRevision(last.revision);
      }
      idempotencyKey.current = null;
      setNotice(`已保存（应用 ${batches.reduce((total, batch) => total + batch.length, 0)} 条编辑）`);
      await load();
      onSaved?.(last);
    } catch (failure) {
      const described = describeEditorError(failure);
      // 幂等键冲突说明这次提交与上一次不是同一个请求：换键，否则会一直冲突。
      if (described.kind === "idempotency") idempotencyKey.current = null;
      if (described.kind === "commandRejected" && described.path) {
        setError(`${described.message}（${described.path}）`);
      } else {
        setError(described.message);
      }
      // 409：手上的副本过期，重新读取是唯一能继续的动作。
      if (described.kind === "conflict") await load();
    } finally {
      setBusy(false);
    }
  }

  const outline = view?.outline;
  const selectedScene = scenes.find((scene) => scene.id === selectedSceneId) || scenes[0] || null;
  const dirty = Boolean(view) && buffer.current.isDirty();

  return <Panel className="openmaic-stage-editor">
    <SectionHeading
      title="场景编辑"
      detail={outline ? `${outline.title} · ${scenes.length} 个场景${dirty ? " · 未保存" : ""}` : "读取中"}
    />

    {notice ? <p className="openmaic-hint" role="status">{notice}</p> : null}
    {error ? <p className="openmaic-hint openmaic-hint--error" role="alert">{error}</p> : null}

    <div className="openmaic-stage-editor__toolbar">
      <label className="openmaic-stage-editor__type">
        <span>新建</span>
        <select value={addType} onChange={(event) => setAddType(event.target.value)} aria-label="新场景类型">
          {SCENE_TYPES.map((type) => <option key={type} value={type}>{SCENE_TYPE_LABELS[type] || type}</option>)}
        </select>
      </label>
      <Button type="button" onClick={() => run(sceneCreateCommand(addType, { title: `新${SCENE_TYPE_LABELS[addType] || addType}` }))}>
        添加场景
      </Button>
      <Button type="button" variant="secondary" disabled={!buffer.current.canUndo()} onClick={undo}>撤销</Button>
      <Button type="button" variant="secondary" disabled={!buffer.current.canRedo()} onClick={redo}>重做</Button>
      <Button type="button" disabled={!dirty || busy} onClick={save}>{busy ? "保存中…" : "保存"}</Button>
      <Button type="button" variant="quiet" disabled={!dirty || busy} onClick={discard}>放弃更改</Button>
    </div>

    {loading ? <p className="openmaic-hint">正在读取场景…</p>
      : scenes.length ? <div className="openmaic-stage-editor__workspace">
        <ol className="openmaic-scene-list">
        {scenes.map((scene, index) => <li
          className={`openmaic-scene-item${selectedScene?.id === scene.id ? " is-selected" : ""}`}
          key={scene.id}
        >
          <span className="openmaic-scene-item__order">{index + 1}</span>
          <span className="openmaic-scene-item__type">{SCENE_TYPE_LABELS[scene.type] || scene.type}</span>
          <button type="button" className="openmaic-scene-item__select" aria-label={`预览场景：${scene.title}`} aria-pressed={selectedScene?.id === scene.id} onClick={() => setSelectedSceneId(scene.id)}><span className="row-copy"><strong>{scene.title}</strong>
            <small>{Array.isArray(scene.actions) && scene.actions.length ? `${scene.actions.length} 个动作` : "暂无动作"}</small>
          </span></button>
          <Button type="button" variant="quiet" disabled={index === 0} onClick={() => run(sceneMoveCommand(scene.id, index - 1))}>上移</Button>
          <Button type="button" variant="quiet" disabled={index === scenes.length - 1} onClick={() => run(sceneMoveCommand(scene.id, index + 1))}>下移</Button>
          <Button type="button" variant="quiet" onClick={() => setPlayingSceneId(scene.id)}>播放</Button>
          <Button type="button" variant="quiet" disabled={sceneLoading} onClick={() => editScene(scene.id)}>编辑内容</Button>
          <Button type="button" variant="quiet" onClick={() => run(sceneDuplicateCommand(scene.id))}>复制</Button>
          <Button type="button" variant="quiet" onClick={() => run(sceneDeleteCommand(scene.id))}>删除</Button>
        </li>)}
        </ol>
        <StageCanvasPreview
          scene={selectedScene}
          onMoveElement={moveSlideElement}
          onUpdateTextElement={updateTextElement}
        />
      </div>
      : <div className="openmaic-home__empty openmaic-home__empty--wide">
        <Icon name="PhLayout" size={26} />
        <div><strong>这份内容还没有场景</strong><p>添加一个场景后即可继续编辑。</p></div>
      </div>}

    {editingScene ? <section className="openmaic-scene-content-editor" aria-label="场景内容编辑器">
      <SectionHeading title={`编辑：${editingScene.title}`} detail="服务端会再次执行 DSL 校验；保存前可继续撤销。" />
      <textarea
        aria-label="场景 DSL 内容"
        value={sceneDraft}
        onChange={(event) => setSceneDraft(event.target.value)}
        rows={16}
        spellCheck="false"
      />
      <div className="openmaic-stage-editor__toolbar">
        <Button type="button" onClick={saveSceneDraft}>应用编辑</Button>
        <Button type="button" variant="quiet" onClick={() => { setEditingScene(null); setSceneDraft(""); }}>取消</Button>
      </div>
    </section> : null}

    {/* 播放器只在服务端给出播放计划时才有内容；unsupported 场景会显示缺什么。 */}
    {playingSceneId ? <StagePlayerPanel
      courseId={courseId}
      workspaceId={workspaceId}
      stageId={stageId}
      startSceneId={playingSceneId}
      onClose={() => setPlayingSceneId("")}
    /> : null}
  </Panel>;
}
