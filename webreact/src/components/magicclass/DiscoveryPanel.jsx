import React from "react";
import { Link } from "react-router-dom";
import { Button, Panel, SectionHeading } from "../Primitives.jsx";
import { Icon } from "../Icon.jsx";
import * as api from "../../data/api.js";
import { formatDateTime } from "../../utils/date.js";
import {
  DISCOVERY_PAGE_LIMIT,
  buildFolderTree,
  describeDiscoveryError,
  isSearchableQuery,
  nextCursorOf,
  normalizeFolderList,
  normalizeFolderName,
  normalizeSearchResults,
  searchHitKey,
} from "../../features/magicclass/discoveryModel.js";

const dateText = (value) => formatDateTime(value, { dateStyle: "medium", timeStyle: "short" }, "时间待定");

/**
 * 课程内的文件夹与站内搜索。
 *
 * 只在服务端真实上报 `folder` / `search` 能力时由父组件渲染。它自己不假设
 * 任何能力存在：两个区块各自按 `canBrowseFolders` / `canSearch` 开关，
 * 关掉的那一块不渲染，而不是渲染一个点了必然失败的入口。
 */
export default function DiscoveryPanel({ courseId, canBrowseFolders = false, canSearch = false }) {
  const [folders, setFolders] = React.useState([]);
  const [cursor, setCursor] = React.useState(null);
  const [loading, setLoading] = React.useState(canBrowseFolders);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState("");
  const [notice, setNotice] = React.useState("");
  const [name, setName] = React.useState("");
  const [expanded, setExpanded] = React.useState(() => new Set());
  // 同一个用户动作重试必须复用同一个幂等键，所以它跟着"这次提交"走。
  const pendingKey = React.useRef(null);

  const [query, setQuery] = React.useState("");
  const [hits, setHits] = React.useState([]);
  const [searchCursor, setSearchCursor] = React.useState(null);
  const [searching, setSearching] = React.useState(false);
  const [searchedFor, setSearchedFor] = React.useState("");
  const [searchError, setSearchError] = React.useState("");

  const load = React.useCallback(async () => {
    if (!canBrowseFolders) return;
    setLoading(true);
    setError("");
    try {
      const payload = await api.listMagicClassFolders(courseId, { limit: DISCOVERY_PAGE_LIMIT });
      setFolders(normalizeFolderList(payload));
      setCursor(nextCursorOf(payload));
    } catch (failure) {
      const described = describeDiscoveryError(failure);
      setError(described.message);
    } finally {
      setLoading(false);
    }
  }, [canBrowseFolders, courseId]);

  React.useEffect(() => {
    setFolders([]);
    setCursor(null);
    setExpanded(new Set());
    setHits([]);
    setSearchCursor(null);
    setSearchedFor("");
    setQuery("");
    void load();
  }, [courseId, load]);

  const tree = React.useMemo(() => buildFolderTree(folders), [folders]);

  async function createFolder(event) {
    event.preventDefault();
    const normalized = normalizeFolderName(name);
    if (!normalized || busy) return;
    setBusy(true);
    setError("");
    setNotice("");
    pendingKey.current = pendingKey.current || api.newIdempotencyKey();
    try {
      await api.createMagicClassFolder(courseId, { name: normalized, idempotencyKey: pendingKey.current });
      pendingKey.current = null;
      setName("");
      setNotice(`已创建文件夹「${normalized}」`);
      await load();
    } catch (failure) {
      const described = describeDiscoveryError(failure);
      // 只有"这次提交本身有问题"才弃键；503 之类可重试的失败必须复用同一个键，
      // 否则重试会真的再建一个文件夹。
      if (!described.retryable) pendingKey.current = null;
      setError(described.message);
    } finally {
      setBusy(false);
    }
  }

  async function removeFolder(folder) {
    if (busy) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api.deleteMagicClassFolder(courseId, folder.id, { revision: folder.revision });
      setNotice(`已删除文件夹「${folder.name}」，其中的内容已移到未归档`);
      await load();
    } catch (failure) {
      const described = describeDiscoveryError(failure);
      setError(described.message);
      // 409 说明本地副本过期：重新读取是唯一能继续的动作。
      if (described.kind === "conflict") await load();
    } finally {
      setBusy(false);
    }
  }

  async function runSearch(event, { append = false } = {}) {
    event?.preventDefault?.();
    if (!isSearchableQuery(query) || searching) {
      if (!isSearchableQuery(query)) setSearchError("请输入 1–200 个字符的关键词。");
      return;
    }
    setSearching(true);
    setSearchError("");
    try {
      const payload = await api.searchMagicClassContent(courseId, {
        query: query.trim(),
        limit: DISCOVERY_PAGE_LIMIT,
        cursor: append ? searchCursor : null,
      });
      const nextHits = normalizeSearchResults(payload);
      setHits((previous) => (append ? [...previous, ...nextHits] : nextHits));
      setSearchCursor(nextCursorOf(payload));
      setSearchedFor(query.trim());
    } catch (failure) {
      setSearchError(describeDiscoveryError(failure).message);
    } finally {
      setSearching(false);
    }
  }

  if (!canBrowseFolders && !canSearch) return null;

  return <Panel className="magicclass-discovery-panel">
    <SectionHeading title="内容整理" detail="文件夹与站内搜索" />

    {notice ? <p className="magicclass-discovery__notice" role="status">{notice}</p> : null}
    {error ? <p className="magicclass-discovery__error" role="alert">{error}</p> : null}

    {canBrowseFolders ? <div className="magicclass-discovery__folders">
      <form className="magicclass-discovery__create" onSubmit={createFolder}>
        <label className="magicclass-discovery__input">
          <Icon name="PhFolderSimplePlus" size={18} />
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="新建文件夹名称"
            aria-label="新建文件夹名称"
          />
        </label>
        <Button type="submit" disabled={!normalizeFolderName(name) || busy}>{busy ? "处理中" : "新建文件夹"}</Button>
      </form>

      {loading ? <p className="muted-copy">正在读取文件夹…</p>
        : tree.roots.length ? <ul className="magicclass-folder-tree">
          {tree.roots.map((folder) => <FolderRow
            key={folder.id}
            folder={folder}
            tree={tree}
            expanded={expanded}
            onToggle={(id) => setExpanded((previous) => {
              const next = new Set(previous);
              if (next.has(id)) next.delete(id); else next.add(id);
              return next;
            })}
            onRemove={removeFolder}
            busy={busy}
          />)}
        </ul>
        : <div className="magicclass-home__empty magicclass-home__empty--wide">
          <Icon name="PhFolderSimple" size={26} />
          <div><strong>还没有文件夹</strong><p>把同一门课的内容分组后，这里会显示文件夹树。</p></div>
        </div>}
    </div> : null}

    {canSearch ? <div className="magicclass-discovery__search">
      <form className="magicclass-discovery__create" onSubmit={runSearch}>
        <label className="magicclass-discovery__input">
          <Icon name="PhMagnifyingGlass" size={18} />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="搜索本课程内我的工作台与内容"
            aria-label="搜索我的课程内容"
            maxLength={200}
          />
        </label>
        <Button type="submit" disabled={!isSearchableQuery(query) || searching}>{searching ? "搜索中" : "搜索"}</Button>
      </form>

      {searchError ? <p className="magicclass-discovery__error" role="alert">{searchError}</p> : null}

      {searchedFor && !hits.length && !searchError ? <p className="muted-copy">没有找到与「{searchedFor}」匹配的内容。</p> : null}

      {hits.length ? <div className="magicclass-search-hits">
        <p className="muted-copy">「{searchedFor}」的匹配结果</p>
        {hits.map((hit) => hit.href ? <Link className="magicclass-search-hit" key={searchHitKey(hit)} to={hit.href}>
          <span className="magicclass-search-hit__kind">{hit.kind === "stage" ? "内容" : "工作台"}</span>
          <strong>{hit.title}</strong>
          {hit.snippet ? <small>{hit.snippet}</small> : null}
          <span className="magicclass-search-hit__date">{dateText(hit.updatedAt)}</span>
        </Link> : <div className="magicclass-search-hit" key={searchHitKey(hit)}>
          <span className="magicclass-search-hit__kind">{hit.kind === "stage" ? "内容" : "工作台"}</span>
          <strong>{hit.title}</strong>
          <small>该条目暂时没有可用的站内位置。</small>
        </div>)}
        {searchCursor ? <Button type="button" variant="secondary" onClick={() => runSearch(null, { append: true })} disabled={searching}>
          加载更多
        </Button> : null}
      </div> : null}
    </div> : null}
  </Panel>;
}

