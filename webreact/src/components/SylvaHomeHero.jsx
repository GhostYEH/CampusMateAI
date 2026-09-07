import { SylvaHero } from "@designcodeio/threeui";

/**
 * Sylva living-scene background.
 *
 * This component renders the Sylva three.js ecosystem scene as the fixed,
 * full-viewport background layer of the CampusMate home page. It never moves
 * with document scroll and never intercepts pointer events: all interactive
 * business content lives in the foreground layer above it.
 */
export default function SylvaHomeHero() {
  return (
    <section className="sylva-home-hero sylva-scene-background" aria-hidden="true">
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
