import { useEffect, useRef } from "react";

const vertexSource = `#version 300 es
in vec2 position;
void main() {
  gl_Position = vec4(position, 0.0, 1.0);
}`;

const fragmentSource = `#version 300 es
precision highp float;

out vec4 outColor;

uniform vec2 uResolution;
uniform float uTime;
uniform float uHover;
uniform float uPress;
uniform vec2 uPointer;
uniform vec2 uRipple;
uniform float uRippleTime;

float hash(vec2 p) {
  p = fract(p * vec2(123.34, 345.45));
  p += dot(p, p + 34.345);
  return fract(p.x * p.y);
}

float noise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  f = f * f * (3.0 - 2.0 * f);
  return mix(
    mix(hash(i), hash(i + vec2(1.0, 0.0)), f.x),
    mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), f.x),
    f.y
  ) * 2.0 - 1.0;
}

float fbm(vec2 p) {
  float value = 0.0;
  float amplitude = 0.58;
  for (int i = 0; i < 4; i++) {
    value += noise(p) * amplitude;
    p = p * 2.03 + 11.7;
    amplitude *= 0.5;
  }
  return value;
}

float sdPill(vec2 p, vec2 halfExtent, float radius) {
  vec2 q = abs(p) - halfExtent + radius;
  return min(max(q.x, q.y), 0.0) + length(max(q, 0.0)) - radius;
}

float softBand(float value) {
  float phase = fract(value);
  float edge = 0.055;
  float width = 0.44;
  return smoothstep(0.5 - width - edge, 0.5 - width, phase)
    * (1.0 - smoothstep(0.5 + width, 0.5 + width + edge, phase));
}

vec3 spectral(float value) {
  return clamp(vec3(1.5) - abs(4.0 * value - vec3(3.0, 2.0, 1.0)), 0.0, 1.0);
}

void main() {
  float aspect = uResolution.x / max(uResolution.y, 1.0);
  vec2 p = (gl_FragCoord.xy / uResolution - 0.5) * vec2(aspect, 1.0);
  vec2 halfExtent = vec2(aspect * 0.5, 0.5);
  float signedDistance = sdPill(p, halfExtent, 0.5);
  float edge = max(fwidth(signedDistance) * 1.5, 0.003);
  float mask = 1.0 - smoothstep(-edge, edge, signedDistance);
  if (mask < 0.001) {
    outColor = vec4(0.0);
    return;
  }

  float pointerDistance = length(p - uPointer);
  float pointerGlow = exp(-pointerDistance * pointerDistance * 8.5) * uHover;
  vec2 warped = p + normalize(p - uPointer + vec2(0.0001)) * pointerGlow * 0.085;
  float valley = noise(vec2(warped.x * 1.25, uTime * 0.12)) * 0.34;
  float density = 2.25 + 0.75 * noise(vec2(warped.x * 0.42 + 9.0, uTime * 0.08));
  float field = (warped.y - valley) * density;
  field += fbm(warped * vec2(1.4, 2.5) + vec2(uTime * 0.045, -uTime * 0.028)) * 0.08;

  float rippleAge = max(uTime - uRippleTime, 0.0);
  float rippleDistance = length(p - uRipple);
  float rippleFront = exp(-pow((rippleDistance - rippleAge * 0.95) / 0.075, 2.0))
    * exp(-rippleAge * 1.25);
  field += rippleFront * 0.34;

  vec3 reflection = vec3(0.0);
  vec3 weight = vec3(0.0);
  for (int i = 0; i < 15; i++) {
    float wavelength = float(i) / 14.0;
    vec3 spectrum = spectral(wavelength);
    float dispersion = (1.0 - pow(1.0 - wavelength, 1.5)) - 0.42;
    reflection += spectrum * softBand(field + dispersion * 0.34);
    weight += spectrum;
  }
  reflection /= max(weight, vec3(0.001));

  float rimTravel = 0.5 + 0.5 * sin(uTime * 0.85 + p.x * 3.0 - p.y * 2.0);
  float rim = 1.0 - smoothstep(0.0, 0.035, abs(signedDistance));
  float topLight = smoothstep(-0.15, 0.55, p.y);
  float intensity = 0.25 + uHover * 0.75 + uPress * 0.18;
  vec3 metal = mix(vec3(0.22, 0.30, 0.20), vec3(0.90, 0.96, 1.0), reflection);
  metal += vec3(0.25, 0.82, 0.64) * pointerGlow * 0.65;
  metal += vec3(0.56, 0.72, 1.0) * rippleFront * 0.65;
  metal += vec3(1.0) * rim * (0.10 + rimTravel * 0.22) * topLight;

  float alpha = mask * (0.12 + intensity * 0.48);
  alpha += rim * mask * (0.08 + uHover * 0.18);
  outColor = vec4(clamp(metal * intensity, 0.0, 1.0), clamp(alpha, 0.0, 0.82));
}`;

