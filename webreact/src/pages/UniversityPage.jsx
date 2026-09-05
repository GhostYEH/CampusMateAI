import { useEffect, useState } from "react";
import * as api from "../data/api.js";
import { itemsOf } from "../data/contracts.js";
import { AsyncState, Button, PageFrame } from "../components/Primitives.jsx";
import { Icon } from "../components/Icon.jsx";
import { formatDateTime } from "../utils/date.js";

function useLoad(loader, deps = []) {
  const [state, setState] = useState({ data: null, loading: true, error: "" });
  const [version, setVersion] = useState(0);
  useEffect(() => {
    let active = true;
    setState((current) => ({ ...current, loading: true, error: "" }));
    Promise.resolve().then(loader).then((data) => active && setState({ data, loading: false, error: "" })).catch((error) => active && setState({ data: null, loading: false, error: error?.response?.data?.message || error?.message || "加载失败，请稍后重试" }));
    return () => { active = false; };
  // Loader is intentionally recreated by the page; version and explicit deps control reloads.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, version]);
  return { ...state, reload: () => setVersion((current) => current + 1) };
}

const list = itemsOf;
const errorText = (error, fallback = "操作失败") => error?.response?.data?.message || error?.response?.data?.detail || error?.message || fallback;

function PageNotice({ message, tone = "info" }) { return message ? <div className={`page-notice notice-${tone}`} role={tone === "error" ? "alert" : "status"}><Icon name={tone === "error" ? "PhWarningCircle" : "PhInfo"} size={17} />{message}</div> : null; }
function FilterBar({ value, onChange, placeholder = "搜索…" }) { return <div className="filter-bar"><label className="search-field-wrap"><Icon name="PhMagnifyingGlass" size={17} /><input className="search-field" value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} /></label></div>; }

export default function UniversityPage() {
  const resource = useLoad(() => Promise.all([api.getUniversities({ page_size: 50 }), api.getProfile()]), []);
  const [query, setQuery] = useState("");
  const [notice, setNotice] = useState("");
  const current = resource.data?.[1]?.university_id;
  const items = list(resource.data?.[0]).filter((item) => `${item.name} ${item.short_name} ${item.city}`.toLocaleLowerCase().includes(query.toLocaleLowerCase()));

  async function choose(item) {
    if (!window.confirm(`切换到 ${item.name} 后，论坛内容将切换到新学校。个人待办不会删除。`)) return;
    try {
      await api.selectUniversity(item.id);
      setNotice(`已切换到 ${item.name}`);
      resource.reload();
    } catch (error) {
      setNotice(errorText(error, "切换大学失败"));
    }
  }

  return <PageFrame eyebrow="Identity / University" title="我的大学" description="校园公共内容会按你的大学身份隔离。" actions={<Button variant="secondary" icon="PhArrowClockwise" onClick={resource.reload}>刷新</Button>}><FilterBar value={query} onChange={setQuery} placeholder="搜索大学名称或简称" /><PageNotice message={notice} tone={notice.includes("失败") ? "error" : "info"} /><AsyncState loading={resource.loading} error={resource.error} empty={!items.length ? "没有匹配的大学" : null} onRetry={resource.reload}><div className="stack reveal">{items.map((item) => <article className="university-row panel" key={item.id}><span className="university-logo">{(item.short_name || item.name || "校").slice(0, 2)}</span><div><span className="eyebrow">{item.province || item.city || "CAMPUS"}</span><h2>{item.name}</h2><p>{item.city || "城市待补充"} · 校园社区{item.forum_enabled ? "已开放" : "待开放"}</p>{item.official_website && <a className="text-link" href={item.official_website} target="_blank" rel="noreferrer">学校官网</a>}</div><Button variant={current === item.id ? "secondary" : "primary"} disabled={current === item.id} onClick={() => choose(item)}>{current === item.id ? "当前大学" : "选择大学"}</Button></article>)}</div></AsyncState></PageFrame>;
}
