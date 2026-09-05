import { useEffect, useRef } from "react";
import { Mesh, Program, Renderer, Triangle } from "ogl";
import "./Prism.css";

export default function Prism({
  height = 3.5,
  baseWidth = 5.5,
  animationType = "rotate",
  glow = 1,
  offset = { x: 0, y: 0 },
  noise = 0.5,
  transparent = true,
  scale = 3.6,
  hueShift = 0,
  colorFrequency = 1,
  hoverStrength = 2,
  inertia = 0.05,
  bloom = 1,
  suspendWhenOffscreen = false,
  timeScale = 0.5,
  lightMode = false,
  paused = false,
  className = "",
}) {
  const containerRef = useRef(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return undefined;

    const H = Math.max(0.001, height);
    const BW = Math.max(0.001, baseWidth);
    const BASE_HALF = BW * 0.5;
    const GLOW = Math.max(0, glow);
    const NOISE = Math.max(0, noise);
    const offX = offset?.x ?? 0;
    const offY = offset?.y ?? 0;
    const SAT = transparent ? 1.5 : 1;
    const SCALE = Math.max(0.001, scale);
    const HUE = hueShift || 0;
    const CFREQ = Math.max(0, colorFrequency || 1);
    const BLOOM = Math.max(0, bloom || 1);
    const TS = Math.max(0, Number(timeScale) || 0);
    const HOVSTR = Math.max(0, hoverStrength || 1);
    const INERT = Math.max(0, Math.min(1, inertia || 0.12));
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const renderer = new Renderer({ dpr, alpha: transparent, antialias: false });
    const gl = renderer.gl;
    gl.disable(gl.DEPTH_TEST);
    gl.disable(gl.CULL_FACE);
    gl.disable(gl.BLEND);
    Object.assign(gl.canvas.style, { position: "absolute", inset: "0", width: "100%", height: "100%", display: "block" });
    container.appendChild(gl.canvas);

    const vertex = `
      attribute vec2 position;
      void main() { gl_Position = vec4(position, 0.0, 1.0); }
    `;
    const fragment = `
      precision highp float;
      uniform vec2 iResolution;
      uniform float iTime;
      uniform float uHeight;
      uniform float uBaseHalf;
      uniform mat3 uRot;
      uniform int uUseBaseWobble;
      uniform float uGlow;
      uniform vec2 uOffsetPx;
      uniform float uNoise;
      uniform float uSaturation;
      uniform float uScale;
      uniform float uHueShift;
      uniform float uColorFreq;
      uniform float uBloom;
      uniform float uCenterShift;
      uniform float uInvBaseHalf;
      uniform float uInvHeight;
      uniform float uMinAxis;
      uniform float uPxScale;
      uniform float uTimeScale;
      uniform float uLightMode;

      vec4 tanh4(vec4 x) {
        vec4 e2x = exp(2.0 * x);
        return (e2x - 1.0) / (e2x + 1.0);
      }
      float rand(vec2 co) {
        return fract(sin(dot(co, vec2(12.9898, 78.233))) * 43758.5453123);
      }
      float sdOctaAnisoInv(vec3 p) {
        vec3 q = vec3(abs(p.x) * uInvBaseHalf, abs(p.y) * uInvHeight, abs(p.z) * uInvBaseHalf);
        return (q.x + q.y + q.z - 1.0) * uMinAxis * 0.5773502691896258;
      }
      float sdPyramidUpInv(vec3 p) { return max(sdOctaAnisoInv(p), -p.y); }
      mat3 hueRotation(float a) {
        float c = cos(a), s = sin(a);
        mat3 W = mat3(0.299, 0.587, 0.114, 0.299, 0.587, 0.114, 0.299, 0.587, 0.114);
        mat3 U = mat3(0.701, -0.587, -0.114, -0.299, 0.413, -0.114, -0.300, -0.588, 0.886);
        mat3 V = mat3(0.168, -0.331, 0.500, 0.328, 0.035, -0.500, -0.497, 0.296, 0.201);
        return W + U * c + V * s;
      }
      void main() {
        vec2 f = (gl_FragCoord.xy - 0.5 * iResolution.xy - uOffsetPx) * uPxScale;
        float z = 5.0;
        float d = 0.0;
        vec3 p;
        vec4 o = vec4(0.0);
        mat2 wob = mat2(1.0);
        if (uUseBaseWobble == 1) {
          float t = iTime * uTimeScale;
          wob = mat2(cos(t), cos(t + 33.0), cos(t + 11.0), cos(t));
        }
        for (int i = 0; i < 100; i++) {
          p = vec3(f, z);
          p.xz = p.xz * wob;
          p = uRot * p;
          vec3 q = p;
          q.y += uCenterShift;
          d = 0.1 + 0.2 * abs(sdPyramidUpInv(q));
          z -= d;
          o += (sin((p.y + z) * uColorFreq + vec4(0.0, 1.0, 2.0, 3.0)) + 1.0) / d;
        }
        o = tanh4(o * o * (uGlow * uBloom) / 1e5);
        vec3 col = o.rgb;
        col += (rand(gl_FragCoord.xy + vec2(iTime)) - 0.5) * uNoise;
        col = clamp(col, 0.0, 1.0);
        float luminance = dot(col, vec3(0.2126, 0.7152, 0.0722));
        col = clamp(mix(vec3(luminance), col, uSaturation), 0.0, 1.0);
        if (abs(uHueShift) > 0.0001) col = clamp(hueRotation(uHueShift) * col, 0.0, 1.0);
        if (uLightMode > 0.5) {
          float peak = max(col.r, max(col.g, col.b));
          vec3 chroma = pow(clamp(col / max(peak, 0.0001), 0.0, 1.0), vec3(1.14));
          gl_FragColor = vec4(mix(vec3(1.0), chroma, o.a * 0.94), 1.0);
        } else {
          gl_FragColor = vec4(col, o.a);
        }
      }
    `;
    const geometry = new Triangle(gl);
    const iResBuf = new Float32Array(2);
    const offsetPxBuf = new Float32Array(2);
    const program = new Program(gl, {
      vertex,
      fragment,
      uniforms: {
        iResolution: { value: iResBuf }, iTime: { value: 0 }, uHeight: { value: H }, uBaseHalf: { value: BASE_HALF },
        uUseBaseWobble: { value: 1 }, uRot: { value: new Float32Array([1, 0, 0, 0, 1, 0, 0, 0, 1]) }, uGlow: { value: GLOW },
        uOffsetPx: { value: offsetPxBuf }, uNoise: { value: NOISE }, uSaturation: { value: SAT }, uScale: { value: SCALE },
        uHueShift: { value: HUE }, uColorFreq: { value: CFREQ }, uBloom: { value: BLOOM }, uCenterShift: { value: H * 0.25 },
        uInvBaseHalf: { value: 1 / BASE_HALF }, uInvHeight: { value: 1 / H }, uMinAxis: { value: Math.min(BASE_HALF, H) },
        uPxScale: { value: 1 / ((gl.drawingBufferHeight || 1) * 0.1 * SCALE) }, uTimeScale: { value: TS }, uLightMode: { value: lightMode ? 1 : 0 },
      },
    });
    const mesh = new Mesh(gl, { geometry, program });
    const resize = () => {
      renderer.setSize(container.clientWidth || 1, container.clientHeight || 1);
      iResBuf[0] = gl.drawingBufferWidth;
      iResBuf[1] = gl.drawingBufferHeight;
      offsetPxBuf[0] = offX * dpr;
      offsetPxBuf[1] = offY * dpr;
      program.uniforms.uPxScale.value = 1 / ((gl.drawingBufferHeight || 1) * 0.1 * SCALE);
    };
    const ro = new ResizeObserver(resize);
    ro.observe(container);
    resize();

    const rotBuf = new Float32Array(9);
    const setRotation = (yawY, pitchX, rollZ, out) => {
      const cy = Math.cos(yawY), sy = Math.sin(yawY), cx = Math.cos(pitchX), sx = Math.sin(pitchX), cz = Math.cos(rollZ), sz = Math.sin(rollZ);
      out[0] = cy * cz + sy * sx * sz; out[1] = cx * sz; out[2] = -sy * cz + cy * sx * sz;
      out[3] = -cy * sz + sy * sx * cz; out[4] = cx * cz; out[5] = sy * sz + cy * sx * cz;
      out[6] = sy * cx; out[7] = -sx; out[8] = cy * cx;
      return out;
    };
    const noNoise = NOISE < 1e-6;
    let raf = 0;
    const startRAF = () => { if (!raf && !paused) raf = requestAnimationFrame(render); };
    const stopRAF = () => { if (raf) cancelAnimationFrame(raf); raf = 0; };
    const random = () => Math.random();
    const wX = 0.3 + random() * 0.6, wY = 0.2 + random() * 0.7, wZ = 0.1 + random() * 0.5;
    const phX = random() * Math.PI * 2, phZ = random() * Math.PI * 2;
    let yaw = 0, pitch = 0, roll = 0, targetYaw = 0, targetPitch = 0;
    const lerp = (a, b, t) => a + (b - a) * t;
    const pointer = { x: 0, y: 0, inside: true };
    const onPointerMove = (event) => {
      if (animationType !== "hover") return;
      const nx = (event.clientX - window.innerWidth * 0.5) / Math.max(1, window.innerWidth * 0.5);
      const ny = (event.clientY - window.innerHeight * 0.5) / Math.max(1, window.innerHeight * 0.5);
      pointer.x = Math.max(-1, Math.min(1, nx)); pointer.y = Math.max(-1, Math.min(1, ny)); pointer.inside = true; startRAF();
    };
    const onLeave = () => { pointer.inside = false; };
    const render = (timeStamp) => {
      const time = (timeStamp - startTime) * 0.001;
      program.uniforms.iTime.value = time;
      let continueRAF = !paused;
      if (animationType === "hover") {
        targetYaw = (pointer.inside ? -pointer.x : 0) * 0.6 * HOVSTR;
        targetPitch = (pointer.inside ? pointer.y : 0) * 0.6 * HOVSTR;
        yaw = lerp(yaw, targetYaw, INERT); pitch = lerp(pitch, targetPitch, INERT); roll = lerp(roll, 0, 0.1);
        program.uniforms.uRot.value = setRotation(yaw, pitch, roll, rotBuf);
        if (noNoise && Math.abs(yaw - targetYaw) < 1e-4 && Math.abs(pitch - targetPitch) < 1e-4 && Math.abs(roll) < 1e-4) continueRAF = false;
      } else if (animationType === "3drotate") {
        const scaled = time * TS;
        yaw = scaled * wY; pitch = Math.sin(scaled * wX + phX) * 0.6; roll = Math.sin(scaled * wZ + phZ) * 0.5;
        program.uniforms.uRot.value = setRotation(yaw, pitch, roll, rotBuf);
        if (TS < 1e-6) continueRAF = false;
      } else {
        program.uniforms.uRot.value = setRotation(0, 0, 0, rotBuf);
        if (TS < 1e-6) continueRAF = false;
      }
      renderer.render({ scene: mesh });
      raf = continueRAF ? requestAnimationFrame(render) : 0;
    };
    const startTime = performance.now();
    if (animationType === "hover") {
      window.addEventListener("pointermove", onPointerMove, { passive: true });
      window.addEventListener("mouseleave", onLeave);
      program.uniforms.uUseBaseWobble.value = 0;
    } else if (animationType === "3drotate") {
      program.uniforms.uUseBaseWobble.value = 0;
    }
    let io;
    if (suspendWhenOffscreen) {
      io = new IntersectionObserver((entries) => entries.some((entry) => entry.isIntersecting) ? startRAF() : stopRAF());
      io.observe(container);
    }
    if (paused) render(startTime);
    else startRAF();

    return () => {
      stopRAF();
      ro.disconnect();
      io?.disconnect();
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("mouseleave", onLeave);
      if (gl.canvas.parentElement === container) container.removeChild(gl.canvas);
    };
  }, [animationType, baseWidth, bloom, colorFrequency, glow, height, hueShift, inertia, lightMode, noise, offset?.x, offset?.y, paused, scale, suspendWhenOffscreen, timeScale, transparent, hoverStrength]);

  return <div ref={containerRef} className={`prism-container ${className}`.trim()} aria-hidden="true" />;
}