function FolderRow({ folder, tree, expanded, onToggle, onRemove, busy }) {
  const children = tree.childrenOf(folder.id);
  const isOpen = expanded.has(folder.id);
  return <li className="magicclass-folder-tree__node">
    <div className="magicclass-folder-tree__row">
      {children.length ? <button
        type="button"
        className="magicclass-folder-tree__toggle"
        aria-expanded={isOpen}
        aria-label={`${isOpen ? "收起" : "展开"}「${folder.name}」`}
        onClick={() => onToggle(folder.id)}
      ><Icon name={isOpen ? "PhCaretDown" : "PhCaretRight"} size={14} /></button>
        : <span className="magicclass-folder-tree__spacer" aria-hidden="true" />}
      <Icon name="PhFolderSimple" size={17} />
      <span className="magicclass-folder-tree__name">{folder.name}</span>
      <small>{folder.workspaceCount} 个内容</small>
      <Button type="button" variant="secondary" disabled={busy} onClick={() => onRemove(folder)}>删除</Button>
    </div>
    {children.length && isOpen ? <ul className="magicclass-folder-tree__children">
      {children.map((child) => <FolderRow
        key={child.id}
        folder={child}
        tree={tree}
        expanded={expanded}
        onToggle={onToggle}
        onRemove={onRemove}
        busy={busy}
      />)}
    </ul> : null}
  </li>;
}
