import { useEffect, useRef } from "react";
import { Geometry, Mesh, Program, RenderTarget, Renderer, Texture, Triangle } from "ogl";
import "./RippleDistortion.css";

const MAX_WAVES = 100;
const QUALITY_SCALE = { low: 0.4, medium: 0.7, high: 1 };
const START_SCALE = 1.5;
const LIFE_CONSTANT = Math.log(500);

const waveVertex = `
precision highp float;
attribute vec2 position; attribute vec2 uv; attribute vec2 iOffset; attribute vec2 iScale; attribute float iOpacity;
varying vec2 vUv; varying float vOpacity;
void main() { vUv = uv; vOpacity = iOpacity; gl_Position = vec4(iOffset + position * iScale, 0.0, 1.0); }
`;
const waveFragment = `
precision highp float;
varying vec2 vUv; varying float vOpacity;
uniform float uRings;
const float PI = 3.141592653589793; const float EDGE = 0.006737947;
void main() {
  vec2 p = vUv * 2.0 - 1.0; float r = dot(p, p); if (r > 1.0) discard;
  float brush = (exp(-r * 5.0) - EDGE) / (1.0 - EDGE);
  brush *= 0.55 + 0.45 * cos(sqrt(r) * PI * 2.0 * uRings);
  gl_FragColor = vec4(vec3(brush * vOpacity * vOpacity), 1.0);
}
`;
const screenVertex = `
precision highp float;
attribute vec2 position; attribute vec2 uv; varying vec2 vUv;
void main() { vUv = uv; gl_Position = vec4(position, 0.0, 1.0); }
`;
const compositeFragment = `
precision highp float;
varying vec2 vUv;
uniform sampler2D uTexture; uniform sampler2D uDisplacement; uniform vec2 uResolution; uniform vec2 uTextureSize; uniform vec2 uTexel;
uniform vec3 uTint; uniform vec3 uHighlight; uniform float uStrength; uniform float uSwirl; uniform float uDispersion; uniform float uGlint; uniform float uTintAmount; uniform float uGrayscale;
const float TAU = 6.283185307179586;
vec2 coverUV(vec2 uv) {
  vec2 safe = max(uTextureSize, vec2(1.0)); vec2 s = uResolution / safe; vec2 scaledSize = safe * max(s.x, s.y); vec2 offset = (uResolution - scaledSize) * 0.5;
  return (uv * uResolution - offset) / scaledSize;
}
void main() {
  float amount = texture2D(uDisplacement, vUv).r; vec2 base = coverUV(vUv); float theta = amount * uSwirl * TAU; vec2 push = vec2(sin(theta), cos(theta)) * amount * uStrength;
  vec3 color;
  if (uDispersion > 0.001) { float split = uDispersion * 0.25; color.r = texture2D(uTexture, base + push * (1.0 + split)).r; color.g = texture2D(uTexture, base + push).g; color.b = texture2D(uTexture, base + push * (1.0 - split)).b; }
  else color = texture2D(uTexture, base + push).rgb;
  if (uGrayscale > 0.001) color = mix(color, vec3(dot(color, vec3(0.2126, 0.7152, 0.0722))), uGrayscale);
  if (uTintAmount > 0.001) color = mix(color, color * uTint * 1.9, clamp(amount * 1.6, 0.0, 1.0) * uTintAmount);
  if (uGlint > 0.001) {
    float ex = texture2D(uDisplacement, vUv + vec2(uTexel.x, 0.0)).r - texture2D(uDisplacement, vUv - vec2(uTexel.x, 0.0)).r;
    float ey = texture2D(uDisplacement, vUv + vec2(0.0, uTexel.y)).r - texture2D(uDisplacement, vUv - vec2(0.0, uTexel.y)).r;
    vec3 normal = normalize(vec3(-ex * 26.0, -ey * 26.0, 1.0)); vec3 light = normalize(vec3(-0.35, 0.55, 1.0));
    float raw = pow(max(dot(normal, light), 0.0), 22.0); float flatSpec = pow(max(light.z, 0.0), 22.0);
    color += uHighlight * clamp((raw - flatSpec) / max(1.0 - flatSpec, 0.0001), 0.0, 1.0) * uGlint;
  }
  gl_FragColor = vec4(color, 1.0);
}
`;

