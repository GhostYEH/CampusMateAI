import { useEffect, useRef } from "react";

const MIN_POINTS = 2;

function resolveColor(color) {
  if (!color.startsWith("var(")) return color;
  const tokenName = color.slice(4, -1).trim();
  return getComputedStyle(document.documentElement).getPropertyValue(tokenName).trim() || "#3267d6";
}

export default function SmoothCursor({
  className = "",
  pointsCount = 40,
  lineWidth = 0.3,
  springStrength = 0.4,
  dampening = 0.5,
  color = "#3267d6",
  blur = 0,
  mixBlendMode = "source-over",
  velocityScale = false,
  trailOpacity = 1,
  smoothFactor = 1,
  paused = false,
}) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const pointerMedia = window.matchMedia?.("(hover: hover) and (pointer: fine)");
    if (!canvas || paused || pointerMedia?.matches === false) return undefined;

    const context = canvas.getContext("2d");
    if (!context) return undefined;

    const pointer = { x: window.innerWidth / 2, y: window.innerHeight / 2, active: false };
    const points = [];
    const pointTotal = Math.max(MIN_POINTS, Math.round(pointsCount));
    const strokeColor = resolveColor(color);
    const spring = springStrength / Math.max(0.5, Math.min(2, smoothFactor));
    let animationFrame;
    let devicePixelRatio = 1;
    let viewportWidth = window.innerWidth;
    let viewportHeight = window.innerHeight;

    const seedPoints = () => {
      points.length = 0;
      for (let index = 0; index < pointTotal; index += 1) {
        points.push({ x: pointer.x, y: pointer.y, vx: 0, vy: 0 });
      }
    };

    const resize = () => {
      viewportWidth = window.innerWidth;
      viewportHeight = window.innerHeight;
      devicePixelRatio = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.round(viewportWidth * devicePixelRatio);
      canvas.height = Math.round(viewportHeight * devicePixelRatio);
      canvas.style.width = `${viewportWidth}px`;
      canvas.style.height = `${viewportHeight}px`;
      context.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0);
      seedPoints();
    };

    const handlePointerMove = (event) => {
      pointer.x = event.clientX;
      pointer.y = event.clientY;
      pointer.active = true;
    };

    const handleWindowBlur = () => {
      pointer.active = false;
    };

    const springPoint = (point, target) => {
      point.vx = (point.vx + (target.x - point.x) * spring) * dampening;
      point.vy = (point.vy + (target.y - point.y) * spring) * dampening;
      point.x += point.vx;
      point.y += point.vy;
    };

    const draw = () => {
      context.clearRect(0, 0, viewportWidth, viewportHeight);

      if (pointer.active) {
        springPoint(points[0], pointer);
        for (let index = 1; index < points.length; index += 1) {
          springPoint(points[index], points[index - 1]);
        }

        const speed = Math.min(2, Math.hypot(points[0].vx, points[0].vy) / 18);
        context.beginPath();
        context.moveTo(points[0].x, points[0].y);
        for (let index = 1; index < points.length - 1; index += 1) {
          const current = points[index];
          const next = points[index + 1];
          const midpointX = current.x + (next.x - current.x) * 0.5;
          const midpointY = current.y + (next.y - current.y) * 0.5;
          context.quadraticCurveTo(current.x, current.y, midpointX, midpointY);
        }
        const lastPoint = points[points.length - 1];
        context.lineTo(lastPoint.x, lastPoint.y);
        context.strokeStyle = strokeColor;
        context.lineWidth = Math.max(0.7, lineWidth * (velocityScale ? 1 + speed : 1));
        context.lineCap = "round";
        context.lineJoin = "round";
        context.globalAlpha = trailOpacity;
        context.globalCompositeOperation = mixBlendMode;
        context.filter = blur > 0 ? `blur(${blur}px)` : "none";
        context.stroke();
        context.globalAlpha = 1;
        context.globalCompositeOperation = "source-over";
        context.filter = "none";
      }

      animationFrame = window.requestAnimationFrame(draw);
    };

    resize();
    window.addEventListener("resize", resize, { passive: true });
    window.addEventListener("pointermove", handlePointerMove, { passive: true });
    window.addEventListener("blur", handleWindowBlur, { passive: true });
    animationFrame = window.requestAnimationFrame(draw);

    return () => {
      window.cancelAnimationFrame(animationFrame);
      window.removeEventListener("resize", resize);
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("blur", handleWindowBlur);
      context.clearRect(0, 0, viewportWidth, viewportHeight);
    };
  }, [blur, color, dampening, lineWidth, mixBlendMode, paused, pointsCount, springStrength, smoothFactor, trailOpacity, velocityScale]);

  return <canvas ref={canvasRef} className={`smooth-cursor-layer ${className}`.trim()} aria-hidden="true" />;
}
