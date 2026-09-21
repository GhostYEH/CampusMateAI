import React from "react";
import { Button, LinkButton, Panel, SectionHeading } from "../Primitives.jsx";
import { Icon } from "../Icon.jsx";
import * as api from "../../data/api.js";
import { formatDateTime } from "../../utils/date.js";
import StageEditorPanel from "./StageEditorPanel.jsx";
import {
  WORKSPACE_PAGE_LIMIT,
  describeWorkspaceError,
  nextCursorOf,
  normalizeStageList,
  normalizeWorkspaceList,
  normalizeWorkspaceName,
} from "../../features/magicclass/workspaceModel.js";
import {
  DISCOVERY_PAGE_LIMIT,
  normalizeFolderList,
} from "../../features/magicclass/discoveryModel.js";
import {
  describeArchiveError,
  filenameFromContentDisposition,
  normalizeImportedStage,
  validateImportCandidate,
} from "../../features/magicclass/archiveModel.js";

const dateText = (value) => formatDateTime(value, { dateStyle: "medium", timeStyle: "short" }, "时间待定");

/**
 * 把一份导出结果存成文件。
 *
 * 用 `Content-Disposition` 里的名字，而不是用标题现拼：服务端已经决定过下载名，
 * 前端再拼一次只会在两边规则分叉时静默不一致。
 */
