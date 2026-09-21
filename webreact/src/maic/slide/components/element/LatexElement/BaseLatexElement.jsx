/**
 * 逐字移植自参考
 * `components/slide-renderer/components/element/LatexElement/BaseLatexElement.tsx`。
 *
 * 机械改写：去掉 `'use client'`、TypeScript 类型与 `@magicclass/dsl` 类型导入；
 * `ALIGN_MAP` 的 `as const` 随类型检查一起去掉。
 *
 * 关于 KaTeX：目标项目没有安装 `katex` / `temml`（也禁止改 package.json），
 * 所以这里**不注入第三方的 katex.css、也不做公式排版**。参考项目里
 * `elementInfo.html` 是生成阶段就烤好的 KaTeX HTML，渲染层只负责把它塞进
 * `dangerouslySetInnerHTML`——这条分支在目标项目里原样保留：只要 canvas 数据
 * 带 `html`（PPTist 导入链路产出的数据就是这种），渲染结果与参考完全一致。
 * 只有 `html` 缺失时，参考会退回旧版 SVG path 分支（也保留）；两者都没有时
 * 参考渲染空内容——目标项目在这一档改为显示 `elementInfo.latex` 源码，样式
 * 沿用同一个外框（见 `LatexSourceFallback`），保证「没有任何排版引擎时至少
 * 看得见公式源码」而不是一片空白。
 */
import { useRef, useState, useLayoutEffect } from 'react';

/**
 * Base latex element for read-only/playback mode.
 * Renders KaTeX HTML if available, falls back to legacy SVG path.
 */
export function BaseLatexElement({ elementInfo }) {
  return (
    <div
      className="base-element-latex absolute"
      style={{
        top: `${elementInfo.top}px`,
        left: `${elementInfo.left}px`,
        width: `${elementInfo.width}px`,
        height: `${elementInfo.height}px`,
      }}
    >
      <div
        className="rotate-wrapper w-full h-full"
        style={{ transform: `rotate(${elementInfo.rotate}deg)` }}
      >
        <div
          className="element-content relative w-full h-full"
          style={{ color: elementInfo.color }}
        >
          {elementInfo.html ? (
            <KatexContent
              html={elementInfo.html}
              width={elementInfo.width}
              height={elementInfo.height}
              align={elementInfo.align}
            />
          ) : elementInfo.path && elementInfo.viewBox ? (
            <svg
              overflow="visible"
              width={elementInfo.width}
              height={elementInfo.height}
              stroke={elementInfo.color}
              strokeWidth={elementInfo.strokeWidth}
              fill="none"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="transform-origin-[0_0] overflow-visible"
            >
              <g
                transform={`scale(${elementInfo.width / elementInfo.viewBox[0]}, ${
                  elementInfo.height / elementInfo.viewBox[1]
                }) translate(0,0) matrix(1,0,0,1,0,0)`}
              >
                <path d={elementInfo.path} />
              </g>
            </svg>
          ) : elementInfo.latex ? (
            <LatexSourceFallback
              latex={elementInfo.latex}
              width={elementInfo.width}
              height={elementInfo.height}
              align={elementInfo.align}
            />
          ) : null}
        </div>
      </div>
    </div>
  );
}

const ALIGN_MAP = {
  left: 'flex-start',
  center: 'center',
  right: 'flex-end',
};

function KatexContent({ html, width, height, align = 'center' }) {
  const innerRef = useRef(null);
  const [scale, setScale] = useState(1);

  useLayoutEffect(() => {
    if (!innerRef.current) return;
    const naturalW = innerRef.current.scrollWidth;
    const naturalH = innerRef.current.scrollHeight;
    if (naturalW > 0 && naturalH > 0) {
      setScale(Math.min(width / naturalW, height / naturalH));
    }
  }, [html, width, height]);

  const justify = ALIGN_MAP[align];
  const origin =
    align === 'left' ? 'left center' : align === 'right' ? 'right center' : 'center center';

  return (
    <div
      style={{
        width,
        height,
        overflow: 'hidden',
        display: 'flex',
        alignItems: 'center',
        justifyContent: justify,
      }}
    >
      <div
        ref={innerRef}
        className="[&_.katex-display]:!m-0"
        style={{
          transformOrigin: origin,
          transform: `scale(${scale})`,
          whiteSpace: 'nowrap',
        }}
        dangerouslySetInnerHTML={{ __html: html }}
      />
    </div>
  );
}

/**
 * 目标项目没有 KaTeX：`html` 缺失时把 LaTeX 源码放进与 `KatexContent` 相同的外框
 * （同样的 width/height/overflow/flex 对齐），只换内层为等宽字体的源码呈现。
 * `elementInfo.color` 由父级 `element-content` 提供，与参考一致。
 */
function LatexSourceFallback({ latex, width, height, align = 'center' }) {
  const justifyContent = ALIGN_MAP[align];
  const textAlign = align === 'left' ? 'left' : align === 'right' ? 'right' : 'center';

  return (
    <div
      style={{
        width,
        height,
        overflow: 'hidden',
        display: 'flex',
        alignItems: 'center',
        justifyContent,
      }}
    >
      <div
        data-latex-fallback="source"
        style={{
          fontFamily:
            '"JetBrains Mono", "Fira Code", "SF Mono", "Cascadia Code", ui-monospace, SFMono-Regular, "Liberation Mono", Menlo, Monaco, Consolas, monospace',
          fontSize: '16px',
          lineHeight: 1.4,
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
          textAlign,
          maxWidth: '100%',
        }}
      >
        {latex}
      </div>
    </div>
  );
}
