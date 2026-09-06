import { useEffect, useRef } from "react";
import { Mesh, Program, Renderer, Triangle } from "ogl";
import "./ElasticMesh.css";

const vertexShader = `attribute vec2 position; attribute vec2 uv; varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position, 0., 1.); }`;

const fragmentShader = `
  precision highp float;
  varying vec2 vUv;
  uniform float uTime;
  uniform vec2 uResolution;
  void main() {
    vec2 uv = vUv;
    float ripple = sin(uv.x * 16.0 + uTime) * sin(uv.y * 13.0 - uTime * .8) * .018;
    uv += ripple;
    vec2 cells = abs(fract(uv * vec2(12., 8.) - .5) - .5);
    float grid = 1.0 - smoothstep(.035, .095, min(cells.x, cells.y));
    float glow = smoothstep(.8, .15, distance(uv, vec2(.74, .34)));
    vec3 color = mix(vec3(.31, .56, .96), vec3(.77, .48, .96), uv.y + ripple);
    color = mix(color, vec3(1.), glow * .55);
    float alpha = .08 + grid * .19 + glow * .18;
    gl_FragColor = vec4(color, alpha);
  }
`;

export default function ElasticMesh({ speed = 0.55, maxFps = 60, suspendWhileScrolling = true, ...props }) {
  const containerRef = useRef(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return undefined;

    const renderer = new Renderer({ alpha: true, dpr: Math.min(window.devicePixelRatio || 1, 1.5) });
    const gl = renderer.gl;
    const program = new Program(gl, {
      vertex: vertexShader,
      fragment: fragmentShader,
      transparent: true,
      uniforms: { uTime: { value: 0 }, uResolution: { value: [1, 1] } },
    });
    const mesh = new Mesh(gl, { geometry: new Triangle(gl), program });
    const resize = () => {
      const width = Math.max(1, container.clientWidth);
      const height = Math.max(1, container.clientHeight);
      renderer.setSize(width, height);
      program.uniforms.uResolution.value = [width, height];
    };

    resize();
    container.appendChild(gl.canvas);
    const observer = new ResizeObserver(resize);
    observer.observe(container);
    let animationId = 0;
    let lastRenderTime = -Infinity;
    let scrollPauseUntil = 0;
    const render = (time) => {
      const frameInterval = 1000 / Math.max(1, maxFps);
      if ((!suspendWhileScrolling || time >= scrollPauseUntil) && time - lastRenderTime >= frameInterval) {
        program.uniforms.uTime.value = time * 0.001 * speed;
        renderer.render({ scene: mesh });
        lastRenderTime = time;
      }
      animationId = window.requestAnimationFrame(render);
    };
    const handleScroll = () => { scrollPauseUntil = performance.now() + 140; };
    if (suspendWhileScrolling) window.addEventListener("scroll", handleScroll, { passive: true });
    animationId = window.requestAnimationFrame(render);

    return () => {
      window.cancelAnimationFrame(animationId);
      if (suspendWhileScrolling) window.removeEventListener("scroll", handleScroll);
      observer.disconnect();
      gl.canvas.remove();
      gl.getExtension("WEBGL_lose_context")?.loseContext();
    };
  }, [speed, maxFps, suspendWhileScrolling]);

  return <div ref={containerRef} className="elastic-mesh" {...props} />;
}
