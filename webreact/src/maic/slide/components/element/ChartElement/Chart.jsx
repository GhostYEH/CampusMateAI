/**
 * 参考文件：`components/slide-renderer/components/element/ChartElement/Chart.tsx`
 *
 * 参考实现用 **echarts**（SVGRenderer）：`echarts.init(div, null, {renderer:'svg'})`
 * + `setOption(getChartOption(params), true)` + `ResizeObserver -> resize()`。
 * 目标项目没有安装 echarts，也不允许改 package.json，所以这里换成**纯 SVG 回退
 * 渲染**，它消费同一份 `getChartOption()` 输出（颜色顺序、图例有无、数值标签
 * 开关、饼图/环形图半径比例、雷达 indicator、散点数据配对全部来自该 option），
 * 因此配色与结构语义与参考一致。
 *
 * 视觉盒模型与参考完全一致：外层元素由 `BaseChartElement` 提供尺寸，这里沿用
 * 参考的根节点 `className="chart w-full h-full"`，只是把 echarts 生成的
 * `<svg>` 换成本组件自己画的 `<svg>`。
 *
 * 覆盖的图表类型与参考支持的 8 种一致：bar / column / line / pie / ring /
 * area / radar / scatter。未覆盖的是 echarts 的交互能力（tooltip、hover 高亮、
 * emphasis 阴影）与动画——read-only 播放路径不需要它们。
 *
 * 主题色补齐逻辑（≤10 个时用 tinycolor2 的 analogous 扩到 10 个）逐字保留，
 * tinycolor2 由 `_compat/color.js` 等价实现。
 */
import { useMemo } from 'react';
import { analogous } from '../../../_compat/color.js';
import { getChartOption } from './chartOption.js';

const DEFAULT_TEXT_COLOR = '#333333';
const AXIS_LINE_COLOR = '#6b7280';
const SPLIT_LINE_COLOR = '#e5e7eb';
const FONT_SIZE = 12;
const LEGEND_HEIGHT = 25;
const LEGEND_ITEM_GAP = 12;
/** echarts 默认的类目轴留白比例（boundaryGap: true） */
const CATEGORY_GAP = 0.2;

export function Chart({
  width,
  height,
  type,
  data,
  themeColors: rawThemeColors,
  textColor,
  lineColor,
  options,
}) {
  // Generate theme colors — same补齐规则 as the reference
  const themeColors = useMemo(() => {
    const source = Array.isArray(rawThemeColors) ? rawThemeColors : [];
    let colors = [];
    if (source.length >= 10) {
      colors = source;
    } else if (source.length === 1) {
      colors = analogous(source[0], 10).map((color) => color);
    } else if (source.length === 0) {
      colors = [];
    } else {
      const len = source.length;
      const supplement = analogous(source[len - 1], 10 + 1 - len);
      colors = [...source.slice(0, len - 1), ...supplement];
    }
    return colors;
  }, [rawThemeColors]);

  const option = useMemo(
    () =>
      getChartOption({
        type,
        data,
        themeColors,
        textColor,
        lineColor,
        lineSmooth: options?.lineSmooth || false,
        stack: options?.stack || false,
      }),
    [type, data, themeColors, textColor, lineColor, options],
  );

  const w = Number.isFinite(width) && width > 0 ? width : 1;
  const h = Number.isFinite(height) && height > 0 ? height : 1;

  // 参考项目在 option 为 null 时什么都不画（echarts 保持空白画布）。
  if (!option) {
    return <div className="chart w-full h-full" data-chart-fallback="empty" />;
  }

  return (
    <div className="chart w-full h-full" data-chart-fallback="svg">
      <svg
        width={w}
        height={h}
        viewBox={`0 0 ${w} ${h}`}
        preserveAspectRatio="none"
        style={{ display: 'block', overflow: 'visible' }}
        role="img"
        aria-label={`${type} chart`}
      >
        <ChartBody option={option} type={type} width={w} height={h} textColor={textColor} />
      </svg>
    </div>
  );
}

