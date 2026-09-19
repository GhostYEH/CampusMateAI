import React from "react";
import { Button, Panel, SectionHeading } from "../Primitives.jsx";
import { Icon } from "../Icon.jsx";
import * as api from "../../data/api.js";
import StagePlayerPanel from "./StagePlayerPanel.jsx";
import {
  MAX_COMMANDS_PER_REQUEST,
  SCENE_TYPE_LABELS,
  SCENE_TYPES,
  createCommandBuffer,
  describeEditorError,
  normalizeOutline,
  sceneCreateCommand,
  sceneDeleteCommand,
  sceneDuplicateCommand,
  sceneMoveCommand,
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
  const [loading, setLoading] = React.useState(true);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState("");
  const [notice, setNotice] = React.useState("");
  const [addType, setAddType] = React.useState("slide");
  // 正在播放的场景：播放器自己按 scene_id 恢复位置，编辑器只负责记下这一个 id。
  const [playingSceneId, setPlayingSceneId] = React.useState("");

  const scopeKey = `${courseId}:${workspaceId}:${stageId}`;

  const load = React.useCallback(async () => {
    const mine = (epoch.current += 1);
    setLoading(true);
    setError("");
    try {
      const payload = await api.getOpenMAICStageOutline(courseId, workspaceId, stageId);
      if (mine !== epoch.current) return; // 迟到的响应：切课/切 workspace 后必须丢弃
      const outline = normalizeOutline(payload);
      buffer.current.setBase(
        { stage: { id: outline.stageId || stageId, name: outline.title }, scenes: outline.scenes },
        outline.revision,
      );
      idempotencyKey.current = null;
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
    setNotice("");
    void load();
    // scopeKey 变化即"换了一份被编辑的内容"：必须重建缓冲，否则会把上一个
    // workspace 的命令提交到这里。
  }, [scopeKey, load]);

  function run(command) {
    setError("");
    setNotice("");
    try {
      buffer.current.run(command);
      setView((current) => (current ? { ...current, document: buffer.current.preview() } : current));
    } catch (failure) {
      // 本地不接受的命令绝不发出去，也就不会出现"界面改了服务端没改"。
      setError(failure.message || "这条编辑无法应用。");
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
  const scenes = view?.document?.scenes || [];
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
      : scenes.length ? <ol className="openmaic-scene-list">
        {scenes.map((scene, index) => <li className="openmaic-scene-item" key={scene.id}>
          <span className="openmaic-scene-item__order">{index + 1}</span>
          <span className="openmaic-scene-item__type">{SCENE_TYPE_LABELS[scene.type] || scene.type}</span>
          <span className="row-copy"><strong>{scene.title}</strong>
            <small>{scene.actions ? `${scene.actions} 个动作` : "暂无动作"}</small>
          </span>
          <Button type="button" variant="quiet" disabled={index === 0} onClick={() => run(sceneMoveCommand(scene.id, index - 1))}>上移</Button>
          <Button type="button" variant="quiet" disabled={index === scenes.length - 1} onClick={() => run(sceneMoveCommand(scene.id, index + 1))}>下移</Button>
          <Button type="button" variant="quiet" onClick={() => setPlayingSceneId(scene.id)}>播放</Button>
          <Button type="button" variant="quiet" onClick={() => run(sceneDuplicateCommand(scene.id))}>复制</Button>
          <Button type="button" variant="quiet" onClick={() => run(sceneDeleteCommand(scene.id))}>删除</Button>
        </li>)}
      </ol>
      : <div className="openmaic-home__empty openmaic-home__empty--wide">
        <Icon name="PhLayout" size={26} />
        <div><strong>这份内容还没有场景</strong><p>添加一个场景后即可继续编辑。</p></div>
      </div>}

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
