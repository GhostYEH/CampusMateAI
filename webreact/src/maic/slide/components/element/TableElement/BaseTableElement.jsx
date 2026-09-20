/**
 * 逐字移植自参考
 * `components/slide-renderer/components/element/TableElement/BaseTableElement.tsx`。
 * 只去掉 `'use client'` 与 TypeScript 类型。
 */
import { StaticTable } from './StaticTable.jsx';

/**
 * Base table element for read-only / playback / thumbnail mode
 */
export function BaseTableElement({ elementInfo, target }) {
  return (
    <div
      className={`base-element-table absolute ${target === 'thumbnail' ? 'pointer-events-none' : ''}`}
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
        <div className="element-content w-full h-full">
          <StaticTable elementInfo={elementInfo} />
        </div>
      </div>
    </div>
  );
}