function ChartBody({ option, type, width, height, textColor }) {
  const labelColor = textColor ?? DEFAULT_TEXT_COLOR;
  const legends = Array.isArray(option.series)
    ? option.series.map((series) => series.name).filter((name) => name !== undefined)
    : [];
  const showLegend = !!option.legend && legends.length > 1;
  const legendBlock = showLegend ? LEGEND_HEIGHT : 0;

  if (type === 'pie' || type === 'ring') {
    return (
      <PieLikeChart
        option={option}
        type={type}
        width={width}
        height={height}
        labelColor={labelColor}
        legends={legends}
        showLegend={showLegend}
      />
    );
  }

  if (type === 'radar') {
    return (
      <RadarChart
        option={option}
        width={width}
        height={height}
        labelColor={labelColor}
        legends={legends}
        showLegend={showLegend}
      />
    );
  }

  return (
    <CartesianChart
      option={option}
      type={type}
      width={width}
      height={height}
      labelColor={labelColor}
      legends={legends}
      showLegend={showLegend}
      legendBlock={legendBlock}
    />
  );
}

/* ============================ helpers ============================ */

function seriesValues(series) {
  const values = [];
  for (const item of series) {
    if (Array.isArray(item.data)) {
      for (const value of item.data) {
        if (typeof value === 'number' && Number.isFinite(value)) values.push(value);
      }
    }
  }
  return values;
}

function niceMax(value) {
  if (!Number.isFinite(value) || value <= 0) return 1;
  const exponent = Math.floor(Math.log10(value));
  const magnitude = Math.pow(10, exponent);
  const normalized = value / magnitude;
  const step = normalized <= 1 ? 1 : normalized <= 2 ? 2 : normalized <= 5 ? 5 : 10;
  return step * magnitude;
}

/** echarts 默认分 4 段 */
const VALUE_SPLIT_NUMBER = 4;

function buildValueTicks(min, max, count = VALUE_SPLIT_NUMBER) {
  const span = max - min;
  const step = span / count;
  const ticks = [];
  for (let i = 0; i <= count; i++) {
    ticks.push(min + step * i);
  }
  return ticks;
}

function formatTickValue(value) {
  if (!Number.isFinite(value)) return '';
  if (Number.isInteger(value)) return String(value);
  if (Math.abs(value) >= 100) return value.toFixed(0);
  if (Math.abs(value) >= 1) return value.toFixed(1);
  return value.toFixed(2);
}

/** 类目轴标签抽稀：≤8 个全显示，否则按 2/5/10 阶梯递增到可读密度 */
function categoryLabelStep(count) {
  if (count <= 8) return 1;
  if (count <= 16) return 2;
  if (count <= 40) return 5;
  return 10;
}

function measureText(text, fontSize = FONT_SIZE) {
  return String(text ?? '').length * fontSize * 0.62;
}

