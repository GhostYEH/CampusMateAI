import { userErrorMessage } from "../data/contracts.js";
import { useEffect, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import * as api from "../data/api.js";
import { AsyncState, BackLink, Button, PageFrame, Panel } from "../components/Primitives.jsx";
import { Icon } from "../components/Icon.jsx";
import { formatDateTime } from "../utils/date.js";
import { useAsyncResource } from "../hooks/useAsyncResource.js";

const dateText = (value) => formatDateTime(value, { dateStyle: "medium", timeStyle: "short" }, "时间待定");
const errorText = (error, fallback) => userErrorMessage(error, fallback);

export default function AnnouncementPage() {
  const { announcementId } = useParams(); const navigate = useNavigate(); const [searchParams] = useSearchParams();
  const { data: item, loading, error: loadError, reload: load } = useAsyncResource(() => api.getAnnouncement(announcementId), [announcementId]);
  const error = loadError ? errorText(loadError, "通知详情加载失败，请稍后重试") : "";
  const [notice, setNotice] = useState(""); const [read, setRead] = useState(null);
  useEffect(() => {
    let cancelled = false;
    if (item?.id && item.has_read === false) api.markAnnouncementRead(announcementId).then(() => {
      if (!cancelled) setRead({ id: announcementId, value: true });
    }).catch(() => {});
    return () => { cancelled = true; };
  }, [item?.id, item?.has_read, announcementId]);
  const isRead = read?.id === announcementId ? read.value : item?.has_read;
  const body = item?.content || item?.body || "";
  const extractText = [item?.title, body].filter(Boolean).join("\n");
  async function markRead() { try { await api.markAnnouncementRead(announcementId); setRead({ id: announcementId, value: true }); setNotice("已标记为已读"); } catch (cause) { setNotice(errorText(cause, "标记已读失败")); } }
  const source = searchParams.get("source") || item?.source_name || item?.course_name || item?.source || "课程班级";
  return <PageFrame eyebrow="Inbox / Announcement" title={item?.title || "通知详情"} description={source} actions={<><BackLink to="/notifications">返回通知</BackLink><Button variant="secondary" icon="PhArrowClockwise" onClick={load}>刷新</Button></>}><AsyncState loading={loading} error={error} onRetry={load}><Panel className="article-panel reveal"><div className="article-meta"><span><Icon name="PhBuildings" />来源：{source}</span><span><Icon name="PhCalendarBlank" />发布：{dateText(item?.published_at || item?.created_at)}</span>{item?.updated_at && <span>更新：{dateText(item.updated_at)}</span>}</div><div className="detail-grid"><div><span>发布人</span><strong>{item?.author_name || item?.publisher || "校园通知"}</strong></div><div><span>阅读要求</span><strong>{item?.require_read ? "需要确认阅读" : "普通通知"}</strong></div><div><span>当前状态</span><strong>{isRead ? "已读" : "未读"}</strong></div></div><div className="rich-copy">{body || "暂无通知内容"}</div><div className="form-footer"><Button variant="secondary" icon="PhListChecks" disabled={!extractText.trim()} onClick={() => navigate(`/notifications?extract=${encodeURIComponent(extractText)}`)}>生成待办</Button>{!isRead && <Button icon="PhCheck" onClick={markRead}>标记已读</Button>}</div>{notice && <div className={`page-notice ${notice.includes("失败") ? "notice-error" : "notice-info"}`} role={notice.includes("失败") ? "alert" : "status"}>{notice}</div>}</Panel></AsyncState></PageFrame>;
}