function saveBlob(blob, filename) {
  if (typeof document === "undefined" || typeof URL === "undefined") return;
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  // Keep the object URL alive long enough for Chrome to attach the download.
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/**
 * 课程内的学习工作台列表。
 *
 * 这个面板只在服务端上报 `workspace` 能力时才渲染（由父组件决定）；它自己负责
 * 的是"读写正确"：创建走幂等键，删除带回读到的 revision，409 提示重新读取而不是
 * 原样重试。
 */
export default function WorkspacePanel({
  courseId,
  courseName = "",
  canFile = false,
  canEdit = false,
  canExportArchive = false,
  canImportArchive = false,
  canExportMarkdown = false,
  canExportDocx = false,
  canExportPptx = false,
  canExportVideo = false,
  canImportPptx = false,
}) {
  const [items, setItems] = React.useState([]);
  const [cursor, setCursor] = React.useState(null);
  const [folders, setFolders] = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState("");
  const [notice, setNotice] = React.useState("");
  const [name, setName] = React.useState("");
  const [targetFolder, setTargetFolder] = React.useState("");
  // 展开的 workspace 与它的场景列表：编辑入口只在用户主动展开后加载。
  const [openWorkspaceId, setOpenWorkspaceId] = React.useState("");
  const [stages, setStages] = React.useState([]);
  const [stageTitle, setStageTitle] = React.useState("");
  const [editingStageId, setEditingStageId] = React.useState("");
  // 切换课程后迟到的响应不得写进新课程上下文。
  const epoch = React.useRef(0);
  const importInputRef = React.useRef(null);
  const pptxInputRef = React.useRef(null);
  const [localReject, setLocalReject] = React.useState("");
  // 同一个用户动作的幂等键必须在重试之间保持不变，所以它跟着"这次提交"走，
  // 而不是每次请求现生成。
  const pendingKey = React.useRef(null);

  const load = React.useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const payload = await api.listMagicClassWorkspaces(courseId, { limit: WORKSPACE_PAGE_LIMIT });
      setItems(normalizeWorkspaceList(payload));
      setCursor(nextCursorOf(payload));
      // 只有服务端上报过 folder 能力时才会去读文件夹；否则归档下拉框根本不渲染。
      if (canFile) {
        const folderPayload = await api.listMagicClassFolders(courseId, { limit: DISCOVERY_PAGE_LIMIT });
        setFolders(normalizeFolderList(folderPayload));
      }
    } catch (err) {
      setItems([]);
      setCursor(null);
      setError(describeWorkspaceError(err).message);
    } finally {
      setLoading(false);
    }
  }, [canFile, courseId]);

  React.useEffect(() => {
    pendingKey.current = null;
    setName("");
    setNotice("");
    void load();
  }, [courseId, load]);

  const loadStages = React.useCallback(async (workspaceId) => {
    const mine = (epoch.current += 1);
    setError("");
    try {
      const payload = await api.listMagicClassStages(courseId, workspaceId, { limit: WORKSPACE_PAGE_LIMIT });
      if (mine !== epoch.current) return;
      setStages(normalizeStageList(payload));
    } catch (err) {
      if (mine !== epoch.current) return;
      setStages([]);
      setError(describeWorkspaceError(err).message);
    }
  }, [courseId]);

  async function toggleStages(item) {
    const next = openWorkspaceId === item.id ? "" : item.id;
    setOpenWorkspaceId(next);
    setEditingStageId("");
    setStages([]);
    setLocalReject("");
    if (importInputRef.current) importInputRef.current.value = "";
    if (pptxInputRef.current) pptxInputRef.current.value = "";
    // 换工作台就换一次"这次提交"：上一个工作台没提交的导入不该复用它的幂等键。
    pendingKey.current = null;
    if (next) await loadStages(next);
  }

  async function addStage(workspaceId) {
    const title = stageTitle.trim();
    if (!title) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api.createMagicClassStage(courseId, workspaceId, {
        title,
        idempotencyKey: api.newIdempotencyKey(),
      });
      setStageTitle("");
      setNotice(`已新增内容「${title}」`);
      await loadStages(workspaceId);
    } catch (err) {
      setError(describeWorkspaceError(err).message);
    } finally {
      setBusy(false);
    }
  }

  /**
   * 导出一份内容为 `.maic.zip`。
   *
   * 响应是字节流，所以走 blob；下载名由服务端的 `Content-Disposition` 决定。
   */
  async function exportStage(workspaceId, stage) {
    if (busy) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await api.exportMagicClassStage(courseId, workspaceId, stage.id);
      saveBlob(result.blob, filenameFromContentDisposition(result.disposition));
      setNotice(`已导出「${stage.title}」`);
    } catch (err) {
      setError(describeArchiveError(err).message);
    } finally {
      setBusy(false);
    }
  }

  async function exportFormat(workspaceId, stage, format) {
    if (busy) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await api.exportMagicClassStageFormat(courseId, workspaceId, stage.id, format);
      saveBlob(result.blob, filenameFromContentDisposition(result.disposition));
      setNotice(`已导出「${stage.title}」为 ${format.toUpperCase()}`);
    } catch (err) {
      setError(describeArchiveError(err).message);
    } finally {
      setBusy(false);
    }
  }

  async function exportVideo(workspaceId, stage) {
    if (busy) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const queued = await api.enqueueMagicClassStageVideo(courseId, workspaceId, stage.id, { idempotencyKey: api.newIdempotencyKey() });
      let job = queued.job || null;
      const jobId = queued.job_id || job?.id;
      if (!jobId) throw new Error("受管服务未返回视频导出任务");
      while (job && ["queued", "running"].includes(job.status)) {
        await new Promise((resolve) => window.setTimeout(resolve, 800));
        job = await api.getMagicClassJob(courseId, jobId);
      }
      if (!job || job.status !== "completed" || !job.artifact_id) throw new Error(job?.error_code || "视频导出失败");
      const artifact = await api.getMagicClassArtifact(courseId, job.artifact_id);
      saveBlob(artifact.blob, filenameFromContentDisposition(artifact.disposition) || `${stage.title}.mp4`);
      setNotice(`已导出「${stage.title}」为 MP4`);
    } catch (err) {
      setError(describeArchiveError(err).message || err.message || "视频导出失败");
    } finally { setBusy(false); }
  }

  /**
   * 导入一份 `.maic.zip`。
   *
   * 落点始终是当前展开的工作台：档案里的来源说明只是说明文字。
   * 可重试的失败复用同一个幂等键，否则重试会真的产生第二份内容。
   */
  async function importArchive(workspaceId) {
    const file = importInputRef.current?.files?.[0] || null;
    const rejected = validateImportCandidate(file);
    if (rejected) {
      setLocalReject(rejected);
      return;
    }
    if (busy) return;
    setBusy(true);
    setLocalReject("");
    setError("");
    setNotice("");
    pendingKey.current = pendingKey.current || api.newIdempotencyKey();
    try {
      const payload = await api.importMagicClassStage(courseId, workspaceId, {
        file,
        idempotencyKey: pendingKey.current,
      });
      pendingKey.current = null;
      if (importInputRef.current) importInputRef.current.value = "";
      const imported = normalizeImportedStage(payload);
      setNotice(
        imported
          ? `已导入「${imported.title}」${imported.migrated ? "（已按当前 DSL 版本迁移）" : ""}`
          : "已导入",
      );
      await loadStages(workspaceId);
    } catch (err) {
      const described = describeArchiveError(err);
      // 只有"这个档案本身不合格"才弃键；可重试的失败必须复用同一个键。
      if (!described.retryable) pendingKey.current = null;
      setError(described.message);
    } finally {
      setBusy(false);
    }
  }

  async function importPptx(workspaceId) {
    const file = pptxInputRef.current?.files?.[0] || null;
    if (!file) {
      setLocalReject("请选择一个 .pptx 课件。");
      return;
    }
    if (!/\.pptx$/i.test(String(file.name || ""))) {
      setLocalReject("请选择 .pptx 课件。");
      return;
    }
    if (Number(file.size) > 3 * 1024 * 1024) {
      setLocalReject("PPTX 不能超过 3 MB。");
      return;
    }
    if (busy) return;
    setBusy(true);
    setLocalReject("");
    setError("");
    setNotice("");
    try {
      const payload = await api.importMagicClassPptx(courseId, workspaceId, {
        file,
        idempotencyKey: api.newIdempotencyKey(),
      });
      if (pptxInputRef.current) pptxInputRef.current.value = "";
      const imported = normalizeImportedStage(payload);
      setNotice(imported ? `已导入 PPTX「${imported.title}」` : "已导入 PPTX");
      await loadStages(workspaceId);
    } catch (err) {
      setError(describeArchiveError(err).message);
    } finally {
      setBusy(false);
    }
  }

  async function loadMore() {
    if (!cursor) return;
    setBusy(true);
    setError("");
    try {
      const payload = await api.listMagicClassWorkspaces(courseId, {
        limit: WORKSPACE_PAGE_LIMIT,
        cursor,
      });
      setItems((current) => [...current, ...normalizeWorkspaceList(payload)]);
      setCursor(nextCursorOf(payload));
    } catch (err) {
      setError(describeWorkspaceError(err).message);
    } finally {
      setBusy(false);
    }
  }

  async function create(event) {
    event.preventDefault();
    const normalized = normalizeWorkspaceName(name);
    if (!normalized) return;
    // 同一次提交的键：失败后重试拿回同一个工作台，而不是再建一个。
    pendingKey.current ||= api.newIdempotencyKey();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const created = await api.createMagicClassWorkspace(courseId, {
        name: normalized,
        folderId: canFile && targetFolder ? targetFolder : undefined,
        idempotencyKey: pendingKey.current,
      });
      pendingKey.current = null;
      setName("");
      setTargetFolder("");
      setNotice(`已创建「${created.name}」`);
      await load();
    } catch (err) {
      const described = describeWorkspaceError(err);
      setError(described.message);
      if (described.kind === "idempotency") pendingKey.current = null;
    } finally {
      setBusy(false);
    }
  }

  /** 归档/取消归档。revision 必须用服务端最近一次返回的值。 */
  async function moveToFolder(item, folderId) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api.updateMagicClassWorkspace(courseId, item.id, {
        revision: item.revision,
        folderId: folderId || null,
      });
      setNotice(folderId ? `已把「${item.name}」移入文件夹` : `已把「${item.name}」移到未归档`);
      await load();
    } catch (err) {
      const described = describeWorkspaceError(err);
      setError(described.message);
      if (described.kind === "conflict") await load();
    } finally {
      setBusy(false);
    }
  }

  async function remove(item) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      // revision 用服务端最近一次返回的值；不本地推算。
      await api.deleteMagicClassWorkspace(courseId, item.id, { revision: item.revision });
      setNotice(`已删除「${item.name}」`);
      await load();
    } catch (err) {
      const described = describeWorkspaceError(err);
      setError(described.message);
      // 409 表示手上的副本过期：重新读取，而不是原样重试。
      if (described.kind === "conflict") await load();
    } finally {
      setBusy(false);
    }
  }

  const canSubmit = Boolean(normalizeWorkspaceName(name)) && !busy;

  return <Panel className="magicclass-workspaces">
    <SectionHeading title="学习工作台" detail={courseName ? `${courseName} · ${items.length} 个` : `${items.length} 个`} />

    <form className="magicclass-command" onSubmit={create}>
      <label className="magicclass-command__input">
        <Icon name="PhSquaresFour" size={18} />
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="新建工作台，例如「期末复习」"
          aria-label="工作台名称"
          maxLength={120}
        />
      </label>
      <Button type="submit" disabled={!canSubmit}>{busy ? "处理中…" : "创建工作台"}</Button>
      {/* 只有服务端上报过 folder 能力时才出现归档下拉框；否则不渲染死入口。 */}
      {canFile ? <select
        value={targetFolder}
        onChange={(event) => setTargetFolder(event.target.value)}
        aria-label="归档到文件夹"
        disabled={busy}
      >
        <option value="">未归档</option>
        {folders.map((folder) => <option key={folder.id} value={folder.id}>{folder.name}</option>)}
      </select> : null}
    </form>

    {notice && <p className="magicclass-hint" role="status">{notice}</p>}
    {error && <p className="magicclass-hint magicclass-hint--error" role="alert">{error}</p>}

    {loading ? <p className="magicclass-hint">正在读取工作台…</p>
      : items.length ? <>
        <div className="magicclass-workspace-list">{items.map((item) => <article className="magicclass-workspace-item" key={item.id}>
          <span className="row-icon tone-violet"><Icon name="PhSquaresFour" size={18} /></span>
          <span className="row-copy">
            <strong>{item.name}</strong>
            <small>{item.description || "暂无说明"} · 更新于 {dateText(item.updatedAt)}</small>
          </span>
          {/* 操作必须收进一个容器。`.magicclass-workspace-item` 是三列栅格
              （图标 / 文案 / 操作），若把 select 和三个按钮平铺成兄弟节点，它们会
              自动落到隐式第二行：32px 的第一列放"进入工作台"会被压成每行一个字，
              中间的"内容"则被 minmax(0,1fr) 拉成一整条。 */}
          <span className="magicclass-workspace-item__actions">
            {canFile ? <select
              value={item.folderId || ""}
              onChange={(event) => moveToFolder(item, event.target.value)}
              aria-label={`把「${item.name}」移动到文件夹`}
              disabled={busy}
            >
              <option value="">未归档</option>
              {folders.map((folder) => <option key={folder.id} value={folder.id}>{folder.name}</option>)}
            </select> : null}
            <LinkButton variant="quiet" to={`/courses/${courseId}/workspaces/${item.id}`}>进入工作台</LinkButton>
            <Button variant="quiet" disabled={busy} onClick={() => toggleStages(item)}>
              {openWorkspaceId === item.id ? "收起内容" : "内容"}
            </Button>
            <Button variant="quiet" disabled={busy} onClick={() => remove(item)}>删除</Button>
          </span>
        </article>)}</div>
        {cursor && <Button variant="quiet" disabled={busy} onClick={loadMore}>加载更多</Button>}
      </>
      : <div className="magicclass-home__empty"><Icon name="PhSquaresFour" size={24} /><p>还没有工作台</p><small>工作台用来把一门课的学习内容分开存放，例如「期末复习」「第三章练习」。</small></div>}

    {openWorkspaceId ? <section className="magicclass-stage-browser" aria-label="内容列表">
      <div className="magicclass-command">
        <label className="magicclass-command__input">
          <Icon name="PhLayout" size={18} />
          <input
            value={stageTitle}
            onChange={(event) => setStageTitle(event.target.value)}
            placeholder="新增内容，例如「第一章讲解」"
            aria-label="新增内容标题"
            maxLength={200}
          />
        </label>
        <Button type="button" disabled={!stageTitle.trim() || busy} onClick={() => addStage(openWorkspaceId)}>
          新增内容
        </Button>
      </div>

      {localReject ? <p className="magicclass-hint magicclass-hint--error" role="alert">{localReject}</p> : null}

      {/* 导入入口只在服务端上报 import-maic 时出现。 */}
      {canImportArchive ? <div className="magicclass-command">
        <label className="magicclass-command__input">
          <Icon name="PhFileText" size={18} />
          <input
            ref={importInputRef}
            type="file"
            accept=".zip,application/zip"
            aria-label="选择要导入的 .maic.zip 档案"
            onChange={(event) => setLocalReject(validateImportCandidate(event.target.files?.[0]) || "")}
          />
        </label>
        <Button type="button" variant="secondary" disabled={busy} onClick={() => importArchive(openWorkspaceId)}>
          导入档案
        </Button>
      </div> : null}

      {canImportPptx ? <div className="magicclass-command">
        <label className="magicclass-command__input">
          <Icon name="PhFileText" size={18} />
          <input
            ref={pptxInputRef}
            type="file"
            accept=".pptx,application/vnd.openxmlformats-officedocument.presentationml.presentation"
            aria-label="选择要导入的 PPTX 课件"
            onChange={(event) => setLocalReject(event.target.files?.[0] && !/\.pptx$/i.test(event.target.files[0].name) ? "请选择 .pptx 课件。" : "")}
          />
        </label>
        <Button type="button" variant="secondary" disabled={busy} onClick={() => importPptx(openWorkspaceId)}>
          导入 PPTX
        </Button>
      </div> : null}

      {stages.length ? <ul className="magicclass-stage-browser__list">
        {stages.map((stage) => <li key={stage.id}>
          <span className="row-copy">
            <strong>{stage.title}</strong>
            <small>{stage.dslVersion ? `DSL ${stage.dslVersion}` : "尚未写入内容"} · revision {stage.revision}</small>
          </span>
          {/* 导出只在服务端上报 export-maic 时出现。 */}
          {canExportArchive ? <Button
            type="button"
            variant="secondary"
            disabled={busy}
            onClick={() => exportStage(openWorkspaceId, stage)}
          >导出</Button> : null}
          {canExportMarkdown ? <Button type="button" variant="quiet" disabled={busy} onClick={() => exportFormat(openWorkspaceId, stage, "markdown")}>Markdown</Button> : null}
          {canExportDocx ? <Button type="button" variant="quiet" disabled={busy} onClick={() => exportFormat(openWorkspaceId, stage, "docx")}>DOCX</Button> : null}
          {canExportPptx ? <Button type="button" variant="quiet" disabled={busy} onClick={() => exportFormat(openWorkspaceId, stage, "pptx")}>PPTX</Button> : null}
          {canExportVideo ? <Button type="button" variant="quiet" disabled={busy} onClick={() => exportVideo(openWorkspaceId, stage)}>MP4</Button> : null}
          {canEdit ? <Button
            type="button"
            variant="secondary"
            onClick={() => setEditingStageId((current) => (current === stage.id ? "" : stage.id))}
          >{editingStageId === stage.id ? "结束编辑" : "编辑场景"}</Button> : null}
        </li>)}
      </ul> : <p className="magicclass-hint">这个工作台还没有内容。</p>}

      {/* 只有服务端上报 editor 能力时才挂载编辑器；未上报时连组件都不出现。 */}
      {canEdit && editingStageId ? <StageEditorPanel
        courseId={courseId}
        workspaceId={openWorkspaceId}
        stageId={editingStageId}
        onSaved={() => loadStages(openWorkspaceId)}
      /> : null}
    </section> : null}
  </Panel>;
}
