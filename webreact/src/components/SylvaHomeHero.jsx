import { SylvaHero } from "@designcodeio/threeui";
import { useEffect, useRef } from "react";

const POINTER_MESSAGE = "campusmate:pointer";

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function postPointerToScene(frame, x, y, active = true) {
  frame?.contentWindow?.postMessage({ type: POINTER_MESSAGE, x, y, active }, window.location.origin);
}

function updateReactivePane(pane, clientX, clientY, x, y) {
  const rect = pane.getBoundingClientRect();
  const localX = clamp(((clientX - rect.left) / Math.max(1, rect.width)) * 100, 0, 100);
  const localY = clamp(((clientY - rect.top) / Math.max(1, rect.height)) * 100, 0, 100);
  const distance = Math.hypot(x - 0.5, y - 0.5) * 2;
  const nearPane = clientX >= rect.left - rect.width * 0.45 && clientX <= rect.right + rect.width * 0.45
    && clientY >= rect.top - rect.height * 0.45 && clientY <= rect.bottom + rect.height * 0.45;
  pane.style.setProperty("--pane-x", `${localX}%`);
  pane.style.setProperty("--pane-y", `${localY}%`);
  pane.style.setProperty("--pane-glow", nearPane ? String(0.28 - distance * 0.06) : "0.08");
  pane.style.setProperty("--pane-shift-x", `${(x - 0.5) * 5}px`);
  pane.style.setProperty("--pane-shift-y", `${(y - 0.5) * 3}px`);
}

/**
 * Sylva living-scene background.
 *
 * This component renders the Sylva three.js ecosystem scene as the fixed,
 * full-viewport background layer of the CampusMate home page. It never moves
 * with document scroll and never intercepts pointer events: all interactive
 * business content lives in the foreground layer above it.
 */
export default function SylvaHomeHero() {
  const heroRef = useRef(null);

  useEffect(() => {
    const hero = heroRef.current;
    const page = hero?.closest(".sylva-home-page");
    const frame = hero?.querySelector("iframe");
    if (!hero || !page || !frame) return undefined;

    const reducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;
    const finePointer = window.matchMedia?.("(hover: hover) and (pointer: fine)")?.matches ?? true;
    if (reducedMotion || !finePointer) return undefined;

    const panes = Array.from(page.querySelectorAll(".sylva-cursor-reactive"));
    const target = { x: 0.5, y: 0.42 };
    const current = { x: target.x, y: target.y };
    let animationFrame = 0;

    const publish = () => {
      animationFrame = 0;
      current.x += (target.x - current.x) * 0.16;
      current.y += (target.y - current.y) * 0.16;
      const dx = (current.x - 0.5) * 2;
      const dy = (current.y - 0.5) * 2;
      page.style.setProperty("--cursor-x", `${current.x * 100}%`);
      page.style.setProperty("--cursor-y", `${current.y * 100}%`);
      page.style.setProperty("--cursor-dx", String(dx));
      page.style.setProperty("--cursor-dy", String(dy));
      for (const pane of panes) updateReactivePane(pane, target.x * window.innerWidth, target.y * window.innerHeight, current.x, current.y);
      postPointerToScene(frame, current.x, current.y);
      if (Math.abs(target.x - current.x) > 0.001 || Math.abs(target.y - current.y) > 0.001) animationFrame = window.requestAnimationFrame(publish);
    };

    const schedule = (event) => {
      if (event.pointerType === "touch") return;
      target.x = clamp(event.clientX / Math.max(1, window.innerWidth), 0, 1);
      target.y = clamp(event.clientY / Math.max(1, window.innerHeight), 0, 1);
      if (!animationFrame) animationFrame = window.requestAnimationFrame(publish);
    };

    const reset = () => {
      target.x = 0.5;
      target.y = 0.42;
      if (!animationFrame) animationFrame = window.requestAnimationFrame(publish);
      postPointerToScene(frame, 0.5, 0.42, false);
    };

    const syncAfterLoad = () => postPointerToScene(frame, current.x, current.y);
    frame.addEventListener("load", syncAfterLoad);
    window.addEventListener("pointermove", schedule, { passive: true });
    window.addEventListener("pointerleave", reset, { passive: true });
    publish();

    return () => {
      window.cancelAnimationFrame(animationFrame);
      frame.removeEventListener("load", syncAfterLoad);
      window.removeEventListener("pointermove", schedule);
      window.removeEventListener("pointerleave", reset);
      postPointerToScene(frame, 0.5, 0.42, false);
    };
  }, []);

  return (
    <section ref={heroRef} className="sylva-home-hero sylva-scene-background" aria-hidden="true">
      <div className="sylva-cursor-aura" aria-hidden="true" />
      <div className="shader-frame">
        <SylvaHero
          variant="living-green"
          headingFont="lexend"
          bodyFont="lexend"
          headingWeight="300"
          bodyWeight="300"
          primaryColor="#ffffff"
          headingSize={63}
          bodySize={16.5}
          headingLetterSpacing={-0.006}
          style={{ pointerEvents: "none" }}
        />
      </div>
    </section>
  );
}
