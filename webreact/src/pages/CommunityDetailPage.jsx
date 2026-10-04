import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import * as api from "../data/api.js";
import { itemsOf, userErrorMessage } from "../data/contracts.js";
import { buildCommentTree } from "../data/alignment.js";
import { AsyncState, BackLink, Button, PageFrame, Panel, SectionHeading } from "../components/Primitives.jsx";

import { formatDateTime } from "../utils/date.js";
import { useAsyncResource } from "../hooks/useAsyncResource.js";

const dateText = (value) => formatDateTime(value, { dateStyle: "medium", timeStyle: "short" }, "时间待定");
const errorText = (error) => userErrorMessage(error, "操作失败，请稍后重试");

function CommentNode({ item, onReply }) {
  return <article className="comment-row"><span className="avatar avatar-small"><img src={item.author_avatar || "/assets/generated/home-reference-student-avatar.png"} alt="" /></span><div><strong>{item.is_anonymous ? "匿名同学" : item.author_name || "校园用户"}</strong><p>{item.content}</p><small>{dateText(item.created_at)} <button type="button" className="text-link" onClick={() => onReply(item.id)}>回复</button></small>{item.children?.length ? <div className="comment-children">{item.children.map((child) => <CommentNode key={child.id} item={child} onReply={onReply} />)}</div> : null}</div></article>;
}

export default function CommunityDetailPage() {
  const { postId } = useParams(); const navigate = useNavigate();
  const { data, loading, error: loadError, reload: load } = useAsyncResource(() => Promise.all([api.getCommunityPost(postId), api.getComments(postId)]), [postId]);
  const post = data?.[0] || null;
  const comments = itemsOf(data?.[1]);
  const error = loadError ? errorText(loadError) : "";
  const [notice, setNotice] = useState("");
  const [comment, setComment] = useState(""); const [anonymous, setAnonymous] = useState(false); const [parent, setParent] = useState(null);
  const commentTree = buildCommentTree(comments);
  async function submitComment(event) { event.preventDefault(); if (!comment.trim()) return; try { await api.createComment(postId, { content: comment.trim(), parent_comment_id: parent, is_anonymous: anonymous }); setComment(""); setParent(null); await load(); } catch (cause) { setNotice(errorText(cause)); } }
  async function remove() { if (!window.confirm("确认删除这条帖子吗？")) return; try { await api.deleteCommunityPost(postId); navigate("/community", { replace: true }); } catch (cause) { setNotice(errorText(cause)); } }
  async function toggleLike() { try { await (post?.liked ? api.unlikePost(postId) : api.likePost(postId)); await load(); } catch (cause) { setNotice(errorText(cause)); } }
  async function toggleFavorite() { try { await (post?.favorited ? api.unfavoritePost(postId) : api.favoritePost(postId)); await load(); } catch (cause) { setNotice(errorText(cause)); } }
  return <PageFrame eyebrow="Community / Detail" title={post?.title || "帖子详情"} description={post?.category || "校园社区"} actions={<BackLink to="/community">返回社区</BackLink>}><AsyncState loading={loading} error={error} onRetry={load}><div className="grid grid-2 reveal"><Panel><div className="post-detail-meta"><span className="avatar avatar-small"><img src={post?.author_avatar || "/assets/generated/home-reference-student-avatar.png"} alt="" /></span><span><strong>{post?.is_anonymous ? "匿名同学" : post?.author_name || "校园用户"}</strong><small>{dateText(post?.created_at)}</small></span></div><div className="rich-copy post-content">{post?.content || "暂无内容"}</div>{post?.images?.length ? <div className="post-images">{post.images.map((image) => <img key={image} src={api.resolveAssetUrl(image)} alt="帖子配图" width="180" height="130" />)}</div> : null}<div className="post-detail-actions"><Button variant="quiet" onClick={toggleLike}>{post?.liked ? "已点赞" : "点赞"} {post?.like_count || 0}</Button><Button variant="quiet" onClick={toggleFavorite}>{post?.favorited ? "已收藏" : "收藏"}</Button>{post?.is_owner && <Button variant="danger" icon="PhTrash" onClick={remove}>删除帖子</Button>}</div>{notice && <div className={`page-notice ${notice.includes("失败") ? "notice-error" : "notice-info"}`} role={notice.includes("失败") ? "alert" : "status"}>{notice}</div>}</Panel><Panel><SectionHeading title="评论" detail={`${comments.length} 条回应`} />{commentTree.length ? <div className="comment-list">{commentTree.map((item) => <CommentNode key={item.id} item={item} onReply={setParent} />)}</div> : <div className="inline-empty">还没有评论，来留下第一条回应。</div>}<form className="comment-form" onSubmit={submitComment}>{parent && <p className="muted-copy">正在回复一条评论 <Button type="button" variant="quiet" onClick={() => setParent(null)}>取消回复</Button></p>}<input required value={comment} onChange={(event) => setComment(event.target.value)} placeholder="写下你的回应…" aria-label="评论内容" /><label className="check-label"><input type="checkbox" checked={anonymous} onChange={(event) => setAnonymous(event.target.checked)} />匿名发表</label><Button icon="PhPaperPlaneRight">发送</Button></form></Panel></div></AsyncState></PageFrame>;
}