function hexToRGB(hex) {
  const clean = String(hex || "#ffffff").replace("#", "");
  const full = clean.length === 3 ? clean.split("").map((char) => char + char).join("") : clean;
  const value = parseInt(full, 16);
  if (Number.isNaN(value)) return [1, 1, 1];
  return [(value >> 16 & 255) / 255, (value >> 8 & 255) / 255, (value & 255) / 255];
}

export default function RippleDistortion({
  src = "/assets/counselor-campus-hero-reference.png",
  brushSize = 150,
  strength = 0.2,
  swirl = 1,
  rings = 4,
  spread = 5,
  fade = 3,
  spacing = 15,
  dispersion = 0,
  glint = 0,
  tint = "#a855f7",
  tintAmount = 0.1,
  grayscale = true,
  highlightColor = "#ffffff",
  trigger = "hover",
  clickStrength = 2,
  quality = "low",
  enabled = true,
  className = "",
  style,
}) {
  const mountRef = useRef(null);
  const configRef = useRef({});
  const uniformsRef = useRef(null);
  configRef.current = { brushSize, spread, fade, spacing, clickStrength, trigger, enabled };

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return undefined;
    const reduceMotion = Boolean(window.matchMedia?.("(prefers-reduced-motion: reduce)").matches);
    const renderer = new Renderer({ alpha: false, antialias: false, dpr: Math.min(window.devicePixelRatio || 1, 2) });
    const gl = renderer.gl;
    gl.clearColor(0, 0, 0, 1);
    const canvas = gl.canvas;
    Object.assign(canvas.style, { width: "100%", height: "100%", display: "block" });
    mount.appendChild(canvas);

    const imageTexture = new Texture(gl, { generateMipmaps: false, minFilter: gl.LINEAR, magFilter: gl.LINEAR, wrapS: gl.CLAMP_TO_EDGE, wrapT: gl.CLAMP_TO_EDGE });
    let disposed = false;
    const useVideo = /\.(mp4|webm|ogg|mov|m4v)(\?|$)/i.test(src);
    const initialRect = mount.getBoundingClientRect();
    let isVisible = initialRect.bottom > 0 && initialRect.right > 0 && initialRect.top < window.innerHeight && initialRect.left < window.innerWidth;
    let raf = 0;
    let previousTime = 0;
    let scrollResumeTimer = 0;
    let isScrolling = false;
    let requestRender = () => {};
    let updatePlayback = () => {};
    let mediaEl = null;
    if (useVideo) {
      mediaEl = document.createElement("video");
      mediaEl.src = src;
      mediaEl.loop = true;
      mediaEl.muted = true;
      mediaEl.autoplay = false;
      mediaEl.playsInline = true;
      mediaEl.setAttribute("muted", "");
      mediaEl.load();
      mediaEl.addEventListener("loadeddata", () => {
        if (disposed) return;
        imageTexture.image = mediaEl;
        compositeUniforms.uTextureSize.value = [mediaEl.videoWidth || 1, mediaEl.videoHeight || 1];
        updatePlayback();
        requestRender();
      });
    } else {
      mediaEl = new window.Image();
      mediaEl.crossOrigin = "anonymous";
      mediaEl.decoding = "async";
      mediaEl.onload = () => {
        if (disposed) return;
        imageTexture.image = mediaEl;
        compositeUniforms.uTextureSize.value = [mediaEl.naturalWidth || 1, mediaEl.naturalHeight || 1];
        requestRender();
      };
      mediaEl.src = src;
    }

    const offsets = new Float32Array(MAX_WAVES * 2);
    const scales = new Float32Array(MAX_WAVES * 2);
    const opacities = new Float32Array(MAX_WAVES);
    const waves = Array.from({ length: MAX_WAVES }, () => ({ x: 0, y: 0, scale: START_SCALE, target: START_SCALE, size: 1, opacity: 0 }));
    let current = 0;
    const geometry = new Geometry(gl, {
      position: { size: 2, data: new Float32Array([-1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1]) },
      uv: { size: 2, data: new Float32Array([0, 0, 1, 0, 0, 1, 0, 1, 1, 0, 1, 1]) },
      iOffset: { instanced: 1, size: 2, data: offsets }, iScale: { instanced: 1, size: 2, data: scales }, iOpacity: { instanced: 1, size: 1, data: opacities },
    });
    const waveUniforms = { uRings: { value: rings } };
    const waveProgram = new Program(gl, { vertex: waveVertex, fragment: waveFragment, uniforms: waveUniforms, transparent: true, depthTest: false, depthWrite: false, cullFace: false });
    waveProgram.setBlendFunc(gl.ONE, gl.ONE);
    const waveMesh = new Mesh(gl, { geometry, program: waveProgram, frustumCulled: false });
    const displacementTarget = new RenderTarget(gl, { width: 2, height: 2, depth: false, minFilter: gl.LINEAR, magFilter: gl.LINEAR, wrapS: gl.CLAMP_TO_EDGE, wrapT: gl.CLAMP_TO_EDGE });
    const compositeUniforms = {
      uTexture: { value: imageTexture }, uDisplacement: { value: displacementTarget.texture }, uResolution: { value: [1, 1] }, uTextureSize: { value: [1, 1] }, uTexel: { value: [1, 1] },
      uTint: { value: hexToRGB(tint) }, uHighlight: { value: hexToRGB(highlightColor) }, uStrength: { value: strength }, uSwirl: { value: swirl }, uDispersion: { value: dispersion },
      uGlint: { value: glint }, uTintAmount: { value: tintAmount }, uGrayscale: { value: grayscale ? 1 : 0 },
    };
    const compositeMesh = new Mesh(gl, { geometry: new Triangle(gl), program: new Program(gl, { vertex: screenVertex, fragment: compositeFragment, uniforms: compositeUniforms, depthTest: false, depthWrite: false }) });
    uniformsRef.current = { wave: waveUniforms, composite: compositeUniforms };

    let width = 1;
    let height = 1;
    const resize = () => {
      width = Math.max(1, mount.clientWidth); height = Math.max(1, mount.clientHeight); renderer.setSize(width, height);
      compositeUniforms.uResolution.value = [width, height];
      const scale = QUALITY_SCALE[quality] || QUALITY_SCALE.high; const fieldW = Math.max(2, Math.round(width * scale)); const fieldH = Math.max(2, Math.round(height * scale));
      displacementTarget.setSize(fieldW, fieldH); compositeUniforms.uTexel.value = [1 / fieldW, 1 / fieldH];
      requestRender();
    };
    const ro = new ResizeObserver(resize); ro.observe(mount); resize();
    const setNewWave = (x, y, power) => { const cfg = configRef.current; const wave = waves[current]; current = (current + 1) % MAX_WAVES; wave.x = x; wave.y = y; wave.scale = START_SCALE * power; wave.target = START_SCALE * Math.max(1, cfg.spread) * power; wave.size = Math.max(1, cfg.brushSize); wave.opacity = 1; requestRender(); };
    const localPoint = (clientX, clientY) => { const rect = mount.getBoundingClientRect(); if (!rect.width || !rect.height || clientX < rect.left || clientX > rect.right || clientY < rect.top || clientY > rect.bottom) return null; return [clientX - rect.left, rect.height - (clientY - rect.top)]; };
    let previousX = 0; let previousY = 0;
    const onMove = (event) => { const cfg = configRef.current; if (!cfg.enabled || reduceMotion || cfg.trigger === "click") return; const point = localPoint(event.clientX, event.clientY); if (!point) return; const step = Math.max(1, cfg.spacing); if (Math.abs(point[0] - previousX) > step || Math.abs(point[1] - previousY) > step) { setNewWave(point[0], point[1], 1); previousX = point[0]; previousY = point[1]; } };
    const onDown = (event) => { const cfg = configRef.current; if (!cfg.enabled || reduceMotion || cfg.trigger === "hover") return; const point = localPoint(event.clientX, event.clientY); if (point) setNewWave(point[0], point[1], Math.max(1, cfg.clickStrength)); };
    window.addEventListener("pointermove", onMove, { passive: true }); window.addEventListener("pointerdown", onDown, { passive: true });
    const loop = (now) => {
      raf = 0;
      if (disposed || !isVisible || isScrolling || document.hidden) { previousTime = 0; return; }
      const delta = previousTime ? Math.min(0.05, (now - previousTime) / 1000) : 0; previousTime = now; const cfg = configRef.current;
      if (useVideo && mediaEl && mediaEl.readyState >= 2) { if (!imageTexture.image) imageTexture.image = mediaEl; imageTexture.needsUpdate = true; }
      const motionAllowed = cfg.enabled && !reduceMotion;
      const growth = motionAllowed ? 1 - Math.exp(-delta * 1.09) : 0; const decay = motionAllowed ? Math.exp((-delta * LIFE_CONSTANT) / Math.max(0.15, cfg.fade)) : 0;
      for (let i = 0; i < MAX_WAVES; i += 1) { const wave = waves[i]; if (wave.opacity <= 0) { opacities[i] = 0; continue; } wave.opacity *= decay; wave.scale += (wave.target - wave.scale) * growth; if (wave.opacity < 0.002) { wave.opacity = 0; opacities[i] = 0; continue; } const half = wave.scale * wave.size / 2; offsets[i * 2] = wave.x / width * 2 - 1; offsets[i * 2 + 1] = wave.y / height * 2 - 1; scales[i * 2] = half / width * 2; scales[i * 2 + 1] = half / height * 2; opacities[i] = wave.opacity; }
      geometry.attributes.iOffset.needsUpdate = true; geometry.attributes.iScale.needsUpdate = true; geometry.attributes.iOpacity.needsUpdate = true;
      renderer.render({ scene: waveMesh, target: displacementTarget, clear: true }); renderer.render({ scene: compositeMesh });
      const hasActiveWaves = waves.some((wave) => wave.opacity > 0);
      const shouldContinue = hasActiveWaves || (useVideo && motionAllowed && mediaEl?.readyState >= 2 && !mediaEl.paused);
      if (shouldContinue) raf = requestAnimationFrame(loop);
      else previousTime = 0;
    };
    requestRender = () => {
      if (!disposed && isVisible && !isScrolling && !document.hidden && !raf) raf = requestAnimationFrame(loop);
    };
    updatePlayback = () => {
      if (!useVideo || !mediaEl) return;
      const shouldPlay = configRef.current.enabled && !reduceMotion && isVisible && !isScrolling && !document.hidden;
      if (shouldPlay) {
        const playPromise = mediaEl.play();
        if (playPromise?.catch) playPromise.catch(() => {});
      } else mediaEl.pause();
      requestRender();
    };
    const visibilityObserver = typeof IntersectionObserver === "undefined" ? null : new IntersectionObserver(([entry]) => {
      isVisible = Boolean(entry?.isIntersecting);
      if (!isVisible && raf) { cancelAnimationFrame(raf); raf = 0; previousTime = 0; }
      updatePlayback();
    });
    visibilityObserver?.observe(mount);
    const onVisibilityChange = () => updatePlayback();
    const onScroll = () => {
      isScrolling = true;
      if (raf) { cancelAnimationFrame(raf); raf = 0; previousTime = 0; }
      if (useVideo) mediaEl?.pause();
      window.clearTimeout(scrollResumeTimer);
      scrollResumeTimer = window.setTimeout(() => { isScrolling = false; updatePlayback(); requestRender(); }, 500);
    };
    document.addEventListener("visibilitychange", onVisibilityChange);
    window.addEventListener("scroll", onScroll, { passive: true });
    updatePlayback();
    requestRender();
    return () => { disposed = true; cancelAnimationFrame(raf); window.clearTimeout(scrollResumeTimer); ro.disconnect(); visibilityObserver?.disconnect(); document.removeEventListener("visibilitychange", onVisibilityChange); window.removeEventListener("scroll", onScroll); window.removeEventListener("pointermove", onMove); window.removeEventListener("pointerdown", onDown); uniformsRef.current = null; if (useVideo && mediaEl) { mediaEl.pause(); mediaEl.removeAttribute("src"); mediaEl.load(); } if (canvas.parentNode === mount) mount.removeChild(canvas); gl.getExtension("WEBGL_lose_context")?.loseContext(); };
  }, [enabled, quality, src]);

  useEffect(() => {
    const uniforms = uniformsRef.current;
    if (!uniforms) return;
    uniforms.wave.uRings.value = rings; uniforms.composite.uStrength.value = strength; uniforms.composite.uSwirl.value = swirl; uniforms.composite.uDispersion.value = dispersion;
    uniforms.composite.uGlint.value = glint; uniforms.composite.uTintAmount.value = tintAmount; uniforms.composite.uGrayscale.value = grayscale ? 1 : 0; uniforms.composite.uHighlight.value = hexToRGB(highlightColor); uniforms.composite.uTint.value = hexToRGB(tint);
  }, [dispersion, glint, grayscale, highlightColor, rings, strength, swirl, tint, tintAmount]);

  return <div ref={mountRef} className={`ripple-distortion ${className}`.trim()} style={style} aria-hidden="true" />;
}
