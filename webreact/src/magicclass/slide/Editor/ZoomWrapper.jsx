/**
 * 逐字移植自参考 `components/slide-renderer/Editor/ZoomWrapper.tsx`。
 * 只去掉 `'use client'`、TypeScript 类型与 `@/lib/types/action` 类型导入
 * （`PercentageGeometry` 的形状见 `_compat/geometry.js`）。
 *
 * 说明：参考的 `ScreenCanvas` 目前把缩放内联在画布容器上，`ZoomWrapper`
 * 在播放路径上没有调用点。仍然原样移植，供编辑/演示壳按需使用。
 */
import { motion } from 'motion/react';

/**
 * 缩放包装器组件
 *
 * 功能：
 * - 包裹整个画布，根据 zoomTarget 进行缩放
 * - 以元素中心为缩放原点
 * - 使用百分比坐标系统
 */
export function ZoomWrapper({ children, zoomTarget, geometry }) {
  if (!zoomTarget || !geometry) {
    return <>{children}</>;
  }

  const { scale } = zoomTarget;
  const { centerX, centerY } = geometry;

  return (
    <motion.div
      className="w-full h-full"
      initial={{ scale: 1 }}
      animate={{ scale }}
      exit={{ scale: 1 }}
      transition={{
        type: 'spring',
        stiffness: 200,
        damping: 25,
      }}
      style={{
        transformOrigin: `${centerX}% ${centerY}%`,
      }}
    >
      {children}
    </motion.div>
  );
}
