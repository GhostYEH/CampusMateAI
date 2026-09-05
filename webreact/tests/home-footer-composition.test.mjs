import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(new URL("../src/components/HomeFooter.jsx", import.meta.url), "utf8");
const classicHome = await readFile(new URL("../src/pages/home/ClassicHome.jsx", import.meta.url), "utf8");

test("HomeFooter renders the page content passed by each homepage variant", () => {
  assert.match(source, /export default function HomeFooter\(\{ children, fixedBrand = false \}\)/);
  assert.match(source, /<div className="home-foreground">[\s\S]*\{children\}[\s\S]*<FooterInfo \/>/);
  assert.match(source, /home-brand-underlay/);
  assert.match(classicHome, /<HomeFooter fixedBrand>/);
});
