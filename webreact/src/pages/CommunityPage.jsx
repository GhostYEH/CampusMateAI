import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import * as api from "../data/api.js";
import { Icon } from "../components/Icon.jsx";
import LineSidebar from "../components/LineSidebar.jsx";
import "../styles/community.css";

const PAGE_SIZE = 20;

const FALLBACK_CATS = [
  { key: "question", label: "提问", icon: "PhQuestion", color: "#3b82f6" },
  { key: "recruit", label: "招募", icon: "PhUsers", color: "#8b5cf6" },
  { key: "errand", label: "带价帮忙", icon: "PhHandCoins", color: "#f59e0b" },
  { key: "campus", label: "校园动态", icon: "PhBuildings", color: "#10b981" },
  { key: "study", label: "学习交流", icon: "PhBookOpen", color: "#06b6d4" },
  { key: "life", label: "生活随笔", icon: "PhCoffee", color: "#ec4899" },
  { key: "secondhand", label: "二手交易", icon: "PhStorefront", color: "#6366f1" },
  { key: "activity", label: "活动", icon: "PhCalendarHeart", color: "#14b8a6" },
  { key: "experience", label: "经验分享", icon: "PhLightbulb", color: "#f97316" },
  { key: "other", label: "其它", icon: "PhDotsThree", color: "#6b7280" },
];

const ANNOUNCEMENTS = [
  ["新学期社区秩序公约", "08/15"],
  ["关于规范二手交易的通知", "08/10"],
  ["校园论坛发帖规范更新", "08/05"],
  ["防诈骗安全提示", "07/28"],
];

const TIPS = [
  ["选择合适的分类", "选对分类能让更多人看到你的帖子", "PhSealCheck"],
  ["标题简明有吸引力", "清晰的标题更容易获得回复", "PhNotePencil"],
  ["补充详细内容", "完整的信息能更快得到帮助", "PhChatCircleText"],
  ["文明友善交流", "尊重他人，共建温暖社区", "PhUsersThree"],
];

const HOT_TONES = ["violet", "orange", "blue", "green"];

function catMeta(key, categories) {
  const fromApi = categories.find((c) => c.key === key);
  return fromApi || FALLBACK_CATS.find((c) => c.key === key) || { label: key, icon: "PhDotsThree", color: "#6b7280" };
}

function buildExtraTags(post) {
  const e = post.extra || {};
  const cat = post.category;
  const tags = [];
  if (cat === "recruit") {
    if (e.headcount) tags.push(`招募 ${e.headcount} 人`);
    if (e.location) tags.push(`地点：${e.location}`);
    if (e.deadline) tags.push(`截止：${e.deadline}`);
  } else if (cat === "errand") {
    if (e.price != null) tags.push(`酬金 ¥${e.price}`);
    if (e.location) tags.push(`地点：${e.location}`);
    if (e.deadline) tags.push(`截止：${e.deadline}`);
  }
  return tags;
}

function timeText(value) {
  try { return new Date(value).toLocaleString("zh-CN"); } catch { return value; }
}

function PostCard({ post, categories, onLike, onFavorite, onOpen, onReport }) {
  const meta = catMeta(post.category, categories);
  const content = post.content || "";
  const excerpt = content.length > 200 ? content.slice(0, 200) + "…" : content;
  const previewImages = (post.images || []).slice(0, 1);
  const extraTags = buildExtraTags(post);
  return (
    <article className="forum-card" onClick={() => onOpen(post)}>
      <header className="forum-card-head">
        <span className="forum-avatar">{(post.author_name || "同").slice(0, 1)}</span>
        <div className="forum-card-meta">
          <strong>{post.is_anonymous ? "匿名同学" : post.author_name || "校园用户"}</strong>
          <small>
            <span className="forum-cat-tag" style={{ background: meta.color + "22", color: meta.color }}><Icon name={meta.icon} size={13} />{meta.label}</span>
            · {timeText(post.created_at)}
          </small>
        </div>
      </header>
      <h2 className="forum-card-title">{post.title}</h2>
      <p className="forum-card-content">{excerpt}</p>
      {extraTags.length > 0 && (
        <div className="forum-extra-tags">{extraTags.map((t) => <span key={t} className="forum-extra-tag">{t}</span>)}</div>
      )}
      {previewImages.length > 0 && (
        <div className="forum-card-images">{previewImages.map((url, i) => <img key={url + i} src={api.resolveAssetUrl(url)} alt="帖子图片" loading="lazy" />)}</div>
      )}
      <footer className="forum-card-foot">
        <button type="button" className={post.liked ? "active" : ""} onClick={(e) => { e.stopPropagation(); onLike(post); }}><Icon name={post.liked ? "PhHeart" : "PhHeartStraight"} size={16} />{post.like_count || 0}</button>
        <button type="button" onClick={(e) => { e.stopPropagation(); onOpen(post); }}><Icon name="PhChatCircle" size={16} />{post.comment_count || 0}</button>
        <button type="button" className={post.favorited ? "active" : ""} onClick={(e) => { e.stopPropagation(); onFavorite(post); }}><Icon name={post.favorited ? "PhBookmarkSimple" : "PhBookmark"} size={16} />{post.favorite_count || 0}</button>
        {!post.is_owner ? (
          <button type="button" className="forum-report-btn" onClick={(e) => { e.stopPropagation(); onReport(post); }}><Icon name="PhFlag" size={14} /></button>
        ) : (
          <span className="forum-owner-mark">我的发布</span>
        )}
      </footer>
    </article>
  );
}

