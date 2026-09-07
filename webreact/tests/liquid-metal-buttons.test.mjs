import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const component = await readFile(new URL("../src/components/LiquidMetalButton.jsx", import.meta.url), "utf8");
const styles = await readFile(new URL("../src/styles/button-effects.css", import.meta.url), "utf8");
const overview = await readFile(new URL("../src/pages/home/SylvaCampusOverview.jsx", import.meta.url), "utf8");
const priority = await readFile(new URL("../src/pages/home/SylvaPriorityCard.jsx", import.meta.url), "utf8");
const schedule = await readFile(new URL("../src/pages/home/SylvaScheduleCard.jsx", import.meta.url), "utf8");

test("homepage CTA buttons use the reusable liquid-metal control", () => {
  assert.match(component, /getContext\("webgl2"/);
  assert.match(component, /uRippleTime/);
  assert.match(component, /pointerenter/);
  assert.match(component, /pointerdown/);
  assert.match(component, /prefers-reduced-motion/);
  assert.match(styles, /\.liquid-metal-canvas/);
  assert.match(styles, /\.liquid-metal-fallback/);
  assert.match(overview, /<LiquidMetalButton className="sylva-overview-primary"/);
  assert.match(overview, /<LiquidMetalButton className="sylva-overview-secondary"/);
  assert.match(priority, /<LiquidMetalButton className="sylva-card-link"/);
  assert.match(priority, /<LiquidMetalButton className="sylva-priority-more"/);
  assert.match(schedule, /<LiquidMetalButton className="sylva-card-link"/);
});
