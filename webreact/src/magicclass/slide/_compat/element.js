/**
 * 移植补充：元素几何与路径工具。
 *
 * 从参考 `lib/utils/element.ts` 摘出 slide 渲染层实际用到的部分，逐字移植，
 * 只去掉 TypeScript 类型。未摘入的是 `nanoid` 依赖的 ID 生成工具和编辑器专用
 * 的视图范围判定——read-only 播放路径不触及它们。
 *
 * 与参考的唯一实现替换：`getTableSubThemeColor` 用本目录 `color.js` 复刻
 * tinycolor2 的 `setAlpha().toRgbString()`（目标项目没有 tinycolor2）。
 */
import { withAlpha } from './color.js';

export const getRectRotatedRange = (element) => {
  const { left, top, width, height, rotate = 0 } = element;

  const radius = Math.sqrt(Math.pow(width, 2) + Math.pow(height, 2)) / 2;
  const auxiliaryAngle = (Math.atan(height / width) * 180) / Math.PI;

  const tlbraRadian = ((180 - rotate - auxiliaryAngle) * Math.PI) / 180;
  const trblaRadian = ((auxiliaryAngle - rotate) * Math.PI) / 180;

  const middleLeft = left + width / 2;
  const middleTop = top + height / 2;

  const xAxis = [
    middleLeft + radius * Math.cos(tlbraRadian),
    middleLeft + radius * Math.cos(trblaRadian),
    middleLeft - radius * Math.cos(tlbraRadian),
    middleLeft - radius * Math.cos(trblaRadian),
  ];
  const yAxis = [
    middleTop - radius * Math.sin(tlbraRadian),
    middleTop - radius * Math.sin(trblaRadian),
    middleTop + radius * Math.sin(tlbraRadian),
    middleTop + radius * Math.sin(trblaRadian),
  ];

  return {
    xRange: [Math.min(...xAxis), Math.max(...xAxis)],
    yRange: [Math.min(...yAxis), Math.max(...yAxis)],
  };
};

export const getRectRotatedOffset = (element) => {
  const { xRange: originXRange, yRange: originYRange } = getRectRotatedRange({
    left: element.left,
    top: element.top,
    width: element.width,
    height: element.height,
    rotate: 0,
  });
  const { xRange: rotatedXRange, yRange: rotatedYRange } = getRectRotatedRange({
    left: element.left,
    top: element.top,
    width: element.width,
    height: element.height,
    rotate: element.rotate,
  });
  return {
    offsetX: rotatedXRange[0] - originXRange[0],
    offsetY: rotatedYRange[0] - originYRange[0],
  };
};

/**
 * 计算元素在画布中的位置范围
 */
export const getElementRange = (element) => {
  let minX, maxX, minY, maxY;

  if (element.type === 'line') {
    minX = element.left;
    maxX = element.left + Math.max(element.start[0], element.end[0]);
    minY = element.top;
    maxY = element.top + Math.max(element.start[1], element.end[1]);
  } else if ('rotate' in element && element.rotate) {
    const { left, top, width, height, rotate } = element;
    const { xRange, yRange } = getRectRotatedRange({
      left,
      top,
      width,
      height,
      rotate,
    });
    minX = xRange[0];
    maxX = xRange[1];
    minY = yRange[0];
    maxY = yRange[1];
  } else {
    minX = element.left;
    maxX = element.left + element.width;
    minY = element.top;
    maxY = element.top + element.height;
  }
  return { minX, maxX, minY, maxY };
};

export const getElementListRange = (elementList) => {
  const leftValues = [];
  const topValues = [];
  const rightValues = [];
  const bottomValues = [];

  elementList.forEach((element) => {
    const { minX, maxX, minY, maxY } = getElementRange(element);
    leftValues.push(minX);
    topValues.push(minY);
    rightValues.push(maxX);
    bottomValues.push(maxY);
  });

  const minX = Math.min(...leftValues);
  const maxX = Math.max(...rightValues);
  const minY = Math.min(...topValues);
  const maxY = Math.max(...bottomValues);

  return { minX, maxX, minY, maxY };
};

export const getLineElementLength = (element) => {
  const deltaX = element.end[0] - element.start[0];
  const deltaY = element.end[1] - element.start[1];
  const len = Math.sqrt(deltaX * deltaX + deltaY * deltaY);
  return len;
};

export const uniqAlignLines = (lines) => {
  const byValue = new Map();
  for (const line of lines) {
    const existing = byValue.get(line.value);
    if (!existing) {
      byValue.set(line.value, line);
    } else {
      byValue.set(line.value, {
        value: line.value,
        range: [
          Math.min(existing.range[0], line.range[0]),
          Math.max(existing.range[1], line.range[1]),
        ],
      });
    }
  }
  return Array.from(byValue.values());
};

/**
 * 根据表格的主题色，获取对应用于配色的子颜色
 */
export const getTableSubThemeColor = (themeColor) => {
  return [withAlpha(themeColor, 0.3), withAlpha(themeColor, 0.1)];
};

/**
 * 获取线条元素路径字符串
 */
export const getLineElementPath = (element) => {
  // Defensive: ensure start and end are arrays
  const startArr = Array.isArray(element.start) ? element.start : [0, 0];
  const endArr = Array.isArray(element.end) ? element.end : [100, 100];
  const start = startArr.join(',');
  const end = endArr.join(',');
  if (element.broken) {
    const mid = element.broken.join(',');
    return `M${start} L${mid} L${end}`;
  } else if (element.broken2) {
    const { minX, maxX, minY, maxY } = getElementRange(element);
    if (maxX - minX >= maxY - minY)
      return `M${start} L${element.broken2[0]},${startArr[1]} L${element.broken2[0]},${endArr[1]} ${end}`;
    return `M${start} L${startArr[0]},${element.broken2[1]} L${endArr[0]},${element.broken2[1]} ${end}`;
  } else if (element.curve) {
    const mid = element.curve.join(',');
    return `M${start} Q${mid} ${end}`;
  } else if (element.cubic) {
    const [c1, c2] = element.cubic;
    const p1 = c1.join(',');
    const p2 = c2.join(',');
    return `M${start} C${p1} ${p2} ${end}`;
  }
  return `M${start} L${end}`;
};

/**
 * 判断一个元素是否在可视范围内
 */
export const isElementInViewport = (element, parent) => {
  const elementRect = element.getBoundingClientRect();
  const parentRect = parent.getBoundingClientRect();

  return elementRect.top >= parentRect.top && elementRect.bottom <= parentRect.bottom;
};