export default function CommunityPage() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [sort, setSort] = useState("time");
  const [categories, setCategories] = useState([]);
  const [hotTopics, setHotTopics] = useState(["图书馆占位技巧", "食堂隐藏菜单", "本周社团招新", "期末复习资料"]);
  const [showReport, setShowReport] = useState(false);
  const [reportTarget, setReportTarget] = useState(null);
  const [reportReason, setReportReason] = useState("垃圾广告");
  const [reportDetails, setReportDetails] = useState("");

  const categoryOptions = categories.length ? categories : FALLBACK_CATS;
  const categorySidebarItems = [{ key: "all", label: "全部", icon: "PhSquaresFour" }, ...categoryOptions];
  const hasMore = items.length < total;

  useEffect(() => {
    let alive = true;
    (async () => {
      try { const data = await api.getCommunityCategories(); if (alive) setCategories(data.items || []); } catch { /* keep fallback */ }
    })();
    return () => { alive = false; };
  }, []);

  async function load(reset = false) {
    const targetPage = reset ? 1 : page;
    if (reset) { setPage(1); setItems([]); }
    setLoading(true); setError("");
    try {
      const params = { page: targetPage, page_size: PAGE_SIZE, sort };
      if (query.trim()) params.q = query.trim();
      if (category) params.category = category;
      const data = await api.getCommunityPosts(params);
      const next = data.items || [];
      setItems((current) => reset ? next : [...current, ...next.filter((item) => !current.some((e) => e.id === item.id))]);
      setTotal(Number(data.total || 0));
    } catch (e) {
      setError(e.response?.data?.code === "UNIVERSITY_REQUIRED" ? "请先选择你的大学，再进入校园论坛。" : (e.response?.data?.message || "论坛加载失败"));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(true); }, [query, category, sort]);

  async function onLike(post) {
    try { const next = await (post.liked ? api.unlikePost(post.id) : api.likePost(post.id)); setItems((current) => current.map((item) => item.id === next.id ? next : item)); } catch (e) { setError(e.response?.data?.message || "操作失败"); }
  }
  async function onFavorite(post) {
    try { const next = await (post.favorited ? api.unfavoritePost(post.id) : api.favoritePost(post.id)); setItems((current) => current.map((item) => item.id === next.id ? next : item)); } catch (e) { setError(e.response?.data?.message || "操作失败"); }
  }
  function onReport(post) { setReportTarget(post); setReportReason("垃圾广告"); setReportDetails(""); setShowReport(true); }
  async function submitReport() {
    if (!reportTarget) return;
    try { await api.reportPost({ target_id: reportTarget.id, reason: reportReason, details: reportDetails || null }); setShowReport(false); } catch (e) { setError(e.response?.data?.message || "举报失败"); }
  }
  function chooseTopic(topic) { setQuery(topic); }
  function loadMore() { const next = page + 1; setPage(next); load(false); }

  return (
    <main className="forum-page">
      <section className="forum-hero">
        <div>
          <span className="forum-kicker">CAMPUSMATE FORUM</span>
          <h1>校园论坛 <Icon name="PhSparkle" size={25} /></h1>
          <p>校园墙 · 提问 / 招募 / 带价帮忙 / 热门讨论，一站刷到。</p>
        </div>
        <button className="forum-publish" onClick={() => navigate("/community/create")}><Icon name="PhPlus" />发布帖子</button>
      </section>

      <div className="forum-columns">
        <aside className="forum-panel forum-filter-sidebar">
          <div className="forum-filter-heading">
            <span className="forum-filter-eyebrow">BROWSE BY</span>
            <h2><Icon name="PhList" size={16} />帖子分类</h2>
            <span className="forum-filter-count">{category ? "已选择 1 个分类" : "浏览全部讨论"}</span>
          </div>
          <LineSidebar
            items={categorySidebarItems}
            defaultActive={Math.max(0, categorySidebarItems.findIndex((item) => item.key === (category || "all")))}
            onItemClick={(_index) => {
              const key = categorySidebarItems[_index].key;
              setCategory(key === "all" ? "" : key);
            }}
          />
        </aside>

        <div className="forum-main-column">
          <section className="forum-panel forum-toolbar">
            <div className="forum-toolbar-right">
              <form className="forum-search" onSubmit={(e) => { e.preventDefault(); load(true); }}>
                <Icon name="PhMagnifyingGlass" size={17} />
                <input value={query} aria-label="搜索标题或内容" placeholder="搜索标题或内容" onChange={(e) => setQuery(e.target.value)} />
              </form>
              <div className="forum-sort">
                <button className={sort === "time" ? "active" : ""} onClick={() => setSort("time")}>最新</button>
                <button className={sort === "hot" ? "active" : ""} onClick={() => setSort("hot")}>热门</button>
              </div>
            </div>
          </section>

          <section className="forum-panel hot-topics">
            <span className="hot-topics-title"><span>🔥</span><strong>今日热门话题</strong></span>
            {hotTopics.map((label, i) => (
              <button key={label} className={`hot-topic ${HOT_TONES[i % HOT_TONES.length]}`} onClick={() => chooseTopic(label)}>{label} <small>热</small></button>
            ))}
            <button className="hot-refresh" onClick={() => setHotTopics((current) => [...current.slice(1), current[0]])}>换一换 <Icon name="PhArrowClockwise" size={14} /></button>
          </section>

          {error && <div className="forum-alert"><Icon name="PhWarningCircle" />{error}<button onClick={() => load(true)}>重试</button></div>}

          {loading && !items.length ? (
            <section className="forum-panel forum-loading"><i></i><i></i><i></i></section>
          ) : !items.length ? (
            <section className="forum-panel forum-empty">
              <Icon name="PhChatsCircle" size={40} />
              <strong>暂无帖子</strong>
              <span>成为当前大学第一个发帖的同学吧。</span>
              <button className="forum-publish" onClick={() => navigate("/community/create")}>发布第一篇帖子</button>
            </section>
          ) : (
            <section className="forum-feed">
              {items.map((item) => <PostCard key={item.id} post={item} categories={categoryOptions} onLike={onLike} onFavorite={onFavorite} onOpen={(post) => navigate(`/community/${post.id}`)} onReport={onReport} />)}
            </section>
          )}

          {hasMore && !loading ? (
            <div className="forum-load-more"><button onClick={loadMore}>加载更多</button></div>
          ) : items.length ? (
            <p className="forum-end-note">已经到底啦，没有更多内容了～</p>
          ) : null}
        </div>

        <aside className="forum-side-column">
          <section className="forum-panel forum-side-card">
            <header><h2><Icon name="PhMegaphone" />社区公告</h2><button>更多 <Icon name="PhCaretRight" size={13} /></button></header>
            {ANNOUNCEMENTS.map(([title, date]) => (
              <button key={title} className="announcement-row" onClick={() => setQuery(title)}><span>{title}</span><time>{date}</time></button>
            ))}
          </section>
          <section className="forum-panel forum-side-card">
            <header><h2><Icon name="PhLightbulb" />发帖小贴士</h2><button>更多 <Icon name="PhCaretRight" size={13} /></button></header>
            {TIPS.map(([title, desc, icon]) => (
              <button key={title} className="tip-row" onClick={() => navigate("/community/create")}>
                <span className="tip-icon"><Icon name={icon} size={16} /></span>
                <span><strong>{title}</strong><small>{desc}</small></span>
              </button>
            ))}
            <button className="tips-guide" onClick={() => navigate("/community/create")}>查看发帖指南</button>
          </section>
        </aside>
      </div>

      {showReport && (
        <div className="forum-modal-mask" onClick={(e) => { if (e.target === e.currentTarget) setShowReport(false); }}>
          <div className="forum-modal">
            <h3><Icon name="PhFlag" />举报帖子</h3>
            <p className="forum-modal-desc">选择举报原因，管理员将审核处理。</p>
            <div className="forum-report-reasons">
              {["垃圾广告", "辱骂攻击", "色情低俗", "违法违规", "隐私泄露", "诈骗", "其它"].map((reason) => (
                <button key={reason} className={reportReason === reason ? "active" : ""} onClick={() => setReportReason(reason)}>{reason}</button>
              ))}
            </div>
            <label className="forum-field">补充说明（可选）<textarea value={reportDetails} rows={3} onChange={(e) => setReportDetails(e.target.value)} /></label>
            <div className="forum-modal-actions">
              <button className="secondary" onClick={() => setShowReport(false)}>取消</button>
              <button className="primary" onClick={submitReport}>提交举报</button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
