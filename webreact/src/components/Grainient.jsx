import { Mesh, Program, Renderer, Triangle } from "ogl";
import { useEffect, useRef, useState } from "react";
import "./Grainient.css";

const vertex = `
attribute vec2 position;
void main() { gl_Position = vec4(position, 0.0, 1.0); }
`;

const fragment = `
precision highp float;
uniform vec2 uResolution;
uniform float uTime;
uniform float uTimeSpeed;
uniform float uWarpStrength;
uniform float uGrainAmount;
uniform float uContrast;
uniform float uSaturation;
uniform vec3 uColor1;
uniform vec3 uColor2;
uniform vec3 uColor3;

float noise(vec2 point) {
  return fract(sin(dot(point, vec2(12.9898, 78.233))) * 43758.5453);
}

void main() {
  vec2 uv = gl_FragCoord.xy / uResolution.xy;
  float aspect = uResolution.x / max(uResolution.y, 1.0);
  vec2 field = (uv - .5) * vec2(aspect, 1.0);
  float time = uTime * uTimeSpeed;
  field += vec2(sin(field.y * 5.0 + time), cos(field.x * 4.0 - time * 1.3)) * (.045 * uWarpStrength);
  float firstBlend = smoothstep(-.62, .46, field.x + sin(field.y * 3.0 + time) * .16);
  float secondBlend = smoothstep(-.42, .58, field.y - cos(field.x * 2.5 - time) * .14);
  vec3 color = mix(uColor3, uColor2, firstBlend);
  color = mix(color, uColor1, secondBlend);
  float grain = noise(uv * uResolution.xy * .35 + time) - .5;
  color += grain * uGrainAmount;
  color = (color - .5) * uContrast + .5;
  float luminance = dot(color, vec3(.2126, .7152, .0722));
  color = mix(vec3(luminance), color, uSaturation);
  gl_FragColor = vec4(clamp(color, 0.0, 1.0), 1.0);
}
`;

function hexToRgb(hex) {
  const match = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  return match ? [1, 2, 3].map((index) => Number.parseInt(match[index], 16) / 255) : [1, 1, 1];
}

export default function Grainient({
  color1 = "#d9e7ff",
  color2 = "#9ab9ff",
  color3 = "#dcd8ff",
  timeSpeed = 0.16,
  warpStrength = 0.85,
  grainAmount = 0.045,
  contrast = 1.05,
  saturation = 0.82,
  paused = false,
  renderScale = 1,
  frameRate = 60,
  className = "",
}) {
  const containerRef = useRef(null);
  const [failed, setFailed] = useState(false);
  const safeRenderScale = Math.min(1, Math.max(.25, renderScale));
  const safeFrameRate = Math.min(60, Math.max(1, frameRate));

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return undefined;

    let animationFrame = 0;
    let renderer;
    let canvas;
    let resizeObserver;
    let intersectionObserver;
    let lastFrameTime = Number.NEGATIVE_INFINITY;

    try {
      renderer = new Renderer({ alpha: true, antialias: false, dpr: Math.min(window.devicePixelRatio || 1, 2) });
      const gl = renderer.gl;
      canvas = gl.canvas;
      const program = new Program(gl, {
        vertex,
        fragment,
        uniforms: {
          uResolution: { value: new Float32Array([1, 1]) }, uTime: { value: 0 },
          uTimeSpeed: { value: timeSpeed }, uWarpStrength: { value: warpStrength },
          uGrainAmount: { value: grainAmount }, uContrast: { value: contrast }, uSaturation: { value: saturation },
          uColor1: { value: new Float32Array(hexToRgb(color1)) }, uColor2: { value: new Float32Array(hexToRgb(color2)) }, uColor3: { value: new Float32Array(hexToRgb(color3)) },
        },
      });
      const mesh = new Mesh(gl, { geometry: new Triangle(gl), program });
      const resize = () => {
        renderer.setSize(
          Math.max(1, Math.round(container.clientWidth * safeRenderScale)),
          Math.max(1, Math.round(container.clientHeight * safeRenderScale)),
        );
        canvas.style.width = "100%";
        canvas.style.height = "100%";
        program.uniforms.uResolution.value[0] = gl.drawingBufferWidth;
        program.uniforms.uResolution.value[1] = gl.drawingBufferHeight;
        renderer.render({ scene: mesh });
      };
      const render = (time) => {
        if (time - lastFrameTime >= 1000 / safeFrameRate) {
          lastFrameTime = time;
          program.uniforms.uTime.value = time * .001;
          renderer.render({ scene: mesh });
        }
        animationFrame = window.requestAnimationFrame(render);
      };

      canvas.className = "grainient-canvas";
      container.appendChild(canvas);
      resizeObserver = new ResizeObserver(resize);
      resizeObserver.observe(container);
      resize();
      if (!paused) animationFrame = window.requestAnimationFrame(render);
      intersectionObserver = new IntersectionObserver(([entry]) => {
        if (!entry.isIntersecting && animationFrame) {
          window.cancelAnimationFrame(animationFrame);
          animationFrame = 0;
        } else if (entry.isIntersecting && !paused && !animationFrame) {
          animationFrame = window.requestAnimationFrame(render);
        }
      });
      intersectionObserver.observe(container);
    } catch {
      setFailed(true);
    }

    return () => {
      window.cancelAnimationFrame(animationFrame);
      resizeObserver?.disconnect();
      intersectionObserver?.disconnect();
      if (canvas?.parentNode === container) container.removeChild(canvas);
      renderer?.gl?.getExtension("WEBGL_lose_context")?.loseContext();
    };
  }, [color1, color2, color3, contrast, frameRate, grainAmount, paused, renderScale, safeFrameRate, safeRenderScale, saturation, timeSpeed, warpStrength]);

  return <div ref={containerRef} className={`grainient-container ${failed ? "is-fallback" : ""} ${className}`.trim()} aria-hidden="true" />;
}
