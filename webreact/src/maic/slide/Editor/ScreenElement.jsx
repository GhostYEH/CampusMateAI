/**
 * 逐字移植自参考
 * `components/slide-renderer/Editor/ScreenElement.tsx`。
 *
 * 机械改写：
 *   - 去掉 `'use client'`、TypeScript 类型与 `@magicclass/dsl` 的 `PPTElement` 类型；
 *   - `ElementTypes` 常量对象 → `_compat/dsl.js`；
 *   - `@/lib/contexts/scene-context` 的 `useSceneSelector` → `_compat/scene-context.js`；
 *   - `../element-dom` → `_compat/element-dom.js`。
 *
 * 保留的语义：`screen-element` 根节点带 `zIndex` / `color` / `fontFamily`，
 * `ScreenElement` 用 `elementInfo.type` 选组件，未识别的类型返回 null。
 *
 * 注意：参考文件的根节点没有 `position: absolute`——绝对定位由被渲染的
 * base 元素自己负责（`base-element-* absolute`）。这里原样保留。
 */
import { useMemo } from 'react';

import { ElementTypes } from '../_compat/dsl.js';
import { BaseImageElement } from '../components/element/ImageElement/BaseImageElement.jsx';
import { BaseTextElement } from '../components/element/TextElement/BaseTextElement.jsx';
import { BaseShapeElement } from '../components/element/ShapeElement/BaseShapeElement.jsx';
import { BaseLineElement } from '../components/element/LineElement/BaseLineElement.jsx';
import { BaseChartElement } from '../components/element/ChartElement/BaseChartElement.jsx';
import { BaseLatexElement } from '../components/element/LatexElement/BaseLatexElement.jsx';
import { BaseTableElement } from '../components/element/TableElement/BaseTableElement.jsx';
import { BaseVideoElement } from '../components/element/VideoElement/BaseVideoElement.jsx';
import { BaseCodeElement } from '../components/element/CodeElement/BaseCodeElement.jsx';
import { useSceneSelector } from '../_compat/scene-context.js';
import { maicElementIdAttributes, screenElementDomId } from '../_compat/element-dom.js';

export function ScreenElement({
  elementInfo,
  elementIndex,
  animate,
  renderImage,
  renderVideo,
  renderText,
  renderShapeLabel,
  renderTable,
}) {
  const CurrentElementComponent = useMemo(() => {
    const elementTypeMap = {
      [ElementTypes.IMAGE]: BaseImageElement,
      [ElementTypes.TEXT]: BaseTextElement,
      [ElementTypes.SHAPE]: BaseShapeElement,
      [ElementTypes.LINE]: BaseLineElement,
      [ElementTypes.CHART]: BaseChartElement,
      [ElementTypes.LATEX]: BaseLatexElement,
      [ElementTypes.TABLE]: BaseTableElement,
      [ElementTypes.VIDEO]: BaseVideoElement,
      [ElementTypes.CODE]: BaseCodeElement,
      // TODO: Add other element types
      // [ElementTypes.AUDIO]: BaseAudioElement,
    };
    return elementTypeMap[elementInfo.type] || null;
  }, [elementInfo.type]);

  const theme = useSceneSelector((content) => {
    if (content.type === 'slide') {
      return content.canvas.theme;
    }
    return {
      fontColor: '#333333',
      fontName: 'Microsoft YaHei',
    };
  });

  if (!CurrentElementComponent) {
    return null;
  }

  const resolvedTheme = theme ?? {
    fontColor: '#333333',
    fontName: 'Microsoft YaHei',
  };

  return (
    <div
      className="screen-element"
      id={screenElementDomId(elementInfo.id)}
      {...maicElementIdAttributes(elementInfo.id)}
      style={{
        zIndex: elementIndex,
        color: resolvedTheme.fontColor,
        fontFamily: resolvedTheme.fontName,
      }}
    >
      <CurrentElementComponent
        elementInfo={elementInfo}
        animate={animate}
        renderImage={renderImage}
        renderVideo={renderVideo}
        renderText={renderText}
        renderShapeLabel={renderShapeLabel}
        renderTable={renderTable}
      />
    </div>
  );
}
