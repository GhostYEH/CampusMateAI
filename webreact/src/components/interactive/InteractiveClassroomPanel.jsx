import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import * as api from "../../data/api.js";
import {
  CLASSROOM_STATES,
  CLASSROOM_STATE_TEXT,
  INTERACTIVE_MODES,
  MODE_INTENT_NOTE,
  canGenerateInState,
  classroomState,
  compositionSummary,
  describeComposition,
  interactiveStepLabel,
  isSafeClassroomUrl,
  isSessionLive,
  normalizeMode,
  normalizeTrustedOrigins,
  trustedOriginsFromStatus,
} from "../../data/interactiveClassroom.js";
import { createEpochGuard } from "../../data/epochGuard.js";
import { createPollScope } from "../../data/pollScope.js";
import { Button, Panel, SectionHeading } from "../Primitives.jsx";
import { Icon } from "../Icon.jsx";
import ClassroomEmbed from "./ClassroomEmbed.jsx";

export const interactiveErrorText = (error, fallback = "操作失败，请稍后重试") => {
  if (typeof error === "string" && error.trim()) return error.trim();
  return (
    error?.response?.data?.detail ||
    error?.response?.data?.message ||
    (error?.response?.data?.code === "OPENMAIC_NOT_ENABLED" ? "互动课堂服务尚未配置，无法生成。" : null) ||
    (error?.response?.data?.code === "OPENMAIC_INCOMPATIBLE"
      ? "互动课堂服务版本不兼容，已暂停生成，请联系管理员核对部署版本。"
      : null) ||
    error?.message ||
    fallback
  );
};

const MODE_ICONS = {
  adaptive: "PhPath",
  explain: "PhChatCircleText",
  quiz: "PhExam",
  simulation: "PhFlask",
  visualization: "PhCube",
  mindmap: "PhTreeStructure",
  coding: "PhCode",
  pbl: "PhTray",
  review: "PhClockCounterClockwise",
};

const DIFFICULTY_OPTIONS = [
  { value: "beginner", label: "入门" },
  { value: "standard", label: "标准" },
  { value: "advanced", label: "进阶" },
];

const DURATION_OPTIONS = [15, 30, 45, 60];

const modeLabel = (mode) =>
  INTERACTIVE_MODES.find((m) => m.mode === normalizeMode(mode))?.label || "互动课堂";

const statusText = (state, status) => {
  const base = CLASSROOM_STATE_TEXT[state] || CLASSROOM_STATE_TEXT.not_configured;
  if (state === CLASSROOM_STATES.EMBED_BLOCKED && status?.browser_embed_reason) {
    return { ...base, body: status.browser_embed_reason };
  }
  return base;
};

/** 学生可见的生成前简报（不可用时也能展示课程与形态，只是不能生成）。 */
function PlanCard({
  plan,
  planLoading,
  brief,
  onBriefChange,
  onToggleMaterial,
  onGenerate,
  polling,
}) {
  if (planLoading && !plan) {
    return <p className="interactive-hint">正在准备这次的学习计划…</p>;
  }
  if (!plan) return null;
  const selected = new Set(brief.materialIds || []);
  return (
    <div className="interactive-plan">
      <h3>生成前请确认</h3>
      <ul className="interactive-plan-facts">
        <li>
          <span>课程</span>
          <strong>{plan.course_name || plan.course_id}</strong>
        </li>
        <li>
          <span>学习形态</span>
          <strong>{plan.mode_label || modeLabel(plan.mode)}</strong>
        </li>
        {plan.adaptive_reason ? (
          <li>
            <span>为什么推荐</span>
            <strong>{plan.adaptive_reason}</strong>
          </li>
        ) : null}
      </ul>

      {Array.isArray(plan.context_warnings) && plan.context_warnings.length > 0 ? (
        <div className="page-notice notice-warn" role="status">
          以下数据本次未能读取，生成结果可能不完整：{plan.context_warnings.join("；")}
        </div>
      ) : null}

      {Array.isArray(plan.materials) && plan.materials.length > 0 ? (
        <fieldset className="interactive-materials">
          <legend>使用哪些课程资料</legend>
          {plan.materials.map((material) => (
            <label key={material.id}>
              <input
                type="checkbox"
                checked={selected.has(material.id)}
                onChange={() => onToggleMaterial(material.id)}
              />
              <span>{material.title}</span>
              <small>{material.kind}</small>
            </label>
          ))}
        </fieldset>
      ) : (
        <p className="interactive-hint">这门课暂时没有已同步的可用资料，课堂将依据课程结构生成。</p>
      )}

      <p className="interactive-hint">{MODE_INTENT_NOTE}</p>

      <div className="interactive-actions interactive-primary">
        <Button icon="PhPlay" disabled={polling} onClick={() => onGenerate(plan.mode)}>
          确认生成 {plan.mode_label || modeLabel(plan.mode)}
        </Button>
      </div>
    </div>
  );
}

