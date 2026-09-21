/**
 * 逐字移植自参考
 * `components/slide-renderer/components/element/TableElement/index.tsx`。
 * 只去掉 `'use client'`、TypeScript 类型与 `@magicclass/dsl` 类型导入。
 */
import { StaticTable } from './StaticTable.jsx';

export { BaseTableElement } from './BaseTableElement.jsx';

/**
 * Editable table element component.
 * Supports selection/drag/resize via selectElement callback.
 * Cell editing is not implemented yet (display-only, matching ChartElement pattern).
 */
export function TableElement({ elementInfo, selectElement }) {
  const handleSelectElement = (e) => {
    if (elementInfo.lock) return;
    e.stopPropagation();
    selectElement?.(e, elementInfo);
  };

  return (
    <div
      className={`editable-element-table absolute ${elementInfo.lock ? 'lock' : ''}`}
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
          className={`element-content relative w-full h-full overflow-hidden ${
            elementInfo.lock ? 'cursor-default' : 'cursor-move'
          }`}
          onMouseDown={handleSelectElement}
          onTouchStart={handleSelectElement}
        >
          <StaticTable elementInfo={elementInfo} />
        </div>
      </div>
    </div>
  );
}
