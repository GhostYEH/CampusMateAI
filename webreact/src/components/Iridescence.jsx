import { Renderer, Program, Mesh, Color, Triangle } from "ogl";
import { useEffect, useRef, useState } from "react";
import "./Iridescence.css";

const vertexShader = `
attribute vec2 uv;
attribute vec2 position;

varying vec2 vUv;

void main() {
  vUv = uv;
  gl_Position = vec4(position, 0, 1);
}
`;

const fragmentShader = `
precision highp float;

uniform float uTime;
uniform vec3 uColor;
uniform vec3 uResolution;
uniform vec2 uMouse;
uniform float uAmplitude;
uniform float uSpeed;

varying vec2 vUv;

void main() {
  float mr = min(uResolution.x, uResolution.y);
  vec2 uv = (vUv.xy * 2.0 - 1.0) * uResolution.xy / mr;

  uv += (uMouse - vec2(0.5)) * uAmplitude;

  float d = -uTime * 0.5 * uSpeed;
  float a = 0.0;
  for (float i = 0.0; i < 8.0; ++i) {
    a += cos(i - d - a * uv.x);
    d += sin(uv.y * i + a);
  }
  d += uTime * 0.5 * uSpeed;
  vec3 col = vec3(cos(uv * vec2(d, a)) * 0.6 + 0.4, cos(a + d) * 0.5 + 0.5);
  col = cos(col * cos(vec3(d, a, 2.5)) * 0.5 + 0.5) * uColor;
  gl_FragColor = vec4(col, 1.0);
}
`;

export default function Iridescence(props) {
  const {
    color = [1, 1, 1],
    speed = 1,
    amplitude = 0.1,
    mouseReact = true,
    paused = false,
    ariaHidden = true,
    className = "",
    ...rest
  } = props;
  const containerRef = useRef(null);
  const mousePosition = useRef({ x: 0.5, y: 0.5 });
  const [webglFailed, setWebglFailed] = useState(false);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return undefined;

    setWebglFailed(false);
    let renderer;
    let gl;
    let program;
    let geometry;
    let mesh;
    let animationId = 0;

    try {
      renderer = new Renderer();
      gl = renderer.gl;
      gl.clearColor(1, 1, 1, 1);

      function resize() {
        renderer.setSize(container.offsetWidth, container.offsetHeight);
        if (program) {
          program.uniforms.uResolution.value = new Color(
            gl.canvas.width,
            gl.canvas.height,
            gl.canvas.width / Math.max(1, gl.canvas.height),
          );
        }
      }

      window.addEventListener("resize", resize, false);
      resize();

      geometry = new Triangle(gl);
      program = new Program(gl, {
        vertex: vertexShader,
        fragment: fragmentShader,
        uniforms: {
          uTime: { value: 0 },
          uColor: { value: new Color(...color) },
          uResolution: { value: new Color(gl.canvas.width, gl.canvas.height, gl.canvas.width / Math.max(1, gl.canvas.height)) },
          uMouse: { value: new Float32Array([mousePosition.current.x, mousePosition.current.y]) },
          uAmplitude: { value: amplitude },
          uSpeed: { value: speed },
        },
      });

      mesh = new Mesh(gl, { geometry, program });

      function render(time = 0) {
        program.uniforms.uTime.value = time * 0.001;
        renderer.render({ scene: mesh });
      }

      function update(time) {
        render(time);
        animationId = requestAnimationFrame(update);
      }

      container.appendChild(gl.canvas);
      render();
      if (!paused) animationId = requestAnimationFrame(update);

      function handleMouseMove(event) {
        const bounds = container.getBoundingClientRect();
        const x = (event.clientX - bounds.left) / Math.max(1, bounds.width);
        const y = 1 - (event.clientY - bounds.top) / Math.max(1, bounds.height);
        mousePosition.current = { x, y };
        program.uniforms.uMouse.value[0] = x;
        program.uniforms.uMouse.value[1] = y;
      }

      // The page content sits above this click-through background, so the
      // background element itself cannot receive mouse events.
      if (mouseReact && !paused) window.addEventListener("mousemove", handleMouseMove);

      return () => {
        cancelAnimationFrame(animationId);
        window.removeEventListener("resize", resize);
        if (mouseReact && !paused) window.removeEventListener("mousemove", handleMouseMove);
        if (gl?.canvas.parentNode === container) container.removeChild(gl.canvas);
        gl?.getExtension("WEBGL_lose_context")?.loseContext();
      };
    } catch {
      setWebglFailed(true);
      return undefined;
    }
  }, [color, speed, amplitude, mouseReact, paused]);

  return <div ref={containerRef} className={`iridescence-container ${className}${webglFailed ? " is-fallback" : ""}`} aria-hidden={ariaHidden} {...rest} />;
}
