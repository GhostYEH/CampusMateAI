/**
 * 逐字移植自参考
 * `components/slide-renderer/components/element/ShapeElement/BaseShapeElement.tsx`。
 *
 * 机械改写：去掉 `'use client'`、TypeScript 类型与 `@openmaic/dsl` 类型导入
 * （`ShapeText` 只是类型）。类名、内联样式、`--paragraphSpace` 自定义属性、
 * SVG `<g transform>` 表达式逐字保留。
 */
import { useElementOutline } from '../hooks/useElementOutline.js';
import { useElementShadow } from '../hooks/useElementShadow.js';
import { useElementFlip } from '../hooks/useElementFlip.js';
import { useElementFill } from '../hooks/useElementFill.js';
import { GradientDefs } from './GradientDefs.jsx';
import { PatternDefs } from './PatternDefs.jsx';

/**
 * Base shape element for read-only/playback mode
 */
export function BaseShapeElement({ elementInfo }) {
  const { fill } = useElementFill(elementInfo, 'base');
  const { outlineWidth, outlineColor, strokeDashArray } = useElementOutline(elementInfo.outline);
  const { shadowStyle } = useElementShadow(elementInfo.shadow);
  const { flipStyle } = useElementFlip(elementInfo.flipH, elementInfo.flipV);

  const text = elementInfo.text || {
    content: '',
    align: 'middle',
    defaultFontName: 'Microsoft YaHei',
    defaultColor: '#333333',
  };

  return (
    <div
      className="base-element-shape absolute"
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
          style={{
            opacity: elementInfo.opacity,
            filter: shadowStyle ? `drop-shadow(${shadowStyle})` : '',
            transform: flipStyle,
            color: text.defaultColor,
            fontFamily: text.defaultFontName,
          }}
        >
          <svg
            overflow="visible"
            width={elementInfo.width}
            height={elementInfo.height}
            className="transform-origin-[0_0] overflow-visible block"
          >
            <defs>
              {elementInfo.pattern && (
                <PatternDefs id={`base-pattern-${elementInfo.id}`} src={elementInfo.pattern} />
              )}
              {elementInfo.gradient && (
                <GradientDefs
                  id={`base-gradient-${elementInfo.id}`}
                  type={elementInfo.gradient.type}
                  colors={elementInfo.gradient.colors}
                  rotate={elementInfo.gradient.rotate}
                />
              )}
            </defs>
            <g
              transform={`scale(${elementInfo.width / elementInfo.viewBox[0]}, ${
                elementInfo.height / elementInfo.viewBox[1]
              }) translate(0,0) matrix(1,0,0,1,0,0)`}
            >
              <path
                vectorEffect="non-scaling-stroke"
                strokeLinecap="butt"
                strokeMiterlimit="8"
                d={elementInfo.path}
                fill={fill}
                stroke={outlineColor}
                strokeWidth={outlineWidth}
                strokeDasharray={strokeDashArray}
              />
            </g>
          </svg>

          <div
            className={`shape-text flex flex-col px-2.5 py-2.5 leading-relaxed break-words absolute inset-0 ${
              text.align === 'top'
                ? 'justify-start'
                : text.align === 'bottom'
                  ? 'justify-end'
                  : 'justify-center'
            }`}
            style={{
              lineHeight: text.lineHeight,
              letterSpacing: `${text.wordSpace || 0}px`,
            }}
          >
            <div
              className="ProseMirror-static [&_p]:mb-[var(--paragraphSpace)]"
              style={{
                '--paragraphSpace': `${text.paragraphSpace === undefined ? 5 : text.paragraphSpace}px`,
              }}
              dangerouslySetInnerHTML={{ __html: text.content }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