/** 真实组成展示：只呈现回读到的内容，绝不根据请求形态推断。 */
function CompositionBlock({ composition, loading, error, onReload }) {
  if (loading) return <p className="interactive-hint">正在读取这节课的真实内容…</p>;
  if (error) {
    return (
      <div className="page-notice notice-warn" role="status">
        课堂内容读取失败：{error}
        <button type="button" className="text-button" onClick={onReload}>
          重试
        </button>
      </div>
    );
  }
  const description = describeComposition(composition);
  if (!description) return null;
  if (description.error) {
    return (
      <div className="page-notice notice-warn" role="status">
        课堂内容读取失败：{description.error}
      </div>
    );
  }
  return (
    <div className="interactive-composition">
      <p>{compositionSummary(description)}</p>
      {description.widgets && description.widgets.length > 0 ? (
        <p className="interactive-hint">
          互动形式：
          {description.widgets.map((w) => `${w.label} ×${w.count}`).join("、")}
        </p>
      ) : null}
      {description.requires3d && !description.external3dAvailable ? (
        <p className="interactive-hint">
          这节课包含 3D 内容，但当前环境无法访问外部 3D 资源，这部分可能打不开。
        </p>
      ) : null}
      {description.requires3d && description.external3dAvailable ? (
        <p className="interactive-hint">这节课包含 3D 内容，需要能访问外部 CDN 才能正常查看。</p>
      ) : null}
    </div>
  );
}

/**
 * 互动课堂的**纯展示**视图：只由 props 决定渲染结果，不发起请求、不读取全局状态。
 * 拆出来是为了能用真实 React 渲染直接断言"成功课堂可以打开 / 不可信 Origin 必须降级"。
 */
