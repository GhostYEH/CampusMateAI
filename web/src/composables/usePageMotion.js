import { nextTick, onBeforeUnmount, onMounted, unref, watch } from "vue";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { createMotionProfile } from "../motion/motionPolicy";
import { isReducedMotion } from "../motion/gsapMotion";

gsap.registerPlugin(ScrollTrigger);

export function usePageMotion({
  root,
  ready,
  reduceMotion,
  hero = [],
  reveal = "[data-motion-reveal]",
  parallax = "",
}) {
  let ctx;
  let buildVersion = 0;
  let motionQuery;

  function cleanup() {
    ctx?.revert();
    ctx = undefined;
  }

  async function build() {
    const version = ++buildVersion;
    await nextTick();
    if (version !== buildVersion) return;
    cleanup();

    const element = root.value;
    if (!element || !unref(ready)) return;
    const profile = createMotionProfile(isReducedMotion(unref(reduceMotion)));

    ctx = gsap.context((context) => {
      const heroTargets = hero.flatMap((selector) => gsap.utils.toArray(selector, element));
      const revealTargets = gsap.utils.toArray(reveal, element)
        .filter((target) => !heroTargets.includes(target));
      const parallaxTargets = parallax ? gsap.utils.toArray(parallax, element) : [];
      const allTargets = [...heroTargets, ...revealTargets, ...parallaxTargets];

      if (!profile.hero.duration) {
        gsap.set(allTargets, { clearProps: "opacity,visibility,transform" });
        return;
      }

      if (heroTargets.length) {
        gsap.timeline({ defaults: { overwrite: "auto" } }).fromTo(
          heroTargets,
          { autoAlpha: 0, y: profile.hero.y },
          {
            autoAlpha: 1,
            y: 0,
            duration: profile.hero.duration,
            ease: profile.hero.ease,
            stagger: profile.hero.stagger,
            clearProps: "opacity,visibility,transform",
          },
        );
      }

      if (revealTargets.length) {
        gsap.set(revealTargets, { autoAlpha: 0, y: profile.reveal.y });
        context.add("revealBatch", (batch) => gsap.to(batch, {
          autoAlpha: 1,
          y: 0,
          duration: profile.reveal.duration,
          ease: profile.reveal.ease,
          stagger: profile.reveal.stagger,
          overwrite: "auto",
          clearProps: "opacity,visibility,transform",
        }));
        ScrollTrigger.batch(revealTargets, {
          start: "top 88%",
          once: true,
          interval: 0.08,
          batchMax: 4,
          onEnter: context.revealBatch,
        });
      }

      if (parallaxTargets.length && window.innerWidth >= 960) {
        parallaxTargets.forEach((target) => {
          gsap.to(target, {
            yPercent: profile.parallax.yPercent,
            ease: "none",
            scrollTrigger: {
              trigger: target.closest("section") || element,
              start: "clamp(top bottom)",
              end: "clamp(bottom top)",
              scrub: profile.parallax.scrub,
              invalidateOnRefresh: true,
            },
          });
        });
      }
    }, element);

    ScrollTrigger.refresh();
  }

  function handleSystemMotionChange() {
    void build();
  }

  onMounted(() => {
    motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    motionQuery.addEventListener?.("change", handleSystemMotionChange);
    void build();
  });

  watch(
    [() => unref(ready), () => unref(reduceMotion)],
    () => { void build(); },
    { flush: "post" },
  );

  onBeforeUnmount(() => {
    buildVersion += 1;
    motionQuery?.removeEventListener?.("change", handleSystemMotionChange);
    cleanup();
  });
}
