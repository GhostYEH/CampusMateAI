<script setup>
import { onBeforeUnmount, onMounted, shallowRef, watch } from "vue";
import { gsap } from "gsap";
import { useAppStore } from "../../../stores/app";

const sectionRef = shallowRef(null);
const canvasRef = shallowRef(null);
const store = useAppStore();

const BRAND_TEXT = "CAMPUSMATE";
const targetPointer = { x: 0, y: 0 };
const currentPointer = { x: 0, y: 0 };
let pointerVelocityX = 0;
let pointerVelocityY = 0;
let targetAmplitude = 0;
let currentAmplitude = 0;
let pointerActive = false;
let pointerReady = false;
let lastPointerTime = 0;
let lastPointerX = 0;
let lastPointerY = 0;
let tickerRunning = false;
let resizeObserver = null;
let motionQuery = null;
let coarseQuery = null;
let canvasContext = null;
let sourceCanvas = null;
let sourceContext = null;
let canvasWidth = 0;
let canvasHeight = 0;
let devicePixelRatioValue = 1;
let sliceHeight = 5;

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function prefersStaticMode() {
  return Boolean(store.reduceMotion || motionQuery?.matches || coarseQuery?.matches);
}

function getTextLayout() {
  if (!sourceContext || !canvasWidth || !canvasHeight) return null;
  let fontSize = Math.min(canvasHeight * 0.82, canvasWidth / 7.2);
  sourceContext.font = `900 ${fontSize}px Arial Black, Arial, sans-serif`;
  let metrics = sourceContext.measureText(BRAND_TEXT);
  if (metrics.width > canvasWidth * 0.94) {
    fontSize *= (canvasWidth * 0.94) / metrics.width;
    sourceContext.font = `900 ${fontSize}px Arial Black, Arial, sans-serif`;
    metrics = sourceContext.measureText(BRAND_TEXT);
  }
  const ascent = metrics.actualBoundingBoxAscent || fontSize * 0.72;
  const descent = metrics.actualBoundingBoxDescent || fontSize * 0.18;
  return {
    fontSize,
    x: (canvasWidth - metrics.width) / 2,
    y: canvasHeight / 2 + (ascent - descent) / 2,
  };
}

function paintSourceText() {
  if (!sourceCanvas || !sourceContext) return;
  sourceContext.setTransform(devicePixelRatioValue, 0, 0, devicePixelRatioValue, 0, 0);
  sourceContext.clearRect(0, 0, canvasWidth, canvasHeight);
  const layout = getTextLayout();
  if (!layout) return;
  sourceContext.fillStyle = "rgba(255, 255, 255, .98)";
  sourceContext.textBaseline = "alphabetic";
  sourceContext.fillText(BRAND_TEXT, layout.x, layout.y);
}

function resizeCanvas() {
  const section = sectionRef.value;
  const canvas = canvasRef.value;
  if (!section || !canvas) return;
  const rect = section.getBoundingClientRect();
  canvasWidth = Math.max(1, Math.round(rect.width));
  canvasHeight = Math.max(1, Math.round(rect.height));
  devicePixelRatioValue = Math.min(window.devicePixelRatio || 1, 2);
  sliceHeight = clamp(Math.round(canvasHeight / 11), 14, 48);

  canvas.width = Math.round(canvasWidth * devicePixelRatioValue);
  canvas.height = Math.round(canvasHeight * devicePixelRatioValue);
  canvasContext = canvas.getContext("2d");
  canvasContext?.setTransform(devicePixelRatioValue, 0, 0, devicePixelRatioValue, 0, 0);

  sourceCanvas = document.createElement("canvas");
  sourceCanvas.width = canvas.width;
  sourceCanvas.height = canvas.height;
  sourceContext = sourceCanvas.getContext("2d");
  paintSourceText();

  targetPointer.x = canvasWidth / 2;
  targetPointer.y = canvasHeight / 2;
  currentPointer.x = targetPointer.x;
  currentPointer.y = targetPointer.y;
  drawFrame();
}

