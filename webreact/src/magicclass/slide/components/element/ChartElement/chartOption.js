/**
 * 逐字移植自参考
 * `components/slide-renderer/components/element/ChartElement/chartOption.ts`。
 *
 * 机械改写：去掉 `'use client'` 之外的 TypeScript 部分——`ComposeOption` /
 * `BarSeriesOption` 等 echarts 类型导入、`EChartOption` 联合类型、
 * `ChartOptionPayload` 接口与 `as const`。
 *
 * 为什么保留这个文件：目标项目没有 echarts，图表改用纯 SVG 回退渲染
 * （见 `Chart.jsx`）。但 `getChartOption` 描述的是「参考项目交给 echarts 的
 * 那份配置」——主题色数组、坐标轴、legend 位置、饼图半径、雷达 indicator、
 * 散点数据配对等全部语义都在这里。SVG 回退直接消费这份 option，可以保证
 * 颜色顺序、图例有无、数值标签开关、饼图/环形图半径比例与参考一致，
 * 而不是我另起一套视觉规则。
 */
export const getChartOption = ({
  type,
  data,
  themeColors,
  textColor,
  lineColor,
  lineSmooth,
  stack,
}) => {
  const textStyle = textColor
    ? {
        color: textColor,
      }
    : {};

  const axisLine = textColor
    ? {
        lineStyle: {
          color: textColor,
        },
      }
    : undefined;

  const axisLabel = {
    show: true,
    color: textColor ?? '#333333',
  };

  const splitLine = lineColor
    ? {
        lineStyle: {
          color: lineColor,
        },
      }
    : {};

  // Defensive check: ensure series is a non-empty array before processing
  if (!Array.isArray(data?.series) || data.series.length === 0 || !Array.isArray(data.labels)) {
    return null;
  }
  const categoryAxisLabel = {
    ...axisLabel,
    interval: data.labels.length <= 8 ? 0 : 'auto',
  };

  const legend =
    data.series.length > 1
      ? {
          top: 'bottom',
          textStyle,
        }
      : undefined;

  if (type === 'bar') {
    return {
      color: themeColors,
      textStyle,
      legend,
      xAxis: {
        type: 'category',
        data: data.labels,
        axisLine,
        axisLabel: categoryAxisLabel,
      },
      yAxis: {
        type: 'value',
        axisLine,
        axisLabel,
        splitLine,
      },
      series: data.series.map((item, index) => {
        const seriesItem = {
          data: item,
          name: data.legends[index],
          type: 'bar',
          label: {
            show: true,
          },
          itemStyle: {
            borderRadius: [2, 2, 0, 0],
          },
        };
        if (stack) seriesItem.stack = 'A';
        return seriesItem;
      }),
    };
  }
  if (type === 'column') {
    return {
      color: themeColors,
      textStyle,
      legend,
      yAxis: {
        type: 'category',
        data: data.labels,
        axisLine,
        axisLabel: categoryAxisLabel,
      },
      xAxis: {
        type: 'value',
        axisLine,
        axisLabel,
        splitLine,
      },
      series: data.series.map((item, index) => {
        const seriesItem = {
          data: item,
          name: data.legends[index],
          type: 'bar',
          label: {
            show: true,
          },
          itemStyle: {
            borderRadius: [0, 2, 2, 0],
          },
        };
        if (stack) seriesItem.stack = 'A';
        return seriesItem;
      }),
    };
  }
  if (type === 'line') {
    return {
      color: themeColors,
      textStyle,
      legend,
      xAxis: {
        type: 'category',
        data: data.labels,
        axisLine,
        axisLabel: categoryAxisLabel,
      },
      yAxis: {
        type: 'value',
        axisLine,
        axisLabel,
        splitLine,
      },
      series: data.series.map((item, index) => {
        const seriesItem = {
          data: item,
          name: data.legends[index],
          type: 'line',
          smooth: lineSmooth,
          label: {
            show: true,
          },
        };
        if (stack) seriesItem.stack = 'A';
        return seriesItem;
      }),
    };
  }
  if (type === 'pie') {
    const series0 = data.series[0];
    if (!Array.isArray(series0)) return null;
    return {
      color: themeColors,
      textStyle,
      legend: {
        top: 'bottom',
        textStyle,
      },
      series: [
        {
          data: series0.map((item, index) => ({
            value: item,
            name: data.labels[index],
          })),
          label: textColor
            ? {
                color: textColor,
              }
            : {},
          type: 'pie',
          radius: '70%',
          emphasis: {
            itemStyle: {
              shadowBlur: 10,
              shadowOffsetX: 0,
              shadowColor: 'rgba(0, 0, 0, 0.5)',
            },
            label: {
              show: true,
              fontSize: 14,
              fontWeight: 'bold',
            },
          },
        },
      ],
    };
  }
  if (type === 'ring') {
    const series0 = data.series[0];
    if (!Array.isArray(series0)) return null;
    return {
      color: themeColors,
      textStyle,
      legend: {
        top: 'bottom',
        textStyle,
      },
      series: [
        {
          data: series0.map((item, index) => ({
            value: item,
            name: data.labels[index],
          })),
          label: textColor
            ? {
                color: textColor,
              }
            : {},
          type: 'pie',
          radius: ['40%', '70%'],
          padAngle: 1,
          avoidLabelOverlap: false,
          itemStyle: {
            borderRadius: 4,
          },
          emphasis: {
            label: {
              show: true,
              fontSize: 14,
              fontWeight: 'bold',
            },
          },
        },
      ],
    };
  }
  if (type === 'area') {
    return {
      color: themeColors,
      textStyle,
      legend,
      xAxis: {
        type: 'category',
        boundaryGap: false,
        data: data.labels,
        axisLine,
        axisLabel: categoryAxisLabel,
      },
      yAxis: {
        type: 'value',
        axisLine,
        axisLabel,
        splitLine,
      },
      series: data.series.map((item, index) => {
        const seriesItem = {
          data: item,
          name: data.legends[index],
          type: 'line',
          areaStyle: {},
          label: {
            show: true,
          },
        };
        if (stack) seriesItem.stack = 'A';
        return seriesItem;
      }),
    };
  }
  if (type === 'radar') {
    // Display is broken without max in indicator; setting max triggers console warnings. No workaround — waiting for ECharts to fix this bug
    // const values: number[] = []
    // for (const item of data.series) {
    //   values.push(...item)
    // }
    // const max = Math.max(...values)

    return {
      color: themeColors,
      textStyle,
      legend,
      radar: {
        indicator: data.labels.map((item) => ({ name: item })),
        splitLine,
        axisLine: lineColor
          ? {
              lineStyle: {
                color: lineColor,
              },
            }
          : undefined,
      },
      series: [
        {
          data: data.series.map((item, index) => ({
            value: item,
            name: data.legends[index],
          })),
          type: 'radar',
        },
      ],
    };
  }
  if (type === 'scatter') {
    const series0 = data.series[0];
    if (!Array.isArray(series0)) return null;
    const formatedData = [];
    for (let i = 0; i < series0.length; i++) {
      const x = series0[i];
      const y = data.series[1]?.[i] ?? x;
      formatedData.push([x, y]);
    }

    return {
      color: themeColors,
      textStyle,
      xAxis: {
        axisLine,
        axisLabel,
        splitLine,
      },
      yAxis: {
        axisLine,
        axisLabel,
        splitLine,
      },
      series: [
        {
          symbolSize: 12,
          data: formatedData,
          type: 'scatter',
        },
      ],
    };
  }

  return null;
};