function createShader(gl, type, source) {
  const shader = gl.createShader(type);
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    const message = gl.getShaderInfoLog(shader) || "Liquid metal shader compilation failed";
    gl.deleteShader(shader);
    throw new Error(message);
  }
  return shader;
}

function createProgram(gl) {
  const program = gl.createProgram();
  const vertexShader = createShader(gl, gl.VERTEX_SHADER, vertexSource);
  const fragmentShader = createShader(gl, gl.FRAGMENT_SHADER, fragmentSource);
  gl.attachShader(program, vertexShader);
  gl.attachShader(program, fragmentShader);
  gl.bindAttribLocation(program, 0, "position");
  gl.linkProgram(program);
  gl.deleteShader(vertexShader);
  gl.deleteShader(fragmentShader);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
    const message = gl.getProgramInfoLog(program) || "Liquid metal program linking failed";
    gl.deleteProgram(program);
    throw new Error(message);
  }
  return program;
}

function localPoint(event, element) {
  const rect = element.getBoundingClientRect();
  const height = Math.max(rect.height, 1);
  return [
    (event.clientX - (rect.left + rect.width / 2)) / height,
    -(event.clientY - (rect.top + rect.height / 2)) / height,
  ];
}

export default function LiquidMetalButton({ children, className = "", ...props }) {
  const buttonRef = useRef(null);
  const canvasRef = useRef(null);

  useEffect(() => {
    const button = buttonRef.current;
    const canvas = canvasRef.current;
    if (!button || !canvas || typeof window === "undefined") return undefined;

    let gl;
    try {
      gl = canvas.getContext("webgl2", {
        alpha: true,
        antialias: false,
        premultipliedAlpha: true,
        powerPreference: "high-performance",
      });
    } catch {
      gl = null;
    }
    if (!gl) {
      button.classList.add("liquid-metal-fallback");
      return undefined;
    }

    let program;
    try {
      program = createProgram(gl);
    } catch {
      button.classList.add("liquid-metal-fallback");
      return undefined;
    }

    const vertexArray = gl.createVertexArray();
    const vertexBuffer = gl.createBuffer();
    gl.bindVertexArray(vertexArray);
    gl.bindBuffer(gl.ARRAY_BUFFER, vertexBuffer);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
    gl.enableVertexAttribArray(0);
    gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);

    const uniforms = {
      resolution: gl.getUniformLocation(program, "uResolution"),
      time: gl.getUniformLocation(program, "uTime"),
      hover: gl.getUniformLocation(program, "uHover"),
      press: gl.getUniformLocation(program, "uPress"),
      pointer: gl.getUniformLocation(program, "uPointer"),
      ripple: gl.getUniformLocation(program, "uRipple"),
      rippleTime: gl.getUniformLocation(program, "uRippleTime"),
    };

    const reducedMotionQuery = window.matchMedia?.("(prefers-reduced-motion: reduce)");
    let reducedMotion = reducedMotionQuery?.matches ?? false;
    let resizeObserver;
    let animationFrame = null;
    let width = 1;
    let height = 1;
    let hover = 0;
    let hoverTarget = 0;
    let press = 0;
    let pressTarget = 0;
    let pointer = [0, 0];
    let pointerSmooth = [0, 0];
    let ripple = [0, 0];
    let rippleTime = -99;
    let startTime = performance.now();
    let lastFrame = 0;

    const resize = () => {
      const rect = button.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      width = Math.max(2, Math.round(rect.width * dpr));
      height = Math.max(2, Math.round(rect.height * dpr));
      if (canvas.width !== width || canvas.height !== height) {
        canvas.width = width;
        canvas.height = height;
      }
    };

    const requestFrame = () => {
      if (animationFrame === null) animationFrame = window.requestAnimationFrame(render);
    };

    const render = (now) => {
      animationFrame = null;
      const frameDelta = Math.min(0.05, Math.max(0.001, (now - lastFrame) / 1000));
      const elapsed = (now - startTime) / 1000;
      if (lastFrame !== 0 && now - lastFrame < (reducedMotion ? 1000 : 33)) {
        requestFrame();
        return;
      }
      lastFrame = now;

      const ease = 1 - Math.pow(0.001, frameDelta);
      hover += (hoverTarget - hover) * ease;
      press += (pressTarget - press) * ease;
      pointerSmooth[0] += (pointer[0] - pointerSmooth[0]) * 0.18;
      pointerSmooth[1] += (pointer[1] - pointerSmooth[1]) * 0.18;

      resize();
      gl.viewport(0, 0, width, height);
      gl.useProgram(program);
      gl.bindVertexArray(vertexArray);
      gl.enable(gl.BLEND);
      gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
      gl.uniform2f(uniforms.resolution, width, height);
      gl.uniform1f(uniforms.time, reducedMotion ? 0 : elapsed);
      gl.uniform1f(uniforms.hover, hover);
      gl.uniform1f(uniforms.press, press);
      gl.uniform2f(uniforms.pointer, pointerSmooth[0], pointerSmooth[1]);
      gl.uniform2f(uniforms.ripple, ripple[0], ripple[1]);
      gl.uniform1f(uniforms.rippleTime, rippleTime);
      gl.drawArrays(gl.TRIANGLES, 0, 3);

      if (!reducedMotion || hoverTarget > 0 || pressTarget > 0 || Math.abs(hover - hoverTarget) > 0.001 || Math.abs(press - pressTarget) > 0.001) {
        requestFrame();
      }
    };

    const handlePointerEnter = (event) => {
      pointer = localPoint(event, button);
      hoverTarget = 1;
      requestFrame();
    };
    const handlePointerMove = (event) => {
      pointer = localPoint(event, button);
      requestFrame();
    };
    const handlePointerLeave = () => {
      hoverTarget = 0;
      requestFrame();
    };
    const handlePointerDown = (event) => {
      pointer = localPoint(event, button);
      ripple = pointer;
      rippleTime = (performance.now() - startTime) / 1000;
      pressTarget = 1;
      requestFrame();
    };
    const handlePointerUp = () => {
      pressTarget = 0;
      requestFrame();
    };
    const handleFocus = () => {
      if (button.matches(":focus-visible")) hoverTarget = 1;
      requestFrame();
    };
    const handleBlur = () => {
      hoverTarget = 0;
      pressTarget = 0;
      requestFrame();
    };
    const handleKeyDown = (event) => {
      if ((event.key === "Enter" || event.key === " ") && !event.repeat) {
        pressTarget = 1;
        ripple = [0, 0];
        rippleTime = (performance.now() - startTime) / 1000;
        requestFrame();
      }
    };
    const handleKeyUp = (event) => {
      if (event.key === "Enter" || event.key === " ") {
        pressTarget = 0;
        requestFrame();
      }
    };
    const handleMotionChange = (event) => {
      reducedMotion = event.matches;
      requestFrame();
    };

    button.addEventListener("pointerenter", handlePointerEnter);
    button.addEventListener("pointermove", handlePointerMove);
    button.addEventListener("pointerleave", handlePointerLeave);
    button.addEventListener("pointerdown", handlePointerDown);
    window.addEventListener("pointerup", handlePointerUp);
    window.addEventListener("pointercancel", handlePointerUp);
    button.addEventListener("focus", handleFocus);
    button.addEventListener("blur", handleBlur);
    button.addEventListener("keydown", handleKeyDown);
    button.addEventListener("keyup", handleKeyUp);
    reducedMotionQuery?.addEventListener("change", handleMotionChange);
    resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(button);
    resize();
    requestFrame();

    return () => {
      button.removeEventListener("pointerenter", handlePointerEnter);
      button.removeEventListener("pointermove", handlePointerMove);
      button.removeEventListener("pointerleave", handlePointerLeave);
      button.removeEventListener("pointerdown", handlePointerDown);
      window.removeEventListener("pointerup", handlePointerUp);
      window.removeEventListener("pointercancel", handlePointerUp);
      button.removeEventListener("focus", handleFocus);
      button.removeEventListener("blur", handleBlur);
      button.removeEventListener("keydown", handleKeyDown);
      button.removeEventListener("keyup", handleKeyUp);
      reducedMotionQuery?.removeEventListener("change", handleMotionChange);
      resizeObserver?.disconnect();
      if (animationFrame !== null) window.cancelAnimationFrame(animationFrame);
      gl.deleteBuffer(vertexBuffer);
      gl.deleteVertexArray(vertexArray);
      gl.deleteProgram(program);
    };
  }, []);

  return (
    <button ref={buttonRef} type="button" className={`liquid-metal-button ${className}`.trim()} {...props}>
      <canvas ref={canvasRef} className="liquid-metal-canvas" aria-hidden="true" />
      {children}
    </button>
  );
}