function drawFrame() {
  if (!canvasContext || !sourceCanvas || !canvasWidth || !canvasHeight) return;
  canvasContext.setTransform(devicePixelRatioValue, 0, 0, devicePixelRatioValue, 0, 0);
  canvasContext.clearRect(0, 0, canvasWidth, canvasHeight);
  canvasContext.drawImage(sourceCanvas, 0, 0, sourceCanvas.width, sourceCanvas.height, 0, 0, canvasWidth, canvasHeight);

  if (prefersStaticMode() || currentAmplitude < 0.01 || !pointerActive) return;

  const radiusX = clamp(canvasWidth * 0.2, 180, 300);
  const radiusY = clamp(canvasHeight * 0.62, 80, 160);
  const scaledSliceHeight = sliceHeight * devicePixelRatioValue;
  const sliceCount = Math.ceil(canvasHeight / sliceHeight);

  for (let index = 0; index < sliceCount; index += 1) {
    const y = index * sliceHeight;
    const height = Math.min(sliceHeight, canvasHeight - y);
    const centerY = y + height / 2;
    const distanceY = Math.abs(centerY - currentPointer.y);
    const yInfluence = Math.exp(-((distanceY * distanceY) / (2 * radiusY * radiusY)));
    if (yInfluence < 0.015) continue;

    const distanceX = Math.abs(currentPointer.x - canvasWidth / 2);
    const xInfluence = Math.exp(-((distanceX * distanceX) / (2 * radiusX * radiusX)));
    const localInfluence = yInfluence * (0.65 + xInfluence * 0.35);
    const stableNoise = Math.sin(index * 12.9898) * 0.5 + Math.cos(index * 3.14159) * 0.25;
    const direction = index % 2 === 0 ? 1 : -1;
    const offsetX = direction * (0.8 + stableNoise * 0.25) * currentAmplitude * 72 * localInfluence;

    canvasContext.save();
    canvasContext.beginPath();
    canvasContext.rect(currentPointer.x - radiusX, y, radiusX * 2, height);
    canvasContext.clip();
    canvasContext.drawImage(
      sourceCanvas,
      0,
      y * devicePixelRatioValue,
      sourceCanvas.width,
      scaledSliceHeight,
      offsetX,
      y,
      canvasWidth,
      height,
    );
    canvasContext.restore();
  }
}

function startTicker() {
  if (tickerRunning) return;
  tickerRunning = true;
  gsap.ticker.add(animate);
}

function stopTicker() {
  if (!tickerRunning) return;
  gsap.ticker.remove(animate);
  tickerRunning = false;
}

function animate(_time, deltaTime = 1000 / 60) {
  if (prefersStaticMode()) {
    stopTicker();
    drawFrame();
    return;
  }
  const frameRatio = clamp(deltaTime / (1000 / 60), 0.25, 3);
  const pointerBlend = 1 - Math.pow(1 - 0.12, frameRatio);
  const amplitudeBlend = 1 - Math.pow(1 - 0.1, frameRatio);
  currentPointer.x += (targetPointer.x - currentPointer.x) * pointerBlend;
  currentPointer.y += (targetPointer.y - currentPointer.y) * pointerBlend;
  currentAmplitude += (targetAmplitude - currentAmplitude) * amplitudeBlend;
  targetAmplitude *= Math.pow(pointerActive ? 0.94 : 0.78, frameRatio);
  drawFrame();

  if (currentAmplitude <= 0.01 && targetAmplitude <= 0.01 && !pointerActive) stopTicker();
}

function updatePointer(event) {
  const canvas = canvasRef.value;
  if (!canvas || prefersStaticMode()) return;
  const rect = canvas.getBoundingClientRect();
  const nextX = clamp(event.clientX - rect.left, 0, canvasWidth);
  const nextY = clamp(event.clientY - rect.top, 0, canvasHeight);
  const now = performance.now();
  const elapsed = Math.max(8, now - (lastPointerTime || now - 16));
  let deltaX = 0;
  let deltaY = 0;
  if (!pointerReady) {
    lastPointerX = nextX;
    lastPointerY = nextY;
    pointerReady = true;
  } else {
    deltaX = nextX - lastPointerX;
    deltaY = nextY - lastPointerY;
  }

  pointerVelocityX = clamp((deltaX / elapsed) * 16, -30, 30);
  pointerVelocityY = clamp((deltaY / elapsed) * 16, -30, 30);
  targetPointer.x = nextX;
  targetPointer.y = nextY;
  targetAmplitude = clamp(Math.abs(pointerVelocityX) * 0.045 + Math.abs(pointerVelocityY) * 0.02, 0, 1.8);
  lastPointerX = nextX;
  lastPointerY = nextY;
  lastPointerTime = now;
  pointerActive = true;
  startTicker();
}

