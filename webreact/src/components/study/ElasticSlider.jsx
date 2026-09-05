import { animate, motion, useMotionValue, useMotionValueEvent, useTransform } from "motion/react";
import { useMemo, useRef, useState } from "react";
import { Icon } from "../Icon.jsx";

const MAX_OVERFLOW = 50;

export function clampSliderValue(value, min, max) {
  return Math.min(max, Math.max(min, Number(value) || min));
}

export function valueFromPointer(clientX, rect, min, max, step = 1) {
  if (!rect?.width) return min;
  const ratio = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
  const rawValue = min + ratio * (max - min);
  return clampSliderValue(min + Math.round((rawValue - min) / step) * step, min, max);
}

function decay(value, max) {
  if (!max) return 0;
  const entry = value / max;
  return (2 * (1 / (1 + Math.exp(-entry)) - 0.5)) * max;
}

export function ElasticSlider({
  value = 0,
  onChange,
  min = 0,
  max = 100,
  step = 1,
  className = "",
  leftIcon = <Icon name="PhSpeakerSimpleLow" size={17} />,
  rightIcon = <Icon name="PhSpeakerSimpleHigh" size={17} />,
}) {
  const sliderRef = useRef(null);
  const [region, setRegion] = useState("middle");
  const clientX = useMotionValue(0);
  const overflow = useMotionValue(0);
  const scale = useMotionValue(1);
  const currentValue = clampSliderValue(value, min, max);
  const percentage = useMemo(() => ((currentValue - min) / (max - min || 1)) * 100, [currentValue, min, max]);
  const trackScaleX = useTransform(overflow, [0, MAX_OVERFLOW], [1, 1.12]);
  const trackScaleY = useTransform(overflow, [0, MAX_OVERFLOW], [1, 0.82]);
  const bodyScale = useTransform(scale, [1, 1.2], [1, 1.2]);
  const bodyOpacity = useTransform(scale, [1, 1.2], [0.72, 1]);
  const trackHeight = useTransform(scale, [1, 1.2], [6, 12]);
  const leftIconX = useTransform(() => region === "left" ? -overflow.get() / scale.get() : 0);
  const rightIconX = useTransform(() => region === "right" ? overflow.get() / scale.get() : 0);
  const trackOrigin = useTransform(() => {
    const rect = sliderRef.current?.getBoundingClientRect();
    return clientX.get() < (rect?.left || 0) + (rect?.width || 0) / 2 ? "right" : "left";
  });

  useMotionValueEvent(clientX, "change", (latest) => {
    if (!sliderRef.current) return;
    const { left, right } = sliderRef.current.getBoundingClientRect();
    const distance = latest < left ? left - latest : latest > right ? latest - right : 0;
    setRegion(latest < left ? "left" : latest > right ? "right" : "middle");
    overflow.jump(decay(distance, MAX_OVERFLOW));
  });

  function handlePointerMove(event) {
    if (!(event.buttons > 0) || !sliderRef.current) return;
    onChange?.(valueFromPointer(event.clientX, sliderRef.current.getBoundingClientRect(), min, max, step));
    clientX.jump(event.clientX);
  }

  function handlePointerDown(event) {
    event.currentTarget.setPointerCapture(event.pointerId);
    handlePointerMove(event);
  }

  function handlePointerUp() {
    animate(overflow, 0, { type: "spring", bounce: 0.5 });
  }

  function handleKeyDown(event) {
    const delta = event.key === "ArrowRight" || event.key === "ArrowUp" ? step : event.key === "ArrowLeft" || event.key === "ArrowDown" ? -step : 0;
    if (!delta && event.key !== "Home" && event.key !== "End") return;
    event.preventDefault();
    const nextValue = event.key === "Home" ? min : event.key === "End" ? max : currentValue + delta;
    onChange?.(clampSliderValue(min + Math.round((nextValue - min) / step) * step, min, max));
  }

  return <div className={`elastic-slider ${className}`}>
    <motion.button
      type="button"
      className="elastic-slider__icon"
      aria-label="降低音量"
      onClick={() => onChange?.(clampSliderValue(currentValue - step, min, max))}
      onHoverStart={() => animate(scale, 1.2)}
      onHoverEnd={() => animate(scale, 1)}
      style={{ scale: bodyScale, opacity: bodyOpacity, x: leftIconX }}
    >{leftIcon}</motion.button>
    <div
      ref={sliderRef}
      className="elastic-slider__root"
      role="slider"
      tabIndex={0}
      aria-label="白噪音音量"
      aria-valuemin={min}
      aria-valuemax={max}
      aria-valuenow={currentValue}
      aria-valuetext={`${Math.round(currentValue)}%`}
      onPointerMove={handlePointerMove}
      onPointerDown={handlePointerDown}
      onPointerUp={handlePointerUp}
      onPointerCancel={handlePointerUp}
      onLostPointerCapture={handlePointerUp}
      onKeyDown={handleKeyDown}
    >
      <motion.div
        className="elastic-slider__track-wrapper"
        style={{ scaleX: trackScaleX, scaleY: trackScaleY, transformOrigin: trackOrigin, height: trackHeight }}
      >
        <div className="elastic-slider__track"><div className="elastic-slider__range" style={{ width: `${percentage}%` }} /><span className="elastic-slider__thumb" style={{ left: `${percentage}%` }} /></div>
      </motion.div>
    </div>
    <motion.button
      type="button"
      className="elastic-slider__icon"
      aria-label="提高音量"
      onClick={() => onChange?.(clampSliderValue(currentValue + step, min, max))}
      onHoverStart={() => animate(scale, 1.2)}
      onHoverEnd={() => animate(scale, 1)}
      style={{ scale: bodyScale, opacity: bodyOpacity, x: rightIconX }}
    >{rightIcon}</motion.button>
  </div>;
}
