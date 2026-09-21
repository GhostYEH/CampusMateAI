import { CLASSROOM_ASPECT_RATIO, useContainBox } from "../../features/magicclass/workbenchLayoutModel.js";

/**
 * 16:9 舞台盒。
 *
 * **不用 `aspect-ratio`。** 画布首次挂载时宿主往往还在 settle（pane 列宽过渡、
 * 字体回流、场景 rail 异步出现），纯 CSS 会按那一刻的错误尺寸把框撑出来，症状是
 * "第一次打开舞台是歪的"。这里按测得的像素写死宽高，测量策略见 `useContainBox`。
 *
 * 居中在外层，尺寸在内层：外层始终占满宿主并 `overflow: hidden`，内层只负责自己的
 * 像素盒，所以 letterbox 的黑边是外层背景，不会跟着内层一起缩放。
 */
export default function ContainBox({ ratio = CLASSROOM_ASPECT_RATIO, fit = "contain", className = "", label, children }) {
  const { hostRef, box } = useContainBox({ ratio, fit });
  const sized = box.width > 0;
  return <div ref={hostRef} className="ow-contain" data-testid="ow-contain-host">
    <div
      className={`ow-contain__box ${className}`}
      data-maic-stage-card="true"
      aria-label={label}
      style={sized ? { width: box.width, height: box.height } : { width: "100%", height: "100%" }}
      data-sized={sized ? "true" : "false"}
    >
      {children}
    </div>
  </div>;
}