function CartesianChart({
  option,
  type,
  width,
  height,
  labelColor,
  legends,
  showLegend,
  legendBlock,
}) {
  const categories = Array.isArray(option.xAxis?.data)
    ? option.xAxis.data
    : Array.isArray(option.yAxis?.data)
      ? option.yAxis.data
      : [];
  // scatter 没有类目轴：option 的 x/y 轴都是数值轴
  const isScatter = type === 'scatter';
  const valueSeries = Array.isArray(option.series) ? option.series : [];
  const values = seriesValues(valueSeries);
  const rawMax = values.length ? Math.max(...values) : 1;
  const rawMin = values.length ? Math.min(...values, 0) : 0;
  const maxValue = niceMax(Math.max(rawMax, 1));
  const minValue = rawMin < 0 ? -niceMax(Math.abs(rawMin)) : 0;

  const categoryWidths = categories.map((label) => measureText(label));
  const maxCategoryWidth = categoryWidths.length ? Math.max(...categoryWidths) : 0;
  const maxValueWidth = Math.max(
    measureText(formatTickValue(maxValue)),
    measureText(formatTickValue(minValue)),
  );

  // 轴刻度标签占位：类目轴横排取最长标签的一半 + 内边距
  const leftInset = Math.max(28, maxValueWidth + 10);
  const rightInset = isScatter ? 24 : Math.max(16, maxCategoryWidth / 2);
  const topInset = 18;
  const bottomInset = showLegend ? legendBlock + 18 : Math.max(22, maxCategoryWidth / 2);

  const plotW = Math.max(1, width - leftInset - rightInset);
  const plotH = Math.max(1, height - topInset - bottomInset);

  const yRatio = (value) => {
    const span = maxValue - minValue || 1;
    return topInset + plotH - ((value - minValue) / span) * plotH;
  };
  const zeroY = yRatio(0);

  const bandWidth = categories.length ? plotW / categories.length : plotW;
  const xCenter = (index) => leftInset + bandWidth * (index + 0.5);
  const valueY = (value) => (isScatter ? yRatio(value) : yRatio(value));

  const valueTicks = buildValueTicks(minValue, maxValue);
  const labelStep = categoryLabelStep(categories.length);
  const axisLineStroke = option.xAxis?.axisLine?.lineStyle?.color ?? AXIS_LINE_COLOR;
  const splitLineStroke = option.yAxis?.splitLine?.lineStyle?.color ?? SPLIT_LINE_COLOR;
  const isVerticalBars = type === 'bar' || type === 'column';

  const barCount = isVerticalBars ? valueSeries.length : 1;
  const groupSlot = isVerticalBars && !isScatter ? bandWidth * 0.7 : 0;
  const barSlot = barCount > 0 ? groupSlot / barCount : 0;

  return (
    <g>
      {/* 数值轴网格线 + 刻度标签 */}
      {valueTicks.map((tick, index) => {
        const y = yRatio(tick);
        const isZero = tick === 0;
        return (
          <g key={`tick-${index}`}>
            {!isZero && index > 0 ? (
              <line
                x1={leftInset}
                y1={y}
                x2={leftInset + plotW}
                y2={y}
                stroke={splitLineStroke}
                strokeWidth={1}
              />
            ) : null}
            <text
              x={leftInset - 6}
              y={y + FONT_SIZE * 0.35}
              textAnchor="end"
              fill={labelColor}
              fontSize={FONT_SIZE}
            >
              {formatTickValue(tick)}
            </text>
          </g>
        );
      })}

      {/* 坐标轴 */}
      <line
        x1={leftInset}
        y1={topInset}
        x2={leftInset}
        y2={topInset + plotH}
        stroke={axisLineStroke}
        strokeWidth={1}
      />
      <line
        x1={leftInset}
        y1={zeroY}
        x2={leftInset + plotW}
        y2={zeroY}
        stroke={axisLineStroke}
        strokeWidth={1}
      />

      {/* 类目轴刻度标签 */}
      {categories.map((label, index) =>
        index % labelStep === 0 ? (
          <text
            key={`cat-${index}`}
            x={xCenter(index)}
            y={topInset + plotH + FONT_SIZE + 6}
            textAnchor="middle"
            fill={labelColor}
            fontSize={FONT_SIZE}
          >
            {label}
          </text>
        ) : null,
      )}

      {/* 数据系列 */}
      {valueSeries.map((series, seriesIndex) => {
        const color = option.color?.[seriesIndex] ?? DEFAULT_TEXT_COLOR;
        const values = Array.isArray(series.data) ? series.data : [];

        if (isScatter) {
          const xs = values.map((pair) => (Array.isArray(pair) ? pair[0] : 0));
          const ys = values.map((pair) => (Array.isArray(pair) ? pair[1] : 0));
          const xMax = niceMax(Math.max(...xs, 1));
          const yMax = niceMax(Math.max(...ys, 1));
          const symbolSize = Number.isFinite(series.symbolSize) ? series.symbolSize : 12;
          return (
            <g key={`series-${seriesIndex}`}>
              {values.map((pair, pointIndex) => {
                const px = leftInset + ((Array.isArray(pair) ? pair[0] : 0) / (xMax || 1)) * plotW;
                const py = topInset + plotH - ((Array.isArray(pair) ? pair[1] : 0) / (yMax || 1)) * plotH;
                return (
                  <circle
                    key={`point-${pointIndex}`}
                    cx={px}
                    cy={py}
                    r={symbolSize / 2}
                    fill={color}
                  />
                );
              })}
            </g>
          );
        }

        if (type === 'line' || type === 'area') {
          const points = values.map((value, index) => ({
            x: xCenter(index),
            y: valueY(value),
            value,
          }));
          const linePath = smoothPolyline(points, !!series.smooth);
          const areaPath = `${linePath} L ${points[points.length - 1]?.x ?? leftInset} ${zeroY} L ${
            points[0]?.x ?? leftInset
          } ${zeroY} Z`;
          return (
            <g key={`series-${seriesIndex}`}>
              {type === 'area' ? (
                <path d={areaPath} fill={color} fillOpacity={0.25} stroke="none" />
              ) : null}
              <path d={linePath} fill="none" stroke={color} strokeWidth={2} />
              {points.map((point, pointIndex) => (
                <circle
                  key={`point-${pointIndex}`}
                  cx={point.x}
                  cy={point.y}
                  r={2.5}
                  fill={color}
                />
              ))}
              {series.label?.show
                ? points.map((point, pointIndex) => (
                    <text
                      key={`label-${pointIndex}`}
                      x={point.x}
                      y={point.y - 6}
                      textAnchor="middle"
                      fill={labelColor}
                      fontSize={FONT_SIZE}
                    >
                      {formatTickValue(point.value)}
                    </text>
                  ))
                : null}
            </g>
          );
        }

        // bar / column
        return (
          <g key={`series-${seriesIndex}`}>
            {values.map((value, index) => {
              const center = xCenter(index);
              const groupLeft = center - groupSlot / 2;
              const x = groupLeft + barSlot * seriesIndex + barSlot * 0.1;
              const barWidth = Math.max(1, barSlot * 0.8);
              const y = valueY(value);
              const barHeight = Math.abs(y - zeroY);
              return (
                <g key={`bar-${index}`}>
                  <rect
                    x={x}
                    y={Math.min(y, zeroY)}
                    width={barWidth}
                    height={Math.max(barHeight, 0)}
                    fill={color}
                  />
                  {series.label?.show ? (
                    <text
                      x={x + barWidth / 2}
                      y={y - 4}
                      textAnchor="middle"
                      fill={labelColor}
                      fontSize={FONT_SIZE}
                    >
                      {formatTickValue(value)}
                    </text>
                  ) : null}
                </g>
              );
            })}
          </g>
        );
      })}

      {showLegend ? (
        <Legend
          items={legends.map((name, index) => ({
            name,
            color: option.color?.[index] ?? DEFAULT_TEXT_COLOR,
          }))}
          width={width}
          y={height - LEGEND_HEIGHT / 2 + FONT_SIZE / 2}
          labelColor={labelColor}
        />
      ) : null}
    </g>
  );
}

