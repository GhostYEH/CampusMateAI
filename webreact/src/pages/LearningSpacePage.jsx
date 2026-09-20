/**
 * LearningSpacePage — 导航栏「学习空间」（/learning-space）。
 *
 * 学习空间是上游 OpenMAIC 应用以**独立进程、独立 Origin** 运行的那一份
 * （仓库根目录 `openmaic-app/`，版本与 `third_party/openmaic/` 固定的来源一致）。
 * 这一页只做三件事：
 *
 * 1. 向后端要「是否可用 + 允许从哪个公开 Origin 内嵌」；未配置公开 Origin 时
 *    fail-closed，不渲染任何 iframe。
 * 2. 可用时交给 `ClassroomEmbed` —— 全站**唯一**的 iframe 渲染点，不在这里另开一个，
 *    也就不可能在别处悄悄放宽 sandbox。
 * 3. 不可用时说清是链条上哪一段没起来、以及怎么起来，不摆一个点了没反应的假入口。
 *
 * 不在这里重新实现 OpenMAIC 的任何界面：那是它自己的产品。
 */
import { useCallback, useEffect, useState } from "react";

import ClassroomEmbed from "../components/interactive/ClassroomEmbed.jsx";
import { Icon } from "../components/Icon.jsx";
import { Button, PageFrame } from "../components/Primitives.jsx";
import {
  isSameOriginAsPage,
  isTrustedEmbedUrl,
  trustedOriginsFromStatus,
} from "../data/interactiveClassroom.js";
import { getLearningSpaceStatus } from "../data/learningSpaceApi.js";

/** 起服务的命令按仓库根目录相对书写，不写本机盘符或绝对路径。 */
const START_HINT = "在仓库根目录执行 node scripts/openmaic-local.mjs start（先跑 doctor 体检）。";

/**
 * 从后端状态推导出「这一页该显示什么」。
 *
 * 抽成纯函数是为了能把它钉在测试里：fail-closed 的判定散落在 JSX 里时，
 * 唯一能验的就是"某段文案在不在"，放宽了也看不出来。这里返回的 `ready`
 * 是页面上唯一决定是否渲染 iframe 的开关。
 */
export function learningSpaceView(status) {
  const origins = trustedOriginsFromStatus(status);
  const origin = origins[0] || null;
  const blocker = status ? blockerFor({ status, origins, origin }) : null;
  const ready = Boolean(status?.enabled) && !blocker && Boolean(origin);
  return { origins, origin, blocker, ready };
}

export function blockerFor({ status, origins, origin }) {
  if (!status) return null;
  if (status.incompatible === true || status.compatibility === "incompatible") {
    return {
      title: "学习空间版本与后端约定不一致",
      body: "应用连得上，但接口契约或版本不匹配。重试无用，需要核对 openmaic-app/ 的版本。",
      hint: START_HINT,
    };
  }
  if (status.unavailable === true) {
    return {
      title: "学习空间的应用进程没有在运行",
      body: "后端已配置它的地址，但连不上。这一页不会替你启动进程。",
      hint: START_HINT,
    };
  }
  if (!status.configured) {
    return {
      title: "学习空间尚未启用",
      body: "后端还没有配置它的内部地址，因此浏览器无从得知该访问哪里。",
      hint: START_HINT,
    };
  }
  if (!origin) {
    return {
      title: "浏览器访问尚未开放",
      body: "后端未配置公开 Origin。为免把内部地址下发到浏览器，这里不会猜测一个地址。",
      hint: "在 backend/.env 配置 OPENMAIC_EMBED_ORIGIN 后重新检测。",
    };
  }
  if (isSameOriginAsPage(origin)) {
    return {
      title: "学习空间与本站同源，已拒绝内嵌",
      body: "同源 iframe 上 sandbox 的 allow-same-origin 会失去隔离意义，因此这里不做同源内嵌。",
      hint: "让学习空间使用独立 Origin（不同端口或子域）后重新检测。",
    };
  }
  if (!isTrustedEmbedUrl(origin, origins)) {
    return {
      title: "学习空间地址不在可信范围内",
      body: "公开 Origin 未通过校验，已阻止内嵌。",
      hint: "核对 backend/.env 的 OPENMAIC_EMBED_ORIGIN。",
    };
  }
  return null;
}

export default function LearningSpacePage() {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setStatus(await getLearningSpaceStatus());
    } catch (err) {
      setError(err);
      setStatus(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const { origins, origin, blocker, ready } = learningSpaceView(
    loading || error ? null : status,
  );

  const openExternal = () => {
    if (ready) window.open(origin, "_blank", "noopener,noreferrer");
  };

  const actions = (
    <>
      <Button variant="secondary" icon="PhArrowClockwise" onClick={load} disabled={loading}>
        重新检测
      </Button>
      {ready && (
        <Button variant="quiet" icon="PhArrowUpRight" onClick={openExternal}>
          在新窗口打开
        </Button>
      )}
    </>
  );

  return (
    <PageFrame
      className="learning-space-page"
      eyebrow="学习空间"
      title="学习空间"
      description="magic'class 以独立进程运行，这里直接承载它完整的课堂、工作台与编辑器。"
      actions={actions}
    >
      {loading && (
        <div className="state-card loading-state" aria-busy="true">
          <span className="loading-orb" />
          <p>正在检测学习空间…</p>
        </div>
      )}

      {!loading && error && (
        <div className="state-card error-state" role="alert">
          <Icon name="PhWarningCircle" size={24} />
          <p>学习空间状态读取失败：{String(error?.message || error)}</p>
          <Button variant="secondary" onClick={load}>重试</Button>
        </div>
      )}

      {blocker && (
        <div className="state-card empty-state" role="status">
          <Icon name="PhChalkboardTeacher" size={34} />
          <h2 className="learning-space-blocker__title">{blocker.title}</h2>
          <p>{blocker.body}</p>
          <p className="learning-space-blocker__hint">{blocker.hint}</p>
        </div>
      )}

      {ready && (
        <div className="learning-space-stage">
          <ClassroomEmbed
            url={origin}
            trustedOrigins={origins}
            title="学习空间"
            onOpenExternal={openExternal}
          />
        </div>
      )}

      {ready && (
        <p className="learning-space-note">
          <Icon name="PhInfo" size={15} />
          学习空间是独立应用，拥有自己的账号门禁与主题；本站的身份与课程权限不会传给它。
        </p>
      )}

      {origin && !origin.startsWith("https:") && (
        <p className="learning-space-note">
          <Icon name="PhWarningCircle" size={15} />
          当前公开 Origin 是 <code>{origin}</code>（非 HTTPS）——
          仅适用于本机开发；生产环境必须使用 HTTPS。
        </p>
      )}
    </PageFrame>
  );
}
