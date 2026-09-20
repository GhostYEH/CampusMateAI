/**
 * 逐字移植自参考
 * `components/slide-renderer/components/element/ChartElement/BaseChartElement.tsx`。
 * 只去掉 `'use client'`、TypeScript 类型与 `@openmaic/dsl` 类型导入。
 * `Chart` 换成同 props 的 SVG 回退实现（见 `Chart.jsx`）。
 */
import { ElementOutline } from '../ElementOutline.jsx';
import { Chart } from './Chart.jsx';

/**
 * Base chart element for read-only/playback mode
 */
export function BaseChartElement({ elementInfo, target }) {
  return (
    <div
      className={`base-element-chart absolute ${target === 'thumbnail' ? 'pointer-events-none' : ''}`}
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
          className="element-content w-full h-full"
          style={{
            backgroundColor: elementInfo.fill,
          }}
        >
          <ElementOutline
            width={elementInfo.width}
            height={elementInfo.height}
            outline={elementInfo.outline}
          />
          <Chart
            width={elementInfo.width}
            height={elementInfo.height}
            type={elementInfo.chartType}
            data={elementInfo.data}
            themeColors={elementInfo.themeColors}
            textColor={elementInfo.textColor}
            lineColor={elementInfo.lineColor}
            options={elementInfo.options}
          />
        </div>
      </div>
    </div>
  );
}
