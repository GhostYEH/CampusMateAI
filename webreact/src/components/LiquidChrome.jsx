import { useEffect, useRef } from "react";
import { Mesh, Program, Renderer, Triangle } from "ogl";
import "./LiquidChrome.css";

const vertexShader = `
  attribute vec2 position;
  attribute vec2 uv;
  varying vec2 vUv;

  void main() {
    vUv = uv;
    gl_Position = vec4(position, 0.0, 1.0);
  }
`;

const fragmentShader = `
  precision highp float;
  uniform float uTime;
  uniform vec3 uResolution;
  uniform vec3 uBaseColor;
  uniform float uAmplitude;
  uniform float uFrequencyX;
  uniform float uFrequencyY;
  uniform vec2 uMouse;
  varying vec2 vUv;

  vec4 renderImage(vec2 uvCoord) {
    vec2 fragCoord = uvCoord * uResolution.xy;
    vec2 uv = (2.0 * fragCoord - uResolution.xy) / min(uResolution.x, uResolution.y);

    for (float i = 1.0; i < 10.0; i++) {
      uv.x += uAmplitude / i * cos(i * uFrequencyX * uv.y + uTime + uMouse.x * 3.14159);
      uv.y += uAmplitude / i * cos(i * uFrequencyY * uv.x + uTime + uMouse.y * 3.14159);
    }

    vec2 diff = uvCoord - uMouse;
    float dist = length(diff);
    float falloff = exp(-dist * 20.0);
    float ripple = sin(10.0 * dist - uTime * 2.0) * 0.03;
    uv += (diff / (dist + 0.0001)) * ripple * falloff;

    vec3 color = uBaseColor / abs(sin(uTime - uv.y - uv.x));
    return vec4(color, 1.0);
  }

  void main() {
    vec4 color = vec4(0.0);
    int samples = 0;

    for (int i = -1; i <= 1; i++) {
      for (int j = -1; j <= 1; j++) {
        vec2 offset = vec2(float(i), float(j)) * (1.0 / min(uResolution.x, uResolution.y));
        color += renderImage(vUv + offset);
        samples++;
      }
    }

    gl_FragColor = color / float(samples);
  }
`;

export default function LiquidChrome({
  baseColor = [0.1, 0.1, 0.1],
  speed = 0.2,
  amplitude = 0.3,
  frequencyX = 3,
  frequencyY = 3,
  interactive = true,
  ...props
}) {
  const containerRef = useRef(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return undefined;

    const renderer = new Renderer({ antialias: true });
    const gl = renderer.gl;
    gl.clearColor(1, 1, 1, 1);
    const geometry = new Triangle(gl);
    const program = new Program(gl, {
      vertex: vertexShader,
      fragment: fragmentShader,
      uniforms: {
        uTime: { value: 0 },
        uResolution: { value: new Float32Array([1, 1, 1]) },
        uBaseColor: { value: new Float32Array(baseColor) },
        uAmplitude: { value: amplitude },
        uFrequencyX: { value: frequencyX },
        uFrequencyY: { value: frequencyY },
        uMouse: { value: new Float32Array([0.5, 0.5]) },
      },
    });
    const mesh = new Mesh(gl, { geometry, program });
    const reducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

    function resize() {
      const width = Math.max(1, container.offsetWidth);
      const height = Math.max(1, container.offsetHeight);
      renderer.setSize(width, height);
      const resolution = program.uniforms.uResolution.value;
      resolution[0] = gl.canvas.width;
      resolution[1] = gl.canvas.height;
      resolution[2] = gl.canvas.width / gl.canvas.height;
    }

    function updateMouse(clientX, clientY) {
      const rect = container.getBoundingClientRect();
      if (!rect.width || !rect.height) return;
      const mouse = program.uniforms.uMouse.value;
      mouse[0] = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
      mouse[1] = Math.max(0, Math.min(1, 1 - (clientY - rect.top) / rect.height));
    }

    function handleMouseMove(event) {
      updateMouse(event.clientX, event.clientY);
    }

    function handleTouchMove(event) {
      const touch = event.touches[0];
      if (touch) updateMouse(touch.clientX, touch.clientY);
    }

    function render(time) {
      program.uniforms.uTime.value = time * 0.001 * speed;
      renderer.render({ scene: mesh });
    }

    resize();
    container.appendChild(gl.canvas);
    window.addEventListener("resize", resize);
    if (interactive) {
      window.addEventListener("mousemove", handleMouseMove);
      window.addEventListener("touchmove", handleTouchMove, { passive: true });
    }

    let animationId;
    if (reducedMotion) {
      render(0);
    } else {
      const update = (time) => {
        render(time);
        animationId = requestAnimationFrame(update);
      };
      animationId = requestAnimationFrame(update);
    }

    return () => {
      if (animationId) cancelAnimationFrame(animationId);
      window.removeEventListener("resize", resize);
      if (interactive) {
        window.removeEventListener("mousemove", handleMouseMove);
        window.removeEventListener("touchmove", handleTouchMove);
      }
      gl.canvas.parentElement?.removeChild(gl.canvas);
      gl.getExtension("WEBGL_lose_context")?.loseContext();
    };
  }, [amplitude, baseColor[0], baseColor[1], baseColor[2], frequencyX, frequencyY, interactive, speed]);

  return <div ref={containerRef} className="liquidChrome-container" {...props} />;
}
