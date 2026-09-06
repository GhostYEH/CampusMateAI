import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { gsap } from "gsap";
import "./TargetCursor.css";

const REST_POSITIONS = [
  { x: -18, y: -18 },
  { x: 6, y: -18 },
  { x: 6, y: 6 },
  { x: -18, y: 6 },
];

export default function TargetCursor({
  targetSelector = "[data-target-cursor]",
  spinDuration = 2,
  hoverDuration = 0.2,
  hideDefaultCursor = true,
  cursorColor = "#b0b0e3",
  cursorColorOnTarget = "#8b43ce",
}) {
  const cursorRef = useRef(null);
  const dotRef = useRef(null);

  useEffect(() => {
    const cursor = cursorRef.current;
    const finePointer = window.matchMedia?.("(hover: hover) and (pointer: fine)");
    if (!cursor || finePointer?.matches === false) return undefined;

    const corners = Array.from(cursor.querySelectorAll(".target-cursor-corner"));
    const originalCursor = document.body.style.cursor;
    const pointer = { x: window.innerWidth / 2, y: window.innerHeight / 2 };
    let activeTarget = null;

    if (hideDefaultCursor) {
      document.body.classList.add("target-cursor-active");
    }

    gsap.set(cursor, { xPercent: -50, yPercent: -50, x: pointer.x, y: pointer.y });
    const spin = gsap.to(cursor, { rotation: 360, duration: spinDuration, ease: "none", repeat: -1 });

    const setTargetColor = (color) => {
      gsap.to(corners, { borderColor: color, duration: 0.15, overwrite: "auto" });
      gsap.to(dotRef.current, { backgroundColor: color, duration: 0.15, overwrite: "auto" });
    };

    const reset = () => {
      activeTarget = null;
      setTargetColor(cursorColor);
      gsap.to(corners, {
        x: (index) => REST_POSITIONS[index].x,
        y: (index) => REST_POSITIONS[index].y,
        duration: hoverDuration,
        ease: "power3.out",
        overwrite: "auto",
      });
      spin.resume();
    };

    const alignToTarget = (target, duration = hoverDuration) => {
      const rect = target.getBoundingClientRect();
      const cornerSize = 12;
      const border = 3;
      const positions = [
        { x: rect.left - pointer.x - border, y: rect.top - pointer.y - border },
        { x: rect.right - pointer.x - cornerSize + border, y: rect.top - pointer.y - border },
        { x: rect.right - pointer.x - cornerSize + border, y: rect.bottom - pointer.y - cornerSize + border },
        { x: rect.left - pointer.x - border, y: rect.bottom - pointer.y - cornerSize + border },
      ];
      gsap.to(corners, {
        x: (index) => positions[index].x,
        y: (index) => positions[index].y,
        duration,
        ease: "power2.out",
        overwrite: "auto",
      });
    };

    const handlePointerMove = (event) => {
      pointer.x = event.clientX;
      pointer.y = event.clientY;
      gsap.to(cursor, { x: pointer.x, y: pointer.y, duration: 0.1, ease: "power3.out", overwrite: "auto" });
      if (activeTarget) alignToTarget(activeTarget, 0.1);
    };

    const handlePointerOver = (event) => {
      const target = event.target.closest?.(targetSelector);
      if (!target || target === activeTarget) return;
      activeTarget = target;
      spin.pause();
      gsap.to(cursor, { rotation: 0, duration: 0.16, ease: "power2.out", overwrite: "auto" });
      setTargetColor(cursorColorOnTarget);
      alignToTarget(target);
    };

    const handlePointerOut = (event) => {
      if (!activeTarget || activeTarget.contains(event.relatedTarget)) return;
      if (event.target === activeTarget || event.target.closest?.(targetSelector) === activeTarget) reset();
    };

    const handleScroll = () => {
      if (activeTarget) alignToTarget(activeTarget, 0);
    };

    window.addEventListener("pointermove", handlePointerMove, { passive: true });
    window.addEventListener("pointerover", handlePointerOver, { passive: true });
    window.addEventListener("pointerout", handlePointerOut, { passive: true });
    window.addEventListener("scroll", handleScroll, { passive: true });

    return () => {
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerover", handlePointerOver);
      window.removeEventListener("pointerout", handlePointerOut);
      window.removeEventListener("scroll", handleScroll);
      spin.kill();
      gsap.killTweensOf([cursor, ...corners, dotRef.current]);
      document.body.classList.remove("target-cursor-active");
      document.body.style.cursor = originalCursor;
    };
  }, [cursorColor, cursorColorOnTarget, hideDefaultCursor, hoverDuration, spinDuration, targetSelector]);

  return createPortal(
    <div ref={cursorRef} className="target-cursor-wrapper" aria-hidden="true">
      <span ref={dotRef} className="target-cursor-dot" style={{ backgroundColor: cursorColor }} />
      <span className="target-cursor-corner target-cursor-corner--tl" style={{ borderColor: cursorColor }} />
      <span className="target-cursor-corner target-cursor-corner--tr" style={{ borderColor: cursorColor }} />
      <span className="target-cursor-corner target-cursor-corner--br" style={{ borderColor: cursorColor }} />
      <span className="target-cursor-corner target-cursor-corner--bl" style={{ borderColor: cursorColor }} />
    </div>,
    document.body,
  );
}