export function InteractiveClassroomView({
  status = {},
  items = [],
  itemsLoading = false,
  mode = "adaptive",
  brief = { objective: "", currentDifficulty: "", duration: null, difficultyLevel: "", wantsMorePractice: false, materialIds: [] },
  plan = null,
  planLoading = false,
  session = null,
  polling = false,
  composition = null,
  compositionLoading = false,
  compositionError = "",
  error = "",
  notice = "",
  trustedEmbedOrigins = null,
  onSelectMode = () => {},
  onBriefChange = () => {},
  onToggleMaterial = () => {},
  onPreviewPlan = () => {},
  onGenerate = () => {},
  onRetry = () => {},
  onReset = () => {},
  onRefresh = () => {},
  onAskCpm = () => {},
  onLoadComposition = () => {},
  onOpenHistoryItem = () => {},
  onStopViewing = () => {},
}) {
  // 可信 Origin：显式注入优先（测试/受限部署，传入即权威，空数组=完全禁止内嵌），
  // 否则使用后端 /status 返回的 OpenMAIC Origin（未配置时为空 → fail-closed）。
  const trustedOrigins = useMemo(() => {
    if (trustedEmbedOrigins != null) return normalizeTrustedOrigins(trustedEmbedOrigins);
    return trustedOriginsFromStatus(status);
  }, [trustedEmbedOrigins, status]);

  const state = classroomState(status);
  const targetMode = INTERACTIVE_MODES.find((m) => m.mode === normalizeMode(mode)) || INTERACTIVE_MODES[0];
  const live = polling || isSessionLive(session);
  const browserEmbedAvailable = trustedEmbedOrigins != null || status.browser_embed_available === true;
  const safeUrl =
    browserEmbedAvailable && isSafeClassroomUrl(session?.url, trustedOrigins) ? session.url : null;
  const hasGeneratedUrl = Boolean(session?.url);
  const openInNewWindow = () => {
    if (safeUrl) window.open(safeUrl, "_blank", "noopener,noreferrer");
  };

  if (state === CLASSROOM_STATES.LOADING) {
    const text = CLASSROOM_STATE_TEXT.loading;
    return (
      <Panel className="interactive-panel">
        <SectionHeading title="智能辅导" detail="正在检测辅导服务…" />
        <div className="interactive-loading">
          <span className="loading-orb" />
          <p>{text.body}</p>
        </div>
      </Panel>
    );
  }

  if (!canGenerateInState(state)) {
    const text = statusText(state, status);
    // 区分两种情况：
    // - 有公开地址但浏览器被拦（如 ACCESS_CODE 保护）→ "课堂浏览授权尚未配置"；
    // - 课堂已生成但**根本没有公开地址**（未配置 OPENMAIC_EMBED_ORIGIN）
    //   → "已生成，但当前部署未开放浏览器访问"，否则学生以为白生成了。
    const generatedButClosed =
      state === CLASSROOM_STATES.EMBED_BLOCKED &&
      session?.status === "succeeded" &&
      !session?.url;
    return (
      <Panel className="interactive-panel">
        <SectionHeading title="智能辅导" detail="课程互动课堂" />
        <div className="interactive-unavailable interactive-state">
          <span className="interactive-state-icon">
            <Icon
              name={
                generatedButClosed
                  ? "PhGraduationCap"
                  : state === CLASSROOM_STATES.UNAVAILABLE
                    ? "PhWifiSlash"
                    : state === CLASSROOM_STATES.INCOMPATIBLE
                      ? "PhWarningCircle"
                      : state === CLASSROOM_STATES.EMBED_BLOCKED
                        ? "PhLock"
                        : "PhInfo"
              }
              size={26}
            />
          </span>
          <h3>{generatedButClosed ? "课堂已生成，但当前部署未开放浏览器访问" : text.title}</h3>
          <p>{text.body}</p>
          {status.compatibility_reason && state === CLASSROOM_STATES.INCOMPATIBLE ? (
            <p className="interactive-hint">{status.compatibility_reason}</p>
          ) : null}
          <Button variant="quiet" icon="PhArrowClockwise" onClick={onRefresh}>
            重新检测
          </Button>
          <Button variant="quiet" icon="PhChatCircleText" onClick={onAskCpm}>
            先问 CPM 获取辅导
          </Button>
        </div>
      </Panel>
    );
  }

  return (
    <Panel className="interactive-panel">
      <div className="interactive-panel-head">
        <SectionHeading
          title="智能辅导"
          detail={`互动课堂 · ${status.service || "OpenMAIC"}${status.version ? ` ${status.version}` : ""}`}
          action={
            <Button variant="quiet" icon="PhArrowsClockwise" disabled={polling} onClick={onRefresh}>
              刷新
            </Button>
          }
        />
        <button type="button" className="text-button interactive-ask-cpm" onClick={onAskCpm}>
          <Icon name="PhChatCircleText" size={16} />
          问 CPM 了解这门课该如何学
        </button>
      </div>

      {status.degraded ? (
        <div className="page-notice notice-warn" role="status">
          部分能力当前不可用
          {Array.isArray(status.unavailable_capabilities) && status.unavailable_capabilities.length
            ? `：${status.unavailable_capabilities.join("、")}`
            : ""}
          ，仍可生成其它形式的内容。
        </div>
      ) : null}
      {status.external_3d_available === false ? (
        <div className="page-notice notice-warn" role="status">
          当前环境无法访问外部 3D 资源，3D/可视化形态不可用。
        </div>
      ) : null}

      {!live && !hasGeneratedUrl && (
        <>
          <div className="interactive-modes" role="radiogroup" aria-label="选择辅导模式">
            {INTERACTIVE_MODES.map((m) => (
              <button
                key={m.mode}
                type="button"
                className={normalizeMode(mode) === m.mode ? "active" : ""}
                aria-pressed={normalizeMode(mode) === m.mode}
                onClick={() => onSelectMode(m.mode)}
              >
                <Icon name={MODE_ICONS[m.mode] || "PhPath"} size={20} />
                <strong>{m.label}</strong>
                <small>{m.description}</small>
              </button>
            ))}
          </div>

          <div className="interactive-brief">
            <label className="interactive-objective">
              <span>学习目标</span>
              <input
                value={brief.objective || ""}
                onChange={(e) => onBriefChange({ objective: e.target.value })}
                placeholder="例如：期中考试前巩固第 3 章难点"
                aria-label="学习目标"
              />
            </label>
            <label className="interactive-objective">
              <span>当前困惑</span>
              <input
                value={brief.currentDifficulty || ""}
                onChange={(e) => onBriefChange({ currentDifficulty: e.target.value })}
                placeholder="例如：不知道怎么求特征向量"
                aria-label="当前困惑"
              />
            </label>
            <label className="interactive-objective">
              <span>希望时长</span>
              <select
                value={brief.duration ?? ""}
                onChange={(e) =>
                  onBriefChange({ duration: e.target.value ? Number(e.target.value) : null })
                }
                aria-label="希望时长"
              >
                <option value="">不指定</option>
                {DURATION_OPTIONS.map((min) => (
                  <option key={min} value={min}>
                    {min} 分钟
                  </option>
                ))}
              </select>
            </label>
            <label className="interactive-objective">
              <span>难度</span>
              <select
                value={brief.difficultyLevel || ""}
                onChange={(e) => onBriefChange({ difficultyLevel: e.target.value })}
                aria-label="难度"
              >
                <option value="">不指定</option>
                {DIFFICULTY_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="interactive-checkbox">
              <input
                type="checkbox"
                checked={Boolean(brief.wantsMorePractice)}
                onChange={(e) => onBriefChange({ wantsMorePractice: e.target.checked })}
              />
              <span>多给我一些练习</span>
            </label>
          </div>

          <PlanCard
            plan={plan}
            planLoading={planLoading}
            brief={brief}
            onBriefChange={onBriefChange}
            onToggleMaterial={onToggleMaterial}
            onGenerate={onGenerate}
            polling={polling}
          />
          {!plan && !planLoading ? (
            <div className="interactive-actions">
              <Button variant="quiet" icon="PhEye" onClick={onPreviewPlan} disabled={polling}>
                查看这次会生成什么
              </Button>
            </div>
          ) : null}

          {error && (
            <div className="interactive-error" role="alert">
              <Icon name="PhWarningCircle" size={16} />
              {error}
              <button type="button" className="text-button" onClick={onRetry}>
                重试
              </button>
            </div>
          )}

          {itemsLoading ? (
            <p className="interactive-hint">正在读取已生成的课堂…</p>
          ) : (
            items.length > 0 && (
              <div className="interactive-list">
                <h3>已生成的课堂</h3>
                {items.map((item) => (
                  <article className="interactive-item" key={item.session_id || item.id}>
                    <span className="row-icon tone-violet">
                      <Icon name="PhGraduationCap" size={18} />
                    </span>
                    <span className="row-copy">
                      <strong>{modeLabel(item.mode)}</strong>
                      <small>
                        {item.scenes_count ? `${item.scenes_count} 个场景` : "互动课堂"} ·{" "}
                        {item.created_at ? new Date(item.created_at).toLocaleString("zh-CN") : "已生成"}
                        {!item.url && item.url_unavailable_reason
                          ? ` · ${item.url_unavailable_reason}`
                          : ""}
                      </small>
                    </span>
                    {browserEmbedAvailable && isSafeClassroomUrl(item.url, trustedOrigins) ? (
                      <a
                        className="button button-quiet"
                        href={item.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        aria-label="打开互动课堂"
                      >
                        打开
                      </a>
                    ) : (
                      <Button
                        variant="quiet"
                        disabled
                        title={item.url_unavailable_reason || "当前无法打开"}
                      >
                        待打开
                      </Button>
                    )}
                    <Button
                      variant="quiet"
                      onClick={() => onOpenHistoryItem(item.session_id || item.id)}
                    >
                      在页面内查看
                    </Button>
                  </article>
                ))}
              </div>
            )
          )}
        </>
      )}

      {live && (
        <div className="interactive-progress" role="status" aria-live="polite">
          <div className="interactive-progress-head">
            <span>{interactiveStepLabel(session?.step)}</span>
            <strong>{session?.progress != null ? `${session.progress}%` : "同步中"}</strong>
          </div>
          <div className="mastery-track">
            <span style={{ width: `${Math.max(0, Math.min(100, Number(session?.progress) || 8))}%` }} />
          </div>
          <p>{session?.message || "正在生成你的互动课堂，请稍候…"}</p>
          {session?.updated_at ? (
            <p className="interactive-hint">
              最近更新：{new Date(session.updated_at).toLocaleString("zh-CN")}
            </p>
          ) : null}
          <Button
            variant="quiet"
            icon="PhEyeSlash"
            onClick={onStopViewing}
            title="只停止本页的进度刷新，不会取消服务器上的生成任务"
          >
            停止查看进度
          </Button>
        </div>
      )}

      {!live && session && session.status === "failed" && (
        <div className="interactive-error interactive-state" role="alert">
          <Icon name="PhWarningCircle" size={20} />
          <p>{session.error || session.message || "课堂生成失败"}</p>
          {session.error_code ? <p className="interactive-hint">错误码：{session.error_code}</p> : null}
          <Button onClick={onRetry}>重新生成</Button>
          <Button variant="quiet" onClick={onReset}>
            放弃
          </Button>
        </div>
      )}

      {hasGeneratedUrl && !live && (
        <div className="interactive-result">
          <div className="interactive-result-bar">
            <ClassroomEmbed
              /* 传原始 url 让内嵌组件给出**具体**的拒绝原因；
                 是否渲染 iframe 由 ClassroomEmbed 内部统一判定。 */
              url={hasGeneratedUrl ? session.url : null}
              trustedOrigins={trustedOrigins}
              onOpenExternal={openInNewWindow}
            />
          </div>
          <CompositionBlock
            composition={composition}
            loading={compositionLoading}
            error={compositionError}
            onReload={onLoadComposition}
          />
          {session.partial ? (
            <div className="page-notice notice-warn" role="status">
              部分内容没有生成成功，你可以先看已生成的部分，或重新生成一次。
            </div>
          ) : null}
          <div className="interactive-result-controls">
            <Button
              variant="quiet"
              icon="PhArrowSquareOut"
              onClick={openInNewWindow}
              aria-label="在新窗口打开课堂"
              disabled={!safeUrl}
            >
              新窗口打开课堂
            </Button>
            <Button variant="quiet" icon="PhArrowClockwise" onClick={onReset}>
              重新生成
            </Button>
            <Button variant="quiet" icon="PhBookOpen" onClick={onRefresh}>
              返回课堂列表
            </Button>
          </div>
        </div>
      )}

      {!live && session && session.status === "succeeded" && !hasGeneratedUrl && (
        <div className="page-notice notice-warn" role="status">
          课堂已生成，但当前部署未开放浏览器访问。
          {status.browser_embed_reason ? `（${status.browser_embed_reason}）` : ""}
        </div>
      )}

      {notice && !live && (
        <div className="page-notice notice-info" role="status">
          {notice}
        </div>
      )}
    </Panel>
  );
}

const EMPTY_BRIEF = {
  objective: "",
  currentDifficulty: "",
  duration: null,
  difficultyLevel: "",
  wantsMorePractice: false,
  materialIds: [],
};

/**
 * 课程智能辅导空间面板（容器）。独立封装，自带状态与错误处理：
 * 服务不可用（enabled:false）/ 版本不兼容 / 请求失败都只影响本面板，绝不抛到课程详情整页。
 *
 * 生成必须由学生**明确确认**：先看 /plan 的课程、资料与推荐理由，再点"确认生成"。
 * /plan 是只读的，不创建任何 OpenMAIC 任务。
 *
 * 并发正确性（这是修复的重点）：切换课程 A→B 时，A 的旧请求可能晚于 B 返回。
 * 共享一个 `alive` 布尔量是不够的 —— B 的 effect 会把 `alive` 立刻设回 true，
 * A 的迟到响应就会被误认为有效并覆盖 B 的界面。这里改用 **courseId 绑定的 epoch**：
 * 每个异步结果在写回之前都要确认"我出发时的 epoch 仍然是当前 epoch"。
 */
export default function InteractiveClassroomPanel({ courseId, trustedEmbedOrigins = null, initialSessionId = "" }) {
  const navigate = useNavigate();
  const [status, setStatus] = useState({ enabled: false, loading: true, unavailable: false });
  const [items, setItems] = useState([]);
  const [itemsLoading, setItemsLoading] = useState(false);
  const [mode, setMode] = useState("adaptive");
  const [brief, setBrief] = useState(EMPTY_BRIEF);
  const [plan, setPlan] = useState(null);
  const [planLoading, setPlanLoading] = useState(false);
  const [session, setSession] = useState(null);
  const [polling, setPolling] = useState(false);
  const [composition, setComposition] = useState(null);
  const [compositionLoading, setCompositionLoading] = useState(false);
  const [compositionError, setCompositionError] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  // 轮询作用域：**停止查看**必须作废所有在途 poll，否则在途响应会把轮询重新点着。
  const pollScope = useRef(createPollScope()).current;
  // 课程/会话作用域的 epoch：异步结果写回前必须确认自己没被切换作废。
  const guard = useRef(createEpochGuard()).current;
  const isCurrent = (myEpoch) => guard.isCurrent(myEpoch);

  const stopPoll = useCallback(() => {
    pollScope.stop();
  }, [pollScope]);

  const loadOverview = useCallback(
    async (myEpoch) => {
      setStatus((s) => ({ ...s, loading: true }));
      // status 接口已对失败宽容；此项失败也不应让其余 tabs 抛错。
      const result = await api.getInteractiveClassroomStatus(courseId);
      if (!isCurrent(myEpoch)) return;
      setStatus({
        enabled: !!result.enabled,
        loading: false,
        unavailable: !!result.unavailable,
        incompatible: !!result.incompatible,
        compatibility: result.compatibility,
        compatibility_reason: result.compatibility_reason,
        degraded: !!result.degraded,
        unavailable_capabilities: result.unavailable_capabilities || [],
        service: result.service,
        version: result.version,
        embed_origin: result.embed_origin,
        browser_embed_available: result.browser_embed_available === true,
        browser_embed_reason: result.browser_embed_reason,
        external_3d_available: result.external_3d_available !== false,
      });
      if (result.enabled && result.browser_embed_available === true) {
        setItemsLoading(true);
        api
          .listInteractiveClassrooms(courseId)
          .then((data) => {
            if (isCurrent(myEpoch)) setItems(data.items || []);
          })
          .catch(() => {
            // 历史列表失败只影响列表本身
          })
          .finally(() => {
            if (isCurrent(myEpoch)) setItemsLoading(false);
          });
      } else {
        setItems([]);
      }
    },
    [courseId],
  );

  const loadPlan = useCallback(
    async (targetMode, myEpoch) => {
      setPlanLoading(true);
      try {
        const data = await api.getInteractiveClassroomPlan(courseId, targetMode);
        if (isCurrent(myEpoch)) setPlan(data);
      } catch {
        if (isCurrent(myEpoch)) setPlan(null);
      } finally {
        if (isCurrent(myEpoch)) setPlanLoading(false);
      }
    },
    [courseId],
  );

  // 切换课程：递增 epoch 让所有在途请求作废，并清空上一门课的全部状态。
  useEffect(() => {
    const myEpoch = guard.next();
    stopPoll();
    setSession(null);
    setComposition(null);
    setCompositionError("");
    setPlan(null);
    setPlanLoading(false);
    setItems([]);
    setItemsLoading(false);
    setBrief(EMPTY_BRIEF);
    setMode("adaptive");
    setError("");
    setNotice("");
    setPolling(false);
    setStatus({ enabled: false, loading: true, unavailable: false });
    loadOverview(myEpoch);
    return () => {
      // 卸载：作废在途请求并停止轮询
      guard.invalidate();
      stopPoll();
    };
  }, [courseId, loadOverview, stopPoll, guard]);

  useEffect(() => {
    if (status.loading || !status.enabled) return;
    loadPlan(mode, guard.current);
  }, [courseId, mode, status.loading, status.enabled, loadPlan]);

  const loadComposition = useCallback(
    async (sess, myEpoch) => {
      const sid = sess?.session_id || sess?.id;
      if (!sid) return;
      setCompositionLoading(true);
      setCompositionError("");
      try {
        const data = await api.getInteractiveClassroomComposition(courseId, sid);
        if (isCurrent(myEpoch)) setComposition(data);
      } catch (err) {
        // 读取失败必须明说，不能显示成"这节课没有内容"
        if (isCurrent(myEpoch)) {
          setCompositionError(interactiveErrorText(err, "课堂内容读取失败"));
        }
      } finally {
        if (isCurrent(myEpoch)) setCompositionLoading(false);
      }
    },
    [courseId],
  );

  const schedulePoll = useCallback(
    (sess, myEpoch, myToken = pollScope.begin()) => {
      const delay = Number(sess.poll_interval_ms) || 3000;
      pollScope.arm(async () => {
        pollScope.disarm();
        // 课程切走 / 学生点了"停止查看" → 在途响应一律丢弃，绝不重新安排轮询
        if (!isCurrent(myEpoch) || !pollScope.isCurrent(myToken)) return;
        try {
          const job = await api.getInteractiveClassroomJob(courseId, sess.session_id || sess.id);
          if (!isCurrent(myEpoch) || !pollScope.isCurrent(myToken)) return;
          const next = job?.session || job;
          setSession(next);
          if (next.status === "succeeded") {
            setPolling(false);
            setNotice("课堂已生成");
            loadOverview(myEpoch);
            loadComposition(next, myEpoch);
          } else if (next.status === "failed") {
            setPolling(false);
            setError(interactiveErrorText(next.error || next.message, "课堂生成失败，可重试。"));
          } else {
            schedulePoll(next, myEpoch, myToken);
          }
        } catch (err) {
          if (!isCurrent(myEpoch) || !pollScope.isCurrent(myToken)) return;
          setPolling(false);
          setError(interactiveErrorText(err, "进度查询失败"));
        }
      }, delay, myToken);
    },
    [courseId, loadComposition, loadOverview, pollScope],
  );

  /**
   * 在页面内打开一节**已存在**的课堂（历史列表 / 站内深链 `?session=`）。
   *
   * 与 startGenerate 的区别：这里绝不创建新任务，只回读服务端已有的 session，
   * 因此学生点"在页面内查看"或从"最近内容"深链进来都不会产生费用。
   */
  const openExistingSession = useCallback(
    async (sessionId, myEpoch) => {
      if (!sessionId) return;
      stopPoll();
      setError("");
      setNotice("");
      try {
        const job = await api.getInteractiveClassroomJob(courseId, sessionId);
        if (!isCurrent(myEpoch)) return;
        const next = job?.session || job;
        if (!next) {
          setError("这节课堂不存在，可能已被清理。");
          return;
        }
        setSession(next);
        if (next.status === "succeeded") {
          setPolling(false);
          loadComposition(next, myEpoch);
        } else if (next.status === "failed") {
          setPolling(false);
          setError(interactiveErrorText(next.error || next.message, "课堂生成失败，可重试。"));
        } else {
          // 仍在生成：继续订阅同一个任务
          setPolling(true);
          schedulePoll(next, myEpoch);
        }
      } catch (err) {
        if (isCurrent(myEpoch)) setError(interactiveErrorText(err, "课堂读取失败"));
      }
    },
    [courseId, loadComposition, pollScope, schedulePoll, stopPoll],
  );

  const startGenerate = async (targetMode = mode, retire = null) => {
    const myEpoch = guard.current;
    stopPoll();
    setError("");
    setNotice("");
    setSession(null);
    setComposition(null);
    setPolling(true);
    const payload = {
      mode: normalizeMode(targetMode),
      ...(brief.objective.trim() ? { learning_objective: brief.objective.trim() } : {}),
      ...(brief.currentDifficulty.trim()
        ? { current_difficulty: brief.currentDifficulty.trim() }
        : {}),
      ...(brief.duration ? { desired_duration_minutes: Number(brief.duration) } : {}),
      ...(brief.difficultyLevel ? { difficulty_level: brief.difficultyLevel } : {}),
      ...(brief.wantsMorePractice ? { wants_more_practice: true } : {}),
      ...(brief.materialIds.length ? { selected_material_ids: brief.materialIds } : {}),
    };
    try {
      const resp = retire
        ? await api.retryInteractiveClassroom(courseId, retire.session_id || retire.id, payload)
        : await api.generateInteractiveClassroom(courseId, payload);
      if (!isCurrent(myEpoch)) return;
      const created = resp?.session || resp;
      setSession(created);
      // 学生指定的资料无法使用时必须明说；旧任务没有快照时也要明确告知降级
      if (resp?.materials_warning) setNotice(resp.materials_warning);
      else if (resp?.request_source_note) setNotice(resp.request_source_note);
      schedulePoll(created, myEpoch);
    } catch (err) {
      if (!isCurrent(myEpoch)) return;
      setPolling(false);
      setError(interactiveErrorText(err));
    }
  };

  const retryCurrent = () => {
    if (!session) {
      setError("暂无可重试的生成任务");
      return;
    }
    startGenerate(session.mode || mode, session);
  };

  const resetPanel = () => {
    stopPoll();
    setError("");
    setNotice("");
    setSession(null);
    setComposition(null);
    setCompositionError("");
    setPolling(false);
  };

  // 站内深链 `?tab=mentoring&session=<id>`：等能力状态就绪后自动打开一次。
  // 用 ref 记住已处理过的 key，避免状态变化把它重复打开（也就不会重复请求）。
  const autoOpened = useRef("");
  useEffect(() => {
    if (!initialSessionId) return;
    if (status.loading || !status.enabled) return;
    const key = `${courseId}:${initialSessionId}`;
    if (autoOpened.current === key) return;
    autoOpened.current = key;
    void openExistingSession(initialSessionId, guard.current);
  }, [initialSessionId, courseId, status.loading, status.enabled, openExistingSession, guard]);

  const askCpm = () => {
    const label = INTERACTIVE_MODES.find((m) => m.mode === normalizeMode(mode))?.label || mode;
    const params = new URLSearchParams();
    params.set("course", courseId);
    if (label) params.set("prompt", `我想用「${label}」方式学习这门课。`);
    navigate(`/counselor?${params.toString()}`);
  };

  return (
    <InteractiveClassroomView
      status={status}
      items={items}
      itemsLoading={itemsLoading}
      mode={mode}
      brief={brief}
      plan={plan}
      planLoading={planLoading}
      session={session}
      polling={polling}
      composition={composition}
      compositionLoading={compositionLoading}
      compositionError={compositionError}
      error={error}
      notice={notice}
      trustedEmbedOrigins={trustedEmbedOrigins}
      onSelectMode={(m) => {
        setMode(m);
        setError("");
      }}
      onBriefChange={(patch) => setBrief((prev) => ({ ...prev, ...patch }))}
      onToggleMaterial={(id) =>
        setBrief((prev) => ({
          ...prev,
          materialIds: prev.materialIds.includes(id)
            ? prev.materialIds.filter((x) => x !== id)
            : [...prev.materialIds, id],
        }))
      }
      onPreviewPlan={() => loadPlan(mode, guard.current)}
      onGenerate={(m) => startGenerate(m)}
      onRetry={retryCurrent}
      onReset={resetPanel}
      onRefresh={() => loadOverview(guard.current)}
      onAskCpm={askCpm}
      onLoadComposition={() => loadComposition(session, guard.current)}
      onOpenHistoryItem={(sessionId) => void openExistingSession(sessionId, guard.current)}
      onStopViewing={() => {
        stopPoll();
        setPolling(false);
        setNotice("已停止查看进度。生成任务仍在服务端继续，稍后可从历史课堂打开。");
      }}
    />
  );
}