function handlePointerEnter(event) {
  if (prefersStaticMode()) return;
  pointerActive = true;
  pointerReady = false;
  updatePointer(event);
}

function handlePointerMove(event) {
  updatePointer(event);
}

function handlePointerLeave() {
  pointerActive = false;
  pointerReady = false;
  targetAmplitude = 0;
  startTicker();
}

function bindPointerEvents() {
  const section = sectionRef.value;
  if (!section) return;
  section.addEventListener("pointerenter", handlePointerEnter);
  section.addEventListener("pointermove", handlePointerMove);
  section.addEventListener("pointerleave", handlePointerLeave);
}

function unbindPointerEvents() {
  const section = sectionRef.value;
  if (!section) return;
  section.removeEventListener("pointerenter", handlePointerEnter);
  section.removeEventListener("pointermove", handlePointerMove);
  section.removeEventListener("pointerleave", handlePointerLeave);
}

function handleMotionPreferenceChange() {
  if (prefersStaticMode()) {
    pointerActive = false;
    targetAmplitude = 0;
    currentAmplitude = 0;
    stopTicker();
    drawFrame();
  }
}

watch(() => store.reduceMotion, handleMotionPreferenceChange);

onMounted(() => {
  motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
  coarseQuery = window.matchMedia("(pointer: coarse)");
  resizeCanvas();
  bindPointerEvents();

  if (motionQuery.addEventListener) {
    motionQuery.addEventListener("change", handleMotionPreferenceChange);
    coarseQuery.addEventListener("change", handleMotionPreferenceChange);
  }

  resizeObserver = new ResizeObserver(resizeCanvas);
  resizeObserver.observe(sectionRef.value);
});

onBeforeUnmount(() => {
  stopTicker();
  resizeObserver?.disconnect();
  unbindPointerEvents();
  if (motionQuery?.removeEventListener) {
    motionQuery.removeEventListener("change", handleMotionPreferenceChange);
    coarseQuery.removeEventListener("change", handleMotionPreferenceChange);
  }
});
</script>

<template>
  <section ref="sectionRef" class="interactive-brand" aria-labelledby="interactive-brand-title">
    <span id="interactive-brand-title" class="visually-hidden">CampusMate 互动品牌区</span>
    <canvas ref="canvasRef" class="interactive-brand-canvas" role="img" aria-label="CAMPUSMATE">CAMPUSMATE</canvas>
    <span class="interactive-brand-caption">MOVE THROUGH CAMPUSMATE</span>
  </section>
</template>

<style scoped>
.interactive-brand {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 0;
  overflow: hidden;
  border-radius: 0;
  background: linear-gradient(112deg, #8158f1 0%, #6c61ec 46%, #3c72ee 100%);
  isolation: isolate;
}

.interactive-brand::before,
.interactive-brand::after {
  content: "";
  position: absolute;
  pointer-events: none;
}

.interactive-brand::before {
  inset: 0;
  background: radial-gradient(circle at 14% 10%, rgba(255,255,255,.2), transparent 20%), radial-gradient(circle at 86% 88%, rgba(148,208,255,.25), transparent 28%);
  mix-blend-mode: screen;
}

.interactive-brand::after {
  top: 18%;
  right: -5%;
  width: 38%;
  height: 1px;
  background: rgba(255,255,255,.26);
  box-shadow: -160px 42px 0 rgba(255,255,255,.12), -320px -30px 0 rgba(255,255,255,.1);
  transform: rotate(-12deg);
}

.interactive-brand-canvas {
  position: absolute;
  z-index: 1;
  inset: 0;
  width: 100%;
  height: 100%;
  display: block;
}

.interactive-brand-caption {
  position: absolute;
  z-index: 2;
  right: 22px;
  bottom: 15px;
  color: rgba(255,255,255,.62);
  font-size: 8px;
  font-weight: 750;
  letter-spacing: .18em;
  pointer-events: none;
}

.visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

@media (max-width: 620px) {
  .interactive-brand-caption {
    right: 14px;
    bottom: 11px;
    font-size: 7px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .interactive-brand { transition: none; }
}
</style>
