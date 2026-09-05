import { Icon } from "../../../components/Icon.jsx";

function rankLabel(index) {
  return `TOP${index + 1}`;
}

function categoryLabel(category) {
  return ({
    campus: "校园生活",
    study: "学习交流",
    life: "生活随笔",
    activity: "校园活动",
    secondhand: "二手交易",
    question: "提问求助",
    recruit: "组队招募",
    errand: "校园互助",
    experience: "经验分享",
  }[category] || "校园论坛");
}

function relativeTime(value) {
  if (!value) return "";
  const time = new Date(value).getTime();
  if (Number.isNaN(time)) return "";
  const diff = Math.max(0, Date.now() - time);
  if (diff < 3600000) return `${Math.max(1, Math.floor(diff / 60000))} 分钟前`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`;
  if (diff < 172800000) return "昨天";
  return new Date(value).toLocaleDateString("zh-CN", { month: "numeric", day: "numeric" });
}

export default function CampusHotPostsPanel({ posts, onOpenPost }) {
  if (!posts?.length) {
    return (
      <div className="compact-empty">
        <Icon name="PhChatsCircle" size={26} /><strong>今日热门话题暂未生成</strong><span>去论坛看看，或发布第一条校园话题。</span>
      </div>
    );
  }
  return (
    <div className="hot-posts-list" aria-label="今日热门话题">
      {posts.map((post, index) => (
        <button key={post.id} onClick={() => onOpenPost?.(post.id)}>
          <span className="home-row-icon violet"><b>{rankLabel(index)}</b></span>
          <span><strong>{post.title}</strong><small>{categoryLabel(post.category)} · {post.like_count || 0} 赞 · {post.comment_count || 0} 评</small></span>
          <time>{relativeTime(post.created_at)}</time>
        </button>
      ))}
    </div>
  );
}
