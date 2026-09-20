/**
 * 逐字移植自参考 `packages/@openmaic/renderer/src/effects/LaserOverlay.tsx`。
 * 只去掉 `'use client'` 与 TypeScript 类型。`geometry` 的形状是
 * `_compat/geometry.js` 里的 `PercentageGeometry`。
 */
import { motion } from 'motion/react';

export function LaserOverlay({ geometry, color = '#ff3b30', duration: _duration = 3000 }) {
  const { centerX, centerY } = geometry;

  const startPos = {
    x: centerX > 50 ? 105 : -5,
    y: centerY > 50 ? 105 : -5,
  };

  return (
    <motion.div
      key={`laser-${centerX}-${centerY}`}
      initial={{ opacity: 0, left: `${startPos.x}%`, top: `${startPos.y}%` }}
      animate={{ opacity: 1, left: `${centerX}%`, top: `${centerY}%` }}
      exit={{
        opacity: 0,
        left: `${startPos.x}%`,
        top: `${startPos.y}%`,
        transition: { duration: 0.25, ease: [0.4, 0, 1, 1] },
      }}
      transition={{
        left: { duration: 0.5, ease: [0.22, 1, 0.36, 1] },
        top: { duration: 0.5, ease: [0.22, 1, 0.36, 1] },
        opacity: { duration: 0.15 },
      }}
      style={{ position: 'absolute', zIndex: 101, pointerEvents: 'none' }}
    >
      <div style={{ position: 'relative', transform: 'translate(-50%, -50%)' }}>
        <motion.div
          animate={{ scale: [1, 2.8], opacity: [0.6, 0] }}
          transition={{
            repeat: Infinity,
            duration: 1.5,
            ease: 'easeOut',
            repeatDelay: 0.3,
          }}
          style={{
            position: 'absolute',
            inset: 0,
            borderRadius: '9999px',
            border: `1.5px solid ${color}`,
          }}
        />
        <div
          style={{
            width: '10px',
            height: '10px',
            borderRadius: '9999px',
            backgroundColor: color,
            boxShadow: `0 0 8px 2px ${color}60`,
          }}
        />
      </div>
    </motion.div>
  );
}
