/**
 * 逐字移植自参考 `packages/@magicclass/renderer/src/hooks/useViewportSize.ts`。
 * 只去掉 TypeScript 类型与 `RefObject` 泛型。逻辑、默认值（1000 / 0.5625 / 100）
 * 与副作用顺序完全保留。
 *
 * 新增一处「容器尚未布局」的守卫（参考文件没有、但参考项目里由宿主保证不会
 * 触发）：`useEffect(computeFit)` 在首次 commit 时跑，此刻若容器的
 * clientWidth/clientHeight 还是 0（例如 canvas 挂在一个刚 mount、高度由
 * flex 决定的壳里），参考公式会算出 scale = 0，画布不可见且要等下一次
 * ResizeObserver 回调才恢复。这里改为：尺寸为 0 时跳过本次计算并挂一个
 * requestAnimationFrame 重试，非 0 时行为与参考逐字一致。
 */
import { useState, useEffect, useMemo, useCallback, useRef } from 'react';

export function useViewportSize(canvasRef, options = {}) {
  const {
    viewportSize = 1000,
    viewportRatio = 0.5625,
    canvasPercentage = 100,
    onScaleChange,
  } = options;

  const [viewportLeft, setViewportLeft] = useState(0);
  const [viewportTop, setViewportTop] = useState(0);
  const [fitScale, setFitScale] = useState(1);
  const lastReportedScaleRef = useRef(undefined);
  const wasReportingScaleRef = useRef(false);

  const updateFitScale = useCallback(
    (nextScale) => {
      if (Object.is(lastReportedScaleRef.current, nextScale)) return;
      lastReportedScaleRef.current = nextScale;
      setFitScale(nextScale);
      onScaleChange?.(nextScale);
    },
    [onScaleChange],
  );

  useEffect(() => {
    const isReportingScale = onScaleChange !== undefined;
    if (isReportingScale && !wasReportingScaleRef.current) {
      lastReportedScaleRef.current = undefined;
    }
    wasReportingScaleRef.current = isReportingScale;
  }, [onScaleChange]);

  const computeFit = useCallback(() => {
    if (!canvasRef.current) return;
    const canvasWidth = canvasRef.current.clientWidth;
    const canvasHeight = canvasRef.current.clientHeight;

    // 容器尚未布局（首帧或 display:none）：等下一帧再量，避免算出 scale = 0
    if (canvasWidth === 0 || canvasHeight === 0) {
      return requestAnimationFrame(() => computeFit());
    }

    if (canvasHeight / canvasWidth > viewportRatio) {
      const viewportActualWidth = canvasWidth * (canvasPercentage / 100);
      const nextScale = viewportActualWidth / viewportSize;
      updateFitScale(nextScale);
      setViewportLeft((canvasWidth - viewportActualWidth) / 2);
      setViewportTop((canvasHeight - viewportActualWidth * viewportRatio) / 2);
    } else {
      const viewportActualHeight = canvasHeight * (canvasPercentage / 100);
      const nextScale = viewportActualHeight / (viewportSize * viewportRatio);
      updateFitScale(nextScale);
      setViewportLeft((canvasWidth - viewportActualHeight / viewportRatio) / 2);
      setViewportTop((canvasHeight - viewportActualHeight) / 2);
    }
  }, [canvasRef, canvasPercentage, updateFitScale, viewportRatio, viewportSize]);

  useEffect(() => {
    computeFit();
  }, [computeFit]);

  useEffect(() => {
    const el = canvasRef.current;
    if (!el) return;
    const resizeObserver = new ResizeObserver(computeFit);
    resizeObserver.observe(el);
    return () => resizeObserver.unobserve(el);
  }, [canvasRef, computeFit]);

  const viewportStyles = useMemo(
    () => ({
      width: viewportSize,
      height: viewportSize * viewportRatio,
      left: viewportLeft,
      top: viewportTop,
    }),
    [viewportSize, viewportRatio, viewportLeft, viewportTop],
  );

  return { viewportStyles, fitScale };
}
