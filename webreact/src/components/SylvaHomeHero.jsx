import { useEffect, useRef } from "react";
import { SylvaHero } from "@designcodeio/threeui";

const SYLVA_DOCK_ROUTES = Object.freeze([
  "/home",
  "/courses",
  "/community",
  "/tasks",
  "/profile",
]);

export default function SylvaHomeHero({ onNavigate, onExplore }) {
  const heroRef = useRef(null);

  useEffect(() => {
    const iframe = heroRef.current?.querySelector("iframe");
    if (!iframe) return undefined;

    let removeFrameListeners = () => {};

    const connectFrameActions = () => {
      removeFrameListeners();

      const frameDocument = iframe.contentDocument;
      if (!frameDocument) return;

      const cleanups = [];
      const dockItems = [...frameDocument.querySelectorAll("[data-dock]")];
      dockItems.forEach((item, index) => {
        const route = SYLVA_DOCK_ROUTES[index];
        if (!route) return;
        const handleDockClick = (event) => {
          event.preventDefault();
          onNavigate(route);
        };
        item.addEventListener("click", handleDockClick);
        cleanups.push(() => item.removeEventListener("click", handleDockClick));
      });

      const exploreButton = frameDocument.querySelector(".liquid-button--explore");
      if (exploreButton) {
        const handleExplore = () => onExplore();
        exploreButton.addEventListener("click", handleExplore);
        cleanups.push(() => exploreButton.removeEventListener("click", handleExplore));
      }

      const playButton = frameDocument.querySelector(".liquid-button--play");
      if (playButton) {
        const handlePlay = () => onNavigate("/study");
        playButton.addEventListener("click", handlePlay);
        cleanups.push(() => playButton.removeEventListener("click", handlePlay));
      }

      removeFrameListeners = () => cleanups.forEach((cleanup) => cleanup());
    };

    iframe.addEventListener("load", connectFrameActions);
    if (iframe.contentDocument?.readyState === "complete") connectFrameActions();

    return () => {
      iframe.removeEventListener("load", connectFrameActions);
      removeFrameListeners();
    };
  }, [onExplore, onNavigate]);

  return (
    <section ref={heroRef} className="sylva-home-hero" aria-label="CampusMate 生态学习空间">
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
        />
      </div>
    </section>
  );
}