/**
 * 折线/面积图路径：`smooth` 时用二次贝塞尔把相邻中点连起来（与 echarts
 * smooth 折线的视觉近似），否则直接折线。
 */
function smoothPolyline(points, smooth) {
  if (!points.length) return '';
  if (points.length === 1) return `M ${points[0].x} ${points[0].y}`;
  if (!smooth) {
    return points.map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x} ${point.y}`).join(' ');
  }
  let path = `M ${points[0].x} ${points[0].y}`;
  for (let i = 1; i < points.length; i++) {
    const previous = points[i - 1];
    const current = points[i];
    const midX = (previous.x + current.x) / 2;
    const midY = (previous.y + current.y) / 2;
    path += ` Q ${previous.x} ${previous.y} ${midX} ${midY}`;
    if (i === points.length - 1) {
      path += ` T ${current.x} ${current.y}`;
    }
  }
  return path;
}

function Legend({ items, width, y, labelColor }) {
  const rendered = items.map((item) => ({
    ...item,
    textWidth: measureText(item.name),
  }));
  const totalWidth =
    rendered.reduce((sum, item) => sum + 12 + 4 + item.textWidth, 0) +
    LEGEND_ITEM_GAP * Math.max(0, rendered.length - 1);
  let cursor = Math.max(8, (width - totalWidth) / 2);

  return (
    <g>
      {rendered.map((item, index) => {
        const x = cursor;
        cursor += 12 + 4 + item.textWidth + LEGEND_ITEM_GAP;
        return (
          <g key={`legend-${index}`}>
            <rect x={x} y={y - 9} width={12} height={12} rx={2} fill={item.color} />
            <text x={x + 16} y={y} fill={labelColor} fontSize={FONT_SIZE}>
              {item.name}
            </text>
          </g>
        );
      })}
    </g>
  );
}

function PieLikeChart({ option, type, width, height, labelColor, legends, showLegend }) {
  const series = option.series?.[0];
  const sliceData = Array.isArray(series?.data) ? series.data : [];
  const total = sliceData.reduce(
    (sum, item) => sum + (typeof item.value === 'number' && Number.isFinite(item.value) ? item.value : 0),
    0,
  );

  const legendBlock = showLegend ? LEGEND_HEIGHT : 0;
  const availableHeight = Math.max(1, height - legendBlock);
  // option.series[0].radius 是 echarts 语义：'70%' 或 ['40%','70%']
  const radiusSpec = series?.radius ?? '70%';
  const percentages = Array.isArray(radiusSpec)
    ? radiusSpec.map((value) => parseFloat(value) / 100)
    : [0, parseFloat(radiusSpec) / 100];
  const outerFraction = percentages[percentages.length - 1] ?? 0.7;
  const innerFraction = percentages.length > 1 ? percentages[0] : 0;

  const outerRadius = (Math.min(width, availableHeight) / 2) * outerFraction;
  const innerRadius = outerRadius * (outerFraction === 0 ? 0 : innerFraction / outerFraction);
  const centerX = width / 2;
  const centerY = availableHeight / 2;

  if (total <= 0) {
    return <g />;
  }

  const padAngle = type === 'ring' ? 1 : 0;
  let startAngle = -90;

  const slices = sliceData.map((item, index) => {
    const value = typeof item.value === 'number' && Number.isFinite(item.value) ? item.value : 0;
    const sweep = (value / total) * 360;
    const endAngle = startAngle + sweep;
    const midAngle = startAngle + sweep / 2;
    const color = option.color?.[index % (option.color?.length || 1)] ?? DEFAULT_TEXT_COLOR;
    const labelRadius = outerRadius + 14;
    const slice = {
      value,
      name: item.name,
      color,
      midAngle,
      labelX: centerX + Math.cos((midAngle * Math.PI) / 180) * labelRadius,
      labelY: centerY + Math.sin((midAngle * Math.PI) / 180) * labelRadius,
      labelAnchor:
        Math.cos((midAngle * Math.PI) / 180) > 0.1
          ? 'start'
          : Math.cos((midAngle * Math.PI) / 180) < -0.1
            ? 'end'
            : 'middle',
      path: donutSlicePath(centerX, centerY, outerRadius, innerRadius, startAngle, endAngle, padAngle),
    };
    startAngle = endAngle;
    return slice;
  });

  return (
    <g>
      {slices.map((slice, index) => (
        <path key={`slice-${index}`} d={slice.path} fill={slice.color} stroke="#fff" strokeWidth={1} />
      ))}
      {slices.map((slice, index) => (
        <text
          key={`slice-label-${index}`}
          x={slice.labelX}
          y={slice.labelY}
          textAnchor={slice.labelAnchor}
          fill={labelColor}
          fontSize={FONT_SIZE}
        >
          {`${slice.name ?? ''} ${formatTickValue(slice.value)}`}
        </text>
      ))}
      {showLegend ? (
        <Legend
          items={legends.map((name, index) => ({
            name,
            color: option.color?.[index % (option.color?.length || 1)] ?? DEFAULT_TEXT_COLOR,
          }))}
          width={width}
          y={height - LEGEND_HEIGHT / 2 + FONT_SIZE / 2}
          labelColor={labelColor}
        />
      ) : null}
    </g>
  );
}

/**
 * 环形/扇形路径。`padAngle`（echarts 的 deg 语义）按半径换算成角度留缝，
 * `innerRadius > 0` 时挖空成环。
 */
function donutSlicePath(cx, cy, outerRadius, innerRadius, startAngle, endAngle, padAngle = 0) {
  const padDeg =
    padAngle > 0 && outerRadius > 0
      ? (padAngle / 2 / ((Math.PI * outerRadius) / 180)) * (180 / Math.PI)
      : 0;
  const safeStart = startAngle + padDeg;
  const safeEnd = Math.max(safeStart, endAngle - padDeg);

  const point = (angle, radius) => {
    const radian = (angle * Math.PI) / 180;
    return [cx + Math.cos(radian) * radius, cy + Math.sin(radian) * radius];
  };

  const [outerStartX, outerStartY] = point(safeStart, outerRadius);
  const [outerEndX, outerEndY] = point(safeEnd, outerRadius);
  const outerSweep = safeEnd - safeStart > 180 ? 1 : 0;

  if (innerRadius <= 0) {
    const [centerX, centerY] = [cx, cy];
    return `M ${centerX} ${centerY} L ${outerStartX} ${outerStartY} A ${outerRadius} ${outerRadius} 0 ${outerSweep} 1 ${outerEndX} ${outerEndY} Z`;
  }

  const [innerEndX, innerEndY] = point(safeEnd, innerRadius);
  const [innerStartX, innerStartY] = point(safeStart, innerRadius);
  const innerSweep = safeEnd - safeStart > 180 ? 1 : 0;

  return `M ${outerStartX} ${outerStartY} A ${outerRadius} ${outerRadius} 0 ${outerSweep} 1 ${outerEndX} ${outerEndY} L ${innerEndX} ${innerEndY} A ${innerRadius} ${innerRadius} 0 ${innerSweep} 0 ${innerStartX} ${innerStartY} Z`;
}

function RadarChart({ option, width, height, labelColor, legends, showLegend }) {
  const indicator = Array.isArray(option.radar?.indicator) ? option.radar.indicator : [];
  const seriesList = Array.isArray(option.series) ? option.series : [];
  const seriesValuesFlat = [];
  for (const series of seriesList) {
    const entries = Array.isArray(series.data) ? series.data : [];
    for (const entry of entries) {
      if (Array.isArray(entry.value)) {
        for (const value of entry.value) {
          if (typeof value === 'number' && Number.isFinite(value)) seriesValuesFlat.push(value);
        }
      }
    }
  }
  // 参考项目的 chartOption 注释里明确说「没有 max 雷达图显示会坏」，
  // 因此这里同样按数据最大值归一化——与 echarts 实际取 max 的行为一致。
  const maxValue = niceMax(Math.max(...seriesValuesFlat, 1));

  const legendBlock = showLegend ? LEGEND_HEIGHT : 0;
  const availableHeight = Math.max(1, height - legendBlock);
  const centerX = width / 2;
  const centerY = availableHeight / 2;
  const radius = Math.max(10, Math.min(width, availableHeight) / 2 - 30);
  const axes = indicator.length;

  const pointAt = (axisIndex, ratio) => {
    const angle = -Math.PI / 2 + (axisIndex / Math.max(axes, 1)) * Math.PI * 2;
    return [centerX + Math.cos(angle) * radius * ratio, centerY + Math.sin(angle) * radius * ratio];
  };

  const ringPolygon = (ratio) =>
    Array.from({ length: axes }, (_, index) => pointAt(index, ratio))
      .map(([x, y]) => `${x},${y}`)
      .join(' ');

  return (
    <g>
      <polygon points={ringPolygon(1)} fill="none" stroke={SPLIT_LINE_COLOR} strokeWidth={1} />
      <polygon points={ringPolygon(0.5)} fill="none" stroke={SPLIT_LINE_COLOR} strokeWidth={1} />
      {Array.from({ length: axes }, (_, index) => {
        const [x, y] = pointAt(index, 1);
        return (
          <line
            key={`axis-${index}`}
            x1={centerX}
            y1={centerY}
            x2={x}
            y2={y}
            stroke={SPLIT_LINE_COLOR}
            strokeWidth={1}
          />
        );
      })}
      {indicator.map((item, index) => {
        const [x, y] = pointAt(index, 1.12);
        return (
          <text
            key={`indicator-${index}`}
            x={x}
            y={y}
            textAnchor="middle"
            fill={labelColor}
            fontSize={FONT_SIZE}
          >
            {item.name}
          </text>
        );
      })}
      {seriesList.map((series, seriesIndex) => {
        const color = option.color?.[seriesIndex] ?? DEFAULT_TEXT_COLOR;
        const entries = Array.isArray(series.data) ? series.data : [];
        return (
          <g key={`radar-series-${seriesIndex}`}>
            {entries.map((entry, entryIndex) => {
              const values = Array.isArray(entry.value) ? entry.value : [];
              const points = values
                .map((value, axisIndex) => {
                  const ratio = Math.min(1, Math.max(0, value / maxValue));
                  const [x, y] = pointAt(axisIndex, ratio);
                  return `${x},${y}`;
                })
                .join(' ');
              return (
                <polygon
                  key={`radar-polygon-${entryIndex}`}
                  points={points}
                  fill={color}
                  fillOpacity={0.25}
                  stroke={color}
                  strokeWidth={1.5}
                />
              );
            })}
          </g>
        );
      })}
      {showLegend ? (
        <Legend
          items={legends.map((name, index) => ({
            name,
            color: option.color?.[index] ?? DEFAULT_TEXT_COLOR,
          }))}
          width={width}
          y={height - LEGEND_HEIGHT / 2 + FONT_SIZE / 2}
          labelColor={labelColor}
        />
      ) : null}
    </g>
  );
}
