import { useState } from "react";
import {
  isSameOriginAsPage,
  isTrustedEmbedUrl,
  normalizeTrustedOrigins,
} from "../../data/interactiveClassroom.js";
import { Button } from "../Primitives.jsx";
import { Icon } from "../Icon.jsx";

/**
 * 互动课堂内嵌容器 —— 唯一的 iframe 渲染点。
 *
 * 安全约束（不满足就绝不渲染 iframe）：
 * - 只接受后端下发的可信 HTTPS Origin，scheme + host + port **精确匹配**；
 * - 课堂 Origin **不得等于 CampusMate 页面自身 Origin**：同源 iframe 上
 *   `allow-same-origin` 会失去隔离意义（框架内容可与父页面互相访问）；
 * - sandbox 收紧为 `allow-scripts allow-same-origin allow-forms`：
 *   `allow-same-origin` 必须保留（magic class 课堂页是 Next.js 应用，需要自身
 *   origin 的 storage），但仅在**跨源**时安全 —— 上面的同源硬断言保证这一点。
 *   移除 `allow-popups` / `allow-downloads`（学生不需要，且扩大攻击面）。
 * - 不设置 `allow="*"`；`referrerPolicy="no-referrer"`；
 * - 不可信 URL 连"新窗口打开"都不提供；
 * - 内嵌失败只降级本组件，不影响课程其它页签。
 */
export const CLASSROOM_SANDBOX = "allow-scripts allow-same-origin allow-forms";

export default function ClassroomEmbed({
  url,
  trustedOrigins = [],
  title = "智能辅导互动课堂",
  onOpenExternal = null,
}) {
  const [blocked, setBlocked] = useState(false);
  const origins = normalizeTrustedOrigins(trustedOrigins);
  const sameOrigin = isSameOriginAsPage(url);
  const safe = isTrustedEmbedUrl(url, origins) && !sameOrigin;

  if (!safe) {
    return (
      <div className="interactive-fallback">
        <Icon name="PhLock" size={24} />
        <h3>无法在此内嵌课堂</h3>
        <p>
          {sameOrigin
            ? "该课堂地址与当前站点同源，出于隔离要求已阻止内嵌。"
            : "该课堂地址不在受信任的互动课堂服务范围内，已阻止打开。"}
        </p>
      </div>
    );
  }

  if (blocked) {
    return (
      <div className="interactive-fallback">
        <Icon name="PhWarningCircle" size={24} />
        <h3>浏览器阻止了内嵌</h3>
        <p>可以改用新窗口打开这节课，内容不受影响。</p>
        {onOpenExternal ? (
          <Button variant="quiet" icon="PhArrowSquareOut" onClick={onOpenExternal}>
            在新窗口打开课堂
          </Button>
        ) : null}
      </div>
    );
  }

  return (
    <iframe
      className="interactive-frame"
      src={url}
      title={title}
      aria-label={title}
      sandbox={CLASSROOM_SANDBOX}
      referrerPolicy="no-referrer"
      loading="lazy"
      onError={() => setBlocked(true)}
    />
  );
}
