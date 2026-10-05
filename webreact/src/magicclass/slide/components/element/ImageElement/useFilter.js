/**
 * 逐字移植自参考
 * `components/slide-renderer/components/element/ImageElement/useFilter.ts`。
 * 只去掉 TypeScript 类型与 `@magicclass/dsl` 类型导入。
 */
import { useMemo } from 'react';

const FILTER_UNITS = {
  blur: 'px',
  brightness: '%',
  contrast: '%',
  grayscale: '%',
  saturate: '%',
  'hue-rotate': 'deg',
  sepia: '%',
  invert: '%',
  opacity: '%',
};

export function imageFiltersToCss(filters) {
  if (!filters) return '';
  const parts = [];
  for (const [name, value] of Object.entries(filters)) {
    if (value === undefined || value === null || value === '') continue;
    const unit = FILTER_UNITS[name] ?? '';
    const rendered = unit && !value.endsWith(unit) ? `${value}${unit}` : value;
    parts.push(`${name}(${rendered})`);
  }
  return parts.join(' ');
}

/**
 * Calculate a CSS filter string from the current DSL filter map.
 */
export function useFilter(filters) {
  const filter = useMemo(() => {
    return imageFiltersToCss(filters);
  }, [filters]);

  return {
    filter,
  };
}
