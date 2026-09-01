import { gsap } from "gsap";
import { createMotionProfile, resolveReducedMotion } from "./motionPolicy";

const activeContexts = new WeakMap();

export function isReducedMotion(appReduced = false) {
  const systemReduced = typeof window !== "undefined"
    && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  const saveData = typeof navigator !== "undefined"
    && Boolean(navigator.connection?.saveData);
  return resolveReducedMotion({ appReduced, systemReduced, saveData });
}

function replaceContext(element, create) {
  activeContexts.get(element)?.revert();
  const context = gsap.context(create, element);
  activeContexts.set(element, context);
  return context;
}

function finishTransition(element, context, done) {
  context.revert();
  if (activeContexts.get(element) === context) activeContexts.delete(element);
  done();
}

export function animateRouteEnter(element, done, appReduced = false) {
  const profile = createMotionProfile(isReducedMotion(appReduced));
  if (!profile.route.enter.duration) {
    gsap.set(element, { clearProps: "opacity,visibility,transform" });
    done();
    return;
  }

  let context;
  context = replaceContext(element, () => {
    const children = Array.from(element.children).slice(0, 7);
    const timeline = gsap.timeline({
      defaults: { overwrite: "auto" },
      onComplete: () => finishTransition(element, context, done),
    });

    timeline.fromTo(
      element,
      { autoAlpha: 0, y: profile.route.enter.y },
      {
        autoAlpha: 1,
        y: 0,
        duration: profile.route.enter.duration,
        ease: profile.route.enter.ease,
      },
    );

    if (children.length > 1) {
      timeline.fromTo(
        children,
        { autoAlpha: 0.78, y: 8 },
        {
          autoAlpha: 1,
          y: 0,
          duration: 0.3,
          ease: "power2.out",
          stagger: 0.035,
        },
        "<0.1",
      );
    }
  });
}

export function animateRouteLeave(element, done, appReduced = false) {
  const profile = createMotionProfile(isReducedMotion(appReduced));
  if (!profile.route.leave.duration) {
    done();
    return;
  }

  let context;
  context = replaceContext(element, () => {
    gsap.to(element, {
      autoAlpha: 0,
      y: profile.route.leave.y,
      duration: profile.route.leave.duration,
      ease: profile.route.leave.ease,
      overwrite: "auto",
      onComplete: () => finishTransition(element, context, done),
    });
  });
}

export function animatePanelEnter(element, done, appReduced = false) {
  if (isReducedMotion(appReduced)) {
    done();
    return;
  }
  gsap.fromTo(
    element,
    { autoAlpha: 0, y: -10, scale: 0.985, transformOrigin: "top center" },
    {
      autoAlpha: 1,
      y: 0,
      scale: 1,
      duration: 0.24,
      ease: "power2.out",
      clearProps: "opacity,visibility,transform,transformOrigin",
      onComplete: done,
    },
  );
}

export function animatePanelLeave(element, done, appReduced = false) {
  if (isReducedMotion(appReduced)) {
    done();
    return;
  }
  gsap.to(element, {
    autoAlpha: 0,
    y: -6,
    scale: 0.99,
    duration: 0.14,
    ease: "power1.in",
    overwrite: "auto",
    onComplete: done,
  });
}
