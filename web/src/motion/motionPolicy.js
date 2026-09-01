export const MOTION_EASE = Object.freeze({
  emphasized: "power3.out",
  standard: "power2.out",
  exit: "power2.in",
  linear: "none",
});

export function resolveReducedMotion({
  appReduced = false,
  systemReduced = false,
  saveData = false,
} = {}) {
  return Boolean(appReduced || systemReduced || saveData);
}

export function createMotionProfile(reduced = false) {
  if (reduced) {
    return {
      route: {
        enter: { duration: 0, y: 0, ease: MOTION_EASE.standard },
        leave: { duration: 0, y: 0, ease: MOTION_EASE.exit },
      },
      hero: { duration: 0, y: 0, stagger: 0, ease: MOTION_EASE.standard },
      reveal: { duration: 0, y: 0, stagger: 0, ease: MOTION_EASE.standard },
      parallax: { yPercent: 0, scrub: false },
    };
  }

  return {
    route: {
      enter: { duration: 0.44, y: 18, ease: MOTION_EASE.emphasized },
      leave: { duration: 0.16, y: -8, ease: MOTION_EASE.exit },
    },
    hero: { duration: 0.56, y: 22, stagger: 0.07, ease: MOTION_EASE.emphasized },
    reveal: { duration: 0.5, y: 24, stagger: 0.055, ease: MOTION_EASE.emphasized },
    parallax: { yPercent: 7, scrub: 0.65 },
  };
}
