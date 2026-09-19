import React from "react";
import { Button, Panel, SectionHeading } from "../Primitives.jsx";
import { Icon } from "../Icon.jsx";
import * as api from "../../data/api.js";
import { formatDateTime } from "../../utils/date.js";
import {
  WORKSPACE_PAGE_LIMIT,
  describeWorkspaceError,
  nextCursorOf,
  normalizeWorkspaceList,
  normalizeWorkspaceName,
} from "../../features/openmaic/workspaceModel.js";
import {
  DISCOVERY_PAGE_LIMIT,
  normalizeFolderList,
} from "../../features/openmaic/discoveryModel.js";

const dateText = (value) => formatDateTime(value, { dateStyle: "medium", timeStyle: "short" }, "时间待定");

/**
 * 课程内的学习工作台列表。
 *
 * 这个面板只在服务端上报 `workspace` 能力时才渲染（由父组件决定）；它自己负责
 * 的是"读写正确"：创建走幂等键，删除带回读到的 revision，409 提示重新读取而不是
 * 原样重试。
 */
export default function WorkspacePanel({ courseId, courseName = "", canFile = false }) {
  const [items, setItems] = React.useState([]);
  const [cursor, setCursor] = React.useState(null);
  const [folders, setFolders] = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState("");
  const [notice, setNotice] = React.useState("");
  const [name, setName] = React.useState("");
  const [targetFolder, setTargetFolder] = React.useState("");
  // 同一个用户动作的幂等键必须在重试之间保持不变，所以它跟着"这次提交"走，
  // 而不是每次请求现生成。
  const pendingKey = React.useRef(null);

  const load = React.useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const payload = await api.listOpenMAICWorkspaces(courseId, { limit: WORKSPACE_PAGE_LIMIT });
      setItems(normalizeWorkspaceList(payload));
      setCursor(nextCursorOf(payload));
      // 只有服务端上报过 folder 能力时才会去读文件夹；否则归档下拉框根本不渲染。
      if (canFile) {
        const folderPayload = await api.listOpenMAICFolders(courseId, { limit: DISCOVERY_PAGE_LIMIT });
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

  async function loadMore() {
    if (!cursor) return;
    setBusy(true);
    setError("");
    try {
      const payload = await api.listOpenMAICWorkspaces(courseId, {
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
      const created = await api.createOpenMAICWorkspace(courseId, {
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
      await api.updateOpenMAICWorkspace(courseId, item.id, {
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
      await api.deleteOpenMAICWorkspace(courseId, item.id, { revision: item.revision });
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

  return <Panel className="openmaic-workspaces">
    <SectionHeading title="学习工作台" detail={courseName ? `${courseName} · ${items.length} 个` : `${items.length} 个`} />

    <form className="openmaic-command" onSubmit={create}>
      <label className="openmaic-command__input">
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

    {notice && <p className="openmaic-hint" role="status">{notice}</p>}
    {error && <p className="openmaic-hint openmaic-hint--error" role="alert">{error}</p>}

    {loading ? <p className="openmaic-hint">正在读取工作台…</p>
      : items.length ? <>
        <div className="openmaic-workspace-list">{items.map((item) => <article className="openmaic-workspace-item" key={item.id}>
          <span className="row-icon tone-violet"><Icon name="PhSquaresFour" size={18} /></span>
          <span className="row-copy">
            <strong>{item.name}</strong>
            <small>{item.description || "暂无说明"} · 更新于 {dateText(item.updatedAt)}</small>
          </span>
          {canFile ? <select
            value={item.folderId || ""}
            onChange={(event) => moveToFolder(item, event.target.value)}
            aria-label={`把「${item.name}」移动到文件夹`}
            disabled={busy}
          >
            <option value="">未归档</option>
            {folders.map((folder) => <option key={folder.id} value={folder.id}>{folder.name}</option>)}
          </select> : null}
          <Button variant="quiet" disabled={busy} onClick={() => remove(item)}>删除</Button>
        </article>)}</div>
        {cursor && <Button variant="quiet" disabled={busy} onClick={loadMore}>加载更多</Button>}
      </>
      : <div className="openmaic-home__empty"><Icon name="PhSquaresFour" size={24} /><p>还没有工作台</p><small>工作台用来把一门课的学习内容分开存放，例如「期末复习」「第三章练习」。</small></div>}
  </Panel>;
}
