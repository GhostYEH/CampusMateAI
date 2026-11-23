import "../styles/learning-space-native.css";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import * as api from "../data/api.js";
import { Button, PageFrame } from "../components/Primitives.jsx";
import SubmittedAssignmentReviews from "../components/SubmittedAssignmentReviews.jsx";
import { itemsOf } from "../data/contracts.js";
import { describeFusionState } from "../features/magicclass/homeModel.js";
import { normalizeWorkspaceList } from "../features/magicclass/workspaceModel.js";
import { useTopicClassroomGeneration } from "../features/magicclass/useTopicClassroomGeneration.js";

/**
 * 学习空间首页（原生版）。
 *
 * 这里**不渲染 iframe**：课堂内容与工作台都由 CampusMate 自己的页面承载，
 * 上游 magic class 只作为受管服务提供数据。视觉参考 Android 的互动课堂：
 * 深绿讲台 + 米白纸面 + 琥珀强调。
 *
 * 三条规则：
 * 1. 服务不可用时说清原因，不用一个点了没反应的按钮糊过去；
 * 2. 「最近学习」只用于回到**原生**课堂入口，不把用户带回内嵌页；
 * 3. 旧内嵌版仍保留在 `/learning-space/legacy`，可随时回退。
 */
export default function LearningSpaceHomePage() {
  const navigate = useNavigate();
  const [courses, setCourses] = useState([]);
  const [courseId, setCourseId] = useState("");
  const [topic, setTopic] = useState("");
  const [workspaces, setWorkspaces] = useState([]);
  const [recent, setRecent] = useState([]);
  const [fusion, setFusion] = useState(null);
  const [provider, setProvider] = useState(null);
  const [loading, setLoading] = useState(true);
  const [listLoading, setListLoading] = useState(false);
  const [error, setError] = useState(null);
  const [listError, setListError] = useState(null);
  const generation = useTopicClassroomGeneration(courseId);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [coursePayload, recentPayload, fusionStatus, providerStatus] = await Promise.all([
        api.getCourses(),
        api.getMagicClassRecent(6).catch(() => []),
        api.getMagicClassFusionStatus().catch(() => null),
        api.getMagicClassProviderStatus().catch(() => null),
      ]);
      const list = itemsOf(coursePayload).filter((course) => course && course.id != null);
      setCourses(list);
      setCourseId((current) => current || (list[0] ? String(list[0].id) : ""));
      setRecent(itemsOf(recentPayload).filter((item) => item && item.course_id));
      setFusion(fusionStatus);
      setProvider(providerStatus);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (!courseId) { setWorkspaces([]); return; }
    let alive = true;
    setListLoading(true);
    setListError(null);
    api.listMagicClassWorkspaces(courseId, { limit: 12 })
      .then((payload) => { if (alive) setWorkspaces(normalizeWorkspaceList(payload)); })
      .catch((err) => { if (alive) { setWorkspaces([]); setListError(err); } })
      .finally(() => { if (alive) setListLoading(false); });
    return () => { alive = false; };
  }, [courseId]);

  const fusionView = useMemo(() => describeFusionState(fusion), [fusion]);
  const canEnter = !loading && fusionView.state === "ready" && fusionView.canCreateWorkspace;
  const canGenerate = Boolean(courseId && canEnter && fusion?.capabilities?.includes("generation") && provider?.providers?.llm);
  const currentCourse = courses.find((course) => String(course.id) === courseId) || null;

  const enterClassroom = useCallback(() => {
    if (!courseId) return;
    navigate(`/courses/${courseId}/classroom`);
  }, [courseId, navigate]);

  return (
    <PageFrame className="lsn-page" showHeading={false}>
      <section className="lsn-hero" aria-label="互动课堂">
        <div className="lsn-hero__body">
          <span className="lsn-hero__eyebrow">学习空间</span>
          <h1>互动课堂</h1>
          <p>选好主题，走进你的课堂</p>
          <div className="lsn-hero__stats" role="list">
            <div role="listitem">
              <strong>{courses.length}</strong>
              <span>门课程</span>
            </div>
            <div role="listitem">
              <strong>{recent.length}</strong>
              <span>节最近课堂</span>
            </div>
            <div role="listitem">
              <strong>{workspaces.length}</strong>
              <span>个学习工作台</span>
            </div>
          </div>
        </div>
        <div className="lsn-hero__art" aria-hidden="true">
          <span className="lsn-hero__board" />
          <span className="lsn-hero__glow" />
        </div>
      </section>

      {loading && (
        <div className="lsn-state" aria-busy="true">
          <span className="loading-orb" />
          <p>正在读取你的课堂…</p>
        </div>
      )}

      {!loading && error && (
        <div className="lsn-state is-error" role="alert">
          <p>课堂数据读取失败：{String(error?.message || error)}</p>
          <Button variant="secondary" onClick={load}>重试</Button>
        </div>
      )}

      {!loading && !error && (
        <div className="lsn-grid">
          <section className="lsn-card lsn-start" aria-labelledby="lsn-start-title">
            <header className="lsn-card__head">
              <h2 id="lsn-start-title">开始一节课</h2>
              <span className={`lsn-chip ${canEnter ? "is-ready" : "is-warn"}`}>
                {canEnter ? "服务就绪" : fusionView.label}
              </span>
            </header>
            <p className="lsn-card__hint">
              {canEnter
                ? "选一门课程，输入想学的主题，自动安排讲解、动手活动和测验。"
                : fusionView.detail}
            </p>

            <label className="lsn-field">
              <span>课程</span>
              <select
                value={courseId}
                onChange={(event) => setCourseId(event.target.value)}
                disabled={!courses.length || generation.busy}
              >
                {!courses.length && <option value="">暂无可见课程</option>}
                {courses.map((course) => (
                  <option key={course.id} value={String(course.id)}>
                    {course.name || course.title || `课程 ${course.id}`}
                  </option>
                ))}
              </select>
            </label>

            {currentCourse && (
              <p className="lsn-course__meta">
                {currentCourse.code ? `${currentCourse.code} · ` : ""}
                {currentCourse.teacher_name || currentCourse.teacher || "教师信息待同步"}
              </p>
            )}

            <form className="lsn-topic" onSubmit={(event) => { event.preventDefault(); if (canGenerate) void generation.generate(topic); }}>
              <label className="lsn-field">
                <span>学习主题</span>
                <textarea value={topic} onChange={(event) => setTopic(event.target.value)} rows={3} maxLength={750}
                  placeholder="例如，比较圆柱和圆锥的空间结构" disabled={generation.busy} />
              </label>
              <div className="lsn-topic__actions">
                <Button type="submit" disabled={!canGenerate || !topic.trim() || generation.busy}>
                  {generation.busy ? generation.phase?.title || "正在生成…" : "生成互动课堂"}
                </Button>
                <Button type="button" variant="secondary" onClick={enterClassroom} disabled={!canEnter || !courseId || generation.busy}>
                  进入课堂 →
                </Button>
              </div>
              {generation.error && <p className="lsn-inline-error" role="alert">{generation.error}</p>}
              {!generation.error && canEnter && !canGenerate && courseId && (
                <p className="lsn-card__hint" role="status">课堂生成模型暂不可用，已有课堂仍可打开。</p>
              )}
            </form>

            {listError && (
              <p className="lsn-inline-error" role="status">
                工作台列表读取失败：{String(listError?.response?.data?.message || listError?.message || listError)}
              </p>
            )}
          </section>

          <section className="lsn-card lsn-workspaces" aria-labelledby="lsn-ws-title">
            <header className="lsn-card__head">
              <h2 id="lsn-ws-title">我的课堂</h2>
              {listLoading && <span className="lsn-chip">读取中…</span>}
            </header>
            {!listLoading && !workspaces.length ? (
              <div className="lsn-empty">
                <p>这门课还没有学习工作台。</p>
                <Button variant="secondary" onClick={enterClassroom} disabled={!canEnter || !courseId}>
                  现场生成一节
                </Button>
              </div>
            ) : (
              <ul className="lsn-list">
                {workspaces.map((workspace) => (
                  <li key={workspace.id}>
                    <Link to={`/courses/${courseId}/workspaces/${workspace.id}?mode=playback`} className="lsn-row">
                      <span className="lsn-row__title">{workspace.name}</span>
                      <span className="lsn-row__meta">
                        {workspace.description || "继续上次的课堂内容"}
                      </span>
                      <span className="lsn-row__go">继续学习 →</span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="lsn-card lsn-recent" aria-labelledby="lsn-recent-title">
            <header className="lsn-card__head">
              <h2 id="lsn-recent-title">最近学习</h2>
              <span className="lsn-card__aside">回到对应课程的课堂</span>
            </header>
            {!recent.length ? (
              <div className="lsn-empty"><p>还没有完成的课堂记录。</p></div>
            ) : (
              <ul className="lsn-list">
                {recent.map((item) => (
                  <li key={`${item.course_id}-${item.id}`}>
                    <button
                      type="button"
                      className="lsn-row"
                      onClick={() => navigate(`/courses/${item.course_id}/classroom`)}
                    >
                      <span className="lsn-row__title">
                        {item.course_name} · {item.title || "学习课堂"}
                      </span>
                      <span className="lsn-row__meta">
                        {item.scenes_count ? `${item.scenes_count} 页 · ` : ""}
                        {item.updated_at ? new Date(item.updated_at).toLocaleString() : ""}
                      </span>
                      <span className="lsn-row__go">回到课程 →</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="lsn-card lsn-tools" aria-label="课堂学习工具">
            <header className="lsn-card__head">
              <h2>学习工具</h2>
            </header>
            <SubmittedAssignmentReviews compact />
          </section>
        </div>
      )}
    </PageFrame>
  );
}
